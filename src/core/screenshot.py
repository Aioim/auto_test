"""
ScreenshotHelper - 截图辅助类（优化版 + 安全增强）

提供丰富的截图功能，支持页面截图、元素截图、高亮标注、
截图管理、Allure 集成等。

安全特性：
- 所有文件名组件均经过清洗，防止路径穿越
- 标签键和值均进行安全过滤
- 支持上下文标签注入，自动生成结构化文件名
"""

from __future__ import annotations
import json
import base64
import time
import warnings
import re
import sys
from typing import Optional, Union, List, Dict, Any, Generator
from datetime import datetime
from pathlib import Path
from enum import Enum
from contextlib import contextmanager
from collections import OrderedDict

from playwright.sync_api import Page, Locator, ElementHandle
import allure
from config import settings
from logger import logger
from core.selector import SelectorHelper, Selector, SelectorLike


# ==================== 常量定义 ====================

class ScreenshotType(Enum):
    FULL_PAGE = "full_page"
    VIEWPORT = "viewport"
    ELEMENT = "element"
    HIGHLIGHTED = "highlighted"
    ANNOTATED = "annotated"


class ScreenshotFormat(Enum):
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class ScreenshotQuality(Enum):
    LOW = 50
    MEDIUM = 75
    HIGH = 90
    MAX = 100


_HIGHLIGHT_BORDER_THICKNESS = 3
_HIGHLIGHT_BORDER_STYLE = "solid"
_HIGHLIGHT_BORDER_COLOR = "red"
_HIGHLIGHT_SHADOW_BLUR = 10
_HIGHLIGHT_CLASS = "__screenshot_helper_highlight__"

_HIGHLIGHT_JS = """
({element, borderStyle, shadowBlur, color, className}) => {
    if (!element || !element.isConnected) return false;
    const originalStyle = element.getAttribute('style') || '';
    element.setAttribute('data-original-style', originalStyle);
    element.style.border = borderStyle;
    element.style.boxShadow = `0 0 ${shadowBlur}px ${color}`;
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
            annotations: Optional[List[Dict[str, Any]]] = None,
            error_context: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.filepath = str(Path(filepath).as_posix())
        self.screenshot_type = screenshot_type
        self.timestamp = timestamp
        self.url = url
        self.title = title
        self.viewport = viewport
        self.size = size
        self.annotations = annotations or []
        self.error_context = error_context or {}

    def to_dict(self) -> Dict[str, Any]:
        result = {
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
        if self.error_context:
            result["error_context"] = self.error_context
        return result

    def __repr__(self) -> str:
        return f"<ScreenshotMetadata {self.name} ({self.screenshot_type.value})>"


# ==================== 核心辅助类 ====================

class ScreenshotHelper:
    DEFAULT_SCREENSHOT_DIR = getattr(settings, "screenshot_dir", "screenshots")
    DEFAULT_FORMAT = ScreenshotFormat(getattr(settings, "screenshot_format", "png"))
    DEFAULT_QUALITY = getattr(settings, "screenshot_quality", ScreenshotQuality.HIGH.value)
    DEFAULT_TIMEOUT = getattr(settings, "screenshot_timeout", 5000)
    HIGHLIGHT_WAIT_MS = getattr(settings, "highlight_wait_ms", 100)
    MAX_LOCATOR_CACHE_SIZE = 128

    def __init__(
            self,
            page: Page,
            screenshot_dir: Path = DEFAULT_SCREENSHOT_DIR,
            auto_cleanup: bool = False,
            max_screenshots: int = 100,
            enable_allure: bool = True,
            context_tags: Optional[Dict[str, str]] = None
    ):
        self.page = page
        self.screenshot_dir = Path(screenshot_dir)
        self.auto_cleanup = auto_cleanup
        self.max_screenshots = max_screenshots
        self.enable_allure = enable_allure
        self.context_tags = context_tags or {}

        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._history: List[ScreenshotMetadata] = []
        self._locator_cache: OrderedDict[str, Locator] = OrderedDict()

        self._check_compatibility()
        logger.debug(f"ScreenshotHelper initialized: {self.screenshot_dir}, tags={self.context_tags}")

    # ==================== 上下文标签管理 ====================

    def set_context_tags(self, tags: Dict[str, str]) -> None:
        """设置或更新全局上下文标签（合并，覆盖同名键）"""
        self.context_tags.update(tags)
        logger.debug(f"Context tags updated: {self.context_tags}")

    def clear_context_tags(self) -> None:
        """清空所有上下文标签"""
        self.context_tags.clear()
        logger.debug("Context tags cleared")

    def _build_filename_with_tags(self, base_name: str, suffix: str = "", add_timestamp: bool = True) -> str:
        """
        根据基础名称和上下文标签构建安全的文件名

        Args:
            base_name: 基础名称（如 "error", "screenshot"）
            suffix: 可选后缀（如 "dialog", "timeout"）
            add_timestamp: 是否添加时间戳（默认 True）

        Returns:
            安全的文件名（不含扩展名）
        """
        parts = [self._sanitize_filename(base_name)]

        # 添加上下文标签（键和值都清洗）
        if self.context_tags:
            for key, value in sorted(self.context_tags.items()):
                safe_key = self._sanitize_filename(key)
                safe_value = self._sanitize_filename(value)
                if safe_key and safe_value:
                    parts.append(f"{safe_key}_{safe_value}")

        if suffix:
            parts.append(self._sanitize_filename(suffix))

        if add_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            parts.append(timestamp)

        # 用下划线连接，整体再清洗一次（防止中间产生非法字符）
        raw_name = "_".join(parts)
        return self._sanitize_filename(raw_name)

    # ==================== 安全工具方法 ====================

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清洗文件名，防止路径穿越攻击。保留字母、数字、下划线、连字符、点。"""
        if not name:
            return "empty"
        return re.sub(r'[^\w\-_\.]', '_', name).strip('_')

    def _get_safe_filepath(self, name: str, ext: str) -> Path:
        safe_name = self._sanitize_filename(name)
        filename = f"{safe_name}.{ext.lstrip('.')}"
        filepath = (self.screenshot_dir / filename).resolve()
        try:
            filepath.relative_to(self.screenshot_dir.resolve())
        except ValueError:
            raise ValueError(f"Invalid filename '{name}' - path traversal attempt detected")
        return filepath

    # ==================== 核心截图逻辑 ====================

    def _capture_screenshot_bytes(
            self,
            screenshot_type: ScreenshotType,
            selector: Optional[Union[Locator, str, ElementHandle, Selector]] = None,
            format: ScreenshotFormat = DEFAULT_FORMAT,
            quality: Optional[int] = None,
            timeout: Optional[int] = None,
            annotations: Optional[List[Dict[str, Any]]] = None,
            **kwargs
    ) -> bytes:
        try:
            screenshot_options = self._prepare_screenshot_options(
                format=format,
                quality=quality,
                timeout=timeout,
                **kwargs
            )

            if screenshot_type == ScreenshotType.FULL_PAGE:
                return self._capture_full_page_screenshot(screenshot_options)
            elif screenshot_type == ScreenshotType.VIEWPORT:
                return self._capture_viewport_screenshot(screenshot_options)
            elif screenshot_type == ScreenshotType.ELEMENT:
                return self._capture_element_screenshot(selector, timeout, screenshot_options)
            elif screenshot_type == ScreenshotType.HIGHLIGHTED:
                return self._capture_highlighted_element_screenshot(selector, timeout, screenshot_options)
            elif screenshot_type == ScreenshotType.ANNOTATED:
                return self._capture_annotated_screenshot(screenshot_options, annotations or [])
            else:
                raise ValueError(f"Unsupported screenshot type: {screenshot_type}")
        except Exception as e:
            logger.error(f"Screenshot capture failed (type={screenshot_type.value}): {e}", exc_info=True)
            raise

    def _prepare_screenshot_options(
            self,
            format: ScreenshotFormat,
            quality: Optional[int],
            timeout: Optional[int],
            **kwargs
    ) -> Dict[str, Any]:
        timeout = timeout or self.DEFAULT_TIMEOUT
        screenshot_options: Dict[str, Any] = {
            "type": format.value,
            "timeout": timeout,
            **kwargs
        }

        if format in (ScreenshotFormat.JPEG, ScreenshotFormat.WEBP):
            if quality is not None:
                if not (0 <= quality <= 100):
                    raise ValueError(f"Quality must be between 0 and 100, got {quality}")
                screenshot_options["quality"] = quality
            else:
                screenshot_options["quality"] = self.DEFAULT_QUALITY
        return screenshot_options

    def _capture_full_page_screenshot(self, options: Dict[str, Any]) -> bytes:
        options["full_page"] = True
        return self.page.screenshot(**options)

    def _capture_viewport_screenshot(self, options: Dict[str, Any]) -> bytes:
        options["full_page"] = False
        return self.page.screenshot(**options)

    def _capture_element_screenshot(
            self,
            selector: Optional[Union[Locator, str, ElementHandle, Selector]],
            timeout: Optional[int],
            options: Dict[str, Any]
    ) -> bytes:
        if selector is None:
            raise ValueError("selector required")
        if isinstance(selector, ElementHandle):
            element = selector
        else:
            locator = self._resolve_locator(selector)
            locator.wait_for(state="visible", timeout=timeout or self.DEFAULT_TIMEOUT)
            element = locator.element_handle(timeout=timeout or self.DEFAULT_TIMEOUT)
        return element.screenshot(**options)

    def _capture_highlighted_element_screenshot(
            self,
            selector: Optional[Union[Locator, str, ElementHandle, Selector]],
            timeout: Optional[int],
            options: Dict[str, Any]
    ) -> bytes:
        if selector is None:
            raise ValueError("selector required")
        if isinstance(selector, ElementHandle):
            element = selector
        else:
            locator = self._resolve_locator(selector)
            locator.wait_for(state="visible", timeout=timeout or self.DEFAULT_TIMEOUT)
            element = locator.element_handle(timeout=timeout or self.DEFAULT_TIMEOUT)

        @contextmanager
        def highlight_ctx():
            try:
                self._highlight_element_handle(element, timeout=timeout)
                self.page.wait_for_timeout(self.HIGHLIGHT_WAIT_MS)
                yield
            finally:
                self.remove_highlight(timeout=timeout)

        with highlight_ctx():
            return element.screenshot(**options)

    def _capture_annotated_screenshot(self, options: Dict[str, Any], annotations: List[Dict[str, Any]]) -> bytes:
        annotation_elements = []
        try:
            for ann in annotations:
                el = self._add_annotation_element(ann)
                if el:
                    annotation_elements.append(el)
            self.page.wait_for_timeout(100)
            options["full_page"] = True
            return self.page.screenshot(**options)
        finally:
            for el in annotation_elements:
                try:
                    el.evaluate("el => el.remove()")
                except Exception:
                    pass

    # 标注辅助方法（实现略，保持与之前相同）
    def _add_annotation_element(self, annotation: Dict[str, Any]) -> Optional[ElementHandle]:
        ann_type = annotation.get('type', 'text')
        if ann_type == 'text':
            return self._add_text_annotation(annotation)
        elif ann_type == 'arrow':
            return self._add_arrow_annotation(annotation)
        elif ann_type == 'rectangle':
            return self._add_rectangle_annotation(annotation)
        else:
            logger.warning(f"Unsupported annotation type: {ann_type}")
            return None

    def _add_text_annotation(self, annotation: Dict[str, Any]) -> Optional[ElementHandle]:
        text = annotation.get('text', '')
        x = annotation.get('x', 10)
        y = annotation.get('y', 10)
        color = annotation.get('color', 'red')
        font_size = annotation.get('font_size', 14)
        try:
            return self.page.evaluate_handle('''
                ({text, x, y, color, font_size}) => {
                    const div = document.createElement('div');
                    div.style.position = 'fixed';
                    div.style.left = `${x}px`;
                    div.style.top = `${y}px`;
                    div.style.color = color;
                    div.style.fontSize = `${font_size}px`;
                    div.style.fontWeight = 'bold';
                    div.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                    div.style.padding = '4px 8px';
                    div.style.borderRadius = '4px';
                    div.style.zIndex = '999999';
                    div.style.pointerEvents = 'none';
                    div.textContent = text;
                    document.body.appendChild(div);
                    return div;
                }
            ''', {'text': text, 'x': x, 'y': y, 'color': color, 'font_size': font_size})
        except Exception as e:
            logger.warning(f"Failed to add text annotation: {e}")
            return None

    def _add_arrow_annotation(self, annotation: Dict[str, Any]) -> Optional[ElementHandle]:
        x1 = annotation.get('x1', 10)
        y1 = annotation.get('y1', 10)
        x2 = annotation.get('x2', 100)
        y2 = annotation.get('y2', 100)
        color = annotation.get('color', 'red')
        thickness = annotation.get('thickness', 2)
        try:
            return self.page.evaluate_handle('''
                ({x1, y1, x2, y2, color, thickness}) => {
                    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                    svg.style.position = 'fixed';
                    svg.style.left = '0';
                    svg.style.top = '0';
                    svg.style.width = '100vw';
                    svg.style.height = '100vh';
                    svg.style.pointerEvents = 'none';
                    svg.style.zIndex = '999999';
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', x1);
                    line.setAttribute('y1', y1);
                    line.setAttribute('x2', x2);
                    line.setAttribute('y2', y2);
                    line.setAttribute('stroke', color);
                    line.setAttribute('stroke-width', thickness);
                    svg.appendChild(line);
                    document.body.appendChild(svg);
                    return svg;
                }
            ''', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'color': color, 'thickness': thickness})
        except Exception as e:
            logger.warning(f"Failed to add arrow annotation: {e}")
            return None

    def _add_rectangle_annotation(self, annotation: Dict[str, Any]) -> Optional[ElementHandle]:
        x = annotation.get('x', 10)
        y = annotation.get('y', 10)
        width = annotation.get('width', 100)
        height = annotation.get('height', 100)
        color = annotation.get('color', 'red')
        thickness = annotation.get('thickness', 2)
        opacity = annotation.get('opacity', 0.3)
        try:
            return self.page.evaluate_handle('''
                ({x, y, width, height, color, thickness, opacity}) => {
                    const div = document.createElement('div');
                    div.style.position = 'fixed';
                    div.style.left = `${x}px`;
                    div.style.top = `${y}px`;
                    div.style.width = `${width}px`;
                    div.style.height = `${height}px`;
                    div.style.border = `${thickness}px solid ${color}`;
                    div.style.backgroundColor = `${color}${Math.round(opacity * 255).toString(16).padStart(2, '0')}`;
                    div.style.pointerEvents = 'none';
                    div.style.zIndex = '999999';
                    document.body.appendChild(div);
                    return div;
                }
            ''', {'x': x, 'y': y, 'width': width, 'height': height, 'color': color, 'thickness': thickness, 'opacity': opacity})
        except Exception as e:
            logger.warning(f"Failed to add rectangle annotation: {e}")
            return None

    # ==================== 公共截图 API ====================

    def take_screenshot(
            self,
            name: Optional[str] = None,
            screenshot_type: ScreenshotType = ScreenshotType.VIEWPORT,
            full_page: Optional[bool] = None,
            selector: Optional[Union[Locator, str, ElementHandle, Selector]] = None,
            format: ScreenshotFormat = DEFAULT_FORMAT,
            quality: Optional[int] = None,
            timeout: Optional[int] = None,
            annotations: Optional[List[Dict[str, Any]]] = None,
            error_context: Optional[Dict[str, Any]] = None,
            add_timestamp: bool = True,
            **kwargs
    ) -> ScreenshotMetadata:
        if full_page is not None:
            warnings.warn("'full_page' is deprecated, use screenshot_type", DeprecationWarning, stacklevel=2)
            screenshot_type = ScreenshotType.FULL_PAGE if full_page else ScreenshotType.VIEWPORT

        # 生成最终文件名
        if name is None:
            # 自动生成：基础名 + 上下文标签 + 后缀 + 时间戳
            base_name = screenshot_type.value
            if error_context and error_context.get("error_type"):
                # P0 修复：对 error_type 进行清洗
                raw_error_type = error_context["error_type"]
                safe_error_type = self._sanitize_filename(raw_error_type)
                base_name = f"error_{safe_error_type}"
            name = self._build_filename_with_tags(base_name, suffix="", add_timestamp=add_timestamp)
        else:
            # 用户指定名称，根据 add_timestamp 决定是否追加时间戳
            safe_name = self._sanitize_filename(name)
            if add_timestamp:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                name = f"{safe_name}_{timestamp}"
            else:
                name = safe_name

        ext = format.value
        filepath = self._get_safe_filepath(name, ext)

        try:
            data = self._capture_screenshot_bytes(
                screenshot_type=screenshot_type,
                selector=selector,
                format=format,
                quality=quality,
                timeout=timeout,
                annotations=annotations,
                **kwargs
            )
            filepath.write_bytes(data)

            metadata = ScreenshotMetadata(
                name=name,
                filepath=str(filepath),
                screenshot_type=screenshot_type,
                timestamp=time.time(),
                url=self.page.url,
                title=self.page.title(),
                viewport={
                    "width": self.page.viewport_size["width"],
                    "height": self.page.viewport_size["height"]
                },
                size=len(data),
                annotations=annotations if screenshot_type == ScreenshotType.ANNOTATED else [],
                error_context=error_context
            )

            self._process_screenshot_post_capture(metadata)
            logger.info(f"Screenshot saved: {filepath} ({len(data)} bytes)")
            return metadata

        except Exception as e:
            if filepath.exists():
                try:
                    filepath.unlink()
                except Exception:
                    pass
            raise

    def take_error_screenshot(
            self,
            error_type: str,
            func_name: str,
            error_message: Optional[str] = None,
            screenshot_type: ScreenshotType = ScreenshotType.FULL_PAGE,
            selector: Optional[Union[Locator, str, ElementHandle, Selector]] = None,
            additional_tags: Optional[Dict[str, str]] = None,
            add_timestamp: bool = True,
            **kwargs
    ) -> ScreenshotMetadata:
        """
        专门用于错误场景的截图（不可变标签设计，不修改实例的 context_tags）
        """
        # 构建临时标签（不修改 self.context_tags）
        tags = {
            "error_type": self._sanitize_filename(error_type),
            "func": self._sanitize_filename(func_name)
        }
        if additional_tags:
            for k, v in additional_tags.items():
                tags[self._sanitize_filename(k)] = self._sanitize_filename(v)

        # 临时保存原有标签
        original_tags = self.context_tags.copy()
        try:
            # 临时合并标签（仅用于本次文件名生成）
            self.context_tags.update(tags)
            error_context = {
                "error_type": error_type,
                "function": func_name,
                "message": error_message,
                "timestamp": time.time()
            }
            return self.take_screenshot(
                name=None,
                screenshot_type=screenshot_type,
                selector=selector,
                error_context=error_context,
                add_timestamp=add_timestamp,
                **kwargs
            )
        finally:
            # 恢复原有标签
            self.context_tags.clear()
            self.context_tags.update(original_tags)

    # 其他公共方法（保持兼容）
    def take_element_screenshot(
            self,
            selector: Union[Locator, str, ElementHandle, Selector],
            name: Optional[str] = None,
            highlight: bool = False,
            **kwargs
    ) -> ScreenshotMetadata:
        screenshot_type = ScreenshotType.HIGHLIGHTED if highlight else ScreenshotType.ELEMENT
        return self.take_screenshot(name=name, screenshot_type=screenshot_type, selector=selector, **kwargs)

    def take_full_page_screenshot(self, name: Optional[str] = None, **kwargs) -> ScreenshotMetadata:
        return self.take_screenshot(name=name, screenshot_type=ScreenshotType.FULL_PAGE, **kwargs)

    def take_viewport_screenshot(self, name: Optional[str] = None, **kwargs) -> ScreenshotMetadata:
        return self.take_screenshot(name=name, screenshot_type=ScreenshotType.VIEWPORT, **kwargs)

    def annotate_screenshot(self, name: Optional[str] = None,
                            annotations: Optional[List[Dict[str, Any]]] = None,
                            **kwargs) -> ScreenshotMetadata:
        return self.take_screenshot(name=name, screenshot_type=ScreenshotType.ANNOTATED, annotations=annotations or [], **kwargs)

    # ==================== 高亮功能 ====================

    def _highlight_element_handle(self, element: ElementHandle, color: str = _HIGHLIGHT_BORDER_COLOR,
                                  thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
                                  style: str = _HIGHLIGHT_BORDER_STYLE,
                                  timeout: Optional[int] = None) -> bool:
        try:
            if not self._is_element_valid(element):
                return False
            border_style = f"{thickness}px {style} {color}"
            result = self.page.evaluate(
                _HIGHLIGHT_JS,
                {
                    "element": element,
                    "borderStyle": border_style,
                    "shadowBlur": _HIGHLIGHT_SHADOW_BLUR,
                    "color": color,
                    "className": _HIGHLIGHT_CLASS
                }
            )
            if result:
                logger.debug(f"Element highlighted with {border_style}")
            return result
        except Exception as e:
            logger.warning(f"Failed to highlight element: {e}")
            return False

    def _is_element_valid(self, element: ElementHandle) -> bool:
        try:
            is_connected = element.evaluate("el => el ? el.isConnected : false")
            if not is_connected:
                logger.warning("Element not connected to DOM")
                return False
        except Exception as e:
            logger.warning(f"Element handle invalid: {e}")
            return False
        try:
            if not element.is_visible():
                logger.debug("Element not visible, but applying highlight anyway")
        except Exception:
            pass
        return True

    def highlight_element(self, selector: Union[Locator, str, ElementHandle, Selector],
                          color: str = _HIGHLIGHT_BORDER_COLOR,
                          thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
                          style: str = _HIGHLIGHT_BORDER_STYLE,
                          timeout: Optional[int] = None) -> bool:
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

    def highlight_elements(self, selector: Union[Locator, str, Selector],
                           color: str = _HIGHLIGHT_BORDER_COLOR,
                           thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
                           style: str = _HIGHLIGHT_BORDER_STYLE,
                           timeout: Optional[int] = None) -> int:
        timeout = timeout or self.DEFAULT_TIMEOUT
        count = 0
        try:
            locator = self._resolve_locator(selector)
            locator.first.wait_for(state="visible", timeout=timeout)
            total = locator.count()
            for i in range(total):
                try:
                    element = locator.nth(i).element_handle(timeout=1000)
                    if element and self._highlight_element_handle(element, color, thickness, style, timeout=1000):
                        count += 1
                except Exception:
                    continue
            logger.debug(f"Highlighted {count}/{total} elements")
            return count
        except Exception as e:
            logger.warning(f"Failed to highlight elements: {e}")
            return 0

    def remove_highlight(self, timeout: Optional[int] = None) -> int:
        try:
            count = self.page.evaluate(_REMOVE_HIGHLIGHT_JS, _HIGHLIGHT_CLASS)
            logger.debug(f"Removed highlights from {count} elements")
            return count
        except Exception as e:
            logger.warning(f"Failed to remove highlight: {e}")
            return 0

    @contextmanager
    def highlighted_context(self, selector: Union[Locator, str, ElementHandle, Selector],
                            color: str = _HIGHLIGHT_BORDER_COLOR,
                            thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
                            style: str = _HIGHLIGHT_BORDER_STYLE,
                            duration: Optional[float] = None):
        if duration is not None:
            warnings.warn("duration is deprecated, use time.sleep() inside context", DeprecationWarning, stacklevel=2)
        try:
            self.highlight_element(selector, color, thickness, style)
            yield
        finally:
            self.remove_highlight()

    def highlight_and_capture(self, selector: Union[Locator, str, ElementHandle, Selector],
                              name: Optional[str] = None,
                              color: str = _HIGHLIGHT_BORDER_COLOR,
                              thickness: int = _HIGHLIGHT_BORDER_THICKNESS,
                              style: str = _HIGHLIGHT_BORDER_STYLE,
                              duration: float = 0.3,
                              **kwargs) -> ScreenshotMetadata:
        with self.highlighted_context(selector, color, thickness, style):
            if duration:
                self.page.wait_for_timeout(int(duration * 1000))
            return self.take_element_screenshot(selector=selector, name=name, highlight=False, **kwargs)

    # ==================== 截图管理 ====================

    def get_history(self) -> List[ScreenshotMetadata]:
        return self._history.copy()

    def get_latest_screenshot(self) -> Optional[ScreenshotMetadata]:
        return self._history[-1] if self._history else None

    def clear_history(self) -> None:
        self._history.clear()
        logger.debug("Screenshot history cleared")

    def cleanup_screenshots(self, keep_latest: Optional[int] = None,
                            older_than: Optional[float] = None,
                            pattern: Optional[str] = None) -> int:
        deleted = 0
        try:
            files: List[Path] = []
            for ext in ("png", "jpg", "jpeg", "webp"):
                files.extend(self.screenshot_dir.glob(f"*.{ext}"))
            files.sort(key=lambda f: f.stat().st_mtime)
            if keep_latest is not None:
                to_delete = files[:-keep_latest] if len(files) > keep_latest else []
            elif older_than is not None:
                to_delete = [f for f in files if f.stat().st_mtime < older_than]
            elif pattern:
                to_delete = [f for f in files if f.match(pattern)]
            else:
                to_delete = files
            for file in to_delete:
                try:
                    file.unlink()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {file.name}: {e}")
            self._cleanup_history()
            logger.info(f"Cleaned up {deleted} screenshots")
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup screenshots: {e}")
            return 0

    def _cleanup_old_screenshots(self) -> None:
        if len(self._history) <= self.max_screenshots:
            return
        to_delete = self._history[:-self.max_screenshots]
        for metadata in to_delete:
            filepath = Path(metadata.filepath)
            if filepath.exists():
                try:
                    filepath.unlink()
                except Exception:
                    pass
        self._history = self._history[-self.max_screenshots:]

    def _cleanup_history(self) -> None:
        original = len(self._history)
        self._history = [m for m in self._history if Path(m.filepath).exists()]
        if original - len(self._history):
            logger.debug(f"Cleaned {original - len(self._history)} missing files from history")

    def export_history(self, filepath: Union[str, Path]) -> None:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        data = [m.to_dict() for m in self._history]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported {len(data)} records to {filepath}")

    # ==================== 工具方法 ====================

    def _resolve_locator(self, selector: Union[Locator, str, Selector]) -> Locator:
        if isinstance(selector, Locator):
            return selector
        if isinstance(selector, Selector):
            return SelectorHelper.resolve_locator(self.page, selector)
        if isinstance(selector, str):
            if selector in self._locator_cache:
                return self._locator_cache[selector]
            locator = self.page.locator(selector)
            if len(self._locator_cache) >= self.MAX_LOCATOR_CACHE_SIZE:
                self._locator_cache.popitem(last=False)
            self._locator_cache[selector] = locator
            return locator
        raise ValueError(f"Unsupported selector type: {type(selector)}")

    def clear_locator_cache(self) -> None:
        """清除定位器缓存（页面导航后建议调用）"""
        self._locator_cache.clear()
        logger.debug("Locator cache cleared")

    def _attach_to_allure(self, filepath: Path, name: str, metadata: ScreenshotMetadata) -> None:
        if not self.enable_allure:
            return
        try:
            if not filepath.exists():
                return
            with open(filepath, 'rb') as f:
                data = f.read()
            ext = filepath.suffix.lower()
            try:
                if ext in ('.jpg', '.jpeg'):
                    attachment_type = getattr(allure.attachment_type, 'JPG', getattr(allure.attachment_type, 'JPEG', 'image/jpeg'))
                elif ext == '.png':
                    attachment_type = allure.attachment_type.PNG
                elif ext == '.gif':
                    attachment_type = allure.attachment_type.GIF
                elif ext == '.webp':
                    attachment_type = "image/webp"
                elif ext == '.bmp':
                    attachment_type = allure.attachment_type.BMP
                elif ext == '.svg':
                    attachment_type = allure.attachment_type.SVG
                else:
                    attachment_type = allure.attachment_type.PNG
            except Exception:
                attachment_type = 'image/png'
            allure.attach(data, name=name, attachment_type=attachment_type)
            allure.attach(json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
                          name=f"{name}_metadata", attachment_type=allure.attachment_type.JSON)
        except Exception as e:
            logger.warning(f"Failed to attach to Allure: {e}")

    def save_screenshot_data(self, data: bytes, name: Optional[str] = None,
                             format: ScreenshotFormat = DEFAULT_FORMAT,
                             add_timestamp: bool = True) -> ScreenshotMetadata:
        if not name:
            name = self._build_filename_with_tags("screenshot", add_timestamp=add_timestamp)
        ext = format.value
        filepath = self._get_safe_filepath(name, ext)
        try:
            filepath.write_bytes(data)
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
            if self.enable_allure:
                self._attach_to_allure(filepath, name, metadata)
            logger.info(f"Screenshot data saved: {filepath}")
            return metadata
        except Exception as e:
            if filepath.exists():
                try:
                    filepath.unlink()
                except Exception:
                    pass
            raise

    def get_screenshot_as_base64(self, screenshot_type: ScreenshotType = ScreenshotType.VIEWPORT,
                                 selector: Optional[Union[Locator, str, ElementHandle, Selector]] = None,
                                 format: ScreenshotFormat = DEFAULT_FORMAT,
                                 quality: Optional[int] = None,
                                 timeout: Optional[int] = None,
                                 **kwargs) -> str:
        data = self._capture_screenshot_bytes(
            screenshot_type=screenshot_type,
            selector=selector,
            format=format,
            quality=quality,
            timeout=timeout,
            **kwargs
        )
        return base64.b64encode(data).decode('utf-8')

    # 静态方法
    @staticmethod
    def ensure_dir(directory: Union[str, Path]) -> Path:
        path = Path(directory).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_screenshot_dir(test_name: Optional[str] = None) -> Path:
        base = getattr(settings, "screenshot_dir", None)
        if base is None:
            base = getattr(settings, "SCREENSHOT_DIR", "output/screenshots")
        base_dir = Path(base).resolve()
        if test_name:
            safe_name = re.sub(r'[^\w\-_\.]', '_', test_name).strip('_')
            return base_dir / safe_name
        return base_dir

    @staticmethod
    def cleanup_directory(directory: Union[str, Path], pattern: str = "*", keep_latest: Optional[int] = None) -> int:
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0
        files = sorted((f for f in dir_path.glob(pattern) if f.is_file()), key=lambda f: f.stat().st_mtime)
        if keep_latest is not None and len(files) > keep_latest:
            to_delete = files[:-keep_latest]
        else:
            to_delete = files
        count = 0
        for f in to_delete:
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        return count

    def _process_screenshot_post_capture(self, metadata: ScreenshotMetadata) -> None:
        self._history.append(metadata)
        if self.auto_cleanup and len(self._history) > self.max_screenshots:
            self._cleanup_old_screenshots()
        if self.enable_allure:
            self._attach_to_allure(Path(metadata.filepath), metadata.name, metadata)

    def _check_compatibility(self) -> None:
        try:
            import playwright
            logger.debug(f"Playwright version: {getattr(playwright, '__version__', 'unknown')}")
            if not hasattr(self.page, 'screenshot'):
                logger.warning("Page.screenshot() not available")
            if not hasattr(self.page, 'evaluate'):
                logger.warning("Page.evaluate() not available")
        except Exception as e:
            logger.warning(f"Compatibility check failed: {e}")


# ==================== 便捷函数 ====================

def take_screenshot(page: Page, name: Optional[str] = None, full_page: bool = False,
                    screenshot_dir: Optional[str] = None, **kwargs) -> str:
    helper = ScreenshotHelper(page, screenshot_dir=screenshot_dir)
    metadata = helper.take_screenshot(name=name, full_page=full_page, **kwargs)
    return metadata.filepath


def highlight_and_screenshot(page: Page, selector: Union[Locator, str], name: Optional[str] = None,
                             screenshot_dir: Optional[str] = None, **kwargs) -> str:
    helper = ScreenshotHelper(page, screenshot_dir=screenshot_dir)
    metadata = helper.highlight_and_capture(selector, name=name, **kwargs)
    return metadata.filepath


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.baidu.com")

        helper = ScreenshotHelper(page, context_tags={"test_suite": "smoke"})
        helper.take_viewport_screenshot(name="homepage")
        helper.take_full_page_screenshot(name="full_page")
        helper.take_error_screenshot(error_type="AssertionError", func_name="test_login", error_message="Login failed")
        browser.close()