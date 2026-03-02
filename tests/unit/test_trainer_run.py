"""Tests for rl.trainer.Trainer — properties and run() method.

Covers reinforce_spec/rl/trainer.py lines 68-75 (properties) and
96-131 (run method body).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reinforce_spec._internal._config import RLConfig
from reinforce_spec._internal._replay_buffer import PrioritizedReplayBuffer, Transition
from reinforce_spec.rl.trainer import TrainResult, Trainer


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_transition(reward: float = 1.0) -> Transition:
    import numpy as np

    return Transition(
        observation=np.zeros(10),
        action=0,
        reward=reward,
        next_observation=np.zeros(10),
        done=False,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestTrainerProperties:
    """Cover the property accessors."""

    def test_policy_manager_property(self) -> None:
        mgr = MagicMock()
        trainer = Trainer(policy_manager=mgr)
        assert trainer.policy_manager is mgr

    def test_replay_buffer_property(self) -> None:
        buf = MagicMock()
        mgr = MagicMock()
        trainer = Trainer(policy_manager=mgr, replay_buffer=buf)
        assert trainer.replay_buffer is buf

    @patch("reinforce_spec.rl.trainer.PolicyManager")
    def test_default_policy_manager(self, MockPM: MagicMock) -> None:
        trainer = Trainer()
        assert trainer.policy_manager is not None

    @patch("reinforce_spec.rl.trainer.PolicyManager")
    def test_default_replay_buffer(self, MockPM: MagicMock) -> None:
        trainer = Trainer()
        assert trainer.replay_buffer is not None


class TestTrainerRun:
    """Cover the async run() method."""

    @pytest.mark.asyncio
    async def test_run_empty_buffer(self) -> None:
        """Buffer empty → returns early with 0 steps."""
        mgr = MagicMock()
        mgr.active_policy = MagicMock()
        mgr.active_version = "v1"

        buf = MagicMock()
        buf.size = 0

        config = RLConfig()
        trainer = Trainer(config=config, policy_manager=mgr, replay_buffer=buf)
        result = await trainer.run(n_steps=100)

        assert result.steps == 0
        assert result.mean_reward == 0.0
        assert result.policy_version == "v1"

    @pytest.mark.asyncio
    async def test_run_empty_buffer_no_version(self) -> None:
        """Buffer empty and no active version → uses 'none'."""
        mgr = MagicMock()
        mgr.active_policy = MagicMock()
        mgr.active_version = None

        buf = MagicMock()
        buf.size = 0

        trainer = Trainer(policy_manager=mgr, replay_buffer=buf)
        result = await trainer.run()

        assert result.policy_version == "none"

    @pytest.mark.asyncio
    @patch("reinforce_spec.rl.trainer.PPOPolicy")
    async def test_run_no_active_policy_creates_fresh(self, MockPPO: MagicMock) -> None:
        """No active policy → creates a fresh PPOPolicy."""
        mock_policy = MagicMock()
        mock_policy.train.return_value = {"loss": 0.1}
        MockPPO.return_value = mock_policy

        mgr = MagicMock()
        mgr.active_policy = None
        mgr.active_version = "v1"

        transitions = [_mock_transition(2.0) for _ in range(3)]
        buf = MagicMock()
        buf.size = 10

        config = RLConfig()
        buf.sample.return_value = (transitions, [0, 1, 2], [1.0, 1.0, 1.0])

        trainer = Trainer(config=config, policy_manager=mgr, replay_buffer=buf)
        result = await trainer.run(n_steps=50)

        MockPPO.assert_called_once()
        mock_policy.train.assert_called_once_with(total_timesteps=50)
        assert result.steps == 50
        assert result.mean_reward == pytest.approx(2.0)
        assert result.policy_version == "v1"

    @pytest.mark.asyncio
    async def test_run_with_active_policy(self) -> None:
        """Uses existing active policy when available."""
        mock_policy = MagicMock()
        mock_policy.train.return_value = {"loss": 0.05, "entropy": 1.2}

        mgr = MagicMock()
        mgr.active_policy = mock_policy
        mgr.active_version = "v3"

        transitions = [_mock_transition(r) for r in [1.0, 3.0, 5.0]]
        buf = MagicMock()
        buf.size = 20
        buf.sample.return_value = (transitions, [0, 1, 2], [1.0, 1.0, 1.0])

        config = RLConfig()
        trainer = Trainer(config=config, policy_manager=mgr, replay_buffer=buf)
        result = await trainer.run(n_steps=200)

        mock_policy.train.assert_called_once_with(total_timesteps=200)
        assert result.steps == 200
        assert result.mean_reward == pytest.approx(3.0)
        assert result.policy_version == "v3"

    @pytest.mark.asyncio
    async def test_run_metrics_dict_returned(self) -> None:
        """When policy.train returns a dict, it becomes TrainResult.metrics."""
        mock_policy = MagicMock()
        training_metrics = {"loss": 0.2, "entropy": 0.8}
        mock_policy.train.return_value = training_metrics

        mgr = MagicMock()
        mgr.active_policy = mock_policy
        mgr.active_version = "v2"

        buf = MagicMock()
        buf.size = 5
        buf.sample.return_value = ([_mock_transition()], [0], [1.0])

        trainer = Trainer(config=RLConfig(), policy_manager=mgr, replay_buffer=buf)
        result = await trainer.run(n_steps=10)

        assert result.metrics == training_metrics

    @pytest.mark.asyncio
    async def test_run_non_dict_result(self) -> None:
        """When policy.train returns non-dict, metrics is empty."""
        mock_policy = MagicMock()
        mock_policy.train.return_value = "ok"

        mgr = MagicMock()
        mgr.active_policy = mock_policy
        mgr.active_version = "v1"

        buf = MagicMock()
        buf.size = 5
        buf.sample.return_value = ([_mock_transition()], [0], [1.0])

        trainer = Trainer(config=RLConfig(), policy_manager=mgr, replay_buffer=buf)
        result = await trainer.run(n_steps=10)

        assert result.metrics == {}

    @pytest.mark.asyncio
    async def test_run_uses_config_steps_when_none(self) -> None:
        """n_steps=None falls back to config.ppo_n_steps."""
        mock_policy = MagicMock()
        mock_policy.train.return_value = {}

        mgr = MagicMock()
        mgr.active_policy = mock_policy
        mgr.active_version = "v1"

        config = RLConfig()
        buf = MagicMock()
        buf.size = 100
        buf.sample.return_value = ([_mock_transition()], [0], [1.0])

        trainer = Trainer(config=config, policy_manager=mgr, replay_buffer=buf)
        result = await trainer.run()

        assert result.steps == config.ppo_n_steps
        mock_policy.train.assert_called_once_with(total_timesteps=config.ppo_n_steps)


class TestTrainResult:
    """Test TrainResult dataclass."""

    def test_fields(self) -> None:
        r = TrainResult(steps=100, mean_reward=3.5, policy_version="v2")
        assert r.steps == 100
        assert r.mean_reward == 3.5
        assert r.policy_version == "v2"
        assert r.metrics == {}

    def test_with_metrics(self) -> None:
        r = TrainResult(
            steps=50, mean_reward=2.0, policy_version="v1",
            metrics={"loss": 0.1},
        )
        assert r.metrics == {"loss": 0.1}

    def test_frozen(self) -> None:
        r = TrainResult(steps=1, mean_reward=0.0, policy_version="v1")
        with pytest.raises(AttributeError):
            r.steps = 2  # type: ignore[misc]
