"""日志处理器工厂模块"""

import logging
import time
import atexit
import signal
from pathlib import Path
from typing import Optional, Dict
import threading

# 直接导入依赖模块
from .config import LogConfig
from .formatters import SecurityFormatter

# 使用模块级别的变量来存储状态，这样即使模块被多次导入，这些变量也不会被重新初始化
import os
import tempfile

# 使用环境变量来存储初始化状态，这样即使模块被多次导入，也不会重复初始化
INITIALIZED_FLAG = "__logger_initialized__"

# 初始化状态
_module_initialized = os.environ.get(INITIALIZED_FLAG, "False") == "True"
_module_lock = threading.RLock()
_initialized_dirs: set = set()
_first_init = not _module_initialized

class HandlerFactory:
    """日志处理器工厂"""
    _handlers: Dict[int, logging.Handler] = {}
    _refcount: Dict[int, int] = {}
    _lock = threading.RLock()

    @classmethod
    def _ensure_log_dir(cls, target_dir: Optional[Path] = None) -> Path:
        """确保日志目录存在"""
        global _initialized_dirs, _first_init, _module_initialized, _module_lock, INITIALIZED_FLAG
        log_dir = (target_dir or LogConfig.LOG_DIR).resolve()
        try:
            with _module_lock:
                if log_dir in _initialized_dirs:
                    return log_dir
                # 只创建目录，不执行写入测试，减少初始化时间
                log_dir.mkdir(parents=True, exist_ok=True)
                was_first = _first_init
                _first_init = False
                _initialized_dirs.add(log_dir)
                if was_first and not LogConfig.QUIET:
                    import sys
                    print(f"✅ Secure logger initialized: {log_dir}", file=sys.stderr)
                # 设置环境变量，标记已经初始化
                os.environ[INITIALIZED_FLAG] = "True"
                _module_initialized = True
                return log_dir
        except Exception as e:
            error_msg = f"❌ Log directory initialization failed: {e} (path: {log_dir})"
            if not LogConfig.QUIET:
                import sys
                print(error_msg, file=sys.stderr)
            # 重新抛出异常，附带更详细的信息
            raise RuntimeError(error_msg) from e

    @classmethod
    def create_handler(
        cls,
        handler_type: str,
        filename: str,
        level: int,
        fmt: str = None,
        datefmt: str = None,
        **kwargs
    ) -> logging.Handler:
        """创建日志处理器"""
        log_dir = cls._ensure_log_dir()
        
        # 使用默认格式
        if fmt is None:
            fmt = SecurityFormatter.STANDARD_FORMAT
        if datefmt is None:
            datefmt = SecurityFormatter.DATE_FORMAT
            
        formatter = SecurityFormatter(fmt, datefmt)

        if handler_type == "timed":
            from logging.handlers import TimedRotatingFileHandler
            # 创建历史日志目录
            history_dir = log_dir / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            
            handler = TimedRotatingFileHandler(
                filename=log_dir / filename,
                when=kwargs.get("when", "midnight"),
                interval=kwargs.get("interval", 1),
                backupCount=LogConfig.BACKUP_COUNT,
                encoding="utf-8",
                delay=False
            )
            # 设置备份目录
            if hasattr(handler, 'suffix'):
                # 重写rotation_filename方法来指定备份目录
                original_rotation_filename = handler.rotation_filename
                def custom_rotation_filename(path):
                    # 获取文件名
                    fname = Path(path).name
                    # 返回历史目录中的路径
                    return str(history_dir / fname)
                handler.rotation_filename = custom_rotation_filename
        elif handler_type == "rotating":
            from logging.handlers import RotatingFileHandler
            # 创建历史日志目录
            history_dir = log_dir / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            
            handler = RotatingFileHandler(
                filename=log_dir / filename,
                maxBytes=kwargs.get("maxBytes", LogConfig.MAX_BYTES),
                backupCount=kwargs.get("backupCount", 5),
                encoding="utf-8",
                delay=False
            )
            # 设置备份目录
            if hasattr(handler, 'suffix'):
                # 重写rotation_filename方法来指定备份目录
                original_rotation_filename = handler.rotation_filename
                def custom_rotation_filename(path):
                    # 获取文件名
                    fname = Path(path).name
                    # 返回历史目录中的路径
                    return str(history_dir / fname)
                handler.rotation_filename = custom_rotation_filename
        elif handler_type == "console":
            import sys
            handler = logging.StreamHandler(sys.stdout)
        else:
            raise ValueError(f"Unknown handler type: {handler_type}")

        handler.setLevel(level)
        handler.setFormatter(formatter)
        cls._register(handler)
        return handler

    @classmethod
    def _register(cls, handler: logging.Handler) -> None:
        """注册处理器"""
        hid = id(handler)
        with cls._lock:
            cls._handlers[hid] = handler
            cls._refcount[hid] = cls._refcount.get(hid, 0) + 1

    @classmethod
    def cleanup(cls, force: bool = False) -> None:
        """清理处理器"""
        with cls._lock:
            for hid in list(cls._handlers.keys()):
                ref = cls._refcount.get(hid, 0)
                if force or ref <= 0:
                    handler = cls._handlers.pop(hid, None)
                    cls._refcount.pop(hid, None)
                    if handler:
                        try:
                            handler.acquire()
                            try:
                                handler.flush()
                                handler.close()
                            finally:
                                handler.release()
                        except Exception:
                            pass

    @classmethod
    def get_handler_count(cls) -> int:
        """获取处理器数量"""
        with cls._lock:
            return len(cls._handlers)

# 注册清理函数
atexit.register(lambda: HandlerFactory.cleanup(force=True))
try:
    signal.signal(signal.SIGTERM, lambda s, f: HandlerFactory.cleanup(force=True))
    signal.signal(signal.SIGINT, lambda s, f: HandlerFactory.cleanup(force=True))
except ValueError:
    pass
