"""Seed the calibration anchor set from fixture data.

Usage:
    python scripts/seed_calibration_set.py [--database-url postgresql://...]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path


async def main(database_url: str) -> None:
    """Load calibration anchors into the persistence layer."""
    from reinforce_spec._internal._persistence import Storage

    fixtures_path = Path(__file__).parent.parent / "tests" / "fixtures" / "calibration_anchors.json"
    if not fixtures_path.exists():
        print(f"Fixture file not found: {fixtures_path}")
        return

    anchors = json.loads(fixtures_path.read_text())

    storage = Storage(database_url=database_url)
    await storage.connect()

    for anchor in anchors:
        await storage.append_audit_log(
            event_type="calibration_anchor_seeded",
            payload=anchor,
            actor="seed_script",
        )
        print(f"  Seeded anchor: {anchor['name']}")

    await storage.close()
    print(f"Done — {len(anchors)} anchors seeded into {database_url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed calibration anchors")
    parser.add_argument(
        "--database-url",
        default="postgresql://postgres:postgres@localhost:5432/reinforce_spec",
        help="PostgreSQL connection string",
    )
    args = parser.parse_args()
    asyncio.run(main(args.database_url))
