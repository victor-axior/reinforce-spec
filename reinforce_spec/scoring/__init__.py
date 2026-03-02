"""Public scoring API.

Provides the EnterpriseScorer and scoring utilities.
"""

from __future__ import annotations

from reinforce_spec._internal._rubric import (
    Dimension,
    DimensionDefinition,
    format_rubric_for_prompt,
    get_all_dimensions,
    get_default_weights,
    get_dimension_definition,
    validate_weights,
)
from reinforce_spec.scoring.presets import get_preset, list_presets

# ScoringPreset is an alias for the presets dict
ScoringPreset = dict[str, float]

__all__ = [
    "Dimension",
    "DimensionDefinition",
    "EnterpriseScorer",
    "ScoringPreset",
    "format_rubric_for_prompt",
    "get_all_dimensions",
    "get_default_weights",
    "get_dimension_definition",
    "get_preset",
    "list_presets",
    "validate_weights",
]


# Defer EnterpriseScorer import to avoid circular deps
def __getattr__(name: str) -> object:
    if name == "EnterpriseScorer":
        from reinforce_spec.scoring.judge import EnterpriseScorer

        return EnterpriseScorer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
