playwright-automation-framework/
│
├── .github/                          # GitHub 配置
│   ├── workflows/                    # CI/CD 工作流
│   │   ├── ci.yml                    # 持续集成
│   │   ├── nightly.yml               # 每日构建
│   │   └── release.yml               # 版本发布
│   └── ISSUE_TEMPLATE/               # Issue 模板
│       ├── bug_report.md
│       └── feature_request.md
│
├── conf/                             # 配置模块
│   ├── __init__.py
│   ├── settings.py                   # 全局配置（环境变量集成）
│   ├── settings_dev.py               # 开发环境配置
│   ├── settings_staging.py           # 预发布环境配置
│   ├── settings_prod.py              # 生产环境配置
│   ├── locators_i18n.py              # 国际化文本映射
│   ├── test_data.py                  # 测试数据管理
│   ├── secrets.py                    # 敏感信息管理（加密）
│   └── constants.py                  # 常量定义
│
├── pages/                            # 页面对象层 (Page Object Model)
│   ├── __init__.py
│   ├── base_page.py                  # 基础页面类（核心封装）
│   ├── components/                   # 可复用组件
│   │   ├── __init__.py
│   │   ├── header_component.py       # 头部组件
│   │   ├── sidebar_component.py      # 侧边栏组件
│   │   └── modal_component.py        # 弹窗组件
│   ├── common/                       # 通用页面
│   │   ├── __init__.py
│   │   ├── login_page.py             # 登录页
│   │   ├── dashboard_page.py         # 仪表盘
│   │   └── settings_page.py          # 设置页
│   └── business/                     # 业务页面
│       ├── __init__.py
│       ├── baidu_page.py             # 百度搜索页（示例）
│       ├── ecommerce/                # 电商模块
│       │   ├── product_list_page.py
│       │   ├── product_detail_page.py
│       │   ├── cart_page.py
│       │   └── checkout_page.py
│       └── crm/                      # CRM 模块
│           ├── contact_list_page.py
│           └── contact_detail_page.py
│
├── tests/                            # 测试用例层
│   ├── __init__.py
│   ├── conftest.py                   # Pytest 全局配置
│   ├── fixtures/                     # 自定义 Fixture
│   │   ├── __init__.py
│   │   ├── api_fixtures.py           # API 相关 Fixture
│   │   ├── db_fixtures.py            # 数据库 Fixture
│   │   └── user_fixtures.py          # 用户数据 Fixture
│   ├── unit/                         # 单元测试
│   │   ├── test_selector_helper.py
│   │   ├── test_logger.py
│   │   └── test_helpers.py
│   ├── integration/                  # 集成测试
│   │   ├── test_api_integration.py
│   │   └── test_db_integration.py
│   ├── ui/                           # UI 测试（核心）
│   │   ├── __init__.py
│   │   ├── smoke/                    # 冒烟测试
│   │   │   ├── test_login_smoke.py
│   │   │   └── test_dashboard_smoke.py
│   │   ├── regression/               # 回归测试
│   │   │   ├── baidu/
│   │   │   │   ├── test_baidu_search.py
│   │   │   │   ├── test_baidu_navigation.py
│   │   │   │   └── test_baidu_suggestions.py
│   │   │   ├── ecommerce/
│   │   │   │   ├── test_product_flow.py
│   │   │   │   └── test_checkout_flow.py
│   │   │   └── crm/
│   │   │       ├── test_contact_management.py
│   │   │       └── test_lead_conversion.py
│   │   └── visual/                   # 视觉测试
│   │       ├── test_layout.py
│   │       └── test_responsive.py
│   └── api/                          # API 测试
│       ├── test_auth_api.py
│       └── test_product_api.py
│
├── utils/                            # 工具模块
│   ├── __init__.py
│   ├── selector_helper.py            # 智能选择器（核心）
│   ├── screenshot_helper.py          # 高级截图（带高亮/标注）
│   ├── logger.py                     # 企业级日志（彩色/脱敏/轮转）
│   ├── report_generator.py           # 多格式报告生成
│   ├── helpers.py                    # 通用工具函数
│   ├── api_client.py                 # API 客户端封装
│   ├── db_helper.py                  # 数据库操作助手
│   ├── excel_helper.py               # Excel 数据处理
│   ├── csv_helper.py                 # CSV 数据处理
│   ├── json_helper.py                # JSON 数据处理
│   ├── xml_helper.py                 # XML 数据处理
│   ├── cache_helper.py               # 缓存管理
│   ├── retry_helper.py               # 重试机制
│   ├── performance_monitor.py        # 性能监控
│   ├── security_scanner.py           # 安全扫描
│   └── templates/                    # 报告模板
│       ├── report.html.j2
│       └── email_template.html.j2
│
├── scripts/                          # 运维脚本
│   ├── __init__.py
│   ├── run_tests.py                  # 主测试运行器
│   ├── generate_report.py            # 报告生成器
│   ├── setup_env.py                  # 环境初始化
│   ├── cleanup.py                    # 清理临时文件
│   ├── backup_results.py             # 备份测试结果
│   ├── send_notification.py          # 通知发送（邮件/钉钉）
│   ├── compare_screenshots.py        # 截图对比
│   └── migrate_test_data.py          # 测试数据迁移
│
├── reports/                          # 测试报告
│   ├── allure-results/               # Allure 原始结果（.json）
│   ├── allure-report/                # Allure 静态报告
│   ├── html/                         # HTML 报告
│   │   ├── report_20240131_103045.html
│   │   └── summary.json
│   ├── junit/                        # JUnit XML 报告
│   │   └── results.xml
│   ├── json/                         # JSON 格式报告
│   │   └── report_20240131_103045.json
│   ├── csv/                          # CSV 格式报告
│   │   └── results.csv
│   ├── logs/                         # 日志文件
│   │   ├── test_run.log              # 常规日志（按天轮转）
│   │   ├── error_20240131.log        # 错误日志
│   │   ├── performance.log           # 性能日志
│   │   ├── security.log              # 安全审计日志
│   │   └── structured_20240131.log   # JSON 结构化日志
│   └── metrics/                      # 质量指标
│       ├── coverage.json             # 测试覆盖率
│       ├── flaky_tests.json          # 不稳定测试
│       └── performance_trends.json   # 性能趋势
│
├── screenshots/                      # 截图存储
│   ├── failures/                     # 失败截图
│   │   ├── failure_test_login_20240131_103045.png
│   │   └── ...
│   ├── elements/                     # 元素级截图
│   ├── fullpages/                    # 全页截图
│   └── comparisons/                  # 截图对比
│
├── videos/                           # 录屏存储
│   ├── test_login_20240131_103045.webm
│   └── ...
│
├── test_data/                        # 测试数据文件
│   ├── users.csv                     # 用户数据
│   ├── products.json                 # 产品数据
│   ├── test_cases.xlsx               # 测试用例表
│   └── localization/                 # 多语言数据
│       ├── zh-CN.json
│       ├── en-US.json
│       └── ja-JP.json
│
├── docs/                             # 项目文档
│   ├── ARCHITECTURE.md               # 架构设计
│   ├── GETTING_STARTED.md            # 快速开始
│   ├── PAGE_OBJECT_GUIDE.md          # Page Object 指南
│   ├── SELECTOR_STRATEGY.md          # 选择器策略
│   ├── REPORTING_GUIDE.md            # 报告指南
│   ├── TROUBLESHOOTING.md            # 故障排查
│   ├── API_REFERENCE.md              # API 参考
│   └── BEST_PRACTICES.md             # 最佳实践
│
├── docker/                           # Docker 配置
│   ├── Dockerfile                    # 应用镜像
│   ├── docker-compose.yml            # 服务编排
│   └── playwright.Dockerfile         # Playwright 专用镜像
│
├── .allure/                          # Allure 配置
│   └── config.json
│
├── .playwright/                      # Playwright 配置
│   └── package.json
│
├── .vscode/                          # VSCode 配置
│   ├── settings.json
│   ├── launch.json
│   └── tasks.json
│
├── requirements/                     # 依赖管理
│   ├── base.txt                      # 基础依赖
│   ├── dev.txt                       # 开发依赖
│   ├── test.txt                      # 测试依赖
│   └── prod.txt                      # 生产依赖
│
├── .env.example                      # 环境变量模板
├── .env                              # 本地环境变量（.gitignore）
├── .gitignore                        # Git 忽略规则
├── .pre-commit-config.yaml           # Pre-commit 配置
├── pytest.ini                        # Pytest 配置
├── setup.cfg                         # 项目配置
├── setup.py                          # 安装脚本
├── requirements.txt                  # 主依赖文件
├── pyproject.toml                    # Python 项目配置
├── README.md                         # 项目概览
├── CHANGELOG.md                      # 变更日志
├── LICENSE                           # 许可证
└── SECURITY.md                       # 安全策略