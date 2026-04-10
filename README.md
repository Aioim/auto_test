# auto_test 自动化测试框架

## 项目简介

auto_test 是一个功能强大的自动化测试框架，基于 Python 和 Playwright 构建，旨在提供高效、稳定、可扩展的自动化测试解决方案。

### 核心特性

- **智能环境检测**：自动检测 CI/CD、容器、操作系统等环境并进行优化配置
- **多环境支持**：内置开发、测试、预发布、生产环境配置管理
- **Page Object Model**：标准化的页面对象设计模式
- **高级日志系统**：支持多级别日志、结构化日志、日志轮转
- **安全管理**：环境变量加密、密钥管理
- **数据驱动测试**：支持 YAML 数据文件驱动测试
- **视觉验证**：截图对比、元素级截图
- **多格式报告**：支持 Allure、HTML、JUnit 等多种报告格式
- **性能监控**：测试执行性能监控
- **智能登录**：自动管理登录状态，支持多环境和多用户
- **错误监控**：捕获页面弹窗、控制台错误、网络请求失败等
- **数据库操作**：支持 MySQL、PostgreSQL、SQLite 等常见数据库

## 快速开始

### 环境要求

- Python 3.11+
- 支持的操作系统：Windows、macOS、Linux

### 安装步骤

1. **克隆项目**

```bash
git clone <repository-url>
cd auto_test
```

2. **安装依赖**

```bash
# 安装基础依赖
pip install -e .

# 安装开发依赖（包含测试工具）
pip install -e .[dev]
```

3. **配置环境变量**

复制 `.env.example` 文件为 `.env` 并根据实际情况修改：

```bash
cp .env.example .env
# 编辑 .env 文件
```

4. **安装 Playwright 浏览器**

```bash
playwright install
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_login.py

# 运行带 Allure 报告的测试
pytest --alluredir=output/allure-results

# 生成 Allure 报告
allure generate output/allure-results -o output/allure-report

# 查看报告
allure open output/allure-report
```

## 项目结构

```
auto_test/
├── environments/          # 环境配置文件
│   ├── base.yaml          # 基础配置
│   ├── dev.yaml           # 开发环境
│   ├── prod.yaml          # 生产环境
│   └── staging.yaml       # 预发布环境
├── pages/                 # 页面对象层
│   ├── components/        # 可复用组件
│   │   ├── base_component.py
│   │   └── header.py
│   ├── __init__.py
│   ├── baidu_page.py      # 百度搜索页示例
│   ├── baidu_selector.py  # 百度页面选择器
│   └── base_page.py       # 基础页面类
├── src/                   # 源代码
│   ├── auth/              # 认证和登录管理
│   │   ├── __init__.py
│   │   ├── cache_utils.py
│   │   ├── login_cache.py
│   │   └── smart_login.py
│   ├── config/            # 配置管理
│   │   ├── __init__.py
│   │   ├── env_loader.py  # 环境变量加载器
│   │   ├── locators_i18n.py # 国际化定位器
│   │   ├── path.py        # 路径管理
│   │   ├── settings.py    # 配置设置
│   │   └── yaml_loader.py # YAML配置加载器
│   ├── core/              # 核心功能
│   │   ├── __init__.py
│   │   ├── allure_attachments.py
│   │   ├── network.py
│   │   ├── screenshot.py
│   │   ├── selector.py
│   │   ├── visual.py
│   │   └── wait.py
│   ├── data/              # 数据管理
│   │   ├── __init__.py
│   │   ├── data_faker.py  # 测试数据生成
│   │   ├── db_helper.py   # 数据库操作
│   │   └── yaml_cases_loader.py # YAML测试用例加载
│   ├── logger/            # 日志系统
│   │   ├── __init__.py
│   │   ├── lazy.py
│   │   └── secure_log.py
│   ├── monitoring/        # 错误监控
│   │   ├── __init__.py
│   │   └── error_monitor.py
│   └── __init__.py
├── test_data/             # 测试数据
│   ├── visual/            # 视觉测试数据
│   ├── login_cases.yaml   # 登录测试用例
│   └── login_page.yaml    # 登录页配置
├── tests/                 # 测试用例
│   ├── conftest.py        # pytest配置
│   ├── test_dialog_handling.py
│   ├── test_login.py
│   └── test_screenshot_helper.py
├── .gitignore
├── README.md
├── demo_dialog_effect.py  # 弹窗效果演示
├── demo_dialog_handling.py # 弹窗处理演示
├── pf_logger.py           # 日志演示
├── pyproject.toml         # 项目配置（包含pytest配置）
└── test_simple_dialog.py  # 简单弹窗测试
```

## 核心模块

### 1. 环境管理

`src/config/` 目录提供智能环境检测和配置加载功能：

- **env_loader.py**：自动检测 CI/CD 环境、容器环境和操作系统，并进行相应的优化配置
- **yaml_loader.py**：从 YAML 文件加载配置，支持多环境配置
- **settings.py**：基于 Pydantic 的配置管理，提供类型安全的配置访问
- **locators_i18n.py**：提供页面元素文本的多语言映射功能
- **path.py**：管理项目路径，提供统一的路径访问

### 2. 页面对象模型

`pages/` 目录实现了标准化的 Page Object Model：

- **base_page.py**：基础页面类，提供通用方法，如导航、元素操作、断言等
- **components/**：可复用组件，如头部导航、侧边栏等
- **baidu_page.py**：示例页面实现，展示如何使用页面对象模式

### 3. 认证管理

`src/auth/` 目录提供智能登录和认证管理功能：

- **smart_login.py**：智能登录管理，自动处理登录状态，支持缓存和多环境
- **login_cache.py**：API 测试的 Token 缓存管理
- **cache_utils.py**：浏览器登录状态缓存公共工具

### 4. 数据管理

`src/data/` 目录提供数据处理和生成功能：

- **data_faker.py**：基于 Faker 的测试数据生成器，支持生成各种类型的测试数据
- **yaml_cases_loader.py**：YAML 测试用例加载器，支持从 YAML 文件加载测试数据
- **db_helper.py**：数据库操作助手，支持 MySQL、PostgreSQL、SQLite 等常见数据库

### 5. 核心功能

`src/core/` 目录提供核心功能模块：

- **screenshot.py**：高级截图功能，支持页面截图、元素截图、高亮标注等
- **selector.py**：智能选择器辅助，支持多种定位策略和智能解析
- **visual.py**：视觉验证工具，支持图像比较和视觉回归测试
- **network.py**：网络捕获工具，支持捕获和分析网络请求
- **allure_attachments.py**：Allure 报告附件工具，支持添加各种类型的附件
- **wait.py**：等待工具，提供智能的元素等待和页面状态等待

### 6. 错误监控

`src/monitoring/` 目录提供错误监控功能：

- **error_monitor.py**：错误监控装饰器，支持捕获页面弹窗、控制台错误、网络请求失败等

### 7. 日志系统

`src/logger/` 目录提供高级日志功能：

- **secure_log.py**：安全日志系统，支持日志脱敏和结构化日志
- **lazy.py**：延迟初始化日志，提高性能

## 测试用例编写

### 基本结构

```python
import pytest
from pages.baidu_page import BaiduPage
from utils import logger, log_step

def test_baidu_search(page):
    """测试百度搜索功能"""
    logger.info("开始测试百度搜索功能")
    
    baidu_page = BaiduPage(page)
    
    with log_step("导航到百度首页"):
        baidu_page.navigate()
    
    with log_step("执行搜索"):
        baidu_page.search("Playwright")
    
    with log_step("验证搜索结果"):
        assert baidu_page.is_search_result_displayed()
    
    logger.info("百度搜索测试完成")
```

### 数据驱动测试

使用 YAML 数据文件驱动测试：

```python
import pytest
from pages.login_page import LoginPage
from utils import load_yaml_file

def test_login_with_data(page, yaml_data):
    """使用数据驱动测试登录功能"""
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(yaml_data["username"], yaml_data["password"])
    assert login_page.is_logged_in()
```

### 智能登录测试

使用智能登录功能进行测试：

```python
import pytest
from auth.smart_login import SmartLogin
from pages.dashboard_page import DashboardPage

def test_dashboard_access():
    """测试登录后访问仪表盘"""
    with SmartLogin(username="admin", password="password123") as (page, context):
        dashboard_page = DashboardPage(page)
        dashboard_page.navigate()
        assert dashboard_page.is_dashboard_displayed()
        assert "dashboard" in page.url.lower()
```

### API 测试

使用 API 客户端进行测试：

```python
import pytest
from utils import APIClient

def test_api_endpoint(api_client):
    """测试 API 端点"""
    # 发送 GET 请求
    response = api_client.get("/api/test")
    # 验证状态码
    api_client.assert_status(response, 200)
    # 验证响应字段
    api_client.assert_field_exists(response, "data")
    # 验证响应时间
    api_client.assert_response_time(response, 2.0)
```

### 错误监控测试

使用错误监控装饰器捕获页面错误：

```python
import pytest
from utils.monitoring import monitor_errors

def test_with_error_monitoring(page):
    """测试错误监控功能"""
    
    @monitor_errors(
        page=page,
        screenshot_on_error=True,
        screenshot_dir="./screenshots",
        raise_on_error=True
    )
    def test_login_flow():
        """测试登录流程"""
        page.goto("https://example.com/login")
        page.fill("#username", "testuser")
        page.fill("#password", "password")
        page.click("#login-button")
        page.wait_for_load_state("networkidle")
    
    test_login_flow()
```

## 配置管理

### 环境配置

在 `environments/` 目录下定义不同环境的配置：

- `base.yaml`：基础配置
- `dev.yaml`：开发环境配置
- `staging.yaml`：预发布环境配置
- `prod.yaml`：生产环境配置

### 环境变量

支持以下环境变量：

| 环境变量 | 描述 | 默认值 |
|---------|------|-------|
| `ENV` | 运行环境 | - |
| `BASE_URL` | 基础 URL | - |
| `API_BASE_URL` | API 基础 URL | - |
| `BROWSER_HEADLESS` | 无头浏览器模式 | `false` |
| `BROWSER_TYPE` | 浏览器类型 (chromium/webkit/firefox) | `chromium` |
| `VIEWPORT_WIDTH` | 浏览器视口宽度 | 1920 |
| `VIEWPORT_HEIGHT` | 浏览器视口高度 | 1080 |
| `PAGE_LOAD_TIMEOUT` | 页面加载超时 (秒) | 30 |
| `ELEMENT_WAIT_TIMEOUT` | 元素等待超时 (秒) | 10 |
| `LOG_LEVEL` | 日志级别 | `info` |
| `VIDEO_RECORDING` | 视频录制模式 (off/on/failed) | `failed` |
| `ENABLE_NETWORK_TRACING` | 启用网络跟踪 | `false` |

## 报告生成

### Allure 报告

```bash
# 运行测试并生成 Allure 结果
pytest --alluredir=output/allure-results

# 生成 Allure 报告
allure generate output/allure-results -o output/allure-report

# 查看报告
allure open output/allure-report
```

### HTML 报告

```bash
# 运行测试并生成 HTML 报告
pytest --html=output/html/report.html
```

## 最佳实践

1. **页面对象设计**：
   - 每个页面创建单独的类
   - 页面元素使用统一的选择器管理
   - 封装页面操作方法

2. **测试用例组织**：
   - 按功能模块组织测试文件
   - 使用描述性的测试方法名
   - 添加适当的注释和文档

3. **数据管理**：
   - 使用 YAML 文件管理测试数据
   - 敏感数据使用环境变量
   - 动态数据使用数据生成器

4. **性能优化**：
   - 使用并行测试
   - 合理设置超时时间
   - 避免不必要的操作

5. **稳定性提升**：
   - 使用显式等待
   - 实现重试机制
   - 处理异常情况

6. **错误监控**：
   - 使用错误监控装饰器捕获页面错误
   - 合理设置错误过滤规则
   - 启用实时日志输出

7. **智能登录**：
   - 使用智能登录管理登录状态
   - 配置适当的缓存策略
   - 处理多环境和多用户场景

## 故障排查

### 常见问题

1. **浏览器启动失败**：
   - 检查 Playwright 是否已正确安装
   - 检查浏览器驱动是否匹配
   - 检查系统资源是否充足

2. **元素定位失败**：
   - 检查选择器是否正确
   - 检查页面是否完全加载
   - 检查元素是否在 iframe 中

3. **测试执行缓慢**：
   - 检查网络连接
   - 优化测试步骤
   - 减少不必要的操作

4. **环境配置问题**：
   - 检查 .env 文件配置
   - 检查环境变量是否正确设置
   - 检查配置文件格式

5. **登录失败**：
   - 检查用户名和密码是否正确
   - 检查登录流程是否改变
   - 检查登录缓存是否有效

### 日志分析

```bash
# 查看测试日志
cat output/logs/test_run.log

# 查看错误日志
cat output/logs/error_*.log
```

## CI/CD 集成

### GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]
          playwright install
      - name: Run tests
        run: pytest --alluredir=output/allure-results
      - name: Generate Allure report
        run: allure generate output/allure-results -o output/allure-report
      - name: Upload Allure report
        uses: actions/upload-artifact@v3
        with:
          name: allure-report
          path: output/allure-report
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test
  - report

test:
  stage: test
  image: python:3.11
  script:
    - pip install -e .[dev]
    - playwright install
    - pytest --alluredir=output/allure-results
  artifacts:
    paths:
      - output/allure-results

report:
  stage: report
  image: frankescobar/allure-report-action
  script:
    - allure generate output/allure-results -o output/allure-report
  artifacts:
    paths:
      - output/allure-report
```

## 贡献指南

1. **Fork 项目**
2. **创建特性分支** (`git checkout -b feature/amazing-feature`)
3. **提交更改** (`git commit -m 'Add some amazing feature'`)
4. **推送到分支** (`git push origin feature/amazing-feature`)
5. **创建 Pull Request**

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系我们

- 作者：chao
- 邮箱：178754558@qq.com

---

**注意**：本框架持续迭代中，如有任何问题或建议，欢迎提交 Issue 或 Pull Request。