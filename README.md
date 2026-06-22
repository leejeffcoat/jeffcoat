# jeffcoat — a personal genealogy research tool

A local-first toolkit for building and enriching a family tree from scratch, using
APIs and (where necessary) scrapers. Data lives as **SQLite** (working store) and
exports to **GEDCOM** so you can open the tree in a real genealogy app
(Gramps — free — or RootsMagic) for viewing and editing.

This is a personal tool. It is not a hosted app and has no UI of its own by design:
the heavy tree-viewing is delegated to Gramps via GEDCOM round-trip.

## Design principles

1. **GEDCOM is the spine.** Every person/event can be exported to GEDCOM 5.5.1 so you
   are never locked in and can move into any genealogy app.
2. **Every fact carries a citation.** A record without a source is a guess. The schema
   forces facts to point at the source they came from.
3. **API-first, scrape only where you must.** Official APIs are stable and allowed.
   Scraping is a fallback for sites with no API, run at personal rate only.
4. **Collectors are modular.** Each data source is a self-contained collector that
   normalizes its output into the common schema. Adding a source = adding one file.

## Quick start

```bash
# from the repo root  (set PYTHONPATH=src first; PowerShell: $env:PYTHONPATH="src")
python -m jeffcoat init                       # create data/tree.db
python -m jeffcoat import-seed data/seed-mine.json
python -m jeffcoat list                       # everyone, with ids
python -m jeffcoat show I7                     # one person + events + sources
python -m jeffcoat queue                       # who's missing birth/death/parents
python -m jeffcoat export-gedcom data/tree.ged # open this in Gramps
```

### The research loop (search → verify → attach)

Search a source, eyeball the results, and attach the one *you* judge to be a
real match. The attach writes the fact **with its citation and a confidence
level** so unverified hits are always marked as such.

```bash
python -m jeffcoat search-news "Roy Jeffcoat" --place "South Carolina"   # no key
python -m jeffcoat attach-news I7 3 --type DEAT --place "South Carolina"  # attach result #3 as a death
python -m jeffcoat search-wikitree "Roy Jeffcoat"                          # no key
python -m jeffcoat attach-wikitree I7 1                                    # attach profile #1 (BIRT)
```

You decide what attaches — the tool never auto-merges ambiguous common-name
hits into the tree.

No third-party packages are required for the core (SQLite + GEDCOM + the no-auth
collectors). Scraper collectors that need extra packages declare them at the top of
their file and fail with a clear message if missing.

## Data sources

| Source | Access | Status | Notes |
|---|---|---|---|
| **Chronicling America** (Library of Congress) | Free JSON API, no key | ✅ working | Public-domain historic newspapers: obituaries, marriage notices. |
| **WikiTree** | Free API | ✅ working (public profiles) | Collaborative open tree. Some fields need login. |
| **FamilySearch** | Free official API (requires registered app key) | 🔲 stub | The backbone once you register a developer key. |
| **BillionGraves** | API | 🔲 planned | Headstones with GPS. |
| **FindAGrave** | Scrape (Playwright) | 🔲 stub | No public API; Ancestry-owned. Personal-rate only. |
| **Ancestry.com** | ⚠️ do not scrape | n/a | ToS forbids scraping and they hard-ban. Use their GEDCOM *export* of your own tree, then enrich from the sources above. |

## Layout

```
src/jeffcoat/
  db.py                 SQLite schema + connection
  models.py             Person / Event / Family / Source / Citation dataclasses
  gedcom.py             GEDCOM 5.5.1 exporter
  seed_loader.py        load a from-scratch tree from a JSON seed
  tree_ops.py           attach a Finding as sourced fact; render a person
  research_queue.py     "who needs research" work queue
  cli.py                command-line entry point (python -m jeffcoat)
  collectors/
    base.py             Collector interface + Finding result type
    chronicling_america.py   working, no auth
    wikitree.py              working, no auth (public profiles)
    familysearch.py          stub — needs a registered API key
    findagrave.py            stub — Playwright scraper
data/                   working SQLite + GEDCOM exports (gitignored)
seed/roots.example.json a couple of root people to start a from-scratch tree
```

## Adding a collector

1. Copy `collectors/chronicling_america.py` as a template.
2. Implement `name`, `requires` (extra packages, if any), and `search(person) -> list[Finding]`.
3. A `Finding` carries proposed facts **plus the source/citation** they came from.
4. Register it in `collectors/__init__.py`.

## Legal note

This tool is for personal family-history research. Respect each source's terms of
service and rate limits. Do not scrape sites that prohibit it (notably Ancestry).
Public-domain records (pre-1929 newspapers, census on FamilySearch) and official
APIs are the safe, durable backbone.
