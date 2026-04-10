# Auth 模块文档

## 模块概述

Auth 模块是一个功能强大的认证和登录管理系统，为自动化测试提供了全面的登录状态管理和认证功能。它通过智能缓存和便捷的登录机制，简化了测试中的认证流程，提高了测试效率和稳定性。

**核心功能**：
- **智能登录**：自动管理登录状态，优先使用缓存，缓存无效时自动执行实时登录
- **登录状态缓存**：基于文件的登录状态缓存，支持多环境和多用户
- **Token 管理**：提供 API 测试的 Token 缓存和管理功能
- **环境变量管理**：支持从环境变量加载认证信息和配置
- **多种使用方式**：支持上下文管理器、装饰器、批量任务执行等多种使用方式

## 模块结构

Auth 模块包含以下文件：

- **__init__.py**：模块初始化文件
- **cache_utils.py**：浏览器登录状态缓存公共工具模块
- **login_cache.py**：API 测试的 Token 缓存模块
- **smart_login.py**：智能登录管理模块

## 核心功能

### 1. 智能登录 (`SmartLogin`)

**功能**：
- **自动缓存管理**：优先使用缓存的登录状态，缓存无效时自动执行实时登录
- **多环境支持**：为不同环境（如 beta, prod）维护独立的缓存
- **多种使用方式**：支持上下文管理器、装饰器、批量任务执行等
- **安全处理**：登录后立即清除内存中的密码，降低泄露风险
- **统一的登录成功等待机制**：支持 SPA 选择器或 URL 变化检测

**主要方法**：
- `smart_login()`：智能登录，优先尝试缓存，若无效则执行实时登录并保存缓存
- `execute_with_login(task_func, *args, **kwargs)`：执行带登录的任务，任务完成后自动关闭浏览器
- `execute_multiple_tasks(tasks)`：批量执行多个任务，每个任务独立启动浏览器
- `__enter__()` 和 `__exit__()`：支持上下文管理器，自动处理登录和资源释放

**装饰器**：
- `smart_login_decorator`：智能登录装饰器，自动处理登录和资源释放

### 2. 登录状态缓存 (`cache_utils`)

**功能**：
- **缓存路径生成**：与环境绑定的缓存文件路径生成
- **缓存有效性验证**：支持 cookie 快速检查和回退访问首页验证
- **线程安全的缓存保存**：使用 filelock 确保线程安全
- **环境变量加载**：支持 .env 和 .env.<env> 文件加载
- **角色凭证管理**：从环境变量获取不同角色的凭证
- **统一的登录成功等待机制**：支持 SPA 选择器或 URL 变化检测

**主要方法**：
- `get_storage_state_path(username, env=None)`：生成 storage_state 缓存文件路径
- `is_storage_state_valid(storage_path, browser, base_url)`：验证缓存文件是否有效
- `save_storage_state(page, username, env=None)`：保存当前页面的登录状态到缓存文件
- `wait_for_login_success(page, timeout=None)`：等待页面登录成功
- `load_env_by_name(env_name)`：根据环境名加载对应的 .env 文件
- `get_role_credentials(role, env=None)`：根据角色名从环境变量获取用户名密码
- `get_all_accounts_from_env(env_name)`：从环境变量中提取所有账号
- `clear_all_browser_caches(env=None)`：清除指定环境（或所有环境）的浏览器缓存文件

### 3. Token 缓存 (`login_cache`)

**功能**：
- **API 测试 Token 管理**：为 API 测试提供 Token 缓存功能
- **多进程支持**：使用 filelock 支持多进程并行
- **过期管理**：自动处理 Token 过期
- **安全存储**：将 Token 存储在文件系统中

**主要方法**：
- `get_token(key, max_age=None)`：获取缓存的 token
- `save_token(token, key)`：保存 token 到缓存
- `clear_token(key)`：清除指定 key 的 token 缓存
- `clear_all()`：清除所有 token 缓存文件及锁文件

**类封装**：
- `TokenCache`：Token 缓存的类封装，便于依赖注入

## 使用示例

### 1. 智能登录 - 上下文管理器

```python
from auth.smart_login import SmartLogin

# 使用上下文管理器
with SmartLogin(username="admin", password="password123") as (page, context):
    # 已登录，可直接操作页面
    page.goto("/dashboard")
    # 执行测试操作
    page.click("#create-button")
# 退出上下文时自动关闭浏览器
```

### 2. 智能登录 - 装饰器

```python
from auth.smart_login import smart_login_decorator

@smart_login_decorator(username="admin", password="password123", env="prod")
def test_dashboard(page, context):
    """测试仪表盘功能"""
    page.goto("/dashboard")
    # 执行测试操作
    assert page.locator("#welcome-message").text_content() == "Welcome, admin"

# 调用测试函数，自动处理登录
test_dashboard()
```

### 3. 智能登录 - 批量任务执行

```python
from auth.smart_login import SmartLogin

def task1(page, context):
    """任务 1：测试仪表盘"""
    page.goto("/dashboard")
    return page.locator("#stats").text_content()

def task2(page, context):
    """任务 2：测试用户管理"""
    page.goto("/users")
    return page.locator("#user-count").text_content()

# 创建 SmartLogin 实例
smart_login = SmartLogin(username="admin", password="password123")

# 批量执行任务
results = smart_login.execute_multiple_tasks([task1, task2])

# 处理结果
for i, result in enumerate(results, 1):
    if result["success"]:
        print(f"任务 {i} 成功: {result['result']}")
    else:
        print(f"任务 {i} 失败: {result['error']}")
```

### 4. Token 缓存使用

```python
from auth.login_cache import get_token, save_token, clear_token

# 尝试从缓存获取 token
token = get_token("admin")

if not token:
    # 缓存不存在或已过期，执行登录获取新 token
    token = perform_login("admin", "password123")
    # 保存 token 到缓存
    save_token(token, "admin")

# 使用 token 进行 API 请求
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("/api/users", headers=headers)

# 登出时清除 token 缓存
clear_token("admin")
```

### 5. 从环境变量获取角色凭证

```python
from auth.cache_utils import get_role_credentials, load_env_by_name

# 加载环境变量
load_env_by_name("beta")

# 获取管理员凭证
admin_creds = get_role_credentials("admin")
print(f"Admin username: {admin_creds['username']}")

# 获取普通用户凭证
user_creds = get_role_credentials("employee")
print(f"Employee username: {user_creds['username']}")
```

## 配置说明

### 1. 智能登录配置

在 `settings.py` 中可以配置以下选项：

- `base_url`：应用基础 URL
- `env`：环境标识（如 beta, prod）
- `browser.type`：浏览器类型（chromium, firefox, webkit）
- `browser.headless`：是否使用无头模式
- `browser.viewport`：浏览器视口大小
- `browser.permissions`：浏览器权限
- `browser.geolocation`：地理位置
- `login_success_selector`：登录成功的选择器（用于 SPA 应用）
- `login_timeout`：登录等待超时时间（毫秒）
- `browser_state_cache_enabled`：是否启用浏览器状态缓存

### 2. Token 缓存配置

在 `settings.py` 中可以配置以下选项：

- `token_cache_dir`：Token 缓存目录
- `token_max_age`：Token 最大有效期（秒）

### 3. 环境变量配置

支持以下环境变量命名模式：

- **单账号**：`{ENV}_USERNAME`, `{ENV}_PASSWORD`
- **多账号**：`{ENV}_USER_1`, `{ENV}_PASS_1`, `{ENV}_USER_2`, `{ENV}_PASS_2`
- **角色账号**：`{ENV}_ADMIN_USER`, `{ENV}_ADMIN_PASS`, `{ENV}_MANAGER_USER`, `{ENV}_MANAGER_PASS`

## 最佳实践

### 1. 智能登录最佳实践

- **使用上下文管理器**：优先使用 `with` 语句，自动处理资源释放
- **合理设置环境**：根据测试环境设置正确的 `env` 参数
- **使用装饰器**：对于简单测试，使用 `@smart_login_decorator` 简化代码
- **批量执行任务**：对于多个相关测试，使用 `execute_multiple_tasks` 提高效率
- **密码安全**：不要硬编码密码，使用环境变量或配置管理

### 2. Token 缓存最佳实践

- **合理设置过期时间**：根据实际 Token 有效期设置 `max_age`
- **使用唯一键**：使用唯一的 `key`（如用户名）来标识不同用户的 Token
- **及时清除**：登出或测试完成后及时清除 Token 缓存
- **错误处理**：处理 Token 过期或无效的情况

### 3. 环境变量管理最佳实践

- **使用 .env 文件**：为不同环境创建不同的 .env 文件（如 .env.beta, .env.prod）
- **避免硬编码**：所有敏感信息和配置都应通过环境变量管理
- **角色分离**：为不同角色设置不同的环境变量，便于测试不同权限
- **安全存储**：不要将包含敏感信息的 .env 文件提交到版本控制系统

### 4. 性能优化

- **启用缓存**：启用浏览器状态缓存和 Token 缓存，减少登录次数
- **合理设置超时**：根据网络速度和应用响应时间设置合理的超时时间
- **批量执行**：对于多个测试用例，使用批量执行减少浏览器启动次数
- **清理缓存**：定期清理过期的缓存文件，避免磁盘空间占用

## 依赖

- **playwright**：浏览器自动化库，提供页面操作和元素定位功能
- **filelock**：文件锁库，确保多进程安全
- **python-dotenv**：环境变量加载库，支持从 .env 文件加载环境变量
- **config**：配置管理模块，提供应用配置
- **logger**：日志模块，提供日志记录功能

## 安装

```bash
pip install playwright filelock python-dotenv
```

## 总结

Auth 模块是一个功能强大、设计合理的认证和登录管理系统，为自动化测试提供了全面的认证功能支持。通过智能缓存和多种使用方式，它大大简化了测试中的认证流程，提高了测试效率和稳定性。

**使用 Auth 模块的优势**：
- **简化登录流程**：自动管理登录状态，减少重复登录
- **提高测试效率**：缓存登录状态，加速测试执行
- **增强测试稳定性**：统一的登录成功等待机制，提高登录可靠性
- **灵活多样的使用方式**：支持上下文管理器、装饰器、批量任务执行等多种使用方式
- **安全可靠**：登录后立即清除内存中的密码，降低泄露风险

**适用场景**：
- **Web 自动化测试**：需要登录的 Web 应用测试
- **API 测试**：需要 Token 认证的 API 测试
- **多环境测试**：在不同环境（如 beta, prod）进行测试
- **多用户测试**：测试不同角色和权限的用户

通过使用 Auth 模块，您可以：
- 编写更简洁、更可靠的测试代码
- 提高测试的执行效率
- 减少测试中的登录失败率
- 更好地管理测试环境和用户凭证
- 专注于测试业务逻辑，而不是登录流程

---

**注意**：使用前请确保已安装所有必要的依赖，并根据实际需求配置相关选项。对于密码等敏感信息，建议通过环境变量或配置管理，避免硬编码。