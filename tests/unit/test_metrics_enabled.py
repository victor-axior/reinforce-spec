"""Tests for MetricsCollector with Prometheus *enabled*.

Covers reinforce_spec/_internal/_metrics.py lines 34-124 (metric creation
in __init__) and 153-157, 172-174, 189-190 (record_* enabled paths).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from reinforce_spec._internal._metrics import MetricsCollector


def _make_enabled_collector() -> MetricsCollector:
    """Create a MetricsCollector with mocked prometheus_client."""
    mock_prom = MagicMock()
    # Each call to Counter/Histogram/Gauge must return a unique mock
    mock_prom.Counter.side_effect = lambda *a, **kw: MagicMock(name=f"Counter({a[0]})")
    mock_prom.Histogram.side_effect = lambda *a, **kw: MagicMock(name=f"Histogram({a[0]})")
    mock_prom.Gauge.side_effect = lambda *a, **kw: MagicMock(name=f"Gauge({a[0]})")
    with (
        patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", True),
        patch.dict("sys.modules", {"prometheus_client": mock_prom}),
    ):
        collector = MetricsCollector()
    return collector


class TestMetricsCollectorEnabled:
    """MetricsCollector when prometheus_client is available."""

    def test_enabled_flag(self) -> None:
        c = _make_enabled_collector()
        assert c._enabled is True

    def test_generation_metrics_created(self) -> None:
        c = _make_enabled_collector()
        assert hasattr(c, "generation_requests_total")
        assert hasattr(c, "generation_latency_seconds")
        assert hasattr(c, "candidates_generated")

    def test_scoring_metrics_created(self) -> None:
        c = _make_enabled_collector()
        assert hasattr(c, "composite_score")
        assert hasattr(c, "dimension_scores")
        assert hasattr(c, "judge_calls_total")

    def test_rl_metrics_created(self) -> None:
        c = _make_enabled_collector()
        assert hasattr(c, "rl_reward")
        assert hasattr(c, "replay_buffer_size")
        assert hasattr(c, "policy_train_steps")
        assert hasattr(c, "selection_method_total")

    def test_llm_and_breaker_metrics_created(self) -> None:
        c = _make_enabled_collector()
        assert hasattr(c, "llm_calls_total")
        assert hasattr(c, "llm_latency_seconds")
        assert hasattr(c, "llm_tokens_total")
        assert hasattr(c, "circuit_breaker_state")

    def test_drift_metric_created(self) -> None:
        c = _make_enabled_collector()
        assert hasattr(c, "drift_detected_total")

    # ── record_generation enabled path ─────────────────────────────

    def test_record_generation_enabled(self) -> None:
        c = _make_enabled_collector()
        c.record_generation("enterprise", "success", 1.5, 3)
        c.generation_requests_total.labels.assert_called_with(
            customer_type="enterprise", status="success",
        )
        c.generation_latency_seconds.observe.assert_called_with(1.5)
        c.candidates_generated.observe.assert_called_with(3)

    def test_record_generation_error_status(self) -> None:
        c = _make_enabled_collector()
        c.record_generation("sme", "error", 0.2, 0)
        c.generation_requests_total.labels.assert_called_with(
            customer_type="sme", status="error",
        )

    # ── record_score enabled path ──────────────────────────────────

    def test_record_score_enabled(self) -> None:
        c = _make_enabled_collector()
        c.record_score(4.0, {"accuracy": 4.5, "clarity": 3.5})
        c.composite_score.observe.assert_called_with(4.0)
        assert c.dimension_scores.labels.call_count == 2

    def test_record_score_empty_dimensions(self) -> None:
        c = _make_enabled_collector()
        c.record_score(0.0, {})
        c.composite_score.observe.assert_called_with(0.0)
        c.dimension_scores.labels.assert_not_called()

    # ── record_rl_step enabled path ────────────────────────────────

    def test_record_rl_step_enabled(self) -> None:
        c = _make_enabled_collector()
        c.record_rl_step(3.0, "hybrid")
        c.rl_reward.observe.assert_called_with(3.0)
        c.selection_method_total.labels.assert_called_with(method="hybrid")

    def test_record_rl_step_different_method(self) -> None:
        c = _make_enabled_collector()
        c.record_rl_step(0.5, "scoring_only")
        c.selection_method_total.labels.assert_called_with(method="scoring_only")


class TestMetricsCollectorDisabled:
    """Ensure disabled path short-circuits."""

    def test_disabled_no_metrics(self) -> None:
        with patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False):
            c = MetricsCollector()
        assert c._enabled is False
        assert not hasattr(c, "generation_requests_total")

    def test_record_generation_noop(self) -> None:
        with patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False):
            c = MetricsCollector()
        c.record_generation("x", "y", 0, 0)  # should not raise

    def test_record_score_noop(self) -> None:
        with patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False):
            c = MetricsCollector()
        c.record_score(0.0, {})

    def test_record_rl_step_noop(self) -> None:
        with patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False):
            c = MetricsCollector()
        c.record_rl_step(0.0, "x")
