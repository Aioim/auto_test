import os
from pathlib import Path
from typing import Callable, Optional, Any, Tuple, List, Dict
from playwright.sync_api import Page, Browser, BrowserContext, sync_playwright, Playwright
from config import settings, PROJECT_ROOT
from pages.components.login_page import login_page
from utils.logger import logger

class SmartLogin:
    def __init__(
        self,
        username: str,
        password: str,
        login_func: Callable[[Page, str, str], None],
        auth_identity: Optional[str] = None,
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
        """
        self.username = username
        self.password = password
        self.login_func = login_func
        self.auth_identity = auth_identity or username
        self.auth_file = self._get_auth_file()

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        self.is_browser_started = False
        self.ignore_dialog = {
            "permissions": settings.browser.permissions,
            "geolocation": settings.browser.geolocation,
            "viewport": settings.browser.viewport,
        }

    def _get_auth_file(self) -> str:
        auth_dir = PROJECT_ROOT / settings.browser.auth_dir
        auth_dir.mkdir(exist_ok=True, parents=True)
        return str(auth_dir / f"auth_{self.auth_identity}.json")

    def start_browser(self, headless: bool = False):
        if self.is_browser_started:
            return
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=headless, args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.is_browser_started = True
            logger.info("✅ 浏览器已启动")
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败：{e}")
            self.is_browser_started = False
            self._stop_playwright_safely()
            raise

    def stop_browser(self):
        self._close_page_safely()
        self._close_context_safely()
        if self.browser:
            try:
                self.browser.close()
                logger.info("🛑 浏览器已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭浏览器失败：{e}")
        self._stop_playwright_safely()
        self.is_browser_started = False

    def _close_page_safely(self):
        if self.page:
            try:
                self.page.close()
            except Exception as e:
                logger.warning(f"⚠️ 关闭页面失败: {e}")
            finally:
                self.page = None

    def _close_context_safely(self):
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                logger.warning(f"⚠️ 关闭上下文失败: {e}")
            finally:
                self.context = None

    def _stop_playwright_safely(self):
        if self.playwright:
            try:
                self.playwright.stop()
                logger.info("🛑 Playwright 已停止")
            except Exception as e:
                logger.error(f"❌ 停止 Playwright 失败：{e}")
            finally:
                self.playwright = None

    def save_state(self):
        if self.context is None:
            logger.warning("⚠️ 没有可保存的上下文状态")
            return
        try:
            self.context.storage_state(path=self.auth_file)
            logger.info(f"💾 账号 {self.auth_identity} 状态已保存")
        except Exception as e:
            logger.error(f"❌ 保存状态失败：{e}")

    def load_state(self) -> bool:
        if not os.path.exists(self.auth_file):
            logger.info(f"📁 未找到状态文件：{self.auth_file}")
            return False
        try:
            self.context = self.browser.new_context(**self.ignore_dialog, storage_state=self.auth_file)
            self.page = self.context.new_page()
            logger.info(f"✅ 已加载账号 {self.auth_identity} 的登录状态")
            return True
        except Exception as e:
            logger.warning(f"⚠️ 加载状态失败：{e}")
            # 备份旧状态文件，防止丢失
            bak_file = self.auth_file + ".bak"
            if os.path.exists(self.auth_file):
                os.replace(self.auth_file, bak_file)
                logger.warning(f"⚠️ 状态文件已备份为 {bak_file}")
            return False

    def login(self):
        try:
            self.context = self.browser.new_context(**self.ignore_dialog)
            self.page = self.context.new_page()
            self.login_func(self.page, self.username, self.password)
            logger.info(f"✅ 账号 {self.auth_identity} 登录成功")
        except Exception as e:
            logger.error(f"❌ 登录失败：{e}")
            raise

    def smart_login(self) -> Page:
        try:
            self.start_browser()
            base_url = getattr(settings, "base_url", None)
            if not base_url:
                logger.error("❌ 未配置 base_url")
                raise ValueError("base_url 未配置")
            if self.load_state():
                self.page.goto(base_url)
                if "login" in self.page.url.lower():
                    logger.info("⚠️ 登录状态已失效，重新登录...")
                    self._close_page_safely()
                    self._close_context_safely()
                    # 状态文件已备份
                    self.login()
                    self.save_state()
                else:
                    logger.info("✅ 登录状态有效")
            else:
                self.login()
                self.save_state()
            return self.page
        except Exception as e:
            self.stop_browser()
            raise RuntimeError(f"智能登录失败: {e}")

    def execute_with_login(self, task_func: Callable[[Page, BrowserContext, Any], Any], *args, **kwargs) -> Any:
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
            logger.error(f"❌ execute_with_login失败：{e}")
            raise
        finally:
            self.stop_browser()

    def execute_multiple_tasks(self, tasks: List[Callable[[Page, BrowserContext,Any], Any]]) -> List[Dict[str, Any]]:
        """
        批量执行多个任务，收集结果和异常
        """
        results = []
        for i, task in enumerate(tasks, 1):
            logger.info(f"开始执行任务 {i}...")
            try:
                res = self.execute_with_login(task)
                results.append({"task": i, "success": True, "result": res})
                logger.info(f"任务 {i} 执行完成")
            except Exception as e:
                results.append({"task": i, "success": False, "error": str(e)})
                logger.error(f"任务 {i} 执行失败: {e}")
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

if __name__ == '__main__':

    smart_login = SmartLogin(
        username="username",
        password="password",
        login_func=login_page,
    )
    page = smart_login.smart_login()
    page.pause()
    smart_login.stop_browser()
