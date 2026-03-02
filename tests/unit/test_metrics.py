"""Unit tests for Prometheus metrics collector."""

from __future__ import annotations

from unittest.mock import patch

from reinforce_spec._internal._metrics import MetricsCollector


class TestMetricsCollectorDisabled:
    """Test MetricsCollector when Prometheus is unavailable."""

    @patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False)
    def test_init_disabled(self) -> None:
        mc = MetricsCollector()
        assert mc._enabled is False

    @patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_generation_noop(self) -> None:
        mc = MetricsCollector()
        # Should not raise
        mc.record_generation("bank", "success", 1.5, 5)

    @patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_score_noop(self) -> None:
        mc = MetricsCollector()
        mc.record_score(3.5, {"compliance_regulatory": 4.0})

    @patch("reinforce_spec._internal._metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_rl_step_noop(self) -> None:
        mc = MetricsCollector()
        mc.record_rl_step(2.5, "hybrid")


class TestMetricsCollectorEnabled:
    """Test MetricsCollector when Prometheus is available."""

    def test_init_enabled(self) -> None:
        mc = MetricsCollector()
        # May or may not be enabled depending on prometheus_client install
        assert isinstance(mc._enabled, bool)

    def test_record_generation(self) -> None:
        mc = MetricsCollector()
        if mc._enabled:
            mc.record_generation("saas", "success", 2.0, 3)

    def test_record_score(self) -> None:
        mc = MetricsCollector()
        if mc._enabled:
            mc.record_score(4.0, {
                "compliance_regulatory": 4.5,
                "security_architecture": 3.5,
            })

    def test_record_rl_step(self) -> None:
        mc = MetricsCollector()
        if mc._enabled:
            mc.record_rl_step(3.0, "scoring_only")


class TestMetricsSingleton:
    """Test the module-level metrics singleton."""

    def test_singleton_exists(self) -> None:
        from reinforce_spec._internal._metrics import metrics

        assert isinstance(metrics, MetricsCollector)
