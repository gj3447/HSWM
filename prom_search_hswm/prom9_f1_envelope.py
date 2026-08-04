"""Registered F1 token envelope: caps, filler spec, and pre-run projection.

The PROM-9 budget contract requires one registered total input-plus-output
token cap per item before measurement, with non-semantic control context
padded or truncated under declaration.  This module is the fail-closed core
of that contract:

* :func:`validate_token_envelope` structurally validates the manifest block.
* :func:`check_tokenizer_identity` binds the manifest to one exact tokenizer.
* :func:`enforce_projection` recomputes, per item, arm, and call, an upper
  bound of the natural (unpadded) prompt tokens and rejects the manifest when
  any bound exceeds the registered per-call input caps, or when the declared
  per-arm output projections already spread wider than the token tolerance.
* :func:`compute_minimum_input_caps` derives the smallest feasible caps, so
  builders register tight envelopes instead of convenient ones.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_function_network import (
    TYPED_ARM,
    CallEnvelopeV1,
    FunctionNetworkItemV1,
    answer_context_payload,
    bond_scoring_payload,
    query_envelope_payload,
    request_id_for,
)
from prom_search_hswm.hswm_function_registry import FunctionRegistryV1
from prom_search_hswm.hswm_token_meter import TokenMeter
from prom_search_hswm.hswm_typed_ports import (
    MAX_FILLER_CHARS,
    PARITY_FILLER_FIELD,
    canonical_json,
)


ENVELOPE_SCHEMA = "hswm-prom9-f1-token-envelope/v1"


class EnvelopeError(RuntimeError):
    """The registered token envelope is malformed or infeasible."""


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeError(f"{label} must be non-empty text")
    return value


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise EnvelopeError(f"{label} must be a lowercase SHA-256")
    return text


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise EnvelopeError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EnvelopeError(f"{label} must be a non-negative integer")
    return value


def _keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise EnvelopeError(
            f"{label} keys drifted: missing={sorted(expected-set(value))}, "
            f"extra={sorted(set(value)-expected)}"
        )


def _call_triplet(value: object, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise EnvelopeError(f"{label} must be an object")
    _keys(value, {"1", "2", "3"}, label)
    return {key: _positive_int(value[key], f"{label} call {key}") for key in ("1", "2", "3")}


def validate_token_envelope(
    value: object, *, arms: Sequence[str]
) -> dict[str, object]:
    """Structurally validate the manifest ``token_envelope`` block."""

    if not isinstance(value, dict):
        raise EnvelopeError("token_envelope must be an object")
    _keys(
        value,
        {
            "schema_version",
            "tokenizer",
            "filler",
            "per_call_input_caps",
            "per_call_output_caps",
            "projected_output_tokens_by_arm",
            "projection_slack_tokens",
        },
        "token_envelope",
    )
    if value.get("schema_version") != ENVELOPE_SCHEMA:
        raise EnvelopeError("unsupported token envelope schema")
    tokenizer = value["tokenizer"]
    if not isinstance(tokenizer, dict):
        raise EnvelopeError("token_envelope tokenizer must be an object")
    if "validation_receipt_sha256" in tokenizer:
        _sha(tokenizer["validation_receipt_sha256"], "tokenizer validation receipt")
    filler = value["filler"]
    if not isinstance(filler, dict):
        raise EnvelopeError("token_envelope filler must be an object")
    _keys(filler, {"field", "unit", "max_filler_chars"}, "token_envelope filler")
    if filler["field"] != PARITY_FILLER_FIELD:
        raise EnvelopeError(f"filler field must be the canonical {PARITY_FILLER_FIELD}")
    _text(filler["unit"], "filler unit")
    max_filler_chars = _nonnegative_int(filler["max_filler_chars"], "max filler chars")
    if max_filler_chars > MAX_FILLER_CHARS:
        raise EnvelopeError("max filler chars exceeds the port ceiling")
    input_caps = _call_triplet(value["per_call_input_caps"], "per_call_input_caps")
    output_caps = _call_triplet(value["per_call_output_caps"], "per_call_output_caps")
    projections = value["projected_output_tokens_by_arm"]
    if not isinstance(projections, dict) or set(projections) != set(arms):
        raise EnvelopeError("projected_output_tokens_by_arm must exactly cover F1 arms")
    normalized_projections: dict[str, dict[str, int]] = {}
    for arm in arms:
        triplet = _call_triplet(projections[arm], f"projected outputs for {arm}")
        for call_index, projected in triplet.items():
            if projected > output_caps[call_index]:
                raise EnvelopeError(
                    f"projected output for {arm} call {call_index} exceeds its output cap"
                )
        normalized_projections[arm] = triplet
    slack = _nonnegative_int(value["projection_slack_tokens"], "projection slack")
    return {
        "schema_version": ENVELOPE_SCHEMA,
        "tokenizer": dict(tokenizer),
        "filler": {
            "field": PARITY_FILLER_FIELD,
            "unit": str(filler["unit"]),
            "max_filler_chars": max_filler_chars,
        },
        "per_call_input_caps": input_caps,
        "per_call_output_caps": output_caps,
        "projected_output_tokens_by_arm": normalized_projections,
        "projection_slack_tokens": slack,
    }


def check_tokenizer_identity(declared: Mapping[str, object], meter: TokenMeter) -> None:
    """Bind the manifest to exactly the supplied meter, or refuse to run."""

    identity = meter.identity()
    expected_keys = set(identity) | {"validation_receipt_sha256"}
    if set(declared) != expected_keys:
        raise EnvelopeError(
            "tokenizer identity keys drifted: "
            f"missing={sorted(expected_keys-set(declared))}, "
            f"extra={sorted(set(declared)-expected_keys)}"
        )
    for key, expected in identity.items():
        if declared.get(key) != expected:
            raise EnvelopeError(f"tokenizer identity drifted for {key}")
    _sha(declared.get("validation_receipt_sha256"), "tokenizer validation receipt")


def envelope_spec(envelope: Mapping[str, object], meter: TokenMeter) -> CallEnvelopeV1:
    """Build the runtime call envelope from a validated manifest block."""

    input_caps = envelope["per_call_input_caps"]
    output_caps = envelope["per_call_output_caps"]
    filler = envelope["filler"]
    return CallEnvelopeV1(
        input_caps=(input_caps["1"], input_caps["2"], input_caps["3"]),
        output_caps=(output_caps["1"], output_caps["2"], output_caps["3"]),
        filler_field=str(filler["field"]),
        filler_unit=str(filler["unit"]),
        max_filler_chars=int(filler["max_filler_chars"]),
        meter=meter,
    )


def _minimal_plan(request_id: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "objectives": [],
        "required_evidence_types": [],
        "constraints": [],
        "abstain": True,
    }


def project_item_call_upper_bounds(
    *,
    run_id: str,
    item: FunctionNetworkItemV1,
    arm_id: str,
    registries: Mapping[str, FunctionRegistryV1],
    meter: TokenMeter,
    projected_outputs: Mapping[str, Mapping[str, int]],
    slack: int,
) -> tuple[int, int, int]:
    """Upper-bound the natural prompt tokens of each call for one arm.

    Call 1 is exact: its payload depends only on the item.  Calls 2 and 3 add
    the declared per-arm QF output projection plus the registered slack to
    cover the not-yet-produced query plan; call 3 additionally uses the exact
    worst-case selection (the longest admissible evidence contents), so no
    model choice can push a feasible envelope over its cap.
    """

    request_id = request_id_for(run_id, arm_id, item.item_id)
    registry = registries[arm_id]
    plan_tokens = projected_outputs[arm_id]["1"]
    bound_1 = meter.count_chat_prompt(
        registry.by_id("QF_QUERY_COMPILER").prompt,
        canonical_json(query_envelope_payload(item=item, request_id=request_id)),
    )
    bound_2 = (
        meter.count_chat_prompt(
            registry.by_id("BF_BOND_PROPOSER").prompt,
            canonical_json(
                bond_scoring_payload(
                    item=item,
                    arm_id=arm_id,
                    request_id=request_id,
                    query_plan=_minimal_plan(request_id),
                )
            ),
        )
        + plan_tokens
        + slack
    )
    worst = sorted(
        item.candidates,
        key=lambda candidate: meter.count_text(candidate.content),
        reverse=True,
    )[: item.max_evidence_items]
    worst_links = None
    if arm_id == TYPED_ARM and len(worst) >= 2:
        worst_links = [
            {
                "evidence_id_a": first.evidence_id,
                "evidence_id_b": second.evidence_id,
                "bridge": "0" * 64,
            }
            for first, second in zip(worst, worst[1:], strict=False)
        ]
        if len(worst) >= 3:
            worst_links.append(
                {
                    "evidence_id_a": worst[0].evidence_id,
                    "evidence_id_b": worst[2].evidence_id,
                    "bridge": "0" * 64,
                }
            )
    bound_3 = (
        meter.count_chat_prompt(
            registry.by_id("AF_ANSWER_SYNTHESIZER").prompt,
            canonical_json(
                answer_context_payload(
                    item=item,
                    request_id=request_id,
                    query_plan=_minimal_plan(request_id),
                    selected=worst,
                    composition_links=worst_links,
                )
            ),
        )
        + plan_tokens
        + slack
    )
    return (bound_1, bound_2, bound_3)


def enforce_projection(
    *,
    run_id: str,
    items: Sequence[FunctionNetworkItemV1],
    arms: Sequence[str],
    registries: Mapping[str, FunctionRegistryV1],
    meter: TokenMeter,
    envelope: Mapping[str, object],
    token_tolerance: int,
) -> dict[str, object]:
    """Fail-closed pre-run envelope check.

    Rejects the manifest when any item's projected natural prompt tokens
    exceed the registered per-call input caps, when the caps violate an
    item's own budgets, or when the declared per-arm output projections
    already spread wider than the registered token tolerance.  Returns the
    projection record that run receipts carry for audit.
    """

    input_caps = envelope["per_call_input_caps"]
    output_caps = envelope["per_call_output_caps"]
    projections = envelope["projected_output_tokens_by_arm"]
    slack = int(envelope["projection_slack_tokens"])
    total_input_cap = input_caps["1"] + input_caps["2"] + input_caps["3"]
    records: list[dict[str, object]] = []
    for item in items:
        if total_input_cap > item.max_input_tokens:
            raise EnvelopeError(
                f"item {item.item_id}: registered input caps exceed the item input budget"
            )
        for call_index in ("1", "2", "3"):
            if output_caps[call_index] > item.max_output_tokens_per_call:
                raise EnvelopeError(
                    f"item {item.item_id}: output cap for call {call_index} "
                    "exceeds the item output budget"
                )
        per_arm: dict[str, list[int]] = {}
        for arm in arms:
            bounds = project_item_call_upper_bounds(
                run_id=run_id,
                item=item,
                arm_id=arm,
                registries=registries,
                meter=meter,
                projected_outputs=projections,
                slack=slack,
            )
            for position, bound in enumerate(bounds, start=1):
                if bound > input_caps[str(position)]:
                    raise EnvelopeError(
                        f"item {item.item_id} arm {arm} call {position}: projected "
                        f"natural prompt of {bound} tokens exceeds the registered "
                        f"input cap {input_caps[str(position)]}"
                    )
            per_arm[arm] = list(bounds)
        records.append({"item_id": item.item_id, "projected_upper_bounds": per_arm})
    projected_totals = {
        arm: total_input_cap + sum(projections[arm].values()) for arm in arms
    }
    spread = max(projected_totals.values()) - min(projected_totals.values())
    if spread > token_tolerance:
        raise EnvelopeError(
            "declared per-arm output projections spread "
            f"{spread} tokens, beyond the registered tolerance {token_tolerance}: "
            + ", ".join(f"{arm}={total}" for arm, total in sorted(projected_totals.items()))
        )
    return {
        "projected_total_tokens_by_arm": projected_totals,
        "projected_spread": spread,
        "items": records,
    }


def compute_minimum_input_caps(
    *,
    run_id: str,
    items: Sequence[FunctionNetworkItemV1],
    arms: Sequence[str],
    registries: Mapping[str, FunctionRegistryV1],
    meter: TokenMeter,
    projected_outputs: Mapping[str, Mapping[str, int]],
    slack: int,
) -> dict[str, int]:
    """Derive the smallest feasible per-call input caps for a cohort."""

    caps = {"1": 1, "2": 1, "3": 1}
    for item in items:
        for arm in arms:
            bounds = project_item_call_upper_bounds(
                run_id=run_id,
                item=item,
                arm_id=arm,
                registries=registries,
                meter=meter,
                projected_outputs=projected_outputs,
                slack=slack,
            )
            for position, bound in enumerate(bounds, start=1):
                caps[str(position)] = max(caps[str(position)], bound)
    return caps


__all__ = [
    "ENVELOPE_SCHEMA",
    "EnvelopeError",
    "check_tokenizer_identity",
    "compute_minimum_input_caps",
    "enforce_projection",
    "envelope_spec",
    "project_item_call_upper_bounds",
    "validate_token_envelope",
]
