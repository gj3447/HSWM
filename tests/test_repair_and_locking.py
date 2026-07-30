"""Tests for v2.8 chain hardening: repairs skiplist + append() flocking.

Motivation (2026-07-28, see ERRATA in OOPTDD_CHAIN_INCIDENT_2026-07-28.md):
(a) writers that bypass append() can leave bodies that no longer match their
stored hashes (linkage intact) — the repairs file documents such records
without rewriting history; (b) verify→write was not atomic, so racing
harness runs could interleave — the flock closes (b). The 2026-07-28 chain
"incident" itself was later errata'd as a misdiagnosis (corrupted LOCAL
transcription copy, canonical always clean); the two hardening verbs stand.
"""
from __future__ import annotations

import json
import threading

import pytest

from ooptdd.receipt_log import append, load_repairs, verify


def _record(rid: str, seq_salt: str = "x") -> dict:
    return {"kind": "receipt", "receipt_id": rid, "receipt_sha": seq_salt * 64,
            "source_shas": {}, "lock_sha": "l" * 64, "verdict": "VALID",
            "exit_code": 0, "status": "self-valid", "mutation_score": None,
            "attestation": None}


def test_repairs_skiplist_roundtrip(tmp_path):
    log = str(tmp_path / "chain.jsonl")
    append(log, _record("r0", "a"))
    append(log, _record("r1", "b"))
    append(log, _record("r2", "c"))
    assert verify(log) == (True, [])

    # tamper the middle record's body (keep stored hash and linkage intact)
    lines = open(log).read().splitlines()
    rec = json.loads(lines[1])
    rec["verdict"] = "INVALID"  # post-hoc edit
    lines[1] = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    open(log, "w").write("\n".join(lines) + "\n")

    ok, errs = verify(log)
    assert not ok and any("hash mismatch" in e for e in errs)

    # a repair entry with the WRONG stored_hash must not apply
    repairs = tmp_path / "chain.jsonl.repairs.json"
    repairs.write_text(json.dumps({"repairs": [
        {"seq": 1, "stored_hash": "0" * 64, "reason": "wrong hash", "attested_by": "tester"}]}))
    ok, errs = verify(log)
    assert not ok, "repair with wrong stored_hash must not whitewash"

    # the correct entry restores verification — history is documented, not rewritten
    repairs.write_text(json.dumps({"repairs": [
        {"seq": 1, "receipt_id": "r1", "stored_hash": rec["hash"],
         "reason": "test repair", "attested_by": "tester"}]}))
    assert verify(log) == (True, [])

    # and the chain accepts new records again
    append(log, _record("r3", "d"))
    assert verify(log) == (True, [])

    # a SECOND unlisted tamper is still detected
    lines = open(log).read().splitlines()
    rec3 = json.loads(lines[3])
    rec3["verdict"] = "INVALID"
    lines[3] = json.dumps(rec3, ensure_ascii=False, sort_keys=True)
    open(log, "w").write("\n".join(lines) + "\n")
    ok, errs = verify(log)
    assert not ok and any("seq=3" in e for e in errs)


def test_repairs_file_requires_reason_and_attestor(tmp_path):
    bad = tmp_path / "rep.json"
    bad.write_text(json.dumps({"repairs": [{"stored_hash": "x" * 64}]}))
    with pytest.raises(ValueError, match="stored_hash, reason, attested_by"):
        load_repairs(str(bad))


def test_concurrent_appends_never_corrupt(tmp_path):
    log = str(tmp_path / "chain.jsonl")
    n_threads, n_appends = 8, 5
    errors: list[BaseException] = []

    def worker(tid: int) -> None:
        try:
            for i in range(n_appends):
                append(log, _record(f"r_t{tid}_{i}", "abcdefgh"[tid] * 8))
        except BaseException as e:  # noqa: BLE001 - collected for assertion
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent appends raised: {errors!r}"
    ok, errs = verify(log)
    assert ok, f"chain corrupt after concurrent appends: {errs}"
    records = [json.loads(line) for line in open(log).read().splitlines()]
    assert len(records) == n_threads * n_appends
    assert [r["seq"] for r in records] == list(range(n_threads * n_appends))
