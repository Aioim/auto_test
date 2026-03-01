"""简单测试浏览器弹窗处理功能"""

from playwright.sync_api import sync_playwright


def test_simple_dialog():
    """简单测试弹窗处理功能"""
    print("=== 简单测试浏览器弹窗处理功能 ===")
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 创建一个简单的HTML页面，包含触发alert的按钮
        html_content = """
        <html>
        <body>
            <button id="alert-btn">Show Alert</button>
            <script>
                document.getElementById('alert-btn').addEventListener('click', function() {
                    alert('This is a test alert!');
                });
            </script>
        </body>
        </html>
        """
        
        # 加载页面
        page.set_content(html_content)
        
        print("\n测试 Alert 对话框...")
        # 等待对话框并点击按钮
        with page.expect_event("dialog") as dialog_info:
            # 使用 JavaScript 点击按钮，避免 Playwright 的点击超时问题
            page.evaluate("document.getElementById('alert-btn').click()")
        dialog = dialog_info.value
        print(f"获取到对话框，消息: {dialog.message}")
        dialog.accept()
        print("✅ Alert 对话框已接受")
        
        print("\n测试 Confirm 对话框...")
        # 更新页面内容，添加 confirm 按钮
        html_content = """
        <html>
        <body>
            <button id="confirm-btn">Show Confirm</button>
            <div id="result"></div>
            <script>
                document.getElementById('confirm-btn').addEventListener('click', function() {
                    const result = confirm('Do you want to continue?');
                    document.getElementById('result').textContent = result ? 'Confirmed' : 'Cancelled';
                });
            </script>
        </body>
        </html>
        """
        page.set_content(html_content)
        
        # 等待对话框并点击按钮
        with page.expect_event("dialog") as dialog_info:
            # 使用 JavaScript 点击按钮
            page.evaluate("document.getElementById('confirm-btn').click()")
        dialog = dialog_info.value
        print(f"获取到对话框，消息: {dialog.message}")
        dialog.accept()
        print("✅ Confirm 对话框已接受")
        
        # 验证结果
        result = page.text_content('#result')
        print(f"结果: {result}")
        assert result == 'Confirmed'
        
        print("\n=== 所有测试完成 ===")
        
        # 关闭浏览器
        browser.close()


if __name__ == "__main__":
    test_simple_dialog()
