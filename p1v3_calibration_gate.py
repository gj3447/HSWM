"""Development-only headroom gate for a future P1v3 heldout freeze.

The gate consumes only calibration observations and a list of future heldout
identifiers.  It proves that the no-memory arm is not at ceiling and that the
typed policy can change and improve at least one calibration decision.  It is
an environment-admission gate, not a scientific heldout judgment.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence

from hswm_weight_snapshot import canonical_sha256
from p1v2_prompt_parity import ARM_IDS


SCHEMA_VERSION = "hswm-p1v3-policy-calibration-gate/v1"


class PolicyCalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyCalibrationConfigV1:
    minimum_cases: int = 3
    maximum_no_memory_accuracy: float = 0.8
    minimum_typed_disagreements: int = 1
    minimum_typed_improvements: int = 1

    def __post_init__(self) -> None:
        if (
            not isinstance(self.minimum_cases, int)
            or isinstance(self.minimum_cases, bool)
            or self.minimum_cases <= 0
            or not isinstance(self.minimum_typed_disagreements, int)
            or isinstance(self.minimum_typed_disagreements, bool)
            or self.minimum_typed_disagreements <= 0
            or not isinstance(self.minimum_typed_improvements, int)
            or isinstance(self.minimum_typed_improvements, bool)
            or self.minimum_typed_improvements <= 0
            or not math.isfinite(self.maximum_no_memory_accuracy)
            or not 0 <= self.maximum_no_memory_accuracy < 1
        ):
            raise PolicyCalibrationError("calibration thresholds are invalid")

    def canonical(self) -> dict[str, object]:
        return {
            "minimum_cases": self.minimum_cases,
            "maximum_no_memory_accuracy": self.maximum_no_memory_accuracy,
            "minimum_typed_disagreements": self.minimum_typed_disagreements,
            "minimum_typed_improvements": self.minimum_typed_improvements,
        }


def _case_ids(values: Sequence[str], label: str) -> tuple[str, ...]:
    result = tuple(values)
    if (
        not result
        or any(not isinstance(value, str) or not value for value in result)
        or len(set(result)) != len(result)
    ):
        raise PolicyCalibrationError(f"{label} IDs must be unique non-empty strings")
    return result


def evaluate_policy_calibration(
    observations: Sequence[Mapping[str, object]],
    *,
    calibration_case_ids: Sequence[str],
    future_heldout_case_ids: Sequence[str],
    environment_sha256: str,
    config: PolicyCalibrationConfigV1 = PolicyCalibrationConfigV1(),
) -> dict[str, object]:
    """Evaluate headroom without accepting any future-heldout observation."""

    calibration_ids = _case_ids(calibration_case_ids, "calibration")
    heldout_ids = _case_ids(future_heldout_case_ids, "future heldout")
    if set(calibration_ids) & set(heldout_ids):
        raise PolicyCalibrationError("calibration and future heldout IDs overlap")
    if (
        not isinstance(environment_sha256, str)
        or len(environment_sha256) != 64
        or any(character not in "0123456789abcdef" for character in environment_sha256)
    ):
        raise PolicyCalibrationError("environment SHA-256 is invalid")
    if not isinstance(config, PolicyCalibrationConfigV1):
        raise PolicyCalibrationError("calibration config type drifted")
    if not observations:
        raise PolicyCalibrationError("calibration observations are empty")

    by_case: dict[str, Mapping[str, object]] = {}
    no_memory_correct = 0
    typed_correct = 0
    typed_disagreements = 0
    typed_improvements = 0
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise PolicyCalibrationError("calibration observation must be a mapping")
        case_id = observation.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in by_case:
            raise PolicyCalibrationError("calibration observation IDs are invalid")
        if case_id in heldout_ids:
            raise PolicyCalibrationError("future heldout outcome entered calibration")
        arms = observation.get("arms")
        budget = observation.get("budget")
        gold_boundary = observation.get("gold_boundary")
        if not isinstance(arms, Mapping) or set(arms) != set(ARM_IDS):
            raise PolicyCalibrationError("calibration arm cut drifted")
        if (
            not isinstance(budget, Mapping)
            or budget.get("logical_model_calls") != 4
            or budget.get("token_parity") is not True
        ):
            raise PolicyCalibrationError("calibration call/token parity failed")
        if (
            not isinstance(gold_boundary, Mapping)
            or gold_boundary.get("gold_sent_to_answer_port") is not False
            or gold_boundary.get("gold_opened_only_after_all_arm_answers") is not True
            or gold_boundary.get("gold_values_published") is not False
        ):
            raise PolicyCalibrationError("calibration gold boundary failed")
        for arm in ARM_IDS:
            row = arms[arm]
            if (
                not isinstance(row, Mapping)
                or row.get("set_match") not in (0, 1)
                or row.get("logical_call_count") != 1
            ):
                raise PolicyCalibrationError("calibration arm receipt drifted")
        typed = arms["T1_typed_lesson"]
        no_memory = arms["T3_no_memory"]
        changed = typed.get("answers_sha256") != no_memory.get("answers_sha256")
        no_memory_correct += int(no_memory["set_match"])
        typed_correct += int(typed["set_match"])
        typed_disagreements += int(changed)
        typed_improvements += int(
            changed and typed["set_match"] > no_memory["set_match"]
        )
        by_case[case_id] = observation

    if set(by_case) != set(calibration_ids):
        raise PolicyCalibrationError("observation cut differs from calibration IDs")
    case_count = len(by_case)
    no_memory_accuracy = no_memory_correct / case_count
    typed_accuracy = typed_correct / case_count
    reasons: list[str] = []
    if case_count < config.minimum_cases:
        reasons.append("insufficient_calibration_cases")
    if no_memory_accuracy > config.maximum_no_memory_accuracy:
        reasons.append("no_memory_baseline_at_or_near_ceiling")
    if typed_disagreements < config.minimum_typed_disagreements:
        reasons.append("typed_policy_did_not_change_enough_answers")
    if typed_improvements < config.minimum_typed_improvements:
        reasons.append("typed_policy_did_not_improve_enough_answers")
    passed = not reasons
    unsigned: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "stage": "DEVELOPMENT_ONLY_BEFORE_HELDOUT_FREEZE",
        "environment_sha256": environment_sha256,
        "config": config.canonical(),
        "calibration_case_ids": sorted(calibration_ids),
        "future_heldout_case_ids_sha256": canonical_sha256({
            "case_ids": sorted(heldout_ids)
        }),
        "heldout_outcomes_inspected": False,
        "metrics": {
            "case_count": case_count,
            "no_memory_exact_set_match_count": no_memory_correct,
            "no_memory_exact_set_match_rate": no_memory_accuracy,
            "typed_exact_set_match_count": typed_correct,
            "typed_exact_set_match_rate": typed_accuracy,
            "typed_answer_disagreement_count": typed_disagreements,
            "typed_improvement_count": typed_improvements,
        },
        "gate_status": "CALIBRATION_PASS" if passed else "CALIBRATION_REJECT",
        "heldout_freeze_authorized": passed,
        "reasons": reasons,
        "scientific_judgment_emitted": False,
    }
    return {**unsigned, "calibration_receipt_sha256": canonical_sha256(unsigned)}


__all__ = [
    "PolicyCalibrationConfigV1",
    "PolicyCalibrationError",
    "evaluate_policy_calibration",
]
