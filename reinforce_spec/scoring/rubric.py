"""Public rubric interface.

Re-exports rubric definitions from _internal for public consumption.
"""

from __future__ import annotations

from reinforce_spec._internal._rubric import (
    RUBRIC,
    Dimension,
    DimensionDefinition,
    ScoreCriterion,
    format_rubric_for_prompt,
    get_all_dimensions,
    get_default_weights,
    get_dimension_definition,
    validate_weights,
)

__all__ = [
    "RUBRIC",
    "Dimension",
    "DimensionDefinition",
    "ScoreCriterion",
    "format_rubric_for_prompt",
    "get_all_dimensions",
    "get_default_weights",
    "get_dimension_definition",
    "validate_weights",
]
