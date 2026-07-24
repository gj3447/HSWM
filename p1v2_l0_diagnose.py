"""Post-measurement diagnosis for a P1v2 L0 typed-lesson result.

This module does not rerun the model or change the scientific judgment.  It
checks the frozen measurement and judge receipts, then identifies whether the
test had observable answer headroom for the registered intervention.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping

from hswm_weight_snapshot import canonical_sha256
from p1v2_l0_harness import ARM_IDS, verify_lakato_evidence_record


DIAGNOSIS_SCHEMA_VERSION = "hswm-p1v2-l0-inertness-diagnosis/v1"


class L0DiagnosisError(ValueError):
    pass


def _verify_judge_receipt(receipt: Mapping[str, object]) -> None:
    if receipt.get("schema_version") != "hswm-p1v2-l0-judge-receipt/v1":
        raise L0DiagnosisError("judge receipt schema drifted")
    unsigned = dict(receipt)
    declared = unsigned.pop("judge_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise L0DiagnosisError("judge receipt self-hash drifted")


def diagnose_l0_inertness(
    evidence: Mapping[str, object],
    judge_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Return a deterministic failure-mode diagnosis without a new verdict."""

    verify_lakato_evidence_record(evidence)
    _verify_judge_receipt(judge_receipt)
    if judge_receipt.get("evidence_sha256") != evidence.get("evidence_sha256"):
        raise L0DiagnosisError("judge receipt does not bind the evidence")
    measurement = evidence.get("measurement")
    if not isinstance(measurement, Mapping):
        raise L0DiagnosisError("measurement schema drifted")
    observations = measurement.get("observations")
    if not isinstance(observations, list) or not observations:
        raise L0DiagnosisError("measurement has no observations")

    no_memory_correct = 0
    typed_correct = 0
    all_arm_answer_identity = 0
    typed_changed_no_memory = 0
    typed_improved_no_memory = 0
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise L0DiagnosisError("observation schema drifted")
        arms = observation.get("arms")
        if not isinstance(arms, Mapping) or set(arms) != set(ARM_IDS):
            raise L0DiagnosisError("observation arm cut drifted")
        hashes = {arms[arm]["answers_sha256"] for arm in ARM_IDS}
        typed = arms["T1_typed_lesson"]
        no_memory = arms["T3_no_memory"]
        no_memory_correct += int(no_memory["set_match"])
        typed_correct += int(typed["set_match"])
        all_arm_answer_identity += int(len(hashes) == 1)
        changed = typed["answers_sha256"] != no_memory["answers_sha256"]
        typed_changed_no_memory += int(changed)
        typed_improved_no_memory += int(
            changed and typed["set_match"] > no_memory["set_match"]
        )

    case_count = len(observations)
    if no_memory_correct == case_count and all_arm_answer_identity == case_count:
        diagnosis = "BASELINE_CEILING_AND_INTERVENTION_INERT"
        reuse_allowed = False
    elif typed_changed_no_memory == 0:
        diagnosis = "INTERVENTION_INERT"
        reuse_allowed = False
    elif typed_improved_no_memory == 0:
        diagnosis = "INTERVENTION_CHANGED_WITHOUT_BENEFIT"
        reuse_allowed = False
    else:
        diagnosis = "ACTUATION_PRESENT"
        reuse_allowed = True

    judge_criteria = judge_receipt.get("criteria")
    if (
        not isinstance(judge_criteria, Mapping)
        or judge_criteria.get("valid_case_count") != case_count
        or judge_criteria.get("typed_actuation_case_count")
        != typed_improved_no_memory
    ):
        raise L0DiagnosisError("judge criteria differ from the derived diagnosis")

    unsigned: dict[str, object] = {
        "schema_version": DIAGNOSIS_SCHEMA_VERSION,
        "evidence_sha256": evidence["evidence_sha256"],
        "judge_receipt_sha256": judge_receipt["judge_receipt_sha256"],
        "diagnosis": diagnosis,
        "metrics": {
            "case_count": case_count,
            "no_memory_exact_set_match_count": no_memory_correct,
            "typed_exact_set_match_count": typed_correct,
            "all_four_arms_identical_answer_count": all_arm_answer_identity,
            "typed_changed_no_memory_answer_count": typed_changed_no_memory,
            "typed_improved_no_memory_count": typed_improved_no_memory,
        },
        "root_cause": (
            "The exact retrieved documents and frozen answer prompt already made "
            "the complete answer set available to the no-memory arm. The oracle "
            "lesson restated an answering policy instead of supplying a missing, "
            "outcome-relevant source-trust or conflict-resolution rule."
        ),
        "same_environment_reuse_allowed": reuse_allowed,
        "next_environment_gates": [
            "Use development-only calibration cases to prove non-ceiling no-memory behavior before freezing a new heldout cut.",
            "The typed lesson must encode an outcome-relevant source-trust or conflict-resolution rule absent from the base system prompt.",
            "Require at least one calibration answer disagreement caused by that lesson; do not inspect the new heldout outcomes.",
            "Register LakatoTree direction as higher and bind the independent judge script SHA before measurement.",
        ],
        "scientific_judgment_reused_not_reissued": True,
    }
    return {**unsigned, "diagnosis_receipt_sha256": canonical_sha256(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--judge-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    diagnosis = diagnose_l0_inertness(
        json.loads(args.evidence.read_text(encoding="utf-8")),
        json.loads(args.judge_receipt.read_text(encoding="utf-8")),
    )
    encoded = json.dumps(
        diagnosis, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    if args.output.exists() and args.output.read_text(encoding="utf-8") != encoded:
        raise L0DiagnosisError("refusing to overwrite a different diagnosis")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({
        "diagnosis": diagnosis["diagnosis"],
        "diagnosis_receipt_sha256": diagnosis["diagnosis_receipt_sha256"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["L0DiagnosisError", "diagnose_l0_inertness"]
