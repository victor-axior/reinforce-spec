"""Unit tests for logging configuration."""

from __future__ import annotations

import logging

from reinforce_spec._internal._logging import _InterceptHandler, configure_logging


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_json_output(self) -> None:
        configure_logging(level="INFO", json_output=True)
        # If it doesn't raise, configuration succeeded

    def test_configure_console_output(self) -> None:
        configure_logging(level="DEBUG", json_output=False)

    def test_configure_with_log_file(self, tmp_path) -> None:
        log_file = str(tmp_path / "test.log")
        configure_logging(level="DEBUG", json_output=False, log_file=log_file)

    def test_configure_different_levels(self) -> None:
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            configure_logging(level=level, json_output=True)


class TestInterceptHandler:
    """Test the stdlib-to-loguru bridge."""

    def test_handler_is_logging_handler(self) -> None:
        handler = _InterceptHandler()
        assert isinstance(handler, logging.Handler)

    def test_emit_routes_to_loguru(self) -> None:
        handler = _InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        # Should not raise
        handler.emit(record)

    def test_emit_with_unknown_level(self) -> None:
        handler = _InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=99,  # Non-standard level
            pathname="test.py",
            lineno=1,
            msg="custom level message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
