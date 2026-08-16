"""Compatibility import for :mod:`hswm.learning.p1v2.l0_diagnose`."""

from hswm.learning.p1v2 import l0_diagnose as _canonical
from hswm.learning.p1v2.l0_diagnose import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
