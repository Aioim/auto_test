"""指标收集模块"""

import time
import threading
from typing import Dict, Any

class LogMetrics:
    """SRE监控指标"""
    _lock = threading.Lock()
    _stats = {
        "total_logs": 0, "filtered_logs": 0, "masking_time_ns": 0,
        "handler_errors": 0, "password_leak_attempts": 0,
        "serialization_failures": 0,
    }
    _start_time = time.time()

    @classmethod
    def record(cls, key: str, value: int = 1):
        """记录指标"""
        with cls._lock:
            if key not in cls._stats:
                cls._stats[key] = 0
            cls._stats[key] = cls._stats.get(key, 0) + value

    @classmethod
    def get_snapshot(cls) -> Dict[str, Any]:
        """获取指标快照"""
        with cls._lock:
            uptime = time.time() - cls._start_time
            stats = cls._stats.copy()
            stats.update({
                "uptime_seconds": round(uptime, 2),
                "logs_per_second": round(stats["total_logs"] / max(uptime, 1), 2),
            })
            return stats

    @classmethod
    def reset(cls):
        """重置指标"""
        with cls._lock:
            cls._stats = {
                "total_logs": 0, "filtered_logs": 0, "masking_time_ns": 0,
                "handler_errors": 0, "password_leak_attempts": 0,
                "serialization_failures": 0,
            }
            cls._start_time = time.time()
