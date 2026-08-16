"""Compatibility import for :mod:`hswm.prototypes.synth_longdoc`."""

from hswm.prototypes import synth_longdoc as _canonical
from hswm.prototypes.synth_longdoc import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
