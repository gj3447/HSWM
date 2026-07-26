#!/usr/bin/env python3
"""Verify local Longinus baselines for the HSWM cellular definition.

This verifier is deliberately read-only.  It checks byte hashes, line ranges,
symbol tokens, layer coverage, and the explicit no-KG-write boundary.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "LONGINUS_HSWM_CELLULAR_DEFINITION_BINDING_2026-07-26.json"
REQUIRED_LAYERS = {
    "KG_NODE",
    "CONTRACT_BINDING",
    "CODE_SYMBOL",
    "FILE_LINE",
    "LINE_RANGE",
    "SHA256",
    "CRATE_SCRIPT",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_range(raw: str) -> tuple[int, int]:
    left, right = raw.split("-", 1)
    start, end = int(left), int(right)
    if start < 1 or end < start:
        raise ValueError(f"invalid line_range: {raw}")
    return start, end


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if set(manifest["layers"]) != REQUIRED_LAYERS:
        raise AssertionError("seven-layer contract is incomplete or changed")
    if manifest["kg"]["write_state"] != "NOT_AUTHORIZED_NOT_WRITTEN":
        raise AssertionError("local verifier refuses a manifest claiming a KG write")

    bindings = manifest["bindings"]
    source_ids = [binding["sourceId"] for binding in bindings]
    duplicates = [key for key, count in Counter(source_ids).items() if count > 1]
    if duplicates:
        raise AssertionError(f"duplicate sourceId values: {duplicates}")

    states: Counter[str] = Counter()
    checked = []
    for binding in bindings:
        path = REPO_ROOT / binding["source_path"]
        if not path.is_file():
            raise AssertionError(f"missing source: {binding['source_path']}")
        actual_hash = sha256(path)
        expected_hash = binding["sha256_baseline"]
        if actual_hash != expected_hash or binding["sha256"] != expected_hash:
            raise AssertionError(
                f"sha256 drift: {binding['sourceId']} "
                f"expected={expected_hash} actual={actual_hash}"
            )

        lines = path.read_text(encoding="utf-8").splitlines()
        start, end = parse_range(binding["line_range"])
        if end > len(lines):
            raise AssertionError(
                f"line range outside file: {binding['sourceId']} "
                f"end={end} lines={len(lines)}"
            )
        excerpt = "\n".join(lines[start - 1 : end])
        token = binding["symbol_token"]
        if token not in excerpt:
            raise AssertionError(
                f"symbol token absent from bound range: "
                f"{binding['sourceId']} token={token!r}"
            )

        states[binding["binding_state"]] += 1
        checked.append(binding["sourceId"])

    required_states = {
        "EXACT",
        "STRUCTURAL_EXACT",
        "PARTIAL_MATERIALIZATION",
        "CONFOUNDED_EVIDENCE",
        "UNPROVEN_CONDITION",
    }
    if not required_states.issubset(states):
        raise AssertionError(
            f"binding states fail to expose all definition/runtime gaps: {states}"
        )

    result = {
        "schema": "hswm-cellular-longinus-verification/v1",
        "status": "PASS",
        "binding_id": manifest["binding_id"],
        "checked": len(checked),
        "states": dict(sorted(states.items())),
        "layers": len(manifest["layers"]),
        "kg_write_state": manifest["kg"]["write_state"],
    }
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
