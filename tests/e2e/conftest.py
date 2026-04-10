"""
E2E 测试专用 fixtures（基于 Playwright）
提供：
- playwright
- browser
- context
- page
- logged_in_page
- multi_users_pages
"""
import pytest
from typing import Dict, Optional, Any, Generator

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from config import settings
from core.cache_utils import (
    LOGIN_FALLBACK_ENABLED,
    get_role_credentials,
    get_storage_state_path,
    is_storage_state_valid,
    save_storage_state,
    wait_for_login_success,
)
from logger import logger
from pages.components.login_page import login_page


# ==================== Playwright 基础 fixtures ====================
@pytest.fixture(scope="session")
def playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright):
    """启动浏览器（会话级别）"""
    try:
        browser_type = getattr(playwright, settings.browser.type)
        browser = browser_type.launch(headless=settings.browser.headless)
        yield browser
        browser.close()
    except Exception as e:
        pytest.exit(f"启动浏览器失败: {e}", returncode=1)


@pytest.fixture(scope="function")
def context(browser: Browser) -> Generator[BrowserContext, Any, None]:
    """创建浏览器上下文（函数级别，隔离 cookies/storage）"""
    viewport = getattr(settings.browser, "viewport", {"width": 1920, "height": 1080})
    context = browser.new_context(viewport=viewport)
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    """创建页面对象"""
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)
    yield page


# ==================== 已登录页面 fixture ====================
@pytest.fixture(scope="function")
def logged_in_page(browser: Browser, request) -> Generator[Page, Any, None]:
    """
    返回已登录的 Page 对象。
    优先从缓存恢复，若缓存无效且允许回退则实时登录。
    可通过 request.param 传入自定义凭证字典。
    """
    # 获取凭证
    if hasattr(request, "param") and request.param:
        username = request.param.get("username")
        password = request.param.get("password")
    else:
        username = getattr(settings, "TEST_USERNAME", "")
        password = getattr(settings, "TEST_PASSWORD", "")

    if not username or not password:
        pytest.skip("缺少用户名或密码")

    base_url = getattr(settings, "BASE_URL", None)
    if not base_url:
        pytest.skip("settings 中未配置 BASE_URL")

    storage_path = get_storage_state_path(username)

    # 尝试从缓存恢复
    if storage_path and is_storage_state_valid(storage_path, browser, base_url):
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()
        page.set_default_timeout(settings.timeouts.page_load)
        logger.info(f"从缓存恢复登录态: {storage_path}")
        yield page
        context.close()
        return

    # 缓存无效，检查是否允许回退
    if not LOGIN_FALLBACK_ENABLED:
        pytest.fail(
            f"登录缓存无效且 fallback 登录已禁用，请运行:\n"
            f"python scripts/generate_login_state.py --username {username} --password <password> --env {settings.ENV}"
        )

    # 实时登录
    logger.info(f"缓存无效，实时登录: {username}")
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)
    try:
        login_page(page, username, password)
        wait_for_login_success(page)
        save_storage_state(page, username)
        yield page
    except Exception as e:
        pytest.fail(f"实时登录失败: {e}")
    finally:
        context.close()


# ==================== 多角色页面 fixture ====================
@pytest.fixture(scope="function")
def multi_users_pages(browser: Browser, request) -> Generator[dict[Any, Any], Any, None]:
    """
    为多个角色创建独立的已登录页面对象。
    支持两种输入方式（通过 request.param）：
    1. multi_users: {角色名: {username, password}}
    2. roles: {角色名: 角色key}，从环境变量获取凭证
    """
    base_url = getattr(settings, "base_url", None)
    if not base_url:
        pytest.skip("settings 中未配置 BASE_URL")

    param = request.param if hasattr(request, "param") else {}
    multi_users = param.get("multi_users")
    if multi_users is None:
        roles = param.get("roles")
        if roles:
            multi_users = {role_name: get_role_credentials(role_key) for role_name, role_key in roles.items()}

    if not multi_users:
        pytest.skip("multi_users_pages 需要 multi_users 或 roles 参数")

    contexts = {}
    pages = {}
    failed = []

    for role, creds in multi_users.items():
        username = creds.get("username")
        password = creds.get("password")
        if not username or not password:
            failed.append(f"{role}: 缺少用户名或密码")
            continue

        storage_path = get_storage_state_path(username)
        context = None
        try:
            if storage_path and is_storage_state_valid(storage_path, browser, base_url):
                context = browser.new_context(storage_state=str(storage_path))
                page = context.new_page()

                logger.info(f"角色 '{role}' 从缓存恢复登录态")
            elif LOGIN_FALLBACK_ENABLED:
                logger.info(f"角色 '{role}' 缓存无效，实时登录")
                context = browser.new_context()
                page = context.new_page()
                login_page(page, username, password)
                wait_for_login_success(page)
                save_storage_state(page, username)
                logger.info(f"角色 '{role}' 实时登录成功并保存缓存")
            else:
                failed.append(f"{role}: 缓存无效且 fallback 禁用")
                continue
            page.set_default_timeout(settings.timeouts.page_load)

            contexts[role] = context
            pages[role] = page
        except Exception as e:
            logger.error(f"角色 '{role}' 登录失败: {e}")
            failed.append(f"{role} ({username}) - {e}")
            if context:
                context.close()

    if failed:
        pytest.fail(f"以下角色登录失败：\n" + "\n".join(failed))

    yield pages

    for ctx in contexts.values():
        ctx.close()
