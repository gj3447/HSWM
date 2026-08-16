"""Compatibility import for :mod:`hswm.prototypes.synth`."""

from hswm.prototypes import synth as _canonical
from hswm.prototypes.synth import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
