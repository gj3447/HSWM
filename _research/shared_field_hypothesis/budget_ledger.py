#!/usr/bin/env python3
"""Artifact-derived equal-budget accounting for the HSWM E1 harness.

The projector accepts operation-level usage events plus executable parameter and
serialized-state inventories.  It never trusts a result-level
``equal_budget=true`` assertion.  Protocol-v1 discrete dimensions are compared
exactly per task and split; noisy resource dimensions are cap-checked and
reported separately.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence


USAGE_SCHEMA = "hswm-budget-usage-event/v1"
PARAMETER_INVENTORY_SCHEMA = "hswm-parameter-inventory/v1"
STATE_INVENTORY_SCHEMA = "hswm-serialized-state-inventory/v1"
PROJECTION_SCHEMA = "hswm-budget-projection/v1"
PARITY_SCHEMA = "hswm-budget-parity/v1"

# Kept byte-for-byte aligned with manifest.v1.json.  These names are not an
# implicit protocol-v2 amendment.
LEGACY_V1_EXACT_DIMENSIONS = (
    "unique_trainable_parameters",
    "optimizer_steps",
    "training_examples",
    "embedding_calls",
    "offline_model_calls",
    "online_model_calls",
    "input_tokens",
    "output_tokens",
    "candidate_edge_scores",
    "revision_events_consumed",
)
# E1 adds engineering counters required by PROM section 9.1 without pretending
# to rewrite the immutable v1 design lock.
E1_EXACT_DIMENSIONS = LEGACY_V1_EXACT_DIMENSIONS + (
    "serialized_mutable_bytes",
    "update_packets",
    "dispatch_count",
    "evaluation_cadence",
)
# Compatibility spelling for code that explicitly means manifest-v1.
EXACT_DIMENSIONS = LEGACY_V1_EXACT_DIMENSIONS
CAPPED_DIMENSIONS = ("wall_seconds", "peak_bytes", "monetary_cost")

# Additional E1 engineering guards requested by the prior-art comparison.  They
# are kept separate so their introduction cannot silently mutate protocol v1.
ARTIFACT_PARITY_GUARDS = (
    "serialized_learned_state_bytes",
    "scorer_flops",
    "judge_calls",
    "replay_bytes",
)
SEED_DIMENSION = "seed_binding"

_INVENTORY_DERIVED = {
    "unique_trainable_parameters",
    "serialized_mutable_bytes",
    "serialized_learned_state_bytes",
}
_REPLAY_DERIVED = {"replay_bytes"}
_USAGE_DIMENSIONS = (
    set(E1_EXACT_DIMENSIONS)
    | set(CAPPED_DIMENSIONS)
    | set(ARTIFACT_PARITY_GUARDS)
    | {SEED_DIMENSION}
) - _INVENTORY_DERIVED - _REPLAY_DERIVED
_HEX = frozenset("0123456789abcdef")
_HEAD_ROLE_MARKERS = (
    "head",
    "router",
    "scorer",
    "decoder",
    "lookup",
    "policy",
)


class BudgetViolation(ValueError):
    """An invalid accounting artifact with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _validate_json_shape(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise BudgetViolation(
                    "NON_CANONICAL_JSON", f"{path} contains a non-string object key"
                )
            _validate_json_shape(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_json_shape(child, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise BudgetViolation("NON_CANONICAL_JSON", f"{path} contains a non-finite number")


def _canonical_bytes(value: Any) -> bytes:
    _validate_json_shape(value)
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        json.loads(encoded)
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise BudgetViolation(
            "NON_CANONICAL_JSON", f"artifact is not strict JSON: {exc}"
        ) from exc
    return encoded


def _clone(value: Any) -> Any:
    return json.loads(_canonical_bytes(value))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BudgetViolation("INVALID_IDENTIFIER", f"{label} must be non-empty text")
    return value


def _count(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BudgetViolation("INVALID_COUNT", f"{label} must be a non-negative integer")
    return value


def _resource(value: Any, label: str) -> int | float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise BudgetViolation(
            "INVALID_RESOURCE_VALUE", f"{label} must be finite and non-negative"
        )
    return value


def _contains_key(value: Any, forbidden: str) -> bool:
    if isinstance(value, Mapping):
        return forbidden in value or any(
            _contains_key(child, forbidden) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(child, forbidden) for child in value)
    return False


def _is_padding(event: Mapping[str, Any]) -> bool:
    if event.get("padding") is True:
        return True
    purpose = event.get("purpose")
    return isinstance(purpose, str) and purpose.strip().lower() in {
        "pad",
        "padding",
        "budget_padding",
        "parity_padding",
    }


def make_usage_event(
    *,
    usage_event_id: str,
    arm_id: str,
    task_id: str,
    split_id: str,
    dimension: str,
    amount: int | float,
    source_event_sha256: str | None = None,
) -> dict[str, Any]:
    """Build one raw operation-accounting event; it is never an aggregate claim."""

    event: dict[str, Any] = {
        "schema": USAGE_SCHEMA,
        "usage_event_id": _text(usage_event_id, "usage_event_id"),
        "arm_id": _text(arm_id, "arm_id"),
        "task_id": _text(task_id, "task_id"),
        "split_id": _text(split_id, "split_id"),
        "dimension": dimension,
        "amount": amount,
        "padding": False,
    }
    if source_event_sha256 is not None:
        event["source_event_sha256"] = source_event_sha256
    return event


def make_seed_event(
    *,
    usage_event_id: str,
    arm_id: str,
    task_id: str,
    split_id: str,
    seed_id: str,
    seed_sha256: str,
    source_event_sha256: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "schema": USAGE_SCHEMA,
        "usage_event_id": _text(usage_event_id, "usage_event_id"),
        "arm_id": _text(arm_id, "arm_id"),
        "task_id": _text(task_id, "task_id"),
        "split_id": _text(split_id, "split_id"),
        "dimension": SEED_DIMENSION,
        "seed_id": _text(seed_id, "seed_id"),
        "seed_sha256": seed_sha256,
        "padding": False,
    }
    if source_event_sha256 is not None:
        event["source_event_sha256"] = source_event_sha256
    return event


def extract_usage_events(
    experiment_events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Extract hash-bound usage payloads from canonical harness budget events."""

    extracted: list[dict[str, Any]] = []
    for index, envelope in enumerate(experiment_events):
        if not isinstance(envelope, Mapping):
            raise BudgetViolation("EXPERIMENT_EVENT_INVALID", f"event {index} is not an object")
        if envelope.get("event_type") != "budget":
            continue
        payload = envelope.get("payload")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("usage"), Mapping):
            raise BudgetViolation(
                "BUDGET_PAYLOAD_INVALID", f"budget event {index} lacks payload.usage"
            )
        event_sha256 = envelope.get("event_sha256")
        if not _is_sha256(event_sha256):
            raise BudgetViolation(
                "SOURCE_EVENT_HASH_INVALID", f"budget event {index} has no canonical hash"
            )
        unsigned_envelope = dict(envelope)
        unsigned_envelope.pop("event_sha256", None)
        if _digest(unsigned_envelope) != event_sha256:
            raise BudgetViolation(
                "SOURCE_EVENT_HASH_MISMATCH",
                f"budget event {index} envelope bytes do not match event_sha256",
            )
        usage = _clone(dict(payload["usage"]))
        if usage.get("arm_id") != envelope.get("arm_id"):
            raise BudgetViolation(
                "CROSS_ARM_USAGE_REFERENCE",
                f"budget event {index} carries usage for another arm",
            )
        supplied = usage.get("source_event_sha256")
        if supplied is not None and supplied != event_sha256:
            raise BudgetViolation(
                "SOURCE_EVENT_HASH_MISMATCH",
                f"budget event {index} usage source does not match its envelope",
            )
        usage["source_event_sha256"] = event_sha256
        extracted.append(usage)
    return extracted


def _role_looks_head_like(role: str) -> bool:
    normalized = role.strip().lower()
    return any(marker in normalized for marker in _HEAD_ROLE_MARKERS)


def inspect_inventories(
    *,
    arm_id: str,
    parameter_inventory: Mapping[str, Any],
    serialized_state_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive unique capacity and reject hidden or multiply allocated blocks."""

    arm_id = _text(arm_id, "arm_id")
    if not isinstance(parameter_inventory, Mapping):
        raise BudgetViolation("PARAMETER_INVENTORY_INVALID", "parameter inventory must be an object")
    if not isinstance(serialized_state_inventory, Mapping):
        raise BudgetViolation("STATE_INVENTORY_INVALID", "state inventory must be an object")
    parameters = _clone(dict(parameter_inventory))
    states = _clone(dict(serialized_state_inventory))
    if parameters.get("schema") != PARAMETER_INVENTORY_SCHEMA:
        raise BudgetViolation("PARAMETER_INVENTORY_SCHEMA_MISMATCH", "parameter schema drift")
    if states.get("schema") != STATE_INVENTORY_SCHEMA:
        raise BudgetViolation("STATE_INVENTORY_SCHEMA_MISMATCH", "state schema drift")
    if parameters.get("arm_id") != arm_id or states.get("arm_id") != arm_id:
        raise BudgetViolation("CROSS_ARM_INVENTORY", "inventory belongs to another arm")

    registered = parameters.get("registered_learned_block_ids")
    blocks = parameters.get("blocks")
    entries = states.get("entries")
    if not isinstance(registered, list) or not isinstance(blocks, list):
        raise BudgetViolation(
            "PARAMETER_INVENTORY_INVALID",
            "registered_learned_block_ids and blocks must be arrays",
        )
    if not isinstance(entries, list):
        raise BudgetViolation("STATE_INVENTORY_INVALID", "entries must be an array")
    registered_ids = [_text(value, "registered learned block id") for value in registered]
    if len(registered_ids) != len(set(registered_ids)):
        raise BudgetViolation(
            "DUPLICATE_LEARNED_BLOCK_ID", "registered learned-block ids must be unique"
        )

    seen_block_ids: set[str] = set()
    parameter_allocations: set[str] = set()
    parameter_total = 0
    normalized_blocks: list[dict[str, Any]] = []
    for index, raw_block in enumerate(blocks):
        if not isinstance(raw_block, Mapping):
            raise BudgetViolation("PARAMETER_BLOCK_INVALID", f"block {index} is not an object")
        block = _clone(dict(raw_block))
        block_id = _text(block.get("learned_block_id"), f"block {index} learned_block_id")
        allocation_id = _text(block.get("allocation_id"), f"block {index} allocation_id")
        role = _text(block.get("role"), f"block {index} role")
        count = _count(block.get("trainable_parameters"), f"block {index} trainable_parameters")
        if block_id in seen_block_ids:
            raise BudgetViolation(
                "DUPLICATE_LEARNED_BLOCK_ID", f"learned block {block_id!r} is listed twice"
            )
        if allocation_id in parameter_allocations:
            raise BudgetViolation(
                "DUPLICATE_ALLOCATION", f"parameter allocation {allocation_id!r} is double counted"
            )
        if block_id not in registered_ids:
            raise BudgetViolation(
                "HIDDEN_HEAD_DETECTED",
                f"learned block {block_id!r} is outside the registered architecture",
            )
        seen_block_ids.add(block_id)
        parameter_allocations.add(allocation_id)
        parameter_total += count
        normalized_blocks.append(
            {
                "learned_block_id": block_id,
                "allocation_id": allocation_id,
                "role": role,
                "trainable_parameters": count,
            }
        )
    missing_blocks = sorted(set(registered_ids) - seen_block_ids)
    if missing_blocks:
        raise BudgetViolation(
            "REGISTERED_BLOCK_MISSING",
            f"registered blocks have no allocation: {','.join(missing_blocks)}",
        )

    seen_state_ids: set[str] = set()
    state_allocations: set[str] = set()
    serialized_learned_bytes = 0
    serialized_mutable_bytes = 0
    normalized_entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, Mapping):
            raise BudgetViolation("STATE_ENTRY_INVALID", f"state entry {index} is not an object")
        entry = _clone(dict(raw_entry))
        state_id = _text(entry.get("state_id"), f"state entry {index} state_id")
        allocation_id = _text(entry.get("allocation_id"), f"state entry {index} allocation_id")
        role = _text(entry.get("role"), f"state entry {index} role")
        byte_length = _count(entry.get("byte_length"), f"state entry {index} byte_length")
        learned = entry.get("learned")
        mutable = entry.get("mutable")
        if not isinstance(learned, bool) or not isinstance(mutable, bool):
            raise BudgetViolation(
                "STATE_ENTRY_INVALID", f"state entry {index} learned/mutable must be bool"
            )
        block_id = entry.get("learned_block_id")
        if block_id is not None:
            block_id = _text(block_id, f"state entry {index} learned_block_id")
        if state_id in seen_state_ids:
            raise BudgetViolation("DUPLICATE_STATE_ID", f"state id {state_id!r} is listed twice")
        if allocation_id in state_allocations:
            raise BudgetViolation(
                "DUPLICATE_ALLOCATION", f"state allocation {allocation_id!r} is double counted"
            )
        if block_id is not None and block_id not in seen_block_ids:
            raise BudgetViolation(
                "HIDDEN_HEAD_DETECTED",
                f"state {state_id!r} references an unregistered learned block",
            )
        if learned and block_id is None:
            raise BudgetViolation(
                "HIDDEN_HEAD_DETECTED", f"learned state {state_id!r} has no registered block"
            )
        if _role_looks_head_like(role) and block_id is None:
            shared_hash = entry.get("shared_artifact_sha256")
            if learned or mutable or not _is_sha256(shared_hash):
                raise BudgetViolation(
                    "HIDDEN_HEAD_DETECTED",
                    f"head-like state {state_id!r} is neither registered nor immutable hash-shared",
                )
        if block_id is not None:
            serialized_learned_bytes += byte_length
        if mutable:
            serialized_mutable_bytes += byte_length
        seen_state_ids.add(state_id)
        state_allocations.add(allocation_id)
        normalized_entries.append(
            {
                "state_id": state_id,
                "allocation_id": allocation_id,
                "role": role,
                "byte_length": byte_length,
                "learned": learned,
                "mutable": mutable,
                "learned_block_id": block_id,
                "shared_artifact_sha256": entry.get("shared_artifact_sha256"),
            }
        )

    normalized_blocks.sort(key=lambda item: item["learned_block_id"])
    normalized_entries.sort(key=lambda item: item["state_id"])
    report = {
        "arm_id": arm_id,
        "learned_block_ids": sorted(seen_block_ids),
        "unique_trainable_parameters": parameter_total,
        "serialized_mutable_bytes": serialized_mutable_bytes,
        "serialized_learned_state_bytes": serialized_learned_bytes,
        "parameter_allocations": normalized_blocks,
        "state_allocations": normalized_entries,
    }
    report["inventory_sha256"] = _digest(report)
    return report


def _validate_usage_events(
    arm_id: str, usage_events: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_source_dimensions: set[tuple[str, str, str, str]] = set()
    seed_bindings: dict[tuple[str, str, str], str] = {}
    for index, raw_event in enumerate(usage_events):
        if not isinstance(raw_event, Mapping):
            raise BudgetViolation("USAGE_EVENT_INVALID", f"usage event {index} is not an object")
        event = _clone(dict(raw_event))
        if _contains_key(event, "equal_budget"):
            raise BudgetViolation(
                "FORGED_SELF_REPORT_FIELD",
                f"usage event {index} contains forbidden equal_budget authority",
            )
        if event.get("schema") != USAGE_SCHEMA:
            raise BudgetViolation("USAGE_SCHEMA_MISMATCH", f"usage event {index} schema drift")
        usage_id = _text(event.get("usage_event_id"), f"usage event {index} id")
        if usage_id in seen_ids:
            raise BudgetViolation("DUPLICATE_USAGE_EVENT", f"usage id {usage_id!r} is repeated")
        seen_ids.add(usage_id)
        if event.get("arm_id") != arm_id:
            raise BudgetViolation("CROSS_ARM_USAGE_REFERENCE", f"usage event {index} arm mismatch")
        _text(event.get("task_id"), f"usage event {index} task_id")
        _text(event.get("split_id"), f"usage event {index} split_id")
        if event.get("padding") is not False or _is_padding(event):
            raise BudgetViolation(
                "PADDING_EVENT_FORBIDDEN", f"usage event {usage_id!r} is a padding operation"
            )
        source_hash = event.get("source_event_sha256")
        if not _is_sha256(source_hash):
            raise BudgetViolation(
                "SOURCE_EVENT_HASH_INVALID", f"usage event {usage_id!r} lacks source evidence"
            )
        dimension = event.get("dimension")
        source_dimension = (
            source_hash,
            str(dimension),
            event["task_id"],
            event["split_id"],
        )
        if source_dimension in seen_source_dimensions:
            raise BudgetViolation(
                "DUPLICATE_SOURCE_ACCOUNTING",
                f"source {source_hash} accounts {dimension!r} more than once",
            )
        seen_source_dimensions.add(source_dimension)
        if dimension in _INVENTORY_DERIVED:
            raise BudgetViolation(
                "INVENTORY_COUNTER_SELF_REPORT",
                f"{dimension} must be derived from executable inventories",
            )
        if dimension in _REPLAY_DERIVED:
            raise BudgetViolation(
                "REPLAY_BYTES_SELF_REPORT", "replay_bytes is derived from canonical ledger bytes"
            )
        if dimension not in _USAGE_DIMENSIONS:
            raise BudgetViolation(
                "UNKNOWN_BUDGET_DIMENSION", f"usage event {usage_id!r} has {dimension!r}"
            )
        if dimension == SEED_DIMENSION:
            seed_id = _text(event.get("seed_id"), f"usage event {index} seed_id")
            seed_sha256 = event.get("seed_sha256")
            if not _is_sha256(seed_sha256):
                raise BudgetViolation("SEED_HASH_INVALID", f"usage event {usage_id!r} seed hash")
            seed_key = (event["task_id"], event["split_id"], seed_id)
            old = seed_bindings.get(seed_key)
            if old is not None and old != seed_sha256:
                raise BudgetViolation(
                    "SEED_BINDING_CONFLICT", f"seed {seed_id!r} has conflicting hashes"
                )
            seed_bindings[seed_key] = seed_sha256
        elif dimension in CAPPED_DIMENSIONS:
            event["amount"] = _resource(event.get("amount"), f"usage event {index} amount")
        else:
            event["amount"] = _count(event.get("amount"), f"usage event {index} amount")
        normalized.append(event)
    return normalized


def _normalized_replay_bytes(events: Sequence[Mapping[str, Any]]) -> int:
    normalized: list[dict[str, Any]] = []
    for raw in sorted(events, key=lambda item: str(item["usage_event_id"])):
        item = _clone(dict(raw))
        item["arm_id"] = "<ARM>"
        item["source_event_sha256"] = "<SOURCE_EVENT_SHA256>"
        item["usage_event_id"] = "<USAGE_EVENT_ID>"
        normalized.append(item)
    return len(_canonical_bytes(normalized))


def derive_budget_projection(
    *,
    arm_id: str,
    usage_events: Sequence[Mapping[str, Any]],
    parameter_inventory: Mapping[str, Any],
    serialized_state_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Project raw artifacts into complete task/split counters."""

    arm_id = _text(arm_id, "arm_id")
    inventory = inspect_inventories(
        arm_id=arm_id,
        parameter_inventory=parameter_inventory,
        serialized_state_inventory=serialized_state_inventory,
    )
    events = _validate_usage_events(arm_id, usage_events)
    if not events:
        raise BudgetViolation("USAGE_SCOPE_EMPTY", "at least one raw usage/seed event is required")

    scopes: dict[tuple[str, str], dict[str, Any]] = {}
    by_scope_events: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    evidence_presence: dict[tuple[str, str], set[str]] = defaultdict(set)
    for event in events:
        key = (event["task_id"], event["split_id"])
        if key not in scopes:
            scopes[key] = {
                "task_id": key[0],
                "split_id": key[1],
                "exact": {dimension: 0 for dimension in E1_EXACT_DIMENSIONS},
                "artifact_guards": {
                    dimension: 0 for dimension in ARTIFACT_PARITY_GUARDS
                },
                "capped": {dimension: 0 for dimension in CAPPED_DIMENSIONS},
                "seed_manifest": [],
            }
        by_scope_events[key].append(event)
        dimension = event["dimension"]
        evidence_presence[key].add(dimension)
        if dimension == SEED_DIMENSION:
            scopes[key]["seed_manifest"].append(
                {"seed_id": event["seed_id"], "seed_sha256": event["seed_sha256"]}
            )
        elif dimension in E1_EXACT_DIMENSIONS:
            scopes[key]["exact"][dimension] += event["amount"]
        elif dimension in CAPPED_DIMENSIONS:
            scopes[key]["capped"][dimension] += event["amount"]
        else:
            scopes[key]["artifact_guards"][dimension] += event["amount"]

    for key, scope in scopes.items():
        required_usage_dimensions = (
            set(E1_EXACT_DIMENSIONS)
            | set(ARTIFACT_PARITY_GUARDS)
            | {SEED_DIMENSION}
        ) - _INVENTORY_DERIVED - _REPLAY_DERIVED
        missing_dimensions = sorted(required_usage_dimensions - evidence_presence[key])
        if missing_dimensions:
            raise BudgetViolation(
                "BUDGET_DIMENSION_MISSING",
                f"{key[0]}/{key[1]} lacks source events for {','.join(missing_dimensions)}",
            )
        scope["exact"]["unique_trainable_parameters"] = inventory[
            "unique_trainable_parameters"
        ]
        scope["exact"]["serialized_mutable_bytes"] = inventory[
            "serialized_mutable_bytes"
        ]
        scope["artifact_guards"]["serialized_learned_state_bytes"] = inventory[
            "serialized_learned_state_bytes"
        ]
        scope["artifact_guards"]["replay_bytes"] = _normalized_replay_bytes(
            by_scope_events[key]
        )
        scope["seed_manifest"].sort(key=lambda item: (item["seed_id"], item["seed_sha256"]))

    ordered_scopes = [scopes[key] for key in sorted(scopes)]
    source = {
        "usage_event_count": len(events),
        "usage_events_sha256": _digest(sorted(events, key=lambda item: item["usage_event_id"])),
        "inventory_sha256": inventory["inventory_sha256"],
    }
    projection = {
        "schema": PROJECTION_SCHEMA,
        "arm_id": arm_id,
        "legacy_v1_exact_dimensions": list(LEGACY_V1_EXACT_DIMENSIONS),
        "e1_exact_dimensions": list(E1_EXACT_DIMENSIONS),
        "artifact_parity_guards": list(ARTIFACT_PARITY_GUARDS),
        "capped_dimensions": list(CAPPED_DIMENSIONS),
        "inventory": inventory,
        "scopes": ordered_scopes,
        "source": source,
    }
    projection["projection_sha256"] = _digest(projection)
    return projection


def _scope_map(projection: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (scope["task_id"], scope["split_id"]): scope
        for scope in projection["scopes"]
    }


def compare_budget_parity(
    *,
    arm_artifacts: Mapping[str, Mapping[str, Any]],
    compared_arms: Sequence[str],
    numeric_caps: Mapping[str, int | float] | None = None,
    self_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare artifact projections; caller self-reports are recorded as ignored."""

    arms = list(compared_arms)
    if len(arms) < 2 or len(arms) != len(set(arms)):
        raise BudgetViolation(
            "COMPARED_ARMS_INVALID", "compared_arms must contain at least two unique arms"
        )
    projections: dict[str, dict[str, Any]] = {}
    for arm_id in arms:
        artifacts = arm_artifacts.get(arm_id)
        if not isinstance(artifacts, Mapping):
            raise BudgetViolation("ARM_ARTIFACT_MISSING", f"missing artifacts for {arm_id!r}")
        projections[arm_id] = derive_budget_projection(
            arm_id=arm_id,
            usage_events=artifacts.get("usage_events", ()),
            parameter_inventory=artifacts.get("parameter_inventory", {}),
            serialized_state_inventory=artifacts.get("serialized_state_inventory", {}),
        )

    mismatches: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    baseline_id = arms[0]
    baseline_scopes = _scope_map(projections[baseline_id])
    all_scopes = set(baseline_scopes)
    for arm_id in arms[1:]:
        all_scopes.update(_scope_map(projections[arm_id]))

    for key in sorted(all_scopes):
        baseline = baseline_scopes.get(key)
        if baseline is None:
            mismatches.append(
                {
                    "code": "BUDGET_INVALID_SCOPE_MISMATCH",
                    "task_id": key[0],
                    "split_id": key[1],
                    "arm_id": baseline_id,
                    "reason": "scope_missing",
                }
            )
            continue
        for arm_id in arms[1:]:
            candidate = _scope_map(projections[arm_id]).get(key)
            if candidate is None:
                mismatches.append(
                    {
                        "code": "BUDGET_INVALID_SCOPE_MISMATCH",
                        "task_id": key[0],
                        "split_id": key[1],
                        "arm_id": arm_id,
                        "reason": "scope_missing",
                    }
                )
                continue
            for dimension in E1_EXACT_DIMENSIONS:
                expected = baseline["exact"][dimension]
                observed = candidate["exact"][dimension]
                if observed != expected:
                    mismatches.append(
                        {
                            "code": "BUDGET_INVALID_EXACT_DIMENSION",
                            "task_id": key[0],
                            "split_id": key[1],
                            "arm_id": arm_id,
                            "dimension": dimension,
                            "expected": expected,
                            "observed": observed,
                        }
                    )
            for dimension in ARTIFACT_PARITY_GUARDS:
                expected = baseline["artifact_guards"][dimension]
                observed = candidate["artifact_guards"][dimension]
                if observed != expected:
                    mismatches.append(
                        {
                            "code": "BUDGET_INVALID_ARTIFACT_GUARD",
                            "task_id": key[0],
                            "split_id": key[1],
                            "arm_id": arm_id,
                            "dimension": dimension,
                            "expected": expected,
                            "observed": observed,
                        }
                    )
            if candidate["seed_manifest"] != baseline["seed_manifest"]:
                mismatches.append(
                    {
                        "code": "BUDGET_INVALID_SEED_BINDING",
                        "task_id": key[0],
                        "split_id": key[1],
                        "arm_id": arm_id,
                    }
                )

    caps = dict(numeric_caps or {})
    unknown_caps = sorted(set(caps) - set(CAPPED_DIMENSIONS))
    if unknown_caps:
        raise BudgetViolation("UNKNOWN_RESOURCE_CAP", f"unknown caps: {','.join(unknown_caps)}")
    for dimension, value in list(caps.items()):
        caps[dimension] = _resource(value, f"numeric cap {dimension}")
    capped_totals: dict[str, dict[str, int | float]] = {}
    for arm_id in arms:
        totals = {dimension: 0 for dimension in CAPPED_DIMENSIONS}
        for scope in projections[arm_id]["scopes"]:
            for dimension in CAPPED_DIMENSIONS:
                totals[dimension] += scope["capped"][dimension]
        capped_totals[arm_id] = totals
        for dimension, cap in caps.items():
            if totals[dimension] > cap:
                mismatches.append(
                    {
                        "code": "CAPPED_RESOURCE_EXCEEDED",
                        "arm_id": arm_id,
                        "dimension": dimension,
                        "cap": cap,
                        "observed": totals[dimension],
                    }
                )
    capped_equal = all(
        capped_totals[arm_id] == capped_totals[baseline_id] for arm_id in arms[1:]
    )
    if not capped_equal:
        warnings.append(
            {
                "code": "CAPPED_RESOURCE_NON_EQUAL_REPORTED",
                "message": "capped resources are not exact-equality dimensions",
            }
        )
    if self_report is not None:
        warnings.append(
            {
                "code": "SELF_REPORT_IGNORED",
                "self_report_sha256": _digest(dict(self_report)),
                "message": "equal_budget and caller aggregates have no authority",
            }
        )

    parity_failure_codes = {
        "BUDGET_INVALID_SCOPE_MISMATCH",
        "BUDGET_INVALID_EXACT_DIMENSION",
        "BUDGET_INVALID_ARTIFACT_GUARD",
        "BUDGET_INVALID_SEED_BINDING",
    }
    cap_failure = any(item["code"] == "CAPPED_RESOURCE_EXCEEDED" for item in mismatches)
    equal_measured_budget = not any(
        item["code"] in parity_failure_codes for item in mismatches
    )
    result = {
        "schema": PARITY_SCHEMA,
        "boundary": "ENGINEERING_ONLY_NO_SCIENTIFIC_VERDICT",
        "compared_arms": arms,
        "projections": projections,
        "equal_measured_budget": equal_measured_budget,
        "capped_resources_within_limits": not cap_failure,
        "engineering_budget_valid": equal_measured_budget and not cap_failure,
        "status": (
            "PARITY_PASS" if equal_measured_budget and not cap_failure else "BUDGET_INVALID"
        ),
        "mismatches": mismatches,
        "capped_resources": {
            "totals": capped_totals,
            "numeric_caps": caps,
            "exactly_equal": capped_equal,
            "equality_required": False,
        },
        "self_report_authoritative": False,
        "warnings": warnings,
        "scientific_verdict": None,
    }
    result["parity_sha256"] = _digest(result)
    return result


__all__ = [
    "ARTIFACT_PARITY_GUARDS",
    "BudgetViolation",
    "CAPPED_DIMENSIONS",
    "E1_EXACT_DIMENSIONS",
    "EXACT_DIMENSIONS",
    "LEGACY_V1_EXACT_DIMENSIONS",
    "PARAMETER_INVENTORY_SCHEMA",
    "PARITY_SCHEMA",
    "PROJECTION_SCHEMA",
    "SEED_DIMENSION",
    "STATE_INVENTORY_SCHEMA",
    "USAGE_SCHEMA",
    "compare_budget_parity",
    "derive_budget_projection",
    "extract_usage_events",
    "inspect_inventories",
    "make_seed_event",
    "make_usage_event",
]
