"""Compatibility import for :mod:`hswm.prototypes.llm_judgment_loop`."""

from hswm.prototypes import llm_judgment_loop as _canonical
from hswm.prototypes.llm_judgment_loop import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
