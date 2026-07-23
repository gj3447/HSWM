#!/usr/bin/env python3
"""Deterministic, arm-isolated event harness for the HSWM E1 experiment gate.

This module is deliberately smaller than the product feedback runtime.  It owns
only a frozen starting artifact, isolated arm clones, a canonical per-arm hash
chain, request idempotency, and deterministic replay.  It does not register an
experiment, execute an efficacy run, or produce a scientific verdict.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


EVENT_SCHEMA = "hswm-experiment-event/v1"
FROZEN_ARTIFACT_SCHEMA = "hswm-frozen-starting-artifact/v1"
REPLAY_SCHEMA = "hswm-experiment-replay/v1"
EVENT_TYPES = frozenset({"input", "score", "update", "evaluation", "budget"})
RECEIPT_SCHEMA = "hswm-experiment-harness-receipt/v1"
EXPERIMENT_HARNESS_PASS = "EXPERIMENT_HARNESS_PASS"
EVENT_TOPOLOGY_SCHEMA = "hswm-replay-event-topology/v1"
CANONICAL_ARM_IDS = (
    "one_field",
    "separate_heads",
    "hard_versioned_revision_comparator",
    "unversioned_negative_control",
)
EXACT_PARITY_COHORT = ("one_field", "separate_heads")
CONTROL_ARM_IDS = (
    "hard_versioned_revision_comparator",
    "unversioned_negative_control",
)
ARM_ROLE_IDS = {
    "one_field": "A_ONE_FIELD",
    "separate_heads": "B_SHARED_SUBSTRATE_SEPARATE_HEADS",
    "hard_versioned_revision_comparator": "C_HARD_REVISION_THEN_SCORING",
    "unversioned_negative_control": "D_UNVERSIONED_SHARED_NEGATIVE_CONTROL",
}
CONTROL_BUDGET_POLICY_CODE = "CONTROL_ARCHITECTURE_EXACT_PARITY_EXEMPT"
REPLAY_DERIVED_USAGE_COUNTERS = ("update_packets", "evaluation_cadence")
_UNCHANGED = object()
_HEX = frozenset("0123456789abcdef")


class HarnessViolation(ValueError):
    """A fail-closed E1 harness rejection with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _validate_json_shape(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise HarnessViolation(
                    "NON_CANONICAL_JSON", f"{path} contains a non-string object key"
                )
            _validate_json_shape(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_json_shape(child, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise HarnessViolation("NON_CANONICAL_JSON", f"{path} contains a non-finite number")


def canonical_json_bytes(value: Any) -> bytes:
    """Return strict canonical JSON bytes or reject a non-JSON artifact.

    NaN and infinity are intentionally rejected because their spelling and
    comparison behavior cannot be used as a stable cross-process state fact.
    A round trip also detaches caller-owned mappings and lists.
    """

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
        raise HarnessViolation(
            "NON_CANONICAL_JSON", f"value is not strict JSON: {exc}"
        ) from exc
    return encoded


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _clone_json(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value))


def _nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise HarnessViolation("INVALID_IDENTIFIER", f"{label} must be non-empty text")
    return value


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _padding_requested(payload: Mapping[str, Any]) -> bool:
    if payload.get("padding") is True:
        return True
    purpose = payload.get("purpose")
    return isinstance(purpose, str) and purpose.strip().lower() in {
        "pad",
        "padding",
        "budget_padding",
        "parity_padding",
    }


def _state_sha256(run_id: str, arm_id: str, state: Any) -> str:
    return canonical_sha256(
        {
            "schema": "hswm-arm-state/v1",
            "run_id": run_id,
            "arm_id": arm_id,
            "state": state,
        }
    )


def _genesis_sha256(
    experiment_id: str,
    run_id: str,
    arm_id: str,
    artifact_sha256: str,
) -> str:
    return canonical_sha256(
        {
            "schema": "hswm-experiment-genesis/v1",
            "experiment_id": experiment_id,
            "run_id": run_id,
            "arm_id": arm_id,
            "starting_artifact_sha256": artifact_sha256,
        }
    )


def _intent_sha256(event_type: str, payload: Any, state_argument: Any) -> str:
    return canonical_sha256(
        {
            "event_type": event_type,
            "payload": payload,
            "state_argument": state_argument,
        }
    )


def _event_sha256(event: Mapping[str, Any]) -> str:
    unsigned = dict(event)
    unsigned.pop("event_sha256", None)
    return canonical_sha256(unsigned)


@dataclass(frozen=True)
class FrozenArtifact:
    """One content-addressed canonical starting artifact."""

    _canonical_bytes: bytes
    sha256: str

    @classmethod
    def freeze(cls, value: Any) -> "FrozenArtifact":
        encoded = canonical_json_bytes(value)
        envelope = {
            "schema": FROZEN_ARTIFACT_SCHEMA,
            "value": json.loads(encoded),
        }
        return cls(encoded, canonical_sha256(envelope))

    def clone(self) -> Any:
        """Return a fresh mutable clone; callers never receive shared state."""

        return json.loads(self._canonical_bytes)


@dataclass(frozen=True)
class ReplayResult:
    """A deterministic terminal projection of one verified arm log."""

    experiment_id: str
    run_id: str
    arm_id: str
    event_count: int
    terminal_state_sha256: str
    terminal_event_sha256: str
    replay_sha256: str
    _terminal_state_bytes: bytes

    @property
    def terminal_state(self) -> Any:
        return json.loads(self._terminal_state_bytes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": REPLAY_SCHEMA,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "arm_id": self.arm_id,
            "event_count": self.event_count,
            "terminal_state_sha256": self.terminal_state_sha256,
            "terminal_event_sha256": self.terminal_event_sha256,
            "replay_sha256": self.replay_sha256,
        }


class ArmRun:
    """An in-memory append-only arm stream with isolated mutable state."""

    def __init__(
        self,
        *,
        experiment_id: str,
        run_id: str,
        arm_id: str,
        frozen_artifact: FrozenArtifact,
    ) -> None:
        self.experiment_id = _nonempty_text(experiment_id, "experiment_id")
        self.run_id = _nonempty_text(run_id, "run_id")
        self.arm_id = _nonempty_text(arm_id, "arm_id")
        self.starting_artifact_sha256 = frozen_artifact.sha256
        self._starting_state = frozen_artifact.clone()
        self._state = frozen_artifact.clone()
        self._events: list[dict[str, Any]] = []
        self._requests: dict[str, tuple[str, dict[str, Any]]] = {}
        self._genesis_sha256 = _genesis_sha256(
            self.experiment_id,
            self.run_id,
            self.arm_id,
            self.starting_artifact_sha256,
        )

    @property
    def state(self) -> Any:
        return _clone_json(self._state)

    @property
    def state_sha256(self) -> str:
        return _state_sha256(self.run_id, self.arm_id, self._state)

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self._events))

    @property
    def terminal_event_sha256(self) -> str:
        if not self._events:
            return self._genesis_sha256
        return str(self._events[-1]["event_sha256"])

    def append_event(
        self,
        *,
        request_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        state_after: Any = _UNCHANGED,
    ) -> dict[str, Any]:
        """Append once, replay an exact retry, or reject a conflicting retry."""

        request_id = _nonempty_text(request_id, "request_id")
        if event_type not in EVENT_TYPES:
            raise HarnessViolation(
                "EVENT_TYPE_INVALID", f"event_type must be one of {sorted(EVENT_TYPES)}"
            )
        if not isinstance(payload, Mapping):
            raise HarnessViolation("PAYLOAD_INVALID", "payload must be an object")
        canonical_payload = _clone_json(dict(payload))
        if _padding_requested(canonical_payload):
            raise HarnessViolation(
                "PADDING_EVENT_FORBIDDEN", "budget parity may not be manufactured by padding"
            )

        supplied_state = state_after is not _UNCHANGED
        canonical_state_argument: Any = (
            _clone_json(state_after) if supplied_state else "<UNCHANGED>"
        )
        intent_sha256 = _intent_sha256(
            event_type, canonical_payload, canonical_state_argument
        )
        prior = self._requests.get(request_id)
        if prior is not None:
            prior_intent, prior_event = prior
            if prior_intent != intent_sha256:
                raise HarnessViolation(
                    "REQUEST_ID_CONFLICT",
                    "the request_id was already committed with different intent",
                )
            return copy.deepcopy(prior_event)

        if event_type == "update" and not supplied_state:
            raise HarnessViolation(
                "UPDATE_STATE_REQUIRED", "update events must record their complete next state"
            )
        before = _clone_json(self._state)
        after = _clone_json(state_after) if supplied_state else _clone_json(before)
        if event_type != "update" and canonical_json_bytes(after) != canonical_json_bytes(before):
            raise HarnessViolation(
                "NON_UPDATE_STATE_MUTATION",
                f"{event_type} events cannot mutate arm state",
            )

        before_sha256 = _state_sha256(self.run_id, self.arm_id, before)
        after_sha256 = _state_sha256(self.run_id, self.arm_id, after)
        event: dict[str, Any] = {
            "schema": EVENT_SCHEMA,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "arm_id": self.arm_id,
            "seq": len(self._events),
            "request_id": request_id,
            "event_type": event_type,
            "parent_event_sha256": self.terminal_event_sha256,
            "starting_artifact_sha256": self.starting_artifact_sha256,
            "state_before": {"arm_id": self.arm_id, "sha256": before_sha256},
            "state_after": {"arm_id": self.arm_id, "sha256": after_sha256},
            "state_snapshot": after if event_type == "update" else None,
            "payload": canonical_payload,
            "intent_sha256": intent_sha256,
        }
        event["event_sha256"] = _event_sha256(event)

        committed = _clone_json(event)
        self._events.append(committed)
        self._state = after
        self._requests[request_id] = (intent_sha256, committed)
        return copy.deepcopy(committed)

    def replay(self, events: Sequence[Mapping[str, Any]] | None = None) -> ReplayResult:
        return replay_arm(
            starting_artifact=self._starting_state,
            experiment_id=self.experiment_id,
            run_id=self.run_id,
            arm_id=self.arm_id,
            events=self._events if events is None else events,
            expected_artifact_sha256=self.starting_artifact_sha256,
        )


class ExperimentHarness:
    """Clone one canonical artifact into deterministic, isolated named arm runs."""

    def __init__(
        self,
        starting_artifact: Any,
        arm_ids: Iterable[str],
        *,
        experiment_id: str,
        run_names: Mapping[str, str] | None = None,
    ) -> None:
        self.experiment_id = _nonempty_text(experiment_id, "experiment_id")
        self.frozen_artifact = FrozenArtifact.freeze(starting_artifact)
        names = list(arm_ids)
        if not names:
            raise HarnessViolation("ARM_SET_EMPTY", "at least one arm is required")
        for arm_id in names:
            _nonempty_text(arm_id, "arm_id")
        if len(names) != len(set(names)):
            raise HarnessViolation("DUPLICATE_ARM_ID", "arm ids must be unique")
        supplied_names = dict(run_names or {})
        if set(supplied_names) - set(names):
            raise HarnessViolation(
                "UNKNOWN_RUN_NAME_ARM", "run_names contains an undeclared arm"
            )
        resolved_names = {
            arm_id: supplied_names.get(arm_id, f"{self.experiment_id}:{arm_id}")
            for arm_id in names
        }
        if len(set(resolved_names.values())) != len(resolved_names):
            raise HarnessViolation("DUPLICATE_RUN_ID", "named arm runs must be unique")
        self._runs = {
            arm_id: ArmRun(
                experiment_id=self.experiment_id,
                run_id=_nonempty_text(resolved_names[arm_id], "run_id"),
                arm_id=arm_id,
                frozen_artifact=self.frozen_artifact,
            )
            for arm_id in names
        }

    @property
    def arm_ids(self) -> tuple[str, ...]:
        return tuple(self._runs)

    def arm(self, arm_id: str) -> ArmRun:
        try:
            return self._runs[arm_id]
        except KeyError as exc:
            raise HarnessViolation("ARM_UNKNOWN", f"unknown arm {arm_id!r}") from exc


def _require_event_fields(event: Mapping[str, Any], index: int) -> None:
    required = {
        "schema",
        "experiment_id",
        "run_id",
        "arm_id",
        "seq",
        "request_id",
        "event_type",
        "parent_event_sha256",
        "starting_artifact_sha256",
        "state_before",
        "state_after",
        "state_snapshot",
        "payload",
        "intent_sha256",
        "event_sha256",
    }
    missing = sorted(required - set(event))
    if missing:
        raise HarnessViolation(
            "EVENT_MISSING_FIELDS", f"event {index} is missing {','.join(missing)}"
        )
    unexpected = sorted(set(event) - required)
    if unexpected:
        raise HarnessViolation(
            "EVENT_UNEXPECTED_FIELDS",
            f"event {index} has undeclared fields {','.join(unexpected)}",
        )


def replay_arm(
    *,
    starting_artifact: Any,
    experiment_id: str,
    run_id: str,
    arm_id: str,
    events: Sequence[Mapping[str, Any]],
    expected_artifact_sha256: str | None = None,
) -> ReplayResult:
    """Fail closed over one arm chain and derive its terminal state digest."""

    experiment_id = _nonempty_text(experiment_id, "experiment_id")
    run_id = _nonempty_text(run_id, "run_id")
    arm_id = _nonempty_text(arm_id, "arm_id")
    frozen = FrozenArtifact.freeze(starting_artifact)
    if expected_artifact_sha256 is not None and frozen.sha256 != expected_artifact_sha256:
        raise HarnessViolation(
            "STARTING_ARTIFACT_MISMATCH", "starting artifact does not match the arm binding"
        )
    artifact_sha256 = expected_artifact_sha256 or frozen.sha256
    state = frozen.clone()
    parent_sha256 = _genesis_sha256(
        experiment_id, run_id, arm_id, artifact_sha256
    )
    request_intents: dict[str, str] = {}

    for index, raw_event in enumerate(events):
        if not isinstance(raw_event, Mapping):
            raise HarnessViolation("EVENT_INVALID", f"event {index} must be an object")
        event = _clone_json(dict(raw_event))
        _require_event_fields(event, index)
        if event["schema"] != EVENT_SCHEMA:
            raise HarnessViolation("EVENT_SCHEMA_MISMATCH", f"event {index} schema drift")
        if event["experiment_id"] != experiment_id:
            raise HarnessViolation(
                "EVENT_EXPERIMENT_MISMATCH", f"event {index} belongs to another experiment"
            )
        if event["arm_id"] != arm_id:
            raise HarnessViolation(
                "CROSS_ARM_EVENT", f"event {index} belongs to arm {event['arm_id']!r}"
            )
        if event["run_id"] != run_id:
            raise HarnessViolation(
                "EVENT_RUN_MISMATCH", f"event {index} belongs to another run"
            )
        if event["starting_artifact_sha256"] != artifact_sha256:
            raise HarnessViolation(
                "STARTING_ARTIFACT_REFERENCE_MISMATCH",
                f"event {index} references another starting artifact",
            )
        if not isinstance(event["seq"], int) or isinstance(event["seq"], bool):
            raise HarnessViolation("EVENT_SEQUENCE_INVALID", f"event {index} seq is not an int")
        if event["seq"] != index:
            raise HarnessViolation(
                "EVENT_SEQUENCE_MISMATCH",
                f"expected seq {index}, observed {event['seq']}",
            )
        if event["parent_event_sha256"] != parent_sha256:
            raise HarnessViolation(
                "EVENT_PARENT_MISMATCH",
                f"event {index} parent does not match this arm chain",
            )
        if event["event_type"] not in EVENT_TYPES:
            raise HarnessViolation("EVENT_TYPE_INVALID", f"event {index} type is invalid")
        if not isinstance(event["payload"], Mapping):
            raise HarnessViolation("PAYLOAD_INVALID", f"event {index} payload is not an object")
        if _padding_requested(event["payload"]):
            raise HarnessViolation(
                "PADDING_EVENT_FORBIDDEN", f"event {index} is an accounting pad"
            )
        request_id = _nonempty_text(event["request_id"], "request_id")
        if request_id in request_intents:
            raise HarnessViolation(
                "DUPLICATE_REQUEST_EVENT",
                f"exact retry {request_id!r} must not append a second event",
            )

        before_ref = event["state_before"]
        after_ref = event["state_after"]
        if not isinstance(before_ref, Mapping) or not isinstance(after_ref, Mapping):
            raise HarnessViolation(
                "STATE_REFERENCE_INVALID", f"event {index} state references must be objects"
            )
        if before_ref.get("arm_id") != arm_id or after_ref.get("arm_id") != arm_id:
            raise HarnessViolation(
                "CROSS_ARM_STATE_REFERENCE",
                f"event {index} state reference belongs to another arm",
            )
        observed_before = _state_sha256(run_id, arm_id, state)
        if before_ref.get("sha256") != observed_before:
            raise HarnessViolation(
                "STATE_BEFORE_MISMATCH", f"event {index} does not continue terminal state"
            )

        if event["event_type"] == "update":
            next_state = _clone_json(event["state_snapshot"])
            state_argument: Any = next_state
        else:
            if event["state_snapshot"] is not None:
                raise HarnessViolation(
                    "NON_UPDATE_STATE_MUTATION",
                    f"event {index} carries state outside an update",
                )
            next_state = _clone_json(state)
            state_argument = "<UNCHANGED>"
        observed_after = _state_sha256(run_id, arm_id, next_state)
        if after_ref.get("sha256") != observed_after:
            raise HarnessViolation(
                "STATE_AFTER_MISMATCH", f"event {index} next-state digest is invalid"
            )
        expected_intent = _intent_sha256(
            event["event_type"], event["payload"], state_argument
        )
        if event["intent_sha256"] != expected_intent:
            raise HarnessViolation(
                "EVENT_INTENT_MISMATCH", f"event {index} intent digest is invalid"
            )
        if event["event_sha256"] != _event_sha256(event):
            raise HarnessViolation(
                "EVENT_HASH_MISMATCH", f"event {index} bytes were tampered"
            )

        request_intents[request_id] = expected_intent
        state = next_state
        parent_sha256 = str(event["event_sha256"])

    terminal_state_sha256 = _state_sha256(run_id, arm_id, state)
    replay_payload = {
        "schema": REPLAY_SCHEMA,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "arm_id": arm_id,
        "starting_artifact_sha256": artifact_sha256,
        "event_count": len(events),
        "terminal_state_sha256": terminal_state_sha256,
        "terminal_event_sha256": parent_sha256,
    }
    return ReplayResult(
        experiment_id=experiment_id,
        run_id=run_id,
        arm_id=arm_id,
        event_count=len(events),
        terminal_state_sha256=terminal_state_sha256,
        terminal_event_sha256=parent_sha256,
        replay_sha256=canonical_sha256(replay_payload),
        _terminal_state_bytes=canonical_json_bytes(state),
    )


def _mutable_object_ids(value: Any) -> set[int]:
    ids: set[int] = set()
    if isinstance(value, dict):
        ids.add(id(value))
        for child in value.values():
            ids.update(_mutable_object_ids(child))
    elif isinstance(value, list):
        ids.add(id(value))
        for child in value:
            ids.update(_mutable_object_ids(child))
    return ids


def _receipt_sha256(receipt: Mapping[str, Any]) -> str:
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    return canonical_sha256(unsigned)


def _derive_event_topology(
    *, arm_id: str, events: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Count only counters that canonical replay events can independently prove.

    In this E1 slice one ``update`` envelope is one update packet, while
    ``evaluation_cadence`` is the count of evaluation envelopes per task/split.
    Ordered event sequence numbers are bound so the receipt exposes the observed
    cadence topology without claiming wall-clock interval evidence.
    """

    scopes: dict[tuple[str, str], dict[str, Any]] = {}
    for index, event in enumerate(events):
        event_type = event.get("event_type")
        if event_type not in {"update", "evaluation"}:
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            raise HarnessViolation(
                "BUDGET_EVENT_TOPOLOGY_SCOPE_INVALID",
                f"arm {arm_id!r} event {index} lacks a scope payload",
            )
        task_id = _nonempty_text(payload.get("task_id"), "topology task_id")
        split_id = _nonempty_text(payload.get("split_id"), "topology split_id")
        key = (task_id, split_id)
        if key not in scopes:
            scopes[key] = {
                "task_id": task_id,
                "split_id": split_id,
                "update_packets": 0,
                "evaluation_cadence": 0,
                "update_event_seqs": [],
                "evaluation_event_seqs": [],
            }
        if event_type == "update":
            scopes[key]["update_packets"] += 1
            scopes[key]["update_event_seqs"].append(event["seq"])
        else:
            scopes[key]["evaluation_cadence"] += 1
            scopes[key]["evaluation_event_seqs"].append(event["seq"])

    topology: dict[str, Any] = {
        "schema": EVENT_TOPOLOGY_SCHEMA,
        "arm_id": arm_id,
        "derivable_counters": list(REPLAY_DERIVED_USAGE_COUNTERS),
        "counter_semantics": {
            "update_packets": "count(update events) per task_id/split_id",
            "evaluation_cadence": (
                "count(evaluation events) per task_id/split_id; ordered seqs are "
                "bound, wall-clock intervals are not proved"
            ),
        },
        "scopes": [scopes[key] for key in sorted(scopes)],
    }
    topology["topology_sha256"] = canonical_sha256(topology)
    return topology


def _require_projection_matches_event_topology(
    *, arm_id: str, projection: Mapping[str, Any], topology: Mapping[str, Any]
) -> None:
    projection_scopes = {
        (scope["task_id"], scope["split_id"]): scope
        for scope in projection["scopes"]
    }
    topology_scopes = {
        (scope["task_id"], scope["split_id"]): scope
        for scope in topology["scopes"]
    }
    for key in sorted(set(projection_scopes) | set(topology_scopes)):
        projection_scope = projection_scopes.get(key)
        topology_scope = topology_scopes.get(key)
        for dimension in REPLAY_DERIVED_USAGE_COUNTERS:
            asserted = (
                projection_scope["exact"][dimension]
                if projection_scope is not None
                else None
            )
            derived = topology_scope[dimension] if topology_scope is not None else 0
            if asserted != derived:
                raise HarnessViolation(
                    "BUDGET_EVENT_TOPOLOGY_MISMATCH",
                    f"arm {arm_id!r} {key[0]}/{key[1]} {dimension}: "
                    f"usage asserted {asserted!r}, replay derived {derived!r}",
                )


def build_engineering_receipt(
    *,
    experiment: ExperimentHarness,
    required_arms: Sequence[str],
    arm_inventories: Mapping[str, Mapping[str, Any]],
    evaluator_sha256: str,
    analysis_code_sha256: str,
    numeric_caps: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    """Replay and budget-project every arm before issuing the E1 engineering pass.

    Raw usage supplied directly by a caller is forbidden.  Usage must first be
    committed as canonical ``budget`` events, survive arm replay, and then be
    extracted from those verified event envelopes.
    """

    if not isinstance(experiment, ExperimentHarness):
        raise HarnessViolation("HARNESS_INVALID", "experiment must be an ExperimentHarness")
    supplied_arms = list(required_arms)
    for arm_id in supplied_arms:
        _nonempty_text(arm_id, "required arm")
    if (
        len(supplied_arms) != len(set(supplied_arms))
        or set(supplied_arms) != set(CANONICAL_ARM_IDS)
    ):
        raise HarnessViolation(
            "RECEIPT_ARM_SET_INVALID",
            "required arms must be exactly the canonical A/B/C/D arm IDs",
        )
    arms = list(CANONICAL_ARM_IDS)
    if not _is_sha256(evaluator_sha256) or not _is_sha256(analysis_code_sha256):
        raise HarnessViolation(
            "CODE_HASH_INVALID", "evaluator and analysis bindings must be lowercase SHA-256"
        )
    missing_harness_arms = sorted(set(arms) - set(experiment.arm_ids))
    extra_harness_arms = sorted(set(experiment.arm_ids) - set(arms))
    if missing_harness_arms or extra_harness_arms:
        raise HarnessViolation(
            "RECEIPT_ARM_SET_INVALID",
            "harness arms must exactly match canonical A/B/C/D; "
            f"missing={missing_harness_arms}, extra={extra_harness_arms}",
        )
    if not isinstance(arm_inventories, Mapping):
        raise HarnessViolation("INVENTORY_SET_INVALID", "arm_inventories must be an object")
    missing_inventory_arms = sorted(set(arms) - set(arm_inventories))
    extra_inventory_arms = sorted(set(arm_inventories) - set(arms))
    if missing_inventory_arms or extra_inventory_arms:
        raise HarnessViolation(
            "RECEIPT_ARM_MISSING",
            "inventory arms must exactly match required arms; "
            f"missing={missing_inventory_arms}, extra={extra_inventory_arms}",
        )

    try:
        import budget_ledger as budget
    except ImportError as exc:  # pragma: no cover - installation failure, not policy
        raise HarnessViolation("BUDGET_LEDGER_UNAVAILABLE", str(exc)) from exc

    verified_replays: dict[str, ReplayResult] = {}
    verified_event_logs: dict[str, tuple[dict[str, Any], ...]] = {}
    derived_artifacts: dict[str, dict[str, Any]] = {}
    inventory_hashes: dict[str, dict[str, str]] = {}
    mutable_id_sets: list[set[int]] = []
    run_ids: set[str] = set()
    for arm_id in arms:
        run = experiment.arm(arm_id)
        events = run.events
        observed_types = {event.get("event_type") for event in events}
        missing_types = sorted(EVENT_TYPES - observed_types)
        if missing_types:
            raise HarnessViolation(
                "EVENT_TYPE_COVERAGE_MISSING",
                f"arm {arm_id!r} lacks {','.join(missing_types)}",
            )
        replay = run.replay(events)
        verified_replays[arm_id] = replay
        verified_event_logs[arm_id] = events
        if run.run_id in run_ids:
            raise HarnessViolation("CROSS_ARM_RUN_ID", "arm runs must have unique run ids")
        run_ids.add(run.run_id)
        mutable_ids = _mutable_object_ids(run._starting_state)  # noqa: SLF001
        mutable_ids.update(_mutable_object_ids(run._state))  # noqa: SLF001
        mutable_id_sets.append(mutable_ids)

        inventory_artifacts = arm_inventories[arm_id]
        if not isinstance(inventory_artifacts, Mapping):
            raise HarnessViolation(
                "INVENTORY_SET_INVALID", f"inventory artifacts for {arm_id!r} are invalid"
            )
        if "usage_events" in inventory_artifacts:
            raise HarnessViolation(
                "DIRECT_USAGE_ARTIFACT_FORBIDDEN",
                "receipt usage must be extracted from verified harness events",
            )
        parameters = inventory_artifacts.get("parameter_inventory")
        states = inventory_artifacts.get("serialized_state_inventory")
        if not isinstance(parameters, Mapping) or not isinstance(states, Mapping):
            raise HarnessViolation(
                "INVENTORY_SET_INVALID", f"arm {arm_id!r} lacks both inventories"
            )
        try:
            usage_events = budget.extract_usage_events(events)
        except budget.BudgetViolation as exc:
            raise HarnessViolation(exc.code, str(exc)) from exc
        derived_artifacts[arm_id] = {
            "usage_events": usage_events,
            "parameter_inventory": parameters,
            "serialized_state_inventory": states,
        }
        inventory_hashes[arm_id] = {
            "parameter_inventory_sha256": canonical_sha256(dict(parameters)),
            "serialized_state_inventory_sha256": canonical_sha256(dict(states)),
        }

    for index, left in enumerate(mutable_id_sets):
        for right in mutable_id_sets[index + 1 :]:
            if left & right:
                raise HarnessViolation(
                    "CROSS_ARM_MUTABLE_ALIAS", "arm state graphs share mutable objects"
                )

    try:
        parity = budget.compare_budget_parity(
            arm_artifacts=derived_artifacts,
            compared_arms=EXACT_PARITY_COHORT,
            shared_artifact_arms=CANONICAL_ARM_IDS,
            numeric_caps=numeric_caps,
        )
    except budget.BudgetViolation as exc:
        raise HarnessViolation(exc.code, str(exc)) from exc
    if not parity["engineering_budget_valid"]:
        codes = sorted({item["code"] for item in parity["mismatches"]})
        raise HarnessViolation(
            "BUDGET_INVALID", f"artifact parity failed with {','.join(codes)}"
        )

    event_topologies: dict[str, dict[str, Any]] = {}
    for arm_id in arms:
        topology = _derive_event_topology(
            arm_id=arm_id, events=verified_event_logs[arm_id]
        )
        _require_projection_matches_event_topology(
            arm_id=arm_id,
            projection=parity["projections"][arm_id],
            topology=topology,
        )
        event_topologies[arm_id] = topology

    arm_replays: dict[str, dict[str, Any]] = {}
    for arm_id in arms:
        replay = verified_replays[arm_id]
        projection = parity["projections"][arm_id]
        arm_replays[arm_id] = {
            "run_id": replay.run_id,
            "event_count": replay.event_count,
            "event_root_sha256": replay.terminal_event_sha256,
            "terminal_state_sha256": replay.terminal_state_sha256,
            "replay_sha256": replay.replay_sha256,
            "usage_event_count": projection["source"]["usage_event_count"],
            "usage_events_sha256": projection["source"]["usage_events_sha256"],
            "parameter_inventory_sha256": inventory_hashes[arm_id][
                "parameter_inventory_sha256"
            ],
            "serialized_state_inventory_sha256": inventory_hashes[arm_id][
                "serialized_state_inventory_sha256"
            ],
            "inventory_sha256": projection["source"]["inventory_sha256"],
            "budget_projection_sha256": projection["projection_sha256"],
            "shared_immutable_state_bindings_sha256": canonical_sha256(
                projection["inventory"]["shared_immutable_state_bindings"]
            ),
            "event_topology": {
                key: value
                for key, value in event_topologies[arm_id].items()
                if key != "topology_sha256"
            },
            "event_topology_sha256": event_topologies[arm_id]["topology_sha256"],
        }

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "pass_code": EXPERIMENT_HARNESS_PASS,
        "authority": "ENGINEERING_ONLY",
        "scientific_verdict": None,
        "experiment_id": experiment.experiment_id,
        "starting_artifact_sha256": experiment.frozen_artifact.sha256,
        "required_arms": arms,
        "arm_roles": [
            {"arm_id": arm_id, "role_id": ARM_ROLE_IDS[arm_id]}
            for arm_id in arms
        ],
        "arm_replays": arm_replays,
        "isolation": {
            "unique_run_ids": True,
            "mutable_state_object_ids_disjoint": True,
            "cross_arm_references_rejected_by_replay": True,
        },
        "budget": {
            "engineering_budget_valid": True,
            "equal_measured_budget": True,
            "exact_parity_cohort": list(EXACT_PARITY_COHORT),
            "shared_immutable_state_cohort": list(CANONICAL_ARM_IDS),
            "control_arm_policy": {
                "policy_code": CONTROL_BUDGET_POLICY_CODE,
                "arms": list(CONTROL_ARM_IDS),
                "exact_equality_exempt": True,
                "required_guards": [
                    "canonical_participation_and_role_binding",
                    "complete_source_backed_projection",
                    "inventory_validation",
                    "numeric_caps",
                    "shared_immutable_state_identity",
                    "replay_counter_consistency",
                ],
            },
            "replay_derived_usage_counters": list(
                REPLAY_DERIVED_USAGE_COUNTERS
            ),
            "raw_usage_only_not_replay_derivable": ["dispatch_count"],
            "event_topology_consistent_with_usage": True,
            "parity_sha256": parity["parity_sha256"],
            "capped_resources_within_limits": parity[
                "capped_resources_within_limits"
            ],
        },
        "code_bindings": {
            "evaluator_sha256": evaluator_sha256,
            "analysis_code_sha256": analysis_code_sha256,
        },
        "claim_boundary": {
            "preregistration_claimed": False,
            "efficacy_claimed": False,
            "winner_claimed": False,
            "production_claimed": False,
        },
    }
    receipt["receipt_sha256"] = _receipt_sha256(receipt)
    return receipt


def verify_engineering_receipt(
    *,
    receipt: Mapping[str, Any],
    experiment: ExperimentHarness,
    required_arms: Sequence[str],
    arm_inventories: Mapping[str, Mapping[str, Any]],
    evaluator_sha256: str,
    analysis_code_sha256: str,
    numeric_caps: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    """Rebuild every receipt fact from live artifacts and require byte equality."""

    if not isinstance(receipt, Mapping):
        raise HarnessViolation("RECEIPT_INVALID", "receipt must be an object")
    observed = _clone_json(dict(receipt))
    if observed.get("schema") != RECEIPT_SCHEMA:
        raise HarnessViolation("RECEIPT_SCHEMA_MISMATCH", "receipt schema drift")
    if observed.get("receipt_sha256") != _receipt_sha256(observed):
        raise HarnessViolation("RECEIPT_HASH_MISMATCH", "receipt bytes were altered")
    expected = build_engineering_receipt(
        experiment=experiment,
        required_arms=required_arms,
        arm_inventories=arm_inventories,
        evaluator_sha256=evaluator_sha256,
        analysis_code_sha256=analysis_code_sha256,
        numeric_caps=numeric_caps,
    )
    if canonical_json_bytes(observed) != canonical_json_bytes(expected):
        raise HarnessViolation(
            "RECEIPT_EVIDENCE_MISMATCH",
            "receipt does not match replay, budget, inventory, or code artifacts",
        )
    return expected


__all__ = [
    "ARM_ROLE_IDS",
    "ArmRun",
    "CANONICAL_ARM_IDS",
    "CONTROL_ARM_IDS",
    "CONTROL_BUDGET_POLICY_CODE",
    "EVENT_SCHEMA",
    "EVENT_TOPOLOGY_SCHEMA",
    "EVENT_TYPES",
    "EXACT_PARITY_COHORT",
    "EXPERIMENT_HARNESS_PASS",
    "ExperimentHarness",
    "FrozenArtifact",
    "HarnessViolation",
    "ReplayResult",
    "REPLAY_DERIVED_USAGE_COUNTERS",
    "RECEIPT_SCHEMA",
    "build_engineering_receipt",
    "canonical_json_bytes",
    "canonical_sha256",
    "replay_arm",
    "verify_engineering_receipt",
]
