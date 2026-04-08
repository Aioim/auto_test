"""
🔐 安全模块包 - 企业级敏感信息管理

核心功能：
- SecretsManager: 内存加密存储敏感信息
- SecureEnvLoader: 安全加载 .env 文件（支持 ENC[...] 格式）
- SecretStr: 防泄露敏感字符串容器
- 密钥轮换与审计工具

安全原则：
✅ 内存中仅存储加密数据
✅ 生产环境零降级（密钥无效立即终止）
✅ 防内存转储（禁止 pickle/weakref）
✅ 防意外泄露（__repr__/__str__ 强制掩码）
✅ 恒定时间比较（防时序攻击）
"""
from security.secret_str import SecretStr
from security.secrets_manager import SecretsManager, get_secret, set_secret, generate_key_file
from security.env_loader import SecureEnvLoader, load_dotenv_secure
from security.env_encrypt import encrypt_value, decrypt_value, encrypt_env_file, decrypt_env_key as decrypt_env
from security.key_rotation import KeyRotator, rotate_keys

__all__ = [
    # 核心类
    "SecretsManager",
    "SecretStr",
    "SecureEnvLoader",
    "KeyRotator",
    "decrypt_env",

    # 便捷函数
    "get_secret",
    "set_secret",
    "generate_key_file",
    "load_dotenv_secure",
    "encrypt_value",
    "decrypt_value",
    "encrypt_env_file",
    "rotate_keys",
]

# 创建全局实例（延迟初始化）
_secrets_manager = None


def _get_secrets_manager():
    """延迟初始化 SecretsManager（避免模块加载时副作用）"""
    global _secrets_manager
    if _secrets_manager is None:
        from .secrets import SecretsManager
        _secrets_manager = SecretsManager()
    return _secrets_manager


# 提供便捷访问
def get_secret(name: str, default: str = None, required: bool = False):
    """便捷获取敏感信息"""
    return _get_secrets_manager().get_secret(name, default=default, required=required)


def set_secret(name: str, value: str):
    """便捷存储敏感信息"""
    return _get_secrets_manager().set_secret(name, value)


def is_encrypted() -> bool:
    """检查加密是否启用"""
    return _get_secrets_manager().is_encrypted()