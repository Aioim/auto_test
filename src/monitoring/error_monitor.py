"""
Playwright 错误监控装饰器（优化版，依赖 ScreenshotHelper）

提供错误监控能力：捕获页面弹窗、控制台错误、请求失败、页面自定义错误元素。
截图功能完全委托给 ScreenshotHelper，实现统一管理。

P0/P1 修复：
- 移除失效的 selector_timeout 参数
- 明确 auto_continue_after_screenshot 与 raise_on_error 的优先级
- 使用批量 evaluate 检查错误元素，性能提升
- 支持错误忽略模式（正则）
- 支持交互模式与自动继续模式
"""

from functools import wraps
from typing import Optional, List, Callable, Dict, Any
from pathlib import Path
import time
import traceback
import re
from collections import deque

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from logger import logger
from core.screenshot import ScreenshotHelper, ScreenshotType, ScreenshotMetadata


class ErrorMonitor:
    """
    错误监控器，用于捕获页面各类错误

    依赖 ScreenshotHelper 实现截图，功能丰富（全屏/元素/高亮、元数据、Allure 集成）
    """

    def __init__(
        self,
        page: Page,
        screenshot_helper: Optional[ScreenshotHelper] = None,
        screenshot_on_error: bool = True,
        screenshot_dir: str = "errors",
        func_name: str = "unknown",
        max_errors: int = 100,
        ignore_errors: Optional[List[str]] = None,
        interactive_mode: bool = False,
        auto_continue_after_screenshot: bool = False,
    ):
        """
        初始化错误监控器

        Args:
            page: Playwright Page 对象
            screenshot_helper: 可选的 ScreenshotHelper 实例（推荐传入）
            screenshot_on_error: 是否在错误时截图
            screenshot_dir: 截图保存目录（仅在未提供 screenshot_helper 时生效）
            func_name: 被监控的函数名，用于日志和截图标签
            max_errors: 每种类型最多记录的错误数量（防止内存溢出）
            ignore_errors: 忽略的错误消息模式列表（支持正则表达式字符串）
            interactive_mode: 交互模式，出现错误时暂停并等待用户按键继续
            auto_continue_after_screenshot: 自动继续模式，截图后自动继续执行（不抛出异常，优先级高于 raise_on_error）
        """
        self.page = page
        self.func_name = func_name
        self.max_errors = max_errors
        self.ignore_patterns = [re.compile(pattern) for pattern in (ignore_errors or [])]
        self.interactive_mode = interactive_mode
        self.auto_continue_after_screenshot = auto_continue_after_screenshot

        # 错误记录容器（使用 deque 限制最大长度）
        self.dialogs: deque = deque(maxlen=max_errors)
        self.console_errors: deque = deque(maxlen=max_errors)
        self.failed_requests: deque = deque(maxlen=max_errors)

        # 截图相关
        self.screenshot_on_error = screenshot_on_error
        self.screenshot_helper = screenshot_helper
        self.screenshot_taken = False
        self.screenshot_metadata: Optional[ScreenshotMetadata] = None

        # 如果启用了截图但未提供 helper，则创建默认实例
        if self.screenshot_on_error and self.screenshot_helper is None:
            self.screenshot_helper = ScreenshotHelper(
                page=page,
                screenshot_dir=screenshot_dir,
                auto_cleanup=False,
                enable_allure=True,
                context_tags={"func": func_name}
            )
            logger.debug(f"Created default ScreenshotHelper for {func_name}")

        # 保存事件处理器引用，便于移除
        self._dialog_handler = self._create_dialog_handler()
        self._console_handler = self._create_console_handler()
        self._request_failed_handler = self._create_request_failed_handler()

        self._setup_listeners()

    def _should_ignore(self, text: str) -> bool:
        """判断是否应该忽略该错误消息"""
        for pattern in self.ignore_patterns:
            if pattern.search(text):
                logger.debug(f"Ignoring error matching pattern '{pattern.pattern}': {text[:100]}")
                return True
        return False

    def _create_dialog_handler(self):
        """创建对话框事件处理器（仅记录，不截图，因为原生弹窗无法被截图捕获）"""
        def on_dialog(dialog):
            dialog_info = {
                "type": dialog.type,
                "message": dialog.message,
                "timestamp": time.time()
            }
            if self._should_ignore(dialog.message):
                dialog.accept()
                return

            self.dialogs.append(dialog_info)
            logger.warning(f"⚠️ 检测到弹窗 [{dialog.type}]: {dialog.message}")

            # 原生弹窗无法被 page.screenshot() 捕获，所以这里不尝试截图
            # 统一在 check_errors 时截图（但弹窗已被 accept，截不到内容）
            # 因此仅记录，不依赖截图

            # 自动接受对话框，避免测试阻塞
            try:
                dialog.accept()
                logger.debug("弹窗已自动接受")
            except Exception as e:
                logger.error(f"接受弹窗失败：{e}")

        return on_dialog

    def _create_console_handler(self):
        """创建控制台事件处理器"""
        def on_console(msg):
            if msg.type not in ("error", "warning"):
                return

            error_info = {
                "type": msg.type,
                "text": msg.text,
                "timestamp": time.time()
            }

            if self._should_ignore(msg.text):
                return

            self.console_errors.append(error_info)
            logger.debug(f"控制台 {msg.type}: {msg.text}")

        return on_console

    def _create_request_failed_handler(self):
        """创建请求失败事件处理器"""
        def on_request_failed(request):
            failure = request.failure
            error_text = f"{request.url} - {failure}"
            if self._should_ignore(error_text):
                return

            self.failed_requests.append({
                "url": request.url,
                "failure": failure,
                "timestamp": time.time()
            })
            logger.debug(f"请求失败：{request.url} - {failure}")

        return on_request_failed

    def _setup_listeners(self):
        """设置事件监听器"""
        self.page.on("dialog", self._dialog_handler)
        self.page.on("console", self._console_handler)
        self.page.on("requestfailed", self._request_failed_handler)
        logger.debug(f"ErrorMonitor 监听器已设置 (func={self.func_name})")

    def remove_listeners(self):
        """移除事件监听器，防止泄漏"""
        try:
            self.page.remove_listener("dialog", self._dialog_handler)
            self.page.remove_listener("console", self._console_handler)
            self.page.remove_listener("requestfailed", self._request_failed_handler)
            logger.debug(f"ErrorMonitor 监听器已移除 (func={self.func_name})")
        except Exception as e:
            logger.warning(f"移除监听器失败：{e}")

    def _take_error_screenshot(self, error_type: str, error_message: str = "") -> Optional[ScreenshotMetadata]:
        """
        使用 ScreenshotHelper 截取错误截图
        """
        if not self.screenshot_on_error or self.screenshot_helper is None:
            return None

        if self.screenshot_taken:
            logger.debug("已截取过截图，跳过重复截图")
            return self.screenshot_metadata

        try:
            metadata = self.screenshot_helper.take_error_screenshot(
                error_type=error_type,
                func_name=self.func_name,
                error_message=error_message[:200] if error_message else None,
                screenshot_type=ScreenshotType.FULL_PAGE,
                additional_tags={"source": "error_monitor"},
                add_timestamp=True
            )
            self.screenshot_taken = True
            self.screenshot_metadata = metadata
            logger.info(f"📸 错误截图已保存：{metadata.name} ({metadata.size} bytes)")
            return metadata
        except Exception as e:
            logger.error(f"截图失败：{e}\n{traceback.format_exc()}")
            return None

    def check_errors(
        self,
        error_selectors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        检查各类错误（不再支持 selector_timeout，因为使用批量 evaluate 无超时）

        Args:
            error_selectors: 页面上错误元素的 CSS 选择器列表

        Returns:
            包含所有错误信息的字典
        """
        logger.debug(f"开始检查错误 (func={self.func_name})...")

        # 收集页面错误元素（一次性 evaluate，性能最优）
        page_errors: List[Dict[str, str]] = []
        if error_selectors:
            try:
                js_code = """
                (selectors) => {
                    const results = [];
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            const texts = Array.from(elements).map(el => el.textContent || '').join(' | ');
                            results.push({ selector: selector, text: texts });
                        }
                    }
                    return results;
                }
                """
                page_errors = self.page.evaluate(js_code, error_selectors)
                for err in page_errors:
                    logger.warning(f"发现页面错误元素 [{err['selector']}]: {err['text'][:100]}")
            except Exception as e:
                logger.warning(f"检查页面错误元素失败：{e}")

        # 判断是否有任何错误
        has_any_error = bool(
            self.dialogs or
            self.console_errors or
            self.failed_requests or
            page_errors
        )

        # 如果有错误且尚未截图，立即截图（错误类型优先取第一个）
        if has_any_error and not self.screenshot_taken:
            error_type = "PageError"
            if self.dialogs:
                error_type = f"Dialog_{self.dialogs[0]['type']}"
            elif self.console_errors:
                error_type = "ConsoleError"
            elif self.failed_requests:
                error_type = "RequestFailed"
            error_msg = self.format_error_message({
                "dialogs": self.dialogs,
                "console_errors": self.console_errors,
                "failed_requests": self.failed_requests,
                "page_errors": page_errors,
            })
            self._take_error_screenshot(error_type=error_type, error_message=error_msg)

        result = {
            "dialogs": list(self.dialogs),
            "console_errors": list(self.console_errors),
            "failed_requests": list(self.failed_requests),
            "page_errors": page_errors,
            "screenshot": self.screenshot_metadata.name if self.screenshot_metadata else None,
            "screenshot_path": self.screenshot_metadata.filepath if self.screenshot_metadata else None,
            "has_error": has_any_error,
        }

        # 交互模式：如果有错误且未自动继续，则等待用户确认
        if has_any_error and self.interactive_mode and not self.auto_continue_after_screenshot:
            input(f"\n⚠️ 检测到错误，截图已保存。按 Enter 继续执行...")

        logger.debug(f"错误检查完成：has_error={has_any_error}, screenshot={result['screenshot']}")
        return result

    def format_error_message(self, errors: Dict[str, Any]) -> str:
        """格式化错误信息，生成清晰的错误报告"""
        error_summary = []

        if errors.get("dialogs"):
            dialog_types = [d["type"] for d in errors["dialogs"]]
            error_summary.append(f"弹窗：{len(errors['dialogs'])} 个 ({', '.join(set(dialog_types))})")

        if errors.get("console_errors"):
            error_count = sum(1 for e in errors["console_errors"] if e["type"] == "error")
            warning_count = sum(1 for e in errors["console_errors"] if e["type"] == "warning")
            error_summary.append(f"控制台：{error_count} 个错误，{warning_count} 个警告")

        if errors.get("failed_requests"):
            error_summary.append(f"失败请求：{len(errors['failed_requests'])} 个")

        if errors.get("page_errors"):
            error_summary.append(f"页面错误元素：{len(errors['page_errors'])} 个")

        return ", ".join(error_summary) if error_summary else "无错误"

    def clear(self):
        """清理数据并移除监听器（实例不可再用）"""
        logger.debug(f"清理 ErrorMonitor (func={self.func_name})...")
        self.remove_listeners()
        self.dialogs.clear()
        self.console_errors.clear()
        self.failed_requests.clear()
        self.screenshot_taken = False
        self.screenshot_metadata = None

    # 上下文管理器支持
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear()


def monitor_errors(
    page: Page,
    error_selectors: Optional[List[str]] = None,
    raise_on_error: bool = True,
    screenshot_on_error: bool = True,
    screenshot_dir: str = "errors",
    interactive_mode: bool = False,
    auto_continue_after_screenshot: bool = False,
    max_errors: int = 100,
    ignore_errors: Optional[List[str]] = None,
    screenshot_helper: Optional[ScreenshotHelper] = None,
):
    """
    错误监控装饰器工厂

    Args:
        page: Playwright Page 对象
        error_selectors: 页面上错误元素的 CSS 选择器列表
        raise_on_error: 检测到错误时是否抛出 AssertionError（如果 auto_continue_after_screenshot=True，则忽略此参数）
        screenshot_on_error: 检测到错误时是否截图
        screenshot_dir: 截图保存目录（仅在未提供 screenshot_helper 时生效）
        interactive_mode: 交互模式，出现错误时等待用户确认
        auto_continue_after_screenshot: 自动继续模式，截图后自动继续执行（不抛出异常，优先级高于 raise_on_error）
        max_errors: 每种类型最多记录的错误数量
        ignore_errors: 忽略的错误消息模式列表（正则表达式字符串）
        screenshot_helper: 可选的 ScreenshotHelper 实例（推荐传入）

    Returns:
        装饰器函数
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"🔍 开始监控函数：{func.__name__}")

            monitor = ErrorMonitor(
                page=page,
                screenshot_helper=screenshot_helper,
                screenshot_on_error=screenshot_on_error,
                screenshot_dir=screenshot_dir,
                func_name=func.__name__,
                max_errors=max_errors,
                ignore_errors=ignore_errors,
                interactive_mode=interactive_mode,
                auto_continue_after_screenshot=auto_continue_after_screenshot,
            )

            errors: Dict[str, Any] = {}
            try:
                # 执行被装饰的函数
                result = func(*args, **kwargs)

                # 函数执行成功后检查错误
                errors = monitor.check_errors(error_selectors)

                if errors["has_error"]:
                    error_summary = monitor.format_error_message(errors)
                    msg = f"❌ {func.__name__} 检测到错误 - {error_summary}"
                    screenshot_info = f" | 截图：{errors['screenshot']}" if errors.get("screenshot") else ""
                    full_msg = f"{msg}{screenshot_info}"

                    # 优先级：auto_continue_after_screenshot > raise_on_error
                    if auto_continue_after_screenshot:
                        logger.warning(f"{full_msg} (自动继续模式，不抛出异常)")
                    elif raise_on_error:
                        raise AssertionError(full_msg)
                    else:
                        logger.warning(full_msg)

                else:
                    logger.info(f"✅ {func.__name__} 执行成功，无错误")

                return result

            except Exception as e:
                logger.error(f"函数 {func.__name__} 抛出异常：{e}")

                # 如果函数本身抛出异常，也尝试截图记录现场
                if screenshot_on_error and not monitor.screenshot_taken:
                    error_type = type(e).__name__
                    error_msg = str(e)
                    monitor._take_error_screenshot(error_type=error_type, error_message=error_msg)

                # 自动继续模式：忽略异常，返回 None
                if auto_continue_after_screenshot:
                    logger.warning(f"自动继续模式：忽略异常 {e}")
                    return None
                else:
                    raise

            finally:
                monitor.clear()
                logger.debug(f"函数 {func.__name__} 监控结束")

        return wrapper
    return decorator


# ==================== 辅助测试函数 ====================

def test_alert_screenshot(page: Page, screenshot_dir: str = "./test_screenshots"):
    """
    测试弹窗监控功能（注意：原生弹窗无法被截图捕获，仅演示监控能力）

    用法:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            test_alert_screenshot(page)
            browser.close()
    """
    import os
    os.makedirs(screenshot_dir, exist_ok=True)

    @monitor_errors(
        page=page,
        screenshot_on_error=True,
        screenshot_dir=screenshot_dir,
        raise_on_error=False,
        auto_continue_after_screenshot=True
    )
    def trigger_alert():
        page.goto("data:text/html,<h1>测试页面</h1>")
        page.evaluate("alert('测试弹窗消息（无法被截图捕获）')")
        time.sleep(0.5)

    try:
        trigger_alert()
        print(f"\n✅ 测试完成，请检查目录：{os.path.abspath(screenshot_dir)}")
        print("注意：原生弹窗无法被截图捕获，截图仅包含页面内容。")
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")


# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("✅ ErrorMonitor 模块加载成功（P0/P1 修复版，依赖 ScreenshotHelper）")
    print("\n=== 基本使用示例 ===")
    print("""
from playwright.sync_api import sync_playwright
from utils.error_monitor import monitor_errors
from utils.screenshot_helper import ScreenshotHelper

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # 推荐：创建共享的 ScreenshotHelper 实例
    screenshot_helper = ScreenshotHelper(page, screenshot_dir="screenshots")
    
    @monitor_errors(
        page=page,
        screenshot_helper=screenshot_helper,
        raise_on_error=True,
        screenshot_on_error=True,
        ignore_errors=[r"404 Not Found", r"favicon\\.ico"],
        auto_continue_after_screenshot=False
    )
    def test_login():
        page.goto("https://example.com/login")
        page.fill("#username", "test")
        page.fill("#password", "wrong")
        page.click("#login-button")
        page.wait_for_selector(".error-message", timeout=3000)
    
    test_login()
    browser.close()
    """)