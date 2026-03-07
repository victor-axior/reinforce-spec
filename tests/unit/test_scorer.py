"""Unit tests for EnterpriseScorer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from reinforce_spec._internal._bias import PairwiseComparison
from reinforce_spec._internal._config import ScoringConfig
from reinforce_spec._internal._rubric import Dimension
from reinforce_spec._internal._scorer import (
    EnterpriseScorer,
    _build_pairwise_prompt,
    _build_pointwise_prompt,
)
from reinforce_spec.types import CandidateSpec, DimensionScore, ScoringWeights

# ── Helpers ──────────────────────────────────────────────────────────────────

ALL_DIM_NAMES = [d.value for d in Dimension]


def _make_mock_client(judge_models: list[str] | None = None) -> MagicMock:
    client = MagicMock()
    client.judge_models = judge_models or ["test/judge-a"]
    return client


def _make_score_response(score: float = 3.0) -> str:
    """Build a valid JSON response from a judge."""
    evaluations = {}
    for dim in ALL_DIM_NAMES:
        evaluations[dim] = {
            "reasoning": "Good coverage",
            "score": score,
            "justification": "Adequate",
            "evidence": ["some text"],
        }
    return json.dumps(
        {
            "evaluations": evaluations,
            "composite_score": score,
            "top_strengths": ["s1"],
            "critical_gaps": ["g1"],
        }
    )


def _make_candidates(n: int = 3) -> list[CandidateSpec]:
    return [
        CandidateSpec(
            index=i,
            content=f"Spec content {i} with enough text to avoid short",
            spec_type="api",
            source_model="test/generator",
            composite_score=float(i),
        )
        for i in range(n)
    ]


# ── Prompt builders ──────────────────────────────────────────────────────────


class TestBuildPrompts:
    """Test prompt builders."""

    def test_pointwise_prompt_contains_rubric(self) -> None:
        prompt = _build_pointwise_prompt("Test spec content")
        assert "Rubric" in prompt or "rubric" in prompt or "dimension" in prompt.lower()
        assert "Test spec content" in prompt

    def test_pairwise_prompt_contains_both_specs(self) -> None:
        prompt = _build_pairwise_prompt("Spec A content", "Spec B content")
        assert "Spec A content" in prompt
        assert "Spec B content" in prompt


# ── Static / pure methods ────────────────────────────────────────────────────


class TestParseScores:
    """Test EnterpriseScorer._parse_scores."""

    def test_valid_evaluations(self) -> None:
        resp = _make_score_response(4.0)
        scores = EnterpriseScorer._parse_scores(resp)
        assert isinstance(scores, dict)
        for dim in ALL_DIM_NAMES:
            assert dim in scores
            assert scores[dim] == 4.0

    def test_invalid_json_fallback_to_minimum(self) -> None:
        scores = EnterpriseScorer._parse_scores("not json")
        assert isinstance(scores, dict)
        # Should return 1.0 for every dimension on failure
        for dim in ALL_DIM_NAMES:
            assert scores[dim] == 1.0

    def test_code_fenced_json_stripped(self) -> None:
        inner = _make_score_response(2.5)
        fenced = f"```json\n{inner}\n```"
        scores = EnterpriseScorer._parse_scores(fenced)
        for dim in ALL_DIM_NAMES:
            assert scores[dim] == 2.5

    def test_scores_clamped_to_range(self) -> None:
        """Scores outside [1, 5] should be clamped."""
        evaluations = {dim: {"score": 10.0} for dim in ALL_DIM_NAMES}
        resp = json.dumps({"evaluations": evaluations})
        scores = EnterpriseScorer._parse_scores(resp)
        for v in scores.values():
            assert v <= 5.0

    def test_scores_clamped_low(self) -> None:
        evaluations = {dim: {"score": -2.0} for dim in ALL_DIM_NAMES}
        resp = json.dumps({"evaluations": evaluations})
        scores = EnterpriseScorer._parse_scores(resp)
        for v in scores.values():
            assert v >= 1.0

    def test_numeric_dim_values_parsed(self) -> None:
        """Dimension values that are plain numbers (not dicts) are accepted."""
        evaluations = {dim: 3.5 for dim in ALL_DIM_NAMES}
        resp = json.dumps({"evaluations": evaluations})
        scores = EnterpriseScorer._parse_scores(resp)
        for v in scores.values():
            assert v == 3.5


class TestComputeComposite:
    """Test EnterpriseScorer._compute_composite."""

    def test_uniform_scores(self) -> None:
        weights = ScoringWeights()
        dim_scores = [DimensionScore(dimension=k, score=3.0) for k in weights.as_dict()]
        composite = EnterpriseScorer._compute_composite(dim_scores, weights)
        # Total = sum(3.0 * w) = 3.0 * 1.0 = 3.0  (weights sum to ~1.0)
        assert abs(composite - 3.0) < 0.1

    def test_empty_scores(self) -> None:
        composite = EnterpriseScorer._compute_composite([], ScoringWeights())
        assert composite == 0.0

    def test_missing_dimension_gets_zero_weight(self) -> None:
        """Unknown dimension name → weight=0 → no contribution."""
        dim_scores = [DimensionScore(dimension="unknown_dim", score=5.0)]
        composite = EnterpriseScorer._compute_composite(dim_scores, ScoringWeights())
        assert composite == 0.0


class TestParsePairwiseWinner:
    """Test EnterpriseScorer._parse_pairwise_winner."""

    def test_winner_a(self) -> None:
        resp = json.dumps({"overall_winner": "A", "confidence": 0.9})
        assert EnterpriseScorer._parse_pairwise_winner(resp) == "A"

    def test_winner_b(self) -> None:
        resp = json.dumps({"overall_winner": "B"})
        assert EnterpriseScorer._parse_pairwise_winner(resp) == "B"

    def test_lowercase_normalised(self) -> None:
        resp = json.dumps({"overall_winner": "b"})
        assert EnterpriseScorer._parse_pairwise_winner(resp) == "B"

    def test_invalid_json_defaults_to_a(self) -> None:
        assert EnterpriseScorer._parse_pairwise_winner("garbage") == "A"

    def test_code_fenced_response(self) -> None:
        inner = json.dumps({"overall_winner": "B"})
        fenced = f"```json\n{inner}\n```"
        assert EnterpriseScorer._parse_pairwise_winner(fenced) == "B"


class TestMergeRankings:
    """Test EnterpriseScorer._merge_rankings."""

    def test_no_pairwise_results_returns_original(self) -> None:
        candidates = _make_candidates(3)
        result = EnterpriseScorer._merge_rankings(candidates, [], top_k=2)
        assert result == candidates

    def test_consistent_wins_rerank_top_k(self) -> None:
        candidates = _make_candidates(3)
        # Create a consistent comparison where candidate-0 wins over candidate-1
        comp = PairwiseComparison(
            spec_a_index=0,
            spec_b_index=1,
            a_preferred_forward=True,
            b_preferred_forward=False,
            a_preferred_reversed=True,
            b_preferred_reversed=False,
        )
        result = EnterpriseScorer._merge_rankings(candidates, [comp], top_k=2)
        assert len(result) == 3
        # Candidate 0 should rank higher than candidate 1 in the top section
        top_indices = [c.index for c in result[:2]]
        assert 0 in top_indices


# ── Async scoring pipeline ───────────────────────────────────────────────────


@pytest.mark.asyncio()
class TestScoringPipeline:
    """Integration-style tests for the scoring pipeline."""

    async def test_score_candidates_single_judge(self) -> None:
        client = _make_mock_client()
        resp = _make_score_response()
        client.complete = AsyncMock(return_value=(resp, MagicMock()))

        config = ScoringConfig(
            scoring_mode="single_judge",
            calibration_enabled=False,
            judge_samples_per_model=1,
            pairwise_top_k=2,
        )
        scorer = EnterpriseScorer(client, config)
        candidates = _make_candidates(3)
        result = await scorer.score_candidates(candidates)
        assert len(result) == 3
        assert client.complete.call_count >= 3

    async def test_score_candidates_multi_judge(self) -> None:
        client = _make_mock_client(judge_models=["judge/a", "judge/b"])
        resp = _make_score_response(4.0)
        client.complete = AsyncMock(return_value=(resp, MagicMock()))

        config = ScoringConfig(
            scoring_mode="multi_judge",
            calibration_enabled=False,
            judge_samples_per_model=1,
            pairwise_top_k=2,
        )
        scorer = EnterpriseScorer(client, config)
        candidates = _make_candidates(2)
        result = await scorer.score_candidates(candidates)
        assert len(result) == 2
        # Two judges × 2 candidates = 4 calls minimum
        assert client.complete.call_count >= 4

    async def test_score_candidates_with_calibration(self) -> None:
        client = _make_mock_client()
        resp = _make_score_response()
        client.complete = AsyncMock(return_value=(resp, MagicMock()))

        config = ScoringConfig(
            scoring_mode="single_judge",
            calibration_enabled=True,
            judge_samples_per_model=1,
            pairwise_top_k=2,
        )
        scorer = EnterpriseScorer(client, config)
        candidates = _make_candidates(2)
        result = await scorer.score_candidates(candidates)
        assert len(result) == 2

    async def test_score_candidates_with_pairwise(self) -> None:
        """pairwise_top_k > 0 triggers pairwise comparison phase."""
        client = _make_mock_client()
        resp = _make_score_response(3.0)
        pairwise_resp = json.dumps({"overall_winner": "A", "confidence": 0.8})
        # First calls are pointwise, then pairwise
        client.complete = AsyncMock(
            side_effect=[
                (resp, MagicMock()),
                (resp, MagicMock()),
                (resp, MagicMock()),
                (pairwise_resp, MagicMock()),
                (pairwise_resp, MagicMock()),
            ]
        )

        config = ScoringConfig(
            scoring_mode="single_judge",
            calibration_enabled=False,
            judge_samples_per_model=1,
            pairwise_top_k=3,
        )
        scorer = EnterpriseScorer(client, config)
        candidates = _make_candidates(3)
        result = await scorer.score_candidates(candidates)
        assert len(result) == 3

    async def test_pairwise_compare(self) -> None:
        client = _make_mock_client()
        a_resp = json.dumps({"overall_winner": "A"})
        b_resp = json.dumps({"overall_winner": "B"})
        client.complete = AsyncMock(
            side_effect=[
                (a_resp, MagicMock()),
                (b_resp, MagicMock()),
            ]
        )

        config = ScoringConfig(scoring_mode="single_judge", calibration_enabled=False)
        scorer = EnterpriseScorer(client, config)

        spec_a = _make_candidates(1)[0]
        spec_b = CandidateSpec(
            index=1,
            content="Another spec text here",
            spec_type="api",
            source_model="test/gen",
            composite_score=2.0,
        )
        comp = await scorer._pairwise_compare(spec_a, spec_b)
        assert isinstance(comp, PairwiseComparison)

    async def test_apply_calibration_no_anchors(self) -> None:
        client = _make_mock_client()
        config = ScoringConfig(scoring_mode="single_judge", calibration_enabled=True)
        scorer = EnterpriseScorer(client, config)
        candidates = _make_candidates(2)
        result = await scorer._apply_calibration(candidates)
        assert result == candidates

    async def test_score_single(self) -> None:
        client = _make_mock_client()
        resp = _make_score_response(4.0)
        client.complete = AsyncMock(return_value=(resp, MagicMock()))

        config = ScoringConfig(scoring_mode="single_judge", calibration_enabled=False)
        scorer = EnterpriseScorer(client, config)

        candidate = _make_candidates(1)[0]
        idx, scores, judge = await scorer._score_single(candidate, "test/judge-a", 0)
        assert idx == candidate.index
        assert isinstance(scores, dict)
        assert judge == "test/judge-a"
