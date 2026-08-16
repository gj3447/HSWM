"""Compatibility import for :mod:`hswm.learning.p1.rank_invariance`."""

from hswm.learning.p1 import rank_invariance as _canonical
from hswm.learning.p1.rank_invariance import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
