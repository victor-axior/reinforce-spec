"""Seed the calibration anchor set from fixture data.

Usage:
    python scripts/seed_calibration_set.py [--db-path data/reinforce_spec.db]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path


async def main(db_path: str) -> None:
    """Load calibration anchors into the persistence layer."""
    from reinforce_spec._internal._persistence import Storage

    fixtures_path = Path(__file__).parent.parent / "tests" / "fixtures" / "calibration_anchors.json"
    if not fixtures_path.exists():
        print(f"Fixture file not found: {fixtures_path}")
        return

    anchors = json.loads(fixtures_path.read_text())

    storage = Storage(db_path=Path(db_path))
    await storage.connect()

    for anchor in anchors:
        await storage.append_audit_log(
            event_type="calibration_anchor_seeded",
            data=anchor,
            actor="seed_script",
        )
        print(f"  Seeded anchor: {anchor['name']}")

    await storage.close()
    print(f"Done — {len(anchors)} anchors seeded into {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed calibration anchors")
    parser.add_argument(
        "--db-path",
        default="data/reinforce_spec.db",
        help="Path to the SQLite database",
    )
    args = parser.parse_args()
    asyncio.run(main(args.db_path))
