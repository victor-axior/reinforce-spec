# Contributing to ReinforceSpec

Thank you for your interest in contributing! This document provides guidelines
for contributing to the project.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/reinforce-spec/reinforce-spec.git
cd reinforce-spec

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (including dev extras)
uv sync --all-extras

# Run the test suite (unit + property)
uv run pytest tests/unit/ tests/property/ -q

# Run linting
uv run ruff check reinforce_spec/ tests/
uv run ruff format --check reinforce_spec/ tests/
```

## Code Style

- **Formatter**: [Ruff](https://docs.astral.sh/ruff/) (line length 100)
- **Type checking**: [mypy](https://mypy-lang.org/) in strict mode
- **Docstrings**: NumPy-style (`Parameters`, `Returns`, `Raises` sections)
- **Imports**: `from __future__ import annotations` in every file
- **Logging**: Use [loguru](https://github.com/Delgan/loguru) — never `print()`

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`.
2. **Write tests** for any new functionality in the appropriate test directory:
   - `tests/unit/` — fast, isolated unit tests
   - `tests/integration/` — tests requiring external services
   - `tests/behavioral/` — invariant checks
   - `tests/property/` — Hypothesis property-based tests
3. **Ensure all tests pass**: `uv run pytest tests/unit/ tests/property/ -q`
4. **Lint your code**: `uv run ruff check --fix . && uv run ruff format .`
5. **Type-check**: `uv run mypy reinforce_spec/`
6. **Submit a PR** with a clear description of changes.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add drift detection alerting
fix: handle edge case in PSI calculation
docs: update API endpoint documentation
test: add property tests for clamp()
refactor: split server routes into sub-package
```

## Architecture

The project follows the **specs → RL selection** pipeline:

1. **User provides spec candidates** (no generation)
2. **Multi-judge scoring** via LLM ensemble (12 enterprise dimensions)
3. **RL-based selection** using PPO policy trained on feedback
4. **Feedback loop** shapes future policy training

Key packages:
- `reinforce_spec/_internal/` — Private implementation details
- `reinforce_spec/scoring/` — Rubric, calibration, presets
- `reinforce_spec/rl/` — Public RL API (environment, trainer, selector)
- `reinforce_spec/server/` — FastAPI server
- `reinforce_spec/observability/` — Metrics, experiments, audit logging

## Integration Tests (PostgreSQL)

Set a `TEST_DATABASE_URL` before running integration tests, for example:

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/reinforce_spec_test \
   uv run pytest tests/integration/ -q
```

## Reporting Issues

- Use GitHub Issues for bugs and feature requests
- Include reproduction steps and environment details
- Label issues appropriately (`bug`, `enhancement`, `documentation`)
