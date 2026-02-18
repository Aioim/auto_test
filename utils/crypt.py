import os
import re
import base64
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import dotenv_values, set_key
from config import settings


class EnvCrypt:
    """EnvCrypt: 安全的 .env 文件敏感字段加密/解密工具"""

    # 默认敏感字段关键词（不区分大小写，支持部分匹配）
    DEFAULT_SENSITIVE_KEYS = [
        'password', 'passwd', 'pwd',
        'api_key', 'apikey', 'token', 'secret',
        'private_key', 'privatekey',
        'access_key', 'accesskey',
        'client_secret', 'clientsecret',
        'encryption_key', 'encryptionkey',
        'db_url', 'database_url'
    ]
    ENCRYPTION_PREFIX = 'enc://'
    PBKDF2_ITERATIONS = 480_000  # 符合2026年安全标准

    def __init__(
            self,
            key: Optional[bytes] = None,
            key_file: Optional[str] = None,
            password: Optional[str] = None,
            salt: Optional[bytes] = None,
            sensitive_keys: Optional[List[str]] = None
    ):
        """
        初始化加密器（三选一提供密钥源）

        :param key: Fernet 密钥 (32字节 base64 编码)
        :param key_file: 密钥文件路径
        :param password: 用于派生密钥的密码（必须配合 salt 使用）
        :param salt: 密钥派生所需的 salt（至少16字节），禁止使用固定 salt
        :param sensitive_keys: 敏感字段关键词列表（默认使用 DEFAULT_SENSITIVE_KEYS）
        :raises ValueError: 参数组合无效或缺少必要参数
        """
        if sum([key is not None, key_file is not None, password is not None]) != 1:
            raise ValueError("必须且只能提供 key、key_file 或 password 之一")

        if password and salt is None:
            raise ValueError(
                "使用 password 派生密钥时必须提供 cryptographically secure 的 salt。"
                "请使用 EnvCrypt.generate_salt() 生成随机 salt 并安全存储。"
            )
        if password and (salt is not None and len(salt) < 16):
            raise ValueError("salt 长度必须至少为 16 字节以保证安全性")

        self.sensitive_keys = [k.lower() for k in (sensitive_keys or self.DEFAULT_SENSITIVE_KEYS)]
        self.fernet = self._init_fernet(key, key_file, password, salt)

    def _init_fernet(
            self,
            key: Optional[bytes],
            key_file: Optional[str],
            password: Optional[str],
            salt: Optional[bytes]
    ) -> Fernet:
        """初始化 Fernet 加密器"""
        if key:
            return Fernet(key)
        elif key_file:
            key_path = Path(key_file)
            if not key_path.exists():
                raise FileNotFoundError(f"密钥文件不存在: {key_path}")
            raw_key = self.load_key(key_path)
            if len(raw_key) != 44:  # Fernet key is 32 bytes -> base64 encoded is 44 chars
                raise ValueError(f"无效的 Fernet 密钥文件格式: {key_file}")
            return Fernet(raw_key)
        elif password:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=self.PBKDF2_ITERATIONS,
            )
            derived_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            return Fernet(derived_key)
        else:
            raise ValueError("无法初始化 Fernet 加密器")  # 理论上不会触发

    @staticmethod
    def generate_key() -> bytes:
        """生成新的 Fernet 密钥"""
        return Fernet.generate_key()

    @staticmethod
    def load_key(key_path):
        with open(key_path, 'rb') as f:
            raw_key = f.read().strip()
        return raw_key

    @staticmethod
    def save_key(key: bytes, path: str):
        """安全保存密钥到文件（权限 600）"""
        key_path = Path(path)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        with open(key_path, 'wb') as f:
            f.write(key)
        key_path.chmod(0o600)

    def _is_sensitive(self, key: str) -> bool:
        """判断字段是否为敏感字段（大小写不敏感）"""
        key_lower = key.lower().strip()
        return any(s in key_lower for s in self.sensitive_keys)

    def _is_encrypted_value(self, value: str) -> bool:
        """判断值是否已加密（以 enc:// 开头）"""
        return value.strip().startswith(self.ENCRYPTION_PREFIX)

    def encrypt_value(self, plaintext: str) -> str:
        """加密单个值，返回 enc://<ciphertext> 格式"""
        if not plaintext:
            return plaintext  # 空值不加密
        ciphertext = self.fernet.encrypt(plaintext.encode())
        return f"{self.ENCRYPTION_PREFIX}{ciphertext.decode()}"

    def decrypt_value(self, encrypted_value: str) -> str:
        """解密 enc://<ciphertext> 格式的值"""
        if not self._is_encrypted_value(encrypted_value):
            raise ValueError(
                f"值未加密或格式错误（应以 '{self.ENCRYPTION_PREFIX}' 开头）: {encrypted_value[:30]}..."
            )
        ciphertext = encrypted_value[len(self.ENCRYPTION_PREFIX):]
        try:
            return self.fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise ValueError(
                "解密失败：无效的密钥、损坏的密文或使用了错误的 salt。"
                "请确认密钥/salt 与加密时完全一致。"
            )

    def _parse_line(self, line: str) -> Tuple[Optional[str], Optional[str], bool]:
        """
        安全解析 .env 行

        :return: (key, value, is_key_value_pair)
        """
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            return None, None, False

        # 匹配 KEY=VALUE 格式（允许值包含等号）
        match = re.match(r'^\s*([^#=\s]+)\s*=\s*(.*)$', line)
        if not match:
            return None, None, False

        key = match.group(1).strip()
        value = match.group(2).rstrip()  # 保留值内部空格，仅去除尾部换行

        # 移除值两端的引号（dotenv 标准行为）
        if len(value) >= 2 and (
                (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
        ):
            value = value[1:-1]

        return key, value, True

    def process_env_file(
            self,
            env_path: str,
            output_path: Optional[str] = None,
            mode: str = 'encrypt',
            dry_run: bool = False,
            backup: bool = True
    ) -> Dict:
        """
        处理 .env 文件（保留注释/空行/格式）

        :param env_path: 输入 .env 文件路径
        :param output_path: 输出路径（默认覆盖原文件）
        :param mode: 'encrypt' 或 'decrypt'
        :param dry_run: 仅预览不修改文件
        :param backup: 处理前自动备份（.env.backup）
        :return: 处理统计信息
        """
        if mode not in ('encrypt', 'decrypt'):
            raise ValueError("mode 必须是 'encrypt' 或 'decrypt'")

        env_path = Path(env_path)
        if not env_path.exists():
            raise FileNotFoundError(f".env 文件不存在: {env_path}")

        # 读取原始内容（保留原始换行符）
        with open(env_path, 'r', encoding='utf-8') as f:
            original_lines = f.read().splitlines(keepends=False)

        processed_lines = []
        stats = {
            'total_lines': len(original_lines),
            'processed': 0,
            'skipped': 0,
            'encrypted': 0,
            'decrypted': 0,
            'errors': [],
            'dry_run': dry_run,
            'mode': mode
        }

        for line_num, raw_line in enumerate(original_lines, 1):
            key, value, is_kv = self._parse_line(raw_line)

            if not is_kv:
                processed_lines.append(raw_line)
                stats['skipped'] += 1
                continue

            is_sensitive = self._is_sensitive(key)
            is_encrypted = self._is_encrypted_value(value)
            should_process = (
                    (mode == 'encrypt' and is_sensitive and not is_encrypted) or
                    (mode == 'decrypt' and is_encrypted)
            )

            if should_process:
                try:
                    if mode == 'encrypt':
                        new_value = self.encrypt_value(value)
                        stats['encrypted'] += 1
                    else:  # decrypt
                        new_value = self.decrypt_value(value)
                        stats['decrypted'] += 1

                    # 保留原始缩进（从原行提取）
                    indent = re.match(r'^\s*', raw_line).group(0)
                    processed_lines.append(f"{indent}{key}={new_value}")
                    stats['processed'] += 1
                except Exception as e:
                    stats['errors'].append(f"L{line_num} ({key}): {str(e)}")
                    processed_lines.append(raw_line)  # 保留原始行避免数据丢失
            else:
                processed_lines.append(raw_line)
                stats['skipped'] += 1

        # 写入结果
        output_path = Path(output_path) if output_path else env_path

        if not dry_run:
            if backup and output_path.exists():
                backup_path = output_path.with_suffix(output_path.suffix + '.backup')
                shutil.copy2(output_path, backup_path)
                stats['backup_path'] = str(backup_path)

            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                f.write('\n'.join(processed_lines) + '\n')

        return stats

    def get_sensitive_fields(self, env_path: str) -> List[str]:
        """扫描 .env 文件，返回所有敏感字段名"""
        env_path = Path(env_path)
        if not env_path.exists():
            raise FileNotFoundError(f".env 文件不存在: {env_path}")

        env_vars = dotenv_values(str(env_path))
        return [k for k in env_vars.keys() if self._is_sensitive(k)]

    def verify_key(self, test_value: str = "test") -> bool:
        """验证密钥有效性（加密-解密 roundtrip 测试）"""
        try:
            encrypted = self.encrypt_value(test_value)
            decrypted = self.decrypt_value(encrypted)
            return decrypted == test_value
        except Exception:
            return False


class SecureStorage:
    """安全存储 salt 和密钥的辅助类"""

    def __init__(self, base_dir: Path = None):
        if base_dir:
            self.base_dir = base_dir
        else:
            self.base_dir = settings.project_root
        # self.base_dir = Path(base_dir) if base_dir else Path.home() / ".envcrypt"
        # self.base_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    @staticmethod
    def generate_salt(length: int = 32) -> bytes:
        """生成 cryptographically secure 的随机 salt"""
        return os.urandom(length)

    def save_salt(self, salt: bytes, name: str = "main") -> Path:
        path = self.base_dir / f"{name}.salt.bin"
        with open(path, 'wb') as f:
            f.write(salt)
        path.chmod(0o600)
        return path

    def load_salt(self, name: str = "main") -> bytes:
        path = self.base_dir / f"{name}.salt.bin"
        if not path.exists():
            raise FileNotFoundError(f"Salt 文件不存在: {path}")
        return path.read_bytes()


if __name__ == '__main__':
    # 生成 salt 和密钥
    # key = EnvCrypt.generate_key()  # Fernet 密钥
    # # 创建安全目录
    # # envcrypt_dir = Path.home() / ".envcrypt"  # 或项目内 .envcrypt/
    # # envcrypt_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    from config import PROJECT_ROOT
    # # 保存密钥（同样 600 权限）
    key_path = PROJECT_ROOT/ ".key"
    # EnvCrypt.save_key(key, key_path)
    #
    # print(f"✓ 密钥保存至: {key_path}")

    # 加密.env文件
    # 2. 初始化加密器（三选一）
    # crypt = EnvCrypt(key=key)  # 推荐：直接使用密钥
    crypt = EnvCrypt(key_file=key_path)
    # 或 crypt = EnvCrypt(password="my_pass", salt=salt)  # 必须提供 salt

    # 3. 验证密钥有效性
    assert crypt.verify_key()

    # 4. 处理 .env 文件
    # stats = crypt.process_env_file(settings.project_root/".env", mode="encrypt", backup=True)
    # print(f"加密完成: {stats['encrypted']} 个字段")
    from dotenv import load_dotenv

    load_dotenv()
    ADMIN_PASSWORD = crypt.decrypt_value(os.getenv('ADMIN_PASSWORD'))
    print(ADMIN_PASSWORD)

    # === 阶段 1: 初始化（仅一次）===
    # salt = EnvCrypt.generate_salt(length=32)  # 生成 32 字节 cryptographically secure 随机数
    # password = "MyStrongPassword2026!"  # 用户记忆的密码
    #
    # # 保存 salt 到安全位置（必须！）
    # with open(settings.project_root/"/salt.bin", "wb") as f:
    #     f.write(salt)
    # os.chmod(settings.project_root/"/salt.bin", 0o600)
    #
    # # === 阶段 2: 加密 .env ===
    # crypt = EnvCrypt(password=password, salt=salt)  # 相同 password+salt → 相同密钥
    # crypt.process_env_file(settings.project_root/".env", mode="encrypt")
    #
    # === 阶段 3: 解密 .env（未来任意时间）===
    # # 从安全位置读取 salt
    # with open(settings.project_root/"/salt.bin", "rb") as f:
    #     salt = f.read()
    #
    # # 用相同 password+salt 重建密钥
    # crypt = EnvCrypt(password=password, salt=salt)
    # crypt.process_env_file(settings.project_root/".env", mode="decrypt")  # ✅ 成功解密
    """
    storage = SecureStorage()
    # 1. 生成 salt 并保存
    salt = storage.generate_salt()
    storage.save_salt(salt, settings.env)  # 命名区分环境

    # 2. 用密码派生密钥并加密 .env
    password = "your-strong-password"  # 从安全渠道获取
    crypt = EnvCrypt(password=password, salt=salt)
    crypt.process_env_file(".env", mode="encrypt", backup=True)

    # ===== 后续解密流程 =====
    salt = storage.load_salt("prod")
    crypt = EnvCrypt(password=password, salt=salt)
    crypt.process_env_file(".env", mode="decrypt")
    """
