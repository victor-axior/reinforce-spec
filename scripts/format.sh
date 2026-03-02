#!/usr/bin/env bash
# Auto-format the codebase with ruff.
set -euo pipefail

echo "==> Running ruff format..."
uv run ruff format reinforce_spec/ tests/

echo "==> Running ruff check --fix..."
uv run ruff check --fix reinforce_spec/ tests/

echo "✅ Formatting complete."
