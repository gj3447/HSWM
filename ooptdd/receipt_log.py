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


def load_repairs(repairs_path: str) -> dict:
    """stored_hash -> repair entry. Missing file = no repairs (not an error)."""
    if not os.path.exists(repairs_path):
        return {}
    with open(repairs_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for e in data.get("repairs", []):
        if not e.get("stored_hash") or not e.get("reason") or not e.get("attested_by"):
            raise ValueError(f"{repairs_path}: every repair needs stored_hash, reason, attested_by")
        out[e["stored_hash"]] = e
    return out


def _verify_records(records: list[dict], repairs: dict | None = None
                    ) -> tuple[bool, list[str], list[str]]:
    """Core check over parsed records. Returns (ok, errors, repaired_notes)."""
    repairs = repairs or {}
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
            if entry is not None:
                repaired.append(f"{where}: documented repair ({entry.get('reason', '')[:80]})")
            else:
                errors.append(f"{where}: hash mismatch (post-hoc edit)")
        prev = rec.get("hash", prev)
    return (not errors), errors, repaired


def verify(log_path: str, repairs_path: str | None = None) -> tuple[bool, list[str]]:
    """Check chain integrity. Returns (ok, errors). Never raises on bad content.

    Records whose stored hash is listed in the repairs skiplist verify as
    intact (the repair file is the attestation); everything else is fail-closed.
    """
    errors: list[str] = []
    try:
        records = load(log_path)
        repairs = load_repairs(repairs_path or repairs_path_for(log_path))
    except ValueError as e:
        return False, [str(e)]
    ok, errs, _repaired = _verify_records(records, repairs)
    errors.extend(errs)
    return ok, errors


def append(log_path: str, record: dict, signer=None) -> dict:
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
            repairs = load_repairs(repairs_path_for(log_path))
            ok, errors, _repaired = _verify_records(records, repairs)
            if not ok:
                raise ValueError(f"refusing to append to corrupt chain: {errors}")
            rec = dict(record)
            rec["seq"] = len(records)
            rec["prev_hash"] = records[-1]["hash"] if records else GENESIS_PREV
            rec.setdefault("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds"))
            if signer is not None:
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
