from .manager import ConfigManager
from .env_loader import EnvLoader
from .yaml_loader import YamlLoader
from ._path import PROJECT_ROOT

# 全局唯一配置实例
settings = ConfigManager()
__all__ = [
    "settings", 
    "EnvLoader", 
    "YamlLoader",
    "PROJECT_ROOT"
]
