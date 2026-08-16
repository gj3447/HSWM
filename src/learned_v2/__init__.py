"""Compatibility import for :mod:`hswm.prototypes.learned_v2`."""

from hswm.prototypes import learned_v2 as _canonical
from hswm.prototypes.learned_v2 import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
