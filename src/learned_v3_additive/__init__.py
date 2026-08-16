"""Compatibility import for :mod:`hswm.prototypes.learned_v3_additive`."""

from hswm.prototypes import learned_v3_additive as _canonical
from hswm.prototypes.learned_v3_additive import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
