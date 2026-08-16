"""Compatibility import for :mod:`_research.bookscale.c1_prelude_bookscale`."""

from _research.bookscale import c1_prelude_bookscale as _canonical
from _research.bookscale.c1_prelude_bookscale import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
