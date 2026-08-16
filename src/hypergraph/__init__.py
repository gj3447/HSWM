"""Compatibility alias for the historical flat ``hypergraph`` import."""

from __future__ import annotations

import sys as _sys

from hswm.substrate import hypergraph as _canonical


_sys.modules[__name__] = _canonical
