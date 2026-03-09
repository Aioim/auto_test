"""
测试 ErrorMonitor 功能
"""

from playwright.sync_api import sync_playwright
import logging
from src.utils.error_monitor import monitor_errors, test_alert_screenshot

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_error_monitor():
    """测试 ErrorMonitor 的完整功能"""
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print("\n=== 测试 1: 弹窗截图功能 ===")
        test_alert_screenshot(page, screenshot_dir="./test_screenshots/alert")
        
        print("\n=== 测试 2: 控制台错误监控 ===")
        
        @monitor_errors(
            page=page,
            screenshot_on_error=True,
            screenshot_dir="./test_screenshots/console",
            raise_on_error=False
        )
        def test_console_error():
            page.goto("data:text/html,<h1>测试页面</h1>")
            # 触发控制台错误
            page.evaluate("console.error('测试控制台错误'); console.warn('测试控制台警告');")
        
        test_console_error()
        
        print("\n=== 测试 3: 页面错误元素监控 ===")
        
        @monitor_errors(
            page=page,
            error_selectors=[".error", ".alert-danger"],
            screenshot_on_error=True,
            screenshot_dir="./test_screenshots/page_error",
            raise_on_error=False
        )
        def test_page_error():
            # 加载包含错误元素的页面
            page.goto("data:text/html,<h1>测试页面</h1><div class='error'>这是一个错误信息</div>")
        
        test_page_error()
        
        print("\n=== 测试 4: 异常截图功能 ===")
        
        @monitor_errors(
            page=page,
            screenshot_on_error=True,
            screenshot_dir="./test_screenshots/exception",
            raise_on_error=False
        )
        def test_exception():
            page.goto("data:text/html,<h1>测试页面</h1>")
            # 触发异常
            raise ValueError("测试异常")
        
        try:
            test_exception()
        except Exception as e:
            print(f"捕获到预期异常：{e}")
        
        # 关闭浏览器
        browser.close()
        print("\n✅ 所有测试完成，请检查 test_screenshots 目录中的截图")


if __name__ == "__main__":
    test_error_monitor()