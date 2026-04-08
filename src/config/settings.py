# config/settings.py
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set, ClassVar
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError
from pydantic.types import SecretStr

from config.path import PROJECT_ROOT
from config.env_loader import EnvLoader
from config.yaml_loader import YamlLoader


# ========== 配置模型 ==========
class BrowserConfig(BaseModel):
    headless: bool = True
    type: str = "chromium"
    enable_js: bool = True
    viewport: Dict[str, int] = Field(default_factory=lambda: {"width": 1920, "height": 1080})
    locale: str = "zh-CN"
    permissions: list[str] = Field(default_factory=lambda: ["geolocation", "notifications", "clipboard-read"])
    geolocation: Dict[str, float] = Field(default_factory=lambda: {"latitude": 31.2304, "longitude": 121.4737})
    auth_dir: Optional[Path] = None

    @field_validator("type")
    @classmethod
    def validate_browser_type(cls, v: str) -> str:
        valid = ["chromium", "firefox", "webkit"]
        if v not in valid:
            raise ValueError(f"无效浏览器类型: {v}, 必须是 {valid}")
        return v

    model_config = ConfigDict(protected_namespaces=())


class TimeoutsConfig(BaseModel):
    page_load: int = 30000
    element_wait: int = 10000
    api: int = 15000

    @field_validator("page_load", "element_wait", "api", mode="before")
    @classmethod
    def validate_positive(cls, v: Any) -> int:
        if isinstance(v, (int, float)) and v <= 0:
            raise ValueError("超时值必须大于0")
        return int(v)

    model_config = ConfigDict(protected_namespaces=())


class AllureConfig(BaseModel):
    results_dir: Path = PROJECT_ROOT / "output/reports/allure-results"
    auto_clean: bool = True
    default_severity: str = "critical"

    model_config = ConfigDict(protected_namespaces=())


class LogConfig(BaseModel):
    log_dir: Path = PROJECT_ROOT / "logs"
    log_level: str = "INFO"
    log_file: str = "test_run.log"
    backup_count: int = 7
    max_bytes: int = 10 * 1024 * 1024
    perf_max_bytes: int = 5 * 1024 * 1024
    enable_colors: bool = False
    enable_emergency_response: bool = False
    quiet: bool = False
    replace_main_with_filename: bool = True

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
    frontend_version: str = "v2026.01"
    base_url: Optional[str] = None
    api_base_url: Optional[str] = None
    login_url: Optional[str] = None

    # 敏感凭证（使用 SecretStr）
    username: str = ""
    password: SecretStr = SecretStr("")
    api_secret_key: SecretStr = SecretStr("")

    # 子配置
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    allure: AllureConfig = Field(default_factory=AllureConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    # 高级选项
    preserve_context_on_failure: bool = False
    video_recording: str = "failed"  # always/failed/off
    enable_network_tracing: bool = True
    selector_strategy: str = "lenient"
    resource_cleanup_timeout: int = 5

    # 运行时信息
    time_now: datetime = Field(default_factory=datetime.now)

    # 路径配置（基于 PROJECT_ROOT）
    screenshot_dir: Path = PROJECT_ROOT / "output/screenshots"
    visual_baseline_dir: Path = PROJECT_ROOT / "test_data/visual/baseline"
    visual_diff_dir: Path = PROJECT_ROOT / "test_data/visual/diff"
    visual_threshold: float = 0.92

    @field_validator("video_recording")
    @classmethod
    def validate_video_strategy(cls, v: str) -> str:
        strategies = ["always", "failed", "off"]
        if v not in strategies:
            raise ValueError(f"无效视频策略: {v}, 必须是 {strategies}")
        return v

    @field_validator("selector_strategy")
    @classmethod
    def validate_selector_strategy(cls, v: str) -> str:
        strategies = ["strict", "lenient"]
        if v not in strategies:
            raise ValueError(f"无效选择器策略: {v}, 必须是 {strategies}")
        return v

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
    def from_env(cls) -> Dict[str, Any]:
        """
        从环境变量构建配置字典（无前缀要求，读取所有环境变量）。
        支持嵌套：使用双下划线 __ 表示嵌套层级，例如 BROWSER__HEADLESS=true 映射到 browser.headless。
        """
        env_data = {}
        for key, value in os.environ.items():
            # 转换为小写，便于匹配模型字段（模型字段为小写蛇形命名）
            clean_key = key.lower()
            
            # 处理嵌套分隔符 __
            if "__" in clean_key:
                parts = clean_key.split("__")
                current = env_data
                for part in parts[:-1]:
                    current = current.setdefault(part, {})
                current[parts[-1]] = cls._parse_env_value(value)
            else:
                env_data[clean_key] = cls._parse_env_value(value)
        return env_data

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

    model_config = ConfigDict(protected_namespaces=(), extra="ignore")


# ========== 配置管理器 ==========
class ConfigManager:
    """统一配置管理器 - 聚合 YAML、环境变量、命令行覆盖"""

    def __init__(self):
        self._config: Optional[AppConfig] = None
        self._yaml_loader = YamlLoader()
        self._env_loader = EnvLoader(enable_auto_optimize=True)
        self._overrides: Dict[str, Any] = {}
        self._initialized = False

    def _load_full_config(self) -> AppConfig:
        """加载并合并所有配置源"""
        # 1. 运行环境自适应优化（会修改 os.environ）
        self._env_loader.load()

        # 2. 加载 YAML 基础配置（按环境）
        env_name = self._overrides.get("env") or os.getenv("ENV", "dev")
        yaml_config = self._yaml_loader.load_environment(env=env_name)

        # 3. 从环境变量获取覆盖字典（无前缀，读取所有环境变量）
        env_overrides = AppConfig.from_env()

        # 4. 深度合并：YAML 被环境变量覆盖
        merged_dict = self._deep_merge(yaml_config, env_overrides)

        # 5. 应用命令行覆盖（优先级最高）
        final_dict = self._deep_merge(merged_dict, self._overrides)

        # 6. 验证并返回最终配置
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
        """通过点号路径获取嵌套配置，如 settings.get('timeouts.page_load')"""
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

    def validate(self) -> None:
        """显式验证配置（初始化时已做）"""
        if self._config is None:
            self.initialize()

    def to_yaml(self) -> str:
        """导出当前配置为 YAML（隐藏敏感字段）"""
        if self._config is None:
            self.initialize()
        data = self._config.model_dump(exclude={"admin_password", "api_secret_key"})
        import yaml
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def reload(self) -> None:
        """热重载配置（清空缓存并重新加载）"""
        self._yaml_loader.clear_cache()
        self._config = None
        self._initialized = False
        self.initialize()


# ========== 全局单例 ==========
settings = ConfigManager()

if __name__ == "__main__":
    print(settings.env)
    print(settings.username)
    print(settings.password)
    print(settings.browser)
    print(settings.to_yaml())
