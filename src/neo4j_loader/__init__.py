"""Compatibility import for :mod:`hswm.prototypes.neo4j_loader`."""

from hswm.prototypes import neo4j_loader as _canonical
from hswm.prototypes.neo4j_loader import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
