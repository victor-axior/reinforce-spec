"""Prometheus metrics collector.

Defines application-level metrics for monitoring the generation pipeline,
scoring subsystem, and RL policy performance.

Metrics are only registered if ``prometheus_client`` is installed.
"""

from __future__ import annotations

from loguru import logger

from reinforce_spec._compat import PROMETHEUS_AVAILABLE


class MetricsCollector:
    """Application metrics.

    Safe no-op when prometheus_client is not installed.
    """

    def __init__(self) -> None:
        """Initialize metrics collector.

        Registers Prometheus counters, histograms, and gauges when
        ``prometheus_client`` is installed.  Otherwise operates as a
        silent no-op.
        """
        self._enabled = PROMETHEUS_AVAILABLE
        if not self._enabled:
            logger.debug("prometheus_not_installed_metrics_disabled")
            return

        from prometheus_client import Counter, Gauge, Histogram  # type: ignore[import-untyped]

        # ── Generation metrics ────────────────────────────────────────
        self.generation_requests_total = Counter(
            "reinforce_spec_generation_requests_total",
            "Total generation requests",
            ["customer_type", "status"],
        )

        self.generation_latency_seconds = Histogram(
            "reinforce_spec_generation_latency_seconds",
            "End-to-end generation latency",
            buckets=[1, 2, 5, 10, 20, 30, 60, 120],
        )

        self.candidates_generated = Histogram(
            "reinforce_spec_candidates_generated",
            "Number of candidates generated per request",
            buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        )

        # ── Scoring metrics ───────────────────────────────────────────
        self.composite_score = Histogram(
            "reinforce_spec_composite_score",
            "Distribution of composite enterprise scores",
            buckets=[1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        )

        self.dimension_scores = Histogram(
            "reinforce_spec_dimension_score",
            "Per-dimension scores",
            ["dimension"],
            buckets=[1.0, 2.0, 3.0, 4.0, 5.0],
        )

        self.judge_calls_total = Counter(
            "reinforce_spec_judge_calls_total",
            "Total LLM judge calls",
            ["model", "status"],
        )

        # ── RL metrics ────────────────────────────────────────────────
        self.rl_reward = Histogram(
            "reinforce_spec_rl_reward",
            "RL reward distribution",
            buckets=[0, 1, 2, 3, 4, 5],
        )

        self.replay_buffer_size = Gauge(
            "reinforce_spec_replay_buffer_size",
            "Current replay buffer size",
        )

        self.policy_train_steps = Counter(
            "reinforce_spec_policy_train_steps_total",
            "Total policy training steps",
        )

        self.selection_method_total = Counter(
            "reinforce_spec_selection_method_total",
            "Selection method usage",
            ["method"],
        )

        # ── LLM client metrics ───────────────────────────────────────
        self.llm_calls_total = Counter(
            "reinforce_spec_llm_calls_total",
            "Total LLM API calls",
            ["model", "status"],
        )

        self.llm_latency_seconds = Histogram(
            "reinforce_spec_llm_latency_seconds",
            "LLM call latency",
            ["model"],
            buckets=[0.5, 1, 2, 5, 10, 20, 30],
        )

        self.llm_tokens_total = Counter(
            "reinforce_spec_llm_tokens_total",
            "Total tokens consumed",
            ["model", "direction"],  # direction: prompt/completion
        )

        self.circuit_breaker_state = Gauge(
            "reinforce_spec_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half_open)",
        )

        # ── Drift metrics ────────────────────────────────────────────
        self.drift_detected_total = Counter(
            "reinforce_spec_drift_detected_total",
            "Number of drift detections",
            ["test"],
        )

    def record_generation(
        self,
        customer_type: str,
        status: str,
        latency_s: float,
        n_candidates: int,
    ) -> None:
        """Record a generation request.

        Parameters
        ----------
        customer_type : str
            Enterprise customer archetype.
        status : str
            Request outcome (e.g. ``'success'``, ``'error'``).
        latency_s : float
            End-to-end latency in seconds.
        n_candidates : int
            Number of candidates generated.

        """
        if not self._enabled:
            return
        self.generation_requests_total.labels(
            customer_type=customer_type, status=status
        ).inc()
        self.generation_latency_seconds.observe(latency_s)
        self.candidates_generated.observe(n_candidates)

    def record_score(self, composite: float, dimension_scores: dict[str, float]) -> None:
        """Record scoring results.

        Parameters
        ----------
        composite : float
            Aggregate composite score.
        dimension_scores : dict[str, float]
            Per-dimension score mapping.

        """
        if not self._enabled:
            return
        self.composite_score.observe(composite)
        for dim, score in dimension_scores.items():
            self.dimension_scores.labels(dimension=dim).observe(score)

    def record_rl_step(self, reward: float, method: str) -> None:
        """Record an RL selection step.

        Parameters
        ----------
        reward : float
            Reward signal received.
        method : str
            Selection method used (e.g. ``'hybrid'``).

        """
        if not self._enabled:
            return
        self.rl_reward.observe(reward)
        self.selection_method_total.labels(method=method).inc()


# Singleton
metrics = MetricsCollector()

__all__ = ["MetricsCollector", "metrics"]
