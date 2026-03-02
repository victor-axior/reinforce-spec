"""Backpressure middleware.

Limits the number of concurrent in-flight requests to prevent overload.
Health endpoints bypass the limiter.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse


class BackpressureMiddleware(BaseHTTPMiddleware):
    """Reject requests when concurrency exceeds the configured limit.

    Returns 503 Service Unavailable with a ``Retry-After`` header when
    the server is under excessive load.

    Parameters
    ----------
    app : Any
        ASGI application.
    max_concurrent : int
        Maximum number of concurrent in-flight requests.

    """

    def __init__(self, app: Any, max_concurrent: int = 50) -> None:
        super().__init__(app)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Enforce concurrency limit on non-health endpoints."""
        # Health endpoints bypass backpressure
        if request.url.path.startswith("/v1/health"):
            return await call_next(request)

        if not self._semaphore._value:  # noqa: SLF001
            logger.warning(
                "backpressure_triggered",
                max_concurrent=self._max_concurrent,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "server_overloaded",
                    "message": "Too many concurrent requests. Please retry.",
                },
                headers={"Retry-After": "5"},
            )

        async with self._semaphore:
            return await call_next(request)
