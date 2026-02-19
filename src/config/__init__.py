from .manager import ConfigManager
from .locators_i18n import get_text
from .env_loader import EnvLoader
from .yaml_loader import YamlLoader
from ._path import PROJECT_ROOT
# 全局唯一配置实例
settings = ConfigManager()

__all__ = [
    "settings",
    "get_text",
    "EnvLoader",
    "YamlLoader",
    "PROJECT_ROOT"
]
