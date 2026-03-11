"""Idempotency middleware.

Intercepts requests carrying an ``Idempotency-Key`` header and:
  1. Returns the cached response if the key was seen before.
  2. Acquires a lock, forwards the request, and caches the response.

Requires ``IdempotencyStore`` to be attached at ``app.state.idempotency``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Ensure at-most-once processing for write endpoints."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Check idempotency key before forwarding the request."""
        # Only applies to mutating methods
        if request.method not in {"POST", "PUT", "PATCH"}:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        store = getattr(request.app.state, "idempotency", None)
        if store is None:
            return await call_next(request)

        # Check for cached response
        cached = await store.check(key)
        if cached is not None:
            logger.info("idempotency_hit | key={key}", key=key)
            return JSONResponse(
                status_code=cached.get("status_code", 200),
                content=cached.get("body"),
            )

        # Acquire lock and process
        await store.acquire(key)
        try:
            response = await call_next(request)

            # Cache successful responses
            if 200 <= response.status_code < 300:
                body = b""
                maybe_iterator = getattr(response, "body_iterator", None)
                if maybe_iterator is not None:
                    body_iterator = cast("AsyncIterator[Any]", maybe_iterator)
                    async for chunk in body_iterator:
                        if isinstance(chunk, bytes):
                            body += chunk
                        else:
                            body += chunk.encode("utf-8")

                await store.save(
                    key,
                    {
                        "status_code": response.status_code,
                        "body": json.loads(body) if body else None,
                    },
                )

                # Reconstruct response since we consumed the body
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )

            return response
        finally:
            await store.release(key)
