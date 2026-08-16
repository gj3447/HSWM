"""Compatibility import for :mod:`hswm.artifacts.layout`."""

from hswm.artifacts import layout as _canonical
from hswm.artifacts.layout import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
