"""Hash-chained, append-only ooptdd receipt log (v2).

One JSON record per line. Each record's `hash` is sha256 over the canonical
JSON of the record without the `hash` field; `prev_hash` links to the previous
record. Genesis prev_hash is 64 zeroes.

Fail-closed rules:
  - append() re-verifies the existing chain first; a corrupt chain refuses
    new records.
  - verify() detects any post-hoc edit (hash mismatch) and any deletion or
    reordering (prev_hash / seq mismatch).

v2.8 (2026-07-28, chain incident):
  - REPAIRS: a sibling `<log>.repairs.json` skiplist (same culture as
    lakatotree R6 fsck skiplists and transparency-log witnessed exceptions).
    A record whose stored hash is listed there — with reason and attestor —
    is reported intact. Unlisted tampering is still detected; a stale or
    wrong repair entry does nothing. The file is the visibility: repairs are
    data, not code, and are reviewed like any other receipt.
  - LOCKING: append() takes an exclusive flock and re-verifies UNDER the
    lock. Two racing harness runs used to interleave verify→write and could
    corrupt the chain — a race actually observed 2026-07-28 (two sessions
    appending at 05:26/05:30/05:31 UTC). POSIX fcntl; on platforms without
    it the lock is a no-op with the same semantics as v2.7.

v3.0 (2026-08-05, ouroboros closure): three ways the chain could be made to
lie about itself, each now visible instead of silent.

  - AUTHENTICATED REPAIRS. v2.8 shipped the skiplist as free-text data: any
    writer of the sibling file could suppress a hash mismatch by naming the
    stored hash, with an unchecked `attested_by` string. That is an
    unauthenticated bypass of the only local tamper detector. Entries now
    carry a `trust` grade — signed / untrusted / unsigned / invalid — from
    an ed25519 signature over the entry body (sign_repair_entry), checked
    against the auditor registry. Malformed entries (a stored_hash that is
    not 64 hex — the live file has one, 45 chars, unnoticed since 07-28) are
    graded `invalid` and never suppress anything. Progressive by default so
    the historical file keeps working; strict_repairs=True honours ONLY
    `signed` entries, and that is what the gate uses.
  - SIGNATURE STRIP. record_hash excludes "signature" so the signature can
    sign the digest — which also made removing the block free and invisible.
    A signed record now carries `signer_pubkey` INSIDE the hashed body: strip
    the signature and the record still claims a signer, which is an error.
    Legacy records have no such field, so their hashes are untouched.
  - TRUNCATION. Dropping the tail leaves a perfectly valid shorter chain;
    local verification cannot see it, by construction. verify() accepts
    expect_head / expect_min_len so an EXTERNAL memory (the LakatoTree
    anchor) can supply what the file cannot know about itself. Without those
    arguments the blindness is real — see ooptdd.attacks and ooptdd.gate.

Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

try:
    import fcntl
except ImportError:  # non-POSIX: locking no-ops (v2.7 semantics)
    fcntl = None

GENESIS_PREV = "0" * 64


def canonical(obj: Any) -> bytes:
    """Deterministic serialization used for all hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: str) -> str:
    with open(path, "rb") as f:
        return sha256_hex(f.read())


def record_hash(record: dict) -> str:
    # "signature" is excluded alongside "hash": the signature signs this very
    # digest (v2.9), so it cannot be part of it. Legacy records carry no
    # signature key, so their hashes are unchanged.
    body = {k: v for k, v in record.items() if k not in ("hash", "signature")}
    return sha256_hex(canonical(body))


def load(log_path: str) -> list[dict]:
    if not os.path.exists(log_path):
        return []
    records: list[dict] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{log_path}:{i}: unparseable record: {e}") from e
    return records


def repairs_path_for(log_path: str) -> str:
    """The repairs skiplist lives next to the log: <log>.repairs.json."""
    return log_path + ".repairs.json"


REPAIR_PAYLOAD = "repair_entry"


def repair_signing_digest(entry: dict) -> str:
    """The digest a repair signature covers: the entry minus its own signature.

    Same shape as record_hash's exclusion rule, for the same reason — the
    signature cannot be part of what it signs.
    """
    body = {k: v for k, v in entry.items() if k != "signature"}
    return sha256_hex(canonical(body))


def sign_repair_entry(entry: dict, sk: bytes) -> dict:
    """Return a copy of `entry` carrying an ed25519 signature over its digest."""
    from ooptdd import signing

    signed = {k: v for k, v in entry.items() if k != "signature"}
    signed["signature"] = signing.sign_record(repair_signing_digest(signed), sk)
    signed["signature"]["payload"] = REPAIR_PAYLOAD
    return signed


def _grade_repair(entry: dict, registry_pubkeys: dict[str, str] | None) -> str:
    """trust grade for one repair entry — the whole point of v3.0.

    signed     — ed25519 signature valid AND the pubkey is the one the auditor
                 registry holds for `attested_by`. The only grade strict mode
                 accepts.
    untrusted  — signature valid but the attestor has no registered pubkey
                 (real cryptographic authorship, no established identity).
    unsigned   — no signature block. This is what every historical entry is:
                 a claim, honoured only because backward compatibility says so.
    invalid    — malformed entry, bad stored_hash shape, broken signature, or a
                 pubkey that contradicts the registry. Never suppresses anything.
    """
    from ooptdd import signing

    stored = entry.get("stored_hash")
    if (not stored or not entry.get("reason") or not entry.get("attested_by")
            or not isinstance(stored, str) or len(stored) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in stored)):
        return "invalid"
    block = entry.get("signature")
    if not isinstance(block, dict):
        return "unsigned"
    if block.get("payload") != REPAIR_PAYLOAD:
        return "invalid"
    try:
        pk = bytes.fromhex(block["pubkey"])
        sig = bytes.fromhex(block["sig"])
    except (KeyError, ValueError, TypeError):
        return "invalid"
    if not signing.verify_signature(sig, repair_signing_digest(entry).encode("ascii"), pk):
        return "invalid"
    registered = (registry_pubkeys or {}).get(entry["attested_by"])
    if registered is None:
        return "untrusted"
    return "signed" if registered == block["pubkey"] else "invalid"


def load_repairs(repairs_path: str, registry_pubkeys: dict[str, str] | None = None) -> dict:
    """stored_hash -> repair entry (with `trust` graded). Missing file = {}.

    v3.0: a structurally broken entry no longer raises and takes the whole
    chain down with it — it is graded `invalid` and ignored. Raising was the
    wrong failure mode: one bad line in an advisory sidecar would have made
    every receipt in the repo unverifiable, which is an availability hole
    dressed as strictness. Being ignored *and counted* (ooptdd.census) is the
    honest treatment.
    """
    if not os.path.exists(repairs_path):
        return {}
    with open(repairs_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for e in data.get("repairs", []):
        entry = dict(e)
        entry["trust"] = _grade_repair(entry, registry_pubkeys)
        key = entry.get("stored_hash")
        if isinstance(key, str) and key:
            out[key] = entry
    return out


def registry_pubkeys_for(log_path: str, registry_path: str | None = None) -> dict[str, str]:
    """auditor_id -> pubkey from the auditor registry beside the chain."""
    path = registry_path or os.path.join(os.path.dirname(os.path.abspath(log_path)), "auditors.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {a["auditor_id"]: a["pubkey"] for a in data.get("auditors", [])
            if a.get("auditor_id") and a.get("pubkey")}


HONOURED_REPAIR_TRUST = ("signed", "untrusted", "unsigned")


def _verify_records(records: list[dict], repairs: dict | None = None,
                    strict_repairs: bool = False,
                    expect_head: str | None = None,
                    expect_min_len: int | None = None,
                    ) -> tuple[bool, list[str], list[str]]:
    """Core check over parsed records. Returns (ok, errors, repaired_notes).

    strict_repairs — honour ONLY cryptographically `signed` repair entries.
    expect_head / expect_min_len — external expectations the file cannot hold
    about itself; without them, tail truncation is undetectable here.
    """
    repairs = repairs or {}
    honoured = ("signed",) if strict_repairs else HONOURED_REPAIR_TRUST
    errors: list[str] = []
    repaired: list[str] = []
    prev = GENESIS_PREV
    for expected_seq, rec in enumerate(records):
        where = f"seq={rec.get('seq', '?')} receipt={rec.get('receipt_id', '?')}"
        if rec.get("seq") != expected_seq:
            errors.append(f"{where}: seq gap/reorder (expected {expected_seq})")
        if rec.get("prev_hash") != prev:
            errors.append(f"{where}: prev_hash broken (deletion or reorder)")
        if "hash" not in rec:
            errors.append(f"{where}: missing hash")
        elif rec["hash"] != record_hash(rec):
            entry = repairs.get(rec["hash"])
            trust = (entry or {}).get("trust", "invalid")
            if entry is not None and trust in honoured:
                repaired.append(f"{where}: documented repair [{trust}] ({entry.get('reason', '')[:80]})")
            elif entry is not None:
                errors.append(f"{where}: hash mismatch, repair entry rejected (trust={trust})")
            else:
                errors.append(f"{where}: hash mismatch (post-hoc edit)")
        # v3.0 — two signature checks verify() never used to make.
        #
        # (a) A present signature must actually verify against THIS record's
        #     hash. Without it, a valid signature could be grafted from one
        #     record onto another: record_hash excludes "signature", so the
        #     graft moves no digest and nothing objected.
        # (b) A record that names its signer must still carry that signature.
        #     Stripping the block is likewise digest-neutral; signer_pubkey
        #     lives inside the hashed body so the claim survives the strip and
        #     turns it into a contradiction. Records written before v3.0 have
        #     no signer_pubkey and so remain strip-blind — a debt the census
        #     counts rather than a hole the verifier can close retroactively.
        claimed_pubkey = rec.get("signer_pubkey")
        block = rec.get("signature")
        if isinstance(block, dict):
            from ooptdd import signing

            if not signing.verify_record_signature(rec):
                errors.append(f"{where}: signature does not verify against this record's hash "
                              f"(forged, or grafted from another record)")
            elif claimed_pubkey and block.get("pubkey") != claimed_pubkey:
                errors.append(f"{where}: signature pubkey {str(block.get('pubkey'))[:12]}… "
                              f"contradicts declared signer_pubkey {str(claimed_pubkey)[:12]}…")
        elif claimed_pubkey:
            errors.append(f"{where}: signer_pubkey {str(claimed_pubkey)[:12]}… declared but signature stripped")
        prev = rec.get("hash", prev)

    # v3.1 — second pass: a later `resign` record can attest a legacy signature.
    #
    # v2.9 records carry a signature but no signer_pubkey, so stripping the block
    # moves no digest and the anchored head still matches — nothing in the system
    # sees it (ooptdd.attacks: legacy_blind). Re-signing in place is impossible:
    # record_hash would move and every prev_hash after it would break, and the
    # original signer's key is generally gone.
    #
    # Instead a `resign` record names, inside ITS hashed body, which record hashes
    # are supposed to carry which pubkey. Strip the old signature and the chain now
    # holds an attestation about a record that no longer matches it.
    #
    # This does NOT retire the exposure, it relocates it: truncate the resign
    # record away and local verification is quiet again. legacy_blind becomes
    # anchor_only — which is the class expect_head/expect_min_len exist for.
    attested: dict[str, dict] = {}
    for rec in records:
        if rec.get("kind") != "resign":
            continue
        for a in rec.get("attests") or []:
            if isinstance(a, dict) and a.get("target_hash"):
                attested[a["target_hash"]] = {**a, "by_seq": rec.get("seq")}
    for rec in records:
        entry = attested.get(rec.get("hash") or "")
        if not entry:
            continue
        where = f"seq={rec.get('seq', '?')} receipt={rec.get('receipt_id', '?')}"
        block = rec.get("signature")
        want = entry.get("signer_pubkey")
        if not isinstance(block, dict):
            errors.append(f"{where}: resign record (seq={entry['by_seq']}) attests signer "
                          f"{str(want)[:12]}… but the signature is gone")
        elif want and block.get("pubkey") != want:
            errors.append(f"{where}: signature pubkey {str(block.get('pubkey'))[:12]}… "
                          f"contradicts resign attestation {str(want)[:12]}… (seq={entry['by_seq']})")

    if expect_min_len is not None and len(records) < expect_min_len:
        errors.append(f"truncation: {len(records)} records < externally expected {expect_min_len} "
                      f"(local verification cannot see this on its own)")
    if expect_head is not None:
        actual_head = records[-1].get("hash") if records else GENESIS_PREV
        if actual_head != expect_head:
            errors.append(f"head mismatch: local {str(actual_head)[:16]}… != externally anchored "
                          f"{expect_head[:16]}… (truncated, rewritten, or the anchor is behind)")
    return (not errors), errors, repaired


def verify(log_path: str, repairs_path: str | None = None,
           strict_repairs: bool = False,
           expect_head: str | None = None,
           expect_min_len: int | None = None,
           registry_path: str | None = None) -> tuple[bool, list[str]]:
    """Check chain integrity. Returns (ok, errors). Never raises on bad content.

    Records whose stored hash is listed in the repairs skiplist verify as
    intact (the repair file is the attestation); everything else is fail-closed.

    v3.0 — `strict_repairs` narrows that indulgence to signed entries only,
    and expect_head/expect_min_len let an external anchor supply the one fact
    a file can never establish about itself: that nothing was cut off the end.
    """
    errors: list[str] = []
    try:
        records = load(log_path)
        repairs = load_repairs(repairs_path or repairs_path_for(log_path),
                               registry_pubkeys_for(log_path, registry_path))
    except (ValueError, json.JSONDecodeError, OSError) as e:
        return False, [str(e)]
    ok, errs, _repaired = _verify_records(records, repairs, strict_repairs=strict_repairs,
                                          expect_head=expect_head, expect_min_len=expect_min_len)
    errors.extend(errs)
    return ok, errors


def append(log_path: str, record: dict, signer=None, signer_pubkey: str | None = None) -> dict:
    """Verify the chain UNDER AN EXCLUSIVE LOCK, then append one record.

    Refuses (raises) if the existing chain is corrupt — fail-closed, no silent
    continuation on top of broken history. The flock serializes concurrent
    harness runs: the verify→write pair is atomic against other append()
    callers (writers that bypass append() entirely are exactly what the
    repairs skiplist documents).

    signer (v2.9): optional callable taking the record's hash hex (computed
    AFTER seq/prev_hash/timestamp are filled, so the signature binds the exact
    chained content) and returning a signature block to embed before hashing.
    record_hash excludes "signature", so the block signs the final digest.

    signer_pubkey (v3.0): the signer's pubkey, written INTO the hashed body.
    This is what makes a stripped signature detectable — the digest keeps
    claiming a signer even after the block is gone. Omit it and you get v2.9
    semantics, silent downgrade included.
    """
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a+", encoding="utf-8") as f:
        if fcntl is not None:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            records: list[dict] = []
            for i, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    records.append(json.loads(line))
            repairs = load_repairs(repairs_path_for(log_path),
                                   registry_pubkeys_for(log_path))
            ok, errors, _repaired = _verify_records(records, repairs)
            if not ok:
                raise ValueError(f"refusing to append to corrupt chain: {errors}")
            rec = dict(record)
            rec["seq"] = len(records)
            rec["prev_hash"] = records[-1]["hash"] if records else GENESIS_PREV
            rec.setdefault("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds"))
            if signer is not None:
                if signer_pubkey:
                    rec["signer_pubkey"] = signer_pubkey
                rec["signature"] = signer(record_hash(rec))
            rec["hash"] = record_hash(rec)
            f.seek(0, os.SEEK_END)
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            if fcntl is not None:
                fcntl.flock(f, fcntl.LOCK_UN)
    return rec
