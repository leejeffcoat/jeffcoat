"""FindAGrave collector — WORKING via HTML scrape (no Playwright, no API key).

FindAGrave has no public API and is Ancestry-owned, but its search results page
serves real HTML to a browser User-Agent (no Cloudflare challenge for normal
rates). We parse the memorial cards directly. Scrape at personal rate only, for
your own family research.

Each result becomes a BURI finding with the cemetery + location as the place and
the death date as the event date; the full "b. … d. …" string is kept in the
summary, and both dates are preserved in raw for future multi-event attach.
"""

from __future__ import annotations

import html as html_lib
import re
import time
import urllib.parse

from ..models import Person
from .base import Collector, Finding
from .http_util import get_html

SEARCH_URL = "https://www.findagrave.com/memorial/search"

_ITEM_RE = re.compile(r'id="sr-(\d+)"(.*?)(?=id="sr-\d+"|memorial-list-data-footer|</main>)', re.S)
_NAME_RE = re.compile(r'name-grave[^>]*>\s*<i[^>]*>(.*?)</i>', re.S)
_DATES_RE = re.compile(r'birthDeathDates[^>]*>(.*?)</b>', re.S)
_CEM_RE = re.compile(r'title="([^"]*)"[^>]*>[^<]*</button>\s*</form>', re.S)
_ADDR_RE = re.compile(r'addr-cemet[^>]*>(.*?)</p>', re.S)
_SLUG_RE = re.compile(r'href="(/memorial/\d+/[^"]+)"')

_MONTHS = {m.lower(): m.upper() for m in
           ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]}


class FindAGraveCollector(Collector):
    name = "findagrave"
    requires = ()  # plain HTTP + regex; no Playwright

    def search(self, person: Person, place: str = "", rows: int = 5, **kwargs) -> list[Finding]:
        params = {
            "firstname": person.given,
            "lastname": person.surname,
        }
        if place:
            params["location"] = place
        url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
        page = get_html(url, use_curl=True)  # Cloudflare TLS fingerprinting

        findings: list[Finding] = []
        for mem_id, block in _ITEM_RE.findall(page):
            name = _clean(_first(_NAME_RE, block)) or person.display_name
            raw_dates = _clean(_first(_DATES_RE, block))
            birth, death = _split_dates(raw_dates)
            cemetery = _clean(_first(_CEM_RE, block))
            location = _clean(_first(_ADDR_RE, block))
            slug = _first(_SLUG_RE, block)
            mem_url = f"https://www.findagrave.com{slug}" if slug else \
                f"https://www.findagrave.com/memorial/{mem_id}"
            place_str = ", ".join(p for p in (cemetery, location) if p)
            summary = f"b. {birth or '?'}  d. {death or '?'}"
            if cemetery:
                summary += f"  ({cemetery})"
            findings.append(
                Finding(
                    collector=self.name,
                    title=f"{name}, FindAGrave memorial {mem_id}",
                    url=mem_url,
                    summary=summary,
                    date=_gedcom_date(death) or _gedcom_date(birth),
                    place=place_str,
                    event_type="BURI",
                    confidence="probable",
                    raw={"memorial_id": mem_id, "birth": birth, "death": death,
                         "cemetery": cemetery, "location": location},
                )
            )
            if len(findings) >= rows:
                break
        return findings


MEMORIAL_URL = "https://www.findagrave.com/memorial/{id}"

_H1_RE = re.compile(r'<h1[^>]*itemprop="name"[^>]*>(.*?)</h1>', re.S)
# Anchor on the main person's label id; family-member cards use id="family*".
_BIRTH_RE = re.compile(r'id="birthDateLabel"[^>]*itemprop="birthDate"[^>]*>\s*([^<]+?)\s*<')
_DEATH_RE = re.compile(r'id="deathDateLabel"[^>]*itemprop="deathDate"[^>]*>\s*([^<]+?)\s*<')
_CEMNAME_RE = re.compile(r'href="/cemetery/\d+/[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([^<]+?)\s*<', re.S)
_RELBLOCK_RE = re.compile(
    r'<b id="\w+Label" class="label-relation">([^<]+)</b>(.*?)</ul>', re.S)
# Capture the whole name node up to </h3>; it may contain an <i>maiden</i> tag,
# which _clean() flattens (so "Ina Letha <i>Livingston</i> Poole" survives).
_RELMEMBER_RE = re.compile(
    r'href="/memorial/(\d+)/[^"]+"[\s\S]*?itemprop="name">([\s\S]*?)</h3>', re.S)


def fetch_memorial(mem_id: str | int) -> dict:
    """Fetch one FindAGrave memorial detail page and return structured data:

    {id, name, birth, death, cemetery, url,
     relations: {Parents: [(id,name)], Spouse: [...], Children: [...], Siblings: [...]}}
    Dates are GEDCOM-formatted. Read-only; one HTTP request.
    """
    url = MEMORIAL_URL.format(id=mem_id)
    # FindAGrave can return a short stub for rapid successive requests; retry.
    doc = get_html(url, use_curl=True, courtesy_delay=1.2)
    raw_name = _first(_H1_RE, doc)
    if not raw_name:
        time.sleep(3)
        doc = get_html(url, use_curl=True, courtesy_delay=1.2)
        raw_name = _first(_H1_RE, doc)

    # the h1 carries a veteran badge (<b ...>) after the name — cut it off first
    name = _clean(raw_name.split("<b", 1)[0])
    birth = _gedcom_date(_clean(_first(_BIRTH_RE, doc)))
    death = _gedcom_date(_clean(_first(_DEATH_RE, doc)))
    cemetery = _clean(_first(_CEMNAME_RE, doc))

    relations: dict[str, list[tuple[str, str]]] = {}
    for rel, seg in _RELBLOCK_RE.findall(doc):
        members = [(mid, _clean(nm)) for mid, nm in _RELMEMBER_RE.findall(seg)]
        if members:
            relations[rel.strip()] = members
    return {
        "id": str(mem_id),
        "name": name,
        "birth": birth,
        "death": death,
        "cemetery": cemetery,
        "url": url,
        "relations": relations,
    }


def _first(rx: re.Pattern, text: str) -> str:
    m = rx.search(text)
    return m.group(1) if m else ""


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_lib.unescape(s)
    return " ".join(s.split())


def _split_dates(s: str) -> tuple[str, str]:
    # "22 Jun 1927 – 10 Sep 1981" (en dash may already be unescaped)
    parts = re.split(r"\s*[–—-]\s*", s, maxsplit=1)
    birth = parts[0].strip() if parts else ""
    death = parts[1].strip() if len(parts) > 1 else ""
    return birth, death


def _gedcom_date(s: str) -> str:
    if not s or s.lower() in ("unknown", "?"):
        return ""
    # "22 Jun 1927" -> "22 JUN 1927"; "1927" -> "1927"
    m = re.match(r"(?:(\d{1,2})\s+)?([A-Za-z]{3,})?\s*(\d{4})", s)
    if not m:
        return s
    day, mon, year = m.group(1), m.group(2), m.group(3)
    out = []
    if day:
        out.append(str(int(day)))
    if mon and mon[:3].lower() in _MONTHS:
        out.append(_MONTHS[mon[:3].lower()])
    out.append(year)
    return " ".join(out)
