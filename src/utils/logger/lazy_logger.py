"""延迟初始化日志实例模块"""

import logging
import sys
import threading
from datetime import datetime, timezone
from typing import Dict, Any

# 使用模块级别的变量来存储日志实例，这样即使模块被多次导入，这些变量也不会被重新初始化
_module_instances: Dict[str, Any] = {}
_module_lock = threading.Lock()


class LazyLogger:
    """延迟初始化日志实例"""

    @classmethod
    def get(cls, name: str, **kwargs):
        """获取或创建日志实例"""
        global _module_instances, _module_lock
        # 直接在锁的保护下检查和创建日志实例，避免多次创建
        with _module_lock:
            if name not in _module_instances:
                # 导入依赖
                from .handlers import HandlerFactory
                from .formatters import SecurityFormatter, ColoredFormatter
                from .config import LogConfig

                logger = logging.getLogger(name)
                
                # 清理旧处理器
                if logger.handlers:
                    handlers = logger.handlers[:]
                    for handler in handlers:
                        try:
                            logger.removeHandler(handler)
                            handler.close()
                        except Exception:
                            pass
                    logger.handlers.clear()

                level = getattr(logging, (kwargs.get('log_level') or LogConfig.LOG_LEVEL).upper(), logging.INFO)
                logger.setLevel(level)
                logger.propagate = False
                logger.parent = None

                # 添加控制台处理器
                if kwargs.get('log_to_console', True):
                    handler = logging.StreamHandler(sys.stdout)
                    handler.setLevel(logging.DEBUG)
                    formatter = SecurityFormatter(
                        SecurityFormatter.STANDARD_FORMAT,
                        SecurityFormatter.DATE_FORMAT
                    )
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)
                
                # 添加文件处理器
                if kwargs.get('log_to_file', True):
                    # 主日志器：test_run.log
                    if name == "automation":
                        logger.addHandler(HandlerFactory.create_handler(
                            "timed", LogConfig.MAIN_LOG_FILE, logging.DEBUG
                        ))
                        # 错误日志（含堆栈）
                        logger.addHandler(HandlerFactory.create_handler(
                            "rotating",
                            f"error_{datetime.now().strftime('%Y%m%d')}.log",
                            logging.ERROR,
                            fmt="%(asctime)s %(levelname)-8s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s\nEXCEPTION: %(exc_info)s",
                            maxBytes=LogConfig.MAX_BYTES
                        ))
                    # 其他自定义日志器
                    elif kwargs.get('separate_log_file'):
                        filename = f"{name}.log" if kwargs.get('separate_log_file') is True else kwargs.get('separate_log_file')
                        logger.addHandler(HandlerFactory.create_handler(
                            "timed", filename, logging.DEBUG
                        ))

                # 初始化横幅
                if name == "automation" and not LogConfig.QUIET:
                    logger.info("=" * 70)
                    logger.info(f"✅ Secure Logger | Env: {LogConfig.ENV} | Level: {logging.getLevelName(level)}")
                    logger.info(f"⏰ UTC: {datetime.now(timezone.utc).isoformat()}")
                    logger.info("=" * 70)

                _module_instances[name] = logger
        return _module_instances[name]

    @classmethod
    def cleanup(cls):
        """清理所有日志实例"""
        global _module_instances, _module_lock
        with _module_lock:
            for logger in _module_instances.values():
                if hasattr(logger, 'handlers'):
                    for handler in logger.handlers:
                        try:
                            handler.close()
                        except Exception:
                            pass
            _module_instances.clear()