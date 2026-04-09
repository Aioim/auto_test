"""
登录 Token 缓存模块（用于 API 测试）

提供基于文件的 token 缓存，支持多进程并行（使用 filelock）。
缓存文件存储在 .token_cache 目录下，每个 key（如用户名）对应一个 JSON 文件。
"""

import json
import time
from pathlib import Path
from typing import Optional

from filelock import FileLock
from config import settings

# 缓存目录（可从 settings 或环境变量获取）
TOKEN_CACHE_DIR = Path(getattr(settings, "TOKEN_CACHE_DIR", ".token_cache"))
TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_MAX_AGE = getattr(settings, "TOKEN_MAX_AGE", 3600)  # 默认 1 小时


def _get_cache_path(key: str) -> Path:
    """生成缓存文件路径"""
    safe_key = "".join(c for c in key if c.isalnum() or c in "._-")
    return TOKEN_CACHE_DIR / f"{safe_key}.json"


def _get_lock_path(key: str) -> Path:
    """锁文件路径"""
    return TOKEN_CACHE_DIR / f"{key}.lock"


def get_token(key: str, max_age: int = None) -> Optional[str]:
    """
    获取缓存的 token。

    Args:
        key: 唯一标识，例如用户名
        max_age: token 有效期（秒），默认使用 TOKEN_MAX_AGE

    Returns:
        token 字符串，如果不存在或已过期则返回 None
    """
    max_age = max_age or TOKEN_MAX_AGE
    cache_file = _get_cache_path(key)
    if not cache_file.exists():
        return None

    lock = FileLock(_get_lock_path(key))
    with lock:
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            if time.time() - data.get("timestamp", 0) > max_age:
                return None
            return data.get("token")
        except (json.JSONDecodeError, KeyError, OSError):
            # 缓存文件损坏，忽略并返回 None
            return None


def save_token(token: str, key: str) -> None:
    """
    保存 token 到缓存。

    Args:
        token: 要缓存的 token
        key: 唯一标识
    """
    cache_file = _get_cache_path(key)
    lock = FileLock(_get_lock_path(key))
    with lock:
        try:
            with open(cache_file, 'w') as f:
                json.dump({"token": token, "timestamp": time.time()}, f)
        except OSError as e:
            # 记录警告但不抛出异常，避免影响测试
            print(f"Warning: Failed to save token for {key}: {e}")


def clear_token(key: str) -> None:
    """清除指定 key 的 token 缓存"""
    cache_file = _get_cache_path(key)
    lock = FileLock(_get_lock_path(key))
    with lock:
        if cache_file.exists():
            cache_file.unlink()


def clear_all() -> None:
    """清除所有 token 缓存文件及锁文件"""
    for f in TOKEN_CACHE_DIR.glob("*.json"):
        f.unlink()
    for l in TOKEN_CACHE_DIR.glob("*.lock"):
        l.unlink()


# 可选：提供类封装，便于依赖注入
class TokenCache:
    def __init__(self, cache_dir: Optional[Path] = None, max_age: int = TOKEN_MAX_AGE):
        self.cache_dir = cache_dir or TOKEN_CACHE_DIR
        self.max_age = max_age
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[str]:
        return get_token(key, self.max_age)

    def set(self, key: str, token: str) -> None:
        save_token(token, key)

    def delete(self, key: str) -> None:
        clear_token(key)

    def clear(self) -> None:
        clear_all()


# 默认实例（保持与原有 login_cache 模块接口一致）
default_cache = TokenCache()

# 为了方便直接导入模块函数，已经在模块顶层定义了 get_token, save_token, clear_token, clear_all