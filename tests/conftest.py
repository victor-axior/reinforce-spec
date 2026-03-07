"""Shared test fixtures and configuration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from reinforce_spec._internal._config import AppConfig
from reinforce_spec.types import CandidateSpec, DimensionScore

if TYPE_CHECKING:
    from collections.abc import Generator

# ── Fixtures Directory ────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list | dict:
    """Load a JSON fixture file by name (without extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text())


# ── Pytest Configuration ─────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: integration tests (mocked LLM)")
    config.addinivalue_line("markers", "behavioral: behavioral invariant tests")
    config.addinivalue_line("markers", "statistical: statistical distribution tests (nightly)")
    config.addinivalue_line("markers", "slow: slow tests excluded from CI by default")


# ── Session Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def test_config() -> AppConfig:
    """Minimal config for testing (no real API calls)."""
    return AppConfig.for_testing()


# ── Sample Data Fixtures ─────────────────────────────────────────────────────

SPEC_TYPES = ["srs", "api", "architecture", "prd", "test_plan"]


@pytest.fixture()
def sample_candidates() -> list[CandidateSpec]:
    """Five sample scored candidates for testing."""
    candidates = []
    for i in range(5):
        candidate = CandidateSpec(
            index=i,
            spec_type=SPEC_TYPES[i % len(SPEC_TYPES)],
            content=f"Sample specification content #{i}. " * 20,
            source_model="test-model",
            composite_score=3.0 + i * 0.3,
            dimension_scores=[
                DimensionScore(
                    dimension=f"dim_{d}",
                    score=2.5 + i * 0.2 + d * 0.1,
                    justification=f"Test justification for dim_{d}",
                )
                for d in range(12)
            ],
        )
        candidates.append(candidate)
    return candidates


@pytest.fixture()
def sample_specs_fixture() -> list[dict]:
    """Load sample spec fixtures from JSON."""
    return load_fixture("sample_specs")


@pytest.fixture()
def calibration_anchors_fixture() -> list[dict]:
    """Load calibration anchor fixtures from JSON."""
    return load_fixture("calibration_anchors")


@pytest.fixture()
def scoring_weights_fixture() -> dict:
    """Load scoring weight fixtures from JSON."""
    return load_fixture("scoring_weights")
