"""
工具模块公共 API

提供统一的工具函数和类的导出，方便用户通过 `from utils import ...` 直接导入。
"""

# 核心工具
from .api_client import APIClient
from .login_cache import login_cache
from .error_monitor import ErrorMonitor, monitor_errors

# 公共模块 - common
from .common import (
    ScreenshotHelper,
    SelectorHelper,
    VisualValidator,
    RealtimeLogMonitor
)

# 公共模块 - data
from .data import (
    load_yaml_file,
    TestDataGenerator,
    DatabaseHelper,
    db_helper,
    get_db_helper,
    execute_sql,
    insert_data,
    update_data,
    delete_data,
    get_session
)

# 公共模块 - logger
from .logger import (
    logger,
    setup_logger,
    log_exception,
    log_security_event,
    log_step,
    log_duration,
    log_performance,
    mask_sensitive_data,
    request_logger,
    perf_logger,
    security_logger,
    api_logger,
    LazyLogger,
    LogConfig,
    LogMetrics,
    diagnose_logger,
    print_logger_diagnosis,
    HandlerFactory,
    verify_api_logging,
    cleanup
)

# 公共模块 - security
from .security import (
    SecretsManager,
    SecretStr,
    SecureEnvLoader,
    KeyRotator,
    get_secret,
    set_secret,
    generate_key_file,
    load_dotenv_secure,
    encrypt_value,
    decrypt_value,
    encrypt_env_file,
    rotate_keys,
    is_encrypted
)

__all__ = [
    # 核心工具
    "APIClient",
    "login_cache",
    "ErrorMonitor",
    "monitor_errors",
    
    # common 模块
    "ScreenshotHelper",
    "SelectorHelper",
    "VisualValidator",
    "RealtimeLogMonitor",
    
    # data 模块
    "load_yaml_file",
    "TestDataGenerator",
    "DatabaseHelper",
    "db_helper",
    "get_db_helper",
    "execute_sql",
    "insert_data",
    "update_data",
    "delete_data",
    "get_session",
    
    # logger 模块
    "logger",
    "setup_logger",
    "log_exception",
    "log_security_event",
    "log_step",
    "log_duration",
    "log_performance",
    "mask_sensitive_data",
    "request_logger",
    "perf_logger",
    "security_logger",
    "api_logger",
    "LazyLogger",
    "LogConfig",
    "LogMetrics",
    "diagnose_logger",
    "print_logger_diagnosis",
    "HandlerFactory",
    "verify_api_logging",
    "cleanup",
    
    # security 模块
    "SecretsManager",
    "SecretStr",
    "SecureEnvLoader",
    "KeyRotator",
    "get_secret",
    "set_secret",
    "generate_key_file",
    "load_dotenv_secure",
    "encrypt_value",
    "decrypt_value",
    "encrypt_env_file",
    "rotate_keys",
    "is_encrypted"
]

