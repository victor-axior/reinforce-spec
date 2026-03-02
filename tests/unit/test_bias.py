"""Unit tests for bias detection and mitigation."""

from __future__ import annotations

import pytest

from reinforce_spec._internal._bias import (
    BiasDetector,
    PairwiseComparison,
    aggregate_scores_trimmed_mean,
    check_self_enhancement_risk,
)


class TestPairwiseComparison:
    """Test pairwise comparison position-bias detection."""

    def test_consistent_result(self) -> None:
        # A wins in both orderings
        pc = PairwiseComparison(
            spec_a_index=0,
            spec_b_index=1,
            a_preferred_forward=True,
            b_preferred_forward=False,
            a_preferred_reversed=True,
            b_preferred_reversed=False,
        )
        assert pc.is_consistent is True
        assert pc.winner_index == 0
        assert pc.confidence == 1.0

    def test_inconsistent_result(self) -> None:
        # A wins when shown first, B wins when B shown first (position bias)
        pc = PairwiseComparison(
            spec_a_index=0,
            spec_b_index=1,
            a_preferred_forward=True,
            b_preferred_forward=False,
            a_preferred_reversed=False,
            b_preferred_reversed=True,
        )
        assert pc.is_consistent is False
        assert pc.winner_index is None
        assert pc.confidence == 0.0

    def test_b_wins_consistently(self) -> None:
        pc = PairwiseComparison(
            spec_a_index=0,
            spec_b_index=1,
            a_preferred_forward=False,
            b_preferred_forward=True,
            a_preferred_reversed=False,
            b_preferred_reversed=True,
        )
        assert pc.is_consistent is True
        assert pc.winner_index == 1
        assert pc.confidence == 1.0


class TestBiasDetector:
    """Test session-level bias detection."""

    def test_record_score(self) -> None:
        bd = BiasDetector()
        bd.record_score(3.5, 500)
        bd.record_score(4.0, 600)
        assert len(bd._session_scores) == 2
        assert len(bd._session_lengths) == 2

    def test_check_leniency_drift_insufficient_data(self) -> None:
        bd = BiasDetector()
        for i in range(5):
            bd.record_score(3.0 + i * 0.1, 500)
        result = bd.check_leniency_drift(window_size=10)
        assert result is None

    def test_check_leniency_drift_no_drift(self) -> None:
        bd = BiasDetector()
        for _ in range(10):
            bd.record_score(3.0, 500)
        slope = bd.check_leniency_drift(window_size=10)
        assert slope is not None
        assert slope == pytest.approx(0.0, abs=0.01)

    def test_check_leniency_drift_positive(self) -> None:
        bd = BiasDetector()
        for i in range(10):
            bd.record_score(2.0 + i * 0.3, 500)
        slope = bd.check_leniency_drift(window_size=10)
        assert slope is not None
        assert slope > 0

    def test_check_verbosity_correlation_insufficient(self) -> None:
        bd = BiasDetector()
        bd.record_score(3.0, 500)
        result = bd.check_verbosity_correlation(min_samples=5)
        assert result is None

    def test_check_verbosity_correlation_no_correlation(self) -> None:
        bd = BiasDetector()
        # No relationship between length and score
        scores_lengths = [(3.0, 100), (3.0, 200), (3.0, 300), (3.0, 400), (3.0, 500)]
        for score, length in scores_lengths:
            bd.record_score(score, length)
        corr = bd.check_verbosity_correlation(min_samples=5)
        assert corr is not None
        assert corr == pytest.approx(0.0, abs=0.01)

    def test_check_verbosity_correlation_positive(self) -> None:
        bd = BiasDetector()
        # Perfect positive correlation: longer = higher score
        for i in range(10):
            bd.record_score(1.0 + i * 0.4, 100 + i * 100)
        corr = bd.check_verbosity_correlation(min_samples=5)
        assert corr is not None
        assert corr > 0.9

    def test_reset_session(self) -> None:
        bd = BiasDetector()
        bd.record_score(3.0, 500)
        bd.record_score(4.0, 600)
        bd.reset_session()
        assert len(bd._session_scores) == 0
        assert len(bd._session_lengths) == 0


class TestCheckSelfEnhancementRisk:
    """Test self-enhancement risk detection."""

    def test_same_provider_with_slash(self) -> None:
        assert check_self_enhancement_risk("openai/gpt-4o", "openai/gpt-3.5-turbo") is True

    def test_different_provider(self) -> None:
        assert check_self_enhancement_risk("anthropic/claude-3.5", "openai/gpt-4o") is False

    def test_same_provider_no_slash(self) -> None:
        # Without slash, entire string is used as provider
        # "gpt-4o" != "gpt-3.5-turbo" — different full strings
        assert check_self_enhancement_risk("gpt-4o", "gpt-3.5-turbo") is False

    def test_same_string_no_slash(self) -> None:
        # Exact same model string → same family
        assert check_self_enhancement_risk("gpt-4o", "gpt-4o") is True

    def test_mixed_format(self) -> None:
        # One with slash, one without
        assert check_self_enhancement_risk("openai/gpt-4o", "gpt-4o") is False

    def test_case_insensitive(self) -> None:
        assert check_self_enhancement_risk("OpenAI/gpt-4o", "openai/gpt-3.5") is True


class TestAggregateScoresTrimmedMean:
    """Test trimmed mean aggregation."""

    def test_empty_input(self) -> None:
        assert aggregate_scores_trimmed_mean([]) == {}

    def test_single_judge(self) -> None:
        result = aggregate_scores_trimmed_mean([{"compliance_regulatory": 3.5}])
        assert result == {"compliance_regulatory": 3.5}

    def test_two_judges_no_trim(self) -> None:
        result = aggregate_scores_trimmed_mean([
            {"compliance_regulatory": 3.0},
            {"compliance_regulatory": 5.0},
        ])
        assert result["compliance_regulatory"] == pytest.approx(4.0)

    def test_three_judges_with_trim(self) -> None:
        result = aggregate_scores_trimmed_mean(
            [
                {"compliance_regulatory": 1.0},  # trimmed
                {"compliance_regulatory": 3.0},
                {"compliance_regulatory": 5.0},  # trimmed
            ],
            trim_fraction=0.3,
        )
        # After trimming top and bottom 1, only middle value remains
        assert result["compliance_regulatory"] == pytest.approx(3.0)

    def test_multiple_dimensions(self) -> None:
        result = aggregate_scores_trimmed_mean([
            {"compliance_regulatory": 3.0, "security_architecture": 4.0},
            {"compliance_regulatory": 4.0, "security_architecture": 2.0},
        ])
        assert result["compliance_regulatory"] == pytest.approx(3.5)
        assert result["security_architecture"] == pytest.approx(3.0)

    def test_no_trim_for_small_set(self) -> None:
        # With 2 judges and trim_fraction=0.3, trim_count=0 so no trimming
        result = aggregate_scores_trimmed_mean(
            [
                {"compliance_regulatory": 2.0},
                {"compliance_regulatory": 4.0},
            ],
            trim_fraction=0.3,
        )
        assert result["compliance_regulatory"] == pytest.approx(3.0)
