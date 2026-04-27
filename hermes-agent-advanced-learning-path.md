# Hermes Agent 进阶学习路径

> 面向 Python 开发者的完整学习指南  
> 版本：1.0  
> 最后更新：2026 年 4 月

---

## 目录

1. [学习路径概览](#学习路径概览)
2. [阶段一：基础入门（1-2 周）](#阶段一基础入门 1-2 周)
3. [阶段二：核心工具与技能（2-3 周）](#阶段二核心工具与技能 2-3 周)
4. [阶段三：高级功能与自动化（3-4 周）](#阶段三高级功能与自动化 3-4 周)
5. [阶段四：多智能体与扩展开发（4-6 周）](#阶段四多智能体与扩展开发 4-6 周)
6. [阶段五：生产部署与最佳实践](#阶段五生产部署与最佳实践)
7. [实战项目建议](#实战项目建议)
8. [参考资料与资源](#参考资料与资源)

---

## 学习路径概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Hermes Agent 学习路径                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  阶段一          阶段二          阶段三          阶段四          │
│  基础入门   →   核心工具   →   高级功能   →   多智能体         │
│  (1-2 周)      (2-3 周)       (3-4 周)       (4-6 周)          │
│     ↓             ↓             ↓             ↓                │
│  安装配置      工具集使用     定时任务      子智能体委托       │
│  CLI 命令      技能系统       Webhook       自定义工具开发     │
│  会话管理      文件/终端      MCP 服务器     多智能体编排       │
│                                                                 │
│                              ↓                                  │
│                        阶段五：生产部署                          │
│                        Gateway 部署                             │
│                        监控与日志                               │
│                        最佳实践                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 前置要求

- ✅ Python 编程能力（你已具备）
- ✅ Linux/macOS 终端基础
- ✅ Git 版本控制基础
- ✅ API 和 HTTP 基础概念
- ✅ YAML/JSON 配置文件基础

### 学习成果

完成本学习路径后，你将能够：

1. **熟练使用** Hermes Agent 进行日常开发任务
2. **自动化**重复性工作流（定时任务、Webhook）
3. **扩展** Hermes 功能（自定义工具、MCP 服务器）
4. **编排**多智能体系统完成复杂项目
5. **部署**生产级 Hermes Gateway 服务

---

## 阶段一：基础入门（1-2 周）

### 学习目标

- 理解 Hermes Agent 的核心概念和架构
- 完成安装和基础配置
- 掌握 CLI 基本命令和会话管理
- 能够进行简单的对话式任务执行

### 1.1 核心概念

#### 什么是 Hermes Agent？

Hermes Agent 是一个开源 AI 智能体框架，由 Nous Research 开发。它能够：

- 在终端、消息平台（Telegram、Discord 等）和 IDE 中运行
- 使用工具调用与系统交互（文件、终端、网络等）
- 通过"技能"系统学习和保存工作流程
- 跨会话保持记忆和上下文

#### 关键特性

| 特性 | 说明 |
|------|------|
| **技能系统** | 将复杂任务保存为可重用的技能文档 |
| **持久记忆** | 跨会话记住用户偏好、环境细节 |
| **多平台网关** | 同一智能体运行在 10+ 消息平台 |
| **提供者无关** | 支持 20+ LLM 提供者，可随时切换 |
| **配置文件** | 支持多配置文件，隔离不同项目 |

### 1.2 安装与配置

#### 快速安装

```bash
# 方法 1：官方安装脚本（推荐）
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 方法 2：从源码安装
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
pip install -e .
```

#### 初始配置

```bash
# 运行设置向导
hermes setup

# 或手动配置
hermes config edit  # 打开 config.yaml
hermes config env-path  # 查看.env 文件位置
```

#### 配置示例 (~/.hermes/config.yaml)

```yaml
# 模型配置
model:
  default: anthropic/claude-sonnet-4
  provider: anthropic
  context_length: 200000

# 终端配置
terminal:
  backend: local
  cwd: ~/projects
  timeout: 180

# 工具集启用
tools:
  enabled:
    - terminal
    - file
    - web
    - browser
    - code_execution

# 记忆配置
memory:
  memory_enabled: true
  user_profile_enabled: true

# 显示配置
display:
  skin: default
  tool_progress: true
  show_cost: true
```

#### 环境变量 (~/.hermes/.env)

```bash
# LLM API 密钥
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...

# 可选：其他服务密钥
GROQ_API_KEY=gsk_...
ELEVENLABS_API_KEY=...
```

### 1.3 CLI 基础命令

#### 启动与对话

```bash
# 交互式对话（默认）
hermes

# 单次查询
hermes chat -q "什么是 Python 的装饰器？"

# 指定模型
hermes chat -m anthropic/claude-sonnet-4 -q "解释异步编程"

# 恢复会话
hermes --resume SESSION_ID
hermes --continue  # 恢复最近的会话
```

#### 会话管理

```bash
# 列出会话
hermes sessions list

# 浏览会话
hermes sessions browse

# 重命名会话
hermes sessions rename OLD_ID "新名称"

# 导出会话
hermes sessions export sessions.jsonl

# 清理旧会话
hermes sessions prune --older-than 30
```

#### 配置管理

```bash
# 查看配置
hermes config

# 编辑配置
hermes config edit

# 设置配置项
hermes config set model.default anthropic/claude-sonnet-4
hermes config set terminal.timeout 300

# 检查配置
hermes config check

# 查看配置路径
hermes config path
hermes config env-path
```

### 1.4 斜杠命令（会话内）

在交互式会话中，可以使用斜杠命令：

```bash
# 会话控制
/new          # 新会话
/clear        # 清屏并开始新会话
/retry        # 重发最后一条消息
/undo         # 撤销最后一条交换
/title NAME   # 命名会话
/quit         # 退出

# 配置
/model        # 查看/更改模型
/verbose      # 切换详细输出
/yolo         # 切换危险命令跳过确认

# 工具与技能
/tools        # 管理工具
/skills       # 搜索/安装技能
/skill NAME   # 加载技能到会话

# 实用工具
/help         # 显示帮助
/usage        # 查看 token 使用
/insights     # 使用分析
```

### 1.5 实践练习

#### 练习 1：环境设置

```bash
# 1. 安装 Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 2. 运行健康检查
hermes doctor

# 3. 配置模型
hermes model

# 4. 测试对话
hermes chat -q "你好，请用 Python 写一个快速排序"
```

#### 练习 2：会话管理

```bash
# 1. 开始一个新会话并完成一个任务
hermes chat -q "创建一个 Python 项目结构"

# 2. 列出所有会话
hermes sessions list

# 3. 恢复之前的会话
hermes --continue

# 4. 重命名会话
hermes sessions rename $(hermes sessions list | head -1 | cut -d' ' -f1) "python-project"
```

#### 练习 3：配置探索

```bash
# 1. 查看当前配置
hermes config

# 2. 修改超时时间
hermes config set terminal.timeout 600

# 3. 启用代码执行
hermes tools enable code_execution

# 4. 验证更改
hermes config check
```

### 1.6 推荐资源

- [Hermes 官方文档](https://hermes-agent.nousresearch.com/docs/)
- [CLI 命令参考](https://hermes-agent.nousresearch.com/docs/reference/cli-commands)
- [配置指南](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)
- [GitHub 仓库](https://github.com/NousResearch/hermes-agent)

---

## 阶段二：核心工具与技能（2-3 周）

### 学习目标

- 掌握所有核心工具集的使用
- 理解技能系统的工作原理
- 能够编写和使用自定义技能
- 熟练进行文件操作和终端命令执行

### 2.1 工具集详解

#### 可用工具集

| 工具集 | 功能 | 典型用途 |
|--------|------|----------|
| `terminal` | 执行 shell 命令 | 运行脚本、构建项目、git 操作 |
| `file` | 文件读写搜索 | 读取代码、修改配置、搜索内容 |
| `web` | 网页搜索和提取 | 研究文档、查找信息 |
| `browser` | 浏览器自动化 | 测试网页、抓取动态内容 |
| `code_execution` | Python 代码执行 | 运行测试、数据处理 |
| `vision` | 图像分析 | 识别截图、分析图表 |
| `search` | 文件内容搜索 | 代码库搜索、日志分析 |
| `memory` | 持久化记忆 | 保存用户偏好、项目信息 |
| `session_search` | 搜索历史会话 | 查找之前的讨论 |
| `delegation` | 子智能体委托 | 并行任务执行 |
| `cronjob` | 定时任务 | 自动化定期任务 |
| `clarify` | 向用户提问 | 获取澄清信息 |
| `messaging` | 发送消息 | Telegram/Discord 通知 |

#### 工具管理

```bash
# 交互式管理工具
hermes tools

# 列出所有工具
hermes tools list

# 启用工具集
hermes tools enable browser
hermes tools enable code_execution

# 禁用工具集
hermes tools disable web
```

### 2.2 文件工具使用

#### 读取文件

```python
# 在对话中请求
"读取 src/main.py 的内容"

# 或使用终端命令
hermes chat -q "读取并分析 project/config.yaml"
```

#### 写入文件

```python
# 创建新文件
"创建一个 Python 文件 hello.py，包含打印 Hello World 的代码"

# 修改现有文件
"在 src/utils.py 中添加一个计算斐波那契的函数"
```

#### 搜索文件

```python
# 搜索内容
"在 src/目录下搜索所有包含'import requests'的 Python 文件"

# 搜索文件
"找到项目中所有的测试文件"
```

#### 修补文件

```python
# 精确替换
"将 config.py 中的 DEBUG = True 改为 DEBUG = False"
```

### 2.3 终端工具使用

#### 执行命令

```python
# 简单命令
"运行 pytest tests/ -v"

# 带工作目录
"在 ~/projects/myapp 目录下运行 npm install"

# 后台任务
"启动 Flask 开发服务器并在后台运行"
```

#### 进程管理

```python
# 列出后台进程
"显示所有后台进程"

# 等待进程完成
"等待构建完成并报告结果"

# 终止进程
"停止所有 Python 进程"
```

### 2.4 技能系统

#### 什么是技能？

技能是 Hermes 的核心学习机制。它将复杂任务保存为可重用的 Markdown 文档，包含：

- 触发条件
- 执行步骤
- 注意事项
- 相关资源

#### 技能结构

```markdown
---
name: my-skill
description: 技能描述
version: 1.0.0
author: Your Name
---

# 技能名称

## 概述

技能的简要说明。

## 何时使用

- 使用场景 1
- 使用场景 2

## 执行步骤

1. 第一步
2. 第二步
3. ...

## 示例

```python
# 代码示例
```

## 注意事项

- 注意点 1
- 注意点 2
```

#### 技能管理

```bash
# 列出已安装技能
hermes skills list

# 搜索技能
hermes skills search "code review"

# 安装技能
hermes skills install SKILL_ID

# 预览技能
hermes skills inspect SKILL_ID

# 更新技能
hermes skills update

# 卸载技能
hermes skills uninstall SKILL_NAME

# 浏览所有可用技能
hermes skills browse
```

#### 在会话中使用技能

```bash
# 加载技能到当前会话
/skill skill-name

# 启动时预加载技能
hermes -s skill-name -s another-skill

# 在对话中引用
"使用 test-driven-development 技能来实现这个功能"
```

### 2.5 实践练习

#### 练习 1：文件操作工作流

```bash
# 任务：创建一个 Python 项目并添加功能

hermes chat -q "
1. 创建项目结构：myproject/{src,tests,docs}
2. 在 src/创建__init__.py 和 main.py
3. 在 tests/创建 test_main.py
4. 创建 requirements.txt
5. 初始化 git 仓库
"
```

#### 练习 2：技能探索

```bash
# 1. 浏览可用技能
hermes skills browse

# 2. 安装开发相关技能
hermes skills install writing-plans
hermes skills install test-driven-development
hermes skills install systematic-debugging

# 3. 在会话中使用
hermes chat -q "使用 writing-plans 技能为我制定一个实现用户认证系统的计划"
```

#### 练习 3：代码执行

```bash
# 1. 启用代码执行工具
hermes tools enable code_execution

# 2. 执行 Python 代码
hermes chat -q "
执行以下 Python 代码并返回结果：

import math
def calculate_stats(numbers):
    return {
        'mean': sum(numbers)/len(numbers),
        'std': math.sqrt(sum((x-sum(numbers)/len(numbers))**2 for x in numbers)/len(numbers))
    }

print(calculate_stats([1,2,3,4,5,6,7,8,9,10]))
"
```

#### 练习 4：创建自定义技能

```bash
# 1. 创建技能目录
mkdir -p ~/.hermes/skills/my-skills/python-project-template

# 2. 创建 SKILL.md
cat > ~/.hermes/skills/my-skills/python-project-template/SKILL.md << 'EOF'
---
name: python-project-template
description: 创建标准 Python 项目结构
version: 1.0.0
author: Your Name
---

# Python 项目模板

## 何时使用

当需要创建新的 Python 项目时使用此技能。

## 执行步骤

1. 创建目录结构：
   - project_name/
     - src/
     - tests/
     - docs/
     - .github/workflows/

2. 创建基础文件：
   - pyproject.toml
   - README.md
   - .gitignore
   - src/__init__.py

3. 初始化 git 仓库

4. 创建虚拟环境

## 示例命令

```bash
mkdir -p project_name/{src,tests,docs,.github/workflows}
cd project_name
git init
python -m venv venv
```
EOF

# 3. 测试技能
hermes chat -q "使用 python-project-template 技能创建一个名为 myapi 的项目"
```

### 2.6 推荐资源

- [工具参考文档](https://hermes-agent.nousresearch.com/docs/reference/tools-reference)
- [技能目录](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog)
- [技能开发指南](https://hermes-agent.nousresearch.com/docs/developer-guide/skills)

---

## 阶段三：高级功能与自动化（3-4 周）

### 学习目标

- 掌握定时任务（Cron）系统
- 理解和使用 Webhook
- 配置 MCP 服务器
- 实现自动化工作流

### 3.1 定时任务系统

#### Cron 基础

```bash
# 列出所有任务
hermes cron list

# 创建定时任务
hermes cron create "30m"  # 每 30 分钟
hermes cron create "every 2h"  # 每 2 小时
hermes cron create "0 9 * * *"  # 每天早上 9 点（cron 表达式）

# 查看任务
hermes cron list

# 暂停/恢复任务
hermes cron pause JOB_ID
hermes cron resume JOB_ID

# 手动触发
hermes cron run JOB_ID

# 删除任务
hermes cron remove JOB_ID

# 查看调度器状态
hermes cron status
```

#### Cron 表达式参考

```
* * * * *
│ │ │ │ │
│ │ │ │ └─ 星期几 (0-7, 0 和 7 都是周日)
│ │ │ └─── 月份 (1-12)
│ │ └───── 日期 (1-31)
│ └─────── 小时 (0-23)
└───────── 分钟 (0-59)

# 示例
0 9 * * *      # 每天早上 9 点
*/15 * * * *   # 每 15 分钟
0 0 * * 0      # 每周日凌晨
0 0 1 * *      # 每月 1 号凌晨
```

#### 定时任务示例

```bash
# 示例 1：每日备份
hermes cron create "0 2 * * *" --name "daily-backup" --prompt "
执行以下备份任务：
1. 压缩 ~/projects 目录
2. 复制到备份位置
3. 删除 7 天前的备份
4. 发送完成通知到 Telegram
"

# 示例 2：定期检查
hermes cron create "*/30 * * * *" --name "health-check" --prompt "
检查 API 健康状态：
1. 调用 https://api.example.com/health
2. 如果失败，发送警报
3. 记录响应时间到日志
"

# 示例 3：数据同步
hermes cron create "0 */4 * * *" --name "data-sync" --prompt "
同步数据库：
1. 从主数据库导出数据
2. 导入到分析数据库
3. 验证数据完整性
4. 报告同步结果
"
```

### 3.2 Webhook 系统

#### Webhook 基础

```bash
# 创建 webhook 订阅
hermes webhook subscribe my-endpoint

# 列出所有订阅
hermes webhook list

# 测试 webhook
hermes webhook test my-endpoint

# 删除订阅
hermes webhook remove my-endpoint
```

#### Webhook 使用示例

```bash
# 1. 创建 webhook
hermes webhook subscribe github-deploy

# 2. 在 GitHub 中配置 webhook
# Settings → Webhooks → Add webhook
# Payload URL: https://your-hermes-instance.com/webhooks/github-deploy
# Content type: application/json

# 3. 测试
curl -X POST https://your-hermes-instance.com/webhooks/github-deploy \
  -H "Content-Type: application/json" \
  -d '{"action": "push", "ref": "refs/heads/main"}'
```

#### Webhook 处理示例

```python
# webhook_handler.py
# 当 webhook 触发时执行的脚本

import json
import sys

def handle_github_deploy(payload):
    """处理 GitHub 部署 webhook"""
    if payload.get('action') == 'push':
        ref = payload.get('ref', '')
        if 'main' in ref:
            # 触发部署流程
            print("触发主分支部署...")
            # 这里可以调用 hermes 命令
    return {"status": "success"}

if __name__ == "__main__":
    payload = json.loads(sys.stdin.read())
    result = handle_github_deploy(payload)
    print(json.dumps(result))
```

### 3.3 MCP 服务器

#### 什么是 MCP？

MCP（Model Context Protocol）是一个标准协议，允许 AI 智能体与外部工具和服务交互。

#### MCP 管理

```bash
# 添加 MCP 服务器
hermes mcp add github -- npx @modelcontextprotocol/server-github

# 添加数据库服务器
hermes mcp add postgres -- npx @anthropic-ai/server-postgres \
  --connection-string postgresql://localhost/mydb

# 列出服务器
hermes mcp list

# 测试连接
hermes mcp test github

# 配置服务器
hermes mcp configure github

# 删除服务器
hermes mcp remove github
```

#### 常用 MCP 服务器

```bash
# GitHub
hermes mcp add -s user github -- npx @modelcontextprotocol/server-github

# PostgreSQL
hermes mcp add -s local postgres -- npx @anthropic-ai/server-postgres \
  --connection-string postgresql://user:pass@localhost/db

# Puppeteer（网页测试）
hermes mcp add puppeteer -- npx @anthropic-ai/server-puppeteer

# 文件系统
hermes mcp add filesystem -- npx @modelcontextprotocol/server-filesystem \
  ~/projects

# Slack
hermes mcp add slack -- npx @modelcontextprotocol/server-slack
```

#### MCP 作用域

| 标志 | 作用域 | 存储位置 |
|------|--------|----------|
| `-s user` | 全局（所有项目） | `~/.claude.json` |
| `-s local` | 当前项目（个人） | `.claude/settings.local.json` |
| `-s project` | 当前项目（团队） | `.claude/settings.json` |

### 3.4 自动化工作流

#### 工作流示例 1：CI/CD 自动化

```bash
# 创建定时任务检查 PR
hermes cron create "*/15 * * * *" --name "pr-checker" --prompt "
检查 GitHub PR 状态：
1. 获取所有打开的 PR
2. 检查 CI 状态
3. 如果有失败的构建，通知开发者
4. 如果 PR 已批准且 CI 通过，提醒可以合并
"
```

#### 工作流示例 2：监控和警报

```bash
# 创建监控任务
hermes cron create "*/5 * * * *" --name "api-monitor" --prompt "
监控 API 健康：
1. 调用所有端点的健康检查
2. 记录响应时间和状态码
3. 如果任何端点失败或响应时间>1s，发送警报
4. 生成每日报告
"
```

#### 工作流示例 3：数据管道

```bash
# 创建数据同步任务
hermes cron create "0 */6 * * *" --name "etl-pipeline" --prompt "
执行 ETL 流程：
1. 从源数据库提取数据
2. 转换和清洗数据
3. 加载到目标数据库
4. 验证数据完整性
5. 发送执行报告
"
```

### 3.5 实践练习

#### 练习 1：设置每日报告

```bash
# 1. 创建每日报告任务
hermes cron create "0 8 * * *" --name "daily-report" --prompt "
生成每日报告：
1. 统计昨天的 git 提交数
2. 列出完成的 PR
3. 检查测试覆盖率变化
4. 发送报告到指定频道
"

# 2. 验证任务
hermes cron list

# 3. 手动触发测试
hermes cron run $(hermes cron list | grep daily-report | cut -d' ' -f1)
```

#### 练习 2：配置 MCP 服务器

```bash
# 1. 添加 GitHub MCP 服务器
hermes mcp add -s user github -- npx @modelcontextprotocol/server-github

# 2. 测试连接
hermes mcp test github

# 3. 在对话中使用
hermes chat -q "使用 GitHub MCP 服务器列出我的前 5 个仓库"
```

#### 练习 3：创建 Webhook 处理器

```bash
# 1. 创建 webhook
hermes webhook subscribe deploy-trigger

# 2. 创建处理脚本
cat > ~/scripts/deploy-handler.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import subprocess

def handle_deploy(payload):
    branch = payload.get('branch', 'main')
    print(f"开始部署 {branch} 分支...")
    
    # 执行部署命令
    result = subprocess.run(
        ['git', 'pull', 'origin', branch],
        capture_output=True,
        text=True
    )
    
    return {
        'status': 'success' if result.returncode == 0 else 'failed',
        'output': result.stdout
    }

if __name__ == "__main__":
    payload = json.loads(sys.stdin.read())
    result = handle_deploy(payload)
    print(json.dumps(result))
EOF

chmod +x ~/scripts/deploy-handler.py
```

### 3.6 推荐资源

- [Cron 文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)
- [MCP 指南](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
- [MCP 服务器目录](https://github.com/modelcontextprotocol/servers)

---

## 阶段四：多智能体与扩展开发（4-6 周）

### 学习目标

- 理解子智能体委托机制
- 掌握多智能体编排
- 能够开发自定义工具
- 实现复杂的多智能体工作流

### 4.1 子智能体委托

#### delegate_task 基础

```python
# 基本用法
delegate_task(
    goal="实现用户认证功能",
    context="项目使用 Flask，需要 JWT 认证",
    toolsets=['terminal', 'file']
)
```

#### 委托模式

| 模式 | 说明 | 使用场景 |
|------|------|----------|
| 单任务 | 一个子智能体完成一个任务 | 独立功能开发 |
| 批量并行 | 多个子智能体同时执行 | 独立模块开发 |
| 编排者 | 子智能体可以再委托 | 大型项目分解 |

#### 单任务委托示例

```python
delegate_task(
    goal="为 User 模型添加密码哈希功能",
    context="""
    任务详情：
    - 文件：src/models/user.py
    - 使用 bcrypt 库
    - 添加 set_password() 和 check_password() 方法
    
    项目上下文：
    - Python 3.11, Flask 应用
    - 现有模型在 src/models/
    - 测试使用 pytest
    
    遵循 TDD：
    1. 先写测试
    2. 运行测试确认失败
    3. 实现最小代码
    4. 验证测试通过
    """,
    toolsets=['terminal', 'file']
)
```

#### 批量并行委托

```python
delegate_task(
    tasks=[
        {
            "goal": "实现用户注册 API",
            "context": "创建 POST /api/register 端点",
            "toolsets": ['terminal', 'file']
        },
        {
            "goal": "实现用户登录 API",
            "context": "创建 POST /api/login 端点",
            "toolsets": ['terminal', 'file']
        },
        {
            "goal": "实现用户信息 API",
            "context": "创建 GET /api/user 端点",
            "toolsets": ['terminal', 'file']
        }
    ]
)
```

### 4.2 多智能体编排

#### 编排者模式

```python
# 创建一个编排者智能体
delegate_task(
    goal="协调整个认证系统的开发",
    context="需要开发注册、登录、令牌刷新三个模块",
    role="orchestrator",  # 编排者角色
    toolsets=['terminal', 'file']
)
```

#### 智能体间通信

```python
# 智能体 A：后端
terminal(command="tmux new-session -d -s backend 'hermes -w'")
terminal(command="sleep 8 && tmux send-keys -t backend '构建用户管理 REST API' Enter")

# 智能体 B：前端
terminal(command="tmux new-session -d -s frontend 'hermes -w'")
terminal(command="sleep 8 && tmux send-keys -t frontend '构建用户管理 React 仪表板' Enter")

# 检查进度并传递上下文
backend_output = terminal(command="tmux capture-pane -t backend -p | tail -30")
terminal(command=f"tmux send-keys -t frontend '这是后端 API 架构：{backend_output}' Enter")
```

#### 两阶段审查流程

```python
# 阶段 1：规范审查
spec_review = delegate_task(
    goal="审查实现是否符合规范",
    context="""
    原始规范：
    - 创建 src/models/user.py
    - 字段：email (str), password_hash (str)
    - 使用 bcrypt
    
    检查项：
    - [ ] 所有规范要求已实现？
    - [ ] 文件路径匹配规范？
    - [ ] 函数签名匹配规范？
    - [ ] 行为符合预期？
    """
)

# 阶段 2：代码质量审查
if spec_review['status'] == 'PASS':
    quality_review = delegate_task(
        goal="审查代码质量",
        context="""
        审查文件：
        - src/models/user.py
        - tests/test_user.py
        
        检查项：
        - [ ] 遵循项目规范？
        - [ ] 适当的错误处理？
        - [ ] 清晰的命名？
        - [ ] 足够的测试覆盖？
        """
    )
```

### 4.3 自定义工具开发

#### 工具结构

```
hermes-agent/
├── tools/
│   ├── registry.py      # 工具注册表
│   └── my_tool.py       # 自定义工具
└── toolsets.py          # 工具集定义
```

#### 创建自定义工具

```python
# tools/my_custom_tool.py
import json
import os
from tools.registry import registry

def check_requirements() -> bool:
    """检查工具是否可用"""
    return bool(os.getenv("MY_API_KEY"))

def my_custom_tool(param: str, task_id: str = None) -> str:
    """
    自定义工具实现
    
    Args:
        param: 输入参数
        task_id: 任务 ID（可选）
    
    Returns:
        JSON 格式的结果
    """
    result = {
        "success": True,
        "data": f"处理了参数：{param}",
        "task_id": task_id
    }
    return json.dumps(result)

# 注册工具
registry.register(
    name="my_custom_tool",
    toolset="my_tools",
    schema={
        "name": "my_custom_tool",
        "description": "我的自定义工具描述",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {
                    "type": "string",
                    "description": "输入参数"
                },
                "task_id": {
                    "type": "string",
                    "description": "可选的任务 ID"
                }
            },
            "required": ["param"]
        }
    },
    handler=lambda args, **kw: my_custom_tool(
        param=args.get("param", ""),
        task_id=kw.get("task_id")
    ),
    check_fn=check_requirements,
    requires_env=["MY_API_KEY"],
)
```

#### 添加到工具集

```python
# toolsets.py
_HERMES_CORE_TOOLS = [
    # ... 现有工具
    "tools.my_custom_tool",  # 添加你的工具
]
```

### 4.4 技能开发

#### 完整技能示例

```markdown
---
name: api-development
description: REST API 开发工作流
version: 1.0.0
author: Your Name
tags: [api, rest, development, workflow]
---

# API 开发工作流

## 概述

本技能提供完整的 REST API 开发流程，包括设计、实现、测试和文档。

## 何时使用

- 创建新的 API 端点
- 修改现有 API
- API 重构

## 执行步骤

### 1. API 设计

1.1 定义端点路径和方法
1.2 设计请求/响应格式
1.3 定义错误码
1.4 创建 OpenAPI 规范

### 2. 实现

2.1 创建路由文件
2.2 实现业务逻辑
2.3 添加输入验证
2.4 实现错误处理

### 3. 测试

3.1 编写单元测试
3.2 编写集成测试
3.3 运行测试套件
3.4 修复失败测试

### 4. 文档

4.1 更新 API 文档
4.2 添加使用示例
4.3 更新变更日志

## 示例

### 创建用户端点

```python
# routes/users.py
from flask import Blueprint, request, jsonify

users_bp = Blueprint('users', __name__)

@users_bp.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    # 验证输入
    if not data or 'email' not in data:
        return jsonify({'error': 'Email required'}), 400
    
    # 创建用户
    user = User.create(**data)
    return jsonify(user.to_dict()), 201
```

## 注意事项

- 始终先写测试
- 使用适当的 HTTP 状态码
- 实现速率限制
- 记录所有请求
```

#### 发布技能

```bash
# 1. 创建技能目录
mkdir -p ~/.hermes/skills/my-skills/api-development

# 2. 创建 SKILL.md
# (如上所示)

# 3. 测试技能
hermes skills browse  # 应该能看到你的技能

# 4. 发布到技能中心（可选）
hermes skills publish ~/.hermes/skills/my-skills/api-development
```

### 4.5 实践练习

#### 练习 1：实现子智能体工作流

```python
# 创建一个多步骤开发任务

# 步骤 1：规划
plan = delegate_task(
    goal="为博客系统制定实现计划",
    context="需要文章 CRUD、评论系统、标签功能"
)

# 步骤 2：执行每个任务
for task in plan['tasks']:
    result = delegate_task(
        goal=task['goal'],
        context=task['context'],
        toolsets=['terminal', 'file']
    )
    
    # 审查
    review = delegate_task(
        goal="审查实现质量",
        context=f"审查文件：{result['files']}"
    )
```

#### 练习 2：创建自定义工具

```bash
# 1. 创建工具文件
cat > ~/.hermes/tools/weather_tool.py << 'EOF'
import json
import os
import requests
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("WEATHER_API_KEY"))

def get_weather(city: str) -> str:
    api_key = os.getenv("WEATHER_API_KEY")
    url = f"https://api.weatherapi.com/v1/current.json?key={api_key}&q={city}"
    
    try:
        response = requests.get(url)
        data = response.json()
        return json.dumps({
            "success": True,
            "city": data['location']['name'],
            "temp": data['current']['temp_c'],
            "condition": data['current']['condition']['text']
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

registry.register(
    name="get_weather",
    toolset="weather",
    schema={
        "name": "get_weather",
        "description": "获取城市当前天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"]
        }
    },
    handler=lambda args, **kw: get_weather(args.get("city", "")),
    check_fn=check_requirements,
    requires_env=["WEATHER_API_KEY"],
)
EOF

# 2. 添加到工具集（编辑 toolsets.py）
# 3. 测试工具
hermes tools enable weather
hermes chat -q "北京现在天气如何？"
```

#### 练习 3：多智能体协作项目

```bash
# 创建一个完整的项目开发流程

# 智能体 1：后端开发
terminal(command="tmux new-session -d -s backend-dev 'hermes -w'")
terminal(command="sleep 5 && tmux send-keys -s backend-dev '使用 Flask 创建一个博客 API，包括文章 CRUD 和评论功能' Enter")

# 智能体 2：前端开发
terminal(command="tmux new-session -d -s frontend-dev 'hermes -w'")
terminal(command="sleep 5 && tmux send-keys -s frontend-dev '使用 React 创建博客前端，连接后端 API' Enter")

# 智能体 3：测试
terminal(command="tmux new-session -d -s testing 'hermes -w'")
terminal(command="sleep 5 && tmux send-keys -s testing '为博客系统编写完整的测试套件' Enter")

# 协调进度
terminal(command="sleep 60 && for s in backend-dev frontend-dev testing; do echo \"=== $s ===\"; tmux capture-pane -t $s -p -S -10; done")
```

### 4.6 推荐资源

- [子智能体开发技能](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog#subagent-driven-development)
- [工具开发指南](https://hermes-agent.nousresearch.com/docs/developer-guide/tools)
- [技能开发文档](https://hermes-agent.nousresearch.com/docs/developer-guide/skills)

---

## 阶段五：生产部署与最佳实践

### 5.1 Gateway 部署

#### 安装 Gateway

```bash
# 安装为后台服务
hermes gateway install

# 启动服务
hermes gateway start

# 查看状态
hermes gateway status

# 查看日志
tail -f ~/.hermes/logs/gateway.log
```

#### 配置平台

```bash
# 交互式配置
hermes gateway setup

# 或手动配置 config.yaml
# gateway:
#   platforms:
#     telegram:
#       enabled: true
#       token: ${TELEGRAM_BOT_TOKEN}
#     discord:
#       enabled: true
#       token: ${DISCORD_BOT_TOKEN}
```

#### 平台特定配置

**Telegram:**
```bash
# 从 @BotFather 获取 token
export TELEGRAM_BOT_TOKEN="your-bot-token"

# 配置
hermes config set gateway.platforms.telegram.enabled true
```

**Discord:**
```bash
# 在 Discord Developer Portal 创建应用
# 启用 Message Content Intent
export DISCORD_BOT_TOKEN="your-bot-token"

# 配置
hermes config set gateway.platforms.discord.enabled true
```

**Slack:**
```bash
# 创建 Slack App，订阅事件
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."

# 配置
hermes config set gateway.platforms.slack.enabled true
```

### 5.2 监控与日志

#### 日志管理

```bash
# 查看 Gateway 日志
tail -f ~/.hermes/logs/gateway.log

# 查看错误日志
grep -i "error\|failed" ~/.hermes/logs/gateway.log | tail -50

# 日志轮转配置
# 在 config.yaml 中：
# logging:
#   rotation: daily
#   retention_days: 30
```

#### 使用分析

```bash
# 查看使用统计
hermes insights

# 查看最近 N 天
hermes insights --days 7

# 会话统计
hermes sessions stats
```

### 5.3 最佳实践

#### 安全实践

```yaml
# config.yaml
security:
  # 启用 Tirith 安全检查
  tirith_enabled: true
  
  # 网站黑名单
  website_blocklist:
    - malicious-site.com
  
  # 命令审批
  terminal:
    require_approval:
      - "rm -rf *"
      - "git push --force"
      - "DROP TABLE*"
```

#### 性能优化

```yaml
# config.yaml
# 上下文压缩
compression:
  enabled: true
  threshold: 0.50  # 50% 时触发
  target_ratio: 0.20  # 压缩到 20%

# 模型配置
model:
  context_length: 200000  # 根据模型调整
  
# 凭证池（多 API 密钥轮换）
credential_pools:
  anthropic:
    - key1
    - key2
    - key3
```

#### 错误处理

```python
# 在自定义工具中
def safe_operation(param):
    try:
        result = do_something(param)
        return json.dumps({"success": True, "data": result})
    except KnownError as e:
        return json.dumps({"success": False, "error": str(e)})
    except Exception as e:
        # 记录详细日志
        log_error(e)
        return json.dumps({"success": False, "error": "Internal error"})
```

### 5.4 故障排除

#### 常见问题

```bash
# Gateway 无法启动
hermes doctor --fix

# 工具不可用
hermes tools list  # 检查启用状态
hermes tools enable <toolset>

# 模型/提供者问题
hermes model  # 重新选择
hermes login  # 重新认证

# 技能不显示
hermes skills list  # 确认安装
hermes skills config  # 检查平台启用

# Gateway 崩溃循环
systemctl --user reset-failed hermes-gateway
```

#### 调试技巧

```bash
# 启用详细日志
hermes chat -v

# 检查配置
hermes config check

# 查看会话
hermes sessions browse

# 测试工具
hermes chat -q "列出所有可用工具"
```

---

## 实战项目建议

### 项目 1：个人自动化助手

**目标：** 创建一个处理日常任务的自动化系统

**任务：**
- 每日待办事项提醒
- 新闻摘要生成
- 天气报告
- 日历事件管理

**技能应用：**
- Cron 定时任务
- Webhook 触发
- 消息平台集成

### 项目 2：代码审查机器人

**目标：** 自动审查 GitHub PR

**任务：**
- 监听 PR 事件
- 运行代码分析
- 检查测试覆盖
- 生成审查报告

**技能应用：**
- Webhook 处理
- MCP GitHub 服务器
- 子智能体委托

### 项目 3：多智能体开发团队

**目标：** 模拟完整开发团队

**任务：**
- 产品智能体（需求分析）
- 开发智能体（代码实现）
- 测试智能体（质量保证）
- 部署智能体（CI/CD）

**技能应用：**
- 多智能体编排
- 工作流自动化
- Git 集成

### 项目 4：自定义工具集

**目标：** 为特定领域创建工具

**示例领域：**
- 数据分析工具
- API 测试工具
- 文档生成工具
- 监控工具

**技能应用：**
- 自定义工具开发
- 技能创建
- MCP 集成

---

## 参考资料与资源

### 官方文档

- [Hermes Agent 文档](https://hermes-agent.nousresearch.com/docs/)
- [GitHub 仓库](https://github.com/NousResearch/hermes-agent)
- [CLI 命令参考](https://hermes-agent.nousresearch.com/docs/reference/cli-commands)
- [配置指南](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)
- [工具参考](https://hermes-agent.nousresearch.com/docs/reference/tools-reference)
- [技能目录](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog)

### 社区资源

- [Discord 社区](https://discord.gg/nousresearch)
- [技能贡献指南](https://hermes-agent.nousresearch.com/docs/developer-guide/skills)
- [MCP 服务器目录](https://github.com/modelcontextprotocol/servers)

### 学习路径检查清单

#### 阶段一：基础入门
- [ ] 完成安装和配置
- [ ] 熟悉 CLI 命令
- [ ] 掌握会话管理
- [ ] 了解斜杠命令

#### 阶段二：核心工具与技能
- [ ] 熟练使用文件工具
- [ ] 熟练使用终端工具
- [ ] 理解技能系统
- [ ] 创建第一个自定义技能

#### 阶段三：高级功能与自动化
- [ ] 配置定时任务
- [ ] 设置 Webhook
- [ ] 集成 MCP 服务器
- [ ] 实现自动化工作流

#### 阶段四：多智能体与扩展开发
- [ ] 理解子智能体委托
- [ ] 实现多智能体编排
- [ ] 开发自定义工具
- [ ] 发布技能

#### 阶段五：生产部署
- [ ] 部署 Gateway
- [ ] 配置消息平台
- [ ] 设置监控
- [ ] 实施最佳实践

---

## 结语

恭喜你完成 Hermes Agent 进阶学习路径！

记住以下关键原则：

1. **实践为主**：每个概念都要动手实践
2. **循序渐进**：不要跳过基础阶段
3. **持续学习**：Hermes 在快速发展，关注更新
4. **社区参与**：贡献技能和工具，帮助他人
5. **安全第一**：始终注意命令审批和安全配置

祝你在使用 Hermes Agent 的旅程中取得成功！

---

*文档版本：1.0*  
*最后更新：2026 年 4 月*  
*作者：Hermes Agent*
