"""Compatibility import for :mod:`hswm.substrate.supersede_ledger`."""

from hswm.substrate import supersede_ledger as _canonical
from hswm.substrate.supersede_ledger import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
