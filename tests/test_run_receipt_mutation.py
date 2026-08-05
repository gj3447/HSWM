"""Integration test: run_receipt --mutation-target chains a full mutation_score.

v2.7 — the chained record must carry the allowlist-adjusted picture
(effective_total / equivalents / open_gaps / survivors), not only killed/total.

v3.3 — the operator table is derived from the ast spec (ordering comparisons are
family-closed, arithmetic replaces within {Add, Sub, Mult}), so the same fixture
now yields FIVE sites instead of three. The old expectation (2/3) was a
transcript of the hand-written dict; it is restated here from the derived set.

Fixture: a tiny module with exactly five single-fault sites and a receipt that
holds against the original. Expected mutant outcomes:

  cmp GtE->Gt    : pick(10) -> 0  != 11  -> KILLED
  cmp GtE->Lt    : pick(10) -> 0  != 11  -> KILLED
  cmp GtE->LtE   : pick(10) -> 11 == 11  -> SURVIVES (boundary is not observed)
  binop Add->Sub : pick(10) -> 9  != 11  -> KILLED
  binop Add->Mult: pick(10) -> 10 != 11  -> KILLED

so the chained score must be killed=4, total=5, open_gaps=1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TINY_MOD = '''\
def pick(x):
    if x >= 10:
        return x + 1
    return 0
'''

TINY_RECEIPT = '''\
import tiny_mod

LOCK = {"F": "pick(10) == 11"}
LOCK_CHECKS = {"F": "f_ok"}


def main():
    f_ok = tiny_mod.pick(10) == 11
    ok = f_ok
    print("RECEIPT:", "VALID" if ok else "INVALID")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def test_run_receipt_chains_full_mutation_score(tmp_path):
    mod = tmp_path / "tiny_mod.py"
    mod.write_text(TINY_MOD)
    receipt = tmp_path / "tiny_receipt.py"
    receipt.write_text(TINY_RECEIPT)
    log = tmp_path / "chain.jsonl"

    env = dict(os.environ, PYTHONPATH=str(ROOT))
    r = subprocess.run(
        [sys.executable, "-m", "ooptdd.run_receipt", str(receipt),
         "--source", str(mod), "--mutation-target", str(mod),
         "--max-mutants", "8", "--log", str(log)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MUTATION SCORE: 4/5 killed" in r.stdout

    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(records) == 1
    ms = records[0]["mutation_score"]
    assert ms["killed"] == 4
    assert ms["total"] == 5
    # tiny_mod has no allowlist entries: no documented equivalents, the
    # GtE->LtE survivor must show up as an honest open gap
    assert ms["effective_total"] == 5
    assert ms["equivalents"] == 0
    assert ms["open_gaps"] == 1
    assert any("GtE->LtE" in s for s in ms["survivors"])
    assert ms["errors"] == []
    # a chained score must carry the pool it was sampled from and the operator
    # table that built the pool, or two scores cannot be told apart
    assert ms["sites_available"] == 5
    assert ms["sample_seed"] == 20260805
    assert len(ms["operator_set"]) == 12
    assert ms["operator_set"] in r.stdout

    # module under mutation must be restored byte-identical after the run
    assert mod.read_text() == TINY_MOD
