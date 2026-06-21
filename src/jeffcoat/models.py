"""Lightweight dataclasses mirroring the schema.

These are plain data carriers used by collectors and the GEDCOM exporter so
code doesn't pass raw sqlite Rows around.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Person:
    id: str
    given: str = ""
    surname: str = ""
    suffix: str = ""
    sex: str = "U"
    notes: str = ""

    @property
    def display_name(self) -> str:
        base = f"{self.given} {self.surname}".strip()
        if self.suffix:
            base = f"{base} {self.suffix}".strip()
        return base or "(unknown)"


@dataclass
class Event:
    type: str                # GEDCOM tag, e.g. BIRT
    date: str = ""
    place: str = ""
    notes: str = ""
    person_id: str | None = None
    family_id: str | None = None
    id: int | None = None


@dataclass
class Family:
    id: str
    husband_id: str | None = None
    wife_id: str | None = None
    children: list[str] = field(default_factory=list)


@dataclass
class Source:
    id: str
    title: str
    collector: str = ""
    url: str = ""
    repository: str = ""


@dataclass
class Citation:
    source_id: str
    person_id: str | None = None
    event_id: int | None = None
    page: str = ""
    text: str = ""
    confidence: str = "unverified"
