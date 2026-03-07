"""Extended persistence layer tests — covering uncovered Storage methods."""

from __future__ import annotations

import pytest

from reinforce_spec._internal._persistence import Storage


@pytest.fixture()
async def storage(tmp_path) -> Storage:
    db_path = tmp_path / "extended_test.db"
    store = Storage(db_path=db_path)
    await store.connect()
    yield store
    await store.close()


@pytest.mark.asyncio()
class TestStorageExtended:
    """Tests for Storage methods not already covered by integration tests."""

    async def test_db_property_raises_when_not_connected(self, tmp_path) -> None:
        store = Storage(db_path=tmp_path / "no_connect.db")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = store.db

    async def test_context_manager(self, tmp_path) -> None:
        db_path = tmp_path / "ctx.db"
        async with Storage(db_path=db_path) as store:
            assert store.db is not None
        # After exit, db should be None
        with pytest.raises(RuntimeError):
            _ = store.db

    async def test_fail_request(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-f01", n_specs=1)
        await storage.fail_request("req-f01", "something went wrong")
        req = await storage.get_request("req-f01")
        assert req is not None
        assert req["status"] == "failed"

    async def test_get_request_nonexistent(self, storage: Storage) -> None:
        result = await storage.get_request("does-not-exist")
        assert result is None

    async def test_save_dimension_scores(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-d01", n_specs=1)
        await storage.save_candidate(
            request_id="req-d01",
            spec_id="spec-d01",
            index_pos=0,
            content="test content",
        )
        scores = [
            {"dimension": "compliance_regulatory", "score": 4.0, "justification": "good"},
            {"dimension": "identity_access", "score": 3.5, "judge_model": "test/judge"},
        ]
        await storage.save_dimension_scores(spec_id="spec-d01", scores=scores)

        # Verify via raw query
        async with storage.db.execute(
            "SELECT * FROM dimension_scores WHERE spec_id = ?", ("spec-d01",)
        ) as cursor:
            rows = await cursor.fetchall()
            assert len(rows) == 2

    async def test_save_feedback_with_spec_id(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-fb1", n_specs=1)
        await storage.save_candidate(
            request_id="req-fb1",
            spec_id="spec-fb1",
            index_pos=0,
            content="test",
        )
        fid = await storage.save_feedback(
            request_id="req-fb1",
            rating=5.0,
            comment="Excellent",
            spec_id="spec-fb1",
        )
        assert isinstance(fid, str)

        feedback = await storage.get_feedback_for_request("req-fb1")
        assert len(feedback) == 1
        assert feedback[0]["spec_id"] == "spec-fb1"

    async def test_get_candidates_for_request_sorted(self, storage: Storage) -> None:
        await storage.save_request(request_id="req-sort", n_specs=2)
        await storage.save_candidate(
            request_id="req-sort",
            spec_id="s1",
            index_pos=0,
            content="a",
            composite_score=2.0,
        )
        await storage.save_candidate(
            request_id="req-sort",
            spec_id="s2",
            index_pos=1,
            content="b",
            composite_score=4.0,
        )
        candidates = await storage.get_candidates_for_request("req-sort")
        assert len(candidates) == 2
        assert candidates[0]["composite_score"] >= candidates[1]["composite_score"]

    async def test_cleanup_expired_idempotency_keys(self, storage: Storage) -> None:
        # Fresh store → no expired keys
        deleted = await storage.cleanup_expired_idempotency_keys()
        assert deleted == 0

    async def test_get_audit_log_all_types(self, storage: Storage) -> None:
        await storage.append_audit_log("type_a", {"a": 1})
        await storage.append_audit_log("type_b", {"b": 2})
        all_logs = await storage.get_audit_log()
        assert len(all_logs) == 2

    async def test_save_episode_with_policy_id(self, storage: Storage) -> None:
        eid = await storage.save_episode(
            request_id=None,
            observation=[1.0, 2.0],
            action=0,
            reward=1.0,
            policy_id="v001",
        )
        assert isinstance(eid, str)
        episodes = await storage.get_recent_episodes(limit=1)
        assert len(episodes) == 1
        assert episodes[0]["policy_id"] == "v001"

    async def test_close_twice(self, tmp_path) -> None:
        store = Storage(db_path=tmp_path / "double_close.db")
        await store.connect()
        await store.close()
        await store.close()  # should not raise
