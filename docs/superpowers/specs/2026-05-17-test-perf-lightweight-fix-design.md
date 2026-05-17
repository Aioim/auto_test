# 测试框架性能轻量级优化方案

日期：2026-05-17 | 类型：性能优化 | 策略：方案 A（轻量级修补）

## 背景

基于 `auto_test` 自动化测试框架（Python + Playwright + Allure + YAML 数据驱动），面向大规模 E2E 测试套件（100+ 用例）的性能瓶颈分析。用户主要痛点：浏览器操作执行慢。

## 根因分析

| # | 瓶颈 | 位置 | 每次开销 |
|---|------|------|---------|
| 1 | 登录缓存验证创建临时 Context | `cache_utils.is_storage_state_valid()` | 2x Context 创建 + 1 次导航 |
| 2 | 缓存恢复后冗余页面验证 | `smart_login.smart_login()` | 1 次额外完整页面导航 |
| 3 | NetworkCapture 固定延迟 | `network_capture.capture()` | 0.3s 无条件 sleep |

## 设计

### 修改 1：简化 `is_storage_state_valid()`

**当前**：cookie 快速检查 → 若不通过则创建临时 Context 导航 base_url 验证登录。

**改后**：只保留 cookie `expires` 时间戳检查。cookie 的 expires 是服务端设定的权威值，若未过期即有效。极少数服务端提前吊销的情况会在测试第一步操作时自然暴露。

签名变更：`is_storage_state_valid(storage_path, browser, base_url)` → `is_storage_state_valid(storage_path)`

删除内部函数 `_is_page_logged_in()`。

**影响文件**：
- `src/core/cache_utils.py`（定义）
- `src/auth/smart_login.py` — `SmartLogin.load_state()` 调用处
- `tests/e2e/conftest.py` — `logged_in_page` 和 `multi_users_pages` 调用处

### 修改 2：去掉 `smart_login()` 缓存恢复后的冗余验证

**当前**：`load_state()` 返回 True 后，再次 `page.goto(base_url)` + `wait_for_login_success()`。

**改后**：`load_state()` 返回 True 后直接返回 Page 对象。Context 已通过 storage_state 注入 cookies/localStorage，无需二次验证。

**影响文件**：`src/auth/smart_login.py`

### 修改 3：NetworkCapture 默认延迟归零

**当前**：`capture()` 方法 `final_delay` 默认为 `0.3` 秒，每次捕获无条件 sleep。

**改后**：默认值改为 `0`。Playwright 事件监听是同步回调，不存在延迟触发问题。

**影响文件**：`src/core/network_capture.py`

## 影响面

| 文件 | 改动规模 | 风险 |
|------|---------|------|
| `src/core/cache_utils.py` | ~20 行删除 | 低 |
| `src/auth/smart_login.py` | ~11 行删除 | 低 |
| `tests/e2e/conftest.py` | 2 处参数调整 | 低 |
| `src/core/network_capture.py` | 1 行数值修改 | 极低 |

## 预期效果

- 单次缓存命中测试：消除 1 次 Context 创建 + 2 次页面完整导航 → 预计提速 40-60%
- 100 用例套件：消除 30s NetworkCapture 固定延迟
- 无新增依赖，无架构变更，无 API 兼容性破坏
