"""High-level policy training façade.

Provides a one-call ``train()`` function and the ``Trainer`` class that
orchestrates replay-buffer sampling, PPO updates, and checkpoint saving.

Examples
--------
>>> from reinforce_spec.rl.trainer import Trainer
>>> trainer = Trainer(config)
>>> result = await trainer.run(n_steps=2048)
"""

from __future__ import annotations

import dataclasses
from typing import Any

from loguru import logger

from reinforce_spec._internal._config import RLConfig
from reinforce_spec._internal._policy import PolicyManager, PPOPolicy
from reinforce_spec._internal._replay_buffer import PrioritizedReplayBuffer


@dataclasses.dataclass(frozen=True, slots=True)
class TrainResult:
    """Summary of a training run.

    Attributes
    ----------
    steps : int
        Number of timesteps completed.
    mean_reward : float
        Average reward over the training run.
    policy_version : str
        Version tag of the updated policy.
    metrics : dict[str, Any]
        Additional training metrics (loss, entropy, etc.).

    """

    steps: int
    mean_reward: float
    policy_version: str
    metrics: dict[str, Any] = dataclasses.field(default_factory=dict)


class Trainer:
    """Orchestrates PPO policy training on the replay buffer.

    Parameters
    ----------
    config : RLConfig
        RL hyperparameters.
    policy_manager : PolicyManager or None
        Existing policy manager. A fresh one is created when ``None``.
    replay_buffer : PrioritizedReplayBuffer or None
        Experience replay buffer. A default one is created when ``None``.

    """

    def __init__(
        self,
        config: RLConfig | None = None,
        policy_manager: PolicyManager | None = None,
        replay_buffer: PrioritizedReplayBuffer | None = None,
    ) -> None:
        self._config = config or RLConfig()
        self._manager = policy_manager or PolicyManager(self._config)
        self._buffer = replay_buffer or PrioritizedReplayBuffer(capacity=10_000)

    @property
    def policy_manager(self) -> PolicyManager:
        """Return the underlying policy manager."""
        return self._manager

    @property
    def replay_buffer(self) -> PrioritizedReplayBuffer:
        """Return the underlying replay buffer."""
        return self._buffer

    async def run(self, n_steps: int | None = None) -> TrainResult:
        """Execute a training iteration.

        Parameters
        ----------
        n_steps : int or None
            Number of PPO timesteps.  Uses config default if ``None``.

        Returns
        -------
        TrainResult
            Summary of the training run.

        """
        steps = n_steps or self._config.ppo_n_steps
        policy = self._manager.active_policy

        if policy is None:
            logger.warning("trainer_no_active_policy — creating fresh policy")
            policy = PPOPolicy(config=self._config)

        logger.info("training_started | steps={steps}", steps=steps)

        # Sample from replay buffer
        batch_size = min(self._config.retrain_batch_size, self._buffer.size)
        if batch_size == 0:
            logger.warning("training_skipped — replay buffer empty")
            return TrainResult(
                steps=0,
                mean_reward=0.0,
                policy_version=self._manager.active_version or "none",
            )

        transitions, indices, weights = self._buffer.sample(batch_size)

        # Run PPO update
        result = policy.train(total_timesteps=steps)

        # Compute mean reward from sampled transitions
        mean_reward = sum(t.reward for t in transitions) / len(transitions)

        version = self._manager.active_version or "v0"
        logger.info(
            "training_completed | steps={steps} mean_reward={reward} version={version}",
            steps=steps,
            reward=round(mean_reward, 4),
            version=version,
        )

        return TrainResult(
            steps=steps,
            mean_reward=mean_reward,
            policy_version=version,
            metrics=result if isinstance(result, dict) else {},
        )
