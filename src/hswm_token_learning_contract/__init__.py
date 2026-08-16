"""Compatibility import for :mod:`hswm.learning.token_learning_contract`."""

from hswm.learning import token_learning_contract as _canonical
from hswm.learning.token_learning_contract import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
