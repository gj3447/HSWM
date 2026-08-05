"""Repository validation scripts.

tests/test_hswm_research_ledger.py and tests/test_hswm_semantic_weight_metric.py
import from this directory (`from scripts.validate_... import ...`). It worked in
the source tree as an implicit namespace package, which is exactly why it was
invisible to packaging: setuptools' build_py skips a directory listed in
`packages` when it has no __init__.py, so the wheel shipped nothing and the sdist
shipped nothing, and both tests failed to collect there. Keep this file.
"""
