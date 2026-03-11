"""Unit tests for security headers middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from reinforce_spec.server.middleware.security import SecurityHeadersMiddleware


@pytest.fixture
def app_with_security() -> FastAPI:
    """Create a test app with security middleware."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"message": "ok"}

    app.add_middleware(SecurityHeadersMiddleware)
    return app


@pytest.fixture
def app_dev_mode() -> FastAPI:
    """Create a test app with development security settings."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"message": "ok"}

    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=False,
        csp_report_only=True,
    )
    return app


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    def test_csp_header_present(self, app_with_security: FastAPI) -> None:
        """CSP header should be present in production mode."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        assert "default-src 'none'" in response.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]

    def test_hsts_header_present(self, app_with_security: FastAPI) -> None:
        """HSTS header should be present when enabled."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        assert "Strict-Transport-Security" in response.headers
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_hsts_disabled_in_dev(self, app_dev_mode: FastAPI) -> None:
        """HSTS header should be absent when disabled."""
        client = TestClient(app_dev_mode)
        response = client.get("/test")

        assert "Strict-Transport-Security" not in response.headers

    def test_csp_report_only_in_dev(self, app_dev_mode: FastAPI) -> None:
        """CSP should use report-only header in development."""
        client = TestClient(app_dev_mode)
        response = client.get("/test")

        assert "Content-Security-Policy-Report-Only" in response.headers
        assert "Content-Security-Policy" not in response.headers

    def test_x_content_type_options(self, app_with_security: FastAPI) -> None:
        """X-Content-Type-Options should be nosniff."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self, app_with_security: FastAPI) -> None:
        """X-Frame-Options should be DENY."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        assert response.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self, app_with_security: FastAPI) -> None:
        """Referrer-Policy should be set."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, app_with_security: FastAPI) -> None:
        """Permissions-Policy should disable sensitive features."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        permissions = response.headers["Permissions-Policy"]
        assert "camera=()" in permissions
        assert "microphone=()" in permissions
        assert "geolocation=()" in permissions

    def test_xss_protection(self, app_with_security: FastAPI) -> None:
        """X-XSS-Protection should be set for legacy browsers."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_cache_control_default(self, app_with_security: FastAPI) -> None:
        """Cache-Control should be set if not already present."""
        client = TestClient(app_with_security)
        response = client.get("/test")

        assert "no-store" in response.headers["Cache-Control"]

    def test_preserves_existing_cache_control(self) -> None:
        """Should not override existing Cache-Control header."""
        app = FastAPI()

        @app.get("/cached")
        async def cached_endpoint() -> JSONResponse:
            return JSONResponse(
                {"data": "cached"},
                headers={"Cache-Control": "max-age=3600"},
            )

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)
        response = client.get("/cached")

        assert response.headers["Cache-Control"] == "max-age=3600"


class TestRateLimiterCleanup:
    """Tests for rate limiter memory management."""

    def test_cleanup_removes_stale_entries(self) -> None:
        """Cleanup should remove entries older than TTL."""
        from reinforce_spec.server.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app, requests_per_minute=10)

        # Simulate old entries
        middleware._windows = {
            "192.168.1.1": [0.0, 1.0, 2.0],  # Very old
            "192.168.1.2": [0.0],  # Very old
        }

        # Current time much later
        now = 1000.0
        middleware._cleanup_stale_entries(now)

        # Should remove stale entries
        assert len(middleware._windows) == 0

    def test_cleanup_keeps_recent_entries(self) -> None:
        """Cleanup should keep entries within TTL."""
        from reinforce_spec.server.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app, requests_per_minute=10)

        now = 1000.0
        middleware._windows = {
            "192.168.1.1": [now - 30.0, now - 10.0],  # Recent
            "192.168.1.2": [0.0],  # Old
        }

        middleware._cleanup_stale_entries(now)

        assert "192.168.1.1" in middleware._windows
        assert "192.168.1.2" not in middleware._windows

    def test_max_clients_enforcement(self) -> None:
        """Should trim to max_clients when exceeded."""
        from reinforce_spec.server.middleware.rate_limit import RateLimitMiddleware

        app = FastAPI()
        middleware = RateLimitMiddleware(app, requests_per_minute=10, max_clients=10)

        now = 1000.0
        # Create 20 clients
        middleware._windows = {f"192.168.1.{i}": [now - i] for i in range(20)}

        middleware._cleanup_stale_entries(now)

        # Should reduce to max_clients / 2
        assert len(middleware._windows) <= 5
