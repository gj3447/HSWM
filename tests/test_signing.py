"""Tests for v2.9 ed25519 audit signatures (G1 closure).

Layer 1 pins the crypto itself against the RFC 8032 test vectors (a subtly
wrong ed25519 must fail loudly); layer 2 pins the policy matrix
(verified / untrusted / absent / refused) on fixture chains.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ooptdd import signing
from ooptdd.audit_policy import (PolicyRefusal, record_audit, register_auditor,
                                 verify_signatures)
from ooptdd.receipt_log import append, verify

# --- layer 1: the crypto, pinned by RFC 8032 ---------------------------------

RFC_TEST_1 = {
    # official RFC 8032 §7.1 TEST 1 (verified against rfc-editor.org text 2026-07-28;
    # an earlier draft of this test pinned a misremembered sk — the implementation
    # was correct, the vector was not. That is exactly why vectors live here.)
    "sk": "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
    "pk": "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    "msg": "",
    "sig": ("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
}
RFC_TEST_2 = {
    "sk": "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
    "pk": "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
    "msg": "72",
    "sig": ("92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
            "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
}


def test_rfc8032_vector_1_empty_message():
    sk = bytes.fromhex(RFC_TEST_1["sk"])
    assert signing.publickey(sk).hex() == RFC_TEST_1["pk"]
    sig = signing.sign(b"", sk)
    assert sig.hex() == RFC_TEST_1["sig"]
    assert signing.verify_signature(sig, b"", bytes.fromhex(RFC_TEST_1["pk"]))


def test_rfc8032_vector_2_one_octet_message():
    sk = bytes.fromhex(RFC_TEST_2["sk"])
    assert signing.publickey(sk).hex() == RFC_TEST_2["pk"]
    msg = bytes.fromhex(RFC_TEST_2["msg"])
    sig = signing.sign(msg, sk)
    assert sig.hex() == RFC_TEST_2["sig"]
    assert signing.verify_signature(sig, msg, bytes.fromhex(RFC_TEST_2["pk"]))


def test_wrong_message_and_wrong_key_fail():
    sk, pk = signing.generate_keypair()
    sig = signing.sign(b"claim A", sk)
    assert signing.verify_signature(sig, b"claim A", pk)
    assert not signing.verify_signature(sig, b"claim B", pk)
    _sk2, pk2 = signing.generate_keypair()
    assert not signing.verify_signature(sig, b"claim A", pk2)
    assert not signing.verify_signature(b"\x00" * 64, b"claim A", pk)
    assert not signing.verify_signature(sig, b"claim A", b"\xff" * 32)


# --- layer 2: policy matrix on fixture chains --------------------------------


def _receipt_record(rid: str, sha: str) -> dict:
    return {"kind": "receipt", "receipt_id": rid, "receipt_sha": sha,
            "source_shas": {}, "lock_sha": "l" * 64, "verdict": "VALID",
            "exit_code": 0, "status": "self-valid", "mutation_score": None,
            "attestation": None}


@pytest.fixture()
def chain(tmp_path, monkeypatch):
    key_dir = tmp_path / "keys"
    monkeypatch.setenv("OOPTDD_KEY_DIR", str(key_dir))
    log = str(tmp_path / "chain.jsonl")
    registry = str(tmp_path / "auditors.json")
    receipt = tmp_path / "receipt_x.py"
    receipt.write_text("LOCK = {'a': 'b'}\n")
    append(log, _receipt_record("receipt_x", "s" * 64))
    return {"log": log, "registry": registry, "receipt": str(receipt),
            "key_dir": str(key_dir)}


BUDGET = {"mutants": 10, "counterexamples": 20, "wall_clock_min": 30}


def test_signed_audit_verified_when_registered(chain):
    info = signing.genkey("aud-1")
    register_auditor("aud-1", pubkey=info["pubkey"], registry_path=chain["registry"])
    rec = record_audit(chain["receipt"], chain["log"], "aud-1", "upheld",
                       "signed", BUDGET, registry_path=chain["registry"])
    assert rec["policy"]["signature"] == "verified"
    assert rec["signature"]["pubkey"] == info["pubkey"]
    assert signing.verify_record_signature(rec)
    # signature binds the exact chained content: record hash must still verify
    assert verify(chain["log"]) == (True, [])
    ok, lines = verify_signatures(chain["log"], chain["registry"])
    assert ok and any("sig OK — verified" in line for line in lines)


def test_unregistered_key_chains_as_untrusted(chain):
    signing.genkey("aud-2")
    rec = record_audit(chain["receipt"], chain["log"], "aud-2", "upheld",
                       "unregistered key", BUDGET, registry_path=chain["registry"])
    assert rec["policy"]["signature"] == "untrusted"
    assert signing.verify_record_signature(rec)


def test_no_key_chains_as_absent(chain):
    rec = record_audit(chain["receipt"], chain["log"], "aud-3", "upheld",
                       "no key", BUDGET, registry_path=chain["registry"])
    assert rec["policy"]["signature"] == "absent"
    assert "signature" not in rec


def test_registry_contradicting_key_refused(chain):
    signing.genkey("aud-4")
    _sk, other_pk = signing.generate_keypair()
    register_auditor("aud-4", pubkey=other_pk.hex(), registry_path=chain["registry"])
    with pytest.raises(PolicyRefusal, match="key mismatch"):
        record_audit(chain["receipt"], chain["log"], "aud-4", "upheld",
                     "impersonation-shaped", BUDGET, registry_path=chain["registry"])


def test_silent_pubkey_rotation_refused(chain):
    _sk, pk1 = signing.generate_keypair()
    _sk2, pk2 = signing.generate_keypair()
    register_auditor("aud-5", pubkey=pk1.hex(), registry_path=chain["registry"])
    with pytest.raises(ValueError, match="rotation refused"):
        register_auditor("aud-5", pubkey=pk2.hex(), registry_path=chain["registry"])
    # same pubkey re-register is idempotent
    register_auditor("aud-5", pubkey=pk1.hex(), registry_path=chain["registry"])


def test_post_hoc_tamper_breaks_signature(chain):
    info = signing.genkey("aud-6")
    register_auditor("aud-6", pubkey=info["pubkey"], registry_path=chain["registry"])
    rec = record_audit(chain["receipt"], chain["log"], "aud-6", "upheld",
                       "will be tampered", BUDGET, registry_path=chain["registry"])
    tampered = dict(rec)
    tampered["audit_notes"] = "rewritten history"
    assert not signing.verify_record_signature(tampered)


def test_genkey_refuses_overwrite(chain):
    signing.genkey("aud-7")
    with pytest.raises(ValueError, match="already exists"):
        signing.genkey("aud-7")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
