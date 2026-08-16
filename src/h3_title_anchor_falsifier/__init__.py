"""Compatibility import for :mod:`hswm.evaluation.h3.title_anchor_falsifier`."""

from hswm.evaluation.h3 import title_anchor_falsifier as _canonical
from hswm.evaluation.h3.title_anchor_falsifier import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
