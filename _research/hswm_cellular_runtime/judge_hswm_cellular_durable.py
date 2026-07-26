#!/usr/bin/env python3
"""Locked deterministic judge for the HSWM durable-runtime preregistration.

This judge scores only engineering fault gates.  A score of 1.0 is not evidence
for semantic learning, larger-AI behavior, transfer, topology, or consolidation.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


RECEIPT_SCHEMA = "hswm-cellular-durable-runtime-validation/v1"
METRIC = "durable_runtime_fault_gate_fraction"
REQUIRED_FAULT_GATES = (
    "atomic_request_event_and_outbox",
    "pending_outbox_recovers_after_reopen",
    "single_claim_under_competition",
    "unknown_outcome_is_not_auto_retried",
    "completion_event_and_outbox_success_are_atomic",
    "exact_command_retry_adds_no_event",
    "same_key_different_intent_is_rejected",
    "same_history_has_stable_digest",
    "typed_cell_port_completes",
)
ALLOWED_MODEL_PROBES = {"FIXTURE_PASS", "LIVE_PASS"}


def judge(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError(f"receipt schema must be {RECEIPT_SCHEMA!r}")
    gates = receipt.get("fault_gates")
    if not isinstance(gates, dict):
        raise ValueError("fault_gates must be an object")
    if set(gates) != set(REQUIRED_FAULT_GATES):
        missing = sorted(set(REQUIRED_FAULT_GATES) - set(gates))
        extra = sorted(set(gates) - set(REQUIRED_FAULT_GATES))
        raise ValueError(f"fault gate field set mismatch: missing={missing}, extra={extra}")
    if any(not isinstance(gates[name], bool) for name in REQUIRED_FAULT_GATES):
        raise ValueError("every fault gate must be boolean")

    model_probe = receipt.get("model_probe")
    if model_probe not in ALLOWED_MODEL_PROBES:
        raise ValueError(
            f"model_probe must be one of {sorted(ALLOWED_MODEL_PROBES)}, got {model_probe!r}"
        )
    passed = sum(1 for name in REQUIRED_FAULT_GATES if gates[name])
    total = len(REQUIRED_FAULT_GATES)
    score = passed / total
    return {
        "schema": "hswm-cellular-durable-runtime-judge/v1",
        "metric": METRIC,
        "value": score,
        "passed": passed,
        "total": total,
        "eligible": score == 1.0,
        "model_probe": model_probe,
        "scientific_status": "UNJUDGED",
        "claim_boundary": "Crash-safe runtime engineering only; no HSWM scientific hypothesis is judged.",
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} RECEIPT.json", file=sys.stderr)
        return 2
    try:
        receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        result = judge(receipt)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"status": "SCORING_REFUSED", "error": str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
