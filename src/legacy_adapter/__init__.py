"""Compatibility import for :mod:`hswm.substrate.legacy_adapter`."""

from hswm.substrate import legacy_adapter as _canonical
from hswm.substrate.legacy_adapter import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
