from pathlib import Path
from typing import Any, Dict
import yaml
from ._path import PROJECT_ROOT


class YamlLoader:
    """YAML配置加载器"""

    def __init__(self, config_dir: str = PROJECT_ROOT / "environments"):
        self.config_dir = Path(config_dir)
        self._cache = {}  # 缓存结构: {env: (merged_config, mtime_dict)}

    def load_environment(self, env: str = "dev") -> Dict[str, Any]:
        """加载指定环境的YAML配置"""
        # 检查缓存是否有效
        if env in self._cache:
            cached_config, mtime_dict = self._cache[env]
            if self._is_cache_valid(mtime_dict):
                return cached_config.copy()

        # 1. 加载基础配置
        base_config, base_mtime = self._load_yaml_with_mtime("base.yaml")
        # 2. 加载环境特定配置
        env_file = f"{env}.yaml"
        env_config, env_mtime = self._load_yaml_with_mtime(env_file) if (self.config_dir / env_file).exists() else ({}, 0)

        # 3. 递归合并
        merged = self._deep_merge(base_config, env_config)

        # 4. 缓存结果（包含文件修改时间）
        mtime_dict = {
            "base.yaml": base_mtime,
            f"{env}.yaml": env_mtime
        }
        self._cache[env] = (merged, mtime_dict)
        return merged.copy()

    def _is_cache_valid(self, mtime_dict: Dict[str, float]) -> bool:
        """检查缓存是否有效（基于文件修改时间）"""
        for filename, cached_mtime in mtime_dict.items():
            file_path = self.config_dir / filename
            if file_path.exists():
                current_mtime = file_path.stat().st_mtime
                if current_mtime > cached_mtime:
                    return False
        return True

    def _load_yaml_with_mtime(self, filename: str) -> tuple[Dict[str, Any], float]:
        """安全加载YAML文件并返回修改时间"""
        file_path = self.config_dir / filename

        if not file_path.exists():
            if filename == "base.yaml":
                raise FileNotFoundError(f"基础配置文件不存在: {file_path}")
            return {}, 0

        try:
            # 获取文件修改时间
            mtime = file_path.stat().st_mtime
            
            with open(file_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config, mtime
        except yaml.YAMLError as e:
            raise ValueError(f"YAML解析错误 ({file_path}): {str(e)}") from e
        except Exception as e:
            raise ValueError(f"加载YAML文件失败 ({file_path}): {str(e)}") from e

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """安全加载YAML文件"""
        config, _ = self._load_yaml_with_mtime(filename)
        return config

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        递归合并字典
        - override中的值覆盖base
        - 嵌套字典深度合并
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()

    @staticmethod
    def load_reporting_config() -> Dict[str, Any]:
        """加载报告专项配置 (独立于环境)"""
        # 尝试从多个位置加载
        possible_paths = [
            Path("config/reporting.yaml"),
            PROJECT_ROOT / "config/reporting.yaml",
            PROJECT_ROOT / "reporting.yaml"
        ]

        for reporting_file in possible_paths:
            if reporting_file.exists():
                try:
                    with open(reporting_file, "r", encoding="utf-8") as f:
                        return yaml.safe_load(f) or {}
                except yaml.YAMLError as e:
                    print(f"⚠️ 报告配置加载警告: {str(e)}")
                break
        return {}


if __name__ == '__main__':
    conf = YamlLoader().load_environment()
    print(conf)
