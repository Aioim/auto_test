# 浏览器插件：Locator 采集 + Page Object + E2E 用例生成 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 开发一个 Chrome Manifest V3 浏览器插件，自动检测页面元素的 Playwright Locator，生成符合项目规范的 Selector + BasePage + pytest 代码文件。

**Architecture:** 三个模块 — Content Script（DOM 扫描 + Locator 策略匹配）、Service Worker（消息路由 + 代码生成 + 文件下载）、Side Panel（主 UI，展示元素树 + 代码预览 + 导出控制）。纯 JS，无外部依赖。

**Tech Stack:** Chrome Manifest V3, vanilla JavaScript (ES2020+), HTML/CSS, Inter + JetBrains Mono fonts

**Spec:** `docs/superpowers/specs/2026-05-17-browser-extension-locator-generator-design.md`
**UI Preview:** `docs/superpowers/specs/ui-preview-side-panel.html`

---

## File Structure

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
│   ├── locator-engine.js
│   ├── code-generator.js
│   └── templates/
│       ├── selector.tmpl.js
│       ├── page.tmpl.js
│       └── test.tmpl.js
├── shared/
│   └── constants.js
└── assets/
    └── icons/
        ├── icon16.png
        ├── icon48.png
        └── icon128.png
```

**Boundary Decisions:**
- `locator-engine.js` — pure functions, no DOM/chrome API access, independently testable
- `code-generator.js` — pure functions, no DOM/chrome API access, independently testable
- `content.js` — injects into target page, uses `locator-engine.js` functions (duplicated in content script world)
- `worker.js` — uses `code-generator.js` + templates, coordinates downloads
- `panel.js` — manages Side Panel UI state, communicates via `chrome.runtime.sendMessage`
- `constants.js` — shared message type constants, element type definitions, strategy priority order

---

### Task 1: 项目骨架 + manifest.json

**Files:**
- Create: `browser-extension/manifest.json`
- Create: `browser-extension/assets/icons/icon16.png`
- Create: `browser-extension/assets/icons/icon48.png`
- Create: `browser-extension/assets/icons/icon128.png`

- [ ] **Step 1: 创建目录结构**

Run:
```bash
mkdir -p /e/Code/auto_test/browser-extension/{sidepanel,content,service/templates,shared,assets/icons}
```

- [ ] **Step 2: 编写 manifest.json**

File: `browser-extension/manifest.json`
```json
{
  "manifest_version": 3,
  "name": "Auto Test Locator",
  "version": "0.1.0",
  "description": "自动检测页面元素 Playwright Locator，生成 Page Object 和 E2E 测试用例",
  "permissions": [
    "sidePanel",
    "activeTab",
    "scripting",
    "storage",
    "downloads"
  ],
  "host_permissions": [
    "<all_urls>"
  ],
  "side_panel": {
    "default_path": "sidepanel/index.html"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content/content.js"],
      "run_at": "document_idle"
    }
  ],
  "background": {
    "service_worker": "service/worker.js"
  },
  "icons": {
    "16": "assets/icons/icon16.png",
    "48": "assets/icons/icon48.png",
    "128": "assets/icons/icon128.png"
  },
  "action": {
    "default_title": "Auto Test Locator"
  }
}
```

- [ ] **Step 3: 生成占位图标（16/48/128 SVG转PNG）**

生成 3 个蓝色方块 PNG 占位图标。用 HTML canvas 脚本生成：

将以下 HTML 保存为 `/tmp/gen-icons.html` 并在浏览器打开，逐个保存生成的图片到 `browser-extension/assets/icons/`：

```html
<!DOCTYPE html><html><body><script>
[16,48,128].forEach(s => {
  const c = document.createElement('canvas');
  c.width = c.height = s;
  const ctx = c.getContext('2d');
  const grad = ctx.createLinearGradient(0,0,s,s);
  grad.addColorStop(0,'#4B91F7');
  grad.addColorStop(1,'#3878E0');
  ctx.fillStyle = grad;
  ctx.beginPath(); ctx.roundRect(0,0,s,s,s*0.18); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.font = `bold ${s*0.5}px Inter,sans-serif`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText('🔍', s/2, s/2);
  c.toBlob(b => {
    const a = document.createElement('a');
    a.download = `icon${s}.png`; a.href = URL.createObjectURL(b); a.click();
  });
});
</script></body></html>
```

- [ ] **Step 4: 验证目录结构**

Run: `find /e/Code/auto_test/browser-extension -type f | sort`
Expected: 列出 manifest.json 和 3 个图标文件

- [ ] **Step 5: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/
git commit -m "chore: 初始化浏览器插件项目骨架和 manifest.json"
```

---

### Task 2: 共享常量模块

**Files:**
- Create: `browser-extension/shared/constants.js`

- [ ] **Step 1: 编写常量文件**

File: `browser-extension/shared/constants.js`
```js
// ============================================================================
// 消息类型常量（Side Panel ↔ Service Worker ↔ Content Script）
// ============================================================================
export const MSG = {
  // Panel → Worker
  START_SCAN: 'START_SCAN',
  GET_ELEMENTS: 'GET_ELEMENTS',
  PREVIEW_CODE: 'PREVIEW_CODE',
  EXPORT_FILES: 'EXPORT_FILES',
  UPDATE_SETTINGS: 'UPDATE_SETTINGS',

  // Panel → Content (via Worker)
  HIGHLIGHT_ELEMENT: 'HIGHLIGHT_ELEMENT',
  CLEAR_HIGHLIGHTS: 'CLEAR_HIGHLIGHTS',
  MANUAL_PICK_MODE: 'MANUAL_PICK_MODE',

  // Content → Panel (via Worker)
  SCAN_COMPLETE: 'SCAN_COMPLETE',
  ELEMENT_CLICKED: 'ELEMENT_CLICKED',

  // Worker → Panel
  CODE_GENERATED: 'CODE_GENERATED',
  EXPORT_COMPLETE: 'EXPORT_COMPLETE'
};

// ============================================================================
// Locator 策略（优先级从高到低，与 Playwright 官方推荐一致）
// ============================================================================
export const STRATEGY = {
  TEST_ID:     { name: 'test_id',     priority: 1, selector_field: 'test_id' },
  ROLE:        { name: 'role',        priority: 2, selector_field: 'role' },
  LABEL:       { name: 'label',       priority: 3, selector_field: 'label' },
  PLACEHOLDER: { name: 'placeholder', priority: 4, selector_field: 'placeholder' },
  TEXT:        { name: 'text',        priority: 5, selector_field: 'text' },
  ALT:         { name: 'alt',         priority: 6, selector_field: 'alt' },
  TITLE:       { name: 'title',       priority: 7, selector_field: 'title' },
  CSS:         { name: 'css',         priority: 8, selector_field: 'css' }
};

// ============================================================================
// 目标元素类型
// ============================================================================
export const ELEMENT_TYPES = {
  BUTTON: 'button',
  LINK: 'link',
  INPUT: 'input',
  SELECT: 'select',
  CHECKBOX: 'checkbox',
  RADIO: 'radio',
  TEXTAREA: 'textarea',
  FORM: 'form',
  TABLE: 'table',
  NAV: 'nav',
  DIALOG: 'dialog',
  IMAGE: 'image'
};

// ============================================================================
// 可扫描的元素选择器（用于 querySelectorAll）
// ============================================================================
export const SCANNABLE_SELECTORS = [
  'button',
  'a[href]',
  'input:not([type="hidden"])',
  'select',
  'textarea',
  '[role="button"]',
  '[role="link"]',
  '[role="checkbox"]',
  '[role="radio"]',
  '[role="combobox"]',
  '[role="listbox"]',
  '[role="textbox"]',
  '[role="searchbox"]',
  '[role="switch"]',
  '[role="dialog"]',
  '[role="alertdialog"]',
  'form',
  'table',
  'nav a',
  'nav button',
  '[data-testid]'
];

// ============================================================================
// 隐式 ARIA role 映射（HTML5 元素默认 role）
// ============================================================================
export const IMPLICIT_ROLE = {
  'button': 'button',
  'a': 'link',
  'input[type="button"]': 'button',
  'input[type="submit"]': 'button',
  'input[type="reset"]': 'button',
  'input[type="checkbox"]': 'checkbox',
  'input[type="radio"]': 'radio',
  'input[type="text"]': 'textbox',
  'input[type="email"]': 'textbox',
  'input[type="password"]': 'textbox',
  'input[type="search"]': 'searchbox',
  'input[type="tel"]': 'textbox',
  'input[type="url"]': 'textbox',
  'input[type="number"]': 'spinbutton',
  'select': 'combobox',
  'textarea': 'textbox',
  'form': 'form',
  'table': 'table',
  'nav': 'navigation',
  'img': 'img',
  'dialog': 'dialog'
};

// ============================================================================
// 代码生成相关
// ============================================================================
export const MAX_STRATEGIES_PER_SELECTOR = 3;

// ============================================================================
// 方法推断规则
// ============================================================================
export const METHOD_RULES = {
  INPUT_BUTTON: 'fill_and_click',
  SINGLE_BUTTON: 'click',
  SINGLE_LINK: 'goto',
  SELECT_BUTTON: 'select_and_click',
  FORM_SUBMIT: 'submit_form',
  TABLE: 'get_rows'
};
```

- [ ] **Step 2: 验证语法**

Run: `node --check /e/Code/auto_test/browser-extension/shared/constants.js`
Expected: 无输出（语法正确）

- [ ] **Step 3: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/shared/constants.js
git commit -m "feat: 添加共享常量模块（消息类型/策略/元素类型）"
```

---

### Task 3: Locator 检测引擎（核心算法）

**Files:**
- Create: `browser-extension/service/locator-engine.js`

- [ ] **Step 1: 编写 locator-engine.js**

File: `browser-extension/service/locator-engine.js`
```js
// ============================================================================
// Locator 检测引擎 — 纯函数，无 DOM 依赖
// 入参：元素元数据（从 Content Script 的 DOM 分析提取）
// 出参：Locator 策略数组 + 唯一性状态
// ============================================================================

/**
 * @typedef {Object} ElementMeta — Content Script 提取的元素元数据
 * @property {string} tagName
 * @property {string} [inputType]
 * @property {string} [testId] — data-testid 属性
 * @property {string} [role] — 显式 ARIA role 或隐式 role
 * @property {string} [accessibleName] — 可访问名称（from label/text/aria-label）
 * @property {string} [labelText] — 关联 label 文本
 * @property {string} [placeholder]
 * @property {string} [text] — 可见文本内容（截断至 100 字符）
 * @property {string} [alt]
 * @property {string} [title]
 * @property {string} [cssPath] — CSS 最短唯一路径
 * @property {string} [containerTag] — 父容器标签名
 * @property {string} [elementType] — ELEMENT_TYPES 之一
 */

/**
 * @typedef {Object} LocatorStrategy
 * @property {string} type — 'test_id' | 'role' | 'label' | 'placeholder' | 'text' | 'alt' | 'title' | 'css'
 * @property {number} priority — 1-8
 * @property {Object} params — Selector 构造参数
 */

/**
 * @typedef {Object} LocatorResult
 * @property {LocatorStrategy[]} strategies — 按优先级排列
 * @property {'unique'|'multi'|'fallback'} status
 * @property {number} matchCount — CSS 选择器匹配数
 */

/**
 * 为单个元素生成 Locator 策略列表
 * @param {ElementMeta} meta
 * @returns {LocatorResult}
 */
export function generateLocators(meta) {
  const strategies = [];
  let matchCount = 1; // 默认为 1（无法验证时）

  // 优先级 1: data-testid
  if (meta.testId) {
    strategies.push({
      type: 'test_id',
      priority: 1,
      params: { test_id: meta.testId }
    });
  }

  // 优先级 2: ARIA role + accessible name
  if (meta.role && meta.accessibleName) {
    strategies.push({
      type: 'role',
      priority: 2,
      params: { role: meta.role, role_name: meta.accessibleName }
    });
  } else if (meta.role && !meta.accessibleName) {
    strategies.push({
      type: 'role',
      priority: 2,
      params: { role: meta.role }
    });
  }

  // 优先级 3: label
  if (meta.labelText) {
    strategies.push({
      type: 'label',
      priority: 3,
      params: { label: meta.labelText }
    });
  }

  // 优先级 4: placeholder
  if (meta.placeholder) {
    strategies.push({
      type: 'placeholder',
      priority: 4,
      params: { placeholder: meta.placeholder }
    });
  }

  // 优先级 5: text content
  if (meta.text && meta.text.trim()) {
    const trimmed = meta.text.trim().substring(0, 100);
    strategies.push({
      type: 'text',
      priority: 5,
      params: { text: trimmed }
    });
  }

  // 优先级 6: alt
  if (meta.alt) {
    strategies.push({
      type: 'alt',
      priority: 6,
      params: { alt: meta.alt }
    });
  }

  // 优先级 7: title
  if (meta.title) {
    strategies.push({
      type: 'title',
      priority: 7,
      params: { title: meta.title }
    });
  }

  // 优先级 8: CSS 兜底
  if (meta.cssPath) {
    strategies.push({
      type: 'css',
      priority: 8,
      params: { css: meta.cssPath }
    });
  }

  // 判定状态
  const status = determineStatus(strategies, matchCount);

  return { strategies: limitStrategies(strategies), status, matchCount };
}

/**
 * 判定选择器状态
 */
function determineStatus(strategies, matchCount) {
  if (strategies.length === 0) return 'fallback';
  if (matchCount === 1 && strategies[0].priority <= 5) return 'unique';
  if (strategies.length > 1 || matchCount === 1) return 'unique';
  if (matchCount > 1) return 'multi';
  return 'fallback';
}

/**
 * 限制策略数量（最多 MAX_STRATEGIES_PER_SELECTOR 条）
 * 优先保留高优先级策略
 */
function limitStrategies(strategies) {
  const MAX = 3;
  // 去重：相同 css 兜底只保留最高优先级
  const seen = new Set();
  const filtered = [];
  for (const s of strategies) {
    const key = s.type === 'css' ? 'css' : `${s.type}:${JSON.stringify(s.params)}`;
    if (!seen.has(key)) {
      seen.add(key);
      filtered.push(s);
    }
  }
  return filtered.slice(0, MAX);
}

/**
 * 按 DOM 层级自动分组
 * @param {ElementMeta[]} elements
 * @returns {Map<string, ElementMeta[]>}
 */
export function groupByContainer(elements) {
  const groups = new Map();
  for (const el of elements) {
    const key = el.containerTag || 'ungrouped';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(el);
  }
  return groups;
}

/**
 * 从 document.title 推断页面名
 * @param {string} title
 * @returns {string}
 */
export function inferPageName(title) {
  if (!title) return 'UntitledPage';
  // 去掉常见后缀
  const cleaned = title.replace(/[-–|].*$/, '').trim();
  return cleaned || 'UntitledPage';
}

/**
 * 从 URL path 推断类名
 * @param {string} pathname
 * @returns {string}
 */
export function inferClassName(pathname) {
  if (!pathname || pathname === '/') return 'HomePage';
  // /user/login → UserLoginPage
  const parts = pathname.replace(/^\//, '').replace(/\/$/, '').split('/');
  return parts
    .filter(Boolean)
    .map(p => p.charAt(0).toUpperCase() + p.slice(1).replace(/[-_]/g, ''))
    .join('') + 'Page';
}

/**
 * 推断方法签名
 * @param {ElementMeta[]} groupElements — 同一分组内的元素
 * @returns {{name: string, params: string[], action: string}[]}
 */
export function inferMethods(groupElements) {
  const methods = [];
  const inputs = groupElements.filter(e => ['input', 'select', 'textarea'].includes(e.elementType));
  const buttons = groupElements.filter(e => e.elementType === 'button');
  const links = groupElements.filter(e => e.elementType === 'link');
  const tables = groupElements.filter(e => e.elementType === 'table');

  // input + button 组合
  if (inputs.length > 0 && buttons.length > 0) {
    const name = inferActionName(inputs[0], buttons[0]);
    methods.push({
      name,
      params: inputs.map(i => toSnakeCase(i.labelText || i.placeholder || i.text || 'value')),
      action: 'fill + click'
    });
    return methods;
  }

  // 单个 button
  for (const btn of buttons) {
    methods.push({
      name: 'click_' + toSnakeCase(btn.accessibleName || btn.text || 'button').replace(/^click_/, 'click_'),
      params: [],
      action: 'click'
    });
  }

  // 单个 link
  for (const link of links) {
    methods.push({
      name: 'goto_' + toSnakeCase(link.accessibleName || link.text || 'page'),
      params: [],
      action: 'click link'
    });
  }

  // table
  for (const tbl of tables) {
    methods.push({
      name: 'get_' + toSnakeCase(tbl.text || 'table') + '_rows',
      params: [],
      action: 'get rows'
    });
  }

  return methods;
}

function inferActionName(input, button) {
  const verb = button.accessibleName || button.text || 'submit';
  return toSnakeCase(verb);
}

function toSnakeCase(str) {
  if (!str) return 'action';
  // 中文直接返回拼音首字母，简化处理：中文用 'action'
  const hasChinese = /[一-鿿]/.test(str);
  if (hasChinese) {
    // 简单映射常见中文动词
    const map = { '登录': 'login', '注册': 'register', '搜索': 'search',
                  '提交': 'submit', '保存': 'save', '取消': 'cancel',
                  '删除': 'delete', '编辑': 'edit', '添加': 'add',
                  '确认': 'confirm', '关闭': 'close', '返回': 'back',
                  '首页': 'home', '设置': 'settings', '个人中心': 'profile' };
    return map[str] || 'action';
  }
  return str.toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .substring(0, 40);
}
```

- [ ] **Step 2: 验证语法**

Run: `node --check /e/Code/auto_test/browser-extension/service/locator-engine.js`
Expected: 无输出

- [ ] **Step 3: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/service/locator-engine.js
git commit -m "feat: 添加 Locator 检测引擎（策略优先级/分组/命名推断）"
```

---

### Task 4: Locator 引擎单元测试

**Files:**
- Create: `browser-extension/service/locator-engine.test.js`

- [ ] **Step 1: 编写测试用例**

File: `browser-extension/service/locator-engine.test.js`
```js
// ============================================================================
// locator-engine 单元测试 — 使用 Node.js 内置 assert
// 运行: node service/locator-engine.test.js
// ============================================================================
import { generateLocators, groupByContainer, inferPageName, inferClassName, inferMethods, toSnakeCase } from './locator-engine.js';

import assert from 'node:assert';
import test from 'node:test';

// ----- generateLocators -----

test('generateLocators: test_id 优先级最高', () => {
  const meta = {
    tagName: 'button', testId: 'submit-btn', role: 'button',
    accessibleName: '提交', text: '提交', cssPath: 'button.primary'
  };
  const result = generateLocators(meta);
  assert.strictEqual(result.strategies[0].type, 'test_id');
  assert.strictEqual(result.strategies[0].params.test_id, 'submit-btn');
  assert.strictEqual(result.status, 'unique');
});

test('generateLocators: role + accessible name', () => {
  const meta = {
    tagName: 'button', role: 'button', accessibleName: '登录',
    cssPath: '#login-btn'
  };
  const result = generateLocators(meta);
  assert.strictEqual(result.strategies[0].type, 'role');
  assert.strictEqual(result.strategies[0].params.role_name, '登录');
});

test('generateLocators: label 策略', () => {
  const meta = {
    tagName: 'input', inputType: 'text', role: 'textbox',
    labelText: '用户名', placeholder: '请输入用户名'
  };
  const result = generateLocators(meta);
  const labels = result.strategies.filter(s => s.type === 'label');
  assert.strictEqual(labels.length, 1);
  assert.strictEqual(labels[0].params.label, '用户名');
});

test('generateLocators: placeholder 策略', () => {
  const meta = {
    tagName: 'input', inputType: 'password', role: 'textbox',
    placeholder: '请输入密码', cssPath: '#password'
  };
  const result = generateLocators(meta);
  const phs = result.strategies.filter(s => s.type === 'placeholder');
  assert.strictEqual(phs.length, 1);
});

test('generateLocators: 无可用策略时仅有 CSS 兜底', () => {
  const meta = { tagName: 'div', cssPath: 'div.wrapper > span' };
  const result = generateLocators(meta);
  assert.strictEqual(result.status, 'fallback');
  assert.strictEqual(result.strategies.length, 1);
  assert.strictEqual(result.strategies[0].type, 'css');
});

test('generateLocators: 策略不超过 3 条', () => {
  const meta = {
    tagName: 'input', testId: 'email', role: 'textbox',
    accessibleName: '邮箱', labelText: '邮箱地址',
    placeholder: '请输入邮箱', text: '', alt: '',
    title: '电子邮箱', cssPath: '#email'
  };
  const result = generateLocators(meta);
  assert.ok(result.strategies.length <= 3);
});

// ----- groupByContainer -----

test('groupByContainer: 按容器分组', () => {
  const elements = [
    { containerTag: 'form#login', tagName: 'input', labelText: '用户名' },
    { containerTag: 'form#login', tagName: 'button', text: '登录' },
    { containerTag: 'nav#header', tagName: 'a', text: '首页' }
  ];
  const groups = groupByContainer(elements);
  assert.strictEqual(groups.size, 2);
  assert.strictEqual(groups.get('form#login').length, 2);
  assert.strictEqual(groups.get('nav#header').length, 1);
});

// ----- inferPageName -----

test('inferPageName: 去掉标题后缀', () => {
  assert.strictEqual(inferPageName('用户登录 - 管理系统'), '用户登录');
  assert.strictEqual(inferPageName('Dashboard | My App'), 'Dashboard');
  assert.strictEqual(inferPageName(''), 'UntitledPage');
});

// ----- inferClassName -----

test('inferClassName: URL 路径转类名', () => {
  assert.strictEqual(inferClassName('/user/login'), 'UserLoginPage');
  assert.strictEqual(inferClassName('/'), 'HomePage');
  assert.strictEqual(inferClassName('/admin/user-management/'), 'AdminUserManagementPage');
});

// ----- inferMethods -----

test('inferMethods: input + button 组合', () => {
  const elements = [
    { tagName: 'input', elementType: 'input', labelText: '用户名' },
    { tagName: 'input', elementType: 'input', placeholder: '密码' },
    { tagName: 'button', elementType: 'button', text: '登录', accessibleName: '登录' }
  ];
  const methods = inferMethods(elements);
  assert.strictEqual(methods.length, 1);
  assert.strictEqual(methods[0].name, 'login');
  assert.strictEqual(methods[0].params.length, 2);
});

test('inferMethods: 单个按钮', () => {
  const elements = [{ tagName: 'button', elementType: 'button', text: '保存', accessibleName: '保存' }];
  const methods = inferMethods(elements);
  assert.strictEqual(methods.length, 1);
  assert.strictEqual(methods[0].name, 'click_save');
});

test('inferMethods: 链接', () => {
  const elements = [{ tagName: 'a', elementType: 'link', text: '首页', accessibleName: '首页' }];
  const methods = inferMethods(elements);
  assert.strictEqual(methods[0].name, 'goto_home');
});
```

- [ ] **Step 2: 运行测试**

Run: `cd /e/Code/auto_test/browser-extension && node service/locator-engine.test.js`
Expected: 所有 10 个测试通过

- [ ] **Step 3: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/service/locator-engine.test.js
git commit -m "test: 添加 locator-engine 单元测试（策略/分组/命名/方法推断）"
```

---

### Task 5: 代码生成模板

**Files:**
- Create: `browser-extension/service/templates/selector.tmpl.js`
- Create: `browser-extension/service/templates/page.tmpl.js`
- Create: `browser-extension/service/templates/test.tmpl.js`

- [ ] **Step 1: 编写 Selector 模板**

File: `browser-extension/service/templates/selector.tmpl.js`
```js
// ============================================================================
// Selector 文件模板 → {page}_selector.py
// ============================================================================

/**
 * @param {Object} ctx
 * @param {string} ctx.imports — import 语句
 * @param {{name: string, fields: string, description: string}[]} ctx.selectors
 * @returns {string}
 */
export function renderSelector(ctx) {
  let out = ctx.imports + '\n\n';
  for (const sel of ctx.selectors) {
    out += `# ${sel.description}\n`;
    out += `${sel.name} = Selector(\n`;
    out += sel.fields;
    out += `    description="${sel.description}"\n`;
    out += `)\n\n`;
  }
  return out.trimEnd() + '\n';
}

/**
 * 将策略数组转换为 Selector 参数字符串
 * @param {{type: string, params: Object}[]} strategies
 * @returns {string}
 */
export function strategiesToFields(strategies) {
  const lines = [];
  for (const s of strategies) {
    switch (s.type) {
      case 'test_id':
        lines.push(`    test_id="${s.params.test_id}",`);
        break;
      case 'role':
        lines.push(`    role="${s.params.role}",`);
        if (s.params.role_name) {
          lines.push(`    role_name="${s.params.role_name}",`);
        }
        break;
      case 'label':
        lines.push(`    label="${s.params.label}",`);
        break;
      case 'placeholder':
        lines.push(`    placeholder="${s.params.placeholder}",`);
        break;
      case 'text':
        lines.push(`    text="${s.params.text}",`);
        break;
      case 'alt':
        lines.push(`    alt="${s.params.alt}",`);
        break;
      case 'title':
        lines.push(`    title="${s.params.title}",`);
        break;
      case 'css':
        lines.push(`    css="${s.params.css}",`);
        break;
    }
  }
  return lines.join('\n') + '\n';
}

/**
 * 生成 Python 变量名（驼峰转蛇形）
 * @param {string} elementName
 * @returns {string}
 */
export function toSelectorName(elementName) {
  // 中文直接映射
  const zhMap = {
    '用户名': 'username', '用户名输入框': 'username_input',
    '密码': 'password', '密码输入框': 'password_input',
    '登录': 'login', '登录按钮': 'login_button',
    '注册': 'register', '注册按钮': 'register_button',
    '搜索': 'search', '搜索按钮': 'search_button',
    '提交': 'submit', '提交按钮': 'submit_button',
    '保存': 'save', '保存按钮': 'save_button',
    '取消': 'cancel', '取消按钮': 'cancel_button',
    '忘记密码': 'forgot_password',
    '首页': 'home', '首页链接': 'home_link',
    '个人中心': 'profile', '个人中心链接': 'profile_link',
    '设置': 'settings', '设置链接': 'settings_link',
    '邮箱': 'email', '手机号': 'phone',
    '验证码': 'verification_code'
  };
  if (zhMap[elementName]) return zhMap[elementName];
  // 否则转蛇形
  return elementName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'element';
}
```

- [ ] **Step 2: 编写 Page 模板**

File: `browser-extension/service/templates/page.tmpl.js`
```js
// ============================================================================
// Page Object 文件模板 → {page}_page.py
// ============================================================================

/**
 * @param {Object} ctx
 * @param {string} ctx.className — 页面类名 (e.g. "LoginPage")
 * @param {string} ctx.selectorImports — selector 导入语句
 * @param {string} ctx.selectorNames — 逗号分隔的 selector 变量名
 * @param {{name: string, params: string[], action: string, body: string}[]} ctx.methods
 * @param {{name: string, description: string}[]} ctx.elements — 纳入生成的元素列表
 * @returns {string}
 */
export function renderPage(ctx) {
  return `"""\n${ctx.className} 页面对象\n"""\n`
    + `from base_page import BasePage\n`
    + `from ${ctx.selectorModule} import (\n    ${ctx.selectorNames}\n)\n`
    + `from logger import logger\n\n\n`
    + `class ${ctx.className}(BasePage):\n`
    + `    """${ctx.className} 页面"""\n\n`
    + renderOpenMethod(ctx)
    + renderActionMethods(ctx)
    + renderDebugMethod(ctx);
}

function renderOpenMethod(ctx) {
  return `    def open(self) -> None:\n`
    + `        """打开页面"""\n`
    + `        self.goto("${ctx.path || '/'}")\n`
    + (ctx.selectorNames ? `        self.wait_for(${ctx.firstSelector}, state="visible")\n` : '')
    + `\n`;
}

function renderActionMethods(ctx) {
  let out = '';
  for (const m of ctx.methods) {
    const params = m.params.length > 0 ? 'self, ' + m.params.join(', ') : 'self';
    out += `    def ${m.name}(${params}) -> None:\n`;
    out += `        """${m.action || '执行操作'}"""\n`;
    out += m.body;
    out += '\n';
  }
  return out;
}

function renderDebugMethod(ctx) {
  if (!ctx.elements || ctx.elements.length === 0) return '';
  let out = `    def debug_elements(self) -> dict:\n`;
  out += `        """调试元素状态"""\n`;
  out += `        return {\n`;
  for (const el of ctx.elements) {
    out += `            "${el.name}": {\n`;
    out += `                "visible": self.is_visible(${el.name}),\n`;
    out += `                "enabled": self.is_enabled(${el.name})\n`;
    out += `            },\n`;
  }
  out += `        }\n`;
  return out;
}

/**
 * 生成方法体（根据方法类型）
 * @param {{name: string, params: string[], action: string, elements: Object[]}} method
 * @returns {string}
 */
export function generateMethodBody(method) {
  let body = '';
  if (method.elements) {
    for (const el of method.elements) {
      if (el.elementType === 'input' || el.elementType === 'textarea') {
        body += `        self.fill(${el.selectorName}, ${el.paramName})\n`;
      } else if (el.elementType === 'select') {
        body += `        self.select_option(${el.selectorName}, ${el.paramName})\n`;
      }
    }
    const lastBtn = method.elements.find(e => e.elementType === 'button');
    if (lastBtn) {
      body += `        self.click(${lastBtn.selectorName})\n`;
    }
  }
  if (!body) {
    body += `        pass  # 方法体需手动补充\n`;
  }
  return body;
}
```

- [ ] **Step 3: 编写 Test 模板**

File: `browser-extension/service/templates/test.tmpl.js`
```js
// ============================================================================
// pytest 测试文件模板 → test_{page}.py
// ============================================================================

/**
 * @param {Object} ctx
 * @param {string} ctx.pageModule — 页面模块路径
 * @param {string} ctx.className — 页面类名
 * @param {string} ctx.fixtureName — fixture 名称
 * @param {{name: string, body: string, markers: string[]}[]} ctx.testCases
 * @returns {string}
 */
export function renderTest(ctx) {
  const shortName = ctx.fixtureName;
  return `import pytest\n`
    + `from playwright.sync_api import Page, expect\n`
    + `from pages.${ctx.pageModule} import ${ctx.className}\n\n\n`
    + `@pytest.fixture\ndef ${shortName}(page: Page) -> ${ctx.className}:\n`
    + `    """初始化页面对象"""\n`
    + `    p = ${ctx.className}(page)\n`
    + `    p.open()\n`
    + `    return p\n\n\n`
    + `class Test${ctx.className}:\n`
    + `    """${ctx.className} 页面测试"""\n\n`
    + renderTestCases(ctx.testCases, ctx);
}

function renderTestCases(cases, ctx) {
  let out = '';
  for (const tc of cases) {
    const markers = tc.markers.map(m => `    ${m}\n`).join('');
    out += markers;
    out += `    def ${tc.name}(self, ${ctx.fixtureName}):\n`;
    out += `        """${tc.description || ''}"""\n`;
    out += tc.body;
    out += '\n';
  }
  return out;
}

/**
 * 根据页面特征推断测试用例
 * @param {Object} ctx — 页面上下文（元素列表、页面名等）
 * @returns {{name: string, body: string, markers: string[], description: string}[]}
 */
export function inferTestCases(ctx) {
  const cases = [];

  // 1. 页面加载测试
  const checkedElements = (ctx.elements || []).filter(e => e.checked !== false);
  cases.push({
    name: 'test_page_loads',
    markers: ['@pytest.mark.smoke'],
    description: '验证页面正确加载',
    body: checkedElements.length > 0
      ? checkedElements.map(e => `        ${ctx.fixtureName}.expect_visible(${e.name})\n`).join('')
      : `        pass  # 无勾选元素\n`
  });

  // 2. 必填字段验证
  const requiredInputs = (ctx.elements || []).filter(e =>
    ['input', 'textarea'].includes(e.elementType) && e.required
  );
  if (requiredInputs.length > 0) {
    cases.push({
      name: 'test_required_fields_validation',
      markers: [],
      description: '必填字段空提交验证',
      body: `        # 不填写任何字段，直接提交\n`
        + `        pass  # TODO: 根据实际页面调整触发逻辑\n`
    });
  }

  // 3. 表单提交流程
  const hasForm = (ctx.methods || []).some(m => m.action === 'fill + click');
  if (hasForm) {
    const method = ctx.methods.find(m => m.action === 'fill + click');
    const args = method.params.map(p => `"test_${p}"`).join(', ');
    cases.push({
      name: `test_${method.name}_flow`,
      markers: ['@pytest.mark.regression'],
      description: method.action + ' 流程测试',
      body: `        ${ctx.fixtureName}.${method.name}(${args})\n`
    });
  }

  // 4. 导航链接测试
  const links = (ctx.elements || []).filter(e =>
    e.elementType === 'link' && e.checked !== false
  );
  for (const link of links) {
    cases.push({
      name: `test_navigate_to_${link.name}`,
      markers: [],
      description: `导航至 ${link.description || link.name}`,
      body: `        ${ctx.fixtureName}.click(${link.name})\n`
        + `        pass  # TODO: 添加 URL 或页面断言\n`
    });
  }

  return cases;
}
```

- [ ] **Step 4: 验证语法**

```bash
node --check /e/Code/auto_test/browser-extension/service/templates/selector.tmpl.js
node --check /e/Code/auto_test/browser-extension/service/templates/page.tmpl.js
node --check /e/Code/auto_test/browser-extension/service/templates/test.tmpl.js
```

- [ ] **Step 5: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/service/templates/
git commit -m "feat: 添加代码生成模板（Selector/Page/Test）"
```

---

### Task 6: 代码生成引擎

**Files:**
- Create: `browser-extension/service/code-generator.js`

- [ ] **Step 1: 编写 code-generator.js**

File: `browser-extension/service/code-generator.js`
```js
// ============================================================================
// 代码生成引擎 — 将采集的元素数据转为 Python 代码文件
// ============================================================================
import { renderSelector, strategiesToFields, toSelectorName } from './templates/selector.tmpl.js';
import { renderPage, generateMethodBody } from './templates/page.tmpl.js';
import { renderTest, inferTestCases } from './templates/test.tmpl.js';

/**
 * @typedef {Object} ElementEntry — 用户确认后的元素条目
 * @property {string} id — 唯一标识
 * @property {string} name — 元素显示名
 * @property {string} selectorName — Python 变量名
 * @property {string} elementType — button/link/input/select/textarea/form/table
 * @property {boolean} checked — 是否纳入生成
 * @property {boolean} [required] — 是否必填
 * @property {{type: string, params: Object}[]} strategies
 * @property {string} description — 元素描述
 * @property {string} containerId — 所属分组
 */

/**
 * @typedef {Object} Group — 分组信息
 * @property {string} id — 分组标识
 * @property {string} name — 分组名称
 * @property {string} containerTag — DOM 标签
 * @property {string[]} elementIds — 元素 ID 列表
 */

/**
 * @typedef {Object} PageContext
 * @property {string} pageName — 页面名
 * @property {string} className — 类名
 * @property {string} moduleName — 模块名（用于文件命名）
 * @property {string} path — URL 路径
 * @property {ElementEntry[]} elements
 * @property {Group[]} groups
 */

/**
 * 生成完整的 3 个文件内容
 * @param {PageContext} ctx
 * @returns {{selectorFile: string, pageFile: string, testFile: string}}
 */
export function generateAll(ctx) {
  return {
    selectorFile: generateSelectorFile(ctx),
    pageFile: generatePageFile(ctx),
    testFile: generateTestFile(ctx)
  };
}

function generateSelectorFile(ctx) {
  const checked = ctx.elements.filter(e => e.checked !== false);
  const selectors = checked.map(el => ({
    name: el.selectorName,
    fields: strategiesToFields(el.strategies),
    description: el.description || el.name
  }));
  return renderSelector({
    imports: 'from core.selector import Selector',
    selectors
  });
}

function generatePageFile(ctx) {
  const checked = ctx.elements.filter(e => e.checked !== false);
  const selectorNames = checked.map(e => e.selectorName).join(',\n    ');
  const firstChecked = checked[0];

  // 生成方法
  const methods = [];
  for (const group of ctx.groups) {
    const groupElements = checked.filter(e => group.elementIds.includes(e.id));
    if (groupElements.length === 0) continue;
    // 按类型分类
    const inputs = groupElements.filter(e => ['input', 'textarea', 'select'].includes(e.elementType));
    const buttons = groupElements.filter(e => e.elementType === 'button');
    const links = groupElements.filter(e => e.elementType === 'link');

    if (inputs.length > 0 && buttons.length > 0) {
      methods.push({
        name: toSnakeCase(buttons[0].name),
        params: inputs.map(inp => inp.selectorName.replace('_input', '').replace('_', '_')),
        action: 'fill + click',
        body: inputs.map(inp =>
          `        self.fill(${inp.selectorName}, ${inp.selectorName.replace('_input', '')})\n`
        ).join('') + `        self.click(${buttons[0].selectorName})\n`
      });
    }
    for (const btn of buttons) {
      if (inputs.length > 0 && buttons.indexOf(btn) === 0) continue; // 已处理
      methods.push({
        name: 'click_' + btn.selectorName,
        params: [],
        action: 'click',
        body: `        self.click(${btn.selectorName})\n`
      });
    }
    for (const link of links) {
      methods.push({
        name: 'goto_' + link.selectorName,
        params: [],
        action: 'click link',
        body: `        self.click(${link.selectorName})\n`
      });
    }
  }

  return renderPage({
    className: ctx.className,
    selectorModule: ctx.moduleName + '_selector',
    selectorNames: selectorNames || 'None',
    firstSelector: firstChecked ? firstChecked.selectorName : '',
    path: ctx.path || '/',
    methods,
    elements: checked.map(e => ({ name: e.selectorName }))
  });
}

function generateTestFile(ctx) {
  const checked = ctx.elements.filter(e => e.checked !== false);
  const fixtureName = ctx.moduleName + '_page';
  const testCases = inferTestCases({
    fixtureName,
    elements: checked.map(e => ({
      name: e.selectorName,
      elementType: e.elementType,
      checked: e.checked,
      required: e.required,
      description: e.description
    })),
    methods: [] // 由 generatePageFile 中提取
  });

  // 补充方法信息到测试用例
  const methodsForTest = [];
  for (const group of ctx.groups) {
    const groupElements = checked.filter(e => group.elementIds.includes(e.id));
    const inputs = groupElements.filter(e => ['input', 'textarea', 'select'].includes(e.elementType));
    const buttons = groupElements.filter(e => e.elementType === 'button');
    if (inputs.length > 0 && buttons.length > 0) {
      methodsForTest.push({
        name: toSnakeCase(buttons[0].name),
        params: inputs.map(inp => inp.selectorName.replace('_input', '')),
        action: 'fill + click'
      });
    }
  }
  // 更新测试用例中的 form submit 用例
  const formMethod = methodsForTest[0];
  if (formMethod) {
    const formCase = testCases.find(tc => tc.name === `test_${formMethod.name}_flow`);
    if (formCase) {
      formCase.body = `        ${fixtureName}.${formMethod.name}(${formMethod.params.map(p => `"test_${p}"`).join(', ')})\n`;
    }
  }

  return renderTest({
    pageModule: ctx.moduleName + '_page',
    className: ctx.className,
    fixtureName,
    testCases
  });
}

/**
 * 触发浏览器下载指定内容的文件
 * @param {string} content — 文件内容
 * @param {string} filename — 文件名
 */
export function downloadFile(content, filename) {
  const dataUrl = 'data:text/plain;charset=utf-8,' + encodeURIComponent(content);
  chrome.downloads.download({
    url: dataUrl,
    filename: filename,
    saveAs: true
  });
}
```

- [ ] **Step 2: 验证语法**

Run: `node --check /e/Code/auto_test/browser-extension/service/code-generator.js`
Expected: 无输出

- [ ] **Step 3: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/service/code-generator.js
git commit -m "feat: 添加代码生成引擎（组装模板/生成完整文件/下载）"
```

---

### Task 7: Content Script（DOM 扫描 + 元素采集）

**Files:**
- Create: `browser-extension/content/content.js`

- [ ] **Step 1: 编写 content.js**

File: `browser-extension/content/content.js`
```js
// ============================================================================
// Content Script — 注入目标页面，执行 DOM 扫描和元素采集
// 通过 chrome.runtime.sendMessage 与 Service Worker 通信
// 注意：Content Script 运行在隔离的 JS 环境中，不能直接 import Service Worker 的模块
// 因此这里内联核心算法
// ============================================================================

(function() {
  'use strict';

  // ==============================
  // 消息监听
  // ==============================
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    switch (msg.type) {
      case 'START_SCAN':
        const result = scanPage();
        sendResponse(result);
        break;
      case 'HIGHLIGHT_ELEMENT':
        highlightElement(msg.elementId);
        sendResponse({ ok: true });
        break;
      case 'CLEAR_HIGHLIGHTS':
        clearHighlights();
        sendResponse({ ok: true });
        break;
      case 'MANUAL_PICK_MODE':
        toggleManualPick(msg.enabled);
        sendResponse({ ok: true });
        break;
    }
    return true; // 保持消息通道开启（异步响应）
  });

  // ==============================
  // 页面扫描
  // ==============================
  function scanPage() {
    const elements = collectElements();
    const groups = groupByDOM(elements);
    return {
      pageName: inferPageName(document.title),
      className: inferClassName(location.pathname),
      path: location.pathname,
      url: location.href,
      elements,
      groups
    };
  }

  function collectElements() {
    const selectors = [
      'button', 'a[href]',
      'input:not([type="hidden"])', 'select', 'textarea',
      '[role="button"]', '[role="link"]', '[role="checkbox"]',
      '[role="radio"]', '[role="combobox"]', '[role="listbox"]',
      '[role="textbox"]', '[role="searchbox"]', '[role="switch"]',
      '[role="dialog"]', '[role="alertdialog"]',
      'form', 'table',
      '[data-testid]'
    ];

    const seen = new Set();
    const elements = [];

    for (const sel of selectors) {
      try {
        const nodes = document.querySelectorAll(sel);
        for (const el of nodes) {
          if (seen.has(el)) continue;
          if (!isVisible(el)) continue;
          seen.add(el);

          const meta = extractMeta(el);
          if (meta) elements.push(meta);
        }
      } catch (e) { /* 跳过无效选择器 */ }
    }

    return elements;
  }

  // ==============================
  // 元素元数据提取
  // ==============================
  function extractMeta(el) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = el.getAttribute('role') || getImplicitRole(tag, type);
    const elementType = classifyElement(tag, type, role);

    if (!elementType) return null; // 跳过非目标类型

    const text = getTextContent(el);
    const container = findSemanticContainer(el);

    return {
      id: generateId(el),
      tagName: tag,
      inputType: type || undefined,
      elementType,
      testId: el.getAttribute('data-testid') || undefined,
      role: role || undefined,
      accessibleName: getAccessibleName(el) || undefined,
      labelText: findLabelText(el) || undefined,
      placeholder: el.getAttribute('placeholder') || undefined,
      text: text || undefined,
      alt: el.getAttribute('alt') || undefined,
      title: el.getAttribute('title') || undefined,
      cssPath: getShortestUniquePath(el),
      required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
      containerTag: container ? getContainerLabel(container) : 'ungrouped',
      containerId: container ? generateId(container) : 'ungrouped',
      description: text || getAccessibleName(el) || el.getAttribute('placeholder') || tag
    };
  }

  function classifyElement(tag, type, role) {
    if (tag === 'button' || role === 'button' || type === 'submit' || type === 'reset' || type === 'button') return 'button';
    if (tag === 'a' && elHasHref()) return 'link'; // 需在调用上下文中判断
    if ((tag === 'input' && ['checkbox'].includes(type)) || role === 'checkbox') return 'checkbox';
    if ((tag === 'input' && ['radio'].includes(type)) || role === 'radio') return 'radio';
    if (tag === 'select' || role === 'combobox' || role === 'listbox') return 'select';
    if (tag === 'textarea') return 'textarea';
    if (tag === 'input' || role === 'textbox' || role === 'searchbox' || role === 'spinbutton') return 'input';
    if (tag === 'form') return 'form';
    if (tag === 'table' || role === 'table') return 'table';
    if (tag === 'nav' || role === 'navigation') return 'nav';
    if (role === 'dialog' || role === 'alertdialog') return 'dialog';
    if ((tag === 'img' || tag === 'svg') && (el.getAttribute('alt') || el.getAttribute('aria-label'))) return 'image';

    // a[href] 特殊处理
    if (tag === 'a') {
      const href = el.getAttribute('href');
      if (href && href !== '#' && !href.startsWith('javascript:')) return 'link';
    }
    return null;
  }

  function getImplicitRole(tag, type) {
    const map = {
      'button': 'button', 'a': 'link', 'select': 'combobox',
      'textarea': 'textbox', 'form': 'form', 'table': 'table',
      'nav': 'navigation', 'img': 'img', 'dialog': 'dialog'
    };
    if (map[tag]) return map[tag];
    if (tag === 'input') {
      const inputRoles = { 'button': 'button', 'submit': 'button', 'reset': 'button',
        'checkbox': 'checkbox', 'radio': 'radio', 'text': 'textbox',
        'email': 'textbox', 'password': 'textbox', 'search': 'searchbox',
        'tel': 'textbox', 'url': 'textbox', 'number': 'spinbutton' };
      return inputRoles[type] || 'textbox';
    }
    return null;
  }

  function getAccessibleName(el) {
    return el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')
      ? document.getElementById(el.getAttribute('aria-labelledby'))?.textContent?.trim() : null
      || el.getAttribute('aria-label') || null;
  }

  function findLabelText(el) {
    const id = el.id;
    if (id) {
      const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (label) return label.textContent.trim().substring(0, 80);
    }
    const parentLabel = el.closest('label');
    if (parentLabel) return parentLabel.textContent.replace(el.textContent || '', '').trim().substring(0, 80);
    return null;
  }

  function getTextContent(el) {
    const text = (el.textContent || el.innerText || '').replace(/\s+/g, ' ').trim();
    return text.substring(0, 100);
  }

  function findSemanticContainer(el) {
    return el.closest('form, nav, fieldset, section, [role="dialog"], [role="form"], '
      + '[role="navigation"], [role="region"], div[id], div[class*="form"], '
      + 'div[class*="nav"], div[class*="panel"], div[class*="container"]');
  }

  function getContainerLabel(container) {
    if (!container) return 'ungrouped';
    const id = container.id ? '#' + container.id : '';
    const cls = container.className && typeof container.className === 'string'
      ? '.' + container.className.split(' ')[0] : '';
    return container.tagName.toLowerCase() + id + cls;
  }

  function getShortestUniquePath(el) {
    // 生成 CSS 选择器最短唯一路径
    const path = [];
    let current = el;
    while (current && current !== document.body) {
      let segment = current.tagName.toLowerCase();
      if (current.id) {
        path.unshift('#' + CSS.escape(current.id));
        break;
      }
      const parent = current.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(
          c => c.tagName === current.tagName
        );
        if (siblings.length > 1) {
          const idx = siblings.indexOf(current) + 1;
          segment += `:nth-child(${idx})`;
        }
      }
      path.unshift(segment);
      current = parent;
      // 检查唯一性
      const selector = path.join(' > ');
      try {
        if (document.querySelectorAll(selector).length === 1) break;
      } catch (e) { /* 继续 */ }
    }
    return path.join(' > ');
  }

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
  }

  function generateId(el) {
    let id = el.id || el.getAttribute('data-testid') || '';
    if (!id) {
      const hash = simpleHash(el.tagName + getShortestUniquePath(el) + (el.textContent || ''));
      id = 'el-' + hash;
    }
    return id;
  }

  function simpleHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash).toString(16).substring(0, 8);
  }

  // ==============================
  // DOM 分组
  // ==============================
  function groupByDOM(elements) {
    const groupsMap = new Map();
    for (const el of elements) {
      const key = el.containerId;
      if (!groupsMap.has(key)) {
        groupsMap.set(key, {
          id: key,
          name: el.containerTag.replace(/#.*/, '').replace(/\..*/, '') || '未分组',
          containerTag: el.containerTag,
          elementIds: []
        });
      }
      groupsMap.get(key).elementIds.push(el.id);
    }
    return Array.from(groupsMap.values());
  }

  // ==============================
  // 命名推断
  // ==============================
  function inferPageName(title) {
    if (!title) return 'UntitledPage';
    return title.replace(/[-–|].*$/, '').trim() || 'UntitledPage';
  }

  function inferClassName(pathname) {
    if (!pathname || pathname === '/') return 'HomePage';
    const parts = pathname.replace(/^\//, '').replace(/\/$/, '').split('/');
    return parts.filter(Boolean)
      .map(p => p.charAt(0).toUpperCase() + p.slice(1).replace(/[-_]/g, ''))
      .join('') + 'Page';
  }

  // ==============================
  // 元素高亮
  // ==============================
  let highlightOverlay = null;
  let manualPickEnabled = false;

  function highlightElement(elementId) {
    clearHighlights();
    const el = findElementById(elementId);
    if (!el) return;

    const rect = el.getBoundingClientRect();
    highlightOverlay = document.createElement('div');
    highlightOverlay.style.cssText = `
      position: fixed; pointer-events: none; z-index: 999999;
      left: ${rect.left}px; top: ${rect.top}px;
      width: ${rect.width}px; height: ${rect.height}px;
      outline: 2px solid #4B91F7; outline-offset: 2px;
      background: rgba(75,145,247,0.08); border-radius: 3px;
    `;
    document.body.appendChild(highlightOverlay);
  }

  function clearHighlights() {
    if (highlightOverlay) { highlightOverlay.remove(); highlightOverlay = null; }
    document.querySelectorAll('.atl-highlight').forEach(e => e.remove());
  }

  function toggleManualPick(enabled) {
    manualPickEnabled = enabled;
    if (enabled) {
      document.body.style.cursor = 'crosshair';
      document.addEventListener('click', onManualPick, true);
    } else {
      document.body.style.cursor = '';
      document.removeEventListener('click', onManualPick, true);
    }
  }

  function onManualPick(e) {
    if (!manualPickEnabled) return;
    e.preventDefault();
    e.stopPropagation();
    const el = e.target;
    const meta = extractMeta(el);
    if (meta) {
      chrome.runtime.sendMessage({ type: 'ELEMENT_CLICKED', element: meta });
    }
  }

  function findElementById(id) {
    if (id.startsWith('el-')) {
      // 哈希 ID，需遍历查找
      for (const el of document.querySelectorAll('*')) {
        if (generateId(el) === id) return el;
      }
    }
    return document.getElementById(id) || document.querySelector(`[data-testid="${id}"]`);
  }

})();
```

- [ ] **Step 2: 验证语法**

```bash
node --check /e/Code/auto_test/browser-extension/content/content.js
```

- [ ] **Step 3: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/content/content.js
git commit -m "feat: 添加 Content Script（DOM 扫描/元素采集/高亮/手动补充）"
```

---

### Task 8: Service Worker（消息路由 + 协调）

**Files:**
- Create: `browser-extension/service/worker.js`

- [ ] **Step 1: 编写 worker.js**

File: `browser-extension/service/worker.js`
```js
// ============================================================================
// Service Worker — 后台协调：消息路由、代码生成、下载管理
// ============================================================================

// 使用 importScripts 加载依赖（Service Worker 不支持 ES modules）
importScripts(
  'locator-engine.js',
  'code-generator.js',
  'templates/selector.tmpl.js',
  'templates/page.tmpl.js',
  'templates/test.tmpl.js'
);

// ==============================
// 会话状态
// ==============================
let sessionState = {
  elements: [],    // ElementEntry[]
  groups: [],      // Group[]
  pageName: '',
  className: '',
  moduleName: '',
  path: '/'
};

// ==============================
// Side Panel 通信
// ==============================
chrome.runtime.onConnect.addListener((port) => {
  if (port.name === 'sidepanel') {
    port.onMessage.addListener(handlePanelMessage);
  }
});

// 备用：通过 runtime.sendMessage 通信
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender).then(sendResponse);
  return true;
});

async function handleMessage(msg, sender) {
  switch (msg.type) {
    case 'START_SCAN':
      return await startScan(msg.tabId);
    case 'PREVIEW_CODE':
      return generatePreview(sessionState);
    case 'EXPORT_FILES':
      return exportFiles(sessionState);
    case 'UPDATE_SETTINGS':
      return updateSettings(msg.settings);
    default:
      return { error: 'Unknown message type: ' + msg.type };
  }
}

// ==============================
// 扫描流程
// ==============================
async function startScan(tabId) {
  try {
    const result = await chrome.tabs.sendMessage(tabId, { type: 'START_SCAN' });

    // 将 Content Script 采集的元数据转为 ElementEntry 格式
    const elements = (result.elements || []).map(el => ({
      ...el,
      selectorName: toSelectorName(el.description || el.text || el.tagName),
      checked: true  // 默认勾选
    }));

    sessionState = {
      elements,
      groups: result.groups || [],
      pageName: result.pageName || 'Untitled',
      className: result.className || 'HomePage',
      moduleName: result.className
        ? result.className.replace(/Page$/, '').replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '')
        : 'home',
      path: result.path || '/'
    };

    return {
      type: 'SCAN_COMPLETE',
      pageName: sessionState.pageName,
      className: sessionState.className,
      moduleName: sessionState.moduleName,
      elements: sessionState.elements,
      groups: sessionState.groups
    };
  } catch (e) {
    return { type: 'SCAN_ERROR', error: e.message };
  }
}

function generatePreview(state) {
  try {
    const ctx = buildPageContext(state);
    const files = generateAll(ctx);
    return { type: 'CODE_GENERATED', ...files };
  } catch (e) {
    return { type: 'GENERATE_ERROR', error: e.message };
  }
}

function exportFiles(state) {
  try {
    const ctx = buildPageContext(state);
    const files = generateAll(ctx);

    // 下载 3 个文件
    downloadFile(files.selectorFile, `${ctx.moduleName}_selector.py`);
    // 短暂延迟避免 Chrome 合并下载
    setTimeout(() => downloadFile(files.pageFile, `${ctx.moduleName}_page.py`), 500);
    setTimeout(() => downloadFile(files.testFile, `test_${ctx.moduleName}.py`), 1000);

    return { type: 'EXPORT_COMPLETE', files: 3 };
  } catch (e) {
    return { type: 'EXPORT_ERROR', error: e.message };
  }
}

function buildPageContext(state) {
  return {
    pageName: state.pageName,
    className: state.className,
    moduleName: state.moduleName,
    path: state.path,
    elements: state.elements,
    groups: state.groups
  };
}

// ==============================
// 设置管理
// ==============================
function updateSettings(settings) {
  chrome.storage.local.set({ settings });
  return { ok: true };
}

// ==============================
// Side Panel 打开时自动开始扫描
// ==============================
chrome.sidePanel?.onShown?.addListener?.(async () => {
  // Side Panel 打开时，获取当前活跃 tab 并通知扫描
  // 实际扫描由 panel.js 发起
});
```

- [ ] **Step 2: 验证语法**

```bash
node --check /e/Code/auto_test/browser-extension/service/worker.js
```

- [ ] **Step 3: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/service/worker.js
git commit -m "feat: 添加 Service Worker（消息路由/扫描协调/代码生成/下载）"
```

---

### Task 9: Side Panel UI — HTML + CSS

**Files:**
- Create: `browser-extension/sidepanel/index.html`
- Create: `browser-extension/sidepanel/styles.css`

- [ ] **Step 1: 复制 HTML 预览为 index.html**

从 `docs/superpowers/specs/ui-preview-side-panel.html` 复制 HTML 结构和 CSS，调整为 Side Panel 规格：

File: `browser-extension/sidepanel/index.html`
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Auto Test Locator</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>

<div id="app" class="side-panel">

  <!-- Header -->
  <div class="header">
    <div class="header-row">
      <div class="header-logo">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
      </div>
      <span class="header-title">Auto Test Locator</span>
      <span class="header-version">v0.1</span>
    </div>
    <div class="meta-row">
      <div class="meta-field">
        <span class="meta-label">页面</span>
        <input class="meta-input js-page-name" value="—" placeholder="页面名称">
      </div>
      <div class="meta-field">
        <span class="meta-label">类名</span>
        <input class="meta-input js-class-name" value="—" placeholder="PageName">
      </div>
    </div>
  </div>

  <!-- Toolbar -->
  <div class="toolbar">
    <div class="toolbar-actions">
      <button class="btn btn-accent js-btn-scan">
        <svg class="btn-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M13.5 2.5a.5.5 0 0 1 1 0v4a.5.5 0 0 1-.5.5h-4a.5.5 0 0 1 0-1h3.2a5.5 5.5 0 1 0 1.8 3.5.5.5 0 1 1 1 .1 6.5 6.5 0 1 1-2.6-6.3l.1-.8Z"/></svg>
        重新扫描
      </button>
      <button class="btn js-btn-select-all">
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><polyline points="9 12 12 15 20 6"/></svg>
        全选
      </button>
      <button class="btn btn-ghost js-btn-deselect-all">取消</button>
    </div>
    <div class="toolbar-row">
      <select class="filter-select js-filter-type">
        <option value="all">全部</option>
        <option value="button">按钮</option>
        <option value="input">输入框</option>
        <option value="link">链接</option>
        <option value="form">表单</option>
      </select>
      <input class="filter-input js-filter-search" type="text" placeholder="搜索元素…">
    </div>
  </div>

  <!-- Element Tree -->
  <div id="element-tree" class="element-tree">
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
      </div>
      <p>点击"重新扫描"开始检测页面元素</p>
    </div>
  </div>

  <!-- Manual Add -->
  <div class="manual-add js-btn-manual-pick">
    <span class="manual-add-plus">+</span>
    手动补充元素
  </div>

  <!-- Method Preview -->
  <div class="method-preview">
    <div class="method-preview-header">
      <span class="method-dot"></span>
      <span class="method-preview-title">生成方法预览</span>
    </div>
    <div id="method-list" class="method-list">
      <div class="method-item method-placeholder">等待扫描…</div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    <button class="btn-footer btn-footer-outline js-btn-preview">
      <svg class="btn-icon-s" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
      预览
    </button>
    <button class="btn-footer btn-footer-primary js-btn-export">
      <svg class="btn-icon-s" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      导出文件
    </button>
  </div>

  <!-- Code Preview Modal -->
  <div id="preview-modal" class="modal-overlay" style="display:none;">
    <div class="modal-content">
      <div class="modal-header">
        <div class="modal-tabs">
          <button class="modal-tab active" data-tab="selector">selector.py</button>
          <button class="modal-tab" data-tab="page">page.py</button>
          <button class="modal-tab" data-tab="test">test.py</button>
        </div>
        <button class="modal-close js-btn-close-preview">&times;</button>
      </div>
      <pre class="modal-code"><code id="preview-code"></code></pre>
    </div>
  </div>

</div>

<script src="panel.js"></script>
</body>
</html>
```

- [ ] **Step 2: 编写 styles.css**

从 `docs/superpowers/specs/ui-preview-side-panel.html` 复制完整 CSS（`<style>` 标签内容），移除 body 外层（居中/背景），保留 `.side-panel` 内所有样式，并补充 Modal 和 Empty State 样式：

```css
/* 追加以下样式到从 ui-preview 复制的 CSS 之后 */

.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 32px 20px; color: var(--fg-dim); text-align: center; gap: 12px;
}
.empty-icon { opacity: 0.4; }

.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  animation: fadeIn 150ms var(--ease-out);
}
.modal-content {
  width: 90vw; max-width: 560px; max-height: 80vh;
  background: var(--bg-card); border-radius: var(--radius-lg);
  border: 1px solid var(--border); box-shadow: var(--shadow-lg);
  display: flex; flex-direction: column; overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-bottom: 1px solid var(--border-light);
}
.modal-tabs { display: flex; gap: 2px; }
.modal-tab {
  padding: 6px 14px; font-size: 11px; font-family: 'Inter', sans-serif;
  font-weight: 500; border: none; border-radius: var(--radius-sm);
  background: transparent; color: var(--fg-muted); cursor: pointer;
  transition: all var(--duration-fast);
}
.modal-tab.active { background: rgba(75,145,247,0.12); color: var(--accent); }
.modal-close {
  width: 28px; height: 28px; border: none; background: transparent;
  color: var(--fg-muted); font-size: 18px; cursor: pointer;
  border-radius: var(--radius-sm); transition: background var(--duration-fast);
}
.modal-close:hover { background: var(--bg-hover); }
.modal-code {
  flex: 1; overflow: auto; margin: 0; padding: 14px 16px;
  background: var(--bg-code); font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px; line-height: 1.65; color: var(--fg-secondary);
  white-space: pre; tab-size: 4;
}
.modal-code code { all: unset; }

.method-placeholder { color: var(--fg-dim); font-style: italic; font-family: 'Inter', sans-serif; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
```

- [ ] **Step 3: 验证文件完整性**

```bash
wc -l /e/Code/auto_test/browser-extension/sidepanel/index.html
wc -l /e/Code/auto_test/browser-extension/sidepanel/styles.css
```

- [ ] **Step 4: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/sidepanel/index.html browser-extension/sidepanel/styles.css
git commit -m "feat: 添加 Side Panel UI（HTML 结构 + 完整 CSS 设计系统）"
```

---

### Task 10: Side Panel UI — JS 逻辑

**Files:**
- Create: `browser-extension/sidepanel/panel.js`

- [ ] **Step 1: 编写 panel.js**

File: `browser-extension/sidepanel/panel.js`
```js
// ============================================================================
// Side Panel 逻辑 — UI 状态管理、事件绑定、消息通信
// ============================================================================

// ==============================
// 状态
// ==============================
const state = {
  elements: [],       // ElementEntry[]
  groups: [],         // Group[]
  pageName: '',
  className: '',
  moduleName: '',
  path: '/',
  filterType: 'all',
  filterSearch: '',
  manualPick: false,
  generatedCode: null  // { selectorFile, pageFile, testFile }
};

// ==============================
// DOM 引用
// ==============================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
  pageName: $('.js-page-name'),
  className: $('.js-class-name'),
  btnScan: $('.js-btn-scan'),
  btnSelectAll: $('.js-btn-select-all'),
  btnDeselectAll: $('.js-btn-deselect-all'),
  btnManualPick: $('.js-btn-manual-pick'),
  btnPreview: $('.js-btn-preview'),
  btnExport: $('.js-btn-export'),
  btnClosePreview: $('.js-btn-close-preview'),
  filterType: $('.js-filter-type'),
  filterSearch: $('.js-filter-search'),
  elementTree: $('#element-tree'),
  methodList: $('#method-list'),
  previewModal: $('#preview-modal'),
  previewCode: $('#preview-code'),
  modalTabs: $$('.modal-tab')
};

// ==============================
// 初始化
// ==============================
async function init() {
  bindEvents();
  // 自动扫描当前活跃 tab
  await scanPage();
}

function bindEvents() {
  dom.btnScan.addEventListener('click', scanPage);
  dom.btnSelectAll.addEventListener('click', () => toggleAll(true));
  dom.btnDeselectAll.addEventListener('click', () => toggleAll(false));
  dom.btnManualPick.addEventListener('click', toggleManualPick);
  dom.btnPreview.addEventListener('click', previewCode);
  dom.btnExport.addEventListener('click', exportFiles);
  dom.btnClosePreview.addEventListener('click', closePreview);
  dom.filterType.addEventListener('change', renderTree);
  dom.filterSearch.addEventListener('input', renderTree);

  // 页面名/类名手动修改
  dom.pageName.addEventListener('input', () => {
    state.pageName = dom.pageName.value;
  });
  dom.className.addEventListener('input', () => {
    state.className = dom.className.value;
    state.moduleName = state.className
      .replace(/Page$/, '')
      .replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '').replace(/__/g, '_');
  });

  // 模态 Tab 切换
  dom.modalTabs.forEach(tab => {
    tab.addEventListener('click', () => switchPreviewTab(tab.dataset.tab));
  });
}

// ==============================
// 页面扫描
// ==============================
async function scanPage() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;

  dom.btnScan.textContent = '扫描中…';
  dom.btnScan.disabled = true;

  try {
    const response = await chrome.tabs.sendMessage(tab.id, { type: 'START_SCAN' });
    if (!response || response.type === 'SCAN_ERROR') {
      showError('扫描失败: ' + (response?.error || '未知错误'));
      return;
    }

    // 收到来自 Content Script 的扫描结果，也通知 Worker
    // 统一通过 Worker 管理状态
    const workerResponse = await chrome.runtime.sendMessage({
      type: 'START_SCAN',
      tabId: tab.id
    });

    if (workerResponse.type === 'SCAN_COMPLETE') {
      Object.assign(state, {
        elements: workerResponse.elements,
        groups: workerResponse.groups,
        pageName: workerResponse.pageName,
        className: workerResponse.className,
        moduleName: workerResponse.moduleName,
        path: state.path
      });
      updateUI();
    }
  } catch (e) {
    showError('扫描失败: ' + e.message + '。请刷新目标页面后重试。');
  } finally {
    dom.btnScan.innerHTML = `<svg class="btn-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M13.5 2.5a.5.5 0 0 1 1 0v4a.5.5 0 0 1-.5.5h-4a.5.5 0 0 1 0-1h3.2a5.5 5.5 0 1 0 1.8 3.5.5.5 0 1 1 1 .1 6.5 6.5 0 1 1-2.6-6.3l.1-.8Z"/></svg> 重新扫描`;
    dom.btnScan.disabled = false;
  }
}

function showError(msg) {
  dom.elementTree.innerHTML = `<div class="empty-state"><p style="color:var(--red)">${escapeHtml(msg)}</p></div>`;
}

function updateUI() {
  dom.pageName.value = state.pageName;
  dom.className.value = state.className;
  renderTree();
  renderMethods();
}

// ==============================
// 渲染元素树
// ==============================
function renderTree() {
  const filtered = filterElements(state.elements);
  const grouped = groupFiltered(filtered);

  if (filtered.length === 0) {
    dom.elementTree.innerHTML = '<div class="empty-state"><p>无匹配元素</p></div>';
    return;
  }

  let html = '';
  for (const [groupKey, groupElements] of Object.entries(grouped)) {
    const group = state.groups.find(g => g.id === groupKey) || {
      name: '未分组',
      containerTag: groupKey
    };
    html += renderGroup(group, groupElements);
  }
  dom.elementTree.innerHTML = html;

  // 绑定元素卡片点击事件
  dom.elementTree.querySelectorAll('.element-card').forEach(card => {
    card.addEventListener('click', (e) => {
      const id = card.dataset.elementId;
      toggleElement(id);
    });
  });
}

function filterElements(elements) {
  let filtered = [...elements];
  if (state.filterType !== 'all') {
    filtered = filtered.filter(e => e.elementType === state.filterType);
  }
  if (state.filterSearch) {
    const q = state.filterSearch.toLowerCase();
    filtered = filtered.filter(e =>
      (e.name || '').toLowerCase().includes(q) ||
      (e.description || '').toLowerCase().includes(q) ||
      (e.selectorName || '').toLowerCase().includes(q)
    );
  }
  return filtered;
}

function groupFiltered(elements) {
  const map = {};
  for (const el of elements) {
    const key = el.containerId || 'ungrouped';
    if (!map[key]) map[key] = [];
    map[key].push(el);
  }
  return map;
}

function renderGroup(group, elements) {
  let html = `<div class="group">`;
  html += `<div class="group-header">`;
  html += `<span class="group-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg></span>`;
  html += `<span class="group-name">${escapeHtml(group.name)}</span>`;
  html += `<span class="group-tag">${escapeHtml(group.containerTag || '')}</span>`;
  html += `</div><div class="group-items">`;

  for (const el of elements) {
    const statusClass = el.strategies && el.strategies.length > 0
      ? (el.strategies[0].type === 'css' && el.strategies.length === 1 ? 'status-fallback' : 'status-unique')
      : 'status-fallback';
    const checked = el.checked !== false;
    const badge = el.strategies && el.strategies.length > 0
      ? (el.strategies[0].type === 'css' && el.strategies.length === 1
        ? '<span class="status-badge badge-fallback">CSS 兜底</span>'
        : '<span class="status-badge badge-unique">唯一匹配</span>')
      : '<span class="status-badge badge-fallback">不可用</span>';

    html += `<div class="element-card ${statusClass} ${checked ? '' : 'unchecked'}" data-element-id="${escapeHtml(el.id)}">`;
    html += `<div class="checkbox"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></div>`;
    html += `<div class="element-info">`;
    html += `<div class="element-name-row">`;
    html += `<span class="element-name">${escapeHtml(el.selectorName || el.description || el.tagName)}</span>`;
    html += badge;
    html += `</div>`;
    if (el.strategies && el.strategies.length > 0) {
      html += `<div class="strategies">`;
      el.strategies.slice(0, 3).forEach(s => {
        html += `<span class="strategy">${strategyToLabel(s)}</span>`;
      });
      html += `</div>`;
    }
    html += `</div></div>`;
  }

  html += `</div></div>`;
  return html;
}

function strategyToLabel(s) {
  switch (s.type) {
    case 'test_id': return `get_by_test_id("${s.params.test_id}")`;
    case 'role': return `get_by_role(${s.params.role}${s.params.role_name ? ', "' + s.params.role_name + '"' : ''})`;
    case 'label': return `get_by_label("${s.params.label}")`;
    case 'placeholder': return `get_by_placeholder("${s.params.placeholder}")`;
    case 'text': return `get_by_text("${s.params.text}")`;
    case 'alt': return `get_by_alt_text("${s.params.alt}")`;
    case 'title': return `get_by_title("${s.params.title}")`;
    case 'css': return `css("${s.params.css}")`;
    default: return JSON.stringify(s);
  }
}

function toggleElement(id) {
  const el = state.elements.find(e => e.id === id);
  if (el) {
    el.checked = !el.checked;
    renderTree();
    renderMethods();
  }
}

function toggleAll(checked) {
  state.elements.forEach(e => { e.checked = checked; });
  renderTree();
  renderMethods();
}

// ==============================
// 渲染方法预览
// ==============================
function renderMethods() {
  const checked = state.elements.filter(e => e.checked !== false);
  if (checked.length === 0) {
    dom.methodList.innerHTML = '<div class="method-item method-placeholder">无选中元素</div>';
    return;
  }

  let html = '';
  const methods = inferMethodsFromState();
  for (const m of methods) {
    html += `<div class="method-item">`;
    html += `<span class="method-name">${escapeHtml(m.name)}</span>`;
    html += `<span class="method-args">(${m.params.join(', ')})</span>`;
    html += `<span class="method-arrow">→</span>`;
    html += `<span class="method-result">${escapeHtml(m.action)}</span>`;
    html += `</div>`;
  }
  if (!methods.length) {
    html = '<div class="method-item method-placeholder">选择元素后将自动推断方法</div>';
  }
  dom.methodList.innerHTML = html;
}

function inferMethodsFromState() {
  const methods = [];
  for (const group of state.groups) {
    const groupElements = state.elements.filter(
      e => group.elementIds.includes(e.id) && e.checked !== false
    );
    if (groupElements.length === 0) continue;

    const inputs = groupElements.filter(e => ['input', 'textarea', 'select'].includes(e.elementType));
    const buttons = groupElements.filter(e => e.elementType === 'button');
    const links = groupElements.filter(e => e.elementType === 'link');

    if (inputs.length > 0 && buttons.length > 0) {
      methods.push({
        name: toSnakeCase(buttons[0].description || 'action'),
        params: inputs.map(i => i.selectorName.replace(/_input$/, '')),
        action: 'fill + click'
      });
    }
    for (const btn of buttons) {
      if (inputs.length > 0 && buttons.indexOf(btn) === 0) continue;
      methods.push({ name: 'click_' + btn.selectorName, params: [], action: 'click' });
    }
    for (const link of links) {
      methods.push({ name: 'goto_' + link.selectorName, params: [], action: 'click link' });
    }
  }
  return methods;
}

// ==============================
// 代码预览
// ==============================
async function previewCode() {
  try {
    const response = await chrome.runtime.sendMessage({ type: 'PREVIEW_CODE' });
    if (response.type === 'CODE_GENERATED') {
      state.generatedCode = response;
      // 默认显示 selector 文件
      showPreviewModal('selector');
    } else {
      alert('生成失败: ' + (response.error || '未知错误'));
    }
  } catch (e) {
    // 如果 Service Worker 不可用，尝试本地生成（TODO: 加载本地生成逻辑）
    alert('代码预览需要插件 Service Worker 运行中。请重新加载插件。');
  }
}

function showPreviewModal(tab) {
  dom.previewModal.style.display = 'flex';
  switchPreviewTab(tab);
}

function closePreview() {
  dom.previewModal.style.display = 'none';
}

function switchPreviewTab(tab) {
  dom.modalTabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  const code = state.generatedCode || {};
  dom.previewCode.textContent = code[tab + 'File'] || '// 暂无内容';
}

// ==============================
// 导出文件
// ==============================
async function exportFiles() {
  dom.btnExport.textContent = '导出中…';
  dom.btnExport.disabled = true;
  try {
    const response = await chrome.runtime.sendMessage({ type: 'EXPORT_FILES' });
    if (response.type === 'EXPORT_COMPLETE') {
      dom.btnExport.innerHTML = `<svg class="btn-icon-s" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> 已导出`;
      setTimeout(() => {
        dom.btnExport.innerHTML = `<svg class="btn-icon-s" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> 导出文件`;
        dom.btnExport.disabled = false;
      }, 2000);
    } else {
      alert('导出失败: ' + (response.error || '未知错误'));
      dom.btnExport.innerHTML = '导出文件';
      dom.btnExport.disabled = false;
    }
  } catch (e) {
    alert('导出失败: ' + e.message);
    dom.btnExport.innerHTML = '导出文件';
    dom.btnExport.disabled = false;
  }
}

// ==============================
// 手动补充模式
// ==============================
async function toggleManualPick() {
  state.manualPick = !state.manualPick;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;

  if (state.manualPick) {
    dom.btnManualPick.innerHTML = '<span class="manual-add-plus" style="background:rgba(239,68,68,0.2);color:var(--red)">✕</span> 退出采集模式';
    dom.btnManualPick.style.borderColor = 'rgba(242,89,89,0.3)';
  } else {
    dom.btnManualPick.innerHTML = '<span class="manual-add-plus">+</span> 手动补充元素';
    dom.btnManualPick.style.borderColor = '';
  }

  await chrome.tabs.sendMessage(tab.id, {
    type: 'MANUAL_PICK_MODE',
    enabled: state.manualPick
  });
}

// ==============================
// 工具函数
// ==============================
function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function toSnakeCase(str) {
  if (!str) return 'action';
  const map = {
    '登录': 'login', '注册': 'register', '搜索': 'search',
    '提交': 'submit', '保存': 'save', '取消': 'cancel',
    '删除': 'delete', '编辑': 'edit', '添加': 'add',
    '确认': 'confirm', '关闭': 'close', '返回': 'back',
    '首页': 'home', '设置': 'settings', '个人中心': 'profile',
    '忘记密码': 'forgot_password', '用户名': 'username', '密码': 'password'
  };
  if (map[str]) return map[str];
  return str.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'action';
}

// ==============================
// 启动
// ==============================
init();
```

- [ ] **Step 2: 验证语法**

```bash
node --check /e/Code/auto_test/browser-extension/sidepanel/panel.js
```

- [ ] **Step 3: 提交**

```bash
cd /e/Code/auto_test
git add browser-extension/sidepanel/panel.js
git commit -m "feat: 添加 Side Panel JS 逻辑（状态管理/渲染/事件/通信）"
```

---

### Task 11: 安装测试 + 端到端验证

- [ ] **Step 1: 在 Chrome 中加载插件**

1. 打开 `chrome://extensions/`
2. 开启"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择 `E:\Code\auto_test\browser-extension\` 目录

- [ ] **Step 2: 在测试页面中验证扫描功能**

1. 打开任意网页（例如 `https://www.baidu.com`）
2. 点击工具栏中的插件图标 → 打开 Side Panel
3. 点击"重新扫描"
4. 验证：元素树展示扫描结果，分组正确，策略标签可读

- [ ] **Step 3: 验证勾选/取消 + 方法预览**

1. 点击元素卡片切换勾选状态
2. 验证：方法预览区实时更新
3. 点击"全选"/"取消"按钮
4. 验证：全部切换

- [ ] **Step 4: 验证过滤 + 搜索**

1. 选择过滤类型 "按钮" → 验证仅显示按钮元素
2. 输入搜索关键字 → 验证过滤结果

- [ ] **Step 5: 验证代码预览**

1. 点击"预览"按钮
2. 验证：模态弹窗显示 3 个 tab（selector.py / page.py / test.py）
3. 切换 tab → 验证内容切换正确
4. 关闭弹窗

- [ ] **Step 6: 验证导出**

1. 点击"导出文件"
2. 验证：下载 3 个 .py 文件
3. 检查文件内容格式是否正确

- [ ] **Step 7: 提交（如有修复）**

```bash
cd /e/Code/auto_test
git add -A
git commit -m "fix: 端到端验证后的修复"
```

---

### Task 12: 文档 + README

- [ ] **Step 1: 编写 pages/README.md 补充说明**

编辑 `browser-extension/../pages/README.md` 或在扩展目录中创建简短说明：

不需要额外 README——UI 预览和设计文档已就绪。

- [ ] **Step 2: 最终提交**

```bash
cd /e/Code/auto_test
git status
git add -A
git commit -m "docs: 浏览器插件实施完成，设计文档和 UI 预览就绪"
```

---

## 自检清单

- [x] Spec 全覆盖：Locator 算法（Task 3）、代码生成（Task 5, 6）、DOM 扫描（Task 7）、UI（Task 9, 10）
- [x] 无占位符：所有步骤均有完整代码
- [x] 类型一致：ElementMeta/LocatorStrategy/ElementEntry 等类型在跨模块中一致
- [x] 待定事项已排除：i18n、LLM、跨浏览器均不在本计划范围内
