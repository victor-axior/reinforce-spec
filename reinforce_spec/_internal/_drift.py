"""Score distribution drift detection.

Monitors for covariate shift between training and production score
distributions using statistical tests:

  - **PSI (Population Stability Index)**: measures distributional divergence
    between reference and current score distributions.
  - **KS test (Kolmogorov–Smirnov)**: non-parametric test for distributional
    difference.

When drift is detected beyond configurable thresholds, signals the system to
retrain or raise an alert.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from typing import Any

import numpy as np
from loguru import logger


@dataclasses.dataclass(frozen=True, slots=True)
class DriftResult:
    """Result from a drift detection test."""

    test_name: str
    statistic: float
    threshold: float
    is_drifted: bool
    p_value: float | None = None
    details: dict[str, Any] = dataclasses.field(default_factory=dict)


class DriftDetector:
    """Monitor score distributions for drift.

    Parameters
    ----------
    window_size : int
        Number of recent scores to keep in the sliding window.
    psi_threshold : float
        PSI above which drift is flagged (default 0.2 = moderate shift).
    ks_alpha : float
        Significance level for KS test (default 0.05).
    n_bins : int
        Number of bins for PSI histogram computation.

    """

    def __init__(
        self,
        window_size: int = 500,
        psi_threshold: float = 0.2,
        ks_alpha: float = 0.05,
        n_bins: int = 10,
    ) -> None:
        self._window_size = window_size
        self._psi_threshold = psi_threshold
        self._ks_alpha = ks_alpha
        self._n_bins = n_bins

        self._reference: np.ndarray | None = None
        self._current: deque[float] = deque(maxlen=window_size)
        self._drift_count: int = 0

    def set_reference(self, scores: list[float] | np.ndarray) -> None:
        """Set the reference (training) distribution.

        Parameters
        ----------
        scores : list[float] or np.ndarray
            Score values from the training distribution.

        """
        self._reference = np.array(scores, dtype=np.float64)
        logger.info(
            "drift_reference_set | n_samples={n_samples} mean={mean} std={std}",
            n_samples=len(self._reference),
            mean=round(float(np.mean(self._reference)), 3),
            std=round(float(np.std(self._reference)), 3),
        )

    def add_score(self, score: float) -> None:
        """Add a new production score observation.

        Parameters
        ----------
        score : float
            Observed score value.

        """
        self._current.append(score)

    def add_scores(self, scores: list[float]) -> None:
        """Add multiple production score observations.

        Parameters
        ----------
        scores : list[float]
            Observed score values.

        """
        self._current.extend(scores)

    def check_drift(self) -> list[DriftResult]:
        """Run all drift detection tests.

        Returns
        -------
        list[DriftResult]
            One result per test (PSI, KS). Empty if insufficient data.

        """
        if self._reference is None or len(self._current) < 30:
            return []

        current = np.array(self._current)
        results: list[DriftResult] = []

        # PSI
        psi_result = self._compute_psi(self._reference, current)
        results.append(psi_result)

        # KS test
        ks_result = self._compute_ks(self._reference, current)
        results.append(ks_result)

        # Log if any drift detected
        if any(r.is_drifted for r in results):
            self._drift_count += 1
            logger.warning(
                "drift_detected | tests={tests} drift_count={drift_count}",
                tests=[r.test_name for r in results if r.is_drifted],
                drift_count=self._drift_count,
            )

        return results

    @property
    def drift_count(self) -> int:
        """Return cumulative number of drift alerts."""
        return self._drift_count

    @property
    def has_sufficient_data(self) -> bool:
        """Return ``True`` when enough data exists for drift checks."""
        return self._reference is not None and len(self._current) >= 30

    def _compute_psi(
        self,
        reference: np.ndarray,
        current: np.ndarray,
    ) -> DriftResult:
        """Compute Population Stability Index."""
        # Define bin edges from combined data
        combined = np.concatenate([reference, current])
        bin_edges = np.linspace(
            float(np.min(combined)) - 0.01,
            float(np.max(combined)) + 0.01,
            self._n_bins + 1,
        )

        # Compute histograms (proportions)
        ref_counts, _ = np.histogram(reference, bins=bin_edges)
        cur_counts, _ = np.histogram(current, bins=bin_edges)

        # Normalize to proportions with Laplace smoothing
        ref_props = (ref_counts + 1e-4) / (len(reference) + 1e-4 * self._n_bins)
        cur_props = (cur_counts + 1e-4) / (len(current) + 1e-4 * self._n_bins)

        # PSI = Σ (p_i - q_i) · ln(p_i / q_i)
        psi = float(np.sum((cur_props - ref_props) * np.log(cur_props / ref_props)))

        return DriftResult(
            test_name="PSI",
            statistic=round(psi, 4),
            threshold=self._psi_threshold,
            is_drifted=psi > self._psi_threshold,
            details={
                "interpretation": (
                    "no_shift"
                    if psi < 0.1
                    else "moderate_shift"
                    if psi < 0.25
                    else "significant_shift"
                ),
            },
        )

    def _compute_ks(
        self,
        reference: np.ndarray,
        current: np.ndarray,
    ) -> DriftResult:
        """Compute Kolmogorov–Smirnov test statistic."""
        # Sort both distributions
        ref_sorted = np.sort(reference)
        cur_sorted = np.sort(current)

        # Combine and compute empirical CDFs
        all_values = np.concatenate([ref_sorted, cur_sorted])
        all_values.sort()

        ref_cdf = np.searchsorted(ref_sorted, all_values, side="right") / len(reference)
        cur_cdf = np.searchsorted(cur_sorted, all_values, side="right") / len(current)

        ks_stat = float(np.max(np.abs(ref_cdf - cur_cdf)))

        # Critical value approximation (two-sample KS)
        n_eff = len(reference) * len(current) / (len(reference) + len(current))
        # Asymptotic p-value approximation
        lam = (np.sqrt(n_eff) + 0.12 + 0.11 / np.sqrt(n_eff)) * ks_stat
        # Survival function of Kolmogorov distribution (first term approx)
        p_value = float(2 * np.exp(-2 * lam**2))
        p_value = max(0.0, min(1.0, p_value))

        return DriftResult(
            test_name="KS",
            statistic=round(ks_stat, 4),
            threshold=self._ks_alpha,
            is_drifted=p_value < self._ks_alpha,
            p_value=round(p_value, 4),
        )


__all__ = ["DriftDetector", "DriftResult"]
