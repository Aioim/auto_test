from datetime import datetime


def format_time(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化指定的 datetime 对象"""
    return dt.strftime(fmt)
