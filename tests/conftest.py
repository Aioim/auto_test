"""
pytest 配置文件

提供：
- Playwright 浏览器 fixtures
- API 客户端 fixtures
- 数据库 fixtures（支持事务回滚）
- 登录状态缓存（支持多账号、多环境、并行安全）
- YAML 数据驱动测试
- 环境变量自动加载
- 多角色协作测试支持
"""

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

# 导入核心模块（请根据实际项目调整导入路径）
from config import PROJECT_ROOT, settings
from core import login_cache
from core.cache_utils import (
    BROWSER_STATE_CACHE_ENABLED,
    LOGIN_FALLBACK_ENABLED,
    get_role_credentials,
    get_storage_state_path,
    is_storage_state_valid,
    load_env_by_name,
    save_storage_state,
    wait_for_login_success,
)
from data.db_helper import DatabaseHelper
from data.yaml_cases_loader import InvalidYamlFormatError, load_yaml_file
from logger import logger
from pages.components.login_page import login_page
from security import decrypt_env
from src.utils.api_client import APIClient

# ==================== 配置常量 ====================
TEST_DATA_DIR = Path(getattr(settings, "test_data_dir", PROJECT_ROOT / "test_data/test_cases/"))


# ==================== pytest 钩子 ====================
def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=os.getenv("ENV", "beta"),
        choices=["alpha", "beta", "prod"],
        help="指定测试环境：alpha, beta, prod"
    )


def pytest_collection_modifyitems(config, items):
    """根据环境标记跳过测试"""
    current_env = config.getoption("--env")
    for item in items:
        env_marker = item.get_closest_marker("env")
        if env_marker:
            allowed_envs = env_marker.args
            if not allowed_envs:
                continue
            if len(allowed_envs) == 1 and isinstance(allowed_envs[0], (list, tuple)):
                allowed_envs = allowed_envs[0]
            if current_env not in allowed_envs:
                reason = f"测试仅允许在环境 {allowed_envs} 中运行，当前环境为 {current_env}"
                item.add_marker(pytest.mark.skip(reason=reason))


# ==================== Playwright fixtures ====================
@pytest.fixture(scope="session")
def playwright():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright):
    try:
        browser_type = getattr(playwright, settings.browser.type)
        browser = browser_type.launch(headless=settings.browser.headless)
        yield browser
        browser.close()
    except Exception as e:
        pytest.exit(f"启动浏览器失败: {e}", returncode=1)


@pytest.fixture(scope="function")
def context(browser: Browser) -> BrowserContext:
    viewport = getattr(settings.browser, "viewport", {"width": 1920, "height": 1080})
    context = browser.new_context(viewport=viewport)
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)
    yield page


# ==================== API fixtures ====================
@pytest.fixture(scope="function")
def api_client():
    api_base_url = getattr(settings, "api_base_url", None)
    if not api_base_url:
        pytest.skip("API 基础 URL 未配置")
    timeout = getattr(settings, "api_timeout", 30)
    client = APIClient(base_url=api_base_url, timeout=timeout)
    yield client
    client.close()


@pytest.fixture(scope="function")
def user_credentials(request) -> Dict[str, str]:
    """获取用户凭证，优先使用参数化传入，否则使用 settings.default_user"""
    if hasattr(request, "param") and request.param:
        return request.param
    return {
        "username": settings.username,
        "password": settings.password
    }


@pytest.fixture(scope="function")
def auth_token(api_client: APIClient, user_credentials: Dict[str, str]) -> Optional[str]:
    """获取 API 认证 token（基于文件缓存）"""
    username = user_credentials.get("username")
    password = user_credentials.get("password")
    if not username or not password:
        pytest.skip("缺少用户名或密码，无法获取认证 token")
    cached_token = login_cache.get_token(username)
    if cached_token:
        return cached_token
    resp = api_client.post("/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.fail(f"登录失败: {resp.status_code} {resp.text}")
    token = resp.json().get("access_token")
    if not token:
        pytest.fail("登录响应中未包含 access_token")
    login_cache.save_token(token, username)
    return token


# ==================== 数据库 fixtures ====================
@pytest.fixture(scope="function")
def db():
    """数据库 helper，支持自动事务回滚"""
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [cfg for cfg in required if not getattr(settings, cfg, None)]
    if missing:
        pytest.skip(f"缺少数据库配置: {', '.join(missing)}")
    db_helper = DatabaseHelper()
    if hasattr(db_helper, 'begin_transaction'):
        db_helper.begin_transaction()
    else:
        logger.warning("DatabaseHelper 未实现 begin_transaction，无法自动回滚")
    yield db_helper
    if hasattr(db_helper, 'rollback'):
        db_helper.rollback()
    db_helper.close_all()


# ==================== 登录页面 fixtures ====================
@pytest.fixture(scope="function")
def logged_in_page(browser: Browser, user_credentials: Dict[str, str]) -> Page:
    """
    返回已登录的 Page 对象。
    优先从缓存恢复，若缓存无效且 LOGIN_FALLBACK_ENABLED 为 True，则实时登录并保存缓存。
    """
    username = user_credentials.get("username")
    password = user_credentials.get("password")
    if not username or not password:
        pytest.skip("缺少用户名或密码")
    base_url = getattr(settings, "base_url", None)
    if not base_url:
        pytest.skip("settings 中未配置 base_url")

    storage_path = get_storage_state_path(username)
    context = None
    page = None

    # 尝试从缓存恢复
    if storage_path and is_storage_state_valid(storage_path, browser, base_url):
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()
        page.set_default_timeout(settings.timeouts.page_load)
        logger.info(f"从缓存恢复登录态: {storage_path}")
        yield page
        context.close()
        return

    # 缓存无效，检查是否允许 fallback
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


@pytest.fixture(scope="function")
def multi_users_pages(browser: Browser, request) -> Dict[str, Page]:
    """
    为多个角色创建独立的已登录页面对象。
    支持两种输入方式：
    1. 通过 YAML 的 multi_users 字段，直接提供 {角色名: {username, password}}
    2. 通过 YAML 的 roles 字段，提供 {角色名: 角色key}，从环境变量获取凭证
    """
    base_url = getattr(settings, "base_url", None)
    if not base_url:
        pytest.skip("settings 中未配置 base_url")

    # 获取参数
    multi_users = None
    try:
        multi_users = request.getfixturevalue('multi_users')
    except pytest.FixtureLookupError:
        pass

    if multi_users is None:
        try:
            roles = request.getfixturevalue('roles')
            multi_users = {}
            for role_name, role_key in roles.items():
                multi_users[role_name] = get_role_credentials(role_key)
        except pytest.FixtureLookupError:
            pytest.skip("multi_users_pages 需要 multi_users 或 roles 参数")

    if not multi_users:
        pytest.skip("multi_users 参数为空")

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
        page = None
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


# ==================== YAML 数据驱动测试 ====================
@lru_cache(maxsize=128)
def _cached_load_yaml(file_path_str: str) -> Dict[str, List[Dict[str, Any]]]:
    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"YAML文件不存在: {file_path}")
    return load_yaml_file(file_path)


def _extract_yaml_param_names(metafunc, first_case: Dict[str, Any]) -> List[str]:
    yaml_fields = set(first_case.keys()) if first_case else set()
    param_names = [p for p in metafunc.fixturenames if p in yaml_fields]
    if not param_names and yaml_fields:
        all_params = set(metafunc.fixturenames)
        _raise_usage_error(
            metafunc,
            f"测试函数参数与YAML字段无匹配\n"
            f"  YAML字段: {sorted(yaml_fields)}\n"
            f"  测试参数: {sorted(all_params)}\n"
            f"  要求: 测试函数参数名必须与YAML字段名完全一致（pytest 内置 fixture 如 request, caplog 无需出现在 YAML 中）"
        )
    unused_fields = yaml_fields - set(param_names)
    if unused_fields:
        logger.warning(f"[YAML数据] 以下YAML字段未被测试函数使用: {sorted(unused_fields)}")
    return param_names


def _mark_test_skip_due_to_no_cases(metafunc, reason: str = "No valid YAML test cases found") -> None:
    """
    标记测试为跳过，并创建一个虚拟参数化以避免 pytest 因缺少参数而失败。
    要求测试函数必须包含 'request' fixture。
    """
    metafunc.definition.add_marker(pytest.mark.skip(reason=reason))
    # 若测试函数没有 request 参数，则此方法可能无效，但大多数数据驱动测试都会用到 request
    if "request" in metafunc.fixturenames:
        # 进行一次无意义的参数化，满足 pytest 对参数化测试的要求
        metafunc.parametrize("request", [pytest.param(None)], indirect=True)


def pytest_generate_tests(metafunc):
    marker = metafunc.definition.get_closest_marker("yaml_data")
    if marker is None:
        return

    try:
        file_name = marker.kwargs["file"]
        group_name = marker.kwargs["group"]
    except KeyError as e:
        _raise_usage_error(
            metafunc,
            f"@pytest.mark.yaml_data 缺少必需参数 {e}\n"
            f"  正确用法: @pytest.mark.yaml_data(file='xxx.yaml', group='yyy')\n"
            f"  当前参数: {marker.kwargs}"
        )
        return

    if "params" in marker.kwargs:
        _raise_usage_error(
            metafunc,
            f"@pytest.mark.yaml_data 不再支持 'params' 参数\n"
            f"  要求: 测试函数参数名必须与YAML字段名完全一致"
        )
        return

    abs_file_path = TEST_DATA_DIR / file_name
    logger.debug(f"Loading YAML file: {abs_file_path}")

    if not abs_file_path.exists():
        logger.warning(f"YAML数据文件不存在，跳过测试: {abs_file_path}")
        _mark_test_skip_due_to_no_cases(metafunc, f"YAML file {file_name} not found")
        return

    try:
        res = _cached_load_yaml(str(abs_file_path))
    except InvalidYamlFormatError as e:
        _raise_usage_error(metafunc, f"YAML数据格式验证失败，测试终止:\n{e}")
        return
    except Exception as e:
        logger.warning(f"加载YAML数据时发生异常，跳过测试: {type(e).__name__}: {e}")
        _mark_test_skip_due_to_no_cases(metafunc, f"YAML loading error: {e}")
        return

    if group_name not in res:
        available = list(res.keys())
        logger.warning(
            f"YAML中不存在用例组 '{group_name}'，跳过测试。\n"
            f"  可用组: {available if available else '[空]'}"
        )
        _mark_test_skip_due_to_no_cases(metafunc, f"Group '{group_name}' not found in YAML")
        return

    cases = res[group_name]
    if isinstance(cases, dict):
        cases = [cases]
    if not cases:
        logger.warning(f"用例组 '{group_name}' 为空（无有效用例），跳过测试")
        _mark_test_skip_due_to_no_cases(metafunc, f"Group '{group_name}' has no cases")
        return

    param_names = _extract_yaml_param_names(metafunc, cases[0])
    if not param_names:
        logger.warning(
            f"无法提取有效参数名（YAML字段与测试参数无交集）\n"
            f"  YAML字段: {list(cases[0].keys()) if cases else 'N/A'}\n"
            f"  测试参数: {metafunc.fixturenames}"
        )
        _mark_test_skip_due_to_no_cases(metafunc, "No matching parameter names found")
        return

    param_values: List[Tuple[Any, ...]] = []
    param_ids: List[str] = []
    used_ids = set()

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            continue

        missing = [p for p in param_names if p not in case]
        if missing:
            logger.warning(f"[YAML数据] 用例 {idx} 缺少字段 {missing}，已跳过")
            continue

        case_id = (
            str(case.get("id", "")) or
            str(case.get("name", "")) or
            str(case.get("desc", "")) or
            f"{group_name}_{idx}"
        )
        case_id = re.sub(r'[^a-zA-Z0-9_]', '_', case_id)
        case_id = re.sub(r'_+', '_', case_id).strip('_')
        if not case_id or not case_id[0].isalpha():
            case_id = f"{group_name}_{idx}"
        if case_id in used_ids:
            suffix = 2
            while f"{case_id}_{suffix}" in used_ids:
                suffix += 1
            case_id = f"{case_id}_{suffix}"
        used_ids.add(case_id)
        if len(case_id) > 100:
            case_id = case_id[:97] + "..."

        values = tuple(case[p] for p in param_names)
        param_values.append(values)
        param_ids.append(case_id)

    if not param_values:
        logger.warning(
            f"用例组 '{group_name}' 无有效用例（所有用例均因字段缺失被跳过）\n"
            f"  所需参数: {param_names}"
        )
        _mark_test_skip_due_to_no_cases(metafunc, "No valid cases after filtering")
        return

    metafunc.parametrize(
        ",".join(param_names),
        param_values,
        ids=param_ids,
        scope="function"
    )


def _raise_usage_error(metafunc, message: str) -> None:
    raise pytest.UsageError(
        f"[YAML数据错误] in {metafunc.definition.nodeid}\n{message}"
    )