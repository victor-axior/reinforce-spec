"""Persistence layer — async PostgreSQL storage via SQLAlchemy ORM."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    delete,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from reinforce_spec._internal._utils import generate_request_id, utc_now


class Base(DeclarativeBase):
    """Base class for ORM models."""


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    response_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvaluationRequest(Base):
    __tablename__ = "evaluation_requests"

    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    customer_type: Mapped[str | None] = mapped_column(String, nullable=True)
    n_specs: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")


class CandidateSpec(Base):
    __tablename__ = "candidate_specs"

    spec_id: Mapped[str] = mapped_column(String, primary_key=True)
    request_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("evaluation_requests.request_id"),
        nullable=False,
    )
    index_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    spec_type: Mapped[str] = mapped_column(String, nullable=False, default="")
    spec_format: Mapped[str] = mapped_column(String, nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_model: Mapped[str | None] = mapped_column(String, nullable=True)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DimensionScore(Base):
    __tablename__ = "dimension_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spec_id: Mapped[str] = mapped_column(
        String, ForeignKey("candidate_specs.spec_id"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_model: Mapped[str | None] = mapped_column(String, nullable=True)


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(String, primary_key=True)
    request_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("evaluation_requests.request_id"),
        nullable=False,
    )
    spec_id: Mapped[str | None] = mapped_column(String, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RLEpisode(Base):
    __tablename__ = "rl_episodes"

    episode_id: Mapped[str] = mapped_column(String, primary_key=True)
    request_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("evaluation_requests.request_id")
    )
    observation: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    action: Mapped[int] = mapped_column(Integer, nullable=False)
    reward: Mapped[float] = mapped_column(Float, nullable=False)
    policy_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    log_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False, default="system")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("idx_specs_request", CandidateSpec.request_id)
Index("idx_scores_spec", DimensionScore.spec_id)
Index("idx_feedback_request", Feedback.request_id)
Index("idx_episodes_request", RLEpisode.request_id)
Index("idx_audit_event", AuditLog.event_type, AuditLog.created_at)
Index("idx_idempotency_expires", IdempotencyKey.expires_at)


class Storage:
    """Async PostgreSQL storage backend using SQLAlchemy ORM."""

    def __init__(self, database_url: str) -> None:
        self._database_url = self._normalize_url(database_url)
        self._require_ssl = self._should_require_ssl(database_url)
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    @staticmethod
    def _normalize_url(database_url: str) -> str:
        # Ensure asyncpg driver prefix
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return database_url

    @staticmethod
    def _should_require_ssl(database_url: str) -> bool:
        """Check if SSL should be required (non-localhost connections)."""
        return "localhost" not in database_url and "127.0.0.1" not in database_url

    async def connect(self) -> None:
        connect_args = {"ssl": "require"} if self._require_ssl else {}
        self._engine = create_async_engine(
            self._database_url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(
            "storage_connected | database_url={database_url}", database_url=self._database_url
        )

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
        self._sessionmaker = None

    async def __aenter__(self) -> Storage:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    def _require_sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        if self._sessionmaker is None:
            raise RuntimeError("Storage not connected. Call connect() first.")
        return self._sessionmaker

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        return {col.key: getattr(row, col.key) for col in row.__table__.columns}

    # ── Idempotency ──────────────────────────────────────────────────────

    async def get_idempotent_response(self, key: str) -> str | None:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = select(IdempotencyKey.response_json).where(
                IdempotencyKey.key == key,
                IdempotencyKey.expires_at > utc_now(),
            )
            result = await session.execute(stmt)
            row = result.first()
            return row[0] if row else None

    async def set_idempotent_response(
        self, key: str, response_json: str, ttl_hours: int = 24
    ) -> None:
        now = utc_now()
        expires = now + timedelta(hours=ttl_hours)
        stmt = (
            pg_insert(IdempotencyKey)
            .values(
                key=key,
                response_json=response_json,
                created_at=now,
                expires_at=expires,
            )
            .on_conflict_do_update(
                index_elements=[IdempotencyKey.key],
                set_={
                    "response_json": response_json,
                    "created_at": now,
                    "expires_at": expires,
                },
            )
        )
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()

    async def cleanup_expired_idempotency_keys(self) -> int:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = delete(IdempotencyKey).where(IdempotencyKey.expires_at <= utc_now())
            result = await session.execute(stmt)
            await session.commit()
            return getattr(result, "rowcount", 0) or 0

    # ── Generation Requests ──────────────────────────────────────────────

    async def save_request(
        self,
        request_id: str,
        n_specs: int,
        description: str = "",
        customer_type: str | None = None,
    ) -> None:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            session.add(
                EvaluationRequest(
                    request_id=request_id,
                    description=description,
                    customer_type=customer_type,
                    n_specs=n_specs,
                    created_at=utc_now(),
                    status="pending",
                )
            )
            await session.commit()

    async def complete_request(self, request_id: str) -> None:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = (
                update(EvaluationRequest)
                .where(EvaluationRequest.request_id == request_id)
                .values(status="completed", completed_at=utc_now())
            )
            await session.execute(stmt)
            await session.commit()

    async def fail_request(self, request_id: str, error: str) -> None:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = (
                update(EvaluationRequest)
                .where(EvaluationRequest.request_id == request_id)
                .values(status="failed", completed_at=utc_now())
            )
            await session.execute(stmt)
            await session.commit()
        await self.append_audit_log("request_failed", {"request_id": request_id, "error": error})

    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = select(EvaluationRequest).where(EvaluationRequest.request_id == request_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return self._row_to_dict(row) if row else None

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
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            session.add(
                CandidateSpec(
                    spec_id=spec_id,
                    request_id=request_id,
                    index_pos=index_pos,
                    spec_type=spec_type,
                    spec_format=spec_format,
                    content=content,
                    source_model=source_model,
                    composite_score=composite_score,
                    is_selected=is_selected,
                    created_at=utc_now(),
                )
            )
            await session.commit()

    async def save_dimension_scores(self, spec_id: str, scores: list[dict[str, Any]]) -> None:
        if not scores:
            return
        rows = [
            {
                "spec_id": spec_id,
                "dimension": s["dimension"],
                "score": s["score"],
                "justification": s.get("justification"),
                "judge_model": s.get("judge_model"),
            }
            for s in scores
        ]
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            await session.execute(pg_insert(DimensionScore), rows)
            await session.commit()

    async def get_candidates_for_request(self, request_id: str) -> list[dict[str, Any]]:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = (
                select(CandidateSpec)
                .where(CandidateSpec.request_id == request_id)
                .order_by(CandidateSpec.composite_score.desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(row) for row in rows]

    # ── Feedback ─────────────────────────────────────────────────────────

    async def save_feedback(
        self,
        request_id: str,
        rating: float | None = None,
        comment: str | None = None,
        spec_id: str | None = None,
    ) -> str:
        feedback_id = generate_request_id()
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            session.add(
                Feedback(
                    feedback_id=feedback_id,
                    request_id=request_id,
                    spec_id=spec_id,
                    rating=rating,
                    comment=comment,
                    created_at=utc_now(),
                )
            )
            await session.commit()
        return feedback_id

    async def get_feedback_for_request(self, request_id: str) -> list[dict[str, Any]]:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = (
                select(Feedback)
                .where(Feedback.request_id == request_id)
                .order_by(Feedback.created_at.desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(row) for row in rows]

    # ── RL Episodes ──────────────────────────────────────────────────────

    async def save_episode(
        self,
        request_id: str | None,
        observation: list[float],
        action: int,
        reward: float,
        policy_id: str | None = None,
    ) -> str:
        episode_id = generate_request_id()
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            session.add(
                RLEpisode(
                    episode_id=episode_id,
                    request_id=request_id,
                    observation=observation,
                    action=action,
                    reward=reward,
                    policy_id=policy_id,
                    created_at=utc_now(),
                )
            )
            await session.commit()
        return episode_id

    async def get_recent_episodes(self, limit: int = 1000) -> list[dict[str, Any]]:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = select(RLEpisode).order_by(RLEpisode.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(row) for row in rows]

    # ── Audit Log ────────────────────────────────────────────────────────

    async def append_audit_log(
        self,
        event_type: str,
        payload: dict[str, Any],
        actor: str = "system",
    ) -> None:
        log_id = generate_request_id()
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            session.add(
                AuditLog(
                    log_id=log_id,
                    event_type=event_type,
                    actor=actor,
                    payload=payload,
                    created_at=utc_now(),
                )
            )
            await session.commit()

    async def get_audit_log(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sessionmaker = self._require_sessionmaker()
        async with sessionmaker() as session:
            stmt = select(AuditLog)
            if event_type:
                stmt = stmt.where(AuditLog.event_type == event_type)
            stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(row) for row in rows]


__all__ = [
    "AuditLog",
    "Base",
    "CandidateSpec",
    "DimensionScore",
    "EvaluationRequest",
    "Feedback",
    "IdempotencyKey",
    "RLEpisode",
    "Storage",
]
