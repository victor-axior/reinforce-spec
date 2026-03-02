#!/usr/bin/env bash
# Run the standard test suite (unit + property).
set -euo pipefail

echo "==> Running unit and property tests..."
uv run pytest tests/unit/ tests/property/ \
    -m "not statistical and not slow" \
    --tb=short -q \
    --cov=reinforce_spec \
    --cov-report=term-missing \
    "$@"
