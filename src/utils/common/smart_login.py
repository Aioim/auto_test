"""
from src.utils.common.smart_login import SmartLogin
from pages.components.login_page import login_page

def test_basic_login():
    # 创建 SmartLogin 实例
    smart_login = SmartLogin("username", "password", login_page)
    
    # 执行智能登录
    page = smart_login.smart_login()
    
    # 登录后执行操作
    page.goto("https://example.com/dashboard")
    print("登录成功，当前页面:", page.url)
    
    # 关闭浏览器
    smart_login.stop_browser()
    
from src.utils.common.smart_login import SmartLogin
from pages.components.login_page import login_page

def test_task_with_login():
    #使用 execute_with_login 执行任务
    
    def task(page, context):
        #要执行的任务函数
        # 执行需要登录的操作
        page.goto("https://example.com/profile")
        page.click("text=编辑资料")
        page.fill("input[name='name']", "新名称")
        page.click("text=保存")
        print("资料更新成功")
        return "任务执行完成"
    
    # 创建 SmartLogin 实例
    smart_login = SmartLogin("username", "password", login_page)
    
    # 执行任务
    result = smart_login.execute_with_login(task)
    print("任务结果:", result)
    # 浏览器会自动关闭
    
from src.utils.common.smart_login import SmartLogin
from pages.components.login_page import login_page

def test_with_statement():
    #使用 with 语句管理资源
    # 创建 SmartLogin 实例
    smart_login = SmartLogin("username", "password", login_page)
    
    # 使用 with 语句
    with smart_login as (page, context):
        # 登录后执行操作
        page.goto("https://example.com/settings")
        print("当前页面:", page.url)
        # 执行其他操作...
    
    # 退出 with 块后，浏览器会自动关闭
    print("浏览器已关闭")
from src.utils.common.smart_login import SmartLogin
from pages.components.login_page import login_page

def test_multiple_tasks():
    #批量执行多个任务
    
    def task1(page, context):
        #任务 1: 查看个人资料
        page.goto("https://example.com/profile")
        print("任务 1 完成: 查看个人资料")
    
    def task2(page, context):
        #任务 2: 查看订单列表
        page.goto("https://example.com/orders")
        print("任务 2 完成: 查看订单列表")
    
    def task3(page, context):
        #任务 3: 查看设置
        page.goto("https://example.com/settings")
        print("任务 3 完成: 查看设置")
    
    # 创建 SmartLogin 实例
    smart_login = SmartLogin("username", "password", login_page)
    
    # 执行多个任务
    tasks = [task1, task2, task3]
    for i, task in enumerate(tasks, 1):
        print(f"开始执行任务 {i}...")
        smart_login.execute_with_login(task)
        print(f"任务 {i} 执行完成\n")
"""
import os
from pathlib import Path
from typing import Callable, Optional, Any
from playwright.sync_api import Page, sync_playwright

from config import settings, PROJECT_ROOT
from pages.components.login_page import login_page
from utils.logger import logger


class SmartLogin:
    def __init__(self, username: str, password: str, login_func: Callable[[str, str], None]):
        """
        初始化 SmartLogin

        Args:
            username: 用户名
            password: 密码
            login_func: 登录函数，接受用户名和密码作为参数
        """
        self.page: Optional[Page] = None
        self.login_func = login_func
        self.username = username
        self.password = password
        self.context = None
        self.browser = None
        self.playwright = None
        self.auth_file = self.get_auth_file()
        self.ignore_dialog = {
            "permissions": settings.browser.permissions,
            "geolocation": settings.browser.geolocation,
            "viewport": settings.browser.viewport,
        }

    def start_browser(self, headless: bool = False):
        """
        启动浏览器

        Args:
            headless: 是否以无头模式启动浏览器

        Raises:
            Exception: 浏览器启动失败时抛出
        """
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("✅ 浏览器已启动")
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败：{e}")
            if self.playwright:
                try:
                    self.playwright.stop()
                except Exception:
                    pass
            raise

    def stop_browser(self):
        """
        关闭浏览器
        """
        if self.browser:
            try:
                self.browser.close()
                logger.info("🛑 浏览器已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭浏览器失败：{e}")
        
        if self.playwright:
            try:
                self.playwright.stop()
                logger.info("🛑 Playwright 已停止")
            except Exception as e:
                logger.error(f"❌ 停止 Playwright 失败：{e}")

    def get_auth_file(self) -> str:
        """
        获取账号对应的状态文件路径

        Returns:
            str: 状态文件路径
        """
        auth_dir = PROJECT_ROOT / settings.browser.auth_dir
        # 确保目录存在
        auth_dir.mkdir(exist_ok=True, parents=True)
        return str(auth_dir / f"auth_{self.username}.json")

    def save_state(self):
        """
        保存登录状态
        """
        try:
            self.context.storage_state(path=self.auth_file)
            logger.info(f"💾 账号 {self.username} 状态已保存")
        except Exception as e:
            logger.error(f"❌ 保存状态失败：{e}")

    def load_state(self) -> bool:
        """
        加载已保存的登录状态

        Returns:
            bool: 是否成功加载状态
        """
        if not os.path.exists(self.auth_file):
            logger.info(f"📁 未找到状态文件：{self.auth_file}")
            return False

        try:
            self.context = self.browser.new_context(**self.ignore_dialog, storage_state=self.auth_file)
            self.page = self.context.new_page()
            logger.info(f"✅ 已加载账号 {self.username} 的登录状态")
            return True
        except Exception as e:
            logger.warning(f"⚠️ 加载状态失败：{e}")
            if os.path.exists(self.auth_file):
                os.remove(self.auth_file)
            return False

    def login(self):
        """
        执行登录操作
        """
        try:
            self.context = self.browser.new_context(**self.ignore_dialog)
            self.page = self.context.new_page()
            self.login_func(self.username, self.password)
            logger.info(f"✅ 账号 {self.username} 登录成功")
        except Exception as e:
            logger.error(f"❌ 登录失败：{e}")
            raise

    def smart_login(self) -> Page:
        """
        智能登录

        1、打开浏览器
        2、加载状态文件
        ---成功，加载状态文件登录，返回page
        ---失败，重新登录，保存状态文件，返回page

        Returns:
            Page: 登录后的页面对象
        """
        try:
            self.start_browser()
            
            # 获取 base_url 配置
            base_url = getattr(settings, "base_url", None)
            if not base_url:
                logger.error("❌ 未配置 base_url")
                raise ValueError("base_url 未配置")
                
            if self.load_state():
                self.page.goto(base_url)
                if "login" in self.page.url.lower():
                    logger.info("⚠️ 登录状态已失效，重新登录...")
                    if os.path.exists(self.auth_file):
                        os.remove(self.auth_file)
                    self.login()
                    self.save_state()
                else:
                    logger.info("✅ 登录状态有效")
            else:
                self.login()
                self.save_state()
            return self.page
        except Exception:
            # 发生异常时确保浏览器关闭
            self.stop_browser()
            raise

    def execute_with_login(self, task_func: Callable[[Page, Any], Any], *args, **kwargs):
        """
        装饰器模式：确保登录后执行任务

        Args:
            task_func: 要执行的任务函数，接受 page 和 context 作为参数
            *args: 任务函数的位置参数
            **kwargs: 任务函数的关键字参数

        Returns:
            任务函数的返回值
        """
        try:
            self.start_browser()

            page = self.smart_login()

            # 执行任务
            result = task_func(self.page, self.context, *args, **kwargs)

            return result

        finally:
            self.stop_browser()

    def __enter__(self):
        """
        支持 with 语句

        Returns:
            Tuple[Page, Any]: 登录后的页面对象和上下文
        """
        try:
            self.start_browser()
            page = self.smart_login()
            return page, self.context
        except Exception as e:
            self.stop_browser()
            raise RuntimeError(f"登录失败: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        自动释放资源

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常回溯

        Returns:
            bool: 是否吞掉异常，这里返回 False，不吞异常
        """
        self.stop_browser()
        return False  # 不吞异常


if __name__ == '__main__':
    smart_login = SmartLogin("username", "password", login_page)
    page = smart_login.smart_login()
    page.pause()
    smart_login.stop_browser()