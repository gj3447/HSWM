"""Compatibility import for :mod:`hswm.evaluation.h3.b3_manifest`."""

from hswm.evaluation.h3 import b3_manifest as _canonical
from hswm.evaluation.h3.b3_manifest import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
