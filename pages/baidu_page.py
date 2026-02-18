"""
百度搜索页面对象
"""
from typing import Dict, Any

from base_page import BasePage
from baidu_selector import search_input, search_results, search_button, search_suggestions, first_result_title, \
    baidu_logo

from utils.logger import logger



class BaiduPage(BasePage):
    """百度搜索页面"""

    # ===== 核心元素选择器 =====
    # 搜索输入框 - 多策略定位（百度经常变更结构，提供多种备选）


    # ===== 页面操作方法 =====
    def open(self) -> None:
        """打开百度首页"""
        self.goto("https://www.baidu.com")
        # 等待搜索框可见，确保页面加载完成
        self.wait_for(search_input, state="visible", timeout=10000)

    def search(self, keyword: str) -> None:
        """
        执行搜索操作

        Args:
            keyword: 搜索关键词
        """
        # 清空输入框（防御性操作）
        self.clear(search_input)

        # 输入关键词
        self.fill(search_input, keyword)

        # 等待搜索建议出现（可选，增强稳定性）
        if self.exists(search_suggestions, timeout=1000):
            self.wait_for_timeout(300)  # 短暂等待建议稳定

        # 点击搜索按钮
        self.click(search_button)

        # 等待搜索结果加载
        self.wait_for(search_results, state="detached", timeout=10000)

    def get_first_result_title(self) -> str:
        """获取第一个搜索结果的标题"""
        return self.text(first_result_title)

    def has_search_results(self) -> bool:
        """检查是否有搜索结果"""
        return self.exists(search_results, timeout=3000)

    def is_search_input_visible(self) -> bool:
        """检查搜索输入框是否可见"""
        return self.is_visible(search_input)

    # ===== 高级操作 =====

    def search_with_keyboard(self, keyword: str) -> None:
        """
        使用键盘回车执行搜索（不点击按钮）
        """
        self.clear(search_input)
        self.fill(search_input, keyword)
        self.press(search_input, "Enter")
        self.wait_for(search_results, state="visible", timeout=10000)

    def verify_search_flow(self, keyword: str, expected_text: str) -> bool:
        """
        完整的搜索验证流程

        Args:
            keyword: 搜索关键词
            expected_text: 期望在结果中出现的文本

        Returns:
            bool: 验证是否成功
        """
        try:
            # 1. 打开页面
            self.open()

            # 2. 验证页面加载
            self.assert_visible(baidu_logo, "百度Logo应可见")
            self.assert_visible(search_input, "搜索框应可见")

            # 3. 执行搜索
            self.search(keyword)

            # 4. 验证结果
            self.assert_exists(search_results, "应存在搜索结果")
            self.assert_text(first_result_title, expected_text,
                             message=f"第一个结果应包含 '{expected_text}'")

            return True

        except AssertionError as e:
            # 捕获断言失败并截图
            self.screenshot_on_failure(f"search_verification_failed_{keyword}")
            logger.info(f"搜索验证失败: {e}")
            raise

    # ===== 调试辅助 =====
    def debug_search_elements(self) -> Dict[str, Any]:
        """调试搜索相关元素的状态"""
        return {
            "search_input": {
                "exists": self.exists(search_input),
                "visible": self.is_visible(search_input),
                "enabled": self.is_enabled(search_input),
                "debug_info": self.debug_info(search_input)
            },
            "search_button": {
                "exists": self.exists(search_button),
                "visible": self.is_visible(search_button),
                "enabled": self.is_enabled(search_button),
                "debug_info": self.debug_info(search_button)
            },
            "logo": {
                "exists": self.exists(baidu_logo),
                "debug_info": self.debug_info(baidu_logo)
            }
        }

if __name__=='__main__':
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        baidu_page= BaiduPage(page)
        baidu_page.open()
        logger.info(baidu_page.debug_search_elements())
        baidu_page.search('111111111')

        page.pause()