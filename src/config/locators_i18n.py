"""
国际化定位器支持模块
提供页面元素文本的多语言映射功能
"""
import os
from pathlib import Path
from typing import Dict, Optional
import json
import yaml
from ._path import PROJECT_ROOT

# 默认本地化映射
DEFAULT_LOCATORS_I18N = {
    "zh": {
        "login.username": "用户名",
        "login.password": "密码",
        "login.submit": "登录",
        "dashboard.title": "控制台"
    },
    "en": {
        "login.username": "Username",
        "login.password": "Password",
        "login.submit": "Sign in",
        "dashboard.title": "Dashboard"
    }
}

class I18nManager:
    """国际化管理器"""
    
    def __init__(self):
        self._locales: Dict[str, Dict[str, str]] = DEFAULT_LOCATORS_I18N.copy()
        self._loaded_files: set[str] = set()
        self._default_locale = "zh"
    
    def load_from_file(self, file_path: str | Path) -> bool:
        """从文件加载国际化配置
        
        支持 JSON 和 YAML 格式
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            bool: 是否加载成功
        """
        file_path = Path(file_path)
        file_key = str(file_path.absolute())
        
        # 避免重复加载
        if file_key in self._loaded_files:
            return True
        
        if not file_path.exists():
            return False
        
        try:
            ext = file_path.suffix.lower()
            
            if ext in (".json",):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif ext in (".yaml", ".yml"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                return False
            
            # 合并配置
            if isinstance(data, dict):
                for locale, mappings in data.items():
                    if isinstance(locale, str) and isinstance(mappings, dict):
                        if locale not in self._locales:
                            self._locales[locale] = {}
                        self._locales[locale].update(mappings)
            
            self._loaded_files.add(file_key)
            return True
        except Exception:
            return False
    
    def load_from_directory(self, dir_path: str | Path) -> int:
        """从目录加载所有国际化配置文件
        
        Args:
            dir_path: 配置目录路径
            
        Returns:
            int: 加载成功的文件数
        """
        dir_path = Path(dir_path)
        if not dir_path.exists() or not dir_path.is_dir():
            return 0
        
        loaded_count = 0
        for file_path in dir_path.glob("*.{json,yaml,yml}"):
            if self.load_from_file(file_path):
                loaded_count += 1
        
        return loaded_count
    
    def get_text(self, key: str, locale: Optional[str] = None) -> str:
        """获取指定语言的文本
        
        Args:
            key: 文本键
            locale: 语言代码，默认为 None（使用默认语言）
            
        Returns:
            str: 本地化文本，如果未找到则返回空字符串
        """
        # 使用指定语言或默认语言
        target_locale = locale or self._default_locale
        
        # 先从指定语言获取
        if target_locale in self._locales:
            text = self._locales[target_locale].get(key, "")
            if text:
                return text
        
        # 如果指定语言未找到，尝试从默认语言获取
        if target_locale != self._default_locale and self._default_locale in self._locales:
            return self._locales[self._default_locale].get(key, "")
        
        return ""
    
    def set_default_locale(self, locale: str) -> None:
        """设置默认语言
        
        Args:
            locale: 语言代码
        """
        self._default_locale = locale
    
    def get_available_locales(self) -> list[str]:
        """获取可用的语言列表
        
        Returns:
            list[str]: 语言代码列表
        """
        return list(self._locales.keys())
    
    def clear_cache(self) -> None:
        """清除缓存，重新加载默认配置"""
        self._locales = DEFAULT_LOCATORS_I18N.copy()
        self._loaded_files.clear()


# 全局国际化管理器实例
i18n_manager = I18nManager()

# 尝试从默认位置加载配置
i18n_manager.load_from_directory(PROJECT_ROOT / "config" / "locales")
i18n_manager.load_from_file(PROJECT_ROOT / "config" / "locators_i18n.json")
i18n_manager.load_from_file(PROJECT_ROOT / "config" / "locators_i18n.yaml")


def get_text(key: str, locale: Optional[str] = None) -> str:
    """获取指定语言的文本
    
    Args:
        key: 文本键
        locale: 语言代码，默认为 None（使用默认语言）
        
    Returns:
        str: 本地化文本，如果未找到则返回空字符串
    """
    return i18n_manager.get_text(key, locale)