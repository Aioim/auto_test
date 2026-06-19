"""
配置管理模块 - 生产级多语言代码分析平台
支持：YAML 基础配置、环境变量覆盖（无前缀，双下划线表示嵌套）、命令行覆盖
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List, ClassVar, Set
from datetime import datetime
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, field_validator, SecretStr
from config.path import PROJECT_ROOT
from config.yaml_loader import YamlLoader


# ============================================================================
# 配置模型定义
# ============================================================================
class ProjectConfig(BaseModel):
    """项目基础配置"""
    name: str = "code-graph-analyzer"
    root: Path = PROJECT_ROOT
    version: str = "1.0.0"

    model_config = ConfigDict(extra="allow")


class LanguagesConfig(BaseModel):
    """启用的分析语言"""
    enabled: List[str] = Field(default_factory=lambda: ["python"])

    model_config = ConfigDict(extra="allow")


class PythonConfig(BaseModel):
    """Python 语言特定配置"""
    external_lib_paths: List[Path] = Field(default_factory=list)
    ignore_patterns: List[str] = Field(default_factory=list)

    @field_validator("external_lib_paths", mode="before")
    @classmethod
    def validate_paths(cls, v):
        if isinstance(v, list):
            return [Path(p) for p in v]
        return v

    model_config = ConfigDict(extra="allow")


class Neo4jConfig(BaseModel):
    """Neo4j 连接配置"""
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: SecretStr = Field(default=SecretStr("neo4j"), exclude=True)
    database: str = "neo4j"

    model_config = ConfigDict(extra="allow")


class SQLiteConfig(BaseModel):
    """SQLite 元数据存储配置"""
    path: Path = PROJECT_ROOT / "analysis_meta.db"

    model_config = ConfigDict(extra="allow")


class StorageConfig(BaseModel):
    """存储后端总配置"""
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    sqlite: SQLiteConfig = Field(default_factory=SQLiteConfig)

    model_config = ConfigDict(extra="allow")


class LogConfig(BaseModel):
    """日志配置 - 与现有 logger 模块兼容"""
    log_dir: Path = PROJECT_ROOT / "logs"
    log_level: str = "INFO"
    log_file: str = "code_graph.log"
    backup_count: int = 7
    max_bytes: int = 10 * 1024 * 1024
    perf_max_bytes: int = 5 * 1024 * 1024
    enable_colors: bool = False
    enable_emergency_response: bool = False
    quiet: bool = False
    replace_main_with_filename: bool = True
    structured: bool = True  # 是否输出结构化日志（JSON）

    SENSITIVE_KEYS: ClassVar[Set[str]] = {
        "password", "pwd", "pass", "secret", "token", "api_key", "apikey",
        "authorization", "cookie", "x-api-key", "access_token", "refresh_token",
        "new_password", "old_password", "confirm_password", "credit_card",
        "ssn", "social_security", "passport", "cvv", "pin", "private_key"
    }

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v = v.upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid:
            raise ValueError(f"无效日志级别: {v}, 必须是 {valid}")
        return v

    def initialize(self) -> None:
        """初始化日志目录（由日志模块调用）"""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            if not self.quiet:
                print(f"⚠️ 无法创建日志目录: {e}", file=sys.stderr)

    model_config = ConfigDict(protected_namespaces=())


class AppConfig(BaseModel):
    """应用主配置 - 支持环境变量覆盖（无前缀要求，使用双下划线表示嵌套）"""
    # 核心配置
    env: str = "beta"
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    languages: LanguagesConfig = Field(default_factory=LanguagesConfig)
    python: PythonConfig = Field(default_factory=PythonConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    # 运行时信息
    time_now: datetime = Field(default_factory=datetime.now)

    # 可选全局设置
    debug: bool = False

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        return v.lower()

    @classmethod
    def from_env(cls) -> Dict[str, Any]:
        """
        从环境变量构建配置字典（无前缀要求，读取所有环境变量）。
        支持嵌套：使用双下划线 __ 表示嵌套层级，例如 PROJECT__NAME=foo 映射到 project.name。
        """
        env_data = {}
        for key, value in os.environ.items():
            clean_key = key.lower()
            if "__" in clean_key:
                parts = clean_key.split("__")
                current = env_data
                for part in parts[:-1]:
                    current = current.setdefault(part, {})
                current[parts[-1]] = cls._parse_env_value(value)
            else:
                env_data[clean_key] = cls._parse_env_value(value)
        return env_data

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        """将环境变量字符串转换为合适类型"""
        low = value.lower()
        if low in ("true", "false"):
            return low == "true"
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        return value

    @classmethod
    def from_env_full(cls) -> "AppConfig":
        """从环境变量构建完整的 AppConfig 实例（包含默认值），主要用于测试"""
        env_dict = cls.from_env()
        default_instance = cls()
        merged = cls._deep_merge(default_instance.model_dump(), env_dict)
        return cls(**merged)

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = AppConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    model_config = ConfigDict(protected_namespaces=(), extra="allow")


# ============================================================================
# 配置管理器（单例）
# ============================================================================
class ConfigManager:
    """统一配置管理器 - 聚合 YAML、环境变量、命令行覆盖"""

    _instance: ClassVar[Optional["ConfigManager"]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config: Optional[AppConfig] = None
            cls._instance._yaml_loader = YamlLoader()
            cls._instance._overrides: Dict[str, Any] = {}
            cls._instance._initialized = False
        return cls._instance

    def _load_full_config(self) -> AppConfig:
        """加载并合并所有配置源"""
        # 1. 加载 YAML 基础配置（按环境）
        env_name = self._overrides.get("env") or os.getenv("ENV", "beta")
        yaml_config = self._yaml_loader.load_environment(env=env_name)

        # 2. 从环境变量获取覆盖字典
        env_overrides = AppConfig.from_env()

        # 3. 深度合并：YAML 被环境变量覆盖
        merged_dict = self._deep_merge(yaml_config, env_overrides)

        # 4. 应用命令行覆盖（优先级最高）
        final_dict = self._deep_merge(merged_dict, self._overrides)

        # 5. 验证并返回最终配置
        return AppConfig(**final_dict)

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def initialize(self) -> None:
        """显式初始化（通常由属性访问自动触发）"""
        if not self._initialized:
            try:
                self._config = self._load_full_config()
                # 初始化日志目录
                self._config.log.initialize()
                self._initialized = True
            except Exception as e:
                raise RuntimeError(f"配置加载失败: {e}") from e

    def __getattr__(self, name: str) -> Any:
        if self._config is None:
            self.initialize()
        try:
            return getattr(self._config, name)
        except AttributeError:
            available = [attr for attr in dir(self._config) if not attr.startswith("_")]
            raise AttributeError(f"配置中不存在属性 '{name}'. 可用属性: {', '.join(available[:20])}")

    def get(self, path: str, default: Any = None) -> Any:
        """通过点号路径获取嵌套配置，如 settings.get('storage.neo4j.uri')"""
        if self._config is None:
            self.initialize()
        current = self._config.model_dump()
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def apply_overrides(self, overrides_str: str) -> None:
        """解析命令行覆盖字符串 'key=value,key2.subkey=value2'"""
        if not overrides_str:
            return
        self._overrides = {}
        pairs = overrides_str.split(",")
        for pair in pairs:
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            keys = [k.strip() for k in key.strip().split(".")]
            current = self._overrides
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = self._parse_override_value(value.strip())

    @staticmethod
    def _parse_override_value(value: str) -> Any:
        """解析命令行覆盖的值（支持布尔、数字、列表、简单字典）"""
        low = value.lower()
        if low in ("true", "false"):
            return low == "true"
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        if value.startswith("[") and value.endswith("]"):
            items = value[1:-1].split(",")
            return [ConfigManager._parse_override_value(it.strip()) for it in items if it.strip()]
        if value.startswith("{") and value.endswith("}"):
            result = {}
            content = value[1:-1].strip()
            if content:
                for item in content.split(","):
                    if ":" in item:
                        k, v = item.split(":", 1)
                        result[k.strip().strip('"\'')] = ConfigManager._parse_override_value(v.strip())
            return result
        return value

    def load_from_file(self, config_path: Path) -> None:
        """直接加载指定的配置文件（忽略环境区分）"""
        import yaml
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._config = AppConfig(**data)
        self._config.log.initialize()
        self._initialized = True

    def validate(self) -> None:
        """显式验证配置（初始化时已做）"""
        if self._config is None:
            self.initialize()

    def to_yaml(self) -> str:
        """导出当前配置为 YAML（隐藏敏感字段）"""
        if self._config is None:
            self.initialize()
        # 排除密码字段
        data = self._config.model_dump(exclude={"storage": {"neo4j": {"password"}}})
        import yaml
        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def reload(self) -> None:
        """热重载配置（清空缓存并重新加载）"""
        self._yaml_loader.clear_cache()
        self._config = None
        self._initialized = False
        self.initialize()


# ============================================================================
# 全局单例导出
# ============================================================================
settings = ConfigManager()

# 为了兼容直接导入配置模型的需求，也可以导出模型类
__all__ = [
    "settings",
    "AppConfig",
    "ProjectConfig",
    "LanguagesConfig",
    "PythonConfig",
    "Neo4jConfig",
    "SQLiteConfig",
    "StorageConfig",
    "LogConfig",
]

if __name__ == "__main__":
    # 简单测试
    print("=== 配置测试 ===")
    print(f"项目名称: {settings.project.name}")
    print(f"项目根目录: {settings.project.root}")
    print(f"环境: {settings.env}")
    print(f"日志级别: {settings.log.log_level}")
    print(f"Neo4j URI: {settings.storage.neo4j.uri}")
    print(f"密码（隐藏）: {settings.storage.neo4j.password}")
