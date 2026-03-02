"""Prometheus metrics façade.

Re-exports the internal ``MetricsCollector`` with a simpler import path
and adds convenience helpers.

Examples
--------
>>> from reinforce_spec.observability.metrics import MetricsCollector
>>> collector = MetricsCollector()
>>> collector.observe_composite_score(4.2)
"""

from __future__ import annotations

from reinforce_spec._internal._metrics import MetricsCollector

__all__ = ["MetricsCollector"]
