#!/usr/bin/env python3
"""Read-only seven-layer Longinus verifier for HSWM durable runtime v2."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "LONGINUS_HSWM_DURABLE_RUNTIME_BINDING_2026-07-26.json"
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
OUTBOX_PARITY = {
    "pending": ("PENDING", "pending"),
    "inFlight": ("IN_FLIGHT", "in_flight"),
    "unknownOutcome": ("UNKNOWN_OUTCOME", "unknown_outcome"),
    "succeeded": ("SUCCEEDED", "succeeded"),
    "failedPermanent": ("FAILED_PERMANENT", "failed_permanent"),
}
FAULT_GATES = {
    "atomic_request_event_and_outbox",
    "pending_outbox_recovers_after_reopen",
    "single_claim_under_competition",
    "unknown_outcome_is_not_auto_retried",
    "completion_event_and_outbox_success_are_atomic",
    "exact_command_retry_adds_no_event",
    "same_key_different_intent_is_rejected",
    "same_history_has_stable_digest",
    "typed_cell_port_completes",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_range(raw: str) -> tuple[int, int]:
    start_raw, end_raw = raw.split("-", 1)
    start, end = int(start_raw), int(end_raw)
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
    duplicates = [key for key, count in Counter(source_ids).items() if count > 1]
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
                f"line range outside file: {source_path} end={end} lines={len(lines)}"
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

    lean_text = (REPO_ROOT / "formal/HSWMDurableRuntime.lean").read_text(
        encoding="utf-8"
    )
    python_text = (REPO_ROOT / "hswm_cellular_store.py").read_text(encoding="utf-8")
    fsm = json.loads(
        (REPO_ROOT / "_research/hswm_cellular_runtime/outbox_fsm.v1.json").read_text(
            encoding="utf-8"
        )
    )
    fsm_text = json.dumps(fsm, sort_keys=True)
    for lean_token, (python_token, fsm_token) in OUTBOX_PARITY.items():
        if lean_token not in lean_text:
            raise AssertionError(f"Lean outbox token missing: {lean_token!r}")
        if python_token not in python_text:
            raise AssertionError(f"Python outbox token missing: {python_token!r}")
        if fsm_token not in fsm_text:
            raise AssertionError(f"FSM outbox token missing: {fsm_token!r}")

    prereg = json.loads(
        (
            REPO_ROOT
            / "_research/hswm_cellular_runtime/PREREG_HSWM_CELLULAR_DURABLE_RUNTIME_V2_2026-07-26.json"
        ).read_text(encoding="utf-8")
    )
    if prereg.get("registered_before_implementation") is not True:
        raise AssertionError("preregistration ordering claim is absent")
    judge_path = REPO_ROOT / prereg["locked_judge"]["path"]
    if digest(judge_path) != prereg["locked_judge"]["sha256"]:
        raise AssertionError("locked judge SHA-256 drift")

    receipt = json.loads(
        (
            REPO_ROOT
            / "receipts/HSWM_CELLULAR_DURABLE_RUNTIME_VALIDATION_20260726.json"
        ).read_text(encoding="utf-8")
    )
    if receipt.get("schema") != prereg["locked_judge"]["receipt_schema"]:
        raise AssertionError("receipt schema does not match preregistration")
    if set(receipt.get("fault_gates", {})) != FAULT_GATES:
        raise AssertionError("receipt fault-gate field set drift")
    if not all(receipt["fault_gates"].values()):
        raise AssertionError("one or more preregistered fault gates failed")
    if receipt.get("model_probe") not in prereg["allowed_model_probe"]:
        raise AssertionError("receipt model probe is not preregistered")
    if receipt.get("scientific_status") != "UNJUDGED":
        raise AssertionError("engineering receipt overclaims scientific status")

    result = {
        "schema": "hswm-cellular-durable-runtime-longinus-verification/v1",
        "status": "PASS",
        "binding_id": manifest["binding_id"],
        "bindings_checked": len(manifest["bindings"]),
        "files_checked": len(files),
        "layers": len(manifest["layers"]),
        "outbox_symbol_pairs_checked": len(OUTBOX_PARITY),
        "fault_gates_checked": len(FAULT_GATES),
        "states": dict(sorted(states.items())),
        "kg_write_state": manifest["kg"]["write_state"],
        "scientific_status": receipt["scientific_status"],
        "claim_boundary": "Local hashes, ranges, contracts, symbols, preregistration, and receipt only; not a KG write or HSWM scientific verdict.",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
