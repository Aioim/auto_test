"""日志格式化器模块"""

import logging
import re
import json
from datetime import datetime, timezone
from typing import Any
import inspect
from pathlib import Path

# 直接导入依赖模块
from .config import LogConfig
from .security import mask_sensitive_data
from .metrics import LogMetrics

class SecurityFormatter(logging.Formatter):
    """统一日志格式：时间 级别 [文件:函数:行号] 消息"""
    _CRLF_PATTERN = re.compile(r'[\r\n\x1b\x9b]')
    _ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    STANDARD_FORMAT = "%(asctime)s %(levelname)-8s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # 缓存：保存__main__模块的实际文件名映射
    _main_module_cache = {}
    
    def format(self, record: logging.LogRecord) -> str:
        # 修复 __main__ 为实际文件名
        original_module = record.module
        original_filename = record.filename

        if LogConfig.REPLACE_MAIN_WITH_FILENAME and record.module == "__main__":
            # 尝试从缓存获取
            if record.filename in self._main_module_cache:
                record.module, record.filename = self._main_module_cache[record.filename]
            else:
                try:
                    frame = inspect.currentframe()
                    depth = 0
                    while frame and depth < 10:  # 减少最大深度，提高性能
                        code = frame.f_code
                        filename = code.co_filename
                        if (filename and not filename.startswith('<') and
                            filename != __file__ and 'logging' not in filename and
                            'secure_logger' not in filename):
                            module_name = Path(filename).stem
                            file_name = Path(filename).name
                            record.module = module_name
                            record.filename = file_name
                            # 缓存结果
                            self._main_module_cache[original_filename] = (module_name, file_name)
                            break
                        frame = frame.f_back
                        depth += 1
                except Exception:
                    record.module = "script"
                    record.filename = "unknown.py"
                    # 缓存错误情况
                    self._main_module_cache[original_filename] = ("script", "unknown.py")

        # 安全清理
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)
        if record.args and isinstance(record.args, dict):
            record.args = {
                self._sanitize(k): self._sanitize(v) if isinstance(v, str) else v
                for k, v in record.args.items()
            }

        result = super().format(record)
        record.module = original_module
        record.filename = original_filename
        return result

    @staticmethod
    def _sanitize(text: str) -> str:
        text = SecurityFormatter._ANSI_ESCAPE.sub('', text)
        return SecurityFormatter._CRLF_PATTERN.sub(' ', text)
    
    @classmethod
    def clear_cache(cls):
        """清理缓存"""
        cls._main_module_cache.clear()

class ColorCodes:
    """颜色代码定义"""
    RESET = "\x1b[0m"
    CYAN = "\x1b[36m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BG_RED = "\x1b[41m"
    WHITE = "\x1b[37m"
    BOLD = "\x1b[1m"
    CRITICAL = BOLD + BG_RED + WHITE

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    LEVEL_COLORS = {
        logging.DEBUG: ColorCodes.CYAN,
        logging.INFO: ColorCodes.GREEN,
        logging.WARNING: ColorCodes.YELLOW,
        logging.ERROR: ColorCodes.RED,
        logging.CRITICAL: ColorCodes.CRITICAL,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        if color and LogConfig.ENABLE_COLORS:
            original = record.levelname
            try:
                record.levelname = f"{color}{record.levelname}{ColorCodes.RESET}"
                return super().format(record)
            finally:
                record.levelname = original
        return super().format(record)

class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    def format(self, record: logging.LogRecord) -> str:
        safe_record = logging.makeLogRecord(record.__dict__)
        SecurityFormatter().format(safe_record)

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_sensitive_data(safe_record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_data["stack"] = self.formatStack(record.stack_info)

        try:
            return json.dumps(log_data, ensure_ascii=False, default=_json_default)
        except Exception:
            try:
                LogMetrics.record("serialization_failures")
            except Exception:
                pass
            return json.dumps({
                "error": "JSON serialization failed",
                "raw_msg": str(record.msg)[:200],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, ensure_ascii=False)

def _json_default(obj: Any) -> str:
    """JSON序列化默认处理函数"""
    try:
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool, list, dict)):
            return obj
        if hasattr(obj, '__dict__'):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            try:
                return list(obj)
            except Exception:
                pass
        if hasattr(obj, '__str__'):
            return str(obj)
        return f"<object: {type(obj).__name__}>"
    except Exception as e:
        return f"<unserializable: {type(obj).__name__}: {str(e)[:50]}>"
