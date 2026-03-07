"""Unit tests for the prioritized experience replay buffer."""

from __future__ import annotations

import numpy as np
import pytest

from reinforce_spec._internal._replay_buffer import (
    PrioritizedReplayBuffer,
    SumTree,
    Transition,
)


def _make_transition(reward: float = 1.0) -> Transition:
    """Helper to create a test transition."""
    return Transition(
        observation=np.zeros(10, dtype=np.float32),
        action=0,
        reward=reward,
        next_observation=np.zeros(10, dtype=np.float32),
        done=True,
    )


class TestSumTree:
    """Test the sum-tree data structure."""

    def test_add_and_total(self) -> None:
        tree = SumTree(capacity=4)
        tree.add(1.0, "a")
        tree.add(2.0, "b")
        tree.add(3.0, "c")
        assert tree.total == pytest.approx(6.0)
        assert tree.size == 3

    def test_sample_proportional(self) -> None:
        tree = SumTree(capacity=4)
        tree.add(1.0, "low")
        tree.add(100.0, "high")
        _, _, data = tree.sample(0.5)
        assert data == "low"
        _, _, data = tree.sample(50.0)
        assert data == "high"

    def test_capacity_wraparound(self) -> None:
        tree = SumTree(capacity=2)
        tree.add(1.0, "a")
        tree.add(2.0, "b")
        tree.add(3.0, "c")
        assert tree.size == 2
        assert tree.total == pytest.approx(5.0)

    def test_update_priority(self) -> None:
        tree = SumTree(capacity=4)
        tree.add(1.0, "a")
        tree.add(2.0, "b")
        tree.update(3, 10.0)
        assert tree.total == pytest.approx(12.0)

    def test_min_priority(self) -> None:
        tree = SumTree(capacity=4)
        tree.add(5.0, "a")
        tree.add(1.0, "b")
        tree.add(3.0, "c")
        assert tree.min_priority == pytest.approx(1.0)


class TestPrioritizedReplayBuffer:
    """Test the PER buffer."""

    def test_add_and_size(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100)
        assert buf.size == 0
        buf.add(_make_transition())
        assert buf.size == 1

    def test_sample_returns_correct_count(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100)
        for i in range(20):
            buf.add(_make_transition(reward=float(i)))
        transitions, weights, indices = buf.sample(batch_size=8)
        assert len(transitions) == 8
        assert len(weights) == 8
        assert len(indices) == 8

    def test_importance_sampling_weights_normalized(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100, alpha=0.6, beta_start=1.0)
        for i in range(50):
            buf.add(_make_transition(), td_error=float(i + 1))
        _, weights, _ = buf.sample(batch_size=16)
        assert np.max(weights) <= 1.01

    def test_beta_annealing(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100, beta_start=0.4, beta_end=1.0, beta_frames=100)
        assert buf.beta == pytest.approx(0.4)
        for _i in range(10):
            buf.add(_make_transition())
        buf.sample(batch_size=1)
        assert buf.beta > 0.4

    def test_update_priorities(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100)
        for _ in range(10):
            buf.add(_make_transition())
        _, _, indices = buf.sample(batch_size=5)
        errors = [1.0, 2.0, 3.0, 4.0, 5.0]
        buf.update_priorities(indices, errors)

    def test_clear(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100)
        buf.add(_make_transition())
        buf.clear()
        assert buf.size == 0

    def test_sample_from_empty_buffer(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100)
        transitions, weights, indices = buf.sample(batch_size=5)
        assert len(transitions) == 0

    def test_transition_fields(self) -> None:
        t = _make_transition(reward=2.5)
        assert t.reward == 2.5
        assert t.action == 0
        assert t.done is True
        assert t.observation.shape == (10,)
        assert t.next_observation.shape == (10,)

    def test_add_with_td_error(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100)
        buf.add(_make_transition(), td_error=5.0)
        assert buf.size == 1

    def test_large_batch_clamped_to_size(self) -> None:
        buf = PrioritizedReplayBuffer(capacity=100)
        for _ in range(3):
            buf.add(_make_transition())
        transitions, weights, indices = buf.sample(batch_size=10)
        # PER samples with replacement, so we get batch_size items
        assert len(transitions) == 10
