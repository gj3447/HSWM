"""Compatibility import for :mod:`hswm.cells.store`."""

from hswm.cells import store as _canonical
from hswm.cells.store import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
