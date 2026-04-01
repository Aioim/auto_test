import pytest
import warnings
import sys
import os
import logging
from pathlib import Path
from typing import List, Tuple, Any, Dict, Optional, Union
from functools import lru_cache
import re
from config import PROJECT_ROOT, settings
from utils.data.yaml_cases_loader import load_yaml_file, InvalidYamlFormatError
from playwright.sync_api import sync_playwright, Page, Response, Browser, BrowserContext
from utils.api_client import APIClient
from utils.common.smart_login import SmartLogin
from utils.data.db_helper import DatabaseHelper
from utils import login_cache
from utils.logger import logger

# ==================== 辅助函数与常量 ====================
# 确保 PROJECT_ROOT 为 Path 对象（防御性检查）
assert isinstance(PROJECT_ROOT, Path), "PROJECT_ROOT 必须为 pathlib.Path 对象"


class APIResponseCollector:
    """
    API 响应收集器，用于监控和收集非 2xx 状态码的 API 响应
    改进：支持初始化时传入忽略模式，避免动态添加滞后问题
    """
    def __init__(self, page: Page, ignore_patterns: Optional[List[str]] = None):
        self.page = page
        self.ignore_patterns = ignore_patterns or []
        self.non_ok_responses: List[Dict[str, Any]] = []
        self._setup_listener()

    def _should_ignore(self, url: str) -> bool:
        """检查是否应该忽略指定的 URL"""
        return any(pattern in url for pattern in self.ignore_patterns)

    def _setup_listener(self):
        """设置响应监听器"""
        def on_response(response: Response):
            # 只监控 XHR/Fetch
            if response.request.resource_type not in ("xhr", "fetch"):
                return
            status = response.status
            url = response.url
            if 200 <= status < 300:
                return
            if self._should_ignore(url):
                return
            self.non_ok_responses.append({
                "url": url,
                "status": status,
                "status_text": response.status_text,
                "method": response.request.method,
            })
            logger.warning(f"Non-200 API: {response.request.method} {url} -> {status}")
        self.page.on("response", on_response)

    def get_non_ok_responses(self) -> List[Dict[str, Any]]:
        """获取非 2xx 响应列表"""
        return self.non_ok_responses

    def assert_all_ok(self):
        """断言所有响应都是 2xx 状态码"""
        if self.non_ok_responses:
            msg = "\n".join(
                f"{item['method']} {item['url']} -> {item['status']} {item['status_text']}"
                for item in self.non_ok_responses
            )
            pytest.fail(f"检测到非 2xx API 响应：\n{msg}")

    def ignore_urls(self, *patterns):
        """添加要忽略的 URL 模式（注意：此方法仅对后续响应生效）"""
        self.ignore_patterns.extend(patterns)


# ==================== Playwright 相关 Fixtures ====================
@pytest.fixture(scope="session")
def playwright():
    """提供 Playwright 实例（会话级）"""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright):
    """
    启动浏览器实例（会话级）
    改进：增加异常处理，提供友好错误提示
    """
    try:
        browser_type = getattr(playwright, settings.browser.type)
        browser = browser_type.launch(headless=settings.browser.headless)
        yield browser
        browser.close()
    except Exception as e:
        pytest.exit(f"启动浏览器失败: {e}", returncode=1)


@pytest.fixture(scope="function")
def context(browser: Browser) -> BrowserContext:
    """
    创建浏览器上下文（函数级）
    设置视口大小为 1920x1080
    """
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    """
    创建新的页面实例（函数级）
    设置默认超时时间为配置文件中指定的值
    """
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)
    yield page
    # 页面会随上下文关闭而自动关闭，无需显式 close


@pytest.fixture(scope="function")
def page_with_monitor(context: BrowserContext, ignore_api_patterns: Optional[List[str]] = None) -> Page:
    """
    带 API 响应监控的页面 fixture
    改进：复用 context 而非直接创建新页面，支持传入忽略模式列表
    """
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)
    collector = APIResponseCollector(page, ignore_patterns=ignore_api_patterns)
    page.api_collector = collector
    yield page
    collector.assert_all_ok()
    # 页面会随上下文关闭而自动关闭


# ==================== API 相关 Fixtures ====================
@pytest.fixture(scope="function")
def api_client():
    """创建 API 客户端实例（函数级）"""
    api_base_url = getattr(settings, "api_base_url", None)
    if not api_base_url:
        pytest.skip("API 基础 URL 未配置")

    client = APIClient(base_url=api_base_url)
    yield client
    client.close()


@pytest.fixture(scope="function")
def user_credentials(request) -> Dict[str, str]:
    """
    提供用户凭证的 fixture，支持间接参数化
    用法示例：
        @pytest.mark.parametrize("user_credentials", [{"username": "admin", "password": "pass"}], indirect=True)
        def test_something(auth_token, user_credentials):
            ...
    """
    # 如果测试函数通过参数化传入了 user_credentials，则使用；否则使用配置默认值
    if hasattr(request, "param") and request.param:
        return request.param
    default_user = getattr(settings, "default_user", {})
    return {
        "username": default_user.get("username", ""),
        "password": default_user.get("password", "")
    }


@pytest.fixture(scope="function")
def auth_token(api_client: APIClient, user_credentials: Dict[str, str]) -> Optional[str]:
    """
    获取认证 token（函数级）
    支持动态用户名/密码，优先使用 user_credentials 中的凭证
    """
    username = user_credentials.get("username")
    password = user_credentials.get("password")

    if not username or not password:
        pytest.skip("缺少用户名或密码，无法获取认证 token")

    # 尝试从缓存获取
    cached_token = login_cache.get_token(key=username)
    if cached_token:
        return cached_token

    # 调用登录接口
    resp = api_client.post("/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.fail(f"登录失败: {resp.status_code} {resp.text}")

    token = resp.json().get("access_token")
    if not token:
        pytest.fail("登录响应中未包含 access_token")

    # 缓存 token
    login_cache.save_token(token, key=username)
    return token


# ==================== 数据库相关 Fixtures ====================
@pytest.fixture(scope="function")
def db():
    """
    创建数据库 helper 实例（函数级）
    改进：简化配置检查，使用列表推导
    """
    required_db_configs = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [cfg for cfg in required_db_configs if not getattr(settings, cfg, None)]
    if missing:
        pytest.skip(f"缺少数据库配置: {', '.join(missing)}")

    db_type = getattr(settings, "DB_TYPE", "mysql")
    db_helper = DatabaseHelper()
    yield db_helper
    db_helper.close_all()


# ==================== 登录相关 Fixtures ====================
@pytest.fixture(scope="function")
def smart_login(browser: Browser, user_credentials: Dict[str, str]):
    """
    智能登录 fixture（函数级）
    改进：复用 browser 实例，避免重复启动浏览器；增加登录函数防御
    """
    # 尝试导入 login_page 模块，若无则使用默认登录函数
    try:
        from pages.components.login_page import login_page
        login_func = login_page
    except ImportError:
        def default_login(page: Page, username: str, password: str):
            # 增加防御：确保 page 已初始化
            if not page:
                raise RuntimeError("登录页面未初始化")
            page.goto(settings.login_url or settings.base_url)
            page.fill("input[name='username']", username)
            page.fill("input[name='password']", password)
            page.click("button[type='submit']")
        login_func = default_login

    username = user_credentials["username"]
    password = user_credentials["password"]

    # 创建 SmartLogin 实例，传入 browser 而非直接创建
    smart_login_instance = SmartLogin(
        username=username,
        password=password,
        login_func=login_func,
        browser=browser   # 假设 SmartLogin 支持接收 browser 参数
    )
    yield smart_login_instance
    smart_login_instance.stop_browser()


@pytest.fixture(scope="function")
def logged_in_page(smart_login: SmartLogin) -> Page:
    """
    已登录的页面对象（函数级）
    """
    page = smart_login.smart_login()
    yield page
    # 页面会在 smart_login fixture 中自动关闭


# ==================== pytest 配置 ====================
def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption(
        "--env",
        action="store",
        default=os.getenv("ENV", "beta"),
        choices=["alpha", "beta", "prod"],
        help="指定测试环境：alpha, beta, prod"
    )


def pytest_collection_modifyitems(config, items):
    """
    根据环境标记过滤测试用例
    修复：当标记无参数时，跳过过滤（允许所有环境）
    """
    current_env = config.getoption("--env")

    for item in items:
        env_marker = item.get_closest_marker("env")
        if env_marker:
            allowed_envs = env_marker.args
            # 如果没有参数，表示不限制环境
            if not allowed_envs:
                continue

            # 处理可能嵌套的列表（如 @pytest.mark.env(['dev', 'prod'])）
            if len(allowed_envs) == 1 and isinstance(allowed_envs[0], (list, tuple)):
                allowed_envs = allowed_envs[0]

            # 检查当前环境是否在允许列表中
            if current_env not in allowed_envs:
                reason = f"测试仅允许在环境 {allowed_envs} 中运行，当前环境为 {current_env}"
                item.add_marker(pytest.mark.skip(reason=reason))


# ==================== YAML 数据驱动测试 ====================
@lru_cache(maxsize=128)
def _cached_load_yaml(file_path_str: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    带缓存的YAML加载（基于绝对路径）
    """
    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"YAML文件不存在: {file_path}")
    return load_yaml_file(file_path)


def _extract_yaml_param_names(metafunc, first_case: Dict[str, Any]) -> List[str]:
    """
    提取需从YAML注入的参数名（强制要求参数名与YAML字段名一致）
    """
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
    return param_names


def pytest_generate_tests(metafunc):
    """
    pytest 动态参数化钩子
    改进：
      - 跳过无效用例时发出警告
      - 修复空参数化时的错误处理
    """
    marker = metafunc.definition.get_closest_marker("yaml_data")
    if marker is None:
        return

    # 1. 验证标记参数
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

    # 2. 构建文件路径
    abs_file_path = PROJECT_ROOT / "test_data" / file_name
    logger.debug(f"Loading YAML file: {abs_file_path}")

    # 3. 文件存在性检查
    if not abs_file_path.exists():
        _warn_and_skip(
            metafunc,
            f"YAML数据文件不存在，跳过测试: {abs_file_path}\n"
        )
        _parametrize_empty(metafunc)
        return

    # 4. 加载YAML数据
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

    # 5. 验证用例组存在性
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

    # 6. 提取参数名
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

    # 7. 构建参数值与ID
    param_values: List[Tuple[Any, ...]] = []
    param_ids: List[str] = []
    used_ids = set()  # 用于去重ID

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

        # 生成可读性ID，并保证唯一性
        case_id = (
            str(case.get("id", "")) or
            str(case.get("name", "")) or
            str(case.get("desc", "")) or
            f"{group_name}_{idx}"
        )
        # 清理为有效标识符
        case_id = re.sub(r'[^a-zA-Z0-9_]', '_', case_id)
        case_id = re.sub(r'_+', '_', case_id).strip('_')
        if not case_id or not case_id[0].isalpha():
            case_id = f"{group_name}_{idx}"
        # 去重：如果ID已存在，添加后缀
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

    # 8. 处理无有效用例场景
    if not param_values:
        _warn_and_skip(
            metafunc,
            f"用例组 '{group_name}' 无有效用例（所有用例均因字段缺失被跳过）\n"
            f"  所需参数: {param_names}"
        )
        _parametrize_empty(metafunc)
        return

    # 9. 正常参数化
    metafunc.parametrize(
        ",".join(param_names),
        param_values,
        ids=param_ids,
        scope="function"
    )


# ==================== 辅助函数 ====================
def _raise_usage_error(metafunc, message: str) -> None:
    """在收集阶段抛出使用错误"""
    raise pytest.UsageError(
        f"[YAML数据错误] in {metafunc.definition.nodeid}\n{message}"
    )


def _warn_and_skip(metafunc, message: str) -> None:
    """安全发出警告并使用空参数化跳过测试"""
    full_message = f"[YAML数据] in {metafunc.definition.nodeid}\n{message}"
    warnings.warn(full_message, UserWarning, stacklevel=2)
    print(f"\n⚠️  YAML数据跳过 [{metafunc.definition.nodeid}]:\n{message}", file=sys.stderr)


def _parametrize_empty(metafunc) -> None:
    """
    参数化空列表触发pytest自动跳过
    改进：确保参数名有效且存在于 fixturenames 中
    """
    safe_params = [
        p for p in metafunc.fixturenames
        if p.isidentifier() and not p.startswith("_") and p != "request"
    ]

    if not safe_params:
        _raise_usage_error(
            metafunc,
            "测试函数无有效参数，无法通过空参数化跳过。请检查测试函数是否至少有一个参数。"
        )
        return

    param_name = safe_params[0]
    metafunc.parametrize(
        param_name,
        [],  # 空列表触发跳过
        ids=[],
        scope="function"
    )