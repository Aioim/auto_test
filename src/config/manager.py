import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, Field
# 现在使用绝对导入
from config.sources.env_loader import EnvLoader
from config.sources.yaml_loader import YamlLoader

PROJECT_ROOT = Path.cwd().resolve().parent


class _SettingsBase(BaseModel):
    """自定义设置基类，替代BaseSettings"""

    # Pydantic V2 配置方式 - 使用 ConfigDict 替代 class Config
    model_config = ConfigDict(
        env_prefix="APP_",  # 环境变量前缀
        env_nested_delimiter="__",  # 嵌套分隔符
        extra="ignore"  # 忽略未定义字段
    )

    @classmethod
    def _load_from_env(cls, prefix: str = "") -> Dict[str, Any]:
        """从环境变量加载配置"""
        result = {}
        prefix = prefix or cls.model_config.get("env_prefix", "APP_")

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 移除前缀
                clean_key = key[len(prefix):].lower()

                # 处理嵌套结构
                nested_delimiter = cls.model_config.get("env_nested_delimiter", "__")
                if nested_delimiter in clean_key:
                    parts = clean_key.split(nested_delimiter)
                    current = result
                    for part in parts[:-1]:
                        current = current.setdefault(part, {})
                    current[parts[-1]] = value
                else:
                    result[clean_key] = value

        # 递归转换值类型
        return cls._convert_env_values(result)

    @classmethod
    def _convert_env_values(cls, data: Any) -> Any:
        """递归转换环境变量值类型"""
        if isinstance(data, dict):
            return {k: cls._convert_env_values(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls._convert_env_values(v) for v in data]
        elif isinstance(data, str):
            # 布尔值转换
            if data.lower() in ("true", "false"):
                return data.lower() == "true"
            # 数字转换
            try:
                if "." in data:
                    return float(data)
                return int(data)
            except ValueError:
                pass
            # 列表转换 (简单支持)
            if data.startswith("[") and data.endswith("]"):
                items = data[1:-1].split(",")
                return [cls._convert_env_values(item.strip()) for item in items]
        return data

    @classmethod
    def _merge_configs(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并配置字典"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._merge_configs(result[key], value)
            else:
                result[key] = value

        return result


class BrowserConfig(BaseModel):
    """浏览器配置模型"""
    headless: bool = True
    type: str = "chromium"  # chromium/firefox/webkit
    enable_js: bool = True
    viewport: Dict[str, int] = {"width": 1280, "height": 720}

    @field_validator("type")
    @classmethod
    def validate_browser_type(cls, v):
        valid_types = ["chromium", "firefox", "webkit"]
        if v not in valid_types:
            raise ValueError(f"无效的浏览器类型: {v}, 必须是 {valid_types}")
        return v

    # 添加模型配置
    model_config = ConfigDict(protected_namespaces=())


class LogConfig(BaseModel):
    """浏览器配置模型"""
    log_dir: Path = PROJECT_ROOT / 'logs'
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file: str = 'TestRun'

    @field_validator("log_level")
    @classmethod
    def validate_browser_type(cls, v):
        valid_types = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_types:
            raise ValueError(f"无效的浏览器类型: {v}, 必须是 {valid_types}")
        return v

    # 添加模型配置
    model_config = ConfigDict(protected_namespaces=())


class TimeoutsConfig(BaseModel):
    """超时配置模型"""
    page_load: int = 30000
    element_wait: int = 10000
    api: int = 15000

    @field_validator("*")
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("超时值必须大于0")
        return v

    # 添加模型配置
    model_config = ConfigDict(protected_namespaces=())


class AllureConfig(BaseModel):
    """Allure报告配置"""
    results_dir: Path = PROJECT_ROOT / "reports/allure-results"
    auto_clean: bool = True
    default_severity: str = "critical"

    # 添加模型配置
    model_config = ConfigDict(protected_namespaces=())


class AppConfig(_SettingsBase):
    """应用级配置模型"""

    # 核心配置
    env: str = "dev"
    frontend_version: str = "v2024.01"
    base_url: str = "https://example.com"
    api_base_url: Optional[str] = None

    # 敏感凭证 (通过.env加载)
    admin_username: str = ""
    admin_password: str = ""
    api_secret_key: str = ""

    # 子配置
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    allure: AllureConfig = Field(default_factory=AllureConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    # 高级选项
    preserve_context_on_failure: bool = False
    video_recording: str = "failed"  # always/failed/off
    enable_network_tracing: bool = True
    selector_strategy: str = "lenient"  # strict/lenient
    resource_cleanup_timeout: int = 5

    # path
    project_root: Path = PROJECT_ROOT
    # 添加模型配置
    model_config = ConfigDict(protected_namespaces=())

    @field_validator("env")
    @classmethod
    def validate_env(cls, v):
        valid_envs = ["dev", "staging", "prod"]
        if v not in valid_envs:
            raise ValueError(f"无效环境: {v}, 必须是 {valid_envs}")
        return v

    @field_validator("video_recording")
    @classmethod
    def validate_video_strategy(cls, v):
        strategies = ["always", "failed", "off"]
        if v not in strategies:
            raise ValueError(f"无效视频策略: {v}, 必须是 {strategies}")
        return v

    @classmethod
    def load_from_environment(cls) -> "AppConfig":
        """从环境加载配置"""
        # 1. 加载环境变量覆盖
        env_overrides = cls._load_from_env()

        # 2. 创建基础实例
        instance = cls()

        # 3. 应用环境变量覆盖
        instance_dict = instance.model_dump()
        merged_config = cls._merge_configs(instance_dict, env_overrides)

        # 4. 验证并返回
        return cls(**merged_config)


class ConfigManager:
    """配置管理核心"""

    def __init__(self):
        self._config: Optional[AppConfig] = None
        self._yaml_loader = YamlLoader()
        self._env_loader = EnvLoader()
        self._overrides: Dict[str, Any] = {}
        self._initialized = False

    def _load_config(self) -> AppConfig | None:
        """加载完整配置"""
        # 1. 加载基础YAML配置
        base_config = self._yaml_loader.load_environment(
            env=self._overrides.get("env") or os.getenv("ENV", "dev")
        )

        # 2. 合并环境变量
        env_config = self._env_loader.load()

        # 3. 深度合并基础配置和环境变量
        merged_base_env = self._deep_merge(base_config, env_config)

        # 4. 应用命令行覆盖
        final_config = self._deep_merge(merged_base_env, self._overrides)

        # 5. 创建配置实例
        try:
            config_instance = AppConfig(**final_config)
            return config_instance
        except ValidationError as e:
            self._handle_validation_error(e)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并字典"""
        # 处理非字典类型
        if not isinstance(base, dict):
            return override

        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def initialize(self):
        """显式初始化 (通常不需要调用)"""
        if not self._initialized:
            self._config = self._load_config()
            self._initialized = True

    def __getattr__(self, name: str) -> Any:
        """动态属性访问"""
        if self._config is None:
            self.initialize()

        # 调试信息：显示所有可用属性
        if name == "__debug_config_attrs__":
            return list(self._config.__dict__.keys())

        # 直接访问配置实例的属性
        try:
            return getattr(self._config, name)
        except AttributeError:
            # 尝试带下划线的环境变量风格
            if "_" in name:
                alt_name = name.replace("_", "")
                try:
                    return getattr(self._config, alt_name)
                except AttributeError:
                    pass

            # 添加更详细的错误信息
            available_attrs = dir(self._config)
            error_msg = (
                f"配置中不存在属性: {name}\n"
                f"可用属性: {', '.join(attr for attr in available_attrs if not attr.startswith('_'))[:100]}..."
            )
            raise AttributeError(error_msg) from None

    def get(self, path: str, default: Any = None) -> Any:
        """
        安全获取嵌套配置
        示例: settings.get("timeouts.page_load", 30000)
        """
        if self._config is None:
            self.initialize()

        current = self._config.model_dump()
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def apply_overrides(self, overrides_str: str):
        """
        应用命令行覆盖
        格式: "key1=value1,key2.subkey=value2"
        """
        if not overrides_str:
            return

        self._overrides = {}
        pairs = overrides_str.split(",")
        for pair in pairs:
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            keys = [k.strip() for k in key.strip().split(".")]  # 确保清理空格
            current = self._overrides

            # 构建嵌套字典
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = self._parse_value(value.strip())

    def _parse_value(self, value: str) -> Any:
        """智能解析配置值类型"""
        # 布尔值
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # 数字
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # 列表 (逗号分隔)
        if value.startswith("[") and value.endswith("]"):
            items = value[1:-1].split(",")
            return [self._parse_value(item.strip()) for item in items]

        # 字典 (简单支持)
        if value.startswith("{") and value.endswith("}"):
            items_str = value[1:-1].strip()
            if not items_str:
                return {}

            items = {}
            for item in items_str.split(","):
                if ":" in item:
                    k, v = item.split(":", 1)
                    key_name = k.strip().strip('"').strip("'")
                    items[key_name] = self._parse_value(v.strip())
            return items

        return value

    def validate(self):
        """显式验证配置 (通常在初始化时调用)"""
        if self._config is None:
            self._config = self._load_config()

    def to_yaml(self) -> str:
        """生成配置快照YAML"""
        if self._config is None:
            self.initialize()

        data = self._config.model_dump(exclude={"admin_password", "api_secret_key"})
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @staticmethod
    def _handle_validation_error(error: ValidationError):
        """处理验证错误"""
        messages = []
        for err in error.errors():
            loc = ".".join(str(l) for l in err["loc"])
            msg = f"配置项 '{loc}': {err['msg']} (值: {err['input']})"
            messages.append(msg)

        error_msg = "配置验证失败:\n" + "\n".join(messages)
        raise RuntimeError(error_msg) from None


# ======================
# 命令行验证 (完整自包含)
# ======================
if __name__ == '__main__':
    settings = ConfigManager()
    print(settings.to_yaml())
