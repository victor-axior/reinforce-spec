"""Integration tests for the persistence layer."""

from __future__ import annotations

import os

import pytest

from reinforce_spec._internal._persistence import Storage


@pytest.fixture()
async def storage() -> Storage:
    """Create a storage instance backed by PostgreSQL.

    Set TEST_DATABASE_URL to run these tests.
    """
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")

    store = Storage(database_url=database_url)
    await store.connect()
    yield store
    await store.close()


@pytest.mark.asyncio()
@pytest.mark.integration()
class TestStorage:
    """Test async PostgreSQL storage."""

    async def test_save_and_get_request(self, storage: Storage) -> None:
        await storage.save_request(
            request_id="req-001",
            n_specs=5,
            description="Design a payment service",
            customer_type="bank",
        )
        result = await storage.get_request("req-001")
        assert result is not None
        assert result["description"] == "Design a payment service"
        assert result["status"] == "pending"

    async def test_complete_request(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-002", n_specs=3)
        await storage.complete_request("req-002")
        result = await storage.get_request("req-002")
        assert result["status"] == "completed"

    async def test_save_candidate(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-003", n_specs=1)
        await storage.save_candidate(
            request_id="req-003",
            spec_id="spec-001",
            index_pos=0,
            spec_type="api",
            spec_format="json",
            content="API spec content",
            composite_score=4.2,
        )
        candidates = await storage.get_candidates_for_request("req-003")
        assert len(candidates) == 1
        assert candidates[0]["spec_type"] == "api"

    async def test_save_feedback(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-004", n_specs=1)
        fid = await storage.save_feedback(request_id="req-004", rating=4.5, comment="Great spec")
        assert fid is not None

        feedback = await storage.get_feedback_for_request("req-004")
        assert len(feedback) == 1
        assert feedback[0]["rating"] == 4.5

    async def test_audit_log(self, storage: Storage) -> None:
        await storage.append_audit_log(
            "test_event",
            {"key": "value"},
            actor="test",
        )
        logs = await storage.get_audit_log(event_type="test_event")
        assert len(logs) == 1
        assert logs[0]["actor"] == "test"

    async def test_idempotency_key(self, storage: Storage) -> None:
        await storage.set_idempotent_response("key-1", '{"result": "ok"}')
        result = await storage.get_idempotent_response("key-1")
        assert result == '{"result": "ok"}'

    async def test_idempotency_key_missing(self, storage: Storage) -> None:
        result = await storage.get_idempotent_response("nonexistent")
        assert result is None

    async def test_save_episode(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-005", n_specs=1)
        eid = await storage.save_episode(
            request_id="req-005",
            observation=[0.1, 0.2, 0.3],
            action=2,
            reward=4.0,
        )
        assert eid is not None

        episodes = await storage.get_recent_episodes(limit=10)
        assert len(episodes) >= 1
