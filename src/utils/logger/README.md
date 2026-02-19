# 企业级安全日志系统

一个功能强大、安全可靠的企业级日志系统，为自动化测试和应用程序提供全面的日志记录能力。

## 功能特性

### 🛡️ 安全特性
- **敏感数据脱敏**：自动检测和屏蔽密码、令牌、API密钥等敏感信息
- **安全事件记录**：专门的安全日志通道，记录用户登录、权限变更等安全事件
- **URL参数脱敏**：自动屏蔽URL中的敏感参数
- **请求/响应安全日志**：安全记录API请求和响应，保护敏感信息

### 📊 日志类型
- **主日志** (`test_run.log`)：应用程序主日志
- **API日志** (`api.log`)：API请求和响应日志
- **性能日志** (`performance.log`)：性能指标和耗时记录
- **安全日志** (`security.log`)：安全事件和审计日志
- **错误日志** (`error_YYYYMMDD.log`)：错误和异常记录
- **自定义日志**：支持创建自定义日志文件

### ⚡ 高级功能
- **延迟初始化**：日志实例按需创建，减少启动开销
- **性能监控**：函数执行时间监控，标记慢操作
- **步骤跟踪**：工作流步骤的开始和完成记录
- **执行时长记录**：使用上下文管理器记录代码块执行时间
- **异常自动捕获**：自动捕获和记录异常，包含完整堆栈信息
- **请求/响应日志**：结构化记录API请求和响应
- **彩色控制台输出**：开发环境友好的彩色日志
- **JSON格式化**：支持JSON格式的结构化日志

### 🔧 配置管理
- **集中配置**：统一的日志配置管理
- **文件轮转**：基于时间和大小的日志文件轮转
- **日志级别控制**：支持不同日志级别的精细控制
- **环境感知**：自动适应不同环境的日志配置

### 📈 可观测性
- **日志诊断**：内置日志系统诊断工具
- **API日志验证**：验证API日志是否正确记录
- **性能指标**：记录日志系统自身的性能指标

## 快速开始

### 基本使用

```python
from utils.logger import logger

# 基本日志记录
logger.debug("调试信息")
logger.info("信息日志")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")

# 记录异常
try:
    1 / 0
except Exception:
    from utils.logger import log_exception
    log_exception(context="除法运算")
```

### 高级使用

#### 性能监控

```python
from utils.logger import log_performance

@log_performance(threshold_ms=100)  # 超过100ms标记为慢操作
def slow_function():
    # 执行耗时操作
    import time
    time.sleep(0.2)
    return "完成"

# 调用函数，自动记录执行时间
result = slow_function()
```

#### 步骤跟踪

```python
from utils.logger import log_step

@log_step("数据处理")
def process_data(data):
    # 处理数据
    return processed_data

# 调用函数，自动记录步骤开始和完成
result = process_data(raw_data)
```

#### 执行时长记录

```python
from utils.logger import log_duration

with log_duration("数据库查询"):
    # 执行数据库查询
    results = db.query("SELECT * FROM users")
```

#### API请求/响应日志

```python
from utils.logger import request_logger

# 记录请求
request_id = request_logger.log_request(
    method="POST",
    url="https://api.example.com/login?username=admin&password=secret"
)

# 记录响应
request_logger.log_response(
    request_id=request_id,
    status_code=200,
    duration_ms=45.6
)
```

#### 安全事件记录

```python
from utils.logger import log_security_event

# 记录安全事件
log_security_event(
    action="user_login",
    user="admin",
    resource="/admin",
    status="success",
    details={"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"}
)
```

## 日志实例

系统提供了以下预配置的日志实例：

| 日志实例 | 用途 | 默认级别 | 日志文件 |
|---------|------|---------|----------|
| `logger` | 主日志 | INFO | test_run.log |
| `api_logger` | API日志 | DEBUG | api.log |
| `perf_logger` | 性能日志 | DEBUG | performance.log |
| `security_logger` | 安全日志 | INFO | security.log |

## 自定义日志器

您可以创建自定义日志器以满足特定需求：

```python
from utils.logger import setup_logger

# 创建自定义日志器
custom_logger = setup_logger(
    name="my_app",
    log_level="DEBUG",
    log_to_console=True,
    log_to_file=True,
    separate_log_file="my_app.log"  # 自定义日志文件
)

# 使用自定义日志器
custom_logger.info("自定义日志信息")
```

## 日志格式

系统使用统一的日志格式，包含六大要素：

```
2026-02-19 15:12:04 INFO     [demo.py:main:42] Application started
```

格式说明：
1. **时间戳**：`2026-02-19 15:12:04`
2. **日志级别**：`INFO`
3. **文件名**：`demo.py`
4. **函数名**：`main`
5. **行号**：`42`
6. **日志内容**：`Application started`

## 安全特性

### 敏感数据脱敏

系统会自动脱敏以下类型的敏感数据：

- 密码（password、pwd）
- 令牌（token）
- API密钥（api_key、apikey）
- 密钥（secret）
- 授权信息（authorization）
- Cookie信息（cookie）
- X-API-Key头部

脱敏示例：

```python
from utils.logger import logger, mask_sensitive_data

# 自动脱敏
logger.info("用户登录: username=admin, password=secret123")
# 输出: 用户登录: username=admin, password=******

# 手动脱敏
sensitive_data = "API密钥: sk-1234567890abcdef"
desensitized = mask_sensitive_data(sensitive_data)
print(desensitized)  # 输出: API密钥: sk-******
```

## 诊断工具

### 日志系统诊断

```python
from utils.logger import diagnose_logger, print_logger_diagnosis

# 诊断日志系统
diagnosis = diagnose_logger()

# 打印诊断结果
print_logger_diagnosis(diagnosis)
```

### API日志验证

```python
from utils.logger import verify_api_logging

# 验证API日志配置
is_valid = verify_api_logging()
print(f"API日志配置有效: {is_valid}")
```

## 最佳实践

1. **使用适当的日志级别**：根据消息的重要性选择合适的日志级别
2. **添加上下文信息**：在日志消息中包含足够的上下文信息
3. **使用结构化日志**：对于复杂数据，使用JSON格式的结构化日志
4. **避免日志轰炸**：不要在高频循环中记录过多日志
5. **使用性能监控**：对关键函数使用性能监控装饰器
6. **记录异常**：使用`log_exception`记录异常，包含完整上下文
7. **安全日志**：使用`log_security_event`记录安全相关事件

## 配置选项

### 环境变量

| 环境变量 | 描述 | 默认值 |
|---------|------|-------|
| `LOG_LEVEL` | 日志级别 | INFO |
| `LOG_DIR` | 日志目录 | `./logs` |
| `ENV` | 运行环境 | development |

### 配置文件

日志系统会从项目配置中读取设置，优先使用以下配置：

```python
# config/settings.py
log = {
    "log_level": "INFO",
    "log_dir": "./logs",
    "log_file": "test_run.log"
}
env = "development"
```

## 示例

### 完整示例

```python
from utils.logger import (
    logger, api_logger, perf_logger, security_logger,
    log_exception, log_security_event, log_step, log_duration, log_performance,
    mask_sensitive_data, request_logger
)

# 1. 基本日志
def basic_logging():
    logger.info("应用程序启动")
    logger.warning("磁盘空间不足")
    
    try:
        1 / 0
    except Exception:
        log_exception(context="除法运算")

# 2. 性能监控
@log_performance(threshold_ms=50)
def slow_operation():
    import time
    time.sleep(0.1)
    return "完成"

# 3. 步骤跟踪
@log_step("数据处理")
def process_data(data):
    # 处理数据
    return [item * 2 for item in data]

# 4. 执行时长记录
def database_operation():
    with log_duration("数据库查询"):
        # 模拟数据库查询
        import time
        time.sleep(0.05)
        return ["结果1", "结果2"]

# 5. API请求日志
def api_request_example():
    # 记录请求
    request_id = request_logger.log_request(
        method="POST",
        url="https://api.example.com/login?username=admin&password=secret"
    )
    
    # 模拟API调用
    import time
    time.sleep(0.1)
    
    # 记录响应
    request_logger.log_response(
        request_id=request_id,
        status_code=200,
        duration_ms=105.3
    )

# 6. 安全事件日志
def security_event_example():
    log_security_event(
        action="user_login",
        user="admin",
        resource="/admin",
        status="success",
        details={"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"}
    )

if __name__ == "__main__":
    basic_logging()
    slow_operation()
    process_data([1, 2, 3, 4, 5])
    database_operation()
    api_request_example()
    security_event_example()
    
    logger.info("应用程序执行完成")
```

## 故障排除

### 常见问题

1. **日志文件未生成**
   - 检查日志目录是否存在且可写
   - 检查日志级别设置是否正确
   - 检查应用程序是否有足够的权限

2. **日志级别不生效**
   - 确保在创建日志实例之前设置日志级别
   - 检查是否有其他地方覆盖了日志级别设置

3. **敏感数据未脱敏**
   - 确保使用了正确的日志格式
   - 检查敏感数据是否使用了标准命名格式

4. **日志系统性能问题**
   - 减少高频循环中的日志记录
   - 对非关键路径使用更高的日志级别
   - 考虑使用异步日志处理器

### 日志系统自检

```python
from utils.logger import diagnose_logger, print_logger_diagnosis

# 运行诊断
diagnosis = diagnose_logger()

# 打印诊断结果
print_logger_diagnosis(diagnosis)
```

## 贡献指南

1. **代码风格**：遵循项目的代码风格规范
2. **测试**：为新功能添加测试用例
3. **文档**：更新相关文档
4. **提交**：使用清晰的提交消息

## 许可证

本日志系统采用MIT许可证。
