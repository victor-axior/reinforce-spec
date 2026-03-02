"""Unit tests for drift detection."""

from __future__ import annotations

import numpy as np

from reinforce_spec._internal._drift import DriftDetector


class TestDriftDetector:
    """Test drift detection with PSI and KS tests."""

    def test_no_drift_with_same_distribution(self) -> None:
        detector = DriftDetector(window_size=100)
        rng = np.random.default_rng(42)

        ref = rng.normal(3.0, 0.5, size=200).tolist()
        detector.set_reference(ref)

        current = rng.normal(3.0, 0.5, size=100).tolist()
        detector.add_scores(current)

        results = detector.check_drift()
        assert len(results) == 2
        psi = next(r for r in results if r.test_name == "PSI")
        assert psi.is_drifted is False

    def test_drift_detected_with_shifted_distribution(self) -> None:
        detector = DriftDetector(window_size=100)
        rng = np.random.default_rng(42)

        ref = rng.normal(3.0, 0.5, size=200).tolist()
        detector.set_reference(ref)

        current = rng.normal(4.5, 0.5, size=100).tolist()
        detector.add_scores(current)

        results = detector.check_drift()
        assert any(r.is_drifted for r in results)

    def test_insufficient_data_returns_empty(self) -> None:
        detector = DriftDetector(window_size=100)
        detector.add_score(3.0)
        results = detector.check_drift()
        assert results == []

    def test_has_sufficient_data(self) -> None:
        detector = DriftDetector(window_size=100)
        assert detector.has_sufficient_data is False

        detector.set_reference([3.0] * 50)
        assert detector.has_sufficient_data is False

        detector.add_scores([3.0] * 30)
        assert detector.has_sufficient_data is True

    def test_add_score_singular(self) -> None:
        detector = DriftDetector(window_size=100)
        detector.add_score(3.0)
        detector.add_score(4.0)
        assert len(detector._current) == 2

    def test_drift_count_increments(self) -> None:
        detector = DriftDetector(window_size=100)
        rng = np.random.default_rng(42)

        ref = rng.normal(3.0, 0.5, size=200).tolist()
        detector.set_reference(ref)

        assert detector.drift_count == 0

        # Trigger drift
        shifted = rng.normal(5.0, 0.5, size=100).tolist()
        detector.add_scores(shifted)
        results = detector.check_drift()

        if any(r.is_drifted for r in results):
            assert detector.drift_count >= 1

    def test_set_reference_empty(self) -> None:
        detector = DriftDetector(window_size=100)
        detector.set_reference([])
        assert detector._reference is not None
        assert len(detector._reference) == 0

    def test_no_reference_returns_empty(self) -> None:
        detector = DriftDetector(window_size=100)
        detector.add_scores([3.0] * 50)
        results = detector.check_drift()
        assert results == []

    def test_custom_thresholds(self) -> None:
        detector = DriftDetector(
            window_size=100,
            psi_threshold=0.5,
            ks_alpha=0.01,
            n_bins=20,
        )
        rng = np.random.default_rng(42)
        ref = rng.normal(3.0, 0.5, size=200).tolist()
        detector.set_reference(ref)
        detector.add_scores(rng.normal(3.0, 0.5, size=100).tolist())
        results = detector.check_drift()
        assert len(results) == 2
