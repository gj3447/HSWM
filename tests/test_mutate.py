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

import ast

from ooptdd.mutate import (
    BINOP_FLIPS,
    BOOL_FAMILIES,
    BOOLOP_FLIPS,
    BIN_FAMILIES,
    CMP_FAMILIES,
    COMPARE_FLIPS,
    EXCLUDED_AS_REPLACEMENT,
    EXCLUDED_AS_SOURCE,
    UNARY_FAMILIES,
    UNARYOP_REMOVALS,
    _assert_spec_classified,
    collect_sites,
    mutation_score,
    operator_set_digest,
    render_mutant,
)

TOY_MODULE = textwrap.dedent('''
    import numpy as np

    def score(x):
        return x * 2 + 1

    def floor_ok(w, c):
        return (w - c) >= 0

    def clip_pos(x):
        return np.maximum(x, 0)
''')

# operators the hand-written dicts could not see at all: `/`, `%`, `and`, `not`,
# unary `-`, `in`. Under COMPARE_FLIPS/BINOP_FLIPS as they were shipped before
# v3.3 this module produced ZERO sites for every line below.
BLIND_SPOT_MODULE = textwrap.dedent('''
    def ratio(a, b):
        return a / b

    def wrap(i, n):
        return i % n

    def gate(x, y):
        return x and y

    def missing(k, d):
        return k not in d

    def flip(ok):
        return not ok

    def neg(x):
        return -x
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


def test_pytest_runner_kills_in_package_layout(tmp_path):
    """Regression for the vacuity-map all-zero bug: tests living in a PACKAGE
    (tests/__init__.py) made pytest insert the repo root at sys.path[0], above
    PYTHONPATH, so shadowed mutants never loaded. In-place patching must kill.
    """
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "toy_mod.py").write_text(TOY_MODULE)
    (tmp_path / "tests" / "test_toy.py").write_text(textwrap.dedent('''
        import toy_mod
        def test_floor():
            assert toy_mod.floor_ok(1.0, 1.0)
        def test_clip():
            assert toy_mod.clip_pos(-2.0) == 0.0
    '''))
    result = mutation_score(
        str(tmp_path / "toy_mod.py"),
        str(tmp_path / "tests" / "test_toy.py"),
        repo_root=str(tmp_path),
        max_mutants=20, timeout_per_run=60, runner="pytest",
    )
    assert result["killed"] >= 2, f"package-layout mutants must die: {result}"


def test_module_bytes_restored_after_run(toy_repo):
    """Negative oracle for the restore path: a mutated-then-restored module
    must be byte-identical, or every later run tests the wrong code."""
    path = os.path.join(toy_repo, "toy_mod.py")
    before = open(path, "rb").read()
    mutation_score(path, os.path.join(toy_repo, "receipt_toy.py"),
                   repo_root=toy_repo, max_mutants=4, timeout_per_run=60)
    assert open(path, "rb").read() == before


# ---------------------------------------------------------------------------
# v3.3 — the operator table must be DERIVED from the ast spec.
# These tests are written so that restoring a hand-written dict fails them.
# ---------------------------------------------------------------------------

SPECS = [
    (ast.cmpop, CMP_FAMILIES, COMPARE_FLIPS),
    (ast.operator, BIN_FAMILIES, BINOP_FLIPS),
    (ast.boolop, BOOL_FAMILIES, BOOLOP_FLIPS),
]


@pytest.mark.parametrize("base,families,flips", SPECS)
def test_every_spec_operator_is_classified(base, families, flips):
    """Nothing in the ast spec may be silently absent.

    The pre-v3.3 tables were BINOP_FLIPS = {Add, Sub, Mult} — Div, Mod,
    FloorDiv, Pow, and every bitwise operator were neither mutated nor
    excluded, they were invisible. Re-introducing a hand list fails here.
    """
    declared = {op for members in families.values() for op in members}
    assert declared == set(base.__subclasses__()), (
        f"{base.__name__} families drifted from the spec: "
        f"{sorted(c.__name__ for c in set(base.__subclasses__()) ^ declared)}")
    for op in base.__subclasses__():
        assert op in flips or op in EXCLUDED_AS_SOURCE, (
            f"{op.__name__} is neither mutated nor excluded with a reason")


def test_unaryop_spec_is_classified():
    declared = {op for members in UNARY_FAMILIES.values() for op in members}
    assert declared == set(ast.unaryop.__subclasses__())
    for op in ast.unaryop.__subclasses__():
        assert op in UNARYOP_REMOVALS or op in EXCLUDED_AS_SOURCE


def test_exclusions_are_documented_and_live():
    """Fail-closed like allowlist.py: an exclusion without a reason is refused,
    and an exclusion for something outside the spec is dead code hiding intent."""
    spec = (set(ast.cmpop.__subclasses__()) | set(ast.operator.__subclasses__())
            | set(ast.boolop.__subclasses__()) | set(ast.unaryop.__subclasses__()))
    assert EXCLUDED_AS_SOURCE and EXCLUDED_AS_REPLACEMENT
    for table in (EXCLUDED_AS_SOURCE, EXCLUDED_AS_REPLACEMENT):
        for op, reason in table.items():
            assert op in spec, f"{op.__name__} excluded but not in the ast spec"
            assert reason.strip(), f"{op.__name__} excluded without a reason"


@pytest.mark.parametrize("base,families,flips", SPECS)
def test_replacements_stay_within_family(base, families, flips):
    """Cross-family mutants (`x is None` -> `x < None`) raise TypeError and are
    killed by any test that reaches the line — free kills that inflate the
    score instead of measuring the oracle."""
    of_op = {op: name for name, members in families.items() for op in members}
    for op, repls in flips.items():
        for r in repls:
            assert of_op[r] == of_op[op], f"{op.__name__}->{r.__name__} crosses families"
            assert r is not op
            assert r not in EXCLUDED_AS_REPLACEMENT


def test_derived_set_is_strictly_richer_than_the_old_hand_dict():
    """The shipped hand dict, verbatim — every one of its entries must survive,
    and the derived set must add the direction reversals it never had."""
    hand = {ast.GtE: [ast.Gt, ast.LtE], ast.LtE: [ast.Lt], ast.Gt: [ast.GtE],
            ast.Lt: [ast.LtE], ast.Eq: [ast.NotEq], ast.NotEq: [ast.Eq]}
    for op, repls in hand.items():
        assert set(repls) <= set(COMPARE_FLIPS[op])
    assert ast.Lt in COMPARE_FLIPS[ast.GtE]   # reversal, absent from the hand dict
    assert ast.Gt in COMPARE_FLIPS[ast.LtE]
    hand_bin = {ast.Add: [ast.Sub], ast.Sub: [ast.Add], ast.Mult: [ast.Add]}
    for op, repls in hand_bin.items():
        assert set(repls) <= set(BINOP_FLIPS[op])
    assert ast.Div in BINOP_FLIPS and ast.Mod in BINOP_FLIPS  # invisible before


def test_spec_drift_is_fail_closed():
    incomplete = {"ordering": (ast.Lt, ast.LtE, ast.Gt, ast.GtE)}
    with pytest.raises(RuntimeError, match="out of sync"):
        _assert_spec_classified(ast.cmpop, incomplete)


def test_operator_set_digest_tracks_the_table(monkeypatch):
    """A score is only comparable to one produced by the same operators."""
    before = operator_set_digest()
    assert len(before) == 12
    monkeypatch.setitem(COMPARE_FLIPS, ast.Lt, [ast.LtE])
    assert operator_set_digest() != before


def test_blind_spot_operators_now_have_sites(tmp_path):
    path = tmp_path / "blind.py"
    path.write_text(BLIND_SPOT_MODULE)
    sites = collect_sites(str(path))
    kinds = {s.kind for s in sites}
    assert {"boolop", "unaryop", "binop", "compare"} <= kinds
    details = {s.detail for s in sites}
    assert "And->Or" in details
    assert "Not->remove" in details and "USub->remove" in details
    assert "NotIn->In" in details
    assert any(d.startswith("Div->") for d in details)
    assert any(d.startswith("Mod->") for d in details)


def test_sites_are_uniquely_identified_in_associative_chains(tmp_path):
    """(a + b) + c: both Add nodes report the column of `a`, so a positional
    site id names two nodes and the transformer can only ever reach the inner
    one. Ordinals must give one id and one distinct mutant per node."""
    path = tmp_path / "chain.py"
    path.write_text("def f(a, b, c):\n    return a + b + c\n")
    sites = [s for s in collect_sites(str(path)) if s.detail == "Add->Sub"]
    assert len(sites) == 2
    assert len({s.site_id for s in sites}) == 2
    rendered = {render_mutant(str(path), s) for s in sites}
    assert len(rendered) == 2 and None not in rendered


def test_boolop_and_unaryop_mutants_are_killed(tmp_path):
    """Negative oracle for the new visitors: if `and`->`or` and `not x`->`x`
    survive a receipt that pins them, the new operators are decoration."""
    (tmp_path / "logic_mod.py").write_text(textwrap.dedent('''
        def both(a, b):
            return a and b

        def absent(ok):
            return not ok
    '''))
    (tmp_path / "receipt_logic.py").write_text(textwrap.dedent('''
        import logic_mod
        LOCK = {"and": "both(True, False) is False", "not": "absent(True) is False"}
        ok = (logic_mod.both(True, False) is False
              and logic_mod.absent(True) is False)
        print("RECEIPT:", "VALID" if ok else "INVALID")
        raise SystemExit(0 if ok else 1)
    '''))
    result = mutation_score(
        str(tmp_path / "logic_mod.py"), str(tmp_path / "receipt_logic.py"),
        repo_root=str(tmp_path), max_mutants=20, timeout_per_run=60)
    assert result["total"] == 2, result
    assert result["killed"] == 2, f"boolop/unaryop mutants must die: {result}"


def test_score_records_pool_and_operator_set(toy_repo):
    result = mutation_score(
        os.path.join(toy_repo, "toy_mod.py"),
        os.path.join(toy_repo, "receipt_toy.py"),
        repo_root=toy_repo, max_mutants=2, timeout_per_run=60)
    assert result["total"] == 2
    assert result["sites_available"] == len(collect_sites(
        os.path.join(toy_repo, "toy_mod.py")))
    assert result["sites_available"] > result["total"]
    assert result["operator_set"] == operator_set_digest()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
