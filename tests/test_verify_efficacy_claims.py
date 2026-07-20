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
    assert snapshot["graded_supersession"][
        "wrong_write_primary_recall_cost_points"
    ] == {"musique": 12.69, "2wiki": 31.0}
    assert snapshot["compiler_and_certified_readout"]["status"] == (
        "LOCAL_CONFORMANCE_PASS_NOT_EFFICACY"
    )


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
    )
    for name in names:
        (tmp_path / name).write_bytes((REPO_ROOT / name).read_bytes())

    path = tmp_path / "substrate_bench_results.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["aggregate"]["overall"]["hswm"]["ndcg10"] = 0.1
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(efficacy.EfficacyClaimError, match="nDCG@10 drifted"):
        efficacy.build_snapshot(tmp_path)
