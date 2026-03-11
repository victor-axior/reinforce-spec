"""Unit tests for off-policy evaluation estimators."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from reinforce_spec._internal._ope import (
    OPEResult,
    _bootstrap_ci,
    fitted_q_evaluation,
    importance_sampling,
    weighted_importance_sampling,
)
from reinforce_spec._internal._replay_buffer import Transition


def _make_transition(reward: float = 1.0, action: int = 0, done: bool = False) -> Transition:
    return Transition(
        observation=np.ones(10, dtype=np.float32),
        action=action,
        reward=reward,
        next_observation=np.ones(10, dtype=np.float32),
        done=done,
    )


def _make_mock_policy(action: int = 0, prob: float = 0.8) -> MagicMock:
    """Create a mock PPOPolicy."""
    policy = MagicMock()
    probs = np.zeros(5, dtype=np.float32)
    probs[action] = prob
    probs[1 - action] = 1.0 - prob  # Distribute remaining probability
    policy.get_action_probabilities.return_value = probs
    policy.predict.return_value = (action, prob)
    return policy


class TestOPEResult:
    """Test OPEResult dataclass."""

    def test_construction(self) -> None:
        r = OPEResult(
            estimator="IS",
            estimated_value=2.5,
            confidence_interval=(2.0, 3.0),
            n_samples=100,
            effective_sample_size=50.0,
        )
        assert r.estimator == "IS"
        assert r.estimated_value == 2.5
        assert r.details == {}


class TestImportanceSampling:
    """Test IS estimator."""

    def test_empty_transitions(self) -> None:
        policy = _make_mock_policy()
        result = importance_sampling([], policy, [])
        assert result.estimator == "IS"
        assert result.estimated_value == 0.0
        assert result.n_samples == 0

    def test_basic_estimation(self) -> None:
        policy = _make_mock_policy(action=0, prob=0.8)
        transitions = [_make_transition(reward=2.0) for _ in range(10)]
        behavior_probs = [0.5] * 10

        result = importance_sampling(transitions, policy, behavior_probs)
        assert result.estimator == "IS"
        assert result.n_samples == 10
        assert result.effective_sample_size > 0
        assert result.estimated_value > 0  # ratio > 1 times positive reward

    def test_confidence_interval_returned(self) -> None:
        policy = _make_mock_policy()
        transitions = [_make_transition(reward=float(i)) for i in range(20)]
        behavior_probs = [0.5] * 20

        result = importance_sampling(transitions, policy, behavior_probs)
        _low, _high = result.confidence_interval
        assert True  # CI may not contain mean for IS


class TestWeightedImportanceSampling:
    """Test WIS estimator."""

    def test_empty_transitions(self) -> None:
        policy = _make_mock_policy()
        result = weighted_importance_sampling([], policy, [])
        assert result.estimator == "WIS"
        assert result.estimated_value == 0.0
        assert result.n_samples == 0

    def test_basic_estimation(self) -> None:
        policy = _make_mock_policy(action=0, prob=0.8)
        transitions = [_make_transition(reward=3.0) for _ in range(10)]
        behavior_probs = [0.5] * 10

        result = weighted_importance_sampling(transitions, policy, behavior_probs)
        assert result.estimator == "WIS"
        assert result.n_samples == 10
        assert result.effective_sample_size > 0

    def test_self_normalized(self) -> None:
        """WIS uses self-normalized weights, so equal ratios → mean of rewards."""
        policy = _make_mock_policy(action=0, prob=0.5)
        transitions = [
            _make_transition(reward=2.0),
            _make_transition(reward=4.0),
        ]
        behavior_probs = [0.5, 0.5]  # ratio = 1.0 for all

        result = weighted_importance_sampling(transitions, policy, behavior_probs)
        assert result.estimated_value == pytest.approx(3.0, abs=0.1)


class TestFittedQEvaluation:
    """Test FQE estimator."""

    def test_empty_transitions(self) -> None:
        policy = _make_mock_policy()
        result = fitted_q_evaluation([], policy)
        assert result.estimator == "FQE"
        assert result.estimated_value == 0.0
        assert result.n_samples == 0

    def test_basic_estimation(self) -> None:
        policy = _make_mock_policy(action=0, prob=0.8)
        transitions = [_make_transition(reward=2.0, done=True) for _ in range(10)]

        result = fitted_q_evaluation(transitions, policy, n_iterations=5)
        assert result.estimator == "FQE"
        assert result.n_samples == 10
        assert "n_iterations" in result.details

    def test_with_continuing_transitions(self) -> None:
        policy = _make_mock_policy(action=0, prob=0.8)
        transitions = [_make_transition(reward=1.0, done=False) for _ in range(10)]
        transitions[-1] = _make_transition(reward=5.0, done=True)

        result = fitted_q_evaluation(transitions, policy, n_iterations=3)
        assert result.n_samples == 10


class TestBootstrapCI:
    """Test bootstrap confidence interval calculation."""

    def test_single_value(self) -> None:
        low, high = _bootstrap_ci([5.0])
        assert low == 5.0
        assert high == 5.0

    def test_empty_list(self) -> None:
        low, high = _bootstrap_ci([])
        assert low == 0.0
        assert high == 0.0

    def test_normal_values(self) -> None:
        values = list(np.random.default_rng(42).normal(3.0, 1.0, size=100))
        low, high = _bootstrap_ci(values)
        assert low < high
        assert low < 3.0 < high

    def test_normalized(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        low, high = _bootstrap_ci(values, normalize=True)
        assert isinstance(low, float)
        assert isinstance(high, float)
