"""Public interface for the spec-selection Gym environment.

Re-exports the core ``SpecSelectionEnv`` plus feature-engineering helpers
so that downstream code never needs to import from ``_internal``.

Examples
--------
>>> from reinforce_spec.rl.environment import SpecSelectionEnv, build_observation
>>> env = SpecSelectionEnv()
>>> obs = env.reset()
"""

from __future__ import annotations

from reinforce_spec._internal._environment import (
    N_DIMENSIONS,
    PER_CANDIDATE_FEATURES,
    SpecSelectionEnv,
    build_observation,
)

__all__ = [
    "N_DIMENSIONS",
    "PER_CANDIDATE_FEATURES",
    "SpecSelectionEnv",
    "build_observation",
]
