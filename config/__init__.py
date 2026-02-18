# framework/config/__init__.py
from .manager import ConfigManager

# 全局唯一配置实例
settings = ConfigManager()

__all__ = ["settings"]