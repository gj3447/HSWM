from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from hswm_weight_snapshot import (
    SlowWeightV1,
    WeightDeltaV1,
    apply_candidate,
    make_initial_snapshot,
    make_weight_candidate,
)
from p1_eligibility_tag import derive_eligibility_tags, make_activation_trace
from prom_search_hswm.hswm_call_receipt import ModelCallV1, ModelResponseV1
from prom_search_hswm.hswm_function_network import F1_ARMS, TYPED_ARM
from prom_search_hswm.hswm_typed_ports import TypedPortError, canonical_sha256, validate_port
from prom_search_hswm.prom_f1_function_network import (
    F1HarnessError,
    GOLD_SCHEMA,
    MANIFEST_SCHEMA,
    judge_suite,
    run_suite,
    verify_suite,
)
from prom_search_hswm.prom9_causal_harness import (
    CausalHarnessError,
    P1V5_ARMS,
    P1V5_PACKET_SCHEMA,
    P2_ARMS,
    P2_PACKET_SCHEMA,
    judge_p1v5,
    judge_p2,
)
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL


REPO_ROOT = Path(__file__).resolve().parents[1]


class FakePort:
    def __call__(self, call: ModelCallV1) -> ModelResponseV1:
        request_id = str(call.input_payload["request_id"])
        if call.function_id == "QF_QUERY_COMPILER":
            payload = {
                "request_id": request_id,
                "objectives": ["answer"],
                "required_evidence_types": ["text"],
                "constraints": ["evidence only"],
                "abstain": False,
            }
        elif call.function_id == "BF_BOND_PROPOSER":
            candidates = call.input_payload["candidates"]
            if "role_removed" in call.arm_id:
                payload = {
                    "request_id": request_id,
                    "ordered_bond_ids": [],
                    "bond_potentials": {},
                    "evidence_refs": [],
                    "abstain": True,
                }
            else:
                selected = candidates[0]
                payload = {
                    "request_id": request_id,
                    "ordered_bond_ids": [selected["bond_id"]],
                    "bond_potentials": {selected["bond_id"]: 0.0},
                    "evidence_refs": [selected["evidence_id"]],
                    "abstain": False,
                }
        else:
            evidence = call.input_payload["selected_evidence"]
            supported = [evidence[0]["evidence_id"]] if evidence else []
            payload = {
                "request_id": request_id,
                "answer": "Paris" if call.arm_id == TYPED_ARM else "Lyon",
                "supporting_evidence_ids": supported,
                "uncertainty": "",
                "abstain": not bool(evidence),
            }
        return ModelResponseV1(
            payload=payload,
            model=call.model,
            model_revision=call.model_revision,
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
        )


def _f1_manifest() -> dict:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": "f1-dev-1",
        "mode": "development",
        "model": "fake-model",
        "model_revision": "fake-rev",
        "token_tolerance": 0,
        "state_capacity_bytes": 100,
        "state_bytes_by_arm": {arm: 100 for arm in F1_ARMS},
        "preregistration_receipt_sha256": None,
        "items": [
            {
                "item_id": f"item-{index}",
                "query_text": "What is the capital of France?",
                "allowed_evidence_types": ["text"],
                "candidates": [
                    {
                        "bond_id": "bond-1",
                        "evidence_id": "evidence-1",
                        "content": "Paris is the capital of France.",
                        "observable": {
                            "flat_position": 0,
                            "flat_score": 1.0,
                            "vector_score": 0.9,
                            "source_type": "text",
                            "seam_count": 1,
                        },
                    }
                ],
                "max_evidence_items": 1,
                "max_input_tokens": 100,
                "max_output_tokens_per_call": 16,
            }
            for index in range(4)
        ],
    }


def test_typed_ports_reject_extra_keys_and_positive_bond_potential() -> None:
    with pytest.raises(TypedPortError, match="keys drifted"):
        validate_port(
            "QueryPlanV1",
            {
                "request_id": "r", "objectives": [], "required_evidence_types": [],
                "constraints": [], "abstain": True, "rationale": "hidden channel",
            },
        )
    with pytest.raises(TypedPortError, match="finite and <="):
        validate_port(
            "BondProposalV1",
            {
                "request_id": "r", "ordered_bond_ids": ["b"],
                "bond_potentials": {"b": 0.1}, "evidence_refs": [], "abstain": False,
            },
        )


def test_f1_executes_three_calls_per_arm_and_development_cannot_claim_science() -> None:
    suite = run_suite(
        _f1_manifest(),
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        model_port=FakePort(),
        max_workers=3,
    )
    assert verify_suite(suite) == suite["suite_receipt_sha256"]
    assert len(suite["item_runs"]) == 4 * len(F1_ARMS)
    assert all(len(row["calls"]) == 3 for row in suite["item_runs"])
    request_ids = {
        call["input_payload"]["request_id"]
        for row in suite["item_runs"]
        for call in row["calls"]
    }
    assert all(value.startswith("req-") and len(value) == 24 for value in request_ids)
    assert len(request_ids) == 4 * len(F1_ARMS)
    gold = {
        "schema_version": GOLD_SCHEMA,
        "run_id": "f1-dev-1",
        "evaluator_receipt_sha256": "a" * 64,
        "items": [
            {"item_id": f"item-{index}", "accepted_answers": ["Paris"]}
            for index in range(4)
        ],
    }
    judgment = judge_suite(suite, gold, bootstrap_reps=100, bootstrap_seed=7)
    assert judgment["verdict"] == "DEVELOPMENT_ONLY"
    assert all(judgment["gates"].values())
    assert judgment["comparisons"][
        "typed_minus_flat_single_llm_three_call_workflow"
    ]["mean"] == 1.0


def test_f1_refuses_tampered_call_receipt() -> None:
    suite = run_suite(
        _f1_manifest(),
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        model_port=FakePort(),
    )
    broken = deepcopy(suite)
    broken["item_runs"][0]["calls"][0]["output_tokens"] = 999
    unsigned_run = dict(broken["item_runs"][0])
    unsigned_run.pop("run_receipt_sha256")
    broken["item_runs"][0]["run_receipt_sha256"] = canonical_sha256(unsigned_run)
    unsigned_suite = dict(broken)
    unsigned_suite.pop("suite_receipt_sha256")
    broken["suite_receipt_sha256"] = canonical_sha256(unsigned_suite)
    with pytest.raises(Exception, match="call receipt self-hash drifted"):
        verify_suite(broken)


def _weight_chain():
    base = make_initial_snapshot(
        (SlowWeightV1("edge-a", -0.5), SlowWeightV1("edge-b", -0.5)),
        topology_sha256="1" * 64,
        provenance_root_sha256="2" * 64,
    )
    trace = make_activation_trace(
        episode_id="episode-1",
        question_id="question-1",
        query_sha256="3" * 64,
        snapshot_id=base.snapshot_id,
        target_id="target-1",
        edge_ids=("edge-a",),
        raw_contribution=1.0,
    )
    tag = derive_eligibility_tags("episode-1", (trace,))[0]
    candidate = make_weight_candidate(
        base,
        (
            WeightDeltaV1(
                edge_id="edge-a",
                before_log_salience=-0.5,
                after_log_salience=-0.4,
                eligibility_tag_sha256=tag.tag_id,
            ),
        ),
        learning_policy_sha256="4" * 64,
        provenance_root_sha256="5" * 64,
    )
    return base, tag, candidate, apply_candidate(base, candidate)


def _budget(arms: tuple[str, ...]) -> dict:
    return {
        "calls_per_item_by_arm": {arm: 3 for arm in arms},
        "allowed_tokens_per_item_by_arm": {arm: 300 for arm in arms},
        "candidate_budget_by_arm": {arm: 20 for arm in arms},
        "state_capacity_bytes_by_arm": {arm: 1024 for arm in arms},
        "consumed_token_spread_max": 2,
        "token_tolerance": 2,
    }


def _p1_packet() -> dict:
    base, tag, candidate, promoted = _weight_chain()
    rows = []
    for index in range(4):
        rows.append(
            {
                "item_id": f"fresh-{index}",
                "component_id": f"component-{index}",
                "dataset": "2wiki" if index < 2 else "musique",
                "regime": "fresh",
                "arms": {
                    arm: (1.0 if arm in {
                        "query_conditioned_fast_bond_only",
                        "fast_then_validated_slow_promotion",
                    } else 0.0)
                    for arm in P1V5_ARMS
                },
            }
        )
    for regime in ("cross_field", "in_field", "canary"):
        rows.append(
            {
                "item_id": regime,
                "component_id": regime,
                "dataset": "2wiki",
                "regime": regime,
                "arms": {arm: 1.0 for arm in P1V5_ARMS},
            }
        )
    return {
        "schema_version": P1V5_PACKET_SCHEMA,
        "run_id": "p1v5-dev-1",
        "mode": "development",
        "preregistration_receipt_sha256": None,
        "gate0_acceptance_receipt_sha256": "6" * 64,
        "base_snapshot": base.canonical(),
        "candidate": candidate.canonical(),
        "promoted_snapshot": promoted.canonical(),
        "removal_snapshot": base.canonical(),
        "training": {"used_edge_ids": ["edge-a"], "eligibility_tags": [tag.canonical()]},
        "evaluator": {"independent": True, "receipt_sha256": "7" * 64},
        "leakage_audit": {
            "split_disjoint": True,
            "gold_hidden_from_learner": True,
            "forbidden_features_absent": True,
            "replay_verified": True,
        },
        "budget_audit": _budget(P1V5_ARMS),
        "rows": rows,
    }


def test_p1v5_proves_real_delta_and_removal_but_stays_development_only() -> None:
    result = judge_p1v5(_p1_packet(), bootstrap_reps=100, bootstrap_seed=11)
    assert result["verdict"] == "DEVELOPMENT_ONLY"
    assert all(result["gates"].values())


def test_p1v5_rejects_delta_on_unused_edge() -> None:
    packet = _p1_packet()
    packet["training"]["used_edge_ids"] = ["edge-b"]
    with pytest.raises(CausalHarnessError, match="was not used"):
        judge_p1v5(packet, bootstrap_reps=20)


def _freeze_manifest() -> dict:
    unsigned = {
        "model_sha256": "8" * 64,
        "parameters_sha256": "9" * 64,
        "prompt_sha256": "a" * 64,
        "tools_sha256": "b" * 64,
        "readout_sha256": "c" * 64,
        "budget_sha256": "d" * 64,
    }
    return {**unsigned, "manifest_sha256": canonical_sha256(unsigned)}


def _p2_packet() -> dict:
    base, _, candidate, promoted = _weight_chain()
    rows = []
    for index in range(4):
        rows.append(
            {
                "item_id": f"transfer-{index}",
                "component_id": f"unseen-component-{index}",
                "dataset": "2wiki" if index < 2 else "musique",
                "regime": "fresh_unseen",
                "arms": {
                    arm: (1.0 if arm == "accepted_hswm_slow_weight_write" else 0.0)
                    for arm in P2_ARMS
                },
            }
        )
    freeze = _freeze_manifest()
    return {
        "schema_version": P2_PACKET_SCHEMA,
        "run_id": "p2-dev-1",
        "mode": "development",
        "preregistration_receipt_sha256": None,
        "upstream_acceptance": {
            "f1_judgment_sha256": "e" * 64,
            "f1_verdict": "F1_SUPPORTED_NARROW",
            "p1v5_judgment_sha256": "f" * 64,
            "p1v5_verdict": "P1V5_SUPPORTED_NARROW",
        },
        "base_snapshot": base.canonical(),
        "agent_a_candidate": candidate.canonical(),
        "agent_a_snapshot": promoted.canonical(),
        "removal_snapshot": base.canonical(),
        "agent_a_write": {
            "accepted": True,
            "activation_receipt_sha256": "1" * 64,
            "transcript_sha256": "2" * 64,
        },
        "agent_b_freeze_before": freeze,
        "agent_b_freeze_after": deepcopy(freeze),
        "leakage_audit": {
            "transcript_visible_to_hswm_arm": False,
            "exact_query_cache_hits": 0,
            "train_test_component_overlap": 0,
            "agent_b_parameter_updated": False,
        },
        "budget_audit": _budget(P2_ARMS),
        "evaluator": {"independent": True, "receipt_sha256": "3" * 64},
        "rows": rows,
    }


def test_p2_binds_agent_a_weight_write_to_frozen_b_and_removal() -> None:
    result = judge_p2(_p2_packet(), bootstrap_reps=100, bootstrap_seed=13)
    assert result["verdict"] == "DEVELOPMENT_ONLY"
    assert all(result["gates"].values())


def test_p2_rejects_agent_b_parameter_drift() -> None:
    packet = _p2_packet()
    packet["agent_b_freeze_after"]["parameters_sha256"] = "0" * 64
    unsigned = dict(packet["agent_b_freeze_after"])
    unsigned.pop("manifest_sha256")
    packet["agent_b_freeze_after"]["manifest_sha256"] = canonical_sha256(unsigned)
    result = judge_p2(packet, bootstrap_reps=20)
    assert result["gates"]["agent_b_identity_frozen"] is False
