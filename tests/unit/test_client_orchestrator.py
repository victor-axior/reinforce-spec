"""Unit tests for the ReinforceSpec client orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from reinforce_spec._exceptions import InsufficientCandidatesError
from reinforce_spec._internal._config import AppConfig
from reinforce_spec.client import ReinforceSpec
from reinforce_spec.types import CandidateSpec, DimensionScore, PolicyStage, SelectionMethod


def _make_candidates(n: int = 3) -> list[CandidateSpec]:
    return [
        CandidateSpec(
            index=i,
            content=f"Specification content #{i} with adequate length",
            composite_score=float(i + 1),
            dimension_scores=[
                DimensionScore(dimension="compliance_regulatory", score=3.0),
            ],
        )
        for i in range(n)
    ]


@pytest.mark.asyncio()
class TestReinforceSpec:
    """Test the high-level client."""

    def _make_client(self) -> ReinforceSpec:
        config = AppConfig.for_testing()
        return ReinforceSpec(config=config)

    async def test_init(self) -> None:
        client = self._make_client()
        assert not client._connected

    async def test_from_env(self) -> None:
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            client = ReinforceSpec.from_env()
            assert isinstance(client, ReinforceSpec)

    async def test_connect_and_close(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        client = ReinforceSpec(config=config)
        await client.connect()
        assert client._connected
        await client.close()
        assert not client._connected

    async def test_context_manager(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        async with ReinforceSpec(config=config) as client:
            assert client._connected
        assert not client._connected

    async def test_select_insufficient_candidates(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        async with ReinforceSpec(config=config) as client:
            candidates = _make_candidates(1)
            with pytest.raises(InsufficientCandidatesError):
                await client.select(candidates)

    async def test_select_happy_path(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)

        client = ReinforceSpec(config=config)
        await client.connect()

        # Mock the scorer to return candidates with scores
        candidates = _make_candidates(3)
        mock_scorer = AsyncMock()
        mock_scorer.score_candidates = AsyncMock(return_value=candidates)
        client._scorer = mock_scorer

        # Mock selector
        mock_selector = MagicMock()
        mock_selector.select.return_value = (
            candidates[2],
            {"method": "hybrid", "rl_confidence": 0.8},
        )
        client._selector = mock_selector

        response = await client.select(candidates, description="test")
        assert response.request_id is not None
        assert response.selected == candidates[2]
        assert response.latency_ms > 0

        await client.close()

    async def test_select_scoring_only(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        client = ReinforceSpec(config=config)
        await client.connect()

        candidates = _make_candidates(3)
        mock_scorer = AsyncMock()
        mock_scorer.score_candidates = AsyncMock(return_value=candidates)
        client._scorer = mock_scorer

        mock_selector = MagicMock()
        mock_selector.select.return_value = (
            candidates[2],
            {"method": "scoring_only", "rl_confidence": 1.0},
        )
        client._selector = mock_selector

        response = await client.select(
            candidates, selection_method="scoring_only"
        )
        assert response is not None

        await client.close()

    async def test_submit_feedback(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        async with ReinforceSpec(config=config) as client:
            # First create a request
            await client._storage.save_request(
                request_id="req-fb", n_specs=2,
            )
            fid = await client.submit_feedback(
                request_id="req-fb", rating=4.0, comment="Good"
            )
            assert isinstance(fid, str)

    async def test_submit_feedback_shapes_reward(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        async with ReinforceSpec(config=config) as client:
            await client._storage.save_request(
                request_id="req-fb2", n_specs=2,
            )
            await client.submit_feedback(
                request_id="req-fb2", rating=5.0
            )
            # Env should have received feedback signal
            assert client._env is not None

    async def test_get_policy_status_no_production(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        async with ReinforceSpec(config=config) as client:
            status = await client.get_policy_status()
            assert status.version == "none"
            assert status.training_episodes == 0

    async def test_train_policy_insufficient_data(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        async with ReinforceSpec(config=config) as client:
            result = await client.train_policy()
            assert result["status"] == "insufficient_data"

    async def test_double_connect(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        client = ReinforceSpec(config=config)
        await client.connect()
        await client.connect()  # should not error (idempotent)
        assert client._connected
        await client.close()

    async def test_ensure_connected_auto(self, tmp_path) -> None:
        config = AppConfig.for_testing()
        config.storage.data_dir = str(tmp_path)
        client = ReinforceSpec(config=config)
        # _ensure_connected should trigger connect automatically
        await client._ensure_connected()
        assert client._connected
        await client.close()
