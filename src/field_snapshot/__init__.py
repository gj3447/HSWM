"""Compatibility alias for the historical flat ``field_snapshot`` import."""

from __future__ import annotations

import sys as _sys

from hswm.substrate import field_snapshot as _canonical


_sys.modules[__name__] = _canonical
