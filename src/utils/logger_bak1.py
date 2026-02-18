"""
企业级日志配置模块

特性：
- 彩色控制台输出
- 多文件日志（常规、错误、性能、安全）
- 日志轮转（按时间+大小）
- 结构化 JSON 日志
- 敏感信息脱敏
- 与 Playwright 集成（捕获浏览器控制台日志）
- 与 Allure 集成（自动附加日志）
- 性能监控（函数执行时间）
- 请求/响应日志
"""
import logging
import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Union
from functools import wraps
import traceback
import hashlib

from config import settings
settings=settings.log
# ==================== 敏感信息脱敏配置 ====================

SENSITIVE_PATTERNS = [
    # 密码字段
    (r'(?i)("password"\s*:\s*")[^"]+(")', r'\1******\2'),
    (r'(?i)(password=)[^&\s]+', r'\1******'),
    (r'(?i)(pwd=)[^&\s]+', r'\1******'),

    # Token/API Key
    (r'(?i)("token"\s*:\s*")[^"]+(")', r'\1******\2'),
    (r'(?i)("api[_-]?key"\s*:\s*")[^"]+(")', r'\1******\2'),
    (r'(?i)(token=)[^&\s]+', r'\1******'),

    # 邮箱（保留域名）
    (r'(?i)([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'***@\2'),

    # 手机号（保留后4位）
    (r'(?i)(1[3-9]\d)(\d{4})(\d{4})', r'\1****\3'),

    # 身份证（保留前3后4）
    (r'(?i)(\d{3})\d{11}(\d{4})', r'\1***********\2'),

    # 银行卡（保留前6后4）
    (r'(?i)(\d{6})\d{10}(\d{4})', r'\1******\2'),
]


def mask_sensitive_data(message: str) -> str:
    """
    脱敏敏感信息

    Args:
        message: 原始消息

    Returns:
        str: 脱敏后的消息
    """
    if not isinstance(message, str):
        return message

    masked = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = re.sub(pattern, replacement, masked)

    return masked


# ==================== 彩色格式化器 ====================

class ColorCodes:
    """ANSI 颜色代码"""
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"

    # 前景色
    BLACK = "\x1b[30m"
    RED = "\x1b[31m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    BLUE = "\x1b[34m"
    MAGENTA = "\x1b[35m"
    CYAN = "\x1b[36m"
    WHITE = "\x1b[37m"

    # 背景色
    BG_RED = "\x1b[41m"
    BG_GREEN = "\x1b[42m"
    BG_YELLOW = "\x1b[43m"
    BG_BLUE = "\x1b[44m"
    BG_MAGENTA = "\x1b[45m"
    BG_CYAN = "\x1b[46m"
    BG_WHITE = "\x1b[47m"


class ColoredFormatter(logging.Formatter):
    """彩色日志格式器"""

    LEVEL_COLORS = {
        logging.DEBUG: ColorCodes.CYAN,
        logging.INFO: ColorCodes.GREEN,
        logging.WARNING: ColorCodes.YELLOW,
        logging.ERROR: ColorCodes.RED,
        logging.CRITICAL: ColorCodes.BOLD + ColorCodes.BG_RED + ColorCodes.WHITE,
    }

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt or "%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt or "%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        # 保存原始级别名称
        orig_levelname = record.levelname
        color = self.LEVEL_COLORS.get(record.levelno, "")

        # 应用颜色
        if color:
            record.levelname = f"{color}{record.levelname}{ColorCodes.RESET}"

        # 格式化消息
        output = super().format(record)

        # 恢复原始级别名称（避免影响其他处理器）
        record.levelname = orig_levelname

        return output


# ==================== JSON 格式化器 ====================

class JSONFormatter(logging.Formatter):
    """JSON 格式日志"""

    def __init__(self, fields: Optional[List[str]] = None):
        super().__init__()
        self.fields = fields or [
            "timestamp", "level", "logger", "message", "module", "function",
            "line", "thread", "process", "extra"
        ]

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {}

        # 基础字段
        if "timestamp" in self.fields:
            log_data["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
        if "level" in self.fields:
            log_data["level"] = record.levelname
        if "logger" in self.fields:
            log_data["logger"] = record.name
        if "message" in self.fields:
            log_data["message"] = mask_sensitive_data(record.getMessage())
        if "module" in self.fields:
            log_data["module"] = record.module
        if "function" in self.fields:
            log_data["function"] = record.funcName
        if "line" in self.fields:
            log_data["line"] = record.lineno
        if "thread" in self.fields:
            log_data["thread"] = record.thread
        if "process" in self.fields:
            log_data["process"] = record.process

        # 额外字段
        if hasattr(record, "extra") and "extra" in self.fields:
            log_data["extra"] = record.extra

        # 异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 堆栈信息
        if record.stack_info:
            log_data["stack"] = self.formatStack(record.stack_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


# ==================== 敏感信息过滤器 ====================

class SensitiveDataFilter(logging.Filter):
    """敏感信息过滤器"""

    def filter(self, record: logging.LogRecord) -> bool:
        # 脱敏消息
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)

        # 脱敏参数
        if isinstance(record.args, dict):
            record.args = {k: mask_sensitive_data(v) if isinstance(v, str) else v
                           for k, v in record.args.items()}
        elif isinstance(record.args, (list, tuple)):
            record.args = tuple(mask_sensitive_data(arg) if isinstance(arg, str) else arg
                                for arg in record.args)

        return True


# ==================== 性能日志装饰器 ====================

def log_performance(
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
        threshold_ms: float = 100.0
) -> Callable:
    """
    性能日志装饰器

    Args:
        logger: 日志记录器
        level: 日志级别
        threshold_ms: 仅当日志超过此阈值（毫秒）时记录

    Usage:
        @log_performance()
        def my_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                if duration >= threshold_ms:
                    logger.log(
                        level,
                        f"PERF: {func.__module__}.{func.__name__} took {duration:.2f}ms"
                    )

        return wrapper

    return decorator


# ==================== 请求/响应日志 ====================

class RequestLogger:
    """HTTP 请求/响应日志记录器"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_request(
            self,
            method: str,
            url: str,
            headers: Optional[Dict] = None,
            body: Optional[Any] = None,
            params: Optional[Dict] = None,
            **kwargs
    ) -> str:
        """
        记录请求

        Returns:
            str: 请求ID（用于关联响应）
        """
        request_id = hashlib.md5(f"{method}{url}{datetime.now().timestamp()}".encode()).hexdigest()[:8]

        log_data = {
            "request_id": request_id,
            "method": method.upper(),
            "url": url,
            "params": params or {},
            "headers": self._sanitize_headers(headers or {}),
            "body_preview": self._preview_body(body),
            "timestamp": datetime.now().isoformat()
        }

        self.logger.debug("HTTP Request: %s", json.dumps(log_data, ensure_ascii=False))
        return request_id

    def log_response(
            self,
            request_id: str,
            status_code: int,
            url: str,
            headers: Optional[Dict] = None,
            body: Optional[Any] = None,
            duration_ms: float = 0.0,
            **kwargs
    ) -> None:
        """记录响应"""
        log_data = {
            "request_id": request_id,
            "status_code": status_code,
            "url": url,
            "headers": self._sanitize_headers(headers or {}),
            "body_preview": self._preview_body(body),
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now().isoformat()
        }

        level = logging.INFO if 200 <= status_code < 400 else logging.WARNING
        self.logger.log(level, "HTTP Response: %s", json.dumps(log_data, ensure_ascii=False))

    def _sanitize_headers(self, headers: Dict) -> Dict:
        """脱敏敏感头信息"""
        sensitive_keys = ["authorization", "cookie", "x-api-key", "token"]
        return {
            k: "******" if any(sk in k.lower() for sk in sensitive_keys) else v
            for k, v in headers.items()
        }

    def _preview_body(self, body: Any) -> str:
        """生成请求体预览（截断+脱敏）"""
        if body is None:
            return ""

        try:
            if isinstance(body, (dict, list)):
                preview = json.dumps(body, ensure_ascii=False)
            else:
                preview = str(body)

            preview = mask_sensitive_data(preview)
            return preview[:500] + "..." if len(preview) > 500 else preview
        except Exception:
            return "<non-serializable>"


# ==================== Playwright 日志集成 ====================

class PlaywrightLogHandler(logging.Handler):
    """Playwright 控制台日志处理器"""

    def __init__(self, logger: logging.Logger):
        super().__init__()
        self.target_logger = logger

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.target_logger.debug(f"[Browser Console] {msg}")
        except Exception:
            self.handleError(record)


def setup_playwright_logging(page, logger: logging.Logger) -> None:
    """
    设置 Playwright 页面日志捕获

    Args:
        page: Playwright Page 对象
        logger: 目标日志记录器
    """

    def console_handler(msg):
        level = msg.type
        text = msg.text

        # 根据消息类型选择日志级别
        if level == "error":
            logger.error(f"[Browser Error] {text}")
        elif level == "warning":
            logger.warning(f"[Browser Warning] {text}")
        elif level == "info":
            logger.info(f"[Browser Info] {text}")
        else:
            logger.debug(f"[Browser {level}] {text}")

    # 监听控制台消息
    page.on("console", console_handler)

    # 监听页面错误
    def page_error_handler(error):
        logger.error(f"[Page Error] {error}")

    page.on("pageerror", page_error_handler)


# ==================== Allure 集成 ====================

def attach_logs_to_allure(logger_name: str = "automation") -> None:
    """
    将日志附加到 Allure 报告

    Args:
        logger_name: 日志记录器名称
    """
    try:
        import allure

        log_dir = Path(settings.log_dir)
        log_files = [
            log_dir / "test_run.log",
            log_dir / f"error_{datetime.now().strftime('%Y%m%d')}.log"
        ]

        for log_file in log_files:
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        allure.attach(
                            content,
                            name=f"{log_file.stem}_logs",
                            attachment_type=allure.attachment_type.TEXT
                        )
    except ImportError:
        pass  # Allure 未安装
    except Exception as e:
        logging.getLogger(logger_name).warning(f"Failed to attach logs to Allure: {e}")


# ==================== 主日志配置函数 ====================

def setup_logger(
        name: str = "automation",
        log_level: Optional[str] = None,
        log_to_console: bool = True,
        log_to_file: bool = True,
        log_to_json: bool = False,
        enable_colors: bool = True,
        enable_sensitive_filter: bool = True
) -> logging.Logger:
    """
    设置日志记录器（企业级配置）

    Args:
        name: 日志记录器名称
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_to_console: 是否输出到控制台
        log_to_file: 是否输出到文件
        log_to_json: 是否输出 JSON 格式日志
        enable_colors: 是否启用彩色输出
        enable_sensitive_filter: 是否启用敏感信息过滤

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 获取或创建日志记录器
    logger = logging.getLogger(name)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 设置日志级别
    log_level = (log_level or settings.log_level or "INFO").upper()
    logger.setLevel(getattr(logging, log_level))
    logger.propagate = False  # 避免传播到根记录器

    # 确保日志目录存在
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 敏感信息过滤器
    if enable_sensitive_filter:
        sensitive_filter = SensitiveDataFilter()
        logger.addFilter(sensitive_filter)

    # ========== 控制台处理器 ==========
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        if enable_colors and sys.stdout.isatty():
            console_formatter = ColoredFormatter(
                fmt="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
                datefmt="%H:%M:%S"
            )
        else:
            console_formatter = logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # ========== 常规文件处理器（按时间+大小轮转） ==========
    if log_to_file:
        from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

        # 主日志文件 - 按天轮转，保留7天
        main_handler = TimedRotatingFileHandler(
            filename=log_dir /settings.log_file,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s:%(module)s:%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(main_handler)

        # 错误日志文件 - 仅记录 ERROR 及以上，按大小轮转
        error_log_file = log_dir / f"error_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = RotatingFileHandler(
            filename=error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s:%(module)s:%(funcName)s:%(lineno)d] %(message)s\n%(exc_info)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(error_handler)

        # 性能日志文件
        perf_log_file = log_dir / "performance.log"
        perf_handler = RotatingFileHandler(
            filename=perf_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8"
        )
        perf_handler.setLevel(logging.DEBUG)
        perf_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(perf_handler)

        # 安全日志文件（审计日志）
        security_log_file = log_dir / "security.log"
        security_handler = RotatingFileHandler(
            filename=security_log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        security_handler.setLevel(logging.INFO)
        security_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(security_handler)

    # ========== JSON 格式日志 ==========
    if log_to_json:
        json_log_file = log_dir / f"structured_{datetime.now().strftime('%Y%m%d')}.log"
        json_handler = logging.FileHandler(json_log_file, encoding="utf-8")
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)

    # ========== 初始化消息 ==========
    logger.info("=" * 60)
    logger.info(f"Logger initialized: {name}")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Log directory: {log_dir}")
    logger.info(f"Environment: {os.getenv('ENV', 'unknown')}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    return logger


# ==================== 全局日志记录器 ====================

# 创建全局日志记录器实例
logger = setup_logger("automation")

# 创建专用日志记录器
perf_logger = setup_logger("performance", log_level="DEBUG", log_to_console=False)
security_logger = setup_logger("security", log_level="INFO", log_to_console=False)
api_logger = setup_logger("api", log_level="DEBUG", log_to_console=False)

# 创建请求日志记录器
request_logger = RequestLogger(api_logger)


# ==================== 便捷函数 ====================

def log_exception(logger: logging.Logger = logger, exc: Optional[Exception] = None, context: str = "") -> None:
    """
    记录异常信息

    Args:
        logger: 日志记录器
        exc: 异常对象（如果为 None，使用 sys.exc_info()）
        context: 上下文描述
    """
    if exc is None:
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_value is None:
            return
        exc = exc_value

    tb = traceback.format_exc()
    logger.error(
        "Exception occurred%s:\n%s\nTraceback:\n%s",
        f" ({context})" if context else "",
        str(exc),
        tb
    )


def log_security_event(
        action: str,
        user: str = "unknown",
        resource: str = "",
        status: str = "success",
        details: Optional[Dict] = None
) -> None:
    """
    记录安全事件（审计日志）

    Args:
        action: 操作类型（login, logout, delete, etc.）
        user: 用户标识
        resource: 涉及的资源
        status: 操作状态（success, failed, denied）
        details: 额外详情
    """
    event = {
        "action": action,
        "user": user,
        "resource": resource,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "ip": os.getenv("CLIENT_IP", "unknown"),
        "details": details or {}
    }

    security_logger.info(json.dumps(event, ensure_ascii=False))


def log_step(step_name: str, logger: logging.Logger = logger) -> Callable:
    """
    步骤日志装饰器

    Usage:
        @log_step("用户登录")
        def login():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"▶️ Step: {step_name}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"✅ Step completed: {step_name}")
                return result
            except Exception as e:
                logger.error(f"❌ Step failed: {step_name} - {e}")
                raise

        return wrapper

    return decorator


# ==================== 上下文管理器 ====================

from contextlib import contextmanager


@contextmanager
def log_duration(step_name: str, logger: logging.Logger = logger):
    """
    记录代码块执行时间的上下文管理器

    Usage:
        with log_duration("数据处理"):
            # 执行耗时操作
            time.sleep(1)
    """
    start_time = datetime.now()
    logger.debug(f"⏱️ Starting: {step_name}")

    try:
        yield
    finally:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.debug(f"✅ Completed: {step_name} ({duration:.2f}ms)")


# ==================== 导出公共 API ====================

__all__ = [
    "logger",  # 全局日志记录器
    "setup_logger",  # 日志配置函数
    "log_exception",  # 异常记录
    "log_security_event",  # 安全事件记录
    "log_step",  # 步骤装饰器
    "log_duration",  # 时长上下文管理器
    "log_performance",  # 性能装饰器
    "mask_sensitive_data",  # 敏感信息脱敏
    "setup_playwright_logging",  # Playwright 日志集成
    "attach_logs_to_allure",  # Allure 集成
    "RequestLogger",  # HTTP 请求日志
    "request_logger",  # 全局请求日志记录器
    "perf_logger",  # 性能日志记录器
    "security_logger",  # 安全日志记录器
    "api_logger",  # API 日志记录器
]