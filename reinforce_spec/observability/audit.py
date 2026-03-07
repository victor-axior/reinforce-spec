"""Structured audit logging.

Produces immutable, machine-parseable audit events for every
business-significant action (evaluation, feedback, training, promotion).

Events are logged via loguru with a dedicated ``audit`` tag, making them
easy to filter and forward to an external SIEM / data lake.

Examples
--------
>>> from reinforce_spec.observability.audit import AuditLogger
>>> audit = AuditLogger()
>>> audit.log_evaluation(request_id="abc", n_candidates=5, selected=2)
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from reinforce_spec._internal._utils import utc_now


class AuditLogger:
    """Structured audit event emitter.

    All methods produce a single structured log record tagged
    ``audit=True`` for downstream filtering.
    """

    def _emit(self, event: str, **fields: Any) -> None:
        """Write an audit event to the log sink."""
        with logger.contextualize(audit=True, event=event):
            logger.info(
                "audit | event={event} " + " ".join(f"{k}={{{k}}}" for k in fields),
                event=event,
                **fields,
            )

    def log_evaluation(
        self,
        *,
        request_id: str,
        n_candidates: int,
        selected_index: int,
        method: str,
        customer_type: str | None = None,
        latency_ms: float | None = None,
    ) -> None:
        """Record a spec evaluation event.

        Parameters
        ----------
        request_id : str
            Unique request identifier.
        n_candidates : int
            Number of candidates evaluated.
        selected_index : int
            Index of the chosen candidate.
        method : str
            Selection method used.
        customer_type : str or None
            Customer archetype.
        latency_ms : float or None
            End-to-end latency in milliseconds.

        """
        self._emit(
            "evaluation",
            request_id=request_id,
            n_candidates=n_candidates,
            selected_index=selected_index,
            method=method,
            customer_type=customer_type or "unknown",
            latency_ms=round(latency_ms, 1) if latency_ms else None,
            timestamp=utc_now().isoformat(),
        )

    def log_feedback(
        self,
        *,
        request_id: str,
        feedback_id: str,
        rating: float | None = None,
        spec_id: str | None = None,
    ) -> None:
        """Record a feedback submission event.

        Parameters
        ----------
        request_id : str
            Associated evaluation request ID.
        feedback_id : str
            Unique feedback identifier.
        rating : float or None
            User rating (1-5).
        spec_id : str or None
            Specific spec being rated.

        """
        self._emit(
            "feedback",
            request_id=request_id,
            feedback_id=feedback_id,
            rating=rating,
            spec_id=spec_id or "none",
            timestamp=utc_now().isoformat(),
        )

    def log_training(
        self,
        *,
        policy_version: str,
        steps: int,
        mean_reward: float,
        buffer_size: int,
    ) -> None:
        """Record a policy training event.

        Parameters
        ----------
        policy_version : str
            Version of the trained policy.
        steps : int
            Number of training timesteps.
        mean_reward : float
            Average reward during training.
        buffer_size : int
            Replay buffer size at training time.

        """
        self._emit(
            "training",
            policy_version=policy_version,
            steps=steps,
            mean_reward=round(mean_reward, 4),
            buffer_size=buffer_size,
            timestamp=utc_now().isoformat(),
        )

    def log_promotion(
        self,
        *,
        policy_version: str,
        from_stage: str,
        to_stage: str,
    ) -> None:
        """Record a policy promotion event.

        Parameters
        ----------
        policy_version : str
            Version being promoted.
        from_stage : str
            Previous lifecycle stage.
        to_stage : str
            New lifecycle stage.

        """
        self._emit(
            "promotion",
            policy_version=policy_version,
            from_stage=from_stage,
            to_stage=to_stage,
            timestamp=utc_now().isoformat(),
        )
