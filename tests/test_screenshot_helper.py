import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from utils.screenshot_helper import ScreenshotHelper, ScreenshotType, ScreenshotFormat, ScreenshotQuality, take_screenshot, highlight_and_screenshot


class TestScreenshotHelper(unittest.TestCase):
    """ScreenshotHelper 单元测试"""

    def setUp(self):
        """设置测试环境"""
        # 创建模拟的 Page 对象
        self.mock_page = Mock()
        self.mock_page.url = "https://example.com"
        self.mock_page.title = Mock(return_value="Example Domain")
        self.mock_page.viewport_size = {"width": 1920, "height": 1080}
        self.mock_page.screenshot = Mock(return_value=b"fake image data")
        self.mock_page.evaluate = Mock(return_value=True)
        self.mock_page.wait_for_timeout = Mock()
        
        # 创建模拟的 Locator 对象
        self.mock_locator = Mock()
        self.mock_element = Mock()
        self.mock_element.screenshot = Mock(return_value=b"fake element image")
        self.mock_element.evaluate = Mock(return_value=True)
        self.mock_element.is_visible = Mock(return_value=True)
        self.mock_locator.element_handle = Mock(return_value=self.mock_element)
        self.mock_locator.count = Mock(return_value=1)
        self.mock_locator.first = Mock(return_value=self.mock_locator)
        self.mock_locator.nth = Mock(return_value=self.mock_locator)
        
        self.mock_page.locator = Mock(return_value=self.mock_locator)

    def test_initialization(self):
        """测试初始化功能"""
        helper = ScreenshotHelper(self.mock_page)
        self.assertEqual(helper.page, self.mock_page)
        self.assertTrue(helper.screenshot_dir.exists())
        self.assertEqual(len(helper._history), 0)

    def test_sanitize_filename(self):
        """测试文件名清洗功能"""
        test_cases = [
            ("test screenshot", "test_screenshot"),
            ("test/screenshot", "test_screenshot"),
            ("test..screenshot", "test..screenshot"),
            ("test-screenshot", "test-screenshot"),
            ("test_screenshot", "test_screenshot"),
        ]
        
        for input_name, expected in test_cases:
            result = ScreenshotHelper._sanitize_filename(input_name)
            self.assertEqual(result, expected)

    def test_take_viewport_screenshot(self):
        """测试截取可视区域截图"""
        helper = ScreenshotHelper(self.mock_page)
        metadata = helper.take_viewport_screenshot(name="test_viewport")
        
        self.assertEqual(metadata.screenshot_type, ScreenshotType.VIEWPORT)
        self.assertEqual(len(helper._history), 1)
        self.mock_page.screenshot.assert_called_once()

    def test_take_full_page_screenshot(self):
        """测试截取完整页面截图"""
        helper = ScreenshotHelper(self.mock_page)
        metadata = helper.take_full_page_screenshot(name="test_full_page")
        
        self.assertEqual(metadata.screenshot_type, ScreenshotType.FULL_PAGE)
        self.assertEqual(len(helper._history), 1)
        self.mock_page.screenshot.assert_called_once()

    def test_take_element_screenshot(self):
        """测试截取元素截图"""
        helper = ScreenshotHelper(self.mock_page)
        metadata = helper.take_element_screenshot(
            selector="#test-element",
            name="test_element"
        )
        
        self.assertEqual(metadata.screenshot_type, ScreenshotType.ELEMENT)
        self.assertEqual(len(helper._history), 1)
        self.mock_element.screenshot.assert_called_once()

    def test_highlight_element(self):
        """测试高亮元素功能"""
        helper = ScreenshotHelper(self.mock_page)
        result = helper.highlight_element(selector="#test-element")
        
        self.assertTrue(result)
        self.mock_page.evaluate.assert_called()

    def test_remove_highlight(self):
        """测试移除高亮功能"""
        helper = ScreenshotHelper(self.mock_page)
        result = helper.remove_highlight()
        
        self.assertTrue(result)
        self.mock_page.evaluate.assert_called()

    def test_highlighted_context(self):
        """测试高亮上下文管理器"""
        helper = ScreenshotHelper(self.mock_page)
        
        with helper.highlighted_context(selector="#test-element"):
            # 上下文管理器内部
            pass
        
        # 确保高亮和移除都被调用
        self.assertEqual(self.mock_page.evaluate.call_count, 2)

    def test_get_screenshot_as_base64(self):
        """测试获取 Base64 编码的截图"""
        helper = ScreenshotHelper(self.mock_page)
        result = helper.get_screenshot_as_base64()
        
        self.assertIsInstance(result, str)
        self.mock_page.screenshot.assert_called_once()

    def test_cleanup_screenshots(self):
        """测试清理截图功能"""
        helper = ScreenshotHelper(self.mock_page)
        
        # 模拟截图历史
        helper._history = []
        
        # 测试清理功能
        deleted_count = helper.cleanup_screenshots(keep_latest=0)
        self.assertIsInstance(deleted_count, int)

    def test_export_history(self):
        """测试导出历史功能"""
        helper = ScreenshotHelper(self.mock_page)
        
        # 创建临时文件路径
        temp_file = Path("temp_history.json")
        
        try:
            helper.export_history(temp_file)
            self.assertTrue(temp_file.exists())
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_ensure_dir(self):
        """测试确保目录存在功能"""
        temp_dir = Path("temp_test_dir")
        
        try:
            result = ScreenshotHelper.ensure_dir(temp_dir)
            self.assertTrue(result.exists())
            self.assertEqual(result, temp_dir.resolve())
        finally:
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_get_screenshot_dir(self):
        """测试获取截图目录功能"""
        # 测试基本目录
        base_dir = ScreenshotHelper.get_screenshot_dir()
        self.assertIsInstance(base_dir, Path)
        
        # 测试带测试名的目录
        test_dir = ScreenshotHelper.get_screenshot_dir("test_case")
        self.assertIsInstance(test_dir, Path)
        self.assertTrue("test_case" in str(test_dir))


class TestScreenshotHelperIntegration(unittest.TestCase):
    """ScreenshotHelper 集成测试"""

    def test_take_screenshot_function(self):
        """测试 take_screenshot 便捷函数"""
        # 创建模拟的 Page 对象
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.title = Mock(return_value="Example Domain")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.screenshot = Mock(return_value=b"fake image data")
        mock_page.evaluate = Mock(return_value=True)
        mock_page.wait_for_timeout = Mock()
        mock_page.locator = Mock(return_value=Mock())
        
        # 测试函数调用
        with patch('utils.screenshot_helper.ScreenshotHelper') as mock_helper_class:
            mock_helper = Mock()
            mock_helper.take_screenshot = Mock(return_value=Mock(filepath="test.png"))
            mock_helper_class.return_value = mock_helper
            
            result = take_screenshot(mock_page, name="test")
            self.assertEqual(result, "test.png")
            mock_helper_class.assert_called_once()
            mock_helper.take_screenshot.assert_called_once()

    def test_highlight_and_screenshot_function(self):
        """测试 highlight_and_screenshot 便捷函数"""
        # 创建模拟的 Page 对象
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.title = Mock(return_value="Example Domain")
        mock_page.viewport_size = {"width": 1920, "height": 1080}
        mock_page.screenshot = Mock(return_value=b"fake image data")
        mock_page.evaluate = Mock(return_value=True)
        mock_page.wait_for_timeout = Mock()
        mock_page.locator = Mock(return_value=Mock())
        
        # 测试函数调用
        with patch('utils.screenshot_helper.ScreenshotHelper') as mock_helper_class:
            mock_helper = Mock()
            mock_helper.highlight_and_capture = Mock(return_value=Mock(filepath="test_highlight.png"))
            mock_helper_class.return_value = mock_helper
            
            result = highlight_and_screenshot(mock_page, selector="#test", name="test_highlight")
            self.assertEqual(result, "test_highlight.png")
            mock_helper_class.assert_called_once()
            mock_helper.highlight_and_capture.assert_called_once()


if __name__ == '__main__':
    unittest.main()
