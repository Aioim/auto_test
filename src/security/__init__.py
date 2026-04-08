"""
🔐 Security Module - 企业级敏感信息管理套件

核心组件：
- SecretsManager: 内存加密存储与解密
- SecureEnvLoader: 安全的 .env 文件加载器
- KeyRotator: 密钥轮换与审计工具
- SecretStr: 防泄露的敏感字符串容器

使用示例：
    from security import secrets, load_secure_dotenv, SecretStr

    # 安全加载 .env 文件（自动解密 ENC[...]）
    load_secure_dotenv()

    # 存储敏感信息（内存加密）
    secrets.set_secret("api_key", "sk-xxx")
    api_key = secrets.get_secret("api_key")
    print(api_key)  # ******
"""

__version__ = "2.0.0"
__author__ = "Security Team"

# ==================== 核心类导出 ====================
from .secrets_manager import (
    SecretsManager,
    SecurityConfig,
    secrets,          # 全局单例
    get_secret,
    set_secret,
    generate_key_file,
)

from .secret_str import (
    SecretStr,
    mask_value,
    format_safely,
)

from .secure_env_loader import (
    SecureEnvLoader,
    load_secure_dotenv,  # 重命名后的便捷函数
)

from .key_rotator import (
    KeyRotator,
    perform_key_rotation,
)

# 保留旧名称别名（向后兼容，但会触发弃用警告）
from .env_encryptor import (
    encrypt_value,
    decrypt_value,
    fetch_and_decrypt_env_var as decrypt_env_key,  # 旧名映射
    process_env_file as encrypt_env_file,          # 旧名映射
)

# ==================== 模块公开 API ====================
__all__ = [
    # 核心管理器
    "SecretsManager",
    "SecurityConfig",
    "secrets",
    "get_secret",
    "set_secret",
    "generate_key_file",

    # 敏感字符串
    "SecretStr",
    "mask_value",
    "format_safely",

    # 环境加载
    "SecureEnvLoader",
    "load_secure_dotenv",

    # 密钥轮换
    "KeyRotator",
    "perform_key_rotation",

    # 加密工具（CLI 辅助）
    "encrypt_value",
    "decrypt_value",
    "decrypt_env_key",
    "encrypt_env_file",

    # 元数据
    "__version__",
    "__author__",
]

# ==================== 延迟导入警告（可选） ====================
import warnings

def __getattr__(name):
    """处理已弃用的旧名称，提供友好警告"""
    deprecated_aliases = {
        "load_dotenv_secure": "load_secure_dotenv",
        "rotate_keys": "perform_key_rotation",
        "safe_format": "format_safely",
    }
    if name in deprecated_aliases:
        new_name = deprecated_aliases[name]
        warnings.warn(
            f"'{name}' is deprecated, use '{new_name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # 动态导入新名称返回
        import importlib
        module = importlib.import_module("security")
        return getattr(module, new_name)
    raise AttributeError(f"module 'security' has no attribute '{name}'")