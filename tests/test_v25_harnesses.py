"""Tests for v2.5 harnesses: allowlist (R3) and audit status transitions."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd.allowlist import is_equivalent, load_allowlist
from ooptdd.audit import audited_status, record
from ooptdd.mutate import MutationSite
from ooptdd.receipt_log import append


def test_allowlist_refuses_reasonless_entry(tmp_path):
    p = tmp_path / "allow.json"
    p.write_text(json.dumps({"mod.py": [{"kind": "binop", "detail": "Add->Sub", "reason": ""}]}))
    with pytest.raises(ValueError, match="no reason"):
        load_allowlist(str(p))


def test_allowlist_matches_kind_detail_and_position(tmp_path):
    p = tmp_path / "allow.json"
    p.write_text(json.dumps({"mod.py": [
        {"kind": "compare", "detail": "GtE->Gt", "lineno": 10, "col": 4, "reason": "boundary"}]}))
    entries = load_allowlist(str(p))["mod.py"]
    hit = MutationSite("cmp@10.4.0", 10, "compare", "GtE->Gt", 4)
    miss = MutationSite("cmp@11.4.0", 11, "compare", "GtE->Gt", 4)
    assert is_equivalent(hit, entries) == "boundary"
    assert is_equivalent(miss, entries) is None


def _receipt_record(rid: str, sha: str) -> dict:
    return {"kind": "receipt", "receipt_id": rid, "receipt_sha": sha,
            "source_shas": {}, "lock_sha": "l" * 64, "verdict": "VALID",
            "exit_code": 0, "status": "self-valid", "mutation_score": None,
            "attestation": None}


def test_audit_status_transitions(tmp_path):
    log = str(tmp_path / "chain.jsonl")
    receipt = tmp_path / "receipt_x.py"
    receipt.write_text("LOCK = {'a': 'b'}\n")
    append(log, _receipt_record("receipt_x", "s" * 64))
    assert audited_status(log, "receipt_x") == "self-valid"
    record(str(receipt), log, auditor_id="other-model", verdict="upheld",
           notes="no break", budget="10 mutants")
    assert audited_status(log, "receipt_x") == "audited"
    # an edit (new receipt record with a different sha) reverts audited
    append(log, _receipt_record("receipt_x", "t" * 64))
    assert audited_status(log, "receipt_x") == "self-valid"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
