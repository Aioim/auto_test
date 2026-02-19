from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, List, Tuple, Dict, Union, Literal
import logging
import json
import time
# 尝试导入allure，使其成为可选依赖
try:
    import allure
    ALLURE_AVAILABLE = True
except ImportError:
    allure = None
    ALLURE_AVAILABLE = False

# 尝试导入playwright，使其成为可选依赖
try:
    from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    Page = None
    Locator = None
    PlaywrightTimeoutError = Exception
    PlaywrightError = Exception
    PLAYWRIGHT_AVAILABLE = False
from src.config import settings
from src.config.locators_i18n import get_text as i18n_get_text

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

# Frame cache to improve performance
_frame_cache = {}


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
    if not ALLURE_AVAILABLE or allure is None:
        return
        
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
    # Generate cache key based on frame identifiers
    cache_key = (
        selector.frame_name,
        selector.frame_url_contains,
        selector.frame_locator_css
    )
    
    # Check cache first
    if cache_key in _frame_cache:
        cached_ctx, cached_desc = _frame_cache[cache_key]
        # Validate cached context is still valid
        if isinstance(cached_ctx, Page) or not hasattr(cached_ctx, "is_detached") or not cached_ctx.is_detached():
            return cached_ctx, cached_desc
    
    # Cache miss, resolve context normally
    if selector.frame_name:
        frame = page.frame(name=selector.frame_name)
        if frame:
            _frame_cache[cache_key] = (frame, f"frame(name={selector.frame_name})")
            return _frame_cache[cache_key]
        raise FrameNotFoundError(f"Frame with name '{selector.frame_name}' not found")

    if selector.frame_url_contains:
        for f in page.frames:
            if selector.frame_url_contains in (f.url or ""):
                _frame_cache[cache_key] = (f, f"frame(url_contains={selector.frame_url_contains})")
                return _frame_cache[cache_key]
        raise FrameNotFoundError(f"No frame with url containing '{selector.frame_url_contains}' found")

    if selector.frame_locator_css:
        try:
            fl = page.frame_locator(selector.frame_locator_css)
            _frame_cache[cache_key] = (fl, f"frame_locator(css={selector.frame_locator_css})")
            return _frame_cache[cache_key]
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
        try:
            parts = []
            for part in selector.shadow_path:
                if not isinstance(part, str):
                    logger.warning(f"Non-string shadow path part found: {part}")
                    continue
                parts.append(f"pierce={part}" if selector.use_pierce else part)
            if selector.css:
                return selector.css + " >> " + " >> ".join(parts)
            return " >> ".join(parts)
        except (TypeError, ValueError) as e:
            logger.warning(f"Error composing shadow path: {e}")

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


def _escape_css_value(value: str) -> str:
    """
    Escape CSS attribute value to prevent syntax errors.
    Handles single and double quotes appropriately.
    """
    if not value:
        return "''"
    
    # If value contains single quotes but not double quotes, use double quotes
    if "'" in value and '"' not in value:
        return f'"{value}"'
    
    # Otherwise, use single quotes and escape any single quotes in the value
    escaped_value = value.replace("'", "\\'")
    return f"'{escaped_value}'"


def _try_strategy(ctx, strategy_name, strategy_func, attempts, strategy_value=None):
    """
    Try to execute a locator strategy and handle exceptions.
    
    Args:
        ctx: The context (Page, Frame, or FrameLocator)
        strategy_name: Name of the strategy being tried
        strategy_func: Function that returns a Locator
        attempts: List to record attempts
        strategy_value: Optional value to record instead of function name
    
    Returns:
        Tuple of (Locator, bool) where bool indicates success
    """
    value_to_record = strategy_value if strategy_value is not None else strategy_func.__name__
    attempts.append((strategy_name, value_to_record))
    try:
        locator = strategy_func()
        return locator, True
    except PlaywrightError:
        logger.debug(f"{strategy_name} strategy failed", exc_info=True)
        return None, False


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
        # Handle Locator object case
        if isinstance(selector, Locator):
            return SelectorHelper._resolve_locator_object(selector)

        # Handle string selector case
        if isinstance(selector, str):
            return SelectorHelper._resolve_string_selector(page, selector)

        # Must be structured Selector
        if not isinstance(selector, Selector):
            raise SelectorResolutionError(f"Unsupported selector type: {type(selector)}")

        # Handle structured Selector case
        return SelectorHelper._resolve_structured_selector(page, selector)

    @staticmethod
    def _resolve_structured_selector(page: Page, selector: Selector) -> Tuple[Locator, ResolveInfo]:
        """
        Handle structured Selector case.
        """
        # Localize/template and get context
        selector = _localize(selector)
        ctx, ctx_desc = _resolve_context(page, selector)
        attempts: List[Tuple[str, Any]] = []

        def ok(loc: Locator, strategy: str) -> Tuple[Locator, ResolveInfo]:
            """
            Create ResolveInfo and return locator.
            """
            # Convert attempts to structured dicts for ResolveInfo
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
            def strategy():
                if hasattr(ctx, "get_by_test_id"):
                    return ctx.get_by_test_id(selector.test_id)
                escaped_test_id = _escape_css_value(selector.test_id)
                return ctx.locator(f"[data-testid={escaped_test_id}]")
            attempts.append(("test_id", selector.test_id))
            loc, success = _try_strategy(ctx, "test_id", strategy, attempts, selector.test_id)
            if success:
                return ok(loc, "get_by_test_id" if hasattr(ctx, "get_by_test_id") else "attr_test_id")

        # 3) role (+ optional name)
        if selector.role:
            def strategy():
                if hasattr(ctx, "get_by_role"):
                    if selector.role_name:
                        return ctx.get_by_role(selector.role, name=selector.role_name)
                    return ctx.get_by_role(selector.role)
                escaped_role = _escape_css_value(selector.role)
                sel = f"[role={escaped_role}]"
                if selector.role_name:
                    return ctx.locator(f"{sel} >> text={selector.role_name}")
                return ctx.locator(sel)
            role_info = (selector.role, selector.role_name)
            attempts.append(("role", role_info))
            loc, success = _try_strategy(ctx, "role", strategy, attempts, role_info)
            if success:
                if hasattr(ctx, "get_by_role"):
                    if selector.role_name:
                        return ok(loc, "get_by_role+name")
                    return ok(loc, "get_by_role")
                return ok(loc, "role_attr+text" if selector.role_name else "role_attr")

        # 4) label
        if selector.label:
            def strategy():
                if hasattr(ctx, "get_by_label"):
                    return ctx.get_by_label(selector.label)
                return ctx.locator(f"text={selector.label}")
            attempts.append(("label", selector.label))
            loc, success = _try_strategy(ctx, "label", strategy, attempts, selector.label)
            if success:
                return ok(loc, "get_by_label" if hasattr(ctx, "get_by_label") else "label_text_fallback")

        # 5) placeholder
        if selector.placeholder:
            def strategy():
                if hasattr(ctx, "get_by_placeholder"):
                    return ctx.get_by_placeholder(selector.placeholder)
                escaped_placeholder = _escape_css_value(selector.placeholder)
                return ctx.locator(f"[placeholder={escaped_placeholder}]")
            attempts.append(("placeholder", selector.placeholder))
            loc, success = _try_strategy(ctx, "placeholder", strategy, attempts, selector.placeholder)
            if success:
                return ok(loc, "get_by_placeholder" if hasattr(ctx, "get_by_placeholder") else "placeholder_attr")

        # 6) css
        if selector.css:
            def strategy():
                return ctx.locator(selector.css)
            attempts.append(("css", selector.css))
            loc, success = _try_strategy(ctx, "css", strategy, attempts, selector.css)
            if success:
                return ok(loc, "css")

        # 7) xpath
        if selector.xpath:
            def strategy():
                return ctx.locator(f"xpath={selector.xpath}")
            attempts.append(("xpath", selector.xpath))
            loc, success = _try_strategy(ctx, "xpath", strategy, attempts, selector.xpath)
            if success:
                return ok(loc, "xpath")

        # 8) text
        if selector.text:
            def strategy():
                if hasattr(ctx, "get_by_text"):
                    return ctx.get_by_text(selector.text)
                return ctx.locator(f"text={selector.text}")
            attempts.append(("text", selector.text))
            loc, success = _try_strategy(ctx, "text", strategy, attempts, selector.text)
            if success:
                return ok(loc, "get_by_text" if hasattr(ctx, "get_by_text") else "text_locator")

        # none matched -> record attempts and raise
        _record_attempts(selector, attempts, ctx_desc)
        raise SelectorResolutionError(f"Unable to resolve locator for selector: {selector.description or selector}")

    # Backwards-compatible helper that returns only Locator
    @staticmethod
    def resolve_locator(page: Page, selector: SelectorLike) -> Locator:
        loc, _meta = SelectorHelper.resolve_with_meta(page, selector)
        return loc

    @staticmethod
    def _resolve_locator_object(selector: Locator) -> Tuple[Locator, ResolveInfo]:
        """
        Handle Locator object case.
        """
        info = ResolveInfo(strategy="locator_object", ctx="page", attempts=[])
        logger.debug("resolve_with_meta: received Locator instance; returning as-is with metadata")
        return selector, info

    @staticmethod
    def _resolve_string_selector(page: Page, selector_str: str) -> Tuple[Locator, ResolveInfo]:
        """
        Handle string selector case.
        """
        attempts = [("raw_string", selector_str)]
        try:
            loc = page.locator(selector_str)
            info = ResolveInfo(strategy="raw_string", ctx="page",
                              attempts=[{"strategy": "raw_string", "value": selector_str}])
            _record_attempts(selector_str, attempts, "page")
            return loc, info
        except PlaywrightError as e:
            logger.debug("raw string locator failed: %s", e, exc_info=True)
            raise SelectorResolutionError(f"Raw string selector failed to produce a locator: {selector_str}") from e

    # ---- Find (resolve + wait + retry/backoff) ----
    @staticmethod
    def find(
            page: Page,
            selector: SelectorLike,
            wait_for: Optional[
            Literal["attached", "detached", "hidden", "visible"]
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

    # ---- Common action helpers ----
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
        """
        Resolve locator, wait for desired state, and click with retry/backoff.
        """
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
        """
        Resolve locator, wait for desired state, and fill text with retry/backoff.
        """
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
    ) -> str:
        """
        Resolve locator, wait for desired state, and get text content with retry/backoff.
        """
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
        """
        Check whether an element is visible using Playwright's Locator APIs.
        """
        try:
            loc = SelectorHelper.find(
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
        """
        Resolve locator and wait for desired state with retry/backoff.
        Returns the resolved locator.
        """
        return SelectorHelper.find(
            page, selector, wait_for=wait_for, timeout=timeout,
            retries=retries, initial_delay=initial_delay,
            backoff_factor=backoff_factor, max_delay=max_delay
        )