"""Compatibility import for :mod:`hswm.evaluation.stats_protocol`."""

from hswm.evaluation import stats_protocol as _canonical
from hswm.evaluation.stats_protocol import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
