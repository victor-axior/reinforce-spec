"""Type definitions for the ReinforceSpec SDK."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class SelectionMethod(str, Enum):
    """Method used to select the best candidate."""

    HYBRID = "hybrid"
    SCORING_ONLY = "scoring_only"
    RL_ONLY = "rl_only"


class SpecFormat(str, Enum):
    """Format of the specification content."""

    TEXT = "text"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    OTHER = "other"


class PolicyStage(str, Enum):
    """Deployment stage of the RL policy."""

    CANDIDATE = "candidate"
    SHADOW = "shadow"
    CANARY = "canary"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class CustomerType(str, Enum):
    """Customer segment for scoring weight customization."""

    BANK = "bank"
    SI = "si"
    BPO = "bpo"
    SAAS = "saas"
    DEFAULT = "default"


# =============================================================================
# Request Types
# =============================================================================


class SpecInput(BaseModel):
    """Input specification for evaluation.

    Attributes:
        content: The specification content to evaluate.
        source_model: The LLM that generated this spec (e.g., "gpt-4").
        metadata: Additional metadata for the spec.
    """

    content: str = Field(..., min_length=1, description="Specification content")
    source_model: str | None = Field(None, description="Source LLM model")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class EvaluateRequest(BaseModel):
    """Request body for the /v1/specs endpoint.

    Attributes:
        candidates: List of specs to evaluate (minimum 2).
        selection_method: Method to use for selection.
        request_id: Idempotency key for the request.
        description: Context about what the specs are for.
    """

    candidates: list[SpecInput] = Field(..., min_length=2, description="Candidate specs")
    selection_method: SelectionMethod = Field(
        SelectionMethod.HYBRID, description="Selection method"
    )
    request_id: str | None = Field(None, description="Idempotency key")
    description: str | None = Field(None, max_length=2000, description="Context description")


class FeedbackRequest(BaseModel):
    """Request body for the /v1/specs/feedback endpoint.

    Attributes:
        request_id: The original request ID to provide feedback for.
        rating: Human rating from 1.0 to 5.0.
        comment: Optional comment about the selection.
        spec_id: ID of the specific spec being rated.
    """

    request_id: str = Field(..., description="Original request ID")
    rating: float | None = Field(None, ge=1.0, le=5.0, description="Rating 1-5")
    comment: str | None = Field(None, max_length=2000, description="Feedback comment")
    spec_id: str | None = Field(None, description="Specific spec ID")


# =============================================================================
# Response Types
# =============================================================================


class DimensionScore(BaseModel):
    """Score for a single evaluation dimension.

    Attributes:
        dimension: Name of the scoring dimension.
        score: Score from 1.0 to 5.0.
        justification: Explanation for the score.
        confidence: Confidence level of the score (0.0-1.0).
    """

    dimension: str = Field(..., description="Dimension name")
    score: float = Field(..., ge=1.0, le=5.0, description="Score 1-5")
    justification: str = Field(..., description="Score justification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0-1")


class CandidateSpec(BaseModel):
    """Evaluated candidate specification.

    Attributes:
        index: Position of this candidate in the input list.
        content: The specification content.
        format: Detected format of the content.
        spec_type: Detected type of specification.
        source_model: The LLM that generated this spec.
        dimension_scores: Scores for each evaluation dimension.
        composite_score: Overall weighted score (0.0-5.0).
        judge_models: LLMs used for scoring.
        metadata: Original metadata from input.
    """

    index: int = Field(..., ge=0, description="Candidate index")
    content: str = Field(..., description="Spec content")
    format: SpecFormat = Field(..., description="Content format")
    spec_type: str = Field(..., description="Spec type")
    source_model: str | None = Field(None, description="Source model")
    dimension_scores: list[DimensionScore] = Field(..., description="Per-dimension scores")
    composite_score: float = Field(..., ge=0.0, le=5.0, description="Composite score")
    judge_models: list[str] = Field(..., description="Judge models used")
    metadata: dict[str, Any] | None = Field(None, description="Original metadata")


class SelectionResponse(BaseModel):
    """Response from the /v1/specs endpoint.

    Attributes:
        request_id: Unique identifier for this request.
        selected: The selected best candidate.
        all_candidates: All candidates with their scores.
        selection_method: Method used for selection.
        selection_confidence: Confidence in the selection (0.0-1.0).
        scoring_summary: Summary scores by dimension.
        latency_ms: Processing time in milliseconds.
        timestamp: When the response was generated.
    """

    request_id: str = Field(..., description="Request ID")
    selected: CandidateSpec = Field(..., description="Selected candidate")
    all_candidates: list[CandidateSpec] = Field(..., description="All evaluated candidates")
    selection_method: SelectionMethod = Field(..., description="Selection method used")
    selection_confidence: float = Field(..., ge=0.0, le=1.0, description="Selection confidence")
    scoring_summary: dict[str, float] = Field(..., description="Score summary by dimension")
    latency_ms: float = Field(..., ge=0.0, description="Latency in ms")
    timestamp: datetime = Field(..., description="Response timestamp")


class FeedbackResponse(BaseModel):
    """Response from the /v1/specs/feedback endpoint.

    Attributes:
        feedback_id: Unique identifier for the feedback.
        request_id: The original request this feedback is for.
        received_at: When the feedback was received.
    """

    feedback_id: str = Field(..., description="Feedback ID")
    request_id: str = Field(..., description="Original request ID")
    received_at: datetime = Field(..., description="Receipt timestamp")


class PolicyStatus(BaseModel):
    """RL policy status from /v1/policy/status.

    Attributes:
        version: Policy version string.
        stage: Current deployment stage.
        training_episodes: Number of training episodes completed.
        mean_reward: Average reward from recent episodes.
        explore_rate: Current exploration rate (epsilon).
        drift_psi: PSI drift metric if available.
        last_trained: When policy was last trained.
        last_promoted: When policy was last promoted.
    """

    version: str = Field(..., description="Policy version")
    stage: PolicyStage = Field(..., description="Deployment stage")
    training_episodes: int = Field(..., ge=0, description="Training episodes")
    mean_reward: float = Field(..., description="Mean reward")
    explore_rate: float = Field(..., ge=0.0, le=1.0, description="Exploration rate")
    drift_psi: float | None = Field(None, description="PSI drift metric")
    last_trained: datetime | None = Field(None, description="Last training time")
    last_promoted: datetime | None = Field(None, description="Last promotion time")


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Health status ("healthy", "degraded", "unhealthy").
        version: API version.
        uptime_seconds: Server uptime in seconds.
    """

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    uptime_seconds: float | None = Field(None, description="Uptime in seconds")
