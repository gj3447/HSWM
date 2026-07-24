"""Fail-closed stage gate for the next HSWM research programme.

This harness does not call an LLM, fit a learner, activate a weight, or mint a
scientific verdict.  It verifies the checked-in receipts that constrain the
next experiment, rejudges supplied raw evidence with the existing independent
judges, and emits a self-hashed status receipt.  Exactly one experimental gate
may be active: actual-compute F1, real Gate-0 metrology, causal Delta-W/removal,
weight-only Agent-A-to-frozen-B transfer, then topology and long-horizon work.

# KG: hswm-ordered-research-harness-20260724
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence


PLAN_SCHEMA = "hswm-next-research-plan/v1"
STATUS_SCHEMA = "hswm-next-research-status/v2"
LAKATOTREE_PACKET_SCHEMA = "hswm-next-research-lakatotree-packet/v2"
DEFAULT_PLAN = Path("_research/next_gate_harness/plan.v1.json")
F1_MIN_SEALED_ITEMS = 100
F1_EXPECTED_ARMS = frozenset(
    {
        "typed_hswm_three_function_network",
        "flat_single_llm_three_call_workflow",
        "vector_memory_three_call_workflow",
        "typed_network_role_removed_schema_preserving_null",
        "typed_network_with_role_instructions_shuffled_but_ports_preserved",
    }
)


class NextResearchHarnessError(RuntimeError):
    """The research plan or one of its evidence bindings is invalid."""


def canonical_sha256(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise NextResearchHarnessError(
            f"value is not canonical JSON: {error}"
        ) from error
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise NextResearchHarnessError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except NextResearchHarnessError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NextResearchHarnessError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise NextResearchHarnessError(f"{label} must be a JSON object")
    return value


def _strict_keys(
    value: Mapping[str, object], expected: set[str], label: str
) -> None:
    observed = set(value)
    if observed != expected:
        raise NextResearchHarnessError(
            f"{label} keys drifted: missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )


def _sha(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise NextResearchHarnessError(f"{label} must be a lowercase SHA-256")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise NextResearchHarnessError(f"{label} must be non-empty text")
    return value


def _inside_repo(repo_root: Path, relative: object, label: str) -> Path:
    raw = _text(relative, label)
    candidate = repo_root / raw
    if candidate.is_symlink():
        raise NextResearchHarnessError(f"{label} must not be a symlink: {raw}")
    path = candidate.resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as error:
        raise NextResearchHarnessError(f"{label} escapes repository root") from error
    if not path.is_file() or path.is_symlink():
        raise NextResearchHarnessError(f"{label} is missing or symlinked: {raw}")
    return path


def _verify_file_binding(repo_root: Path, binding: Mapping[str, object], label: str) -> Path:
    path = _inside_repo(repo_root, binding.get("path"), f"{label} path")
    expected = _sha(binding.get("sha256"), f"{label} sha256")
    if file_sha256(path) != expected:
        raise NextResearchHarnessError(f"{label} file hash drifted")
    return path


def _verify_self_hash(value: Mapping[str, object], key: str, label: str) -> str:
    unsigned = dict(value)
    declared = _sha(unsigned.pop(key, None), f"{label} {key}")
    if canonical_sha256(unsigned) != declared:
        raise NextResearchHarnessError(f"{label} self-hash drifted")
    return declared


def _validate_plan(value: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    _strict_keys(
        value,
        {
            "schema_version",
            "claim_boundary",
            "gates",
            "lakatotree",
            "programme_feedback",
        },
        "next research plan",
    )
    if value.get("schema_version") != PLAN_SCHEMA:
        raise NextResearchHarnessError("unsupported next research plan schema")
    _text(value.get("claim_boundary"), "plan claim boundary")
    gates = value.get("gates")
    if not isinstance(gates, list) or not gates:
        raise NextResearchHarnessError("plan gates must be a non-empty list")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    allowed_validators = {
        "p1v4_l2_result",
        "b21_rejected_result",
        "b22_groundwork",
        "b22_gate0_acceptance",
        "f1_judgment",
        "p1v5_packet",
        "p2_packet",
        "none",
    }
    for index, raw_gate in enumerate(gates):
        if not isinstance(raw_gate, dict):
            raise NextResearchHarnessError(f"gate {index} must be an object")
        _strict_keys(
            raw_gate,
            {
                "id",
                "lane",
                "priority",
                "validator",
                "artifact",
                "depends_on",
                "action",
                "completion_evidence",
                "failure_boundary",
            },
            f"gate {index}",
        )
        gate_id = _text(raw_gate.get("id"), f"gate {index} id")
        if gate_id in seen:
            raise NextResearchHarnessError(f"duplicate gate id: {gate_id}")
        dependencies = raw_gate.get("depends_on")
        if (
            not isinstance(dependencies, list)
            or any(not isinstance(item, str) or not item for item in dependencies)
            or len(dependencies) != len(set(dependencies))
        ):
            raise NextResearchHarnessError(f"gate {gate_id} dependencies are invalid")
        missing_or_forward = [item for item in dependencies if item not in seen]
        if missing_or_forward:
            raise NextResearchHarnessError(
                f"gate {gate_id} has missing/forward dependencies: {missing_or_forward}"
            )
        priority = raw_gate.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < 1:
            raise NextResearchHarnessError(f"gate {gate_id} priority is invalid")
        validator = raw_gate.get("validator")
        if validator not in allowed_validators:
            raise NextResearchHarnessError(f"gate {gate_id} validator is unsupported")
        artifact = raw_gate.get("artifact")
        if artifact is not None and (not isinstance(artifact, str) or not artifact):
            raise NextResearchHarnessError(f"gate {gate_id} artifact is invalid")
        for field in (
            "lane",
            "action",
            "completion_evidence",
            "failure_boundary",
        ):
            _text(raw_gate.get(field), f"gate {gate_id} {field}")
        normalized.append(dict(raw_gate))
        seen.add(gate_id)

    lakatotree = value.get("lakatotree")
    if not isinstance(lakatotree, dict):
        raise NextResearchHarnessError("plan LakatoTree block must be an object")
    _strict_keys(
        lakatotree,
        {"tree", "tag", "parent", "author", "questions"},
        "plan LakatoTree block",
    )
    for field in ("tree", "tag", "parent", "author"):
        _text(lakatotree.get(field), f"LakatoTree {field}")
    questions = lakatotree.get("questions")
    if not isinstance(questions, list) or not questions:
        raise NextResearchHarnessError("LakatoTree questions must be non-empty")
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            raise NextResearchHarnessError(f"LakatoTree question {index} is invalid")
        _strict_keys(question, {"qname", "body"}, f"LakatoTree question {index}")
        _text(question.get("qname"), f"LakatoTree question {index} name")
        _text(question.get("body"), f"LakatoTree question {index} body")
    feedback = value.get("programme_feedback")
    if (
        not isinstance(feedback, list)
        or not feedback
        or any(not isinstance(item, str) or not item for item in feedback)
    ):
        raise NextResearchHarnessError("programme feedback must be non-empty text")
    return tuple(normalized)


def _validate_p1v4_l2_result(path: Path) -> dict[str, object]:
    result = _read_json(path, "P1v4 LakatoTree result")
    result_sha = _verify_self_hash(
        result, "result_receipt_sha256", "P1v4 LakatoTree result"
    )
    if (
        result.get("schema_version") != "hswm-p1v4-lakatotree-result/v1"
        or result.get("tree") != "LakatosTree_HSWM_20260719"
        or result.get("tag")
        != "p1v4-fresh-policy-replication-seed5-r2-20260724"
    ):
        raise NextResearchHarnessError("P1v4 result identity drifted")
    measurement = result.get("measurement")
    replay = result.get("persistent_replay")
    node = result.get("node_receipt")
    server = result.get("server_result")
    if not all(isinstance(item, dict) for item in (measurement, replay, node, server)):
        raise NextResearchHarnessError("P1v4 result blocks are missing")
    if (
        measurement.get("verdict") != "PASS"
        or measurement.get("valid_case_count") != 6
        or measurement.get("physical_model_calls") != 24
        or measurement.get("typed_exact_set_match_count") != 6
        or measurement.get("no_memory_exact_set_match_count") != 2
        or measurement.get("typed_improvement_count_vs_no_memory") != 4
        or measurement.get("prior_outcome_reuse") is not False
    ):
        raise NextResearchHarnessError("P1v4 measured L0 contract drifted")
    if (
        replay.get("replay_status") != "verified"
        or replay.get("measurement_grade") != "server_regenerated"
        or replay.get("script_sha_server_verified") is not True
        or node.get("verdict_chain_verified") is not True
        or node.get("rederived_from_receipt") is not True
        or server.get("lakatos") != "progressive"
        or server.get("delta") != 4
    ):
        raise NextResearchHarnessError("P1v4 L2 replay boundary drifted")
    return {
        "disposition": "SUPPORTED_L0_ACTUATION_REPLICATION",
        "result_receipt_sha256": result_sha,
        "typed_vs_no_memory": "6/6_vs_2/6",
        "typed_improvement_count": 4,
        "replay": "verified/server_regenerated",
        "claim_boundary": result.get("claim_boundary"),
    }


def _validate_b21_rejected_result(repo_root: Path, path: Path) -> dict[str, object]:
    packet = _read_json(path, "B2.1 judgment packet")
    if (
        packet.get("schema_version") != "symposium-lakatotree-judgment/v1"
        or packet.get("programme") != "LakatosTree_PromSearchHSWM_20260721"
        or packet.get("branch") != "B2.1r1-query-byte-equivalence-repair"
    ):
        raise NextResearchHarnessError("B2.1 judgment identity drifted")
    prereg = packet.get("preregistration")
    measurement = packet.get("measurement")
    judge = packet.get("judge")
    verification = packet.get("verification")
    diagnostic = packet.get("posthoc_diagnostic")
    if not all(
        isinstance(item, dict)
        for item in (prereg, measurement, judge, verification, diagnostic)
    ):
        raise NextResearchHarnessError("B2.1 judgment blocks are missing")
    for label, block in (
        ("B2.1 preregistration", prereg),
        ("B2.1 evidence", measurement),
        ("B2.1 audit", measurement),
        ("B2.1 submit response", judge),
        ("B2.1 receipt verification", verification),
        ("B2.1 node readback", verification),
        ("B2.1 headroom diagnostic", diagnostic),
    ):
        if label == "B2.1 preregistration":
            binding = {"path": block.get("path"), "sha256": block.get("sha256")}
        elif label == "B2.1 evidence":
            binding = {
                "path": block.get("evidence_path"),
                "sha256": block.get("evidence_sha256"),
            }
        elif label == "B2.1 audit":
            binding = {
                "path": block.get("audit_path"),
                "sha256": block.get("audit_sha256"),
            }
        elif label == "B2.1 submit response":
            binding = {
                "path": block.get("submit_response_path"),
                "sha256": block.get("submit_response_sha256"),
            }
        elif label == "B2.1 receipt verification":
            binding = {
                "path": block.get("verify_output_path"),
                "sha256": block.get("verify_output_sha256"),
            }
        elif label == "B2.1 node readback":
            binding = {
                "path": block.get("node_readback_path"),
                "sha256": block.get("node_readback_sha256"),
            }
        else:
            binding = {"path": block.get("path"), "sha256": block.get("sha256")}
        _verify_file_binding(repo_root, binding, label)
    if (
        prereg.get("registered_before_measurement") is not True
        or measurement.get("scientific_conclusion") != "REJECTED"
        or measurement.get("primary_metric_value") != 0.0
        or measurement.get("standard_cells") != 54
        or measurement.get("standard_joint_passes") != 0
        or judge.get("verdict") != "degenerating"
        or judge.get("metric_verdict") != "equivalent"
        or judge.get("node_state") != "REJECTED"
        or verification.get("ok") is not True
        or verification.get("from_receipt") is not True
        or diagnostic.get("registered_threshold_reachable_by_any_router_over_frozen_actions")
        is not False
    ):
        raise NextResearchHarnessError("B2.1 rejection contract drifted")
    return {
        "disposition": "SATISFIED_BY_FALSIFICATION",
        "scientific_result": "REJECTED_ROUTER_ONLY_ACTION_SPACE",
        "standard_joint_passes": "0/54",
        "primary_metric": 0.0,
        "oracle_headroom_min": diagnostic.get("primary_oracle_headroom_min"),
        "verdict_receipt_sha256": judge.get("verdict_receipt_sha256"),
        "replay_boundary": "client_asserted/replay_refuted",
    }


def _validate_b22_groundwork(repo_root: Path, path: Path) -> dict[str, object]:
    packet = _read_json(path, "B2.2 groundwork packet")
    if (
        packet.get("schema") != "hswm-lakatotree-groundwork-registration/v1"
        or packet.get("tree") != "LakatosTree_PromSearchHSWM_20260721"
    ):
        raise NextResearchHarnessError("B2.2 groundwork identity drifted")
    manifest = packet.get("artifact_manifest")
    boundary = packet.get("claim_boundary")
    frontier = packet.get("frontier_registration")
    if (
        not isinstance(manifest, list)
        or not manifest
        or not isinstance(boundary, dict)
        or not isinstance(frontier, dict)
    ):
        raise NextResearchHarnessError("B2.2 groundwork blocks are missing")
    for index, item in enumerate(manifest):
        if not isinstance(item, dict):
            raise NextResearchHarnessError(f"B2.2 artifact {index} is invalid")
        _strict_keys(item, {"role", "path", "sha256"}, f"B2.2 artifact {index}")
        _text(item.get("role"), f"B2.2 artifact {index} role")
        _verify_file_binding(repo_root, item, f"B2.2 artifact {index}")
    if (
        boundary.get("engineering_groundwork") is not True
        or boundary.get("scientific_prediction_registered") is not False
        or boundary.get("scientific_verdict_exists") is not False
        or boundary.get("production_activation_exists") is not False
        or frontier.get("status") != "OPEN"
    ):
        raise NextResearchHarnessError("B2.2 groundwork claim boundary drifted")
    return {
        "disposition": "ENGINEERING_GROUNDWORK_VERIFIED",
        "artifact_count": len(manifest),
        "frontier": frontier.get("qname"),
        "next_gate": boundary.get("next_gate"),
        "scientific_prediction_registered": False,
    }


def _validate_gate0_acceptance(path: Path) -> dict[str, object]:
    try:
        from prom_search_hswm.hswm_b22_gate0_harness import (
            validate_acceptance_receipt,
        )
    except ImportError as error:
        raise NextResearchHarnessError(
            f"B2.2 Gate-0 validator cannot be imported: {error}"
        ) from error
    try:
        receipt = validate_acceptance_receipt(path)
    except Exception as error:
        raise NextResearchHarnessError(
            f"B2.2 Gate-0 acceptance is invalid: {error}"
        ) from error
    entries = receipt.get("entries")
    if not isinstance(entries, dict):
        raise NextResearchHarnessError("B2.2 Gate-0 accepted entries are missing")
    return {
        "disposition": "REAL_GATE0_PACKS_ACCEPTED",
        "receipt_sha256": file_sha256(path),
        "roles": sorted(entries),
        "learner_allowed": True,
        "scientific_claim_allowed": False,
    }


def _classify_f1_judgment(
    judgment: Mapping[str, object],
) -> tuple[str, dict[str, object]]:
    """Validate an F1 judgment and map it to an ordered-gate state.

    A development judgment is diagnostic even when every numerical gate happens
    to pass.  A sealed support verdict also needs the programme's registered
    minimum of 100 items; the lower-level judge deliberately remains reusable
    for smaller development cuts.
    """

    judgment_sha = _verify_self_hash(judgment, "judgment_sha256", "F1 judgment")
    if judgment.get("schema_version") != "hswm-prom9-f1-judgment/v1":
        raise NextResearchHarnessError("unsupported F1 judgment schema")
    mode = judgment.get("mode")
    verdict = judgment.get("verdict")
    if mode not in {"development", "sealed"}:
        raise NextResearchHarnessError("F1 judgment mode is invalid")
    gates = judgment.get("gates")
    metrics = judgment.get("metrics")
    parity_failures = judgment.get("parity_failures")
    expected_gates = {
        "exact_three_calls_each",
        "equal_budget",
        "typed_beats_flat_lcb_gt_0",
        "typed_beats_vector",
        "removal_loses_effect",
        "shuffle_loses_effect",
    }
    if not isinstance(gates, dict) or set(gates) != expected_gates:
        raise NextResearchHarnessError("F1 judgment gates drifted")
    if any(not isinstance(gates[key], bool) for key in expected_gates):
        raise NextResearchHarnessError("F1 judgment gates must be boolean")
    if not isinstance(metrics, dict) or set(metrics) != F1_EXPECTED_ARMS:
        raise NextResearchHarnessError("F1 judgment metric arms drifted")
    sample_sizes: set[int] = set()
    for arm, raw_metric in metrics.items():
        if not isinstance(arm, str) or not isinstance(raw_metric, dict):
            raise NextResearchHarnessError("F1 judgment metric is invalid")
        count = raw_metric.get("n")
        rate = raw_metric.get("success_rate")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
            or isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not 0.0 <= float(rate) <= 1.0
        ):
            raise NextResearchHarnessError("F1 judgment metric values are invalid")
        sample_sizes.add(count)
    if len(sample_sizes) != 1:
        raise NextResearchHarnessError("F1 judgment arm sample sizes differ")
    sample_size = next(iter(sample_sizes))
    if (
        not isinstance(parity_failures, list)
        or any(not isinstance(item, str) or not item for item in parity_failures)
        or bool(parity_failures) == bool(gates["equal_budget"])
    ):
        raise NextResearchHarnessError("F1 parity evidence is inconsistent")
    conjunction = all(gates.values())
    expected_verdict = (
        "DEVELOPMENT_ONLY"
        if mode == "development"
        else "F1_SUPPORTED_NARROW"
        if conjunction
        else "REJECTED_OR_NARROWED"
    )
    if verdict != expected_verdict:
        raise NextResearchHarnessError("F1 verdict is inconsistent with mode/gates")

    sample_gate = sample_size >= F1_MIN_SEALED_ITEMS
    if mode == "sealed" and conjunction and sample_gate:
        state = "SATISFIED"
        disposition = "F1_SUPPORTED_NARROW_REVALIDATED"
    elif mode == "sealed" and not conjunction:
        state = "REJECTED"
        disposition = "F1_SEALED_CONJUNCTION_REJECTED"
    else:
        state = "ACTION_REQUIRED"
        disposition = (
            "F1_SEALED_SAMPLE_TOO_SMALL"
            if mode == "sealed"
            else "F1_DEVELOPMENT_REPAIR_REQUIRED"
        )
    return state, {
        "disposition": disposition,
        "judgment_sha256": judgment_sha,
        "run_id": judgment.get("run_id"),
        "mode": mode,
        "verdict": verdict,
        "sample_size": sample_size,
        "minimum_sealed_items": F1_MIN_SEALED_ITEMS,
        "sample_gate": sample_gate,
        "gates": dict(gates),
        "parity_failures": list(parity_failures),
        "claim_boundary": judgment.get("allowed_claim"),
    }


def _validate_f1_evidence(
    *,
    repo_root: Path,
    artifact: object,
    suite_path: Path | None,
    gold_path: Path | None,
) -> tuple[str, dict[str, object]]:
    if (suite_path is None) != (gold_path is None):
        raise NextResearchHarnessError("F1 suite and gold must be supplied together")
    if suite_path is None:
        path = _inside_repo(repo_root, artifact, "F1 development judgment artifact")
        return _classify_f1_judgment(_read_json(path, "F1 development judgment"))
    try:
        from prom_search_hswm.prom_f1_function_network import judge_suite

        judgment = judge_suite(
            _read_json(Path(suite_path).resolve(), "F1 suite"),
            _read_json(Path(gold_path).resolve(), "F1 gold"),
        )
    except Exception as error:
        raise NextResearchHarnessError(f"F1 suite/gold rejudgment failed: {error}") from error
    state, evidence = _classify_f1_judgment(judgment)
    evidence["recomputed_from_suite_and_gold"] = True
    evidence["suite_file_sha256"] = file_sha256(Path(suite_path).resolve())
    evidence["gold_file_sha256"] = file_sha256(Path(gold_path).resolve())
    return state, evidence


def _validate_p1v5_packet(path: Path) -> tuple[str, dict[str, object]]:
    try:
        from prom_search_hswm.prom9_causal_harness import judge_p1v5

        packet = _read_json(path, "P1v5 causal packet")
        judgment = judge_p1v5(packet)
    except Exception as error:
        raise NextResearchHarnessError(f"P1v5 packet rejudgment failed: {error}") from error
    verdict = judgment.get("verdict")
    mode = judgment.get("mode")
    if verdict == "P1V5_SUPPORTED_NARROW" and mode == "sealed":
        state = "SATISFIED"
    elif mode == "sealed":
        state = "REJECTED"
    else:
        state = "ACTION_REQUIRED"
    return state, {
        "disposition": "P1V5_PACKET_REJUDGED",
        "packet_file_sha256": file_sha256(path),
        "judgment_sha256": judgment["judgment_sha256"],
        "mode": mode,
        "verdict": verdict,
        "gates": judgment["gates"],
        "base_snapshot_id": judgment["base_snapshot_id"],
        "promoted_snapshot_id": judgment["promoted_snapshot_id"],
        "claim_boundary": judgment["allowed_claim"],
    }


def _validate_p2_packet(path: Path) -> tuple[str, dict[str, object]]:
    try:
        from prom_search_hswm.prom9_causal_harness import judge_p2

        packet = _read_json(path, "P2 transfer packet")
        judgment = judge_p2(packet)
    except Exception as error:
        raise NextResearchHarnessError(f"P2 packet rejudgment failed: {error}") from error
    verdict = judgment.get("verdict")
    mode = judgment.get("mode")
    if verdict == "P2_SUPPORTED_NARROW" and mode == "sealed":
        state = "SATISFIED"
    elif mode == "sealed":
        state = "REJECTED"
    else:
        state = "ACTION_REQUIRED"
    return state, {
        "disposition": "P2_PACKET_REJUDGED",
        "packet_file_sha256": file_sha256(path),
        "judgment_sha256": judgment["judgment_sha256"],
        "mode": mode,
        "verdict": verdict,
        "gates": judgment["gates"],
        "base_snapshot_id": judgment["base_snapshot_id"],
        "agent_a_snapshot_id": judgment["agent_a_snapshot_id"],
        "agent_b_freeze_manifest_sha256": judgment[
            "agent_b_freeze_manifest_sha256"
        ],
        "claim_boundary": judgment["allowed_claim"],
    }


def _validate_recorded_at(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise NextResearchHarnessError("recorded_at must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise NextResearchHarnessError("recorded_at must carry a UTC offset")
    return value


def build_status(  # KG: hswm-gate-status-contract-20260724
    *,
    repo_root: Path,
    plan_path: Path | None = None,
    gate0_acceptance: Path | None = None,
    f1_suite: Path | None = None,
    f1_gold: Path | None = None,
    p1v5_packet: Path | None = None,
    p2_packet: Path | None = None,
    recorded_at: str | None = None,
) -> dict[str, object]:
    """Verify current receipts and return the ordered next-gate status."""

    repo_root = Path(repo_root).resolve()
    if not repo_root.is_dir():
        raise NextResearchHarnessError("repository root does not exist")
    plan_path = (repo_root / DEFAULT_PLAN if plan_path is None else Path(plan_path)).resolve()
    plan = _read_json(plan_path, "next research plan")
    gates = _validate_plan(plan)
    satisfied: set[str] = set()
    rows: list[dict[str, object]] = []
    for gate in gates:
        gate_id = str(gate["id"])
        dependencies = list(gate["depends_on"])
        missing = [dependency for dependency in dependencies if dependency not in satisfied]
        evidence: dict[str, object] | None = None
        state: str
        supplied_out_of_order = (
            (gate_id == "B22_GATE0_REAL_PACKS" and gate0_acceptance is not None)
            or (
                gate_id == "P1V5_THREE_FACTOR_BOND_PLASTICITY"
                and p1v5_packet is not None
            )
            or (
                gate_id == "P2_AGENT_A_TO_FROZEN_B_TRANSFER"
                and p2_packet is not None
            )
        )
        if missing and supplied_out_of_order:
            raise NextResearchHarnessError(
                f"out-of-order evidence supplied for {gate_id}; "
                f"missing prerequisites: {missing}"
            )
        if missing:
            state = "BLOCKED"
        else:
            validator = gate["validator"]
            artifact = gate["artifact"]
            if validator == "p1v4_l2_result":
                path = _inside_repo(repo_root, artifact, f"gate {gate_id} artifact")
                evidence = _validate_p1v4_l2_result(path)
                state = "SATISFIED"
            elif validator == "b21_rejected_result":
                path = _inside_repo(repo_root, artifact, f"gate {gate_id} artifact")
                evidence = _validate_b21_rejected_result(repo_root, path)
                state = "SATISFIED"
            elif validator == "b22_groundwork":
                path = _inside_repo(repo_root, artifact, f"gate {gate_id} artifact")
                evidence = _validate_b22_groundwork(repo_root, path)
                state = "SATISFIED"
            elif validator == "b22_gate0_acceptance":
                if gate0_acceptance is None:
                    state = "ACTION_REQUIRED"
                else:
                    evidence = _validate_gate0_acceptance(Path(gate0_acceptance).resolve())
                    state = "SATISFIED"
            elif validator == "f1_judgment":
                state, evidence = _validate_f1_evidence(
                    repo_root=repo_root,
                    artifact=artifact,
                    suite_path=f1_suite,
                    gold_path=f1_gold,
                )
            elif validator == "p1v5_packet":
                if p1v5_packet is None:
                    state = "ACTION_REQUIRED"
                else:
                    state, evidence = _validate_p1v5_packet(
                        Path(p1v5_packet).resolve()
                    )
            elif validator == "p2_packet":
                if p2_packet is None:
                    state = "ACTION_REQUIRED"
                else:
                    state, evidence = _validate_p2_packet(Path(p2_packet).resolve())
            elif validator == "none":
                state = "READY"
            else:  # pragma: no cover - guarded by plan validation
                raise NextResearchHarnessError(f"unsupported validator: {validator}")
        if state == "SATISFIED":
            satisfied.add(gate_id)
        rows.append(
            {
                "id": gate_id,
                "lane": gate["lane"],
                "priority": gate["priority"],
                "state": state,
                "depends_on": dependencies,
                "missing_dependencies": missing,
                "action": gate["action"],
                "completion_evidence": gate["completion_evidence"],
                "failure_boundary": gate["failure_boundary"],
                "evidence": evidence,
            }
        )
    next_actions = [
        {
            "id": row["id"],
            "lane": row["lane"],
            "priority": row["priority"],
            "state": row["state"],
            "action": row["action"],
        }
        for row in rows
        if row["state"] in {"ACTION_REQUIRED", "READY", "REJECTED"}
    ]
    next_actions.sort(key=lambda item: (int(item["priority"]), str(item["id"])))
    if len(next_actions) > 1:
        raise NextResearchHarnessError(
            "ordered plan exposed more than one active gate; dependency graph drifted"
        )
    ordered_remaining = [row["id"] for row in rows if row["state"] != "SATISFIED"]
    unsigned: dict[str, object] = {
        "schema_version": STATUS_SCHEMA,
        "recorded_at": _validate_recorded_at(recorded_at),
        "claim_boundary": plan["claim_boundary"],
        "plan_sha256": file_sha256(plan_path),
        "harness_sha256": file_sha256(Path(__file__).resolve()),
        "sequence_locked": True,
        "gate0_acceptance_supplied": gate0_acceptance is not None,
        "f1_suite_and_gold_supplied": f1_suite is not None and f1_gold is not None,
        "p1v5_packet_supplied": p1v5_packet is not None,
        "p2_packet_supplied": p2_packet is not None,
        "gates": rows,
        "active_gate": next_actions[0] if next_actions else None,
        "next_actions": next_actions,
        "ordered_remaining": ordered_remaining,
        "programme_feedback": plan["programme_feedback"],
        "scientific_prediction_registered": False,
        "scientific_verdict_emitted": False,
    }
    return {**unsigned, "status_receipt_sha256": canonical_sha256(unsigned)}


def verify_status(  # KG: hswm-status-verification-contract-20260724
    value: Mapping[str, object],
) -> str:
    if value.get("schema_version") != STATUS_SCHEMA:
        raise NextResearchHarnessError("unsupported status receipt schema")
    if (
        value.get("scientific_prediction_registered") is not False
        or value.get("scientific_verdict_emitted") is not False
    ):
        raise NextResearchHarnessError("status receipt crossed its scientific boundary")
    return _verify_self_hash(value, "status_receipt_sha256", "status receipt")


def build_lakatotree_packet(  # KG: hswm-lakatotree-packet-contract-20260724
    *, status: Mapping[str, object], plan: Mapping[str, object], result_path: str
) -> dict[str, object]:
    """Build a DRAFT engineering packet; never a prediction or result submission."""

    status_sha = verify_status(status)
    _validate_plan(plan)
    result_path = _text(result_path, "LakatoTree result path")
    lakatotree = plan["lakatotree"]
    assert isinstance(lakatotree, dict)  # validated above
    packet: dict[str, object] = {
        "schema_version": LAKATOTREE_PACKET_SCHEMA,
        "tree": lakatotree["tree"],
        "node": {
            "tag": lakatotree["tag"],
            "parent": lakatotree["parent"],
            "author": lakatotree["author"],
            "comment": (
                "Fail-closed ordered engineering harness for HSWM F1/B2.2/P1v5/P2/P3/P4; "
                "no scientific result or prediction."
            ),
            "algorithm": (
                "Verify preserved evidence, rejudge actual-compute F1 evidence, then require "
                "real Gate-0 acceptance and rejudge raw P1v5/P2 causal packets in strict "
                "order; expose exactly one active gate without minting a scientific verdict."
            ),
            "result_path": result_path,
        },
        "questions": list(lakatotree["questions"]),
        "events": [
            {
                "realm": "agent",
                "action": "record_fail_closed_ordered_gate_harness",
                "evidence": [result_path],
                "payload": {
                    "status_receipt_sha256": status_sha,
                    "scientific_claim": "NONE_ENGINEERING_SEQUENCE_ONLY",
                },
            }
        ],
        "scientific_prediction_registered": False,
        "scientific_result_submitted": False,
        "node_state_expected": "DRAFT",
    }
    packet["packet_sha256"] = canonical_sha256(packet)
    return packet


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise NextResearchHarnessError(f"refusing to replace receipt: {path}") from error
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

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    status_parser.add_argument("--plan", type=Path)
    status_parser.add_argument("--f1-suite", type=Path)
    status_parser.add_argument("--f1-gold", type=Path)
    status_parser.add_argument("--gate0-acceptance", type=Path)
    status_parser.add_argument("--p1v5-packet", type=Path)
    status_parser.add_argument("--p2-packet", type=Path)
    status_parser.add_argument("--recorded-at")
    status_parser.add_argument("--output", type=Path)

    packet_parser = subparsers.add_parser("lakatotree-packet")
    packet_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    packet_parser.add_argument("--plan", type=Path)
    packet_parser.add_argument("--status", type=Path, required=True)
    packet_parser.add_argument("--result-path", required=True)
    packet_parser.add_argument("--output", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = build_status(
                repo_root=args.repo_root,
                plan_path=args.plan,
                gate0_acceptance=args.gate0_acceptance,
                f1_suite=args.f1_suite,
                f1_gold=args.f1_gold,
                p1v5_packet=args.p1v5_packet,
                p2_packet=args.p2_packet,
                recorded_at=args.recorded_at,
            )
        else:
            repo_root = Path(args.repo_root).resolve()
            plan_path = (
                repo_root / DEFAULT_PLAN if args.plan is None else Path(args.plan)
            ).resolve()
            plan = _read_json(plan_path, "next research plan")
            status = _read_json(Path(args.status), "next research status")
            result = build_lakatotree_packet(
                status=status, plan=plan, result_path=args.result_path
            )
        if args.output:
            _write_once(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except NextResearchHarnessError as error:
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
    "DEFAULT_PLAN",
    "F1_EXPECTED_ARMS",
    "F1_MIN_SEALED_ITEMS",
    "LAKATOTREE_PACKET_SCHEMA",
    "NextResearchHarnessError",
    "PLAN_SCHEMA",
    "STATUS_SCHEMA",
    "build_lakatotree_packet",
    "build_status",
    "canonical_sha256",
    "file_sha256",
    "verify_status",
]
