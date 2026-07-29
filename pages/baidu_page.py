"""
百度搜索页面对象
"""
from typing import Any
from base_page import BasePage
from logger import logger

# ===== 选择器定义 =====
# 百度 2026 新版页面结构：textarea 搜索框 + AI 建议列表
# 注意：百度首页与搜索结果页的 DOM 结构不同，部分选择器仅在一侧生效

search_input = "#chat-textarea"
"""搜索输入框（textarea，首页和搜索结果页均可见）"""

search_button = "button:has-text('百度一下')"
"""搜索按钮（仅首页可见；搜索结果页使用 #chat-submit-button）"""

search_results = "#content_left .result-op"
"""搜索结果列表项（仅搜索结果页有效）"""

first_result_title = "#content_left .result-op h3 a"
"""第一个搜索结果的标题链接（仅搜索结果页有效）"""

search_suggestions = ".bdsug-item"
"""搜索建议下拉项（仅首页有效；触发条件：输入字符后自动出现）"""

baidu_logo = "#s_lg_img"
"""百度 Logo（仅首页有效）"""


class BaiduPage(BasePage):
    """百度搜索页面"""

    # ===== 页面操作方法 =====
    def open(self) -> None:
        """打开百度首页"""
        self.goto("https://www.baidu.com")
        # 等待搜索框可见，确保页面加载完成
        self.wait_for(search_input, state="visible", timeout=10000)

    def search(self, keyword: str) -> None:
        """
        执行搜索操作（键盘回车提交，兼容首页和搜索结果页）

        Args:
            keyword: 搜索关键词
        """
        # 输入关键词
        self.fill(search_input, keyword)

        # 等待搜索建议出现（可选，增强稳定性）
        if self.exists(search_suggestions, timeout=1000):
            self.wait_for_timeout(300)

        # 回车提交（兼容首页和搜索结果页，避免按钮选择器仅首页可见的问题）
        self.press(search_input, "Enter")

        # 等待搜索结果加载
        self.wait_for(search_results, state="visible", timeout=10000)

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
        使用键盘回车执行搜索（等同于 search()，保留以兼容旧调用）
        """
        self.search(keyword)

    def verify_search_flow(self, keyword: str, expected_text: str) -> None:
        """
        完整的搜索验证流程，验证失败时抛出 AssertionError

        Args:
            keyword: 搜索关键词
            expected_text: 期望在结果中出现的文本
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

        except AssertionError as e:
            # 捕获断言失败并截图
            self.screenshot_on_failure(f"search_verification_failed_{keyword}")
            logger.info(f"搜索验证失败: {e}")
            raise

    # ===== 调试辅助 =====
    def debug_search_elements(self) -> dict[str, Any]:
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


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            permissions=["geolocation", "notifications", "clipboard-read"],
            geolocation={"latitude": 31.2304, "longitude": 121.4737}
        )
        page = context.new_page()
        baidu_page = BaiduPage(page)
        baidu_page.open()
        baidu_page.search('111111111')

        page.pause()
