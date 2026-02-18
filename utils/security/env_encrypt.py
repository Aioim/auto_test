"""
🔐 .env 敏感字段加密工具

提供命令行和编程接口，用于加密/解密 .env 文件中的敏感字段。

使用示例：
    # 加密单个值（交互式）
    $ python -m security.env_encrypt DB_PASSWORD

    # 批量加密整个 .env 文件
    $ python -m security.env_encrypt --encrypt-file .env

    # 解密验证
    $ python -m security.env_encrypt --decrypt ENC[gAAAA...]
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

from .secrets import SecretsManager
from .env_loader import SecureEnvLoader


def encrypt_value(value: str) -> str:
    """
    加密单个值并格式化为 ENC[...] 格式

    Args:
        value: 要加密的明文值

    Returns:
        str: ENC[base64_encoded_encrypted_value] 格式

    Example:
        #>>> encrypt_value("mysecretpassword")
        'ENC[gAAAAABkX9J3mZqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7]'
    """
    sm = SecretsManager()
    if not sm._fernet:
        raise RuntimeError("Fernet not initialized")

    encrypted_bytes = sm._fernet.encrypt(value.encode('utf-8'))
    return f"ENC[{encrypted_bytes.decode('utf-8')}]"


def decrypt_value(encrypted_str: str) -> str:
    """
    解密 ENC[...] 格式的值

    Args:
        encrypted_str: ENC[base64_encoded_encrypted_value] 格式

    Returns:
        str: 解密后的明文值

    Raises:
        ValueError: 如果格式无效或解密失败

    Example:
        #>>> decrypt_value("ENC[gAAAAABkX9J3mZqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7XqV7]")
        'mysecretpassword'
    """
    if not encrypted_str.startswith("ENC[") or not encrypted_str.endswith("]"):
        raise ValueError("Invalid ENC format: must be ENC[...]")

    encrypted_b64 = encrypted_str[4:-1]
    sm = SecretsManager()
    if not sm._fernet:
        raise RuntimeError("Fernet not initialized")

    encrypted_bytes = encrypted_b64.encode('utf-8')
    decrypted_bytes = sm._fernet.decrypt(encrypted_bytes)
    return decrypted_bytes.decode('utf-8')


def encrypt_env_file(input_path: str, output_path: Optional[str] = None):
    """
    加密 .env 文件中的敏感字段

    自动识别包含敏感关键词的字段并加密

    Args:
        input_path: 输入 .env 文件路径
        output_path: 输出文件路径（默认为 {input}.encrypted）

    Example:
        #>>> encrypt_env_file(".env.dev", ".env.dev.encrypted")
    """
    input_file = Path(input_path)
    output_file = Path(output_path) if output_path else input_file.with_suffix('.env.encrypted')

    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # 识别敏感字段（基于命名约定）
    sensitive_keys = SecureEnvLoader.SENSITIVE_KEYS
    encrypted_count = 0

    with open(input_file, 'r', encoding='utf-8') as f_in:
        lines = f_in.readlines()

    with open(output_file, 'w', encoding='utf-8') as f_out:
        for line in lines:
            # 跳过空行/注释
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                f_out.write(line)
                continue

            # 解析 key=value
            if '=' not in line:
                f_out.write(line)
                continue

            parts = line.split('=', 1)
            if len(parts) != 2:
                f_out.write(line)
                continue

            key, value = parts
            key_stripped = key.strip().lower()
            value_stripped = value.strip()

            # 检查是否需要加密
            should_encrypt = (
                    any(k in key_stripped for k in sensitive_keys) and
                    not SecureEnvLoader.is_encrypted_value(value_stripped) and
                    not value_stripped.startswith('#')  # 非注释
            )

            if should_encrypt:
                # 移除引号（如果存在）
                clean_value = value_stripped.strip('"').strip("'")
                try:
                    encrypted = encrypt_value(clean_value)
                    f_out.write(f'{key}={encrypted}\n')
                    encrypted_count += 1
                    print(f"  🔒 Encrypted: {key.strip()}")
                except Exception as e:
                    print(f"  ⚠️  Failed to encrypt {key.strip()}: {e}", file=sys.stderr)
                    f_out.write(line)
            else:
                f_out.write(line)

    print(f"\n✅ Encrypted {encrypted_count} fields")
    print(f"   Input:  {input_file.resolve()}")
    print(f"   Output: {output_file.resolve()}")
    print(f"\n⚠️  CRITICAL NEXT STEPS:")
    print(f"   1. Verify output: diff {input_file.name} {output_file.name}")
    print(f"   2. NEVER commit {input_file.name} to Git")
    print(f"   3. Add to .gitignore: echo '{input_file.name}' >> .gitignore")
    print(f"   4. Deploy {output_file.name} as .env to production")


def interactive_encrypt():
    """交互式加密单个值"""
    print("=" * 60)
    print("🔐 .env Sensitive Value Encryptor")
    print("=" * 60)
    print("\nEnter the environment variable name (e.g., DB_PASSWORD):")

    try:
        key = input("> ").strip()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        sys.exit(1)

    if not key:
        print("❌ Empty key", file=sys.stderr)
        sys.exit(1)

    print(f"\nEnter the value for {key}:")
    try:
        value = input("> ").strip()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        sys.exit(1)

    if not value:
        print("❌ Empty value", file=sys.stderr)
        sys.exit(1)

    try:
        encrypted = encrypt_value(value)
    except Exception as e:
        print(f"❌ Encryption failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ ENCRYPTED VALUE")
    print("=" * 60)
    print(f"\n{key}={encrypted}\n")
    print("=" * 60)
    print("\n📋 Copy-paste this line into your .env file")
    print("\n⚠️  SECURITY REMINDERS:")
    print("   • NEVER commit .env with sensitive values to Git")
    print("   • Add .env to .gitignore: echo '.env' >> .gitignore")
    print("   • Rotate keys quarterly using security.rotate_keys()")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="🔐 Secure .env encryption tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python -m security.env_encrypt

  # Encrypt single value
  python -m security.env_encrypt DB_PASSWORD

  # Encrypt entire .env file
  python -m security.env_encrypt --encrypt-file .env

  # Decrypt for verification
  python -m security.env_encrypt --decrypt "ENC[gAAAA...]"
        """
    )
    parser.add_argument('key', nargs='?', help="Environment variable name (interactive mode)")
    parser.add_argument('--encrypt-file', metavar='PATH', help="Encrypt sensitive fields in .env file")
    parser.add_argument('--decrypt', metavar='ENC_VALUE', help="Decrypt an ENC[...] value for verification")
    parser.add_argument('--output', metavar='PATH', help="Output file for --encrypt-file")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    args = parser.parse_args()

    try:
        if args.decrypt:
            decrypted = decrypt_value(args.decrypt)
            print(f"Decrypted value: {decrypted}")
        elif args.encrypt_file:
            encrypt_env_file(args.encrypt_file, args.output)
        elif args.key:
            print(f"Encrypting value for {args.key}...")
            try:
                value = input("Value: ").strip()
            except KeyboardInterrupt:
                print("\n\n❌ Operation cancelled by user")
                sys.exit(1)

            if not value:
                print("❌ Empty value", file=sys.stderr)
                sys.exit(1)

            encrypted = encrypt_value(value)
            print(f"{args.key}={encrypted}")
        else:
            interactive_encrypt()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()