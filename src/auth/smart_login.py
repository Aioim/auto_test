"""
智能登录模块

提供 SmartLogin 类，支持：
- 自动缓存登录状态（基于文件锁，支持并行）
- 缓存有效性验证（cookie 检查 + 可选回退访问首页）
- 统一的登录成功等待机制（支持 SPA 选择器或 URL 变化）
- 批量执行任务、装饰器、上下文管理器等便捷用法
"""

import os
from pathlib import Path
from typing import Callable, Optional, Any, Tuple, List, Dict

from playwright.sync_api import Page, Browser, BrowserContext, sync_playwright, Playwright

from config import settings, PROJECT_ROOT
from pages.components.login_page import login_page
from logger import logger
from .cache_utils import (
    get_storage_state_path,
    is_storage_state_valid,
    save_storage_state,
    wait_for_login_success,
)


class SmartLogin:
    """
    智能登录类，自动管理浏览器生命周期和登录状态缓存
    """

    def __init__(
        self,
        username: str,
        password: str,
        login_func: Callable[[Page, str, str], None] = None,
        env: str = None,
        config=None,
    ):
        """
        初始化 SmartLogin

        Args:
            username: 用户名
            password: 密码
            login_func: 登录函数，接受 (page, username, password) 参数，
                        默认使用 pages.components.login_page.login_page
            env: 环境标识（如 beta, prod），用于区分缓存文件，默认从 settings.ENV 获取
        """
        self.username = username
        self.password = password
        self.login_func = login_func or login_page
        self.env = env or getattr(settings, "ENV", "beta")

        # 浏览器相关属性
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_browser_started = False

        # 浏览器上下文参数（从配置读取）
        self.context_options = {
            "viewport": getattr(settings.browser, "viewport", {"width": 1920, "height": 1080}),
            "permissions": getattr(settings.browser, "permissions", []),
            "geolocation": getattr(settings.browser, "geolocation", None),
        }

    # ==================== 浏览器生命周期管理 ====================
    def start_browser(self, headless: bool = False):
        """启动浏览器"""
        if self.is_browser_started:
            return
        try:
            self.playwright = sync_playwright().start()
            browser_type = getattr(self.playwright, settings.browser.type)
            self.browser = browser_type.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.is_browser_started = True
            logger.info("✅ 浏览器已启动")
        except Exception as e:
            logger.error(f"❌ 浏览器启动失败：{e}")
            self._stop_playwright_safely()
            raise

    def stop_browser(self):
        """关闭浏览器并释放资源"""
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

    # ==================== 登录状态缓存管理 ====================
    def _get_cache_path(self) -> Path:
        """获取当前账号/环境的缓存文件路径"""
        return get_storage_state_path(self.username, self.env)

    def load_state(self) -> bool:
        """从缓存文件加载登录状态，若有效则返回 True"""
        cache_path = self._get_cache_path()
        if not cache_path or not cache_path.exists():
            logger.info(f"📁 未找到缓存文件：{cache_path}")
            return False

        if not self.is_browser_started:
            self.start_browser()

        if is_storage_state_valid(cache_path, self.browser, settings.base_url):
            try:
                self.context = self.browser.new_context(
                    storage_state=str(cache_path),
                    **self.context_options
                )
                self.page = self.context.new_page()
                logger.info(f"✅ 已加载账号 {self.username} 的登录状态")
                return True
            except Exception as e:
                logger.warning(f"⚠️ 加载缓存时出错: {e}")
                # 缓存文件可能损坏，删除并重新登录
                cache_path.unlink(missing_ok=True)
                return False
        else:
            # 缓存无效，备份后删除
            bak_path = cache_path.with_suffix(".json.bak")
            cache_path.rename(bak_path)
            logger.warning(f"⚠️ 缓存无效，已备份至 {bak_path}")
            return False

    def save_state(self):
        """保存当前登录状态到缓存文件"""
        if self.context:
            save_storage_state(self.page, self.username, self.env)

    # ==================== 登录流程 ====================
    def login(self):
        """执行实时登录（不依赖缓存）"""
        try:
            self.context = self.browser.new_context(**self.context_options)
            self.page = self.context.new_page()
            self.login_func(self.page, self.username, self.password)
            # 等待登录成功（使用统一的等待机制）
            wait_for_login_success(self.page)
            logger.info(f"✅ 账号 {self.username} 登录成功")
        except Exception as e:
            logger.error(f"❌ 登录失败：{e}")
            raise

    def smart_login(self) -> Page:
        """
        智能登录：优先尝试缓存，若无效则执行实时登录并保存缓存
        返回已登录的 Page 对象
        """
        try:
            self.start_browser()
            if not self.load_state():
                self.login()
                self.save_state()
            else:
                # 验证缓存恢复后的页面是否仍处于登录状态（可选）
                self.page.goto(settings.base_url)
                # 再次确认登录状态（如果超时则视为失效，重新登录）
                try:
                    wait_for_login_success(self.page, timeout=3000)
                except Exception:
                    logger.warning("⚠️ 缓存恢复后登录状态失效，重新登录")
                    self._close_context_safely()
                    self._close_page_safely()
                    self.login()
                    self.save_state()
            return self.page
        except Exception as e:
            self.stop_browser()
            raise RuntimeError(f"智能登录失败: {e}")

    # ==================== 任务执行便捷方法 ====================
    def execute_with_login(self, task_func: Callable[[Page, BrowserContext, Any], Any], *args, **kwargs) -> Any:
        """
        执行带登录的任务，任务完成后自动关闭浏览器

        Args:
            task_func: 任务函数，签名 (page, context, *args, **kwargs) -> Any
            *args, **kwargs: 传递给任务函数的额外参数

        Returns:
            任务函数的返回值
        """
        try:
            self.start_browser()
            page = self.smart_login()
            result = task_func(page, self.context, *args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"❌ execute_with_login 失败：{e}")
            raise
        finally:
            self.stop_browser()

    def execute_multiple_tasks(self, tasks: List[Callable[[Page, BrowserContext], Any]]) -> List[Dict[str, Any]]:
        """
        批量执行多个任务，每个任务独立启动浏览器（共用账号）
        收集每个任务的结果和异常

        Args:
            tasks: 任务函数列表，每个函数签名 (page, context) -> Any

        Returns:
            结果列表，每个元素为 {"task": index, "success": bool, "result": Any, "error": str}
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

    # ==================== 上下文管理器支持 ====================
    def __enter__(self) -> Tuple[Page, BrowserContext]:
        """支持 with 语句：自动登录并返回 (page, context)"""
        try:
            self.start_browser()
            page = self.smart_login()
            return page, self.context
        except Exception as e:
            self.stop_browser()
            raise RuntimeError(f"登录失败: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """退出 with 块时自动关闭浏览器"""
        self.stop_browser()
        return False  # 不吞异常


# ==================== 装饰器支持 ====================
def smart_login_decorator(login_func: Callable[[Page, str, str], None] = None, **smart_login_kwargs):
    """
    智能登录装饰器，自动处理登录和资源释放

    使用方式：
        @smart_login_decorator
        def my_test(page, context):
            page.goto("...")

    或带参数：
        @smart_login_decorator(username="admin", password="123")
        def my_test(page, context):
            ...
    """
    def decorator(func: Callable[[Page, BrowserContext, Any], Any]) -> Callable[[Any], Any]:
        def wrapper(*args, **kwargs):
            # 如果装饰器参数中提供了 username/password，则使用；否则从函数参数中获取？
            # 简化处理：要求 username/password 必须通过装饰器参数或全局配置传入
            username = smart_login_kwargs.get("username")
            password = smart_login_kwargs.get("password")
            env = smart_login_kwargs.get("env")
            if not username or not password:
                # 尝试从 settings 获取
                username = settings.username
                password = decrypt_env(settings.password)
            if not username or not password:
                raise ValueError("未提供用户名或密码，请通过装饰器参数或 settings.default_user 配置")
            smart_login = SmartLogin(username, password, login_func, env)
            with smart_login as (page, context):
                return func(page, context, *args, **kwargs)
        return wrapper
    if login_func is not None:
        # 直接使用 @smart_login_decorator 无参数的情况
        return decorator(login_func)
    return decorator

def smart_login_decorator_bak(func: Callable[[Page, Any, Any], Any]) -> Callable[[Any], Any]:
    """
    智能登录装饰器，自动处理登录和资源释放
    """
    def wrapper(*args, **kwargs):
        with SmartLogin() as page:
            return func(page, *args, **kwargs)
    return wrapper

def smart_login(username: str, password: str):
    return SmartLogin(username, password).smart_login()
