"""
E2E / API 测试专用 fixtures（基于 Playwright / requests）
提供：
- API 客户端相关：api_client, auth_token, authenticated_client
- 数据库相关：db
- 用户凭证：user_credentials
- Playwright 相关（如需）请另行组合
"""
import os
from typing import Dict, Generator, Optional

import pytest

from api_client import APIClient
from config import settings
from core import login_cache  # 指向上面的 login_cache 模块
from data.db_helper import DatabaseHelper
from logger import logger
from security import decrypt_env_key


# ==================== API 客户端 fixture ====================
@pytest.fixture(scope="function")
def api_client() -> Generator[APIClient, None, None]:
    """返回 API 客户端实例，测试结束后自动关闭"""
    api_base_url = getattr(settings, "api_base_url", None)
    if not api_base_url:
        pytest.skip("api_base_url 未配置")
    timeout = getattr(settings.timeouts, "api", 30)
    client = APIClient(base_url=api_base_url, timeout=timeout)
    yield client
    client.close()


# ==================== 用户凭证 fixture ====================
@pytest.fixture(scope="function")
def user_credentials(request) -> Dict[str, str]:
    """获取用户凭证，优先使用参数化传入，否则使用 settings 默认账号"""
    if hasattr(request, "param") and request.param:
        return request.param
    username = os.getenv("USERNAME")
    password = decrypt_env_key("PASSWORD")
    if not username or not password:
        pytest.skip("默认凭证未配置")
    return {"username": username, "password": password}


# ==================== Token 获取辅助函数 ====================
def _fetch_token(api_client: APIClient, username: str, password: str) -> Optional[str]:
    """实时获取 token，区分 skip 与 fail"""
    login_endpoint = getattr(settings, "api_login_endpoint", None)
    if not login_endpoint:
        pytest.skip("api_login_endpoint 未配置")

    try:
        resp = api_client.post(login_endpoint, json={"username": username, "password": password})
    except Exception as e:
        pytest.fail(f"登录请求异常: {e}")

    if resp.status_code in (401, 403):
        pytest.skip(f"凭证无效或无权登录: {username}")
    elif resp.status_code != 200:
        pytest.fail(f"登录失败: {resp.status_code} {resp.text}")

    token = resp.json().get("access_token")
    if not token:
        pytest.fail("登录响应中未包含 access_token")
    return token


# ==================== 会话级 Token（避免重复登录，并发安全） ====================
@pytest.fixture(scope="session")
def auth_token_session(
    api_client: APIClient,
    user_credentials: Dict[str, str]
) -> Optional[str]:
    """
    会话级别的认证 token，支持 pytest-xdist 并行。
    由于 login_cache 使用 filelock，多进程下缓存读写是安全的。
    """
    username = user_credentials.get("username")
    password = user_credentials.get("password")
    if not username or not password:
        pytest.skip("缺少用户名或密码")

    # 尝试从缓存获取（filelock 保证并发安全）
    cached_token = login_cache.get_token(username)
    if cached_token:
        logger.debug(f"使用缓存的 token: {username}")
        return cached_token

    # 实时登录
    token = _fetch_token(api_client, username, password)
    login_cache.save_token(token, username)
    logger.info(f"获取并缓存新 token: {username}")
    return token


@pytest.fixture(scope="function")
def auth_token(auth_token_session: str) -> str:
    """函数级 token 代理，直接复用会话级 token"""
    return auth_token_session


@pytest.fixture(scope="function")
def authenticated_client(api_client: APIClient, auth_token: str) -> APIClient:
    """返回已自动添加认证头的 API 客户端"""
    api_client.set_auth_token(auth_token)
    return api_client


# ==================== 数据库 fixture ====================
@pytest.fixture(scope="function")
def db() -> Generator[DatabaseHelper, None, None]:
    """数据库 helper，支持事务回滚（需 DatabaseHelper 实现 transaction 方法）"""
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [cfg for cfg in required if not os.getenv(cfg)]
    if missing:
        pytest.skip(f"缺少数据库配置: {', '.join(missing)}")

    db_helper = DatabaseHelper()

    # 期望 DatabaseHelper 提供事务上下文管理器，否则降级处理
    if hasattr(db_helper, "transaction"):
        with db_helper.transaction():
            yield db_helper
    else:
        logger.warning("DatabaseHelper 未实现事务上下文，测试可能污染数据库")
        yield db_helper
        if hasattr(db_helper, "rollback"):
            db_helper.rollback()
        db_helper.close_all()