import logging
from typing import Dict, List, Optional, Union
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from utils.logger import logger

# ==================== 同步版本 ====================

class TableHelper:
    """表格/列表操作工具类（同步）"""
    
    def __init__(self, page: Page, default_row_selector: str = "tr"):
        self.page = page
        self.default_row_selector = default_row_selector
    
    def get_row_locator(
        self, 
        search_conditions: Dict[str, str], 
        row_selector: Optional[str] = None,
        exact: bool = False
    ) -> Locator:
        """
        根据多条件获取行定位器
        
        Args:
            search_conditions: 查询条件字典 {"列名/文本": "值"}
            row_selector: 行选择器，默认使用初始化时的设置
            exact: 是否精确匹配文本

        Returns:
            Locator 对象
        """
        if not search_conditions:
            logger.warning("查询条件为空")
            raise ValueError("搜索条件不能为空")
            
        selector = row_selector or self.default_row_selector
        row_locator = self.page.locator(selector)
        
        for label, value in search_conditions.items():
            if exact:
                row_locator = row_locator.filter(has_text=value)
            else:
                row_locator = row_locator.filter(has_text=value)
            logger.debug(f"添加过滤条件：{label} = {value}")
        
        return row_locator
    
    def click_row_action(
        self,
        search_conditions: Dict[str, str],
        action_text: str,
        row_selector: Optional[str] = None,
        timeout: Optional[float] = 5000,
        max_retries: int = 3,
        exact: bool = False
    ) -> bool:
        """
        在列表中根据多条件定位行，并点击行内的操作按钮（带重试）
        
        Args:
            search_conditions: 查询条件字典
            action_text: 要点击的按钮文本
            row_selector: 行选择器
            timeout: 单次操作超时时间（毫秒）
            max_retries: 最大重试次数
            exact: 是否精确匹配文本

        Returns:
            是否成功
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"尝试第 {attempt} 次点击操作...")
                
                row_locator = self.get_row_locator(search_conditions, row_selector, exact)
                action_btn = row_locator.get_by_text(action_text, exact=exact)
                
                # 等待按钮可见且可点击
                action_btn.wait_for(state="visible", timeout=timeout)
                action_btn.wait_for(state="enabled", timeout=timeout)
                
                # 点击
                action_btn.click(timeout=timeout)
                
                logger.info(f"✅ 成功点击：条件={search_conditions}, 操作={action_text}")
                return True
                
            except PlaywrightTimeoutError as e:
                logger.warning(f"⚠️ 第 {attempt} 次尝试超时：{e}")
                if attempt < max_retries:
                    self.page.wait_for_timeout(1000)  # 等待 1 秒后重试
                else:
                    logger.error(f"❌ 达到最大重试次数，操作失败")
                    raise
            except Exception as e:
                logger.error(f"❌ 第 {attempt} 次尝试发生错误：{e}")
                if attempt < max_retries:
                    self.page.wait_for_timeout(1000)
                else:
                    raise
        
        return False
    
    def click_row_by_columns(
        self,
        column_conditions: Dict[int, str],
        action_text: str,
        row_selector: str = "tr",
        timeout: Optional[float] = 5000
    ) -> bool:
        """
        基于列索引精确匹配（防止不同列有相同文本）
        
        Args:
            column_conditions: {列索引：文本}，索引从 1 开始
                              例如：{1: "张三", 3: "启用"}
            action_text: 要点击的按钮文本
            row_selector: 行选择器
            timeout: 超时时间

        Returns:
            是否成功
        """
        try:
            if not column_conditions:
                logger.warning("列条件为空")
                raise ValueError("列条件不能为空")
                
            row_locator = self.page.locator(row_selector)
            
            for col_index, text in column_conditions.items():
                if col_index < 1:
                    logger.warning(f"列索引 {col_index} 无效，应为正数")
                    raise ValueError(f"列索引 {col_index} 无效，应为正数")
                    
                # 精确匹配指定列
                row_locator = row_locator.filter(
                    has=self.page.locator(f"td:nth-child({col_index})").filter(has_text=text)
                )
                logger.debug(f"添加列条件：第 {col_index} 列 = {text}")
            
            action_btn = row_locator.get_by_text(action_text)
            action_btn.wait_for(state="visible", timeout=timeout)
            action_btn.wait_for(state="enabled", timeout=timeout)
            action_btn.click(timeout=timeout)
            
            logger.info(f"✅ 成功点击（列匹配）：条件={column_conditions}, 操作={action_text}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 列匹配点击失败：{e}")
            raise
    
    def get_row_data(
        self,
        search_conditions: Dict[str, str],
        row_selector: Optional[str] = None,
        timeout: Optional[float] = 5000
    ) -> List[str]:
        """
        获取匹配行的所有单元格文本数据
        
        Args:
            search_conditions: 查询条件
            row_selector: 行选择器
            timeout: 超时时间（毫秒）

        Returns:
            单元格文本列表
        """
        if not search_conditions:
            logger.warning("查询条件为空")
            raise ValueError("搜索条件不能为空")
            
        row_locator = self.get_row_locator(search_conditions, row_selector)
        row_locator.first.wait_for(state="visible", timeout=timeout)
        
        cells = row_locator.first.locator("td").all_inner_texts()
        logger.info(f"📊 获取行数据：{cells}")
        return cells
    
    def verify_row_exists(
        self,
        search_conditions: Dict[str, str],
        row_selector: Optional[str] = None,
        timeout: Optional[float] = 3000
    ) -> bool:
        """
        验证行是否存在
        
        Args:
            search_conditions: 查询条件
            row_selector: 行选择器
            timeout: 超时时间（毫秒）

        Returns:
            True/False
        """
        try:
            if not search_conditions:
                logger.warning("查询条件为空")
                return False
                
            row_locator = self.get_row_locator(search_conditions, row_selector)
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
        search_conditions: Dict[str, str],
        row_selector: Optional[str] = None,
        timeout: Optional[float] = 3000
    ) -> int:
        """
        统计匹配的行数
        
        Args:
            search_conditions: 查询条件
            row_selector: 行选择器
            timeout: 超时时间（毫秒）

        Returns:
            行数
        """
        try:
            if not search_conditions:
                logger.warning("查询条件为空")
                return 0
                
            row_locator = self.get_row_locator(search_conditions, row_selector)
            
            # 等待至少一行加载完成
            try:
                row_locator.first.wait_for(state="visible", timeout=timeout)
            except PlaywrightTimeoutError:
                # 没有匹配的行，返回 0
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
    conditions: Dict[str, str],
    action: str,
    **kwargs
) -> bool:
    """快速点击表格行操作（同步）"""
    helper = TableHelper(page)
    return helper.click_row_action(conditions, action, **kwargs)
