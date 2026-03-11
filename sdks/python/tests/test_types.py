"""Tests for type definitions and models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from reinforce_spec_sdk.types import (
    DimensionScore,
    EvaluateRequest,
    FeedbackRequest,
    HealthResponse,
    PolicyStage,
    SelectionMethod,
    SpecFormat,
    SpecInput,
)


class TestEnums:
    """Tests for enum definitions."""

    def test_selection_method_values(self):
        assert SelectionMethod.HYBRID.value == "hybrid"
        assert SelectionMethod.SCORING_ONLY.value == "scoring_only"
        assert SelectionMethod.RL_ONLY.value == "rl_only"

    def test_spec_format_values(self):
        assert SpecFormat.TEXT.value == "text"
        assert SpecFormat.JSON.value == "json"
        assert SpecFormat.YAML.value == "yaml"

    def test_policy_stage_values(self):
        assert PolicyStage.PRODUCTION.value == "production"
        assert PolicyStage.CANDIDATE.value == "candidate"


class TestModels:
    """Tests for Pydantic model validation."""

    def test_spec_input_requires_content(self):
        with pytest.raises(PydanticValidationError):
            SpecInput(content="")

    def test_spec_input_valid(self):
        spec = SpecInput(content="test content", source_model="gpt-4")
        assert spec.content == "test content"
        assert spec.source_model == "gpt-4"

    def test_evaluate_request_min_candidates(self):
        with pytest.raises(PydanticValidationError):
            EvaluateRequest(candidates=[SpecInput(content="only one")])

    def test_dimension_score_bounds(self):
        with pytest.raises(PydanticValidationError):
            DimensionScore(dimension="Accuracy", score=6.0, justification="x", confidence=0.5)

    def test_feedback_request_rating_bounds(self):
        with pytest.raises(PydanticValidationError):
            FeedbackRequest(request_id="r1", rating=0.5)

    def test_health_response_parsing(self):
        h = HealthResponse(status="healthy", version="1.0.0", uptime_seconds=3600.0)
        assert h.status == "healthy"
