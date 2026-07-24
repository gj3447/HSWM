"""LakatoTree-compatible replay adapter for frozen HSWM heldout judges.

LakatoTree replays a producer with exactly one positional result path and
expects ``metric=<number>`` on stdout.  The result path accepted here is a
self-contained bundle: it embeds the measurement evidence and budget, binds
both by their canonical hashes, and binds the frozen P1v3 scoring contract by
the scorer module's file hash.  The adapter never accepts a client-supplied
metric; it derives the value again through the frozen deterministic judge.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from collections.abc import Mapping
from pathlib import Path
import sys

SCHEMA_VERSION = "hswm-p1v4-lakatotree-replay-bundle/v1"
SCORER_CONTRACT_ID = "p1v3-policy-heldout-judge/v1"
PRIMARY_METRIC = "typed_improvement_count_vs_no_memory"
P1V3_FROZEN_SCORER_SHA256 = (
    "3390d0da21adc7f94830c4a130c5378e3209f7e9c9a37ea0b73923d0d91dfa11"
)
ARM_IDS = (
    "T1_typed_lesson",
    "T2_raw_transcript",
    "T3_no_memory",
    "T4_shuffled_or_removed",
)
_BUNDLE_KEYS = {
    "schema_version",
    "scorer_contract",
    "evidence",
    "budget",
    "bundle_sha256",
}
_CONTRACT_KEYS = {
    "contract_id",
    "primary_metric",
    "scorer_sha256",
    "evidence_sha256",
    "budget_manifest_sha256",
}


class P1V4ReplayJudgeError(ValueError):
    """The replay bundle cannot regenerate a trustworthy metric."""


def _canonical_sha256(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise P1V4ReplayJudgeError(
            f"value is not canonical JSON: {error}"
        ) from error
    return sha256(payload).hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise P1V4ReplayJudgeError(f"{label} must be a mapping")
    return value


def _verify_self_hash(
    value: Mapping[str, object], key: str, label: str
) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(key, None)
    if not isinstance(declared, str) or _canonical_sha256(unsigned) != declared:
        raise P1V4ReplayJudgeError(f"{label} self-hash drifted")
    return declared


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


def _score_frozen_contract(
    evidence: Mapping[str, object], budget: Mapping[str, object]
) -> int:
    """Independent stdlib mirror of the frozen P1v3 primary-metric contract."""

    _verify_self_hash(evidence, "evidence_sha256", "measurement evidence")
    _verify_self_hash(budget, "budget_manifest_sha256", "heldout budget")
    if any(key.casefold() == "verdict" for key in _recursive_keys(evidence)):
        raise P1V4ReplayJudgeError("measurement evidence contains a verdict key")
    if evidence.get("budget_manifest_sha256") != budget.get(
        "budget_manifest_sha256"
    ):
        raise P1V4ReplayJudgeError("evidence binds a different budget")
    observations = evidence.get("observations")
    parity = budget.get("parity")
    contract = budget.get("score_contract")
    if (
        not isinstance(observations, list)
        or not isinstance(parity, Mapping)
        or not isinstance(parity.get("case_plans"), list)
        or not isinstance(contract, Mapping)
    ):
        raise P1V4ReplayJudgeError("judge inputs have invalid schema")
    plans = parity["case_plans"]
    try:
        expected_ids = {plan["case_id"] for plan in plans}
    except (KeyError, TypeError) as error:
        raise P1V4ReplayJudgeError("case plan schema drifted") from error
    observed_ids: set[str] = set()
    typed_improvements = 0
    physical_calls = 0
    parity_passed = True
    gold_boundary_passed = True
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise P1V4ReplayJudgeError("observation must be a mapping")
        _verify_self_hash(observation, "observation_sha256", "observation")
        case_id = observation.get("case_id")
        if not isinstance(case_id, str) or case_id in observed_ids:
            raise P1V4ReplayJudgeError("observation IDs are invalid")
        observed_ids.add(case_id)
        arms = observation.get("arms")
        call_budget = observation.get("budget")
        gold = observation.get("gold_boundary")
        if not isinstance(arms, Mapping) or set(arms) != set(ARM_IDS):
            raise P1V4ReplayJudgeError("observation arm cut drifted")
        arm_rows = [arms[arm] for arm in ARM_IDS]
        if any(
            not isinstance(row, Mapping)
            or row.get("set_match") not in (0, 1)
            or row.get("logical_call_count") != 1
            for row in arm_rows
        ):
            raise P1V4ReplayJudgeError("observation arm receipt drifted")
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
        no_memory = arms["T3_no_memory"]
        changed = typed.get("answers_sha256") != no_memory.get("answers_sha256")
        typed_improvements += int(
            changed and typed["set_match"] > no_memory["set_match"]
        )
    required_cases = contract.get("required_valid_case_count")
    validity_gates = {
        "case_cut_exact": (
            observed_ids == expected_ids and len(observations) == required_cases
        ),
        "physical_call_budget_exact": physical_calls == len(observations) * 4,
        "exact_prompt_token_parity": parity_passed,
        "gold_boundary_preserved": gold_boundary_passed,
    }
    failed = [name for name, passed in validity_gates.items() if not passed]
    if failed:
        raise P1V4ReplayJudgeError(
            "measurement validity gates failed: " + ",".join(failed)
        )
    if contract.get("primary_metric") != PRIMARY_METRIC:
        raise P1V4ReplayJudgeError("budget primary metric drifted")
    return typed_improvements


def build_replay_bundle(
    *, evidence: Mapping[str, object], budget: Mapping[str, object]
) -> dict[str, object]:
    """Build a sealed one-file input without copying a reported metric."""

    evidence_sha = _verify_self_hash(evidence, "evidence_sha256", "evidence")
    budget_sha = _verify_self_hash(
        budget, "budget_manifest_sha256", "budget manifest"
    )
    if evidence.get("budget_manifest_sha256") != budget_sha:
        raise P1V4ReplayJudgeError("evidence binds a different budget")
    unsigned: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scorer_contract": {
            "contract_id": SCORER_CONTRACT_ID,
            "primary_metric": PRIMARY_METRIC,
            "scorer_sha256": P1V3_FROZEN_SCORER_SHA256,
            "evidence_sha256": evidence_sha,
            "budget_manifest_sha256": budget_sha,
        },
        "evidence": dict(evidence),
        "budget": dict(budget),
    }
    return {**unsigned, "bundle_sha256": _canonical_sha256(unsigned)}


def replay_metric(bundle: Mapping[str, object]) -> float:
    """Verify every binding and deterministically regenerate the primary metric."""

    if set(bundle) != _BUNDLE_KEYS:
        raise P1V4ReplayJudgeError("replay bundle fields drifted")
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise P1V4ReplayJudgeError("replay bundle schema drifted")
    _verify_self_hash(bundle, "bundle_sha256", "replay bundle")
    contract = _require_mapping(bundle.get("scorer_contract"), "scorer contract")
    if set(contract) != _CONTRACT_KEYS:
        raise P1V4ReplayJudgeError("scorer contract fields drifted")
    if contract.get("contract_id") != SCORER_CONTRACT_ID:
        raise P1V4ReplayJudgeError("scorer contract identity drifted")
    if contract.get("primary_metric") != PRIMARY_METRIC:
        raise P1V4ReplayJudgeError("primary metric drifted")
    if contract.get("scorer_sha256") != P1V3_FROZEN_SCORER_SHA256:
        raise P1V4ReplayJudgeError("frozen scorer file drifted")
    evidence = _require_mapping(bundle.get("evidence"), "evidence")
    budget = _require_mapping(bundle.get("budget"), "budget")
    if evidence.get("evidence_sha256") != contract.get("evidence_sha256"):
        raise P1V4ReplayJudgeError("scorer contract binds different evidence")
    if budget.get("budget_manifest_sha256") != contract.get(
        "budget_manifest_sha256"
    ):
        raise P1V4ReplayJudgeError("scorer contract binds a different budget")
    value = _score_frozen_contract(evidence, budget)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P1V4ReplayJudgeError("frozen scorer returned a non-numeric metric")
    metric = float(value)
    if not math.isfinite(metric):
        raise P1V4ReplayJudgeError("frozen scorer returned a non-finite metric")
    return metric


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_path", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.result_path.read_text(encoding="utf-8"))
        metric = replay_metric(_require_mapping(payload, "replay bundle"))
    except (OSError, json.JSONDecodeError, P1V4ReplayJudgeError, ValueError) as error:
        print(f"replay_error={type(error).__name__}:{error}", file=sys.stderr)
        return 1
    print(f"metric={metric:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P1V4ReplayJudgeError",
    "P1V3_FROZEN_SCORER_SHA256",
    "build_replay_bundle",
    "replay_metric",
]
