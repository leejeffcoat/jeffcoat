"""Collector registry.

Add a new source by importing its class and adding it to REGISTRY.
"""

from __future__ import annotations

from .base import Collector, Finding
from .chronicling_america import ChroniclingAmericaCollector
from .familysearch import FamilySearchCollector
from .findagrave import FindAGraveCollector
from .wikitree import WikiTreeCollector

REGISTRY: dict[str, type[Collector]] = {
    ChroniclingAmericaCollector.name: ChroniclingAmericaCollector,
    WikiTreeCollector.name: WikiTreeCollector,
    FamilySearchCollector.name: FamilySearchCollector,
    FindAGraveCollector.name: FindAGraveCollector,
}


def get(name: str) -> Collector:
    if name not in REGISTRY:
        raise KeyError(f"unknown collector '{name}'. Known: {', '.join(REGISTRY)}")
    return REGISTRY[name]()


__all__ = ["Collector", "Finding", "REGISTRY", "get"]
