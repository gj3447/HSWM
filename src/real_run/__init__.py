"""Compatibility import for :mod:`hswm.prototypes.real_run`."""

from hswm.prototypes import real_run as _canonical
from hswm.prototypes.real_run import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
