"""RL policy management routes.

Endpoints:
  GET  /v1/policy/status — Current RL policy status
  POST /v1/policy/train  — Trigger policy training
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from reinforce_spec.server.dependencies import get_client
from reinforce_spec.types import PolicyStatus

if TYPE_CHECKING:
    from reinforce_spec.client import ReinforceSpec
    from reinforce_spec.server.schemas import TrainRequest

router = APIRouter(tags=["policy"])


@router.get("/policy/status", response_model=PolicyStatus)
async def policy_status(
    client: ReinforceSpec = Depends(get_client),
) -> PolicyStatus:
    """Get current RL policy status and metrics."""
    return await client.get_policy_status()


@router.post("/policy/train")
async def train_policy(
    body: TrainRequest | None = None,
    client: ReinforceSpec = Depends(get_client),
) -> dict[str, Any]:
    """Trigger a policy training iteration.

    Samples from the replay buffer and updates the PPO policy.
    """
    n_steps = body.n_steps if body else None
    return await client.train_policy(n_steps=n_steps)
