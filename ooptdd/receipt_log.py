"""Hash-chained, append-only ooptdd receipt log (v2).

One JSON record per line. Each record's `hash` is sha256 over the canonical
JSON of the record without the `hash` field; `prev_hash` links to the previous
record. Genesis prev_hash is 64 zeroes.

Fail-closed rules:
  - append() re-verifies the existing chain first; a corrupt chain refuses
    new records.
  - verify() detects any post-hoc edit (hash mismatch) and any deletion or
    reordering (prev_hash / seq mismatch).

Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

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
    body = {k: v for k, v in record.items() if k != "hash"}
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


def verify(log_path: str) -> tuple[bool, list[str]]:
    """Check chain integrity. Returns (ok, errors). Never raises on bad content."""
    errors: list[str] = []
    try:
        records = load(log_path)
    except ValueError as e:
        return False, [str(e)]
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
            errors.append(f"{where}: hash mismatch (post-hoc edit)")
        prev = rec.get("hash", prev)
    return (not errors), errors


def append(log_path: str, record: dict) -> dict:
    """Verify the chain, then append one record with seq/prev_hash/hash filled in.

    Refuses (raises) if the existing chain is corrupt — fail-closed, no silent
    continuation on top of broken history.
    """
    ok, errors = verify(log_path)
    if not ok:
        raise ValueError(f"refusing to append to corrupt chain: {errors}")
    records = load(log_path)
    rec = dict(record)
    rec["seq"] = len(records)
    rec["prev_hash"] = records[-1]["hash"] if records else GENESIS_PREV
    rec.setdefault("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    rec["hash"] = record_hash(rec)
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    return rec
