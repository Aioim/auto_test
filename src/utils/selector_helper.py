from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import Optional, Any, List, Tuple, Dict, Union
import logging
import json
import time
import allure

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from config import settings
from config.locators_i18n import get_text as i18n_get_text

logger = logging.getLogger(__name__)

DEFAULT_WAIT_TIMEOUT = 5000  # milliseconds
DEFAULT_RETRIES = 3
DEFAULT_INITIAL_DELAY = 0.5  # seconds
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_DELAY = 5.0


# ---- Exceptions ----
class SelectorError(Exception):
    """Base selector-related error."""
    pass


class FrameNotFoundError(SelectorError):
    """Raised when an indicated iframe/frame cannot be found."""
    pass


class SelectorResolutionError(SelectorError):
    """Raised when no locator strategy resolves to a locator."""
    pass


class LocatorWaitTimeoutError(SelectorError):
    """Raised when waiting for a locator state times out after retries/backoff."""

    def __init__(self, message: str, attempts: List[Dict[str, Any]]):
        super().__init__(message)
        self.attempts = attempts


# ---- ResolveInfo ----
@dataclass(frozen=True)
class ResolveInfo:
    """
    Metadata returned alongside a Locator describing how it was resolved.
    - strategy: the winning strategy name (e.g. "css", "raw_selector", "get_by_role+name")
    - ctx: context description (e.g. "page", "frame(name=editor)", "frame_locator(css=iframe#x)")
    - attempts: list of attempts (strategy/value) executed during resolution
    """
    strategy: str
    ctx: str
    attempts: List[Dict[str, Any]]


# ---- Selector dataclass (V5) ----
@dataclass(frozen=True)
class Selector:
    # structured locator options
    test_id: Optional[str] = None
    role: Optional[str] = None
    role_name: Optional[str] = None
    role_name_key: Optional[str] = None
    label: Optional[str] = None
    label_key: Optional[str] = None
    placeholder: Optional[str] = None
    css: Optional[str] = None
    xpath: Optional[str] = None
    text: Optional[str] = None
    text_key: Optional[str] = None

    # raw selector string to be passed directly to ctx.locator(...)
    raw_selector: Optional[str] = None

    description: Optional[str] = None
    deprecated: bool = False

    # iframe/frame support
    frame_name: Optional[str] = None
    frame_url_contains: Optional[str] = None
    frame_locator_css: Optional[str] = None

    # shadow/pierce support
    use_pierce: bool = False
    pierce_selector: Optional[str] = None
    shadow_path: Optional[List[str]] = None

    def formatted(self, **kwargs) -> "Selector":
        """
        Replace templated placeholders in string fields and return a new Selector.
        """

        def fmt(s: Optional[str]) -> Optional[str]:
            if not s or "{" not in s:
                return s
            try:
                return s.format(**kwargs)
            except (KeyError, ValueError) as e:
                logger.warning(f"Selector formatting failed for '{s}': {e}")
                return s  # 降级返回原字符串

        return Selector(
            test_id=fmt(self.test_id),
            role=self.role,
            role_name=fmt(self.role_name) if self.role_name else None,
            role_name_key=self.role_name_key,
            label=fmt(self.label),
            label_key=self.label_key,
            placeholder=fmt(self.placeholder),
            css=fmt(self.css),
            xpath=fmt(self.xpath),
            text=fmt(self.text),
            text_key=self.text_key,
            raw_selector=fmt(self.raw_selector),
            description=self.description,
            deprecated=self.deprecated,
            frame_name=self.frame_name,
            frame_url_contains=self.frame_url_contains,
            frame_locator_css=fmt(self.frame_locator_css),
            use_pierce=self.use_pierce,
            pierce_selector=fmt(self.pierce_selector),
            shadow_path=[fmt(p) for p in self.shadow_path if p] if self.shadow_path else None
        )


# ---- Internal helpers ----
def _localize(selector: Selector) -> Selector:
    """
    Replace key fields with localized text based on settings.locale.

    使用 __dict__ 解包方式重构，避免手动列出所有字段导致遗漏风险。
    """
    locale = getattr(settings, "locale", "zh")

    # 仅当需要本地化时才构建更新字段
    update_fields = {}

    # label 本地化
    if selector.label_key and not selector.label:
        localized = i18n_get_text(selector.label_key, locale)
        if localized:
            update_fields["label"] = localized

    # role_name 本地化
    if selector.role_name_key and not selector.role_name:
        localized = i18n_get_text(selector.role_name_key, locale)
        if localized:
            update_fields["role_name"] = localized

    # text 本地化
    if selector.text_key and not selector.text:
        localized = i18n_get_text(selector.text_key, locale)
        if localized:
            update_fields["text"] = localized

    # 仅当有字段需要更新时才创建新实例
    if update_fields:
        return Selector(**{**selector.__dict__, **update_fields})

    return selector


def _attach_to_allure(name: str, payload: Any, kind: str = "application/json"):
    """Attach structured info to Allure; defensive about failures."""
    try:
        if kind == "application/json":
            content = json.dumps(payload, ensure_ascii=False, indent=2)
            allure.attach(content, name=name, attachment_type=allure.attachment_type.JSON)
        else:
            allure.attach(str(payload), name=name, attachment_type=allure.attachment_type.TEXT)
    except Exception:
        logger.debug("Allure attach failed for %s", name, exc_info=True)


def _resolve_context(page: Page, selector: Selector) -> Tuple[Any, str]:
    """
    Return context (Page | Frame | FrameLocator) and description.
    Raises FrameNotFoundError if requested frame cannot be found.
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
        except Exception as e:
            raise FrameNotFoundError(f"FrameLocator with css '{selector.frame_locator_css}' failed: {e}")

    return page, "page"


def _compose_shadow_or_pierce(selector: Selector) -> Optional[str]:
    """
    Compose a locator string for shadow/pierce usage when requested.
    Returns a string suitable for ctx.locator(...).
    """
    if selector.pierce_selector:
        return f"pierce={selector.pierce_selector}"

    if selector.shadow_path:
        parts = []
        for part in selector.shadow_path:
            parts.append(f"pierce={part}" if selector.use_pierce else part)
        if selector.css:
            return selector.css + " >> " + " >> ".join(parts)
        return " >> ".join(parts)

    if selector.css and selector.use_pierce:
        return f"pierce={selector.css}"

    return None


def _record_attempts(selector: Union[Selector, str], attempts: List[Tuple[str, Any]], ctx_desc: str):
    """Log and attach the attempts for debugging."""
    info = {
        "selector": selector.__dict__ if isinstance(selector, Selector) else str(selector),
        "attempts": [{"strategy": s, "value": v} for s, v in attempts],
        "locale": getattr(settings, "locale", None),
        "context": ctx_desc
    }
    logger.debug("Selector attempts: %s", json.dumps(info, ensure_ascii=False))
    _attach_to_allure("selector_attempts", info)


def _calculate_backoff_delay(attempt: int, initial: float, factor: float, max_delay: float) -> float:
    return min(initial * (factor ** (attempt - 1)), max_delay)


# ---- Public API ----
SelectorLike = Union[Selector, str, Locator]


class SelectorHelper:
    # ---- Resolve with metadata ----
    @staticmethod
    def resolve_with_meta(page: Page, selector: SelectorLike) -> Tuple[Locator, ResolveInfo]:
        """
        Resolve and return (Locator, ResolveInfo) WITHOUT waiting.

        Accepts:
          - Selector (structured; V5 includes raw_selector)
          - str (raw locator string -> passed to page.locator)
          - Locator (returned as-is, ResolveInfo.strategy='locator_object')

        Raises:
          - FrameNotFoundError
          - SelectorResolutionError
        """
        # If caller passed a Locator instance, return it with metadata
        if isinstance(selector, Locator):
            info = ResolveInfo(strategy="locator_object", ctx="page", attempts=[])
            logger.debug("resolve_with_meta: received Locator instance; returning as-is with metadata")
            return selector, info

        # If caller passed a raw string, treat as a Playwright locator string and use page.locator
        if isinstance(selector, str):
            attempts = [("raw_string", selector)]
            try:
                loc = page.locator(selector)
                info = ResolveInfo(strategy="raw_string", ctx="page",
                                   attempts=[{"strategy": "raw_string", "value": selector}])
                _record_attempts(selector, attempts, "page")
                return loc, info
            except PlaywrightError as e:
                logger.debug("raw string locator failed: %s", e, exc_info=True)
                raise SelectorResolutionError(f"Raw string selector failed to produce a locator: {selector}") from e

        # Must be structured Selector
        if not isinstance(selector, Selector):
            raise SelectorResolutionError(f"Unsupported selector type: {type(selector)}")

        # Localize/template and get context
        selector = _localize(selector)
        ctx, ctx_desc = _resolve_context(page, selector)
        attempts: List[Tuple[str, Any]] = []

        def ok(loc: Locator, strategy: str) -> Tuple[Locator, ResolveInfo]:
            """
            创建 ResolveInfo 并返回定位器。

            注意：不再向 attempts 追加 ("used", strategy)，
            因为 attempts 应只包含实际尝试过的策略，而非最终使用的策略。
            最终使用的策略已通过 ResolveInfo.strategy 字段明确标识。
            """
            # 将 attempts 转换为结构化字典用于 ResolveInfo
            attempts_dicts = [{"strategy": s, "value": v} for s, v in attempts]
            info = ResolveInfo(strategy=strategy, ctx=ctx_desc, attempts=attempts_dicts)
            _record_attempts(selector, attempts, ctx_desc)
            return loc, info

        # 0) raw_selector in Selector (V5) -> use it directly via ctx.locator()
        if selector.raw_selector:
            attempts.append(("raw_selector", selector.raw_selector))
            try:
                return ok(ctx.locator(selector.raw_selector), "raw_selector")
            except PlaywrightError:
                logger.debug("raw_selector failed", exc_info=True)

        # 1) shadow/pierce combined (if applicable)
        combined = _compose_shadow_or_pierce(selector)
        if combined:
            attempts.append(("shadow/pierce", combined))
            try:
                return ok(ctx.locator(combined), "shadow/pierce")
            except PlaywrightError:
                logger.debug("shadow/pierce failed", exc_info=True)

        # 2) test_id
        if selector.test_id:
            attempts.append(("test_id", selector.test_id))
            try:
                if hasattr(ctx, "get_by_test_id"):
                    return ok(ctx.get_by_test_id(selector.test_id), "get_by_test_id")
                return ok(ctx.locator(f"[data-testid='{selector.test_id}']"), "attr_test_id")
            except PlaywrightError:
                logger.debug("test_id strategy failed", exc_info=True)

        # 3) role (+ optional name)
        if selector.role:
            attempts.append(("role", (selector.role, selector.role_name)))
            try:
                if hasattr(ctx, "get_by_role"):
                    if selector.role_name:
                        return ok(ctx.get_by_role(selector.role, name=selector.role_name), "get_by_role+name")
                    return ok(ctx.get_by_role(selector.role), "get_by_role")
                sel = f"[role='{selector.role}']"
                if selector.role_name:
                    return ok(ctx.locator(f"{sel} >> text={selector.role_name}"), "role_attr+text")
                return ok(ctx.locator(sel), "role_attr")
            except PlaywrightError:
                logger.debug("role strategy failed", exc_info=True)

        # 4) label
        if selector.label:
            attempts.append(("label", selector.label))
            try:
                if hasattr(ctx, "get_by_label"):
                    return ok(ctx.get_by_label(selector.label), "get_by_label")
                return ok(ctx.locator(f"text={selector.label}"), "label_text_fallback")
            except PlaywrightError:
                logger.debug("label strategy failed", exc_info=True)

        # 5) placeholder
        if selector.placeholder:
            attempts.append(("placeholder", selector.placeholder))
            try:
                if hasattr(ctx, "get_by_placeholder"):
                    return ok(ctx.get_by_placeholder(selector.placeholder), "get_by_placeholder")
                return ok(ctx.locator(f"[placeholder='{selector.placeholder}']"), "placeholder_attr")
            except PlaywrightError:
                logger.debug("placeholder strategy failed", exc_info=True)

        # 6) css
        if selector.css:
            attempts.append(("css", selector.css))
            try:
                return ok(ctx.locator(selector.css), "css")
            except PlaywrightError:
                logger.debug("css strategy failed", exc_info=True)

        # 7) xpath
        if selector.xpath:
            attempts.append(("xpath", selector.xpath))
            try:
                return ok(ctx.locator(f"xpath={selector.xpath}"), "xpath")
            except PlaywrightError:
                logger.debug("xpath strategy failed", exc_info=True)

        # 8) text
        if selector.text:
            attempts.append(("text", selector.text))
            try:
                if hasattr(ctx, "get_by_text"):
                    return ok(ctx.get_by_text(selector.text), "get_by_text")
                return ok(ctx.locator(f"text={selector.text}"), "text_locator")
            except PlaywrightError:
                logger.debug("text strategy failed", exc_info=True)

        # none matched -> record attempts and raise
        _record_attempts(selector, attempts, ctx_desc)
        raise SelectorResolutionError(f"Unable to resolve locator for selector: {selector.description or selector}")

    # Backwards-compatible helper that returns only Locator
    @staticmethod
    def resolve_locator(page: Page, selector: SelectorLike) -> Locator:
        loc, _meta = SelectorHelper.resolve_with_meta(page, selector)
        return loc

    # ---- Find (resolve + wait + retry/backoff) ----
    @staticmethod
    def find(
            page: Page,
            selector: SelectorLike,
            wait_for:typing.Optional[
            typing.Literal["attached", "detached", "hidden", "visible"]
        ] = None,
            timeout: Optional[int] = None,
            *,
            retries: int = DEFAULT_RETRIES,
            initial_delay: float = DEFAULT_INITIAL_DELAY,
            backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
            max_delay: float = DEFAULT_MAX_DELAY
    ) -> Locator:
        """
        Resolve locator and wait for desired state with retry/backoff.

        Returns Locator on success or raises LocatorWaitTimeoutError / SelectorResolutionError / FrameNotFoundError.
        """
        timeout = timeout if timeout is not None else DEFAULT_WAIT_TIMEOUT
        attempts_info: List[Dict[str, Any]] = []
        last_exc = None

        for attempt in range(1, max(1, retries) + 1):
            try:
                loc, meta = SelectorHelper.resolve_with_meta(page, selector)
            except FrameNotFoundError as e:
                _attach_to_allure("frame_error", {"error": str(e), "selector": str(selector)})
                raise
            except SelectorResolutionError as e:
                _attach_to_allure("resolution_error", {"error": str(e), "selector": str(selector)})
                raise

            # attach resolve meta for debugging
            try:
                _attach_to_allure("resolve_meta",
                                  {"strategy": meta.strategy, "ctx": meta.ctx, "attempts": meta.attempts})
            except Exception:
                pass

            if not wait_for:
                return loc

            try:
                loc.wait_for(state=wait_for, timeout=timeout)
                attempts_info.append({"attempt": attempt, "success": True, "resolve_meta": meta.__dict__})
                _attach_to_allure("find_attempts", {"selector": str(selector), "attempts": attempts_info})
                return loc
            except PlaywrightTimeoutError as e:
                last_exc = e
                info = {"attempt": attempt, "wait_for": wait_for, "timeout_ms": timeout, "error": str(e),
                        "resolve_meta": meta.__dict__}
                attempts_info.append(info)
                logger.warning("Selector wait attempt %s failed: %s", attempt, str(e))
                if attempt >= retries:
                    break
                delay = _calculate_backoff_delay(attempt, initial_delay, backoff_factor, max_delay)
                _attach_to_allure("find_backoff_step",
                                  {"selector": str(selector), "attempt": attempt, "delay_s": delay, "info": info})
                time.sleep(delay)
            except Exception as e:
                last_exc = e
                attempts_info.append({"attempt": attempt, "error": str(e)})
                _attach_to_allure("find_unexpected_error",
                                  {"selector": str(selector), "attempt": attempt, "error": str(e)})
                raise

        payload = {"selector": str(selector), "attempts": attempts_info, "retries": retries, "timeout_ms": timeout}
        _attach_to_allure("find_failed", payload)
        raise LocatorWaitTimeoutError(f"Waiting for selector timed out after {retries} attempts: {selector}",
                                      attempts_info)

    # ---- Exists (use Playwright APIs, not custom polling) ----
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
        """
        Check whether an element exists using Playwright's Locator APIs.

        Behavior:
        - Accepts Selector | str | Locator.
        - If `timeout` is provided (>0), each attempt calls locator.wait_for(state="attached", timeout=timeout).
        - Otherwise it performs a quick check using locator.count().
        - Retries with exponential backoff are supported; DOM operations use Playwright's methods.
        """
        attempts: List[Dict[str, Any]] = []

        for attempt in range(1, max(1, retries) + 1):
            try:
                loc, meta = SelectorHelper.resolve_with_meta(page, selector)
            except (SelectorResolutionError, FrameNotFoundError) as e:
                # Non-transient: attach and return False
                attempts.append({"attempt": attempt, "error": str(e)})
                _attach_to_allure("exists_resolution_error", {"selector": str(selector), "attempts": attempts})
                return False

            # Attach resolve meta for observability
            try:
                _attach_to_allure("exists_resolve_meta",
                                  {"strategy": meta.strategy, "ctx": meta.ctx, "attempts": meta.attempts})
            except Exception:
                pass

            try:
                if timeout and timeout > 0:
                    try:
                        loc.wait_for(state="attached", timeout=timeout)
                        count = loc.count()
                        ok = count > 0
                        attempts.append({"attempt": attempt, "count": count, "ok": ok, "resolve_meta": meta.__dict__})
                    except PlaywrightTimeoutError as e:
                        attempts.append({"attempt": attempt, "wait_for_timeout_ms": timeout, "error": str(e),
                                         "resolve_meta": meta.__dict__})
                        ok = False
                else:
                    # quick non-blocking check (Playwright's count)
                    count = loc.count()
                    ok = count > 0
                    attempts.append({"attempt": attempt, "count": count, "ok": ok, "resolve_meta": meta.__dict__})

                if ok:
                    _attach_to_allure("exists_result", {"selector": str(selector), "attempts": attempts})
                    return True

            except Exception as e:
                attempts.append({"attempt": attempt, "error": str(e)})
                logger.debug("exists check attempt %s error: %s", attempt, str(e), exc_info=True)

            if attempt >= retries:
                break
            delay = _calculate_backoff_delay(attempt, initial_delay, backoff_factor, max_delay)
            _attach_to_allure("exists_backoff_step", {"selector": str(selector), "attempt": attempt, "delay_s": delay})
            time.sleep(delay)

        _attach_to_allure("exists_result", {"selector": str(selector), "attempts": attempts})
        return False