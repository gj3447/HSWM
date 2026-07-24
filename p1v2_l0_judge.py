"""Pure independent judge for the P1v2 L0 oracle-actuation stage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

from hswm_weight_snapshot import canonical_sha256
from p1v2_l0_harness import ARM_IDS, verify_lakato_evidence_record


JUDGE_SCHEMA_VERSION = "hswm-p1v2-l0-judge-receipt/v1"
CONTRADICTION_SCHEMA_VERSION = "hswm-p1v2-contradiction-refusal/v1"


class L0JudgeError(ValueError):
    pass


def make_contradiction_receipt(
    *,
    candidate_lesson_sha256: str,
    admission_guard_sha256: str,
    rejected: bool,
    error_class: str | None,
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema_version": CONTRADICTION_SCHEMA_VERSION,
        "candidate_lesson_sha256": candidate_lesson_sha256,
        "admission_guard_sha256": admission_guard_sha256,
        "rejected": rejected,
        "error_class": error_class,
    }
    receipt["contradiction_receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def verify_contradiction_receipt(receipt: Mapping[str, object]) -> None:
    if receipt.get("schema_version") != CONTRADICTION_SCHEMA_VERSION:
        raise L0JudgeError("contradiction receipt schema drifted")
    unsigned = dict(receipt)
    declared = unsigned.pop("contradiction_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise L0JudgeError("contradiction receipt self-hash drifted")
    if not isinstance(receipt.get("rejected"), bool):
        raise L0JudgeError("contradiction receipt rejection state is invalid")


def _verify_budget(budget: Mapping[str, object]) -> None:
    if budget.get("schema_version") != "hswm-p1v2-l0-budget-manifest/v1":
        raise L0JudgeError("budget manifest schema drifted")
    unsigned = dict(budget)
    declared = unsigned.pop("budget_manifest_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise L0JudgeError("budget manifest self-hash drifted")
    if budget.get("measurement_state") != "FROZEN_UNRUN":
        raise L0JudgeError("budget was not frozen before measurement")
    if budget.get("scientific_judgment_emitted") is not False:
        raise L0JudgeError("budget contains a scientific self-judgment")


def judge_l0(
    evidence: Mapping[str, object],
    budget: Mapping[str, object],
    contradiction_receipt: Mapping[str, object],
) -> dict[str, object]:
    verify_lakato_evidence_record(evidence)
    _verify_budget(budget)
    verify_contradiction_receipt(contradiction_receipt)
    measurement = evidence.get("measurement")
    if not isinstance(measurement, Mapping):
        raise L0JudgeError("evidence measurement schema mismatch")
    observations = measurement.get("observations")
    if not isinstance(observations, list) or not observations:
        raise L0JudgeError("evidence has no L0 observations")
    parity = budget.get("parity")
    if not isinstance(parity, Mapping) or not isinstance(parity.get("case_plans"), list):
        raise L0JudgeError("budget parity plan schema mismatch")
    plans = {plan["case_id"]: plan for plan in parity["case_plans"]}
    if len(plans) != len(parity["case_plans"]):
        raise L0JudgeError("budget case IDs are not unique")
    by_case = {observation.get("case_id"): observation for observation in observations}
    if len(by_case) != len(observations) or set(by_case) != set(plans):
        raise L0JudgeError("evidence case cut differs from the frozen budget")

    rows: list[dict[str, object]] = []
    for case_id in sorted(plans):
        plan = plans[case_id]
        observation = by_case[case_id]
        if observation.get("parity_receipt_sha256") != plan["parity_receipt_sha256"]:
            raise L0JudgeError("observation parity receipt differs from budget")
        arms = observation.get("arms")
        budget_row = observation.get("budget")
        gold_boundary = observation.get("gold_boundary")
        if not isinstance(arms, Mapping) or set(arms) != set(ARM_IDS):
            raise L0JudgeError("observation arm set drifted")
        if (
            not isinstance(budget_row, Mapping)
            or budget_row.get("logical_model_calls") != 4
            or budget_row.get("token_parity") is not True
            or budget_row.get("user_prompt_tokens_per_arm")
            != plan["target_input_tokens_per_arm"]
        ):
            raise L0JudgeError("observation violated the frozen call/token budget")
        if (
            not isinstance(gold_boundary, Mapping)
            or gold_boundary.get("gold_sent_to_answer_port") is not False
            or gold_boundary.get("gold_opened_only_after_all_arm_answers") is not True
            or gold_boundary.get("gold_values_published") is not False
        ):
            raise L0JudgeError("observation violated the sealed-gold boundary")
        for arm in ARM_IDS:
            arm_row = arms[arm]
            if (
                arm_row.get("logical_call_count") != 1
                or arm_row.get("user_prompt_tokens")
                != plan["target_input_tokens_per_arm"]
                or arm_row.get("set_match") not in (0, 1)
            ):
                raise L0JudgeError("arm receipt violates parity or metric schema")
        typed = arms["T1_typed_lesson"]
        raw = arms["T2_raw_transcript"]
        no_memory = arms["T3_no_memory"]
        rows.append({
            "case_id": case_id,
            "typed_minus_no_memory": typed["set_match"] - no_memory["set_match"],
            "typed_minus_raw_transcript": typed["set_match"] - raw["set_match"],
            "typed_changed_no_memory_answer": (
                typed["answers_sha256"] != no_memory["answers_sha256"]
            ),
        })

    actuated = [
        row for row in rows
        if row["typed_minus_no_memory"] > 0 and row["typed_changed_no_memory_answer"]
    ]
    contradiction_rejected = contradiction_receipt["rejected"] is True
    passed = bool(actuated) and contradiction_rejected
    unsigned: dict[str, object] = {
        "schema_version": JUDGE_SCHEMA_VERSION,
        "stage": "L0_ORACLE_ACTUATION",
        "verdict": "PASS" if passed else "KILL",
        "evidence_sha256": evidence["evidence_sha256"],
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "contradiction_receipt_sha256": contradiction_receipt[
            "contradiction_receipt_sha256"
        ],
        "criteria": {
            "valid_case_count": len(rows),
            "typed_actuation_case_count": len(actuated),
            "typed_beats_raw_transcript_case_count": sum(
                row["typed_minus_raw_transcript"] > 0 for row in rows
            ),
            "contradicted_lesson_rejected": contradiction_rejected,
            "all_call_token_gold_gates_valid": True,
        },
        "actuation_case_ids": [row["case_id"] for row in actuated],
        "claim_boundary": (
            "L0 proves only that a training-evidence-derived typed lesson can "
            "causally actuate the frozen answer interface on this synthetic cut."
        ),
    }
    return {**unsigned, "judge_receipt_sha256": canonical_sha256(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--contradiction-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = judge_l0(
        json.loads(args.evidence.read_text(encoding="utf-8")),
        json.loads(args.budget.read_text(encoding="utf-8")),
        json.loads(args.contradiction_receipt.read_text(encoding="utf-8")),
    )
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "verdict": receipt["verdict"],
        "judge_receipt_sha256": receipt["judge_receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "L0JudgeError",
    "judge_l0",
    "make_contradiction_receipt",
    "verify_contradiction_receipt",
]
