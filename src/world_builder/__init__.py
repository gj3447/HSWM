"""Compatibility alias for the historical flat ``world_builder`` import."""

from __future__ import annotations

import sys as _sys

from hswm.substrate import world_builder as _canonical


_sys.modules[__name__] = _canonical
