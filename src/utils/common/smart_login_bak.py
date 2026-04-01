import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Any, Tuple, List, Dict, Union, TypeVar
from playwright.sync_api import Page, Browser, BrowserContext, sync_playwright, Playwright, Error as PlaywrightError
from config import settings, PROJECT_ROOT
from utils.logger import logger as default_logger

T = TypeVar('T')


class SmartLogin:
    def __init__(
        self,
        username: str,
        password: str,
        login_func: Callable[[Page, str, str], None],
        auth_identity: Optional[str] = None,
        logger=default_logger,
        config=settings,
        base_url: Optional[str] = None,
        browser_type: str = "chromium",
        timeout: int = 30000,
        retry_count: int = 3,
    ):
        """
        智能登录初始化
        Args:
            username: 用户名
            password: 密码
            login_func: 登录函数, 接受 page, 用户名, 密码参数
            auth_identity: 可选, 唯一身份信息用于状态文件命名, 默认用户名
            logger: 日志对象
            config: 配置对象（如 settings）
            base_url: 目标网站基础URL，若未提供则从 config 获取
            browser_type: 浏览器类型，支持 'chromium', 'firefox', 'webkit'
            timeout: 页面操作默认超时时间（毫秒）
            retry_count: 登录重试次数
        """
        self.username = username
        self.password = password
        self.login_func = login_func
        self.logger = logger
        self.config = config
        self.auth_identity = auth_identity or username
        self.auth_file = self._get_auth_file()
        self.base_url = base_url or getattr(config, "base_url", None)
        if not self.base_url:
            raise ValueError("base_url 未配置，请通过参数或 config 提供")
        self.browser_type = browser_type
        self.timeout = timeout
        self.retry_count = retry_count

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        self.is_browser_started = False
        self.context_options = {
            "permissions": self.config.browser.permissions,
            "geolocation": self.config.browser.geolocation,
            "viewport": self.config.browser.viewport,
        }

    def _get_auth_file(self) -> str:
        """获取状态文件路径，并确保目录存在"""
        auth_dir = PROJECT_ROOT / self.config.browser.auth_dir
        auth_dir.mkdir(exist_ok=True, parents=True)
        return str(auth_dir / f"auth_{self.auth_identity}.json")

    def start_browser(self, headless: bool = False):
        """启动浏览器"""
        if self.is_browser_started:
            return
        try:
            self.playwright = sync_playwright().start()
            browser_launcher = getattr(self.playwright, self.browser_type)
            self.browser = browser_launcher.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.is_browser_started = True
            self.logger.info("浏览器已启动")
        except Exception as e:
            self.logger.error(f"浏览器启动失败：{e}")
            self.is_browser_started = False
            self._stop_playwright_safely()
            raise

    def stop_browser(self):
        """停止浏览器并释放所有资源"""
        self._close_page_safely()
        self._close_context_safely()
        if self.browser:
            try:
                self.browser.close()
                self.logger.info("浏览器已关闭")
            except Exception as e:
                self.logger.error(f"关闭浏览器失败：{e}")
        self._stop_playwright_safely()
        self.is_browser_started = False

    def _close_page_safely(self):
        """安全关闭页面"""
        if self.page:
            try:
                self.page.close()
            except Exception as e:
                self.logger.warning(f"关闭页面失败: {e}")
            finally:
                self.page = None

    def _close_context_safely(self):
        """安全关闭上下文"""
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                self.logger.warning(f"关闭上下文失败: {e}")
            finally:
                self.context = None

    def _stop_playwright_safely(self):
        """安全停止 Playwright"""
        if self.playwright:
            try:
                self.playwright.stop()
                self.logger.info("Playwright 已停止")
            except Exception as e:
                self.logger.error(f"停止 Playwright 失败：{e}")
            finally:
                self.playwright = None

    def _create_context_and_page(self, storage_state: Optional[str] = None):
        """
        统一创建上下文和页面
        Args:
            storage_state: 可选的状态文件路径
        """
        options = self.context_options.copy()
        if storage_state:
            options["storage_state"] = storage_state
        self.context = self.browser.new_context(**options)
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout)

    def save_state(self):
        """保存登录状态到文件"""
        if self.context is None:
            self.logger.warning("没有可保存的上下文状态")
            return
        try:
            self.context.storage_state(path=self.auth_file)
            self.logger.info(f"账号 {self.auth_identity} 状态已保存")
        except Exception as e:
            self.logger.error(f"保存状态失败：{e}")

    def load_state(self) -> bool:
        """加载登录状态，成功返回 True"""
        if not os.path.exists(self.auth_file):
            self.logger.info(f"未找到状态文件：{self.auth_file}")
            return False
        try:
            self._create_context_and_page(storage_state=self.auth_file)
            self.logger.info(f"已加载账号 {self.auth_identity} 的登录状态")
            return True
        except Exception as e:
            self.logger.warning(f"加载状态失败：{e}")
            # 备份旧状态文件，防止丢失
            bak_file = self.auth_file + ".bak"
            if os.path.exists(self.auth_file):
                os.replace(self.auth_file, bak_file)
                self.logger.warning(f"状态文件已备份为 {bak_file}")
            return False

    def _login_with_retry(self) -> None:
        """带重试机制的登录"""
        last_exception = None
        for attempt in range(1, self.retry_count + 1):
            try:
                # 每次重试都创建新的上下文和页面，避免残留状态
                self._create_context_and_page()
                self.login_func(self.page, self.username, self.password)
                self.logger.info(f"账号 {self.auth_identity} 登录成功")
                return
            except Exception as e:
                last_exception = e
                self.logger.warning(f"登录失败 (尝试 {attempt}/{self.retry_count}): {e}")
                # 清理本次创建的页面和上下文
                self._close_page_safely()
                self._close_context_safely()
                if attempt == self.retry_count:
                    break
        raise last_exception or RuntimeError("登录失败，无具体异常")

    def smart_login(self) -> Page:
        """
        智能登录：尝试加载状态，失效则重新登录，并返回页面对象。
        异常时会自动停止浏览器。
        """
        try:
            self.start_browser()
            if self.load_state():
                self.page.goto(self.base_url)
                if "login" in self.page.url.lower():
                    self.logger.info("登录状态已失效，重新登录...")
                    self._close_page_safely()
                    self._close_context_safely()
                    self._login_with_retry()
                    self.save_state()
                else:
                    self.logger.info("登录状态有效")
            else:
                self._login_with_retry()
                self.save_state()
            return self.page
        except Exception as e:
            self.stop_browser()
            raise RuntimeError(f"智能登录失败: {e}")

    def execute_with_login(self, task_func: Callable[[Page, BrowserContext, T], T], *args, **kwargs) -> T:
        """
        执行带登录的任务，并自动释放资源。
        """
        result = None
        try:
            self.start_browser()
            page = self.smart_login()
            result = task_func(page, self.context, *args, **kwargs)
            return result
        except Exception as e:
            self.logger.error(f"execute_with_login失败：{e}")
            raise
        finally:
            self.stop_browser()

    def execute_multiple_tasks(
        self,
        tasks: List[Callable[[Page, BrowserContext], Any]],
        share_browser: bool = False,
    ) -> List[Dict[str, Union[int, bool, Any, str]]]:
        """
        批量执行多个任务，收集结果和异常

        Args:
            tasks: 任务函数列表，每个函数接受 page, context
            share_browser: 是否共享同一个浏览器会话（所有任务共用登录状态）

        Returns:
            每个任务的结果字典列表，包含 task序号, success, result/error
        """
        results: List[Dict[str, Union[int, bool, Any, str]]] = []

        if share_browser:
            try:
                self.start_browser()
                page = self.smart_login()
                for i, task in enumerate(tasks, 1):
                    self.logger.info(f"开始执行任务 {i}...")
                    try:
                        res = task(page, self.context)
                        results.append({"task": i, "success": True, "result": res})
                        self.logger.info(f"任务 {i} 执行完成")
                    except Exception as e:
                        results.append({"task": i, "success": False, "error": str(e)})
                        self.logger.error(f"任务 {i} 执行失败: {e}")
            finally:
                self.stop_browser()
        else:
            # 每个任务独立启停浏览器
            for i, task in enumerate(tasks, 1):
                self.logger.info(f"开始执行任务 {i}...")
                try:
                    res = self.execute_with_login(task)
                    results.append({"task": i, "success": True, "result": res})
                    self.logger.info(f"任务 {i} 执行完成")
                except Exception as e:
                    results.append({"task": i, "success": False, "error": str(e)})
                    self.logger.error(f"任务 {i} 执行失败: {e}")

        return results

    def __enter__(self) -> Tuple[Page, BrowserContext]:
        try:
            self.start_browser()
            page = self.smart_login()
            return page, self.context
        except Exception as e:
            self.stop_browser()
            raise RuntimeError(f"登录失败: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.stop_browser()
        return False  # 不吞异常


def smart_login_decorator(
    username: str,
    password: str,
    login_func: Callable[[Page, str, str], None],
    auth_identity: Optional[str] = None,
    base_url: Optional[str] = None,
    browser_type: str = "chromium",
    timeout: int = 30000,
    retry_count: int = 3,
):
    """
    智能登录装饰器工厂，返回一个装饰器，自动处理登录和资源释放。

    Args:
        username: 用户名
        password: 密码
        login_func: 登录函数
        auth_identity: 可选，状态标识
        base_url: 可选，基础URL
        browser_type: 浏览器类型
        timeout: 页面超时
        retry_count: 登录重试次数

    Returns:
        装饰器函数
    """
    def decorator(func: Callable[[Page, BrowserContext, Any], Any]) -> Callable[[Any], Any]:
        def wrapper(*args, **kwargs):
            with SmartLogin(
                username=username,
                password=password,
                login_func=login_func,
                auth_identity=auth_identity,
                base_url=base_url,
                browser_type=browser_type,
                timeout=timeout,
                retry_count=retry_count,
            ) as (page, context):
                return func(page, context, *args, **kwargs)
        return wrapper
    return decorator