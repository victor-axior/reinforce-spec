"""Statistical tests for score distribution properties.

These tests verify statistical properties that should hold over many
runs.  They are intentionally non-deterministic and should be run
nightly (not on every PR).
"""

from __future__ import annotations

import numpy as np
import pytest

from reinforce_spec._internal._drift import DriftDetector


@pytest.mark.statistical()
class TestPSIStatistics:
    """Test PSI estimator statistical properties."""

    def test_psi_zero_for_identical_samples(self) -> None:
        """PSI should be near zero when sampling from the same distribution."""
        rng = np.random.default_rng(42)
        detector = DriftDetector(window_size=1000, n_bins=10)

        ref = rng.normal(3.0, 1.0, size=5000).tolist()
        detector.set_reference(ref)

        # Draw from the same distribution
        current = rng.normal(3.0, 1.0, size=1000).tolist()
        detector.add_scores(current)

        results = detector.check_drift()
        psi = next(r for r in results if r.test_name == "PSI")
        # PSI should be very small (<0.1) for identical distributions
        assert psi.statistic < 0.1

    def test_psi_increases_with_shift(self) -> None:
        """PSI should increase monotonically with distribution shift."""
        rng = np.random.default_rng(42)
        psi_values: list[float] = []

        for shift in [0.0, 0.5, 1.0, 1.5, 2.0]:
            detector = DriftDetector(window_size=1000, n_bins=10)

            ref = rng.normal(3.0, 1.0, size=5000).tolist()
            detector.set_reference(ref)

            current = rng.normal(3.0 + shift, 1.0, size=1000).tolist()
            detector.add_scores(current)

            results = detector.check_drift()
            psi = next(r for r in results if r.test_name == "PSI")
            psi_values.append(psi.statistic)

        # PSI should be monotonically increasing with shift
        for i in range(1, len(psi_values)):
            assert psi_values[i] >= psi_values[i - 1] - 0.01  # small tolerance


@pytest.mark.statistical()
class TestReplayBufferSampling:
    """Test that PER sampling maintains expected statistical properties."""

    def test_high_priority_sampled_more_often(self) -> None:
        """Higher-priority transitions should be sampled more frequently."""
        from reinforce_spec._internal._replay_buffer import (
            PrioritizedReplayBuffer,
            Transition,
        )

        buf = PrioritizedReplayBuffer(capacity=100, alpha=0.6, beta_start=1.0)
        for i in range(50):
            t = Transition(
                observation=np.zeros(10, dtype=np.float32),
                action=i % 5,
                reward=float(i),
                next_observation=np.zeros(10, dtype=np.float32),
                done=False,
            )
            # Give first 10 transitions very high priority
            td_error = 100.0 if i < 10 else 1.0
            buf.add(t, td_error=td_error)

        # Sample many times and count how often high-priority items appear
        high_count = 0
        total_samples = 1000
        for _ in range(total_samples):
            transitions, _, _ = buf.sample(batch_size=1)
            if transitions[0].reward < 10:  # First 10 transitions
                high_count += 1

        # High-priority items should be sampled >50% of the time
        assert high_count / total_samples > 0.3
