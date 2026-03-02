"""Unit tests for compatibility shims."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from reinforce_spec._compat import (
    GYM_AVAILABLE,
    GYM_VERSION,
    MLFLOW_AVAILABLE,
    PYDANTIC_V2,
    PROMETHEUS_AVAILABLE,
    REDIS_AVAILABLE,
    SB3_AVAILABLE,
    SB3_VERSION,
    SENTENCE_TRANSFORMERS_AVAILABLE,
    python_version_info,
    require_dependency,
)


class TestCompatFlags:
    """Test dependency detection flags."""

    def test_pydantic_v2_is_bool(self) -> None:
        assert isinstance(PYDANTIC_V2, bool)

    def test_pydantic_v2_detected(self) -> None:
        # We know pydantic v2 is installed in this project
        assert PYDANTIC_V2 is True

    def test_gym_available_is_bool(self) -> None:
        assert isinstance(GYM_AVAILABLE, bool)

    def test_gym_version_is_str(self) -> None:
        assert isinstance(GYM_VERSION, str)
        if GYM_AVAILABLE:
            parts = GYM_VERSION.split(".")
            assert len(parts) >= 2

    def test_sb3_available_is_bool(self) -> None:
        assert isinstance(SB3_AVAILABLE, bool)

    def test_sb3_version_is_str(self) -> None:
        assert isinstance(SB3_VERSION, str)
        if SB3_AVAILABLE:
            parts = SB3_VERSION.split(".")
            assert len(parts) >= 2

    def test_sentence_transformers_is_bool(self) -> None:
        assert isinstance(SENTENCE_TRANSFORMERS_AVAILABLE, bool)

    def test_redis_is_bool(self) -> None:
        assert isinstance(REDIS_AVAILABLE, bool)

    def test_mlflow_is_bool(self) -> None:
        assert isinstance(MLFLOW_AVAILABLE, bool)

    def test_prometheus_is_bool(self) -> None:
        assert isinstance(PROMETHEUS_AVAILABLE, bool)


class TestRequireDependency:
    """Test the require_dependency utility."""

    def test_require_installed_module(self) -> None:
        mod = require_dependency("json")
        assert hasattr(mod, "dumps")

    def test_require_missing_module_raises(self) -> None:
        with pytest.raises(ImportError, match="not installed"):
            require_dependency("nonexistent_module_xyz_12345")

    def test_require_missing_with_extra_hint(self) -> None:
        with pytest.raises(ImportError, match=r"pip install reinforce-spec\[redis\]"):
            require_dependency("nonexistent_module_xyz_12345", extra="redis")

    def test_require_missing_without_extra_hint(self) -> None:
        with pytest.raises(ImportError, match="pip install nonexistent_module"):
            require_dependency("nonexistent_module")

    def test_require_returns_module(self) -> None:
        mod = require_dependency("os")
        assert hasattr(mod, "path")


class TestPythonVersionInfo:
    """Test python_version_info utility."""

    def test_returns_version_string(self) -> None:
        result = python_version_info()
        v = sys.version_info
        assert result == f"{v.major}.{v.minor}.{v.micro}"

    def test_format_is_dotted(self) -> None:
        result = python_version_info()
        parts = result.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
