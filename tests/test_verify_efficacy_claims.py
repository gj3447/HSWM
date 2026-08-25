from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_efficacy_claims as efficacy


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_default_root_tracks_repository_after_script_move(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert efficacy.DEFAULT_ROOT == REPO_ROOT


def test_installed_verifier_requires_explicit_source_root() -> None:
    with pytest.raises(
        efficacy.EfficacyClaimError,
        match="requires --root pointing to an HSWM source checkout",
    ):
        efficacy.build_snapshot(None)


def test_checked_in_efficacy_snapshot_matches_public_claims() -> None:
    snapshot = efficacy.build_snapshot(REPO_ROOT)

    assert snapshot["schema_version"] == "hswm-efficacy-snapshot/v4"
    assert snapshot["verification_scope"] == {
        "kind": "SELECTED_HEADLINE_ONLY",
        "whole_ledger_completeness_pass": False,
        "exit_zero": "SELECTED_CLAIMS_MATCH_CHECKED_IN_RECEIPTS",
    }
    assert snapshot["retrieval_substrate"]["status"] == (
        "MEASURED_POSITIVE_WITH_BUDGET_CAVEAT"
    )
    assert snapshot["retrieval_substrate"]["delta_hswm_minus_cosine"] == {
        "sup_recall_at_3": 0.0364,
        "ndcg10": 0.0259,
        "downstream_f1": 0.0729,
    }
    assert snapshot["retrieval_substrate"][
        "raw_per_query_mean_delta_downstream_f1"
    ] == 0.072834
    assert snapshot["cognitive_uplift_vs_direct_llm"]["status"] == (
        "PREREGISTERED_CROSS_DATASET_CLAIM_FAILED"
    )
    assert snapshot["cognitive_uplift_vs_direct_llm"][
        "per_run_delta_hswm_minus_direct"
    ] == {"musique_s7": -0.2566, "musique_s13": -0.2317, "2wiki_s7": 0.0414}
    assert snapshot["cognitive_uplift_vs_direct_llm"][
        "raw_per_query_mean_delta"
    ] == -0.148971
    assert snapshot["query_time_traversal"]["status"] == (
        "CERTIFIED_OFF_ON_MUSIQUE_AND_2WIKI"
    )
    assert snapshot["query_time_traversal"]["support_recall_hop_drop"] == {
        "static": 0.2409,
        "selected_traversal": 0.3539,
    }
    assert snapshot["p1_closed_macro_weight_loop"] == {
        "status": "ENGINEERING_COMPLETE_SCIENTIFIC_RED",
        "scientific_domain_status": "CAUSAL_EFFICACY_REJECTED",
        "evidence_authority": "CHECKED_IN_DIRECT_MEASUREMENT",
        "historical_measurement_self_verdict": "FAIL",
        "a1_minus_a2_mean_paired_recall10": 0.0,
        "bootstrap95_lower": 0.0,
        "a1_linear_slope": -0.02708333333333333,
        "later_episode_mean_recall10": {
            "A1_tagged_commit": 0.16510416666666666,
            "A2_no_commit": 0.16510416666666666,
            "A3_shuffled_M": 0.16510416666666666,
            "A4_uniform_commit": 0.16510416666666666,
        },
        "candidates_staged": 12,
        "fresh_gate_passes": 0,
        "activations": 0,
        "rank_replay": {
            "candidates": 12,
            "fresh_query_evaluations": 456,
            "touched_selected_path_evaluations": 21,
            "score_change_evaluations": 21,
            "top10_order_changes": 0,
            "top10_membership_changes": 0,
            "max_abs_score_delta": 3.235855457806025e-05,
            "max_delta_to_boundary_gap": 0.10269710791092374,
        },
        "experiment_receipt_id": (
                "81bd2f816226ea6e5d0ea8df345aad4947599d3378f40397972a2b9e1b0399de"
        ),
        "boundary": (
            "The outcome-to-credit-to-candidate loop executed, but no "
            "candidate changed fresh top-10 retrieval or became active. "
            "The checked-in evidence self-recorded FAIL; no removed "
            "external-tool verdict is retained as authority."
        ),
    }
    lineage = snapshot["p1_typed_policy_lineage"]
    assert lineage["status"] == (
        "P1V2_KILL_P1V3_P1V4_NARROW_L0_PASS_"
        "L1_KILLED_BEFORE_REGISTRATION"
    )
    assert lineage["p1v2_type6_oracle_actuation"] == {
        "verdict": "KILL",
        "claim_status": "NO_TYPED_LESSON_ACTUATION_ON_FROZEN_TYPE6_CUT",
        "valid_cases": 6,
        "no_memory_exact_set_matches": 6,
        "typed_actuation_cases": 0,
        "all_four_arms_identical_answers": 6,
        "failure_mode": "BASELINE_CEILING_AND_INTERVENTION_INERT",
        "same_environment_reuse_allowed": False,
    }
    assert lineage["p1v3_policy_actuation"]["scope"] == (
        "SYNTHETIC_PHANTOMWIKI_L0_POLICY_ACTUATION_N6"
    )
    assert lineage["p1v3_policy_actuation"]["typed_improvements_vs_no_memory"] == 6
    assert lineage["p1v4_fresh_policy_replication"][
        "typed_improvements_vs_no_memory"
    ] == 4
    assert lineage["l1_causal_lesson"] == {
        "registration_state": "KILLED_BEFORE_REGISTRATION",
        "measurement_authorized_for_stage": "NONE_DRAFT_KILLED",
        "implementation_status": "NOT_IMPLEMENTED",
        "scientific_status": "UNMEASURED_UNJUDGED",
        "design_verdict": "KILL_AND_PRUNE_BEFORE_IMPLEMENTATION",
        "transitive_provenance_complete": False,
        "stale_file_sha256_references": [
            "receipts/p1v2_l0_r2_512_closeout_20260724.json",
            "receipts/p1v2_l0_diagnosis_r2_512_20260724.json",
        ],
        "next_candidate": {
            "registration_state": "UNREGISTERED_UNAUTHORIZED",
            "scope": (
                "durable numeric delta-routing/W-only diagnostic; delta-H and "
                "topology are explicit nonclaims"
            ),
            "physical_model_call_ceiling": 160,
            "efficacy_verdict_permitted": False,
        },
    }
    assert snapshot["graded_supersession"][
        "wrong_write_primary_recall_cost_points"
    ] == {"musique": 12.69, "2wiki": 31.0}
    assert snapshot["compiler_and_certified_readout"]["status"] == (
        "LOCAL_CONFORMANCE_PASS_NOT_EFFICACY"
    )
    assert snapshot["qkv_structure"] == {
        "synthetic_ordered_routing": "PASS_64_OF_64",
        "b1_real_data_development": "CROSS_DATASET_GATE_FAILED",
        "k2_minus_matched_k1": {
            "musique": {
                "ndcg10_k2_minus_k1": -0.015238,
                "asr10_k2_minus_k1": -0.04,
            },
            "2wiki": {
                "ndcg10_k2_minus_k1": -0.035466,
                "asr10_k2_minus_k1": 0.010204,
            },
        },
        "heterogeneous_semantic_fixture": {
            "status": "PASS_128_NAMESPACE_CASES_4_UNIQUE_TEMPLATES",
            "typed_exact": 128,
            "homogeneous_association_erased_exact": 64,
            "branch_erasure_atomic_refused": 128,
        },
        "2wiki_evaluator_supplied_memory": {
            "status": "EXECUTOR_COVERAGE_NOT_EFFICACY",
            "conditional_exact": 132,
            "conditional_n": 132,
            "full_development_refusal_counted_exact_rate": 0.66,
            "type_erased_exact": 80,
            "resolver_off_exact": 109,
        },
        "boundary": (
            "Supplied heterogeneous typed programs execute coherently, but "
            "the deployable no-label arm remains absent and current "
            "title-value recurrence does not establish reasoning uplift"
        ),
    }


def test_headline_drift_fails_closed(tmp_path: Path) -> None:
    names = (
        "substrate_bench_results.json",
        "ab_p5_full_results.json",
        "ab_p5_full_musique_s7.json",
        "ab_p5_full_musique_s13.json",
        "ab_p5_full_2wiki_s7.json",
        "traversal_bench_results.json",
        "cert_musique_result.json",
        "cert_2wiki_result.json",
        "stale_poisoning_musique_result.json",
        "stale_poisoning_2wiki_result.json",
        "certified_cut_comparison_result.json",
        "h3_title_anchor_result.json",
        "qkv_routing_result.json",
        "qkv_b1_development_result.json",
        "semantic_layer_result.json",
        "semantic_2wiki_oracle_result.json",
        "SEMANTIC_QKV_EXPERIMENT_PLAN_2026-07-20.md",
        "semantic_layer_falsifier.py",
        "semantic_layer_fixture_manifest.json",
        "semantic_layer_routing.py",
        "semantic_2wiki_oracle.py",
        "EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json",
        "P1_GATE_DIAGNOSTIC_R2_2026-07-23.json",
        "P1_RANK_INVARIANCE_DIAGNOSTIC_R2_2026-07-23.json",
        "PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json",
        "receipts/p1v2_l0_r2_512_closeout_20260724.json",
        "prereg/PREREG_P1V3_POLICY_ACTUATION_2026-07-24.json",
        "receipts/p1v3_policy_heldout_judge_seed3_20260724.json",
        "prereg/PREREG_P1V4_FRESH_POLICY_REPLICATION_2026-07-24.json",
        "receipts/p1v4_policy_heldout_judge_seed5_r2_20260724.json",
        "prereg/PREREG_P1V3V4_L1_CAUSAL_LESSON_2026-07-25.json",
    )
    for name in names:
        source = efficacy.resolve_artifact_path(
            name, root=REPO_ROOT, must_exist=False,
        )
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    path = tmp_path / "substrate_bench_results.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["aggregate"]["overall"]["hswm"]["ndcg10"] = 0.1
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(efficacy.EfficacyClaimError, match="nDCG@10 drifted"):
        efficacy.build_snapshot(tmp_path)


def test_p1v2_kill_drift_fails_closed(monkeypatch) -> None:
    original_load = efficacy._load

    def drifted_load(root: Path, name: str):
        value = original_load(root, name)
        if name == "receipts/p1v2_l0_r2_512_closeout_20260724.json":
            value["scientific_outcome"] = "PASS"
        return value

    monkeypatch.setattr(efficacy, "_load", drifted_load)

    with pytest.raises(efficacy.EfficacyClaimError, match="self-hash drifted"):
        efficacy.build_snapshot(REPO_ROOT)
