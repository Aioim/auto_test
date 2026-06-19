# CLAUDE.md — auto_test 自动化测试框架开发规范

> Python 3.11+ · Playwright · pytest · Allure · requests · Pydantic
> 本文档定义 AI 协作开发的技能调用优先级、开发流程和代码约定。

---

## 1. 技术栈

| 层级 | 技术 |
|:---|:---|
| 语言 | Python 3.11+ |
| 浏览器自动化 | Playwright 1.40+ |
| 测试框架 | pytest（YAML 数据驱动、标记系统） |
| API 测试 | requests + backoff（指数退避重试） |
| 报告 | Allure（allure-pytest） |
| 配置管理 | Pydantic v2 + YAML + .env 环境变量覆盖 |
| 数据库 | SQLAlchemy + MySQL / PostgreSQL / SQLite |
| 视觉验证 | OpenCV + scikit-image |
| 安全 | cryptography + 日志自动脱敏 |
| 数据生成 | Faker |

---

## 2. 项目结构

```
auto_test/
├── environments/          # 环境 YAML 配置（base / dev / staging / prod）
├── pages/                 # Page Object Model
│   └── components/        # 可复用 UI 组件
├── src/
│   ├── api_client/        # API 测试客户端（重试 + 断言链 + 敏感信息过滤）
│   ├── auth/              # 智能登录 & 浏览器状态缓存
│   ├── config/            # Pydantic 配置单例（YAML → 环境变量 → 命令行覆盖）
│   ├── core/              # 截图、智能选择器、视觉验证、网络捕获、等待工具
│   ├── data/              # YAML 用例加载器、Faker 数据生成器、DB 操作助手
│   ├── logger/            # 日志（核心、脱敏、安全事件、性能监控装饰器）
│   ├── monitoring/        # 错误监控装饰器（弹窗/控制台/网络请求）
│   ├── security/          # 加密 & 密钥管理
│   └── utils/             # 通用工具
├── test_data/             # YAML 测试用例数据
├── tests/                 # pytest 测试
│   └── unit/              # 单元测试
├── output/                # 日志、Allure 结果、截图（gitignore）
├── scripts/               # 辅助脚本
└── pyproject.toml         # 项目元数据 & pytest 配置
```

---

## 3. 技能裁决表

只有匹配时调用，不匹配则跳过。

| 任务类型 | 技能 | 触发条件 |
|:---|:---|:---|
| 新功能方案设计 | `superpowers:brainstorming` | 需求模糊、涉及多模块改动 |
| 编写实施计划 | `superpowers:writing-plans` | 任务涉及 3+ 个文件或 5+ 步骤 |
| 编码实现 | `superpowers:test-driven-development` | 中量级及以上任务 |
| 测试失败排查 | `superpowers:systematic-debugging` | 遇到任何测试失败或异常行为 |
| 代码审查 | `superpowers:requesting-code-review` | 完成一个功能模块或修复后 |
| 浏览器端到端验证 | `gstack` (/qa) | 修改了 Page Object 或浏览器交互逻辑 |
| 代码质量检查 | `simplify` | 实现完成后、提交前 |
| 安全检查 | `security-review` | 涉及加密、脱敏、认证、密钥管理的改动 |
| 多任务并行执行 | `superpowers:dispatching-parallel-agents` | 2+ 独立任务可并行推进 |
| 完成前验证 | `superpowers:verification-before-completion` | 声称"完成"前必须有证据 |
| 分支完成收尾 | `superpowers:finishing-a-development-branch` | 实现完成、测试全绿、准备合并 |

---

## 4. 开发流程（按复杂度分流）

### 4.1 轻量级 — 直接修改
修改单个 YAML 数据、调整日志级别/超时参数、修改 pytest 标记、修复拼写错误。

- 流程：直接改 → 运行相关测试 → 人工确认
- 省略：brainstorming、plan、TDD、code review、QA

### 4.2 中量级 — 简化流程
新增一个 Page Object / API 端点测试 / fixture、修复一个明确 bug、重构单个函数。

- 流程：brief brainstorming → TDD（红-绿-重构）→ simplify → 运行测试确认
- 省略：正式 plan 文档、QA 浏览器验证

### 4.3 重量级 — 完整流程
新增认证流程、改造 API 客户端架构、新增模块（如新错误监控器）、跨模块重构。

- 流程：
  1. `superpowers:brainstorming` → 输出需求梳理
  2. `superpowers:writing-plans` → 输出 `PLAN.md`
  3. `superpowers:test-driven-development` → 红-绿-重构循环
  4. `superpowers:requesting-code-review` → 独立审查
  5. `gstack` /qa → 浏览器端到端验证（如涉及 UI）
  6. `superpowers:verification-before-completion` → 证据确认
  7. `superpowers:finishing-a-development-branch` → 合并/PR

---

## 5. pytest 专项约束

### 标记系统
```python
@pytest.mark.smoke              # 冒烟测试
@pytest.mark.regression          # 回归测试
@pytest.mark.env("beta", "prod") # 限制运行环境（alpha/beta/prod）
@pytest.mark.yaml_data(          # YAML 数据驱动
    file="login_page.yaml",
    group="valid_login"
)
```

### 运行约定
- **修改 conftest.py 后**：必须运行 `pytest --co` 确认收集无误
- **修改 YAML 测试数据后**：运行关联测试，确认参数化正常
- **新增自定义标记后**：必须在 `pyproject.toml` 的 `[tool.pytest.ini_options.markers]` 中注册
- **默认运行命令**：`pytest -v --strict-markers -vs --alluredir ./output/allure-results --clean-alluredir`

### Fixture 约定
- 重 fixture（浏览器、API 客户端、登录状态）放在 `conftest.py`
- 页面对象优先通过 fixture 注入，不在测试函数内直接创建浏览器实例
- 测试数据优先使用 YAML 数据驱动，避免在测试代码中硬编码参数

---

## 6. 代码约定

### 日志
```python
from logger import logger                        # 通用日志器
from logger import log_step, log_duration         # 步骤/耗时追踪
from logger import log_performance                # 性能装饰器
from logger import RequestLogger                  # API 请求日志
```
- 日志自动脱敏敏感字段（password、token、secret、authorization 等）
- 禁止使用 `print()` 替代 logger
- API 请求日志通过 `RequestLogger` 自动定位业务调用代码位置

### 配置访问
```python
from config import settings
# 单例，自动合并：YAML 基础配置 → 环境变量覆盖 → 命令行覆盖
url = settings.get("storage.neo4j.uri", "bolt://localhost:7687")
```
- 敏感配置使用 Pydantic `SecretStr`（自动从日志/序列化中排除）
- 环境切换：`--env beta` 或 `ENV=beta`

### API 客户端
```python
from api_client.client import APIClient
client = APIClient("https://api.example.com", timeout=30)
client.set_auth_token(token)
response = client.get("/users")
client.assert_status(response, 200).assert_field_exists("data.id")
```
- 失败自动重试 3 次（指数退避）
- 请求/响应自动过滤敏感信息并附加到 Allure 报告
- 断言支持链式调用

### Page Object
- 选择器与页面逻辑分离（独立 selector 类）
- 可复用组件放 `pages/components/`
- 继承 `base_page.py` 的通用方法，避免为每页重复实现导航/等待
- 页面交互后使用显式等待，禁止 `time.sleep()`

### YAML 测试数据
```yaml
# 文件放在 test_data/ 目录下
# 引用方式：@pytest.mark.yaml_data(file="xxx.yaml", group="group_name")
# 测试函数的参数名需与 YAML 字段名一致
```

---

## 7. 安全红线

- ❌ 硬编码 URL、用户名、密码、Token、API Key——一律走环境变量或 `.env`
- ❌ 向 git 提交 `.env` 文件或含密钥的 YAML 配置
- ❌ 在日志中明文输出敏感字段（框架已自动脱敏，勿绕过）
- ❌ 在测试断言中硬编码生产环境真实用户凭证

---

## 8. 禁止事项

- ❌ 跳过 TDD 直接写实现代码（中量级及以上任务）
- ❌ 修改 conftest.py 后不运行测试收集确认
- ❌ 无验证证据就声称"应该没问题"或"完成了"
- ❌ 代码作者自行审查自己的代码（必须走 `requesting-code-review`）
- ❌ 在 Page Object 中使用 `time.sleep()` 替代显式等待
- ❌ 绕过框架日志模块直接使用 `logging.info()` 或 `print()`
