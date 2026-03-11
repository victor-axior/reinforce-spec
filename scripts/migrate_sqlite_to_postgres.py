"""Migrate ReinforceSpec data from SQLite to PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite-path data/reinforce_spec.db \
        --postgres-url postgresql://user:pass@host:5432/db
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from reinforce_spec._internal._persistence import (
    AuditLog,
    Base,
    CandidateSpec,
    DimensionScore,
    EvaluationRequest,
    Feedback,
    IdempotencyKey,
    RLEpisode,
)


def fetch_rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


async def ensure_schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _table_has_rows(session: AsyncSession, model: type[Base]) -> bool:
    result = await session.execute(select(model).limit(1))
    return result.first() is not None


async def _ensure_empty_target(session: AsyncSession) -> None:
    tables = [
        IdempotencyKey,
        EvaluationRequest,
        CandidateSpec,
        DimensionScore,
        Feedback,
        RLEpisode,
        AuditLog,
    ]
    for model in tables:
        if await _table_has_rows(session, model):
            raise RuntimeError(
                f"Target table '{model.__tablename__}' is not empty. Aborting to avoid overwrites."
            )


def normalize_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


async def migrate(sqlite_path: str, postgres_url: str, *, allow_update: bool) -> None:
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    engine = create_async_engine(normalize_url(postgres_url), pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    await ensure_schema(engine)

    async with sessionmaker() as session:
        await _ensure_empty_target(session)

        rows = fetch_rows(sqlite_conn, "SELECT key, response_json, created_at, expires_at FROM idempotency_keys")
        if rows:
            stmt = pg_insert(IdempotencyKey).values(
                [
                    {
                        "key": row[0],
                        "response_json": row[1],
                        "created_at": row[2],
                        "expires_at": row[3],
                    }
                    for row in rows
                ]
            )
            if allow_update:
                stmt = stmt.on_conflict_do_update(
                    index_elements=[IdempotencyKey.key],
                    set_={
                        "response_json": stmt.excluded.response_json,
                        "created_at": stmt.excluded.created_at,
                        "expires_at": stmt.excluded.expires_at,
                    },
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=[IdempotencyKey.key])
            await session.execute(stmt)

        rows = fetch_rows(
            sqlite_conn,
            "SELECT request_id, description, customer_type, n_specs, created_at, completed_at, status "
            "FROM evaluation_requests",
        )
        if rows:
            await session.execute(
                pg_insert(EvaluationRequest).values(
                    [
                        {
                            "request_id": row[0],
                            "description": row[1],
                            "customer_type": row[2],
                            "n_specs": row[3],
                            "created_at": row[4],
                            "completed_at": row[5],
                            "status": row[6],
                        }
                        for row in rows
                    ]
                ).on_conflict_do_nothing(index_elements=[EvaluationRequest.request_id])
            )

        rows = fetch_rows(
            sqlite_conn,
            "SELECT spec_id, request_id, index_pos, spec_type, spec_format, content, source_model, "
            "composite_score, is_selected, created_at FROM candidate_specs",
        )
        if rows:
            await session.execute(
                pg_insert(CandidateSpec).values(
                    [
                        {
                            "spec_id": row[0],
                            "request_id": row[1],
                            "index_pos": row[2],
                            "spec_type": row[3],
                            "spec_format": row[4],
                            "content": row[5],
                            "source_model": row[6],
                            "composite_score": row[7],
                            "is_selected": bool(row[8]),
                            "created_at": row[9],
                        }
                        for row in rows
                    ]
                ).on_conflict_do_nothing(index_elements=[CandidateSpec.spec_id])
            )

        rows = fetch_rows(
            sqlite_conn,
            "SELECT spec_id, dimension, score, justification, judge_model FROM dimension_scores",
        )
        if rows:
            await session.execute(
                pg_insert(DimensionScore).values(
                    [
                        {
                            "spec_id": row[0],
                            "dimension": row[1],
                            "score": row[2],
                            "justification": row[3],
                            "judge_model": row[4],
                        }
                        for row in rows
                    ]
                )
            )

        rows = fetch_rows(
            sqlite_conn,
            "SELECT feedback_id, request_id, spec_id, rating, comment, created_at FROM feedback",
        )
        if rows:
            await session.execute(
                pg_insert(Feedback).values(
                    [
                        {
                            "feedback_id": row[0],
                            "request_id": row[1],
                            "spec_id": row[2],
                            "rating": row[3],
                            "comment": row[4],
                            "created_at": row[5],
                        }
                        for row in rows
                    ]
                ).on_conflict_do_nothing(index_elements=[Feedback.feedback_id])
            )

        rows = fetch_rows(
            sqlite_conn,
            "SELECT episode_id, request_id, observation, action, reward, policy_id, created_at "
            "FROM rl_episodes",
        )
        if rows:
            await session.execute(
                pg_insert(RLEpisode).values(
                    [
                        {
                            "episode_id": row[0],
                            "request_id": row[1],
                            "observation": json.loads(row[2]) if isinstance(row[2], str) else row[2],
                            "action": row[3],
                            "reward": row[4],
                            "policy_id": row[5],
                            "created_at": row[6],
                        }
                        for row in rows
                    ]
                ).on_conflict_do_nothing(index_elements=[RLEpisode.episode_id])
            )

        rows = fetch_rows(
            sqlite_conn,
            "SELECT log_id, event_type, actor, payload, created_at FROM audit_log",
        )
        if rows:
            await session.execute(
                pg_insert(AuditLog).values(
                    [
                        {
                            "log_id": row[0],
                            "event_type": row[1],
                            "actor": row[2],
                            "payload": json.loads(row[3]) if isinstance(row[3], str) else row[3],
                            "created_at": row[4],
                        }
                        for row in rows
                    ]
                ).on_conflict_do_nothing(index_elements=[AuditLog.log_id])
            )

        await session.commit()

    sqlite_conn.close()
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        default="data/reinforce_spec.db",
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--postgres-url",
        required=True,
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--allow-update",
        action="store_true",
        help="Allow upserts for idempotency keys (otherwise skip on conflict)",
    )
    args = parser.parse_args()

    asyncio.run(migrate(args.sqlite_path, args.postgres_url, allow_update=args.allow_update))


if __name__ == "__main__":
    main()
