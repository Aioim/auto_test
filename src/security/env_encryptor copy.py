"""
🔐 .env 敏感字段加密工具

提供命令行和编程接口，用于加密/解密 .env 文件中的敏感字段。
"""
import argparse
import sys
import os
import getpass
from pathlib import Path
from typing import Optional

from security.secrets_manager import SecretsManager
from security.secure_env_loader import SecureEnvLoader


def encrypt_value(value: str) -> str:
    sm = SecretsManager()
    if not sm._fernet:
        raise RuntimeError("Fernet not initialized")
    encrypted_bytes = sm._fernet.encrypt(value.encode('utf-8'))
    return f"ENC[{encrypted_bytes.decode('utf-8')}]"


def decrypt_value(encrypted_str: str) -> str:
    if not encrypted_str.startswith("ENC[") or not encrypted_str.endswith("]"):
        raise ValueError("Invalid ENC format: must be ENC[...]")
    encrypted_b64 = encrypted_str[4:-1]
    sm = SecretsManager()
    if not sm._fernet:
        raise RuntimeError("Fernet not initialized")
    encrypted_bytes = encrypted_b64.encode('utf-8')
    decrypted_bytes = sm._fernet.decrypt(encrypted_bytes)
    return decrypted_bytes.decode('utf-8')


def fetch_and_decrypt_env_var(env_var: str) -> str:
    from dotenv import load_dotenv
    load_dotenv()
    encrypted_value = os.getenv(env_var)
    if encrypted_value is None:
        raise ValueError(f"Environment variable '{env_var}' not found")
    if not encrypted_value.strip():
        raise ValueError(f"Environment variable '{env_var}' is empty")
    try:
        return decrypt_value(encrypted_value)
    except ValueError as e:
        raise ValueError(f"Failed to decrypt '{env_var}': {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error decrypting '{env_var}': {str(e)}")


def process_env_file(input_path: str, output_path: Optional[str] = None):
    input_file = Path(input_path)
    output_file = Path(output_path) if output_path else input_file.with_suffix('.env.encrypted')

    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    sensitive_keys = SecureEnvLoader.SECRET_KEY_PATTERNS
    encrypted_count = 0

    with open(input_file, 'r', encoding='utf-8') as f_in:
        lines = f_in.readlines()

    with open(output_file, 'w', encoding='utf-8') as f_out:
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                f_out.write(line)
                continue
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

            should_encrypt = (
                any(k in key_stripped for k in sensitive_keys) and
                not SecureEnvLoader.is_encrypted_value(value_stripped) and
                not value_stripped.startswith('#')
            )

            if should_encrypt:
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


def run_interactive_mode():
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
        if sys.stdin.isatty():
            value = getpass.getpass("> ")
        else:
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
    print("   • Rotate keys quarterly using perform_key_rotation()")


def main():
    parser = argparse.ArgumentParser(
        description="🔐 Secure .env encryption tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python -m security.env_encryptor

  # Encrypt single value
  python -m security.env_encryptor DB_PASSWORD

  # Encrypt entire .env file
  python -m security.env_encryptor --encrypt-file .env

  # Decrypt for verification
  python -m security.env_encryptor --decrypt "ENC[gAAAA...]"
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
            process_env_file(args.encrypt_file, args.output)
        elif args.key:
            print(f"Encrypting value for {args.key}...")
            try:
                if sys.stdin.isatty():
                    value = getpass.getpass("Value: ")
                else:
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
            run_interactive_mode()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()