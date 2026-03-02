"""Off-policy evaluation public API.

Wraps the internal OPE estimators with a simpler interface.

Examples
--------
>>> from reinforce_spec.rl.evaluation import evaluate_policy
>>> result = evaluate_policy(transitions, new_policy, behavior_probs)
>>> print(result.estimated_value, result.confidence_interval)
"""

from __future__ import annotations

from reinforce_spec._internal._ope import (
    OPEResult,
    importance_sampling,
    weighted_importance_sampling,
)
from reinforce_spec._internal._policy import PPOPolicy
from reinforce_spec._internal._replay_buffer import Transition

__all__ = [
    "OPEResult",
    "evaluate_policy",
    "importance_sampling",
    "weighted_importance_sampling",
]


def evaluate_policy(
    transitions: list[Transition],
    new_policy: PPOPolicy,
    behavior_probs: list[float],
    gamma: float = 0.99,
    method: str = "wis",
) -> OPEResult:
    """Evaluate a new policy using off-policy data.

    Parameters
    ----------
    transitions : list[Transition]
        Logged transitions from the behavior policy.
    new_policy : PPOPolicy
        The policy to evaluate.
    behavior_probs : list[float]
        π_old(a|s) for each transition.
    gamma : float
        Discount factor (default 0.99).
    method : str
        Estimator: ``"is"`` (importance sampling) or ``"wis"`` (weighted IS).

    Returns
    -------
    OPEResult
        Estimate with confidence interval and diagnostics.

    """
    if method == "is":
        return importance_sampling(transitions, new_policy, behavior_probs, gamma)
    return weighted_importance_sampling(transitions, new_policy, behavior_probs, gamma)
