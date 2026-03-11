"""Rate-limiting middleware.

Wraps SlowAPI for per-client rate limiting.  When ``slowapi`` is not
installed, all requests pass through (no-op).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi import Request, Response


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip: str = forwarded.split(",")[0].strip()
        return ip
    if request.client:
        return str(request.client.host)
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter.

    Parameters
    ----------
    requests_per_minute : int
        Maximum requests per client IP per minute.
    cleanup_interval : int
        How often to clean up stale entries (every N requests).
    max_clients : int
        Maximum number of tracked clients before forced cleanup.

    """

    def __init__(
        self,
        app: object,
        requests_per_minute: int = 60,
        cleanup_interval: int = 100,
        max_clients: int = 10000,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._rpm = requests_per_minute
        self._cleanup_interval = cleanup_interval
        self._max_clients = max_clients
        self._request_count = 0
        self._windows: dict[str, list[float]] = {}

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Enforce per-IP rate limiting."""
        import time

        # Bypass health checks
        if request.url.path.startswith("/v1/health"):
            return await call_next(request)

        client_ip = _get_client_ip(request)
        now = time.monotonic()

        # Sliding window
        window = self._windows.setdefault(client_ip, [])
        window[:] = [ts for ts in window if now - ts < 60.0]

        if len(window) >= self._rpm:
            logger.warning(
                "rate_limited | ip={ip} rpm={rpm}",
                ip=client_ip,
                rpm=self._rpm,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": f"Rate limit exceeded ({self._rpm} req/min)",
                },
                headers={"Retry-After": "60"},
            )

        window.append(now)

        # Periodic cleanup to prevent memory leak
        self._request_count += 1
        if self._request_count >= self._cleanup_interval:
            self._cleanup_stale_entries(now)
            self._request_count = 0

        return await call_next(request)

    def _cleanup_stale_entries(self, now: float) -> None:
        """Remove stale client entries to prevent unbounded memory growth."""
        # Remove clients with no recent requests
        stale_clients = [
            client_ip
            for client_ip, window in self._windows.items()
            if not window or (now - max(window)) > 120.0  # 2 min TTL
        ]
        for client_ip in stale_clients:
            del self._windows[client_ip]

        # If still too many clients, remove oldest entries (LRU-style)
        if len(self._windows) > self._max_clients:
            # Sort by most recent request time, keep newest
            sorted_clients = sorted(
                self._windows.items(),
                key=lambda x: max(x[1]) if x[1] else 0,
                reverse=True,
            )
            self._windows = dict(sorted_clients[: self._max_clients // 2])
            logger.info(
                "rate_limiter_cleanup | removed={removed} remaining={remaining}",
                removed=len(sorted_clients) - len(self._windows),
                remaining=len(self._windows),
            )
