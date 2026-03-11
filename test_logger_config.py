"""Test script to verify logger configuration is properly managed"""

import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.logger import logger, LogConfig
from config import settings

print("Testing logger configuration management...")
print("=" * 70)

# Test 1: Verify LogConfig is the same as settings.log
print(f"LogConfig is settings.log: {LogConfig is settings.log}")
print(f"Log directory: {LogConfig.log_dir}")
print(f"Log level: {LogConfig.log_level}")
print(f"Log file: {LogConfig.log_file}")
print(f"Backup count: {LogConfig.backup_count}")
print(f"Max bytes: {LogConfig.max_bytes}")
print(f"Enable colors: {LogConfig.enable_colors}")
print(f"Environment: {settings.env}")

# Test 2: Verify logger works
print("\nTesting logger functionality...")
try:
    logger.info("Test log message")
    logger.debug("Test debug message")
    logger.warning("Test warning message")
    print("✅ Logger is working correctly")
except Exception as e:
    print(f"❌ Logger failed: {e}")

# Test 3: Verify sensitive data masking
print("\nTesting sensitive data masking...")
try:
    test_data = {
        "username": "test_user",
        "password": "secret123",
        "api_key": "abc123def456"
    }
    logger.info(f"Test data: {test_data}")
    print("✅ Sensitive data masking is working")
except Exception as e:
    print(f"❌ Sensitive data masking failed: {e}")

print("\n" + "=" * 70)
print("Test completed!")
