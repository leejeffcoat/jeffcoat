"""Command-line entry point: python -m jeffcoat <command>.

Commands:
  init                    create data/tree.db
  import-seed <file>      load a JSON seed (from-scratch tree)
  add-person ...          add one person
  list                    list everyone in the tree
  queue                   show people with missing facts (research to-do)
  search-news <name>      Chronicling America newspaper search (no key)
  search-wikitree <name>  WikiTree public-profile search (no key)
  export-gedcom <file>    write a .ged for Gramps/RootsMagic
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
from pathlib import Path

from . import collectors, gedcom, graves_walk, research_queue, seed_loader, tree_ops
from .collectors.findagrave import fetch_memorial
from .db import DEFAULT_DB, connect, init_db, next_xref
from .models import Person


def _cmd_init(args) -> int:
    path = init_db(args.db)
    print(f"initialized {path}")
    return 0


def _cmd_import_seed(args) -> int:
    init_db(args.db)
    with connect(args.db) as conn:
        ref_map = seed_loader.load(conn, args.file)
    print(f"loaded {len(ref_map)} people from {args.file}")
    return 0


def _cmd_add_person(args) -> int:
    with connect(args.db) as conn:
        pid = next_xref(conn, "person", "I")
        conn.execute(
            "INSERT INTO person (id, given, surname, suffix, sex, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, args.given, args.surname, args.suffix, args.sex, args.notes or ""),
        )
        conn.commit()
    print(f"added {pid}: {args.given} {args.surname} {args.suffix}".strip())
    return 0


def _cmd_list(args) -> int:
    with connect(args.db) as conn:
        rows = conn.execute("SELECT * FROM person ORDER BY id").fetchall()
    if not rows:
        print("(no people yet — run import-seed or add-person)")
        return 0
    for r in rows:
        suffix = f" {r['suffix']}" if r["suffix"] else ""
        print(f"  {r['id']:<5} {r['given']} {r['surname']}{suffix}  [{r['sex']}]")
    print(f"\n{len(rows)} people")
    return 0


def _cmd_queue(args) -> int:
    with connect(args.db) as conn:
        items = research_queue.open_items(conn)
    if not items:
        print("nothing to research — everyone has birth, death, and parents")
        return 0
    print("research to-do:")
    for it in items:
        print(f"  {it['id']:<5} {it['name']:<28} {', '.join(it['gaps'])}")
    return 0


def _cmd_search(collector_name: str, args) -> int:
    person = Person(id="search", given=_first(args.name), surname=_last(args.name))
    col = collectors.get(collector_name)
    kwargs = {}
    if getattr(args, "place", None):
        kwargs["place"] = args.place
    try:
        col.check_requirements()
        findings = col.search(person, **kwargs)
    except (RuntimeError, NotImplementedError) as e:
        print(f"[{collector_name}] {e}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as e:
        hint = " (rate limited — wait a minute and retry)" if e.code == 429 else ""
        print(f"[{collector_name}] HTTP {e.code}{hint}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"[{collector_name}] network error: {e.reason}", file=sys.stderr)
        return 1
    if not findings:
        print(f"[{collector_name}] no results for {args.name}")
        return 0
    for i, f in enumerate(findings, 1):
        print(f"\n{i}. {f.title}")
        if f.date or f.place:
            print(f"   {f.date}  {f.place}".rstrip())
        if f.summary:
            print(f"   {f.summary}")
        if f.url:
            print(f"   {f.url}")
    return 0


def _cmd_show(args) -> int:
    with connect(args.db) as conn:
        print(tree_ops.render_person(conn, args.person_id))
    return 0


def _cmd_attach(collector_name: str, args) -> int:
    with connect(args.db) as conn:
        person = tree_ops.get_person(conn, args.person_id)
        if person is None:
            print(f"no person {args.person_id}", file=sys.stderr)
            return 1
        name = f"{person['given']} {person['surname']}".strip()
        search_person = Person(id=person["id"], given=person["given"], surname=person["surname"])
        col = collectors.get(collector_name)
        kwargs = {}
        if getattr(args, "place", None):
            kwargs["place"] = args.place
        try:
            col.check_requirements()
            findings = col.search(search_person, **kwargs)
        except (RuntimeError, NotImplementedError) as e:
            print(f"[{collector_name}] {e}", file=sys.stderr)
            return 1
        except urllib.error.HTTPError as e:
            hint = " (rate limited — wait a minute and retry)" if e.code == 429 else ""
            print(f"[{collector_name}] HTTP {e.code}{hint}", file=sys.stderr)
            return 1
        except urllib.error.URLError as e:
            print(f"[{collector_name}] network error: {e.reason}", file=sys.stderr)
            return 1
        if not findings:
            print(f"[{collector_name}] no results for {name}")
            return 1
        if args.result < 1 or args.result > len(findings):
            print(f"result #{args.result} out of range (1..{len(findings)})", file=sys.stderr)
            return 1
        finding = findings[args.result - 1]
        event_type = args.type or finding.event_type or "EVEN"
        source_id, event_id = tree_ops.attach_finding(conn, args.person_id, finding, event_type)
        print(f"attached to {args.person_id}: {event_type} <- {finding.title}")
        print(f"  source {source_id}, citation [{finding.confidence}]")
    return 0


def _cmd_graves_memorial(args) -> int:
    try:
        d = fetch_memorial(args.memorial_id)
    except (RuntimeError, urllib.error.URLError) as e:
        print(f"[findagrave] {e}", file=sys.stderr)
        return 1
    print(f"{d['name']}  (b. {d['birth'] or '?'}  d. {d['death'] or '?'})")
    if d["cemetery"]:
        print(f"  buried: {d['cemetery']}")
    print(f"  {d['url']}")
    for rel, members in d["relations"].items():
        print(f"  {rel}:")
        for mid, name in members:
            print(f"    - {name}  [mem {mid}]")
    return 0


def _cmd_graves_walk(args) -> int:
    try:
        result = graves_walk.walk_ancestors(args.memorial_id, max_up=args.up, max_fetch=args.max)
    except (RuntimeError, urllib.error.URLError) as e:
        print(f"[findagrave] {e}", file=sys.stderr)
        return 1
    print(f"walked {len(result['people'])} memorials, up to {args.up} generations\n")
    if args.emit_seed:
        print(graves_walk.to_seed_fragment(result))
    else:
        print(graves_walk.render(result, args.memorial_id))
    return 0


def _cmd_export(args) -> int:
    with connect(args.db) as conn:
        out = gedcom.export(conn, args.file)
    print(f"exported GEDCOM -> {out}")
    print("open it in Gramps (free) or RootsMagic to view the tree")
    return 0


def _first(name: str) -> str:
    parts = name.split()
    return " ".join(parts[:-1]) if len(parts) > 1 else name


def _last(name: str) -> str:
    parts = name.split()
    return parts[-1] if len(parts) > 1 else ""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jeffcoat", description="personal genealogy tool")
    p.add_argument("--db", default=str(DEFAULT_DB), help=f"SQLite path (default {DEFAULT_DB})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the database").set_defaults(func=_cmd_init)

    sp = sub.add_parser("import-seed", help="load a JSON seed file")
    sp.add_argument("file")
    sp.set_defaults(func=_cmd_import_seed)

    sp = sub.add_parser("add-person", help="add one person")
    sp.add_argument("--given", required=True)
    sp.add_argument("--surname", default="")
    sp.add_argument("--suffix", default="")
    sp.add_argument("--sex", default="U", choices=["M", "F", "U"])
    sp.add_argument("--notes", default="")
    sp.set_defaults(func=_cmd_add_person)

    sub.add_parser("list", help="list everyone").set_defaults(func=_cmd_list)
    sub.add_parser("queue", help="show research to-do").set_defaults(func=_cmd_queue)

    sp = sub.add_parser("show", help="show one person with events + sources")
    sp.add_argument("person_id")
    sp.set_defaults(func=_cmd_show)

    sp = sub.add_parser("attach-news", help="attach a Chronicling America result to a person")
    sp.add_argument("person_id")
    sp.add_argument("result", type=int, help="result number from search-news (1-based)")
    sp.add_argument("--type", default="", help="GEDCOM event tag (DEAT, MARR, RESI...)")
    sp.add_argument("--place", default="", help="US state to scope the search")
    sp.set_defaults(func=lambda a: _cmd_attach("chronicling_america", a))

    sp = sub.add_parser("attach-wikitree", help="attach a WikiTree result to a person")
    sp.add_argument("person_id")
    sp.add_argument("result", type=int, help="result number from search-wikitree (1-based)")
    sp.add_argument("--type", default="", help="GEDCOM event tag (default BIRT from profile)")
    sp.set_defaults(func=lambda a: _cmd_attach("wikitree", a))

    sp = sub.add_parser("attach-graves", help="attach a FindAGrave memorial to a person")
    sp.add_argument("person_id")
    sp.add_argument("result", type=int, help="result number from search-graves (1-based)")
    sp.add_argument("--type", default="", help="GEDCOM event tag (default BURI)")
    sp.add_argument("--place", default="", help="location filter used in the search")
    sp.set_defaults(func=lambda a: _cmd_attach("findagrave", a))

    sp = sub.add_parser("graves-memorial", help="show one FindAGrave memorial + its family links")
    sp.add_argument("memorial_id", help="FindAGrave memorial number")
    sp.set_defaults(func=_cmd_graves_memorial)

    sp = sub.add_parser("graves-walk", help="walk FindAGrave ancestors up from a memorial")
    sp.add_argument("memorial_id", help="FindAGrave memorial number to start from")
    sp.add_argument("--up", type=int, default=3, help="generations to climb (default 3)")
    sp.add_argument("--max", type=int, default=40, help="max memorials to fetch (default 40)")
    sp.add_argument("--emit-seed", action="store_true",
                    help="output a seed JSON fragment to review/merge instead of a tree")
    sp.set_defaults(func=_cmd_graves_walk)

    sp = sub.add_parser("search-news", help="Chronicling America (no key)")
    sp.add_argument("name")
    sp.add_argument("--place", default="", help="US state name, e.g. 'South Carolina'")
    sp.set_defaults(func=lambda a: _cmd_search("chronicling_america", a))

    sp = sub.add_parser("search-wikitree", help="WikiTree public profiles (no key)")
    sp.add_argument("name")
    sp.set_defaults(func=lambda a: _cmd_search("wikitree", a))

    sp = sub.add_parser("search-graves", help="FindAGrave memorials (no key)")
    sp.add_argument("name")
    sp.add_argument("--place", default="", help="location filter, e.g. 'South Carolina'")
    sp.set_defaults(func=lambda a: _cmd_search("findagrave", a))

    sp = sub.add_parser("export-gedcom", help="write a .ged for Gramps/RootsMagic")
    sp.add_argument("file")
    sp.set_defaults(func=_cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    # Ensure non-ASCII place names / OCR snippets print on the Windows cp1252 console.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
