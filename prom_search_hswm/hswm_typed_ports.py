"""Strict JSON ports for the PROM-9 LLM function network.

The validators in this module are deliberately small and dependency free.  A
model response is data until it passes one of these validators; free-form text
is never forwarded as an instruction to the next function.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


PORT_SCHEMA = "hswm-prom9-typed-port/v2"

#: Name of the declared, inert parity-filler field carried by every F1 input
#: envelope.  The field only ever holds repetitions of the manifest-declared
#: filler unit; it pads each call's prompt to the registered per-call input
#: envelope so that consumed-token parity holds by construction.
PARITY_FILLER_FIELD = "parity_filler"

MAX_FILLER_CHARS = 65536


class TypedPortError(ValueError):
    """A PROM-9 function input or output violates its frozen schema."""


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise TypedPortError(f"value is not canonical JSON: {error}") from error


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypedPortError(f"{label} must be an object")
    return dict(value)


def _keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        raise TypedPortError(
            f"{label} keys drifted: missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )


def _text(value: object, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        qualifier = "text" if empty else "non-empty text"
        raise TypedPortError(f"{label} must be {qualifier}")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise TypedPortError(f"{label} must be boolean")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TypedPortError(f"{label} must be a positive integer")
    return value


def _text_list(
    value: object,
    label: str,
    *,
    empty: bool = False,
    unique: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        raise TypedPortError(f"{label} must be an array")
    result = [_text(item, f"{label} item", empty=empty) for item in value]
    if unique and len(result) != len(set(result)):
        raise TypedPortError(f"{label} must not contain duplicates")
    return result


def _finite(value: object, label: str, *, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypedPortError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (maximum is not None and result > maximum):
        suffix = "" if maximum is None else f" and <= {maximum}"
        raise TypedPortError(f"{label} must be finite{suffix}")
    return 0.0 if result == 0.0 else result


def _json_value(value: object, label: str) -> object:
    # A canonical round trip rejects NaN, sets, bytes, custom objects, etc.
    try:
        return json.loads(canonical_json(value))
    except (json.JSONDecodeError, TypedPortError) as error:
        raise TypedPortError(f"{label} is not a JSON value") from error


def _parity_filler(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TypedPortError(f"{label} must be text")
    if len(value) > MAX_FILLER_CHARS:
        raise TypedPortError(f"{label} exceeds the filler character ceiling")
    return value


def _query_envelope(value: object) -> dict[str, object]:
    data = _object(value, "QueryEnvelopeV1")
    _keys(
        data,
        {"request_id", "query_text", "allowed_evidence_types", "budget", PARITY_FILLER_FIELD},
        "QueryEnvelopeV1",
    )
    budget = _object(data["budget"], "QueryEnvelopeV1 budget")
    _keys(
        budget,
        {"max_candidates", "max_evidence_items", "max_input_tokens", "max_output_tokens"},
        "QueryEnvelopeV1 budget",
    )
    return {
        "request_id": _text(data["request_id"], "request_id"),
        "query_text": _text(data["query_text"], "query_text"),
        "allowed_evidence_types": _text_list(
            data["allowed_evidence_types"], "allowed_evidence_types"
        ),
        "budget": {
            key: _positive_int(budget[key], f"budget {key}")
            for key in (
                "max_candidates",
                "max_evidence_items",
                "max_input_tokens",
                "max_output_tokens",
            )
        },
        PARITY_FILLER_FIELD: _parity_filler(data[PARITY_FILLER_FIELD], PARITY_FILLER_FIELD),
    }


def _query_plan(value: object) -> dict[str, object]:
    data = _object(value, "QueryPlanV1")
    _keys(
        data,
        {"request_id", "objectives", "required_evidence_types", "constraints", "abstain"},
        "QueryPlanV1",
    )
    return {
        "request_id": _text(data["request_id"], "request_id"),
        "objectives": _text_list(data["objectives"], "objectives"),
        "required_evidence_types": _text_list(
            data["required_evidence_types"], "required_evidence_types"
        ),
        "constraints": _text_list(data["constraints"], "constraints"),
        "abstain": _boolean(data["abstain"], "abstain"),
    }


def _candidate_table(value: object, label: str) -> dict[str, object]:
    """Validate a columnar candidate table.

    The table carries exactly the same information as the retired
    list-of-objects encoding: ``constants`` holds observable components that
    are identical across every row, ``columns`` names the per-row fields
    (``bond_id`` and ``evidence_id`` are mandatory), and ``rows`` holds one
    array per candidate.  Factoring the schema out of the rows removes
    repeated key names from the prompt without dropping any feature.
    """

    data = _object(value, label)
    _keys(data, {"constants", "columns", "rows"}, label)
    constants = _object(data["constants"], f"{label} constants")
    normalized_constants = {
        _text(key, f"{label} constant key"): _json_value(raw, f"{label} constant {key}")
        for key, raw in constants.items()
    }
    columns = _text_list(data["columns"], f"{label} columns")
    if "bond_id" not in columns or "evidence_id" not in columns:
        raise TypedPortError(f"{label} columns must include bond_id and evidence_id")
    bond_index = columns.index("bond_id")
    evidence_index = columns.index("evidence_id")
    rows = data["rows"]
    if not isinstance(rows, list) or not rows:
        raise TypedPortError(f"{label} rows must be a non-empty array")
    normalized_rows: list[list[object]] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, list) or len(raw) != len(columns):
            raise TypedPortError(f"{label} row {index} must cover every column")
        normalized_rows.append(
            [_json_value(cell, f"{label} row {index} cell") for cell in raw]
        )
        _text(normalized_rows[-1][bond_index], f"{label} row {index} bond_id")
        _text(normalized_rows[-1][evidence_index], f"{label} row {index} evidence_id")
    bond_ids = [str(row[bond_index]) for row in normalized_rows]
    evidence_ids = [str(row[evidence_index]) for row in normalized_rows]
    if len(bond_ids) != len(set(bond_ids)) or len(evidence_ids) != len(set(evidence_ids)):
        raise TypedPortError(f"{label} bond_id and evidence_id values must be unique")
    return {
        "constants": normalized_constants,
        "columns": columns,
        "rows": normalized_rows,
    }


def _bond_scoring_envelope(value: object) -> dict[str, object]:
    data = _object(value, "BondScoringEnvelopeV1")
    _keys(
        data,
        {"request_id", "query_plan", "candidate_table", "candidate_budget", PARITY_FILLER_FIELD},
        "BondScoringEnvelopeV1",
    )
    table = _candidate_table(data["candidate_table"], "BondScoringEnvelopeV1 candidate_table")
    budget = _positive_int(data["candidate_budget"], "candidate_budget")
    if budget > len(table["rows"]):
        raise TypedPortError("candidate_budget exceeds supplied candidates")
    return {
        "request_id": _text(data["request_id"], "request_id"),
        "query_plan": _query_plan(data["query_plan"]),
        "candidate_table": table,
        "candidate_budget": budget,
        PARITY_FILLER_FIELD: _parity_filler(data[PARITY_FILLER_FIELD], PARITY_FILLER_FIELD),
    }


def _bond_proposal(value: object) -> dict[str, object]:
    data = _object(value, "BondProposalV1")
    _keys(
        data,
        {"request_id", "ordered_bond_ids", "bond_potentials", "evidence_refs", "abstain"},
        "BondProposalV1",
    )
    ordered = _text_list(data["ordered_bond_ids"], "ordered_bond_ids")
    potentials = data["bond_potentials"]
    if not isinstance(potentials, Mapping):
        raise TypedPortError("bond_potentials must be an object")
    normalized_potentials = {
        _text(key, "bond_potential key"): _finite(raw, f"bond_potential {key}", maximum=0.0)
        for key, raw in potentials.items()
    }
    if set(normalized_potentials) != set(ordered):
        raise TypedPortError("bond_potentials must exactly cover ordered_bond_ids")
    return {
        "request_id": _text(data["request_id"], "request_id"),
        "ordered_bond_ids": ordered,
        "bond_potentials": normalized_potentials,
        "evidence_refs": _text_list(data["evidence_refs"], "evidence_refs"),
        "abstain": _boolean(data["abstain"], "abstain"),
    }


def _answer_context(value: object) -> dict[str, object]:
    data = _object(value, "AnswerContextV1")
    _keys(
        data,
        {"request_id", "query_text", "query_plan", "selected_evidence", "max_answer_tokens", PARITY_FILLER_FIELD},
        "AnswerContextV1",
    )
    evidence = data["selected_evidence"]
    if not isinstance(evidence, list):
        raise TypedPortError("selected_evidence must be an array")
    normalized: list[dict[str, str]] = []
    for index, raw in enumerate(evidence):
        row = _object(raw, f"selected evidence {index}")
        _keys(row, {"evidence_id", "content"}, f"selected evidence {index}")
        normalized.append(
            {
                "evidence_id": _text(row["evidence_id"], f"evidence {index} id"),
                "content": _text(row["content"], f"evidence {index} content"),
            }
        )
    ids = [row["evidence_id"] for row in normalized]
    if len(ids) != len(set(ids)):
        raise TypedPortError("selected evidence IDs must be unique")
    return {
        "request_id": _text(data["request_id"], "request_id"),
        "query_text": _text(data["query_text"], "query_text"),
        "query_plan": _query_plan(data["query_plan"]),
        "selected_evidence": normalized,
        "max_answer_tokens": _positive_int(data["max_answer_tokens"], "max_answer_tokens"),
        PARITY_FILLER_FIELD: _parity_filler(data[PARITY_FILLER_FIELD], PARITY_FILLER_FIELD),
    }


def _answer_envelope(value: object) -> dict[str, object]:
    data = _object(value, "AnswerEnvelopeV1")
    _keys(
        data,
        {"request_id", "answer", "supporting_evidence_ids", "uncertainty", "abstain"},
        "AnswerEnvelopeV1",
    )
    return {
        "request_id": _text(data["request_id"], "request_id"),
        "answer": _text(data["answer"], "answer", empty=True),
        "supporting_evidence_ids": _text_list(
            data["supporting_evidence_ids"], "supporting_evidence_ids"
        ),
        "uncertainty": _text(data["uncertainty"], "uncertainty", empty=True),
        "abstain": _boolean(data["abstain"], "abstain"),
    }


VALIDATORS = {
    "QueryEnvelopeV1": _query_envelope,
    "QueryPlanV1": _query_plan,
    "BondScoringEnvelopeV1": _bond_scoring_envelope,
    "BondProposalV1": _bond_proposal,
    "AnswerContextV1": _answer_context,
    "AnswerEnvelopeV1": _answer_envelope,
}


def validate_port(port_type: str, value: object) -> dict[str, object]:
    """Validate and normalize one known PROM-9 port value."""

    try:
        validator = VALIDATORS[port_type]
    except KeyError as error:
        raise TypedPortError(f"unsupported port type: {port_type}") from error
    return validator(value)


def port_digest(port_type: str, value: object) -> str:
    normalized = validate_port(port_type, value)
    return canonical_sha256(
        {"schema_version": PORT_SCHEMA, "port_type": port_type, "value": normalized}
    )


__all__ = [
    "MAX_FILLER_CHARS",
    "PARITY_FILLER_FIELD",
    "PORT_SCHEMA",
    "TypedPortError",
    "canonical_json",
    "canonical_sha256",
    "port_digest",
    "validate_port",
]
