"""Operations that mutate the tree: attach a collector Finding to a person as a
sourced fact, and render a person with their events and citations.

Attaching always writes three linked rows: a source (where it came from), an
event (the fact), and a citation (the source backing that exact fact, with the
transcribed snippet and a confidence level). Nothing lands unsourced.
"""

from __future__ import annotations

import sqlite3

from .collectors.base import Finding
from .db import next_xref


def get_person(conn: sqlite3.Connection, person_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM person WHERE id = ?", (person_id,)).fetchone()


def attach_finding(
    conn: sqlite3.Connection,
    person_id: str,
    finding: Finding,
    event_type: str,
) -> tuple[str, int]:
    """Write source + event + citation for a finding. Returns (source_id, event_id)."""
    if get_person(conn, person_id) is None:
        raise KeyError(f"no person {person_id}")

    source_id = next_xref(conn, "source", "S")
    conn.execute(
        "INSERT INTO source (id, title, collector, url) VALUES (?, ?, ?, ?)",
        (source_id, finding.title, finding.collector, finding.url),
    )
    cur = conn.execute(
        "INSERT INTO event (person_id, type, date, place, notes) VALUES (?, ?, ?, ?, ?)",
        (person_id, event_type, finding.date, finding.place, ""),
    )
    event_id = cur.lastrowid
    conn.execute(
        "INSERT INTO citation (source_id, person_id, event_id, text, confidence) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_id, person_id, event_id, finding.summary, finding.confidence),
    )
    conn.commit()
    return source_id, event_id


def render_person(conn: sqlite3.Connection, person_id: str) -> str:
    p = get_person(conn, person_id)
    if p is None:
        return f"no person {person_id}"
    suffix = f" {p['suffix']}" if p["suffix"] else ""
    lines = [f"{p['id']}  {p['given']} {p['surname']}{suffix}  [{p['sex']}]"]
    if p["notes"]:
        lines.append(f"  note: {p['notes']}")

    # parents
    parents = conn.execute(
        """SELECT f.husband_id, f.wife_id FROM child c
           JOIN family f ON f.id = c.family_id WHERE c.person_id = ?""",
        (person_id,),
    ).fetchone()
    if parents:
        for role, pid in (("father", parents["husband_id"]), ("mother", parents["wife_id"])):
            if pid:
                par = get_person(conn, pid)
                if par:
                    lines.append(f"  {role}: {par['given']} {par['surname']} ({pid})")

    events = conn.execute(
        "SELECT * FROM event WHERE person_id = ? ORDER BY id", (person_id,)
    ).fetchall()
    if events:
        lines.append("  events:")
        for ev in events:
            bits = [ev["type"]]
            if ev["date"]:
                bits.append(ev["date"])
            if ev["place"]:
                bits.append(ev["place"])
            lines.append(f"    - {'  '.join(bits)}")
            cites = conn.execute(
                """SELECT s.title, s.url, c.confidence, c.text FROM citation c
                   JOIN source s ON s.id = c.source_id WHERE c.event_id = ?""",
                (ev["id"],),
            ).fetchall()
            for c in cites:
                lines.append(f"        src [{c['confidence']}]: {c['title']}")
                if c["url"]:
                    lines.append(f"             {c['url']}")
    return "\n".join(lines)
