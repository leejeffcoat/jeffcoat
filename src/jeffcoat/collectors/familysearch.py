"""FamilySearch collector — STUB.

FamilySearch is the strongest free source (census, vital records, GEDCOM
export) but its API requires a registered developer key and OAuth. Register an
app at https://www.familysearch.org/developers/ , put the key in config.toml or
the FAMILYSEARCH_APP_KEY env var, then flesh out search() against the
/platform/tree and /platform/records endpoints.

Until then this collector returns nothing and reports what it needs.
"""

from __future__ import annotations

import os

from ..models import Person
from .base import Collector, Finding


class FamilySearchCollector(Collector):
    name = "familysearch"
    requires = ()  # uses urllib once implemented

    def search(self, person: Person, **kwargs) -> list[Finding]:
        key = os.environ.get("FAMILYSEARCH_APP_KEY")
        if not key:
            raise RuntimeError(
                "FamilySearch needs a developer app key. Register at "
                "https://www.familysearch.org/developers/ and set "
                "FAMILYSEARCH_APP_KEY, then implement search() against "
                "/platform/tree/search."
            )
        # TODO: OAuth flow + GET /platform/tree/search?q.givenName=...&q.surname=...
        return []
