"""Validate PROM-9 and prepare fail-closed engineering stage packets.

PROM-9 specifies how typed LLM functions and three-factor bond plasticity are
to be tested.  This module does not run models, inspect benchmark outcomes,
register predictions, or submit scientific results.  It checks the protocol's
causal/equal-budget invariants and binds a requested stage to the independently
generated next-research status receipt.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from hswm_next_research_harness import verify_status


PROTOCOL_SCHEMA = "hswm-prom9-semantic-neural-network/v1"
PACKET_SCHEMA = "hswm-prom9-stage-packet/v1"
DEFAULT_PROTOCOL = Path("prom_search_hswm/prom9_semantic_neural_network.v1.json")

REQUIRED_STAGE_IDS = (
    "G0_REAL_PACKS",
    "F1_TYPED_FUNCTION_NETWORK",
    "P1V5_FAST_TO_SLOW_PLASTICITY",
    "P2_FROZEN_AGENT_TRANSFER",
)
REQUIRED_FUNCTION_IDS = (
    "QF_QUERY_COMPILER",
    "BF_BOND_PROPOSER",
    "AF_ANSWER_SYNTHESIZER",
)
EXPECTED_STATUS_GATES = {
    "G0_REAL_PACKS": "B22_GATE0_REAL_PACKS",
    "F1_TYPED_FUNCTION_NETWORK": "F1_MULTI_LLM_FUNCTION_NETWORK",
    "P1V5_FAST_TO_SLOW_PLASTICITY": "P1V5_THREE_FACTOR_BOND_PLASTICITY",
    "P2_FROZEN_AGENT_TRANSFER": "P2_AGENT_A_TO_FROZEN_B_TRANSFER",
}


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
            "lakatotree",
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
        if stage["status_gate"] != EXPECTED_STATUS_GATES[stage_id]:
            raise Prom9ProtocolError(f"{stage_id} status gate drifted")
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

    lakatotree = value.get("lakatotree")
    if not isinstance(lakatotree, dict):
        raise Prom9ProtocolError("lakatotree must be an object")
    _strict_keys(
        lakatotree,
        {
            "tree",
            "parent",
            "registration_mode",
            "prediction_registration_required_before",
            "scientific_prediction_registered_by_this_protocol",
            "scientific_result_submitted_by_this_protocol",
        },
        "lakatotree",
    )
    for field in ("tree", "parent", "registration_mode"):
        _text(lakatotree.get(field), f"lakatotree {field}")
    _text_list(
        lakatotree.get("prediction_registration_required_before"),
        "lakatotree prediction_registration_required_before",
        minimum=2,
    )
    if (
        lakatotree.get("scientific_prediction_registered_by_this_protocol") is not False
        or lakatotree.get("scientific_result_submitted_by_this_protocol") is not False
    ):
        raise Prom9ProtocolError("PROM-9 crossed its scientific authority boundary")

    return json.loads(json.dumps(value, ensure_ascii=False))


def _validate_recorded_at(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise Prom9ProtocolError("recorded_at must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise Prom9ProtocolError("recorded_at must carry a UTC offset")
    return value


def _status_rows(status: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    try:
        verify_status(status)
    except Exception as error:
        raise Prom9ProtocolError(f"invalid next-research status receipt: {error}") from error
    rows = status.get("gates")
    if not isinstance(rows, list):
        raise Prom9ProtocolError("status receipt lacks gates")
    indexed: dict[str, Mapping[str, object]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise Prom9ProtocolError(f"status gate {index} is invalid")
        gate_id = _text(row.get("id"), f"status gate {index} id")
        if gate_id in indexed:
            raise Prom9ProtocolError(f"duplicate status gate: {gate_id}")
        indexed[gate_id] = row
    return indexed


def build_stage_packet(
    *,
    protocol: Mapping[str, object],
    protocol_sha256: str,
    status: Mapping[str, object],
    stage_id: str,
    run_id: str,
    recorded_at: str | None = None,
) -> dict[str, object]:
    """Bind one currently runnable stage to the verified status receipt.

    The returned packet authorizes preparation only.  It can never authorize a
    sealed scientific measurement or model/topology activation.
    """

    normalized = validate_protocol(protocol)
    if (
        not isinstance(protocol_sha256, str)
        or len(protocol_sha256) != 64
        or any(character not in "0123456789abcdef" for character in protocol_sha256)
    ):
        raise Prom9ProtocolError("protocol_sha256 must be a lowercase SHA-256")
    run_id = _text(run_id, "run_id")
    stages = {stage["id"]: stage for stage in normalized["stages"]}
    if stage_id not in stages:
        raise Prom9ProtocolError(f"unknown PROM-9 stage: {stage_id}")
    stage = stages[stage_id]
    rows = _status_rows(status)
    status_gate = str(stage["status_gate"])
    if status_gate not in rows:
        raise Prom9ProtocolError(f"status receipt lacks PROM-9 gate: {status_gate}")
    observed_state = rows[status_gate].get("state")
    allowed_states = (
        {"ACTION_REQUIRED", "READY"}
        if stage_id == "G0_REAL_PACKS"
        else {"READY"}
    )
    if observed_state not in allowed_states:
        raise Prom9ProtocolError(
            f"PROM-9 stage {stage_id} is not runnable: "
            f"status gate {status_gate} is {observed_state}"
        )
    status_sha = verify_status(status)
    included_functions = (
        normalized["llm_functions"]
        if stage_id in {"F1_TYPED_FUNCTION_NETWORK", "P2_FROZEN_AGENT_TRANSFER"}
        else []
    )
    next_authority = {
        "G0_REAL_PACKS": "Three-pack Gate-0 acceptance receipt",
        "F1_TYPED_FUNCTION_NETWORK": (
            "Frozen implementation, prompt, model, split, and equal-budget manifests "
            "before any sealed F1 evaluation"
        ),
        "P1V5_FAST_TO_SLOW_PLASTICITY": (
            "LakatoTree prediction receipt registered before sealed P1v5 measurement"
        ),
        "P2_FROZEN_AGENT_TRANSFER": (
            "LakatoTree prediction receipt registered before sealed P2 measurement"
        ),
    }[stage_id]
    unsigned: dict[str, object] = {
        "schema_version": PACKET_SCHEMA,
        "programme": normalized["programme"],
        "run_id": run_id,
        "recorded_at": _validate_recorded_at(recorded_at),
        "stage": stage,
        "status_gate_state": observed_state,
        "protocol_sha256": protocol_sha256,
        "status_receipt_sha256": status_sha,
        "llm_functions": included_functions,
        "arm_matrix": normalized["arm_matrix"],
        "budget_contract": normalized["budget_contract"],
        "evaluation": normalized["evaluation"],
        "next_required_authority": next_authority,
        "preparation_allowed": True,
        "sealed_measurement_allowed": False,
        "activation_allowed": False,
        "scientific_prediction_registered": False,
        "scientific_result_submitted": False,
        "claim_boundary": normalized["claim_boundary"],
    }
    return {**unsigned, "packet_sha256": canonical_sha256(unsigned)}


def verify_stage_packet(value: Mapping[str, object]) -> str:
    if value.get("schema_version") != PACKET_SCHEMA:
        raise Prom9ProtocolError("unsupported PROM-9 stage packet schema")
    for field in (
        "sealed_measurement_allowed",
        "activation_allowed",
        "scientific_prediction_registered",
        "scientific_result_submitted",
    ):
        if value.get(field) is not False:
            raise Prom9ProtocolError(f"PROM-9 stage packet crossed boundary: {field}")
    unsigned = dict(value)
    declared = unsigned.pop("packet_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise Prom9ProtocolError("PROM-9 stage packet self-hash drifted")
    return declared


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise Prom9ProtocolError(f"refusing to replace PROM-9 packet: {path}") from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    prepare_parser.add_argument("--status", type=Path, required=True)
    prepare_parser.add_argument("--stage", choices=REQUIRED_STAGE_IDS, required=True)
    prepare_parser.add_argument("--run-id", required=True)
    prepare_parser.add_argument("--recorded-at")
    prepare_parser.add_argument("--output", type=Path)

    args = parser.parse_args(argv)
    try:
        protocol_path = Path(args.protocol).resolve()
        protocol = read_json(protocol_path, "PROM-9 protocol")
        normalized = validate_protocol(protocol)
        if args.command == "validate":
            result: dict[str, object] = {
                "status": "PROM9_PROTOCOL_VALID",
                "protocol_sha256": file_sha256(protocol_path),
                "stage_ids": [stage["id"] for stage in normalized["stages"]],
                "function_ids": [function["id"] for function in normalized["llm_functions"]],
                "scientific_prediction_registered": False,
            }
        else:
            status = read_json(Path(args.status), "next-research status")
            result = build_stage_packet(
                protocol=normalized,
                protocol_sha256=file_sha256(protocol_path),
                status=status,
                stage_id=args.stage,
                run_id=args.run_id,
                recorded_at=args.recorded_at,
            )
            if args.output:
                _write_once(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Prom9ProtocolError as error:
        print(
            json.dumps(
                {"status": "REFUSED", "reason": str(error)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=os.sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_PROTOCOL",
    "PACKET_SCHEMA",
    "PROTOCOL_SCHEMA",
    "Prom9ProtocolError",
    "build_stage_packet",
    "canonical_sha256",
    "file_sha256",
    "read_json",
    "validate_protocol",
    "verify_stage_packet",
]
