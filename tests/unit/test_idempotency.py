"""Unit tests for the idempotency store."""

from __future__ import annotations

import pytest

from reinforce_spec._internal._idempotency import IdempotencyStore


@pytest.mark.asyncio()
class TestIdempotencyStore:
    """Test in-memory idempotency store."""

    async def test_check_returns_none_for_unseen_key(self) -> None:
        store = IdempotencyStore(ttl_seconds=60)
        await store.connect()
        result = await store.check("new-key")
        assert result is None
        await store.close()

    async def test_save_and_check(self) -> None:
        store = IdempotencyStore(ttl_seconds=60)
        await store.connect()
        await store.save("key-1", {"status": "ok"})
        result = await store.check("key-1")
        assert result == {"status": "ok"}
        await store.close()

    async def test_acquire_and_release(self) -> None:
        store = IdempotencyStore(ttl_seconds=60)
        await store.connect()
        acquired = await store.acquire("lock-key")
        assert acquired is True
        await store.release("lock-key")
        await store.close()

    async def test_ttl_expiration(self) -> None:
        store = IdempotencyStore(ttl_seconds=1)
        await store.connect()
        await store.save("expire-key", {"data": "value"})
        # Manually set the timestamp to be in the past
        import time

        store._memory["expire-key"] = (
            time.monotonic() - 2,
            {"data": "value"},
        )
        result = await store.check("expire-key")
        assert result is None
        await store.close()

    async def test_double_acquire_raises_conflict(self) -> None:
        from reinforce_spec._exceptions import IdempotencyConflictError

        store = IdempotencyStore(ttl_seconds=60)
        await store.connect()
        await store.acquire("dup-key")
        with pytest.raises(IdempotencyConflictError):
            await store.acquire("dup-key")
        await store.release("dup-key")
        await store.close()

    async def test_close_without_redis(self) -> None:
        store = IdempotencyStore(ttl_seconds=60)
        await store.connect()
        await store.close()  # should not raise

    async def test_release_nonexistent_key(self) -> None:
        store = IdempotencyStore(ttl_seconds=60)
        await store.connect()
        await store.release("never-acquired")  # should not raise
        await store.close()

    async def test_evict_expired(self) -> None:
        import time

        store = IdempotencyStore(ttl_seconds=1)
        await store.connect()
        store._memory["old"] = (time.monotonic() - 100, {"stale": True})
        store._memory["new"] = (time.monotonic(), {"fresh": True})
        store._evict_expired()
        assert "old" not in store._memory
        assert "new" in store._memory
        await store.close()
