"""Compatibility import for :mod:`hswm.prototypes.falsifier`."""

from hswm.prototypes import falsifier as _canonical
from hswm.prototypes.falsifier import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
