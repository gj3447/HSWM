"""Independent deterministic judge for P1v3 heldout policy actuation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping, Sequence

from hswm_weight_snapshot import canonical_sha256
from p1v2_prompt_parity import ARM_IDS
from p1v3_calibration_preflight import file_sha256, write_once


SCHEMA_VERSION = "hswm-p1v3-policy-heldout-judge/v1"


class P1V3HeldoutJudgeError(ValueError):
    pass


def _verify_self_hash(value: Mapping[str, object], key: str, label: str) -> None:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise P1V3HeldoutJudgeError(f"{label} self-hash drifted")


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


def judge_heldout(
    *,
    evidence: Mapping[str, object],
    budget: Mapping[str, object],
    judge_script_sha256: str,
) -> dict[str, object]:
    _verify_self_hash(evidence, "evidence_sha256", "measurement evidence")
    _verify_self_hash(budget, "budget_manifest_sha256", "heldout budget")
    if any(key.casefold() == "verdict" for key in _recursive_keys(evidence)):
        raise P1V3HeldoutJudgeError("measurement evidence contains a verdict key")
    if evidence.get("budget_manifest_sha256") != budget.get("budget_manifest_sha256"):
        raise P1V3HeldoutJudgeError("evidence binds a different budget")
    if len(judge_script_sha256) != 64:
        raise P1V3HeldoutJudgeError("judge script hash is invalid")
    observations = evidence.get("observations")
    plans = budget.get("parity", {}).get("case_plans")
    contract = budget.get("score_contract")
    if (
        not isinstance(observations, list)
        or not isinstance(plans, list)
        or not isinstance(contract, Mapping)
    ):
        raise P1V3HeldoutJudgeError("judge inputs have invalid schema")
    expected_ids = {plan["case_id"] for plan in plans}
    observed_ids: set[str] = set()
    typed_correct = 0
    no_memory_correct = 0
    raw_correct = 0
    removed_correct = 0
    typed_disagreements = 0
    typed_improvements = 0
    all_arms_identical = 0
    physical_calls = 0
    parity_passed = True
    gold_boundary_passed = True
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise P1V3HeldoutJudgeError("observation must be a mapping")
        _verify_self_hash(observation, "observation_sha256", "observation")
        case_id = observation.get("case_id")
        if not isinstance(case_id, str) or case_id in observed_ids:
            raise P1V3HeldoutJudgeError("observation IDs are invalid")
        observed_ids.add(case_id)
        arms = observation.get("arms")
        call_budget = observation.get("budget")
        gold = observation.get("gold_boundary")
        if not isinstance(arms, Mapping) or set(arms) != set(ARM_IDS):
            raise P1V3HeldoutJudgeError("observation arm cut drifted")
        arm_rows = [arms[arm] for arm in ARM_IDS]
        if any(
            not isinstance(row, Mapping)
            or row.get("set_match") not in (0, 1)
            or row.get("logical_call_count") != 1
            for row in arm_rows
        ):
            raise P1V3HeldoutJudgeError("observation arm receipt drifted")
        physical_calls += sum(int(row["logical_call_count"]) for row in arm_rows)
        parity_passed &= (
            isinstance(call_budget, Mapping)
            and call_budget.get("logical_model_calls") == 4
            and call_budget.get("token_parity") is True
            and len({row.get("user_prompt_tokens") for row in arm_rows}) == 1
        )
        gold_boundary_passed &= (
            isinstance(gold, Mapping)
            and gold.get("gold_sent_to_answer_port") is False
            and gold.get("gold_opened_only_after_all_arm_answers") is True
            and gold.get("gold_values_published") is False
        )
        typed = arms["T1_typed_lesson"]
        raw = arms["T2_raw_transcript"]
        no_memory = arms["T3_no_memory"]
        removed = arms["T4_shuffled_or_removed"]
        typed_correct += int(typed["set_match"])
        raw_correct += int(raw["set_match"])
        no_memory_correct += int(no_memory["set_match"])
        removed_correct += int(removed["set_match"])
        changed = typed.get("answers_sha256") != no_memory.get("answers_sha256")
        typed_disagreements += int(changed)
        typed_improvements += int(
            changed and typed["set_match"] > no_memory["set_match"]
        )
        all_arms_identical += int(
            len({row.get("answers_sha256") for row in arm_rows}) == 1
        )
    required_cases = contract.get("required_valid_case_count")
    minimum_improvements = contract.get("minimum_typed_improvements_for_pass")
    gates = {
        "case_cut_exact": (
            observed_ids == expected_ids
            and len(observations) == required_cases
        ),
        "physical_call_budget_exact": physical_calls == len(observations) * 4,
        "exact_prompt_token_parity": parity_passed,
        "gold_boundary_preserved": gold_boundary_passed,
        "typed_improvement_threshold_met": (
            isinstance(minimum_improvements, int)
            and typed_improvements >= minimum_improvements
        ),
        "measurement_did_not_self_judge": True,
    }
    passed = all(gates.values())
    unsigned: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "verdict": "PASS" if passed else "KILL",
        "primary_metric": contract.get("primary_metric"),
        "value": typed_improvements,
        "baseline": contract.get("baseline"),
        "direction": contract.get("direction"),
        "minimum_typed_improvements_for_pass": minimum_improvements,
        "metrics": {
            "valid_case_count": len(observations),
            "typed_exact_set_match_count": typed_correct,
            "raw_transcript_exact_set_match_count": raw_correct,
            "no_memory_exact_set_match_count": no_memory_correct,
            "removed_exact_set_match_count": removed_correct,
            "typed_answer_disagreement_count": typed_disagreements,
            "typed_improvement_count_vs_no_memory": typed_improvements,
            "all_four_arms_identical_answer_count": all_arms_identical,
            "physical_model_calls": physical_calls,
        },
        "gate_checks": gates,
        "budget_manifest_sha256": budget["budget_manifest_sha256"],
        "evidence_sha256": evidence["evidence_sha256"],
        "judge_script_sha256": judge_script_sha256,
        "judge_type": "deterministic_non_llm",
        "scientific_verdict_emitted": True,
    }
    return {**unsigned, "judge_receipt_sha256": canonical_sha256(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    budget = json.loads(args.budget.read_text(encoding="utf-8"))
    receipt = judge_heldout(
        evidence=evidence,
        budget=budget,
        judge_script_sha256=file_sha256(Path(__file__).resolve()),
    )
    write_once(args.output, receipt)
    print(json.dumps({
        "output": str(args.output),
        "judge_receipt_sha256": receipt["judge_receipt_sha256"],
        "verdict": receipt["verdict"],
        "value": receipt["value"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["P1V3HeldoutJudgeError", "judge_heldout"]
