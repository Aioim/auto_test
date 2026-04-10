"""
登录页面操作封装，支持多环境配置
"""

from playwright.sync_api import Page, TimeoutError
from logger import logger
from config import settings


def login_page(page: Page, username: str, password: str, env: str = "beta", **kwargs) -> None:
    """
    执行标准登录流程（可根据环境动态选择选择器）

    配置建议：在 settings 中定义不同环境的登录选择器映射
    """
    # 获取环境相关配置
    env_config = getattr(settings, "login_config", {}).get(env, {})
    login_url = env_config.get("url") or f"{settings.base_url}/login"
    username_sel = env_config.get("username_selector", "#username")
    password_sel = env_config.get("password_selector", "#password")
    submit_sel = env_config.get("submit_selector", "button[type=submit]")

    logger.info(f"🔐 正在登录 {env} 环境: {username}")

    # 跳转登录页
    if not page.url.startswith(login_url):
        page.goto(login_url, wait_until="domcontentloaded")

    # 检测是否已登录（避免重复操作）
    if _already_logged_in(page, env_config):
        logger.info("已处于登录状态，跳过登录")
        return

    # 等待表单加载
    try:
        page.wait_for_selector(username_sel, state="visible", timeout=10000)
    except TimeoutError:
        # 可能已被重定向或页面异常，尝试截图
        page.screenshot(path="login_error.png")
        raise RuntimeError(f"登录表单未加载，当前 URL: {page.url}")

    # 填写并提交
    page.fill(username_sel, username)
    page.fill(password_sel, password)

    # 可选：勾选“记住我”
    if env_config.get("remember_me_selector"):
        page.check(env_config["remember_me_selector"])

    page.click(submit_sel)
    logger.debug("登录表单已提交")


def _already_logged_in(page: Page, env_config: dict) -> bool:
    """判断当前页面是否为已登录状态"""
    try:
        # 检查 URL 是否已经不在登录页
        if "login" not in page.url.lower():
            # 再检查是否存在用户菜单或头像
            indicator = env_config.get("logged_in_indicator", ".user-avatar")
            page.wait_for_selector(indicator, timeout=2000)
            return True
    except TimeoutError:
        pass
    return False