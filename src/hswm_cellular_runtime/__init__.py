"""Compatibility import for :mod:`hswm.cells.runtime`."""

from hswm.cells import runtime as _canonical
from hswm.cells.runtime import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
