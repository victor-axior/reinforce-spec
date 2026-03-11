"""Logging configuration.

Configures ``loguru`` for production JSON output or
development-friendly colored console output.
"""

from __future__ import annotations

import logging
import sys

from loguru import logger


class _InterceptHandler(logging.Handler):
    """Route stdlib logging into loguru.

    This ensures that logs from third-party libraries (uvicorn, httpx)
    flow through loguru's pipeline.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Find the loguru level that matches the stdlib level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore[assignment]

        # Find the caller from where the log originated
        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(
    *,
    level: str = "INFO",
    json_output: bool = True,
    log_file: str | None = None,
) -> None:
    """Configure logging for the application.

    Parameters
    ----------
    level : str
        Minimum log level (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).
    json_output : bool
        ``True`` for JSON lines (production), ``False`` for
        colored console output (development).
    log_file : str or None
        Optional path to write logs to a rotating file.

    """
    # Remove default loguru handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        level=level.upper(),
        serialize=json_output,
        colorize=not json_output,
        format=(
            "<green>{time:YYYY-MM-DDTHH:mm:ss.SSSZ}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        ),
        backtrace=True,
        diagnose=not json_output,
    )

    # File handler
    if log_file:
        logger.add(
            log_file,
            level=level.upper(),
            serialize=json_output,
            rotation="50 MB",
            retention="7 days",
            compression="gz",
        )

    # Intercept stdlib logging → loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Quiet noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
