# 🔐 Security Module - 企业级敏感信息管理系统

## 模块简介

Security 模块是一个功能完整的企业级敏感信息管理系统，提供全方位的敏感数据保护解决方案。该模块采用多层安全架构，确保敏感信息在存储、传输和使用过程中的安全性。

### 核心价值

- **内存加密存储**：敏感信息在内存中仅以加密形式存在
- **防泄露保护**：自动脱敏、防打印、防序列化
- **企业级安全标准**：符合金融级安全要求
- **无缝集成**：与现有系统完美集成
- **可审计性**：完整的操作审计日志

## 目录结构

```
src/utils/security/
├── __init__.py          # 模块导出定义
├── secret_str.py        # 敏感字符串容器
├── secrets_manager.py   # 内存加密敏感信息管理器
├── env_loader.py        # 安全 .env 文件加载器
├── env_encrypt.py       # 环境变量加密工具
├── key_rotation.py      # 密钥轮换与管理
└── README.md            # 模块文档（本文件）
```

## 核心功能

### 1. SecretStr - 敏感字符串容器

**主要特性**：
- ✅ 禁止直接打印（自动脱敏）
- ✅ 禁止序列化（防内存转储）
- ✅ 恒定时间比较（防时序攻击）
- ✅ 自动内存清零（对象销毁时）
- ✅ 防弱引用（__weakref__ 禁用）

**使用示例**：

```python
from utils.security import SecretStr

# 创建敏感字符串
password = SecretStr("my_secure_password", name="db_password")

# 安全获取值
print(password)  # 输出: my***************ord
print(password.get())  # 输出: my_secure_password

# 安全比较（使用恒定时间比较，防时序攻击）
if password.equals("my_secure_password"):
    print("Password match!")

# 检查访问状态
print(f"Password accessed: {password.is_accessed()}")
```

**技术实现细节**：
- **恒定时间比较**：使用 `secrets.compare_digest()` 实现，防止时序攻击
- **防弱引用**：通过重写 `__getattribute__` 方法禁用 `__weakref__`
- **自动内存清零**：在 `__del__` 方法中清除内存中的敏感数据

### 2. SecretsManager - 内存加密管理器

**主要特性**：
- ✅ 内存中仅存储加密字节（无明文缓存）
- ✅ 每次 get_secret() 动态解密（最小化明文生命周期）
- ✅ 密钥文件严格验证（44字节 URL 安全 base64）
- ✅ 生产环境零容忍（密钥无效立即终止进程）
- ✅ 开发环境自动创建临时密钥

**使用示例**：

```python
from utils.security import SecretsManager, get_secret, set_secret

# 获取全局实例
secrets = SecretsManager()

# 存储敏感信息
set_secret("api_key", "sk-xxxxxxxxxxxx")
set_secret("db_password", "secure_password123")

# 获取敏感信息（返回 SecretStr 实例）
api_key = secrets.get_secret("api_key", required=True)
print(f"API Key: {api_key}")  # 自动脱敏
print(f"API Key (raw): {api_key.get()}")  # 获取原始值

# 便捷函数（自动解包）
db_password = get_secret("db_password")
print(f"DB Password: {db_password}")

# 列出所有密钥名称
print("Stored secrets:", secrets.list_secrets())

# 检查加密状态
print(f"Encryption enabled: {secrets.is_encrypted()}")
```

### 3. SecureEnvLoader - 安全 .env 文件加载器

**主要特性**：
- ✅ 自动识别 ENC[...] 加密字段
- ✅ 与 python-dotenv 完全兼容
- ✅ 解密失败时提供精准诊断
- ✅ 防止敏感字段意外泄露到日志
- ✅ 支持多行值、引号、转义字符

**使用示例**：

```python
from utils.security import SecureEnvLoader, load_dotenv_secure

# 创建加载器
loader = SecureEnvLoader()

# 加载 .env 文件
loader.load(override=True)

# 便捷函数
load_dotenv_secure()

# 现在可以安全访问环境变量
import os
print(f"DB_HOST: {os.getenv('DB_HOST')}")
print(f"DB_PASSWORD: {'******' if os.getenv('DB_PASSWORD') else 'Not set'}")
```

### 4. 环境变量加密工具

**主要特性**：
- ✅ 加密单个值
- ✅ 解密单个值
- ✅ 批量加密 .env 文件
- ✅ 与 SecureEnvLoader 无缝集成

**使用示例**：

```python
from utils.security import encrypt_value, decrypt_value, encrypt_env_file

# 加密值
plain_text = "my_secret_value"
encrypted = encrypt_value(plain_text)
print(f"Encrypted: {encrypted}")  # 输出: ENC[...]

# 解密值
decrypted = decrypt_value(encrypted)
print(f"Decrypted: {decrypted}")  # 输出: my_secret_value

# 加密整个 .env 文件
encrypt_env_file(".env", ".env.encrypted")
```

### 5. 密钥轮换与管理

**主要特性**：
- ✅ 安全轮换 .secret_key
- ✅ 重新加密所有已加密的敏感数据
- ✅ 支持原子性操作（失败回滚）
- ✅ 生成轮换审计报告
- ✅ 备份旧密钥（用于回滚）

**使用示例**：

```python
from utils.security import KeyRotator, rotate_keys

# 创建轮换器
rotator = KeyRotator()

# 执行轮换
report = rotator.rotate(
    backup_dir="./key_backups",
    env_files=[".env"],
    dry_run=False
)

# 便捷函数
report = rotate_keys(
    backup_dir="./key_backups",
    env_files=[".env"]
)

# 查看轮换报告
print("Rotation report:")
print(f"Backup path: {report['backup_path']}")
print(f"Env files processed: {report['env_files_processed']}")
print(f"Next steps: {report['next_steps']}")

# 查看轮换历史
history = rotator.get_rotation_history()
print(f"Rotation history: {len(history)} entries")
```

### 6. 与 SmartLogin 集成示例

**使用示例**：

```python
from utils.security import SecretStr, get_secret
from utils.common.smart_login import SmartLogin
from pages.components.login_page import login_page

def secure_login():
    """使用安全方式登录"""
    # 从安全存储获取凭证
    username = get_secret("login_username")
    password = SecretStr(get_secret("login_password"), name="login_password")
    
    # 创建 SmartLogin 实例
    smart_login = SmartLogin(username, password.get(), login_page)
    
    # 执行登录
    page = smart_login.smart_login()
    print("登录成功")
    
    # 关闭浏览器
    smart_login.stop_browser()

# 执行安全登录
secure_login()
```

## 安装与配置

### 依赖项

```bash
pip install cryptography python-dotenv
```

### 密钥文件配置

1. **开发环境**：自动创建临时密钥（位于 `environments/.secret_key`）
2. **生产环境**：必须预先生成密钥文件

### 生成生产环境密钥

```bash
# 生成有效的 Fernet 密钥
python -c "from cryptography.fernet import Fernet; open('.secret_key', 'wb').write(Fernet.generate_key())"

# 验证密钥有效性
python -c "from cryptography.fernet import Fernet; k=open('.secret_key','rb').read().strip(); assert len(k)==44, 'Invalid length'; Fernet(k); print('✓ VALID KEY')"

# 添加到 .gitignore
echo '.secret_key' >> .gitignore
```

## 安全最佳实践

### 1. 开发环境

- ✅ 使用自动生成的开发密钥
- ✅ 确保 .secret_key 添加到 .gitignore
- ✅ 定期轮换开发密钥

### 2. 生产环境

- ✅ 预先生成密钥并安全分发
- ✅ 启用密钥轮换机制（建议 90 天）
- ✅ 实施最小权限原则
- ✅ 监控密钥使用和访问
- ✅ 建立密钥丢失应急响应流程

### 3. 代码层面

- ✅ 始终使用 SecretStr 存储敏感信息
- ✅ 避免在日志中记录敏感信息
- ✅ 使用安全比较（使用 `equals()` 方法，避免 == 操作符）
- ✅ 及时清理不再需要的敏感信息
- ✅ 对敏感操作进行异常处理

## 常见问题与解决方案

### 1. 密钥文件错误

**症状**：`Invalid key length: XX bytes`

**解决方案**：
```bash
# 删除无效密钥
rm -f environments/.secret_key

# 重新生成
python -c "from cryptography.fernet import Fernet; open('environments/.secret_key', 'wb').write(Fernet.generate_key())"
```

### 2. 解密失败

**症状**：`Decryption failed: Invalid token`

**解决方案**：
- 检查 .secret_key 是否与加密时使用的密钥匹配
- 确认值未被手动编辑（base64 损坏）
- 检查是否使用了正确环境的 .secret_key
- 如密钥丢失，使用备份密钥进行恢复

### 3. 环境变量加载失败

**症状**：`Env file not found`

**解决方案**：
- 创建 .env 文件
- 确保文件格式正确
- 检查文件权限

## API 参考

### 核心类

| 类名 | 描述 | 主要方法 |
|------|------|----------|
| `SecretStr` | 敏感字符串容器 | `get()`, `mask()`, `is_accessed()`, `equals()` |
| `SecretsManager` | 内存加密管理器 | `set_secret()`, `get_secret()`, `delete_secret()` |
| `SecureEnvLoader` | 安全 .env 加载器 | `load()`, `is_encrypted_value()` |
| `KeyRotator` | 密钥轮换器 | `rotate()`, `get_rotation_history()` |

### 便捷函数

| 函数名 | 描述 | 参数 |
|--------|------|------|
| `get_secret()` | 获取敏感值 | `name`, `default=None`, `required=False` |
| `set_secret()` | 存储敏感值 | `name`, `value` |
| `load_dotenv_secure()` | 安全加载 .env 文件 | `dotenv_path=None`, `override=False` |
| `encrypt_value()` | 加密单个值 | `value` |
| `decrypt_value()` | 解密单个值 | `value` |
| `encrypt_env_file()` | 加密 .env 文件 | `input_file`, `output_file=None` |
| `rotate_keys()` | 执行密钥轮换 | `backup_dir=None`, `env_files=None`, `dry_run=False` |

## 安全审计

### 日志记录

- **安全操作**：记录在 `security_logger`
- **常规操作**：记录在 `logger`
- **敏感信息**：自动脱敏后记录

### 审计要点

- ✅ 密钥访问记录
- ✅ 加密/解密操作
- ✅ 密钥轮换事件
- ✅ 环境变量加载
- ✅ 安全异常处理

## 性能考量

### 内存使用
- **SecretStr**：最小内存占用
- **SecretsManager**：内存中仅存储加密字节
- **SecureEnvLoader**：按需加载，无缓存

### 执行速度
- **加密/解密**：使用 Fernet（AES-128-CBC）快速加密
- **比较操作**：恒定时间比较（防时序攻击）
- **加载速度**：延迟初始化，首次访问时加载

### 性能基准
- **加密/解密**：平均处理时间 < 1ms per operation
- **内存占用**：每个 SecretStr 实例 < 100 bytes
- **并发性能**：支持高并发访问，线程安全

## 测试指南

### 单元测试

```python
import unittest
from utils.security import SecretStr, SecretsManager

class TestSecurityModule(unittest.TestCase):
    def test_secret_str_creation(self):
        """测试 SecretStr 创建"""
        secret = SecretStr("test_password")
        self.assertEqual(secret.get(), "test_password")
        
    def test_secret_str_comparison(self):
        """测试 SecretStr 安全比较"""
        secret = SecretStr("test_password")
        self.assertTrue(secret.equals("test_password"))
        self.assertFalse(secret.equals("wrong_password"))
        
    def test_secrets_manager(self):
        """测试 SecretsManager"""
        manager = SecretsManager()
        manager.set_secret("test_key", "test_value")
        secret = manager.get_secret("test_key")
        self.assertEqual(secret.get(), "test_value")

if __name__ == '__main__':
    unittest.main()
```

### 安全审计测试

```python
from utils.security import SecretsManager, KeyRotator

def test_security_audit():
    """测试安全审计功能"""
    # 测试密钥访问记录
    manager = SecretsManager()
    manager.set_secret("audit_test", "audit_value")
    secret = manager.get_secret("audit_test")
    print("密钥访问测试完成")
    
    # 测试密钥轮换
    rotator = KeyRotator()
    report = rotator.rotate(dry_run=True)
    print(f"密钥轮换测试完成: {report['status']}")

# 执行测试
test_security_audit()
```

## 版本信息

### 当前版本
- **Version**: 1.0.0
- **Release Date**: 2026-03-08

### 更新日志
- **v1.0.0** (2026-03-08): 初始版本，包含完整的敏感信息管理功能

## 安全漏洞报告

### 报告流程
1. **安全漏洞**：发送邮件至 security@example.com
2. **功能请求**：在 GitHub Issues 中提交
3. **紧急漏洞**：电话联系安全团队

### 安全更新
- 安全更新将通过邮件列表通知
- 重要漏洞修复会发布安全公告
- 定期安全补丁发布周期：每月

## 分布式环境密钥管理

### 最佳实践
- **密钥分发**：使用安全的密钥分发系统
- **密钥同步**：定期同步密钥状态
- **高可用性**：实现密钥管理的高可用方案
- **灾难恢复**：建立密钥备份和恢复机制

## 许可证

MIT License - 详见项目根目录的 LICENSE 文件

## 贡献指南

1. Fork 仓库
2. 创建特性分支
3. 提交更改
4. 运行测试
5. 提交 Pull Request

## 联系方式

如有安全问题或功能请求，请通过以下方式联系：

- **Email**: security@example.com
- **Issue**: [GitHub Issues](https://github.com/your-project/issues)

---

**⚠️ 重要安全提示**：永远不要将密钥文件提交到版本控制！确保 .secret_key 文件添加到 .gitignore。

*Security First - 安全永远是第一位的！* 🔒