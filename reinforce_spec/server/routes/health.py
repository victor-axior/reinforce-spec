"""Health-check routes.

Endpoints:
  GET /v1/health       — Liveness probe
  GET /v1/health/ready — Readiness probe
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

from reinforce_spec.server.schemas import HealthResponse

if TYPE_CHECKING:
    from reinforce_spec.client import ReinforceSpec

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe."""
    from reinforce_spec.version import VERSION

    return HealthResponse(status="ok", version=VERSION)


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    """Readiness probe — verifies the client is connected."""
    from reinforce_spec.version import VERSION

    client: ReinforceSpec | None = getattr(request.app.state, "client", None)
    if client is None or not client._connected:
        return HealthResponse(status="not_ready", version=VERSION)
    return HealthResponse(status="ready", version=VERSION)
