"""
selector_helper.py - 增强型选择器辅助模块

提供结构化选择器定义、解析、等待与重试机制。
与 BasePage 配合使用，提供底层定位能力。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, replace
from functools import partial
from typing import (
    Any, Callable, Dict, List, Literal, Optional, Tuple, Union, TypeVar, cast
)

import allure
from playwright.sync_api import Page, Locator, Frame, FrameLocator, TimeoutError as PlaywrightTimeoutError, \
    Error as PlaywrightError
from config import settings
from config.locators_i18n import get_text as i18n_get_text
from logger import logger

# ============================================================================
# 常量
# ============================================================================
DEFAULT_WAIT_TIMEOUT = 5000  # 毫秒
DEFAULT_RETRIES = 3
DEFAULT_INITIAL_DELAY = 0.5  # 秒
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_DELAY = 5.0  # 秒

# 是否启用 Allure 附加报告（可通过环境变量或配置控制）
ENABLE_ALLURE_ATTACH = getattr(settings, "enable_selector_allure", False)

# ============================================================================
# 类型别名
# ============================================================================
AnyContext = Union[Page, Frame, FrameLocator]  # 可应用定位器的上下文对象


# ============================================================================
# 自定义异常
# ============================================================================
class SelectorError(Exception):
    """选择器相关错误的基类"""
    pass


class FrameNotFoundError(SelectorError):
    """Frame 未找到"""
    pass


class SelectorResolutionError(SelectorError):
    """选择器解析失败（所有策略均无效）"""
    pass


class LocatorWaitTimeoutError(SelectorError):
    """等待元素状态超时"""

    def __init__(self, message: str, attempts: List[Dict[str, Any]]):
        super().__init__(message)
        self.attempts = attempts


# ============================================================================
# 解析信息数据类
# ============================================================================
@dataclass(frozen=True)
class ResolveInfo:
    """选择器解析元信息"""
    strategy: str  # 成功的策略名称
    ctx: str  # 上下文描述（如 "page", "frame(name=...)"）
    attempts: List[Dict[str, Any]]  # 所有尝试的策略列表


# ============================================================================
# Selector 数据类 (V5)
# ============================================================================
@dataclass(frozen=True)
class Selector:
    """结构化选择器，支持多种定位方式及国际化"""
    test_id: Optional[str] = None
    role: Optional[Literal[
        "alert",
        "alertdialog",
        "application",
        "article",
        "banner",
        "blockquote",
        "button",
        "caption",
        "cell",
        "checkbox",
        "code",
        "columnheader",
        "combobox",
        "complementary",
        "contentinfo",
        "definition",
        "deletion",
        "dialog",
        "directory",
        "document",
        "emphasis",
        "feed",
        "figure",
        "form",
        "generic",
        "grid",
        "gridcell",
        "group",
        "heading",
        "img",
        "insertion",
        "link",
        "list",
        "listbox",
        "listitem",
        "log",
        "main",
        "marquee",
        "math",
        "menu",
        "menubar",
        "menuitem",
        "menuitemcheckbox",
        "menuitemradio",
        "meter",
        "navigation",
        "none",
        "note",
        "option",
        "paragraph",
        "presentation",
        "progressbar",
        "radio",
        "radiogroup",
        "region",
        "row",
        "rowgroup",
        "rowheader",
        "scrollbar",
        "search",
        "searchbox",
        "separator",
        "slider",
        "spinbutton",
        "status",
        "strong",
        "subscript",
        "superscript",
        "switch",
        "tab",
        "table",
        "tablist",
        "tabpanel",
        "term",
        "textbox",
        "time",
        "timer",
        "toolbar",
        "tooltip",
        "tree",
        "treegrid",
        "treeitem",
    ]] = None
    role_name: Optional[str] = None
    role_name_key: Optional[str] = None
    label: Optional[str] = None
    label_key: Optional[str] = None
    placeholder: Optional[str] = None
    alt: Optional[str] = None  # 新增 alt 文本支持
    title: Optional[str] = None  # 新增 title 属性支持
    css: Optional[str] = None
    xpath: Optional[str] = None
    text: Optional[str] = None
    text_key: Optional[str] = None
    raw_selector: Optional[str] = None
    description: Optional[str] = None
    deprecated: bool = False
    exact: bool = False  # 精确匹配（用于 text、role_name）

    # Frame/iframe 支持
    frame_name: Optional[str] = None
    frame_url_contains: Optional[str] = None
    frame_locator_css: Optional[str] = None

    # Shadow DOM / pierce 支持
    use_pierce: bool = False
    pierce_selector: Optional[str] = None
    shadow_path: Optional[List[str]] = None

    def formatted(self, **kwargs) -> "Selector":
        """替换模板变量，返回新的 Selector 实例"""

        def fmt(s: Optional[str]) -> Optional[str]:
            if not s:
                return s
            # 检查是否包含占位符
            try:
                # 使用 str.format 会抛 KeyError 如果没有对应变量，我们只替换存在的
                # 但如果字符串包含 '{' 但没有有效的占位符，format 会抛 ValueError
                # 为避免误判，直接尝试格式化，如果失败则返回原字符串
                return s.format(**kwargs)
            except (KeyError, ValueError):
                # 没有对应的变量或格式错误，返回原字符串
                return s

        return replace(
            self,
            test_id=fmt(self.test_id),
            role_name=fmt(self.role_name) if self.role_name else None,
            label=fmt(self.label),
            placeholder=fmt(self.placeholder),
            alt=fmt(self.alt),
            title=fmt(self.title),
            css=fmt(self.css),
            xpath=fmt(self.xpath),
            text=fmt(self.text),
            raw_selector=fmt(self.raw_selector),
            frame_locator_css=fmt(self.frame_locator_css),
            pierce_selector=fmt(self.pierce_selector),
            shadow_path=[fmt(p) for p in self.shadow_path] if self.shadow_path else None,
            exact=self.exact
        )


# ============================================================================
# 内部辅助函数
# ============================================================================
def _localize(selector: Selector) -> Selector:
    """国际化处理，替换 key 字段为实际文本"""
    locale = getattr(settings, "locale", "zh")
    updates = {}
    # 映射关系: (key字段名, 目标字段名)
    key_mappings = [
        ("label_key", "label"),
        ("role_name_key", "role_name"),
        ("text_key", "text"),
        # 如果有 alt_key、title_key 可在此扩展
    ]
    for key_attr, target_attr in key_mappings:
        key_val = getattr(selector, key_attr)
        if key_val and not getattr(selector, target_attr):
            localized = i18n_get_text(key_val, locale)
            if localized:
                updates[target_attr] = localized
    return replace(selector, **updates) if updates else selector


def _attach_to_allure(name: str, payload: Any, kind: str = "application/json") -> None:
    """附加信息到 Allure 报告，仅在启用且 Allure 可用时执行"""
    if not ENABLE_ALLURE_ATTACH:
        return
    try:
        if kind == "application/json":
            content = json.dumps(payload, ensure_ascii=False, indent=2)
            allure.attach(content, name=name, attachment_type=allure.attachment_type.JSON)
        else:
            allure.attach(str(payload), name=name, attachment_type=allure.attachment_type.TEXT)
    except Exception:
        logger.debug("Allure attach failed for %s", name, exc_info=True)


def _resolve_context(page: Page, selector: Selector) -> Tuple[AnyContext, str]:
    """
    解析选择器中的 frame 信息，返回 (context, description)
    可能返回 Page, Frame, 或 FrameLocator 对象。
    """
    if selector.frame_name:
        frame = page.frame(name=selector.frame_name)
        if frame:
            return frame, f"frame(name={selector.frame_name})"
        raise FrameNotFoundError(f"Frame with name '{selector.frame_name}' not found")

    if selector.frame_url_contains:
        for f in page.frames:
            if selector.frame_url_contains in (f.url or ""):
                return f, f"frame(url_contains={selector.frame_url_contains})"
        raise FrameNotFoundError(f"No frame with url containing '{selector.frame_url_contains}' found")

    if selector.frame_locator_css:
        try:
            fl = page.frame_locator(selector.frame_locator_css)
            return fl, f"frame_locator(css={selector.frame_locator_css})"
        except PlaywrightError as e:
            raise FrameNotFoundError(f"FrameLocator with css '{selector.frame_locator_css}' failed: {e}") from e

    return page, "page"


def _compose_shadow_or_pierce(selector: Selector) -> Optional[str]:
    """
    组合 Shadow DOM / pierce 选择器字符串。
    优先级: pierce_selector > shadow_path > (use_pierce + css)
    """
    if selector.pierce_selector:
        return f"pierce={selector.pierce_selector}"

    if selector.shadow_path:
        # 将 shadow_path 列表转换为 ' >> ' 连接的形式
        try:
            parts = [part for part in selector.shadow_path if part]
            if selector.css:
                return selector.css + " >> " + " >> ".join(parts)
            return " >> ".join(parts) if parts else None
        except (TypeError, ValueError) as e:
            logger.warning(f"Error composing shadow path: {e}")

    if selector.use_pierce and selector.css:
        return f"pierce={selector.css}"

    return None


def _escape_css_value(value: str) -> str:
    """转义 CSS 属性值，使其安全用于选择器"""
    if not value:
        return "''"
    # 如果值同时包含单引号和双引号，使用双引号并转义双引号
    if '"' in value and "'" in value:
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    # 如果值包含单引号但不含双引号，优先使用双引号
    if "'" in value and '"' not in value:
        return f'"{value}"'
    # 其他情况使用单引号并转义单引号
    escaped = value.replace("'", "\\'")
    return f"'{escaped}'"


def _calculate_backoff_delay(attempt: int, initial: float, factor: float, max_delay: float) -> float:
    """计算退避延迟时间（秒）"""
    delay = initial * (factor ** (attempt - 1))
    return min(delay, max_delay)


def _record_attempts(selector: Union[Selector, str], attempts: List[Tuple[str, Any]], ctx_desc: str) -> None:
    """记录尝试信息（日志 + 可选的 Allure 附件）"""
    info = {
        "selector": asdict(selector) if isinstance(selector, Selector) else str(selector),
        "attempts": [{"strategy": s, "value": v} for s, v in attempts],
        "locale": getattr(settings, "locale", None),
        "context": ctx_desc
    }
    logger.debug("Selector attempts: %s", json.dumps(info, ensure_ascii=False))
    _attach_to_allure("selector_attempts", info)


def _try_strategy(
        ctx: AnyContext,
        strategy_name: str,
        builder: Callable[[], Locator],
        attempts: List[Tuple[str, Any]],
        value_repr: Any = None
) -> Optional[Locator]:
    """
    尝试执行一个定位器构建函数，成功返回 Locator，失败返回 None。
    记录尝试信息到 attempts 列表。
    """
    val = value_repr if value_repr is not None else strategy_name
    attempts.append((strategy_name, val))
    try:
        loc = builder()
        return loc
    except (PlaywrightTimeoutError, PlaywrightError) as e:
        logger.debug(f"{strategy_name} strategy failed: {e}", exc_info=True)
        return None
    # 其他异常（如 TypeError 等）让调用者处理，不在此捕获


# ============================================================================
# SelectorHelper 公共 API
# ============================================================================
SelectorLike = Union[Selector, str, Locator]
T = TypeVar('T', bound=Union[Page, Frame, FrameLocator])


class SelectorHelper:
    """选择器解析与操作辅助类"""

    # ------------------------------------------------------------------------
    # 解析相关（不等待）
    # ------------------------------------------------------------------------
    @staticmethod
    def resolve_with_meta(page: Page, selector: SelectorLike) -> Tuple[Locator, ResolveInfo]:
        """解析选择器，返回 (Locator, ResolveInfo)（不等待）"""
        if isinstance(selector, Locator):
            return selector, ResolveInfo(strategy="locator_object", ctx="page", attempts=[])

        if isinstance(selector, str):
            return SelectorHelper._resolve_string_selector(page, selector)

        if not isinstance(selector, Selector):
            raise SelectorResolutionError(f"Unsupported selector type: {type(selector)}")

        return SelectorHelper._resolve_structured_selector(page, selector)

    @staticmethod
    def resolve_locator(page: Page, selector: SelectorLike) -> Locator:
        """仅返回 Locator（不等待）"""
        loc, _ = SelectorHelper.resolve_with_meta(page, selector)
        return loc

    @staticmethod
    def _resolve_string_selector(page: Page, selector_str: str) -> Tuple[Locator, ResolveInfo]:
        """处理字符串选择器"""
        attempts = [("raw_string", selector_str)]
        try:
            loc = page.locator(selector_str)
            info = ResolveInfo(
                strategy="raw_string",
                ctx="page",
                attempts=[{"strategy": "raw_string", "value": selector_str}]
            )
            _record_attempts(selector_str, attempts, "page")
            return loc, info
        except PlaywrightError as e:
            raise SelectorResolutionError(f"Raw string selector failed: {selector_str}") from e

    @staticmethod
    def _resolve_structured_selector(page: Page, selector: Selector) -> Tuple[Locator, ResolveInfo]:
        """处理结构化选择器"""
        selector = _localize(selector)
        ctx, ctx_desc = _resolve_context(page, selector)
        attempts: List[Tuple[str, Any]] = []

        # 定义策略构建函数（使用 partial 绑定当前 ctx 和 selector 属性，避免闭包陷阱）
        def make_strategy(strategy_name: str, builder: Callable[[AnyContext], Locator]) -> Callable[[], Locator]:
            """将 builder 绑定到当前 ctx 并返回无参函数"""
            return partial(builder, ctx)

        # 策略列表: (策略名称, 是否适用, 构建器, 值表示)
        strategies = []

        # 1. raw_selector
        if selector.raw_selector:
            strategies.append((
                "raw_selector",
                True,
                make_strategy("raw_selector", lambda ctx: ctx.locator(selector.raw_selector)),
                selector.raw_selector
            ))

        # 2. shadow/pierce 组合
        combined = _compose_shadow_or_pierce(selector)
        if combined:
            strategies.append((
                "shadow/pierce",
                True,
                make_strategy("shadow/pierce", lambda ctx: ctx.locator(combined)),
                combined
            ))

        # 3. test_id
        if selector.test_id:
            def build_test_id(ctx):
                if hasattr(ctx, "get_by_test_id"):
                    return ctx.get_by_test_id(selector.test_id)
                escaped = _escape_css_value(selector.test_id)
                return ctx.locator(f"[data-testid={escaped}]")

            strategies.append((
                "test_id",
                True,
                make_strategy("test_id", build_test_id),
                selector.test_id
            ))

        # 4. role
        if selector.role:
            def build_role(ctx):
                if hasattr(ctx, "get_by_role"):
                    if selector.role_name:
                        return ctx.get_by_role(selector.role, name=selector.role_name, exact=selector.exact)
                    return ctx.get_by_role(selector.role)
                # 降级方案
                escaped_role = _escape_css_value(selector.role)
                sel = f"[role={escaped_role}]"
                if selector.role_name:
                    if selector.exact:
                        return ctx.locator(f"{sel} >> text={selector.role_name}")
                    else:
                        return ctx.locator(f"{sel} >> text=*{selector.role_name}*")
                return ctx.locator(sel)

            value_repr = (selector.role, selector.role_name)
            strategies.append((
                "role",
                True,
                make_strategy("role", build_role),
                value_repr
            ))

        # 5. label
        if selector.label:
            def build_label(ctx):
                if hasattr(ctx, "get_by_label"):
                    return ctx.get_by_label(selector.label)
                return ctx.locator(f"text={selector.label}")

            strategies.append((
                "label",
                True,
                make_strategy("label", build_label),
                selector.label
            ))

        # 6. placeholder
        if selector.placeholder:
            def build_placeholder(ctx):
                if hasattr(ctx, "get_by_placeholder"):
                    return ctx.get_by_placeholder(selector.placeholder)
                escaped = _escape_css_value(selector.placeholder)
                return ctx.locator(f"[placeholder={escaped}]")

            strategies.append((
                "placeholder",
                True,
                make_strategy("placeholder", build_placeholder),
                selector.placeholder
            ))

        # 7. alt (新增)
        if selector.alt:
            def build_alt(ctx):
                if hasattr(ctx, "get_by_alt_text"):
                    return ctx.get_by_alt_text(selector.alt)
                escaped = _escape_css_value(selector.alt)
                return ctx.locator(f"[alt={escaped}]")

            strategies.append((
                "alt",
                True,
                make_strategy("alt", build_alt),
                selector.alt
            ))

        # 8. title (新增)
        if selector.title:
            def build_title(ctx):
                if hasattr(ctx, "get_by_title"):
                    return ctx.get_by_title(selector.title)
                escaped = _escape_css_value(selector.title)
                return ctx.locator(f"[title={escaped}]")

            strategies.append((
                "title",
                True,
                make_strategy("title", build_title),
                selector.title
            ))

        # 9. css
        if selector.css:
            strategies.append((
                "css",
                True,
                make_strategy("css", lambda ctx: ctx.locator(selector.css)),
                selector.css
            ))

        # 10. xpath
        if selector.xpath:
            strategies.append((
                "xpath",
                True,
                make_strategy("xpath", lambda ctx: ctx.locator(f"xpath={selector.xpath}")),
                selector.xpath
            ))

        # 11. text
        if selector.text:
            def build_text(ctx):
                if hasattr(ctx, "get_by_text"):
                    return ctx.get_by_text(selector.text, exact=selector.exact)
                if selector.exact:
                    return ctx.locator(f"text={selector.text}")
                else:
                    return ctx.locator(f"text=*{selector.text}*")

            strategies.append((
                "text",
                True,
                make_strategy("text", build_text),
                selector.text
            ))

        # 执行策略
        for strategy_name, applicable, builder, value_repr in strategies:
            if not applicable:
                continue
            loc = _try_strategy(ctx, strategy_name, builder, attempts, value_repr)
            if loc is not None:
                # 映射友好的显示名称
                display_name = strategy_name
                if strategy_name == "test_id" and hasattr(ctx, "get_by_test_id"):
                    display_name = "get_by_test_id"
                elif strategy_name == "role" and hasattr(ctx, "get_by_role"):
                    display_name = "get_by_role+name" if selector.role_name else "get_by_role"
                elif strategy_name == "label" and hasattr(ctx, "get_by_label"):
                    display_name = "get_by_label"
                elif strategy_name == "placeholder" and hasattr(ctx, "get_by_placeholder"):
                    display_name = "get_by_placeholder"
                elif strategy_name == "text" and hasattr(ctx, "get_by_text"):
                    display_name = "get_by_text"
                elif strategy_name == "alt" and hasattr(ctx, "get_by_alt_text"):
                    display_name = "get_by_alt_text"
                elif strategy_name == "title" and hasattr(ctx, "get_by_title"):
                    display_name = "get_by_title"
                # 构建 ResolveInfo
                attempts_dicts = [{"strategy": s, "value": v} for s, v in attempts]
                info = ResolveInfo(strategy=display_name, ctx=ctx_desc, attempts=attempts_dicts)
                _record_attempts(selector, attempts, ctx_desc)
                return loc, info

        # 所有策略失败
        _record_attempts(selector, attempts, ctx_desc)
        raise SelectorResolutionError(f"Unable to resolve locator for selector: {selector.description or selector}")

    # ------------------------------------------------------------------------
    # 查找 + 等待 + 重试
    # ------------------------------------------------------------------------
    @staticmethod
    def find(
            page: Page,
            selector: SelectorLike,
            wait_for: Optional[Literal["attached", "detached", "hidden", "visible"]] = None,
            timeout: Optional[int] = None,
            *,
            retries: int = DEFAULT_RETRIES,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> Locator:
        """
        解析选择器，等待指定状态，支持重试/退避。
        若 wait_for 为 None，则只解析不等待。
        """
        timeout = timeout if timeout is not None else DEFAULT_WAIT_TIMEOUT
        attempts_info: List[Dict[str, Any]] = []
        last_exc = None

        for attempt in range(1, max(1, retries) + 1):
            try:
                loc, meta = SelectorHelper.resolve_with_meta(page, selector)
            except (FrameNotFoundError, SelectorResolutionError) as e:
                # 致命错误，不重试
                _attach_to_allure("find_fatal_error", {"error": str(e), "selector": str(selector)})
                raise

            if not wait_for:
                return loc

            try:
                loc.wait_for(state=wait_for, timeout=timeout)
                attempts_info.append({"attempt": attempt, "success": True, "resolve_meta": asdict(meta)})
                return loc
            except PlaywrightTimeoutError as e:
                last_exc = e
                info = {
                    "attempt": attempt,
                    "wait_for": wait_for,
                    "timeout_ms": timeout,
                    "error": str(e),
                    "resolve_meta": asdict(meta)
                }
                attempts_info.append(info)
                logger.warning("Selector wait attempt %s failed: %s", attempt, str(e))
                if attempt >= retries:
                    break
                delay = _calculate_backoff_delay(attempt, initial_delay, backoff_factor, max_delay)
                time.sleep(delay)
            except Exception as e:
                attempts_info.append({"attempt": attempt, "error": str(e)})
                raise

        # 最终失败，附加报告
        payload = {
            "selector": str(selector),
            "attempts": attempts_info,
            "retries": retries,
            "timeout_ms": timeout,
            "wait_for": wait_for
        }
        _attach_to_allure("find_failed", payload)
        raise LocatorWaitTimeoutError(
            f"Waiting for selector timed out after {retries} attempts: {selector}",
            attempts_info
        )

    # ------------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------------
    @staticmethod
    def exists(
            page: Page,
            selector: SelectorLike,
            *,
            timeout: Optional[int] = None,
            retries: int = 1,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> bool:
        """检查元素是否存在（附加到 DOM）"""
        try:
            SelectorHelper.find(
                page, selector, wait_for="attached", timeout=timeout,
                retries=retries, initial_delay=initial_delay,
                backoff_factor=backoff_factor, max_delay=max_delay
            )
            return True
        except (LocatorWaitTimeoutError, SelectorResolutionError, FrameNotFoundError):
            return False

    @staticmethod
    def click(
            page: Page,
            selector: SelectorLike,
            *,
            wait_for: Optional[Literal["attached", "detached", "hidden", "visible"]] = "visible",
            timeout: Optional[int] = None,
            retries: int = DEFAULT_RETRIES,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> None:
        loc = SelectorHelper.find(
            page, selector, wait_for=wait_for, timeout=timeout,
            retries=retries, initial_delay=initial_delay,
            backoff_factor=backoff_factor, max_delay=max_delay
        )
        loc.click()

    @staticmethod
    def fill(
            page: Page,
            selector: SelectorLike,
            value: str,
            *,
            wait_for: Optional[Literal["attached", "detached", "hidden", "visible"]] = "visible",
            timeout: Optional[int] = None,
            retries: int = DEFAULT_RETRIES,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> None:
        loc = SelectorHelper.find(
            page, selector, wait_for=wait_for, timeout=timeout,
            retries=retries, initial_delay=initial_delay,
            backoff_factor=backoff_factor, max_delay=max_delay
        )
        loc.fill(value)

    @staticmethod
    def get_text(
            page: Page,
            selector: SelectorLike,
            *,
            wait_for: Optional[Literal["attached", "detached", "hidden", "visible"]] = "visible",
            timeout: Optional[int] = None,
            retries: int = DEFAULT_RETRIES,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> Optional[str]:
        loc = SelectorHelper.find(
            page, selector, wait_for=wait_for, timeout=timeout,
            retries=retries, initial_delay=initial_delay,
            backoff_factor=backoff_factor, max_delay=max_delay
        )
        return loc.text_content()

    @staticmethod
    def is_visible(
            page: Page,
            selector: SelectorLike,
            *,
            timeout: Optional[int] = None,
            retries: int = 1,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> bool:
        try:
            SelectorHelper.find(
                page, selector, wait_for="visible", timeout=timeout or 1000,
                retries=retries, initial_delay=initial_delay,
                backoff_factor=backoff_factor, max_delay=max_delay
            )
            return True
        except (LocatorWaitTimeoutError, SelectorResolutionError, FrameNotFoundError):
            return False

    @staticmethod
    def wait_for(
            page: Page,
            selector: SelectorLike,
            wait_for: Literal["attached", "detached", "hidden", "visible"] = "visible",
            *,
            timeout: Optional[int] = None,
            retries: int = DEFAULT_RETRIES,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> Locator:
        return SelectorHelper.find(
            page, selector, wait_for=wait_for, timeout=timeout,
            retries=retries, initial_delay=initial_delay,
            backoff_factor=backoff_factor, max_delay=max_delay
        )
