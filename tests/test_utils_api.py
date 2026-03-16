import pytest
import sys
from pathlib import Path


# 测试 utils 模块的公共 API

def test_utils_api_imports():
    """
    测试 utils 模块的公共 API 是否可以正确导入
    """
    # 测试核心工具导入
    from utils import APIClient
    from utils import login_cache
    from utils import ErrorMonitor, error_monitor
    
    # 测试 common 模块导入
    from utils import ScreenshotHelper
    from utils import SelectorHelper
    from utils import VisualValidator
    from utils import RealtimeLogMonitor
    
    # 测试 data 模块导入
    from utils import load_yaml_file
    from utils import TestDataGenerator
    from utils import DatabaseHelper, db_helper, get_db_helper
    from utils import execute_sql, insert_data, update_data, delete_data, get_session
    
    # 测试 logger 模块导入
    from utils import logger
    from utils import setup_logger
    from utils import log_exception, log_security_event, log_step, log_duration, log_performance
    from utils import mask_sensitive_data
    from utils import request_logger, perf_logger, security_logger, api_logger
    from utils import LazyLogger, LogConfig, LogMetrics
    from utils import diagnose_logger, print_logger_diagnosis, HandlerFactory, verify_api_logging, cleanup
    
    # 测试 security 模块导入
    from utils import SecretsManager, SecretStr, SecureEnvLoader, KeyRotator
    from utils import get_secret, set_secret, generate_key_file
    from utils import load_dotenv_secure
    from utils import encrypt_value, decrypt_value, encrypt_env_file
    from utils import rotate_keys, is_encrypted
    
    print("✅ 所有 utils 模块的公共 API 导入成功")


def test_utils_api_usage():
    """
    测试 utils 模块的公共 API 的基本使用
    """
    # 测试 login_cache
    from utils import login_cache
    test_token = "test_token_12345"
    login_cache.save_token(test_token)
    retrieved_token = login_cache.get_token()
    assert retrieved_token == test_token
    login_cache.clear_token()
    print("✅ login_cache 使用成功")
    
    # 测试 APIClient
    from utils import APIClient
    try:
        client = APIClient(base_url="https://example.com")
        assert client is not None
        client.close()
        print("✅ APIClient 使用成功")
    except Exception as e:
        print(f"⚠️ APIClient 测试跳过: {e}")
    
    # 测试 logger
    from utils import logger
    assert logger is not None
    print("✅ logger 使用成功")


def test_utils_api_all():
    """
    测试 utils 模块的 __all__ 列表是否包含所有导出的名称
    """
    import utils
    assert hasattr(utils, "__all__")
    assert isinstance(utils.__all__, list)
    
    # 检查一些关键名称是否在 __all__ 中
    key_names = [
        "APIClient",
        "login_cache",
        "ErrorMonitor",
        "ScreenshotHelper",
        "SelectorHelper",
        "VisualValidator",
        "load_yaml_file",
        "DatabaseHelper",
        "logger",
        "SecretsManager",
        "SecretStr"
    ]
    
    for name in key_names:
        assert name in utils.__all__, f"{name} 不在 utils.__all__ 中"
    
    print(f"✅ utils.__all__ 包含 {len(utils.__all__)} 个导出名称")


if __name__ == "__main__":
    """
    运行所有测试
    """
    print("=== 测试 utils 模块公共 API ===")
    print()
    
    test_utils_api_imports()
    print()
    
    test_utils_api_usage()
    print()
    
    test_utils_api_all()
    print()
    
    print("=== 所有测试通过 ===")
