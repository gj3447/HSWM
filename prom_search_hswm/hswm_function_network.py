"""Three-call PROM-9 function network with matched-budget control arms."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_call_receipt import (
    CallReceiptV1,
    ModelPort,
    invoke_function,
    verify_call_receipt,
)
from prom_search_hswm.hswm_function_registry import FunctionRegistryV1, verify_registry
from prom_search_hswm.hswm_typed_ports import canonical_sha256, validate_port


RUN_SCHEMA = "hswm-prom9-f1-item-run/v1"

TYPED_ARM = "typed_hswm_three_function_network"
FLAT_ARM = "flat_single_llm_three_call_workflow"
VECTOR_ARM = "vector_memory_three_call_workflow"
REMOVAL_ARM = "typed_network_role_removed_schema_preserving_null"
SHUFFLE_ARM = "typed_network_with_role_instructions_shuffled_but_ports_preserved"
F1_ARMS = (TYPED_ARM, FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)


class FunctionNetworkError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceCandidateV1:
    bond_id: str
    evidence_id: str
    content: str
    observable: dict[str, object]

    def __post_init__(self) -> None:
        if not self.bond_id or not self.evidence_id or not self.content:
            raise FunctionNetworkError("candidate IDs and content must be non-empty")

    def universe_identity(self) -> dict[str, str]:
        return {
            "bond_id": self.bond_id,
            "evidence_id": self.evidence_id,
            "content_sha256": canonical_sha256({"content": self.content}),
        }


@dataclass(frozen=True)
class FunctionNetworkItemV1:
    item_id: str
    query_text: str
    allowed_evidence_types: tuple[str, ...]
    candidates: tuple[EvidenceCandidateV1, ...]
    max_evidence_items: int
    max_input_tokens: int
    max_output_tokens_per_call: int

    def __post_init__(self) -> None:
        if not self.item_id or not self.query_text or not self.allowed_evidence_types:
            raise FunctionNetworkError("item identity, query, and evidence types are required")
        if not self.candidates:
            raise FunctionNetworkError("item candidates must be non-empty")
        if len({candidate.bond_id for candidate in self.candidates}) != len(self.candidates):
            raise FunctionNetworkError("candidate bond IDs must be unique")
        if len({candidate.evidence_id for candidate in self.candidates}) != len(self.candidates):
            raise FunctionNetworkError("candidate evidence IDs must be unique")
        for value, label in (
            (self.max_evidence_items, "max_evidence_items"),
            (self.max_input_tokens, "max_input_tokens"),
            (self.max_output_tokens_per_call, "max_output_tokens_per_call"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise FunctionNetworkError(f"{label} must be positive")
        if self.max_evidence_items > len(self.candidates):
            raise FunctionNetworkError("max_evidence_items exceeds candidate count")

    @property
    def candidate_universe_sha256(self) -> str:
        return canonical_sha256(
            [candidate.universe_identity() for candidate in self.candidates]
        )


@dataclass(frozen=True)
class FunctionNetworkRunV1:
    run_id: str
    arm_id: str
    item_id: str
    registry_sha256: str
    candidate_universe_sha256: str
    calls: tuple[CallReceiptV1, ...]
    answer: dict[str, object]
    selected_bond_ids: tuple[str, ...]
    total_input_tokens: int
    total_output_tokens: int
    total_allowed_output_tokens: int
    persistent_state_bytes: int
    run_receipt_sha256: str
    schema_version: str = RUN_SCHEMA

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "arm_id": self.arm_id,
            "item_id": self.item_id,
            "registry_sha256": self.registry_sha256,
            "candidate_universe_sha256": self.candidate_universe_sha256,
            "calls": [call.canonical() for call in self.calls],
            "answer": self.answer,
            "selected_bond_ids": list(self.selected_bond_ids),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_allowed_output_tokens": self.total_allowed_output_tokens,
            "persistent_state_bytes": self.persistent_state_bytes,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "run_receipt_sha256": self.run_receipt_sha256}


def observable_for_arm(
    arm_id: str, observable: Mapping[str, object]
) -> dict[str, object]:
    """Expose only the registered feature plane for each baseline."""

    values = dict(observable)
    if arm_id == FLAT_ARM:
        allowed = {"flat_position", "source_type", "flat_score"}
        return {key: values[key] for key in sorted(values) if key in allowed}
    if arm_id == VECTOR_ARM:
        allowed = {"vector_score", "source_type"}
        return {key: values[key] for key in sorted(values) if key in allowed}
    return {key: values[key] for key in sorted(values)}


def _request_id(run_id: str, arm_id: str, item_id: str) -> str:
    """Return a compact, receipt-bound transport correlation identifier.

    Run, arm, and item identity are already recorded independently in every
    call receipt.  Sending their full human-readable concatenation through an
    LLM makes an otherwise opaque transport field needlessly error-prone, so
    the model copies a deterministic short digest instead.
    """

    identity = {"run_id": run_id, "arm_id": arm_id, "item_id": item_id}
    return f"req-{canonical_sha256(identity)[:20]}"


def run_item(
    *,
    run_id: str,
    arm_id: str,
    item: FunctionNetworkItemV1,
    registry: FunctionRegistryV1,
    model_port: ModelPort,
    persistent_state_bytes: int = 0,
) -> FunctionNetworkRunV1:
    """Execute exactly QF -> BF -> AF, including removal control null calls."""

    if arm_id not in F1_ARMS:
        raise FunctionNetworkError(f"unsupported F1 arm: {arm_id}")
    if isinstance(persistent_state_bytes, bool) or persistent_state_bytes < 0:
        raise FunctionNetworkError("persistent_state_bytes must be non-negative")
    verify_registry(registry)
    qf = registry.by_id("QF_QUERY_COMPILER")
    bf = registry.by_id("BF_BOND_PROPOSER")
    af = registry.by_id("AF_ANSWER_SYNTHESIZER")
    request_id = _request_id(run_id, arm_id, item.item_id)
    query_envelope = validate_port(
        "QueryEnvelopeV1",
        {
            "request_id": request_id,
            "query_text": item.query_text,
            "allowed_evidence_types": list(item.allowed_evidence_types),
            "budget": {
                "max_candidates": len(item.candidates),
                "max_evidence_items": item.max_evidence_items,
                "max_input_tokens": item.max_input_tokens,
                "max_output_tokens": item.max_output_tokens_per_call,
            },
        },
    )
    query_plan, call_1 = invoke_function(
        run_id=run_id,
        arm_id=arm_id,
        item_id=item.item_id,
        call_index=1,
        function=qf,
        input_payload=query_envelope,
        max_output_tokens=item.max_output_tokens_per_call,
        model_port=model_port,
    )
    if query_plan["request_id"] != request_id:
        raise FunctionNetworkError("QF changed request_id")

    scoring = validate_port(
        "BondScoringEnvelopeV1",
        {
            "request_id": request_id,
            "query_plan": query_plan,
            "candidates": [
                {
                    "bond_id": candidate.bond_id,
                    "evidence_id": candidate.evidence_id,
                    "observable": observable_for_arm(arm_id, candidate.observable),
                }
                for candidate in item.candidates
            ],
            "candidate_budget": item.max_evidence_items,
        },
    )
    proposal, call_2 = invoke_function(
        run_id=run_id,
        arm_id=arm_id,
        item_id=item.item_id,
        call_index=2,
        function=bf,
        input_payload=scoring,
        max_output_tokens=item.max_output_tokens_per_call,
        model_port=model_port,
    )
    if proposal["request_id"] != request_id:
        raise FunctionNetworkError("BF changed request_id")
    supplied = {candidate.bond_id: candidate for candidate in item.candidates}
    ordered = list(proposal["ordered_bond_ids"])
    if not set(ordered).issubset(supplied):
        raise FunctionNetworkError("BF selected a bond outside the supplied universe")
    if len(ordered) > item.max_evidence_items:
        raise FunctionNetworkError("BF exceeded the evidence-count budget")
    selected = [] if proposal["abstain"] else [supplied[bond_id] for bond_id in ordered]
    selected_evidence_ids = {candidate.evidence_id for candidate in selected}
    if not set(proposal["evidence_refs"]).issubset(selected_evidence_ids):
        raise FunctionNetworkError("BF cited evidence outside its selected bonds")

    answer_context = validate_port(
        "AnswerContextV1",
        {
            "request_id": request_id,
            "query_text": item.query_text,
            "query_plan": query_plan,
            "selected_evidence": [
                {"evidence_id": candidate.evidence_id, "content": candidate.content}
                for candidate in selected
            ],
            "max_answer_tokens": item.max_output_tokens_per_call,
        },
    )
    answer, call_3 = invoke_function(
        run_id=run_id,
        arm_id=arm_id,
        item_id=item.item_id,
        call_index=3,
        function=af,
        input_payload=answer_context,
        max_output_tokens=item.max_output_tokens_per_call,
        model_port=model_port,
    )
    if answer["request_id"] != request_id:
        raise FunctionNetworkError("AF changed request_id")
    if not set(answer["supporting_evidence_ids"]).issubset(selected_evidence_ids):
        raise FunctionNetworkError("AF cited evidence outside the frozen selection")
    calls = (call_1, call_2, call_3)
    total_input = sum(call.input_tokens for call in calls)
    if total_input > item.max_input_tokens:
        raise FunctionNetworkError("run exceeded the registered total input-token cap")
    total_output = sum(call.output_tokens for call in calls)
    unsigned = {
        "schema_version": RUN_SCHEMA,
        "run_id": run_id,
        "arm_id": arm_id,
        "item_id": item.item_id,
        "registry_sha256": registry.registry_sha256,
        "candidate_universe_sha256": item.candidate_universe_sha256,
        "calls": [call.canonical() for call in calls],
        "answer": answer,
        "selected_bond_ids": [candidate.bond_id for candidate in selected],
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_allowed_output_tokens": 3 * item.max_output_tokens_per_call,
        "persistent_state_bytes": persistent_state_bytes,
    }
    constructor = {
        key: value
        for key, value in unsigned.items()
        if key not in {"schema_version", "calls", "selected_bond_ids"}
    }
    return FunctionNetworkRunV1(
        **constructor,
        calls=calls,
        selected_bond_ids=tuple(unsigned["selected_bond_ids"]),
        run_receipt_sha256=canonical_sha256(unsigned),
    )


def verify_run(value: Mapping[str, object]) -> str:
    data = dict(value)
    if data.get("schema_version") != RUN_SCHEMA:
        raise FunctionNetworkError("unsupported item-run schema")
    declared = data.pop("run_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(data) != declared:
        raise FunctionNetworkError("item-run receipt self-hash drifted")
    calls = data.get("calls")
    if not isinstance(calls, list) or len(calls) != 3:
        raise FunctionNetworkError("item run must contain exactly three calls")
    if [call.get("call_index") for call in calls if isinstance(call, Mapping)] != [1, 2, 3]:
        raise FunctionNetworkError("item call order drifted")
    for call in calls:
        if not isinstance(call, Mapping):
            raise FunctionNetworkError("invalid call receipt")
        verify_call_receipt(call)
    validate_port("AnswerEnvelopeV1", data.get("answer"))
    return declared


__all__ = [
    "EvidenceCandidateV1",
    "F1_ARMS",
    "FLAT_ARM",
    "FunctionNetworkError",
    "FunctionNetworkItemV1",
    "FunctionNetworkRunV1",
    "REMOVAL_ARM",
    "RUN_SCHEMA",
    "SHUFFLE_ARM",
    "TYPED_ARM",
    "VECTOR_ARM",
    "observable_for_arm",
    "run_item",
    "verify_run",
]
