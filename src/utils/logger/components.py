"""高级功能组件模块"""

import hashlib
import time
import sys
import traceback
from functools import wraps, lru_cache
from contextlib import contextmanager
from typing import Optional, Dict, Any, Callable, Tuple
from urllib.parse import urlparse, parse_qs
import os
from datetime import datetime, timezone

# 直接导入依赖模块
from .config import LogConfig
from .security import mask_sensitive_data
from .utils import _get_actual_module_name, _get_caller_info

# 导入日志实例 - 延迟导入以避免循环依赖
import logging

# 全局日志实例引用
api_logger = logging.getLogger("api")
perf_logger = logging.getLogger("performance")
security_logger = logging.getLogger("security")
logger = logging.getLogger("automation")

# 延迟更新为实际的日志实例
def _update_logger_instances():
    """更新日志实例为实际的LazyLogger实例"""
    global api_logger, perf_logger, security_logger, logger
    try:
        from . import api_logger as actual_api_logger
        from . import perf_logger as actual_perf_logger
        from . import security_logger as actual_security_logger
        from . import logger as actual_logger
        api_logger = actual_api_logger
        perf_logger = actual_perf_logger
        security_logger = actual_security_logger
        logger = actual_logger
    except ImportError:
        # 保持默认的logging实例
        pass

# 当模块被完全导入后更新日志实例
import atexit
atexit.register(_update_logger_instances)

class RequestLogger:
    """安全增强的HTTP请求日志记录器（精准定位业务代码）"""

    def __init__(self, logger=None):
        self.logger = logger or api_logger

    def _get_business_caller(self) -> Tuple[str, str, int]:
        """
        精准获取业务代码调用位置（跳过框架层）

        调用栈示例:
          0. _get_business_caller (当前)
          1. log_request/log_response
          2. secure_logger.py (框架)
          3. contextlib (可能)
          4. business_code.py ← 目标位置
        """
        try:
            import inspect
            from pathlib import Path
            frame = inspect.currentframe()
            depth = 0
            # 向上最多10层查找业务代码
            while frame and depth < 10:
                frame = frame.f_back
                depth += 1
                if frame is None:
                    break

                code = frame.f_code
                filename = code.co_filename

                # 跳过框架文件
                skip_patterns = [
                    'secure_logger.py', 'password_guard.py',
                    '/logging/', '\\logging\\',
                    '/contextlib.py', '\\contextlib.py',
                    '<string>', '<stdin>'
                ]
                if any(pattern in filename for pattern in skip_patterns):
                    continue

                # 找到业务代码文件
                return Path(filename).name, code.co_name, frame.f_lineno

            return "unknown.py", "unknown", 0
        except Exception:
            return "unknown.py", "unknown", 0

    def log_request(self, method: str, url: str, **kwargs) -> str:
        # ★★★ 精准获取业务代码位置 ★★★
        filename, func_name, lineno = self._get_business_caller()
        location_prefix = f"[{filename}:{func_name}:{lineno}] "

        request_id = hashlib.sha256(f"{method}{url}{time.time()}".encode()).hexdigest()[:12]

        # ★★★ 优化：清晰的请求格式 ★★★
        # 格式: [业务位置] POST /login (params: token=******, password=******)
        parsed = self._parse_url(url)
        params_str = self._format_params(parsed.params, max_len=80)

        log_msg = f"{location_prefix}{method.upper()} {parsed.path}"
        if params_str:
            log_msg += f" (params: {params_str})"

        self.logger.info(log_msg)
        return request_id

    def log_response(self, request_id: str, status_code: int, **kwargs):
        # ★★★ 精准获取业务代码位置 ★★★
        filename, func_name, lineno = self._get_business_caller()
        location_prefix = f"[{filename}:{func_name}:{lineno}] "

        # ★★★ 修复：确保方法正确传递 ★★★
        method = kwargs.get('method', 'UNKNOWN').upper()
        url = kwargs.get('url', '')
        duration_ms = kwargs.get('duration_ms', 0.0)

        parsed = self._parse_url(url)
        status_marker = "✅" if 200 <= status_code < 300 else "❌"

        # 格式: [业务位置] ✅ POST /login 200 (45.6ms)
        log_msg = f"{location_prefix}{status_marker} {method} {parsed.path} {status_code} ({duration_ms:.1f}ms)"
        self.logger.info(log_msg)

    @staticmethod
    def _parse_url(url: str) -> Any:
        """解析URL为路径和参数"""
        parsed_url = urlparse(url)
        params = parse_qs(parsed_url.query) if parsed_url.query else {}
        return type('ParsedURL', (), {
            'path': parsed_url.path or '/',
            'params': params,
            'full': url
        })()

    @staticmethod
    def _format_params(params: Dict, max_len: int = 80) -> str:
        """格式化参数（敏感字段自动脱敏）"""
        if not params:
            return ""

        parts = []
        for k, v_list in params.items():
            v = v_list[0] if v_list else ""
            # 敏感字段脱敏
            if any(s in k.lower() for s in LogConfig.SENSITIVE_KEYS):
                parts.append(f"{k}=******")
            else:
                # 非敏感字段截断显示
                display = v[:20] + "..." if len(v) > 20 else v
                parts.append(f"{k}={display}")

        result = ", ".join(parts)
        return result[:max_len] + "..." if len(result) > max_len else result

    @staticmethod
    def _sanitize_url(url: str) -> str:
        if '?' not in url:
            return url
        base, query = url.split('?', 1)
        params = query.split('&')
        sanitized = [
            f"{p.split('=')[0]}=******" if any(k in p.lower() for k in LogConfig.SENSITIVE_KEYS)
            else p for p in params
        ]
        return f"{base}?{'&'.join(sanitized)}"

    @staticmethod
    def _sanitize_headers(headers: Dict) -> Dict:
        return {
            k: "******" if any(s in k.lower() for s in LogConfig.SENSITIVE_KEYS) else str(v)[:100]
            for k, v in headers.items()
        }

    @staticmethod
    def _preview_body(body: Any) -> str:
        try:
            import json
            if body is None:
                return ""
            preview = json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body)
            return mask_sensitive_data(preview)[:500] + "..." if len(preview) > 500 else preview
        except Exception:
            return "<non-serializable>"

request_logger = RequestLogger()

def log_performance(
    logger=None,
    level=10,  # logging.INFO
    threshold_ms: float = 50.0,
    enabled: bool = True,
    mark_slow: bool = True
) -> Callable:
    """性能监控装饰器（统一格式）"""
    if not enabled:
        return lambda func: func

    def decorator(func: Callable) -> Callable:
        global perf_logger
        
        log = logger or perf_logger
        actual_module = _get_actual_module_name(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                msg = f"{func.__name__} {duration_ms:.2f}ms"
                if mark_slow and duration_ms >= threshold_ms:
                    msg += f" ⚠️ SLOW"
                log.log(level, msg)
        return wrapper
    return decorator

def log_exception(logger_param=None, exc: Optional[Exception] = None, context: str = ""):
    global logger
    
    log = logger_param or logger
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
        if not LogConfig.QUIET:
            print(error_msg, file=sys.stderr)
        # 尝试使用基本日志记录
        try:
            import logging
            fallback_logger = logging.getLogger("fallback")
            fallback_logger.error(error_msg)
        except Exception:
            pass

def log_security_event(
    action: str,
    user: str = "unknown",
    resource: str = "",
    status: str = "success",
    details: Optional[Dict] = None
) -> bool:
    """安全事件记录（混合格式：前缀 + JSON）"""
    global security_logger, logger
    
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
            "env": LogConfig.ENV,
            "details": safe_details
        }

        # SECURITY 前缀 + 紧凑JSON
        security_logger.info(str(event).replace('\'', '"'))
        return True
    except Exception as e:
        logger.error("SECURITY_LOG_WRITE_FAILED | action=%s | error=%s", action, e)
        return False

def log_step(step_name: str, logger_param=None):
    global logger
    log = logger_param or logger
    
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
    global perf_logger
    
    log = logger_param or perf_logger

    # ★★★ 关键修复：跳过contextlib框架层 ★★★
    filename, func_name, lineno = _get_caller_info(skip_frames=2)
    full_name = f"{filename}:{func_name}:{lineno}"

    start = time.perf_counter()
    log.info("START %s", step_name)

    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        msg = f"END {step_name} {duration_ms:.2f}ms"
        if duration_ms >= threshold_ms:
            msg += f" ⚠️ SLOW"
        log.info(msg)
