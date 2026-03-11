"""Tests for testing utilities."""

from __future__ import annotations

import pytest

from reinforce_spec_sdk.testing import (
    MockClient,
    make_candidate,
    make_dimension_score,
    make_policy_status,
    make_selection_response,
)
from reinforce_spec_sdk.types import PolicyStage


class TestMockClient:
    """Tests for MockClient."""

    @pytest.mark.asyncio
    async def test_select_returns_default(self):
        client = MockClient()
        response = await client.select(candidates=[{"content": "a"}, {"content": "b"}])
        assert response.request_id == "test-request-123"

    @pytest.mark.asyncio
    async def test_submit_feedback_records_calls(self):
        client = MockClient()
        fid1 = await client.submit_feedback("req-1", rating=4.0)
        fid2 = await client.submit_feedback("req-2", rating=5.0)
        assert len(client.get_feedback_calls()) == 2
        assert fid1 == "feedback-1"
        assert fid2 == "feedback-2"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with MockClient() as client:
            health = await client.health()
            assert health.status == "healthy"


class TestFactories:
    """Tests for test factory functions."""

    def test_make_dimension_score(self):
        score = make_dimension_score(dimension="Clarity", score=3.5)
        assert score.dimension == "Clarity"
        assert score.score == 3.5

    def test_make_candidate(self):
        candidate = make_candidate(index=1, composite_score=4.5)
        assert candidate.index == 1
        assert candidate.composite_score == 4.5
        assert len(candidate.dimension_scores) == 3

    def test_make_selection_response(self):
        resp = make_selection_response(num_candidates=3, selected_index=1)
        assert len(resp.all_candidates) == 3
        assert resp.selected.index == 1

    def test_make_policy_status(self):
        status = make_policy_status(version="v002", stage=PolicyStage.CANARY)
        assert status.version == "v002"
        assert status.stage == PolicyStage.CANARY
