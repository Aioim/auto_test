"""
高级功能组件模块
优化说明：
- 移除 atexit 延迟更新逻辑，改为直接使用 LazyLogger.get()
- 保留 RequestLogger、log_performance 等功能，但内部日志实例动态获取
- 修复 log_security_event 的 JSON 序列化问题
"""
import hashlib
import time
import sys
import traceback
import json
from functools import wraps
from contextlib import contextmanager
from typing import Optional, Dict, Any, Callable, Tuple
from urllib.parse import urlparse, parse_qs
import os
from datetime import datetime, timezone

from config import settings
LogConfig = settings.log
from .masking import mask_sensitive_data
from .helpers import _get_actual_module_name, _get_caller_info
from .lazy import LazyLogger


class RequestLogger:
    """安全增强的HTTP请求日志记录器（精准定位业务代码）"""

    def __init__(self, logger=None):
        # 动态获取日志实例，避免提前绑定
        self.logger = logger or LazyLogger.get("api")

    @staticmethod
    def _get_business_caller() -> Tuple[str, str, int]:
        """
        精准获取业务代码调用位置（跳过框架层）
        优化：使用 inspect.getmodule 判断模块名，避免路径字符串误判
        """
        try:
            import inspect
            from pathlib import Path
            frame = inspect.currentframe()
            depth = 0
            while frame and depth < 10:
                frame = frame.f_back
                depth += 1
                if frame is None:
                    break

                code = frame.f_code
                filename = code.co_filename
                module = inspect.getmodule(frame)

                # 跳过框架模块
                skip_modules = {
                    'logging', 'contextlib', 'secure_logger', 'password_guard',
                    'concurrent.futures', 'threading', 'asyncio'
                }
                if module and (module.__name__.split('.')[0] in skip_modules or
                               any(skip in module.__name__ for skip in skip_modules)):
                    continue

                # 找到业务代码
                return Path(filename).name, code.co_name, frame.f_lineno

            return "unknown.py", "unknown", 0
        except Exception:
            return "unknown.py", "unknown", 0

    def log_request(self, method: str, url: str, **kwargs) -> str:
        filename, func_name, lineno = self._get_business_caller()
        location_prefix = f"[{filename}:{func_name}:{lineno}] "

        request_id = hashlib.sha256(f"{method}{url}{time.time()}".encode()).hexdigest()[:12]

        parsed = self._parse_url(url)
        params_str = self._format_params(parsed.params, max_len=80)

        log_msg = f"{location_prefix}{method.upper()} {parsed.path}"
        if params_str:
            log_msg += f" (params: {params_str})"

        self.logger.info(log_msg)
        return request_id

    def log_response(self, request_id: str, status_code: int, **kwargs):
        filename, func_name, lineno = self._get_business_caller()
        location_prefix = f"[{filename}:{func_name}:{lineno}] "

        method = kwargs.get('method', 'UNKNOWN').upper()
        url = kwargs.get('url', '')
        duration_ms = kwargs.get('duration_ms', 0.0)

        parsed = self._parse_url(url)
        status_marker = "✅" if 200 <= status_code < 300 else "❌"

        log_msg = f"{location_prefix}{status_marker} {method} {parsed.path} {status_code} ({duration_ms:.1f}ms)"
        self.logger.info(log_msg)

    @staticmethod
    def _parse_url(url: str) -> Any:
        parsed_url = urlparse(url)
        params = parse_qs(parsed_url.query) if parsed_url.query else {}
        return type('ParsedURL', (), {
            'path': parsed_url.path or '/',
            'params': params,
            'full': url
        })()

    @staticmethod
    def _format_params(params: Dict, max_len: int = 80) -> str:
        if not params:
            return ""

        parts = []
        for k, v_list in params.items():
            v = v_list[0] if v_list else ""
            if any(s in k.lower() for s in LogConfig.SENSITIVE_KEYS):
                parts.append(f"{k}=******")
            else:
                display = v[:20] + "..." if len(v) > 20 else v
                parts.append(f"{k}={display}")

        result = ", ".join(parts)
        return result[:max_len] + "..." if len(result) > max_len else result


# 全局请求日志记录器实例（惰性获取 logger）
request_logger = RequestLogger()


def log_performance(
    logger=None,
    level=10,
    threshold_ms: float = 50.0,
    enabled: bool = True,
    mark_slow: bool = True
) -> Callable:
    """性能监控装饰器（统一格式）"""
    if not enabled:
        return lambda func: func

    def decorator(func: Callable) -> Callable:
        # 动态获取日志器
        log = logger or LazyLogger.get("performance")
        actual_module = _get_actual_module_name(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            except Exception:
                # 异常仍然抛出，但记录耗时
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                msg = f"{actual_module}.{func.__name__} {duration_ms:.2f}ms"
                if mark_slow and duration_ms >= threshold_ms:
                    msg += f" ⚠️ SLOW"
                try:
                    log.log(level, msg)
                except Exception:
                    # 避免日志记录失败影响业务
                    pass
        return wrapper
    return decorator


def log_exception(logger_param=None, exc: Optional[Exception] = None, context: str = ""):
    log = logger_param or LazyLogger.get("automation")
    try:
        if exc is None:
            _, exc_value, _ = sys.exc_info()
            if exc_value is None:
                return
            exc = exc_value
        tb = traceback.format_exc()
        msg = f"Exception in {context}: {exc}" if context else str(exc)
        log.error("%s\nTraceback:\n%s", msg, tb)
    except Exception as e:
        error_msg = f"⚠️  Error in log_exception: {e}"
        if not LogConfig.quiet:
            print(error_msg, file=sys.stderr)


def log_security_event(
    action: str,
    user: str = "unknown",
    resource: str = "",
    status: str = "success",
    details: Optional[Dict] = None
) -> bool:
    """安全事件记录（混合格式：前缀 + JSON）"""
    log = LazyLogger.get("security")
    try:
        safe_details = {}
        if details:
            for k, v in details.items():
                if any(s in str(k).lower() for s in LogConfig.SENSITIVE_KEYS):
                    safe_details[k] = "******"
                else:
                    safe_details[k] = v

        event = {
            "action": action,
            "user": user,
            "resource": resource,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": os.getenv("CLIENT_IP", "unknown"),
            "env": settings.env,
            "details": safe_details
        }

        # 使用 json.dumps 保证有效 JSON
        log.info(json.dumps(event, ensure_ascii=False, default=str))
        return True
    except Exception as e:
        LazyLogger.get("automation").error("SECURITY_LOG_WRITE_FAILED | action=%s | error=%s", action, e)
        return False


def log_step(step_name: str, logger_param=None):
    log = logger_param or LazyLogger.get("automation")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            log.info("▶️ Step: %s", step_name)
            try:
                result = func(*args, **kwargs)
                log.info("✅ Completed: %s", step_name)
                return result
            except Exception as e:
                log.error("❌ Failed: %s | %s", step_name, e)
                raise
        return wrapper
    return decorator


@contextmanager
def log_duration(step_name: str, logger_param=None, threshold_ms: float = 50.0):
    """执行时间跟踪（统一格式，精准定位）"""
    log = logger_param or LazyLogger.get("performance")

    # 获取调用者信息（跳过 contextlib 内部）
    filename, func_name, lineno = _get_caller_info(skip_frames=2)
    full_name = f"{filename}:{func_name}:{lineno}"

    start = time.perf_counter()
    log.info("START %s [%s]", step_name, full_name)

    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        msg = f"END {step_name} {duration_ms:.2f}ms"
        if duration_ms >= threshold_ms:
            msg += f" ⚠️ SLOW"
        try:
            log.info(msg)
        except Exception:
            pass