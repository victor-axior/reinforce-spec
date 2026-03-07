"""Unit tests for the circuit breaker and OpenRouterClient."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from reinforce_spec._exceptions import (
    CircuitBreakerOpenError,
    UpstreamError,
)
from reinforce_spec._internal._client import (
    CircuitBreaker,
    CircuitState,
    LLMCallMetrics,
    OpenRouterClient,
)
from reinforce_spec._internal._config import LLMConfig

# ── CircuitBreaker ────────────────────────────────────────────────────────────


@pytest.mark.asyncio()
class TestCircuitBreaker:
    """Test circuit breaker state machine."""

    async def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker(threshold=3, cooldown_seconds=10.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_open is False

    async def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    async def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(threshold=3, cooldown_seconds=60.0)
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    async def test_check_raises_when_open(self) -> None:
        cb = CircuitBreaker(threshold=1, cooldown_seconds=60.0)
        await cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError):
            await cb.check()

    async def test_check_passes_when_closed(self) -> None:
        cb = CircuitBreaker(threshold=5)
        await cb.check()  # Should not raise

    async def test_success_resets_to_closed(self) -> None:
        cb = CircuitBreaker(threshold=2)
        await cb.record_failure()
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    async def test_cooldown_transitions_to_half_open(self) -> None:
        cb = CircuitBreaker(threshold=1, cooldown_seconds=0.01)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        await asyncio.sleep(0.02)
        # Accessing is_open triggers the transition
        assert cb.is_open is False
        assert cb.state == CircuitState.HALF_OPEN

    async def test_cooldown_remaining(self) -> None:
        cb = CircuitBreaker(threshold=1, cooldown_seconds=10.0)
        await cb.record_failure()
        remaining = cb.cooldown_remaining
        assert remaining > 0
        assert remaining <= 10.0

    async def test_cooldown_remaining_when_closed(self) -> None:
        cb = CircuitBreaker(threshold=5)
        assert cb.cooldown_remaining == 0.0

    async def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(threshold=1, cooldown_seconds=0.01)
        await cb.record_failure()
        await asyncio.sleep(0.02)
        _ = cb.is_open  # Transition to HALF_OPEN
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    async def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker(threshold=1, cooldown_seconds=0.01)
        await cb.record_failure()
        await asyncio.sleep(0.02)
        _ = cb.is_open  # Transition to HALF_OPEN
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN


# ── LLMCallMetrics ────────────────────────────────────────────────────────────


class TestLLMCallMetrics:
    """Test metrics dataclass."""

    def test_defaults(self) -> None:
        m = LLMCallMetrics(model="test/model")
        assert m.prompt_tokens == 0
        assert m.completion_tokens == 0
        assert m.cost_usd is None
        assert m.status == "success"

    def test_custom_values(self) -> None:
        m = LLMCallMetrics(
            model="test/model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=1234.5,
            cost_usd=0.001,
        )
        assert m.total_tokens == 150
        assert m.cost_usd == 0.001


# ── OpenRouterClient ─────────────────────────────────────────────────────────


@pytest.mark.asyncio()
class TestOpenRouterClient:
    """Test OpenRouterClient with mocked AsyncOpenAI."""

    def _make_config(self) -> LLMConfig:
        return LLMConfig(
            openrouter_api_key="test-key",
            judge_models=["model-a", "model-b"],
            fallback_models=["model-a", "model-b", "model-c"],
            timeout_seconds=5.0,
            max_retries=0,
        )

    def _make_mock_response(
        self, content: str = "response", prompt_tokens: int = 10, completion_tokens: int = 20
    ) -> MagicMock:
        usage = MagicMock()
        usage.prompt_tokens = prompt_tokens
        usage.completion_tokens = completion_tokens
        usage.total_tokens = prompt_tokens + completion_tokens

        choice = MagicMock()
        choice.message.content = content

        response = MagicMock()
        response.choices = [choice]
        response.usage = usage
        return response

    async def test_properties(self) -> None:
        config = self._make_config()
        client = OpenRouterClient(config)
        assert client.judge_models == ["model-a", "model-b"]
        assert client.circuit_state == CircuitState.CLOSED
        assert client.total_cost_usd == 0.0
        assert client.total_calls == 0
        await client.close()

    async def test_complete_success(self) -> None:
        config = self._make_config()
        client = OpenRouterClient(config)
        mock_response = self._make_mock_response()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        content, metrics = await client.complete(
            [{"role": "user", "content": "hello"}],
            model="model-a",
        )
        assert content == "response"
        assert metrics.model == "model-a"
        assert metrics.prompt_tokens == 10
        assert client.total_calls == 1
        await client.close()

    async def test_complete_with_fallback_first_succeeds(self) -> None:
        config = self._make_config()
        client = OpenRouterClient(config)
        mock_response = self._make_mock_response("fallback ok")
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        content, metrics = await client.complete_with_fallback(
            [{"role": "user", "content": "test"}],
        )
        assert content == "fallback ok"
        await client.close()

    async def test_complete_with_fallback_all_fail(self) -> None:
        config = self._make_config()
        client = OpenRouterClient(config)
        client.complete = AsyncMock(side_effect=UpstreamError("fail", provider="openrouter"))

        with pytest.raises(UpstreamError, match="All fallback models"):
            await client.complete_with_fallback(
                [{"role": "user", "content": "test"}],
            )
        await client.close()

    async def test_complete_parallel(self) -> None:
        config = self._make_config()
        client = OpenRouterClient(config)
        mock_response = self._make_mock_response()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        results = await client.complete_parallel(
            [
                [{"role": "user", "content": "msg1"}],
                [{"role": "user", "content": "msg2"}],
            ],
            model="model-a",
        )
        assert len(results) == 2
        for r in results:
            assert not isinstance(r, Exception)
        await client.close()

    async def test_close_and_context_manager(self) -> None:
        config = self._make_config()
        client = OpenRouterClient(config)
        client._client.close = AsyncMock()

        async with client as c:
            assert c.judge_models == ["model-a", "model-b"]

        client._client.close.assert_called_once()
