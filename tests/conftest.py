import pytest
import warnings
import sys
from pathlib import Path
from typing import List, Tuple, Any, Dict
from functools import lru_cache
import re

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import PROJECT_ROOT, settings
from utils.data.yaml_cases_loader import load_yaml_file, InvalidYamlFormatError
from playwright.sync_api import sync_playwright
from utils.api_client import APIClient

from utils.data.db_helper import DatabaseHelper


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
    browser = getattr(playwright, settings.BROWSER).launch(headless=settings.HEADLESS)
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
    page.set_default_timeout(settings.TIMEOUT)
    yield page


@pytest.fixture(scope="function")
def api_client():
    """
    创建 API 客户端实例
    作用域：function，每个测试函数创建一个新的客户端
    """
    client = APIClient(base_url=settings.API_BASE_URL)
    yield client
    client.close()


@pytest.fixture(scope="function")
def db():
    """
    创建数据库 helper 实例
    作用域：function，每个测试函数创建一个新的数据库连接
    """
    db_helper = DatabaseHelper(settings.DB_HOST, settings.DB_PORT, settings.DB_NAME, settings.DB_USER, settings.DB_PASSWORD)
    yield db_helper
    db_helper.close()


@pytest.fixture(scope="function")
def auth_token(api_client):
    """
    获取认证 token
    作用域：function，每个测试函数获取一个新的 token
    使用配置文件中的默认用户信息登录
    """
    resp = api_client.post("/auth/login", json={"username": settings.DEFAULT_USER["username"], "password": settings.DEFAULT_USER["password"]})
    return resp.json().get("access_token")


# ==================== 安全的YAML加载（带缓存） ====================
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


# ==================== 核心钩子（完全修复版） ====================
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
    print('abs_file_path:', abs_file_path)
    
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


# ==================== 安全的辅助函数 ====================
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


if __name__=='__main__':
    # 测试文件路径构建
    file_name='login_cases.yaml'
    abs_file_path = PROJECT_ROOT /'test_data'/ file_name
    print('abs_file_path:', abs_file_path)