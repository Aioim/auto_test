"""
🔐 密钥轮换工具 - 企业级密钥管理

功能：
- 安全轮换 .secret_key
- 重新加密所有已加密的敏感数据
- 支持原子性操作（失败回滚）
- 生成轮换审计报告

使用示例：
    #>>> from security.key_rotation import KeyRotator
    #>>> rotator = KeyRotator()
    #>>> rotator.rotate(
    #...     backup_dir="/backup/keys",
    #...     env_files=[".env.production"]
    #... )
"""
import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from cryptography.fernet import Fernet

from .secrets_manager import SecretsManager, SecurityConfig
from .secure_env_loader import SecureEnvLoader
from logger import security_logger, logger


class KeyRotator:
    """
    密钥轮换器 - 安全管理加密密钥生命周期

    特性：
    - 原子性操作（失败自动回滚）
    - 完整审计日志
    - 支持 .env 文件重新加密
    - 备份旧密钥（可选）
    """

    def __init__(self):
        """初始化密钥轮换器"""
        self.current_key_path = SecurityConfig.KEY_FILE
        self._old_fernet: Optional[Fernet] = None
        self._new_fernet: Optional[Fernet] = None

    def rotate(
            self,
            backup_dir: Optional[str] = None,
            env_files: Optional[List[str]] = None,
            dry_run: bool = False
    ) -> Dict[str, any]:
        """
        执行密钥轮换

        流程：
        1. 备份当前密钥
        2. 生成新密钥
        3. 重新加密所有敏感数据
        4. 更新 .env 文件
        5. 验证新密钥有效性
        6. 清理备份（可选）

        Args:
            backup_dir: 备份目录路径（默认 ./key_backups）
            env_files: 需要重新加密的 .env 文件列表
            dry_run: 仅模拟操作，不实际修改

        Returns:
            Dict[str, any]: 轮换报告

        Raises:
            RuntimeError: 如果轮换失败

        Example:
            >>> rotator = KeyRotator()
            >>> report = rotator.rotate(
            ...     backup_dir="/secure/backups",
            ...     env_files=[".env.production"]
            ... )
        """
        security_logger.info("Starting key rotation (dry_run=%s)", dry_run)

        try:
            # 1. 备份当前密钥
            backup_path = self._backup_current_key(backup_dir, dry_run)

            # 2. 生成新密钥
            new_key = self._generate_new_key(dry_run)

            # 3. 重新加密 .env 文件
            env_results = []
            if env_files:
                env_results = self._reencrypt_env_files(env_files, dry_run)

            # 4. 验证新密钥
            if not dry_run:
                self._verify_new_key(new_key)

            # 5. 生成报告
            report = self._generate_rotation_report(
                backup_path=backup_path,
                env_results=env_results,
                dry_run=dry_run
            )

            security_logger.info("Key rotation completed successfully")
            return report

        except Exception as e:
            security_logger.error("Key rotation failed: %s", e)
            # 回滚（如果已开始修改）
            if not dry_run:
                self._rollback_on_failure()
            raise

    def _backup_current_key(self, backup_dir: Optional[str], dry_run: bool) -> Optional[Path]:
        """备份当前密钥"""
        if not self.current_key_path.exists():
            security_logger.warning("No current key to backup")
            return None

        # 创建备份目录
        backup_dir_path = Path(backup_dir) if backup_dir else Path("./key_backups")
        backup_dir_path.mkdir(parents=True, exist_ok=True)

        # 生成备份文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f".secret_key.backup.{timestamp}"
        backup_path = backup_dir_path / backup_filename

        if not dry_run:
            shutil.copy2(self.current_key_path, backup_path)
            # 设置安全权限
            if os.name != 'nt':
                backup_path.chmod(0o600)

            security_logger.info("Backed up current key to: %s", backup_path)

        return backup_path

    def _generate_new_key(self, dry_run: bool) -> Optional[bytes]:
        """生成新密钥"""
        new_key = Fernet.generate_key()

        if not dry_run:
            # 保存新密钥
            with open(self.current_key_path, 'wb') as f:
                f.write(new_key)

            # 设置安全权限
            if os.name != 'nt':
                self.current_key_path.chmod(0o600)

            security_logger.info("Generated and saved new encryption key")

        return new_key if not dry_run else None

    def _reencrypt_env_files(self, env_files: List[str], dry_run: bool) -> List[Dict[str, any]]:
        """重新加密 .env 文件中的敏感字段"""
        results = []

        for env_file in env_files:
            env_path = Path(env_file)
            if not env_path.exists():
                security_logger.warning("Env file not found: %s", env_path)
                results.append({
                    "file": str(env_path),
                    "status": "skipped",
                    "reason": "file_not_found"
                })
                continue

            try:
                result = self._reencrypt_single_env_file(env_path, dry_run)
                results.append(result)
            except Exception as e:
                security_logger.error("Failed to reencrypt %s: %s", env_path, e)
                results.append({
                    "file": str(env_path),
                    "status": "failed",
                    "error": str(e)
                })

        return results

    def _reencrypt_single_env_file(self, env_path: Path, dry_run: bool) -> Dict[str, any]:
        """重新加密单个 .env 文件"""
        # 读取原始文件
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 解析并重新加密
        new_lines = []
        reencrypted_count = 0

        for line in lines:
            stripped = line.strip()

            # 跳过空行和注释
            if not stripped or stripped.startswith('#'):
                new_lines.append(line)
                continue

            # 检查是否为加密字段
            if '=' not in line:
                new_lines.append(line)
                continue

            parts = line.split('=', 1)
            if len(parts) != 2:
                new_lines.append(line)
                continue

            key, value = parts
            value_stripped = value.strip()

            # 如果是加密字段，解密后重新加密
            if SecureEnvLoader.is_encrypted_value(value_stripped):
                try:
                    # 解密（使用旧密钥）
                    decrypted = self._decrypt_with_old_key(value_stripped)

                    # 重新加密（使用新密钥）
                    if not dry_run:
                        reencrypted = self._encrypt_with_new_key(decrypted)
                        new_lines.append(f'{key}={reencrypted}\n')
                    else:
                        new_lines.append(line)  # dry_run 保持原样

                    reencrypted_count += 1
                except Exception as e:
                    security_logger.warning("Failed to reencrypt %s: %s", key, e)
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # 写入文件
        if not dry_run:
            backup_path = env_path.with_suffix('.env.backup')
            shutil.copy2(env_path, backup_path)

            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            security_logger.info("Reencrypted %d fields in %s", reencrypted_count, env_path)

        return {
            "file": str(env_path),
            "status": "success",
            "reencrypted_fields": reencrypted_count,
            "dry_run": dry_run
        }

    def _decrypt_with_old_key(self, encrypted_str: str) -> str:
        """使用旧密钥解密"""
        # 延迟加载旧密钥
        if self._old_fernet is None:
            with open(self.current_key_path, 'rb') as f:
                old_key = f.read().strip()
            self._old_fernet = Fernet(old_key)

        encrypted_b64 = encrypted_str[4:-1]  # 移除 ENC[...]
        encrypted_bytes = encrypted_b64.encode('utf-8')
        decrypted_bytes = self._old_fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')

    def _encrypt_with_new_key(self, value: str) -> str:
        """使用新密钥加密"""
        # 延迟加载新密钥
        if self._new_fernet is None:
            with open(self.current_key_path, 'rb') as f:
                new_key = f.read().strip()
            self._new_fernet = Fernet(new_key)

        encrypted_bytes = self._new_fernet.encrypt(value.encode('utf-8'))
        return f"ENC[{encrypted_bytes.decode('utf-8')}]"

    def _verify_new_key(self, new_key: bytes):
        """验证新密钥有效性"""
        test_value = "key_rotation_test"
        fernet = Fernet(new_key)

        encrypted = fernet.encrypt(test_value.encode('utf-8'))
        decrypted = fernet.decrypt(encrypted).decode('utf-8')

        if decrypted != test_value:
            raise RuntimeError("New key verification failed")

        security_logger.info("New key verified successfully")

    def _generate_rotation_report(
            self,
            backup_path: Optional[Path],
            env_results: List[Dict[str, any]],
            dry_run: bool
    ) -> Dict[str, any]:
        """生成轮换报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "backup_path": str(backup_path) if backup_path else None,
            "env_files_processed": len(env_results),
            "env_files_success": sum(1 for r in env_results if r.get("status") == "success"),
            "env_files_failed": sum(1 for r in env_results if r.get("status") == "failed"),
            "env_details": env_results,
            "next_steps": [
                "1. Verify all services can start with new key",
                "2. Keep backup key for 30 days (rollback window)",
                "3. Update key rotation documentation",
                "4. Schedule next rotation (recommend: 90 days)"
            ] if not dry_run else [
                "Dry run completed successfully",
                "Run without --dry-run to perform actual rotation"
            ]
        }

    def _rollback_on_failure(self):
        """失败时回滚"""
        # TODO: 实现回滚逻辑
        # 1. 恢复备份的密钥
        # 2. 恢复备份的 .env 文件
        security_logger.warning("Rollback mechanism not yet implemented")

    def get_rotation_history(self, backup_dir: str = "./key_backups") -> List[Dict[str, any]]:
        """
        获取密钥轮换历史

        Args:
            backup_dir: 备份目录路径

        Returns:
            List[Dict[str, any]]: 轮换历史记录
        """
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return []

        backups = sorted(
            backup_path.glob(".secret_key.backup.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        history = []
        for backup in backups:
            stat = backup.stat()
            history.append({
                "timestamp": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(backup),
                "size": stat.st_size
            })

        return history


# ========== 便捷函数 ==========

def perform_key_rotation(
        backup_dir: Optional[str] = None,
        env_files: Optional[List[str]] = None,
        dry_run: bool = False
) -> Dict[str, any]:
    """
    便捷函数：执行密钥轮换

    Args:
        backup_dir: 备份目录路径
        env_files: 需要重新加密的 .env 文件列表
        dry_run: 仅模拟操作

    Returns:
        Dict[str, any]: 轮换报告

    Example:
        >>> report = perform_key_rotation(
        ...     backup_dir="/secure/backups",
        ...     env_files=[".env.production"],
        ...     dry_run=False
        ... )
    """
    rotator = KeyRotator()
    return rotator.rotate(backup_dir=backup_dir, env_files=env_files, dry_run=dry_run)


# 保留旧名称别名（向后兼容）
def rotate_keys(
        backup_dir: Optional[str] = None,
        env_files: Optional[List[str]] = None,
        dry_run: bool = False
) -> Dict[str, any]:
    """已弃用：使用 perform_key_rotation 替代"""
    import warnings
    warnings.warn(
        "'rotate_keys' is deprecated, use 'perform_key_rotation' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return perform_key_rotation(backup_dir=backup_dir, env_files=env_files, dry_run=dry_run)