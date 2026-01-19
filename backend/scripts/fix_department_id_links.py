#!/usr/bin/env python3
"""
Backfill Agent.department_id using Department.slug for older DBs where department_id is NULL.

This is safe/idempotent:
- Only updates rows where agents.department_id IS NULL and agents.department matches a department slug.
"""

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    possible_paths = [
        Path("daena.db"),
        Path("backend/daena.db"),
        Path.cwd() / "daena.db",
        Path(__file__).parent.parent.parent / "daena.db",
    ]
    db_path = next((p for p in possible_paths if p.exists()), None)
    if not db_path:
        print("Database not found (daena.db).")
        return 1

    # Avoid emoji to prevent Windows cp1252 console crashes
    print(f"Using database: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        # Ensure column exists (older DBs might not have department_id)
        cur.execute("PRAGMA table_info(agents)")
        cols = [row[1] for row in cur.fetchall()]
        if "department_id" not in cols:
            print("agents.department_id column missing; nothing to backfill.")
            return 0

        cur.execute(
            """
            UPDATE agents
            SET department_id = (
                SELECT d.id FROM departments d
                WHERE d.slug = agents.department
                LIMIT 1
            )
            WHERE agents.department IS NOT NULL
              AND agents.department_id IS NULL
              AND EXISTS (SELECT 1 FROM departments d2 WHERE d2.slug = agents.department)
            """
        )
        updated = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        print(f"Backfilled department_id for {updated} agents")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())


