"""Tests for v2.10 measured-value capture (G3 closure).

The chain pinned verdicts but not the NUMBERS behind them. run_receipt now
harvests the receipt's last `MEASURED {json}` stdout line into the chained
record; absence is recorded honestly (None + flagged), never guessed.
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

from ooptdd.run_receipt import parse_measured


def test_parse_measured_last_good_line_wins():
    out = (
        "noise\n"
        'MEASURED {"a": {"value": 1.0, "unit": "x"}}\n'
        "more noise\n"
        'MEASURED {"b": {"value": 2.0, "unit": "y"}}\n'
    )
    payload, saw = parse_measured(out)
    assert saw and payload == {"b": {"value": 2.0, "unit": "y"}}


def test_parse_measured_malformed_trailing_keeps_previous_good():
    out = (
        'MEASURED {"a": {"value": 1.0}}\n'
        "MEASURED {not json}\n"
    )
    payload, saw = parse_measured(out)
    assert saw and payload == {"a": {"value": 1.0}}


def test_parse_measured_absent_and_broken():
    assert parse_measured("no lines here") == (None, False)
    assert parse_measured("MEASURED {broken") == (None, True)


RECEIPT_WITH = '''\
import json
LOCK = {"F": "1 == 1"}
LOCK_CHECKS = {"F": "f_ok"}
def main():
    f_ok = 1 == 1
    ok = f_ok
    print("MEASURED " + json.dumps({"gain": {"value": 0.1004, "unit": "nDCG", "gate": "F4", "threshold": ">=+0.03"}}))
    print("RECEIPT:", "VALID" if ok else "INVALID")
    return 0 if ok else 1
if __name__ == "__main__":
    raise SystemExit(main())
'''

RECEIPT_WITHOUT = RECEIPT_WITH.replace(
    '    print("MEASURED " + json.dumps({"gain": {"value": 0.1004, "unit": "nDCG", "gate": "F4", "threshold": ">=+0.03"}}))\n', "")


def _run_harness(tmp_path, source: str):
    receipt = tmp_path / "tiny_receipt.py"
    receipt.write_text(source)
    log = tmp_path / "chain.jsonl"
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    r = subprocess.run(
        [sys.executable, "-m", "ooptdd.run_receipt", str(receipt), "--log", str(log)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    records = [json.loads(line) for line in log.read_text().splitlines()]
    return r, records[0]


def test_measured_values_chained(tmp_path):
    r, rec = _run_harness(tmp_path, RECEIPT_WITH)
    assert "measured: 1 metrics captured" in r.stdout
    assert rec["measured"]["gain"]["value"] == 0.1004
    assert rec["measured"]["gain"]["unit"] == "nDCG"
    assert rec["measured"]["gain"]["threshold"] == ">=+0.03"


def test_measured_absent_is_honest_none(tmp_path):
    r, rec = _run_harness(tmp_path, RECEIPT_WITHOUT)
    assert "measured: absent" in r.stdout
    assert rec["measured"] is None


if __name__ == "__main__":
    raise SystemExit(__import__("pytest").main([__file__, "-q"]))
