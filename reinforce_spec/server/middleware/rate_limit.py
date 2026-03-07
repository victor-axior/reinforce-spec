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
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter.

    Parameters
    ----------
    requests_per_minute : int
        Maximum requests per client IP per minute.

    """

    def __init__(self, app: object, requests_per_minute: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._rpm = requests_per_minute
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
        return await call_next(request)
