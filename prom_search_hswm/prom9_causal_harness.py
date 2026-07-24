#!/usr/bin/env python3
"""Causal judges for PROM-9 P1v5 weight learning and P2 agent transfer.

This module consumes immutable experiment packets.  It does not fit a learner,
activate a weight, open a sealed split, or call an LLM.  Its job is to reject a
performance table unless the table is bound to a real snapshot transition,
used-bond eligibility, frozen-agent identity, matched budgets, and causal
removal.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import random
import re
from collections.abc import Mapping, Sequence

from hswm_weight_snapshot import (
    WeightContractError,
    apply_candidate,
    candidate_from_mapping,
    snapshot_from_mapping,
)
from prom_search_hswm.hswm_typed_ports import canonical_sha256


P1V5_PACKET_SCHEMA = "hswm-prom9-p1v5-causal-packet/v1"
P1V5_JUDGMENT_SCHEMA = "hswm-prom9-p1v5-causal-judgment/v1"
P2_PACKET_SCHEMA = "hswm-prom9-p2-transfer-packet/v1"
P2_JUDGMENT_SCHEMA = "hswm-prom9-p2-transfer-judgment/v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")

P1V5_ARMS = (
    "frozen_merged_neutral",
    "query_conditioned_fast_bond_only",
    "fast_then_validated_slow_promotion",
    "static_global_exact_answer_update",
    "random_credit",
    "shuffled_eligibility",
    "no_promotion",
    "slow_promotion_then_causal_removal",
    "equal_budget_flat_reranker",
    "equal_budget_vector_memory",
)
P2_ARMS = (
    "frozen_agent_b_no_agent_a_information",
    "agent_a_transcript_only",
    "flat_memory_write",
    "vector_memory_write",
    "accepted_hswm_slow_weight_write",
    "accepted_hswm_write_then_causal_removal",
)


class CausalHarnessError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise CausalHarnessError(f"duplicate key in {label}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CausalHarnessError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise CausalHarnessError(f"{label} must be an object")
    return value


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise CausalHarnessError(f"refusing to replace output: {path}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise CausalHarnessError(
            f"{label} keys drifted: missing={sorted(expected-set(value))}, "
            f"extra={sorted(set(value)-expected)}"
        )


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CausalHarnessError(f"{label} must be non-empty text")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise CausalHarnessError(f"{label} must be a lowercase SHA-256")
    return value


def _score(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CausalHarnessError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise CausalHarnessError(f"{label} must be finite and in [0, 1]")
    return result


def _mode_and_receipts(
    value: Mapping[str, object], *, prereg_key: str, required_receipts: Sequence[str]
) -> str:
    mode = value.get("mode")
    if mode not in {"development", "sealed"}:
        raise CausalHarnessError("mode must be development or sealed")
    for key in required_receipts:
        raw = value.get(key)
        if mode == "sealed" or raw is not None:
            _sha(raw, key)
    if mode == "sealed":
        _sha(value.get(prereg_key), prereg_key)
    elif value.get(prereg_key) is not None:
        _sha(value.get(prereg_key), prereg_key)
    return str(mode)


def _budget_gate(value: object, arms: Sequence[str]) -> tuple[bool, list[str]]:
    if not isinstance(value, dict):
        raise CausalHarnessError("budget_audit must be an object")
    _keys(
        value,
        {
            "calls_per_item_by_arm", "allowed_tokens_per_item_by_arm",
            "candidate_budget_by_arm", "state_capacity_bytes_by_arm",
            "consumed_token_spread_max", "token_tolerance",
        },
        "budget_audit",
    )
    failures: list[str] = []
    for field in (
        "calls_per_item_by_arm",
        "allowed_tokens_per_item_by_arm",
        "candidate_budget_by_arm",
        "state_capacity_bytes_by_arm",
    ):
        rows = value[field]
        if not isinstance(rows, dict) or set(rows) != set(arms):
            raise CausalHarnessError(f"{field} must exactly cover registered arms")
        normalized = []
        for arm in arms:
            raw = rows[arm]
            if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
                raise CausalHarnessError(f"{field} has invalid value for {arm}")
            normalized.append(raw)
        if len(set(normalized)) != 1:
            failures.append(f"{field}:not-equal")
    spread = value["consumed_token_spread_max"]
    tolerance = value["token_tolerance"]
    if any(isinstance(raw, bool) or not isinstance(raw, int) or raw < 0 for raw in (spread, tolerance)):
        raise CausalHarnessError("token spread and tolerance must be non-negative integers")
    if spread > tolerance:
        failures.append(f"consumed-token-spread:{spread}>{tolerance}")
    return not failures, failures


def _bootstrap_cluster(
    rows: Sequence[Mapping[str, object]],
    left: str,
    right: str,
    *,
    reps: int,
    seed: int,
) -> dict[str, object]:
    if not rows:
        return {"n": 0, "mean": None, "cluster_bootstrap95": [None, None]}
    clusters: dict[str, list[float]] = {}
    for row in rows:
        arms = row["arms"]
        clusters.setdefault(str(row["component_id"]), []).append(
            float(arms[left]) - float(arms[right])
        )
    cluster_ids = sorted(clusters)
    generator = random.Random(seed)
    boot = []
    for _ in range(reps):
        sampled = [cluster_ids[generator.randrange(len(cluster_ids))] for _ in cluster_ids]
        values = [value for cluster in sampled for value in clusters[cluster]]
        boot.append(sum(values) / len(values))
    boot.sort()
    values = [value for rows_in_cluster in clusters.values() for value in rows_in_cluster]
    return {
        "n": len(values),
        "clusters": len(cluster_ids),
        "mean": sum(values) / len(values),
        "cluster_bootstrap95": [
            boot[int(0.025 * (reps - 1))],
            boot[int(0.975 * (reps - 1))],
        ],
    }


def _mean_delta(rows: Sequence[Mapping[str, object]], left: str, right: str) -> float | None:
    if not rows:
        return None
    return sum(float(row["arms"][left]) - float(row["arms"][right]) for row in rows) / len(rows)


def _validate_rows(value: object, arms: Sequence[str], *, p1: bool) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        raise CausalHarnessError("measurement rows must be non-empty")
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise CausalHarnessError(f"row {index} must be an object")
        expected = {"item_id", "component_id", "dataset", "regime", "arms"}
        _keys(raw, expected, f"row {index}")
        item_id = _text(raw["item_id"], f"row {index} item_id")
        if item_id in seen:
            raise CausalHarnessError(f"duplicate measurement item: {item_id}")
        seen.add(item_id)
        arm_values = raw["arms"]
        if not isinstance(arm_values, dict) or set(arm_values) != set(arms):
            raise CausalHarnessError(f"row {item_id} must exactly cover registered arms")
        normalized_arms = {arm: _score(arm_values[arm], f"{item_id} {arm}") for arm in arms}
        regime = _text(raw["regime"], f"{item_id} regime")
        if p1 and regime not in {"fresh", "cross_field", "in_field", "canary"}:
            raise CausalHarnessError(f"unknown P1v5 regime: {regime}")
        if not p1 and regime != "fresh_unseen":
            raise CausalHarnessError("P2 rows must all be fresh_unseen")
        rows.append(
            {
                "item_id": item_id,
                "component_id": _text(raw["component_id"], f"{item_id} component_id"),
                "dataset": _text(raw["dataset"], f"{item_id} dataset"),
                "regime": regime,
                "arms": normalized_arms,
            }
        )
    return rows


def _validate_eligibility(value: object) -> dict[str, str]:
    if not isinstance(value, list) or not value:
        raise CausalHarnessError("eligibility_tags must be non-empty")
    tags: dict[str, str] = {}
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise CausalHarnessError(f"eligibility tag {index} must be an object")
        _keys(
            raw,
            {"schema_version", "edge_id", "tag_strength", "episode_id", "snapshot_id", "source_trace_ids", "tag_id"},
            f"eligibility tag {index}",
        )
        if raw["schema_version"] != "hswm-p1-eligibility-tag/v1":
            raise CausalHarnessError("unsupported eligibility tag schema")
        unsigned = dict(raw)
        tag_id = _sha(unsigned.pop("tag_id"), f"eligibility tag {index} id")
        if canonical_sha256(unsigned) != tag_id:
            raise CausalHarnessError(f"eligibility tag {index} self-hash drifted")
        edge_id = _text(raw["edge_id"], f"eligibility tag {index} edge")
        if edge_id in tags:
            raise CausalHarnessError(f"duplicate eligibility edge: {edge_id}")
        tags[edge_id] = tag_id
    return tags


def _snapshot_chain(
    base_raw: object,
    candidate_raw: object,
    promoted_raw: object,
    removal_raw: object,
) -> tuple[object, object, object]:
    if not all(isinstance(raw, Mapping) for raw in (base_raw, candidate_raw, promoted_raw, removal_raw)):
        raise CausalHarnessError("snapshot and candidate blocks must be objects")
    try:
        base = snapshot_from_mapping(base_raw)
        candidate = candidate_from_mapping(candidate_raw)
        promoted = snapshot_from_mapping(promoted_raw)
        removal = snapshot_from_mapping(removal_raw)
        expected = apply_candidate(base, candidate)
    except (KeyError, TypeError, ValueError, WeightContractError) as error:
        raise CausalHarnessError(f"invalid weight snapshot chain: {error}") from error
    if expected.canonical() != promoted.canonical():
        raise CausalHarnessError("promoted snapshot is not the candidate applied to base")
    if removal.topology_sha256 != base.topology_sha256 or removal.weight_map() != base.weight_map():
        raise CausalHarnessError("causal removal does not restore the base weight field")
    return base, candidate, promoted


def judge_p1v5(
    packet: Mapping[str, object], *, bootstrap_reps: int = 10000, bootstrap_seed: int = 20260724
) -> dict[str, object]:
    _keys(
        packet,
        {
            "schema_version", "run_id", "mode", "preregistration_receipt_sha256",
            "gate0_acceptance_receipt_sha256", "base_snapshot", "candidate",
            "promoted_snapshot", "removal_snapshot", "training", "evaluator",
            "leakage_audit", "budget_audit", "rows",
        },
        "P1v5 packet",
    )
    if packet.get("schema_version") != P1V5_PACKET_SCHEMA:
        raise CausalHarnessError("unsupported P1v5 packet schema")
    mode = _mode_and_receipts(
        packet,
        prereg_key="preregistration_receipt_sha256",
        required_receipts=("gate0_acceptance_receipt_sha256",),
    )
    _text(packet.get("run_id"), "run_id")
    base, candidate, promoted = _snapshot_chain(
        packet["base_snapshot"], packet["candidate"], packet["promoted_snapshot"], packet["removal_snapshot"]
    )
    training = packet["training"]
    if not isinstance(training, dict):
        raise CausalHarnessError("training must be an object")
    _keys(training, {"used_edge_ids", "eligibility_tags"}, "training")
    used = training["used_edge_ids"]
    if not isinstance(used, list) or not used or any(not isinstance(item, str) or not item for item in used) or len(used) != len(set(used)):
        raise CausalHarnessError("used_edge_ids must be unique non-empty text")
    tags = _validate_eligibility(training["eligibility_tags"])
    for delta in candidate.deltas:
        if delta.edge_id not in set(used):
            raise CausalHarnessError("candidate changes an edge that was not used")
        if tags.get(delta.edge_id) != delta.eligibility_tag_sha256:
            raise CausalHarnessError("candidate delta is not bound to its used-edge eligibility")
    evaluator = packet["evaluator"]
    if not isinstance(evaluator, dict):
        raise CausalHarnessError("evaluator must be an object")
    _keys(evaluator, {"independent", "receipt_sha256"}, "evaluator")
    evaluator_ok = evaluator["independent"] is True and bool(_sha(evaluator["receipt_sha256"], "evaluator receipt"))
    leakage = packet["leakage_audit"]
    if not isinstance(leakage, dict):
        raise CausalHarnessError("leakage_audit must be an object")
    _keys(leakage, {"split_disjoint", "gold_hidden_from_learner", "forbidden_features_absent", "replay_verified"}, "leakage_audit")
    leakage_ok = all(leakage[key] is True for key in leakage)
    budget_ok, budget_failures = _budget_gate(packet["budget_audit"], P1V5_ARMS)
    rows = _validate_rows(packet["rows"], P1V5_ARMS, p1=True)
    fresh = [row for row in rows if row["regime"] == "fresh"]
    cross = [row for row in rows if row["regime"] == "cross_field"]
    in_field = [row for row in rows if row["regime"] == "in_field"]
    canary = [row for row in rows if row["regime"] == "canary"]
    frozen = "frozen_merged_neutral"
    fast = "query_conditioned_fast_bond_only"
    slow = "fast_then_validated_slow_promotion"
    removed = "slow_promotion_then_causal_removal"
    comparisons = {
        "fresh_fast_minus_frozen": _bootstrap_cluster(fresh, fast, frozen, reps=bootstrap_reps, seed=bootstrap_seed),
        "fresh_slow_minus_frozen": _bootstrap_cluster(fresh, slow, frozen, reps=bootstrap_reps, seed=bootstrap_seed + 1),
        "fresh_slow_minus_removed": _bootstrap_cluster(fresh, slow, removed, reps=bootstrap_reps, seed=bootstrap_seed + 2),
        "fresh_random_minus_frozen": _bootstrap_cluster(fresh, "random_credit", frozen, reps=bootstrap_reps, seed=bootstrap_seed + 3),
        "fresh_shuffled_minus_frozen": _bootstrap_cluster(fresh, "shuffled_eligibility", frozen, reps=bootstrap_reps, seed=bootstrap_seed + 4),
        "cross_slow_minus_frozen": _bootstrap_cluster(cross, slow, frozen, reps=bootstrap_reps, seed=bootstrap_seed + 5),
        "in_field_slow_minus_frozen": _bootstrap_cluster(in_field, slow, frozen, reps=bootstrap_reps, seed=bootstrap_seed + 6),
        "canary_slow_minus_frozen": _bootstrap_cluster(canary, slow, frozen, reps=bootstrap_reps, seed=bootstrap_seed + 7),
    }
    dataset_deltas = {
        dataset: _mean_delta([row for row in fresh if row["dataset"] == dataset], slow, frozen)
        for dataset in sorted({str(row["dataset"]) for row in fresh})
    }
    slow_fresh = comparisons["fresh_slow_minus_frozen"]
    fast_fresh = comparisons["fresh_fast_minus_frozen"]
    removal_return = _mean_delta(fresh, removed, frozen)
    gates = {
        "snapshot_delta_is_real": promoted.snapshot_id != base.snapshot_id and bool(candidate.deltas),
        "used_bond_eligibility_bound": True,
        "independent_evaluator": evaluator_ok,
        "split_leakage_replay": leakage_ok,
        "equal_budget": budget_ok,
        "fast_effect_lcb_gt_0": bool(fresh) and fast_fresh["cluster_bootstrap95"][0] > 0.0,
        "slow_effect_lcb_gt_0": bool(fresh) and slow_fresh["cluster_bootstrap95"][0] > 0.0,
        "minimum_dataset_delta_gt_002": bool(dataset_deltas) and min(dataset_deltas.values()) > 0.02,
        "cross_retention_ge_minus_002": bool(cross) and comparisons["cross_slow_minus_frozen"]["mean"] >= -0.02,
        "in_field_retention_ge_minus_002": bool(in_field) and comparisons["in_field_slow_minus_frozen"]["mean"] >= -0.02,
        "canary_non_harm_ge_minus_002": bool(canary) and comparisons["canary_slow_minus_frozen"]["mean"] >= -0.02,
        "random_credit_fails": bool(fresh) and comparisons["fresh_random_minus_frozen"]["cluster_bootstrap95"][0] <= 0.0,
        "shuffled_eligibility_fails": bool(fresh) and comparisons["fresh_shuffled_minus_frozen"]["cluster_bootstrap95"][0] <= 0.0,
        "removal_erases_gain": removal_return is not None and abs(removal_return) <= 0.02 and comparisons["fresh_slow_minus_removed"]["mean"] > 0.0,
        "static_update_does_not_explain": (_mean_delta(fresh, slow, "static_global_exact_answer_update") or 0.0) > 0.0,
        "no_promotion_does_not_explain": (_mean_delta(fresh, slow, "no_promotion") or 0.0) > 0.0,
    }
    supported = all(gates.values())
    if mode == "development":
        verdict = "DEVELOPMENT_ONLY"
        allowed_claim = "No durable-learning claim; freeze the learner and register a prediction before sealed measurement."
    elif supported:
        verdict = "P1V5_SUPPORTED_NARROW"
        allowed_claim = "Outcome-bound used-bond eligibility produced a validated slow-weight snapshot whose fresh gain vanished under causal removal on the registered scope."
    elif gates["fast_effect_lcb_gt_0"]:
        verdict = "FAST_ONLY"
        allowed_claim = "Query-conditioned bond attention worked, but durable semantic-weight learning did not satisfy the full conjunction."
    else:
        verdict = "REJECTED_OR_NARROWED"
        allowed_claim = "The registered P1v5 causal conjunction was not satisfied."
    unsigned = {
        "schema_version": P1V5_JUDGMENT_SCHEMA,
        "run_id": packet["run_id"],
        "packet_sha256": canonical_sha256(packet),
        "mode": mode,
        "base_snapshot_id": base.snapshot_id,
        "candidate_id": candidate.candidate_id,
        "promoted_snapshot_id": promoted.snapshot_id,
        "evaluator_receipt_sha256": evaluator["receipt_sha256"],
        "bootstrap": {"reps": bootstrap_reps, "seed": bootstrap_seed, "unit": "component", "paired": True},
        "comparisons": comparisons,
        "fresh_dataset_deltas": dataset_deltas,
        "gates": gates,
        "budget_failures": budget_failures,
        "verdict": verdict,
        "allowed_claim": allowed_claim,
    }
    return {**unsigned, "judgment_sha256": canonical_sha256(unsigned)}


def _validate_freeze_manifest(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CausalHarnessError(f"{label} must be an object")
    _keys(
        value,
        {"model_sha256", "parameters_sha256", "prompt_sha256", "tools_sha256", "readout_sha256", "budget_sha256", "manifest_sha256"},
        label,
    )
    unsigned = dict(value)
    declared = _sha(unsigned.pop("manifest_sha256"), f"{label} manifest hash")
    for key, raw in unsigned.items():
        _sha(raw, f"{label} {key}")
    if canonical_sha256(unsigned) != declared:
        raise CausalHarnessError(f"{label} self-hash drifted")
    return dict(value)


def judge_p2(
    packet: Mapping[str, object], *, bootstrap_reps: int = 10000, bootstrap_seed: int = 20260724
) -> dict[str, object]:
    _keys(
        packet,
        {
            "schema_version", "run_id", "mode", "preregistration_receipt_sha256",
            "upstream_acceptance", "base_snapshot",
            "agent_a_candidate", "agent_a_snapshot", "removal_snapshot", "agent_a_write",
            "agent_b_freeze_before", "agent_b_freeze_after", "leakage_audit",
            "budget_audit", "evaluator", "rows",
        },
        "P2 packet",
    )
    if packet.get("schema_version") != P2_PACKET_SCHEMA:
        raise CausalHarnessError("unsupported P2 packet schema")
    mode = _mode_and_receipts(
        packet,
        prereg_key="preregistration_receipt_sha256",
        required_receipts=(),
    )
    _text(packet.get("run_id"), "run_id")
    upstream = packet["upstream_acceptance"]
    if not isinstance(upstream, dict):
        raise CausalHarnessError("upstream_acceptance must be an object")
    _keys(
        upstream,
        {"f1_judgment_sha256", "f1_verdict", "p1v5_judgment_sha256", "p1v5_verdict"},
        "upstream_acceptance",
    )
    _sha(upstream["f1_judgment_sha256"], "F1 judgment")
    _sha(upstream["p1v5_judgment_sha256"], "P1v5 judgment")
    upstream_ok = (
        upstream["f1_verdict"] == "F1_SUPPORTED_NARROW"
        and upstream["p1v5_verdict"] == "P1V5_SUPPORTED_NARROW"
    )
    base, candidate, agent_a_snapshot = _snapshot_chain(
        packet["base_snapshot"], packet["agent_a_candidate"], packet["agent_a_snapshot"], packet["removal_snapshot"]
    )
    write = packet["agent_a_write"]
    if not isinstance(write, dict):
        raise CausalHarnessError("agent_a_write must be an object")
    _keys(write, {"accepted", "activation_receipt_sha256", "transcript_sha256"}, "agent_a_write")
    write_ok = write["accepted"] is True and bool(_sha(write["activation_receipt_sha256"], "activation receipt"))
    _sha(write["transcript_sha256"], "Agent A transcript hash")
    before = _validate_freeze_manifest(packet["agent_b_freeze_before"], "Agent B freeze before")
    after = _validate_freeze_manifest(packet["agent_b_freeze_after"], "Agent B freeze after")
    frozen_ok = before == after
    leakage = packet["leakage_audit"]
    if not isinstance(leakage, dict):
        raise CausalHarnessError("leakage_audit must be an object")
    _keys(
        leakage,
        {"transcript_visible_to_hswm_arm", "exact_query_cache_hits", "train_test_component_overlap", "agent_b_parameter_updated"},
        "P2 leakage_audit",
    )
    leakage_ok = (
        leakage["transcript_visible_to_hswm_arm"] is False
        and leakage["exact_query_cache_hits"] == 0
        and leakage["train_test_component_overlap"] == 0
        and leakage["agent_b_parameter_updated"] is False
    )
    evaluator = packet["evaluator"]
    if not isinstance(evaluator, dict):
        raise CausalHarnessError("evaluator must be an object")
    _keys(evaluator, {"independent", "receipt_sha256"}, "evaluator")
    evaluator_ok = evaluator["independent"] is True and bool(_sha(evaluator["receipt_sha256"], "evaluator receipt"))
    budget_ok, budget_failures = _budget_gate(packet["budget_audit"], P2_ARMS)
    rows = _validate_rows(packet["rows"], P2_ARMS, p1=False)
    no_a = "frozen_agent_b_no_agent_a_information"
    hswm = "accepted_hswm_slow_weight_write"
    removed = "accepted_hswm_write_then_causal_removal"
    comparisons = {
        "hswm_minus_no_a": _bootstrap_cluster(rows, hswm, no_a, reps=bootstrap_reps, seed=bootstrap_seed),
        "hswm_minus_flat": _bootstrap_cluster(rows, hswm, "flat_memory_write", reps=bootstrap_reps, seed=bootstrap_seed + 1),
        "hswm_minus_vector": _bootstrap_cluster(rows, hswm, "vector_memory_write", reps=bootstrap_reps, seed=bootstrap_seed + 2),
        "hswm_minus_removal": _bootstrap_cluster(rows, hswm, removed, reps=bootstrap_reps, seed=bootstrap_seed + 3),
        "transcript_minus_no_a": _bootstrap_cluster(rows, "agent_a_transcript_only", no_a, reps=bootstrap_reps, seed=bootstrap_seed + 4),
    }
    dataset_deltas = {
        dataset: _mean_delta([row for row in rows if row["dataset"] == dataset], hswm, no_a)
        for dataset in sorted({str(row["dataset"]) for row in rows})
    }
    removal_return = _mean_delta(rows, removed, no_a)
    gates = {
        "upstream_f1_and_p1v5_supported": upstream_ok,
        "accepted_agent_a_weight_write": write_ok and agent_a_snapshot.snapshot_id != base.snapshot_id and bool(candidate.deltas),
        "agent_b_identity_frozen": frozen_ok,
        "fresh_component_disjoint_no_leakage": leakage_ok,
        "independent_evaluator": evaluator_ok,
        "equal_budget": budget_ok,
        "hswm_transfer_lcb_gt_0": comparisons["hswm_minus_no_a"]["cluster_bootstrap95"][0] > 0.0,
        "minimum_dataset_delta_gt_002": bool(dataset_deltas) and min(dataset_deltas.values()) > 0.02,
        "hswm_beats_flat": comparisons["hswm_minus_flat"]["mean"] > 0.0,
        "hswm_beats_vector": comparisons["hswm_minus_vector"]["mean"] > 0.0,
        "causal_removal_erases_gain": removal_return is not None and abs(removal_return) <= 0.02 and comparisons["hswm_minus_removal"]["cluster_bootstrap95"][0] > 0.0,
    }
    supported = all(gates.values())
    if mode == "development":
        verdict = "DEVELOPMENT_ONLY"
        allowed_claim = "No transfer claim; freeze the P2 packet and register before sealed measurement."
    elif supported:
        verdict = "P2_SUPPORTED_NARROW"
        allowed_claim = "An accepted Agent-A HSWM weight write improved frozen Agent B on fresh component-disjoint work, and removal erased the gain."
    else:
        verdict = "REJECTED_OR_NARROWED"
        allowed_claim = "The registered frozen-agent transfer conjunction was not satisfied."
    unsigned = {
        "schema_version": P2_JUDGMENT_SCHEMA,
        "run_id": packet["run_id"],
        "packet_sha256": canonical_sha256(packet),
        "mode": mode,
        "base_snapshot_id": base.snapshot_id,
        "agent_a_candidate_id": candidate.candidate_id,
        "agent_a_snapshot_id": agent_a_snapshot.snapshot_id,
        "agent_b_freeze_manifest_sha256": before["manifest_sha256"],
        "evaluator_receipt_sha256": evaluator["receipt_sha256"],
        "bootstrap": {"reps": bootstrap_reps, "seed": bootstrap_seed, "unit": "component", "paired": True},
        "comparisons": comparisons,
        "fresh_dataset_deltas": dataset_deltas,
        "gates": gates,
        "budget_failures": budget_failures,
        "verdict": verdict,
        "allowed_claim": allowed_claim,
    }
    return {**unsigned, "judgment_sha256": canonical_sha256(unsigned)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("judge-p1v5", "judge-p2"):
        child = subparsers.add_parser(command)
        child.add_argument("--packet", type=Path, required=True)
        child.add_argument("--bootstrap-reps", type=int, default=10000)
        child.add_argument("--bootstrap-seed", type=int, default=20260724)
        child.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        packet = _read_json(args.packet, args.command)
        judge = judge_p1v5 if args.command == "judge-p1v5" else judge_p2
        result = judge(packet, bootstrap_reps=args.bootstrap_reps, bootstrap_seed=args.bootstrap_seed)
        _write_once(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CausalHarnessError",
    "P1V5_ARMS",
    "P1V5_JUDGMENT_SCHEMA",
    "P1V5_PACKET_SCHEMA",
    "P2_ARMS",
    "P2_JUDGMENT_SCHEMA",
    "P2_PACKET_SCHEMA",
    "judge_p1v5",
    "judge_p2",
]
