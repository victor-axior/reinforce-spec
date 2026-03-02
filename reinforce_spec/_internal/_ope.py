"""Off-Policy Evaluation (OPE).

Provides lightweight estimators to evaluate a *new* policy using data
collected by the *old* (behavior) policy, enabling safe policy promotion
without live traffic experimentation.

Estimators
----------
- **Importance Sampling (IS)**: re-weights logged transitions by the
  probability ratio π_new(a|s) / π_old(a|s).
- **Weighted IS (WIS)**: self-normalized variant that reduces variance.
- **Fitted Q-Evaluation (FQE)**: iterative Bellman backup on logged data
  (requires a function approximator — simplified linear version here).
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
from loguru import logger

from reinforce_spec._internal._policy import PPOPolicy
from reinforce_spec._internal._replay_buffer import Transition


@dataclasses.dataclass(frozen=True, slots=True)
class OPEResult:
    """Result of off-policy evaluation."""

    estimator: str
    estimated_value: float
    confidence_interval: tuple[float, float]
    n_samples: int
    effective_sample_size: float
    details: dict[str, Any] = dataclasses.field(default_factory=dict)


def importance_sampling(
    transitions: list[Transition],
    new_policy: PPOPolicy,
    behavior_probs: list[float],
    gamma: float = 0.99,
) -> OPEResult:
    """Ordinary Importance Sampling estimator.

    Parameters
    ----------
    transitions : list[Transition]
        Logged transitions from the behavior policy.
    new_policy : PPOPolicy
        The evaluation (target) policy.
    behavior_probs : list[float]
        π_old(a|s) for each transition — the probability assigned by the
        behavior policy to the action that was actually taken.
    gamma : float
        Discount factor.

    Returns
    -------
    OPEResult
        Estimate with confidence interval and effective sample size.

    """
    if not transitions or not behavior_probs:
        return OPEResult(
            estimator="IS",
            estimated_value=0.0,
            confidence_interval=(0.0, 0.0),
            n_samples=0,
            effective_sample_size=0.0,
        )

    ratios = []
    weighted_rewards = []

    for t, b_prob in zip(transitions, behavior_probs):
        # π_new(a|s)
        new_probs = new_policy.get_action_probabilities(t.observation)
        new_prob = float(new_probs[t.action]) if t.action < len(new_probs) else 1e-8
        b_prob = max(b_prob, 1e-8)

        ratio = new_prob / b_prob
        ratios.append(ratio)
        weighted_rewards.append(ratio * t.reward)

    ratios_arr = np.array(ratios)
    estimated_value = float(np.mean(weighted_rewards))

    # Effective sample size
    ess = float(np.sum(ratios_arr) ** 2 / np.sum(ratios_arr**2)) if np.sum(ratios_arr**2) > 0 else 0.0

    # Bootstrap confidence interval
    ci_low, ci_high = _bootstrap_ci(weighted_rewards)

    return OPEResult(
        estimator="IS",
        estimated_value=estimated_value,
        confidence_interval=(ci_low, ci_high),
        n_samples=len(transitions),
        effective_sample_size=ess,
        details={"mean_ratio": float(np.mean(ratios_arr)), "max_ratio": float(np.max(ratios_arr))},
    )


def weighted_importance_sampling(
    transitions: list[Transition],
    new_policy: PPOPolicy,
    behavior_probs: list[float],
    gamma: float = 0.99,
) -> OPEResult:
    """Self-normalized (Weighted) Importance Sampling.

    Lower variance than ordinary IS but introduces slight bias.

    Parameters
    ----------
    transitions : list[Transition]
        Logged transitions from the behavior policy.
    new_policy : PPOPolicy
        The evaluation (target) policy.
    behavior_probs : list[float]
        π_old(a|s) for each transition.
    gamma : float
        Discount factor.

    Returns
    -------
    OPEResult
        Estimate with confidence interval and effective sample size.

    """
    if not transitions or not behavior_probs:
        return OPEResult(
            estimator="WIS",
            estimated_value=0.0,
            confidence_interval=(0.0, 0.0),
            n_samples=0,
            effective_sample_size=0.0,
        )

    ratios = []
    for t, b_prob in zip(transitions, behavior_probs):
        new_probs = new_policy.get_action_probabilities(t.observation)
        new_prob = float(new_probs[t.action]) if t.action < len(new_probs) else 1e-8
        b_prob = max(b_prob, 1e-8)
        ratios.append(new_prob / b_prob)

    ratios_arr = np.array(ratios)
    rewards_arr = np.array([t.reward for t in transitions])

    total_ratio = float(np.sum(ratios_arr))
    if total_ratio < 1e-12:
        estimated_value = 0.0
    else:
        estimated_value = float(np.sum(ratios_arr * rewards_arr) / total_ratio)

    ess = float(total_ratio**2 / np.sum(ratios_arr**2)) if np.sum(ratios_arr**2) > 0 else 0.0
    ci_low, ci_high = _bootstrap_ci(
        (ratios_arr * rewards_arr).tolist(), normalize=True
    )

    return OPEResult(
        estimator="WIS",
        estimated_value=estimated_value,
        confidence_interval=(ci_low, ci_high),
        n_samples=len(transitions),
        effective_sample_size=ess,
    )


def fitted_q_evaluation(
    transitions: list[Transition],
    new_policy: PPOPolicy,
    gamma: float = 0.99,
    n_iterations: int = 50,
) -> OPEResult:
    """Simplified Fitted Q-Evaluation using linear regression.

    Iteratively fits Q(s, a) ← r + γ · Q(s', π(s')) on logged data.
    Uses a simple linear model for Q.

    Parameters
    ----------
    transitions : list[Transition]
        Logged transitions from the behavior policy.
    new_policy : PPOPolicy
        The evaluation (target) policy.
    gamma : float
        Discount factor.
    n_iterations : int
        Number of Bellman backup iterations.

    Returns
    -------
    OPEResult
        Estimate with confidence interval and weight diagnostics.

    """
    if not transitions:
        return OPEResult(
            estimator="FQE",
            estimated_value=0.0,
            confidence_interval=(0.0, 0.0),
            n_samples=0,
            effective_sample_size=0.0,
        )

    # Build feature matrix: [observation || one-hot(action)]
    n_actions = 5  # max candidates
    obs_dim = len(transitions[0].observation)
    feat_dim = obs_dim + n_actions

    def _features(obs: np.ndarray, action: int) -> np.ndarray:
        f = np.zeros(feat_dim, dtype=np.float32)
        f[:obs_dim] = obs
        if action < n_actions:
            f[obs_dim + action] = 1.0
        return f

    # Initialize Q-function weights (linear)
    weights = np.zeros(feat_dim, dtype=np.float64)

    for iteration in range(n_iterations):
        # Compute targets: r + γ · Q(s', π(s'))
        targets = []
        features = []

        for t in transitions:
            feat = _features(t.observation, t.action)
            features.append(feat)

            if t.done:
                target = t.reward
            else:
                # π_new(s')
                next_action, _ = new_policy.predict(t.next_observation)
                next_feat = _features(t.next_observation, next_action)
                target = t.reward + gamma * float(np.dot(weights, next_feat))

            targets.append(target)

        X = np.array(features)
        y = np.array(targets)

        # Simple least-squares fit with L2 regularization
        reg = 0.01 * np.eye(feat_dim)
        try:
            weights = np.linalg.solve(X.T @ X + reg, X.T @ y)
        except np.linalg.LinAlgError:
            logger.warning("fqe_singular_matrix | iteration={iteration}", iteration=iteration)
            break

    # Evaluate: average Q(s, π(s)) over initial states
    q_values = []
    for t in transitions:
        action, _ = new_policy.predict(t.observation)
        feat = _features(t.observation, action)
        q_values.append(float(np.dot(weights, feat)))

    estimated_value = float(np.mean(q_values)) if q_values else 0.0
    ci_low, ci_high = _bootstrap_ci(q_values)

    return OPEResult(
        estimator="FQE",
        estimated_value=estimated_value,
        confidence_interval=(ci_low, ci_high),
        n_samples=len(transitions),
        effective_sample_size=float(len(transitions)),
        details={"n_iterations": n_iterations, "weight_norm": float(np.linalg.norm(weights))},
    )


def _bootstrap_ci(
    values: list[float],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    normalize: bool = False,
) -> tuple[float, float]:
    """Compute bootstrap confidence interval.

    Parameters
    ----------
    values : list[float]
        Sample values to bootstrap over.
    n_bootstrap : int
        Number of bootstrap resamples.
    alpha : float
        Significance level (two-tailed).
    normalize : bool
        If ``True``, use self-normalized resampling.

    Returns
    -------
    tuple[float, float]
        Lower and upper bounds of the confidence interval.

    """
    if len(values) < 2:
        v = values[0] if values else 0.0
        return (v, v)

    arr = np.array(values)
    estimates = []

    rng = np.random.default_rng(42)
    for _ in range(n_bootstrap):
        sample = rng.choice(arr, size=len(arr), replace=True)
        if normalize:
            estimates.append(float(np.sum(sample) / max(np.sum(np.abs(sample)), 1e-8)))
        else:
            estimates.append(float(np.mean(sample)))

    low = float(np.percentile(estimates, 100 * alpha / 2))
    high = float(np.percentile(estimates, 100 * (1 - alpha / 2)))
    return (low, high)


__all__ = [
    "OPEResult",
    "importance_sampling",
    "weighted_importance_sampling",
    "fitted_q_evaluation",
]
