"""Behavioral tests for scoring invariants.

These tests verify business rules that must always hold, regardless of
the implementation details.
"""

from __future__ import annotations

import pytest

from reinforce_spec.types import CandidateSpec, DimensionScore


@pytest.mark.behavioral()
class TestScoringInvariants:
    """Verify that scoring preserves expected ordering and bounds."""

    def test_higher_quality_spec_scores_higher(self) -> None:
        """A clearly better spec should always score above a minimal one."""
        excellent = CandidateSpec(
            index=0,
            content="# Comprehensive API Design\n" * 50,
            spec_type="api",
            composite_score=4.5,
            dimension_scores=[DimensionScore(dimension=f"dim_{i}", score=4.5) for i in range(12)],
        )
        minimal = CandidateSpec(
            index=1,
            content="Do something.",
            spec_type="srs",
            composite_score=1.2,
            dimension_scores=[DimensionScore(dimension=f"dim_{i}", score=1.2) for i in range(12)],
        )
        assert excellent.composite_score > minimal.composite_score

    def test_composite_score_within_bounds(self) -> None:
        """Composite scores must always be in [0, 5]."""
        for score in [0.0, 1.0, 2.5, 3.0, 4.5, 5.0]:
            c = CandidateSpec(
                index=0,
                content="Test spec content",
                composite_score=score,
            )
            assert 0.0 <= c.composite_score <= 5.0

    def test_dimension_count_always_twelve(self) -> None:
        """We must always have exactly 12 dimensions."""
        from reinforce_spec._internal._rubric import get_all_dimensions

        dims = get_all_dimensions()
        assert len(dims) == 12


@pytest.mark.behavioral()
class TestSelectionInvariants:
    """Verify selection business rules."""

    def test_at_least_two_candidates_required(self) -> None:
        """The system must reject fewer than 2 candidates."""
        from pydantic import ValidationError

        from reinforce_spec.types import SelectionRequest

        with pytest.raises(ValidationError):
            SelectionRequest(
                candidates=[
                    CandidateSpec(content="Only one"),
                ]
            )

    def test_scoring_weights_always_sum_to_one(self) -> None:
        """Weights must always sum to 1.0 (±0.01)."""
        from reinforce_spec.scoring.presets import get_preset, list_presets

        for name in list_presets():
            preset = get_preset(name)
            total = sum(preset.as_dict().values())
            assert abs(total - 1.0) < 0.01, f"{name}: weights sum to {total}"
