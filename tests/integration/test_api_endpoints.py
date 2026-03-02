"""Integration tests for FastAPI server routes.

End-to-end tests against the real app factory with mocked LLM clients.
Covers all API endpoints: health, specs, feedback, policy, and jobs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from reinforce_spec._exceptions import (
    CircuitBreakerOpenError,
    ConfigurationError,
    InputValidationError,
    PolicyNotFoundError,
    RateLimitError,
    ReinforceSpecError,
    ScoringError,
)
from reinforce_spec._internal._config import AppConfig
from reinforce_spec.server.app import create_app
from reinforce_spec.types import (
    CandidateSpec,
    PolicyStage,
    PolicyStatus,
    SelectionResponse,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def app():
    """Create test application with mocked client."""
    config = AppConfig.for_testing()
    return create_app(config)


def _make_mock_client(*, connected: bool = True) -> MagicMock:
    """Create a pre-configured mock ReinforceSpec client."""
    mock = MagicMock()
    mock._connected = connected
    mock.select = AsyncMock()
    mock.submit_feedback = AsyncMock()
    mock.get_policy_status = AsyncMock()
    mock.train_policy = AsyncMock()
    return mock


@pytest.fixture()
def client(app):
    """Sync test client with a connected mock client."""
    @asynccontextmanager
    async def mock_lifespan(app):
        app.state.client = _make_mock_client(connected=True)
        yield

    app.router.lifespan_context = mock_lifespan
    with TestClient(app) as tc:
        yield tc


@pytest.fixture()
def disconnected_client(app):
    """Sync test client with a disconnected mock client."""
    @asynccontextmanager
    async def mock_lifespan(app):
        app.state.client = _make_mock_client(connected=False)
        yield

    app.router.lifespan_context = mock_lifespan
    with TestClient(app) as tc:
        yield tc


def _make_selection_response(*, request_id: str = "req-001") -> SelectionResponse:
    """Build a realistic SelectionResponse for mocking."""
    candidate_a = CandidateSpec(
        index=0,
        content="# SRS: Payment Gateway\n## Compliance\nPCI-DSS Level 1 ...",
        spec_type="srs",
        source_model="gpt-4",
        composite_score=4.2,
    )
    candidate_b = CandidateSpec(
        index=1,
        content="# SRS: Payment Gateway v2\n## Security\nEnd-to-end encryption ...",
        spec_type="srs",
        source_model="claude-3",
        composite_score=3.8,
    )
    return SelectionResponse(
        request_id=request_id,
        selected=candidate_a,
        all_candidates=[candidate_a, candidate_b],
        selection_method="hybrid",
        selection_confidence=0.87,
        scoring_summary={
            "compliance_regulatory": 4.1,
            "security_architecture": 4.3,
        },
        latency_ms=142.5,
        timestamp=datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def _valid_evaluate_payload(**overrides) -> dict:
    """Build a valid POST /v1/specs payload."""
    payload = {
        "candidates": [
            {"content": "# Spec A\nFull compliance section ..."},
            {"content": "# Spec B\nRobust security design ..."},
        ],
        "selection_method": "hybrid",
        "description": "Payment gateway spec evaluation",
    }
    payload.update(overrides)
    return payload


# ── Health Routes ─────────────────────────────────────────────────────────────


@pytest.mark.integration()
class TestHealthRoutes:
    """Test health check endpoints."""

    def test_liveness(self, client: TestClient) -> None:
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_readiness_when_connected(self, client: TestClient) -> None:
        response = client.get("/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_readiness_when_disconnected(self, disconnected_client: TestClient) -> None:
        response = disconnected_client.get("/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"


# ── Spec Evaluation Routes ────────────────────────────────────────────────────


@pytest.mark.integration()
class TestSpecRoutes:
    """Test spec evaluation endpoint — validation and happy paths."""

    # ── Validation ────────────────────────────────────────────────────

    def test_evaluate_rejects_single_candidate(self, client: TestClient) -> None:
        response = client.post(
            "/v1/specs",
            json={"candidates": [{"content": "Only one spec"}]},
        )
        assert response.status_code == 422

    def test_evaluate_rejects_missing_candidates(self, client: TestClient) -> None:
        response = client.post("/v1/specs", json={})
        assert response.status_code == 422

    def test_evaluate_rejects_empty_content(self, client: TestClient) -> None:
        response = client.post(
            "/v1/specs",
            json={"candidates": [{"content": ""}, {"content": "Valid"}]},
        )
        assert response.status_code == 422

    # ── Happy paths ───────────────────────────────────────────────────

    def test_evaluate_success_hybrid(self, client: TestClient) -> None:
        expected = _make_selection_response(request_id="req-hybrid")
        client.app.state.client.select.return_value = expected

        response = client.post("/v1/specs", json=_valid_evaluate_payload(request_id="req-hybrid"))

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "req-hybrid"
        assert data["selection_method"] == "hybrid"
        assert data["selection_confidence"] == pytest.approx(0.87)
        assert len(data["all_candidates"]) == 2
        assert data["selected"]["composite_score"] == pytest.approx(4.2)
        assert "scoring_summary" in data
        assert data["latency_ms"] == pytest.approx(142.5)
        assert "timestamp" in data

        # Verify client.select was called with the right args
        call_kwargs = client.app.state.client.select.call_args.kwargs
        assert len(call_kwargs["candidates"]) == 2
        assert "customer_type" not in call_kwargs
        assert call_kwargs["selection_method"] == "hybrid"

    def test_evaluate_success_scoring_only(self, client: TestClient) -> None:
        expected = _make_selection_response()
        expected = expected.model_copy(update={"selection_method": "scoring_only"})
        client.app.state.client.select.return_value = expected

        payload = _valid_evaluate_payload(selection_method="scoring_only")
        response = client.post("/v1/specs", json=payload)

        assert response.status_code == 200
        assert response.json()["selection_method"] == "scoring_only"
        assert client.app.state.client.select.call_args.kwargs["selection_method"] == "scoring_only"

    def test_evaluate_success_rl_only(self, client: TestClient) -> None:
        expected = _make_selection_response()
        expected = expected.model_copy(update={"selection_method": "rl_only"})
        client.app.state.client.select.return_value = expected

        payload = _valid_evaluate_payload(selection_method="rl_only")
        response = client.post("/v1/specs", json=payload)

        assert response.status_code == 200
        assert response.json()["selection_method"] == "rl_only"

    def test_evaluate_with_idempotency_key(self, client: TestClient) -> None:
        expected = _make_selection_response(request_id="idem-xyz")
        client.app.state.client.select.return_value = expected

        payload = _valid_evaluate_payload(request_id="idem-xyz")
        response = client.post("/v1/specs", json=payload)

        assert response.status_code == 200
        assert response.json()["request_id"] == "idem-xyz"
        assert client.app.state.client.select.call_args.kwargs["request_id"] == "idem-xyz"

    def test_evaluate_with_minimum_candidates(self, client: TestClient) -> None:
        """Exactly 2 candidates (the minimum) should be accepted."""
        expected = _make_selection_response()
        client.app.state.client.select.return_value = expected

        response = client.post("/v1/specs", json=_valid_evaluate_payload())
        assert response.status_code == 200

    def test_evaluate_with_many_candidates(self, client: TestClient) -> None:
        """5+ candidates with metadata should be accepted."""
        expected = _make_selection_response()
        client.app.state.client.select.return_value = expected

        candidates = [
            {"content": f"Spec {i}", "source_model": f"model-{i}", "metadata": {"v": i}}
            for i in range(5)
        ]
        response = client.post("/v1/specs", json={"candidates": candidates})
        assert response.status_code == 200
        assert len(client.app.state.client.select.call_args.kwargs["candidates"]) == 5

    def test_evaluate_optional_fields_default(self, client: TestClient) -> None:
        """Omitting optional fields should use defaults."""
        expected = _make_selection_response()
        client.app.state.client.select.return_value = expected

        payload = {"candidates": [{"content": "A"}, {"content": "B"}]}
        response = client.post("/v1/specs", json=payload)

        assert response.status_code == 200
        call_kwargs = client.app.state.client.select.call_args.kwargs
        assert "customer_type" not in call_kwargs
        assert call_kwargs["selection_method"] == "hybrid"
        assert call_kwargs["request_id"] is None
        assert call_kwargs["description"] == ""


# ── Feedback Routes ───────────────────────────────────────────────────────────


@pytest.mark.integration()
class TestFeedbackRoutes:
    """Test feedback submission endpoint."""

    def test_feedback_rejects_invalid_rating(self, client: TestClient) -> None:
        response = client.post(
            "/v1/specs/feedback",
            json={"request_id": "req-1", "rating": 10.0},
        )
        assert response.status_code == 422

    def test_feedback_rejects_rating_below_minimum(self, client: TestClient) -> None:
        response = client.post(
            "/v1/specs/feedback",
            json={"request_id": "req-1", "rating": 0.5},
        )
        assert response.status_code == 422

    def test_feedback_rejects_missing_request_id(self, client: TestClient) -> None:
        response = client.post("/v1/specs/feedback", json={"rating": 3.0})
        assert response.status_code == 422

    def test_feedback_success_with_rating(self, client: TestClient) -> None:
        client.app.state.client.submit_feedback.return_value = "fb-001"

        response = client.post(
            "/v1/specs/feedback",
            json={"request_id": "req-123", "rating": 4.5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_id"] == "fb-001"
        assert data["status"] == "accepted"

        call_kwargs = client.app.state.client.submit_feedback.call_args.kwargs
        assert call_kwargs["request_id"] == "req-123"
        assert call_kwargs["rating"] == pytest.approx(4.5)

    def test_feedback_success_with_all_fields(self, client: TestClient) -> None:
        client.app.state.client.submit_feedback.return_value = "fb-002"

        response = client.post(
            "/v1/specs/feedback",
            json={
                "request_id": "req-456",
                "rating": 3.0,
                "comment": "Good but missing compliance details",
                "spec_id": "spec-0",
            },
        )

        assert response.status_code == 200
        call_kwargs = client.app.state.client.submit_feedback.call_args.kwargs
        assert call_kwargs["comment"] == "Good but missing compliance details"
        assert call_kwargs["spec_id"] == "spec-0"

    def test_feedback_success_without_optional_fields(self, client: TestClient) -> None:
        client.app.state.client.submit_feedback.return_value = "fb-003"

        response = client.post(
            "/v1/specs/feedback",
            json={"request_id": "req-789"},
        )

        assert response.status_code == 200
        call_kwargs = client.app.state.client.submit_feedback.call_args.kwargs
        assert call_kwargs["rating"] is None
        assert call_kwargs["comment"] is None
        assert call_kwargs["spec_id"] is None


# ── Policy Routes ─────────────────────────────────────────────────────────────


@pytest.mark.integration()
class TestPolicyRoutes:
    """Test RL policy management endpoints."""

    def test_policy_status(self, client: TestClient) -> None:
        client.app.state.client.get_policy_status.return_value = PolicyStatus(
            version="v1.2.0",
            stage=PolicyStage.CANDIDATE,
            training_episodes=500,
            mean_reward=0.72,
            explore_rate=0.15,
            drift_psi=0.03,
            last_trained=datetime(2026, 2, 28, 10, 0, 0, tzinfo=timezone.utc),
        )

        response = client.get("/v1/policy/status")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1.2.0"
        assert data["stage"] == "candidate"
        assert data["training_episodes"] == 500
        assert data["mean_reward"] == pytest.approx(0.72)
        assert data["explore_rate"] == pytest.approx(0.15)
        assert data["drift_psi"] == pytest.approx(0.03)
        assert data["last_trained"] is not None

    def test_policy_train_default(self, client: TestClient) -> None:
        client.app.state.client.train_policy.return_value = {
            "status": "training_started",
            "n_steps": 1000,
        }

        response = client.post("/v1/policy/train")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "training_started"
        client.app.state.client.train_policy.assert_called_once_with(n_steps=None)

    def test_policy_train_with_steps(self, client: TestClient) -> None:
        client.app.state.client.train_policy.return_value = {
            "status": "training_started",
            "n_steps": 100,
        }

        response = client.post("/v1/policy/train", json={"n_steps": 100})

        assert response.status_code == 200
        client.app.state.client.train_policy.assert_called_once_with(n_steps=100)

    def test_policy_train_rejects_zero_steps(self, client: TestClient) -> None:
        response = client.post("/v1/policy/train", json={"n_steps": 0})
        assert response.status_code == 422

    def test_policy_train_rejects_negative_steps(self, client: TestClient) -> None:
        response = client.post("/v1/policy/train", json={"n_steps": -5})
        assert response.status_code == 422


# ── Job Routes ────────────────────────────────────────────────────────────────


@pytest.mark.integration()
class TestJobRoutes:
    """Test background job status endpoint."""

    def test_job_returns_501_when_queue_not_configured(self, client: TestClient) -> None:
        """Without a job_queue on app.state, the endpoint should return 501."""
        response = client.get("/v1/jobs/some-job-id")
        assert response.status_code == 501
        assert response.json()["detail"] == "Job queue not configured"

    def test_job_returns_404_when_not_found(self, client: TestClient) -> None:
        mock_queue = MagicMock()
        mock_queue.get_job.return_value = None
        client.app.state.job_queue = mock_queue

        response = client.get("/v1/jobs/nonexistent-job")

        assert response.status_code == 404
        assert "nonexistent-job" in response.json()["detail"]

    def test_job_returns_status_when_found(self, client: TestClient) -> None:
        mock_job = MagicMock()
        mock_job.id = "job-042"
        mock_job.name = "train_policy"
        mock_job.status.value = "running"
        mock_job.created_at.isoformat.return_value = "2026-03-01T12:00:00+00:00"
        mock_job.started_at.isoformat.return_value = "2026-03-01T12:00:01+00:00"
        mock_job.completed_at = None
        mock_job.error = None

        mock_queue = MagicMock()
        mock_queue.get_job.return_value = mock_job
        client.app.state.job_queue = mock_queue

        response = client.get("/v1/jobs/job-042")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-042"
        assert data["name"] == "train_policy"
        assert data["status"] == "running"
        assert data["created_at"] == "2026-03-01T12:00:00+00:00"
        assert data["started_at"] == "2026-03-01T12:00:01+00:00"
        assert data["completed_at"] is None
        assert data["error"] is None


# ── Exception Handlers ────────────────────────────────────────────────────────


@pytest.mark.integration()
class TestExceptionHandlers:
    """Test that domain exceptions are mapped to correct HTTP responses."""

    def _post_specs(self, client: TestClient) -> object:
        """Helper: POST a valid evaluate request."""
        return client.post("/v1/specs", json=_valid_evaluate_payload())

    def test_input_validation_error_returns_422(self, client: TestClient) -> None:
        client.app.state.client.select.side_effect = InputValidationError("Bad input data")

        response = self._post_specs(client)

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_failed"
        assert "Bad input data" in data["message"]

    def test_rate_limit_error_returns_429(self, client: TestClient) -> None:
        client.app.state.client.select.side_effect = RateLimitError("Too many requests")

        response = self._post_specs(client)

        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "rate_limited"
        assert response.headers["Retry-After"] == "60"

    def test_circuit_breaker_returns_503(self, client: TestClient) -> None:
        client.app.state.client.select.side_effect = CircuitBreakerOpenError("LLM unavailable")

        response = self._post_specs(client)

        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "service_unavailable"
        assert response.headers["Retry-After"] == "30"
        assert data["retry_after"] == 30

    def test_scoring_error_returns_502(self, client: TestClient) -> None:
        client.app.state.client.select.side_effect = ScoringError("Judge model timed out")

        response = self._post_specs(client)

        assert response.status_code == 502
        data = response.json()
        assert data["error"] == "scoring_failed"
        assert "Judge model timed out" in data["message"]

    def test_policy_not_found_returns_404(self, client: TestClient) -> None:
        client.app.state.client.get_policy_status.side_effect = PolicyNotFoundError(
            "No active policy"
        )

        response = client.get("/v1/policy/status")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "policy_not_found"

    def test_configuration_error_returns_500(self, client: TestClient) -> None:
        client.app.state.client.select.side_effect = ConfigurationError("Missing API key")

        response = self._post_specs(client)

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "configuration_error"

    def test_generic_domain_error_returns_500(self, client: TestClient) -> None:
        client.app.state.client.select.side_effect = ReinforceSpecError("Something broke")

        response = self._post_specs(client)

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "internal_error"

    def test_unhandled_exception_returns_500(self, app) -> None:
        @asynccontextmanager
        async def mock_lifespan(a):
            a.state.client = _make_mock_client(connected=True)
            a.state.client.select.side_effect = RuntimeError("Unexpected crash")
            yield

        app.router.lifespan_context = mock_lifespan
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.post("/v1/specs", json=_valid_evaluate_payload())

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "internal_error"
        assert data["message"] == "An unexpected error occurred"


# ── Middleware ─────────────────────────────────────────────────────────────────


@pytest.mark.integration()
class TestMiddleware:
    """Test middleware integration."""

    def test_request_id_header_propagated(self, client: TestClient) -> None:
        response = client.get(
            "/v1/health",
            headers={"X-Request-ID": "test-req-123"},
        )
        assert response.headers.get("X-Request-ID") == "test-req-123"

    def test_server_timing_header(self, client: TestClient) -> None:
        response = client.get("/v1/health")
        assert "Server-Timing" in response.headers

    def test_cors_preflight(self, client: TestClient) -> None:
        response = client.options(
            "/v1/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in response.headers
