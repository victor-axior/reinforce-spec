"""Behavioral tests for drift detection invariants."""

from __future__ import annotations

import numpy as np
import pytest

from reinforce_spec._internal._drift import DriftDetector


@pytest.mark.behavioral()
class TestDriftDetectionInvariants:
    """Verify that drift detection preserves expected semantics."""

    def test_identical_distributions_never_drift(self) -> None:
        """Same distribution as reference should never trigger drift."""
        rng = np.random.default_rng(123)
        detector = DriftDetector(window_size=500, psi_threshold=0.2)

        ref = rng.normal(3.0, 0.5, size=1000).tolist()
        detector.set_reference(ref)

        current = rng.normal(3.0, 0.5, size=500).tolist()
        detector.add_scores(current)

        results = detector.check_drift()
        # PSI should not be drifted for identical distributions
        psi = next(r for r in results if r.test_name == "PSI")
        assert psi.is_drifted is False

    def test_large_shift_always_detected(self) -> None:
        """A 3-sigma mean shift must always be detected."""
        rng = np.random.default_rng(456)
        detector = DriftDetector(window_size=500)

        ref = rng.normal(3.0, 0.5, size=1000).tolist()
        detector.set_reference(ref)

        # 3-sigma shift: mean 3.0 + 3*0.5 = 4.5
        shifted = rng.normal(4.5, 0.5, size=500).tolist()
        detector.add_scores(shifted)

        results = detector.check_drift()
        assert any(r.is_drifted for r in results)

    def test_drift_count_monotonically_increases(self) -> None:
        """Drift count should only increase, never decrease."""
        rng = np.random.default_rng(789)
        detector = DriftDetector(window_size=100)

        ref = rng.normal(3.0, 0.5, size=200).tolist()
        detector.set_reference(ref)

        prev_count = detector.drift_count
        for _ in range(5):
            shifted = rng.normal(5.0, 0.5, size=100).tolist()
            detector._current.clear()
            detector.add_scores(shifted)
            detector.check_drift()
            assert detector.drift_count >= prev_count
            prev_count = detector.drift_count
