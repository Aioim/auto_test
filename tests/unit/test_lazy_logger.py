"""
Unit tests for LazyLogger in src/logger/lazy.py

Tests cover:
- LazyLogger.get(name) creates and returns logger instances with filters
- Same name returns same instance (singleton pattern)
- LazyLogger.cleanup() clears all loggers

Environment Notes:
- LazyLogger.get() internally imports from logger.handlers, logger.formatters,
  logger.filters, and config.settings -- all must be mocked.
- The module uses module-level globals _module_instances and _module_lock
  which persist across tests, so we reset them in a fixture.
- Windows GBK console cannot render emoji; all logger output is captured
  or suppressed via mocks.
"""
import sys
import logging
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_logger_state():
    """Reset module-level _module_instances before and after every test.

    Without this, tests that rely on cached state would interfere with each
    other because _module_instances is a global dict.
    """
    import logger.lazy as lazy_mod
    with lazy_mod._module_lock:
        lazy_mod._module_instances.clear()
    yield
    with lazy_mod._module_lock:
        lazy_mod._module_instances.clear()


@pytest.fixture
def mock_all_deps():
    """Mock every heavy dependency that LazyLogger.get() touches internally.

    LazyLogger.get() does the following inside its critical section:
        from .handlers import HandlerFactory
        from .formatters import SecurityFormatter, ColoredFormatter
        from .filters import SensitiveDataFilter, SecurityAuditFilter
        from config import settings

    This fixture patches all of them so that calling get() does not touch
    real files, real I/O, or the real settings object.
    """
    # Force module loading so the patch targets exist in sys.modules
    import logger.handlers  # noqa: F811
    import logger.formatters  # noqa: F811
    import logger.filters  # noqa: F811
    import config  # noqa: F811

    with patch("logger.handlers.HandlerFactory") as mock_hf, \
            patch("logger.formatters.SecurityFormatter") as mock_sf, \
            patch("logger.formatters.ColoredFormatter") as mock_cf, \
            patch("logger.filters.SensitiveDataFilter") as mock_sdf, \
            patch("logger.filters.SecurityAuditFilter") as mock_saf, \
            patch("config.settings") as mock_settings:

        # -- SecurityFormatter class-level constants used by LazyLogger
        mock_sf.STANDARD_FORMAT = (
            "%(asctime)s %(levelname)-8s "
            "[%(filename)s:%(funcName)s:%(lineno)d] %(message)s"
        )
        mock_sf.DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

        # -- Settings used inside LazyLogger.get()
        mock_settings.log.log_level = "INFO"
        mock_settings.log.quiet = True          # suppress emoji banner
        mock_settings.env = "test"
        mock_settings.log.log_file = "test_run.log"
        mock_settings.log.max_bytes = 10 * 1024 * 1024

        yield {
            "handler_factory": mock_hf,
            "security_formatter": mock_sf,
            "colored_formatter": mock_cf,
            "sensitive_filter": mock_sdf,
            "audit_filter": mock_saf,
            "settings": mock_settings,
        }


# ---------------------------------------------------------------------------
# Tests: LazyLogger.get()
# ---------------------------------------------------------------------------

class TestLazyLoggerGet:
    """Tests for LazyLogger.get(name, **kwargs)."""

    def test_returns_logger_instance(self, mock_all_deps):
        """get() should return a logging.Logger instance."""
        from logger.lazy import LazyLogger

        logger = LazyLogger.get("test_basic")
        assert isinstance(logger, logging.Logger)

    def test_same_name_returns_same_instance(self):
        """Calling get() with the same name twice should reuse the cached instance
        without triggering re-initialization.

        We short-circuit the expensive initialisation by pre-populating the
        module-level _module_instances dict manually.
        """
        from logger.lazy import LazyLogger
        import logger.lazy as lazy_mod

        fake_logger = MagicMock(spec=logging.Logger)
        with lazy_mod._module_lock:
            lazy_mod._module_instances["test_cached"] = fake_logger

        result1 = LazyLogger.get("test_cached")
        result2 = LazyLogger.get("test_cached")

        assert result1 is fake_logger
        assert result2 is fake_logger
        assert result1 is result2

    def test_different_names_different_instances(self, mock_all_deps):
        """Each unique name should produce a separate logger instance."""
        from logger.lazy import LazyLogger

        a = LazyLogger.get("logger_a")
        b = LazyLogger.get("logger_b")
        assert a is not b
        assert id(a) != id(b)

    def test_cleanup_clears_all_instances(self):
        """After cleanup(), get() should create a new instance for the same name."""
        from logger.lazy import LazyLogger
        import logger.lazy as lazy_mod

        mock_logger = MagicMock(spec=logging.Logger)
        with lazy_mod._module_lock:
            lazy_mod._module_instances["test_clean"] = mock_logger

        assert len(lazy_mod._module_instances) == 1

        LazyLogger.cleanup()

        assert len(lazy_mod._module_instances) == 0

    def test_cleanup_calls_handler_close(self):
        """cleanup() should close all handlers on each cached logger."""
        from logger.lazy import LazyLogger
        import logger.lazy as lazy_mod

        mock_handler = MagicMock()
        mock_logger = MagicMock(spec=logging.Logger)
        mock_logger.handlers = [mock_handler]

        with lazy_mod._module_lock:
            lazy_mod._module_instances["test_handler_close"] = mock_logger

        LazyLogger.cleanup()

        mock_handler.close.assert_called_once()
        assert len(lazy_mod._module_instances) == 0

    def test_cleanup_handles_missing_handlers_attr(self):
        """cleanup() should not crash if a logger lacks a 'handlers' attribute."""
        from logger.lazy import LazyLogger
        import logger.lazy as lazy_mod

        bare_obj = MagicMock(spec=[])  # no 'handlers' attribute
        with lazy_mod._module_lock:
            lazy_mod._module_instances["no_handlers"] = bare_obj

        # Should not raise
        LazyLogger.cleanup()
        assert len(lazy_mod._module_instances) == 0

    def test_cleanup_handles_handler_close_exception(self):
        """cleanup() should not crash if handler.close() raises."""
        from logger.lazy import LazyLogger
        import logger.lazy as lazy_mod

        failing_handler = MagicMock()
        failing_handler.close.side_effect = OSError("mock close error")

        mock_logger = MagicMock(spec=logging.Logger)
        mock_logger.handlers = [failing_handler]

        with lazy_mod._module_lock:
            lazy_mod._module_instances["failing_handler"] = mock_logger

        # Should not raise despite the OSError
        LazyLogger.cleanup()
        assert len(lazy_mod._module_instances) == 0

    def test_cleanup_is_idempotent(self):
        """Calling cleanup() twice should be safe."""
        from logger.lazy import LazyLogger
        import logger.lazy as lazy_mod

        with lazy_mod._module_lock:
            lazy_mod._module_instances["a"] = MagicMock(spec=logging.Logger)

        LazyLogger.cleanup()
        LazyLogger.cleanup()  # second call
        assert len(lazy_mod._module_instances) == 0

    def test_new_instance_after_cleanup(self, mock_all_deps):
        """After cleanup, get() with the same name should create a fresh logger."""
        from logger.lazy import LazyLogger

        first = LazyLogger.get("test_new_after_cleanup")
        LazyLogger.cleanup()

        second = LazyLogger.get("test_new_after_cleanup")
        assert first is not second
        assert isinstance(second, logging.Logger)

    def test_get_handles_empty_name(self, mock_all_deps):
        """get() with an empty string should still produce a logger."""
        from logger.lazy import LazyLogger

        logger = LazyLogger.get("")
        assert isinstance(logger, logging.Logger)

    def test_get_with_custom_kwargs(self, mock_all_deps):
        """Custom kwargs like log_level should be respected."""
        from logger.lazy import LazyLogger

        logger = LazyLogger.get("custom_kwargs", log_level="DEBUG")
        assert isinstance(logger, logging.Logger)


# ---------------------------------------------------------------------------
# Safety net: module-level globals are reset even if fixture fails
# ---------------------------------------------------------------------------

def teardown_module(module):
    """Final cleanup to leave no global state behind."""
    import logger.lazy as lazy_mod
    with lazy_mod._module_lock:
        lazy_mod._module_instances.clear()
