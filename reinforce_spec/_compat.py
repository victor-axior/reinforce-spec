"""Compatibility shims for dependency version differences.

Isolates version-specific imports so the rest of the codebase can import
from _compat without caring about which version is installed.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
from typing import Any

# ── Pydantic version detection ────────────────────────────────────────────────

_pydantic_version = importlib.metadata.version("pydantic")
PYDANTIC_V2 = _pydantic_version.startswith("2.")

# ── Gym vs Gymnasium ──────────────────────────────────────────────────────────
# We use OpenAI Gym (gym) as specified. This shim ensures we can detect
# the version and handle API differences between gym 0.26.x and later.

try:
    GYM_AVAILABLE = importlib.util.find_spec("gym") is not None
    GYM_VERSION = importlib.metadata.version("gym") if GYM_AVAILABLE else "0.0.0"
except ImportError:
    GYM_AVAILABLE = False
    GYM_VERSION = "0.0.0"

# ── Stable-Baselines3 ────────────────────────────────────────────────────────

try:
    SB3_AVAILABLE = importlib.util.find_spec("stable_baselines3") is not None
    SB3_VERSION = importlib.metadata.version("stable-baselines3") if SB3_AVAILABLE else "0.0.0"
except ImportError:
    SB3_AVAILABLE = False
    SB3_VERSION = "0.0.0"

# ── Sentence Transformers ────────────────────────────────────────────────────

try:
    import sentence_transformers  # type: ignore[import-untyped]  # noqa: F401

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# ── Redis ─────────────────────────────────────────────────────────────────────

try:
    import redis  # type: ignore[import-untyped]  # noqa: F401

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ── MLflow ────────────────────────────────────────────────────────────────────

try:
    import mlflow  # type: ignore[import-untyped]  # noqa: F401

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

# ── Prometheus ────────────────────────────────────────────────────────────────

try:
    import prometheus_client  # type: ignore[import-untyped]  # noqa: F401

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# ── Utility ───────────────────────────────────────────────────────────────────


def require_dependency(name: str, extra: str = "") -> Any:
    """Import and return a module, raising a clear error if missing.

    Parameters
    ----------
    name : str
        The module name to import (e.g. ``"gym"``).
    extra : str
        The pip extra to suggest (e.g. ``"redis"``).  When empty, the
        install suggestion falls back to ``pip install <name>``.

    Returns
    -------
    types.ModuleType
        The imported module.

    Raises
    ------
    ImportError
        If the module is not installed.

    """
    try:
        return importlib.import_module(name)
    except ImportError:
        install = f"pip install reinforce-spec[{extra}]" if extra else f"pip install {name}"
        raise ImportError(
            f"{name!r} is required but not installed. Install it with: {install}"
        ) from None


def python_version_info() -> str:
    """Return a human-readable Python version string."""
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"
