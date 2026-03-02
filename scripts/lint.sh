#!/usr/bin/env bash
# Lint the codebase with ruff.
set -euo pipefail

echo "==> Running ruff check..."
uv run ruff check reinforce_spec/ tests/

echo "==> Running mypy..."
uv run mypy reinforce_spec/

echo "✅ All lint checks passed."
