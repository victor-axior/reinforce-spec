"""Spec evaluation and feedback routes.

Endpoints:
  POST /v1/specs          — Evaluate and select the best spec
  POST /v1/specs/feedback — Submit feedback on a result
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from reinforce_spec.server.dependencies import get_client
from reinforce_spec.server.schemas import (
    EvaluateRequest,
    FeedbackRequestBody,
    FeedbackResponse,
)
from reinforce_spec.types import CandidateSpec, SelectionResponse

if TYPE_CHECKING:
    from reinforce_spec.client import ReinforceSpec

router = APIRouter(tags=["specs"])


@router.post("/specs", response_model=SelectionResponse)
async def evaluate_specs(
    body: EvaluateRequest,
    client: ReinforceSpec = Depends(get_client),
) -> SelectionResponse:
    """Evaluate and select the best specification from user-provided candidates.

    Pipeline:
    1. Scores each spec on 12 enterprise-readiness dimensions (multi-judge)
    2. Selects the best via hybrid RL + scoring
    3. Returns ranked results with full scoring breakdown
    """
    candidates = [
        CandidateSpec(
            index=i,
            content=spec.content,
            source_model=spec.source_model,
            metadata=spec.metadata,
        )
        for i, spec in enumerate(body.candidates)
    ]

    return await client.select(
        candidates=candidates,
        selection_method=body.selection_method,
        request_id=body.request_id,
        description=body.description,
    )


@router.post("/specs/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackRequestBody,
    client: ReinforceSpec = Depends(get_client),
) -> FeedbackResponse:
    """Submit human feedback for an evaluation result.

    Feedback shapes RL rewards for future policy training.
    """
    feedback_id = await client.submit_feedback(
        request_id=body.request_id,
        rating=body.rating,
        comment=body.comment,
        spec_id=body.spec_id,
    )
    return FeedbackResponse(feedback_id=feedback_id)
