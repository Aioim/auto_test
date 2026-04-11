"""
BasePage - Page Object Pattern 基类（重构版）

提供通用的页面操作方法，通过 Mixin 组合各功能模块。
所有页面对象类应继承此类。
"""
from __future__ import annotations

import time
import re
import os
from contextlib import contextmanager
from typing import (
    Any, Callable, Dict, Generator, List, Literal, Optional, Tuple, Union, Pattern
)
from urllib.parse import urljoin, urlencode, urlparse, parse_qs, urlunparse

from playwright.sync_api import (
    Page, Locator, Response, Frame, TimeoutError as PlaywrightTimeoutError, expect as playwright_expect
)

from config import settings
from logger import logger
from core.selector import (
    SelectorHelper, Selector, SelectorLike, ResolveInfo, FrameNotFoundError
)


# ============================================================================
# Mixin 模块：按职责拆分功能
# ============================================================================

class NavigationMixin:
    """导航相关功能"""

    def goto(self, url: str, timeout: Optional[int] = None,
             wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load") -> Optional[Response]:
        """导航到指定 URL（支持相对路径拼接 base_url）"""
        if not url.startswith(("http://", "https://")) and self.base_url:
            url = urljoin(self.base_url, url)
        logger.info(f"Navigate to: {url}")
        start = time.time()
        response = self.page.goto(url, timeout=timeout, wait_until=wait_until)
        self._load_time = time.time() - start
        logger.info(f"Page loaded in {self._load_time:.2f}s")
        return response

    def reload(self, timeout: Optional[int] = None,
               wait_until: str = "load") -> Optional[Response]:
        logger.info("Reloading page...")
        return self.page.reload(timeout=timeout, wait_until=wait_until)

    def go_back(self, timeout: Optional[int] = None) -> None:
        logger.info("Going back...")
        self.page.go_back(timeout=timeout)

    def go_forward(self, timeout: Optional[int] = None) -> None:
        logger.info("Going forward...")
        self.page.go_forward(timeout=timeout)

    def current_url(self) -> str:
        return self.page.url

    def title(self) -> str:
        return self.page.title()


class ElementActionsMixin:
    """元素操作功能（点击、输入、获取属性等）"""

    # ----- 底层定位 -----
    def resolve(self, selector: SelectorLike) -> Locator:
        """解析选择器并返回 Locator（不等待）"""
        return SelectorHelper.resolve_locator(self.page, selector)

    def resolve_with_info(self, selector: SelectorLike) -> Tuple[Locator, ResolveInfo]:
        """返回 (Locator, ResolveInfo)"""
        return SelectorHelper.resolve_with_meta(self.page, selector)

    # ----- 查找与等待 -----
    def find(self, selector: SelectorLike,
             wait_for: Literal["visible", "hidden", "attached", "detached"] = "visible",
             timeout: Optional[int] = None,
             retries: Optional[int] = None,
             initial_delay: float = 0.5,
             backoff_factor: float = 2.0,
             max_delay: float = 5.0,
             **kwargs) -> Locator:
        """查找元素并等待到指定状态，支持重试退避"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        retries = retries if retries is not None else self.DEFAULT_RETRIES
        return SelectorHelper.find(
            self.page, selector, wait_for=wait_for,
            timeout=timeout, retries=retries,
            initial_delay=initial_delay, backoff_factor=backoff_factor,
            max_delay=max_delay, **kwargs
        )

    def exists(self, selector: SelectorLike,
               timeout: Optional[int] = None,
               retries: Optional[int] = None,
               **kwargs) -> bool:
        """
        检查元素是否存在（快速检查）
        注意：默认 timeout=None 时使用 100ms 快速失败，retries 默认为 1。
        若需要更可靠的检查，请显式传递 timeout 和 retries。
        """
        if timeout is None:
            timeout = 100  # 毫秒，快速失败
        retries = retries if retries is not None else 1
        return SelectorHelper.exists(
            self.page, selector, timeout=timeout, retries=retries, **kwargs
        )

    def wait_for(self, selector: SelectorLike,
                 state: Optional[Literal["attached", "detached", "hidden", "visible"]] = None,
                 timeout: Optional[int] = None) -> Locator:
        """等待元素达到指定状态"""
        locator = self.resolve(selector)
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator.wait_for(state=state, timeout=timeout)
        return locator

    # ----- 点击操作 -----
    def click(self, selector: SelectorLike,
              wait_for: str = "visible",
              timeout: Optional[int] = None,
              retries: Optional[int] = None,
              force: bool = False,
              no_wait_after: bool = False,
              position: Optional[Dict[str, float]] = None,
              modifiers: Optional[List[str]] = None,
              **kwargs) -> None:
        """点击元素"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        retries = retries if retries is not None else self.DEFAULT_RETRIES
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, retries=retries, **kwargs)
        opts = {"timeout": timeout, "force": force, "no_wait_after": no_wait_after}
        if position:
            opts["position"] = position
        if modifiers:
            opts["modifiers"] = modifiers
        logger.debug(f"Clicking element: {selector}")
        locator.click(**opts)

    def double_click(self, selector: SelectorLike,
                     wait_for: str = "visible",
                     timeout: Optional[int] = None,
                     force: bool = False,
                     **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        logger.debug(f"Double clicking element: {selector}")
        locator.dblclick(timeout=timeout, force=force)

    def right_click(self, selector: SelectorLike,
                    wait_for: str = "visible",
                    timeout: Optional[int] = None,
                    **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        logger.debug(f"Right clicking element: {selector}")
        locator.click(button="right", timeout=timeout)

    def hover(self, selector: SelectorLike,
              wait_for: str = "visible",
              timeout: Optional[int] = None,
              **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        logger.debug(f"Hovering over element: {selector}")
        locator.hover(timeout=timeout)

    # ----- 输入操作 -----
    def fill(self, selector: SelectorLike, value: str,
             wait_for: str = "visible",
             timeout: Optional[int] = None,
             retries: Optional[int] = None,
             **kwargs) -> None:
        """填充输入框（先清空再输入）"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        retries = retries if retries is not None else self.DEFAULT_RETRIES
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, retries=retries, **kwargs)
        logger.debug(f"Filling element with value: {value[:50]}")
        locator.fill(value, timeout=timeout)

    def type(self, selector: SelectorLike, text: str,
             wait_for: str = "visible",
             timeout: Optional[int] = None,
             delay: int = 0,
             **kwargs) -> None:
        """逐字符输入"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        logger.debug(f"Typing text: {text[:50]}")
        locator.type(text, delay=delay, timeout=timeout)

    def clear(self, selector: SelectorLike,
              wait_for: str = "visible",
              timeout: Optional[int] = None,
              **kwargs) -> None:
        """清空输入框"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        logger.debug("Clearing element")
        locator.clear(timeout=timeout)  # 修复：传递 timeout

    def press(self, selector: SelectorLike, key: str,
              wait_for: str = "visible",
              timeout: Optional[int] = None,
              **kwargs) -> None:
        """按下键盘按键"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        logger.debug(f"Pressing key: {key}")
        locator.press(key, timeout=timeout)

    def press_sequentially(self, selector: SelectorLike, text: str,
                           wait_for: str = "visible",
                           timeout: Optional[int] = None,
                           delay: int = 100,
                           **kwargs) -> None:
        """
        依次输入文本（支持功能键？建议仅用于普通字符）
        注意：如需输入功能键（如 Enter, Tab），请使用 press() 方法。
        """
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        locator.press_sequentially(text, delay=delay, timeout=timeout)

    # ----- 获取文本与属性 -----
    def text(self, selector: SelectorLike,
             wait_for: str = "visible",
             timeout: Optional[int] = None,
             **kwargs) -> str:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        return locator.inner_text()

    def all_texts(self, selector: SelectorLike,
                  wait_for: str = "attached",
                  timeout: Optional[int] = None,
                  **kwargs) -> List[str]:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        return locator.all_inner_texts()

    def attribute(self, selector: SelectorLike, name: str,
                  wait_for: str = "visible",
                  timeout: Optional[int] = None,
                  **kwargs) -> Optional[str]:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        return locator.get_attribute(name)

    def all_attributes(self, selector: SelectorLike, name: str,
                       wait_for: str = "attached",
                       timeout: Optional[int] = None,
                       **kwargs) -> List[Optional[str]]:
        """获取所有匹配元素的指定属性值列表"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        # 修复：使用 all() 遍历所有匹配元素
        elements = locator.all()
        return [el.get_attribute(name) for el in elements]

    # ----- 状态检查 -----
    def is_checked(self, selector: SelectorLike,
                   timeout: Optional[int] = None) -> bool:
        """检查复选框/单选框是否选中（超时返回 False）"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.resolve(selector)
        try:
            return locator.is_checked(timeout=timeout)
        except PlaywrightTimeoutError:
            logger.debug(f"Timeout checking if element is checked: {selector}")
            return False

    def is_visible(self, selector: SelectorLike,
                   timeout: Optional[int] = None) -> bool:
        """检查元素是否可见（超时返回 False）"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.resolve(selector)
        try:
            return locator.is_visible(timeout=timeout)
        except PlaywrightTimeoutError:
            logger.debug(f"Timeout checking if element is visible: {selector}")
            return False

    def is_enabled(self, selector: SelectorLike,
                   timeout: Optional[int] = None) -> bool:
        """检查元素是否启用（超时返回 False）"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.resolve(selector)
        try:
            return locator.is_enabled(timeout=timeout)
        except PlaywrightTimeoutError:
            logger.debug(f"Timeout checking if element is enabled: {selector}")
            return False

    def is_disabled(self, selector: SelectorLike,
                    timeout: Optional[int] = None) -> bool:
        return not self.is_enabled(selector, timeout)

    # ----- 表单操作 -----
    def select_option(self, selector: SelectorLike,
                      value: Union[str, List[str]],
                      wait_for: str = "visible",
                      timeout: Optional[int] = None,
                      **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        if isinstance(value, str):
            value = [value]
        logger.debug(f"Selecting options: {value}")
        locator.select_option(value, timeout=timeout)

    def upload_file(self, selector: SelectorLike,
                    file_path: Union[str, List[str]],
                    wait_for: str = "visible",
                    timeout: Optional[int] = None,
                    **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        if isinstance(file_path, str):
            file_path = [file_path]
        logger.debug(f"Uploading files: {file_path}")
        locator.set_input_files(file_path, timeout=timeout)

    def clear_file(self, selector: SelectorLike,
                   wait_for: str = "visible",
                   timeout: Optional[int] = None,
                   **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        logger.debug("Clearing uploaded files")
        locator.set_input_files([], timeout=timeout)


class AssertionMixin:
    """断言功能"""

    def assert_exists(self, selector: SelectorLike,
                      message: Optional[str] = None,
                      timeout: Optional[int] = None) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        exists = self.exists(selector, timeout=timeout, retries=1)  # 使用传入的 timeout
        msg = message or f"Element should exist: {selector}"
        assert exists, msg

    def assert_not_exists(self, selector: SelectorLike,
                          message: Optional[str] = None,
                          timeout: Optional[int] = None) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        exists = self.exists(selector, timeout=timeout, retries=1)
        msg = message or f"Element should not exist: {selector}"
        assert not exists, msg

    def assert_visible(self, selector: SelectorLike,
                       message: Optional[str] = None,
                       timeout: Optional[int] = None) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        visible = self.is_visible(selector, timeout=timeout)
        msg = message or f"Element should be visible: {selector}"
        assert visible, msg

    def assert_hidden(self, selector: SelectorLike,
                      message: Optional[str] = None,
                      timeout: Optional[int] = None) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        visible = self.is_visible(selector, timeout=timeout)
        msg = message or f"Element should be hidden: {selector}"
        assert not visible, msg

    def assert_text(self, selector: SelectorLike,
                    expected: str,
                    exact: bool = False,
                    message: Optional[str] = None,
                    timeout: Optional[int] = None,
                    **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        actual = self.text(selector, timeout=timeout, **kwargs)
        if exact:
            msg = message or f"Text should be exactly '{expected}', got '{actual}'"
            assert actual == expected, msg
        else:
            msg = message or f"Text should contain '{expected}', got '{actual}'"
            assert expected in actual, msg

    def assert_attribute(self, selector: SelectorLike,
                         name: str,
                         expected: str,
                         message: Optional[str] = None,
                         timeout: Optional[int] = None,
                         **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        actual = self.attribute(selector, name, timeout=timeout, **kwargs)
        msg = message or f"Attribute '{name}' should be '{expected}', got '{actual}'"
        assert actual == expected, msg


class WaitMixin:
    """等待相关功能"""

    def wait_for_url(self, url: Union[str, Pattern], timeout: Optional[int] = None) -> None:
        """
        等待 URL 匹配（支持字符串或正则表达式）
        注意：不支持 Callable，如需复杂匹配请使用 wait_for_function。
        """
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self.page.wait_for_url(url, timeout=timeout)

    def wait_for_load_state(self, state: Literal["load", "domcontentloaded", "networkidle"] = "networkidle",
                            timeout: Optional[int] = None) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self.page.wait_for_load_state(state, timeout=timeout)

    def wait_for_function(self, expression: str,
                          timeout: Optional[int] = None,
                          polling: Union[int, str] = "raf") -> Any:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        return self.page.wait_for_function(expression, timeout=timeout, polling=polling)

    def wait_for_timeout(self, timeout: int) -> None:
        self.page.wait_for_timeout(timeout)


class FrameMixin:
    """Frame 处理 - 支持上下文自动切换"""

    @contextmanager
    def frame_context(self, frame_name: Optional[str] = None,
                      frame_url: Optional[str] = None) -> Generator[None, None, None]:
        """
        切换到指定 Frame 的上下文管理器。
        在此上下文中，self.page 会临时替换为 Frame 对象，所有操作将在该 Frame 内执行。
        退出后自动恢复原 Page。
        """
        if frame_name:
            frame = self.page.frame(name=frame_name)
        elif frame_url:
            frame = next((f for f in self.page.frames if frame_url in (f.url or "")), None)
        else:
            raise ValueError("Either frame_name or frame_url must be provided")
        if not frame:
            raise FrameNotFoundError(f"Frame not found: {frame_name or frame_url}")
        original_page = self.page
        self.page = frame  # 临时替换为 Frame
        try:
            yield
        finally:
            self.page = original_page  # 恢复


class NetworkMixin:
    """网络请求与下载"""

    def get_api_response(
            self,
            url_matcher: Union[str, Pattern, Callable[[str], bool]],
            trigger_action: Callable[..., Any],
            *args: Any,
            timeout: Optional[float] = None,
            description: str = "unknown action",
            **kwargs: Any,
    ) -> Response:
        """
        执行触发操作并等待匹配的网络响应。
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        logger.debug(
            "[API Wait] Waiting for response matching %s while performing: %s (args=%s, kwargs=%s)",
            url_matcher, description, args, kwargs
        )
        try:
            with self.page.expect_response(url_matcher, timeout=timeout) as response_info:
                trigger_action(*args, **kwargs)
        except Exception as e:
            logger.error(
                "[API Wait] Trigger action '%s' failed before response could be captured: %s",
                description, e, exc_info=True
            )
            raise
        response = response_info.value
        logger.debug(
            "[API Wait] Successfully captured response for %s, status=%s",
            url_matcher, response.status
        )
        return response

    @contextmanager
    def capture_requests(self, urls: List[str]) -> Generator[List[Dict[str, Any]], None, None]:
        """捕获指定 URL 的请求数据"""
        captured = []

        def handler(request):
            for url in urls:
                if url in request.url:
                    captured.append({
                        "url": request.url,
                        "method": request.method,
                        "headers": dict(request.headers),
                        "post_data": request.post_data,
                        "timestamp": time.time()
                    })
                    logger.debug(f"Captured request: {request.method} {request.url}")
                    break

        self.page.on("request", handler)
        try:
            yield captured
        finally:
            self.page.off("request", handler)

    def download_file(self, selector: SelectorLike,
                      wait_for: str = "visible",
                      timeout: Optional[int] = None,
                      **kwargs) -> str:
        """
        下载文件并返回临时路径。
        注意：该临时文件在测试结束后可能被 Playwright 自动删除，建议立即读取或使用 download_file_to()。
        """
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        with self.page.expect_download(timeout=timeout) as download_info:
            self.click(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        download = download_info.value
        logger.info(f"File downloaded: {download.path()}")
        return download.path()

    def download_file_to(self, selector: SelectorLike,
                         target_path: str,
                         wait_for: str = "visible",
                         timeout: Optional[int] = None,
                         **kwargs) -> str:
        """下载文件并保存到指定路径"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        with self.page.expect_download(timeout=timeout) as download_info:
            self.click(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        download = download_info.value
        save_path = download.save_as(target_path)
        logger.info(f"File saved to: {save_path}")
        return save_path

    # ----- 发送请求（共享浏览器上下文）-----
    def send_request(self, method: str, url: str,
                     data: Optional[Dict[str, Any]] = None,
                     headers: Optional[Dict[str, str]] = None,
                     timeout: Optional[int] = None) -> Response:
        """发送 HTTP 请求（使用浏览器上下文）"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        if not url.startswith(("http://", "https://")) and self.base_url:
            url = urljoin(self.base_url, url)
        logger.info(f"Sending {method} request to: {url}")
        logger.debug(f"Request data: {data}")
        response = self.page.request.request(
            method=method,
            url=url,
            data=data,
            headers=headers,
            timeout=timeout
        )
        logger.info(f"Request completed with status: {response.status}")
        return response

    def _add_params_to_url(self, url: str, params: Dict[str, Any]) -> str:
        """安全地向 URL 添加查询参数（保留原有参数）"""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        # 合并新参数（注意 values 是列表形式）
        for key, value in params.items():
            query[key] = [str(value)]
        new_query = urlencode(query, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    def post_json(self, url: str, data: Dict[str, Any],
                  headers: Optional[Dict[str, str]] = None,
                  timeout: Optional[int] = None) -> Dict[str, Any]:
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        response = self.send_request("POST", url, data=data, headers=default_headers, timeout=timeout)
        if response.status < 200 or response.status >= 300:
            logger.error(f"POST request failed with status {response.status}: {response.text()}")
            raise Exception(f"Request failed with status {response.status}")
        try:
            return response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise

    def get_json(self, url: str,
                 params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None,
                 timeout: Optional[int] = None) -> Dict[str, Any]:
        if not url.startswith(("http://", "https://")) and self.base_url:
            url = urljoin(self.base_url, url)
        if params:
            url = self._add_params_to_url(url, params)  # 安全合并参数
        response = self.send_request("GET", url, headers=headers, timeout=timeout)
        if response.status < 200 or response.status >= 300:
            logger.error(f"GET request failed with status {response.status}: {response.text()}")
            raise Exception(f"Request failed with status {response.status}")
        try:
            return response.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise


class DialogMixin:
    """弹窗处理"""

    @contextmanager
    def expect_dialog(self, timeout: Optional[int] = None) -> Generator[Any, None, None]:
        """
        等待对话框出现的上下文管理器。
        用法：
            with page.expect_dialog() as dialog_info:
                page.click_trigger()
            dialog = dialog_info.value
            dialog.accept()
        """
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        with self.page.expect_event("dialog", timeout=timeout) as dialog_info:
            yield dialog_info

    def accept_dialog(self, timeout: Optional[int] = None) -> None:
        """接受对话框（需在触发对话框后调用）"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        dialog = self.page.wait_for_event("dialog", timeout=timeout)
        logger.info(f"Accepting dialog with message: {dialog.message}")
        dialog.accept()

    def dismiss_dialog(self, timeout: Optional[int] = None) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        dialog = self.page.wait_for_event("dialog", timeout=timeout)
        logger.info(f"Dismissing dialog with message: {dialog.message}")
        dialog.dismiss()

    def get_dialog_message(self, timeout: Optional[int] = None) -> str:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        dialog = self.page.wait_for_event("dialog", timeout=timeout)
        message = dialog.message
        logger.info(f"Got dialog message: {message}")
        return message

    def handle_dialog(self, accept: bool = True, timeout: Optional[int] = None) -> str:
        """处理对话框并返回消息"""
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        dialog = self.page.wait_for_event("dialog", timeout=timeout)
        message = dialog.message
        if accept:
            logger.info(f"Accepting dialog with message: {message}")
            dialog.accept()
        else:
            logger.info(f"Dismissing dialog with message: {message}")
            dialog.dismiss()
        return message


class ScrollMixin:
    """滚动操作"""

    def scroll_to(self, selector: SelectorLike,
                  wait_for: str = "visible",
                  timeout: Optional[int] = None,
                  **kwargs) -> None:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)
        locator.scroll_into_view_if_needed(timeout=timeout)

    def scroll_by(self, x: int = 0, y: int = 0) -> None:
        self.page.evaluate(f"window.scrollBy({x}, {y})")

    def scroll_to_top(self) -> None:
        self.page.evaluate("window.scrollTo(0, 0)")

    def scroll_to_bottom(self) -> None:
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")


class ScreenshotMixin:
    """截图与调试"""

    def screenshot(self, path: Optional[str] = None,
                   full_page: bool = False,
                   selector: Optional[SelectorLike] = None,
                   **kwargs) -> bytes:
        if selector:
            locator = self.resolve(selector)
            return locator.screenshot(path=path, **kwargs)
        else:
            return self.page.screenshot(path=path, full_page=full_page, **kwargs)

    def screenshot_on_failure(self, name: str = "failure", full_page: bool = True) -> None:
        """失败时截图（目录从配置读取，默认为 screenshots/）"""
        try:
            screenshot_dir = getattr(settings, "SCREENSHOT_DIR", "screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            timestamp = int(time.time() * 1000)
            path = os.path.join(screenshot_dir, f"{name}_{timestamp}.png")
            self.screenshot(path=path, full_page=full_page)
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}", exc_info=True)

    @contextmanager
    def auto_screenshot_on_error(self, name: str = "operation"):
        try:
            yield
        except Exception as e:
            # 排除系统级异常，避免被错误捕获
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            logger.error(f"{name} failed: {e}")
            self.screenshot_on_failure(name=name)
            raise

    def debug_info(self, selector: SelectorLike) -> Dict[str, Any]:
        """获取选择器的调试信息"""
        try:
            locator, info = self.resolve_with_info(selector)
            return {
                "strategy": info.strategy,
                "context": info.ctx,
                "attempts": info.attempts,
                "exists": locator.count() > 0 if hasattr(locator, "count") else None,
                "visible": locator.is_visible() if hasattr(locator, "is_visible") else None
            }
        except Exception as e:
            return {"error": str(e), "type": type(e).__name__}


class JavaScriptMixin:
    """JavaScript 执行"""

    def evaluate(self, expression: str, *args) -> Any:
        return self.page.evaluate(expression, *args)

    def evaluate_on_selector(self, selector: SelectorLike, expression: str, *args) -> Any:
        locator = self.resolve(selector)
        return locator.evaluate(expression, *args)


class ExpectMixin:
    """Playwright expect 断言封装（支持自动重试）"""

    def expect(self, selector: SelectorLike, **kwargs) -> Any:
        """
        返回 Playwright 的 expect 断言对象，支持链式调用。
        用法：self.expect(selector).to_be_visible()
        """
        locator = self.resolve(selector)
        return playwright_expect(locator, **kwargs)

    # ----- 常用断言快捷方法 -----
    def expect_visible(self, selector: SelectorLike, message: Optional[str] = None) -> None:
        """断言元素可见"""
        if message:
            self.expect(selector).to_be_visible(message=message)
        else:
            self.expect(selector).to_be_visible()

    def expect_hidden(self, selector: SelectorLike, message: Optional[str] = None) -> None:
        """断言元素不可见"""
        if message:
            self.expect(selector).to_be_hidden(message=message)
        else:
            self.expect(selector).to_be_hidden()

    def expect_enabled(self, selector: SelectorLike, message: Optional[str] = None) -> None:
        """断言元素启用"""
        if message:
            self.expect(selector).to_be_enabled(message=message)
        else:
            self.expect(selector).to_be_enabled()

    def expect_disabled(self, selector: SelectorLike, message: Optional[str] = None) -> None:
        """断言元素禁用"""
        if message:
            self.expect(selector).to_be_disabled(message=message)
        else:
            self.expect(selector).to_be_disabled()

    def expect_checked(self, selector: SelectorLike, message: Optional[str] = None) -> None:
        """断言复选框/单选框选中"""
        if message:
            self.expect(selector).to_be_checked(message=message)
        else:
            self.expect(selector).to_be_checked()

    def expect_text(self, selector: SelectorLike, expected: str, exact: bool = False,
                    message: Optional[str] = None) -> None:
        """断言元素文本包含或精确匹配"""
        locator = self.resolve(selector)
        if exact:
            if message:
                playwright_expect(locator).to_have_text(expected, message=message)
            else:
                playwright_expect(locator).to_have_text(expected)
        else:
            if message:
                playwright_expect(locator).to_contain_text(expected, message=message)
            else:
                playwright_expect(locator).to_contain_text(expected)

    def expect_value(self, selector: SelectorLike, expected: str, message: Optional[str] = None) -> None:
        """断言输入框的值"""
        locator = self.resolve(selector)
        if message:
            playwright_expect(locator).to_have_value(expected, message=message)
        else:
            playwright_expect(locator).to_have_value(expected)

    def expect_count(self, selector: SelectorLike, expected: int, message: Optional[str] = None) -> None:
        """断言匹配元素的数量"""
        locator = self.resolve(selector)
        if message:
            playwright_expect(locator).to_have_count(expected, message=message)
        else:
            playwright_expect(locator).to_have_count(expected)

    def expect_attribute(self, selector: SelectorLike, name: str, value: str, message: Optional[str] = None) -> None:
        """断言元素属性值"""
        locator = self.resolve(selector)
        if message:
            playwright_expect(locator).to_have_attribute(name, value, message=message)
        else:
            playwright_expect(locator).to_have_attribute(name, value)

    def expect_url(self, url: Union[str, re.Pattern], message: Optional[str] = None) -> None:
        """断言当前页面 URL"""
        if message:
            playwright_expect(self.page).to_have_url(url, message=message)
        else:
            playwright_expect(self.page).to_have_url(url)

    def expect_title(self, title: Union[str, re.Pattern], message: Optional[str] = None) -> None:
        """断言当前页面标题"""
        if message:
            playwright_expect(self.page).to_have_title(title, message=message)
        else:
            playwright_expect(self.page).to_have_title(title)


# ============================================================================
# BasePage 主类：继承所有 Mixin，组合功能
# ============================================================================

class BasePage(
    NavigationMixin,
    ElementActionsMixin,
    AssertionMixin,
    WaitMixin,
    FrameMixin,
    NetworkMixin,
    DialogMixin,
    ScrollMixin,
    ScreenshotMixin,
    JavaScriptMixin,
    ExpectMixin
):
    """页面对象基类 - 组合所有功能模块"""

    # 默认等待超时时间（毫秒）
    DEFAULT_TIMEOUT = 5000

    # 默认重试次数
    DEFAULT_RETRIES = 3

    def __init__(self, page: Page, base_url: Optional[str] = None):
        """
        初始化 BasePage

        Args:
            page: Playwright Page 对象
            base_url: 基础 URL（可选）
        """
        self.page = page
        self.base_url = base_url or getattr(settings, "BASE_URL", None)
        # 移除了未使用的 self.screenshot_helper

        # 页面元数据
        self._page_name = self.__class__.__name__
        self._load_time: Optional[float] = None

        # 控制台日志（可选监听）
        self._console_logs: List[str] = []
        self._console_handler = None  # 保存监听器引用，以便移除

    # ----- 控制台日志监听（可选）-----
    def start_console_listener(self) -> None:
        """开始监听控制台日志"""

        def handle_console(msg):
            self._console_logs.append(msg.text())

        self._console_handler = handle_console
        self.page.on("console", self._console_handler)
        logger.debug("Console listener started")

    def stop_console_listener(self) -> None:
        """停止监听控制台日志"""
        if self._console_handler:
            self.page.remove_listener("console", self._console_handler)
            self._console_handler = None
            logger.debug("Console listener stopped")

    def console_logs(self) -> List[str]:
        """获取控制台日志（需先启动监听）"""
        return self._console_logs

    # ----- 实用工具 -----
    @staticmethod
    def format_selector(selector: Selector, **kwargs) -> Selector:
        """格式化 Selector（替换模板变量）"""
        return selector.formatted(**kwargs)

    def get_page_load_time(self) -> Optional[float]:
        return self._load_time

    def get_page_name(self) -> str:
        return self._page_name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} url={self.current_url()}>"
