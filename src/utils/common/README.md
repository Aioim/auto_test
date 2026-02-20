# Common 模块文档

## 模块概述

Common 模块是一个功能强大的通用工具集合，为自动化测试提供了多种实用功能：

- **截图辅助**：提供丰富的截图功能，支持页面截图、元素截图、高亮标注等
- **选择器辅助**：提供智能元素定位和操作功能，支持多种定位策略
- **视觉验证**：提供图像比较和视觉回归测试功能
- **日志监控**：提供实时日志监控和密码泄露检测功能

## 安装依赖

```bash
# 安装基础依赖
pip install playwright allure-pytest opencv-python numpy

# 安装可选依赖
pip install tqdm
```

## 核心功能

### 1. 截图辅助 (`ScreenshotHelper`)

**功能**：
- **多种截图类型**：完整页面、可视区域、单个元素、高亮元素等
- **元素高亮**：支持高亮单个元素或多个元素
- **标注功能**：支持文本标注、箭头标注和矩形标注
- **截图管理**：自动清理旧截图，导出截图历史
- **Allure 集成**：自动将截图附加到 Allure 报告
- **安全路径处理**：防止路径穿越攻击

**主要方法**：
- `take_screenshot()`：截取屏幕截图
- `take_element_screenshot()`：截取元素截图
- `take_full_page_screenshot()`：截取完整页面截图
- `take_viewport_screenshot()`：截取可视区域截图
- `highlight_element()`：高亮显示元素
- `highlight_and_capture()`：高亮元素并截图
- `annotate_screenshot()`：截取带标注的截图
- `cleanup_screenshots()`：清理截图文件

### 2. 选择器辅助 (`SelectorHelper`)

**功能**：
- **多种定位策略**：CSS、XPath、文本、角色、测试 ID 等
- **智能解析**：自动尝试多种定位策略，提高定位成功率
- **iframe 支持**：支持在 iframe 中定位元素
- **阴影 DOM 支持**：支持在阴影 DOM 中定位元素
- **重试机制**：支持带退避策略的重试
- **Allure 集成**：自动记录定位尝试和结果
- **国际化支持**：支持基于语言环境的本地化定位

**主要方法**：
- `resolve_locator()`：解析选择器为 Locator 对象
- `find()`：解析并等待元素达到指定状态
- `exists()`：检查元素是否存在
- `click()`：点击元素
- `fill()`：填充输入框
- `get_text()`：获取元素文本
- `is_visible()`：检查元素是否可见
- `wait_for()`：等待元素达到指定状态

### 3. 视觉验证 (`VisualValidator`)

**功能**：
- **多种比较算法**：均方误差 (MSE)、结构相似性 (SSIM)、峰值信噪比 (PSNR)
- **差异分析**：生成差异图像，高亮显示不同之处
- **目录验证**：支持验证整个目录中的图像
- **基准更新**：支持将测试图像更新为基准图像
- **阈值配置**：可配置相似度阈值

**主要方法**：
- `validate()`：验证测试图像与基准图像的相似度
- `update_baseline()`：将测试图像更新为基准图像
- `validate_directory()`：验证整个目录中的图像
- `get_baseline_images()`：获取所有基准图像
- `get_test_images()`：获取所有测试图像

### 4. 日志监控 (`RealtimeLogMonitor`)

**功能**：
- **实时监控**：实时扫描日志文件
- **密码泄露检测**：检测日志中的密码、令牌、API 密钥等敏感信息
- **紧急告警**：发现泄露时立即发出告警
- **应急记录**：将泄露信息写入应急文件
- **安全模式**：忽略已脱敏的敏感信息

**主要方法**：
- `start()`：启动监控线程
- `stop()`：停止监控

## 使用示例

### 1. 截图辅助示例

#### 基础用法

```python
from playwright.sync_api import sync_playwright
from utils.common import ScreenshotHelper

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")
    
    # 创建截图辅助实例
    helper = ScreenshotHelper(page)
    
    # 截取可视区域
    helper.take_viewport_screenshot(name="homepage")
    
    # 截取完整页面
    helper.take_full_page_screenshot(name="full_page")
    
    # 截取元素并高亮
    helper.take_element_screenshot(
        selector="h1",
        name="header",
        highlight=True
    )
    
    # 高亮元素并截图
    helper.highlight_and_capture(
        selector="p",
        name="paragraph",
        color="blue"
    )
    
    browser.close()
```

#### 带标注的截图

```python
# 截取带标注的截图
annotations = [
    {
        "type": "text",
        "text": "Important element",
        "x": 100,
        "y": 100,
        "color": "red",
        "font_size": 16
    },
    {
        "type": "arrow",
        "x1": 150,
        "y1": 150,
        "x2": 200,
        "y2": 200,
        "color": "green",
        "thickness": 2
    },
    {
        "type": "rectangle",
        "x": 250,
        "y": 250,
        "width": 100,
        "height": 50,
        "color": "blue",
        "thickness": 2,
        "opacity": 0.3
    }
]

helper.annotate_screenshot(
    name="annotated_screenshot",
    annotations=annotations
)
```

### 2. 选择器辅助示例

#### 基础用法

```python
from playwright.sync_api import sync_playwright
from utils.common import SelectorHelper, Selector

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")
    
    # 使用字符串选择器
    locator = SelectorHelper.resolve_locator(page, "h1")
    print(locator.text_content())
    
    # 使用结构化选择器
    selector = Selector(
        css="p",
        description="Paragraph element"
    )
    locator = SelectorHelper.resolve_locator(page, selector)
    print(locator.text_content())
    
    # 查找元素并等待可见
    locator = SelectorHelper.find(page, "h1", wait_for="visible")
    
    # 点击元素
    SelectorHelper.click(page, "button")
    
    # 填充输入框
    SelectorHelper.fill(page, "input[type='text']", "test value")
    
    # 检查元素是否存在
    exists = SelectorHelper.exists(page, "div.result")
    print(f"Result exists: {exists}")
    
    browser.close()
```

#### 使用 iframe 和阴影 DOM

```python
# 在 iframe 中定位元素
iframe_selector = Selector(
    css="button",
    frame_name="iframe-name"
)
SelectorHelper.click(page, iframe_selector)

# 在阴影 DOM 中定位元素
shadow_selector = Selector(
    css="input",
    shadow_path=["#shadow-host", ".shadow-content"]
)
SelectorHelper.fill(page, shadow_selector, "test")
```

### 3. 视觉验证示例

#### 基础用法

```python
from utils.common import VisualValidator

# 创建视觉验证实例
validator = VisualValidator(
    baseline_dir="test_data/visual/baseline",
    test_dir="screenshots",
    diff_dir="test_data/visual/diff",
    threshold=0.92,
    algorithm="ssim"
)

# 验证单个图像
result = validator.validate("homepage.png")
print(f"验证结果: {'通过' if result['success'] else '失败'}")
print(f"相似度: {result['similarity']:.4f}")

# 验证整个目录
 directory_result = validator.validate_directory()
print(f"目录验证结果: 总计 {directory_result['total']}, 通过 {directory_result['passed']}, 失败 {directory_result['failed']}")

# 更新基准图像
validator.update_baseline("new_homepage.png")
```

### 4. 日志监控示例

#### 基础用法

```python
from pathlib import Path
from utils.common import RealtimeLogMonitor

# 创建日志监控实例
monitor = RealtimeLogMonitor(
    log_dir=Path("logs"),
    check_interval=1.0
)

# 启动监控
monitor.start()

# 运行一段时间后停止
import time
time.sleep(60)  # 监控 60 秒
monitor.stop()
```

#### 命令行运行

```bash
# 监控默认日志目录
python log_monitor.py

# 监控指定日志目录
python log_monitor.py --log-dir /var/log/myapp

# 自定义检查间隔
python log_monitor.py --log-dir /var/log/myapp --interval 2.0
```

## API 参考

### 1. ScreenshotHelper

#### 初始化

```python
def __init__(
    self,
    page: Page,
    screenshot_dir: Optional[str] = None,
    auto_cleanup: bool = False,
    max_screenshots: int = 100,
    enable_allure: bool = True
)
```

#### 主要方法

- `take_screenshot(name=None, screenshot_type=ScreenshotType.VIEWPORT, selector=None, format=DEFAULT_FORMAT, quality=None, timeout=None, **kwargs) -> ScreenshotMetadata`
- `take_element_screenshot(selector, name=None, highlight=False, **kwargs) -> ScreenshotMetadata`
- `take_full_page_screenshot(name=None, **kwargs) -> ScreenshotMetadata`
- `take_viewport_screenshot(name=None, **kwargs) -> ScreenshotMetadata`
- `highlight_element(selector, color="red", thickness=3, style="solid", timeout=None) -> bool`
- `highlight_and_capture(selector, name=None, color="red", thickness=3, style="solid", duration=0.3, **kwargs) -> ScreenshotMetadata`
- `annotate_screenshot(name=None, annotations=None, **kwargs) -> ScreenshotMetadata`
- `cleanup_screenshots(keep_latest=None, older_than=None, pattern=None) -> int`

### 2. SelectorHelper

#### 主要方法

- `resolve_locator(page: Page, selector: SelectorLike) -> Locator`
- `find(page: Page, selector: SelectorLike, wait_for=None, timeout=None, *, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> Locator`
- `exists(page: Page, selector: SelectorLike, *, timeout=None, retries=1, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> bool`
- `click(page: Page, selector: SelectorLike, *, wait_for="visible", timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> None`
- `fill(page: Page, selector: SelectorLike, value: str, *, wait_for="visible", timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> None`
- `get_text(page: Page, selector: SelectorLike, *, wait_for="visible", timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> Optional[str]`
- `is_visible(page: Page, selector: SelectorLike, *, timeout=None, retries=1, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> bool`
- `wait_for(page: Page, selector: SelectorLike, wait_for="visible", *, timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> Locator`

### 3. VisualValidator

#### 初始化

```python
def __init__(
    self,
    baseline_dir: Optional[str] = None,
    test_dir: Optional[str] = None,
    diff_dir: Optional[str] = None,
    threshold: float = 0.92,
    algorithm: ComparisonAlgorithm = ComparisonAlgorithm.SSIM
)
```

#### 主要方法

- `validate(test_image_name: str, baseline_image_name: Optional[str] = None, threshold: Optional[float] = None, generate_diff: bool = True) -> Dict[str, Any]`
- `update_baseline(test_image_name: str, baseline_image_name: Optional[str] = None) -> bool`
- `validate_directory(threshold: Optional[float] = None) -> Dict[str, Any]`
- `get_baseline_images() -> List[str]`
- `get_test_images() -> List[str]`

### 4. RealtimeLogMonitor

#### 初始化

```python
def __init__(self, log_dir: Path, check_interval: float = 1.0)
```

#### 主要方法

- `start() -> None`
- `stop(timeout: float = 2.0) -> None`

## 配置

### 1. 截图辅助配置

可以在 `config.py` 中配置以下选项：

- `SCREENSHOT_DIR`：截图保存目录
- `SCREENSHOT_FORMAT`：默认截图格式
- `SCREENSHOT_QUALITY`：默认截图质量
- `SCREENSHOT_TIMEOUT`：截图超时时间
- `HIGHLIGHT_WAIT_MS`：高亮等待时间

### 2. 视觉验证配置

可以在 `config.py` 中配置以下选项：

- `VISUAL_BASELINE_DIR`：基准图像目录
- `VISUAL_TEST_DIR`：测试图像目录
- `VISUAL_DIFF_DIR`：差异图像输出目录
- `VISUAL_VALIDATION_THRESHOLD`：相似度阈值

### 3. 选择器辅助配置

可以在 `config.py` 中配置以下选项：

- `locale`：语言环境，用于国际化支持

## 最佳实践

### 1. 截图辅助最佳实践

- **使用上下文管理器**：对于需要高亮的操作，使用 `highlighted_context` 上下文管理器
- **合理命名**：为截图提供有意义的名称，便于后续分析
- **设置自动清理**：对于长时间运行的测试，启用自动清理功能
- **使用 Allure 集成**：启用 Allure 集成，自动将截图附加到报告
- **安全路径**：避免在截图名称中使用特殊字符，依赖内置的安全路径处理

### 2. 选择器辅助最佳实践

- **使用结构化选择器**：对于复杂的定位，使用 `Selector` 对象而非字符串
- **提供描述**：为选择器提供描述，便于调试和日志记录
- **使用多种策略**：对于不稳定的元素，提供多种定位策略
- **合理设置超时**：根据页面加载速度设置合理的超时时间
- **使用重试机制**：对于不稳定的操作，使用重试机制提高可靠性

### 3. 视觉验证最佳实践

- **选择合适的算法**：对于不同类型的页面，选择合适的比较算法
- **设置合理的阈值**：根据页面特性设置合理的相似度阈值
- **定期更新基准**：当页面有意改变时，及时更新基准图像
- **分析差异图像**：当验证失败时，分析差异图像找出原因
- **验证关键页面**：只验证对视觉要求高的关键页面

### 4. 日志监控最佳实践

- **在生产环境运行**：在生产环境中运行日志监控，及时发现密码泄露
- **配置合适的间隔**：根据日志生成速度设置合适的检查间隔
- **监控应急文件**：定期检查应急文件，及时处理泄露事件
- **与告警系统集成**：将监控与告警系统集成，及时收到泄露通知
- **定期检查规则**：定期检查和更新密码模式规则，适应新的泄露形式

## 依赖

- **playwright**：用于浏览器自动化和截图
- **allure-pytest**：用于测试报告集成
- **opencv-python**：用于图像处理和比较
- **numpy**：用于数值计算
- **tqdm**：用于显示进度（可选）

## 安装

```bash
pip install playwright allure-pytest opencv-python numpy tqdm
```

## 总结

Common 模块是一个功能强大、易于使用的通用工具集合，为自动化测试提供了全面的支持：

- **截图辅助**：提供丰富的截图功能，支持各种场景的截图需求
- **选择器辅助**：智能元素定位，提高测试的可靠性和稳定性
- **视觉验证**：检测视觉回归，确保页面外观符合预期
- **日志监控**：实时检测密码泄露，提高系统安全性

通过使用 Common 模块，您可以：
- 更有效地管理测试截图
- 提高元素定位的成功率
- 及时发现视觉回归问题
- 增强系统的安全性
- 生成更丰富、更专业的测试报告

---

**注意**：使用前请确保已安装所有必要的依赖，并根据实际需求配置相关选项。