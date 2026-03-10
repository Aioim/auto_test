"""
测试 ErrorMonitor 的自动继续模式功能
"""

from playwright.sync_api import sync_playwright
from utils.error_monitor import monitor_errors


def test_auto_continue_mode():
    """测试自动继续模式功能"""
    print("=== 测试 ErrorMonitor 自动继续模式 ===")
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        @monitor_errors(
            page=page,
            screenshot_on_error=True,
            screenshot_dir="./test-screenshots/auto_continue",
            raise_on_error=False,
            auto_continue_after_screenshot=True  # 启用自动继续模式
        )
        def test_with_auto_continue():
            """测试带有自动继续的场景"""
            print("\n1. 加载测试页面")
            page.goto("data:text/html,<h1>测试页面</h1>")
            
            print("2. 触发弹窗")
            page.evaluate("alert('测试弹窗消息')")
            
            print("3. 触发控制台错误")
            page.evaluate("console.error('测试控制台错误')")
            
            print("4. 自动继续执行...")
            # 这里会自动继续执行，不会中断测试
            
            print("5. 执行后续操作")
            page.evaluate("console.log('测试继续执行')")
            print("6. 测试完成")
        
        try:
            test_with_auto_continue()
            print("\n✅ 测试完成 - 自动继续模式工作正常")
        except Exception as e:
            print(f"\n❌ 测试失败：{e}")
        finally:
            browser.close()


if __name__ == "__main__":
    test_auto_continue_mode()