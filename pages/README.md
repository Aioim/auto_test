# BasePage 文档

## 模块概述

BasePage 是一个基于 Page Object Pattern 的页面对象基类，为自动化测试提供了全面的页面操作功能。它通过 Mixin 模式组合了多个功能模块，为所有页面对象类提供了统一的接口和丰富的操作方法。

**核心功能**：
- **页面导航**：页面跳转、刷新、前进、后退等
- **元素操作**：点击、输入、选择、上传等
- **断言功能**：元素存在、可见、文本内容等断言
- **等待机制**：等待元素、URL、页面加载状态等
- **Frame 处理**：Frame 切换和操作
- **网络请求**：API 响应捕获、文件下载、HTTP 请求等
- **弹窗处理**：对话框的等待、接受、取消等
- **滚动操作**：滚动到元素、滚动页面等
- **截图功能**：页面截图、元素截图、失败自动截图等
- **JavaScript 执行**：执行 JavaScript 代码
- **Playwright 断言**：基于 Playwright expect 的断言功能

## 类结构

### BasePage 主类

BasePage 继承了多个 Mixin 类，组合了所有功能模块：

```python
class BasePage(
    NavigationMixin,
    ElementActionsMixin,
    AssertionMixin,
    WaitMixin,
    FrameMixin,
    NetworkMixin,
    DialogMixin,
    ScrollMixin,
    ScreenshotMixin,
    JavaScriptMixin,
    ExpectMixin
):
    """页面对象基类 - 组合所有功能模块"""

    # 默认等待超时时间（毫秒）
    DEFAULT_TIMEOUT = 5000

    # 默认重试次数
    DEFAULT_RETRIES = 3

    def __init__(self, page: Page, base_url: Optional[str] = None):
        """
        初始化 BasePage

        Args:
            page: Playwright Page 对象
            base_url: 基础 URL（可选）
        """
        self.page = page
        self.base_url = base_url or getattr(settings, "BASE_URL", None)
        # 页面元数据
        self._page_name = self.__class__.__name__
        self._load_time: Optional[float] = None
        # 控制台日志（可选监听）
        self._console_logs: List[str] = []
        self._console_handler = None  # 保存监听器引用，以便移除
```

### Mixin 模块

#### 1. NavigationMixin

**功能**：页面导航相关操作

**主要方法**：
- `goto(url, timeout=None, wait_until="load")`：导航到指定 URL（支持相对路径拼接 base_url）
- `reload(timeout=None, wait_until="load")`：重新加载页面
- `go_back(timeout=None)`：返回上一页
- `go_forward(timeout=None)`：前进到下一页
- `current_url()`：获取当前 URL
- `title()`：获取页面标题

#### 2. ElementActionsMixin

**功能**：元素操作相关功能（点击、输入、获取属性等）

**主要方法**：
- **底层定位**：`resolve(selector)`、`resolve_with_info(selector)`
- **查找与等待**：`find(selector, wait_for="visible", timeout=None, retries=None)`、`exists(selector, timeout=None, retries=None)`、`wait_for(selector, state=None, timeout=None)`
- **点击操作**：`click(selector, wait_for="visible", timeout=None, retries=None, force=False, no_wait_after=False, position=None, modifiers=None)`、`double_click(selector, wait_for="visible", timeout=None, force=False)`、`right_click(selector, wait_for="visible", timeout=None)`、`hover(selector, wait_for="visible", timeout=None)`
- **输入操作**：`fill(selector, value, wait_for="visible", timeout=None, retries=None)`、`clear(selector, wait_for="visible", timeout=None)`、`press(selector, key, wait_for="visible", timeout=None)`、`press_sequentially(selector, keys, wait_for="visible", timeout=None, delay=100)`
- **获取文本与属性**：`text(selector, wait_for="visible", timeout=None)`、`all_texts(selector, wait_for="attached", timeout=None)`、`attribute(selector, name, wait_for="visible", timeout=None)`、`all_attributes(selector, name, wait_for="attached", timeout=None)`
- **状态检查**：`is_checked(selector, timeout=None)`、`is_visible(selector, timeout=None)`、`is_enabled(selector, timeout=None)`、`is_disabled(selector, timeout=None)`
- **表单操作**：`select_option(selector, value, wait_for="visible", timeout=None)`、`upload_file(selector, file_path, wait_for="visible", timeout=None)`、`clear_file(selector, wait_for="visible", timeout=None)`

#### 3. AssertionMixin

**功能**：断言相关功能（使用 find 等待元素，提高稳定性）

**主要方法**：
- `assert_exists(selector, message=None, timeout=None)`：断言元素存在（等待 attached 状态）
- `assert_not_exists(selector, message=None, timeout=None)`：断言元素不存在（等待 detach 或检查 count）
- `assert_visible(selector, message=None, timeout=None)`：断言元素可见
- `assert_hidden(selector, message=None, timeout=None)`：断言元素隐藏
- `assert_text(selector, expected, exact=False, message=None, timeout=None)`：断言元素文本
- `assert_attribute(selector, name, expected, message=None, timeout=None)`：断言元素属性

#### 4. WaitMixin

**功能**：等待相关功能

**主要方法**：
- `wait_for_url(url, timeout=None)`：等待 URL 匹配（支持字符串或函数）
- `wait_for_load_state(state="networkidle", timeout=None)`：等待页面加载状态
- `wait_for_function(expression, timeout=None, polling="raf")`：等待 JavaScript 函数返回 true
- `wait_for_timeout(timeout)`：等待指定时间

#### 5. FrameMixin

**功能**：Frame 处理

**主要方法**：
- `frame_context(frame_name=None, frame_url=None)`：切换到指定 Frame 的上下文管理器（无需切换回主页面，直接返回 frame）

#### 6. NetworkMixin

**功能**：网络请求与下载

**主要方法**：
- `get_api_response(url_matcher, trigger_action, *args, timeout=None, description="unknown action", **kwargs)`：执行触发操作并等待匹配的网络响应
- `capture_requests(urls)`：捕获指定 URL 的请求数据
- `download_file(selector, wait_for="visible", timeout=None)`：下载文件并返回临时路径
- `download_file_to(selector, target_path, wait_for="visible", timeout=None)`：下载文件并保存到指定路径
- `send_request(method, url, data=None, headers=None, timeout=None)`：发送 HTTP 请求（使用浏览器上下文）
- `post_json(url, data, headers=None, timeout=None)`：发送 POST 请求并返回 JSON
- `get_json(url, params=None, headers=None, timeout=None)`：发送 GET 请求并返回 JSON，正确处理已有查询参数的 URL

#### 7. DialogMixin

**功能**：弹窗处理（注意：对话框必须在触发操作后立即处理）

**主要方法**：
- `wait_for_dialog(timeout=None)`：等待对话框出现并返回对话框对象（需在触发对话框的操作之后调用）
- `accept_dialog(timeout=None)`：接受当前对话框（需在触发对话框后调用）
- `dismiss_dialog(timeout=None)`：取消当前对话框（需在触发对话框后调用）
- `get_dialog_message(timeout=None)`：获取对话框消息（不自动关闭）
- `handle_dialog(accept=True, timeout=None)`：处理对话框并返回消息（自动接受或取消）

#### 8. ScrollMixin

**功能**：滚动操作

**主要方法**：
- `scroll_to(selector, wait_for="visible", timeout=None)`：滚动到指定元素
- `scroll_by(x=0, y=0)`：按指定偏移量滚动
- `scroll_to_top()`：滚动到页面顶部
- `scroll_to_bottom()`：滚动到页面底部

#### 9. ScreenshotMixin

**功能**：截图与调试

**主要方法**：
- `screenshot(path=None, full_page=False, selector=None, **kwargs)`：截取页面或元素截图
- `screenshot_on_failure(name="failure", full_page=True)`：失败时截图（目录从配置读取，默认为 screenshots/），使用 UUID 避免冲突
- `auto_screenshot_on_error(name="operation")`：上下文管理器，操作失败时自动截图
- `debug_info(selector)`：获取选择器的调试信息

#### 10. JavaScriptMixin

**功能**：JavaScript 执行

**主要方法**：
- `evaluate(expression, *args)`：执行 JavaScript 表达式
- `evaluate_on_selector(selector, expression, *args)`：在指定元素上执行 JavaScript 表达式

#### 11. ExpectMixin

**功能**：Playwright expect 断言封装（支持自动重试）

**主要方法**：
- `expect(selector, **kwargs)`：返回 Playwright 的 expect 断言对象，支持链式调用
- **常用断言快捷方法**：`expect_visible(selector, message=None)`、`expect_hidden(selector, message=None)`、`expect_enabled(selector, message=None)`、`expect_disabled(selector, message=None)`、`expect_checked(selector, message=None)`、`expect_text(selector, expected, exact=False, message=None)`、`expect_value(selector, expected, message=None)`、`expect_count(selector, expected, message=None)`、`expect_attribute(selector, name, value, message=None)`、`expect_url(url, message=None)`、`expect_title(title, message=None)`

## 使用示例

### 1. 基本使用

```python
from pages.base_page import BasePage
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    # 初始化 BasePage
    base_page = BasePage(page, base_url="https://example.com")
    
    # 导航到页面
    base_page.goto("/")
    
    # 点击元素
    base_page.click("button")
    
    # 填充输入框
    base_page.fill("input[type='text']", "test value")
    
    # 获取文本
    text = base_page.text("h1")
    print(f"Page title: {text}")
    
    # 断言元素可见
    base_page.assert_visible("div.result")
    
    # 截图
    base_page.screenshot(path="screenshot.png")
    
    browser.close()
```

### 2. 继承 BasePage 创建自定义页面类

```python
from pages.base_page import BasePage
from core.selector import Selector

class LoginPage(BasePage):
    """登录页面对象"""
    
    # 选择器
    USERNAME_INPUT = Selector(css="#username", description="用户名输入框")
    PASSWORD_INPUT = Selector(css="#password", description="密码输入框")
    LOGIN_BUTTON = Selector(css="#login-btn", description="登录按钮")
    ERROR_MESSAGE = Selector(css=".error-message", description="错误信息")
    
    def login(self, username, password):
        """执行登录操作"""
        self.fill(self.USERNAME_INPUT, username)
        self.fill(self.PASSWORD_INPUT, password)
        self.click(self.LOGIN_BUTTON)
    
    def get_error_message(self):
        """获取错误信息"""
        return self.text(self.ERROR_MESSAGE)
    
    def is_login_failed(self):
        """检查登录是否失败"""
        return self.exists(self.ERROR_MESSAGE)

# 使用示例
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    login_page = LoginPage(page, base_url="https://example.com")
    login_page.goto("/login")
    
    # 执行登录
    login_page.login("invalid", "password")
    
    # 检查登录失败
    if login_page.is_login_failed():
        error = login_page.get_error_message()
        print(f"Login failed with error: {error}")
    
    browser.close()
```

### 3. 使用网络请求功能

```python
# 捕获 API 响应
def test_api_response():
    # 点击按钮并捕获 API 响应
    response = base_page.get_api_response(
        url_matcher="/api/login",
        trigger_action=base_page.click,
        selector="#login-btn",
        description="Click login button"
    )
    
    # 检查响应状态
    assert response.status == 200
    
    # 解析响应数据
    data = response.json()
    assert data.get("success") == True

# 发送 HTTP 请求
def test_send_request():
    # 发送 POST 请求
    response = base_page.post_json(
        "/api/users",
        data={"name": "Test User", "email": "test@example.com"}
    )
    assert response.get("id") is not None
    
    # 发送 GET 请求
    user_data = base_page.get_json("/api/users/1")
    assert user_data.get("name") == "Test User"
```

### 4. 使用截图功能

```python
# 失败时自动截图
def test_with_screenshot():
    with base_page.auto_screenshot_on_error(name="login_test"):
        base_page.goto("/login")
        base_page.fill("#username", "admin")
        base_page.fill("#password", "wrongpassword")
        base_page.click("#login-btn")
        # 如果断言失败，会自动截图
        base_page.assert_visible("#dashboard")

# 手动截图
def test_manual_screenshot():
    base_page.goto("/")
    # 截取整个页面
    base_page.screenshot(path="full_page.png", full_page=True)
    # 截取元素
    base_page.screenshot(path="header.png", selector="header")
```

### 5. 使用 Frame 功能

```python
def test_frame_interaction():
    base_page.goto("/page-with-frame")
    
    # 使用 Frame 上下文
    with base_page.frame_context(frame_name="iframe-name") as frame:
        # 在 Frame 中操作元素
        frame.fill("#frame-input", "test value")
        frame.click("#frame-button")
    
    # 自动切换回主页面
    base_page.click("#main-button")
```

### 6. 使用 Playwright expect 断言

```python
def test_expect_assertions():
    base_page.goto("/")
    
    # 使用 expect 断言
    base_page.expect("h1").to_be_visible()
    base_page.expect("h1").to_have_text("Welcome")
    
    # 使用快捷方法
    base_page.expect_visible("#login-form")
    base_page.expect_text("#welcome-message", "Hello, User")
    base_page.expect_url("https://example.com/")
```

## 最佳实践

### 1. 页面类设计

- **继承 BasePage**：所有页面对象类都应继承 BasePage，获得完整的功能集
- **定义选择器**：在页面类中定义静态选择器，使用 Selector 对象提高可读性和可维护性
- **封装业务逻辑**：将页面特定的业务逻辑封装为方法，如 `login()`, `search()`, `submit_form()` 等
- **使用描述性方法名**：方法名应清晰描述其功能，如 `get_error_message()` 而不是 `get_text()"

### 2. 元素定位

- **使用 Selector 对象**：使用 Selector 对象定义元素，提供描述和多种定位策略
- **合理设置超时**：根据页面加载速度设置合理的超时时间
- **使用重试机制**：对于不稳定的元素，使用 `retries` 参数提高可靠性
- **优先使用可见性**：默认使用 `wait_for="visible"` 确保元素可交互

### 3. 断言和验证

- **使用断言方法**：使用 BasePage 提供的断言方法，如 `assert_visible()`, `assert_text()` 等
- **结合 Playwright expect**：对于复杂的断言，使用 `expect()` 方法获得更丰富的断言能力
- **添加有意义的错误信息**：在断言中添加描述性的错误信息，便于调试

### 4. 异常处理

- **使用 auto_screenshot_on_error**：在关键操作中使用 `auto_screenshot_on_error` 上下文管理器，自动捕获失败并截图
- **合理处理超时**：对于可能超时的操作，设置适当的超时时间并处理异常
- **日志记录**：使用 logger 记录关键操作和错误信息

### 5. 性能优化

- **减少等待时间**：对于快速操作，使用较短的超时时间
- **合理使用网络捕获**：只捕获必要的网络请求，避免过度捕获影响性能
- **复用页面对象**：在测试中复用页面对象，避免重复初始化
- **清理资源**：在测试结束时清理资源，如停止控制台监听器

### 6. 代码风格

- **遵循 PEP 8**：保持代码风格一致，使用 PEP 8 规范
- **添加文档字符串**：为方法和类添加详细的文档字符串
- **使用类型注解**：使用类型注解提高代码可读性和 IDE 支持
- **模块化设计**：将复杂的页面逻辑分解为多个方法，提高可维护性

## 依赖

- **playwright**：浏览器自动化库，提供页面操作和元素定位功能
- **config**：配置管理模块，提供 BASE_URL 等配置
- **logger**：日志模块，提供日志记录功能
- **core.selector**：选择器辅助模块，提供 Selector 类和选择器解析功能
- **core.screenshot**：截图辅助模块，提供截图功能（当前未使用）

## 总结

BasePage 是一个功能强大、结构清晰的页面对象基类，为自动化测试提供了全面的页面操作功能。通过 Mixin 模式，它将不同功能模块分离，提高了代码的可维护性和可扩展性。

**使用 BasePage 的优势**：
- **功能全面**：提供了几乎所有常见的页面操作功能
- **结构清晰**：通过 Mixin 模式组织代码，结构清晰易维护
- **稳定性高**：内置重试机制和等待策略，提高测试稳定性
- **扩展性强**：可以轻松扩展新的功能模块
- **使用便捷**：提供了丰富的方法和快捷方式，简化测试代码

**适用场景**：
- **Web 自动化测试**：适用于各种 Web 应用的自动化测试
- **端到端测试**：支持完整的端到端测试流程
- **API 测试**：内置网络请求功能，支持 API 测试
- **视觉测试**：支持截图功能，可用于视觉回归测试

通过使用 BasePage，您可以：
- 编写更简洁、更可靠的测试代码
- 提高测试的可维护性和可扩展性
- 减少测试代码的重复和冗余
- 获得更丰富的测试功能和更好的测试体验

---

**注意**：使用前请确保已安装所有必要的依赖，并根据实际需求配置相关选项。