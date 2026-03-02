"""Bias mitigation strategies for LLM-as-judge scoring.

Addresses:
- Position bias: evaluate pairs in both orders, discard if flipped
- Verbosity bias: normalize scores against length
- Self-enhancement bias: prevent model from judging own outputs
- Leniency drift: detect within-session score inflation
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from loguru import logger


@dataclass
class PairwiseComparison:
    """Result of comparing two specs in both position orders."""

    spec_a_index: int
    spec_b_index: int
    a_preferred_forward: bool  # A preferred when A shown first
    b_preferred_forward: bool  # B preferred when A shown first (i.e., B wins)
    a_preferred_reversed: bool  # A preferred when B shown first
    b_preferred_reversed: bool  # B preferred when B shown first (i.e., A wins)
    is_consistent: bool = False  # same winner in both orders
    winner_index: int | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        # Forward: who won?
        forward_winner = self.spec_a_index if self.a_preferred_forward else self.spec_b_index
        # Reversed: who won?
        reverse_winner = self.spec_a_index if self.a_preferred_reversed else self.spec_b_index

        self.is_consistent = forward_winner == reverse_winner
        if self.is_consistent:
            self.winner_index = forward_winner
            self.confidence = 1.0
        else:
            # Position bias detected — inconclusive
            self.winner_index = None
            self.confidence = 0.0
            logger.info(
                "position_bias_detected | spec_a={spec_a} spec_b={spec_b}",
                spec_a=self.spec_a_index,
                spec_b=self.spec_b_index,
            )


class BiasDetector:
    """Detects and reports various biases in scoring sessions."""

    def __init__(self) -> None:
        """Initialize the detector with empty session history."""
        self._session_scores: list[float] = []
        self._session_lengths: list[int] = []

    def record_score(self, composite_score: float, spec_length: int) -> None:
        """Record a score for session-level drift detection.

        Parameters
        ----------
        composite_score : float
            Weighted composite score for the candidate.
        spec_length : int
            Character length of the spec content.

        """
        self._session_scores.append(composite_score)
        self._session_lengths.append(spec_length)

    def check_leniency_drift(self, window_size: int = 10) -> float | None:
        """Check if scores are inflating over the session.

        Parameters
        ----------
        window_size : int
            Number of recent scores to include in the regression.

        Returns
        -------
        float or None
            Slope of a linear regression over the last *window_size*
            scores.  Positive slope indicates leniency drift.  Returns
            ``None`` if insufficient data.

        """
        if len(self._session_scores) < window_size:
            return None

        recent = self._session_scores[-window_size:]
        n = len(recent)
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(recent)

        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        return slope

    def check_verbosity_correlation(self, min_samples: int = 5) -> float | None:
        """Check correlation between spec length and score.

        Parameters
        ----------
        min_samples : int
            Minimum number of samples required to compute the
            correlation.

        Returns
        -------
        float or None
            Pearson correlation coefficient.  Values above ``0.5``
            suggest verbosity bias (longer specs scored higher
            regardless of quality).  Returns ``None`` if insufficient
            data.

        """
        if len(self._session_scores) < min_samples:
            return None

        scores = self._session_scores[-min_samples:]
        lengths = [float(x) for x in self._session_lengths[-min_samples:]]

        mean_s = statistics.mean(scores)
        mean_l = statistics.mean(lengths)

        cov = sum((s - mean_s) * (l - mean_l) for s, l in zip(scores, lengths))
        std_s = statistics.stdev(scores) if len(scores) > 1 else 1.0
        std_l = statistics.stdev(lengths) if len(lengths) > 1 else 1.0

        if std_s == 0 or std_l == 0:
            return 0.0

        n = len(scores)
        return cov / ((n - 1) * std_s * std_l)

    def reset_session(self) -> None:
        """Reset session tracking."""
        self._session_scores.clear()
        self._session_lengths.clear()


def check_self_enhancement_risk(
    judge_model: str,
    source_model: str,
) -> bool:
    """Check if a judge model might exhibit self-enhancement bias.

    Parameters
    ----------
    judge_model : str
        Model identifier for the judge (e.g.
        ``"anthropic/claude-3.5-sonnet"``).
    source_model : str
        Model identifier that generated the spec.

    Returns
    -------
    bool
        ``True`` if the judge and source model are from the same
        provider family, which risks inflated scores.

    """
    # Extract provider from model strings like "anthropic/claude-3.5-sonnet"
    judge_provider = judge_model.split("/")[0].lower() if "/" in judge_model else judge_model.lower()
    gen_provider = (
        source_model.split("/")[0].lower()
        if "/" in source_model
        else source_model.lower()
    )

    is_same_family = judge_provider == gen_provider

    if is_same_family:
        logger.warning(
            "self_enhancement_risk | judge_model={judge_model} source_model={source_model} message={message}",
            judge_model=judge_model,
            source_model=source_model,
            message="Judge and source are from the same model family",
        )

    return is_same_family


def aggregate_scores_trimmed_mean(
    scores_per_judge: list[dict[str, float]],
    trim_fraction: float = 0.0,
) -> dict[str, float]:
    """Aggregate scores from multiple judges using trimmed mean.

    Parameters
    ----------
    scores_per_judge : list[dict[str, float]]
        List of ``{dimension_key: score}`` dicts, one per judge.
    trim_fraction : float
        Fraction of extreme values to trim from each end.
        ``0.0`` = regular mean, ``0.25`` = drop top and bottom 25%.

    Returns
    -------
    dict[str, float]
        Aggregated ``{dimension_key: trimmed_mean_score}``.

    """
    if not scores_per_judge:
        return {}

    if len(scores_per_judge) == 1:
        return scores_per_judge[0].copy()

    dimensions = set()
    for s in scores_per_judge:
        dimensions.update(s.keys())

    aggregated: dict[str, float] = {}
    for dim in dimensions:
        values = sorted(s[dim] for s in scores_per_judge if dim in s)
        if not values:
            continue

        if len(values) >= 3 and trim_fraction > 0:
            trim_count = max(1, int(len(values) * trim_fraction))
            trimmed = values[trim_count:-trim_count] if trim_count < len(values) // 2 else values
        else:
            trimmed = values

        aggregated[dim] = sum(trimmed) / len(trimmed)

    return aggregated
