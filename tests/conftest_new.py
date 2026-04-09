import pytest
import warnings
import sys
import os
import json
from pathlib import Path
from typing import List, Tuple, Any, Dict, Optional
from functools import lru_cache
import re
from config import PROJECT_ROOT, settings
from utils.data.yaml_cases_loader import load_yaml_file, InvalidYamlFormatError
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from utils.api_client import APIClient
from utils.data.db_helper import DatabaseHelper
from utils import login_cache
from utils.logger import logger

# 登录页面函数（根据实际项目调整导入路径）
from pages.components.login_page import login_page


# ==================== Playwright 相关 Fixtures ====================
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
    viewport = getattr(settings, "browser_viewport", {"width": 1920, "height": 1080})
    context = browser.new_context(viewport=viewport)
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)
    yield page


# ==================== API 相关 Fixtures ====================
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
    if hasattr(request, "param") and request.param:
        return request.param
    default_user = getattr(settings, "default_user", {})
    return {
        "username": default_user.get("username", ""),
        "password": default_user.get("password", "")
    }


@pytest.fixture(scope="function")
def auth_token(api_client: APIClient, user_credentials: Dict[str, str]) -> Optional[str]:
    username = user_credentials.get("username")
    password = user_credentials.get("password")
    if not username or not password:
        pytest.skip("缺少用户名或密码，无法获取认证 token")
    # 注意：login_cache 默认实现可能非线程安全，若使用并行测试请添加锁或改用 pytest 内置 cache
    cached_token = login_cache.get_token(key=username)
    if cached_token:
        return cached_token
    resp = api_client.post("/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.fail(f"登录失败: {resp.status_code} {resp.text}")
    token = resp.json().get("access_token")
    if not token:
        pytest.fail("登录响应中未包含 access_token")
    login_cache.save_token(token, key=username)
    return token


# ==================== 数据库相关 Fixtures ====================
@pytest.fixture(scope="function")
def db():
    required_db_configs = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [cfg for cfg in required_db_configs if not getattr(settings, cfg, None)]
    if missing:
        pytest.skip(f"缺少数据库配置: {', '.join(missing)}")
    db_helper = DatabaseHelper()
    yield db_helper
    db_helper.close_all()


# ==================== 登录缓存辅助函数 ====================
def _get_storage_state_path(username: str) -> Optional[Path]:
    """根据用户名和环境生成缓存文件路径"""
    if not getattr(settings, "browser_state_cache_enabled", True):
        return None
    cache_dir = Path(getattr(settings, "browser_state_cache_dir", ".browser_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = getattr(settings, "env", "beta")
    safe_username = "".join(c for c in username if c.isalnum() or c in "._-")
    filename = f"{safe_username}_{env}.json"
    return cache_dir / filename


def _is_storage_state_valid(storage_path: Path, browser: Browser, base_url: str) -> bool:
    """尝试验证缓存文件是否有效（仍处于登录状态）"""
    if not storage_path.exists():
        return False
    try:
        with open(storage_path, 'r') as f:
            json.load(f)
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()
        page.goto(base_url, timeout=5000)
        is_logged_in = "login" not in page.url.lower()
        context.close()
        return is_logged_in
    except Exception as e:
        logger.warning(f"缓存文件无效: {storage_path}, 错误: {e}")
        return False


# ==================== 登录相关 Fixtures（仅缓存模式） ====================
@pytest.fixture(scope="function")
def logged_in_page(browser: Browser, user_credentials: Dict[str, str]) -> Page:
    """
    返回已登录的 Page 对象，仅从缓存文件恢复登录态。
    如果缓存不存在或无效，则跳过测试并提示用户运行生成脚本。
    """
    username = user_credentials.get("username")
    if not username:
        pytest.skip("未提供用户名，无法定位缓存文件")

    base_url = getattr(settings, "base_url", None)
    if not base_url:
        pytest.skip("settings 中未配置 base_url，无法验证缓存有效性")

    storage_path = _get_storage_state_path(username)
    if not storage_path or not _is_storage_state_valid(storage_path, browser, base_url):
        script_cmd = f"python scripts/generate_login_state.py --username {username} --password <your_password> --env {getattr(settings, 'ENV', 'beta')}"
        pytest.fail(
            f"登录状态缓存文件不存在或已失效，请先运行以下脚本生成缓存：\n{script_cmd}\n"
            f"期望缓存路径: {storage_path}"
        )

    context = browser.new_context(storage_state=str(storage_path))
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)

    yield page

    context.close()


# ==================== 多角色协作 Fixtures（基于 YAML 参数） ====================
@pytest.fixture(scope="function")
def multi_users_pages(browser: Browser, multi_users: Dict[str, Dict[str, str]]) -> Dict[str, Page]:
    """
    为 YAML 中定义的多个角色创建独立的已登录页面对象，仅从缓存恢复。
    要求：测试函数必须声明 multi_users 参数，该参数从 YAML 用例中读取，格式为：
        {
            "role1": {"username": "user1", "password": "pass1"},
            "role2": {"username": "user2", "password": "pass2"},
            ...
        }
    返回：{角色名: Page对象}
    如果任一角色的缓存不存在或无效，则终止测试并提示运行生成脚本。
    """
    base_url = getattr(settings, "base_url", None)
    if not base_url:
        pytest.skip("settings 中未配置 base_url，无法验证缓存有效性")

    if not multi_users:
        pytest.skip("multi_users 参数为空，无法创建多角色页面")

    contexts: Dict[str, BrowserContext] = {}
    pages: Dict[str, Page] = {}
    failed_roles = []

    try:
        for role, creds in multi_users.items():
            username = creds.get("username")
            if not username:
                raise ValueError(f"角色 '{role}' 缺少用户名")

            storage_path = _get_storage_state_path(username)
            if not storage_path or not _is_storage_state_valid(storage_path, browser, base_url):
                failed_roles.append(role)
                continue

            context = browser.new_context(storage_state=str(storage_path))
            page = context.new_page()
            page.set_default_timeout(settings.timeouts.page_load)
            contexts[role] = context
            pages[role] = page
            logger.info(f"角色 '{role}' 从缓存恢复登录态: {storage_path}")

        if failed_roles:
            script_examples = []
            for role in failed_roles:
                creds = multi_users[role]
                username = creds.get("username")
                script_cmd = f"python scripts/generate_login_state.py --username {username} --password <your_password> --env {getattr(settings, 'ENV', 'beta')}"
                script_examples.append(f"  角色 '{role}': {script_cmd}")
            pytest.fail(
                f"以下角色的登录状态缓存不存在或已失效，请先运行生成脚本：\n" + "\n".join(script_examples)
            )

        yield pages

    finally:
        for ctx in contexts.values():
            ctx.close()


# ==================== pytest 配置 ====================
def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=os.getenv("ENV", "beta"),
        choices=["alpha", "beta", "prod"],
        help="指定测试环境：alpha, beta, prod"
    )


def pytest_collection_modifyitems(config, items):
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
            f"  要求: 测试函数参数名必须与YAML字段名完全一致"
        )
    unused_fields = yaml_fields - set(param_names)
    if unused_fields:
        warnings.warn(
            f"[YAML数据] 以下YAML字段未被测试函数使用: {sorted(unused_fields)}",
            UserWarning,
            stacklevel=2
        )
    return param_names


def _parametrize_empty(metafunc) -> None:
    """当没有有效用例时，通过参数化一个不存在的参数名来强制跳过测试"""
    metafunc.parametrize(
        "_skip_due_to_no_yaml_cases",
        [],
        ids=["no_cases"],
        scope="function"
    )


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

    abs_file_path = PROJECT_ROOT / "test_data" / file_name
    logger.debug(f"Loading YAML file: {abs_file_path}")

    if not abs_file_path.exists():
        _warn_and_skip(
            metafunc,
            f"YAML数据文件不存在，跳过测试: {abs_file_path}\n"
        )
        _parametrize_empty(metafunc)
        return

    try:
        res = _cached_load_yaml(str(abs_file_path))
    except InvalidYamlFormatError as e:
        _raise_usage_error(metafunc, f"YAML数据格式验证失败，测试终止:\n{e}")
        return
    except Exception as e:
        _warn_and_skip(
            metafunc,
            f"加载YAML数据时发生异常，跳过测试: {type(e).__name__}: {e}"
        )
        _parametrize_empty(metafunc)
        return

    if group_name not in res:
        available = list(res.keys())
        _warn_and_skip(
            metafunc,
            f"YAML中不存在用例组 '{group_name}'，跳过测试。\n"
            f"  可用组: {available if available else '[空]'}"
        )
        _parametrize_empty(metafunc)
        return

    cases = res[group_name]
    if isinstance(cases, dict):
        cases = [cases]
    if not cases:
        _warn_and_skip(
            metafunc,
            f"用例组 '{group_name}' 为空（无有效用例），跳过测试"
        )
        _parametrize_empty(metafunc)
        return

    param_names = _extract_yaml_param_names(metafunc, cases[0])
    if not param_names:
        _warn_and_skip(
            metafunc,
            f"无法提取有效参数名（YAML字段与测试参数无交集）\n"
            f"  YAML字段: {list(cases[0].keys()) if cases else 'N/A'}\n"
            f"  测试参数: {metafunc.fixturenames}"
        )
        _parametrize_empty(metafunc)
        return

    param_values: List[Tuple[Any, ...]] = []
    param_ids: List[str] = []
    used_ids = set()

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            continue

        missing = [p for p in param_names if p not in case]
        if missing:
            warnings.warn(
                f"[YAML数据] 用例 {idx} 缺少字段 {missing}，已跳过",
                UserWarning,
                stacklevel=2
            )
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
        _warn_and_skip(
            metafunc,
            f"用例组 '{group_name}' 无有效用例（所有用例均因字段缺失被跳过）\n"
            f"  所需参数: {param_names}"
        )
        _parametrize_empty(metafunc)
        return

    metafunc.parametrize(
        ",".join(param_names),
        param_values,
        ids=param_ids,
        scope="function"
    )


# ==================== 辅助函数 ====================
def _raise_usage_error(metafunc, message: str) -> None:
    raise pytest.UsageError(
        f"[YAML数据错误] in {metafunc.definition.nodeid}\n{message}"
    )


def _warn_and_skip(metafunc, message: str) -> None:
    full_message = f"[YAML数据] in {metafunc.definition.nodeid}\n{message}"
    warnings.warn(full_message, UserWarning, stacklevel=2)