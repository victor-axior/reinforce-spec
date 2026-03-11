"""Tests for the ReinforceSpec SDK client."""

import pytest

from reinforce_spec_sdk import ReinforceSpecClient, SelectionResponse
from reinforce_spec_sdk.exceptions import (
    RateLimitError,
    ValidationError,
)


@pytest.fixture
def base_url() -> str:
    return "https://api.reinforce-spec.dev"


@pytest.fixture
def api_key() -> str:
    return "test-api-key"


class TestReinforceSpecClient:
    """Tests for ReinforceSpecClient."""

    @pytest.mark.asyncio
    async def test_select_success(self, httpx_mock, base_url, api_key):
        """Test successful selection."""
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/v1/specs",
            json={
                "request_id": "test-123",
                "selected": {
                    "index": 0,
                    "content": "Test content",
                    "format": "text",
                    "spec_type": "api_spec",
                    "source_model": "gpt-4",
                    "dimension_scores": [
                        {
                            "dimension": "Accuracy",
                            "score": 4.0,
                            "justification": "Good",
                            "confidence": 0.9,
                        }
                    ],
                    "composite_score": 4.0,
                    "judge_models": ["claude-3"],
                    "metadata": None,
                },
                "all_candidates": [],
                "selection_method": "hybrid",
                "selection_confidence": 0.85,
                "scoring_summary": {"Accuracy": 4.0},
                "latency_ms": 150.0,
                "timestamp": "2025-01-01T00:00:00Z",
            },
        )

        async with ReinforceSpecClient(base_url, api_key) as client:
            response = await client.select(
                candidates=[
                    {"content": "First"},
                    {"content": "Second"},
                ]
            )

            assert isinstance(response, SelectionResponse)
            assert response.request_id == "test-123"
            assert response.selected.index == 0
            assert response.selection_confidence == 0.85

    @pytest.mark.asyncio
    async def test_select_validation_error(self, httpx_mock, base_url, api_key):
        """Test validation error handling."""
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/v1/specs",
            status_code=400,
            json={
                "detail": "At least 2 candidates required",
                "details": {"field": "candidates", "min": 2},
            },
        )

        async with ReinforceSpecClient(base_url, api_key) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.select(candidates=[{"content": "Only one"}])

            assert exc_info.value.status_code == 400
            assert "2 candidates" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_select_rate_limit(self, httpx_mock, base_url, api_key):
        """Test rate limit error handling."""
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/v1/specs",
            status_code=429,
            headers={
                "Retry-After": "30",
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0",
            },
            json={"detail": "Rate limit exceeded"},
        )

        async with ReinforceSpecClient(base_url, api_key, max_retries=0) as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.select(
                    candidates=[{"content": "A"}, {"content": "B"}]
                )

            assert exc_info.value.status_code == 429
            assert exc_info.value.retry_after == 30.0
            assert exc_info.value.limit == 100

    @pytest.mark.asyncio
    async def test_submit_feedback(self, httpx_mock, base_url, api_key):
        """Test feedback submission."""
        httpx_mock.add_response(
            method="POST",
            url=f"{base_url}/v1/specs/feedback",
            json={
                "feedback_id": "fb-123",
                "request_id": "req-456",
                "received_at": "2025-01-01T00:00:00Z",
            },
        )

        async with ReinforceSpecClient(base_url, api_key) as client:
            feedback_id = await client.submit_feedback(
                request_id="req-456",
                rating=4.5,
                comment="Good result",
            )

            assert feedback_id == "fb-123"

    @pytest.mark.asyncio
    async def test_get_policy_status(self, httpx_mock, base_url, api_key):
        """Test policy status retrieval."""
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/v1/policy/status",
            json={
                "version": "v001",
                "stage": "production",
                "training_episodes": 10000,
                "mean_reward": 0.75,
                "explore_rate": 0.1,
                "drift_psi": 0.05,
                "last_trained": "2025-01-01T00:00:00Z",
                "last_promoted": "2025-01-01T00:00:00Z",
            },
        )

        async with ReinforceSpecClient(base_url, api_key) as client:
            status = await client.get_policy_status()

            assert status.version == "v001"
            assert status.stage.value == "production"
            assert status.mean_reward == 0.75

    @pytest.mark.asyncio
    async def test_health_check(self, httpx_mock, base_url, api_key):
        """Test health check."""
        httpx_mock.add_response(
            method="GET",
            url=f"{base_url}/v1/health",
            json={
                "status": "healthy",
                "version": "1.0.0",
                "uptime_seconds": 3600.0,
            },
        )

        async with ReinforceSpecClient(base_url, api_key) as client:
            health = await client.health()

            assert health.status == "healthy"
            assert health.version == "1.0.0"


class TestClientConfiguration:
    """Tests for client configuration."""

    def test_from_env_missing_url(self, monkeypatch):
        """Test error when base URL is missing."""
        monkeypatch.delenv("REINFORCE_SPEC_BASE_URL", raising=False)

        with pytest.raises(ValueError) as exc_info:
            ReinforceSpecClient.from_env()

        assert "REINFORCE_SPEC_BASE_URL" in str(exc_info.value)

    def test_from_env_success(self, monkeypatch):
        """Test successful configuration from environment."""
        monkeypatch.setenv("REINFORCE_SPEC_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("REINFORCE_SPEC_API_KEY", "test-key")
        monkeypatch.setenv("REINFORCE_SPEC_TIMEOUT", "60")

        client = ReinforceSpecClient.from_env()

        assert client._http.base_url == "https://api.example.com"
        assert client._http.api_key == "test-key"
        assert client._http._timeout.read == 60.0
