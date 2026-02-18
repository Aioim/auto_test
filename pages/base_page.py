"""
BasePage - Page Object Pattern 基类

提供通用的页面操作方法，封装 SelectorHelper 的能力。
所有页面对象类应继承此类。
"""
from __future__ import annotations

import typing

from utils.logger import logger
import time
from typing import Optional, Union, List, Dict, Any, Callable, Tuple, Literal
from contextlib import contextmanager
from playwright.sync_api import Page, Locator, Response, TimeoutError as PlaywrightTimeoutError
from utils.selector_helper import (
    SelectorHelper,
    Selector,
    SelectorLike,
    ResolveInfo,
    FrameNotFoundError,
)
from utils.screenshot_helper import ScreenshotHelper
from config import settings



class BasePage:
    """页面对象基类 - 封装通用的页面操作方法"""

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
        self.screenshot_helper = ScreenshotHelper(page)

        # 页面元数据
        self._page_name = self.__class__.__name__
        self._load_time: Optional[float] = None

    # ==================== 导航相关方法 ====================

    def goto(self, url: str, timeout: Optional[int] = None, wait_until: str = "load") -> Response:
        """
        导航到指定 URL

        Args:
            url: 目标 URL（如果是相对路径，会拼接 base_url）
            timeout: 超时时间（毫秒）
            wait_until: 等待状态（"load" | "domcontentloaded" | "networkidle" | "commit"）

        Returns:
            Response: 响应对象

        Raises:
            PlaywrightTimeoutError: 导航超时
        """
        from urllib.parse import urljoin

        # 如果是相对路径且有 base_url，拼接完整 URL
        if not url.startswith(("http://", "https://")) and self.base_url:
            url = urljoin(self.base_url, url)

        logger.info(f"Navigate to: {url}")

        start_time = time.time()
        response = self.page.goto(url, timeout=timeout, wait_until=wait_until)
        self._load_time = time.time() - start_time

        logger.info(f"Page loaded in {self._load_time:.2f}s")

        # 自动等待页面稳定
        if wait_until == "networkidle":
            self.page.wait_for_load_state("networkidle")

        return response

    def reload(self, timeout: Optional[int] = None, wait_until: str = "load") -> Response:
        """刷新当前页面"""
        logger.info("Reloading page...")
        return self.page.reload(timeout=timeout, wait_until=wait_until)

    def go_back(self, timeout: Optional[int] = None) -> None:
        """返回上一页"""
        logger.info("Going back...")
        self.page.go_back(timeout=timeout)

    def go_forward(self, timeout: Optional[int] = None) -> None:
        """前进到下一页"""
        logger.info("Going forward...")
        self.page.go_forward(timeout=timeout)

    def current_url(self) -> str:
        """获取当前 URL"""
        return self.page.url

    def title(self) -> str:
        """获取页面标题"""
        return self.page.title()

    # ==================== 元素定位与解析 ====================

    def resolve(self, selector: SelectorLike) -> Locator:
        """
        解析选择器并返回 Locator（不等待）

        Args:
            selector: Selector | str | Locator

        Returns:
            Locator: 定位器对象

        Raises:
            SelectorResolutionError: 选择器解析失败
            FrameNotFoundError: Frame 未找到
        """
        return SelectorHelper.resolve_locator(self.page, selector)

    def resolve_with_info(self, selector: SelectorLike) -> Tuple[Locator, ResolveInfo]:
        """
        解析选择器并返回 (Locator, ResolveInfo)

        Args:
            selector: Selector | str | Locator

        Returns:
            Tuple[Locator, ResolveInfo]: 定位器和解析信息

        Raises:
            SelectorResolutionError: 选择器解析失败
            FrameNotFoundError: Frame 未找到
        """
        return SelectorHelper.resolve_with_meta(self.page, selector)

    # ==================== 等待与查找 ====================

    def find(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        **kwargs
    ) -> Locator:
        """
        查找元素并等待其达到指定状态

        Args:
            selector: Selector | str | Locator
            wait_for: 等待状态（"visible" | "hidden" | "attached" | "detached"）
            timeout: 超时时间（毫秒）
            retries: 重试次数
            **kwargs: 传递给 SelectorHelper.find 的其他参数

        Returns:
            Locator: 定位器对象

        Raises:
            LocatorWaitTimeoutError: 等待超时
            SelectorResolutionError: 选择器解析失败
            FrameNotFoundError: Frame 未找到
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        retries = retries or self.DEFAULT_RETRIES

        return SelectorHelper.find(
            self.page,
            selector,
            wait_for=wait_for,
            timeout=timeout,
            retries=retries,
            **kwargs
        )

    def exists(
        self,
        selector: SelectorLike,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        **kwargs
    ) -> bool:
        """
        检查元素是否存在

        Args:
            selector: Selector | str | Locator
            timeout: 超时时间（毫秒），如果为 None 则快速检查
            retries: 重试次数
            **kwargs: 传递给 SelectorHelper.exists 的其他参数

        Returns:
            bool: 元素是否存在
        """
        retries = retries or 1

        return SelectorHelper.exists(
            self.page,
            selector,
            timeout=timeout,
            retries=retries,
            **kwargs
        )

    def wait_for(
        self,
        selector: SelectorLike,
        state:typing.Optional[
            Literal["attached", "detached", "hidden", "visible"]
        ] = None,
        timeout: Optional[int] = None
    ) -> Locator:
        """
        等待元素达到指定状态

        Args:
            selector: Selector | str | Locator
            state: 等待状态（"visible" | "hidden" | "attached" | "detached"）
            timeout: 超时时间（毫秒）

        Returns:
            Locator: 定位器对象
        """
        locator = self.resolve(selector)
        timeout = timeout or self.DEFAULT_TIMEOUT

        locator.wait_for(state=state, timeout=timeout)
        return locator

    def wait_for_url(
        self,
        url: Union[str, Callable[[str], bool]],
        timeout: Optional[int] = None
    ) -> None:
        """等待 URL 匹配"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        self.page.wait_for_url(url, timeout=timeout)

    def wait_for_load_state(
        self,
        state: str = "networkidle",
        timeout: Optional[int] = None
    ) -> None:
        """等待页面加载状态"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        self.page.wait_for_load_state(state, timeout=timeout)

    # ==================== 点击操作 ====================

    def click(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        force: bool = False,
        no_wait_after: bool = False,
        position: Optional[Dict[str, float]] = None,
        modifiers: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        """
        点击元素

        Args:
            selector: Selector | str | Locator
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            retries: 重试次数
            force: 强制点击（不检查可见性、可点击性等）
            no_wait_after: 点击后不等待导航
            position: 点击位置 {x, y}
            modifiers: 修饰键 ["Alt", "Control", "Meta", "Shift"]
            **kwargs: 传递给 find 的其他参数
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        retries = retries or self.DEFAULT_RETRIES

        locator = self.find(selector, wait_for=wait_for, timeout=timeout, retries=retries, **kwargs)

        click_options = {
            "timeout": timeout,
            "force": force,
            "no_wait_after": no_wait_after
        }

        if position:
            click_options["position"] = position
        if modifiers:
            click_options["modifiers"] = modifiers

        logger.debug(f"Clicking element: {selector}")
        locator.click(**click_options)

    def db_click(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        force: bool = False,
        **kwargs
    ) -> None:
        """双击元素"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        logger.debug(f"Double clicking element: {selector}")
        locator.dblclick(timeout=timeout, force=force)

    def right_click(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """右键点击元素"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        logger.debug(f"Right clicking element: {selector}")
        locator.click(button="right", timeout=timeout)

    def hover(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """鼠标悬停"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        logger.debug(f"Hovering over element: {selector}")
        locator.hover(timeout=timeout)

    # ==================== 输入操作 ====================

    def fill(
        self,
        selector: SelectorLike,
        value: str,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        force: bool = False,
        **kwargs
    ) -> None:
        """
        填充输入框（先清空再输入）

        Args:
            selector: Selector | str | Locator
            value: 输入值
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            retries: 重试次数
            force: 强制填充
            **kwargs: 传递给 find 的其他参数
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        retries = retries or self.DEFAULT_RETRIES

        locator = self.find(selector, wait_for=wait_for, timeout=timeout, retries=retries, **kwargs)

        logger.debug(f"Filling element with value: {value[:50]}")
        locator.fill(value, timeout=timeout, force=force)

    def type(
        self,
        selector: SelectorLike,
        text: str,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        delay: int = 0,
        **kwargs
    ) -> None:
        """
        模拟键盘输入（逐字符输入）

        Args:
            selector: Selector | str | Locator
            text: 输入文本
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            delay: 每个字符间的延迟（毫秒）
            **kwargs: 传递给 find 的其他参数
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        logger.debug(f"Typing text: {text[:50]}")
        locator.type(text, delay=delay, timeout=timeout)

    def clear(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """清空输入框"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        logger.debug(f"Clearing element")
        locator.fill("", timeout=timeout)

    def press(
        self,
        selector: SelectorLike,
        key: str,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        按下键盘按键

        Args:
            selector: Selector | str | Locator
            key: 按键（"Enter", "Tab", "ArrowDown" 等）
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        logger.debug(f"Pressing key: {key}")
        locator.press(key, timeout=timeout)

    def press_sequentially(
        self,
        selector: SelectorLike,
        keys: List[str],
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        delay: int = 100,
        **kwargs
    ) -> None:
        """依次按下多个按键"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        for key in keys:
            logger.debug(f"Pressing key: {key}")
            locator.press(key, timeout=timeout)
            if delay > 0:
                time.sleep(delay / 1000)

    # ==================== 文本与属性 ====================

    def text(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        获取元素文本

        Args:
            selector: Selector | str | Locator
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数

        Returns:
            str: 元素文本内容
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        return locator.inner_text()

    def all_texts(
        self,
        selector: SelectorLike,
        wait_for: str = "attached",
        timeout: Optional[int] = None,
        **kwargs
    ) -> List[str]:
        """
        获取所有匹配元素的文本列表

        Args:
            selector: Selector | str | Locator
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数

        Returns:
            List[str]: 文本列表
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        return locator.all_inner_texts()

    def attribute(
        self,
        selector: SelectorLike,
        name: str,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> Optional[str]:
        """
        获取元素属性值

        Args:
            selector: Selector | str | Locator
            name: 属性名
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数

        Returns:
            Optional[str]: 属性值，不存在则返回 None
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        return locator.get_attribute(name)

    def all_attributes(
        self,
        selector: SelectorLike,
        name: str,
        wait_for: str = "attached",
        timeout: Optional[int] = None,
        **kwargs
    ) -> List[Optional[str]]:
        """
        获取所有匹配元素的属性值列表

        Args:
            selector: Selector | str | Locator
            name: 属性名
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数

        Returns:
            List[Optional[str]]: 属性值列表
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        return locator.all_get_attributes(name)

    def is_checked(
        self,
        selector: SelectorLike,
        timeout: Optional[int] = None,
        # **kwargs
    ) -> bool:
        """检查复选框/单选框是否选中"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.resolve(selector)

        try:
            return locator.is_checked(timeout=timeout)
        except PlaywrightTimeoutError:
            return False

    def is_visible(
        self,
        selector: SelectorLike,
        timeout: Optional[int] = None
    ) -> bool:
        """检查元素是否可见"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.resolve(selector)

        try:
            return locator.is_visible(timeout=timeout)
        except PlaywrightTimeoutError:
            return False

    def is_enabled(
        self,
        selector: SelectorLike,
        timeout: Optional[int] = None
    ) -> bool:
        """检查元素是否启用"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.resolve(selector)

        try:
            return locator.is_enabled(timeout=timeout)
        except PlaywrightTimeoutError:
            return False

    def is_disabled(
        self,
        selector: SelectorLike,
        timeout: Optional[int] = None
    ) -> bool:
        """检查元素是否禁用"""
        return not self.is_enabled(selector, timeout)

    # ==================== 表单操作 ====================

    def select_option(
        self,
        selector: SelectorLike,
        value: Union[str, List[str]],
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        选择下拉框选项

        Args:
            selector: Selector | str | Locator
            value: 选项值（单个或列表）
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        if isinstance(value, str):
            value = [value]

        logger.debug(f"Selecting options: {value}")
        locator.select_option(value, timeout=timeout)

    def upload_file(
        self,
        selector: SelectorLike,
        file_path: Union[str, List[str]],
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        上传文件

        Args:
            selector: Selector | str | Locator
            file_path: 文件路径（单个或列表）
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        if isinstance(file_path, str):
            file_path = [file_path]

        logger.debug(f"Uploading files: {file_path}")
        locator.set_input_files(file_path, timeout=timeout)

    def clear_file(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """清除已上传的文件"""
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        logger.debug("Clearing uploaded files")
        locator.set_input_files([], timeout=timeout)

    # ==================== 断言方法 ====================

    def assert_exists(
        self,
        selector: SelectorLike,
        message: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> None:
        """
        断言元素存在

        Args:
            selector: Selector | str | Locator
            message: 断言失败时的自定义消息
            timeout: 超时时间（毫秒）

        Raises:
            AssertionError: 元素不存在
        """
        exists = self.exists(selector, timeout=timeout)

        msg = message or f"Element should exist: {selector}"
        assert exists, msg

    def assert_not_exists(
        self,
        selector: SelectorLike,
        message: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> None:
        """
        断言元素不存在

        Args:
            selector: Selector | str | Locator
            message: 断言失败时的自定义消息
            timeout: 超时时间（毫秒）

        Raises:
            AssertionError: 元素存在
        """
        exists = self.exists(selector, timeout=timeout)

        msg = message or f"Element should not exist: {selector}"
        assert not exists, msg

    def assert_visible(
        self,
        selector: SelectorLike,
        message: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> None:
        """
        断言元素可见

        Args:
            selector: Selector | str | Locator
            message: 断言失败时的自定义消息
            timeout: 超时时间（毫秒）

        Raises:
            AssertionError: 元素不可见
        """
        visible = self.is_visible(selector, timeout=timeout)

        msg = message or f"Element should be visible: {selector}"
        assert visible, msg

    def assert_hidden(
        self,
        selector: SelectorLike,
        message: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> None:
        """
        断言元素隐藏

        Args:
            selector: Selector | str | Locator
            message: 断言失败时的自定义消息
            timeout: 超时时间（毫秒）

        Raises:
            AssertionError: 元素可见
        """
        visible = self.is_visible(selector, timeout=timeout)

        msg = message or f"Element should be hidden: {selector}"
        assert not visible, msg

    def assert_text(
        self,
        selector: SelectorLike,
        expected: str,
        exact: bool = False,
        message: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        断言元素文本

        Args:
            selector: Selector | str | Locator
            expected: 期望的文本
            exact: 是否精确匹配
            message: 断言失败时的自定义消息
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 text 的其他参数

        Raises:
            AssertionError: 文本不匹配
        """
        actual = self.text(selector, timeout=timeout, **kwargs)

        if exact:
            msg = message or f"Text should be exactly '{expected}', got '{actual}'"
            assert actual == expected, msg
        else:
            msg = message or f"Text should contain '{expected}', got '{actual}'"
            assert expected in actual, msg

    def assert_attribute(
        self,
        selector: SelectorLike,
        name: str,
        expected: str,
        message: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        断言元素属性值

        Args:
            selector: Selector | str | Locator
            name: 属性名
            expected: 期望的属性值
            message: 断言失败时的自定义消息
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 attribute 的其他参数

        Raises:
            AssertionError: 属性值不匹配
        """
        actual = self.attribute(selector, name, timeout=timeout, **kwargs)

        msg = message or f"Attribute '{name}' should be '{expected}', got '{actual}'"
        assert actual == expected, msg

    # ==================== 截图与调试 ====================

    def screenshot(
        self,
        path: Optional[str] = None,
        full_page: bool = False,
        selector: Optional[SelectorLike] = None,
        **kwargs
    ) -> bytes:
        """
        截图

        Args:
            path: 保存路径（如果为 None，返回字节数据）
            full_page: 是否截取完整页面
            selector: 如果指定，只截取该元素
            **kwargs: 传递给 Playwright screenshot 的其他参数

        Returns:
            bytes: 截图数据
        """
        if selector:
            locator = self.resolve(selector)
            return locator.screenshot(path=path, **kwargs)
        else:
            return self.page.screenshot(path=path, full_page=full_page, **kwargs)

    def screenshot_on_failure(
        self,
        name: str = "failure",
        full_page: bool = True
    ) -> None:
        """失败时,截图（用于异常处理）"""
        try:
            timestamp = int(time.time())
            path = f"screenshots/{name}_{timestamp}.png"
            self.screenshot(path=path, full_page=full_page)
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")

    @contextmanager
    def auto_screenshot_on_error(self, name: str = "operation"):
        """
        上下文管理器：操作失败时自动截图

        Usage:
            with page.auto_screenshot_on_error("login"):
                page.click(login_button)
                page.fill(username_field, "user")
        """
        try:
            yield
        except Exception as e:
            logger.error(f"{name} failed: {e}")
            self.screenshot_on_failure(name=name)
            raise

    # ==================== 滚动操作 ====================

    def scroll_to(
        self,
        selector: SelectorLike,
        wait_for: str = "visible",
        timeout: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        滚动到元素

        Args:
            selector: Selector | str | Locator
            wait_for: 等待状态
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 find 的其他参数
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        locator = self.find(selector, wait_for=wait_for, timeout=timeout, **kwargs)

        locator.scroll_into_view_if_needed(timeout=timeout)

    def scroll_by(self, x: int = 0, y: int = 0) -> None:
        """按指定偏移量滚动"""
        self.page.evaluate(f"window.scrollBy({x}, {y})")

    def scroll_to_top(self) -> None:
        """滚动到页面顶部"""
        self.page.evaluate("window.scrollTo(0, 0)")

    def scroll_to_bottom(self) -> None:
        """滚动到页面底部"""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    # ==================== JavaScript 执行 ====================

    def evaluate(self, expression: str, *args) -> Any:
        """
        在页面上下文中执行 JavaScript

        Args:
            expression: JavaScript 表达式
            *args: 传递给表达式的参数

        Returns:
            Any: 执行结果
        """
        return self.page.evaluate(expression, *args)

    def evaluate_on_selector(
        self,
        selector: SelectorLike,
        expression: str,
        *args
    ) -> Any:
        """
        在指定元素上执行 JavaScript

        Args:
            selector: Selector | str | Locator
            expression: JavaScript 表达式（形参为 element）
            *args: 传递给表达式的参数

        Returns:
            Any: 执行结果
        """
        locator = self.resolve(selector)
        return locator.evaluate(expression, *args)

    # ==================== 等待辅助方法 ====================

    def wait_for_timeout(self, timeout: int) -> None:
        """
        等待指定时间（毫秒）

        Args:
            timeout: 等待时间（毫秒）
        """
        self.page.wait_for_timeout(timeout)

    def wait_for_function(
        self,
        expression: str,
        timeout: Optional[int] = None,
        polling: Union[int, str] = "raf"
    ) -> Any:
        """
        等待 JavaScript 函数返回真值

        Args:
            expression: JavaScript 表达式
            timeout: 超时时间（毫秒）
            polling: 轮询间隔（毫秒）或 "raf"（requestAnimationFrame）

        Returns:
            Any: 函数返回值
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        return self.page.wait_for_function(expression, timeout=timeout, polling=polling)

    # ==================== 页面信息 ====================

    def get_page_load_time(self) -> Optional[float]:
        """
        获取页面加载时间（秒）

        Returns:
            Optional[float]: 加载时间，如果未记录则返回 None
        """
        return self._load_time

    def get_page_name(self) -> str:
        """
        获取页面名称（类名）

        Returns:
            str: 页面名称
        """
        return self._page_name

    def console_logs(self) -> List[str]:
        """
        获取控制台日志（需要先监听 console 事件）

        Returns:
            List[str]: 控制台日志列表
        """
        # 需要在页面初始化时添加监听：
        # page.on("console", lambda msg: self._console_logs.append(msg.text()))
        return getattr(self, "_console_logs", [])

    # ==================== 实用工具 ====================

    @staticmethod
    def format_selector( selector: Selector, **kwargs) -> Selector:
        """
        格式化 Selector（替换模板变量）

        Args:
            selector: Selector 对象
            **kwargs: 模板变量

        Returns:
            Selector: 格式化后的 Selector

        Usage:
            # 定义带模板变量的选择器
            DYNAMIC_MSG = Selector(text="订单 {order_id} 已创建")

            # 格式化
            formatted = page.format_selector(DYNAMIC_MSG, order_id="12345")
            page.assert_visible(formatted)
        """
        return selector.formatted(**kwargs)

    # ==================== 上下文管理器 ====================

    @contextmanager
    def frame_context(self, frame_name: Optional[str] = None, frame_url: Optional[str] = None):
        """
        切换到指定 Frame 的上下文管理器

        Args:
            frame_name: Frame 名称
            frame_url: Frame URL（包含）

        Yields:
            Frame: Frame 对象

        Raises:
            FrameNotFoundError: Frame 未找到
            ValueError: 参数无效
        """
        if frame_name:
            frame = self.page.frame(name=frame_name)
        elif frame_url:
            frame = next((f for f in self.page.frames if frame_url in (f.url or "")), None)
        else:
            raise ValueError("Either frame_name or frame_url must be provided")

        if not frame:
            raise FrameNotFoundError(f"Frame not found: {frame_name or frame_url}")

        yield frame

    @contextmanager
    def wait_for_navigation(self, timeout: Optional[int] = None, wait_until: str = "load"):
        """
        等待导航完成的上下文管理器

        Args:
            timeout: 超时时间（毫秒）
            wait_until: 等待状态

        Usage:
            with page.wait_for_navigation():
                page.click(submit_button)
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        with self.page.expect_navigation(timeout=timeout, wait_until=wait_until) as navigation_info:
            yield
            response = navigation_info.value
            logger.info(f"Navigation completed: {response.url if response else 'no response'}")

    @contextmanager
    def wait_for_popup(self, timeout: Optional[int] = None):
        """
        等待弹窗出现的上下文管理器

        Args:
            timeout: 超时时间（毫秒）

        Yields:
            EventContextManager: 弹窗上下文

        Usage:
            with page.wait_for_popup() as popup_info:
                page.click(open_popup_button)
            popup_page = popup_info.value
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        with self.page.expect_popup(timeout=timeout) as popup_info:
            yield popup_info

    # ==================== 调试辅助 ====================

    def debug_info(self, selector: SelectorLike) -> Dict[str, Any]:
        """
        获取选择器的调试信息

        Args:
            selector: Selector | str | Locator

        Returns:
            Dict[str, Any]: 调试信息（包括解析策略、上下文等）

        Usage:
            info = page.debug_info(login_button)
            print(json.dumps(info, indent=2, ensure_ascii=False))
        """
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
            return {
                "error": str(e),
                "type": type(e).__name__
            }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} url={self.current_url()}>"