# Config 模块文档

## 模块概述

Config 模块是一个功能强大的配置管理系统，为自动化测试提供了灵活、可扩展的配置解决方案：

- **统一配置管理**：集中管理所有测试配置，支持多环境配置
- **环境变量支持**：从环境变量加载配置，支持嵌套配置
- **YAML 配置文件**：支持从 YAML 文件加载配置，支持环境特定配置
- **运行环境自适应**：自动检测 CI/容器/操作系统环境并优化配置
- **国际化支持**：提供页面元素文本的多语言映射功能
- **类型安全**：基于 Pydantic 的类型验证，确保配置的有效性

## 安装依赖

```bash
# 安装基础依赖
pip install pydantic python-dotenv pyyaml

# 安装可选依赖
pip install psutil  # 用于系统资源检测
```

## 核心功能

### 1. 配置管理 (`ConfigManager`)

**功能**：
- **多源配置**：从 YAML 文件、环境变量和命令行参数加载配置
- **配置合并**：深度合并多个配置源，支持优先级排序
- **类型安全**：基于 Pydantic 的类型验证和字段验证
- **热重载**：支持配置热重载，无需重启应用
- **路径访问**：支持通过点号路径访问嵌套配置

**主要方法**：
- `initialize()`：显式初始化配置
- `get(path, default=None)`：通过点号路径获取嵌套配置
- `apply_overrides(overrides_str)`：应用命令行覆盖
- `validate()`：显式验证配置
- `to_yaml()`：导出当前配置为 YAML
- `reload()`：热重载配置

### 2. 环境变量加载器 (`EnvLoader`)

**功能**：
- **自动环境检测**：检测 CI/CD 环境、容器环境和操作系统
- **环境优化**：根据检测到的环境自动优化配置
- **.env 文件支持**：从 .env 文件加载环境变量
- **代理设置**：标准化代理设置
- **CA 证书检测**：检测企业 CA 证书
- **CPU 核心优化**：根据 CPU 核心数优化并行度

**主要方法**：
- `load()`：加载并优化环境变量

### 3. YAML 配置加载器 (`YamlLoader`)

**功能**：
- **多环境支持**：支持 base.yaml 和环境特定的配置文件
- **缓存机制**：缓存配置并根据文件修改时间自动更新
- **深度合并**：深度合并 base.yaml 和环境特定配置

**主要方法**：
- `load_environment(env="dev")`：加载指定环境的 YAML 配置
- `clear_cache()`：清除缓存

### 4. 国际化支持 (`I18nManager`)

**功能**：
- **多语言支持**：支持多种语言的文本映射
- **文件加载**：从 JSON 和 YAML 文件加载国际化配置
- **默认语言**：支持设置默认语言
- **回退机制**：当指定语言未找到时，回退到默认语言

**主要方法**：
- `load_from_file(file_path)`：从文件加载国际化配置
- `load_from_directory(dir_path)`：从目录加载所有国际化配置文件
- `get_text(key, locale=None)`：获取指定语言的文本
- `set_default_locale(locale)`：设置默认语言
- `get_available_locales()`：获取可用的语言列表
- `clear_cache()`：清除缓存，重新加载默认配置

## 配置结构

### 1. AppConfig 模型

AppConfig 是配置的核心模型，包含以下主要配置项：

- **核心配置**：
  - `env`：运行环境（dev/beta/prod）
  - `frontend_version`：前端版本
  - `base_url`：基础 URL
  - `api_base_url`：API 基础 URL
  - `login_url`：登录 URL

- **敏感凭证**：
  - `username`：用户名
  - `password`：密码（SecretStr）
  - `api_secret_key`：API 密钥（SecretStr）

- **子配置**：
  - `browser`：浏览器配置
  - `timeouts`：超时配置
  - `allure`：Allure 报告配置
  - `log`：日志配置

- **高级选项**：
  - `preserve_context_on_failure`：失败时保留上下文
  - `video_recording`：视频录制策略
  - `enable_network_tracing`：启用网络追踪
  - `selector_strategy`：选择器策略
  - `resource_cleanup_timeout`：资源清理超时

- **运行时信息**：
  - `time_now`：当前时间

- **路径配置**：
  - `screenshot_dir`：截图目录
  - `visual_baseline_dir`：视觉基线目录
  - `visual_diff_dir`：视觉差异目录
  - `visual_threshold`：视觉相似度阈值

### 2. 浏览器配置 (BrowserConfig)

- `headless`：无头模式
- `type`：浏览器类型（chromium/firefox/webkit）
- `enable_js`：启用 JavaScript
- `viewport`：视口大小
- `locale`：语言区域
- `permissions`：权限列表
- `geolocation`：地理位置
- `auth_dir`：认证目录

### 3. 超时配置 (TimeoutsConfig)

- `page_load`：页面加载超时
- `element_wait`：元素等待超时
- `api`：API 超时

### 4. Allure 配置 (AllureConfig)

- `results_dir`：结果目录
- `auto_clean`：自动清理
- `default_severity`：默认严重程度

### 5. 日志配置 (LogConfig)

- `log_dir`：日志目录
- `log_level`：日志级别
- `log_file`：日志文件
- `backup_count`：备份数量
- `max_bytes`：最大字节数
- `perf_max_bytes`：性能日志最大字节数
- `enable_colors`：启用颜色
- `enable_emergency_response`：启用紧急响应
- `quiet`：安静模式
- `replace_main_with_filename`：用文件名替换 main

## 使用示例

### 1. 基本配置使用

```python
from utils.config import settings

# 访问配置
env = settings.env
username = settings.username
password = settings.password.get_secret_value()
browser_type = settings.browser.type

# 通过点号路径访问嵌套配置
element_wait_timeout = settings.get('timeouts.element_wait')

# 应用命令行覆盖
settings.apply_overrides('env=prod,browser.headless=true')

# 热重载配置
settings.reload()

# 导出配置为 YAML
print(settings.to_yaml())
```

### 2. 环境变量配置

**示例 .env 文件**：

```env
# 核心配置
ENV=prod
BASE_URL=https://example.com
API_BASE_URL=https://api.example.com

# 浏览器配置
BROWSER__HEADLESS=true
BROWSER__TYPE=chromium

# 超时配置
TIMEOUTS__PAGE_LOAD=60000

# 敏感凭证
USERNAME=admin
PASSWORD=secret123
API_SECRET_KEY=api_key_123
```

**环境变量优先级**：
1. 命令行覆盖
2. 环境变量
3. YAML 配置文件
4. 默认值

### 3. YAML 配置文件

**base.yaml**：

```yaml
# 基础配置
env: dev
base_url: http://localhost:3000
api_base_url: http://localhost:8000

browser:
  headless: false
  type: chromium
  viewport:
    width: 1920
    height: 1080

timeouts:
  page_load: 30000
  element_wait: 10000
  api: 15000
```

**prod.yaml**：

```yaml
# 生产环境配置
env: prod
base_url: https://example.com
api_base_url: https://api.example.com

browser:
  headless: true
  type: chromium
```

### 4. 国际化使用

```python
from utils.config import get_text

# 获取中文文本
username_label = get_text('login.username')  # 返回 "用户名"

# 获取英文文本
username_label_en = get_text('login.username', locale='en')  # 返回 "Username"

# 加载自定义国际化配置
from utils.config import i18n_manager
i18n_manager.load_from_file('path/to/locales.yaml')
```

## 环境检测与优化

EnvLoader 会自动检测以下环境并进行优化：

### 1. CI/CD 环境

检测到 CI 环境时，自动设置：
- `CI_ENVIRONMENT`：CI 环境名称
- `BROWSER_HEADLESS`：true
- `VIDEO_RECORDING`：failed
- `PRESERVE_CONTEXT_ON_FAILURE`：false
- `ENABLE_NETWORK_TRACING`：false

### 2. 容器环境

检测到容器环境时，自动设置：
- `CONTAINER_ENVIRONMENT`：true
- `BROWSER_HEADLESS`：true
- `ENABLE_JS`：true

### 3. 操作系统优化

- **Windows**：设置默认浏览器路径，规范化路径斜杠
- **macOS**：默认使用 webkit 浏览器
- **Linux**：根据架构优化浏览器选择

### 4. 调试模式

检测到调试模式时，自动设置：
- `LOG_LEVEL`：debug
- `BROWSER_HEADLESS`：false
- `VIDEO_RECORDING`：always
- `PRESERVE_CONTEXT_ON_FAILURE`：true

## 国际化配置

### 1. 默认映射

Config 模块提供了默认的国际化映射：

- **中文**：
  - `login.username`：用户名
  - `login.password`：密码
  - `login.submit`：登录
  - `dashboard.title`：控制台

- **英文**：
  - `login.username`：Username
  - `login.password`：Password
  - `login.submit`：Sign in
  - `dashboard.title`：Dashboard

### 2. 自定义国际化配置

**locales.yaml**：

```yaml
zh:
  login.username: "用户名"
  login.password: "密码"
  login.submit: "登录"
  dashboard.title: "控制台"
en:
  login.username: "Username"
  login.password: "Password"
  login.submit: "Sign in"
  dashboard.title: "Dashboard"
```

## 最佳实践

### 1. 配置管理最佳实践

- **使用环境变量**：对于敏感信息和环境特定配置，使用环境变量
- **分层配置**：使用 base.yaml 作为基础配置，环境特定配置文件覆盖特定值
- **命令行覆盖**：对于临时修改，使用命令行覆盖
- **类型安全**：利用 Pydantic 的类型验证确保配置的有效性
- **热重载**：在配置文件修改后，使用 `reload()` 热重载配置

### 2. 国际化最佳实践

- **统一命名**：使用一致的命名约定，如 `page.element`
- **默认语言**：设置合适的默认语言，确保所有文本都有默认值
- **回退机制**：利用回退机制，确保即使在未找到指定语言时也能显示默认语言的文本
- **集中管理**：将国际化配置集中管理，便于维护和更新

### 3. 环境检测最佳实践

- **利用自动优化**：启用 EnvLoader 的自动优化功能，适应不同的运行环境
- **自定义环境变量**：根据需要添加自定义环境变量，覆盖默认行为
- **调试模式**：在开发和调试时，使用调试模式获取更详细的日志和更方便的测试环境

## 依赖

- **pydantic**：用于配置模型和类型验证
- **python-dotenv**：用于加载 .env 文件
- **pyyaml**：用于解析 YAML 配置文件
- **psutil**：用于系统资源检测（可选）

## 安装

```bash
pip install pydantic python-dotenv pyyaml psutil
```

## 总结

Config 模块是一个功能强大、灵活易用的配置管理系统，为自动化测试提供了全面的配置解决方案：

- **统一配置管理**：集中管理所有测试配置，支持多环境配置
- **环境自适应**：自动检测运行环境并优化配置
- **国际化支持**：提供页面元素文本的多语言映射功能
- **类型安全**：基于 Pydantic 的类型验证，确保配置的有效性
- **灵活扩展**：支持从多种来源加载配置，支持热重载

通过使用 Config 模块，您可以：
- 更有效地管理测试配置
- 适应不同的运行环境
- 支持多语言测试
- 提高测试的可靠性和稳定性
- 减少配置错误和手动干预

---

**注意**：使用前请确保已安装所有必要的依赖，并根据实际需求配置相关选项。