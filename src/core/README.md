# Core 模块文档

## 模块概述

Core 模块是一个功能强大的通用工具集合，为自动化测试提供了多种实用功能：

- **网络捕获**：提供网络请求和响应的捕获功能
- **截图辅助**：提供丰富的截图功能，支持页面截图、元素截图等
- **选择器辅助**：提供智能元素定位和操作功能，支持多种定位策略
- **视觉验证**：提供图像比较和视觉回归测试功能
- **Allure 附件**：提供将各种类型的附件添加到 Allure 报告的功能

## 安装依赖

```bash
# 安装基础依赖
pip install playwright allure-pytest opencv-python numpy

# 安装可选依赖
pip install tqdm
```

## 核心功能

### 1. 网络捕获 (`network_capture`)

**功能**：
- **请求捕获**：捕获浏览器的网络请求和响应
- **过滤功能**：支持按 URL、方法、状态码等过滤请求
- **响应分析**：解析和分析 HTTP 响应
- **性能分析**：记录请求时间和响应时间

**使用场景**：
- 调试 API 调用
- 验证网络请求参数
- 分析页面加载性能
- 监控第三方服务调用

### 2. 截图辅助 (`ScreenshotHelper`)

**功能**：
- **多种截图类型**：完整页面、可视区域、单个元素等
- **元素高亮**：支持高亮显示元素
- **截图管理**：自动清理旧截图
- **Allure 集成**：自动将截图附加到 Allure 报告

**主要方法**：
- `take_screenshot()`：截取屏幕截图
- `take_element_screenshot()`：截取元素截图
- `take_full_page_screenshot()`：截取完整页面截图
- `take_viewport_screenshot()`：截取可视区域截图
- `highlight_element()`：高亮显示元素
- `cleanup_screenshots()`：清理截图文件

### 3. 选择器辅助 (`SelectorHelper`)

**功能**：
- **多种定位策略**：CSS、XPath、文本等
- **智能解析**：自动尝试多种定位策略，提高定位成功率
- **重试机制**：支持带退避策略的重试
- **Allure 集成**：自动记录定位尝试和结果

**主要方法**：
- `resolve_locator()`：解析选择器为 Locator 对象
- `find()`：解析并等待元素达到指定状态
- `exists()`：检查元素是否存在
- `click()`：点击元素
- `fill()`：填充输入框
- `get_text()`：获取元素文本
- `is_visible()`：检查元素是否可见
- `wait_for()`：等待元素达到指定状态

### 4. 视觉验证 (`VisualValidator`)

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

### 5. Allure 附件 (`allure_attachment`)

**功能**：
- **多种附件类型**：支持 JSON、文件、图像、文本、XML 等
- **自动集成**：自动将附件添加到 Allure 报告
- **便捷方法**：提供简洁的方法添加各种类型的附件

**主要方法**：
- `attach_json()`：添加 JSON 附件
- `attach_file()`：添加文件附件
- `attach_image()`：添加图像附件
- `attach_jpg()`：添加 JPG 图像附件
- `attach_png()`：添加 PNG 图像附件
- `attach_text()`：添加文本附件
- `attach_xml()`：添加 XML 附件

## 使用示例

### 1. 网络捕获示例

```python
from playwright.sync_api import sync_playwright
from utils.core import network_capture

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    # 开始捕获网络请求
    with network_capture(page) as capture:
        page.goto("https://example.com")
        
        # 获取所有请求
        requests = capture.get_requests()
        print(f"捕获到 {len(requests)} 个请求")
        
        # 过滤请求
        api_requests = capture.get_requests(filter_by={"url": "/api"})
        print(f"API 请求: {len(api_requests)}")
        
        # 获取响应
        for req in api_requests:
            response = capture.get_response(req)
            if response:
                print(f"URL: {req.url}, 状态码: {response.status}")
    
    browser.close()
```

### 2. 截图辅助示例

```python
from playwright.sync_api import sync_playwright
from utils.core import ScreenshotHelper

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
    
    # 高亮元素
    helper.highlight_element(selector="p")
    
    # 清理截图
    helper.cleanup_screenshots(keep_latest=10)
    
    browser.close()
```

### 3. 选择器辅助示例

```python
from playwright.sync_api import sync_playwright
from utils.core import SelectorHelper

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")
    
    # 解析选择器
    locator = SelectorHelper.resolve_locator(page, "h1")
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
    
    # 检查元素是否可见
    visible = SelectorHelper.is_visible(page, "div.result")
    print(f"Result visible: {visible}")
    
    browser.close()
```

### 4. 视觉验证示例

```python
from utils.core import VisualValidator

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

### 5. Allure 附件示例

```python
from utils.core import attach_json, attach_file, attach_image, attach_text
import json

# 添加 JSON 附件
data = {"name": "test", "value": 123}
attach_json(data, name="test_data")

# 添加文件附件
attach_file("path/to/file.txt", name="log_file")

# 添加图像附件
attach_image("path/to/image.png", name="screenshot")

# 添加文本附件
attach_text("Test message", name="test_message")
```

## API 参考

### 1. 网络捕获 (`network_capture`)

#### 用法

```python
with network_capture(page) as capture:
    # 执行操作
    page.goto("https://example.com")
    # 获取请求和响应
    requests = capture.get_requests()
    response = capture.get_response(requests[0])
```

#### 主要方法

- `get_requests(filter_by: Optional[Dict[str, Any]] = None) -> List[Request]`
  - 获取捕获的请求，可选择性过滤

- `get_response(request: Request) -> Optional[Response]`
  - 获取请求对应的响应

- `get_responses(filter_by: Optional[Dict[str, Any]] = None) -> List[Response]`
  - 获取捕获的响应，可选择性过滤

### 2. ScreenshotHelper

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
  - 截取屏幕截图

- `take_element_screenshot(selector, name=None, highlight=False, **kwargs) -> ScreenshotMetadata`
  - 截取元素截图

- `take_full_page_screenshot(name=None, **kwargs) -> ScreenshotMetadata`
  - 截取完整页面截图

- `take_viewport_screenshot(name=None, **kwargs) -> ScreenshotMetadata`
  - 截取可视区域截图

- `highlight_element(selector, color="red", thickness=3, style="solid", timeout=None) -> bool`
  - 高亮显示元素

- `cleanup_screenshots(keep_latest=None, older_than=None, pattern=None) -> int`
  - 清理截图文件

### 3. SelectorHelper

#### 主要方法

- `resolve_locator(page: Page, selector: SelectorLike) -> Locator`
  - 解析选择器为 Locator 对象

- `find(page: Page, selector: SelectorLike, wait_for=None, timeout=None, *, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> Locator`
  - 解析并等待元素达到指定状态

- `exists(page: Page, selector: SelectorLike, *, timeout=None, retries=1, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> bool`
  - 检查元素是否存在

- `click(page: Page, selector: SelectorLike, *, wait_for="visible", timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> None`
  - 点击元素

- `fill(page: Page, selector: SelectorLike, value: str, *, wait_for="visible", timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> None`
  - 填充输入框

- `get_text(page: Page, selector: SelectorLike, *, wait_for="visible", timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> Optional[str]`
  - 获取元素文本

- `is_visible(page: Page, selector: SelectorLike, *, timeout=None, retries=1, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> bool`
  - 检查元素是否可见

- `wait_for(page: Page, selector: SelectorLike, wait_for="visible", *, timeout=None, retries=3, initial_delay=0.5, backoff_factor=2.0, max_delay=5.0) -> Locator`
  - 等待元素达到指定状态

### 4. VisualValidator

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
  - 验证测试图像与基准图像的相似度

- `update_baseline(test_image_name: str, baseline_image_name: Optional[str] = None) -> bool`
  - 将测试图像更新为基准图像

- `validate_directory(threshold: Optional[float] = None) -> Dict[str, Any]`
  - 验证整个目录中的图像

- `get_baseline_images() -> List[str]`
  - 获取所有基准图像

- `get_test_images() -> List[str]`
  - 获取所有测试图像

### 5. Allure 附件

#### 主要方法

- `attach_json(data: Any, name: str, attachment_type: AttachmentType = AttachmentType.JSON) -> None`
  - 添加 JSON 附件

- `attach_file(source: Union[str, Path], name: str, attachment_type: Optional[AttachmentType] = None) -> None`
  - 添加文件附件

- `attach_image(source: Union[str, Path, bytes], name: str, attachment_type: AttachmentType = AttachmentType.PNG) -> None`
  - 添加图像附件

- `attach_jpg(source: Union[str, Path, bytes], name: str) -> None`
  - 添加 JPG 图像附件

- `attach_png(source: Union[str, Path, bytes], name: str) -> None`
  - 添加 PNG 图像附件

- `attach_text(content: str, name: str, attachment_type: AttachmentType = AttachmentType.TEXT) -> None`
  - 添加文本附件

- `attach_xml(content: str, name: str) -> None`
  - 添加 XML 附件

## 最佳实践

### 1. 网络捕获最佳实践

- **使用上下文管理器**：使用 `with network_capture(page) as capture:` 确保资源正确释放
- **合理过滤**：使用过滤功能减少需要处理的请求数量
- **及时分析**：在捕获块内及时分析请求和响应，避免内存占用过高
- **结合断言**：将网络捕获与断言结合，验证 API 响应的正确性

### 2. 截图辅助最佳实践

- **合理命名**：为截图提供有意义的名称，便于后续分析
- **设置自动清理**：对于长时间运行的测试，启用自动清理功能
- **使用 Allure 集成**：启用 Allure 集成，自动将截图附加到报告
- **选择合适的截图类型**：根据需要选择合适的截图类型（完整页面、可视区域、元素）

### 3. 选择器辅助最佳实践

- **使用多种定位策略**：对于不稳定的元素，提供多种定位策略
- **合理设置超时**：根据页面加载速度设置合理的超时时间
- **使用重试机制**：对于不稳定的操作，使用重试机制提高可靠性
- **提供详细的选择器描述**：为选择器提供描述，便于调试和日志记录

### 4. 视觉验证最佳实践

- **选择合适的算法**：对于不同类型的页面，选择合适的比较算法
- **设置合理的阈值**：根据页面特性设置合理的相似度阈值
- **定期更新基准**：当页面有意改变时，及时更新基准图像
- **分析差异图像**：当验证失败时，分析差异图像找出原因
- **验证关键页面**：只验证对视觉要求高的关键页面

### 5. Allure 附件最佳实践

- **添加有意义的名称**：为附件提供有意义的名称，便于在报告中查找
- **选择合适的附件类型**：根据内容类型选择合适的附件类型
- **控制附件大小**：避免添加过大的附件，影响报告加载速度
- **结合测试步骤**：在关键测试步骤添加附件，提高报告的可读性

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

Core 模块是一个功能强大、易于使用的通用工具集合，为自动化测试提供了全面的支持：

- **网络捕获**：捕获和分析网络请求，帮助调试和验证 API 调用
- **截图辅助**：提供丰富的截图功能，支持各种场景的截图需求
- **选择器辅助**：智能元素定位，提高测试的可靠性和稳定性
- **视觉验证**：检测视觉回归，确保页面外观符合预期
- **Allure 附件**：丰富测试报告，提供更多测试上下文信息

通过使用 Core 模块，您可以：
- 更有效地调试和分析网络请求
- 提高元素定位的成功率
- 及时发现视觉回归问题
- 生成更丰富、更专业的测试报告
- 提高测试的可靠性和稳定性

---

**注意**：使用前请确保已安装所有必要的依赖，并根据实际需求配置相关选项。