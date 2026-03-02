"""Pydantic request/response schemas for the API.

Centralises all API-facing models so that routes stay thin.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Spec Schemas ──────────────────────────────────────────────────────────────


class SpecInput(BaseModel):
    """Single spec candidate in the request body."""

    content: str = Field(..., min_length=1, description="Specification text (any format)")
    source_model: str = Field("", description="Model that authored this spec (optional)")
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluateRequest(BaseModel):
    """Request body for spec evaluation and selection."""

    candidates: list[SpecInput] = Field(
        ...,
        min_length=2,
        description="Specification candidates (min 2, recommended ≥ 5) in any textual format",
    )
    selection_method: str = Field("hybrid", description="Selection method: hybrid, scoring_only, rl_only")
    request_id: str | None = Field(None, description="Idempotency key")
    description: str = Field("", max_length=2000, description="Optional context for auditing")


# ── Feedback Schemas ──────────────────────────────────────────────────────────


class FeedbackRequestBody(BaseModel):
    """Request body for feedback submission."""

    request_id: str = Field(..., description="ID of the evaluation request")
    rating: float | None = Field(None, ge=1.0, le=5.0, description="Quality rating (1-5)")
    comment: str | None = Field(None, max_length=2000, description="Free-text feedback")
    spec_id: str | None = Field(None, description="Specific spec ID being rated")


class FeedbackResponse(BaseModel):
    """Feedback submission response."""

    feedback_id: str
    status: str = "accepted"


# ── Policy Schemas ────────────────────────────────────────────────────────────


class TrainRequest(BaseModel):
    """Request body for policy training."""

    n_steps: int | None = Field(None, ge=1, description="Training timesteps")


# ── Health Schemas ────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    uptime_seconds: float | None = None


# ── Job Schemas ───────────────────────────────────────────────────────────────


class JobResponse(BaseModel):
    """Background job status response."""

    job_id: str
    name: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
