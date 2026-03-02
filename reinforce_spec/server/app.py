"""FastAPI application factory.

Creates a fully wired FastAPI application with:
  - Lifespan management (startup/shutdown of ReinforceSpec client)
  - Route registration (specs, policy, health)
  - Middleware stack (logging, CORS, rate limiting, idempotency)
  - Exception handlers
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from reinforce_spec._exceptions import (
    CircuitBreakerOpenError,
    ConfigurationError,
    InputValidationError,
    PolicyNotFoundError,
    RateLimitError,
    ReinforceSpecError,
    ScoringError,
)
from reinforce_spec._internal._config import AppConfig
from reinforce_spec.client import ReinforceSpec
from reinforce_spec.server.middleware import BackpressureMiddleware, RequestLoggingMiddleware
from reinforce_spec.server.openapi import custom_openapi
from reinforce_spec.server.routes import router
from reinforce_spec.version import VERSION


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan — startup & shutdown hooks."""
    config: AppConfig = app.state.config
    client = ReinforceSpec(config)

    try:
        await client.connect()
        app.state.client = client
        logger.info("server_started | version={version}", version=VERSION)
        yield
    finally:
        await client.close()
        logger.info("server_stopped")


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Application factory.

    Parameters
    ----------
    config : AppConfig or None
        Application configuration. Loaded from environment if not provided.

    Returns
    -------
    FastAPI
        Fully configured FastAPI application.

    """
    config = config or AppConfig.from_env()

    app = FastAPI(
        title="ReinforceSpec API",
        description=(
            "RL-optimized enterprise specification evaluator and selector. "
            "Scores and selects the best spec from user-provided candidates "
            "using multi-judge LLM evaluation and PPO reinforcement learning."
        ),
        version=VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Store config on app state for access in lifespan
    app.state.config = config

    # ── CORS ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────
    app.include_router(router)

    # ── Middleware (applied in reverse order) ─────────────────────────
    app.add_middleware(BackpressureMiddleware, max_concurrent=config.server.max_concurrent_requests)
    app.add_middleware(RequestLoggingMiddleware)

    # ── Custom OpenAPI schema ─────────────────────────────────────────
    app.openapi = lambda: custom_openapi(app)  # type: ignore[assignment]

    # ── Exception handlers ────────────────────────────────────────────
    _register_exception_handlers(app)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(
        request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": "configuration_error", "message": str(exc)},
        )

    @app.exception_handler(CircuitBreakerOpenError)
    async def circuit_breaker_handler(
        request: Request, exc: CircuitBreakerOpenError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "service_unavailable",
                "message": "Upstream LLM service is temporarily unavailable",
                "retry_after": 30,
            },
            headers={"Retry-After": "30"},
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(
        request: Request, exc: RateLimitError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": str(exc),
            },
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(InputValidationError)
    async def input_validation_error_handler(
        request: Request, exc: InputValidationError
    ) -> JSONResponse:
        logger.warning("input_validation_error | error={error}", error=str(exc))
        return JSONResponse(
            status_code=422,
            content={"error": "validation_failed", "message": str(exc)},
        )

    @app.exception_handler(ScoringError)
    async def scoring_error_handler(
        request: Request, exc: ScoringError
    ) -> JSONResponse:
        logger.error("scoring_error | error={error}", error=str(exc))
        return JSONResponse(
            status_code=502,
            content={"error": "scoring_failed", "message": str(exc)},
        )

    @app.exception_handler(PolicyNotFoundError)
    async def policy_not_found_handler(
        request: Request, exc: PolicyNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "policy_not_found", "message": str(exc)},
        )

    @app.exception_handler(ReinforceSpecError)
    async def generic_handler(
        request: Request, exc: ReinforceSpecError
    ) -> JSONResponse:
        logger.error("unhandled_domain_error | error={error} type={type}", error=str(exc), type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def fallback_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception | error={error}", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "An unexpected error occurred"},
        )
