from config.manager import ConfigManager
from config.env_loader import EnvLoader
from config.yaml_loader import YamlLoader
from config._path import PROJECT_ROOT

# 全局唯一配置实例
settings = ConfigManager()

__all__ = [
    "settings", 
    "EnvLoader", 
    "YamlLoader",
    "PROJECT_ROOT"
]
