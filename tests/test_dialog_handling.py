"""测试浏览器弹窗处理功能"""

import pytest
import sys
import os
from playwright.sync_api import sync_playwright

# Add project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages.base_page import BasePage


class TestDialogHandling:
    """测试浏览器弹窗处理"""

    def test_accept_dialog(self):
        """测试接受对话框"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
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
            base_page = BasePage(page)
            
            # 先等待对话框，然后点击按钮
            with page.expect_event("dialog") as dialog_info:
                page.click('#alert-btn')
            dialog = dialog_info.value
            dialog.accept()
            
            # 验证页面仍然可用
            assert page.title() == ""
            
            browser.close()

    def test_dismiss_dialog(self):
        """测试取消对话框"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # 创建一个简单的HTML页面，包含触发confirm的按钮
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
            
            # 加载页面
            page.set_content(html_content)
            base_page = BasePage(page)
            
            # 先等待对话框，然后点击按钮
            with page.expect_event("dialog") as dialog_info:
                page.click('#confirm-btn')
            dialog = dialog_info.value
            dialog.dismiss()
            
            # 验证取消结果
            assert page.text_content('#result') == 'Cancelled'
            
            browser.close()

    def test_get_dialog_message(self):
        """测试获取对话框消息"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # 创建一个简单的HTML页面，包含触发alert的按钮
            html_content = """
            <html>
            <body>
                <button id="alert-btn">Show Alert</button>
                <script>
                    document.getElementById('alert-btn').addEventListener('click', function() {
                        alert('This is a test alert message!');
                    });
                </script>
            </body>
            </html>
            """
            
            # 加载页面
            page.set_content(html_content)
            base_page = BasePage(page)
            
            # 先等待对话框，然后点击按钮
            with page.expect_event("dialog") as dialog_info:
                page.click('#alert-btn')
            dialog = dialog_info.value
            message = dialog.message
            dialog.accept()
            
            # 验证消息内容
            assert message == 'This is a test alert message!'
            
            browser.close()

    def test_handle_dialog_accept(self):
        """测试处理对话框（接受）"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # 创建一个简单的HTML页面，包含触发confirm的按钮
            html_content = """
            <html>
            <body>
                <button id="confirm-btn">Show Confirm</button>
                <div id="result"></div>
                <script>
                    document.getElementById('confirm-btn').addEventListener('click', function() {
                        const result = confirm('Do you want to accept?');
                        document.getElementById('result').textContent = result ? 'Confirmed' : 'Cancelled';
                    });
                </script>
            </body>
            </html>
            """
            
            # 加载页面
            page.set_content(html_content)
            base_page = BasePage(page)
            
            # 先等待对话框，然后点击按钮
            with page.expect_event("dialog") as dialog_info:
                page.click('#confirm-btn')
            dialog = dialog_info.value
            message = dialog.message
            dialog.accept()
            
            # 验证消息内容和结果
            assert message == 'Do you want to accept?'
            assert page.text_content('#result') == 'Confirmed'
            
            browser.close()

    def test_handle_dialog_dismiss(self):
        """测试处理对话框（取消）"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # 创建一个简单的HTML页面，包含触发confirm的按钮
            html_content = """
            <html>
            <body>
                <button id="confirm-btn">Show Confirm</button>
                <div id="result"></div>
                <script>
                    document.getElementById('confirm-btn').addEventListener('click', function() {
                        const result = confirm('Do you want to accept?');
                        document.getElementById('result').textContent = result ? 'Confirmed' : 'Cancelled';
                    });
                </script>
            </body>
            </html>
            """
            
            # 加载页面
            page.set_content(html_content)
            base_page = BasePage(page)
            
            # 先等待对话框，然后点击按钮
            with page.expect_event("dialog") as dialog_info:
                page.click('#confirm-btn')
            dialog = dialog_info.value
            message = dialog.message
            dialog.dismiss()
            
            # 验证消息内容和结果
            assert message == 'Do you want to accept?'
            assert page.text_content('#result') == 'Cancelled'
            
            browser.close()

    def test_wait_for_dialog_context_manager(self):
        """测试使用上下文管理器等待对话框"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # 创建一个简单的HTML页面，包含触发alert的按钮
            html_content = """
            <html>
            <body>
                <button id="alert-btn">Show Alert</button>
                <script>
                    document.getElementById('alert-btn').addEventListener('click', function() {
                        alert('Context manager test!');
                    });
                </script>
            </body>
            </html>
            """
            
            # 加载页面
            page.set_content(html_content)
            base_page = BasePage(page)
            
            # 使用上下文管理器等待对话框
            with base_page.wait_for_dialog() as dialog_info:
                page.click('#alert-btn')
            dialog = dialog_info.value
            
            # 验证对话框消息并接受
            assert dialog.message == 'Context manager test!'
            dialog.accept()
            
            # 验证页面仍然可用
            assert page.title() == ""
            
            browser.close()
