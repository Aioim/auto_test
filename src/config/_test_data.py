"""
企业级测试数据管理模块

特性：
- 多数据源支持（JSON/CSV/Excel/YAML/数据库）
- 数据工厂模式（动态生成）
- 数据隔离与清理
- 敏感数据加密/脱敏
- Schema 验证
- 缓存机制
- 国际化支持
- Faker 集成
- 与 pytest fixture 无缝集成
"""
import json
import csv
import os
import re
import hashlib
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union, Iterator
from datetime import datetime, timedelta
from enum import Enum
import uuid  # 标准库 UUID 模块（用于可靠生成）
import yaml  # PyYAML
from faker import Faker
from faker.providers import BaseProvider
import logging

from config import settings
from utils.logger import logger, security_logger


# ==================== 数据类型枚举 ====================

class DataType(Enum):
    """测试数据类型"""
    USER = "user"
    PRODUCT = "product"
    ORDER = "order"
    PAYMENT = "payment"
    ADDRESS = "address"
    CONTACT = "contact"
    DOCUMENT = "document"
    SESSION = "session"
    API_KEY = "api_key"
    CUSTOM = "custom"


class DataEnvironment(Enum):
    """数据环境"""
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


# ==================== 自定义 Faker Provider ====================

class AutomationProvider(BaseProvider):
    """自动化测试专用 Faker Provider"""

    def test_username(self) -> str:
        """生成测试用户名"""
        return f"testuser_{self.random_number(digits=6)}"

    def test_email(self, domain: str = "example.com") -> str:
        """生成测试邮箱"""
        username = self.bothify("testuser_####")
        return f"{username}@{domain}"

    def test_phone(self, prefix: str = "138") -> str:
        """生成测试手机号"""
        return f"{prefix}{self.random_number(digits=8)}"

    def order_id(self) -> str:
        """生成订单ID"""
        return f"ORD{datetime.now().strftime('%Y%m%d')}{self.random_number(digits=6)}"

    def transaction_id(self) -> str:
        """生成交易ID"""
        return f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{self.random_number(digits=4)}"

    def uuid_short(self) -> str:
        """
        生成短UUID（8位）

        注意：使用标准库 uuid 保证可靠性，不依赖 Faker 的 uuid4()
        因为 Faker 的 uuid4() 返回字符串，无 .hex 属性
        """
        return uuid.uuid4().hex[:8]  # 直接使用标准库生成可靠 UUID


# ==================== 数据验证器 ====================

class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """验证手机号格式（中国大陆）"""
        pattern = r'^1[3-9]\d{9}$'
        return re.match(pattern, phone) is not None

    @staticmethod
    def validate_password(password: str) -> bool:
        """验证密码强度（至少8位，包含字母和数字）"""
        if len(password) < 8:
            return False
        if not re.search(r'[A-Za-z]', password):
            return False
        if not re.search(r'\d', password):
            return False
        return True

    @staticmethod
    def validate_schema(data: Dict, schema: Dict) -> List[str]:
        """
        验证数据是否符合 Schema

        Args:
            data: 待验证数据
            schema: Schema 定义 {field: type}

        Returns:
            List[str]: 错误列表
        """
        errors = []

        for field, expected_type in schema.items():
            if field not in data:
                errors.append(f"Missing field: {field}")
                continue

            actual_value = data[field]
            if actual_value is None and expected_type is not type(None):
                errors.append(f"Field '{field}' is None but expected {expected_type}")
                continue

            if not isinstance(actual_value, expected_type):
                errors.append(
                    f"Field '{field}' type mismatch: "
                    f"expected {expected_type.__name__}, got {type(actual_value).__name__}"
                )

        return errors


# ==================== 敏感数据加密/脱敏 ====================

class DataSecurity:
    """数据安全处理"""

    @staticmethod
    def encrypt(value: str, key: str = "default_key") -> str:
        """简单加密（生产环境应使用专业加密库）"""
        # 注意：此为示例实现，生产环境应使用 cryptography 等专业库
        combined = f"{key}:{value}"
        return base64.b64encode(combined.encode()).decode()

    @staticmethod
    def decrypt(encrypted_value: str, key: str = "default_key") -> str:
        """解密"""
        try:
            decoded = base64.b64decode(encrypted_value).decode()
            stored_key, value = decoded.split(":", 1)
            if stored_key != key:
                raise ValueError("Invalid decryption key")
            return value
        except Exception as e:
            logger.warning(f"Decryption failed: {e}")
            return "******"

    @staticmethod
    def mask(value: str, visible_start: int = 3, visible_end: int = 4) -> str:
        """脱敏处理（保留首尾）"""
        if not value or len(value) <= visible_start + visible_end:
            return "******"

        masked_length = len(value) - visible_start - visible_end
        return f"{value[:visible_start]}{'*' * masked_length}{value[-visible_end:]}"

    @staticmethod
    def mask_email(email: str) -> str:
        """邮箱脱敏"""
        if "@" not in email:
            return "******@***.com"

        local, domain = email.split("@", 1)
        masked_local = DataSecurity.mask(local, 1, 1) if len(local) > 2 else "***"
        domain_parts = domain.split(".")
        masked_domain = f"***.{domain_parts[-1]}" if len(domain_parts) > 1 else "***"

        return f"{masked_local}@{masked_domain}"


# ==================== 数据工厂 ====================

class DataFactory:
    """测试数据工厂"""

    def __init__(self, locale: str = "zh_CN"):
        self.faker = Faker(locale)
        self.faker.add_provider(AutomationProvider)
        self._cache: Dict[str, Any] = {}

    def create_user(
        self,
        role: str = "user",
        locale: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """创建用户数据"""
        faker = self.faker if locale is None else Faker(locale or "zh_CN")

        user = {
            "id": kwargs.get("id", str(uuid.uuid4())),  # 使用标准库生成可靠 UUID
            "username": kwargs.get("username", faker.test_username()),
            "email": kwargs.get("email", faker.test_email()),
            "password": kwargs.get("password", faker.password(length=12)),
            "fullname": kwargs.get("fullname", faker.name()),
            "phone": kwargs.get("phone", faker.test_phone()),
            "role": role,
            "created_at": kwargs.get("created_at", datetime.now().isoformat()),
            "is_active": kwargs.get("is_active", True),
            "metadata": kwargs.get("metadata", {})
        }

        # 添加角色特定字段
        if role == "admin":
            user["permissions"] = ["admin", "user_management", "system_config"]
        elif role == "vip":
            user["vip_level"] = kwargs.get("vip_level", 1)
            user["vip_expiry"] = kwargs.get(
                "vip_expiry",
                (datetime.now() + timedelta(days=365)).isoformat()
            )

        return user

    def create_product(
        self,
        category: str = "electronics",
        **kwargs
    ) -> Dict[str, Any]:
        """创建产品数据"""
        product = {
            "id": kwargs.get("id", f"PROD{self.faker.random_number(digits=8)}"),
            "name": kwargs.get("name", f"Test Product {self.faker.word()}"),
            "category": category,
            "price": kwargs.get("price", round(self.faker.random_number(digits=3) + 9.99, 2)),
            "stock": kwargs.get("stock", self.faker.random_int(min=0, max=1000)),
            "description": kwargs.get("description", self.faker.text(max_nb_chars=200)),
            "sku": kwargs.get("sku", f"SKU{self.faker.random_number(digits=6)}"),
            "images": kwargs.get("images", [self.faker.image_url()]),
            "created_at": kwargs.get("created_at", datetime.now().isoformat()),
            "is_active": kwargs.get("is_active", True)
        }

        # 类别特定字段
        if category == "electronics":
            product["specs"] = {
                "brand": kwargs.get("brand", self.faker.company()),
                "model": kwargs.get("model", self.faker.bothify("Model ##?#")),
                "color": kwargs.get("color", self.faker.color_name())
            }
        elif category == "books":
            product["specs"] = {
                "author": kwargs.get("author", self.faker.name()),
                "isbn": kwargs.get("isbn", self.faker.isbn13()),
                "publisher": kwargs.get("publisher", self.faker.company()),
                "pages": kwargs.get("pages", self.faker.random_int(min=100, max=1000))
            }

        return product

    def create_order(
        self,
        user_id: str,
        product_ids: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """创建订单数据"""
        if product_ids is None:
            product_ids = [f"PROD{self.faker.random_number(digits=8)}"]

        order = {
            "id": kwargs.get("id", self.faker.order_id()),
            "user_id": user_id,
            "products": kwargs.get("products", [
                {"product_id": pid, "quantity": self.faker.random_int(min=1, max=5)}
                for pid in product_ids
            ]),
            "total_amount": kwargs.get("total_amount", round(sum(
                p.get("price", 100) * p.get("quantity", 1)
                for p in kwargs.get("products", [])
            ), 2)),
            "status": kwargs.get("status", "pending"),
            "shipping_address": kwargs.get("shipping_address", self.create_address()),
            "payment_method": kwargs.get("payment_method", "credit_card"),
            "created_at": kwargs.get("created_at", datetime.now().isoformat()),
            "updated_at": kwargs.get("updated_at", datetime.now().isoformat()),
            # 修正：使用标准库生成可靠 transaction_id
            "transaction_id": kwargs.get("transaction_id", uuid.uuid4().hex)
        }

        return order

    def create_address(self, **kwargs) -> Dict[str, Any]:
        """创建地址数据"""
        return {
            "recipient": kwargs.get("recipient", self.faker.name()),
            "phone": kwargs.get("phone", self.faker.test_phone()),
            "province": kwargs.get("province", "广东省"),
            "city": kwargs.get("city", "深圳市"),
            "district": kwargs.get("district", "南山区"),
            "street": kwargs.get("street", self.faker.street_address()),
            "postal_code": kwargs.get("postal_code", "518000"),
            "is_default": kwargs.get("is_default", True)
        }

    def create_payment(self, order_id: str, **kwargs) -> Dict[str, Any]:
        """创建支付数据"""
        return {
            "id": kwargs.get("id", self.faker.transaction_id()),
            "order_id": order_id,
            "amount": kwargs.get("amount", 100.00),
            "currency": kwargs.get("currency", "CNY"),
            "method": kwargs.get("method", "credit_card"),
            "status": kwargs.get("status", "completed"),
            # 修正：使用标准库生成可靠 transaction_id
            "transaction_id": kwargs.get("transaction_id", uuid.uuid4().hex),
            "paid_at": kwargs.get("paid_at", datetime.now().isoformat()),
            "metadata": kwargs.get("metadata", {})
        }

    def batch_create_users(self, count: int, role: str = "user") -> List[Dict]:
        """批量创建用户"""
        return [self.create_user(role=role) for _ in range(count)]

    def batch_create_products(self, count: int, category: str = "electronics") -> List[Dict]:
        """批量创建产品"""
        return [self.create_product(category=category) for _ in range(count)]


# ==================== 测试数据管理器 ====================

class TestDataManager:
    """测试数据管理器 - 核心类"""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or settings.log.log_dir / "test_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 数据存储
        self._data: Dict[str, Any] = {}
        self._cache: Dict[str, Any] = {}
        self._factories: Dict[str, DataFactory] = {}

        # 初始化默认数据
        self._load_default_data()

        # 初始化数据工厂
        self._init_factories()

        logger.info(f"TestDataManager initialized with data dir: {self.data_dir}")

    def _init_factories(self):
        """初始化数据工厂"""
        locales = ["zh_CN", "en_US", "ja_JP"]
        for locale in locales:
            self._factories[locale] = DataFactory(locale)

        # 默认工厂
        self._factories["default"] = DataFactory("zh_CN")

    def _load_default_data(self):
        """加载默认测试数据"""
        # 用户数据
        self._data["users"] = {
            "valid_user": {
                "username": "testuser",
                "password": "TestPass123!",
                "email": "test@example.com",
                "phone": "13800138000",
                "fullname": "测试用户"
            },
            "admin_user": {
                "username": "admin",
                "password": "AdminPass123!",
                "email": "admin@example.com",
                "role": "admin",
                "permissions": ["admin", "user_management"]
            },
            "vip_user": {
                "username": "vipuser",
                "password": "VipPass123!",
                "email": "vip@example.com",
                "role": "vip",
                "vip_level": 5
            },
            "locked_user": {
                "username": "locked",
                "password": "LockedPass123!",
                "email": "locked@example.com",
                "is_active": False
            },
            "expired_user": {
                "username": "expired",
                "password": "ExpiredPass123!",
                "email": "expired@example.com",
                "expiry_date": "2020-01-01"
            }
        }

        # 搜索关键词
        self._data["search_keywords"] = {
            "valid": ["Python", "人工智能", "Playwright", "自动化测试", "RPA"],
            "edge_cases": ["", " ", "a", "a" * 256],
            "special_chars": ["测试@#￥%", "Hello World!", "123456"],
            "invalid": ["zxcvbnmasdfghjkl", "1234567890!@#$%^&*()"]
        }

        # 产品数据
        self._data["products"] = {
            "electronics": [
                {"name": "无线耳机", "category": "electronics", "price": 299, "stock": 100},
                {"name": "智能手机", "category": "electronics", "price": 2999, "stock": 50},
                {"name": "笔记本电脑", "category": "electronics", "price": 5999, "stock": 30}
            ],
            "books": [
                {"name": "Python编程", "category": "books", "price": 89, "stock": 200},
                {"name": "自动化测试指南", "category": "books", "price": 129, "stock": 150}
            ],
            "clothing": [
                {"name": "T恤", "category": "clothing", "price": 99, "stock": 300},
                {"name": "牛仔裤", "category": "clothing", "price": 199, "stock": 200}
            ]
        }

        # 表单测试数据
        self._data["forms"] = {
            "valid_registration": {
                "username": "newuser123",
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
                "fullname": "新用户",
                "phone": "13900139000"
            },
            "invalid_emails": [
                "invalid-email",
                "@example.com",
                "test@",
                "test@.com",
                "test@@example.com"
            ],
            "invalid_passwords": [
                "short",           # 太短
                "nondigitpassword", # 无数字
                "12345678",        # 无字母
                ""                 # 空
            ]
        }

        # API 测试数据
        self._data["api"] = {
            "valid_tokens": [
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx",
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.yyyyy"
            ],
            "invalid_tokens": [
                "invalid_token",
                "",
                "Bearer ",
                "Basic base64string"
            ],
            "rate_limit": {
                "max_requests": 100,
                "window_seconds": 60
            }
        }

        # 国际化数据
        self._data["i18n"] = {
            "zh-CN": {
                "welcome": "欢迎",
                "submit": "提交",
                "cancel": "取消"
            },
            "en-US": {
                "welcome": "Welcome",
                "submit": "Submit",
                "cancel": "Cancel"
            },
            "ja-JP": {
                "welcome": "ようこそ",
                "submit": "送信",
                "cancel": "キャンセル"
            }
        }

        # 错误消息映射
        self._data["error_messages"] = {
            "invalid_credentials": {
                "zh-CN": "用户名或密码错误",
                "en-US": "Invalid username or password"
            },
            "user_locked": {
                "zh-CN": "账户已被锁定",
                "en-US": "Account is locked"
            },
            "user_expired": {
                "zh-CN": "账户已过期",
                "en-US": "Account has expired"
            }
        }

    # ==================== 基础数据访问 ====================

    def get(self, path: str, default: Any = None) -> Any:
        """
        获取测试数据

        Args:
            path: 数据路径，如 "users.valid_user.username"
            default: 默认值

        Returns:
            Any: 数据值
        """
        keys = path.split(".")
        data = self._data

        for key in keys:
            if isinstance(data, dict):
                data = data.get(key, default)
            elif isinstance(data, list):
                try:
                    idx = int(key)
                    data = data[idx] if idx < len(data) else default
                except (ValueError, IndexError):
                    return default
            else:
                return default

        return data

    def set(self, path: str, value: Any):
        """设置测试数据"""
        keys = path.split(".")
        data = self._data

        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]

        data[keys[-1]] = value

    def delete(self, path: str) -> bool:
        """删除测试数据"""
        keys = path.split(".")
        data = self._data

        for key in keys[:-1]:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return False

        if isinstance(data, dict) and keys[-1] in data:
            del data[keys[-1]]
            return True
        return False

    # ==================== 数据源加载 ====================

    def load_from_json(self, filepath: str) -> bool:
        """从 JSON 文件加载数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._data.update(data)
            logger.info(f"Loaded data from JSON: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load JSON data from {filepath}: {e}")
            return False

    def load_from_csv(self, filepath: str, key: str) -> bool:
        """从 CSV 文件加载数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = [row for row in reader]
                self._data[key] = data
            logger.info(f"Loaded {len(data)} records from CSV: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load CSV data from {filepath}: {e}")
            return False

    def load_from_excel(self, filepath: str, sheet_name: str = "Sheet1") -> bool:
        """从 Excel 文件加载数据（需要 openpyxl）"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath)
            sheet = wb[sheet_name]

            # 读取表头
            headers = [cell.value for cell in sheet[1]]

            # 读取数据
            data = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                record = {headers[i]: row[i] for i in range(len(headers)) if headers[i]}
                data.append(record)

            key = Path(filepath).stem
            self._data[key] = data
            logger.info(f"Loaded {len(data)} records from Excel: {filepath}")
            return True
        except ImportError:
            logger.warning("openpyxl not installed, skipping Excel support")
            return False
        except Exception as e:
            logger.error(f"Failed to load Excel data from {filepath}: {e}")
            return False

    def load_from_yaml(self, filepath: str) -> bool:
        """从 YAML 文件加载数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self._data.update(data)
            logger.info(f"Loaded data from YAML: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load YAML data from {filepath}: {e}")
            return False

    def load_from_db(
        self,
        connection_string: str,
        query: str,
        key: str
    ) -> bool:
        """从数据库加载数据（需要 SQLAlchemy）"""
        try:
            from sqlalchemy import create_engine
            engine = create_engine(connection_string)

            with engine.connect() as conn:
                result = conn.execute(query)
                data = [dict(row) for row in result.fetchall()]

            self._data[key] = data
            logger.info(f"Loaded {len(data)} records from database")
            return True
        except ImportError:
            logger.warning("SQLAlchemy not installed, skipping DB support")
            return False
        except Exception as e:
            logger.error(f"Failed to load DB  {e}")
            return False

    # ==================== 数据工厂接口 ====================

    def factory(self, locale: str = "default") -> DataFactory:
        """获取数据工厂"""
        return self._factories.get(locale, self._factories["default"])

    def create_user(self, role: str = "user", locale: str = "zh_CN", **kwargs) -> Dict:
        """创建用户（便捷方法）"""
        return self.factory(locale).create_user(role=role, **kwargs)

    def create_product(self, category: str = "electronics", **kwargs) -> Dict:
        """创建产品（便捷方法）"""
        return self.factory("zh_CN").create_product(category=category, **kwargs)

    def create_order(self, user_id: str, product_ids: Optional[List[str]] = None, **kwargs) -> Dict:
        """创建订单（便捷方法）"""
        return self.factory("zh_CN").create_order(user_id=user_id, product_ids=product_ids, **kwargs)

    # ==================== 特定数据获取 ====================

    def get_all_users(self) -> Dict[str, Dict]:
        """获取所有用户数据"""
        return self.get("users", {})

    def get_valid_users(self) -> List[Dict]:
        """获取有效用户列表"""
        users = self.get("users", {})
        return [
            user for key, user in users.items()
            if user.get("is_active", True) and "expired" not in key
        ]

    def get_search_keywords(self, category: str = "valid") -> List[str]:
        """获取搜索关键词"""
        return self.get(f"search_keywords.{category}", [])

    def get_products_by_category(self, category: str) -> List[Dict]:
        """按类别获取产品"""
        return self.get(f"products.{category}", [])

    def get_i18n_text(self, key: str, locale: str = "zh-CN") -> str:
        """获取国际化文本"""
        return self.get(f"i18n.{locale}.{key}", key)

    def get_error_message(self, error_key: str, locale: str = "zh-CN") -> str:
        """获取错误消息"""
        return self.get(f"error_messages.{error_key}.{locale}", f"Unknown error: {error_key}")

    # ==================== 数据验证 ====================

    def validate_user(self, user_data: Dict) -> List[str]:
        """验证用户数据"""
        schema = {
            "username": str,
            "password": str,
            "email": str,
            "phone": str
        }

        errors = DataValidator.validate_schema(user_data, schema)

        # 额外验证
        if "email" in user_data and not DataValidator.validate_email(user_data["email"]):
            errors.append(f"Invalid email format: {user_data['email']}")

        if "phone" in user_data and not DataValidator.validate_phone(user_data["phone"]):
            errors.append(f"Invalid phone format: {user_data['phone']}")

        if "password" in user_data and not DataValidator.validate_password(user_data["password"]):
            errors.append("Password does not meet complexity requirements")

        return errors

    def validate_product(self, product_data: Dict) -> List[str]:
        """验证产品数据"""
        schema = {
            "name": str,
            "category": str,
            "price": (int, float),
            "stock": int
        }

        return DataValidator.validate_schema(product_data, schema)

    # ==================== 敏感数据处理 ====================

    def get_masked_user(self, user_key: str) -> Dict:
        """获取脱敏后的用户数据"""
        user = self.get(f"users.{user_key}", {}).copy()

        if "password" in user:
            user["password"] = "******"
        if "email" in user:
            user["email"] = DataSecurity.mask_email(user["email"])
        if "phone" in user:
            user["phone"] = DataSecurity.mask(user["phone"], 3, 4)

        return user

    def encrypt_sensitive_fields(self, data: Dict, fields: List[str]) -> Dict:
        """加密敏感字段"""
        encrypted = data.copy()
        for field in fields:
            if field in encrypted:
                encrypted[field] = DataSecurity.encrypt(str(encrypted[field]))
        return encrypted

    def decrypt_sensitive_fields(self, data: Dict, fields: List[str]) -> Dict:
        """解密敏感字段"""
        decrypted = data.copy()
        for field in fields:
            if field in decrypted:
                decrypted[field] = DataSecurity.decrypt(str(decrypted[field]))
        return decrypted

    # ==================== 缓存管理 ====================

    def cache_set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        self._cache[key] = {
            "value": value,
            "expires_at": (datetime.now() + timedelta(seconds=ttl)) if ttl else None,
            "created_at": datetime.now()
        }

    def cache_get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self._cache:
            return None

        cache_entry = self._cache[key]

        # 检查过期
        if cache_entry["expires_at"] and datetime.now() > cache_entry["expires_at"]:
            del self._cache[key]
            return None

        return cache_entry["value"]

    def cache_clear(self):
        """清除缓存"""
        self._cache.clear()

    # ==================== 数据清理 ====================

    def cleanup_test_data(self, prefix: str = "test_"):
        """
        清理测试数据（删除以特定前缀开头的用户/产品等）

        注意：此方法仅清理内存中的测试数据，不操作真实数据库
        """
        cleaned = 0

        # 清理用户
        users = self.get("users", {})
        to_delete = [k for k in users.keys() if k.startswith(prefix)]
        for key in to_delete:
            del users[key]
            cleaned += 1

        # 清理产品（如果存储在内存中）
        # 实际项目中应调用 API 或数据库清理

        if cleaned > 0:
            security_logger.info(f"Cleaned up {cleaned} test data entries with prefix '{prefix}'")

        return cleaned

    def generate_cleanup_report(self) -> Dict:
        """生成数据清理报告"""
        users = self.get("users", {})
        test_users = [k for k in users.keys() if k.startswith("test_") or "temp" in k]

        return {
            "timestamp": datetime.now().isoformat(),
            "test_users_count": len(test_users),
            "test_users": test_users,
            "recommendation": "Run cleanup_test_data() to remove test users"
        }

    # ==================== 导出功能 ====================

    def export_to_json(self, filepath: str, indent: int = 2):
        """导出数据到 JSON 文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=indent)
            logger.info(f"Exported test data to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to export data to JSON: {e}")
            raise

    def export_to_yaml(self, filepath: str):
        """导出数据到 YAML 文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(self._data, f, allow_unicode=True)
            logger.info(f"Exported test data to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to export data to YAML: {e}")
            raise

    # ==================== 实用方法 ====================

    def generate_unique_email(self, base: str = "testuser") -> str:
        """生成唯一邮箱"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        return f"{base}_{timestamp}@example.com"

    def generate_unique_username(self, base: str = "user") -> str:
        """生成唯一用户名"""
        rand = self.factory().faker.random_number(digits=6)
        return f"{base}_{rand}"

    def generate_test_data_hash(self) -> str:
        """生成测试数据哈希（用于版本控制）"""
        data_str = json.dumps(self._data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()


# ==================== 全局测试数据实例 ====================

# 创建全局测试数据管理器实例
test_data = TestDataManager()

# 便捷函数（向后兼容）
def get_test_data(path: str, default: Any = None) -> Any:
    """获取测试数据（兼容旧代码）"""
    return test_data.get(path, default)


# ==================== Pytest Fixture 集成 ====================

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "test mark test as using test data")


# ==================== 导出公共 API ====================

__all__ = [
    "test_data",                    # 全局测试数据管理器
    "get_test_data",                # 便捷函数
    "TestDataManager",              # 测试数据管理器类
    "DataFactory",                  # 数据工厂
    "DataValidator",                # 数据验证器
    "DataSecurity",                 # 数据安全
    "DataType",                     # 数据类型枚举
    "DataEnvironment",              # 环境枚举
    "pytest_configure"              # Pytest 集成
]

if __name__=='__main__':
    # 1. 基础数据访问
    username = test_data.get("users.valid_user.username")
    keywords = test_data.get_search_keywords("valid")

    # 2. 动态生成唯一用户
    user = test_data.create_user(role="vip", locale="zh_CN")
    print(user["email"])  # testuser_123456@example.com

    # 3. 脱敏显示
    masked = test_data.get_masked_user("valid_user")
    print(masked["email"])  # tes***@example.com

    # 4. 数据验证
    errors = test_data.validate_user({"username": "test", "password": "weak"})
    assert len(errors) > 0  # 密码强度不足

    # 5. 国际化
    msg_zh = test_data.get_i18n_text("submit", "zh-CN")  # "提交"
    msg_en = test_data.get_i18n_text("submit", "en-US")  # "Submit"

    # 6. 批量创建
    users = test_data.factory().batch_create_users(10, role="user")

    # 7. 清理测试数据
    test_data.cleanup_test_data(prefix="test_")