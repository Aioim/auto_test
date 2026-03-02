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
pytest --alluredir=reports/allure-results

# 生成 Allure 报告
allure generate reports/allure-results -o reports/allure-report
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
│   ├── config/            # 配置管理
│   │   ├── __init__.py
│   │   ├── _path.py       # 路径管理
│   │   ├── env_loader.py  # 环境变量加载器
│   │   ├── locators_i18n.py # 国际化定位器
│   │   ├── manager.py     # 配置管理器
│   │   └── yaml_loader.py # YAML配置加载器
│   ├── utils/             # 工具模块
│   │   ├── common/        # 通用工具
│   │   ├── data/          # 数据处理
│   │   ├── logger/        # 日志系统
│   │   └── security/      # 安全相关
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
├── pyproject.toml         # 项目配置
├── pytest.ini             # pytest配置
└── test_simple_dialog.py  # 简单弹窗测试
```

## 核心模块

### 1. 环境管理

`src/config/env_loader.py` 提供智能环境检测和配置加载功能：

- 自动检测 CI/CD 环境（GitHub Actions、GitLab CI 等）
- 检测容器环境并进行资源优化
- 根据操作系统和架构进行特定优化
- 支持从系统环境变量和 .env 文件加载配置

### 2. 页面对象模型

`pages/` 目录实现了标准化的 Page Object Model：

- `base_page.py`：基础页面类，提供通用方法
- `components/`：可复用组件
- `baidu_page.py`：示例页面实现

### 3. 工具模块

#### 通用工具 (`utils/common/`)
- `screenshot_helper.py`：高级截图功能（支持元素高亮、标注）
- `selector_helper.py`：智能选择器辅助
- `visual_validator.py`：视觉验证工具

#### 数据工具 (`utils/data/`)
- `data_faker.py`：测试数据生成
- `data_loader.py`：数据加载
- `yaml_cases_loader.py`：YAML 测试用例加载

#### 日志系统 (`utils/logger/`)
- 支持多级别日志
- 结构化日志输出
- 日志轮转和归档
- 安全日志脱敏

#### 安全工具 (`utils/security/`)
- `env_encrypt.py`：环境变量加密
- `secrets_manager.py`：密钥管理
- `key_rotation.py`：密钥轮换

## 测试用例编写

### 基本结构

```python
import pytest
from pages.baidu_page import BaiduPage

def test_baidu_search(page):
    """测试百度搜索功能"""
    baidu_page = BaiduPage(page)
    baidu_page.navigate()
    baidu_page.search("Playwright")
    assert baidu_page.is_search_result_displayed()
```

### 数据驱动测试

使用 YAML 数据文件驱动测试：

```python
import pytest
from pages.login_page import LoginPage

def test_login_with_data(page, yaml_data):
    """使用数据驱动测试登录功能"""
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(yaml_data["username"], yaml_data["password"])
    assert login_page.is_logged_in()
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
pytest --alluredir=reports/allure-results

# 生成 Allure 报告
allure generate reports/allure-results -o reports/allure-report

# 查看报告
allure open reports/allure-report
```

### HTML 报告

```bash
# 运行测试并生成 HTML 报告
pytest --html=reports/html/report.html
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

### 日志分析

```bash
# 查看测试日志
cat reports/logs/test_run.log

# 查看错误日志
cat reports/logs/error_*.log
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
        run: pytest --alluredir=reports/allure-results
      - name: Generate Allure report
        run: allure generate reports/allure-results -o reports/allure-report
      - name: Upload Allure report
        uses: actions/upload-artifact@v3
        with:
          name: allure-report
          path: reports/allure-report
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
    - pytest --alluredir=reports/allure-results
  artifacts:
    paths:
      - reports/allure-results

report:
  stage: report
  image: frankescobar/allure-report-action
  script:
    - allure generate reports/allure-results -o reports/allure-report
  artifacts:
    paths:
      - reports/allure-report
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