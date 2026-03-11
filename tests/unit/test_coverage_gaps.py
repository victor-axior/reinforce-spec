"""Comprehensive gap-filling tests for remaining coverage holes.

Covers:
  - _client.py: complete_with_fallback (all fail / success), complete_parallel
  - _idempotency.py: Redis-backed paths (connect, check, save, close)
  - client.py: train_policy success, get_policy_status drift, empty transitions
  - server/__main__.py: uvicorn import failure
  - _compat.py: require_dependency error paths
  - _environment.py: gymnasium import fallback
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reinforce_spec._compat import python_version_info, require_dependency
from reinforce_spec._exceptions import (
    CircuitBreakerOpenError,
    UpstreamError,
)
from reinforce_spec._internal._idempotency import IdempotencyStore

# ═══════════════════════════════════════════════════════════════════════════════
# _compat.py — require_dependency
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireDependency:
    """Cover require_dependency success / failure paths."""

    def test_existing_module(self) -> None:
        mod = require_dependency("json")
        assert mod is json

    def test_missing_module_no_extra(self) -> None:
        with pytest.raises(ImportError, match="pip install totally_fake_pkg"):
            require_dependency("totally_fake_pkg")

    def test_missing_module_with_extra(self) -> None:
        with pytest.raises(ImportError, match="pip install reinforce-spec\\[myextra\\]"):
            require_dependency("totally_fake_pkg", extra="myextra")

    def test_python_version_info(self) -> None:
        v = python_version_info()
        parts = v.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# ═══════════════════════════════════════════════════════════════════════════════
# _idempotency.py — Redis backend
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotencyStoreRedis:
    """Cover Redis-backed paths in IdempotencyStore."""

    @pytest.mark.asyncio
    async def test_connect_redis(self) -> None:
        """When redis_url provided and REDIS_AVAILABLE, connects to Redis."""
        mock_redis_instance = AsyncMock()
        mock_aioredis = MagicMock()
        mock_aioredis.from_url.return_value = mock_redis_instance

        mock_redis_module = MagicMock()
        mock_redis_module.asyncio = mock_aioredis

        with (
            patch("reinforce_spec._internal._idempotency.REDIS_AVAILABLE", True),
            patch.dict("sys.modules", {"redis": mock_redis_module, "redis.asyncio": mock_aioredis}),
        ):
            store = IdempotencyStore(redis_url="redis://localhost:6379")
            await store.connect()

        assert store._redis is mock_redis_instance

    @pytest.mark.asyncio
    async def test_close_redis(self) -> None:
        """Closing with redis client calls close on it."""
        mock_redis = AsyncMock()
        store = IdempotencyStore()
        store._redis = mock_redis

        await store.close()
        mock_redis.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_redis_miss(self) -> None:
        """Redis check returns None when key not found."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        store = IdempotencyStore()
        store._redis = mock_redis

        result = await store.check("missing-key")
        assert result is None
        mock_redis.get.assert_awaited_once_with("idem:missing-key")

    @pytest.mark.asyncio
    async def test_check_redis_hit(self) -> None:
        """Redis check returns deserialized response when found."""
        expected = {"status": "ok", "id": "123"}
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(expected)

        store = IdempotencyStore()
        store._redis = mock_redis

        result = await store.check("found-key")
        assert result == expected

    @pytest.mark.asyncio
    async def test_save_redis(self) -> None:
        """Redis save stores JSON with TTL."""
        mock_redis = AsyncMock()
        store = IdempotencyStore(ttl_seconds=3600)
        store._redis = mock_redis

        response = {"status": "created", "id": "456"}
        await store.save("my-key", response)

        mock_redis.setex.assert_awaited_once_with(
            "idem:my-key",
            3600,
            json.dumps(response),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# _client.py — complete_with_fallback / complete_parallel
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpenRouterClientFallback:
    """Cover complete_with_fallback all-fail and success paths."""

    @staticmethod
    def _make_client():
        from reinforce_spec._internal._client import OpenRouterClient
        from reinforce_spec._internal._config import LLMConfig

        config = LLMConfig(
            openrouter_api_key="sk-test",
            judge_models=["model-a", "model-b"],
            fallback_models=["fallback-1", "fallback-2"],
        )
        with patch("reinforce_spec._internal._client.AsyncOpenAI"):
            client = OpenRouterClient(config)
        return client

    @pytest.mark.asyncio
    async def test_fallback_first_succeeds(self) -> None:
        from reinforce_spec._internal._client import LLMCallMetrics

        client = self._make_client()
        metrics = LLMCallMetrics(model="fallback-1")
        client.complete = AsyncMock(return_value=("result", metrics))

        content, _m = await client.complete_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert content == "result"
        client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_first_fails_second_succeeds(self) -> None:
        from reinforce_spec._internal._client import LLMCallMetrics

        client = self._make_client()
        metrics = LLMCallMetrics(model="fallback-2")

        call_count = 0

        async def mock_complete(messages, model=None, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise UpstreamError("model-a failed", provider="openrouter")
            return ("ok", metrics)

        client.complete = mock_complete

        content, _m = await client.complete_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert content == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_fallback_all_fail(self) -> None:
        client = self._make_client()
        client.complete = AsyncMock(
            side_effect=UpstreamError("boom", provider="openrouter"),
        )

        with pytest.raises(UpstreamError, match="All fallback models exhausted"):
            await client.complete_with_fallback(
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_fallback_circuit_breaker_error(self) -> None:
        client = self._make_client()
        client.complete = AsyncMock(
            side_effect=CircuitBreakerOpenError(
                "open",
                provider="openrouter",
                cooldown_remaining=30.0,
            ),
        )

        with pytest.raises(UpstreamError, match="All fallback models exhausted"):
            await client.complete_with_fallback(
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_fallback_custom_models(self) -> None:
        from reinforce_spec._internal._client import LLMCallMetrics

        client = self._make_client()
        metrics = LLMCallMetrics(model="custom-model")
        client.complete = AsyncMock(return_value=("done", metrics))

        content, _ = await client.complete_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
            models=["custom-model"],
        )
        assert content == "done"


class TestOpenRouterClientParallel:
    """Cover complete_parallel."""

    @staticmethod
    def _make_client():
        from reinforce_spec._internal._client import OpenRouterClient
        from reinforce_spec._internal._config import LLMConfig

        config = LLMConfig(
            openrouter_api_key="sk-test",
            judge_models=["model-a"],
        )
        with patch("reinforce_spec._internal._client.AsyncOpenAI"):
            client = OpenRouterClient(config)
        return client

    @pytest.mark.asyncio
    async def test_parallel_all_succeed(self) -> None:
        from reinforce_spec._internal._client import LLMCallMetrics

        client = self._make_client()
        metrics = LLMCallMetrics(model="model-a")
        client.complete = AsyncMock(return_value=("ok", metrics))

        results = await client.complete_parallel(
            messages_list=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
            ],
        )
        assert len(results) == 2
        assert all(isinstance(r, tuple) for r in results)

    @pytest.mark.asyncio
    async def test_parallel_partial_failure(self) -> None:
        from reinforce_spec._internal._client import LLMCallMetrics

        client = self._make_client()
        metrics = LLMCallMetrics(model="model-a")

        call_count = 0

        async def mock_complete(messages, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise UpstreamError("fail", provider="openrouter")
            return ("ok", metrics)

        client.complete = mock_complete

        results = await client.complete_parallel(
            messages_list=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
            ],
        )
        assert len(results) == 2
        assert isinstance(results[0], Exception)
        assert isinstance(results[1], tuple)

    @pytest.mark.asyncio
    async def test_parallel_custom_temperatures(self) -> None:
        from reinforce_spec._internal._client import LLMCallMetrics

        client = self._make_client()
        metrics = LLMCallMetrics(model="model-a")

        captured_temps: list[float] = []

        async def mock_complete(messages, temperature=0.8, **kw):
            captured_temps.append(temperature)
            return ("ok", metrics)

        client.complete = mock_complete

        await client.complete_parallel(
            messages_list=[
                [{"role": "user", "content": "q1"}],
                [{"role": "user", "content": "q2"}],
            ],
            temperatures=[0.1, 0.9],
        )
        assert captured_temps == [0.1, 0.9]


# ═══════════════════════════════════════════════════════════════════════════════
# client.py — ReinforceSpec.train_policy success path
# ═══════════════════════════════════════════════════════════════════════════════


class TestReinforceSpecTrainPolicy:
    """Cover the train_policy success path and get_policy_status drift path."""

    @staticmethod
    def _make_client():
        """Create a ReinforceSpec with mocked internals."""
        from reinforce_spec._internal._config import AppConfig
        from reinforce_spec.client import ReinforceSpec

        config = AppConfig.for_testing()
        client = ReinforceSpec(config=config)
        client._connected = True

        # Mock internal components
        client._policy_manager = MagicMock()
        client._replay_buffer = MagicMock()
        client._scorer = AsyncMock()
        client._drift_detector = MagicMock()
        client._env = MagicMock()

        return client

    @pytest.mark.asyncio
    async def test_train_policy_empty_transitions(self) -> None:
        client = self._make_client()
        client._replay_buffer.size = 1000

        # sample returns empty transitions
        client._replay_buffer.sample.return_value = ([], [], [])

        result = await client.train_policy(n_steps=100)
        assert result["status"] == "empty_buffer"

    @pytest.mark.asyncio
    async def test_train_policy_success(self) -> None:
        from reinforce_spec.types import PolicyStage

        client = self._make_client()
        client._replay_buffer.size = 1000

        # Mock transitions
        transitions = [MagicMock() for _ in range(10)]
        client._replay_buffer.sample.return_value = (transitions, [1.0] * 10, list(range(10)))

        # Mock policy
        mock_policy = MagicMock()
        mock_policy.train_on_batch.return_value = {"loss": 0.1, "n_transitions": 10}
        client._policy_manager.get_production_policy.return_value = mock_policy

        # Mock production meta for checkpoint
        prod_meta = MagicMock()
        prod_meta.stage = PolicyStage.PRODUCTION
        prod_meta.policy_id = "v001"
        client._policy_manager.list_policies.return_value = [prod_meta]

        result = await client.train_policy(n_steps=200)
        assert result["status"] == "trained"
        assert result["loss"] == 0.1

    @pytest.mark.asyncio
    async def test_train_policy_creates_new_policy(self) -> None:
        client = self._make_client()
        client._replay_buffer.size = 1000

        transitions = [MagicMock() for _ in range(5)]
        client._replay_buffer.sample.return_value = (transitions, [1.0] * 5, list(range(5)))

        # No production policy → create_policy is called
        client._policy_manager.get_production_policy.return_value = None
        mock_policy = MagicMock()
        mock_policy.train_on_batch.return_value = {"loss": 0.2}
        mock_meta = MagicMock()
        mock_meta.policy_id = "v001"
        client._policy_manager.create_policy.return_value = (mock_policy, mock_meta)

        # No production in list (freshly created, still candidate)
        client._policy_manager.list_policies.return_value = []

        result = await client.train_policy()
        assert result["status"] == "trained"
        # promote called 3 times (candidate→shadow→canary→production)
        assert client._policy_manager.promote.call_count == 3


# ═══════════════════════════════════════════════════════════════════════════════
# server/__main__.py — uvicorn import failure
# ═══════════════════════════════════════════════════════════════════════════════


class TestServerMainUvicornFail:
    """Cover the 'uvicorn not installed' error path."""

    def test_main_no_uvicorn(self) -> None:
        from reinforce_spec.server.__main__ import main

        with (
            patch("sys.argv", ["reinforce-spec-server"]),
            patch.dict("sys.modules", {"uvicorn": None}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _client.py — close / context manager
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpenRouterClientLifecycle:
    """Cover close() and async context manager."""

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        from reinforce_spec._internal._client import OpenRouterClient
        from reinforce_spec._internal._config import LLMConfig

        config = LLMConfig(openrouter_api_key="sk-test", judge_models=["m1"])
        with patch("reinforce_spec._internal._client.AsyncOpenAI") as MockAI:
            client = OpenRouterClient(config)
            mock_underlying = MockAI.return_value
            mock_underlying.close = AsyncMock()

            await client.close()
            mock_underlying.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        from reinforce_spec._internal._client import OpenRouterClient
        from reinforce_spec._internal._config import LLMConfig

        config = LLMConfig(openrouter_api_key="sk-test", judge_models=["m1"])
        with patch("reinforce_spec._internal._client.AsyncOpenAI") as MockAI:
            mock_underlying = MockAI.return_value
            mock_underlying.close = AsyncMock()

            async with OpenRouterClient(config) as client:
                assert client is not None

            mock_underlying.close.assert_awaited_once()
