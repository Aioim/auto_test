"""配置管理模块"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Set
import threading

# 获取项目根目录
try:
    # 尝试从 src 目录开始的路径
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
except Exception:
    # 回退到当前文件所在目录
    PROJECT_ROOT = Path(__file__).parent.resolve()

class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    def get_env_var(name: str, default: Any = None) -> Any:
        """获取环境变量"""
        return os.environ.get(name, default)
    
    @staticmethod
    def parse_bool(value: Any) -> bool:
        """解析布尔值"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'y')
        return bool(value)
    
    @staticmethod
    def load_from_settings():
        """从settings模块加载配置"""
        config = {
            'log_dir': PROJECT_ROOT / 'logs',
            'log_level': 'INFO',
            'log_file': 'test_run.log',
            'env': 'development'
        }
        
        try:
            # 尝试从 src.config 加载
            try:
                from src.config import settings
                config['log_dir'] = getattr(settings.log, 'log_dir', config['log_dir'])
                config['log_level'] = getattr(settings.log, 'log_level', config['log_level'])
                config['log_file'] = getattr(settings.log, 'log_file', config['log_file'])
                config['env'] = getattr(settings, 'env', config['env'])
            except ImportError:
                # 尝试从 config 加载（兼容旧版）
                try:
                    from src.config import settings
                    config['log_dir'] = getattr(settings.log, 'log_dir', config['log_dir'])
                    config['log_level'] = getattr(settings.log, 'log_level', config['log_level'])
                    config['log_file'] = getattr(settings.log, 'log_file', config['log_file'])
                    config['env'] = getattr(settings, 'env', config['env'])
                except ImportError:
                    pass
        except (ImportError, AttributeError) as e:
            # 静默失败，使用默认配置
            pass
        
        return config
    
    @staticmethod
    def load_from_env():
        """从环境变量加载配置"""
        return {
            'log_dir': ConfigLoader.get_env_var('LOG_DIR', PROJECT_ROOT / 'logs'),
            'log_level': ConfigLoader.get_env_var('LOG_LEVEL', 'INFO').upper(),
            'log_file': ConfigLoader.get_env_var('LOG_FILE', 'test_run.log'),
            'env': ConfigLoader.get_env_var('ENV', 'development'),
            'backup_count': int(ConfigLoader.get_env_var('LOG_BACKUP_COUNT', 7)),
            'max_bytes': int(ConfigLoader.get_env_var('LOG_MAX_BYTES', 10 * 1024 * 1024)),
            'perf_max_bytes': int(ConfigLoader.get_env_var('LOG_PERF_MAX_BYTES', 5 * 1024 * 1024)),
            'enable_colors': ConfigLoader.parse_bool(ConfigLoader.get_env_var('LOG_ENABLE_COLORS', False)),
            'config_path': ConfigLoader.get_env_var('LOG_CONFIG_PATH', PROJECT_ROOT / 'log_config.yaml'),
            'enable_emergency_response': ConfigLoader.parse_bool(ConfigLoader.get_env_var('LOG_ENABLE_EMERGENCY_RESPONSE', False)),
            'quiet': ConfigLoader.parse_bool(ConfigLoader.get_env_var('LOG_QUIET', False)),
            'replace_main_with_filename': ConfigLoader.parse_bool(ConfigLoader.get_env_var('LOG_REPLACE_MAIN_WITH_FILENAME', True))
        }

class LogConfig:
    """集中式配置管理"""
    # 默认配置
    LOG_DIR: Path = PROJECT_ROOT / 'logs'
    LOG_LEVEL: str = 'INFO'
    MAIN_LOG_FILE: str = 'test_run.log'
    BACKUP_COUNT: int = 7
    MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    PERF_MAX_BYTES: int = 5 * 1024 * 1024  # 5MB
    ENABLE_COLORS: bool = False
    ENV: str = 'development'
    SENSITIVE_KEYS: Set[str] = {
        'password', 'pwd', 'pass', 'secret', 'token', 'api_key', 'apikey',
        'authorization', 'cookie', 'x-api-key', 'access_token', 'refresh_token',
        'new_password', 'old_password', 'confirm_password', 'credit_card',
        'ssn', 'social_security', 'passport', 'cvv', 'pin', 'private_key'
    }
    CONFIG_PATH: Optional[Path] = None
    ENABLE_EMERGENCY_RESPONSE: bool = False
    QUIET: bool = False
    REPLACE_MAIN_WITH_FILENAME: bool = True
    
    # 有效的日志级别
    VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    
    @classmethod
    def initialize(cls):
        """初始化配置"""
        # 加载配置（完全依赖settings模块）
        settings_config = ConfigLoader.load_from_settings()
        
        # 使用settings配置
        log_dir = settings_config['log_dir']
        cls.LOG_DIR = Path(log_dir) if not isinstance(log_dir, Path) else log_dir
        cls.LOG_LEVEL = settings_config['log_level'].upper()
        cls.MAIN_LOG_FILE = settings_config['log_file']
        cls.ENV = settings_config['env']
        
        # 其他配置使用默认值（如果需要从环境变量加载，应该通过manager.py的settings加载）
        cls.BACKUP_COUNT = 7
        cls.MAX_BYTES = 10 * 1024 * 1024
        cls.PERF_MAX_BYTES = 5 * 1024 * 1024
        cls.ENABLE_COLORS = False
        
        # 基于环境的默认值
        cls.ENABLE_EMERGENCY_RESPONSE = cls.ENV != "development"
        cls.QUIET = cls.ENV == "production"
        cls.REPLACE_MAIN_WITH_FILENAME = True
        
        # 配置文件路径（暂时不使用，完全依赖settings）
        cls.CONFIG_PATH = None
        
        # 验证配置
        cls._validate_config()
        
        # 确保日志目录存在
        try:
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            if not cls.QUIET:
                print(f"⚠️  Failed to create log directory: {e}", file=sys.stderr)
    
    @classmethod
    def _validate_config(cls):
        """验证配置"""
        # 验证日志级别
        if cls.LOG_LEVEL not in cls.VALID_LOG_LEVELS:
            if not cls.QUIET:
                print(f"⚠️  Invalid log level: {cls.LOG_LEVEL}, using INFO instead", file=sys.stderr)
            cls.LOG_LEVEL = 'INFO'
        
        # 验证备份计数
        if cls.BACKUP_COUNT < 1:
            if not cls.QUIET:
                print(f"⚠️  Invalid backup count: {cls.BACKUP_COUNT}, using 7 instead", file=sys.stderr)
            cls.BACKUP_COUNT = 7
        
        # 验证文件大小
        if cls.MAX_BYTES < 1024:
            if not cls.QUIET:
                print(f"⚠️  Invalid max bytes: {cls.MAX_BYTES}, using 10MB instead", file=sys.stderr)
            cls.MAX_BYTES = 10 * 1024 * 1024
        
        if cls.PERF_MAX_BYTES < 1024:
            if not cls.QUIET:
                print(f"⚠️  Invalid perf max bytes: {cls.PERF_MAX_BYTES}, using 5MB instead", file=sys.stderr)
            cls.PERF_MAX_BYTES = 5 * 1024 * 1024
    
    @classmethod
    def load_config(cls, config_path: Optional[Path] = None):
        """从文件加载配置"""
        if config_path is None:
            config_path = cls.CONFIG_PATH
        if config_path and config_path.exists():
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                if isinstance(config, dict):
                    cls.from_dict(config)
                    # 重新验证配置
                    cls._validate_config()
            except ImportError as e:
                if not cls.QUIET:
                    print(f"⚠️  YAML module not found, skipping config file: {e}", file=sys.stderr)
            except Exception as e:
                if not cls.QUIET:
                    print(f"⚠️  Failed to load config from {config_path}: {e}", file=sys.stderr)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]):
        """从字典加载配置"""
        mapping = {
            'log_dir': 'LOG_DIR',
            'log_level': 'LOG_LEVEL',
            'log_file': 'MAIN_LOG_FILE',
            'backup_count': 'BACKUP_COUNT',
            'max_bytes': 'MAX_BYTES',
            'perf_max_bytes': 'PERF_MAX_BYTES',
            'enable_colors': 'ENABLE_COLORS',
            'env': 'ENV',
            'sensitive_keys': 'SENSITIVE_KEYS',
            'config_path': 'CONFIG_PATH',
            'enable_emergency_response': 'ENABLE_EMERGENCY_RESPONSE',
            'quiet': 'QUIET',
            'replace_main_with_filename': 'REPLACE_MAIN_WITH_FILENAME'
        }
        
        for key, attr in mapping.items():
            if key in config_dict:
                value = config_dict[key]
                if attr == 'LOG_DIR' and not isinstance(value, Path):
                    value = Path(value)
                if attr == 'CONFIG_PATH' and not isinstance(value, Path):
                    value = Path(value)
                if attr == 'SENSITIVE_KEYS' and isinstance(value, list):
                    value = set(value)
                setattr(cls, attr, value)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return getattr(cls, key.upper(), default)
    
    @classmethod
    def refresh(cls):
        """刷新配置"""
        cls.initialize()

# 初始化配置
LogConfig.initialize()

# 确保日志目录存在
try:
    LogConfig.LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
