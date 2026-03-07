"""Unit tests for Pydantic models and enums."""

from __future__ import annotations

from datetime import UTC

import pytest
from pydantic import ValidationError

from reinforce_spec.types import (
    CandidateSpec,
    CustomerType,
    DegradationLevel,
    DimensionScore,
    FeedbackRequest,
    PolicyStage,
    PolicyStatus,
    ScoringWeights,
    SelectionMethod,
    SelectionRequest,
    SelectionResponse,
    SpecFormat,
    SpecResult,
    detect_format,
)


class TestSpecFormat:
    """Test spec format detection."""

    def test_format_values(self) -> None:
        assert SpecFormat.TEXT.value == "text"
        assert SpecFormat.JSON.value == "json"
        assert SpecFormat.YAML.value == "yaml"
        assert SpecFormat.MARKDOWN.value == "markdown"
        assert SpecFormat.OTHER.value == "other"
        assert len(SpecFormat) == 5

    def test_detect_format_json(self) -> None:
        assert detect_format('{"key": "value"}') == SpecFormat.JSON
        assert detect_format('[{"a": 1}]') == SpecFormat.JSON

    def test_detect_format_yaml(self) -> None:
        assert detect_format("key: value\nother: thing") == SpecFormat.TEXT

    def test_detect_format_markdown(self) -> None:
        assert detect_format("# Heading\n\nSome content") == SpecFormat.MARKDOWN
        assert detect_format("## Section\n- item") == SpecFormat.MARKDOWN

    def test_detect_format_text(self) -> None:
        assert detect_format("Just a plain text paragraph.") == SpecFormat.TEXT


class TestEnums:
    """Test enum values and ordering."""

    def test_customer_type_values(self) -> None:
        assert CustomerType.BANK.value == "bank"
        assert CustomerType.SI.value == "si"
        assert CustomerType.BPO.value == "bpo"
        assert CustomerType.SAAS.value == "saas"

    def test_policy_stage_promotion_order(self) -> None:
        stages = list(PolicyStage)
        assert stages.index(PolicyStage.CANDIDATE) < stages.index(PolicyStage.PRODUCTION)

    def test_degradation_level_ordering(self) -> None:
        assert DegradationLevel.L0_FULL.value == "L0_full"
        assert DegradationLevel.L3_EMERGENCY.value == "L3_emergency"

    def test_selection_method_options(self) -> None:
        assert SelectionMethod.HYBRID.value == "hybrid"
        assert SelectionMethod.RL_ONLY.value == "rl_only"
        assert SelectionMethod.SCORING_ONLY.value == "scoring_only"


class TestScoringWeights:
    """Test scoring weight validation."""

    def test_default_sums_to_one(self) -> None:
        w = ScoringWeights()
        total = sum(w.as_dict().values())
        assert abs(total - 1.0) < 0.01

    def test_validation_rejects_bad_sum(self) -> None:
        w = ScoringWeights(compliance_regulatory=0.5, security_architecture=0.5)
        assert w.validate_sum() is False


class TestCandidateSpec:
    """Test candidate spec model."""

    def test_defaults(self) -> None:
        c = CandidateSpec(
            content="Test content for spec",
            spec_type="api",
            source_model="model-1",
        )
        assert c.composite_score == 0.0
        assert c.dimension_scores == []
        assert c.format == SpecFormat.TEXT

    def test_auto_detects_format(self) -> None:
        c = CandidateSpec(content='{"openapi": "3.0"}')
        assert c.format == SpecFormat.JSON

    def test_dimension_score_clamping(self) -> None:
        ds = DimensionScore(dimension="test", score=3.5)
        assert ds.score == 3.5


class TestSelectionRequest:
    """Test selection request validation."""

    def test_rejects_single_candidate(self) -> None:
        with pytest.raises(ValidationError):
            SelectionRequest(
                candidates=[
                    CandidateSpec(content="Only one spec"),
                ]
            )

    def test_auto_indexing(self) -> None:
        req = SelectionRequest(
            candidates=[
                CandidateSpec(content="Spec A"),
                CandidateSpec(content="Spec B"),
                CandidateSpec(content="Spec C"),
            ]
        )
        assert [c.index for c in req.candidates] == [0, 1, 2]


class TestSelectionResponse:
    """Test SelectionResponse model."""

    def test_construction(self) -> None:
        from datetime import datetime

        selected = CandidateSpec(content="Best spec", composite_score=4.5)
        resp = SelectionResponse(
            request_id="req-1",
            selected=selected,
            all_candidates=[selected],
            selection_method="hybrid",
            selection_confidence=0.95,
            latency_ms=123.4,
            timestamp=datetime.now(tz=UTC),
        )
        assert resp.request_id == "req-1"
        assert resp.selection_confidence == 0.95
        assert resp.latency_ms == 123.4

    def test_default_scoring_summary(self) -> None:
        from datetime import datetime

        resp = SelectionResponse(
            request_id="req-2",
            selected=CandidateSpec(content="Spec"),
            all_candidates=[],
            selection_method="scoring_only",
            latency_ms=50.0,
            timestamp=datetime.now(tz=UTC),
        )
        assert resp.scoring_summary == {}


class TestSpecResult:
    """Test SpecResult model."""

    def test_construction(self) -> None:
        selected = CandidateSpec(content="Best spec", composite_score=4.0)
        result = SpecResult(
            selected=selected,
            all_candidates=[selected],
            selection_method=SelectionMethod.HYBRID,
            latency_ms=100.0,
            request_id="req-1",
        )
        assert result.selection_method == SelectionMethod.HYBRID
        assert result.degradation_level == DegradationLevel.L0_FULL
        assert result.policy_version is None


class TestFeedbackRequest:
    """Test FeedbackRequest model."""

    def test_valid_feedback(self) -> None:
        fb = FeedbackRequest(
            request_id="req-1",
            preferred_spec_index=0,
            rating=4.5,
            rationale="Good spec",
        )
        assert fb.request_id == "req-1"
        assert fb.rating == 4.5

    def test_optional_fields(self) -> None:
        fb = FeedbackRequest(
            request_id="req-1",
            preferred_spec_index=0,
        )
        assert fb.rating is None
        assert fb.rationale is None

    def test_rating_bounds(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                request_id="req-1",
                preferred_spec_index=0,
                rating=0.5,
            )
        with pytest.raises(ValidationError):
            FeedbackRequest(
                request_id="req-1",
                preferred_spec_index=0,
                rating=6.0,
            )

    def test_spec_index_bounds(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                request_id="req-1",
                preferred_spec_index=-1,
            )


class TestPolicyStatus:
    """Test PolicyStatus model."""

    def test_construction(self) -> None:
        ps = PolicyStatus(
            version="v1",
            stage=PolicyStage.PRODUCTION,
            training_episodes=1000,
            mean_reward=0.85,
            explore_rate=0.05,
        )
        assert ps.version == "v1"
        assert ps.stage == PolicyStage.PRODUCTION
        assert ps.drift_psi is None
        assert ps.last_trained is None


class TestDetectFormatEdgeCases:
    """Test detect_format edge cases."""

    def test_empty_string(self) -> None:
        assert detect_format("") == SpecFormat.TEXT

    def test_whitespace_only(self) -> None:
        assert detect_format("   \n  ") == SpecFormat.TEXT

    def test_yaml_frontmatter(self) -> None:
        content = "---\ntitle: My Spec\nauthor: Test\n---\nBody text"
        assert detect_format(content) == SpecFormat.YAML

    def test_yaml_multiple_key_value_lines(self) -> None:
        content = "name: test\nversion: 1\ndescription: hello\ntype: api"
        assert detect_format(content) == SpecFormat.YAML

    def test_fenced_code_block_as_markdown(self) -> None:
        content = "Some text\n```python\nprint('hello')\n```"
        assert detect_format(content) == SpecFormat.MARKDOWN

    def test_json_array(self) -> None:
        assert detect_format('[{"a": 1}, {"b": 2}]') == SpecFormat.JSON

    def test_json_with_whitespace(self) -> None:
        assert detect_format('  \n  {"key": "val"}') == SpecFormat.JSON
