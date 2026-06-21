"""GEDCOM 5.5.1 exporter.

Reads the SQLite store and writes a LINEAGE-LINKED .ged file that Gramps and
RootsMagic import cleanly. This is the round-trip that makes "data files" the
viewing strategy: edit/scrape here, view the tree there.

Dates are passed through as stored (free-text GEDCOM form), so keep them in
GEDCOM style at entry time, e.g. "1 JAN 1900", "ABT 1880", "BET 1900 AND 1910".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import __version__

# Event tags that belong to an individual vs. a family record.
FAMILY_EVENT_TAGS = {"MARR", "DIV", "ENGA", "MARB", "MARC"}


def _w(lines: list[str], level: int, tag: str, value: str = "") -> None:
    line = f"{level} {tag}" + (f" {value}" if value else "")
    lines.append(line)


def export(conn: sqlite3.Connection, out_path: Path | str) -> Path:
    """Write the whole tree to a GEDCOM file. Returns the path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    # ---- header ----
    _w(lines, 0, "HEAD")
    _w(lines, 1, "SOUR", "jeffcoat")
    _w(lines, 2, "VERS", __version__)
    _w(lines, 2, "NAME", "jeffcoat genealogy tool")
    _w(lines, 1, "GEDC")
    _w(lines, 2, "VERS", "5.5.1")
    _w(lines, 2, "FORM", "LINEAGE-LINKED")
    _w(lines, 1, "CHAR", "UTF-8")

    # ---- individuals ----
    persons = conn.execute("SELECT * FROM person ORDER BY id").fetchall()
    for p in persons:
        _w(lines, 0, f"@{p['id']}@", "INDI")
        given = (p["given"] or "").strip()
        surname = (p["surname"] or "").strip()
        suffix = (p["suffix"] or "").strip()
        name_line = f"{given} /{surname}/" + (f" {suffix}" if suffix else "")
        _w(lines, 1, "NAME", name_line)
        if given:
            _w(lines, 2, "GIVN", given)
        if surname:
            _w(lines, 2, "SURN", surname)
        if suffix:
            _w(lines, 2, "NSFX", suffix)
        sex = (p["sex"] or "U").upper()[:1]
        if sex in ("M", "F"):
            _w(lines, 1, "SEX", sex)

        # individual events + their citations
        events = conn.execute(
            "SELECT * FROM event WHERE person_id = ? ORDER BY id", (p["id"],)
        ).fetchall()
        for ev in events:
            if ev["type"] in FAMILY_EVENT_TAGS:
                continue
            _write_event(conn, lines, ev)

        if (p["notes"] or "").strip():
            _w(lines, 1, "NOTE", p["notes"].strip())

        # family links
        fams = conn.execute(
            "SELECT id FROM family WHERE husband_id = ? OR wife_id = ? ORDER BY id",
            (p["id"], p["id"]),
        ).fetchall()
        for f in fams:
            _w(lines, 1, "FAMS", f"@{f['id']}@")
        famc = conn.execute(
            "SELECT family_id FROM child WHERE person_id = ? ORDER BY family_id",
            (p["id"],),
        ).fetchall()
        for f in famc:
            _w(lines, 1, "FAMC", f"@{f['family_id']}@")

    # ---- families ----
    families = conn.execute("SELECT * FROM family ORDER BY id").fetchall()
    for fam in families:
        _w(lines, 0, f"@{fam['id']}@", "FAM")
        if fam["husband_id"]:
            _w(lines, 1, "HUSB", f"@{fam['husband_id']}@")
        if fam["wife_id"]:
            _w(lines, 1, "WIFE", f"@{fam['wife_id']}@")
        children = conn.execute(
            "SELECT person_id FROM child WHERE family_id = ? ORDER BY person_id",
            (fam["id"],),
        ).fetchall()
        for c in children:
            _w(lines, 1, "CHIL", f"@{c['person_id']}@")
        fam_events = conn.execute(
            "SELECT * FROM event WHERE family_id = ? ORDER BY id", (fam["id"],)
        ).fetchall()
        for ev in fam_events:
            _write_event(conn, lines, ev)

    # ---- sources ----
    sources = conn.execute("SELECT * FROM source ORDER BY id").fetchall()
    for s in sources:
        _w(lines, 0, f"@{s['id']}@", "SOUR")
        _w(lines, 1, "TITL", s["title"])
        if s["repository"]:
            _w(lines, 1, "REPO", s["repository"])
        if s["url"]:
            _w(lines, 1, "PUBL", s["url"])

    _w(lines, 0, "TRLR")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _write_event(conn: sqlite3.Connection, lines: list[str], ev: sqlite3.Row) -> None:
    _w(lines, 1, ev["type"])
    if ev["date"]:
        _w(lines, 2, "DATE", ev["date"])
    if ev["place"]:
        _w(lines, 2, "PLAC", ev["place"])
    if ev["notes"]:
        _w(lines, 2, "NOTE", ev["notes"])
    cites = conn.execute(
        "SELECT * FROM citation WHERE event_id = ? ORDER BY id", (ev["id"],)
    ).fetchall()
    for c in cites:
        _w(lines, 2, "SOUR", f"@{c['source_id']}@")
        if c["page"]:
            _w(lines, 3, "PAGE", c["page"])
        if c["text"]:
            _w(lines, 3, "DATA")
            _w(lines, 4, "TEXT", c["text"])
