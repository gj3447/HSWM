"""Validate the local PROM-9 typed-function protocol.

PROM-9 specifies how typed LLM functions and three-factor bond plasticity are
to be tested.  This module does not run models, inspect benchmark outcomes,
register predictions, or submit scientific results. It checks only the local
causal and equal-budget invariants; external adjudication and ordered-gate
packet generation are intentionally absent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence


PROTOCOL_SCHEMA = "hswm-prom9-semantic-neural-network/v1"
DEFAULT_PROTOCOL = Path("prom_search_hswm/prom9_semantic_neural_network.v1.json")

REQUIRED_STAGE_IDS = (
    "F1_TYPED_FUNCTION_NETWORK",
    "G0_REAL_PACKS",
    "P1V5_FAST_TO_SLOW_PLASTICITY",
    "P2_FROZEN_AGENT_TRANSFER",
)
REQUIRED_FUNCTION_IDS = (
    "QF_QUERY_COMPILER",
    "BF_BOND_PROPOSER",
    "AF_ANSWER_SYNTHESIZER",
)


class Prom9ProtocolError(RuntimeError):
    """PROM-9 is malformed or a requested stage is not currently admissible."""


def canonical_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise Prom9ProtocolError(f"value is not canonical JSON: {error}") from error
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise Prom9ProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except Prom9ProtocolError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Prom9ProtocolError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise Prom9ProtocolError(f"{label} must be a JSON object")
    return value


def _strict_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        raise Prom9ProtocolError(
            f"{label} keys drifted: missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Prom9ProtocolError(f"{label} must be non-empty text")
    return value


def _text_list(value: object, label: str, *, minimum: int = 1) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise Prom9ProtocolError(f"{label} must contain unique non-empty text")
    return list(value)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise Prom9ProtocolError(f"{label} must be a positive integer")
    return value


def _validate_stage(raw: Mapping[str, object], index: int) -> dict[str, object]:
    label = f"stage {index}"
    _strict_keys(
        raw,
        {
            "id",
            "order",
            "lane",
            "status_gate",
            "depends_on",
            "purpose",
            "permitted_actions",
            "forbidden_actions",
            "required_inputs",
            "exit_evidence",
        },
        label,
    )
    stage_id = _text(raw.get("id"), f"{label} id")
    _positive_int(raw.get("order"), f"{stage_id} order")
    for field in ("lane", "status_gate", "purpose"):
        _text(raw.get(field), f"{stage_id} {field}")
    dependencies = _text_list(raw.get("depends_on"), f"{stage_id} depends_on", minimum=0)
    for field in (
        "permitted_actions",
        "forbidden_actions",
        "required_inputs",
        "exit_evidence",
    ):
        _text_list(raw.get(field), f"{stage_id} {field}")
    normalized = dict(raw)
    normalized["depends_on"] = dependencies
    return normalized


def _validate_function(raw: Mapping[str, object], index: int) -> dict[str, object]:
    label = f"LLM function {index}"
    _strict_keys(
        raw,
        {
            "id",
            "role",
            "model_policy",
            "input_type",
            "output_type",
            "reads",
            "writes",
            "prompt",
            "abstention",
            "forbidden",
        },
        label,
    )
    function_id = _text(raw.get("id"), f"{label} id")
    for field in (
        "role",
        "model_policy",
        "input_type",
        "output_type",
        "prompt",
        "abstention",
    ):
        _text(raw.get(field), f"{function_id} {field}")
    _text_list(raw.get("reads"), f"{function_id} reads")
    _text_list(raw.get("writes"), f"{function_id} writes")
    _text_list(raw.get("forbidden"), f"{function_id} forbidden")
    prompt = str(raw["prompt"])
    if "JSON" not in prompt or "scientific verdict" not in prompt:
        raise Prom9ProtocolError(
            f"{function_id} prompt must freeze JSON output and deny verdict authority"
        )
    return dict(raw)


def validate_protocol(value: Mapping[str, object]) -> dict[str, object]:
    """Validate the complete PROM-9 contract and return a normalized copy."""

    _strict_keys(
        value,
        {
            "schema_version",
            "programme",
            "status",
            "claim_boundary",
            "question",
            "execution_model",
            "stages",
            "llm_functions",
            "arm_matrix",
            "budget_contract",
            "evaluation",
            "conclusion_rules",
            "kill_conditions",
            "external_governance",
        },
        "PROM-9 protocol",
    )
    if value.get("schema_version") != PROTOCOL_SCHEMA:
        raise Prom9ProtocolError("unsupported PROM-9 schema")
    if value.get("status") != "DESIGN_LOCKED_NOT_PREREGISTERED":
        raise Prom9ProtocolError("PROM-9 status crossed its preregistration boundary")
    for field in ("programme", "claim_boundary", "question"):
        _text(value.get(field), f"PROM-9 {field}")

    execution = value.get("execution_model")
    if not isinstance(execution, dict):
        raise Prom9ProtocolError("execution_model must be an object")
    _strict_keys(
        execution,
        {
            "node_equation",
            "forward_path",
            "learning_path",
            "durable_state",
            "non_learning_state",
            "evaluator",
        },
        "execution_model",
    )
    for field in ("node_equation", "forward_path", "learning_path", "evaluator"):
        _text(execution.get(field), f"execution_model {field}")
    _text_list(execution.get("durable_state"), "execution_model durable_state")
    _text_list(execution.get("non_learning_state"), "execution_model non_learning_state")
    if "external" not in str(execution["evaluator"]).lower():
        raise Prom9ProtocolError("PROM-9 evaluator must be external")

    raw_stages = value.get("stages")
    if not isinstance(raw_stages, list):
        raise Prom9ProtocolError("stages must be a list")
    stages = [_validate_stage(raw, index) if isinstance(raw, dict) else None
              for index, raw in enumerate(raw_stages)]
    if any(stage is None for stage in stages):
        raise Prom9ProtocolError("every stage must be an object")
    typed_stages = [stage for stage in stages if stage is not None]
    ids = tuple(str(stage["id"]) for stage in typed_stages)
    if ids != REQUIRED_STAGE_IDS:
        raise Prom9ProtocolError(
            f"PROM-9 stage order drifted: expected={REQUIRED_STAGE_IDS}, observed={ids}"
        )
    seen: set[str] = set()
    for stage in typed_stages:
        stage_id = str(stage["id"])
        forward = [item for item in stage["depends_on"] if item not in seen]
        if forward:
            raise Prom9ProtocolError(f"{stage_id} has missing/forward dependencies: {forward}")
        seen.add(stage_id)

    raw_functions = value.get("llm_functions")
    if not isinstance(raw_functions, list):
        raise Prom9ProtocolError("llm_functions must be a list")
    functions = [_validate_function(raw, index) if isinstance(raw, dict) else None
                 for index, raw in enumerate(raw_functions)]
    if any(function is None for function in functions):
        raise Prom9ProtocolError("every LLM function must be an object")
    typed_functions = [function for function in functions if function is not None]
    function_ids = tuple(str(function["id"]) for function in typed_functions)
    if function_ids != REQUIRED_FUNCTION_IDS:
        raise Prom9ProtocolError(
            "PROM-9 requires exactly the frozen query-compiler, bond-proposer, "
            "and answer-synthesizer roles"
        )
    output_types = [str(function["output_type"]) for function in typed_functions]
    if len(output_types) != len(set(output_types)):
        raise Prom9ProtocolError("LLM function output types must be distinct")

    arms = value.get("arm_matrix")
    if not isinstance(arms, dict):
        raise Prom9ProtocolError("arm_matrix must be an object")
    _strict_keys(arms, {"F1", "P1V5", "P2"}, "arm_matrix")
    for name in ("F1", "P1V5", "P2"):
        _text_list(arms.get(name), f"arm_matrix {name}", minimum=5)
    if not any("role_removed" in arm for arm in arms["F1"]):
        raise Prom9ProtocolError("F1 arm matrix lacks role removal")
    if not any("role_instructions_shuffled" in arm for arm in arms["F1"]):
        raise Prom9ProtocolError("F1 arm matrix lacks role shuffle")
    if not any("causal_removal" in arm for arm in arms["P1V5"]):
        raise Prom9ProtocolError("P1v5 arm matrix lacks causal removal")

    budget = value.get("budget_contract")
    if not isinstance(budget, dict):
        raise Prom9ProtocolError("budget_contract must be an object")
    _strict_keys(
        budget,
        {
            "llm_calls_per_item",
            "call_parity",
            "token_parity",
            "retrieval_parity",
            "state_parity",
            "cost_ledger",
        },
        "budget_contract",
    )
    if _positive_int(budget.get("llm_calls_per_item"), "llm_calls_per_item") != 3:
        raise Prom9ProtocolError("PROM-9 freezes exactly three calls per F1 arm")
    for field in (
        "call_parity",
        "token_parity",
        "retrieval_parity",
        "state_parity",
        "cost_ledger",
    ):
        _text(budget.get(field), f"budget_contract {field}")

    evaluation = value.get("evaluation")
    if not isinstance(evaluation, dict):
        raise Prom9ProtocolError("evaluation must be an object")
    _strict_keys(
        evaluation,
        {"split_contract", "primary_metrics", "promotion_gates", "reporting"},
        "evaluation",
    )
    _text(evaluation.get("split_contract"), "evaluation split_contract")
    _text(evaluation.get("reporting"), "evaluation reporting")
    _text_list(evaluation.get("promotion_gates"), "evaluation promotion_gates")
    metrics = evaluation.get("primary_metrics")
    if not isinstance(metrics, dict):
        raise Prom9ProtocolError("primary_metrics must be an object")
    _strict_keys(metrics, {"F1", "P1V5", "P2"}, "primary_metrics")
    for name in ("F1", "P1V5", "P2"):
        _text(metrics.get(name), f"primary metric {name}")

    _text_list(value.get("conclusion_rules"), "conclusion_rules", minimum=6)
    _text_list(value.get("kill_conditions"), "kill_conditions", minimum=6)

    external_governance = value.get("external_governance")
    if not isinstance(external_governance, dict):
        raise Prom9ProtocolError("external_governance must be an object")
    _strict_keys(
        external_governance,
        {
            "authority",
            "prediction_registration_required",
            "result_submission_allowed",
        },
        "external_governance",
    )
    if (
        external_governance.get("authority") != "NONE"
        or external_governance.get("prediction_registration_required") is not False
        or external_governance.get("result_submission_allowed") is not False
    ):
        raise Prom9ProtocolError("PROM-9 must remain free of external governance")

    return json.loads(json.dumps(value, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)

    args = parser.parse_args(argv)
    try:
        protocol_path = Path(args.protocol).resolve()
        protocol = read_json(protocol_path, "PROM-9 protocol")
        normalized = validate_protocol(protocol)
        result: dict[str, object] = {
            "status": "PROM9_PROTOCOL_VALID",
            "protocol_sha256": file_sha256(protocol_path),
            "stage_ids": [stage["id"] for stage in normalized["stages"]],
            "function_ids": [function["id"] for function in normalized["llm_functions"]],
            "external_governance_authority": "NONE",
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Prom9ProtocolError as error:
        print(
            json.dumps(
                {"status": "REFUSED", "reason": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_PROTOCOL",
    "PROTOCOL_SCHEMA",
    "Prom9ProtocolError",
    "canonical_sha256",
    "file_sha256",
    "read_json",
    "validate_protocol",
]
