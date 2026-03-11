"""Testing utilities for the ReinforceSpec SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from reinforce_spec_sdk.types import (
    CandidateSpec,
    DimensionScore,
    HealthResponse,
    PolicyStage,
    PolicyStatus,
    SelectionMethod,
    SelectionResponse,
    SpecFormat,
)


class MockClient:
    """Mock client for testing applications that use the ReinforceSpec SDK.

    This class provides a test double that mimics the ReinforceSpecClient
    interface without making actual HTTP requests.

    Example:
        >>> from reinforce_spec_sdk.testing import MockClient
        >>>
        >>> # Create mock with predefined responses
        >>> client = MockClient(
        ...     select_response=make_selection_response(selected_index=0),
        ... )
        >>>
        >>> # Use in tests
        >>> response = await client.select(candidates=[...])
        >>> assert response.selected.index == 0
    """

    def __init__(
        self,
        select_response: SelectionResponse | None = None,
        policy_status: PolicyStatus | None = None,
        health_response: HealthResponse | None = None,
    ) -> None:
        """Initialize mock client with predefined responses.

        Args:
            select_response: Response to return from select().
            policy_status: Response to return from get_policy_status().
            health_response: Response to return from health().
        """
        self._select_response = select_response or make_selection_response()
        self._policy_status = policy_status or make_policy_status()
        self._health_response = health_response or HealthResponse(
            status="healthy",
            version="1.0.0",
            uptime_seconds=3600.0,
        )
        self._feedback_calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> MockClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def close(self) -> None:
        pass

    async def select(
        self,
        candidates: list[dict[str, Any]],
        **kwargs: Any,
    ) -> SelectionResponse:
        """Mock select method."""
        return self._select_response

    async def submit_feedback(
        self,
        request_id: str,
        **kwargs: Any,
    ) -> str:
        """Mock submit_feedback method."""
        self._feedback_calls.append({"request_id": request_id, **kwargs})
        return f"feedback-{len(self._feedback_calls)}"

    async def get_policy_status(self) -> PolicyStatus:
        """Mock get_policy_status method."""
        return self._policy_status

    async def train_policy(self, n_steps: int | None = None) -> dict[str, Any]:
        """Mock train_policy method."""
        return {"job_id": "job-123", "status": "started"}

    async def health(self) -> HealthResponse:
        """Mock health method."""
        return self._health_response

    async def ready(self) -> HealthResponse:
        """Mock ready method."""
        return self._health_response

    def get_feedback_calls(self) -> list[dict[str, Any]]:
        """Get all recorded feedback calls."""
        return self._feedback_calls.copy()


def make_dimension_score(
    dimension: str = "Accuracy",
    score: float = 4.0,
    justification: str = "Good accuracy",
    confidence: float = 0.85,
) -> DimensionScore:
    """Create a DimensionScore for testing."""
    return DimensionScore(
        dimension=dimension,
        score=score,
        justification=justification,
        confidence=confidence,
    )


def make_candidate(
    index: int = 0,
    content: str = "Test content",
    composite_score: float = 4.0,
    dimension_scores: list[DimensionScore] | None = None,
) -> CandidateSpec:
    """Create a CandidateSpec for testing."""
    if dimension_scores is None:
        dimension_scores = [
            make_dimension_score("Accuracy", 4.0),
            make_dimension_score("Completeness", 4.2),
            make_dimension_score("Clarity", 3.8),
        ]

    return CandidateSpec(
        index=index,
        content=content,
        format=SpecFormat.TEXT,
        spec_type="api_spec",
        source_model="gpt-4",
        dimension_scores=dimension_scores,
        composite_score=composite_score,
        judge_models=["anthropic/claude-3-opus", "openai/gpt-4-turbo"],
        metadata=None,
    )


def make_selection_response(
    request_id: str = "test-request-123",
    selected_index: int = 0,
    selection_method: SelectionMethod = SelectionMethod.HYBRID,
    num_candidates: int = 2,
) -> SelectionResponse:
    """Create a SelectionResponse for testing."""
    candidates = [make_candidate(i, f"Content {i}", 4.0 - i * 0.5) for i in range(num_candidates)]

    return SelectionResponse(
        request_id=request_id,
        selected=candidates[selected_index],
        all_candidates=candidates,
        selection_method=selection_method,
        selection_confidence=0.85,
        scoring_summary={"Accuracy": 4.0, "Completeness": 4.2, "Clarity": 3.8},
        latency_ms=150.0,
        timestamp=datetime.now(),
    )


def make_policy_status(
    version: str = "v001",
    stage: PolicyStage = PolicyStage.PRODUCTION,
    training_episodes: int = 10000,
    mean_reward: float = 0.75,
) -> PolicyStatus:
    """Create a PolicyStatus for testing."""
    return PolicyStatus(
        version=version,
        stage=stage,
        training_episodes=training_episodes,
        mean_reward=mean_reward,
        explore_rate=0.1,
        drift_psi=0.05,
        last_trained=datetime.now(),
        last_promoted=datetime.now(),
    )
