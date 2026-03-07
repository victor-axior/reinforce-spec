"""OpenAPI schema customisation.

Provides utilities for customising the auto-generated OpenAPI schema and
exporting it to a static YAML file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Generate or return the cached custom OpenAPI schema.

    Adds x-logo and enriched metadata beyond FastAPI defaults.
    """
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add custom extensions
    schema["info"]["x-logo"] = {
        "url": "https://github.com/reinforce-spec/reinforce-spec/raw/main/docs/logo.png"
    }
    schema["info"]["contact"] = {
        "name": "ReinforceSpec Team",
        "url": "https://github.com/reinforce-spec/reinforce-spec",
    }
    schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }

    app.openapi_schema = schema
    return schema


def export_openapi_yaml(app: FastAPI, path: str = "openapi.yml") -> None:
    """Write the OpenAPI schema to a YAML file.

    Parameters
    ----------
    app : FastAPI
        Application whose schema to export.
    path : str
        Output file path.

    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        import json
        from pathlib import Path

        # Fallback to JSON if PyYAML is unavailable
        json_path = path.replace(".yml", ".json").replace(".yaml", ".json")
        Path(json_path).write_text(json.dumps(custom_openapi(app), indent=2))
        return

    from pathlib import Path

    schema = custom_openapi(app)
    Path(path).write_text(yaml.dump(schema, default_flow_style=False, sort_keys=False))
