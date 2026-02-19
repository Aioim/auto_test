"""安全模块"""

import re
import hashlib
from functools import lru_cache
from typing import Dict, List, Tuple
import logging

# 直接导入依赖模块
from .config import LogConfig
from .metrics import LogMetrics

class MaskingEngine:
    """高性能脱敏引擎"""
    _SHORT_THRESHOLD = 100
    _CACHE_THRESHOLD = 500
    _STREAM_CHUNK = 2000

    _PATTERNS = {
        'auth': [
            (re.compile(r'(?i)("password"\s*:\s*")[^"]+(")'), r'\1******\2'),
            (re.compile(r'(?i)(password=)[^&\s]+'), r'\1******'),
            (re.compile(r'(?i)(pwd=)[^&\s]+'), r'\1******'),
            (re.compile(r'(?i)("token"\s*:\s*")[^"]+(")'), r'\1******\2'),
            (re.compile(r'(?i)(token=)[^&\s]+'), r'\1******'),
            (re.compile(r'(?i)("api_key"\s*:\s*")[^"]+(")'), r'\1******\2'),
            (re.compile(r'(?i)(api_key=)[^&\s]+'), r'\1******'),
            (re.compile(r'(?i)("apikey"\s*:\s*")[^"]+(")'), r'\1******\2'),
            (re.compile(r'(?i)(apikey=)[^&\s]+'), r'\1******'),
            (re.compile(r'(?i)("authorization"\s*:\s*")[^"]+(")'), r'\1******\2'),
            (re.compile(r'(?i)(authorization=)[^&\s]+'), r'\1******'),
        ],
        'pii': [
            (re.compile(r'(?i)([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'), r'***@\2'),
            (re.compile(r'(?i)(1[3-9]\d)(\d{4})(\d{4})'), r'\1****\3'),
            (re.compile(r'(?i)([1-9]\d{5})(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(\d{3})([0-9Xx])'), r'\1**********\6'),
            (re.compile(r'(?i)(\d{4})(\d{8})(\d{4})'), r'\1******\3'),
        ],
        'credit_card': [
            (re.compile(r'(?i)("credit_card"\s*:\s*")[^"]+(")'), r'\1******\2'),
            (re.compile(r'(?i)(credit_card=)[^&\s]+'), r'\1******'),
            (re.compile(r'(?i)(\d{4})[ -]?(\d{4})[ -]?(\d{4})[ -]?(\d{4})'), r'\1**** ****\4'),
        ],
    }

    @staticmethod
    def _get_text_hash(text: str) -> str:
        """获取文本哈希值，用于缓存键"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    @staticmethod
    @lru_cache(maxsize=256)
    def _cached_mask(text_hash: str, text: str) -> str:
        """缓存的脱敏方法"""
        result = text
        for category in MaskingEngine._PATTERNS.values():
            for pattern, repl in category:
                if pattern.search(result):
                    result = pattern.sub(repl, result)
        return result

    @classmethod
    def clear_cache(cls):
        """清理缓存"""
        cls._cached_mask.cache_clear()

    @staticmethod
    def mask(text: str) -> str:
        """脱敏主方法"""
        if not isinstance(text, str) or not text:
            return text
        if len(text) < MaskingEngine._SHORT_THRESHOLD:
            return MaskingEngine._direct_mask(text)
        if len(text) < MaskingEngine._CACHE_THRESHOLD:
            text_hash = MaskingEngine._get_text_hash(text)
            return MaskingEngine._cached_mask(text_hash, text)
        return MaskingEngine._stream_mask(text)

    @staticmethod
    def _direct_mask(text: str) -> str:
        """直接脱敏（短文本）"""
        result = text
        for category in MaskingEngine._PATTERNS.values():
            for pattern, repl in category:
                if pattern.search(result):
                    result = pattern.sub(repl, result)
        return result

    @staticmethod
    def _stream_mask(text: str) -> str:
        """流式脱敏（长文本）"""
        chunks = [text[i:i+MaskingEngine._STREAM_CHUNK] for i in range(0, len(text), MaskingEngine._STREAM_CHUNK)]
        return ''.join(MaskingEngine._direct_mask(chunk) for chunk in chunks)

def mask_sensitive_data(message):
    """脱敏敏感数据"""
    return MaskingEngine.mask(message) if isinstance(message, str) else message

class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""
    _PASSWORD_PATTERNS = [
        re.compile(r'(?i)password\s*[:=]\s*["\']?([^\s"\'&]+)', re.UNICODE),
        re.compile(r'(?i)pwd\s*[:=]\s*["\']?([^\s"\'&]+)', re.UNICODE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤敏感数据"""
        try:
            if isinstance(record.msg, str):
                if any(pat.search(record.msg) for pat in self._PASSWORD_PATTERNS):
                    LogMetrics.record("password_leak_attempts")
                    record.msg = re.sub(r'(?i)(password|pwd)[=:]\s*["\']?[^"]+', r'\1=******', record.msg)
            if isinstance(record.msg, str):
                record.msg = mask_sensitive_data(record.msg)
            if record.args and isinstance(record.args, dict):
                record.args = {
                    k: "******" if any(s in str(k).lower() for s in LogConfig.SENSITIVE_KEYS) else v
                    for k, v in record.args.items()
                }
            LogMetrics.record("filtered_logs")
            LogMetrics.record("total_logs")
            return True
        except Exception as e:
            LogMetrics.record("handler_errors")
            error_msg = f"⚠️  Sensitive data filter error: {e}"
            if not LogConfig.QUIET:
                import sys
                print(error_msg, file=sys.stderr)
            # 尝试记录错误
            try:
                import logging
                fallback_logger = logging.getLogger("fallback")
                fallback_logger.error(error_msg)
            except Exception:
                pass
            return True
