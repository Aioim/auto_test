"""
Playwright 错误监控装饰器
用于自动化测试中捕获页面错误、控制台错误、请求失败等信息
"""

from functools import wraps
from typing import Optional, List, Callable, Dict, Any
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from pathlib import Path
import time
import traceback
import logging
from src.utils.logger import logger


class ErrorMonitor:
    """错误监控器，用于捕获页面各类错误"""
    
    def __init__(
        self, 
        page: Page,
        screenshot_on_error: bool = True,
        screenshot_dir: str = "errors",
        func_name: str = "unknown",
        # 添加新的配置选项
        max_errors: int = 100,  # 最大错误数量，防止内存溢出
        ignore_errors: Optional[List[str]] = None,  # 忽略的错误模式
        interactive_mode: bool = False,  # 交互模式，出现错误时等待用户确认
        auto_continue_after_screenshot: bool = False  # 自动继续模式，截图后自动继续执行
    ):
        self.page = page
        self.dialogs: List[Dict[str, str]] = []
        self.console_errors: List[Dict[str, str]] = []
        self.failed_requests: List[Dict[str, Any]] = []
        
        # 新增配置
        self.max_errors = max_errors
        self.ignore_errors = ignore_errors or []
        self.interactive_mode = interactive_mode
        self.auto_continue_after_screenshot = auto_continue_after_screenshot
        
        # 截图配置
        self.screenshot_on_error = screenshot_on_error
        self.screenshot_dir = screenshot_dir
        self.func_name = func_name
        self.screenshot_taken = False
        self.screenshot_filename: Optional[str] = None
        self.dialog_screenshot_taken = False
        
        # 保存回调引用，便于后续移除监听器
        self._on_dialog = self._create_dialog_handler()
        self._on_console = self._create_console_handler()
        self._on_request_failed = self._create_request_failed_handler()
        
        self._setup_listeners()
    
    def _take_screenshot(self, suffix: str = "") -> Optional[str]:
        """立即截图并返回文件名"""
        if not self.screenshot_on_error:
            logger.debug("截图功能已禁用")
            return None
        
        if self.screenshot_taken:
            logger.debug("已截取过截图，跳过")
            return self.screenshot_filename
        
        try:
            # 使用绝对路径，提高跨平台兼容性
            path = Path(self.screenshot_dir).resolve()
            path.mkdir(parents=True, exist_ok=True)
            
            # 改进文件名格式，包含更多信息
            timestamp = int(time.time() * 1000)
            suffix_str = f"_{suffix}" if suffix else ""
            filename = f"{self.func_name}_ERROR_{timestamp}{suffix_str}.png"
            screenshot_path = path / filename
            
            logger.debug(f"开始截图：{screenshot_path}")
            
            # 尝试多次截图，提高成功率
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    self.page.screenshot(path=str(screenshot_path), full_page=True)  # 改为全屏截图
                    break
                except Exception as e:
                    logger.warning(f"截图尝试 {attempt+1}/{max_attempts} 失败：{e}")
                    time.sleep(0.5)
            
            # 验证截图文件是否存在
            if screenshot_path.exists():
                file_size = screenshot_path.stat().st_size
                if file_size > 0:
                    logger.warning(f"📸 截图成功：{filename} ({file_size} bytes)")
                    self.screenshot_taken = True
                    self.screenshot_filename = str(filename)
                    return str(filename)
                else:
                    logger.error(f"截图文件为空：{screenshot_path}")
                    return None
            else:
                logger.error(f"截图文件未创建：{screenshot_path}")
                return None
                
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"截图失败：{e}\n{error_trace}")
            return None
    
    def _create_dialog_handler(self):
        """创建对话框事件处理器"""
        def on_dialog(dialog):
            logger.debug(f"检测到对话框：type={dialog.type}, message={dialog.message}")
            
            # 记录对话框信息
            dialog_info = {
                "type": dialog.type,
                "message": dialog.message,
            }
            self.dialogs.append(dialog_info)
            
            # ✅ 关键：在 accept 之前立即截图
            if dialog.type in ["alert", "confirm", "prompt"]:
                logger.warning(f"⚠️ 检测到弹窗 [{dialog.type}]: {dialog.message}")
                
                if self.screenshot_on_error and not self.dialog_screenshot_taken:
                    logger.debug("尝试在弹窗关闭前截图...")
                    screenshot_file = self._take_screenshot(suffix="DIALOG")
                    if screenshot_file:
                        self.dialog_screenshot_taken = True
                        dialog_info["screenshot"] = screenshot_file
                    else:
                        logger.warning("弹窗截图失败，将在 check_errors 时重试")
                else:
                    logger.debug(f"跳过截图：screenshot_on_error={self.screenshot_on_error}, dialog_screenshot_taken={self.dialog_screenshot_taken}")
            
            # 自动接受对话框，避免阻塞测试
            try:
                dialog.accept()
                logger.debug("弹窗已接受")
            except Exception as e:
                logger.error(f"接受弹窗失败：{e}")
                
        return on_dialog
    
    def _create_console_handler(self):
        """创建控制台事件处理器"""
        def on_console(msg):
            if msg.type in ["error", "warning"]:
                self.console_errors.append({
                    "type": msg.type,
                    "text": msg.text,
                })
                logger.debug(f"控制台 {msg.type}: {msg.text}")
        return on_console
    
    def _create_request_failed_handler(self):
        """创建请求失败事件处理器"""
        def on_request_failed(request):
            # 可在此添加过滤逻辑，忽略某些预期的失败请求
            failure_info = request.failure
            self.failed_requests.append({
                "url": request.url,
                "failure": failure_info,
            })
            logger.debug(f"请求失败：{request.url} - {failure_info}")
        return on_request_failed
    
    def _setup_listeners(self):
        """设置事件监听器"""
        self.page.on("dialog", self._on_dialog)
        self.page.on("console", self._on_console)
        self.page.on("requestfailed", self._on_request_failed)
        logger.debug("事件监听器已设置")
    
    def remove_listeners(self):
        """移除事件监听器，防止泄漏"""
        try:
            self.page.remove_listener("dialog", self._on_dialog)
            self.page.remove_listener("console", self._on_console)
            self.page.remove_listener("requestfailed", self._on_request_failed)
            logger.debug("事件监听器已移除")
        except Exception as e:
            logger.warning(f"移除监听器失败：{e}")
    
    def format_error_message(self, errors: Dict[str, Any]) -> str:
        """格式化错误信息，生成更清晰的错误报告"""
        error_summary = []
        
        if errors["dialogs"]:
            dialog_types = [d["type"] for d in errors["dialogs"]]
            error_summary.append(f"对话框：{len(errors['dialogs'])} 个 ({', '.join(set(dialog_types))})")
        
        if errors["console_errors"]:
            error_count = sum(1 for e in errors["console_errors"] if e["type"] == "error")
            warning_count = sum(1 for e in errors["console_errors"] if e["type"] == "warning")
            error_summary.append(f"控制台：{error_count} 个错误，{warning_count} 个警告")
        
        if errors["failed_requests"]:
            error_summary.append(f"失败请求：{len(errors['failed_requests'])} 个")
        
        if errors["page_errors"]:
            error_summary.append(f"页面错误元素：{len(errors['page_errors'])} 个")
        
        return ", ".join(error_summary)
    
    def check_errors(
        self, 
        error_selectors: Optional[List[str]] = None, 
        selector_timeout: int = 500
    ) -> Dict[str, Any]:
        """
        检查各类错误
        
        Args:
            error_selectors: 页面上错误元素的 CSS 选择器列表
            selector_timeout: 检查元素可见性的超时时间（毫秒）
        
        Returns:
            包含所有错误信息的字典
        """
        logger.debug("开始检查错误...")
        
        if error_selectors is None:
            error_selectors = [".error", ".alert-danger", "[role='alert']"]
        
        page_errors: List[Dict[str, str]] = []
        
        for selector in error_selectors:
            try:
                el = self.page.locator(selector)
                if el.is_visible(timeout=selector_timeout):
                    page_errors.append({
                        "selector": selector, 
                        "text": el.text_content() or ""
                    })
                    logger.warning(f"发现页面错误元素 [{selector}]: {el.text_content()}")
            except PlaywrightTimeoutError:
                continue
            except Exception as e:
                logger.warning(f"检查选择器 {selector} 时发生异常：{e}")
                continue
        
        # 如果检测到错误且尚未截图，立即截图
        has_any_error = any([
            self.dialogs, 
            self.console_errors, 
            self.failed_requests, 
            page_errors
        ])
        
        # 先创建结果对象
        result = {
            "dialogs": self.dialogs,
            "console_errors": self.console_errors,
            "failed_requests": self.failed_requests,
            "page_errors": page_errors,
            "screenshot": self.screenshot_filename,
            "has_error": has_any_error
        }
        
        if has_any_error and not self.screenshot_taken:
            logger.warning("检测到错误但未截图，尝试补截...")
            screenshot_file = self._take_screenshot(suffix="FINAL")
            if not screenshot_file:
                logger.error("补截截图失败")
            else:
                # 更新截图文件名
                result["screenshot"] = self.screenshot_filename
                # 自动继续模式：截图完成后记录并继续执行
                if self.auto_continue_after_screenshot:
                    error_summary = self.format_error_message(result)
                    logger.warning(f"📸 截图完成，自动继续执行 - 错误摘要：{error_summary}")
        
        logger.debug(f"错误检查结果：has_error={result['has_error']}, screenshot={result['screenshot']}")
        return result
    
    def clear(self):
        """清理数据并移除监听器"""
        logger.debug("清理 ErrorMonitor...")
        self.remove_listeners()
        self.dialogs.clear()
        self.console_errors.clear()
        self.failed_requests.clear()
        # 重置截图状态
        self.screenshot_taken = False
        self.screenshot_filename = None
        self.dialog_screenshot_taken = False


def monitor_errors(
    page: Page,
    error_selectors: Optional[List[str]] = None,
    raise_on_error: bool = True,
    screenshot_on_error: bool = True,
    screenshot_dir: str = "errors",
    selector_timeout: int = 500,
    interactive_mode: bool = False,
    auto_continue_after_screenshot: bool = False
):
    """
    错误监控装饰器工厂
    
    Args:
        page: Playwright Page 对象
        error_selectors: 页面上错误元素的 CSS 选择器列表
        raise_on_error: 检测到错误时是否抛出异常
        screenshot_on_error: 检测到错误时是否截图
        screenshot_dir: 截图保存目录
        selector_timeout: 检查元素可见性的超时时间（毫秒）
        interactive_mode: 交互模式，出现错误时等待用户确认
        auto_continue_after_screenshot: 自动继续模式，截图后自动继续执行
    
    Returns:
        装饰器函数
    """
    # 设置日志级别
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"开始监控函数：{func.__name__}")
            
            monitor = ErrorMonitor(
                page=page,
                screenshot_on_error=screenshot_on_error,
                screenshot_dir=screenshot_dir,
                func_name=func.__name__,
                interactive_mode=interactive_mode,
                auto_continue_after_screenshot=auto_continue_after_screenshot
            )
            errors: Dict[str, Any] = {}
            
            try:
                # 执行被装饰的函数
                logger.debug(f"执行函数：{func.__name__}")
                result = func(*args, **kwargs)
                logger.debug(f"函数执行完成：{func.__name__}")
                
                # 函数执行成功后检查错误
                errors = monitor.check_errors(error_selectors, selector_timeout)
                
                if errors["has_error"]:
                    # 格式化错误信息
                    error_summary = monitor.format_error_message(errors)
                    msg = f"❌ {func.__name__} 检测到错误 - {error_summary}"
                    screenshot_info = f" | 截图：{errors.get('screenshot', '无')}" if errors.get('screenshot') else " | ⚠️ 无截图"
                    
                    if raise_on_error:
                        raise AssertionError(f"{msg}{screenshot_info}")
                    else:
                        logger.warning(f"{msg}{screenshot_info} | 详情：{errors}")
                else:
                    logger.info(f"✅ {func.__name__} 执行成功，无错误")
                
                return result
                
            except Exception as e:
                logger.error(f"函数 {func.__name__} 抛出异常：{e}")
                
                # 如果函数本身抛出异常，也尝试截图记录现场
                if screenshot_on_error and not monitor.screenshot_taken:
                    try:
                        # 使用绝对路径，提高跨平台兼容性
                        path = Path(screenshot_dir).resolve()
                        path.mkdir(parents=True, exist_ok=True)
                        filename = f"{func.__name__}_EXCEPTION_{int(time.time() * 1000)}.png"
                        screenshot_path = path / filename
                        
                        # 尝试多次截图，提高成功率
                        max_attempts = 3
                        for attempt in range(max_attempts):
                            try:
                                page.screenshot(path=str(screenshot_path), full_page=True)
                                break
                            except Exception as screenshot_error:
                                logger.warning(f"异常截图尝试 {attempt+1}/{max_attempts} 失败：{screenshot_error}")
                                time.sleep(0.5)
                        
                        if screenshot_path.exists():
                            file_size = screenshot_path.stat().st_size
                            if file_size > 0:
                                monitor.screenshot_filename = str(filename)
                                logger.warning(f"📸 已保存异常截图：{filename} ({file_size} bytes)")
                            else:
                                logger.error("异常截图文件为空")
                        else:
                            logger.error("异常截图文件未创建")
                    except Exception as screenshot_error:
                        logger.error(f"截图失败：{screenshot_error}\n{traceback.format_exc()}")
                
                # 重新抛出原始异常
                raise e
                
            finally:
                # 关键：务必移除监听器，防止泄漏
                monitor.clear()
                logger.debug(f"函数 {func.__name__} 监控结束")
        
        return wrapper
    return decorator


# ============================================================================
# 测试工具函数
# ============================================================================

def test_alert_screenshot(page: Page, screenshot_dir: str = "./test_screenshots"):
    """
    测试弹窗截图功能
    
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
        raise_on_error=False
    )
    def trigger_alert():
        page.goto("data:text/html,<h1>测试页面</h1>")
        page.evaluate("alert('测试弹窗消息')")
        time.sleep(0.5)  # 给截图一点时间
    
    try:
        trigger_alert()
        print(f"\n✅ 测试完成，请检查目录：{os.path.abspath(screenshot_dir)}")
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    print("✅ ErrorMonitor 模块加载成功")
    print("📌 使用方法：@monitor_errors(page=your_page_object)")
    print("📌 弹窗截图功能：在 dialog.accept() 之前执行截图")
    print("📌 调试模式：设置 log_level=logging.DEBUG 查看详细日志")
    print("📌 自动继续模式：设置 auto_continue_after_screenshot=True 截图后自动继续执行")
    print("\n=== 使用示例 ===")
    print("""
# 基本使用示例
from playwright.sync_api import sync_playwright
from utils.error_monitor import monitor_errors

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    @monitor_errors(
        page=page,
        screenshot_on_error=True,
        screenshot_dir="./screenshots",
        raise_on_error=True,
        log_level=logging.INFO
    )
    def test_login():
        #测试登录功能
        page.goto("https://example.com/login")
        page.fill("#username", "testuser")
        page.fill("#password", "password")
        page.click("#login-button")
        # 等待登录完成
        page.wait_for_load_state("networkidle")
    
    try:
        test_login()
        print("✅ 测试执行成功")
    except AssertionError as e:
        print(f"❌ 测试失败：{e}")
    finally:
        browser.close()

# 高级使用示例
from playwright.sync_api import sync_playwright
from utils.error_monitor import monitor_errors

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    @monitor_errors(
        page=page,
        error_selectors=[".error-message", ".alert-danger", "[role='alert']"],
        screenshot_on_error=True,
        screenshot_dir="./test-results/screenshots",
        raise_on_error=False,  # 不抛出异常，只记录
        log_level=logging.DEBUG
    )
    def test_checkout():
        #测试 checkout 流程
        page.goto("https://example.com/checkout")
        # 填写表单
        page.fill("#name", "Test User")
        page.fill("#address", "123 Test St")
        page.fill("#credit-card", "1234567812345678")
        # 提交表单
        page.click("#submit-order")
        # 等待结果
        page.wait_for_timeout(3000)
    
    try:
        test_checkout()
        print("✅ 测试执行完成")
    finally:
        browser.close()

# 测试弹窗截图功能
from playwright.sync_api import sync_playwright
from utils.error_monitor import test_alert_screenshot

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    test_alert_screenshot(page, screenshot_dir="./test-screenshots")
    browser.close()

# 自动继续模式示例
from playwright.sync_api import sync_playwright
from utils.error_monitor import monitor_errors

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    @monitor_errors(
        page=page,
        screenshot_on_error=True,
        screenshot_dir="./screenshots",
        raise_on_error=False,
        auto_continue_after_screenshot=True  # 启用自动继续模式
    )
    def test_auto_continue():
        #测试自动继续模式
        page.goto("data:text/html,<h1>测试页面</h1>")
        # 触发一个弹窗
        page.evaluate("alert('测试弹窗，将自动截图并继续执行')")
        # 触发控制台错误
        page.evaluate("console.error('测试控制台错误')")
        # 继续执行后续操作
        print("继续执行后续测试步骤...")
        page.evaluate("console.log('测试继续执行')")
    
    try:
        test_auto_continue()
        print("✅ 测试执行完成")
    finally:
        browser.close()
""")
    
    # 运行测试（需要传入 page 对象）
    # test_alert_screenshot(page)