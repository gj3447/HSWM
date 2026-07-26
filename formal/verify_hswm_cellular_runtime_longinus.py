#!/usr/bin/env python3
"""Read-only seven-layer Longinus verifier for HSWM cellular runtime v1."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "LONGINUS_HSWM_CELLULAR_RUNTIME_BINDING_2026-07-26.json"
REQUIRED_LAYERS = {
    "KG_NODE",
    "CONTRACT_BINDING",
    "CODE_SYMBOL",
    "FILE_LINE",
    "LINE_RANGE",
    "SHA256",
    "CRATE_SCRIPT",
}
REQUIRED_STATES = {
    "EXACT",
    "STRUCTURAL_EXACT",
    "PARTIAL_MATERIALIZATION",
    "ENGINEERING_ONLY",
}
SYMBOL_PAIRS = (
    ("requestCellStep", "class RequestCellStep"),
    ("recordCellOutput", "class RecordCellOutput"),
    ("cellStepRequested", "class CellStepRequested"),
    ("cellStepCompleted", "class CellStepCompleted"),
    ("invokeCell", "class InvokeCellEffect"),
    ("staleVersion", "STALE_VERSION"),
    ("budgetExhausted", "BUDGET_EXHAUSTED"),
    ("duplicateActivation", "DUPLICATE_ACTIVATION"),
    ("unknownCell", "UNKNOWN_CELL"),
    ("inputTypeMismatch", "INPUT_TYPE_MISMATCH"),
    ("unknownActivation", "UNKNOWN_ACTIVATION"),
    ("outputTypeMismatch", "OUTPUT_TYPE_MISMATCH"),
    ("def decide", "def decide("),
    ("def evolve", "def evolve("),
    ("def effects", "def effects("),
    ("def replay", "def replay("),
)


def digest(path: Path) -> str:
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
        raise AssertionError("seven-layer declaration is incomplete or changed")
    if manifest["kg"]["write_state"] != "NOT_AUTHORIZED_NOT_WRITTEN":
        raise AssertionError("local verifier refuses a manifest claiming a KG write")

    source_ids = [binding["sourceId"] for binding in manifest["bindings"]]
    duplicates = [
        source_id
        for source_id, count in Counter(source_ids).items()
        if count > 1
    ]
    if duplicates:
        raise AssertionError(f"duplicate sourceId values: {duplicates}")

    states: Counter[str] = Counter()
    files: set[str] = set()
    for binding in manifest["bindings"]:
        source_path = binding["source_path"]
        path = REPO_ROOT / source_path
        if not path.is_file():
            raise AssertionError(f"missing source: {source_path}")
        expected = binding["sha256_baseline"]
        actual = digest(path)
        if binding["sha256"] != expected or actual != expected:
            raise AssertionError(
                f"sha256 drift: {binding['sourceId']} expected={expected} actual={actual}"
            )

        lines = path.read_text(encoding="utf-8").splitlines()
        start, end = parse_range(binding["line_range"])
        if end > len(lines):
            raise AssertionError(
                f"line range outside file: {binding['sourceId']} end={end} lines={len(lines)}"
            )
        excerpt = "\n".join(lines[start - 1 : end])
        if binding["symbol_token"] not in excerpt:
            raise AssertionError(
                f"symbol token absent: {binding['sourceId']} "
                f"token={binding['symbol_token']!r}"
            )
        states[binding["binding_state"]] += 1
        files.add(source_path)

    if not REQUIRED_STATES.issubset(states):
        raise AssertionError(f"required binding-state diversity missing: {states}")

    lean_text = (REPO_ROOT / "formal/HSWMRuntime.lean").read_text(encoding="utf-8")
    python_text = (REPO_ROOT / "hswm_cellular_runtime.py").read_text(encoding="utf-8")
    for lean_token, python_token in SYMBOL_PAIRS:
        if lean_token not in lean_text:
            raise AssertionError(f"Lean parity token missing: {lean_token!r}")
        if python_token not in python_text:
            raise AssertionError(f"Python parity token missing: {python_token!r}")

    result = {
        "schema": "hswm-cellular-runtime-longinus-verification/v1",
        "status": "PASS",
        "binding_id": manifest["binding_id"],
        "bindings_checked": len(manifest["bindings"]),
        "files_checked": len(files),
        "layers": len(manifest["layers"]),
        "symbol_pairs_checked": len(SYMBOL_PAIRS),
        "states": dict(sorted(states.items())),
        "kg_write_state": manifest["kg"]["write_state"],
        "claim_boundary": "Local hashes, ranges, symbols, and layer declarations only; not a KG write or scientific verdict.",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
