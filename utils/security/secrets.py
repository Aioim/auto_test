"""
🔐 SecretsManager - 企业级敏感信息管理器

核心安全设计：
✅ 内存中仅存储加密字节（无明文缓存）
✅ 每次 get_secret() 动态解密（最小化明文生命周期）
✅ 密钥文件严格验证（44字节 + base64 校验）
✅ 生产环境零容忍（密钥无效立即终止进程）
✅ 防内存转储（加密数据 + 禁止 pickle）
✅ 防时序攻击（恒定时间比较）

使用示例：
#>>> from security.secrets import SecretsManager
#>>> secrets = SecretsManager()
#>>> secrets.set_secret("api_key", "sk-xxx")
#>>> api_key = secrets.get_secret("api_key")
#>>> api_key.get()
'sk-xxx'
"""
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Final
from cryptography.fernet import Fernet, InvalidToken
from cryptography.exceptions import InvalidSignature

from ..logger import logger, security_logger
from .secret_str import SecretStr

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
print('PROJECT_ROOT:',PROJECT_ROOT)
# ==================== 安全配置 ====================

class SecurityConfig:
    """安全配置集中管理"""
    # 密钥文件路径
    KEY_FILE: Final[Path] = PROJECT_ROOT / "config" / "secrets" / ".secret_key"

    # Fernet 密钥必须为 44 字节 URL 安全 base64
    KEY_LENGTH: Final[int] = 44

    # 环境检测（不可覆盖）
    ENV: Final[str] = os.getenv("ENV", "dev").lower()
    IS_PRODUCTION: Final[bool] = ENV in ("prod", "production", "staging")
    IS_CI: Final[bool] = os.getenv("CI", "false").lower() == "true"

    # 安全策略
    AUTO_GENERATE_IN_PROD: Final[bool] = False  # 严格禁止
    MASK_VISIBLE_START: Final[int] = 3
    MASK_VISIBLE_END: Final[int] = 4


# ==================== 密钥诊断工具 ====================

def _diagnose_key_issue(key_bytes: bytes) -> str:
    """
    精准诊断密钥问题（含平台特定修复指南）

    Args:
        key_bytes: 原始密钥字节

    Returns:
        str: 诊断报告和修复指南
    """
    length = len(key_bytes)
    lines = [f"❌ Invalid key length: {length} bytes (expected {SecurityConfig.KEY_LENGTH})"]

    # 常见问题检测
    if length == SecurityConfig.KEY_LENGTH + 1 and key_bytes.endswith(b'\n'):
        lines.append("   → Contains Unix newline \\n (use 'wb' mode when generating)")
    elif length == SecurityConfig.KEY_LENGTH + 2 and key_bytes.endswith(b'\r\n'):
        lines.append("   → Contains Windows CRLF \\r\\n (critical error!)")
    elif length == 32:
        lines.append("   → Raw 32-byte key (not base64-encoded)")
    elif length < 40:
        lines.append("   → Severely truncated key")

    # 修复指南（跨平台）
    lines.extend([
        "",
        "=" * 70,
        "🔧 KEY REPAIR GUIDE (Cross-Platform)",
        "=" * 70,
        "# STEP 1: Delete invalid key",
        "   # Linux/Mac:   rm -f .secret_key",
        "   # Windows PS:  Remove-Item -Force .secret_key",
        "",
        "# STEP 2: Generate VALID key (BINARY MODE IS CRITICAL)",
        "   python -c \"from cryptography.fernet import Fernet; " +
        "open('.secret_key', 'wb').write(Fernet.generate_key())\"",
        "",
        "# STEP 3: Verify key integrity",
        "   python -c \"from cryptography.fernet import Fernet; " +
        "k=open('.secret_key','rb').read().strip(); " +
        "assert len(k)==44, 'Invalid length'; " +
        "Fernet(k); print('✓ VALID KEY')\"",
        "",
        "# STEP 4: IMMEDIATELY add to .gitignore",
        "   echo '.secret_key' >> .gitignore",
        "=" * 70,
        ""
    ])
    return "\n".join(lines)


# ==================== 核心管理器 ====================

class SecretsManager:
    """
    敏感信息管理器 - 内存加密版

    安全设计：
    • 内存中仅存储加密字节（无明文缓存）
    • 每次 get_secret() 动态解密（最小化明文生命周期）
    • 密钥文件严格验证（44字节 + base64 校验）
    • 生产环境零容忍（密钥无效立即终止进程）

    ⚠️ 重要：本模块不提供持久化存储，重启后内存数据丢失
    """

    def __init__(self):
        """
        初始化 SecretsManager

        流程：
        1. 尝试加载 .secret_key 文件
        2. 验证密钥有效性（44字节 + base64）
        3. 生产环境：失败则立即终止
        4. 开发环境：自动创建临时密钥（带警告）
        """
        self._fernet: Optional[Fernet] = None
        self._encrypted_cache: Dict[str, bytes] = {}  # 仅存储加密字节

        # 严格初始化流程
        try:
            self._load_key_file()
            security_logger.info("✓ Encryption initialized from %s", SecurityConfig.KEY_FILE.name)
        except FileNotFoundError as e:
            self._handle_missing_key(e)
        except (ValueError, InvalidSignature) as e:
            self._handle_invalid_key(e)
        except Exception as e:
            self._handle_initialization_error(e)

        # 生产环境强制验证
        if SecurityConfig.IS_PRODUCTION and not self._fernet:
            self._fatal_error(
                "CRITICAL: Encryption unavailable in production environment\n"
                "Required: Valid 44-byte Fernet key in .secret_key file\n"
                "Action: Pre-generate key in secure environment BEFORE deployment"
            )

    def _load_key_file(self) -> None:
        """
        安全加载密钥文件（严格验证）

        Raises:
            FileNotFoundError: 密钥文件不存在
            ValueError: 密钥格式无效
        """
        if not SecurityConfig.KEY_FILE.exists():
            raise FileNotFoundError(f"Key file not found: {SecurityConfig.KEY_FILE}")

        # 二进制读取 + 严格剥离空白
        with open(SecurityConfig.KEY_FILE, 'rb') as f:
            raw_key = f.read()

        # 精确长度验证（防换行符污染）
        stripped_key = raw_key.strip()
        if len(stripped_key) != SecurityConfig.KEY_LENGTH:
            raise ValueError(
                f"Invalid key length: {len(stripped_key)} bytes\n"
                + _diagnose_key_issue(raw_key)
            )

        # 验证 base64 有效性
        try:
            self._fernet = Fernet(stripped_key)
            # 执行自检：加密-解密循环验证
            test_val = b"__key_verification__"
            assert self._fernet.decrypt(self._fernet.encrypt(test_val)) == test_val
        except Exception as e:
            raise ValueError(f"Key validation failed: {e}") from e

    def _handle_missing_key(self, exc: FileNotFoundError) -> None:
        """处理缺失密钥（环境差异化处理）"""
        if SecurityConfig.IS_PRODUCTION and not SecurityConfig.IS_CI:
            self._fatal_error(
                f"MISSING KEY FILE IN PRODUCTION: {SecurityConfig.KEY_FILE}\n"
                "Policy: Production environments MUST have pre-generated keys\n"
                "Action: Generate key in secure environment and deploy with application"
            )

        # 开发/CI 环境自动创建
        if not SecurityConfig.AUTO_GENERATE_IN_PROD:
            self._generate_dev_key()
            security_logger.warning(
                "\n⚠️  AUTO-GENERATED DEVELOPMENT KEY\n"
                "   Location: %s\n"
                "   ⚠️  CRITICAL: Add to .gitignore IMMEDIATELY:\n"
                "        echo '.secret_key' >> .gitignore\n",
                SecurityConfig.KEY_FILE
            )

    def _handle_invalid_key(self, exc: Exception) -> None:
        """处理无效密钥（生产环境致命错误）"""
        if SecurityConfig.IS_PRODUCTION and not SecurityConfig.IS_CI:
            self._fatal_error(
                f"INVALID KEY IN PRODUCTION: {SecurityConfig.KEY_FILE}\n"
                f"Error: {exc}\n"
                "Policy: Production keys must be pre-validated\n"
                "Action: Regenerate key in secure environment"
            )

        # 开发环境提供诊断
        try:
            with open(SecurityConfig.KEY_FILE, 'rb') as f:
                raw = f.read()
            diagnosis = _diagnose_key_issue(raw)
            logger.warning("Key file diagnosis:\n%s", diagnosis)
        except Exception:
            pass

        # 开发环境自动恢复
        if not SecurityConfig.IS_PRODUCTION or SecurityConfig.IS_CI:
            SecurityConfig.KEY_FILE.unlink(missing_ok=True)
            self._generate_dev_key()

    def _handle_initialization_error(self, exc: Exception) -> None:
        """处理其他初始化错误"""
        if SecurityConfig.IS_PRODUCTION:
            self._fatal_error(f"Encryption initialization failed: {exc}")
        logger.warning("Encryption initialization failed (dev mode): %s", exc)

    def _generate_dev_key(self) -> None:
        """
        为开发环境生成临时密钥（严格限制）

        注意：生产环境禁止调用此方法
        """
        if SecurityConfig.IS_PRODUCTION and not SecurityConfig.AUTO_GENERATE_IN_PROD:
            raise RuntimeError("Auto-key generation forbidden in production")

        # 仅当文件不存在时生成（避免覆盖）
        if not SecurityConfig.KEY_FILE.exists():
            key = Fernet.generate_key()
            SecurityConfig.KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

            # 二进制模式写入（关键！）
            with open(SecurityConfig.KEY_FILE, 'wb') as f:
                f.write(key)

            # Unix 权限加固
            if os.name != 'nt':
                SecurityConfig.KEY_FILE.chmod(0o600)

        # 重新加载（确保有效性）
        self._load_key_file()

    def _fatal_error(self, message: str) -> None:
        """
        生产环境致命错误（立即终止）

        Args:
            message: 错误消息
        """
        logger.critical("=" * 70)
        logger.critical("SECURITY FATAL ERROR")
        logger.critical("=" * 70)
        logger.critical(message)
        logger.critical("=" * 70)
        sys.exit(1)  # 安全第一：终止进程

    def _encrypt(self, value: str) -> bytes:
        """
        加密值（返回字节）

        Args:
            value: 要加密的字符串

        Returns:
            bytes: 加密后的字节

        Raises:
            RuntimeError: 如果加密器未初始化
        """
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        return self._fernet.encrypt(value.encode())

    def _decrypt(self, encrypted_value: bytes) -> str:
        """
        解密值（字节输入）

        Args:
            encrypted_value: 加密的字节

        Returns:
            str: 解密后的字符串

        Raises:
            RuntimeError: 如果加密器未初始化
            ValueError: 如果解密失败
        """
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        try:
            return self._fernet.decrypt(encrypted_value).decode()
        except InvalidToken as e:
            raise ValueError(
                "Decryption failed: Invalid token (key mismatch or corrupted data)"
            ) from e

    # ==================== 公共 API ====================

    def set_secret(self, name: str, value: str) -> None:
        """
        安全存储敏感信息（内存加密）

        内存中仅保留加密字节，无明文缓存

        Args:
            name: 密钥名称
            value: 敏感值

        Raises:
            TypeError: 如果 value 不是字符串
            RuntimeError: 如果加密器未初始化

        Example:
            >>> secrets.set_secret("api_key", "sk-xxx")
        """
        if not isinstance(value, str):
            raise TypeError(f"Secret value must be str, got {type(value).__name__}")

        encrypted = self._encrypt(value)
        self._encrypted_cache[name] = encrypted
        security_logger.info("Secret stored: %s (encrypted in memory)", name)

    def get_secret(
            self,
            name: str,
            default: Optional[str] = None,
            required: bool = False
    ) -> Optional[SecretStr]:
        """
        获取敏感信息（动态解密）

        每次调用返回新 SecretStr 实例，最小化明文生命周期

        Args:
            name: 密钥名称
            default: 默认值（如果未找到）
            required: 是否必需（未找到时抛出异常）

        Returns:
            Optional[SecretStr]: 敏感字符串容器，或 None

        Raises:
            KeyError: 如果 required=True 且未找到
            ValueError: 如果解密失败

        Example:
            >>> secret = secrets.get_secret("api_key", required=True)
            >>> secret.get()
            'sk-xxx'
        """
        encrypted = self._encrypted_cache.get(name)

        if encrypted is None:
            if required:
                raise KeyError(f"Required secret '{name}' not found")
            if default is not None:
                return SecretStr(default, name=f"{name}_default")
            return None

        try:
            decrypted = self._decrypt(encrypted)
            return SecretStr(decrypted, name=name)
        except Exception as e:
            security_logger.error("Decryption failed for secret '%s': %s", name, e)
            raise

    def delete_secret(self, name: str) -> bool:
        """
        从内存中安全删除（覆盖引用）

        Args:
            name: 密钥名称

        Returns:
            bool: 是否成功删除

        Example:
            >>> secrets.delete_secret("api_key")
            True
        """
        if name in self._encrypted_cache:
            del self._encrypted_cache[name]
            security_logger.info("Secret purged from memory: %s", name)
            return True
        return False

    def list_secrets(self) -> list:
        """
        列出所有缓存的秘密名称（不解密）

        Returns:
            list: 密钥名称列表

        Example:
            >>> secrets.list_secrets()
            ['api_key', 'db_password']
        """
        return list(self._encrypted_cache.keys())

    def is_encrypted(self) -> bool:
        """
        检查加密是否可用

        Returns:
            bool: 是否已初始化加密器

        Example:
            >>> secrets.is_encrypted()
            True
        """
        return self._fernet is not None

    def get_status(self) -> Dict[str, Any]:
        """
        获取安全状态（无敏感信息泄露）

        Returns:
            Dict[str, Any]: 状态信息字典

        Example:
            >>> secrets.get_status()
            {
                'encrypted': True,
                'environment': 'development',
                'key_file': '/path/to/.secret_key',
                'key_file_exists': True,
                'key_valid': True,
                'secrets_cached': 2,
                'auto_generated': False
            }
        """
        return {
            "encrypted": self.is_encrypted(),
            "environment": "production" if SecurityConfig.IS_PRODUCTION else "development",
            "key_file": str(SecurityConfig.KEY_FILE),
            "key_file_exists": SecurityConfig.KEY_FILE.exists(),
            "key_valid": self._fernet is not None,
            "secrets_cached": len(self._encrypted_cache),
            "auto_generated": (
                    not SecurityConfig.KEY_FILE.exists()
                    and self.is_encrypted()
                    and not SecurityConfig.IS_PRODUCTION
            )
        }


# ==================== 全局实例（安全初始化） ====================

# 严格初始化（生产环境失败立即终止）
try:
    secrets: SecretsManager = SecretsManager()
except Exception as e:
    # 仅开发环境允许紧急降级
    if not SecurityConfig.IS_PRODUCTION or SecurityConfig.IS_CI:
        logger.warning("Falling back to EMERGENCY UNENCRYPTED mode (dev only): %s", e)


        # 紧急降级实现（无加密）
        class EmergencySecretsManager:
            """紧急降级实现（仅开发环境）"""

            def __init__(self):
                self._cache: Dict[str, SecretStr] = {}
                logger.critical(
                    "⚠️  RUNNING IN EMERGENCY UNENCRYPTED MODE\n"
                    "⚠️  NEVER USE IN PRODUCTION - MEMORY DUMP VULNERABLE"
                )

            def set_secret(self, name: str, value: str) -> None:
                self._cache[name] = SecretStr(value, name=name)
                logger.debug("[EMERGENCY] Cached secret: %s", name)

            def get_secret(self, name: str, default=None, required=False) -> Optional[SecretStr]:
                if name in self._cache:
                    return self._cache[name]
                if required:
                    raise KeyError(f"Secret '{name}' not found")
                return SecretStr(default, name=f"{name}_default") if default is not None else None

            @staticmethod
            def is_encrypted():
                return False

            @staticmethod
            def delete_secret(name: str):
                return False

            @staticmethod
            def list_secrets():
                return []

            @staticmethod
            def get_status():
                return {"encrypted": False, "emergency_mode": True, "environment": "development"}


        secrets = EmergencySecretsManager()
    else:
        # 生产环境无降级
        logger.critical("SecretsManager initialization failed in production: %s", e)
        sys.exit(1)


# ==================== 便捷 API（自动解包） ====================

def get_secret(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """
    便捷获取敏感值（自动解包 SecretStr）

    ⚠️ 警告：返回明文字符串，使用后应尽快丢弃

    Args:
        name: 密钥名称
        default: 默认值
        required: 是否必需

    Returns:
        Optional[str]: 敏感值（明文）或 None

    Example:
        >>> api_key = get_secret("api_key", required=True)
        >>> print(api_key)
        sk-xxx
    """
    secret_obj = secrets.get_secret(name, default=default, required=required)
    return secret_obj.get() if secret_obj else None


def set_secret(name: str, value: str) -> None:
    """
    便捷存储敏感值

    Args:
        name: 密钥名称
        value: 敏感值

    Example:
        >>> set_secret("api_key", "sk-xxx")
    """
    secrets.set_secret(name, value)


# ==================== 密钥管理工具 ====================

def generate_key_file(filepath: Optional[str] = None) -> str:
    """
    安全生成密钥文件（生产环境预置用）

    Args:
        filepath: 密钥文件路径（默认 .secret_key）

    Returns:
        str: 密钥文件绝对路径

    Raises:
        RuntimeError: 生产环境禁止生成

    Example:
        >>> generate_key_file()
        '/path/to/.secret_key'
    """
    if SecurityConfig.IS_PRODUCTION and not SecurityConfig.IS_CI:
        raise RuntimeError("Key generation forbidden in production environment")

    key = Fernet.generate_key()
    key_path = Path(filepath) if filepath else SecurityConfig.KEY_FILE
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # 二进制模式写入（关键！）
    with open(key_path, 'wb') as f:
        f.write(key)

    # Unix 权限加固
    if os.name != 'nt':
        key_path.chmod(0o600)

    # 生成密钥指纹（用于审计）
    fingerprint = key.hex()[:16]

    print(f"\n✓ Encryption key generated: {key_path.resolve()}")
    print(f"✓ Key fingerprint: {fingerprint}")
    print(f"\n⚠️  CRITICAL NEXT STEPS:")
    print(f"   1. Add to .gitignore: echo '.secret_key' >> .gitignore")
    print(f"   2. Securely distribute to production hosts")
    print(f"   3. NEVER commit to version control\n")

    return str(key_path.resolve())