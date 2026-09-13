"""Generate source-bound terminal/reason cases from the original Python APIs.

Run with ``uv run python _research/native_migration_2026-09-13/generate_occurrence_integrity_differential_fixture.py``.
The emitted JSON is consumed by the native port tests; production runtime never
imports or executes this research generator.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests/fixtures/native_migration/occurrence_integrity_v1/differential.original.v1.json"
SOURCES = (
    "src/hswm/infrastructure/occurrence_integrity.py",
    "src/hswm/evaluation/occurrence_dual_evaluator.py",
)
sys.path.insert(0, str(ROOT / "tests"))

from hswm.evaluation.occurrence_dual_evaluator import assess_dual_evaluation
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1
from test_occurrence_dual_evaluator import signed_a, signed_b
from test_occurrence_integrity import assess


def terminal_reason(value: object) -> dict[str, str]:
    return {"terminal": value.terminal.value, "reason": value.reason}


def main() -> None:
    integrity = {
        "duplicate": terminal_reason(assess(duplicate_seen=True)),
        "retry": terminal_reason(assess(retry_seen=True)),
        "duplicate_precedes_retry": terminal_reason(assess(duplicate_seen=True, retry_seen=True)),
        "missing_external_audit": terminal_reason(assess(external_audit=None)),
    }
    dual = {
        "missing_signature": terminal_reason(assess_dual_evaluation(replace(signed_a(), signature=None), signed_b())),
        "unverified_signature": terminal_reason(assess_dual_evaluation(signed_a(verified=False), signed_b())),
        "missing_judgment": terminal_reason(assess_dual_evaluation(None, signed_b())),
        "different_score": terminal_reason(assess_dual_evaluation(signed_a(), replace(signed_b(), canonical_decision_score_sha256="0" * 64, signature=None))),
        "different_input": terminal_reason(assess_dual_evaluation(signed_a(), replace(signed_b(), input=ContentDescriptorV1("application/json", "9" * 64, 1), signature=None))),
        "different_uid": terminal_reason(assess_dual_evaluation(signed_a(), replace(signed_b(), occurrence_uid="g0-occurrence-2", signature=None))),
        "shared_implementation": terminal_reason(assess_dual_evaluation(signed_a(), replace(signed_b(), implementation=signed_a().implementation, signature=None))),
    }
    payload = {
        "schema_version": "hswm-native-occurrence-integrity-differential/v1",
        "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCES},
        "integrity": integrity,
        "dual": dual,
    }
    OUT.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
