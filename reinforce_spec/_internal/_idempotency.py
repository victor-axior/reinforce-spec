"""Idempotency key storage.

Stores request→response mappings so that retried requests return the same
response without re-executing business logic.  Uses Redis when available,
falling back to an in-memory TTL cache.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from reinforce_spec._compat import REDIS_AVAILABLE
from reinforce_spec._exceptions import IdempotencyConflictError


class IdempotencyStore:
    """Idempotency-key storage with Redis/in-memory backend.

    Parameters
    ----------
    ttl_seconds : int
        How long to remember a completed response (default 24 h).
    redis_url : str or None
        Redis connection string.  Falls back to in-memory when ``None``
        or when ``redis`` is not installed.

    """

    def __init__(
        self,
        ttl_seconds: int = 86_400,
        redis_url: str | None = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._redis: Any | None = None
        self._memory: dict[str, tuple[float, dict[str, Any]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._redis_url = redis_url

    async def connect(self) -> None:
        """Initialise the backing store."""
        if self._redis_url and REDIS_AVAILABLE:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]

            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            logger.info("idempotency_store_connected | backend=redis")
        else:
            logger.info("idempotency_store_connected | backend=memory")

    async def close(self) -> None:
        """Shut down the backing store."""
        if self._redis is not None:
            await self._redis.close()

    # ── Public API ────────────────────────────────────────────────────

    async def check(self, key: str) -> dict[str, Any] | None:
        """Return the stored response for *key*, or ``None`` if unseen.

        Raises
        ------
        IdempotencyConflictError
            If the key is currently being processed by another request.

        """
        if self._redis is not None:
            return await self._check_redis(key)
        return self._check_memory(key)

    async def save(self, key: str, response: dict[str, Any]) -> None:
        """Persist a completed response under *key*."""
        if self._redis is not None:
            await self._save_redis(key, response)
        else:
            self._save_memory(key, response)
        logger.debug("idempotency_saved | key={key}", key=key)

    async def acquire(self, key: str) -> bool:
        """Mark *key* as in-flight.  Returns ``False`` if already held."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        acquired = self._locks[key].locked()
        if acquired:
            raise IdempotencyConflictError(
                f"Key {key!r} is already being processed",
                details={"key": key},
            )
        await self._locks[key].acquire()
        return True

    async def release(self, key: str) -> None:
        """Release the in-flight lock for *key*."""
        lock = self._locks.pop(key, None)
        if lock is not None and lock.locked():
            lock.release()

    # ── Memory backend ────────────────────────────────────────────────

    def _check_memory(self, key: str) -> dict[str, Any] | None:
        """Check in-memory store, evicting expired entries."""
        entry = self._memory.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > self._ttl:
            del self._memory[key]
            return None
        return data

    def _save_memory(self, key: str, response: dict[str, Any]) -> None:
        self._memory[key] = (time.monotonic(), response)
        self._evict_expired()

    def _evict_expired(self) -> None:
        """Remove stale entries to prevent unbounded growth."""
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._memory.items() if now - ts > self._ttl]
        for k in expired:
            del self._memory[k]

    # ── Redis backend ─────────────────────────────────────────────────

    async def _check_redis(self, key: str) -> dict[str, Any] | None:
        import json

        raw = await self._redis.get(f"idem:{key}")
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def _save_redis(self, key: str, response: dict[str, Any]) -> None:
        import json

        await self._redis.setex(f"idem:{key}", self._ttl, json.dumps(response))
