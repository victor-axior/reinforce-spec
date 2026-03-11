"""OpenAI Gym environment for spec selection.

Defines ``SpecSelectionEnv`` — a Gymnasium-compatible environment where:
  - Observation: concatenated feature vectors for N candidate specs
  - Action: discrete index selecting one candidate
  - Reward: weighted composite enterprise-readiness score (optionally shaped
    by human feedback signal)

This environment is used to train a PPO policy that learns which spec,
among a set of scored candidates, to recommend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger

from reinforce_spec._compat import require_dependency

# Gymnasium / gym compatibility shim
require_dependency("gym", "rl")

try:
    import gymnasium as gym  # type: ignore[import-untyped]
    from gymnasium import spaces  # type: ignore[import-untyped]
except ImportError:
    import gym  # type: ignore[import-untyped]
    from gym import spaces  # type: ignore[import-untyped]

from reinforce_spec._internal._config import RLConfig

if TYPE_CHECKING:
    from reinforce_spec.types import CandidateSpec

# ── Feature Engineering ──────────────────────────────────────────────────────

N_DIMENSIONS = 12
# Per-candidate feature vector length:
#   12 dimension scores + composite + spec-length-bucket + spec-format-onehot(5)
PER_CANDIDATE_FEATURES = N_DIMENSIONS + 1 + 1 + 5  # = 19

SPEC_FORMAT_INDEX = {
    "text": 0,
    "json": 1,
    "yaml": 2,
    "markdown": 3,
    "other": 4,
}


def _candidate_to_features(candidate: CandidateSpec) -> np.ndarray:
    """Convert a scored CandidateSpec to a flat feature vector."""
    features = np.zeros(PER_CANDIDATE_FEATURES, dtype=np.float32)

    # Dimension scores (normalized to [0, 1])
    score_map = {ds.dimension: ds.score for ds in candidate.dimension_scores}
    for i, dim_name in enumerate(sorted(score_map.keys())):
        features[i] = score_map[dim_name] / 5.0

    # Composite score (normalized)
    features[N_DIMENSIONS] = candidate.composite_score / 5.0

    # Spec length bucket: 0=short(<500), 0.5=medium(500-2000), 1.0=long(>2000)
    content_len = len(candidate.content)
    if content_len < 500:
        features[N_DIMENSIONS + 1] = 0.0
    elif content_len < 2000:
        features[N_DIMENSIONS + 1] = 0.5
    else:
        features[N_DIMENSIONS + 1] = 1.0

    # Spec format one-hot
    fmt_idx = SPEC_FORMAT_INDEX.get(candidate.format.value, 0)
    features[N_DIMENSIONS + 2 + fmt_idx] = 1.0

    return features


def build_observation(candidates: list[CandidateSpec], max_candidates: int = 5) -> np.ndarray:
    """Build a flat observation vector from a list of candidates.

    Pads/truncates to ``max_candidates`` slots.
    """
    obs = np.zeros(max_candidates * PER_CANDIDATE_FEATURES, dtype=np.float32)
    for i, candidate in enumerate(candidates[:max_candidates]):
        start = i * PER_CANDIDATE_FEATURES
        end = start + PER_CANDIDATE_FEATURES
        obs[start:end] = _candidate_to_features(candidate)
    return obs


# ── Gym Environment ──────────────────────────────────────────────────────────


class SpecSelectionEnv(gym.Env):  # type: ignore[misc]
    """Gymnasium environment for spec selection via RL.

    Parameters
    ----------
    config : RLConfig or None
        RL configuration (``n_candidates``, episode length, reward
        shaping, etc.).
    candidates_queue : Any or None
        Optional async queue that feeds candidate sets into the env.
        When ``None``, candidates must be supplied via
        :meth:`set_candidates`.

    Observation Space
    -----------------
    ``Box(low=0, high=1, shape=(max_candidates * features,))``

    Action Space
    ------------
    ``Discrete(max_candidates)``

    Reward
    ------
    Composite enterprise score of the selected candidate (range
    ``[0, 5]``).  Optionally shaped by a feedback signal.

    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        config: RLConfig | None = None,
        candidates_queue: Any | None = None,
    ) -> None:
        super().__init__()

        self._config = config or RLConfig()
        self._max_candidates = self._config.n_candidates
        self._queue = candidates_queue

        # Spaces
        obs_size = self._max_candidates * PER_CANDIDATE_FEATURES
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(obs_size,), dtype=np.float32)
        self.action_space = spaces.Discrete(self._max_candidates)

        # Internal state
        self._candidates: list[CandidateSpec] = []
        self._current_obs: np.ndarray = np.zeros(obs_size, dtype=np.float32)
        self._step_count: int = 0
        self._episode_count: int = 0
        self._total_reward: float = 0.0
        self._feedback_signal: float | None = None  # human reward shaping

        # Replay mode: when set, reset()/step() cycle through stored
        # (observation, reward) pairs from the PER buffer instead of
        # generating live rollouts on potentially-empty candidates.
        self._replay_queue: list[tuple[np.ndarray, float, np.ndarray]] | None = None
        self._replay_idx: int = 0
        self._replay_candidate_rewards: np.ndarray = np.zeros(
            self._max_candidates, dtype=np.float32
        )

    def set_candidates(self, candidates: list[CandidateSpec]) -> None:
        """Supply a fresh set of scored candidates for the next episode."""
        self._candidates = candidates[: self._max_candidates]
        self._current_obs = build_observation(self._candidates, self._max_candidates)

    def set_feedback_signal(self, signal: float) -> None:
        """Override the reward for the current step with human feedback.

        Signal should be in [-1, 1]; it is scaled and added to the
        composite score reward.
        """
        self._feedback_signal = signal

    def load_transitions(
        self,
        transitions: list[Any],
    ) -> None:
        """Prime the environment with replay-buffer transitions.

        While a replay queue is loaded, ``reset()`` cycles through the
        stored observations and ``step()`` returns the stored rewards,
        giving PPO real signal from past experience instead of rolling
        out on empty or stale candidates.

        Parameters
        ----------
        transitions : list[Transition]
            Transitions sampled from the PER buffer.  Each must have
            ``.observation`` (np.ndarray) and ``.reward`` (float)
            attributes.

        """
        self._replay_queue = []
        for t in transitions:
            # Per-candidate rewards enable action-dependent reward in
            # step(), which is critical for PPO to learn *which*
            # candidate is best.  Fall back to constant reward for
            # legacy transitions that predate this field.
            if t.candidate_rewards is not None:
                cr = t.candidate_rewards.copy()
            else:
                cr = np.full(self._max_candidates, float(t.reward), dtype=np.float32)
            self._replay_queue.append((t.observation.copy(), float(t.reward), cr))
        self._replay_idx = 0
        logger.debug(
            "env_replay_loaded | n_transitions={n}",
            n=len(self._replay_queue),
        )

    def clear_replay(self) -> None:
        """Exit replay mode and return to normal live-rollout operation."""
        self._replay_queue = None
        self._replay_idx = 0

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment for a new episode."""
        super().reset(seed=seed)

        self._step_count = 0
        self._total_reward = 0.0
        self._feedback_signal = None
        self._episode_count += 1

        # Replay mode: serve the next stored observation so PPO trains
        # on real past experience rather than empty candidates.
        if self._replay_queue:
            obs, _scalar_reward, candidate_rewards = self._replay_queue[
                self._replay_idx % len(self._replay_queue)
            ]
            self._replay_idx += 1
            self._current_obs = obs.copy()
            self._replay_candidate_rewards = candidate_rewards

        info: dict[str, Any] = {
            "episode": self._episode_count,
            "n_candidates": len(self._candidates),
        }

        return self._current_obs.copy(), info

    def step(
        self,
        action: int,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Take a selection action.

        Parameters
        ----------
        action : int
            Index of the candidate to select (0-based).

        Returns
        -------
        tuple[np.ndarray, float, bool, bool, dict[str, Any]]
            ``(observation, reward, terminated, truncated, info)``.

        """
        self._step_count += 1

        # Replay mode: return action-dependent reward from the per-
        # candidate scores stored in the transition.  This gives PPO
        # the signal it needs to learn *which* candidate is better,
        # rather than seeing a constant reward regardless of action.
        if self._replay_queue:
            clamped = int(action) % self._max_candidates
            base_reward = float(self._replay_candidate_rewards[clamped])
            reward = base_reward
            if self._feedback_signal is not None:
                reward += self._feedback_signal * self._config.feedback_reward_scale
                self._feedback_signal = None
            selected = None
        else:
            # Clamp action to valid range
            action = int(action) % max(len(self._candidates), 1)

            # Compute reward
            if action < len(self._candidates):
                selected = self._candidates[action]
                base_reward = selected.composite_score  # [0, 5]
            else:
                # Invalid action: penalty
                base_reward = 0.0
                selected = None

            # Shape reward with feedback signal
            reward = base_reward
            if self._feedback_signal is not None:
                reward += self._feedback_signal * self._config.feedback_reward_scale
                self._feedback_signal = None

        self._total_reward += reward

        # Single-step episodes (contextual bandit)
        terminated = True
        truncated = False

        info: dict[str, Any] = {
            "action": action,
            "reward": reward,
            "base_reward": base_reward,
            "step": self._step_count,
            "episode": self._episode_count,
        }

        if selected is not None:
            info["selected_spec_type"] = selected.spec_type
            info["selected_composite"] = selected.composite_score

        logger.debug(
            "env_step | action={action} reward={reward} episode={episode}",
            action=action,
            reward=round(reward, 3),
            episode=self._episode_count,
        )

        return self._current_obs.copy(), reward, terminated, truncated, info

    def render(self) -> str | None:  # type: ignore[override]
        """Render current state as ASCII."""
        lines = [f"Episode {self._episode_count} | Step {self._step_count}"]
        for i, c in enumerate(self._candidates):
            marker = "→" if i == 0 else " "
            lines.append(f"  {marker} [{i}] {c.spec_type:<14} composite={c.composite_score:.3f}")
        return "\n".join(lines)


__all__ = [
    "PER_CANDIDATE_FEATURES",
    "SpecSelectionEnv",
    "build_observation",
]
