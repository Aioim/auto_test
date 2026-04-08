from logger import LazyLogger, SensitiveDataFilter, log_performance

logger = LazyLogger.get("automation")
logger.addFilter(SensitiveDataFilter())
logger.info("测试日志")