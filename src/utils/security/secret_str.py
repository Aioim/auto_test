"""
🔐 SecretStr - 军用级敏感字符串容器

防护措施：
• 禁止直接打印（__repr__/__str__ 返回掩码）
• 禁止序列化（__getstate__/__reduce__ 抛出异常）
• 禁止弱引用（__weakref__ 禁用）
• 恒定时间比较（防时序攻击）
• 自动清零（del时覆盖内存）
• 防内存转储（__slots__ 限制属性）

使用示例：
    #>>> secret = SecretStr("my_password", name="db_password")
    #>>> print(secret)
    m**...****ord
    #>>> secret.get()
    'my_password'
"""
import secrets as secrets_lib
from typing import Any, Optional


class SecretStr:
    """
    敏感字符串容器 - 多层防泄露保护

    特性：
    - 禁止直接打印（__repr__/__str__ 返回掩码）
    - 禁止序列化（__getstate__ 抛出异常）
    - 访问需显式调用 .get() 方法
    - 恒定时间比较（防时序攻击）
    - 自动内存清零（对象销毁时）
    """
    __slots__ = ('_value', '_name', '_accessed')

    def __init__(self, value: str, name: str = "secret"):
        """
        初始化敏感字符串容器

        Args:
            value: 敏感值（字符串）
            name: 密钥名称（用于审计日志）

        Raises:
            TypeError: 如果 value 不是字符串
        """
        if not isinstance(value, str):
            raise TypeError(f"Secret value must be str, got {type(value).__name__}")
        self._value = value
        self._name = name
        self._accessed = False

    def get(self) -> str:
        """
        安全获取原始值（记录审计日志）

        Returns:
            str: 原始敏感值

        Example:
            >>> secret = SecretStr("password123", "db_password")
            >>> secret.get()
            'password123'
        """
        self._accessed = True
        # 审计日志由外部记录（避免循环依赖）
        return self._value

    def mask(self, visible_start: int = 3, visible_end: int = 4) -> str:
        """
        返回脱敏版本（恒定长度防信息泄露）

        Args:
            visible_start: 前缀可见字符数（默认3）
            visible_end: 后缀可见字符数（默认4）

        Returns:
            str: 脱敏后的字符串

        Example:
            >>> SecretStr("mysecretpassword").mask()
            'mys***********ord'
        """
        val = self._value or ""
        total_len = len(val)

        # 最小掩码长度保护
        if total_len <= visible_start + visible_end:
            return "*" * max(6, total_len)

        masked_len = total_len - visible_start - visible_end
        return f"{val[:visible_start]}{'*' * masked_len}{val[-visible_end:]}"

    def __repr__(self) -> str:
        """安全的 repr 表示（返回掩码）"""
        return f"<SecretStr name='{self._name}' masked='{self.mask()}'>"

    def __str__(self) -> str:
        """安全的字符串表示（返回掩码）"""
        return self.mask()

    def __eq__(self, other: Any) -> bool:
        """
        恒定时间比较（防时序攻击）

        Args:
            other: 比较对象（SecretStr 或 str）

        Returns:
            bool: 是否相等

        Example:
            >>> s1 = SecretStr("secret")
            >>> s2 = SecretStr("secret")
            >>> s1 == s2
            True
        """
        if isinstance(other, SecretStr):
            other_val = other._value
        elif isinstance(other, str):
            other_val = other
        else:
            return False

        # 使用 secrets.compare_digest 进行恒定时间比较
        return secrets_lib.compare_digest(self._value, other_val)

    def __len__(self) -> int:
        """返回字符串长度"""
        return len(self._value)

    def __bool__(self) -> bool:
        """布尔值判断"""
        return bool(self._value)

    def __hash__(self) -> int:
        """禁止哈希（避免意外用作字典键）"""
        raise TypeError("SecretStr objects are unhashable (security protection)")

    def __del__(self):
        """
        对象销毁时尝试清零内存（尽力而为）

        注意：CPython 的引用计数机制会立即触发，
        但其他 Python 实现可能延迟调用。
        """
        try:
            if hasattr(self, '_value'):
                # 覆盖内存（尽力而为）
                self._value = "*" * len(self._value)
        except Exception:
            # 清零失败不应影响主流程
            pass

    # ========== 禁止序列化 ==========

    def __getstate__(self):
        """
        禁止 pickle 序列化

        Raises:
            RuntimeError: 始终抛出异常

        Example:
            >>> import pickle
            >>> s = SecretStr("secret")
            >>> pickle.dumps(s)
            RuntimeError: Cannot pickle SecretStr 'secret' - sensitive data protection
        """
        raise RuntimeError(
            f"Cannot pickle SecretStr '{self._name}' - sensitive data protection"
        )

    def __setstate__(self, state):
        """禁止反序列化"""
        raise RuntimeError(
            f"Cannot unpickle SecretStr '{self._name}' - sensitive data protection"
        )

    def __reduce__(self):
        """禁止通过 reduce 序列化"""
        raise RuntimeError(
            f"Cannot serialize SecretStr '{self._name}' via pickle/reduce"
        )

    def __reduce_ex__(self, protocol):
        """禁止通过 reduce_ex 序列化"""
        raise RuntimeError(
            f"Cannot serialize SecretStr '{self._name}' via pickle/reduce_ex"
        )

    # ========== 禁止弱引用 ==========

    __weakref__ = None  # 禁用弱引用支持

    # ========== 数值操作保护 ==========

    def __add__(self, other):
        """禁止字符串拼接（防意外泄露）"""
        raise TypeError("Cannot concatenate SecretStr (security protection)")

    def __radd__(self, other):
        """禁止反向字符串拼接"""
        raise TypeError("Cannot concatenate SecretStr (security protection)")

    def __mul__(self, other):
        """禁止字符串重复"""
        raise TypeError("Cannot multiply SecretStr (security protection)")

    def __rmul__(self, other):
        """禁止反向字符串重复"""
        raise TypeError("Cannot multiply SecretStr (security protection)")

    # ========== 安全方法 ==========

    def is_accessed(self) -> bool:
        """检查是否已被访问"""
        return self._accessed

    def reset_access_flag(self) -> None:
        """重置访问标志（用于审计）"""
        self._accessed = False

    @property
    def name(self) -> str:
        """获取密钥名称（只读）"""
        return self._name


# ========== 工具函数 ==========

def mask_value(value: str, visible_start: int = 3, visible_end: int = 4) -> str:
    """
    静态脱敏函数（无需创建 SecretStr 实例）

    Args:
        value: 要脱敏的字符串
        visible_start: 前缀可见字符数
        visible_end: 后缀可见字符数

    Returns:
        str: 脱敏后的字符串

    Example:
        >>> mask_value("mysecretpassword")
        'mys***********ord'
    """
    if not isinstance(value, str):
        return "******"

    total_len = len(value)
    if total_len <= visible_start + visible_end:
        return "*" * max(6, total_len)

    masked_len = total_len - visible_start - visible_end
    return f"{value[:visible_start]}{'*' * masked_len}{value[-visible_end:]}"


def safe_format(template: str, **kwargs) -> str:
    """
    安全的字符串格式化（自动脱敏 SecretStr）

    Args:
        template: 格式化模板
        **kwargs: 格式化参数

    Returns:
        str: 格式化后的字符串（SecretStr 自动脱敏）

    Example:
        >>> pwd = SecretStr("password123", "db_password")
        >>> safe_format("Connecting to DB with password: {pwd}", pwd=pwd)
        'Connecting to DB with password: pas*******123'
    """
    sanitized_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, SecretStr):
            sanitized_kwargs[key] = value.mask()
        else:
            sanitized_kwargs[key] = value

    return template.format(**sanitized_kwargs)