"""Tests for ooptdd.mutate — including its own negative oracle.

If a comparison-flip mutant of a toy module is NOT killed by its receipt,
the mutation runner itself is vacuous.
"""
from __future__ import annotations

import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd.mutate import collect_sites, mutation_score, render_mutant

TOY_MODULE = textwrap.dedent('''
    import numpy as np

    def score(x):
        return x * 2 + 1

    def floor_ok(w, c):
        return (w - c) >= 0

    def clip_pos(x):
        return np.maximum(x, 0)
''')

TOY_RECEIPT = textwrap.dedent('''
    import toy_mod
    LOCK = {"floor": "floor_ok(w,c) is True when w>=c", "clip": "clip_pos zeroes negatives"}
    ok = (toy_mod.floor_ok(1.0, 1.0)
          and toy_mod.clip_pos(3.0) == 3.0
          and toy_mod.clip_pos(-2.0) == 0.0)
    print("RECEIPT:", "VALID" if ok else "INVALID")
    raise SystemExit(0 if ok else 1)
''')


@pytest.fixture()
def toy_repo(tmp_path):
    (tmp_path / "toy_mod.py").write_text(TOY_MODULE)
    (tmp_path / "receipt_toy.py").write_text(TOY_RECEIPT)
    return str(tmp_path)


def test_collect_sites_kinds(toy_repo):
    sites = collect_sites(os.path.join(toy_repo, "toy_mod.py"))
    kinds = {s.kind for s in sites}
    assert "compare" in kinds and "binop" in kinds and "clip-removal" in kinds


def test_render_mutant_applies_and_unparses(toy_repo):
    path = os.path.join(toy_repo, "toy_mod.py")
    site = next(s for s in collect_sites(path) if s.kind == "clip-removal")
    src = render_mutant(path, site)
    assert src is not None and "maximum" not in src


def test_negative_oracle_mutants_are_killed(toy_repo):
    result = mutation_score(
        os.path.join(toy_repo, "toy_mod.py"),
        os.path.join(toy_repo, "receipt_toy.py"),
        repo_root=toy_repo,
        max_mutants=20,
        timeout_per_run=60,
    )
    assert result["total"] > 0
    # the >= -> <= flip on floor_ok(1.0,1.0) and the clip removal must be killed
    assert result["killed"] >= 2, f"vacuous runner: {result}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
