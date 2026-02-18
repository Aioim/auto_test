"""
ScreenshotHelper - 截图辅助类（优化版）

提供丰富的截图功能，支持页面截图、元素截图、高亮标注、
截图管理、Allure 集成等。
"""
from __future__ import annotations
import json
import base64
import time
import warnings
import re
from typing import Optional, Union, List, Dict, Any, Generator
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging
from contextlib import contextmanager

from playwright.sync_api import Page, Locator, ElementHandle

# Allure 导入容错处理
try:
    import allure

    _ALLURE_AVAILABLE = True
except ImportError:
    _ALLURE_AVAILABLE = False
    allure = None  # type: ignore

from config import settings

logger = logging.getLogger(__name__)


# ==================== 常量定义 ====================

class ScreenshotType(Enum):
    """截图类型枚举"""
    FULL_PAGE = "full_page"  # 完整页面
    VIEWPORT = "viewport"  # 可视区域
    ELEMENT = "element"  # 单个元素
    ELEMENTS = "elements"  # 多个元素（实际截取首个匹配元素，Playwright 限制）
    HIGHLIGHTED = "highlighted"  # 高亮元素
    ANNOTATED = "annotated"  # 带标注（未实现）


class ScreenshotFormat(Enum):
    """截图格式枚举"""
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class ScreenshotQuality(Enum):
    """截图质量枚举"""
    LOW = 50
    MEDIUM = 75
    HIGH = 90
    MAX = 100


# 高亮样式常量
_HIGHLIGHT_BORDER_THICKNESS = 3
_HIGHLIGHT_BORDER_STYLE = "solid"
_HIGHLIGHT_BORDER_COLOR = "red"
_HIGHLIGHT_SHADOW_BLUR = 10
_HIGHLIGHT_CLASS = "__screenshot_helper_highlight__"

# JavaScript 逻辑解耦
_HIGHLIGHT_JS = """
(element, borderStyle, shadowBlur, className) => {
    if (!element || !element.isConnected) return false;
    
    // 保存原始样式
    const originalStyle = element.getAttribute('style') || '';
    element.setAttribute('data-original-style', originalStyle);
    
    // 应用高亮样式
    element.style.border = borderStyle;
    element.style.boxShadow = `0 0 ${shadowBlur}px ${borderStyle.split(' ')[2]}`;
    element.classList.add(className);
    return true;
}
"""

_REMOVE_HIGHLIGHT_JS = """
(className) => {
    const elements = document.querySelectorAll('.' + className);
    let count = 0;
    elements.forEach(element => {
        if (!element.isConnected) return;
        
        // 恢复原始样式
        const originalStyle = element.getAttribute('data-original-style');
        if (originalStyle !== null) {
            element.setAttribute('style', originalStyle);
            element.removeAttribute('data-original-style');
        } else {
            element.style.border = '';
            element.style.boxShadow = '';
        }
        element.classList.remove(className);
        count++;
    });
    return count;
}
"""


# ==================== 元数据模型 ====================

class ScreenshotMetadata:
    """截图元数据"""

    def __init__(
            self,
            name: str,
            filepath: str,
            screenshot_type: ScreenshotType,
            timestamp: float,
            url: str,
            title: str,
            viewport: Dict[str, int],
            size: Optional[int] = None,
            annotations: Optional[List[Dict[str, Any]]] = None
    ):
        self.name = name
        self.filepath = filepath
        self.screenshot_type = screenshot_type
        self.timestamp = timestamp
        self.url = url
        self.title = title
        self.viewport = viewport
        self.size = size
        self.annotations = annotations or []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "filepath": self.filepath,
            "type": self.screenshot_type.value,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "url": self.url,
            "title": self.title,
            "viewport": self.viewport,
            "size_kb": round(self.size / 1024, 2) if self.size else None,
            "annotations": self.annotations
        }

    def __repr__(self) -> str:
        return f"<ScreenshotMetadata {self.name} ({self.screenshot_type.value})>"


# ==================== 核心辅助类 ====================

class ScreenshotHelper:
    """
    截图辅助类（优化版）

    提供丰富的截图功能，包括：
    - 页面截图（完整/可视区域）
    - 元素截图（支持高亮）
    - 截图管理与自动清理
    - Allure 集成（自动容错）
    - 安全路径处理
    """

    # 从配置读取默认值（支持外部化配置）
    DEFAULT_SCREENSHOT_DIR = getattr(settings, "SCREENSHOT_DIR", "screenshots")
    DEFAULT_FORMAT = ScreenshotFormat(getattr(settings, "SCREENSHOT_FORMAT", "png"))
    DEFAULT_QUALITY = getattr(settings, "SCREENSHOT_QUALITY", ScreenshotQuality.HIGH.value)
    DEFAULT_TIMEOUT = getattr(settings, "SCREENSHOT_TIMEOUT", 5000)
    HIGHLIGHT_WAIT_MS = getattr(settings, "HIGHLIGHT_WAIT_MS", 100)

    def __init__(
            self,
            page: Page,
            screenshot_dir: Optional[str] = None,
            auto_cleanup: bool = False,
            max_screenshots: int = 100,
            enable_allure: bool = True
    ):
        """
        初始化 ScreenshotHelper

        Args:
            page: Playwright Page 对象
            screenshot_dir: 截图保存目录（默认从 settings 读取）
            auto_cleanup: 是否自动清理旧截图
            max_screenshots: 最大截图数量（用于自动清理）
            enable_allure: 是否启用 Allure 集成（自动检测环境）
        """
        self.page = page
        self.screenshot_dir = Path(screenshot_dir or self.DEFAULT_SCREENSHOT_DIR).resolve()
        self.auto_cleanup = auto_cleanup
        self.max_screenshots = max_screenshots
        self.enable_allure = enable_allure and _ALLURE_AVAILABLE

        # 确保目录存在（安全创建）
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # 截图历史记录
        self._history: List[ScreenshotMetadata] = []

        logger.debug(f"ScreenshotHelper initialized: {self.screenshot_dir}")

    # ==================== 安全工具方法 ====================

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """
        清洗文件名，防止路径穿越攻击

        替换所有非字母数字字符为下划线，保留扩展名安全字符
        """
        # 保留基础字符集：字母、数字、下划线、连字符、点
        return re.sub(r'[^\w\-_\.]', '_', name).strip('_')

    def _get_safe_filepath(self, name: str, ext: str) -> Path:
        """
        生成安全的文件路径，防止路径穿越

        确保最终路径在 screenshot_dir 目录内
        """
        # 清洗文件名
        safe_name = self._sanitize_filename(name)
        filename = f"{safe_name}.{ext.lstrip('.')}"

        # 构建绝对路径并校验是否在目标目录内
        filepath = (self.screenshot_dir / filename).resolve()

        # 安全校验：防止路径穿越
        try:
            filepath.relative_to(self.screenshot_dir.resolve())
        except ValueError:
            raise ValueError(f"Invalid filename '{name}' - path traversal attempt detected")

        return filepath

    # ==================== 核心截图逻辑（统一入口） ====================

    def _capture_screenshot_bytes(
            self,
            screenshot_type: ScreenshotType,
            selector: Optional[Union[Locator, str, ElementHandle]] = None,
            format: ScreenshotFormat = DEFAULT_FORMAT,
            quality: Optional[int] = None,
            timeout: Optional[int] = None,
            **kwargs
    ) -> bytes:
        """
        统一截图逻辑：返回原始字节数据

        处理所有截图类型分发、高亮上下文、异常安全清理
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        screenshot_options: Dict[str, Any] = {
            "type": format.value,
            "timeout": timeout,
            **kwargs
        }

        # 仅对有损格式设置 quality（PNG 为无损格式，不应设置）
        if format in (ScreenshotFormat.JPEG, ScreenshotFormat.WEBP):
            screenshot_options["quality"] = quality if quality is not None else self.DEFAULT_QUALITY

        try:
            if screenshot_type == ScreenshotType.FULL_PAGE:
                screenshot_options["full_page"] = True
                return self.page.screenshot(**screenshot_options)

            elif screenshot_type == ScreenshotType.VIEWPORT:
                screenshot_options["full_page"] = False
                return self.page.screenshot(**screenshot_options)

            elif screenshot_type in (ScreenshotType.ELEMENT, ScreenshotType.HIGHLIGHTED, ScreenshotType.ELEMENTS):
                if selector is None:
                    raise ValueError("selector is required for element screenshot")

                # 解析选择器
                locator = self._resolve_locator(selector) if not isinstance(selector, ElementHandle) else None
                element = selector if isinstance(selector, ElementHandle) else locator.element_handle(timeout=timeout)

                # 高亮上下文管理（仅 HIGHLIGHTED 类型）
                @contextmanager
                def highlight_ctx():
                    cleanup = False
                    try:
                        if screenshot_type == ScreenshotType.HIGHLIGHTED:
                            self._highlight_element_handle(element, timeout=timeout)
                            cleanup = True
                            # 使用 Playwright 原生等待替代 time.sleep
                            self.page.wait_for_timeout(self.HIGHLIGHT_WAIT_MS)
                        yield
                    finally:
                        if cleanup:
                            self.remove_highlight(timeout=timeout)

                with highlight_ctx():
                    return element.screenshot(**screenshot_options)

            elif screenshot_type == ScreenshotType.ANNOTATED:
                raise NotImplementedError(
                    "Annotation feature is not implemented yet. Use external tools for annotations.")

            else:
                raise ValueError(f"Unsupported screenshot type: {screenshot_type}")

        except Exception as e:
            logger.error(f"Screenshot capture failed (type={screenshot_type.value}): {e}", exc_info=True)
            raise

    # ==================== 公共截图 API ====================

    def take_screenshot(
            self,
            name: Optional[str] = None,
            screenshot_type: ScreenshotType = ScreenshotType.VIEWPORT,
            full_page: Optional[bool] = None,
            selector: Optional[Union[Locator, str, ElementHandle]] = None,
            format: ScreenshotFormat = DEFAULT_FORMAT,
            quality: Optional[int] = None,
            timeout: Optional[int] = None,
            **kwargs
    ) -> ScreenshotMetadata:
        """
        截取屏幕截图（安全增强版）

        安全特性：
        - 自动清洗文件名防止路径穿越
        - 截图失败时自动清理残留文件
        - 高亮操作异常安全清理
        - quality=0 被正确识别为有效值

        Args:
            name: 截图名称（自动清洗特殊字符）
            screenshot_type: 截图类型
            full_page: 已废弃，使用 screenshot_type 代替（带警告）
            selector: 元素选择器
            format: 截图格式
            quality: 截图质量（0-100，仅 JPEG/WEBP 有效）
            timeout: 超时时间（毫秒）
            **kwargs: 传递给 Playwright screenshot 的其他参数

        Returns:
            ScreenshotMetadata: 截图元数据

        Raises:
            ValueError: 参数无效或路径穿越尝试
            NotImplementedError: 未实现的功能（如 ANNOTATED）
            Exception: 截图失败
        """
        # 兼容旧参数（带废弃警告）
        if full_page is not None:
            warnings.warn(
                "The 'full_page' parameter is deprecated. Use 'screenshot_type' instead.",
                DeprecationWarning,
                stacklevel=2
            )
            screenshot_type = ScreenshotType.FULL_PAGE if full_page else ScreenshotType.VIEWPORT

        # 生成安全文件名
        if not name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            name = f"screenshot_{timestamp}"

        ext = format.value
        filepath = self._get_safe_filepath(name, ext)

        try:
            # 执行截图（统一入口）
            data = self._capture_screenshot_bytes(
                screenshot_type=screenshot_type,
                selector=selector,
                format=format,
                quality=quality,
                timeout=timeout,
                path=str(filepath),  # Playwright 需要字符串路径
                **kwargs
            )

            # 创建元数据（使用 Playwright API 获取可靠信息）
            metadata = ScreenshotMetadata(
                name=name,
                filepath=str(filepath),
                screenshot_type=screenshot_type,
                timestamp=time.time(),
                url=self.page.url,
                title=self.page.title(),  # Playwright Page 必有 title() 方法
                viewport={
                    "width": self.page.viewport_size["width"],
                    "height": self.page.viewport_size["height"]
                },
                size=len(data),
                annotations=[] if screenshot_type != ScreenshotType.ANNOTATED else None
            )

            # 记录历史
            self._history.append(metadata)

            # 自动清理旧截图
            if self.auto_cleanup and len(self._history) > self.max_screenshots:
                self._cleanup_old_screenshots()

            # Allure 集成
            if self.enable_allure:
                self._attach_to_allure(filepath, name, metadata)

            logger.info(f"Screenshot saved: {filepath} ({len(data)} bytes)")
            return metadata

        except Exception as e:
            # 清理残留文件（截图失败时）
            if filepath.exists():
                try:
                    filepath.unlink()
                    logger.debug(f"Cleaned up failed screenshot: {filepath}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to clean up failed screenshot {filepath}: {cleanup_err}")
            raise

    def take_element_screenshot(
            self,
            selector: Union[Locator, str, ElementHandle],
            name: Optional[str] = None,
            highlight: bool = False,
            **kwargs
    ) -> ScreenshotMetadata:
        """截取元素截图（支持高亮）"""
        screenshot_type = ScreenshotType.HIGHLIGHTED if highlight else ScreenshotType.ELEMENT
        return self.take_screenshot(
            name=name,
            screenshot_type=screenshot_type,
            selector=selector,
            **kwargs
        )

    def take_full_page_screenshot(
            self,
            name: Optional[str] = None,
            **kwargs
    ) -> ScreenshotMetadata:
        """截取完整页面截图"""
        return self.take_screenshot(
            name=name,
            screenshot_type=ScreenshotType.FULL_PAGE,
            **kwargs
        )

    def take_viewport_screenshot(
            self,
            name: Optional[str] = None,
            **kwargs
    ) -> ScreenshotMetadata:
        """截取可视区域截图"""
        return self.take_screenshot(
            name=name,
            screenshot_type=ScreenshotType.VIEWPORT,
            **kwargs
        )

    # ==================== 高亮功能（安全增强） ====================

    def _highlight_element_handle(
            self,
            element: ElementHandle,
            color: str = _HIGHLIGHT_BORDER_COLOR,
            thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
            style: str = _HIGHLIGHT_BORDER_STYLE,
            timeout: Optional[int] = None  # 保留参数用于其他操作（如 element_handle 获取）
    ) -> bool:
        """
        高亮单个元素句柄（内部方法）

        注意：ElementHandle.is_visible() 不支持 timeout 参数
        """
        try:
            # 安全检查 1：元素是否仍在 DOM 中
            try:
                is_connected = element.evaluate("element => element ? element.isConnected : false")
                if not is_connected:
                    logger.warning("Element is not connected to DOM, skipping highlight")
                    return False
            except Exception as e:
                logger.warning(f"Element handle invalid or disconnected: {e}")
                return False

            # 安全检查 2：元素是否可见（无 timeout 参数）
            # 注意：ElementHandle.is_visible() 可能抛出异常（元素已移除/失效）
            try:
                # ⚠️ 无 timeout 参数！这是与 Locator 的关键区别
                if not element.is_visible():
                    logger.debug("Element not visible, but still applying highlight for debugging purposes")
                    # 仍继续高亮（调试场景可能需要高亮不可见元素）
            except Exception as e:
                # 元素可能在检查期间被移除
                logger.debug(f"Visibility check failed (element may have been detached): {e}")
                # 仍尝试高亮（调试友好）
                pass

            # 应用高亮样式
            border_style = f"{thickness}px {style} {color}"

            result = self.page.evaluate(
                _HIGHLIGHT_JS,
                element,
                border_style,
                _HIGHLIGHT_SHADOW_BLUR,
                _HIGHLIGHT_CLASS
            )
            if result:
                logger.debug(f"Element highlighted with {border_style}")
            return result

        except Exception as e:
            logger.warning(f"Failed to highlight element: {e}")
            return False

    def highlight_element(
            self,
            selector: Union[Locator, str, ElementHandle],
            color: str = _HIGHLIGHT_BORDER_COLOR,
            thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
            style: str = _HIGHLIGHT_BORDER_STYLE,
            timeout: Optional[int] = None
    ) -> bool:
        """
        高亮显示元素

        Returns:
            bool: 是否成功高亮
        """
        timeout = timeout or self.DEFAULT_TIMEOUT

        try:
            if isinstance(selector, ElementHandle):
                return self._highlight_element_handle(selector, color, thickness, style, timeout)

            locator = self._resolve_locator(selector)
            locator.wait_for(state="visible", timeout=timeout)
            element = locator.element_handle(timeout=timeout)
            return self._highlight_element_handle(element, color, thickness, style, timeout)

        except Exception as e:
            logger.warning(f"Failed to highlight element: {e}")
            return False

    def highlight_elements(
            self,
            selector: Union[Locator, str],
            color: str = _HIGHLIGHT_BORDER_COLOR,
            thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
            style: str = _HIGHLIGHT_BORDER_STYLE,
            timeout: Optional[int] = None
    ) -> int:
        """
        高亮所有匹配的元素

        Returns:
            int: 成功高亮的元素数量
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        count = 0

        try:
            locator = self._resolve_locator(selector)
            locator.first.wait_for(state="visible", timeout=timeout)
            total = locator.count()

            for i in range(total):
                try:
                    element = locator.nth(i).element_handle(timeout=1000)
                    if element and self._highlight_element_handle(
                            element, color, thickness, style, timeout=1000
                    ):
                        count += 1
                except Exception as e:
                    logger.debug(f"Failed to highlight element #{i}: {e}")
                    continue

            logger.debug(f"Highlighted {count}/{total} elements")
            return count

        except Exception as e:
            logger.warning(f"Failed to highlight elements: {e}")
            return 0

    def remove_highlight(self, timeout: Optional[int] = None) -> int:
        """
        移除所有高亮

        Returns:
            int: 成功移除高亮的元素数量
        """
        try:
            count = self.page.evaluate(_REMOVE_HIGHLIGHT_JS, _HIGHLIGHT_CLASS)
            logger.debug(f"Removed highlights from {count} elements")
            return count
        except Exception as e:
            logger.warning(f"Failed to remove highlight: {e}")
            return 0

    @contextmanager
    def highlighted_context(
            self,
            selector: Union[Locator, str, ElementHandle],
            color: str = _HIGHLIGHT_BORDER_COLOR,
            thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
            style: str = _HIGHLIGHT_BORDER_STYLE,
            duration: Optional[float] = None
    ) -> Generator[None, None, None]:
        """
        高亮元素的上下文管理器（推荐使用方式）

        Usage:
            with helper.highlighted_context(locator):
                page.click(locator)
        """
        try:
            self.highlight_element(selector, color, thickness, style)
            if duration is not None:
                self.page.wait_for_timeout(int(duration * 1000))
            yield
        finally:
            self.remove_highlight()

    def highlight_and_capture(
            self,
            selector: Union[Locator, str, ElementHandle],
            name: Optional[str] = None,
            color: str = _HIGHLIGHT_BORDER_COLOR,
            thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
            style: str = _HIGHLIGHT_BORDER_STYLE,
            duration: float = 0.3,
            **kwargs
    ) -> ScreenshotMetadata:
        """
        高亮元素并截图（自动清理高亮）

        推荐使用 highlighted_context + take_screenshot 组合替代
        """
        with self.highlighted_context(selector, color, thickness, style, duration):
            return self.take_element_screenshot(
                selector=selector,
                name=name,
                highlight=False,  # 已在上下文中高亮
                **kwargs
            )

    # ==================== 标注功能（明确未实现） ====================

    def annotate_screenshot(
            self,
            name: Optional[str] = None,
            annotations: Optional[List[Dict[str, Any]]] = None,
            **kwargs
    ) -> ScreenshotMetadata:
        """
        截取带标注的截图

        Raises:
            NotImplementedError: 功能尚未实现
        """
        raise NotImplementedError(
            "Annotation feature is not implemented. "
            "Consider using external tools like PIL/Pillow for post-processing annotations."
        )

    # ==================== 截图管理 ====================

    def get_history(self) -> List[ScreenshotMetadata]:
        """获取截图历史（返回副本避免外部修改）"""
        return self._history.copy()

    def get_latest_screenshot(self) -> Optional[ScreenshotMetadata]:
        """获取最新截图"""
        return self._history[-1] if self._history else None

    def clear_history(self) -> None:
        """清除截图历史记录（不删除文件）"""
        self._history.clear()
        logger.debug("Screenshot history cleared (files retained)")

    def cleanup_screenshots(
            self,
            keep_latest: Optional[int] = None,
            older_than: Optional[float] = None,
            pattern: Optional[str] = None
    ) -> int:
        """
        清理截图文件

        支持三种清理策略（互斥）：
        - keep_latest: 保留最新 N 个
        - older_than: 删除早于时间戳的文件
        - pattern: 按文件名模式删除

        Returns:
            int: 成功删除的文件数量
        """
        deleted = 0
        try:
            # 收集所有截图文件
            files: List[Path] = []
            for ext in ("png", "jpg", "jpeg", "webp"):
                files.extend(self.screenshot_dir.glob(f"*.{ext}"))

            # 按修改时间排序
            files.sort(key=lambda f: f.stat().st_mtime)

            # 确定待删除文件
            if keep_latest is not None:
                to_delete = files[:-keep_latest] if len(files) > keep_latest else []
            elif older_than is not None:
                to_delete = [f for f in files if f.stat().st_mtime < older_than]
            elif pattern:
                to_delete = [f for f in files if f.match(pattern)]
            else:
                to_delete = files  # 删除全部

            # 执行删除
            for file in to_delete:
                try:
                    file.unlink()
                    deleted += 1
                    logger.debug(f"Deleted screenshot: {file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {file.name}: {e}")

            # 清理历史记录中已删除的文件
            self._cleanup_history()

            logger.info(f"Cleaned up {deleted} screenshots from {self.screenshot_dir}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup screenshots: {e}", exc_info=True)
            return 0

    def _cleanup_old_screenshots(self) -> None:
        """自动清理旧截图（保留最新 max_screenshots 个）"""
        if len(self._history) <= self.max_screenshots:
            return

        # 确定要删除的旧截图
        to_delete = self._history[:-self.max_screenshots]
        deleted_count = 0

        for metadata in to_delete:
            filepath = Path(metadata.filepath)
            if filepath.exists():
                try:
                    filepath.unlink()
                    deleted_count += 1
                    logger.debug(f"Auto-deleted old screenshot: {filepath.name}")
                except Exception as e:
                    logger.warning(f"Failed to auto-delete {filepath.name}: {e}")

        # 更新历史（保留最新）
        self._history = self._history[-self.max_screenshots:]
        logger.debug(f"Auto-cleaned {deleted_count} old screenshots, {len(self._history)} retained")

    def _cleanup_history(self) -> None:
        """清理历史记录中已不存在的文件"""
        original_count = len(self._history)
        self._history = [m for m in self._history if Path(m.filepath).exists()]
        removed = original_count - len(self._history)
        if removed:
            logger.debug(f"Cleaned {removed} missing files from history")

    def export_history(self, filepath: Union[str, Path]) -> None:
        """导出截图历史到 JSON 文件"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        history_data = [meta.to_dict() for meta in self._history]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(history_data)} screenshot records to {filepath}")

    # ==================== 工具方法 ====================

    def _resolve_locator(self, selector: Union[Locator, str]) -> Locator:
        """解析选择器为 Locator"""
        if isinstance(selector, Locator):
            return selector
        elif isinstance(selector, str):
            return self.page.locator(selector)
        else:
            raise ValueError(f"Unsupported selector type: {type(selector)}")

    def _attach_to_allure(
            self,
            filepath: Path,
            name: str,
            metadata: ScreenshotMetadata
    ) -> None:
        """将截图附加到 Allure 报告（带容错）"""
        if not self.enable_allure or not _ALLURE_AVAILABLE or allure is None:
            if self.enable_allure:
                logger.warning("Allure integration requested but module not available")
            return

        try:
            # 读取截图数据
            with open(filepath, 'rb') as f:
                file_data = f.read()

            # 确定附件类型 - 安全处理 Allure 枚举缺失的类型
            ext = filepath.suffix.lower()
            if ext in ('.jpg', '.jpeg'):
                # 容错：JPG/JPEG 枚举名称因版本而异
                attachment_type = getattr(allure.attachment_type, 'JPG',
                                          getattr(allure.attachment_type, 'JPEG', 'image/jpeg'))
            elif ext == '.png':
                attachment_type = allure.attachment_type.PNG
            elif ext == '.gif':
                attachment_type = allure.attachment_type.GIF
            elif ext == '.webp':
                # Allure 无 WEBP 枚举，直接使用 MIME 类型字符串
                attachment_type = "image/webp"
            elif ext == '.bmp':
                attachment_type = allure.attachment_type.BMP
            elif ext == '.svg':
                attachment_type = allure.attachment_type.SVG
            else:
                # 未知格式回退到 PNG
                attachment_type = allure.attachment_type.PNG

            # 附加截图
            allure.attach(
                file_data,
                name=name,
                attachment_type=attachment_type
            )

            # 附加元数据
            metadata_json = json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2)
            allure.attach(
                metadata_json,
                name=f"{name}_metadata",
                attachment_type=allure.attachment_type.JSON
            )

            logger.debug(f"Attached screenshot to Allure: {name} (type: {attachment_type})")

        except Exception as e:
            logger.warning(f"Failed to attach screenshot to Allure: {e}")

    def save_screenshot_data(
            self,
            data: bytes,
            name: Optional[str] = None,
            format: ScreenshotFormat = DEFAULT_FORMAT
    ) -> ScreenshotMetadata:
        """保存原始截图数据（安全路径处理）"""
        if not name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            name = f"screenshot_{timestamp}"

        ext = format.value
        filepath = self._get_safe_filepath(name, ext)

        try:
            # 保存文件
            filepath.write_bytes(data)

            # 创建元数据
            metadata = ScreenshotMetadata(
                name=name,
                filepath=str(filepath),
                screenshot_type=ScreenshotType.VIEWPORT,
                timestamp=time.time(),
                url=self.page.url,
                title=self.page.title(),
                viewport={
                    "width": self.page.viewport_size["width"],
                    "height": self.page.viewport_size["height"]
                },
                size=len(data)
            )

            self._history.append(metadata)

            # Allure 集成
            if self.enable_allure:
                self._attach_to_allure(filepath, name, metadata)

            logger.info(f"Screenshot data saved: {filepath} ({len(data)} bytes)")
            return metadata

        except Exception as e:
            # 清理失败文件
            if filepath.exists():
                try:
                    filepath.unlink()
                except Exception:
                    pass
            raise

    def get_screenshot_as_base64(
            self,
            screenshot_type: ScreenshotType = ScreenshotType.VIEWPORT,
            selector: Optional[Union[Locator, str, ElementHandle]] = None,
            format: ScreenshotFormat = DEFAULT_FORMAT,
            quality: Optional[int] = None,
            timeout: Optional[int] = None,
            **kwargs
    ) -> str:
        """
        获取 Base64 编码的截图

        注意：大图可能产生巨大 Base64 字符串，谨慎使用
        """
        try:
            data = self._capture_screenshot_bytes(
                screenshot_type=screenshot_type,
                selector=selector,
                format=format,
                quality=quality,
                timeout=timeout,
                **kwargs
            )
            encoded = base64.b64encode(data).decode('utf-8')
            logger.debug(f"Encoded {len(data)} bytes to Base64 (length: {len(encoded)})")
            return encoded
        except Exception as e:
            logger.error(f"Failed to get screenshot as base64: {e}", exc_info=True)
            raise

    # ==================== 静态工具方法 ====================

    @staticmethod
    def ensure_dir(directory: Union[str, Path]) -> Path:
        """确保目录存在（返回 Path 对象）"""
        path = Path(directory).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_screenshot_dir(test_name: Optional[str] = None) -> Path:
        """
        获取截图目录路径（支持测试名子目录）

        安全处理测试名中的特殊字符
        """
        base_dir = Path(getattr(settings, "SCREENSHOT_DIR", "screenshots")).resolve()

        if test_name:
            safe_name = re.sub(r'[^\w\-_\.]', '_', test_name).strip('_')
            return base_dir / safe_name

        return base_dir

    @staticmethod
    def cleanup_directory(
            directory: Union[str, Path],
            pattern: str = "*",
            keep_latest: Optional[int] = None
    ) -> int:
        """
        清理目录中的文件（静态工具方法）

        Returns:
            int: 成功删除的文件数量
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0

        # 收集匹配文件
        files = sorted(
            (f for f in dir_path.glob(pattern) if f.is_file()),
            key=lambda f: f.stat().st_mtime
        )

        # 确定待删除文件
        if keep_latest is not None and len(files) > keep_latest:
            to_delete = files[:-keep_latest]
        else:
            to_delete = files

        # 执行删除
        count = 0
        for file in to_delete:
            try:
                file.unlink()
                count += 1
            except Exception:
                pass

        return count


# ==================== 便捷函数（带使用警告） ====================

def take_screenshot(
        page: Page,
        name: Optional[str] = None,
        full_page: bool = False,
        screenshot_dir: Optional[str] = None,
        **kwargs
) -> str:
    """
    便捷函数：快速截图

    ⚠️ 注意：每次调用会创建新的 ScreenshotHelper 实例，
    不会共享历史记录。生产环境建议复用 ScreenshotHelper 实例。

    Args:
        page: Playwright Page 对象
        name: 截图名称
        full_page: 是否截取完整页面（已废弃）
        screenshot_dir: 截图目录
        **kwargs: 其他参数

    Returns:
        str: 截图文件路径
    """
    helper = ScreenshotHelper(page, screenshot_dir=screenshot_dir)
    metadata = helper.take_screenshot(name=name, full_page=full_page, **kwargs)
    return metadata.filepath


def highlight_and_screenshot(
        page: Page,
        selector: Union[Locator, str],
        name: Optional[str] = None,
        screenshot_dir: Optional[str] = None,
        **kwargs
) -> str:
    """
    便捷函数：高亮元素并截图

    ⚠️ 注意：每次调用会创建新的 ScreenshotHelper 实例。
    推荐在测试类中复用 ScreenshotHelper 实例以获得完整历史记录。

    Args:
        page: Playwright Page 对象
        selector: 元素选择器
        name: 截图名称
        screenshot_dir: 截图目录
        **kwargs: 其他参数

    Returns:
        str: 截图文件路径
    """
    helper = ScreenshotHelper(page, screenshot_dir=screenshot_dir)
    metadata = helper.highlight_and_capture(selector, name=name, **kwargs)
    return metadata.filepath


if __name__=='__main__':
    from playwright.sync_api import sync_playwright
    # from screenshot_helper import ScreenshotHelper

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://baidu.com")

        # 创建辅助类实例
        helper = ScreenshotHelper(page)

        # 截取可视区域
        helper.take_viewport_screenshot(name="homepage")

        # 截取完整页面
        helper.take_full_page_screenshot(name="full_page")

        # 截取特定元素
        helper.take_element_screenshot(
            selector="#main-content",
            name="main_content"
        )

        browser.close()

