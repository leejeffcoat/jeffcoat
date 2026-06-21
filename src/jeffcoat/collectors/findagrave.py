"""FindAGrave collector — STUB (Playwright scraper).

FindAGrave has no public API and is Ancestry-owned. Scrape at personal rate
only, for your own family research. This collector is intentionally a stub so
the dependency (Playwright) is opt-in.

To implement: pip install playwright && playwright install chromium, then drive
a headless browser to the search results page and parse memorial cards. Always
run headless (project standing rule) and add a polite delay between requests.
"""

from __future__ import annotations

from ..models import Person
from .base import Collector, Finding


class FindAGraveCollector(Collector):
    name = "findagrave"
    requires = ("playwright",)

    def search(self, person: Person, **kwargs) -> list[Finding]:
        self.check_requirements()  # raises a clear message if Playwright missing
        # TODO: launch headless chromium, navigate to
        #   https://www.findagrave.com/memorial/search?firstname=..&lastname=..
        # parse memorial cards into Findings (BURI events with cemetery + GPS).
        raise NotImplementedError(
            "findagrave scraper not yet implemented — see module docstring"
        )
