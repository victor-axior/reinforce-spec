"""Observability package.

Provides production monitoring primitives:
  - ``metrics`` — Prometheus counters, histograms, gauges
  - ``experiment`` — MLflow experiment tracking
  - ``audit`` — Structured audit logging
"""

from __future__ import annotations

__all__ = [
    "AuditLogger",
    "ExperimentTracker",
    "MetricsCollector",
]


def __getattr__(name: str) -> object:
    if name == "MetricsCollector":
        from reinforce_spec.observability.metrics import MetricsCollector

        return MetricsCollector
    if name == "ExperimentTracker":
        from reinforce_spec.observability.experiment import ExperimentTracker

        return ExperimentTracker
    if name == "AuditLogger":
        from reinforce_spec.observability.audit import AuditLogger

        return AuditLogger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
