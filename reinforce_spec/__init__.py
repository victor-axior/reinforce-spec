"""Reinforce-Spec: RL-optimized enterprise spec evaluation and selection SDK."""

from __future__ import annotations

from reinforce_spec.version import VERSION

__version__ = VERSION
__all__ = [
    "CandidateSpec",
    "ConfigurationError",
    "Dimension",
    "DimensionScore",
    # ── Scoring ───────────────────────────────────────────────────────────────
    "EnterpriseScorer",
    "InputValidationError",
    "PolicyError",
    "PolicyManager",
    # ── Client ────────────────────────────────────────────────────────────────
    "ReinforceSpec",
    # ── Exceptions ────────────────────────────────────────────────────────────
    "ReinforceSpecError",
    "ScoringError",
    "ScoringPreset",
    "ScoringWeights",
    "SelectionMethod",
    "SelectionRequest",
    "SelectionResponse",
    "SpecFormat",
    # ── Types ─────────────────────────────────────────────────────────────────
    "SpecResult",
    # ── RL ─────────────────────────────────────────────────────────────────────
    "SpecSelectionEnv",
    "UpstreamError",
]


def __getattr__(name: str) -> object:
    """Lazy imports to avoid loading heavy dependencies on import."""
    # Mapping of public names to their module paths
    _lazy_imports: dict[str, tuple[str, str]] = {
        # Client
        "ReinforceSpec": ("reinforce_spec.client", "ReinforceSpec"),
        # Scoring
        "EnterpriseScorer": ("reinforce_spec.scoring", "EnterpriseScorer"),
        "ScoringPreset": ("reinforce_spec.scoring", "ScoringPreset"),
        "Dimension": ("reinforce_spec.scoring", "Dimension"),
        # RL
        "SpecSelectionEnv": ("reinforce_spec.rl", "SpecSelectionEnv"),
        "PolicyManager": ("reinforce_spec.rl", "PolicyManager"),
        # Types
        "SpecResult": ("reinforce_spec.types", "SpecResult"),
        "DimensionScore": ("reinforce_spec.types", "DimensionScore"),
        "ScoringWeights": ("reinforce_spec.types", "ScoringWeights"),
        "CandidateSpec": ("reinforce_spec.types", "CandidateSpec"),
        "SpecFormat": ("reinforce_spec.types", "SpecFormat"),
        "SelectionRequest": ("reinforce_spec.types", "SelectionRequest"),
        "SelectionResponse": ("reinforce_spec.types", "SelectionResponse"),
        "SelectionMethod": ("reinforce_spec.types", "SelectionMethod"),
        # Exceptions
        "ReinforceSpecError": ("reinforce_spec._exceptions", "ReinforceSpecError"),
        "InputValidationError": ("reinforce_spec._exceptions", "InputValidationError"),
        "ScoringError": ("reinforce_spec._exceptions", "ScoringError"),
        "PolicyError": ("reinforce_spec._exceptions", "PolicyError"),
        "ConfigurationError": ("reinforce_spec._exceptions", "ConfigurationError"),
        "UpstreamError": ("reinforce_spec._exceptions", "UpstreamError"),
    }

    if name in _lazy_imports:
        module_path, attr_name = _lazy_imports[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, attr_name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
