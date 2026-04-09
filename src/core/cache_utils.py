"""
浏览器登录状态缓存公共工具模块

提供统一的：
- 缓存路径生成（与环境绑定）
- 缓存有效性验证（支持 cookie 快速检查和回退访问首页）
- 线程安全的缓存保存（使用 filelock）
- 环境变量加载（支持 .env 和 .env.<env>）
- 从环境变量获取角色凭证
- 统一的登录成功等待机制（支持 SPA 选择器或 URL）
"""

import json
import os
import time
from pathlib import Path
from typing import Optional, Dict

from filelock import FileLock
from playwright.sync_api import Page, Browser
from dotenv import load_dotenv

from config import settings
from logger import logger
from security import decrypt_env_key
# ==================== 配置常量（优先从 settings 读取，提供默认值） ====================
BROWSER_CACHE_DIR = Path(getattr(settings.browser, "cache_dir", ".browser_cache"))
BROWSER_STATE_CACHE_ENABLED = getattr(settings, "browser_state_cache_enabled", True)
LOGIN_FALLBACK_ENABLED = getattr(settings, "login_enabled", True)
AUTH_COOKIE_NAMES = getattr(settings, "auth_cookie_names", ["sessionid", "token", "auth_token", "jwt"])
LOGIN_SUCCESS_SELECTOR = getattr(settings, "login_success_selector", None)  # SPA 登录成功标志选择器
LOGIN_TIMEOUT = getattr(settings, "login_timeout", 10000)  # 登录等待超时时间（毫秒）


# ==================== 缓存路径管理 ====================
def get_storage_state_path(username: str, env: str = None) -> Optional[Path]:
    """
    生成 storage_state 缓存文件路径（与环境绑定）
    
    Args:
        username: 用户名
        env: 环境标识（如 beta, prod），默认从 settings.ENV 获取
    
    Returns:
        缓存文件路径，若缓存被禁用则返回 None
    """
    if not BROWSER_STATE_CACHE_ENABLED:
        return None
    BROWSER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    env = env or getattr(settings, "env", "beta")
    safe_username = "".join(c for c in username if c.isalnum() or c in "._-")
    filename = f"{safe_username}_{env}.json"
    return BROWSER_CACHE_DIR / filename


# ==================== 缓存有效性验证 ====================
def is_storage_state_valid(storage_path: Path, browser: Browser, base_url: str) -> bool:
    """
    验证缓存文件是否有效（仍处于登录状态）
    
    优先检查认证 cookie 是否过期，若不确定则回退到访问首页验证。
    
    Args:
        storage_path: 缓存文件路径
        browser: Playwright Browser 实例
        base_url: 应用基础 URL
    
    Returns:
        缓存有效返回 True，否则 False
    """
    if not storage_path.exists():
        return False
    try:
        with open(storage_path, 'r') as f:
            state = json.load(f)
        # 快速检查：是否存在有效的认证 cookie
        cookies = state.get('cookies', [])
        now = time.time()
        valid_cookie = any(
            c.get('name') in AUTH_COOKIE_NAMES and
            c.get('expires', now + 1) > now
            for c in cookies
        )
        if valid_cookie:
            return True
        # 快速检查未通过，回退到访问首页验证（开销较大但准确）
        logger.debug(f"快速检查未通过，尝试访问首页验证缓存: {storage_path}")
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()
        page.goto(base_url, timeout=5000)
        # 使用统一的登录成功等待机制判断是否已登录
        is_valid = _is_page_logged_in(page)
        context.close()
        return is_valid
    except Exception as e:
        logger.warning(f"缓存文件无效: {storage_path}, 错误: {e}")
        return False


def _is_page_logged_in(page: Page) -> bool:
    """
    判断当前页面是否已登录（不抛出异常）
    优先使用 LOGIN_SUCCESS_SELECTOR，否则检查 URL 是否包含 login
    """
    try:
        if LOGIN_SUCCESS_SELECTOR:
            # 等待一小段时间，看是否能找到登录成功标志
            page.wait_for_selector(LOGIN_SUCCESS_SELECTOR, timeout=3000)
            return True
        else:
            # 检查 URL 是否包含 login 字样
            return "login" not in page.url.lower()
    except Exception:
        return False


# ==================== 等待登录成功（供登录流程使用） ====================
def wait_for_login_success(page: Page, timeout: int = None) -> None:
    """
    等待页面登录成功
    
    优先使用 settings.LOGIN_SUCCESS_SELECTOR（SPA 场景），
    否则等待 URL 变化（非 SPA 场景）。
    
    Args:
        page: Playwright Page 对象
        timeout: 超时时间（毫秒），默认使用 LOGIN_TIMEOUT
    
    Raises:
        TimeoutError: 超时未检测到登录成功
    """
    timeout = timeout or LOGIN_TIMEOUT
    if LOGIN_SUCCESS_SELECTOR:
        page.wait_for_selector(LOGIN_SUCCESS_SELECTOR, timeout=timeout)
        logger.debug(f"检测到登录成功标志: {LOGIN_SUCCESS_SELECTOR}")
    else:
        base_url = getattr(settings, "base_url", "")
        page.wait_for_url(f"{base_url}**", timeout=timeout)
        logger.debug(f"检测到 URL 变化: {page.url}")


# ==================== 保存登录状态（线程安全） ====================
def save_storage_state(page: Page, username: str, env: str = None) -> None:
    """
    保存当前页面的登录状态到缓存文件（线程安全，使用文件锁）
    
    Args:
        page: 已登录的 Playwright Page 对象
        username: 用户名
        env: 环境标识，默认从 settings.ENV 获取
    """
    storage_path = get_storage_state_path(username, env)
    if not storage_path:
        logger.warning("浏览器状态缓存已禁用，无法保存登录态")
        return
    lock_path = storage_path.with_suffix(".lock")
    with FileLock(lock_path):
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = storage_path.with_suffix(".tmp")
        page.context.storage_state(path=str(temp_path))
        temp_path.replace(storage_path)
    logger.info(f"已保存登录状态到 {storage_path}")


# ==================== 环境变量加载 ====================
def load_env_by_name(env_name: str) -> None:
    """
    根据环境名加载对应的 .env 文件
    
    优先加载 .env.<env_name>，若不存在则尝试加载 .env
    
    Args:
        env_name: 环境标识（如 beta, prod）
    """
    env_file = Path(f".env.{env_name}")
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"已加载环境文件: {env_file}")
    else:
        default_env = Path(".env")
        if default_env.exists():
            load_dotenv(default_env)
            logger.info(f"已加载默认环境文件: {default_env}")
        else:
            logger.warning("未找到 .env 文件，将仅使用系统环境变量")


# ==================== 从环境变量获取角色凭证 ====================
def get_role_credentials(role: str, env: str = None) -> Dict[str, str]:
    """
    根据角色名从环境变量获取用户名密码。
    
    环境变量命名规则（以 beta 环境为例）：
        BETA_{role}_USER, BETA_{role}_PASS
    或回退到单账号变量：
        BETA_USERNAME, BETA_PASSWORD
    
    Args:
        role: 角色名（如 employee, manager, admin）
        env: 环境标识，默认从 settings.ENV 获取
    
    Returns:
        包含 username 和 password 的字典
    
    Raises:
        ValueError: 未找到对应的环境变量配置
    """
    env = env or getattr(settings, "env", "beta")
    prefix = env.upper()
    user_key = f"{prefix}_{role.upper()}_USER"
    pass_key = f"{prefix}_{role.upper()}_PASS"
    username = os.getenv(user_key)
    password = os.getenv(pass_key)
    if username and password:
        password = decrypt_env_key(pass_key)
        return {"username": username, "password": password}
    # 回退到单账号变量
    single_user = os.getenv(f"{prefix}_USERNAME")
    single_pass = os.getenv(f"{prefix}_PASSWORD")
    if single_user and single_pass:
        single_pass = decrypt_env_key(f"{prefix}_PASSWORD")
        return {"username": single_user, "password": single_pass}
    raise ValueError(f"未找到角色 '{role}' 的环境变量配置: {user_key}/{pass_key}")


def get_all_accounts_from_env(env_name: str) -> list:
    """
    从环境变量中提取所有账号（用于 generate_login_state 多账号模式）
    
    支持三种命名模式：
    1. 数字后缀多账号：{ENV}_USER_1, {ENV}_PASS_1, {ENV}_USER_2, ...
    2. 单账号：{ENV}_USERNAME, {ENV}_PASSWORD
    3. 特定角色：{ENV}_ADMIN_USER, {ENV}_ADMIN_PASS（可扩展）
    
    Args:
        env_name: 环境标识
    
    Returns:
        账号字典列表 [{"username": "...", "password": "..."}, ...]
    """
    accounts = []
    prefix = env_name.upper()
    
    # 方式1：数字后缀多账号
    idx = 1
    while True:
        user_key = f"{prefix}_USER_{idx}"
        pass_key = f"{prefix}_PASS_{idx}"
        username = os.getenv(user_key)
        password = os.getenv(pass_key)
        if username is None and password is None:
            break
        if username and password:
            accounts.append({"username": username, "password": password})
        else:
            logger.warning(f"跳过不完整的账号组: {user_key}/{pass_key}")
        idx += 1
    
    # 方式2：单账号变量
    single_user = os.getenv(f"{prefix}_USERNAME")
    single_pass = os.getenv(f"{prefix}_PASSWORD")
    if single_user and single_pass:
        password = decrypt_env_key(f"{prefix}_PASSWORD")
        accounts.append({"username": single_user, "password": single_pass})
    
    # 方式3：特定角色（可在此扩展，例如 admin, manager, employee）
    for role in ["admin", "manager", "employee"]:
        try:
            cred = get_role_credentials(role, env_name)
            # 避免重复添加（如果与已有账号相同）
            if cred not in accounts:
                accounts.append(cred)
        except ValueError:
            pass
    
    # 去重（基于 (username, password) 元组）
    seen = set()
    unique = []
    for acc in accounts:
        key = (acc["username"], acc["password"])
        if key not in seen:
            seen.add(key)
            unique.append(acc)
    return unique


# ==================== 辅助：清理缓存 ====================
def clear_all_browser_caches(env: str = None) -> None:
    """清除指定环境（或所有环境）的浏览器缓存文件"""
    if env:
        pattern = f"*_{env}.json"
    else:
        pattern = "*.json"
    for cache_file in BROWSER_CACHE_DIR.glob(pattern):
        cache_file.unlink()
        logger.info(f"已删除缓存: {cache_file}")
    # 同时清理锁文件
    for lock_file in BROWSER_CACHE_DIR.glob("*.lock"):
        lock_file.unlink()