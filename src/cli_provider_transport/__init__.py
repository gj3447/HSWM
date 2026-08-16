"""Compatibility import for :mod:`hswm.infrastructure.cli_provider_transport`."""

from hswm.infrastructure import cli_provider_transport as _canonical
from hswm.infrastructure.cli_provider_transport import *  # noqa: F401,F403


def __getattr__(name: str):
    return getattr(_canonical, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_canonical)))
