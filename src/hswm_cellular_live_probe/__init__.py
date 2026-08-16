"""Compatibility import for :mod:`hswm.cells.live_probe`."""

from hswm.cells import live_probe as _canonical
from hswm.cells.live_probe import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
