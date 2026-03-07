"""Prioritized Experience Replay (PER) buffer.

Implements a sum-tree-backed priority queue for experience transitions:
  - Proportional prioritization (P(i) = p_i^α / Σ p_j^α)
  - Importance-sampling weights (w_i = (N·P(i))^{-β})
  - β annealing from β_0 → 1.0 over training
  - Efficient O(log N) sampling via segment tree

References
----------
Schaul et al., "Prioritized Experience Replay", ICLR 2016.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
from loguru import logger

# ── Sum-Tree ─────────────────────────────────────────────────────────────────


class SumTree:
    """Binary sum-tree for efficient proportional sampling.

    Provides O(log N) ``update`` and ``sample`` operations.
    Tree structure stores priorities in leaves; internal nodes store sums.
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._tree = np.zeros(2 * capacity - 1, dtype=np.float64)
        self._data: list[Any] = [None] * capacity
        self._write_idx = 0
        self._size = 0

    @property
    def total(self) -> float:
        """Total priority sum (root of the tree)."""
        return float(self._tree[0])

    @property
    def size(self) -> int:
        return self._size

    @property
    def min_priority(self) -> float:
        """Minimum priority among stored entries."""
        if self._size == 0:
            return 0.0
        leaf_start = self.capacity - 1
        leaves = self._tree[leaf_start : leaf_start + self._size]
        positive = leaves[leaves > 0]
        return float(positive.min()) if len(positive) > 0 else 1e-6

    def add(self, priority: float, data: Any) -> None:
        """Add a new experience with given priority."""
        tree_idx = self._write_idx + self.capacity - 1
        self._data[self._write_idx] = data
        self._update_tree(tree_idx, priority)
        self._write_idx = (self._write_idx + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def update(self, tree_idx: int, priority: float) -> None:
        """Update priority at a given tree index."""
        self._update_tree(tree_idx, priority)

    def sample(self, value: float) -> tuple[int, float, Any]:
        """Sample a leaf proportional to stored priorities.

        Parameters
        ----------
        value : float
            Random value in ``[0, total_priority)``.

        Returns
        -------
        tuple[int, float, Any]
            ``(tree_index, priority, data)``.

        """
        idx = 0
        while True:
            left = 2 * idx + 1
            right = left + 1
            if left >= len(self._tree):
                break
            if value <= self._tree[left]:
                idx = left
            else:
                value -= self._tree[left]
                idx = right

        data_idx = idx - self.capacity + 1
        return idx, self._tree[idx], self._data[data_idx]

    def _update_tree(self, tree_idx: int, priority: float) -> None:
        change = priority - self._tree[tree_idx]
        self._tree[tree_idx] = priority
        while tree_idx > 0:
            tree_idx = (tree_idx - 1) // 2
            self._tree[tree_idx] += change


# ── Experience Transition ────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True, slots=True)
class Transition:
    """Single RL transition (s, a, r, s', done).

    Attributes
    ----------
    candidate_rewards : np.ndarray or None
        Composite score for *each* candidate in this observation.
        Shape ``(n_candidates,)``.  When present, the environment
        replay can return action-dependent rewards so PPO learns
        *which* candidate is best, not just that rewardâ 0.
    """

    observation: np.ndarray
    action: int
    reward: float
    next_observation: np.ndarray
    done: bool
    info: dict[str, Any] = dataclasses.field(default_factory=dict)
    candidate_rewards: np.ndarray | None = None


# ── Prioritized Replay Buffer ────────────────────────────────────────────────


class PrioritizedReplayBuffer:
    """Prioritized Experience Replay buffer backed by a sum-tree.

    Parameters
    ----------
    capacity : int
        Maximum number of transitions.
    alpha : float
        Priority exponent.  ``0`` = uniform, ``1`` = full proportional.
    beta_start : float
        Initial importance-sampling exponent.
    beta_end : float
        Final β value (annealed linearly).
    beta_frames : int
        Number of frames over which to anneal β.
    epsilon : float
        Small constant added to priorities to avoid zero probability.

    """

    def __init__(
        self,
        capacity: int = 100_000,
        alpha: float = 0.6,
        beta_start: float = 0.4,
        beta_end: float = 1.0,
        beta_frames: int = 100_000,
        epsilon: float = 1e-6,
    ) -> None:
        self._tree = SumTree(capacity)
        self._alpha = alpha
        self._beta_start = beta_start
        self._beta_end = beta_end
        self._beta_frames = beta_frames
        self._epsilon = epsilon
        self._frame = 0
        self._max_priority = 1.0

    @property
    def size(self) -> int:
        return self._tree.size

    @property
    def capacity(self) -> int:
        return self._tree.capacity

    @property
    def beta(self) -> float:
        """Current importance-sampling β (annealed linearly)."""
        frac = min(1.0, self._frame / max(self._beta_frames, 1))
        return self._beta_start + frac * (self._beta_end - self._beta_start)

    def add(self, transition: Transition, td_error: float | None = None) -> None:
        """Add a transition with optional TD-error-based priority.

        If no ``td_error`` is provided, uses the maximum priority seen so far
        (optimistic initialization).
        """
        if td_error is not None:
            priority = (abs(td_error) + self._epsilon) ** self._alpha
        else:
            priority = self._max_priority

        self._tree.add(priority, transition)

    def sample(
        self,
        batch_size: int,
    ) -> tuple[list[Transition], np.ndarray, list[int]]:
        """Sample a prioritized mini-batch.

        Parameters
        ----------
        batch_size : int
            Number of transitions to sample.

        Returns
        -------
        tuple[list[Transition], np.ndarray, list[int]]
            ``(transitions, is_weights, tree_indices)`` where
            *is_weights* contains importance-sampling corrections and
            *tree_indices* are used for priority updates.

        """
        self._frame += 1
        beta = self.beta

        transitions: list[Transition] = []
        is_weights = np.zeros(batch_size, dtype=np.float32)
        tree_indices: list[int] = []

        total = self._tree.total
        if total == 0:
            logger.warning("replay_buffer_empty")
            return [], np.array([]), []

        segment = total / batch_size
        min_prob = self._tree.min_priority / total

        for i in range(batch_size):
            low = segment * i
            high = segment * (i + 1)
            value = np.random.uniform(low, high)

            idx, priority, data = self._tree.sample(value)

            if data is None:
                continue

            prob = priority / total
            is_weight = (self._tree.size * prob) ** (-beta)
            # Normalize by max weight
            max_weight = (self._tree.size * min_prob) ** (-beta)
            is_weight /= max(max_weight, 1e-8)

            transitions.append(data)
            is_weights[len(transitions) - 1] = is_weight
            tree_indices.append(idx)

        return transitions, is_weights[: len(transitions)], tree_indices

    def update_priorities(
        self,
        tree_indices: list[int],
        td_errors: np.ndarray | list[float],
    ) -> None:
        """Update priorities after learning step."""
        for idx, td_error in zip(tree_indices, td_errors):
            priority = (abs(td_error) + self._epsilon) ** self._alpha
            self._tree.update(idx, priority)
            self._max_priority = max(self._max_priority, priority)

    def clear(self) -> None:
        """Clear the replay buffer."""
        self._tree = SumTree(self._tree.capacity)
        self._max_priority = 1.0
        self._frame = 0


__all__ = [
    "PrioritizedReplayBuffer",
    "SumTree",
    "Transition",
]
