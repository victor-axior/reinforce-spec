"""Unit tests for HybridSelector."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from reinforce_spec._internal._selector import HybridSelector
from reinforce_spec.types import CandidateSpec, DegradationLevel, SelectionMethod


def _make_candidates(n: int = 3, scores: list[float] | None = None) -> list[CandidateSpec]:
    scores = scores or [float(i + 1) for i in range(n)]
    return [
        CandidateSpec(
            index=i,
            content=f"Candidate spec content {i} with enough text",
            spec_type="api",
            composite_score=scores[i],
        )
        for i in range(n)
    ]


def _make_mock_policy(action: int = 0, confidence: float = 0.8) -> MagicMock:
    policy = MagicMock()
    policy.predict.return_value = (action, confidence)
    policy.get_action_probabilities.return_value = np.array(
        [0.1, 0.1, 0.1, 0.1, 0.1],
        dtype=np.float32,
    )
    # Set the action index's probability to the confidence
    probs = np.array([0.05, 0.05, 0.05, 0.05, 0.05], dtype=np.float32)
    probs[action] = confidence
    policy.get_action_probabilities.return_value = probs
    return policy


# ── Basic selection ──────────────────────────────────────────────────────────


class TestSelectBasic:
    """Test fundamental selection behaviours."""

    def test_empty_candidates_raises(self) -> None:
        selector = HybridSelector()
        with pytest.raises(ValueError, match="No candidates"):
            selector.select([])

    def test_single_candidate_returns_directly(self) -> None:
        selector = HybridSelector()
        candidates = _make_candidates(1, scores=[3.0])
        selected, meta = selector.select(candidates)
        assert selected is candidates[0]
        assert meta["method"] == "single"
        assert meta["reason"] == "only_one_candidate"


# ── Scoring-only selection ───────────────────────────────────────────────────


class TestSelectByScoring:
    """Test SCORING_ONLY method."""

    def test_picks_highest_composite(self) -> None:
        selector = HybridSelector()
        candidates = _make_candidates(3, scores=[1.0, 3.0, 2.0])
        selected, meta = selector.select(candidates, SelectionMethod.SCORING_ONLY)
        assert selected.index == 1
        assert meta["method"] == SelectionMethod.SCORING_ONLY.value

    def test_equal_scores_picks_one(self) -> None:
        selector = HybridSelector()
        candidates = _make_candidates(2, scores=[3.0, 3.0])
        selected, _meta = selector.select(candidates, SelectionMethod.SCORING_ONLY)
        assert selected in candidates


# ── RL-only selection ────────────────────────────────────────────────────────


class TestSelectByRL:
    """Test RL_ONLY method."""

    def test_uses_policy_action(self) -> None:
        policy = _make_mock_policy(action=2, confidence=0.9)
        selector = HybridSelector(policy=policy)
        candidates = _make_candidates(3, scores=[1.0, 2.0, 3.0])
        selected, meta = selector.select(candidates, SelectionMethod.RL_ONLY)
        assert selected.index == 2
        assert meta["method"] == SelectionMethod.RL_ONLY.value
        assert meta["action"] == 2

    def test_no_policy_falls_back_to_scoring(self) -> None:
        selector = HybridSelector(policy=None)
        candidates = _make_candidates(3, scores=[1.0, 3.0, 2.0])
        selected, meta = selector.select(candidates, SelectionMethod.RL_ONLY)
        # Falls back to scoring → picks highest composite
        assert selected.index == 1
        assert meta["method"] == SelectionMethod.SCORING_ONLY.value

    def test_action_clamped_to_range(self) -> None:
        """Policy returning large action → modulo num candidates."""
        policy = MagicMock()
        policy.predict.return_value = (7, 0.9)
        policy.get_action_probabilities.return_value = np.array(
            [0.2, 0.2, 0.2, 0.2, 0.2],
            dtype=np.float32,
        )
        selector = HybridSelector(policy=policy)
        candidates = _make_candidates(3)
        selected, _meta = selector.select(candidates, SelectionMethod.RL_ONLY)
        assert selected.index == 7 % 3  # 1


# ── Hybrid selection ─────────────────────────────────────────────────────────


class TestSelectHybrid:
    """Test HYBRID blending method."""

    def test_high_confidence_uses_rl_weight(self) -> None:
        policy = _make_mock_policy(action=0, confidence=0.9)
        selector = HybridSelector(
            policy=policy,
            rl_weight=0.5,
            confidence_threshold=0.3,
        )
        candidates = _make_candidates(3, scores=[3.0, 2.0, 1.0])
        _selected, meta = selector.select(candidates, SelectionMethod.HYBRID)
        assert meta["method"] == SelectionMethod.HYBRID.value
        assert "scoring_weight" in meta
        assert "rl_weight" in meta
        assert "rl_confidence" in meta

    def test_low_confidence_reduces_rl_weight(self) -> None:
        """Confidence below threshold → RL weight reduced proportionally."""
        policy = _make_mock_policy(action=0, confidence=0.1)
        selector = HybridSelector(
            policy=policy,
            rl_weight=0.6,
            confidence_threshold=0.5,
        )
        candidates = _make_candidates(3, scores=[2.0, 4.0, 1.0])
        _selected, meta = selector.select(candidates, SelectionMethod.HYBRID)
        # RL weight should be reduced: 0.6 * (0.1 / 0.5) = 0.12
        assert meta["rl_weight"] < 0.6

    def test_no_policy_zero_rl_signal(self) -> None:
        """No policy → pure scoring via hybrid path."""
        selector = HybridSelector(
            policy=None,
            rl_weight=0.5,
            confidence_threshold=0.3,
        )
        candidates = _make_candidates(3, scores=[1.0, 4.0, 2.0])
        selected, meta = selector.select(candidates, SelectionMethod.HYBRID)
        assert meta["rl_confidence"] == 0.0
        # With zero RL confidence and threshold > 0, RL weight is reduced to ~0
        assert selected.index == 1  # highest scoring


# ── Degradation levels ───────────────────────────────────────────────────────


class TestDegradation:
    """Test graceful degradation ladder."""

    def test_l0_passes_through(self) -> None:
        selector = HybridSelector(degradation_level=DegradationLevel.L0_FULL)
        result = selector._apply_degradation(SelectionMethod.HYBRID)
        assert result == SelectionMethod.HYBRID

    def test_l1_passes_through(self) -> None:
        selector = HybridSelector(degradation_level=DegradationLevel.L1_REDUCED)
        result = selector._apply_degradation(SelectionMethod.HYBRID)
        assert result == SelectionMethod.HYBRID

    def test_l2_forces_scoring(self) -> None:
        selector = HybridSelector(degradation_level=DegradationLevel.L2_FALLBACK)
        result = selector._apply_degradation(SelectionMethod.HYBRID)
        assert result == SelectionMethod.SCORING_ONLY

    def test_l3_forces_scoring(self) -> None:
        selector = HybridSelector(degradation_level=DegradationLevel.L3_EMERGENCY)
        result = selector._apply_degradation(SelectionMethod.RL_ONLY)
        assert result == SelectionMethod.SCORING_ONLY

    def test_degradation_property_setter(self) -> None:
        selector = HybridSelector(degradation_level=DegradationLevel.L0_FULL)
        assert selector.degradation_level == DegradationLevel.L0_FULL
        selector.degradation_level = DegradationLevel.L2_FALLBACK
        assert selector.degradation_level == DegradationLevel.L2_FALLBACK

    def test_degradation_end_to_end_scoring_only(self) -> None:
        """At L2, even HYBRID method yields SCORING_ONLY behaviour."""
        selector = HybridSelector(
            policy=_make_mock_policy(),
            degradation_level=DegradationLevel.L2_FALLBACK,
        )
        candidates = _make_candidates(3, scores=[1.0, 3.0, 2.0])
        selected, meta = selector.select(candidates, SelectionMethod.HYBRID)
        assert meta["method"] == SelectionMethod.SCORING_ONLY.value
        assert selected.index == 1
