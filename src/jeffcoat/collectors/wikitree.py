"""WikiTree collector — WORKING for public profiles, no API key.

WikiTree exposes a free JSON API. Public profiles and relationships are
readable without login; some living-person fields require an authenticated
session (not implemented here — personal research generally targets deceased
ancestors, which are public).

API docs: https://github.com/wikitree/wikitree-api
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from ..models import Person
from .base import Collector, Finding

API_URL = "https://api.wikitree.com/api.php"
USER_AGENT = "jeffcoat-genealogy/0.1 (personal research)"


class WikiTreeCollector(Collector):
    name = "wikitree"
    requires = ()

    def search(self, person: Person, birth_year: str = "", rows: int = 5, **kwargs) -> list[Finding]:
        # WikiTree's open endpoint searches by name fields.
        params = {
            "action": "getProfile",
            "key": "",  # filled per-result below; here we use the search action instead
        }
        # Use the searchPerson action (public).
        params = {
            "action": "searchPerson",
            "FirstName": person.given,
            "LastName": person.surname,
            "fields": "Name,FirstName,LastNameAtBirth,BirthDate,DeathDate,BirthLocation,DeathLocation",
            "limit": str(rows),
            "format": "json",
        }
        if birth_year:
            params["BirthDate"] = birth_year
        url = API_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        findings: list[Finding] = []
        # searchPerson returns a list; shape is [{"matches":[...]}] or similar.
        matches = _extract_matches(payload)
        for m in matches[:rows]:
            wt_id = m.get("Name", "")
            first = m.get("FirstName", "")
            last = m.get("LastNameAtBirth", "")
            birth = m.get("BirthDate", "")
            death = m.get("DeathDate", "")
            bloc = m.get("BirthLocation", "")
            findings.append(
                Finding(
                    collector=self.name,
                    title=f"WikiTree profile {wt_id}: {first} {last}",
                    url=f"https://www.wikitree.com/wiki/{wt_id}" if wt_id else "",
                    summary=f"b. {birth or '?'} {bloc}  d. {death or '?'}".strip(),
                    date=_gedcom_date(birth),
                    place=bloc,
                    event_type="BIRT" if birth else "",
                    confidence="probable",
                    raw=m,
                )
            )
        return findings


def _extract_matches(payload) -> list[dict]:
    if isinstance(payload, list):
        for block in payload:
            if isinstance(block, dict) and "matches" in block:
                return block["matches"] or []
    if isinstance(payload, dict) and "matches" in payload:
        return payload["matches"] or []
    return []


def _gedcom_date(iso: str) -> str:
    # WikiTree dates are YYYY-MM-DD with zeros for unknown parts.
    if not iso:
        return ""
    parts = iso.split("-")
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    y = parts[0]
    if y in ("", "0000"):
        return ""
    if len(parts) == 3 and parts[1] not in ("", "00") and parts[2] not in ("", "00"):
        try:
            return f"{int(parts[2])} {months[int(parts[1]) - 1]} {y}"
        except (ValueError, IndexError):
            return y
    return y
