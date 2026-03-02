"""Public RL API.

Provides the Gym environment, policy manager, replay buffer,
trainer, selector, registry, and off-policy evaluation.
"""

from __future__ import annotations

__all__ = [
    "PolicyManager",
    "PolicyRegistry",
    "Selector",
    "SpecSelectionEnv",
    "Trainer",
    "evaluate_policy",
]


def __getattr__(name: str) -> object:
    if name == "SpecSelectionEnv":
        from reinforce_spec.rl.environment import SpecSelectionEnv

        return SpecSelectionEnv
    if name == "PolicyManager":
        from reinforce_spec._internal._policy import PolicyManager

        return PolicyManager
    if name == "Trainer":
        from reinforce_spec.rl.trainer import Trainer

        return Trainer
    if name == "Selector":
        from reinforce_spec.rl.selector import Selector

        return Selector
    if name == "PolicyRegistry":
        from reinforce_spec.rl.registry import PolicyRegistry

        return PolicyRegistry
    if name == "evaluate_policy":
        from reinforce_spec.rl.evaluation import evaluate_policy

        return evaluate_policy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
