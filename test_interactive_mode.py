"""
测试 ErrorMonitor 的交互模式功能
"""

from playwright.sync_api import sync_playwright
from src.utils.error_monitor import monitor_errors


def test_interactive_mode():
    """测试交互模式功能"""
    print("=== 测试 ErrorMonitor 交互模式 ===")
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        @monitor_errors(
            page=page,
            screenshot_on_error=True,
            screenshot_dir="./test-screenshots/interactive",
            raise_on_error=False,
            interactive_mode=True  # 启用交互模式
        )
        def test_with_interaction():
            """测试带有交互的场景"""
            print("\n1. 加载测试页面")
            page.goto("data:text/html,<h1>测试页面</h1>")
            
            print("2. 触发弹窗")
            page.evaluate("alert('测试弹窗消息')")
            
            print("3. 等待用户交互...")
            # 这里会触发交互模式，等待用户确认
            
            print("4. 继续执行测试")
            page.evaluate("console.error('测试控制台错误')")
            
        try:
            test_with_interaction()
            print("\n✅ 测试完成")
        except Exception as e:
            print(f"\n❌ 测试失败：{e}")
        finally:
            browser.close()


if __name__ == "__main__":
    test_interactive_mode()