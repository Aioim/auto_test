import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Union
from playwright.sync_api import Page, Request, Response


class SyncNetworkCapture:
    """
    网络请求捕获工具，用于在指定操作期间捕获页面中的所有 HTTP 请求和响应。

    特性：
    - 支持捕获请求和响应的详细信息，包括头部、请求体、响应体等。
    - 可配置响应体截断大小，避免内存溢出。
    - 自动处理重定向链，记录中间请求/响应。
    - 支持上下文管理器 (`with` 语句) 和 `capture` 方法两种使用方式。
    - 按时间顺序返回捕获的数据。
    - 每次捕获后自动清空内部状态，避免数据累积。
    """

    # 默认二进制内容类型（响应体不读取）
    DEFAULT_BINARY_MIME_TYPES = {
        'image/', 'video/', 'audio/', 'application/octet-stream',
        'application/pdf', 'application/zip', 'application/gzip',
        'application/x-tar', 'application/x-bzip2', 'font/'
    }

    def __init__(
        self,
        page: Page,
        max_body_size: Optional[int] = 10240,           # 10KB 截断
        binary_mime_types: Optional[Set[str]] = None,
        wait_timeout: int = 5000                        # 默认等待网络空闲超时（毫秒）
    ):
        """
        初始化捕获器。

        :param page: Playwright 页面对象
        :param max_body_size: 响应体最大长度（字节），超过则截断；None 表示不截断
        :param binary_mime_types: 二进制 MIME 类型集合，命中则跳过响应体读取
        :param wait_timeout: 等待网络空闲的超时时间（毫秒），0 或 None 表示不等待
        """
        self.page = page
        self.max_body_size = max_body_size
        self.binary_mime_types = binary_mime_types or self.DEFAULT_BINARY_MIME_TYPES
        self.wait_timeout = wait_timeout

        # 存储请求和响应的数据，以请求对象为键
        self._requests: Dict[Request, Dict] = {}   # 请求对象 -> 请求信息
        self._responses: Dict[Request, Dict] = {}  # 请求对象 -> 响应信息

    def _is_binary_content(self, content_type: str) -> bool:
        """判断 Content-Type 是否属于二进制类型"""
        if not content_type:
            return False
        content_type_lower = content_type.lower()
        return any(content_type_lower.startswith(mime) for mime in self.binary_mime_types)

    def _safe_get_post_data(self, request: Request) -> Optional[str]:
        """安全获取请求体（文本形式）"""
        try:
            return request.post_data
        except Exception:
            return None

    def _safe_get_response_body(self, response: Response) -> Optional[str]:
        """安全获取响应体（文本形式），根据配置截断长度"""
        try:
            content_type = response.headers.get('content-type', '')
            if self._is_binary_content(content_type):
                return None

            body = response.text()
            if body is None:
                return None

            if self.max_body_size is not None and len(body) > self.max_body_size:
                body = body[:self.max_body_size] + '...(truncated)'
            return body
        except Exception:
            return None

    def _on_request(self, request: Request):
        """请求事件回调"""
        # 记录请求信息，包括重定向链
        info = {
            'url': request.url,
            'method': request.method,
            'headers': dict(request.headers),
            'post_data': self._safe_get_post_data(request),
            'timestamp': time.time(),
            'redirected_from': None,   # 将被填充（如果有）
        }

        # 处理重定向：如果这个请求是从另一个请求重定向来的
        if request.redirected_from:
            # 注意：redirected_from 是一个 Request 对象，我们存储它的 URL 以便追踪
            info['redirected_from'] = request.redirected_from.url

        self._requests[request] = info

    def _on_response(self, response: Response):
        """响应事件回调"""
        request = response.request
        if request not in self._requests:
            # 可能因某些原因没有捕获到请求（如监听器注册时机），忽略
            return

        # 构建响应信息
        resp_info = {
            'status': response.status,
            'status_text': response.status_text,
            'response_headers': dict(response.headers),
            'response_body': self._safe_get_response_body(response),
        }

        # 同样处理重定向链：如果这个响应是重定向的最终响应，可以记录来源
        if request.redirected_from:
            resp_info['redirected_from_url'] = request.redirected_from.url

        self._responses[request] = resp_info

    def _register_listeners(self):
        """注册事件监听器"""
        self.page.on('request', self._on_request)
        self.page.on('response', self._on_response)

    def _unregister_listeners(self):
        """移除事件监听器"""
        self.page.remove_listener('request', self._on_request)
        self.page.remove_listener('response', self._on_response)

    def _clear_data(self):
        """清空已存储的数据"""
        self._requests.clear()
        self._responses.clear()

    def _merge_results(self) -> List[Dict]:
        """
        合并请求与响应数据，并按时间戳排序返回。
        对于未收到响应的请求，响应字段为空字典。
        """
        results = []
        for req, req_info in self._requests.items():
            resp_info = self._responses.get(req, {})
            combined = {**req_info, **resp_info}
            results.append(combined)

        # 按时间戳排序
        results.sort(key=lambda x: x['timestamp'])
        return results

    def capture(self, action: Callable[[], Any], timeout: Optional[int] = None) -> List[Dict]:
        """
        在执行 action 期间捕获所有网络请求。

        :param action: 无参数的同步操作（如点击、填表单等）
        :param timeout: 等待网络空闲的超时时间（毫秒），覆盖实例默认值；None 使用实例设置，0 或 None 且实例为 0 则不等待
        :return: 捕获到的请求/响应列表，按时间排序
        :raises: 如果 action 执行过程中抛出异常，则会传播异常，但监听器会被正确清理
        """
        # 清空之前的数据
        self._clear_data()

        # 注册监听器
        self._register_listeners()

        try:
            # 执行用户操作
            action()

            # 等待网络空闲
            wait_timeout = timeout if timeout is not None else self.wait_timeout
            if wait_timeout and wait_timeout > 0:
                try:
                    self.page.wait_for_load_state('networkidle', timeout=wait_timeout)
                except Exception as e:
                    # 等待超时或出错时，不中断捕获，但记录警告（可选）
                    # 这里简单忽略，继续返回已捕获的数据
                    pass
        finally:
            # 无论成功或异常，都移除监听器
            self._unregister_listeners()

        # 合并结果并返回
        return self._merge_results()

    def reset(self):
        """重置内部状态，清除所有已捕获的数据"""
        self._clear_data()

    def __enter__(self):
        """进入上下文时注册监听器"""
        self._register_listeners()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时移除监听器，并清空数据（可选）"""
        self._unregister_listeners()
        self._clear_data()

    # 可选：提供属性以获取原始数据（便于调试）
    @property
    def requests(self) -> Dict[Request, Dict]:
        """返回原始请求数据（以请求对象为键）"""
        return self._requests.copy()

    @property
    def responses(self) -> Dict[Request, Dict]:
        """返回原始响应数据（以请求对象为键）"""
        return self._responses.copy()
    
def demo():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        capture = SyncNetworkCapture(page, max_body_size=5000)

        # 方式1：使用 capture 方法
        def action():
            page.goto('https://example.com')
            page.click('a')
        captured = capture.capture(action)
        for entry in captured:
            print(entry)
            print(entry['url'], entry.get('status'))
            break

        # 方式2：使用上下文管理器，手动控制捕获区域
        with capture:
            page.goto('https://httpbin.org/get')
            # 此时所有请求都会被记录
        # 退出 with 后数据自动清空

        browser.close()

if __name__ == '__main__':
    demo()