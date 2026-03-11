"""Run SQLite → PostgreSQL migration using .env DATABASE_URL or RS_DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from scripts.migrate_sqlite_to_postgres import migrate


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


if __name__ == "__main__":
    _load_env()
    database_url = os.getenv("DATABASE_URL") or os.getenv("RS_DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL or RS_DATABASE_URL not set")

    sqlite_path = os.getenv("SQLITE_PATH", "data/reinforce_spec.db")

    import asyncio

    asyncio.run(migrate(sqlite_path, database_url, allow_update=False))
