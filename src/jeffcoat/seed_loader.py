"""Load a from-scratch tree from a JSON seed file.

Seed format (human-friendly refs are mapped to GEDCOM xrefs on load):

{
  "persons": [
    {"ref": "lee", "given": "Steven Lee", "surname": "Jeffcoat",
     "suffix": "Jr", "sex": "M", "notes": "self"}
  ],
  "families": [
    {"husband": "father", "wife": "mother", "children": ["lee", "joel"]}
  ],
  "events": [
    {"person": "roy", "type": "RESI", "place": "North, South Carolina, USA"}
  ]
}

Idempotency is by design left to the caller: load into a fresh db (init first).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .db import next_xref


def load(conn: sqlite3.Connection, seed_path: Path | str) -> dict[str, str]:
    """Insert all persons/families/events from the seed. Returns ref->person_id map."""
    seed = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    ref_to_id: dict[str, str] = {}

    for p in seed.get("persons", []):
        pid = next_xref(conn, "person", "I")
        ref_to_id[p["ref"]] = pid
        conn.execute(
            "INSERT INTO person (id, given, surname, suffix, sex, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, p.get("given", ""), p.get("surname", ""),
             p.get("suffix", ""), p.get("sex", "U"), p.get("notes", "")),
        )

    for fam in seed.get("families", []):
        fid = next_xref(conn, "family", "F")
        husband = ref_to_id.get(fam.get("husband")) if fam.get("husband") else None
        wife = ref_to_id.get(fam.get("wife")) if fam.get("wife") else None
        conn.execute(
            "INSERT INTO family (id, husband_id, wife_id) VALUES (?, ?, ?)",
            (fid, husband, wife),
        )
        for child_ref in fam.get("children", []):
            cid = ref_to_id.get(child_ref)
            if cid:
                conn.execute(
                    "INSERT OR IGNORE INTO child (family_id, person_id) VALUES (?, ?)",
                    (fid, cid),
                )

    for ev in seed.get("events", []):
        pid = ref_to_id.get(ev.get("person")) if ev.get("person") else None
        conn.execute(
            "INSERT INTO event (person_id, type, date, place, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (pid, ev["type"], ev.get("date", ""), ev.get("place", ""), ev.get("notes", "")),
        )

    conn.commit()
    return ref_to_id
