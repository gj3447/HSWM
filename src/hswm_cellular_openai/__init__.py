"""Compatibility import for :mod:`hswm.cells.openai`."""

from hswm.cells import openai as _canonical
from hswm.cells.openai import *  # noqa: F401,F403

# Preserve the existing nested monkeypatch path while sharing canonical state.
urlrequest = _canonical.urlrequest


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
