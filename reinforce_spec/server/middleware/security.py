"""Security headers middleware.

Applies standard security headers to all responses following OWASP
recommendations and industry standards (Stripe, Cloudflare, Google).

Headers applied:
  - Content-Security-Policy: Mitigates XSS and injection attacks
  - Strict-Transport-Security: Enforces HTTPS connections
  - X-Content-Type-Options: Prevents MIME-type sniffing
  - X-Frame-Options: Prevents clickjacking
  - Referrer-Policy: Controls referrer information leakage
  - Permissions-Policy: Restricts browser features
  - X-XSS-Protection: Legacy XSS filter (for older browsers)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from fastapi import Request, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses.

    Parameters
    ----------
    app : ASGI application
        The wrapped application.
    enable_hsts : bool
        Whether to enable Strict-Transport-Security. Disable in development.
    hsts_max_age : int
        Max age for HSTS in seconds (default: 1 year).
    csp_report_only : bool
        Whether to use Content-Security-Policy-Report-Only header.
        Useful for testing CSP without breaking functionality.

    """

    def __init__(
        self,
        app: object,
        *,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        csp_report_only: bool = False,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._enable_hsts = enable_hsts
        self._hsts_max_age = hsts_max_age
        self._csp_report_only = csp_report_only

        # Build Content-Security-Policy
        # API-focused CSP - restrictive since we don't serve HTML/JS
        self._csp = "; ".join(
            [
                "default-src 'none'",
                "frame-ancestors 'none'",
                "base-uri 'none'",
                "form-action 'none'",
            ]
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Content-Security-Policy
        csp_header = (
            "Content-Security-Policy-Report-Only"
            if self._csp_report_only
            else "Content-Security-Policy"
        )
        response.headers[csp_header] = self._csp

        # Strict-Transport-Security (HSTS)
        # Only enable in production (behind HTTPS load balancer)
        if self._enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self._hsts_max_age}; includeSubDomains; preload"
            )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable browser features we don't need
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Legacy XSS protection (for IE/older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Cache control for API responses
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response
