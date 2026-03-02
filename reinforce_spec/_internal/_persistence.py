"""Persistence layer — async SQLite storage.

Provides durable storage for:
  - Spec generation requests and results
  - Scoring records and dimension breakdowns
  - RL training transitions
  - Feedback signals
  - Audit log entries
  - Idempotency keys

Uses ``aiosqlite`` for fully async I/O; schema is created lazily on
first connection.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite
from loguru import logger

from reinforce_spec._internal._utils import generate_request_id, utc_now

# ── Schema ───────────────────────────────────────────────────────────────────

SCHEMA_SQL = """\
-- Idempotency keys
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key             TEXT PRIMARY KEY,
    response_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL
);

-- Spec evaluation requests
CREATE TABLE IF NOT EXISTS evaluation_requests (
    request_id      TEXT PRIMARY KEY,
    description     TEXT NOT NULL DEFAULT '',
    customer_type   TEXT,
    n_specs         INTEGER NOT NULL DEFAULT 5,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
);

-- Individual candidate specs
CREATE TABLE IF NOT EXISTS candidate_specs (
    spec_id         TEXT PRIMARY KEY,
    request_id      TEXT NOT NULL REFERENCES evaluation_requests(request_id),
    index_pos       INTEGER NOT NULL,
    spec_type       TEXT NOT NULL DEFAULT '',
    spec_format     TEXT NOT NULL DEFAULT 'text',
    content         TEXT NOT NULL,
    source_model    TEXT,
    composite_score REAL,
    is_selected     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

-- Dimension scores per candidate
CREATE TABLE IF NOT EXISTS dimension_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_id         TEXT NOT NULL REFERENCES candidate_specs(spec_id),
    dimension       TEXT NOT NULL,
    score           REAL NOT NULL,
    justification   TEXT,
    judge_model     TEXT
);

-- User feedback signals
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id     TEXT PRIMARY KEY,
    request_id      TEXT NOT NULL REFERENCES evaluation_requests(request_id),
    spec_id         TEXT,
    rating          REAL,
    comment         TEXT,
    created_at      TEXT NOT NULL
);

-- RL training episodes
CREATE TABLE IF NOT EXISTS rl_episodes (
    episode_id      TEXT PRIMARY KEY,
    request_id      TEXT REFERENCES evaluation_requests(request_id),
    observation     TEXT NOT NULL,  -- JSON array
    action          INTEGER NOT NULL,
    reward          REAL NOT NULL,
    policy_id       TEXT,
    created_at      TEXT NOT NULL
);

-- Audit log (immutable append-only)
CREATE TABLE IF NOT EXISTS audit_log (
    log_id          TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,
    actor           TEXT NOT NULL DEFAULT 'system',
    payload         TEXT NOT NULL,  -- JSON
    created_at      TEXT NOT NULL
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_specs_request ON candidate_specs(request_id);
CREATE INDEX IF NOT EXISTS idx_scores_spec ON dimension_scores(spec_id);
CREATE INDEX IF NOT EXISTS idx_feedback_request ON feedback(request_id);
CREATE INDEX IF NOT EXISTS idx_episodes_request ON rl_episodes(request_id);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys(expires_at);
"""


# ── Storage Backend ──────────────────────────────────────────────────────────


class Storage:
    """Async SQLite storage backend.

    Usage::

        async with Storage("data/reinforce.db") as store:
            await store.save_request(...)

    """

    def __init__(self, db_path: str | Path = "data/reinforce_spec.db") -> None:
        """Initialise the storage backend.

        Parameters
        ----------
        db_path : str or Path
            Filesystem path for the SQLite database file.

        """
        self._db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open database connection and ensure schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info("storage_connected | path={path}", path=str(self._db_path))

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> Storage:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    @property
    def db(self) -> aiosqlite.Connection:
        """Return the active database connection.

        Returns
        -------
        aiosqlite.Connection
            The underlying async SQLite connection.

        Raises
        ------
        RuntimeError
            If the storage is not connected.

        """
        if self._db is None:
            raise RuntimeError("Storage not connected. Call connect() first.")
        return self._db

    # ── Idempotency ──────────────────────────────────────────────────────

    async def get_idempotent_response(self, key: str) -> str | None:
        """Return cached response for an idempotency key.

        Parameters
        ----------
        key : str
            The idempotency key to look up.

        Returns
        -------
        str or None
            Cached JSON response, or ``None`` if not found or expired.

        """
        async with self.db.execute(
            "SELECT response_json FROM idempotency_keys "
            "WHERE key = ? AND expires_at > ?",
            (key, utc_now().isoformat()),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_idempotent_response(
        self, key: str, response_json: str, ttl_hours: int = 24
    ) -> None:
        """Cache a response for the idempotency key.

        Parameters
        ----------
        key : str
            The idempotency key.
        response_json : str
            Serialised JSON response to cache.
        ttl_hours : int
            Time-to-live in hours before expiry.

        """
        now = utc_now()
        expires = datetime(
            now.year, now.month, now.day, now.hour + ttl_hours,
            now.minute, now.second, tzinfo=now.tzinfo,
        )
        await self.db.execute(
            "INSERT OR REPLACE INTO idempotency_keys (key, response_json, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (key, response_json, now.isoformat(), expires.isoformat()),
        )
        await self.db.commit()

    async def cleanup_expired_idempotency_keys(self) -> int:
        """Remove expired idempotency keys.

        Returns
        -------
        int
            Number of keys deleted.

        """
        cursor = await self.db.execute(
            "DELETE FROM idempotency_keys WHERE expires_at <= ?",
            (utc_now().isoformat(),),
        )
        await self.db.commit()
        return cursor.rowcount

    # ── Generation Requests ──────────────────────────────────────────────

    async def save_request(
        self,
        request_id: str,
        n_specs: int,
        description: str = "",
        customer_type: str | None = None,
    ) -> None:
        """Persist a new evaluation request.

        Parameters
        ----------
        request_id : str
            Unique request identifier.
        n_specs : int
            Number of candidate specs to generate.
        description : str
            Free-text problem description.
        customer_type : str or None
            Optional customer segment label.

        """
        await self.db.execute(
            "INSERT INTO evaluation_requests "
            "(request_id, description, customer_type, n_specs, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                request_id,
                description,
                customer_type,
                n_specs,
                utc_now().isoformat(),
                "pending",
            ),
        )
        await self.db.commit()

    async def complete_request(self, request_id: str) -> None:
        """Mark a request as completed.

        Parameters
        ----------
        request_id : str
            Unique request identifier.

        """
        await self.db.execute(
            "UPDATE evaluation_requests SET status = 'completed', completed_at = ? "
            "WHERE request_id = ?",
            (utc_now().isoformat(), request_id),
        )
        await self.db.commit()

    async def fail_request(self, request_id: str, error: str) -> None:
        """Mark a request as failed and log the error.

        Parameters
        ----------
        request_id : str
            Unique request identifier.
        error : str
            Error description to record in the audit log.

        """
        await self.db.execute(
            "UPDATE evaluation_requests SET status = 'failed', completed_at = ? "
            "WHERE request_id = ?",
            (utc_now().isoformat(), request_id),
        )
        await self.db.commit()
        await self.append_audit_log("request_failed", {"request_id": request_id, "error": error})

    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        """Retrieve a request by its identifier.

        Parameters
        ----------
        request_id : str
            Unique request identifier.

        Returns
        -------
        dict[str, Any] or None
            Row data as a dictionary, or ``None`` if not found.

        """
        async with self.db.execute(
            "SELECT * FROM evaluation_requests WHERE request_id = ?",
            (request_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))

    # ── Candidate Specs ──────────────────────────────────────────────────

    async def save_candidate(
        self,
        request_id: str,
        spec_id: str,
        index_pos: int,
        spec_type: str = "",
        spec_format: str = "text",
        content: str = "",
        source_model: str | None = None,
        composite_score: float | None = None,
        is_selected: bool = False,
    ) -> None:
        """Persist a candidate spec.

        Parameters
        ----------
        request_id : str
            Parent request identifier.
        spec_id : str
            Unique candidate identifier.
        index_pos : int
            Zero-based position in the candidate list.
        spec_type : str
            Category label for the spec.
        spec_format : str
            Content format (``'text'``, ``'json'``, etc.).
        content : str
            Raw spec content.
        source_model : str or None
            LLM model that generated the spec.
        composite_score : float or None
            Aggregate score from the scoring pipeline.
        is_selected : bool
            Whether this candidate was ultimately selected.

        """
        await self.db.execute(
            "INSERT INTO candidate_specs "
            "(spec_id, request_id, index_pos, spec_type, spec_format, content, "
            "source_model, composite_score, is_selected, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                spec_id,
                request_id,
                index_pos,
                spec_type,
                spec_format,
                content,
                source_model,
                composite_score,
                1 if is_selected else 0,
                utc_now().isoformat(),
            ),
        )
        await self.db.commit()

    async def save_dimension_scores(
        self,
        spec_id: str,
        scores: list[dict[str, Any]],
    ) -> None:
        """Save dimension scores for a candidate spec.

        Parameters
        ----------
        spec_id : str
            Candidate identifier the scores belong to.
        scores : list[dict[str, Any]]
            Each dict must contain ``'dimension'`` and ``'score'``; may also
            include ``'justification'`` and ``'judge_model'``.

        """
        for s in scores:
            await self.db.execute(
                "INSERT INTO dimension_scores (spec_id, dimension, score, justification, judge_model) "
                "VALUES (?, ?, ?, ?, ?)",
                (spec_id, s["dimension"], s["score"], s.get("justification"), s.get("judge_model")),
            )
        await self.db.commit()

    async def get_candidates_for_request(
        self, request_id: str
    ) -> list[dict[str, Any]]:
        """Retrieve all candidates for a request, ordered by score.

        Parameters
        ----------
        request_id : str
            Parent request identifier.

        Returns
        -------
        list[dict[str, Any]]
            Candidate rows sorted by composite score descending.

        """
        async with self.db.execute(
            "SELECT * FROM candidate_specs WHERE request_id = ? ORDER BY composite_score DESC",
            (request_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

    # ── Feedback ─────────────────────────────────────────────────────────

    async def save_feedback(
        self,
        request_id: str,
        rating: float | None = None,
        comment: str | None = None,
        spec_id: str | None = None,
    ) -> str:
        """Record user feedback for a request.

        Parameters
        ----------
        request_id : str
            Parent request identifier.
        rating : float or None
            Numeric rating (e.g. 1–5).
        comment : str or None
            Free-text comment.
        spec_id : str or None
            Specific candidate the feedback targets.

        Returns
        -------
        str
            The generated feedback identifier.

        """
        feedback_id = generate_request_id()
        await self.db.execute(
            "INSERT INTO feedback (feedback_id, request_id, spec_id, rating, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (feedback_id, request_id, spec_id, rating, comment, utc_now().isoformat()),
        )
        await self.db.commit()
        return feedback_id

    async def get_feedback_for_request(
        self, request_id: str
    ) -> list[dict[str, Any]]:
        """Retrieve all feedback for a request.

        Parameters
        ----------
        request_id : str
            Parent request identifier.

        Returns
        -------
        list[dict[str, Any]]
            Feedback rows sorted by creation time descending.

        """
        async with self.db.execute(
            "SELECT * FROM feedback WHERE request_id = ? ORDER BY created_at DESC",
            (request_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

    # ── RL Episodes ──────────────────────────────────────────────────────

    async def save_episode(
        self,
        request_id: str | None,
        observation: list[float],
        action: int,
        reward: float,
        policy_id: str | None = None,
    ) -> str:
        """Record an RL training episode.

        Parameters
        ----------
        request_id : str or None
            Associated request identifier, if any.
        observation : list[float]
            Environment observation vector.
        action : int
            Action taken by the policy.
        reward : float
            Reward signal received.
        policy_id : str or None
            Policy that generated the action.

        Returns
        -------
        str
            The generated episode identifier.

        """
        episode_id = generate_request_id()
        await self.db.execute(
            "INSERT INTO rl_episodes "
            "(episode_id, request_id, observation, action, reward, policy_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                episode_id,
                request_id,
                json.dumps(observation),
                action,
                reward,
                policy_id,
                utc_now().isoformat(),
            ),
        )
        await self.db.commit()
        return episode_id

    async def get_recent_episodes(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Retrieve the most recent RL episodes.

        Parameters
        ----------
        limit : int
            Maximum number of episodes to return.

        Returns
        -------
        list[dict[str, Any]]
            Episode rows sorted by creation time descending.

        """
        async with self.db.execute(
            "SELECT * FROM rl_episodes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

    # ── Audit Log ────────────────────────────────────────────────────────

    async def append_audit_log(
        self,
        event_type: str,
        payload: dict[str, Any],
        actor: str = "system",
    ) -> None:
        """Append an entry to the immutable audit log.

        Parameters
        ----------
        event_type : str
            Category of the event (e.g. ``'request_failed'``).
        payload : dict[str, Any]
            Arbitrary JSON-serialisable event data.
        actor : str
            Identity of the entity that triggered the event.

        """
        log_id = generate_request_id()
        await self.db.execute(
            "INSERT INTO audit_log (log_id, event_type, actor, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (log_id, event_type, actor, json.dumps(payload), utc_now().isoformat()),
        )
        await self.db.commit()

    async def get_audit_log(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query the audit log.

        Parameters
        ----------
        event_type : str or None
            Filter by event type; ``None`` returns all types.
        limit : int
            Maximum number of entries to return.

        Returns
        -------
        list[dict[str, Any]]
            Audit log rows sorted by creation time descending.

        """
        if event_type:
            query = "SELECT * FROM audit_log WHERE event_type = ? ORDER BY created_at DESC LIMIT ?"
            params: tuple[Any, ...] = (event_type, limit)
        else:
            query = "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?"
            params = (limit,)

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in rows]


__all__ = ["Storage"]
