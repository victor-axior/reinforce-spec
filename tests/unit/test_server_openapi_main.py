"""Batch 9 tests — OpenAPI, __main__, lazy imports, dependencies, server inits.

Covers:
  - reinforce_spec.server.openapi (custom_openapi, export_openapi_yaml)
  - reinforce_spec.server.__main__ (CLI arg parsing)
  - reinforce_spec.__init__ (top-level lazy imports)
  - reinforce_spec.server.dependencies (get_client)
  - reinforce_spec.observability.__init__ (lazy imports)
  - reinforce_spec.server.__init__
  - reinforce_spec._internal.__init__
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

# ── OpenAPI utilities ────────────────────────────────────────────────────────


class TestCustomOpenAPI:
    """Test OpenAPI schema customisation."""

    def test_generates_schema(self) -> None:
        from reinforce_spec.server.openapi import custom_openapi

        app = FastAPI(title="test", version="0.1.0", description="desc")
        schema = custom_openapi(app)
        assert "info" in schema
        assert schema["info"]["title"] == "test"
        assert "x-logo" in schema["info"]
        assert schema["info"]["license"]["name"] == "MIT"

    def test_caches_schema(self) -> None:
        from reinforce_spec.server.openapi import custom_openapi

        app = FastAPI(title="test", version="0.1.0")
        s1 = custom_openapi(app)
        s2 = custom_openapi(app)
        assert s1 is s2

    def test_export_yaml_with_pyyaml(self, tmp_path) -> None:
        from reinforce_spec.server.openapi import export_openapi_yaml

        app = FastAPI(title="test", version="0.1.0")
        path = str(tmp_path / "openapi.yml")
        export_openapi_yaml(app, path=path)
        assert Path(path).exists() or (tmp_path / "openapi.json").exists()

    def test_export_yaml_without_pyyaml(self, tmp_path) -> None:
        from reinforce_spec.server.openapi import export_openapi_yaml

        app = FastAPI(title="test", version="0.1.0")
        path = str(tmp_path / "openapi.yml")

        # Mock yaml import failure
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("no yaml")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            export_openapi_yaml(app, path=path)

        json_path = path.replace(".yml", ".json")
        assert Path(json_path).exists()


# ── Server __main__ CLI ──────────────────────────────────────────────────────


class TestServerMain:
    """Test CLI argument parsing (without actually running uvicorn)."""

    def test_parse_defaults(self) -> None:
        import argparse

        from reinforce_spec.server.__main__ import main

        with (
            patch("argparse.ArgumentParser.parse_args") as mock_args,
            patch("uvicorn.run") as mock_uvicorn,
        ):
            mock_args.return_value = argparse.Namespace(
                host="0.0.0.0", port=8000, reload=False, workers=1, log_level="info"
            )
            main()
            mock_uvicorn.assert_called_once()
            call_kwargs = mock_uvicorn.call_args
            assert call_kwargs[1]["port"] == 8000

    def test_parse_custom_args(self) -> None:
        import argparse

        from reinforce_spec.server.__main__ import main

        with (
            patch("argparse.ArgumentParser.parse_args") as mock_args,
            patch("uvicorn.run") as mock_uvicorn,
        ):
            mock_args.return_value = argparse.Namespace(
                host="127.0.0.1", port=9000, reload=True, workers=4, log_level="debug"
            )
            main()
            call_kwargs = mock_uvicorn.call_args
            assert call_kwargs[1]["port"] == 9000
            assert call_kwargs[1]["host"] == "127.0.0.1"
            assert call_kwargs[1]["workers"] == 4


# ── Top-level lazy imports ───────────────────────────────────────────────────


class TestTopLevelLazyImports:
    """Test reinforce_spec.__init__ lazy loading."""

    def test_reinforce_spec_client(self) -> None:
        from reinforce_spec import ReinforceSpec

        assert ReinforceSpec is not None

    def test_enterprise_scorer(self) -> None:
        from reinforce_spec import EnterpriseScorer

        assert EnterpriseScorer is not None

    def test_dimension(self) -> None:
        from reinforce_spec import Dimension

        assert Dimension is not None

    def test_types(self) -> None:
        from reinforce_spec import (
            CandidateSpec,
        )

        assert CandidateSpec is not None

    def test_exceptions(self) -> None:
        from reinforce_spec import (
            InputValidationError,
            ReinforceSpecError,
        )

        assert issubclass(InputValidationError, ReinforceSpecError)

    def test_unknown_attr_raises(self) -> None:
        import reinforce_spec

        with pytest.raises(AttributeError, match="no attribute"):
            reinforce_spec.__getattr__("NonExistent_Thing_123")

    def test_version(self) -> None:
        import reinforce_spec

        assert isinstance(reinforce_spec.__version__, str)


# ── Dependencies ─────────────────────────────────────────────────────────────


class TestDependencies:
    """Test FastAPI dependency injection helpers."""

    def test_get_client(self) -> None:
        from reinforce_spec.server.dependencies import get_client

        mock_request = MagicMock()
        mock_client = MagicMock()
        mock_request.app.state.client = mock_client

        result = get_client(mock_request)
        assert result is mock_client


# ── Observability __init__ lazy imports ──────────────────────────────────────


class TestObservabilityLazyImports:
    """Test observability package lazy loading."""

    def test_metrics_collector(self) -> None:
        from reinforce_spec.observability import MetricsCollector

        assert MetricsCollector is not None

    def test_audit_logger(self) -> None:
        from reinforce_spec.observability import AuditLogger

        assert AuditLogger is not None

    def test_unknown_attr_raises(self) -> None:
        from reinforce_spec import observability

        with pytest.raises(AttributeError):
            observability.__getattr__("NoSuchThing")

    def test_metrics_reexport(self) -> None:
        from reinforce_spec.observability.metrics import MetricsCollector

        assert MetricsCollector is not None


# ── Server __init__ ──────────────────────────────────────────────────────────


class TestServerInit:
    def test_server_package_importable(self) -> None:
        import reinforce_spec.server

        assert reinforce_spec.server is not None


# ── _internal __init__ ───────────────────────────────────────────────────────


class TestInternalInit:
    def test_internal_package_importable(self) -> None:
        import reinforce_spec._internal

        assert reinforce_spec._internal is not None


# ── scoring.calibration ─────────────────────────────────────────────────────


class TestCalibrationModule:
    def test_reexports(self) -> None:
        from reinforce_spec.scoring.calibration import (
            ScoreCalibrator,
        )

        assert ScoreCalibrator is not None


# ── scoring.judge ────────────────────────────────────────────────────────────


class TestJudgeModule:
    def test_reexport(self) -> None:
        from reinforce_spec.scoring.judge import EnterpriseScorer

        assert EnterpriseScorer is not None
