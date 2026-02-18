"""
🔐 SecureEnvLoader - 安全的 .env 文件加载器

特性：
- 自动识别 ENC[...] 加密字段
- 与 python-dotenv 完全兼容
- 解密失败时提供精准诊断
- 防止敏感字段意外泄露到日志
- 支持多行值、引号、转义字符

.env 文件格式示例：
    # 明文字段
    DB_HOST=localhost
    DB_PORT=5432

    # 加密字段
    DB_PASSWORD=ENC[gAAAAABkX9J3mZqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7]
    API_KEY=ENC[gAAAAABkX9J3mZqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7]
"""
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Set
from cryptography.fernet import InvalidToken

from .secrets import SecretsManager
from .secret_str import SecretStr
from utils.logger import security_logger, logger


class SecureEnvLoader:
    """
    安全的环境变量加载器

    特性：
    - 自动识别 ENC[...] 加密字段
    - 与 python-dotenv 完全兼容
    - 解密失败时提供精准诊断
    - 防止敏感字段意外泄露到日志
    """

    # 加密值正则模式：ENC[base64_encoded_value]
    ENC_PATTERN = re.compile(r'^ENC\[(?P<value>[A-Za-z0-9_\-+=/]+)\]$')

    # 敏感字段关键词（用于自动识别）
    SENSITIVE_KEYS: Set[str] = {
        'password', 'pwd', 'secret', 'key', 'token', 'credential',
        'api_key', 'access_key', 'secret_key', 'webhook_secret',
        'private_key', 'cert', 'certificate'
    }

    def __init__(self, env_file: Optional[Path] = None):
        """
        初始化 SecureEnvLoader

        Args:
            env_file: .env 文件路径（默认 .env）
        """
        self.env_file = env_file or Path('.env')
        self.secrets_manager = SecretsManager()
        self._loaded_values: Dict[str, str] = {}  # 脱敏后的值
        self._decryption_errors: Dict[str, str] = {}

    def load(self, override: bool = False) -> Dict[str, str]:
        """
        安全加载 .env 文件

        Args:
            override: 是否覆盖现有环境变量

        Returns:
            Dict[str, str]: 成功加载的变量（不含敏感字段明文）

        Raises:
            RuntimeError: 生产环境解密失败时

        Example:
            >>> loader = SecureEnvLoader(Path('.env'))
            >>> loader.load()
            {'DB_HOST': 'localhost', 'DB_PASSWORD': '******'}
        """
        if not self.env_file.exists():
            logger.warning("Env file not found: %s", self.env_file)
            return {}

        # 读取原始内容（保留注释用于诊断）
        raw_lines = self._read_env_lines()
        parsed = self._parse_env_lines(raw_lines)

        # 分离加密/明文字段
        encrypted_fields = {}
        plain_fields = {}

        for key, value in parsed.items():
            if match := self.ENC_PATTERN.match(value):
                encrypted_fields[key] = match.group('value')
            else:
                plain_fields[key] = value

        # 加载明文字段
        for key, value in plain_fields.items():
            if not override and key in os.environ:
                continue
            os.environ[key] = value
            self._loaded_values[key] = self._mask_for_log(key, value)

        # 解密敏感字段
        for key, encrypted_value in encrypted_fields.items():
            try:
                decrypted = self._decrypt_value(encrypted_value)
                if not override and key in os.environ:
                    continue

                # 安全注入环境变量
                os.environ[key] = decrypted

                # 记录脱敏日志（绝不记录明文！）
                self._loaded_values[key] = self._mask_for_log(key, decrypted)
                security_logger.info("Decrypted sensitive env var: %s", key)

            except Exception as e:
                self._decryption_errors[key] = str(e)
                security_logger.error("Decryption failed for %s: %s", key, e)

        # 安全报告
        self._log_load_summary(plain_fields, encrypted_fields)

        # 生产环境严格模式
        if self._is_production() and self._decryption_errors:
            self._fatal_error(
                f"CRITICAL: Failed to decrypt {len(self._decryption_errors)} sensitive fields\n"
                + "\n".join(f"  • {k}: {v}" for k, v in self._decryption_errors.items())
            )

        return self._loaded_values

    def _read_env_lines(self) -> list[Tuple[int, str]]:
        """
        读取带行号的原始行（用于精准错误定位）

        Returns:
            list[Tuple[int, str]]: (行号, 行内容) 列表
        """
        lines = []
        with open(self.env_file, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f, 1):
                lines.append((idx, line.rstrip('\n\r')))
        return lines

    def _parse_env_lines(self, lines: list[Tuple[int, str]]) -> Dict[str, str]:
        """
        解析 .env 行（支持注释、引号、多行）

        Args:
            lines: (行号, 行内容) 列表

        Returns:
            Dict[str, str]: 解析后的键值对
        """
        env_vars = {}
        current_key = None
        current_value = []
        in_quotes = False
        quote_char = None

        for line_no, line in lines:
            # 跳过空行和注释
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            # 处理多行值（带引号）
            if '=' in stripped and not in_quotes:
                key, value = stripped.split('=', 1)
                key = key.strip()
                value = value.strip()

                # 处理引号
                if value.startswith('"') and not value.endswith('"'):
                    in_quotes = True
                    quote_char = '"'
                    current_key = key
                    current_value = [value[1:]]  # 移除开头引号
                    continue
                elif value.startswith("'") and not value.endswith("'"):
                    in_quotes = True
                    quote_char = "'"
                    current_key = key
                    current_value = [value[1:]]
                    continue
                else:
                    env_vars[key] = self._unescape_value(value)
            elif in_quotes:
                if stripped.endswith(quote_char):
                    current_value.append(stripped[:-1])  # 移除结尾引号
                    env_vars[current_key] = '\n'.join(current_value)
                    in_quotes = False
                    current_key = None
                    current_value = []
                    quote_char = None
                else:
                    current_value.append(stripped)

        return env_vars

    def _unescape_value(self, value: str) -> str:
        """
        处理转义字符（如 \\n -> \n）

        Args:
            value: 原始值

        Returns:
            str: 转义处理后的值
        """
        # 移除首尾引号
        value = value.strip().strip('"').strip("'")
        # 处理转义序列
        return value.replace('\\\\', '\\').replace('\\n', '\n').replace('\\t', '\t')

    def _decrypt_value(self, encrypted_b64: str) -> str:
        """
        解密单个值（复用 SecretsManager）

        Args:
            encrypted_b64: base64 编码的加密值

        Returns:
            str: 解密后的明文

        Raises:
            RuntimeError: 如果 Fernet 未初始化
            ValueError: 如果解密失败
        """
        # 转换为字节（Fernet 需要 bytes）
        encrypted_bytes = encrypted_b64.encode('utf-8')

        # 复用现有 Fernet 实例
        if not self.secrets_manager._fernet:
            raise RuntimeError("Fernet not initialized")

        try:
            decrypted_bytes = self.secrets_manager._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except InvalidToken as e:
            raise ValueError(
                "Decryption failed: Invalid token (key mismatch or corrupted data).\n"
                "Common causes:\n"
                "  • .secret_key was regenerated after encrypting this value\n"
                "  • Value was manually edited (base64 corruption)\n"
                "  • Using wrong environment's .secret_key"
            ) from e

    def _mask_for_log(self, key: str, value: str) -> str:
        """
        为日志生成安全掩码（根据字段类型智能掩码）

        Args:
            key: 字段名
            value: 字段值

        Returns:
            str: 脱敏后的值
        """
        key_lower = key.lower()

        # 完全掩码（密码类）
        if any(k in key_lower for k in ['password', 'pwd', 'secret', 'token']):
            return "******"

        # 部分掩码（API密钥：保留前4后4）
        if any(k in key_lower for k in ['key', 'api']):
            if len(value) > 8:
                return f"{value[:4]}...{value[-4:]}"
            return "******"

        # 邮箱掩码
        if '@' in value and 'email' in key_lower:
            parts = value.split('@', 1)
            if len(parts) == 2:
                user, domain = parts
                return f"{user[0]}***@{domain}"

        # 默认：短值显示，长值截断
        return value if len(value) < 20 else f"{value[:15]}..."

    def _log_load_summary(self, plain_fields: Dict, encrypted_fields: Dict):
        """生成安全加载报告"""
        total = len(plain_fields) + len(encrypted_fields)
        failed = len(self._decryption_errors)
        success_enc = len(encrypted_fields) - failed

        # 安全日志（绝不记录明文）
        security_logger.info(
            "Env loaded: %d total (%d plain, %d encrypted, %d failed)",
            total, len(plain_fields), len(encrypted_fields), failed
        )

        if encrypted_fields:
            logger.info(
                "✓ Loaded %d encrypted secrets (e.g., DB_PASSWORD=******)",
                success_enc
            )

        if self._decryption_errors:
            logger.warning(
                "⚠️  Failed to decrypt %d fields: %s",
                failed,
                ", ".join(self._decryption_errors.keys())
            )

    def _is_production(self) -> bool:
        """检查是否为生产环境"""
        return os.getenv("ENV", "dev").lower() in ("prod", "production", "staging")

    def _fatal_error(self, message: str):
        """生产环境致命错误（立即终止）"""
        logger.critical("=" * 70)
        logger.critical("SECURITY FAILURE: Env decryption failed in production")
        logger.critical("=" * 70)
        logger.critical(message)
        logger.critical("=" * 70)
        sys.exit(1)

    @classmethod
    def is_encrypted_value(cls, value: str) -> bool:
        """
        检查值是否为加密格式

        Args:
            value: 要检查的值

        Returns:
            bool: 是否为 ENC[...] 格式

        Example:
            >>> SecureEnvLoader.is_encrypted_value("ENC[gAAAA...]")
            True
        """
        return bool(cls.ENC_PATTERN.match(value))

    @classmethod
    def mask_value_for_display(cls, key: str, value: str) -> str:
        """
        静态方法：安全掩码（用于UI展示）

        Args:
            key: 字段名
            value: 字段值

        Returns:
            str: 脱敏后的值
        """
        instance = cls()
        return instance._mask_for_log(key, value)


# ========== 全局便捷函数 ==========

def load_dotenv_secure(
        dotenv_path: Optional[str] = None,
        override: bool = False
) -> bool:
    """
    安全加载 .env 文件（替代 python-dotenv.load_dotenv）

    Args:
        dotenv_path: .env 文件路径（默认 .env）
        override: 是否覆盖现有环境变量

    Returns:
        bool: 是否成功加载

    Example:
        #>>> from security.env_loader import load_dotenv_secure
        #>>> load_dotenv_secure()
        True
    """
    env_path = Path(dotenv_path) if dotenv_path else Path('.env')
    loader = SecureEnvLoader(env_path)
    loader.load(override=override)
    return True