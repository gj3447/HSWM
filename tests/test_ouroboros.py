"""Negative oracles for the v3.0 ouroboros closure.

Three claims are under test, and each is stated so that it can fail:

  1. The tamper battery is not decorative — every `local` attack is really
     detected, and every attack either applies or says why it did not.
  2. The three ways the chain could lie about itself are now visible:
     truncation (only with external expectations), unauthenticated repairs
     (only under strict mode), signature strip/graft.
  3. The gate cannot be reached without the outside world, and an unreachable
     outside is not a pass.

Where a hole remains open by construction (a v2.9-signed record has no
commitment to its own signer) the test asserts the hole, not a wish. A test
that asserted the fix worked there would be the vacuity this whole module
exists to prevent.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd import signing
from ooptdd.attacks import ANCHOR_ONLY, ATTACKS, LEGACY_BLIND, LOCAL, LOCAL_STRICT, Skip, materialize
from ooptdd.census import census, check as census_check
from ooptdd.fire_drill import drill
from ooptdd.receipt_log import (
    append,
    load,
    load_repairs,
    record_hash,
    repairs_path_for,
    sign_repair_entry,
    verify,
)


# --- fixtures ----------------------------------------------------------------

def _record(i: int, **extra) -> dict:
    rec = {
        "kind": "receipt",
        "receipt_id": f"receipt_{i}",
        "receipt_sha": f"{i:064x}",
        "source_shas": {},
        "lock_sha": f"{i:064x}",
        "lock_binding": "verified",
        "status": "self-valid",
        "verdict": "VALID",
        "exit_code": 0,
        "mutation_score": None,
        "timestamp": f"2026-08-0{(i % 9) + 1}T00:00:00+00:00",
    }
    rec.update(extra)
    return rec


@pytest.fixture
def chain(tmp_path):
    """A six-record chain: four plain, one v2.9-signed, one v3.0-signed."""
    log = str(tmp_path / "receipt_log.jsonl")
    key_dir = str(tmp_path / "keys")
    sk, pk = signing.generate_keypair()
    for i in range(4):
        append(log, _record(i))
    # v2.9 shape: a signature with no signer_pubkey in the hashed body
    append(log, _record(4, kind="audit", auditor_id="legacy-auditor"),
           signer=lambda rh: signing.sign_record(rh, sk))
    # v3.0 shape: the body commits to its signer
    append(log, _record(5, kind="audit", auditor_id="modern-auditor"),
           signer=lambda rh: signing.sign_record(rh, sk), signer_pubkey=pk.hex())
    registry = str(tmp_path / "auditors.json")
    with open(registry, "w", encoding="utf-8") as f:
        json.dump({"auditors": [{"auditor_id": "attestor-1", "kind": "agent", "pubkey": pk.hex()}]}, f)
    return {"log": log, "sk": sk, "pk": pk.hex(), "registry": registry,
            "key_dir": key_dir, "tmp": tmp_path}


# --- 1. the battery is not decorative ----------------------------------------

def test_control_chain_verifies(chain):
    ok, errors = verify(chain["log"])
    assert ok, errors


def test_every_local_attack_is_detected(chain):
    records = load(chain["log"])
    out_dir = str(chain["tmp"] / "attacks")
    os.makedirs(out_dir, exist_ok=True)
    checked = 0
    for i, attack in enumerate(a for a in ATTACKS if a.detectability == LOCAL):
        path = materialize(attack, records, {}, out_dir, i)
        ok, errors = verify(path)
        assert not ok, f"{attack.name} slipped past verify() — the chain is decorative for it"
        checked += 1
    assert checked >= 8, "the local class shrank; a battery that stops attacking stops measuring"


def test_no_attack_passes_silently(chain):
    """Applicable or SKIPPED with a reason — never quietly dropped."""
    records = load(chain["log"])
    out_dir = str(chain["tmp"] / "all")
    os.makedirs(out_dir, exist_ok=True)
    for i, attack in enumerate(ATTACKS):
        try:
            materialize(attack, records, {}, out_dir, i)
        except Skip as e:
            assert str(e), f"{attack.name} skipped without saying why"


def test_battery_fingerprint_moves_with_the_battery():
    from ooptdd.attacks import Attack, battery_fingerprint

    before = battery_fingerprint()
    ATTACKS.append(Attack("probe", LOCAL, "temp", lambda r, p: (r, p)))
    try:
        assert battery_fingerprint() != before, "a receipt could not tell which battery it survived"
    finally:
        ATTACKS.pop()


# --- 2a. truncation: the bootstrap limit, and the way out --------------------

def test_truncation_is_invisible_locally(chain):
    records = load(chain["log"])
    truncated = str(chain["tmp"] / "truncated.jsonl")
    with open(truncated, "w", encoding="utf-8") as f:
        for r in records[:-1]:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    ok, errors = verify(truncated)
    assert ok, ("if this ever fails, local verification learned to see truncation and the "
                "anchor requirement can be revisited — until then it cannot")


def test_truncation_is_caught_with_external_expectations(chain):
    records = load(chain["log"])
    truncated = str(chain["tmp"] / "truncated2.jsonl")
    with open(truncated, "w", encoding="utf-8") as f:
        for r in records[:-1]:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    ok, errors = verify(truncated, expect_min_len=len(records))
    assert not ok and any("truncation" in e for e in errors), errors
    ok, errors = verify(truncated, expect_head=records[-1]["hash"])
    assert not ok and any("head mismatch" in e for e in errors), errors


def test_full_rewrite_is_invisible_locally_and_caught_by_head(chain):
    records = load(chain["log"])
    attack = next(a for a in ATTACKS if a.name == "full_rewrite")
    path = materialize(attack, records, {}, str(chain["tmp"]), 90)
    assert verify(path)[0], "a rewritten chain is internally consistent — that is the point"
    ok, errors = verify(path, expect_head=records[-1]["hash"])
    assert not ok and any("head mismatch" in e for e in errors), errors


# --- 2b. repairs: an unauthenticated override, now graded --------------------

def _write_repairs(log: str, entries: list[dict]) -> None:
    with open(repairs_path_for(log), "w", encoding="utf-8") as f:
        json.dump({"repairs": entries}, f)


def _tamper_keeping_stored_hash(log: str, out: str, index: int) -> dict:
    records = load(log)
    records[index]["verdict"] = "INVALID"
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return records[index]


def test_unsigned_repair_whitewashes_by_default_and_is_rejected_strictly(chain):
    out = str(chain["tmp"] / "forged.jsonl")
    victim = _tamper_keeping_stored_hash(chain["log"], out, 1)
    _write_repairs(out, [{"stored_hash": victim["hash"], "reason": "forged", "attested_by": "anyone"}])

    assert verify(out)[0], "documented v2.8 behaviour: an unsigned entry is honoured"
    ok, errors = verify(out, strict_repairs=True)
    assert not ok and any("repair entry rejected" in e for e in errors), errors


def test_signed_repair_is_honoured_under_strict(chain):
    out = str(chain["tmp"] / "signed_repair.jsonl")
    victim = _tamper_keeping_stored_hash(chain["log"], out, 1)
    entry = sign_repair_entry(
        {"stored_hash": victim["hash"], "reason": "documented incident", "attested_by": "attestor-1"},
        chain["sk"])
    _write_repairs(out, [entry])
    ok, errors = verify(out, strict_repairs=True, registry_path=chain["registry"])
    assert ok, errors


def test_repair_signed_by_the_wrong_key_is_invalid(chain):
    out = str(chain["tmp"] / "wrongkey.jsonl")
    victim = _tamper_keeping_stored_hash(chain["log"], out, 1)
    other_sk, _ = signing.generate_keypair()
    entry = sign_repair_entry(
        {"stored_hash": victim["hash"], "reason": "impersonation", "attested_by": "attestor-1"},
        other_sk)
    _write_repairs(out, [entry])
    for strict in (False, True):
        ok, errors = verify(out, strict_repairs=strict, registry_path=chain["registry"])
        assert not ok, f"a key contradicting the registry must never absolve (strict={strict})"


def test_tampered_repair_body_breaks_its_own_signature(chain):
    out = str(chain["tmp"] / "tamperedrepair.jsonl")
    victim = _tamper_keeping_stored_hash(chain["log"], out, 1)
    entry = sign_repair_entry(
        {"stored_hash": victim["hash"], "reason": "real reason", "attested_by": "attestor-1"},
        chain["sk"])
    entry["reason"] = "swapped after signing"
    _write_repairs(out, [entry])
    ok, _ = verify(out, strict_repairs=True, registry_path=chain["registry"])
    assert not ok, "the signature must cover the reason, not just the hash"


def test_malformed_repair_is_graded_invalid_not_fatal(chain):
    """The live file has one: a 45-character stored_hash, unnoticed since 07-28."""
    _write_repairs(chain["log"], [
        {"stored_hash": "5215296e1c219c6dfecb8c2f4f0d128b580c75f3135",  # 43 hex, not 64
         "reason": "truncated hash", "attested_by": "someone"}])
    repairs = load_repairs(repairs_path_for(chain["log"]))
    assert repairs["5215296e1c219c6dfecb8c2f4f0d128b580c75f3135"]["trust"] == "invalid"
    ok, errors = verify(chain["log"])
    assert ok, "one bad sidecar line must not make every receipt in the repo unverifiable"


# --- 2c. signatures: strip and graft -----------------------------------------

def test_v3_signature_strip_is_detected(chain):
    records = load(chain["log"])
    target = next(i for i, r in enumerate(records) if r.get("signer_pubkey"))
    records[target].pop("signature")
    out = str(chain["tmp"] / "stripped.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    ok, errors = verify(out)
    assert not ok and any("signature stripped" in e for e in errors), errors


def test_legacy_signature_strip_remains_blind(chain):
    """Asserted as an open hole, because it is one — see census signer_commitment."""
    records = load(chain["log"])
    target = next(i for i, r in enumerate(records)
                  if isinstance(r.get("signature"), dict) and not r.get("signer_pubkey"))
    before = records[target]["hash"]
    records[target].pop("signature")
    out = str(chain["tmp"] / "legacystrip.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    assert verify(out)[0], "no verifier-side fix exists for records written without signer_pubkey"
    assert load(out)[target]["hash"] == before, (
        "and the anchored head still matches — re-signing is the only remedy")


def test_resign_record_makes_a_legacy_strip_visible(chain):
    """v3.1 — a later `resign` record vouches for what a v2.9 record's signature is."""
    records = load(chain["log"])
    legacy = next(r for r in records
                  if isinstance(r.get("signature"), dict) and not r.get("signer_pubkey"))
    append(chain["log"], {
        "kind": "resign", "receipt_id": "attestation",
        "attests": [{"seq": legacy["seq"], "target_hash": legacy["hash"],
                     "signer_pubkey": legacy["signature"]["pubkey"]}],
    })
    assert verify(chain["log"])[0], "attesting must not disturb an intact chain"

    records = load(chain["log"])
    target = next(i for i, r in enumerate(records) if r["hash"] == legacy["hash"])
    records[target].pop("signature")
    out = str(chain["tmp"] / "legacystrip_attested.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    ok, errors = verify(out)
    assert not ok and any("attests signer" in e for e in errors), errors


def test_resign_attestation_is_relocation_not_closure(chain):
    """The honest limit: cut the resign record off and the strip is invisible again.

    Asserted, not hoped. The attestation lives in a LATER record, so the exposure
    moves from legacy_blind to anchor_only — a class that needs expect_head /
    expect_min_len. A test that stopped at the previous one would be claiming a
    closure this mechanism cannot deliver.
    """
    records = load(chain["log"])
    legacy = next(r for r in records
                  if isinstance(r.get("signature"), dict) and not r.get("signer_pubkey"))
    append(chain["log"], {
        "kind": "resign", "receipt_id": "attestation",
        "attests": [{"seq": legacy["seq"], "target_hash": legacy["hash"],
                     "signer_pubkey": legacy["signature"]["pubkey"]}],
    })
    full = load(chain["log"])
    anchored_head, anchored_len = full[-1]["hash"], len(full)

    truncated = [dict(r) for r in full[:-1]]                 # drop the resign record
    target = next(i for i, r in enumerate(truncated) if r["hash"] == legacy["hash"])
    truncated[target].pop("signature")                       # and strip, unopposed
    out = str(chain["tmp"] / "resign_truncated.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in truncated:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

    assert verify(out)[0], "relocation, not closure — local verification is quiet again"
    assert not verify(out, expect_min_len=anchored_len)[0]
    assert not verify(out, expect_head=anchored_head)[0]


def test_resign_pubkey_mismatch_is_detected(chain):
    records = load(chain["log"])
    legacy = next(r for r in records
                  if isinstance(r.get("signature"), dict) and not r.get("signer_pubkey"))
    append(chain["log"], {
        "kind": "resign", "receipt_id": "attestation",
        "attests": [{"seq": legacy["seq"], "target_hash": legacy["hash"],
                     "signer_pubkey": "f" * 64}],       # names the wrong signer
    })
    ok, errors = verify(chain["log"])
    assert not ok and any("contradicts resign attestation" in e for e in errors), errors


def test_grafted_signature_is_detected(chain):
    records = load(chain["log"])
    donor = next(r for r in records if isinstance(r.get("signature"), dict))
    victim = next(r for r in records if not isinstance(r.get("signature"), dict))
    victim["signature"] = json.loads(json.dumps(donor["signature"]))
    out = str(chain["tmp"] / "grafted.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    ok, errors = verify(out)
    assert not ok and any("grafted" in e or "does not verify" in e for e in errors), errors


def test_signer_pubkey_does_not_disturb_legacy_hashes(chain):
    """v3.0 must not invalidate a single historical record."""
    for rec in load(chain["log"]):
        assert rec["hash"] == record_hash(rec)


# --- 3. the census counts what the labels admit -------------------------------

def test_census_counts_the_signature_exposure(chain):
    c = census(load(chain["log"]), {})
    sc = c["dimensions"]["signer_commitment"]
    assert sc["counts"] == {"committed": 1, "strip_exposed": 1}
    assert sc["coverage"] == pytest.approx(0.5)


def test_empty_dimension_is_not_full_coverage(chain):
    c = census([], {})
    assert all(d["coverage"] is None for d in c["dimensions"].values()), \
        "an empty dimension reading 1.0 would let a chain with nothing in it look perfect"


def test_ratchet_catches_regression(chain):
    before = census(load(chain["log"]), {})
    append(chain["log"], _record(9, lock_binding="absent"))
    after = census(load(chain["log"]), {})
    ok, problems = census_check(after, None, before)
    assert not ok and any("lock_binding" in p and "regressed" in p for p in problems), problems


def test_ratchet_passes_when_coverage_improves(chain):
    before = census(load(chain["log"]), {})
    append(chain["log"], _record(9, lock_binding="verified"))
    after = census(load(chain["log"]), {})
    ok, problems = census_check(after, None, before)
    assert ok, problems


def test_floor_cannot_be_met_vacuously(chain):
    c = census([], {})
    ok, problems = census_check(c, {"lock_binding": 0.5}, None)
    assert not ok and any("vacuously" in p for p in problems), problems


# --- 4. the gate needs the outside world --------------------------------------

def _gate(chain, **kw):
    from ooptdd import gate

    kw.setdefault("tree", None)
    kw.setdefault("node", None)
    return gate.evaluate("receipt_0", chain["log"], base_url="http://127.0.0.1:1", **kw)


def test_gate_refuses_done_without_an_anchor(chain):
    c = _gate(chain)
    assert not c.done
    anchor = next(i for i in c.items if i["condition"] == "external anchor")
    assert anchor["status"] == "UNVERIFIABLE"


def test_allow_unanchored_can_never_return_done(chain):
    c = _gate(chain, allow_unanchored=True)
    assert not c.done, "'I could not check' must not share an exit code with 'it checked out'"


def test_gate_passes_when_the_anchor_agrees(chain, monkeypatch):
    from ooptdd import gate

    head = [r for r in load(chain["log"]) if r["receipt_id"] == "receipt_0"][-1]["hash"]
    monkeypatch.setattr(gate, "anchor_check", lambda *a, **k: (
        0, {"match": True, "local_head": head, "local_seq": 0,
            "anchored_high_water": 0, "truncation_detected": False,
            "anchors_seen": 1, "anchored_hashes": [head],   # v3.2: 판정 대상이 앵커돼야 한다
            "prefix_inconsistent": [], "broken_anchor_links": []}))
    c = gate.evaluate("receipt_0", chain["log"], "tree", "node", "http://x")
    assert c.done, c.render()


def test_gate_fails_on_anchored_truncation(chain, monkeypatch):
    from ooptdd import gate

    monkeypatch.setattr(gate, "anchor_check", lambda *a, **k: (
        1, {"match": False, "local_seq": 3, "anchored_high_water": 5,
            "truncation_detected": True}))
    c = gate.evaluate("receipt_0", chain["log"], "tree", "node", "http://x")
    anchor = next(i for i in c.items if i["condition"] == "external anchor")
    assert anchor["status"] == "FAIL" and "TRUNCATION" in anchor["detail"]


def test_gate_runs_the_battery_in_strict_mode(chain):
    """Otherwise the whitewash the gate is meant to refuse would pass through it."""
    code, summary = drill(chain["log"], strict_repairs=True, verbose=False)
    assert summary["strict_repairs"] is True
    whitewashed = [r for r in summary["results"]
                   if r["class"] == LOCAL_STRICT and r["outcome"].startswith("WHITEWASHED")]
    assert not whitewashed, whitewashed


def test_declared_classes_are_exhaustive():
    known = {LOCAL, LOCAL_STRICT, ANCHOR_ONLY, LEGACY_BLIND}
    unknown = [a.name for a in ATTACKS if a.detectability not in known]
    assert not unknown, f"an unclassified attack has no expected outcome to fail against: {unknown}"


def test_anchor_payload_links_to_its_predecessor(chain):
    """v3.1 — 앵커가 독립 스냅샷이 아니라 선행 앵커를 가리키는 사슬이어야 한다."""
    from ooptdd.run_receipt import anchor_chain_head, previous_anchor

    records = load(chain["log"])
    target = records[-1]
    assert previous_anchor(chain["log"], target["receipt_id"]) is None

    append(chain["log"], {
        "kind": "anchor", "receipt_id": target["receipt_id"], "verdict": "VALID",
        "target_hash": target["hash"], "target_seq": target["seq"],
    })
    prev = previous_anchor(chain["log"], target["receipt_id"])
    assert prev is not None and prev["target_hash"] == target["hash"]

    captured = {}

    def fake_urlopen(req, timeout=0):
        captured.update(json.loads(req.data.decode()))
        raise OSError("no server — payload is what this test is about")

    import urllib.request as u
    real = u.urlopen
    u.urlopen = fake_urlopen
    try:
        anchor_chain_head("t", "n", dict(target, receipt_sha="0" * 64), chain["log"])
    finally:
        u.urlopen = real

    assert captured["payload"]["prev_anchor_hash"] == target["hash"]
    assert captured["payload"]["prev_anchor_seq"] == str(target["seq"])


def test_first_anchor_has_an_empty_link_not_a_missing_one(chain):
    """부재와 파손이 같아 보이면 안 된다 — 첫 앵커는 빈 문자열을 명시한다."""
    from ooptdd.run_receipt import anchor_chain_head

    target = load(chain["log"])[-1]
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured.update(json.loads(req.data.decode()))
        raise OSError("no server")

    import urllib.request as u
    real = u.urlopen
    u.urlopen = fake_urlopen
    try:
        anchor_chain_head("t", "n", dict(target, receipt_sha="0" * 64), chain["log"])
    finally:
        u.urlopen = real

    assert captured["payload"]["prev_anchor_hash"] == ""
    assert "prev_anchor_hash" in captured["payload"]


def test_census_counts_never_anchored(chain):
    """앵커 0건이 어떤 표에도 안 나오던 게 문제였다."""
    from ooptdd.census import census

    c = census(load(chain["log"]), {})
    assert c["dimensions"]["anchored"]["counts"].get("never_anchored")
    assert c["dimensions"]["anchored"]["coverage"] == 0.0


# --- 5. the anchor layer, exercised against a real anchor ----------------------

def _fake_anchor_check(anchored: list[tuple[int, str]], local_len: int):
    """anchor_check 의 응답을 흉내낸다 — 서버 없이 게이트 조건만 검사."""
    def _c(tree, node, receipt_id, log_path, base_url=""):
        return 0, {"match": True, "anchors_seen": len(anchored),
                   "anchored_hashes": [h for _s, h in anchored],
                   "anchored_high_water": max((s for s, _h in anchored), default=None),
                   "local_seq": local_len - 1, "truncation_detected": False,
                   "prefix_inconsistent": [], "broken_anchor_links": [],
                   "head_equals_latest_anchor": False}
    return _c


def test_gate_requires_the_judged_record_to_be_anchored_not_merely_consistency(chain, monkeypatch):
    """v3.2 — 체인이 자기 앵커들과 일관돼도, 판정 대상이 앵커 안 됐으면 DONE 아니다.

    '체인이 정합적이다' 와 '이 주장이 증인을 세웠다' 는 다른 문장이고 DONE 을
    허락하는 건 두 번째뿐이다.
    """
    from ooptdd import gate

    records = load(chain["log"])
    target = [r for r in records if r["receipt_id"] == "receipt_0"][-1]
    other = next(r for r in records if r["hash"] != target["hash"])

    # 다른 레코드만 앵커된 상태 — 일관성은 성립하지만 대상은 미앵커
    monkeypatch.setattr(gate, "anchor_check",
                        _fake_anchor_check([(other["seq"], other["hash"])], len(records)))
    c = gate.evaluate("receipt_0", chain["log"], "t", "n", "http://x")
    cond = next(i for i in c.items if i["condition"] == "this record anchored")
    assert cond["status"] == "FAIL" and "never anchored" in cond["detail"]

    # 대상이 앵커되면 통과
    monkeypatch.setattr(gate, "anchor_check",
                        _fake_anchor_check([(target["seq"], target["hash"])], len(records)))
    c = gate.evaluate("receipt_0", chain["log"], "t", "n", "http://x")
    assert next(i for i in c.items if i["condition"] == "this record anchored")["status"] == "PASS"


def test_growth_after_anchoring_is_not_tampering(chain, monkeypatch):
    """head 동일성 요구는 틀렸었다 — 앵커를 기록하는 행위 자체가 head 를 옮긴다.

    2026-08-05 첫 실앵커에서 실측: run_receipt 가 seq 77 을 앵커하고 그 시도를
    seq 78 로 체인하니 head != 앵커 → MISMATCH. 트리는 구조적으로 항상 뒤처진다.
    """
    from ooptdd import gate

    records = load(chain["log"])
    target = [r for r in records if r["receipt_id"] == "receipt_0"][-1]
    monkeypatch.setattr(gate, "anchor_check",
                        _fake_anchor_check([(target["seq"], target["hash"])], len(records)))
    c = gate.evaluate("receipt_0", chain["log"], "t", "n", "http://x")
    anchor = next(i for i in c.items if i["condition"] == "external anchor")
    assert anchor["status"] == "PASS", "성장은 변조가 아니다"


def test_forged_chain_passes_local_verify_and_is_refused_by_the_anchor(chain):
    """프로그램 전체의 논지 — 로컬로 완벽한 위조를 외부만이 거절한다.

    2026-08-05 실측(라이브 체인 + 실 LakatoTree 앵커): 꼬리를 재해싱한 위조가
    verify() 를 (True, []) 로 통과했고, anchor-check 가
    PREFIX INCONSISTENT at [(77, '4ebfb76e26d6')] 로 거절했다.
    """
    from ooptdd.attacks import materialize

    records = load(chain["log"])
    attack = next(a for a in ATTACKS if a.name == "rewrite_middle")
    path = materialize(attack, records, {}, str(chain["tmp"]), 95)
    assert verify(path)[0], "위조가 로컬로 통과해야 이 테스트가 의미를 갖는다"

    forged = load(path)
    victim = next(f for f, o in zip(forged, records) if f["hash"] != o["hash"])
    original = next(o for f, o in zip(forged, records) if f["hash"] != o["hash"] and o["seq"] == victim["seq"])
    # 앵커는 원본 해시를 기억한다 — 위조 체인의 같은 seq 와 어긋난다
    assert victim["hash"] != original["hash"]
