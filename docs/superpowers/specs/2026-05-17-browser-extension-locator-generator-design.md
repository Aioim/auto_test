# 浏览器插件：自动 Locator 采集 + Page Object + E2E 用例生成

> 设计日期：2026-05-17 | 状态：已确认 | 方案：B（纯浏览器插件独立运作）

---

## 1. 目标

开发一个 Chrome 浏览器插件（Manifest V3），用户打开任意目标页面后，自动检测页面元素并生成符合 Playwright 最佳实践的 Locator，基于检测结果自动生成符合项目规范的 Page Object 页面文件（`selector.py` + `page.py`）和 pytest E2E 测试用例（`test_xxx.py`），以 `.py` 文件形式下载到本地。

---

## 2. 核心决策

| 维度 | 决定 |
|:---|:---|
| 使用场景 | 优先内部管理系统/后台，兼顾通用网站 |
| 采集模式 | 自动扫描 + 手动勾选/点击补充（混合模式） |
| 代码格式 | 完全匹配项目 `Selector` + `BasePage` + pytest 规范 |
| 集成方式 | 纯浏览器插件，下载 `.py` 文件到本地 |
| 元素分组 | 按 DOM 层级自动分组，用户可调整 |
| 命名 | 自动从 title/URL 推断，用户可手动修改 |

---

## 3. 整体架构

三个核心模块：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    浏览器插件 (Chrome Manifest V3)                    │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   Side Panel      │  │  Content Script   │  │  Service Worker  │  │
│  │   (主 UI)         │  │  (目标页面注入)    │  │  (后台调度)       │  │
│  │                  │  │                  │  │                  │  │
│  │ 元素列表/树       │  │ DOM 遍历采集      │  │ 消息路由          │  │
│  │ 勾选/取消/搜索     │  │ 元素高亮标注      │  │ 代码生成引擎      │  │
│  │ 分组管理/调整     │◄─┤ 用户点击补充      │◄─┤ 文件导出          │  │
│  │ 代码实时预览      │  │ Locator 策略匹配  │  │ 模板管理          │  │
│  │ 导出按钮          │  │ 唯一性校验        │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

| 模块 | 职责 | 技术 |
|:---|:---|:---|
| Side Panel | 用户交互主界面 | HTML/CSS/JS，`chrome.sidePanel` API |
| Content Script | DOM 注入：遍历元素、分析属性、生成 Locator、高亮反馈 | 纯 JS，注入目标页面 |
| Service Worker | 后台协调：消息处理、代码生成模板、存储管理 | 无 DOM 访问，纯逻辑 |

---

## 4. Locator 检测算法

### 4.1 策略优先级（遵循 Playwright 官方推荐）

```
1. getByTestId()     → data-testid 属性
2. getByRole()       → ARIA role + accessible name
3. getByLabel()      → label 关联（for/id 匹配或嵌套）
4. getByPlaceholder() → placeholder 属性
5. getByText()       → 可见文本内容
6. getByAltText()    → alt 属性（图片）
7. getByTitle()      → title 属性
8. CSS selector      → 最短唯一路径（兜底）
```

### 4.2 逐元素检测流程

Content Script 对每个可交互元素按优先级匹配：
1. 存在 `data-testid` → 生成 test_id 策略，优先级 1
2. 存在 ARIA role（包括隐式 role）→ 提取 accessible name → 生成 role 策略，优先级 2
3. 为 input/select/textarea → 查找关联 label → label 策略（优先级 3）或 placeholder 策略（优先级 4）
4. 为 a/button/span 且有文本 → text 策略，优先级 5
5. 存在 alt/title → alt/title 策略，优先级 6
6. 无法匹配 → CSS 兜底（最短唯一路径），优先级 7

### 4.3 唯一性校验

- `document.querySelectorAll()` 确认匹配数量
- 匹配数 > 1 → 标记"非唯一"（黄色警告），建议添加父级约束
- 匹配数 = 0 → 标记"不可用"（红色告警）
- 匹配数 = 1 → 标记"唯一"（绿色正常）

### 4.4 目标元素筛选

默认采集：按钮、链接、输入框、下拉框、复选框/单选框、导航项、表格、弹窗/对话框、表单。

---

## 5. 代码生成模板

### 5.1 生成产物

导出时生成 3 个文件：

| 文件 | 内容 |
|:---|:---|
| `{page}_selector.py` | `Selector` 数据类，每个元素一个实例，策略按优先级排列（最多 3 条） |
| `{page}_page.py` | `BasePage` 子类，导入 selector，封装操作方法 + debug 辅助 |
| `test_{page}.py` | pytest 测试文件，含 fixture + 推断的测试用例 |

### 5.2 Selector 映射规则

| 采集策略 | Selector 字段 |
|:---|:---|
| test_id | `test_id="xxx"` |
| role + name | `role="button"`, `role_name="xxx"` |
| label | `label="xxx"` |
| placeholder | `placeholder="xxx"` |
| text | `text="xxx"` |
| alt | `alt="xxx"` |
| title | `title="xxx"` |
| css | `css="xxx"` |

### 5.3 Page 方法推断

| 元素组合 | 推断方法 |
|:---|:---|
| input + button（同容器内）| `{action}(self, value)` — fill + click |
| 单个 button | `click_{name}(self)` |
| 单个 link | `goto_{name}(self)` |
| select + button | `select_{name}(self, option)` |
| form + submit button | `submit_{name}(self, **fields)` |
| table | `get_{name}_rows(self)` |

### 5.4 测试用例推断

| 页面特征 | 生成用例 |
|:---|:---|
| 任意页面 | `test_page_loads` — 断言核心元素可见 |
| 有 input[required] | `test_required_fields` — 空提交验证 |
| form + submit | `test_{form}_submit` — 完整提交流程 |
| input[type=email/phone] | `test_{field}_validation` — 格式校验 |
| 有链接到其他页面 | `test_navigate_to_{target}` — 导航验证 |
| 有 table/list | `test_{table}_rendered` — 数据展示验证 |

---

## 6. UI 设计系统

### 6.1 风格定位

软暗蓝灰色调（Soft Slate Blue Dark），参考 Linear / Vercel 现代工具风格，底色柔和不过深，蓝色为主调。

### 6.2 配色方案

| 角色 | 色值 | CSS 变量 | 用途 |
|:---|:---|:---|:---|
| 根背景 | `#1C2338` | `--bg-root` | Side Panel 主背景 |
| Header/Footer | `#1F283D` | `--bg-header` | 顶部/底部栏 |
| 卡片/表面 | `#242D43` | `--bg-card` | 列表项、分组容器 |
| 悬停态 | `#2C364E` | `--bg-hover` | 元素悬停 |
| 代码背景 | `#171E2E` | `--bg-code` | 代码预览区 |
| 输入框背景 | `#1B2335` | `--bg-input` | 搜索框、文本输入 |
| 主文字 | `#E8EDF4` | `--fg-primary` | 标题、元素名 |
| 次要文字 | `#C4CCD8` | `--fg-secondary` | 正文、按钮文字 |
| 辅助文字 | `#929BA8` | `--fg-muted` | 描述、标签 |
| 弱化文字 | `#6B7482` | `--fg-dim` | 占位符、提示 |
| 蓝色主调 | `#4B91F7` | `--accent` | 按钮、图标、链接 |
| 蓝色悬停 | `#5C9DF8` | `--accent-hover` | 悬停态 |
| 绿色(唯一) | `#3ECF8E` | `--green` | 选择器唯一（1/1 匹配） |
| 黄色(多匹配) | `#F5A623` | `--amber` | 选择器匹配多个（N>1） |
| 红色(不可靠) | `#F25959` | `--red` | 仅 CSS 兜底 |
| 边框 | `#313B50` | `--border` | 分隔线、卡片边框 |
| 聚焦边框 | `#4B91F7` | `--border-focus` | 输入框聚焦 |

### 6.3 字体系统

| 用途 | 字体 | 字重 | 大小 |
|:---|:---|:---|:---|
| 标题 | Inter | 600 | 14px |
| 正文/元素名 | Inter | 500 | 12px |
| 辅助/标签 | Inter | 500 | 10-11px |
| 代码预览 | JetBrains Mono | 500 | 10.5-11px |

### 6.4 间距系统（4dp 基准）

`4 / 8 / 12 / 16 / 20 / 24`

### 6.5 动效规范

| 操作 | 动效 | 时长 |
|:---|:---|:---|
| 悬停 | 背景色过渡 | 120ms ease-out |
| 聚焦 | 边框 + 光环 | 120ms ease-out |
| 按钮按下 | scale(0.975) | 120ms |
| 分组折叠 | 旋转箭头 + 高度动画 | 200ms ease-out |
| 代码预览 | 滑入 | 250ms spring |

### 6.6 元素状态视觉标注

| 状态 | 左边框 | 徽章色 | 含义 |
|:---|:---|:---|:---|
| 唯一匹配 | `#3ECF8E` 绿色 | 绿底绿字 | 选择器精确匹配 1 个元素 |
| 多个匹配 | `#F5A623` 黄色 | 黄底黄字 | 匹配 N>1，建议加父级约束 |
| CSS 兜底 | `#F25959` 红色 | 红底红字 | 仅 CSS 选择器，可能不稳定 |
| 未勾选 | 彩色淡化 75% | — | 用户跳过，不纳入代码生成 |

### 6.7 Side Panel 布局

- **顶部**：Logo + 标题 + 版本号，页面名称/类名（自动推断，可编辑）
- **工具栏**：蓝色强调"重新扫描"按钮、全选/取消、类型过滤下拉、搜索框
- **元素树**：按 DOM 层级分组展示，左侧缩进线指示层级，每项显示：蓝色勾选框、SVG 类型图标、元素名、策略标签、状态徽章
- **手动补充入口**：蓝色虚线边框，悬停发光
- **方法预览区**：蓝色圆点指示器 + 生成方法签名（JetBrains Mono）
- **底部操作栏**：边框"预览"按钮 + 蓝色渐变"导出文件"按钮

### 6.8 操作流程

1. 打开目标页面
2. 打开 Side Panel → Content Script 自动注入
3. 自动扫描 DOM（~1-3 秒）→ 匹配 Locator → 自动分组 → 推断类名
4. 展示元素树 + 左边框状态色 + 策略标签
5. 用户勾选/取消、调整分组、修改命名、手动补充元素
6. 预览代码（selector / page / test 三个 Tab）
7. 导出下载 3 个 `.py` 文件

### 6.9 HTML 预览

完整 UI 预览文件：`docs/superpowers/specs/ui-preview-side-panel.html`，可在浏览器中直接打开查看效果。

---

## 7. 技术选型

| 层 | 技术 |
|:---|:---|
| 插件框架 | Chrome Manifest V3 |
| UI | Side Panel（HTML + CSS + vanilla JS） |
| DOM 分析 | Content Script 注入 |
| 消息通信 | `chrome.runtime.sendMessage` |
| 存储 | `chrome.storage.local`（用户偏好、模板缓存） |
| 代码生成 | Service Worker 中 JS 模板引擎（模板字面量） |
| 文件导出 | `chrome.downloads` API |

---

## 8. 待定事项

- 国际化（i18n）的 `_key` 字段支持：可在后续版本中加入
- LLM 辅助推断复杂业务场景：作为可选增强，不在首版范围
- 跨浏览器支持（Firefox、Edge）：首版仅 Chrome

---

## 9. 产出物清单

```
browser-extension/
├── manifest.json
├── sidepanel/
│   ├── index.html
│   ├── styles.css
│   └── panel.js
├── content/
│   └── content.js
├── service/
│   ├── worker.js
│   ├── locator-engine.js      # Locator 检测核心
│   ├── code-generator.js      # 代码生成引擎
│   └── templates/
│       ├── selector.tmpl.js
│       ├── page.tmpl.js
│       └── test.tmpl.js
├── shared/
│   └── constants.js
└── assets/
    └── icons/
```
