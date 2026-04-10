"""
API 测试专用 fixtures
提供：
- api_client
- auth_token
- db
- user_credentials
"""
import os

import pytest
from typing import Dict, Optional

from config import settings
from core import login_cache
from data.db_helper import DatabaseHelper
from logger import logger
from api_client import APIClient


# ==================== API 客户端 fixture ====================
@pytest.fixture(scope="function")
def api_client():
    """返回 API 客户端实例，测试结束后自动关闭"""
    api_base_url = getattr(settings, "API_BASE_URL", None)
    if not api_base_url:
        pytest.skip("API_BASE_URL 未配置")
    timeout = getattr(settings, "API_TIMEOUT", 30)
    client = APIClient(base_url=api_base_url, timeout=timeout)
    yield client
    client.close()


# ==================== 用户凭证 fixture ====================
@pytest.fixture(scope="function")
def user_credentials(request) -> Dict[str, str]:
    """获取用户凭证，优先使用参数化传入，否则使用 settings 默认账号"""
    if hasattr(request, "param") and request.param:
        return request.param
    return {
        "username": getattr(settings, "TEST_USERNAME", ""),
        "password": getattr(settings, "TEST_PASSWORD", "")
    }


# ==================== 认证 Token fixture ====================
@pytest.fixture(scope="function")
def auth_token(api_client: APIClient, user_credentials: Dict[str, str]) -> Optional[str]:
    """获取 API 认证 token（基于文件缓存，支持多账号）"""
    username = user_credentials.get("username")
    password = user_credentials.get("password")
    if not username or not password:
        pytest.skip("缺少用户名或密码，无法获取认证 token")

    # 尝试从缓存获取
    cached_token = login_cache.get_token(username)
    if cached_token:
        logger.debug(f"使用缓存的 token: {username}")
        return cached_token

    # 实时登录获取
    login_endpoint = getattr(settings, "API_LOGIN_ENDPOINT", "/auth/login")
    resp = api_client.post(login_endpoint, json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.fail(f"登录失败: {resp.status_code} {resp.text}")

    token = resp.json().get("access_token")
    if not token:
        pytest.fail("登录响应中未包含 access_token")

    login_cache.save_token(token, username)
    logger.info(f"获取并缓存新 token: {username}")
    return token


# ==================== 数据库 fixture ====================
@pytest.fixture(scope="function")
def db():
    """数据库 helper，支持自动事务回滚（需 DatabaseHelper 实现相应方法）"""
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [cfg for cfg in required if not os.getenv(cfg)]
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
