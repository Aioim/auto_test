import pytest
import warnings
import sys
import os
import logging
from pathlib import Path
from typing import List, Tuple, Any, Dict, Optional
from functools import lru_cache
import re
from config import PROJECT_ROOT, settings
from utils.data.yaml_cases_loader import load_yaml_file, InvalidYamlFormatError
from playwright.sync_api import sync_playwright, Page, Response
from utils.api_client import APIClient
from utils.common.smart_login import SmartLogin
from utils.data.db_helper import DatabaseHelper
from utils import login_cache
from utils.logger import logger
from playwright.sync_api import expect

class APIResponseCollector:
    """
    API 响应收集器，用于监控和收集非 2xx 状态码的 API 响应
    """
    def __init__(self, page: Page, ignore_patterns: List[str] = None):
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
        """添加要忽略的 URL 模式"""
        self.ignore_patterns.extend(patterns)


# ==================== Playwright 相关 Fixtures ====================

@pytest.fixture(scope="function")
def page_with_monitor(browser):
    """
    带 API 响应监控的页面 fixture
    作用域：function，每个测试函数创建一个新的页面
    """
    page = browser.new_page()
    collector = APIResponseCollector(page)
    page.api_collector = collector
    yield page
    collector.assert_all_ok()
    page.close()


@pytest.fixture(scope="session")
def playwright():
    """
    提供 Playwright 实例
    作用域：session，整个测试会话只创建一次
    """
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright):
    """
    启动浏览器实例
    作用域：session，整个测试会话只启动一次浏览器
    使用配置文件中指定的浏览器类型
    """
    browser = getattr(playwright, settings.browser.type).launch(headless=settings.browser.headless)
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def context(browser):
    """
    创建浏览器上下文
    作用域：function，每个测试函数创建一个新的上下文
    设置视口大小为 1920x1080
    """
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context):
    """
    创建新的页面实例
    作用域：function，每个测试函数创建一个新的页面
    设置默认超时时间为配置文件中指定的值
    """
    page = context.new_page()
    page.set_default_timeout(settings.timeouts.page_load)
    yield page


# ==================== API 相关 Fixtures ====================

@pytest.fixture(scope="function")
def api_client():
    """
    创建 API 客户端实例
    作用域：function，每个测试函数创建一个新的客户端
    """
    api_base_url = getattr(settings, "api_base_url", None)
    if not api_base_url:
        pytest.skip("API 基础 URL 未配置")
    
    client = APIClient(base_url=api_base_url)
    yield client
    client.close()


@pytest.fixture(scope="function")
def auth_token(api_client, username: str = None):
    """
    获取认证 token
    作用域：function，每个测试函数获取一个新的 token
    使用配置文件中的默认用户信息登录
    """
    # 获取用户名
    default_user = getattr(settings, "default_user", {})
    username = username or default_user.get("username", "default")
    
    # Try to get token from cache
    cached_token = login_cache.get_token(key=username)
    if cached_token:
        return cached_token
    
    # Get new token
    password = default_user.get("password", "")
    
    if not password:
        pytest.skip("默认用户密码未配置，无法获取认证 token")
    
    resp = api_client.post("/auth/login", json={"username": username, "password": password})
    token = resp.json().get("access_token")
    
    # Cache the token
    if token:
        login_cache.save_token(token, key=username)
    
    return token


# ==================== 数据库相关 Fixtures ====================

@pytest.fixture(scope="function")
def db():
    """
    创建数据库 helper 实例
    作用域：function，每个测试函数创建一个新的数据库连接
    """
    # 检查数据库配置
    required_db_configs = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing_configs = []
    
    for config in required_db_configs:
        if not getattr(settings, config, None):
            missing_configs.append(config)
    
    if missing_configs:
        pytest.skip(f"缺少数据库配置: {', '.join(missing_configs)}")
    
    # 获取数据库类型，默认为 mysql
    db_type = getattr(settings, "DB_TYPE", "mysql")
    
    db_helper = DatabaseHelper()
    yield db_helper
    db_helper.close_all()


# ==================== 登录相关 Fixtures ====================

@pytest.fixture(scope="function")
def smart_login(username: str = None, password: str = None):
    """
    智能登录 fixture
    作用域：function，每个测试函数获取一个新的登录实例
    使用配置文件中的默认用户信息登录
    """
    # 尝试导入 login_page
    try:
        from pages.components.login_page import login_page
        login_func = login_page
    except ImportError:
        # 如果 login_page 模块不存在，使用默认的登录函数
        def default_login(username, password):
            from playwright.sync_api import Page
            page: Page = SmartLogin.page
            if page:
                page.goto(settings.login_url or settings.base_url)
                # 这里可以添加默认的登录逻辑
                page.fill("input[name='username']", username)
                page.fill("input[name='password']", password)
                page.click("button[type='submit']")
        login_func = default_login
    
    # 如果没有提供用户名和密码，从配置中获取
    if not username or not password:
        default_user = getattr(settings, "default_user", {})
        username = username or default_user.get("username", "")
        password = password or default_user.get("password", "")
    
    smart_login_instance = SmartLogin(
        username=username,
        password=password,
        login_func=login_func
    )
    yield smart_login_instance
    smart_login_instance.stop_browser()


@pytest.fixture(scope="function")
def logged_in_page(smart_login):
    """
    已登录的页面对象
    作用域：function，每个测试函数获取一个新的已登录页面
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
    """
    current_env = config.getoption("--env")

    for item in items:
        # 查找 env 标记
        env_marker = item.get_closest_marker("env")
        if env_marker:
            # 获取标记参数（允许的环境列表）
            allowed_envs = env_marker.args
            if not allowed_envs:
                # 如果标记没有传参数，默认允许所有环境（可根据需求调整）
                continue

            # 如果允许的环境列表是单个字符串，转为列表方便判断
            if isinstance(allowed_envs, str):
                allowed_envs = [allowed_envs]
            elif len(allowed_envs) == 1 and isinstance(allowed_envs[0], (list, tuple)):
                # 处理可能嵌套的情况，例如 @pytest.mark.env(['dev', 'prod'])
                allowed_envs = allowed_envs[0]

            # 检查当前环境是否在允许列表中
            if current_env not in allowed_envs:
                reason = f"测试仅允许在环境 {allowed_envs} 中运行，当前环境为 {current_env}"
                # 跳过该测试
                item.add_marker(pytest.mark.skip(reason=reason))


# ==================== YAML 数据驱动测试 ====================

@lru_cache(maxsize=128)
def _cached_load_yaml(file_path_str: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    带缓存的YAML加载（基于绝对路径）
    
    Args:
        file_path_str: YAML文件的绝对路径
        
    Returns:
        加载的YAML数据
        
    Raises:
        FileNotFoundError: 如果文件不存在
    """
    file_path = Path(file_path_str)
    if not file_path.exists():
        raise FileNotFoundError(f"YAML文件不存在: {file_path}")
    return load_yaml_file(file_path)


def _extract_yaml_param_names(metafunc, first_case: Dict[str, Any]) -> List[str]:
    """
    提取需从YAML注入的参数名（强制要求参数名与YAML字段名一致）

    设计原则：
      - 不支持字段名映射（避免复杂性）
      - 测试函数参数名必须与YAML字段名完全一致
      - 自动过滤pytest内置fixture（通过字段存在性判断）
      
    Args:
        metafunc: pytest的metafunc对象
        first_case: 第一个测试用例的数据
        
    Returns:
        提取的参数名列表
    """
    yaml_fields = set(first_case.keys()) if first_case else set()
    param_names = [p for p in metafunc.fixturenames if p in yaml_fields]

    # 验证：至少有一个参数匹配
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

    关键修复：
      ✅ 移除自定义警告类别（改用标准 UserWarning）
      ✅ 修复 _parametrize_empty 确保参数名是有效标识符
      ✅ 移除有歧义的 params 参数（强制参数名匹配）
      ✅ 所有跳过场景均通过参数化空列表实现
    """
    marker = metafunc.definition.get_closest_marker("yaml_data")
    if marker is None:
        return  # 无标记，跳过参数化

    # === 1. 验证marker参数 ===
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

    # 检查是否误用了 params（已移除该功能）
    if "params" in marker.kwargs:
        _raise_usage_error(
            metafunc,
            f"@pytest.mark.yaml_data 不再支持 'params' 参数（2026-02-09重构）\n"
            f"  要求: 测试函数参数名必须与YAML字段名完全一致\n"
            f"  修复方法:\n"
            f"    1. 修改测试函数参数名匹配YAML字段，或\n"
            f"    2. 修改YAML字段名匹配测试函数参数"
        )
        return

    # === 2. 构建完整文件路径 ===
    # 修复文件路径构建
    abs_file_path = PROJECT_ROOT / "test_data" / file_name
    logger.debug(f"Loading YAML file: {abs_file_path}")
    
    # === 3. 文件存在性预检查 ===
    if not abs_file_path.exists():
        _warn_and_skip(
            metafunc,
            f"YAML数据文件不存在，跳过测试: {abs_file_path}\n"
        )
        _parametrize_empty(metafunc)
        return

    # === 4. 加载YAML数据（带缓存）===
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

    # === 5. 验证用例组存在性 ===
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
    # 确保cases始终是列表格式
    if isinstance(cases, dict):
        cases = [cases]
    if not cases:
        _warn_and_skip(
            metafunc,
            f"用例组 '{group_name}' 为空（无有效用例），跳过测试"
        )
        _parametrize_empty(metafunc)
        return

    # === 6. 提取参数名（强制匹配）===
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

    # === 7. 构建参数值与可读性ID ===
    param_values: List[Tuple[Any, ...]] = []
    param_ids: List[str] = []
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            continue

        # 严格验证：所有需要的参数必须存在
        missing = [p for p in param_names if p not in case]
        if missing:
            continue  # 跳过字段缺失的用例

        # 生成可读性ID
        case_id = (
                str(case.get("id", "")) or
                str(case.get("name", "")) or
                str(case.get("desc", "")) or
                f"{group_name}_{idx}"
        )
        # 清理为有效标识符（pytest要求）
        case_id = re.sub(r'[^a-zA-Z0-9_]', '_', case_id)
        case_id = re.sub(r'_+', '_', case_id).strip('_')
        if not case_id or not case_id[0].isalpha():
            case_id = f"{group_name}_{idx}"
        if len(case_id) > 100:
            case_id = case_id[:97] + "..."

        values = tuple(case[p] for p in param_names)
        param_values.append(values)
        param_ids.append(case_id)

    # === 8. 处理无有效用例场景 ===
    if not param_values:
        _warn_and_skip(
            metafunc,
            f"用例组 '{group_name}' 无有效用例（所有用例均因字段缺失被跳过）\n"
            f"  所需参数: {param_names}"
        )
        _parametrize_empty(metafunc)
        return

    # === 9. 正常参数化 ===
    metafunc.parametrize(
        ",".join(param_names),
        param_values,
        ids=param_ids,
        scope="function"
    )


# ==================== 辅助函数 ====================

def _raise_usage_error(metafunc, message: str) -> None:
    """
    在收集阶段抛出使用错误
    
    Args:
        metafunc: pytest的metafunc对象
        message: 错误消息
    """
    raise pytest.UsageError(
        f"[YAML数据错误] in {metafunc.definition.nodeid}\n{message}"
    )


def _warn_and_skip(metafunc, message: str) -> None:
    """
    安全发出警告（使用标准 UserWarning）

    注意：在收集阶段不能使用 pytest.skip()，只能：
      1. 通过 warnings.warn() 发出警告（pytest会捕获到警告摘要）
      2. 同时打印到stderr确保可见性
    
    Args:
        metafunc: pytest的metafunc对象
        message: 警告消息
    """
    full_message = f"[YAML数据] in {metafunc.definition.nodeid}\n{message}"

    # 使用标准 UserWarning（pytest 可识别）
    warnings.warn(full_message, UserWarning, stacklevel=2)

    # 同时输出到stderr（-s模式下实时可见）
    print(f"\n⚠️  YAML数据跳过 [{metafunc.definition.nodeid}]:\n{message}", file=sys.stderr)


def _parametrize_empty(metafunc) -> None:
    """
    参数化空列表触发pytest自动跳过

    关键修复：确保参数名是有效的Python标识符
    
    Args:
        metafunc: pytest的metafunc对象
    """
    # 优先从测试函数参数中选择一个安全的参数名
    safe_params = [
        p for p in metafunc.fixturenames
        if p.isidentifier() and not p.startswith("_") and p != "request"
    ]

    if safe_params:
        param_name = safe_params[0]
    else:
        # 回退到安全默认值
        param_name = "yaml_skip_marker"

    # 确保是有效标识符（双重保险）
    if not param_name.isidentifier() or not param_name[0].isalpha():
        param_name = "yaml_skip_marker"

    # 参数化空列表 → pytest自动将测试标记为 skipped
    metafunc.parametrize(
        param_name,
        [],  # 空列表触发跳过
        ids=[],
        scope="function"
    )
