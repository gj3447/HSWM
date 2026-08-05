"""ooptdd v3.0 — machine-generated tamper battery for the receipt chain.

mutate.py exists because hand-picked negative oracles are vacuous: an author
who chooses the faults measures their own imagination. Until v3.0 the chain's
own tamper-evidence claim was defended by exactly two hand-picked faults
(flip a verdict, delete a record) — the very thing mutate.py was written to
stop. This module applies mutate.py's philosophy to receipt_log itself.

Every attack declares what SHOULD happen, and the drill fails on any
disagreement. Three detectability classes, and the classes are the finding:

  local        verify() must catch this with no outside help. A MISS means the
               chain is decorative for that fault class.
  local_strict verify() catches it only with strict_repairs=True. These are
               faults the v2.8 skiplist could whitewash.
  anchor_only  verify() provably CANNOT catch this — the information needed is
               not in the file. Truncation and full rewrite are the canonical
               pair. A local pass here is not reassurance, it is the shape of
               the bootstrap problem, and it is why ooptdd.gate refuses to call
               anything DONE without a cross-machine anchor.

An attack that cannot be built against the chain at hand (too few records, no
signed record to strip) reports SKIPPED. It never reports success — a battery
that silently drops inapplicable cases would report a coverage it does not have.
"""
from __future__ import annotations

import json
import os
from typing import Callable

from ooptdd.receipt_log import (
    GENESIS_PREV,
    canonical,
    record_hash,
    repairs_path_for,
    sha256_hex,
)

LOCAL = "local"
LOCAL_STRICT = "local_strict"
ANCHOR_ONLY = "anchor_only"
LEGACY_BLIND = "legacy_blind"


class Skip(Exception):
    """This attack does not apply to this chain — reported, never passed over."""


class Attack:
    """One tamper transform plus the detection claim it is meant to test."""

    def __init__(self, name: str, detectability: str, description: str,
                 build: Callable[[list[dict], dict], tuple[list[dict], dict]]):
        self.name = name
        self.detectability = detectability
        self.description = description
        self._build = build

    def apply(self, records: list[dict], repairs: dict) -> tuple[list[dict], dict]:
        """Return (tampered_records, repairs_file_content) — never mutates inputs."""
        return self._build([json.loads(json.dumps(r)) for r in records],
                           json.loads(json.dumps(repairs)))


# --- helpers -----------------------------------------------------------------

def _rehash_from(records: list[dict], start: int) -> list[dict]:
    """Recompute seq/prev_hash/hash from `start` on — the forger's own tool.

    This is what separates a lazy edit from a real rewrite, and it is exactly
    the capability local verification has no defence against.
    """
    prev = records[start - 1]["hash"] if start > 0 else GENESIS_PREV
    for i in range(start, len(records)):
        records[i]["seq"] = i
        records[i]["prev_hash"] = prev
        records[i].pop("signature", None)      # a rewriter cannot forge signatures…
        records[i].pop("signer_pubkey", None)  # …so it drops the claim to have one
        records[i]["hash"] = record_hash(records[i])
        prev = records[i]["hash"]
    return records


def _flip_verdict(rec: dict) -> None:
    rec["verdict"] = "INVALID" if rec.get("verdict") == "VALID" else "VALID"


def _mid(records: list[dict]) -> int:
    return len(records) // 2


# --- attack builders ---------------------------------------------------------

def _verdict_flip(records, repairs):
    _flip_verdict(records[0])
    return records, repairs


def _field_edit(records, repairs):
    i = _mid(records)
    records[i]["status"] = "audited"  # promote a self-valid record by hand
    return records, repairs


def _drop_field(records, repairs):
    i = _mid(records)
    for key in ("lock_binding", "status", "verdict"):
        if key in records[i]:
            records[i].pop(key)
            return records, repairs
    raise Skip("no droppable field on the middle record")


def _middle_delete(records, repairs):
    if len(records) < 3:
        raise Skip("needs >= 3 records")
    i = _mid(records)
    return records[:i] + records[i + 1:], repairs


def _reorder_swap(records, repairs):
    if len(records) < 4:
        raise Skip("needs >= 4 records")
    i = _mid(records)
    records[i], records[i + 1] = records[i + 1], records[i]
    return records, repairs


def _replay_append(records, repairs):
    return records + [json.loads(json.dumps(records[-1]))], repairs


def _genesis_forge(records, repairs):
    """Cut the head off and re-root the survivor at genesis, without rehashing."""
    if len(records) < 2:
        raise Skip("needs >= 2 records")
    rest = records[1:]
    rest[0]["prev_hash"] = GENESIS_PREV
    return rest, repairs


def _backdate(records, repairs):
    i = _mid(records)
    if "timestamp" not in records[i]:
        raise Skip("record carries no timestamp")
    records[i]["timestamp"] = "2020-01-01T00:00:00+00:00"
    return records, repairs


def _tail_truncate(records, repairs):
    """Drop the last record. The remainder is a flawless chain — that is the point.

    This is the cheapest possible cover-up (run a receipt, dislike the verdict,
    delete the line) and the file contains nothing that could reveal it.
    """
    if len(records) < 2:
        raise Skip("needs >= 2 records")
    return records[:-1], repairs


def _full_rewrite(records, repairs):
    """Edit the first record, then recompute the entire tail. Chain verifies."""
    _flip_verdict(records[0])
    return _rehash_from(records, 0), repairs


def _rewrite_middle(records, repairs):
    """Same capability applied deeper in — the prefix is untouched and valid."""
    if len(records) < 3:
        raise Skip("needs >= 3 records")
    i = _mid(records)
    _flip_verdict(records[i])
    return _rehash_from(records, i), repairs


def _repairs_forgery(records, repairs):
    """Tamper a body, keep its stored hash, and write yourself an absolution.

    v2.8 accepted any entry with three non-empty strings. That made the
    skiplist an unauthenticated override of the only local detector there is.
    """
    i = _mid(records)
    _flip_verdict(records[i])  # body changes, `hash` field deliberately does not
    repairs.setdefault("repairs", []).append({
        "seq": records[i].get("seq"),
        "receipt_id": records[i].get("receipt_id"),
        "stored_hash": records[i]["hash"],
        "reason": "fire-drill forgery: an unsigned entry anyone with write access can author",
        "attested_by": "drill-adversary",
        "attested_at": "2026-08-05T00:00:00+00:00",
    })
    return records, repairs


def _repairs_forgery_signed_claim(records, repairs):
    """The same forgery, impersonating a registered attestor without their key."""
    i = _mid(records)
    _flip_verdict(records[i])
    repairs.setdefault("repairs", []).append({
        "seq": records[i].get("seq"),
        "receipt_id": records[i].get("receipt_id"),
        "stored_hash": records[i]["hash"],
        "reason": "fire-drill forgery claiming a real attestor's name, with no signature",
        "attested_by": "kimi-k2.5",
        "attested_at": "2026-08-05T00:00:00+00:00",
    })
    return records, repairs


def _signature_strip(records, repairs):
    """Remove a v3.0 signature block. record_hash excludes it, so the digest holds.

    Caught only because v3.0 puts signer_pubkey inside the hashed body: the
    record goes on claiming a signer it no longer carries.
    """
    for rec in records:
        if isinstance(rec.get("signature"), dict) and rec.get("signer_pubkey"):
            rec.pop("signature")
            return records, repairs
    legacy = sum(1 for r in records if isinstance(r.get("signature"), dict))
    raise Skip(f"no v3.0-signed record (signer_pubkey) to strip; {legacy} legacy-signed record(s) present")


def _signature_strip_legacy(records, repairs):
    """The same strip against a v2.9 record — nothing in the system can see it.

    The digest does not move, so verify() is quiet AND the anchored head still
    matches. There is no verifier-side fix: the record was written without a
    commitment to its own signer. The only remedy is re-signing under v3.0,
    which is why ooptdd.census counts the exposure instead of hiding it.
    """
    for rec in records:
        if isinstance(rec.get("signature"), dict) and not rec.get("signer_pubkey"):
            rec.pop("signature")
            return records, repairs
    raise Skip("no legacy-signed (v2.9) record present — exposure already retired")


def _signature_swap(records, repairs):
    """Graft a valid signature onto a different record, changing nothing else.

    Deliberately does NOT set signer_pubkey: adding it would move the digest and
    make the attack trivially visible. The realistic forger leaves the body
    alone, which is why verify() must check any signature it finds, not only
    the ones a record admits to.
    """
    signed = [r for r in records if isinstance(r.get("signature"), dict)]
    unsigned = [r for r in records if not isinstance(r.get("signature"), dict)]
    if not signed or not unsigned:
        raise Skip("needs one signed and one unsigned record")
    unsigned[-1]["signature"] = json.loads(json.dumps(signed[0]["signature"]))
    return records, repairs


ATTACKS: list[Attack] = [
    Attack("verdict_flip", LOCAL,
           "flip a past verdict in place", _verdict_flip),
    Attack("field_edit", LOCAL,
           "promote a record's status by hand", _field_edit),
    Attack("field_drop", LOCAL,
           "delete a field from a record body", _drop_field),
    Attack("middle_delete", LOCAL,
           "remove a record from the middle", _middle_delete),
    Attack("reorder_swap", LOCAL,
           "swap two adjacent records", _reorder_swap),
    Attack("replay_append", LOCAL,
           "re-append an existing record verbatim", _replay_append),
    Attack("genesis_forge", LOCAL,
           "cut the head and re-root at genesis", _genesis_forge),
    Attack("backdate", LOCAL,
           "rewrite a timestamp", _backdate),
    Attack("signature_strip", LOCAL,
           "remove a v3.0 signature block (hash unchanged by construction)", _signature_strip),
    Attack("signature_strip_legacy", LEGACY_BLIND,
           "remove a v2.9 signature block — no verifier and no anchor can see it",
           _signature_strip_legacy),
    Attack("signature_swap", LOCAL,
           "graft a valid signature onto another record", _signature_swap),
    Attack("repairs_forgery", LOCAL_STRICT,
           "self-authored skiplist entry absolving a tampered body", _repairs_forgery),
    Attack("repairs_forgery_impersonation", LOCAL_STRICT,
           "skiplist entry in a registered attestor's name, unsigned", _repairs_forgery_signed_claim),
    Attack("tail_truncate", ANCHOR_ONLY,
           "drop the last record — the remainder is a valid chain", _tail_truncate),
    Attack("full_rewrite", ANCHOR_ONLY,
           "edit record 0 and recompute every hash after it", _full_rewrite),
    Attack("rewrite_middle", ANCHOR_ONLY,
           "edit a middle record and recompute the tail", _rewrite_middle),
]


def materialize(attack: Attack, records: list[dict], repairs_file: dict,
                out_dir: str, index: int) -> str:
    """Write one attack's chain + repairs sidecar to disk; return the log path."""
    tampered, repairs_out = attack.apply(records, repairs_file)
    path = os.path.join(out_dir, f"{index:02d}_{attack.name}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in tampered:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    if repairs_out.get("repairs"):
        with open(repairs_path_for(path), "w", encoding="utf-8") as f:
            json.dump(repairs_out, f, ensure_ascii=False, indent=1)
    return path


def battery_fingerprint() -> str:
    """Digest of the attack set, so a receipt can pin which battery it survived.

    A drill result means nothing without knowing how many faults it faced.
    """
    return sha256_hex(canonical([[a.name, a.detectability] for a in ATTACKS]))
