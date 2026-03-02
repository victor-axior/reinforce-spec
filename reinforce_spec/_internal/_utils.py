"""Internal shared utilities."""

from __future__ import annotations

import hashlib
import time
from typing import Any
from datetime import datetime, timezone

from ulid import ULID


def generate_request_id() -> str:
    """Generate a unique, sortable request ID using ULID."""
    return str(ULID())


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def hash_content(content: str) -> str:
    """Return a SHA-256 hex digest of the given content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def hash_dict(d: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest of a dict (sorted keys, repr values)."""
    import json

    canonical = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Timer:
    """Simple context-manager timer that records elapsed milliseconds."""

    def __init__(self) -> None:
        self._start: float = 0.0
        self._end: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds."""
        end = self._end if self._end > 0 else time.perf_counter()
        return (end - self._start) * 1000.0


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to [min_val, max_val]."""
    return max(min_val, min(value, max_val))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide without raising ZeroDivisionError."""
    if denominator == 0.0:
        return default
    return numerator / denominator
