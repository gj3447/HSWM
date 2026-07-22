#!/usr/bin/env python3
"""Pure reducer for immutable HSWM absorption candidates.

The active HSWM is never edited by this module.  Each absorption round owns one
immutable candidate lifecycle.  IO is represented by typed commands; registry,
evaluation, and persistence adapters return later events/receipts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping


MAX_EVENTS = 4096
FINAL_STATES = {"rejected", "quarantined", "rolled_back", "superseded"}


@dataclass(frozen=True)
class CandidateConfig:
    candidate_id: str
    implementer_id: str
    base_version: str
    rollback_target_hash: str
    state: str = "collecting"
    candidate_hash: str = ""
    evaluated_candidate_hash: str = ""
    evaluator_id: str = ""
    absorbed_count: int = 0
    expected_seq: int = 0
    canary_windows_passed: int = 0
    required_canary_windows: int = 1
    policy_min_unseen_gain: float = 0.01
    policy_max_retention_drop: float = -0.01
    seen_event_hashes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Command:
    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class Transition:
    id: str
    source: str
    event: str
    target: str
    guard: str | None
    priority: int
    effect: str


def _transition(
    transition_id: str,
    source: str,
    event: str,
    target: str,
    effect: str,
    guard: str | None = None,
    priority: int = 0,
) -> Transition:
    return Transition(transition_id, source, event, target, guard, priority, effect)


TRANSITIONS = (
    _transition("absorb", "collecting", "ABSORB", "collecting", "RecordAbsorption"),
    _transition("freeze", "collecting", "FREEZE", "frozen", "FreezeCandidate", "freeze_allowed"),
    _transition("start_evaluation", "frozen", "START_EVALUATION", "evaluating", "RunEvaluation", "evaluation_allowed"),
    _transition("quarantine_invalid_evidence", "evaluating", "EVALUATION_RECORDED", "quarantined", "QuarantineCandidate", "evidence_invalid", 1),
    _transition("evaluation_pass", "evaluating", "EVALUATION_RECORDED", "canary", "RecordEvaluationPass", "promotion_allowed", 2),
    _transition("evaluation_reject", "evaluating", "EVALUATION_RECORDED", "rejected", "RecordRejection", "evaluation_rejected", 3),
    _transition("canary_observation", "canary", "CANARY_OBSERVATION", "canary", "RecordCanary", "canary_observation_pass"),
    _transition("canary_failed", "canary", "CANARY_FAILED", "rejected", "RecordRejection"),
    _transition("request_promotion", "canary", "REQUEST_PROMOTION", "promotion_pending", "RequestActivation", "canary_complete"),
    _transition("activation_committed", "promotion_pending", "ACTIVATION_COMMITTED", "active", "RecordActivation", "activation_receipt_matches"),
    _transition("activation_retry", "promotion_pending", "ACTIVATION_FAILED", "canary", "RecordActivationFailure", "activation_transient", 1),
    _transition("activation_stale_reject", "promotion_pending", "ACTIVATION_FAILED", "rejected", "RecordRejection", "activation_stale", 2),
    _transition("regression_to_rollback", "active", "REGRESSION_DETECTED", "rollback_pending", "RequestRollback", "regression_confirmed"),
    _transition("active_superseded", "active", "SUPERSESSION_COMMITTED", "superseded", "RecordSupersession", "supersession_receipt_matches"),
    _transition("rollback_committed", "rollback_pending", "ROLLBACK_COMMITTED", "rolled_back", "RecordRollback", "rollback_receipt_matches"),
    _transition("rollback_retry", "rollback_pending", "ROLLBACK_FAILED", "rollback_pending", "RecordRollbackFailure"),
    _transition("rollback_superseded", "rollback_pending", "SUPERSESSION_COMMITTED", "superseded", "RecordSupersession", "supersession_receipt_matches"),
)
EVENT_TYPES = {transition.event for transition in TRANSITIONS}


def canonical_event_hash(event: Mapping[str, Any]) -> str:
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def make_event(
    config: CandidateConfig,
    event_type: str,
    event_id: str,
    actor: str,
    **payload: Any,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "candidate_id": config.candidate_id,
        "actor": actor,
        "event_id": event_id,
        "seq": config.expected_seq,
        **payload,
    }


def _nonempty(event: Mapping[str, Any], *fields: str) -> bool:
    return all(isinstance(event.get(field), str) and bool(event[field]) for field in fields)


def freeze_allowed(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    return config.absorbed_count > 0 and _nonempty(
        event, "candidate_hash", "prereg_hash", "split_manifest_hash"
    )


def evaluation_allowed(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    return (
        event.get("candidate_hash") == config.candidate_hash
        and event.get("fresh_holdout") is True
        and _nonempty(event, "holdout_epoch", "evaluator_id")
        and event.get("evaluator_id") != config.implementer_id
    )


def evidence_invalid(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    return not (
        event.get("candidate_hash") == config.candidate_hash
        and _nonempty(event, "evidence_hash")
        and event.get("evidence_replayed") is True
        and event.get("equal_budget") is True
        and event.get("no_overlap") is True
        and event.get("independent_evaluator") is True
    )


def promotion_allowed(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    if evidence_invalid(config, event):
        return False
    return (
        float(event.get("unseen_delta", float("-inf"))) >= config.policy_min_unseen_gain
        and float(event.get("unseen_ci_low", float("-inf"))) > 0.0
        and float(event.get("retention_delta", float("-inf")))
        >= config.policy_max_retention_drop
    )


def evaluation_rejected(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    return not evidence_invalid(config, event) and not promotion_allowed(config, event)


def canary_observation_pass(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    del config
    return event.get("no_regression") is True and event.get("equal_budget") is True


def canary_complete(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    del event
    return config.canary_windows_passed >= config.required_canary_windows


def activation_receipt_matches(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    return (
        event.get("candidate_hash") == config.candidate_hash
        and event.get("base_version") == config.base_version
        and _nonempty(event, "receipt_hash")
    )


def activation_transient(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    del config
    return event.get("failure_class") == "transient"


def activation_stale(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    del config
    return event.get("failure_class") == "stale_base"


def regression_confirmed(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    del config
    return event.get("confirmed") is True


def rollback_receipt_matches(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    return (
        event.get("rollback_target_hash") == config.rollback_target_hash
        and _nonempty(event, "receipt_hash")
    )


def supersession_receipt_matches(config: CandidateConfig, event: Mapping[str, Any]) -> bool:
    del config
    return _nonempty(event, "successor_hash", "receipt_hash")


GUARDS: dict[str, Callable[[CandidateConfig, Mapping[str, Any]], bool]] = {
    name: value
    for name, value in globals().copy().items()
    if name in {
        "freeze_allowed",
        "evaluation_allowed",
        "evidence_invalid",
        "promotion_allowed",
        "evaluation_rejected",
        "canary_observation_pass",
        "canary_complete",
        "activation_receipt_matches",
        "activation_transient",
        "activation_stale",
        "regression_confirmed",
        "rollback_receipt_matches",
        "supersession_receipt_matches",
    }
}


def _audit(config: CandidateConfig, event: Mapping[str, Any], reason: str) -> Command:
    return Command(
        "AuditInvalidTransition",
        {
            "state": config.state,
            "event": str(event.get("type", "UNKNOWN")),
            "actor": str(event.get("actor", "unknown")),
            "reason": reason,
            "event_id": str(event.get("event_id", "missing")),
        },
    )


def _effect_payload(effect: str, config: CandidateConfig, event: Mapping[str, Any]) -> dict[str, Any]:
    common = {"candidate_id": config.candidate_id}
    if effect == "RecordAbsorption":
        return {**common, "event_id": event["event_id"], "source_manifest_hash": event["source_manifest_hash"]}
    if effect == "FreezeCandidate":
        return {**common, "candidate_hash": event["candidate_hash"]}
    if effect == "RunEvaluation":
        return {**common, "candidate_hash": event["candidate_hash"], "holdout_epoch": event["holdout_epoch"]}
    if effect == "RecordEvaluationPass":
        return {**common, "evidence_hash": event["evidence_hash"]}
    if effect in {"RecordRejection", "QuarantineCandidate", "RecordActivationFailure", "RequestRollback", "RecordRollbackFailure"}:
        return {**common, "reason": event["reason"]}
    if effect == "RecordCanary":
        return {**common, "window_id": event["window_id"]}
    if effect == "RequestActivation":
        return {**common, "request_id": event["request_id"]}
    if effect in {"RecordActivation", "RecordRollback", "RecordSupersession"}:
        return {**common, "receipt_hash": event["receipt_hash"]}
    raise KeyError(f"unbound effect {effect}")


def _remember(config: CandidateConfig, event: Mapping[str, Any]) -> CandidateConfig:
    remembered = config.seen_event_hashes + ((str(event["event_id"]), canonical_event_hash(event)),)
    return replace(config, expected_seq=config.expected_seq + 1, seen_event_hashes=remembered)


def step(config: CandidateConfig, event: Mapping[str, Any]) -> tuple[CandidateConfig, list[Command]]:
    """Reduce one event without performing IO.

    Invalid envelopes, duplicates, reorderings, false guards, and wrong-state
    events leave the complete configuration unchanged and emit one audit command.
    """
    required = {"type", "candidate_id", "actor", "event_id", "seq"}
    missing = sorted(required - set(event))
    if missing:
        return config, [_audit(config, event, f"missing_fields:{','.join(missing)}")]
    if event["candidate_id"] != config.candidate_id:
        return config, [_audit(config, event, "candidate_id_mismatch")]
    if event["type"] not in EVENT_TYPES:
        return config, [_audit(config, event, "unknown_event")]

    event_id = str(event["event_id"])
    event_hash = canonical_event_hash(event)
    seen = dict(config.seen_event_hashes)
    if event_id in seen:
        reason = "duplicate_noop" if seen[event_id] == event_hash else "conflicting_duplicate_tamper"
        return config, [_audit(config, event, reason)]
    if len(config.seen_event_hashes) >= MAX_EVENTS:
        return config, [_audit(config, event, "candidate_event_bound_exceeded")]
    if not isinstance(event["seq"], int) or isinstance(event["seq"], bool):
        return config, [_audit(config, event, "seq_not_integer")]
    if event["seq"] != config.expected_seq:
        return config, [_audit(config, event, f"reordered_expected_{config.expected_seq}")]
    if config.state in FINAL_STATES:
        return config, [_audit(config, event, "terminal_state")]

    choices = sorted(
        (
            transition
            for transition in TRANSITIONS
            if transition.source == config.state and transition.event == event["type"]
        ),
        key=lambda transition: transition.priority,
    )
    if not choices:
        return config, [_audit(config, event, "invalid_state_event")]

    selected: Transition | None = None
    for transition in choices:
        if transition.guard is None or GUARDS[transition.guard](config, event):
            selected = transition
            break
    if selected is None:
        return config, [_audit(config, event, "guard_false")]

    updated = replace(config, state=selected.target)
    if selected.id == "absorb":
        updated = replace(updated, absorbed_count=config.absorbed_count + 1)
    elif selected.id == "freeze":
        updated = replace(updated, candidate_hash=str(event["candidate_hash"]))
    elif selected.id == "start_evaluation":
        updated = replace(
            updated,
            evaluated_candidate_hash=config.candidate_hash,
            evaluator_id=str(event["evaluator_id"]),
        )
    elif selected.id == "canary_observation":
        updated = replace(updated, canary_windows_passed=config.canary_windows_passed + 1)

    updated = _remember(updated, event)
    return updated, [Command(selected.effect, _effect_payload(selected.effect, config, event))]


__all__ = [
    "CandidateConfig",
    "Command",
    "TRANSITIONS",
    "canonical_event_hash",
    "make_event",
    "step",
]
