"""Tests for v3 XLOCKS — executable predicate locks (G2 closure).

Pins the foundation: (a) authority moved from prose to predicate source,
(b) prose is generated and drift is refused, (c) the runner falsifies broken
properties (with counterexamples) and clears green ones, (d) the fallback
engine degrades visibly, (e) the harness chains per-key predicate evidence.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ooptdd.xlocks import (extract_xlocks, parse_xlocks_result, run_xlock,
                           verify_xlock_prose)

FIXTURE = '''\
import json
LOCK = {"F1": "lam is always non-negative"}
LOCK_CHECKS = {"F1": "f1_ok"}


def pred_f1(case):
    """lam is always non-negative"""
    return case["lam"] >= 0


XLOCKS = {"F1": "pred_f1"}
XLOCK_STRATEGIES = {"F1": {"seed": 0, "max_examples": 30, "dim": 4, "edges": 4}}


def main():
    from ooptdd import xlocks
    r = xlocks.run_xlock(pred_f1, XLOCK_STRATEGIES["F1"])
    f1_ok = r["ok"]
    ok = f1_ok
    print("XLOCKS_RESULT " + json.dumps({"F1": r}))
    print("RECEIPT:", "VALID" if ok else "INVALID")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

SPEC = {"seed": 0, "max_examples": 40, "dim": 4, "edges": 4}


def test_extract_xlocks_static(tmp_path):
    p = tmp_path / "receipt_t.py"
    p.write_text(FIXTURE)
    meta = extract_xlocks(str(p))
    assert set(meta) == {"F1"}
    assert meta["F1"]["fn"] == "pred_f1"
    assert meta["F1"]["prose"] == "lam is always non-negative"
    assert len(meta["F1"]["predicate_sha"]) == 64
    assert meta["F1"]["strategy"]["max_examples"] == 30


def test_authority_is_predicate_not_prose(tmp_path):
    p = tmp_path / "receipt_t.py"
    p.write_text(FIXTURE)
    sha1 = extract_xlocks(str(p))["F1"]["predicate_sha"]
    # cosmetic LOCK prose edit (docstring untouched): authority unchanged
    p.write_text(FIXTURE.replace('"lam is always non-negative"}', '"reworded prose, same claim"}'))
    assert extract_xlocks(str(p))["F1"]["predicate_sha"] == sha1
    # predicate BODY edit: authority must move
    p.write_text(FIXTURE.replace('return case["lam"] >= 0', 'return case["lam"] >= -1e-9'))
    assert extract_xlocks(str(p))["F1"]["predicate_sha"] != sha1


def test_prose_drift_refused(tmp_path):
    p = tmp_path / "receipt_t.py"
    p.write_text(FIXTURE.replace('"lam is always non-negative"}', '"some other claim"}'))
    meta = extract_xlocks(str(p))
    problems = verify_xlock_prose({"F1": "some other claim"}, meta)
    assert problems and "prose != predicate docstring" in problems[0]


def test_run_xlock_green_and_broken():
    green = run_xlock(lambda c: c["lam"] >= 0, SPEC)
    assert green["ok"] and green["engine"] == "hypothesis" and green["counterexample"] is None
    broken = run_xlock(lambda c: c["lam"] < 0.5, SPEC)
    assert not broken["ok"] and broken["engine"] == "hypothesis"
    assert broken["counterexample"], "a falsified property must carry a counterexample"


def test_run_xlock_forced_example_first():
    bad_forced = [{"pe": None, "q": None, "M": None, "lam": 1.0}]
    r = run_xlock(lambda c: c["lam"] >= 2.0, SPEC, forced=bad_forced)
    assert not r["ok"] and r["engine"] == "forced"


def test_fallback_engine_degrades_visibly(monkeypatch):
    monkeypatch.setitem(sys.modules, "hypothesis", None)
    monkeypatch.setitem(sys.modules, "hypothesis.strategies", None)
    monkeypatch.setitem(sys.modules, "hypothesis.extra", None)
    monkeypatch.setitem(sys.modules, "hypothesis.extra.numpy", None)
    r = run_xlock(lambda c: c["lam"] >= 0, SPEC)
    assert r["ok"] and r["engine"] == "fallback-unshrunk"


def _run_harness(tmp_path, source: str):
    receipt = tmp_path / "tiny_receipt.py"
    receipt.write_text(source)
    log = tmp_path / "chain.jsonl"
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, "-m", "ooptdd.run_receipt", str(receipt), "--log", str(log)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=180,
    ), log


def test_harness_chains_xlock_evidence(tmp_path):
    r, log = _run_harness(tmp_path, FIXTURE)
    assert r.returncode == 0, r.stdout + r.stderr
    rec = json.loads(log.read_text().splitlines()[0])
    xl = rec["xlocks"]["F1"]
    assert xl["ok"] and xl["engine"] == "hypothesis"
    assert len(xl["predicate_sha"]) == 64
    assert xl["strategy"]["max_examples"] == 30


def test_harness_refuses_prose_drift(tmp_path):
    drifted = FIXTURE.replace('"lam is always non-negative"}', '"edited prose"}')
    r, _log = _run_harness(tmp_path, drifted)
    assert r.returncode == 2
    assert "prose != predicate docstring" in r.stdout


def test_declared_but_unexecuted_xlock_fails_closed(tmp_path):
    no_emit = FIXTURE.replace('    print("XLOCKS_RESULT " + json.dumps({"F1": r}))\n', "")
    r, log = _run_harness(tmp_path, no_emit)
    assert r.returncode == 0, r.stdout + r.stderr  # receipt itself is green...
    rec = json.loads(log.read_text().splitlines()[0])
    assert rec["xlocks"]["F1"]["engine"] == "missing"
    assert rec["xlocks"]["F1"]["ok"] is False
    assert "xlocks WARNING" in r.stderr


def test_parse_xlocks_result_last_good():
    out = 'XLOCKS_RESULT {"F1": {"ok": true}}\nXLOCKS_RESULT {broken\n'
    assert parse_xlocks_result(out) == {"F1": {"ok": True}}


if __name__ == "__main__":
    raise SystemExit(__import__("pytest").main([__file__, "-q"]))
