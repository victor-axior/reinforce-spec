"""Unit tests for structured audit logging."""

from __future__ import annotations

from unittest.mock import patch

from reinforce_spec.observability.audit import AuditLogger


class TestAuditLogger:
    """Test audit event emission."""

    def test_log_evaluation(self) -> None:
        audit = AuditLogger()
        # Should not raise
        audit.log_evaluation(
            request_id="req-1",
            n_candidates=5,
            selected_index=2,
            method="hybrid",
            customer_type="bank",
            latency_ms=150.3,
        )

    def test_log_evaluation_minimal(self) -> None:
        audit = AuditLogger()
        audit.log_evaluation(
            request_id="req-2",
            n_candidates=3,
            selected_index=0,
            method="scoring_only",
        )

    def test_log_feedback(self) -> None:
        audit = AuditLogger()
        audit.log_feedback(
            request_id="req-1",
            feedback_id="fb-1",
            rating=4.5,
            spec_id="spec-1",
        )

    def test_log_feedback_minimal(self) -> None:
        audit = AuditLogger()
        audit.log_feedback(
            request_id="req-1",
            feedback_id="fb-2",
        )

    def test_log_training(self) -> None:
        audit = AuditLogger()
        audit.log_training(
            policy_version="v1",
            steps=1000,
            mean_reward=0.85,
            buffer_size=5000,
        )

    def test_log_promotion(self) -> None:
        audit = AuditLogger()
        audit.log_promotion(
            policy_version="v1",
            from_stage="shadow",
            to_stage="canary",
        )

    def test_emit_called(self) -> None:
        audit = AuditLogger()
        with patch.object(audit, "_emit") as mock_emit:
            audit.log_evaluation(
                request_id="req-1",
                n_candidates=3,
                selected_index=0,
                method="hybrid",
            )
            mock_emit.assert_called_once()
            args = mock_emit.call_args
            assert args[0][0] == "evaluation"
