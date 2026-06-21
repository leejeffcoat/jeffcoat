"""Collector interface.

A collector queries one data source about a person and returns Findings.
A Finding bundles proposed facts together with the source/citation they came
from, so nothing enters the tree unsourced. Collectors never write to the DB
directly — the caller reviews Findings and decides what to merge. That keeps
scraped guesses out of the proven tree until you say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Person


@dataclass
class Finding:
    """One candidate result from a source about a person."""
    collector: str
    title: str                      # human-readable source title for the citation
    url: str = ""
    summary: str = ""               # what the source says, transcribed
    date: str = ""                  # GEDCOM-style date if the source implies one
    place: str = ""
    event_type: str = ""            # suggested GEDCOM tag (BIRT/DEAT/RESI/CENS...) if any
    confidence: str = "unverified"
    raw: dict = field(default_factory=dict)   # original payload for later re-parsing


class Collector:
    """Base class. Subclasses set name/requires and implement search()."""

    name: str = "base"
    #: extra pip packages this collector needs; empty means stdlib-only.
    requires: tuple[str, ...] = ()

    def check_requirements(self) -> None:
        import importlib
        missing = []
        for mod in self.requires:
            try:
                importlib.import_module(mod.split(">=")[0].split("==")[0].replace("-", "_"))
            except ImportError:
                missing.append(mod)
        if missing:
            raise RuntimeError(
                f"collector '{self.name}' needs: {', '.join(missing)} "
                f"(pip install {' '.join(missing)})"
            )

    def search(self, person: Person, **kwargs) -> list[Finding]:
        raise NotImplementedError
