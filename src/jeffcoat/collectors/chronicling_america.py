"""Chronicling America (Library of Congress) collector — WORKING, no API key.

Searches digitized public-domain historic US newspapers. Great for obituaries,
marriage notices, and residence mentions. Stdlib only (urllib).

Uses the current loc.gov collections JSON API (the old chroniclingamerica.loc.gov
search host was retired and now 404s). Endpoint:
  https://www.loc.gov/collections/chronicling-america/?q=..&fo=json&at=results
Place filtering uses the location facet, e.g. fa=location:south carolina.
API docs: https://www.loc.gov/apis/json-and-yaml/
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from ..models import Person
from .base import Collector, Finding

BASE_URL = "https://www.loc.gov/collections/chronicling-america/"
USER_AGENT = "jeffcoat-genealogy/0.1 (personal research)"


class ChroniclingAmericaCollector(Collector):
    name = "chronicling_america"
    requires = ()

    def search(self, person: Person, place: str = "", rows: int = 5, **kwargs) -> list[Finding]:
        name = person.display_name
        params = [
            ("q", name),
            ("fo", "json"),
            ("at", "results"),
            ("c", str(rows)),
        ]
        if place:
            params.append(("fa", f"location:{place.lower()}"))
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        findings: list[Finding] = []
        for item in (data.get("results") or [])[:rows]:
            title = item.get("title") or "newspaper page"
            iso = item.get("date", "")  # YYYY-MM-DD
            pretty_date = _gedcom_date(iso)
            page_url = item.get("url", "") or item.get("id", "")
            partof = item.get("partof_title") or []
            paper = partof[0] if partof else ""
            snippet = _first_snippet(_desc(item), name)
            findings.append(
                Finding(
                    collector=self.name,
                    title=title,
                    url=page_url,
                    summary=snippet,
                    date=pretty_date,
                    place=paper,
                    event_type="",  # newspaper mention — caller decides DEAT/MARR/RESI
                    confidence="unverified",
                    raw={k: item.get(k) for k in ("id", "date", "title", "partof_title")},
                )
            )
        return findings


def _desc(item: dict) -> str:
    d = item.get("description")
    if isinstance(d, list):
        return d[0] if d else ""
    return d or ""


def _gedcom_date(iso: str) -> str:
    if not iso or len(iso) < 4:
        return ""
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    parts = iso.split("-")
    y = parts[0]
    if len(parts) == 3:
        try:
            return f"{int(parts[2])} {months[int(parts[1]) - 1]} {y}"
        except (ValueError, IndexError):
            return y
    return y


def _first_snippet(ocr: str, name: str, width: int = 200) -> str:
    if not ocr:
        return ""
    lo = ocr.lower()
    last = name.lower().split()[-1] if name else ""
    idx = lo.find(last) if last else -1
    if idx == -1:
        return " ".join(ocr[:width].split())
    start = max(0, idx - width // 2)
    return " ".join(ocr[start:start + width].split())
