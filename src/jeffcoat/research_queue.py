"""A tiny research work-queue.

Lists people in the tree who are missing key facts (birth, death, parents) so
you know who to chase next with the collectors. Pure read-only over the DB.
"""

from __future__ import annotations

import sqlite3


def open_items(conn: sqlite3.Connection) -> list[dict]:
    """Return people with gaps worth researching, with a reason for each."""
    items: list[dict] = []
    people = conn.execute("SELECT * FROM person ORDER BY id").fetchall()
    for p in people:
        gaps = []
        has_birth = conn.execute(
            "SELECT 1 FROM event WHERE person_id = ? AND type = 'BIRT' LIMIT 1", (p["id"],)
        ).fetchone()
        has_death = conn.execute(
            "SELECT 1 FROM event WHERE person_id = ? AND type = 'DEAT' LIMIT 1", (p["id"],)
        ).fetchone()
        has_parents = conn.execute(
            "SELECT 1 FROM child WHERE person_id = ? LIMIT 1", (p["id"],)
        ).fetchone()
        if not has_birth:
            gaps.append("no birth")
        if not has_death:
            gaps.append("no death")
        if not has_parents:
            gaps.append("no parents linked")
        if gaps:
            items.append({
                "id": p["id"],
                "name": f"{p['given']} {p['surname']}".strip(),
                "gaps": gaps,
            })
    return items
