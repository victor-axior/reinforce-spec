"""Authentication middleware stub.

Provides a pluggable authentication layer.  The default implementation
accepts all requests (open access).  Subclass or replace for production
use with JWT, API-key, or OAuth2 bearer authentication.
"""

from __future__ import annotations

from loguru import logger
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate incoming requests via ``Authorization`` header.

    Override ``authenticate`` to plug in a real token validator.
    By default, all requests without an ``Authorization`` header are
    allowed through (development mode).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Check authentication before forwarding the request."""
        # Skip auth for health endpoints and docs
        if request.url.path.startswith(("/v1/health", "/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        token = request.headers.get("Authorization")
        if not await self.authenticate(token):
            logger.warning(
                "auth_rejected | path={path}",
                path=request.url.path,
            )
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Invalid or missing credentials"},
            )

        return await call_next(request)

    async def authenticate(self, token: str | None) -> bool:
        """Validate the bearer token.

        Override this method to implement real authentication.
        Returns ``True`` by default (open access).

        Parameters
        ----------
        token : str or None
            Raw ``Authorization`` header value.

        Returns
        -------
        bool
            ``True`` if the request should be allowed.

        """
        # Default: allow all requests (development mode)
        return True
