from __future__ import annotations

import json
from pathlib import Path

import pytest

import verify_efficacy_claims as efficacy


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_efficacy_snapshot_matches_public_claims() -> None:
    snapshot = efficacy.build_snapshot(REPO_ROOT)

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
        "status": "ENGINEERING_COMPLETE_CAUSAL_EFFICACY_REJECTED",
        "verdict": "FAIL",
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
        "experiment_receipt_id": (
            "70cf72a18da617a3494b00848f349f0fd96c6dce444639413c21ace41e24f758"
        ),
        "boundary": (
            "The outcome-to-credit-to-candidate loop executed, but no "
            "candidate changed fresh top-10 retrieval or became active"
        ),
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
        "PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json",
    )
    for name in names:
        (tmp_path / name).write_bytes((REPO_ROOT / name).read_bytes())

    path = tmp_path / "substrate_bench_results.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["aggregate"]["overall"]["hswm"]["ndcg10"] = 0.1
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(efficacy.EfficacyClaimError, match="nDCG@10 drifted"):
        efficacy.build_snapshot(tmp_path)
