# 测试框架性能轻量级优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 E2E 测试执行中 3 个冗余操作瓶颈——缓存验证临时 Context、smart_login 冗余导航、NetworkCapture 固定延迟。

**Architecture:** 纯裁剪：删除重复的 Context 创建和页面导航，简化函数签名，降低默认延迟。不新增任何代码、依赖或抽象。

**Tech Stack:** Python 3.11+, Playwright, pytest

**Spec:** `docs/superpowers/specs/2026-05-17-test-perf-lightweight-fix-design.md`

---

### Task 1: 简化 `is_storage_state_valid()` — 去掉回退验证

**Files:**
- Modify: `src/core/cache_utils.py:57-117`
- Modify: `src/auth/smart_login.py:173`
- Modify: `tests/e2e/conftest.py:99,169`

- [ ] **Step 1: 修改 `is_storage_state_valid()` 函数体**

编辑 `src/core/cache_utils.py`，将 `is_storage_state_valid` 函数替换为纯 cookie 检查版本：

```python
def is_storage_state_valid(storage_path: Path) -> bool:
    """
    验证缓存文件是否有效（检查认证 cookie 是否过期）

    Args:
        storage_path: 缓存文件路径

    Returns:
        缓存有效返回 True，否则 False
    """
    if not storage_path.exists():
        return False
    try:
        with open(storage_path, 'r') as f:
            state = json.load(f)
        cookies = state.get('cookies', [])
        now = time.time()
        return any(
            c.get('name') in AUTH_COOKIE_NAMES and
            c.get('expires', now + 1) > now
            for c in cookies
        )
    except Exception as e:
        logger.warning(f"缓存文件无效: {storage_path}, 错误: {e}")
        return False
```

- [ ] **Step 2: 删除 `_is_page_logged_in()` 函数**

在 `cache_utils.py` 中删除 100-114 行的 `_is_page_logged_in` 函数。

- [ ] **Step 3: 移除未使用的 `Browser` 导入**

将 `cache_utils.py` 第 20 行从：
```python
from playwright.sync_api import Page, Browser
```
改为：
```python
from playwright.sync_api import Page
```

- [ ] **Step 4: 更新 smart_login.py 调用处**

编辑 `src/auth/smart_login.py` 第 173 行，从：
```python
if is_storage_state_valid(cache_path, self.browser, settings.base_url):
```
改为：
```python
if is_storage_state_valid(cache_path):
```

- [ ] **Step 5: 更新 e2e/conftest.py 调用处 (logged_in_page)**

编辑 `tests/e2e/conftest.py` 第 99 行，从：
```python
if storage_path and is_storage_state_valid(storage_path, browser, base_url):
```
改为：
```python
if storage_path and is_storage_state_valid(storage_path):
```

- [ ] **Step 6: 更新 e2e/conftest.py 调用处 (multi_users_pages)**

编辑 `tests/e2e/conftest.py` 第 169 行，从：
```python
if storage_path and is_storage_state_valid(storage_path, browser, base_url):
```
改为：
```python
if storage_path and is_storage_state_valid(storage_path):
```

- [ ] **Step 7: 运行现有测试验证无回归**

```bash
cd E:/Code/auto_test && python -m pytest tests/unit/ -v
```
Expected: 所有单元测试通过。

- [ ] **Step 8: 提交**

```bash
git add src/core/cache_utils.py src/auth/smart_login.py tests/e2e/conftest.py
git commit -m "perf: 简化 is_storage_state_valid，去掉回退验证的临时 Context

- 只保留 cookie expires 时间戳检查
- 移除 _is_page_logged_in 内部函数
- 移除未使用的 Browser 导入
- 更新所有调用处签名

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 去掉 `smart_login()` 缓存恢复后的冗余页面导航

**Files:**
- Modify: `src/auth/smart_login.py:236-247`

- [ ] **Step 1: 删除冗余的二次验证代码**

编辑 `src/auth/smart_login.py`，将 `smart_login()` 方法中第 236-247 行替换。当前代码：

```python
            else:
                # 验证缓存恢复后的页面是否仍处于登录状态（可选）
                self.page.goto(settings.base_url)
                try:
                    wait_for_login_success(self.page, timeout=DEFAULT_LOGIN_SUCCESS_TIMEOUT)
                    logger.info("✅ 缓存登录状态验证通过")
                except Exception:
                    logger.warning("⚠️ 缓存恢复后登录状态失效，重新登录")
                    self._close_context_safely()
                    self._close_page_safely()
                    self.login()
                    self.save_state()
```

替换为：

```python
```

即完全删除 `else` 分支中的 12 行，回到简单的 if-not-then 结构。

`smart_login()` 方法最终为：

```python
    def smart_login(self) -> Page:
        """
        智能登录：优先尝试缓存，若无效则执行实时登录并保存缓存
        返回已登录的 Page 对象
        """
        try:
            self.start_browser()
            if not self.load_state():
                logger.info(f"🔄 缓存不可用，执行实时登录：{self.username}")
                self.login()
                self.save_state()
            return self.page
        except Exception as e:
            self.stop_browser()
            raise RuntimeError(f"智能登录失败: {e}")
```

- [ ] **Step 2: 验证代码结构完整**

```bash
cd E:/Code/auto_test && python -c "from auth.smart_login import SmartLogin; print('Import OK')"
```
Expected: 无 ImportError。

- [ ] **Step 3: 提交**

```bash
git add src/auth/smart_login.py
git commit -m "perf: 去掉 smart_login 缓存恢复后的冗余页面导航

cache restore 后不再做 page.goto + wait_for_login_success 二次验证，
Context 已通过 storage_state 注入有效 cookies。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: NetworkCapture `final_delay` 默认值归零

**Files:**
- Modify: `src/core/network_capture.py:61`

- [ ] **Step 1: 修改默认值**

编辑 `src/core/network_capture.py` 第 61 行，从：
```python
            final_delay: float = 0.3,
```
改为：
```python
            final_delay: float = 0,
```

- [ ] **Step 2: 验证导入正常**

```bash
cd E:/Code/auto_test && python -c "from core.network_capture import NetworkCapture; print('Import OK')"
```
Expected: 无 ImportError。

- [ ] **Step 3: 提交**

```bash
git add src/core/network_capture.py
git commit -m "perf: NetworkCapture final_delay 默认值从 0.3 改为 0

Playwright 事件监听是同步回调，不需要固定延迟等待。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
