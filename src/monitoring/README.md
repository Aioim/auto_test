# Monitoring 模块文档

## 模块概述

Monitoring 模块是一个功能强大的错误监控系统，为自动化测试提供了全面的错误检测和处理能力。它通过捕获页面弹窗、控制台错误、网络请求失败和页面错误元素，帮助测试人员及时发现和处理测试过程中的问题。

**核心功能**：
- **多类型错误检测**：捕获页面弹窗、控制台错误、网络请求失败和页面错误元素
- **智能截图**：错误发生时自动截图，支持全屏和视口截图模式
- **错误过滤**：支持通过正则表达式忽略特定错误
- **实时日志**：实时输出错误信息，消除反馈延迟
- **多种使用方式**：支持装饰器、上下文管理器和直接使用
- **交互式模式**：支持错误发生时暂停并等待用户确认
- **自动继续模式**：支持截图后自动继续执行，不中断测试流程

## 模块结构

Monitoring 模块包含以下文件：

- **__init__.py**：模块初始化文件，导出 ErrorMonitor 和 monitor_errors
- **error_monitor.py**：错误监控的核心实现，包含 ErrorMonitor 类和 monitor_errors 装饰器

## 核心功能

### 1. ErrorMonitor 类

**功能**：
- **错误捕获**：捕获页面弹窗、控制台错误、网络请求失败和页面错误元素
- **智能截图**：错误发生时自动截图，支持全屏和视口截图模式
- **错误过滤**：支持通过正则表达式忽略特定错误
- **实时日志**：实时输出错误信息，消除反馈延迟
- **上下文管理**：支持作为上下文管理器使用
- **资源清理**：自动移除事件监听器，防止资源泄漏

**主要方法**：
- `check_errors(error_selectors=None)`：检查各类错误，返回包含所有错误信息的字典
- `format_error_message(errors)`：格式化错误信息，生成清晰的错误报告
- `remove_listeners()`：移除事件监听器，防止资源泄漏
- `clear()`：清理数据并移除监听器
- `__enter__()` 和 `__exit__()`：支持作为上下文管理器使用

### 2. monitor_errors 装饰器

**功能**：
- **函数监控**：监控被装饰函数的执行过程，捕获错误
- **自动截图**：错误发生时自动截图
- **错误处理**：可配置是否在检测到错误时抛出异常
- **交互式模式**：支持错误发生时暂停并等待用户确认
- **自动继续模式**：支持截图后自动继续执行，不中断测试流程

**参数**：
- `page`：Playwright Page 对象
- `error_selectors`：页面上错误元素的 CSS 选择器列表
- `raise_on_error`：检测到错误时是否抛出 AssertionError
- `screenshot_on_error`：检测到错误时是否截图
- `screenshot_dir`：截图保存目录
- `interactive_mode`：交互模式，出现错误时等待用户确认
- `auto_continue_after_screenshot`：自动继续模式，截图后自动继续执行
- `max_errors`：每种类型最多记录的错误数量
- `ignore_errors`：忽略的错误消息模式列表（正则表达式字符串）
- `screenshot_helper`：可选的 ScreenshotHelper 实例
- `log_immediately`：是否在监听到错误时立即打印日志
- `fast_screenshot`：使用视口截图代替全页截图，提升速度

## 使用示例

### 1. 使用装饰器

```python
from playwright.sync_api import sync_playwright
from utils.monitoring import monitor_errors
from utils.screenshot import ScreenshotHelper

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # 推荐：创建共享的 ScreenshotHelper 实例
    screenshot_helper = ScreenshotHelper(page, screenshot_dir="screenshots")
    
    @monitor_errors(
        page=page,
        screenshot_helper=screenshot_helper,
        raise_on_error=True,
        screenshot_on_error=True,
        ignore_errors=[r"404 Not Found", r"favicon\.ico"],
        auto_continue_after_screenshot=False,
        log_immediately=True,      # 实时输出错误，消除延迟
        fast_screenshot=False      # 默认全屏，可设为 True 提速
    )
    def test_login():
        page.goto("https://example.com/login")
        page.fill("#username", "test")
        page.fill("#password", "wrong")
        page.click("#login-button")
        page.wait_for_selector(".error-message", timeout=3000)
    
    test_login()
    browser.close()
```

### 2. 使用上下文管理器

```python
from playwright.sync_api import sync_playwright
from utils.monitoring import ErrorMonitor
from utils.screenshot import ScreenshotHelper

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # 创建 ScreenshotHelper 实例
    screenshot_helper = ScreenshotHelper(page, screenshot_dir="screenshots")
    
    # 使用上下文管理器
    with ErrorMonitor(
        page=page,
        screenshot_helper=screenshot_helper,
        screenshot_on_error=True,
        func_name="test_form_submission",
        ignore_errors=[r"404 Not Found"],
        log_immediately=True,
        fast_screenshot=True
    ) as monitor:
        # 执行测试操作
        page.goto("https://example.com/form")
        page.fill("#name", "Test User")
        page.fill("#email", "invalid-email")
        page.click("#submit-button")
        
        # 检查错误
        errors = monitor.check_errors(error_selectors=[".error-message", ".validation-error"])
        
        if errors["has_error"]:
            print(f"检测到错误: {monitor.format_error_message(errors)}")
            print(f"截图已保存: {errors['screenshot']}")
    
    browser.close()
```

### 3. 测试弹窗监控

```python
from playwright.sync_api import sync_playwright
from utils.monitoring import test_alert_screenshot

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    test_alert_screenshot(page, screenshot_dir="./test_screenshots")
    browser.close()
```

## 错误类型

Monitoring 模块可以检测以下类型的错误：

### 1. 页面弹窗（Dialogs）
- **类型**：alert、confirm、prompt、beforeunload
- **捕获内容**：弹窗类型、消息内容、时间戳
- **注意**：原生弹窗无法被截图捕获，仅记录

### 2. 控制台错误（Console Errors）
- **类型**：error、warning
- **捕获内容**：错误类型、错误消息、时间戳

### 3. 网络请求失败（Failed Requests）
- **捕获内容**：请求 URL、失败原因、时间戳

### 4. 页面错误元素（Page Errors）
- **捕获方式**：通过 CSS 选择器指定错误元素
- **捕获内容**：选择器、元素文本内容

## 最佳实践

### 1. 错误监控最佳实践

- **使用 ScreenshotHelper**：创建共享的 ScreenshotHelper 实例，提高截图效率和一致性
- **合理设置错误选择器**：根据应用特点，设置合适的错误元素选择器
- **使用错误过滤**：忽略已知的、不影响测试的错误，如 404 错误、favicon 加载失败等
- **实时日志**：启用 `log_immediately=True`，实时了解错误情况
- **快速截图**：对于大型页面，启用 `fast_screenshot=True` 提高截图速度
- **自动继续模式**：对于非关键错误，启用 `auto_continue_after_screenshot=True`，避免测试中断

### 2. 性能优化

- **批量检查**：使用 `check_errors` 一次性检查所有错误，避免多次截图
- **错误过滤**：通过 `ignore_errors` 过滤不需要关注的错误，减少处理开销
- **快速截图**：对于大型页面，使用 `fast_screenshot=True` 提高截图速度
- **资源清理**：使用上下文管理器或手动调用 `clear()` 方法，确保资源被正确释放

### 3. 错误处理策略

- **关键错误**：设置 `raise_on_error=True`，立即中断测试并抛出异常
- **非关键错误**：设置 `raise_on_error=False` 或 `auto_continue_after_screenshot=True`，记录错误但继续执行
- **交互式调试**：在开发和调试阶段，设置 `interactive_mode=True`，暂停并查看错误详情
- **错误分析**：使用 `format_error_message` 生成清晰的错误报告，便于分析和调试

### 4. 截图管理

- **统一目录**：为所有测试设置统一的截图目录，便于管理和分析
- **合理命名**：使用有意义的函数名和错误类型，使截图文件名清晰明了
- **自动清理**：配置 ScreenshotHelper 的 `auto_cleanup` 参数，定期清理旧截图
- **Allure 集成**：启用 ScreenshotHelper 的 `enable_allure` 参数，自动将截图附加到 Allure 报告

## 依赖

- **playwright**：浏览器自动化库，提供页面操作和事件监听功能
- **ScreenshotHelper**：截图辅助工具，提供错误截图功能
- **logger**：日志模块，提供日志记录功能

## 安装

```bash
# 安装基础依赖
pip install playwright

# 安装 ScreenshotHelper 依赖
pip install allure-pytest opencv-python numpy
```

## 总结

Monitoring 模块是一个功能强大、设计合理的错误监控系统，为自动化测试提供了全面的错误检测和处理能力。通过捕获各类错误并自动截图，它帮助测试人员及时发现和处理测试过程中的问题，提高测试的可靠性和稳定性。

**使用 Monitoring 模块的优势**：
- **全面的错误检测**：捕获多种类型的错误，提供全面的错误监控
- **智能截图**：错误发生时自动截图，保存错误现场
- **灵活的配置**：支持多种配置选项，适应不同的测试场景
- **多种使用方式**：支持装饰器、上下文管理器和直接使用，满足不同的使用需求
- **实时反馈**：实时输出错误信息，消除反馈延迟
- **性能优化**：批量检查错误，支持快速截图，提高监控效率

**适用场景**：
- **Web 自动化测试**：监控页面操作过程中的各类错误
- **表单测试**：检测表单验证错误和提交失败
- **API 测试**：监控网络请求失败和响应错误
- **视觉测试**：结合截图功能，检测页面视觉异常
- **稳定性测试**：长期运行测试，监控偶发错误

通过使用 Monitoring 模块，您可以：
- 更全面地检测测试过程中的错误
- 更快速地定位和分析错误原因
- 更有效地管理测试过程和结果
- 提高测试的可靠性和稳定性
- 生成更丰富、更专业的测试报告

---

**注意**：使用前请确保已安装所有必要的依赖，并根据实际需求配置相关选项。对于大型页面，建议启用 `fast_screenshot=True` 以提高截图速度。