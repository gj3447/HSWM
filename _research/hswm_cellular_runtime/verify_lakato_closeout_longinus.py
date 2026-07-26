#!/usr/bin/env python3
"""Read-only supplementary Longinus verifier for the LakatoTree closeout."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("longinus_lakato_closeout.v1.json")
REQUIRED_LAYERS = {
    "KG_NODE",
    "CONTRACT_BINDING",
    "CODE_SYMBOL",
    "FILE_LINE",
    "LINE_RANGE",
    "SHA256",
    "CRATE_SCRIPT",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if set(manifest["layers"]) != REQUIRED_LAYERS:
        raise AssertionError("seven-layer declaration drift")
    if manifest["kg"]["write_state"] != "LAKATOTREE_WRITTEN_KG_NOT_AUTHORIZED":
        raise AssertionError("KG/LakatoTree authority boundary drift")
    source_ids = [item["sourceId"] for item in manifest["bindings"]]
    if len(source_ids) != len(set(source_ids)):
        raise AssertionError("duplicate sourceId")

    states: Counter[str] = Counter()
    for item in manifest["bindings"]:
        path = REPO_ROOT / item["source_path"]
        if digest(path) != item["sha256"] or item["sha256"] != item["sha256_baseline"]:
            raise AssertionError(f"SHA-256 drift: {item['sourceId']}")
        lines = path.read_text(encoding="utf-8").splitlines()
        start, end = (int(part) for part in item["line_range"].split("-", 1))
        if start < 1 or end < start or end > len(lines):
            raise AssertionError(f"line range drift: {item['sourceId']}")
        if item["symbol_token"] not in "\n".join(lines[start - 1 : end]):
            raise AssertionError(f"symbol drift: {item['sourceId']}")
        states[item["binding_state"]] += 1

    v3 = json.loads(
        (REPO_ROOT / "receipts/HSWM_DURABLE_LAKATO_REPLAY_VALIDATION_20260726.json").read_text(
            encoding="utf-8"
        )
    )
    if v3.get("scientific_status") != "UNJUDGED":
        raise AssertionError("Lakato replay receipt overclaims science")
    if not str(v3.get("parent_verdict_preserved", "")).startswith("partial@L0"):
        raise AssertionError("parent partial verdict is not preserved")
    closeout = (
        REPO_ROOT
        / "_research/hswm_cellular_runtime/LAKATOTREE_DURABLE_RUNTIME_CLOSEOUT_2026-07-26.md"
    ).read_text(encoding="utf-8")
    for token in ("LAKATOTREE PARTIAL", "ABANDON", "SCIENCE UNJUDGED"):
        if token not in closeout:
            raise AssertionError(f"honesty token missing: {token}")

    print(
        json.dumps(
            {
                "schema": "hswm-durable-lakato-closeout-longinus-verification/v1",
                "status": "PASS",
                "bindings_checked": len(manifest["bindings"]),
                "layers": len(manifest["layers"]),
                "states": dict(sorted(states.items())),
                "lakatotree_status": "PARTIAL_ABANDONED_BRANCH",
                "scientific_status": "UNJUDGED",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
