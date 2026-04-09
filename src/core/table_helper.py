import re
from enum import Enum
from typing import Dict, List, Optional, Union

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

from logger import logger


class MatchMode(Enum):
    """文本匹配模式"""
    EXACT = "exact"      # 精确匹配
    PARTIAL = "partial"  # 部分匹配（contains）
    REGEX = "regex"      # 正则表达式匹配


class TableHelper:
    """表格/列表操作工具类（同步）"""

    # 可重试的异常类型
    RETRYABLE_EXCEPTIONS = (PlaywrightTimeoutError, PlaywrightError)

    def __init__(self, page: Page, default_row_selector: str = "tr"):
        self.page = page
        self.default_row_selector = default_row_selector

    @staticmethod
    def _apply_text_filter(
            locator: Locator,
            text: Union[str, re.Pattern],
            mode: MatchMode
    ) -> Locator:
        """
        根据匹配模式对定位器应用文本过滤

        Args:
            locator: 原始定位器
            text: 要匹配的文本或正则表达式
            mode: 匹配模式

        Returns:
            过滤后的定位器
        """
        if mode == MatchMode.REGEX:
            if not isinstance(text, re.Pattern):
                raise TypeError("REGEX 模式下必须提供 re.Pattern 对象")
            return locator.filter(has_text=text)
        elif mode == MatchMode.EXACT:
            return locator.filter(has_text=text, exact=True)
        else:  # MatchMode.PARTIAL
            return locator.filter(has_text=text)

    @staticmethod
    def _get_action_locator(
            row_locator: Locator,
            action_text: str,
            mode: MatchMode
    ) -> Locator:
        """
        根据匹配模式获取行内的操作按钮定位器

        Args:
            row_locator: 行定位器
            action_text: 按钮文本
            mode: 匹配模式

        Returns:
            操作按钮定位器
        """
        if mode == MatchMode.REGEX:
            # 假设 action_text 已经是正则表达式字符串，需转换为 Pattern
            # 此处简化处理：直接作为字符串传给 get_by_text，Playwright 会将其视为部分匹配
            # 若要支持真正的正则，需调用者传入 Pattern，此处为保持接口一致，先忽略复杂正则场景
            # 生产环境建议扩展为类似 _apply_text_filter 的方式
            return row_locator.get_by_text(re.compile(action_text))
        elif mode == MatchMode.EXACT:
            return row_locator.get_by_text(action_text, exact=True)
        else:
            return row_locator.get_by_text(action_text)

    def get_row_locator(
            self,
            search_conditions: Dict[str, Union[str, re.Pattern]],
            row_selector: Optional[str] = None,
            mode: MatchMode = MatchMode.PARTIAL
    ) -> Locator:
        """
        根据多条件获取行定位器

        Args:
            search_conditions: 查询条件字典 {"列名/文本": "值"或正则表达式}
            row_selector: 行选择器，默认使用初始化时的设置
            mode: 匹配模式，默认为部分匹配

        Returns:
            Locator 对象
        """
        if not search_conditions:
            logger.warning("查询条件为空")
            raise ValueError("搜索条件不能为空")

        selector = row_selector or self.default_row_selector
        row_locator = self.page.locator(selector)

        for label, value in search_conditions.items():
            row_locator = self._apply_text_filter(row_locator, value, mode)
            logger.debug(f"添加过滤条件：{label} = {value} (模式: {mode.value})")

        return row_locator

    def click_row_action(
            self,
            search_conditions: Dict[str, Union[str, re.Pattern]],
            action_text: str,
            row_selector: Optional[str] = None,
            timeout: Optional[float] = 5000,
            max_retries: int = 3,
            mode: MatchMode = MatchMode.PARTIAL,
            retry_interval: int = 1000
    ) -> bool:
        """
        在列表中根据多条件定位行，并点击行内的操作按钮（带智能重试）

        Args:
            search_conditions: 查询条件字典
            action_text: 要点击的按钮文本
            row_selector: 行选择器
            timeout: 单次操作超时时间（毫秒）
            max_retries: 最大重试次数
            mode: 匹配模式
            retry_interval: 重试间隔（毫秒）

        Returns:
            是否成功
        """
        # 提前进行参数校验，避免无效重试
        if not search_conditions:
            raise ValueError("搜索条件不能为空")

        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"尝试第 {attempt} 次点击操作...")

                row_locator = self.get_row_locator(
                    search_conditions, row_selector, mode=mode
                )
                action_btn = self._get_action_locator(row_locator, action_text, mode)
                action_btn.wait_for(state="visible", timeout=timeout)
                action_btn.wait_for(state="enabled", timeout=timeout)
                action_btn.click(timeout=timeout)

                logger.info(f"✅ 成功点击：条件={search_conditions}, 操作={action_text}")
                return True

            except self.RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                logger.warning(f"⚠️ 第 {attempt} 次尝试失败（可重试）：{e}")
            except Exception as e:
                # 不可重试异常直接抛出
                logger.error(f"❌ 发生不可重试错误：{e}")
                raise

            # 重试等待
            if attempt < max_retries:
                self.page.wait_for_timeout(retry_interval)
            else:
                logger.error(f"❌ 达到最大重试次数，操作失败")
                raise last_exception or RuntimeError("未知错误导致操作失败")

        return False

    def click_row_by_columns(
            self,
            column_conditions: Dict[int, Union[str, re.Pattern]],
            action_text: str,
            row_selector: str = "tr",
            timeout: Optional[float] = 5000,
            mode: MatchMode = MatchMode.EXACT
    ) -> bool:
        """
        基于列索引精确/部分/正则匹配（防止不同列有相同文本）

        Args:
            column_conditions: {列索引：文本或正则}，索引从 1 开始
            action_text: 要点击的按钮文本
            row_selector: 行选择器
            timeout: 超时时间
            mode: 匹配模式

        Returns:
            是否成功
        """
        if not column_conditions:
            logger.warning("列条件为空")
            raise ValueError("列条件不能为空")

        row_locator = self.page.locator(row_selector)

        for col_index, text in column_conditions.items():
            if col_index < 1:
                raise ValueError(f"列索引 {col_index} 无效，应为正数")

            # 构建单元格定位器
            cell_locator = self.page.locator(f"td:nth-child({col_index})")
            cell_locator = self._apply_text_filter(cell_locator, text, mode)
            logger.debug(f"添加列条件：第 {col_index} 列 = {text} (模式: {mode.value})")
            row_locator = row_locator.filter(has=cell_locator)

        action_btn = self._get_action_locator(row_locator, action_text, mode)
        action_btn.wait_for(state="visible", timeout=timeout)
        action_btn.wait_for(state="enabled", timeout=timeout)
        action_btn.click(timeout=timeout)

        logger.info(f"✅ 成功点击（列匹配）：条件={column_conditions}, 操作={action_text}")
        return True

    def get_row_data(
            self,
            search_conditions: Dict[str, Union[str, re.Pattern]],
            row_selector: Optional[str] = None,
            timeout: Optional[float] = 5000,
            mode: MatchMode = MatchMode.PARTIAL,
            max_rows: Optional[int] = None
    ) -> List[List[str]]:
        """
        获取所有匹配行的单元格文本数据

        Args:
            search_conditions: 查询条件
            row_selector: 行选择器
            timeout: 超时时间（毫秒）
            mode: 匹配模式
            max_rows: 最多返回的行数，None 表示返回全部

        Returns:
            二维列表，每个子列表代表一行的单元格文本
        """
        if not search_conditions:
            logger.warning("查询条件为空")
            raise ValueError("搜索条件不能为空")

        row_locator = self.get_row_locator(search_conditions, row_selector, mode=mode)
        row_locator.first.wait_for(state="visible", timeout=timeout)

        count = row_locator.count()
        if max_rows is not None:
            count = min(count, max_rows)

        all_rows_data = []
        for i in range(count):
            cells = row_locator.nth(i).locator("td").all_inner_texts()
            all_rows_data.append(cells)

        logger.info(f"📊 获取到 {len(all_rows_data)} 行数据")
        return all_rows_data

    def verify_row_exists(
            self,
            search_conditions: Dict[str, Union[str, re.Pattern]],
            row_selector: Optional[str] = None,
            timeout: Optional[float] = 3000,
            mode: MatchMode = MatchMode.PARTIAL
    ) -> bool:
        """
        验证行是否存在

        Args:
            search_conditions: 查询条件
            row_selector: 行选择器
            timeout: 超时时间（毫秒）
            mode: 匹配模式

        Returns:
            True/False
        """
        try:
            if not search_conditions:
                logger.warning("查询条件为空")
                return False

            row_locator = self.get_row_locator(search_conditions, row_selector, mode=mode)
            row_locator.first.wait_for(state="visible", timeout=timeout)
            logger.info(f"✅ 行存在：条件={search_conditions}")
            return True
        except PlaywrightTimeoutError:
            logger.warning(f"⚠️ 行不存在（超时）：条件={search_conditions}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ 行不存在（错误）：条件={search_conditions}, 错误={e}")
            return False

    def count_matching_rows(
            self,
            search_conditions: Dict[str, Union[str, re.Pattern]],
            row_selector: Optional[str] = None,
            timeout: Optional[float] = 3000,
            mode: MatchMode = MatchMode.PARTIAL
    ) -> int:
        """
        统计匹配的行数

        Args:
            search_conditions: 查询条件
            row_selector: 行选择器
            timeout: 超时时间（毫秒）
            mode: 匹配模式

        Returns:
            行数
        """
        try:
            if not search_conditions:
                logger.warning("查询条件为空")
                return 0

            row_locator = self.get_row_locator(search_conditions, row_selector, mode=mode)
            try:
                row_locator.first.wait_for(state="visible", timeout=timeout)
            except PlaywrightTimeoutError:
                logger.info(f"📊 匹配行数：0, 条件={search_conditions}")
                return 0

            count = row_locator.count()
            logger.info(f"📊 匹配行数：{count}, 条件={search_conditions}")
            return count
        except Exception as e:
            logger.error(f"统计匹配行数失败：{e}")
            raise


def click_table_row(
        page: Page,
        conditions: Dict[str, Union[str, re.Pattern]],
        action: str,
        **kwargs
) -> bool:
    """快速点击表格行操作（同步）"""
    helper = TableHelper(page)
    return helper.click_row_action(conditions, action, **kwargs)