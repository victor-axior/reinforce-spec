#!/usr/bin/env bash
# Run the full nightly test suite (statistical + behavioral).
set -euo pipefail

echo "==> Running behavioral tests..."
uv run pytest tests/behavioral/ -m behavioral --tb=long -v

echo "==> Running statistical tests..."
uv run pytest tests/statistical/ -m statistical --tb=long -v

echo "==> Running integration tests..."
uv run pytest tests/integration/ -m integration --tb=short -v

echo "✅ Nightly suite complete."
