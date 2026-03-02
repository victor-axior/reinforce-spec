"""Unit tests for server middleware.

Covers: auth, backpressure, rate_limit, idempotency, logging middleware.
Tests use a minimal FastAPI app with the middleware mounted.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with a dummy endpoint."""
    app = FastAPI()

    @app.get("/v1/health/ready")
    async def health_ready():
        return {"status": "ok"}

    @app.get("/v1/test")
    async def test_endpoint():
        return {"data": "hello"}

    @app.post("/v1/submit")
    async def submit_endpoint():
        return {"result": "created"}

    return app


# ── AuthMiddleware ───────────────────────────────────────────────────────────


class TestAuthMiddleware:
    """Test authentication middleware."""

    def test_health_bypasses_auth(self) -> None:
        from reinforce_spec.server.middleware.auth import AuthMiddleware

        app = _make_app()
        app.add_middleware(AuthMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/health/ready")
        assert resp.status_code == 200

    def test_default_allows_all(self) -> None:
        from reinforce_spec.server.middleware.auth import AuthMiddleware

        app = _make_app()
        app.add_middleware(AuthMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test")
        assert resp.status_code == 200

    def test_custom_rejecting_auth(self) -> None:
        from reinforce_spec.server.middleware.auth import AuthMiddleware

        class RejectAuth(AuthMiddleware):
            async def authenticate(self, token: str | None) -> bool:
                return False

        app = _make_app()
        app.add_middleware(RejectAuth)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test")
        assert resp.status_code == 401
        assert resp.json()["error"] == "unauthorized"

    def test_docs_bypass(self) -> None:
        from reinforce_spec.server.middleware.auth import AuthMiddleware

        class RejectAuth(AuthMiddleware):
            async def authenticate(self, token: str | None) -> bool:
                return False

        app = _make_app()
        app.add_middleware(RejectAuth)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/docs")
        # Docs endpoint should bypass auth (redirect or 200)
        assert resp.status_code in (200, 307, 404)


# ── BackpressureMiddleware ───────────────────────────────────────────────────


class TestBackpressureMiddleware:
    """Test concurrency limit middleware."""

    def test_normal_request_passes(self) -> None:
        from reinforce_spec.server.middleware.backpressure import BackpressureMiddleware

        app = _make_app()
        app.add_middleware(BackpressureMiddleware, max_concurrent=10)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test")
        assert resp.status_code == 200

    def test_health_bypasses(self) -> None:
        from reinforce_spec.server.middleware.backpressure import BackpressureMiddleware

        app = _make_app()
        app.add_middleware(BackpressureMiddleware, max_concurrent=1)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/health/ready")
        assert resp.status_code == 200


# ── RateLimitMiddleware ──────────────────────────────────────────────────────


class TestRateLimitMiddleware:
    """Test per-IP rate limiting middleware."""

    def test_normal_request(self) -> None:
        from reinforce_spec.server.middleware.rate_limit import RateLimitMiddleware

        app = _make_app()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test")
        assert resp.status_code == 200

    def test_rate_limit_exceeded(self) -> None:
        from reinforce_spec.server.middleware.rate_limit import RateLimitMiddleware

        app = _make_app()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2)
        client = TestClient(app, raise_server_exceptions=False)
        # Make 3 requests — third should be rate-limited
        client.get("/v1/test")
        client.get("/v1/test")
        resp = client.get("/v1/test")
        assert resp.status_code == 429
        assert resp.json()["error"] == "rate_limited"
        assert "Retry-After" in resp.headers

    def test_health_bypasses_rate_limit(self) -> None:
        from reinforce_spec.server.middleware.rate_limit import RateLimitMiddleware

        app = _make_app()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1)
        client = TestClient(app, raise_server_exceptions=False)
        # Use up the limit
        client.get("/v1/test")
        # Health should still work
        resp = client.get("/v1/health/ready")
        assert resp.status_code == 200

    def test_x_forwarded_for(self) -> None:
        from reinforce_spec.server.middleware.rate_limit import _get_client_ip

        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_no_forwarded_for(self) -> None:
        from reinforce_spec.server.middleware.rate_limit import _get_client_ip

        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        assert _get_client_ip(request) == "10.0.0.1"

    def test_no_client(self) -> None:
        from reinforce_spec.server.middleware.rate_limit import _get_client_ip

        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None
        assert _get_client_ip(request) == "unknown"


# ── IdempotencyMiddleware ────────────────────────────────────────────────────


class TestIdempotencyMiddleware:
    """Test idempotency middleware."""

    def test_get_request_skips(self) -> None:
        from reinforce_spec.server.middleware.idempotency import IdempotencyMiddleware

        app = _make_app()
        app.add_middleware(IdempotencyMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test", headers={"Idempotency-Key": "key-1"})
        assert resp.status_code == 200

    def test_post_without_key_passes_through(self) -> None:
        from reinforce_spec.server.middleware.idempotency import IdempotencyMiddleware

        app = _make_app()
        app.add_middleware(IdempotencyMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/v1/submit")
        assert resp.status_code == 200

    def test_post_with_key_no_store_passes(self) -> None:
        from reinforce_spec.server.middleware.idempotency import IdempotencyMiddleware

        app = _make_app()
        app.add_middleware(IdempotencyMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/v1/submit", headers={"Idempotency-Key": "k1"})
        assert resp.status_code == 200

    def test_post_with_cached_response(self) -> None:
        from reinforce_spec.server.middleware.idempotency import IdempotencyMiddleware

        app = _make_app()
        app.add_middleware(IdempotencyMiddleware)

        store = AsyncMock()
        store.check = AsyncMock(return_value={"status_code": 200, "body": {"cached": True}})
        app.state.idempotency = store

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/v1/submit", headers={"Idempotency-Key": "k2"})
        assert resp.status_code == 200
        assert resp.json()["cached"] is True

    def test_post_new_key_processes_and_caches(self) -> None:
        from reinforce_spec.server.middleware.idempotency import IdempotencyMiddleware

        app = _make_app()
        app.add_middleware(IdempotencyMiddleware)

        store = AsyncMock()
        store.check = AsyncMock(return_value=None)
        store.acquire = AsyncMock()
        store.save = AsyncMock()
        store.release = AsyncMock()
        app.state.idempotency = store

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/v1/submit", headers={"Idempotency-Key": "k3"})
        assert resp.status_code == 200
        # Store.save should have been called
        store.save.assert_called_once()
        store.release.assert_called_once()


# ── RequestLoggingMiddleware ─────────────────────────────────────────────────


class TestRequestLoggingMiddleware:
    """Test structured logging middleware."""

    def test_adds_request_id(self) -> None:
        from reinforce_spec.server.middleware.logging import RequestLoggingMiddleware

        app = _make_app()
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers

    def test_preserves_incoming_request_id(self) -> None:
        from reinforce_spec.server.middleware.logging import RequestLoggingMiddleware

        app = _make_app()
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test", headers={"X-Request-ID": "custom-id-123"})
        assert resp.headers["X-Request-ID"] == "custom-id-123"

    def test_server_timing_header(self) -> None:
        from reinforce_spec.server.middleware.logging import RequestLoggingMiddleware

        app = _make_app()
        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/test")
        assert "Server-Timing" in resp.headers
        assert resp.headers["Server-Timing"].startswith("total;dur=")


# ── middleware __init__ re-exports ────────────────────────────────────────────


class TestMiddlewarePackage:
    def test_imports(self) -> None:
        from reinforce_spec.server.middleware import (
            BackpressureMiddleware,
            RequestLoggingMiddleware,
        )
        assert BackpressureMiddleware is not None
        assert RequestLoggingMiddleware is not None
