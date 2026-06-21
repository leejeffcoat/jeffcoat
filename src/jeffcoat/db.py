"""SQLite working store.

The schema is deliberately close to GEDCOM's model (individuals, families,
events, sources, citations) so export is a straight mapping. Every fact can be
tied to the source it came from via the citation table — a record without a
citation is a guess, and the schema makes that visible.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path("data") / "tree.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
    id          TEXT PRIMARY KEY,        -- GEDCOM-style xref, e.g. I1
    given       TEXT,
    surname     TEXT,
    suffix      TEXT,                    -- Jr, Sr, III...
    sex         TEXT,                    -- M / F / U
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS family (
    id          TEXT PRIMARY KEY,        -- GEDCOM-style xref, e.g. F1
    husband_id  TEXT REFERENCES person(id),
    wife_id     TEXT REFERENCES person(id)
);

CREATE TABLE IF NOT EXISTS child (
    family_id   TEXT NOT NULL REFERENCES family(id),
    person_id   TEXT NOT NULL REFERENCES person(id),
    PRIMARY KEY (family_id, person_id)
);

-- Events attach to either a person (BIRT/DEAT/BURI/CENS...) or a family (MARR...).
CREATE TABLE IF NOT EXISTS event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   TEXT REFERENCES person(id),
    family_id   TEXT REFERENCES family(id),
    type        TEXT NOT NULL,           -- GEDCOM tag: BIRT, DEAT, BURI, CENS, MARR, RESI...
    date        TEXT,                    -- free-text GEDCOM date, e.g. "1 JAN 1900", "ABT 1880"
    place       TEXT,
    notes       TEXT,
    CHECK (person_id IS NOT NULL OR family_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS source (
    id          TEXT PRIMARY KEY,        -- GEDCOM-style xref, e.g. S1
    title       TEXT NOT NULL,
    collector   TEXT,                    -- which collector produced it
    url         TEXT,
    repository  TEXT,
    accessed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS citation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL REFERENCES source(id),
    person_id   TEXT REFERENCES person(id),
    event_id    INTEGER REFERENCES event(id),
    page        TEXT,
    text        TEXT,                    -- transcribed snippet supporting the fact
    confidence  TEXT DEFAULT 'unverified' -- unverified / probable / proven
);

CREATE INDEX IF NOT EXISTS idx_event_person ON event(person_id);
CREATE INDEX IF NOT EXISTS idx_event_family ON event(family_id);
CREATE INDEX IF NOT EXISTS idx_citation_person ON citation(person_id);
"""


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    """Open (creating the parent dir if needed) and return a connection with FKs on."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB) -> Path:
    """Create the schema. Idempotent."""
    db_path = Path(db_path)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
    return db_path


def next_xref(conn: sqlite3.Connection, table: str, prefix: str) -> str:
    """Return the next free GEDCOM xref id like I1, F3, S2 for the given table."""
    rows = conn.execute(f"SELECT id FROM {table} WHERE id LIKE ?", (prefix + "%",)).fetchall()
    used = set()
    for (rid,) in (tuple(r) for r in rows):
        try:
            used.add(int(rid[len(prefix):]))
        except (ValueError, TypeError):
            continue
    n = 1
    while n in used:
        n += 1
    return f"{prefix}{n}"
