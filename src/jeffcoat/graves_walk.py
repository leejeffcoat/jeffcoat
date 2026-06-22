"""Walk FindAGrave memorial family links to assemble an ancestor branch.

Read-only: it fetches detail pages and returns the collected people and
relationships. It never touches the tree DB. The CLI can pretty-print the
lineage or emit a seed-format JSON fragment for you to review and merge into
your own seed file (seed file stays the source of truth).

Starting from one memorial, it follows Parents up `max_up` generations and also
pulls each person's Spouse (so couples are complete and the spouse's own parents
— equally your ancestors — get walked too). It does not descend into children.
"""

from __future__ import annotations

import json
from collections import deque

from .collectors.findagrave import fetch_memorial


def walk_ancestors(start_id: str | int, max_up: int = 3, max_fetch: int = 40) -> dict:
    """Return {people: {id: detail}, parent_edges: [(parent_id, child_id)],
    spouse_edges: [[a, b]]} for the ancestor branch above start_id."""
    people: dict[str, dict] = {}
    parent_edges: set[tuple[str, str]] = set()
    spouse_pairs: set[frozenset] = set()
    queue: deque[tuple[str, int]] = deque([(str(start_id), 0)])

    while queue and len(people) < max_fetch:
        mid, depth = queue.popleft()
        if mid in people:
            continue
        people[mid] = fetch_memorial(mid)
        rel = people[mid]["relations"]

        for sid, _ in rel.get("Spouse", []):
            spouse_pairs.add(frozenset((mid, sid)))
            if sid not in people and len(people) + len(queue) < max_fetch:
                queue.append((sid, depth))  # same generation

        if depth < max_up:
            for pid, _ in rel.get("Parents", []):
                parent_edges.add((pid, mid))
                if pid not in people:
                    queue.append((pid, depth + 1))

    return {
        "people": people,
        "parent_edges": sorted(parent_edges),
        "spouse_edges": [sorted(p) for p in spouse_pairs],
    }


def render(result: dict, start_id: str | int) -> str:
    """Pretty-print the walked branch as an indented ancestor tree."""
    people = result["people"]
    # child -> [parents]
    parents_of: dict[str, list[str]] = {}
    for parent, child in result["parent_edges"]:
        parents_of.setdefault(child, []).append(parent)
    spouse_of: dict[str, list[str]] = {}
    for a, b in result["spouse_edges"]:
        spouse_of.setdefault(a, []).append(b)
        spouse_of.setdefault(b, []).append(a)

    lines: list[str] = []
    seen: set[str] = set()

    def label(mid: str) -> str:
        p = people.get(mid)
        if not p:
            return f"(memorial {mid}, not fetched)"
        dates = f"{p['birth'] or '?'} – {p['death'] or '?'}"
        cem = f" · {p['cemetery']}" if p.get("cemetery") else ""
        return f"{p['name']}  ({dates}){cem}  [mem {mid}]"

    def emit(mid: str, indent: int) -> None:
        if mid in seen:
            lines.append("  " * indent + f"{label(mid)}  (see above)")
            return
        seen.add(mid)
        spouses = spouse_of.get(mid, [])
        couple = label(mid)
        if spouses:
            couple += "   ×   " + " / ".join(label(s) for s in spouses)
        lines.append("  " * indent + couple)
        # parents of this person and of the spouses
        for person in [mid, *spouses]:
            for par in parents_of.get(person, []):
                emit(par, indent + 1)

    emit(str(start_id), 0)
    return "\n".join(lines)


def to_seed_fragment(result: dict) -> str:
    """Emit a seed-format JSON fragment (persons/families/events) for review.

    Refs are 'fg<memorial_id>'. Husband/wife roles in families are a best guess
    (FindAGrave detail doesn't expose sex) — verify before merging.
    """
    people = result["people"]
    persons = []
    events = []
    for mid, p in people.items():
        ref = f"fg{mid}"
        given, surname = _split_name(p["name"])
        persons.append({
            "ref": ref, "given": given, "surname": surname, "sex": "U",
            "notes": f"FindAGrave memorial {mid}",
        })
        if p["birth"]:
            events.append({"person": ref, "type": "BIRT", "date": p["birth"],
                           "notes": f"FindAGrave memorial {mid}"})
        if p["death"]:
            events.append({"person": ref, "type": "DEAT", "date": p["death"],
                           "notes": f"FindAGrave memorial {mid}"})
        if p["cemetery"]:
            events.append({"person": ref, "type": "BURI", "place": p["cemetery"],
                           "notes": f"FindAGrave memorial {mid}"})

    # families: one per spouse pair, plus single-parent families
    families = []
    children_of_pair: dict[frozenset, list[str]] = {}
    pair_members: set[str] = set()
    for a, b in result["spouse_edges"]:
        pair = frozenset((a, b))
        pair_members.update(pair)
        kids = sorted({c for (par, c) in result["parent_edges"] if par in pair})
        children_of_pair[pair] = kids
        a_ref, b_ref = f"fg{a}", f"fg{b}"
        families.append({"husband": a_ref, "wife": b_ref,
                         "children": [f"fg{c}" for c in kids],
                         "_verify_roles": True})
    # parents that have children but no recorded spouse
    for parent, child in result["parent_edges"]:
        if parent in pair_members:
            continue
        existing = next((f for f in families if f.get("husband") == f"fg{parent}" and f["wife"] is None), None)
        if existing:
            if f"fg{child}" not in existing["children"]:
                existing["children"].append(f"fg{child}")
        else:
            families.append({"husband": f"fg{parent}", "wife": None,
                             "children": [f"fg{child}"]})

    return json.dumps({"persons": persons, "families": families, "events": events}, indent=2)


def _split_name(name: str) -> tuple[str, str]:
    parts = name.split()
    if len(parts) < 2:
        return name, ""
    return " ".join(parts[:-1]), parts[-1]
