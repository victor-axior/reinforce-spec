"""Route sub-package.

Assembles all route modules into a single ``router`` that the app factory
includes.
"""

from __future__ import annotations

from fastapi import APIRouter

from reinforce_spec.server.routes.health import router as health_router
from reinforce_spec.server.routes.jobs import router as jobs_router
from reinforce_spec.server.routes.policy import router as policy_router
from reinforce_spec.server.routes.specs import router as specs_router

router = APIRouter(prefix="/v1")
router.include_router(specs_router)
router.include_router(policy_router)
router.include_router(jobs_router)
router.include_router(health_router)

__all__ = ["router"]
