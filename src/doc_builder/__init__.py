"""Compatibility alias for the historical flat ``doc_builder`` import."""

from __future__ import annotations

import sys as _sys

from hswm.substrate import doc_builder as _canonical


_sys.modules[__name__] = _canonical
