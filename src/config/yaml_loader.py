from pathlib import Path
from typing import Any, Dict, Tuple
import yaml
from config.path import PROJECT_ROOT


class YamlLoader:
    """YAML配置加载器（支持缓存和文件修改时间检测）"""

    def __init__(self, config_dir: Path = PROJECT_ROOT / "environments"):
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Tuple[Dict[str, Any], Dict[str, float]]] = {}

    def load_environment(self, env: str = "dev") -> Dict[str, Any]:
        """加载指定环境的YAML配置"""
        # 检查缓存
        if env in self._cache:
            cached_config, mtime_dict = self._cache[env]
            if self._is_cache_valid(mtime_dict):
                return cached_config.copy()

        # 加载 base.yaml 和 {env}.yaml
        base_config, base_mtime = self._load_yaml_with_mtime("base.yaml")
        env_file = f"{env}.yaml"
        env_config, env_mtime = self._load_yaml_with_mtime(env_file) if (self.config_dir / env_file).exists() else ({}, 0)

        merged = self._deep_merge(base_config, env_config)
        mtime_dict = {"base.yaml": base_mtime, f"{env}.yaml": env_mtime}
        self._cache[env] = (merged, mtime_dict)
        return merged.copy()

    def _is_cache_valid(self, mtime_dict: Dict[str, float]) -> bool:
        for filename, cached_mtime in mtime_dict.items():
            file_path = self.config_dir / filename
            if file_path.exists() and file_path.stat().st_mtime > cached_mtime:
                return False
        return True

    def _load_yaml_with_mtime(self, filename: str) -> Tuple[Dict[str, Any], float]:
        file_path = self.config_dir / filename
        if not file_path.exists():
            if filename == "base.yaml":
                raise FileNotFoundError(f"基础配置文件不存在: {file_path}")
            return {}, 0.0

        mtime = file_path.stat().st_mtime
        with open(file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config, mtime

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = YamlLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def clear_cache(self) -> None:
        self._cache.clear()
        
if __name__ == "__main__":
    loader = YamlLoader()
    env = loader.load_environment()
    print(env)