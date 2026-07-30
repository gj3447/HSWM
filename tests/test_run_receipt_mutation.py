"""Integration test: run_receipt --mutation-target chains a full mutation_score.

v2.7 — the chained record must carry the allowlist-adjusted picture
(effective_total / equivalents / open_gaps / survivors), not only killed/total.

Fixture: a tiny module with exactly three single-fault sites and a receipt that
holds against the original. Expected mutant outcomes:

  cmp GtE->Gt   : pick(10) -> 0  != 11  -> KILLED
  cmp GtE->LtE  : pick(10) -> 11 == 11  -> SURVIVES (documented equivalent shape)
  binop Add->Sub: pick(10) -> 9  != 11  -> KILLED

so the chained score must be killed=2, total=3, open_gaps=1.
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
         "--max-mutants", "5", "--log", str(log)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MUTATION SCORE: 2/3 killed" in r.stdout

    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(records) == 1
    ms = records[0]["mutation_score"]
    assert ms["killed"] == 2
    assert ms["total"] == 3
    # tiny_mod has no allowlist entries: no documented equivalents, the
    # GtE->LtE survivor must show up as an honest open gap
    assert ms["effective_total"] == 3
    assert ms["equivalents"] == 0
    assert ms["open_gaps"] == 1
    assert any("LtE" in s for s in ms["survivors"])
    assert ms["errors"] == []

    # module under mutation must be restored byte-identical after the run
    assert mod.read_text() == TINY_MOD
