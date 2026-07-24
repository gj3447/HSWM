"""Negative-oracle tests for the ooptdd v2 receipt chain.

The chain mechanism itself must be receipted: tampering with a past verdict,
deleting a record, and reordering must ALL be detected by verify(), and
append() must refuse a corrupt chain. If these tests cannot break the chain,
the chain is vacuous.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd.receipt_log import GENESIS_PREV, append, load, verify


def _rec(rid: str, verdict: str = "VALID") -> dict:
    return {
        "kind": "receipt",
        "receipt_id": rid,
        "receipt_sha": "a" * 64,
        "source_shas": {},
        "lock_sha": "b" * 64,
        "verdict": verdict,
        "exit_code": 0 if verdict == "VALID" else 1,
        "status": "self-valid",
        "mutation_score": None,
        "attestation": None,
    }


def test_roundtrip_genesis_and_links(tmp_path):
    log = str(tmp_path / "chain.jsonl")
    r0 = append(log, _rec("r0"))
    r1 = append(log, _rec("r1"))
    assert r0["seq"] == 0 and r0["prev_hash"] == GENESIS_PREV
    assert r1["seq"] == 1 and r1["prev_hash"] == r0["hash"]
    ok, errors = verify(log)
    assert ok, errors


def test_negative_oracle_tampered_verdict_detected(tmp_path):
    log = str(tmp_path / "chain.jsonl")
    append(log, _rec("r0"))
    append(log, _rec("r1"))
    records = load(log)
    records[0]["verdict"] = "VALID" if records[0]["verdict"] != "VALID" else "INVALID"
    with open(log, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    ok, errors = verify(log)
    assert not ok, "tampered verdict must break the chain"
    assert any("hash mismatch" in e for e in errors)


def test_negative_oracle_deletion_detected(tmp_path):
    log = str(tmp_path / "chain.jsonl")
    for i in range(3):
        append(log, _rec(f"r{i}"))
    records = load(log)
    del records[1]
    with open(log, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    ok, errors = verify(log)
    assert not ok, "deleted record must break the chain"
    assert any("prev_hash" in e or "seq" in e for e in errors)


def test_append_refuses_corrupt_chain(tmp_path):
    log = str(tmp_path / "chain.jsonl")
    append(log, _rec("r0"))
    records = load(log)
    records[0]["lock_sha"] = "c" * 64  # post-hoc lock edit
    with open(log, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="corrupt chain"):
        append(log, _rec("r1"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
