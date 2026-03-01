"""演示浏览器弹窗处理功能"""

from playwright.sync_api import sync_playwright
import sys
import os
import time

# Add project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pages.base_page import BasePage


def demo_dialog_handling():
    """演示弹窗处理功能"""
    print("=== 演示浏览器弹窗处理功能 ===")
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)  # 无头模式，适合自动化测试
        page = browser.new_page()
        
        # 创建一个简单的HTML页面，包含触发各种对话框的按钮
        html_content = """
        <html>
        <body>
            <h1>对话框测试页面</h1>
            <button id="alert-btn">显示 Alert</button>
            <button id="confirm-btn">显示 Confirm</button>
            <button id="prompt-btn">显示 Prompt</button>
            <div id="result"></div>
            <script>
                document.getElementById('alert-btn').addEventListener('click', function() {
                    alert('这是一个测试 Alert！');
                });
                
                document.getElementById('confirm-btn').addEventListener('click', function() {
                    const result = confirm('你确定要继续吗？');
                    document.getElementById('result').textContent = result ? '已确认' : '已取消';
                });
                
                document.getElementById('prompt-btn').addEventListener('click', function() {
                    const result = prompt('请输入你的名字：', '张三');
                    document.getElementById('result').textContent = result ? '你好，' + result : '未输入';
                });
            </script>
        </body>
        </html>
        """
        
        # 加载页面
        page.set_content(html_content)
        base_page = BasePage(page)
        
        print("\n1. 测试 Alert 对话框（接受）")
        print("点击 '显示 Alert' 按钮...")
        # 使用 expect_event 等待对话框，然后点击按钮
        with page.expect_event("dialog") as dialog_info:
            page.click('#alert-btn')
        dialog = dialog_info.value
        dialog.accept()
        print("✅ Alert 对话框已接受")
        
        print("\n2. 测试 Confirm 对话框（取消）")
        print("点击 '显示 Confirm' 按钮...")
        # 使用 expect_event 等待对话框，然后点击按钮
        with page.expect_event("dialog") as dialog_info:
            page.click('#confirm-btn')
        dialog = dialog_info.value
        dialog.dismiss()
        print("✅ Confirm 对话框已取消")
        
        print("\n3. 测试 Confirm 对话框（接受）")
        print("点击 '显示 Confirm' 按钮...")
        # 使用 expect_event 等待对话框，然后点击按钮
        with page.expect_event("dialog") as dialog_info:
            page.click('#confirm-btn')
        dialog = dialog_info.value
        dialog.accept()
        print("✅ Confirm 对话框已接受")
        
        print("\n4. 测试获取对话框消息")
        print("点击 '显示 Alert' 按钮...")
        # 使用 expect_event 等待对话框，然后点击按钮
        with page.expect_event("dialog") as dialog_info:
            page.click('#alert-btn')
        dialog = dialog_info.value
        message = dialog.message
        dialog.accept()
        print(f"✅ 获取到对话框消息: {message}")
        
        print("\n5. 测试处理对话框并返回消息")
        print("点击 '显示 Confirm' 按钮...")
        # 使用 expect_event 等待对话框，然后点击按钮
        with page.expect_event("dialog") as dialog_info:
            page.click('#confirm-btn')
        dialog = dialog_info.value
        message = dialog.message
        dialog.accept()
        print(f"✅ 处理对话框，消息: {message}")
        
        print("\n6. 测试使用上下文管理器等待对话框")
        print("点击 '显示 Alert' 按钮...")
        # 使用上下文管理器等待对话框
        with base_page.wait_for_dialog() as dialog_info:
            page.click('#alert-btn')
        dialog = dialog_info.value
        print(f"✅ 使用上下文管理器获取到对话框，消息: {dialog.message}")
        dialog.accept()
        
        print("\n=== 所有测试完成 ===")
        
        # 关闭浏览器
        browser.close()


if __name__ == "__main__":
    demo_dialog_handling()
