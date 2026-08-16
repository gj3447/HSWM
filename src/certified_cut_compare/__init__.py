"""Compatibility import for :mod:`hswm.substrate.certified_cut_compare`."""

from hswm.substrate import certified_cut_compare as _canonical
from hswm.substrate.certified_cut_compare import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
