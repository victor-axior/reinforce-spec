"""Request logging middleware.

Provides structured request/response logging with:
  - Request-ID propagation (``X-Request-ID`` header)
  - Loguru contextualised logging
  - Server-Timing header with total latency
"""

from __future__ import annotations

import time

from loguru import logger
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from reinforce_spec._internal._utils import generate_request_id


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and latency."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process a request and log its lifecycle."""
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        start = time.perf_counter()

        with logger.contextualize(request_id=request_id):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "request_error | method={method} path={path}",
                    method=request.method,
                    path=request.url.path,
                )
                raise

            elapsed_ms = (time.perf_counter() - start) * 1000

            response.headers["X-Request-ID"] = request_id
            response.headers["Server-Timing"] = f"total;dur={elapsed_ms:.1f}"

            logger.info(
                "request_completed | method={method} path={path} status={status} latency_ms={latency_ms}",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=round(elapsed_ms, 1),
            )

            return response
