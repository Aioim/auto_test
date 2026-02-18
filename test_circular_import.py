"""测试循环导入问题是否已解决"""

# 测试从 utils.security 导入 SecretStr
print("Testing import from utils.security...")
try:
    from utils.security import SecretStr
    print("✓ Successfully imported SecretStr from utils.security")
except Exception as e:
    print(f"✗ Failed to import SecretStr: {e}")

# 测试从 utils.security.secrets_manager 导入 SecretsManager
print("\nTesting import from utils.security.secrets_manager...")
try:
    from utils.security.secrets_manager import SecretsManager, get_secret, set_secret
    print("✓ Successfully imported from utils.security.secrets_manager")
except Exception as e:
    print(f"✗ Failed to import from secrets_manager: {e}")

# 测试创建 SecretStr 实例
print("\nTesting SecretStr instantiation...")
try:
    secret = SecretStr("test_password", "test_secret")
    print(f"✓ Successfully created SecretStr: {secret}")
except Exception as e:
    print(f"✗ Failed to create SecretStr: {e}")

print("\nTest completed!")
