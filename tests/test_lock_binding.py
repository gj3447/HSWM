"""Tests for v2.2 LOCK↔check binding verification — with its own negative oracle.

A binding verifier that passes prose-only locks is vacuous, so the tests
include locks with no check, checks that don't gate, and non-claim exemptions.
"""
from __future__ import annotations

import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd.run_receipt import extract_lock, verify_lock_binding

GOOD = textwrap.dedent('''
    LOCK = {"F1_floor": "w >= c", "not_guaranteed": "per-query", "negative_oracle": "signed breaks"}
    LOCK_CHECKS = {"F1_floor": "f1_ok", "negative_oracle": ["neg_breaks"]}
    def main():
        f1_ok = True
        neg_breaks = True
        ok = f1_ok and neg_breaks
        return 0 if ok else 1
''')

PROSE_WITHOUT_CHECK = textwrap.dedent('''
    LOCK = {"F1_floor": "w >= c", "F2_ghost": "asserted in prose, never checked"}
    LOCK_CHECKS = {"F1_floor": "f1_ok"}
    def main():
        f1_ok = True
        ok = f1_ok
        return 0 if ok else 1
''')

NON_GATING_CHECK = textwrap.dedent('''
    LOCK = {"F1_floor": "w >= c"}
    LOCK_CHECKS = {"F1_floor": "f1_ok"}
    def main():
        f1_ok = False  # computed but cannot fail the run
        ok = True
        return 0 if ok else 1
''')

NO_LOCK_CHECKS = textwrap.dedent('''
    LOCK = {"F1_floor": "w >= c"}
    def main():
        return 0
''')


@pytest.fixture()
def write(tmp_path):
    def _w(name, src):
        p = tmp_path / name
        p.write_text(src)
        return str(p)
    return _w


def test_verified_binding(write):
    p = write("good.py", GOOD)
    status, problems = verify_lock_binding(p, extract_lock(p))
    assert status == "verified", problems


def test_negative_oracle_prose_without_check_is_broken(write):
    p = write("ghost.py", PROSE_WITHOUT_CHECK)
    status, problems = verify_lock_binding(p, extract_lock(p))
    assert status == "broken"
    assert any("F2_ghost" in pr for pr in problems)


def test_negative_oracle_non_gating_check_is_broken(write):
    p = write("deco.py", NON_GATING_CHECK)
    status, problems = verify_lock_binding(p, extract_lock(p))
    assert status == "broken"
    assert any("gate" in pr for pr in problems)


def test_absent_is_transitional_not_broken(write):
    p = write("bare.py", NO_LOCK_CHECKS)
    status, problems = verify_lock_binding(p, extract_lock(p))
    assert status == "absent"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
