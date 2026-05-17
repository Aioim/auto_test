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

## 6. UI 交互设计

### 6.1 Side Panel 布局

- **顶部**：页面名称（自动推断，可编辑）+ 类名（自动推断，可编辑）
- **工具栏**：重新扫描、全选/取消全选、元素类型过滤、搜索
- **元素树**：按 DOM 层级分组展示，每项显示：勾选框、类型图标、元素名、策略摘要、唯一性状态
- **手动补充入口**：点击进入"点击采集"模式
- **方法预览区**：展示每个分组将生成的方法签名
- **底部操作栏**：预览代码（3 Tab）、导出文件

### 6.2 操作流程

1. 打开目标页面
2. 打开 Side Panel → Content Script 自动注入
3. 自动扫描 DOM（~1-3 秒）→ 匹配 Locator → 自动分组 → 推断类名
4. 展示元素树 + 状态标注
5. 用户勾选/取消、调整分组、修改命名、手动补充元素
6. 预览代码（selector / page / test 三个 Tab）
7. 导出下载 3 个 `.py` 文件

### 6.3 元素状态视觉标注

| 颜色 | 含义 |
|:---|:---|
| 🟢 绿色 | 选择器唯一（1/1 匹配） |
| 🟡 黄色 | 多策略可用，可能匹配多个（N>1） |
| 🔴 红色 | 无可靠选择器，仅 CSS 兜底 |

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
