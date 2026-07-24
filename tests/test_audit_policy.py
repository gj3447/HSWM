"""Negative-oracle tests for ooptdd v2.6 audit policy (R1/R2/R3).

The policy itself must be receipted: a self-audit MUST be refused, an
under-budget `upheld` MUST be refused, a break MUST always chain, and the
rotation MUST be deterministic. If these tests cannot violate the policy,
the policy is vacuous.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd.audit import audited_status
from ooptdd.audit_policy import (BASE_BUDGET, MAX_FACTOR, PolicyRefusal,
                                 calibrated_budget, load_registry,
                                 next_assignment, record_audit,
                                 register_auditor)
from ooptdd.receipt_log import append, load


def _receipt_record(rid: str, sha: str = "s" * 64, author: str | None = None) -> dict:
    rec = {"kind": "receipt", "receipt_id": rid, "receipt_sha": sha,
           "source_shas": {}, "lock_sha": "l" * 64, "lock_binding": "verified",
           "verdict": "VALID", "exit_code": 0, "status": "self-valid",
           "mutation_score": None, "attestation": None}
    if author:
        rec["author_id"] = author
    return rec


def _make(tmp_path, author: str | None = "alice"):
    log = str(tmp_path / "chain.jsonl")
    receipt = tmp_path / "receipt_x.py"
    receipt.write_text("LOCK = {'a': 'b'}\n")
    append(log, _receipt_record("receipt_x", author=author))
    return log, str(receipt)


FULL_BUDGET = dict(BASE_BUDGET)


# R1 — no-self-audit -----------------------------------------------------------

def test_self_audit_refused(tmp_path):
    log, receipt = _make(tmp_path, author="alice")
    with pytest.raises(PolicyRefusal, match="self-audit refused"):
        record_audit(receipt, log, auditor_id="alice", verdict="upheld",
                     notes="i audit myself", budget=FULL_BUDGET)
    assert audited_status(log, "receipt_x") == "self-valid"


def test_other_auditor_enforced_and_promotes(tmp_path):
    log, receipt = _make(tmp_path, author="alice")
    rec = record_audit(receipt, log, auditor_id="bob", verdict="upheld",
                       notes="no break found", budget=FULL_BUDGET)
    assert rec["policy"]["no_self_audit"] == "enforced"
    assert rec["policy"]["budget_check"] == "enforced"
    assert audited_status(log, "receipt_x") == "audited"


def test_unknown_author_degrades_honestly(tmp_path):
    log, receipt = _make(tmp_path, author=None)
    rec = record_audit(receipt, log, auditor_id="bob", verdict="upheld",
                       notes="legacy record, no author", budget=FULL_BUDGET)
    assert rec["policy"]["no_self_audit"] == "unverifiable"


# R3 — calibrated budget --------------------------------------------------------

def test_upheld_below_minimum_refused(tmp_path):
    log, receipt = _make(tmp_path)
    weak = {"mutants": 2, "counterexamples": 3, "wall_clock_min": 5}
    with pytest.raises(PolicyRefusal, match="below calibrated minimum"):
        record_audit(receipt, log, auditor_id="bob", verdict="upheld",
                     notes="ceremony", budget=weak)
    assert audited_status(log, "receipt_x") == "self-valid"


def test_broken_always_chained_even_without_budget(tmp_path):
    log, receipt = _make(tmp_path)
    rec = record_audit(receipt, log, auditor_id="bob", verdict="broken",
                       notes="counterexample: zero-norm embedding", budget=None)
    assert rec["audit_verdict"] == "broken"
    assert audited_status(log, "receipt_x") == "self-valid"


def test_break_doubles_calibrated_minimum_capped(tmp_path):
    log, receipt = _make(tmp_path)
    assert calibrated_budget(load(log), "receipt_x")["factor"] == 1
    for expected in (2, 4, 8, 8):  # cap at MAX_FACTOR
        record_audit(receipt, log, auditor_id="bob", verdict="broken",
                     notes="break", budget=None)
        assert calibrated_budget(load(log), "receipt_x")["factor"] == expected
    assert MAX_FACTOR == 8


def test_free_text_budget_chained_but_unverifiable(tmp_path):
    log, receipt = _make(tmp_path)
    rec = record_audit(receipt, log, auditor_id="bob", verdict="upheld",
                       notes="legacy text budget", budget="10 mutants, 30min")
    assert rec["policy"]["budget_check"] == "unverifiable"
    assert audited_status(log, "receipt_x") == "audited"


# R2 — rotation ---------------------------------------------------------------

def test_rotation_is_deterministic_lru(tmp_path):
    log, receipt = _make(tmp_path, author="alice")
    reg = str(tmp_path / "auditors.json")
    for aid in ("alice", "bob", "carol"):
        register_auditor(aid, "agent", reg)
    # alice (author) is ineligible; bob/carol never audited -> id order
    assert next_assignment(load(log), load_registry(reg), "receipt_x") == "bob"
    record_audit(receipt, log, auditor_id="bob", verdict="broken", notes="", budget=None,
                 registry_path=reg)
    assert next_assignment(load(log), load_registry(reg), "receipt_x") == "carol"
    doubled = {k: v * 2 for k, v in BASE_BUDGET.items()}  # bob's break escalated the minimum x2
    record_audit(receipt, log, auditor_id="carol", verdict="upheld", notes="",
                 budget=doubled, registry_path=reg)
    assert next_assignment(load(log), load_registry(reg), "receipt_x") == "bob"


def test_registry_idempotent(tmp_path):
    reg = str(tmp_path / "auditors.json")
    register_auditor("bob", "agent", reg)
    register_auditor("bob", "human", reg)  # re-register updates kind only
    from ooptdd.audit_policy import load_registry
    auditors = load_registry(reg)
    assert len(auditors) == 1 and auditors[0]["kind"] == "human"


# fail-closed passthrough --------------------------------------------------------

def test_corrupt_chain_refuses_audit(tmp_path):
    log, receipt = _make(tmp_path)
    lines = open(log, encoding="utf-8").read().splitlines()
    rec = json.loads(lines[0])
    rec["verdict"] = "INVALID"  # post-hoc tamper
    open(log, "w", encoding="utf-8").write(json.dumps(rec) + "\n")
    with pytest.raises(ValueError, match="corrupt chain"):
        record_audit(receipt, log, auditor_id="bob", verdict="upheld",
                     notes="", budget=FULL_BUDGET)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
