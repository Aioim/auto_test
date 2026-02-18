from pathlib import Path
from typing import Any, Dict
import yaml
from ._path import PROJECT_ROOT

class YamlLoader:
    """YAML配置加载器"""

    def __init__(self, config_dir: str = PROJECT_ROOT/ "environments"):
        self.config_dir = Path(config_dir)
        self._cache = {}

    def load_environment(self, env: str = "dev") -> Dict[str, Any]:
        """加载指定环境的YAML配置"""
        if env in self._cache:
            return self._cache[env].copy()

        # 1. 加载基础配置
        base_config = self._load_yaml("base.yaml")
        # 2. 加载环境特定配置
        env_file = f"{env}.yaml"
        env_config = self._load_yaml(env_file) if (self.config_dir / env_file).exists() else {}

        # 3. 递归合并
        merged = self._deep_merge(base_config, env_config)

        # 4. 缓存结果
        self._cache[env] = merged
        return merged.copy()

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """安全加载YAML文件"""
        file_path = self.config_dir / filename

        if not file_path.exists():
            if filename == "base.yaml":
                raise FileNotFoundError(f"基础配置文件不存在: {file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML解析错误 ({file_path}): {str(e)}") from e

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

    @staticmethod
    def load_reporting_config( ) -> Dict[str, Any]:
        """加载报告专项配置 (独立于环境)"""
        reporting_file = Path("config/reporting.yaml")
        if reporting_file.exists():
            try:
                with open(reporting_file, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                print(f"⚠️ 报告配置加载警告: {str(e)}")
        return {}


if __name__=='__main__':
    conf=YamlLoader().load_environment()
    print(conf)