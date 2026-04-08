"""
诊断工具模块
提供日志系统状态检查和格式验证
"""
import re
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

from config import settings
LogConfig = settings.log


def diagnose_logger(logger_name: str = "automation") -> Dict[str, Any]:
    """诊断日志器配置"""
    logger = logging.getLogger(logger_name)
    return {
        "name": logger.name,
        "level": logging.getLevelName(logger.level),
        "propagate": logger.propagate,
        "handlers": [
            {
                "type": type(h).__name__,
                "level": logging.getLevelName(h.level),
                "formatter": type(h.formatter).__name__ if h.formatter else "None",
                "filename": getattr(h, 'baseFilename', 'N/A')
            }
            for h in logger.handlers
        ],
        "parent": logger.parent.name if logger.parent else "None"
    }


def print_logger_diagnosis(logger_name: str = "automation"):
    """打印日志器诊断信息"""
    diag = diagnose_logger(logger_name)
    print(f"\n🔍 Logger Diagnosis: {logger_name}")
    print(f"   Level     : {diag['level']}")
    print(f"   Propagate : {'❌ ENABLED' if diag['propagate'] else '✅ DISABLED'}")
    print(f"   Parent    : {diag['parent']}")
    print(f"   Handlers  : {len(diag['handlers'])}")
    for i, h in enumerate(diag['handlers'], 1):
        fname = Path(h['filename']).name if h['filename'] != 'N/A' else 'N/A'
        print(f"     {i}. {fname:25s} | Level={h['level']:7s} | Formatter={h['formatter']}")
    print()


def verify_api_logging() -> Tuple[bool, str]:
    """验证API日志格式是否正确"""
    try:
        api_log = LogConfig.log_dir / "api.log"
        if not api_log.exists():
            return False, "api.log not found"

        content = api_log.read_text(encoding='utf-8')
        lines = [l.strip() for l in content.splitlines() if l.strip()]

        if not lines:
            return False, "api.log is empty"

        last_lines = lines[-3:]
        issues = []

        for line in last_lines:
            if "secure_logger.py" in line:
                issues.append(f"Found framework file in log: {line[:60]}")
            if not re.search(r'\[.*\.py:.*:\d+\]', line):
                issues.append(f"Missing location prefix: {line[:60]}")
            if not (re.search(r'\b(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b', line) or
                    re.search(r'\b\d{3}\b', line)):
                issues.append(f"Invalid format: {line[:60]}")

        if issues:
            return False, "\n".join(issues)
        return True, f"✅ All {len(last_lines)} lines have correct format"
    except Exception as e:
        return False, f"Error verifying API logging: {e}"
    
if __name__ == "__main__":
    print_logger_diagnosis()
    verify_api_logging()