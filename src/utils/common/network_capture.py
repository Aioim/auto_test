from __future__ import annotations
import fnmatch
import json
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Union, Pattern, Tuple
from playwright.sync_api import Page, Request, Response, TimeoutError as PlaywrightTimeoutError
from utils.logger import logger


class NetworkCapture:
    """
    网络请求捕获工具，支持按 URL 过滤。

    过滤规则支持：
        - 字符串：使用 fnmatch 通配符（* 和 ?），例如 "https://api.example.com/*"
        - 正则表达式：使用 re.Pattern 对象或字符串（自动编译）
        - 可调用对象：接收 URL 字符串，返回布尔值
    多个规则之间为“或”关系，任一匹配即捕获。

    特性：
        - 可配置请求体/响应体截断大小，避免内存溢出。
        - 自动处理重定向链，记录中间请求/响应。
        - 支持上下文管理器 (`with` 语句) 和 `capture` 方法两种使用方式。
        - 按时间顺序返回捕获的数据。
        - 每次捕获后自动清空内部状态，避免数据累积。
        - 支持显式等待特定响应（使用 Playwright 原生 expect_response，零轮询延迟）。
        - 提供 attach/detach 方法管理生命周期，避免重复注册。
        - 支持 JSON 自动解析：若请求/响应的 Content-Type 为 JSON 且 body 未截断，则存储为 Python 对象。
        - 支持同一接口多次调用检测：可记录每个 (URL, method) 的出现次数，并在条目中添加序号和总次数。

    注意：本类不是线程安全的，应在同一线程中使用。
    """

    DEFAULT_BINARY_MIME_TYPES = {
        'image/', 'video/', 'audio/', 'application/octet-stream',
        'application/pdf', 'application/zip', 'application/gzip',
        'application/x-tar', 'application/x-bzip2', 'font/'
    }

    def __init__(
        self,
        page: Page,
        url_filters: Optional[Union[str, Pattern, Callable[[str], bool], List[Union[str, Pattern, Callable[[str], bool]]]]] = None,
        max_response_body_size: Optional[int] = 10240,
        max_request_body_size: Optional[int] = 1024,
        binary_mime_types: Optional[Set[str]] = None,
        wait_timeout: int = 15000,
        final_delay: float = 0.3,
        auto_attach: bool = True,
        parse_json: bool = True,
        track_duplicates: bool = True,
        url_normalizer: Optional[Callable[[str], str]] = None
    ):
        """
        初始化捕获器。

        :param page: Playwright 页面对象
        :param url_filters: URL 过滤规则，可以是单个规则或多个规则的列表
        :param max_response_body_size: 响应体最大长度（字符数），超过则截断；None 表示不截断
        :param max_request_body_size: 请求体最大长度（字符数），超过则截断；None 表示不截断
        :param binary_mime_types: 二进制 MIME 类型集合，命中则跳过响应体读取
        :param wait_timeout: 等待显式响应的超时时间（毫秒）
        :param final_delay: 捕获结束后额外的短暂延迟（秒），确保最后触发的监听完成
        :param auto_attach: 是否自动注册事件监听器（默认为 True）
        :param parse_json: 是否自动将 JSON 格式的请求/响应体解析为 Python 对象（默认为 True）
        :param track_duplicates: 是否启用同一接口多次调用检测（默认为 True）
        :param url_normalizer: 用于标准化 URL 的函数，例如移除查询参数。接收原始 URL 字符串，返回标准化后的字符串。
                                默认使用原始 URL（不标准化）。仅在 track_duplicates=True 时生效。
        """
        self.page = page
        self.max_response_body_size = max_response_body_size
        self.max_request_body_size = max_request_body_size
        self.wait_timeout = wait_timeout
        self.final_delay = final_delay
        self.parse_json = parse_json
        self.track_duplicates = track_duplicates
        self.url_normalizer = url_normalizer

        if binary_mime_types is None:
            self.binary_mime_types = set(self.DEFAULT_BINARY_MIME_TYPES)
        else:
            self.binary_mime_types = binary_mime_types

        self._filters: List[Callable[[str], bool]] = []
        if url_filters is not None:
            self.set_filters(url_filters)

        self._requests: Dict[Request, Dict] = {}
        self._responses: Dict[Request, Dict] = {}
        # 内部响应体缓存，避免重复读取
        self._response_body_cache: Dict[Response, Optional[Union[str, Any]]] = {}

        self._listeners_attached = False

        if auto_attach:
            self.attach()

    def attach(self):
        """注册事件监听器。如果已注册，则不做任何操作。"""
        if self._listeners_attached:
            return
        self.page.on('request', self._on_request)
        self.page.on('response', self._on_response)
        self._listeners_attached = True

    def detach(self):
        """注销事件监听器。忽略 KeyError 异常。"""
        if not self._listeners_attached:
            return
        try:
            self.page.remove_listener('request', self._on_request)
        except KeyError:
            logger.debug("Listener 'request' not found or already removed")
        try:
            self.page.remove_listener('response', self._on_response)
        except KeyError:
            logger.debug("Listener 'response' not found or already removed")
        self._listeners_attached = False

    def set_filters(self, filters: Union[str, Pattern, Callable[[str], bool], List[Union[str, Pattern, Callable[[str], bool]]]]):
        """设置 URL 过滤规则。"""
        if not isinstance(filters, list):
            filters = [filters]
        self._filters = []
        for f in filters:
            self._filters.append(self._compile_filter(f))

    def _compile_filter(self, pattern: Union[str, Pattern, Callable[[str], bool]]) -> Callable[[str], bool]:
        if callable(pattern) and not isinstance(pattern, (str, Pattern)):
            return pattern
        elif isinstance(pattern, Pattern):
            return lambda url: pattern.search(url) is not None
        elif isinstance(pattern, str):
            return lambda url: fnmatch.fnmatch(url, pattern)
        else:
            raise TypeError(f"Unsupported filter type: {type(pattern)}")

    def _should_capture(self, url: str) -> bool:
        if not self._filters:
            return True
        return any(f(url) for f in self._filters)

    def _is_binary_content(self, content_type: str) -> bool:
        if not content_type:
            return False
        content_type_lower = content_type.lower()
        return any(content_type_lower.startswith(mime) for mime in self.binary_mime_types)

    def _is_json_content(self, content_type: str) -> bool:
        """检查 Content-Type 是否为 JSON 类型。"""
        if not content_type or not self.parse_json:
            return False
        ct = content_type.lower()
        return ct.startswith('application/json') or '+json' in ct

    def _try_parse_json(self, body: str, content_type: str) -> Optional[Union[str, Any]]:
        """
        尝试将 body 解析为 JSON。如果解析成功且内容未被截断，返回解析后的对象；
        否则返回原始字符串（可能已截断）。注意：截断后的字符串通常不是合法 JSON，直接返回截断字符串。
        """
        if not self._is_json_content(content_type):
            return body

        if body.endswith('...(truncated)'):
            return body

        try:
            parsed = json.loads(body)
            return parsed
        except json.JSONDecodeError:
            return body

    def _safe_get_post_data(self, request: Request) -> Optional[Union[str, Any]]:
        try:
            body = request.post_data
            if body is None:
                return None

            truncated = False
            if self.max_request_body_size is not None and len(body) > self.max_request_body_size:
                body = body[:self.max_request_body_size] + '...(truncated)'
                truncated = True

            if not truncated and self.parse_json:
                content_type = request.headers.get('content-type', '')
                return self._try_parse_json(body, content_type)
            return body
        except Exception as e:
            logger.warning(f"Failed to read request body for {request.url}: {e}")
            return None

    def _safe_get_response_body(self, response: Response) -> Optional[Union[str, Any]]:
        if response in self._response_body_cache:
            return self._response_body_cache[response]

        try:
            content_type = response.headers.get('content-type', '')
            if self._is_binary_content(content_type):
                self._response_body_cache[response] = None
                return None

            body = response.text()
            if body is None:
                self._response_body_cache[response] = None
                return None

            truncated = False
            if self.max_response_body_size is not None and len(body) > self.max_response_body_size:
                body = body[:self.max_response_body_size] + '...(truncated)'
                truncated = True

            if not truncated and self.parse_json:
                parsed = self._try_parse_json(body, content_type)
                self._response_body_cache[response] = parsed
                return parsed
            else:
                self._response_body_cache[response] = body
                return body
        except Exception as e:
            logger.warning(f"Failed to read response body for {response.url}: {e}")
            self._response_body_cache[response] = None
            return None

    def _on_request(self, request: Request):
        if not self._should_capture(request.url):
            return
        info = {
            'url': request.url,
            'method': request.method,
            'headers': dict(request.headers),
            'post_data': self._safe_get_post_data(request),
            'timestamp': time.time(),
            'redirected_from': None,
        }
        if request.redirected_from:
            info['redirected_from'] = request.redirected_from.url
        self._requests[request] = info

    def _on_response(self, response: Response):
        request = response.request
        if request not in self._requests:
            return
        resp_info = {
            'status': response.status,
            'status_text': response.status_text,
            'response_headers': dict(response.headers),
            'response_body': self._safe_get_response_body(response),
        }
        if request.redirected_from:
            resp_info['redirected_from_url'] = request.redirected_from.url
        self._responses[request] = resp_info

    def _clear_data(self):
        self._requests.clear()
        self._responses.clear()
        self._response_body_cache.clear()

    def _merge_results(self) -> List[Dict]:
        results = []
        for req, req_info in self._requests.items():
            resp_info = self._responses.get(req, {})
            results.append({**req_info, **resp_info})
        results.sort(key=lambda x: x['timestamp'])
        return results

    def _build_entry_from_response(self, response: Response) -> Dict:
        """从 Response 对象构建完整的请求-响应条目（用于显式等待但未匹配过滤器的响应）。"""
        request = response.request
        req_info = {
            'url': request.url,
            'method': request.method,
            'headers': dict(request.headers),
            'post_data': self._safe_get_post_data(request),
            'timestamp': time.time(),
            'redirected_from': request.redirected_from.url if request.redirected_from else None,
        }
        resp_info = {
            'status': response.status,
            'status_text': response.status_text,
            'response_headers': dict(response.headers),
            'response_body': self._safe_get_response_body(response),
            'redirected_from_url': request.redirected_from.url if request.redirected_from else None,
        }
        return {**req_info, **resp_info}

    def _update_explicit_response_bodies(self, merged: List[Dict], matched_responses: List[Optional[Response]]):
        """对于显式等待到的响应，更新或补充其响应体。"""
        if not matched_responses:
            return

        explicit_map = {}
        for resp in matched_responses:
            if resp is None:
                continue
            key = (resp.url, resp.request.method)
            explicit_map[key] = resp

        for entry in merged:
            key = (entry.get('url'), entry.get('method'))
            if key in explicit_map:
                resp = explicit_map[key]
                body = self._safe_get_response_body(resp)
                entry['response_body'] = body
                logger.debug(f"Updated response body: {key[0]} length {len(body) if body else 0}")

        for resp in matched_responses:
            if resp is None:
                continue
            key = (resp.url, resp.request.method)
            exists = any(e.get('url') == key[0] and e.get('method') == key[1] for e in merged)
            if not exists:
                entry = self._build_entry_from_response(resp)
                merged.append(entry)
                logger.debug(f"Added missing explicit response entry: {key[0]}")

        merged.sort(key=lambda x: x.get('timestamp', 0))

    def _enrich_with_duplicate_info(self, entries: List[Dict]) -> List[Dict]:
        """
        为每个条目添加重复调用信息：occurrence（当前是第几次）、total_occurrences（总次数）。
        使用标准化后的 URL（如果提供了 url_normalizer）和 HTTP 方法作为键。
        """
        if not self.track_duplicates:
            return entries

        # 统计每个 (normalized_url, method) 的出现次数
        counter = defaultdict(int)
        for entry in entries:
            url = entry['url']
            method = entry['method']
            norm_url = self.url_normalizer(url) if self.url_normalizer else url
            key = (norm_url, method)
            counter[key] += 1

        # 再次遍历，为每个条目添加 occurrence（当前是第几次）
        occurrence_counter = defaultdict(int)
        enriched = []
        for entry in entries:
            url = entry['url']
            method = entry['method']
            norm_url = self.url_normalizer(url) if self.url_normalizer else url
            key = (norm_url, method)
            occurrence_counter[key] += 1
            new_entry = entry.copy()
            new_entry['duplicate_info'] = {
                'occurrence': occurrence_counter[key],
                'total_occurrences': counter[key],
                'normalized_url': norm_url
            }
            enriched.append(new_entry)
        return enriched

    def capture(
        self,
        action: Callable[[], Any],
        timeout: Optional[int] = None,
        wait_for_responses: Optional[Union[str, Pattern, List[Union[str, Pattern]]]] = None,
        additional_wait: Optional[Callable[[], None]] = None,
        ensure_response_body: bool = True,
    ) -> List[Dict]:
        """
        在执行 action 期间捕获所有网络请求。

        :param action: 无参数的同步操作（如点击、填表单等）
        :param timeout: 等待的超时时间（毫秒），覆盖实例默认值；None 使用实例设置
        :param wait_for_responses: 需要额外显式等待并强制读取完整响应体的 URL 模式列表
                                   （字符串通配符或正则表达式）。使用 Playwright 原生 expect_response，零延迟。
        :param additional_wait: 额外的自定义等待条件（如 page.wait_for_selector）
        :param ensure_response_body: 如果为 True，对于通过 wait_for_responses 捕获的响应，会使用
                                      response.text() 强制读取并替换原有响应体（可能因二进制而失败）。
        :param debug: 如果为 True，打印详细的匹配日志，用于排查问题
        :return: 捕获到的请求/响应列表，按时间排序。如果启用了 track_duplicates，每个条目会额外包含
                 'duplicate_info' 字段，包含 'occurrence'（当前调用序号）、'total_occurrences'（总调用次数）
                 和 'normalized_url'（标准化后的 URL）。
        """
        self._clear_data()

        if not self._listeners_attached:
            self.attach()

        matchers = []
        if wait_for_responses:
            if not isinstance(wait_for_responses, list):
                wait_for_responses = [wait_for_responses]
            for pattern in wait_for_responses:
                if isinstance(pattern, str):
                    matchers.append(lambda url, p=pattern: fnmatch.fnmatch(url, p))
                elif isinstance(pattern, Pattern):
                    matchers.append(lambda url, p=pattern: p.search(url) is not None)
                else:
                    raise TypeError(f"Unsupported wait_for_responses type: {type(pattern)}")

        effective_timeout = timeout if timeout is not None else self.wait_timeout
        matched_responses: List[Optional[Response]] = []
        contexts = []
        futures = []

        try:
            if matchers and effective_timeout > 0:
                for matcher in matchers:
                    cm = self.page.expect_response(
                        lambda resp, m=matcher: m(resp.url),
                        timeout=effective_timeout
                    )
                    future = cm.__enter__()
                    contexts.append(cm)
                    futures.append(future)

                action()

                matched_responses = []
                for idx, future in enumerate[Any](futures):
                    try:
                        resp = future.value
                        matched_responses.append(resp)
                        logger.debug(f"Explicitly matched response [{idx}]: {resp.url}")
                    except PlaywrightTimeoutError:
                        matched_responses.append(None)
                        logger.debug(f"Timeout waiting for response [{idx}]")
                    except Exception as e:
                        logger.warning(f"Unexpected error while getting response: {e}")
                        matched_responses.append(None)
            else:
                action()

            if additional_wait:
                additional_wait()

            if self.final_delay > 0:
                time.sleep(self.final_delay)

        finally:
            for cm in contexts:
                try:
                    cm.__exit__(None, None, None)
                except Exception as e:
                    logger.debug(f"Error exiting expect_response context: {e}")

            merged = self._merge_results()
            if ensure_response_body and matched_responses:
                self._update_explicit_response_bodies(merged, matched_responses)

        # 添加重复调用信息
        if self.track_duplicates:
            merged = self._enrich_with_duplicate_info(merged)

        return merged

    def reset(self):
        self._clear_data()

    def cleanup(self):
        self.detach()
        self._clear_data()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    @property
    def requests(self) -> Dict[Request, Dict]:
        return self._requests.copy()

    @property
    def responses(self) -> Dict[Request, Dict]:
        return self._responses.copy()

    def get_captured_data(self) -> List[Dict]:
        data = self._merge_results()
        if self.track_duplicates:
            data = self._enrich_with_duplicate_info(data)
        return data
    
    
def network_capture(page_or_getter=None, **capture_config):
    """
    装饰器工厂，支持普通函数和实例方法。

    用法：
        # 普通函数：直接传入 page 对象
        @sync_network_capture(page)
        def my_action():
            page.click("#btn")

        # 实例方法：自动从 self.page 获取
        class MyPage(BasePage):
            @sync_network_capture()
            def login(self):
                self.page.click("#login")

        # 实例方法：自定义 page 属性名
        @sync_network_capture(page_attr='browser_page')
        def do_something(self):
            self.browser_page.click("#btn")

    :param page_or_getter: Page 对象，或 None（表示自动从实例获取）
    :param capture_config: 其他配置（url_filters, parse_json, track_duplicates 等）
    """
    # 兼容旧调用方式：第一个参数可能是 page 对象或配置字典
    if callable(page_or_getter) and not isinstance(page_or_getter, Page):
        # 被直接用作装饰器 @sync_network_capture 而没有参数的情况
        func = page_or_getter
        return network_capture()(func)

    # 分离 capture 方法参数
    method_params = {}
    method_keys = {'timeout', 'wait_for_responses', 'additional_wait',
                   'ensure_response_body'}
    for key in method_keys:
        if key in capture_config:
            method_params[key] = capture_config.pop(key)

    page_attr = capture_config.pop('page_attr', 'page')  # 实例属性名，默认 'page'

    def decorator(func):
        def wrapper(*args, **kwargs):
            # 确定 page 对象
            if isinstance(page_or_getter, Page):
                page = page_or_getter
            else:
                # 假设第一个参数是 self（实例）
                if not args:
                    raise TypeError("实例方法必须至少有一个参数（self）")
                instance = args[0]
                page = getattr(instance, page_attr)
                if not isinstance(page, Page):
                    raise TypeError(f"{page_attr} 属性不是 Playwright Page 对象")

            with NetworkCapture(page, **capture_config) as capture:
                result = None
                def action():
                    nonlocal result
                    result = func(*args, **kwargs)
                captured = capture.capture(action, **method_params)
            return result, captured
        return wrapper
    return decorator