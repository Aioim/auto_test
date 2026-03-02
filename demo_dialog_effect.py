"""演示浏览器弹窗处理效果"""

from playwright.sync_api import sync_playwright
import sys
import os

# Add project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pages.base_page import BasePage


def demo_dialog_effect():
    """演示弹窗处理效果"""
    print("=== 演示浏览器弹窗处理效果 ===")
    
    with sync_playwright() as p:
        # 启动浏览器（无头模式，快速执行）
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 创建一个包含各种弹窗按钮的HTML页面
        html_content = """
        <html>
        <body>
            <h1>弹窗测试页面</h1>
            <button id="alert-btn">触发 Alert</button>
            <button id="confirm-btn">触发 Confirm</button>
            <div id="result"></div>
            <script>
                // Alert 弹窗
                document.getElementById('alert-btn').addEventListener('click', function() {
                    alert('这是一个测试 Alert 弹窗！');
                });
                
                // Confirm 弹窗
                document.getElementById('confirm-btn').addEventListener('click', function() {
                    const result = confirm('你确定要执行此操作吗？');
                    document.getElementById('result').textContent = result ? '用户点击了确定' : '用户点击了取消';
                });
            </script>
        </body>
        </html>
        """
        
        # 加载页面
        page.set_content(html_content)
        base_page = BasePage(page)
        
        print("\n1. 测试 Alert 弹窗处理")
        print("- 触发 Alert 弹窗...")
        # 使用 JavaScript 触发弹窗（避免 Playwright 点击超时问题）
        with page.expect_event("dialog"):
            page.evaluate("document.getElementById('alert-btn').click()")
        print("✅ Alert 弹窗已自动处理")
        
        print("\n2. 测试 Confirm 弹窗处理（接受）")
        print("- 触发 Confirm 弹窗...")
        # 使用 JavaScript 触发弹窗
        with page.expect_event("dialog") as dialog_info:
            page.evaluate("document.getElementById('confirm-btn').click()")
        dialog = dialog_info.value
        print(f"- 弹窗消息: {dialog.message}")
        dialog.accept()
        print("- 点击了确定按钮")
        result = page.text_content('#result')
        print(f"- 页面结果: {result}")
        print("✅ Confirm 弹窗已接受")
        
        print("\n3. 测试 Confirm 弹窗处理（取消）")
        print("- 触发 Confirm 弹窗...")
        # 使用 JavaScript 触发弹窗
        with page.expect_event("dialog") as dialog_info:
            page.evaluate("document.getElementById('confirm-btn').click()")
        dialog = dialog_info.value
        print(f"- 弹窗消息: {dialog.message}")
        dialog.dismiss()
        print("- 点击了取消按钮")
        result = page.text_content('#result')
        print(f"- 页面结果: {result}")
        print("✅ Confirm 弹窗已取消")
        
        print("\n4. 测试使用 BasePage 方法处理弹窗")
        print("- 触发 Alert 弹窗...")
        # 使用 JavaScript 触发弹窗
        page.evaluate("document.getElementById('alert-btn').click()")
        # 使用 BasePage 方法接受弹窗
        base_page.accept_dialog()
        print("✅ 使用 accept_dialog() 方法接受了弹窗")
        
        print("\n5. 测试获取弹窗消息")
        print("- 触发 Alert 弹窗...")
        # 使用 JavaScript 触发弹窗
        page.evaluate("document.getElementById('alert-btn').click()")
        # 使用 BasePage 方法获取弹窗消息
        message = base_page.get_dialog_message()
        print(f"- 获取到弹窗消息: {message}")
        # 手动接受弹窗
        page.keyboard.press('Enter')
        print("✅ 使用 get_dialog_message() 方法获取了弹窗消息")
        
        print("\n6. 测试 handle_dialog 方法")
        print("- 触发 Confirm 弹窗...")
        # 使用 JavaScript 触发弹窗
        page.evaluate("document.getElementById('confirm-btn').click()")
        # 使用 BasePage 方法处理弹窗
        message = base_page.handle_dialog(accept=True)
        print(f"- 获取到弹窗消息: {message}")
        print("- 点击了确定按钮")
        result = page.text_content('#result')
        print(f"- 页面结果: {result}")
        print("✅ 使用 handle_dialog() 方法处理了弹窗")
        
        print("\n7. 测试 wait_for_dialog 上下文管理器")
        print("- 触发 Alert 弹窗...")
        # 使用上下文管理器等待弹窗
        with base_page.wait_for_dialog():
            page.evaluate("document.getElementById('alert-btn').click()")
        print("✅ 使用 wait_for_dialog() 上下文管理器处理了弹窗")
        
        print("\n=== 所有测试完成 ===")
        print("✅ 浏览器弹窗处理功能工作正常！")
        
        # 关闭浏览器
        browser.close()


if __name__ == "__main__":
    demo_dialog_effect()
