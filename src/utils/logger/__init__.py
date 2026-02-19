"""企业级安全日志系统"""

import sys
import atexit
import logging
import threading

# 按照依赖顺序直接导入所有模块
# 1. 首先导入独立模块
from .metrics import LogMetrics
from .utils import _get_caller_info, _get_actual_module_name, clear_caller_info_cache

# 2. 然后导入配置模块
from .config import LogConfig

# 3. 接着导入安全模块
from .security import MaskingEngine, mask_sensitive_data

# 4. 然后导入格式化器模块
from .formatters import SecurityFormatter, ColoredFormatter, JSONFormatter

# 5. 接着导入处理器模块
from .handlers import HandlerFactory

# 6. 然后导入延迟日志模块
from .lazy_logger import LazyLogger

# 7. 接着导入诊断模块
from .diagnostics import diagnose_logger, print_logger_diagnosis, verify_api_logging

# 8. 最后导入组件模块
from .components import RequestLogger, request_logger, log_performance, log_exception, log_security_event, log_step, log_duration

# 模块级别的变量定义
logger = None
api_logger = None
perf_logger = None
security_logger = None

# 初始化标志，防止重复初始化
_initialized = False
_initialized_lock = threading.Lock()

# 定义所有导入的模块和对象
__all__ = [
    "logger", "setup_logger", "log_exception", "log_security_event",
    "log_step", "log_duration", "log_performance", "mask_sensitive_data",
    "request_logger", "perf_logger", "security_logger", "api_logger",
    "LazyLogger", "LogConfig", "LogMetrics", "_get_caller_info",
    "diagnose_logger", "print_logger_diagnosis", "HandlerFactory",
    "verify_api_logging", "cleanup"
]

# 初始化日志实例
def _initialize_loggers():
    """初始化日志实例"""
    global logger, api_logger, perf_logger, security_logger, _initialized, _initialized_lock
    
    with _initialized_lock:
        if _initialized:
            return
        
        try:
            logger = LazyLogger.get("automation")
            api_logger = LazyLogger.get("api", log_level="DEBUG", log_to_console=False, separate_log_file="api.log")
            perf_logger = LazyLogger.get("performance", log_level="DEBUG", log_to_console=False, separate_log_file="performance.log")
            security_logger = LazyLogger.get("security", log_level="INFO", log_to_console=False, separate_log_file="security.log")
            _initialized = True
        except Exception as e:
            # 回退到基本日志记录
            if not LogConfig.QUIET:
                print(f"⚠️  Logger initialization fallback: {e}", file=sys.stderr)
            
            # 配置基本日志
            if not logger:
                logging.basicConfig(level=logging.INFO)
                logger = logging.getLogger("fallback")

# 设置日志器
def setup_logger(
    name: str = "automation",
    log_level: str = None,
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_to_json: bool = False,
    enable_colors: bool = True,
    enable_sensitive_filter: bool = True,
    separate_log_file: str or bool = None
):
    """
    企业级日志配置（统一六大要素格式）

    标准格式:
        2026-02-15 00:30:45 INFO     [demo.py:main:42] Application started

    六大要素:
        1. 时间戳     : 2026-02-15 00:30:45
        2. 日志级别   : INFO
        3. 文件名     : demo.py
        4. 函数名     : main
        5. 行号       : 42
        6. 日志内容   : Application started
    """
    return LazyLogger.get(name, 
                        log_level=log_level,
                        log_to_console=log_to_console,
                        log_to_file=log_to_file,
                        separate_log_file=separate_log_file)

# 全局清理函数
def cleanup():
    """全局清理函数"""
    try:
        # 清理日志实例
        LazyLogger.cleanup()
        
        # 清理处理器
        HandlerFactory.cleanup(force=True)
        
        # 清理缓存
        MaskingEngine.clear_cache()
        SecurityFormatter.clear_cache()
        
        # 清理utils缓存
        clear_caller_info_cache()
        
        # 重置指标
        LogMetrics.reset()
    except Exception as e:
        if not LogConfig.QUIET:
            print(f"⚠️  Cleanup error: {e}", file=sys.stderr)

# 注册全局清理函数
atexit.register(cleanup)

# 立即初始化日志实例
_initialize_loggers()