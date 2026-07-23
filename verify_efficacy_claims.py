"""Verify selected headline HSWM efficacy claims from checked-in receipts.

This is a read-only selected claim ledger.  It does not rerun an
LLM, rebuild embeddings, or promote an experimental result.  It fails closed
when a headline number or a claim boundary drifts away from the checked-in JSON
artifacts used by ``EFFICACY.md``.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "hswm-efficacy-snapshot/v2"
DEFAULT_ROOT = Path(__file__).resolve().parent


class EfficacyClaimError(RuntimeError):
    """A checked-in result no longer supports the declared claim boundary."""


def _load(root: Path, name: str) -> dict[str, Any]:
    path = root / name
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EfficacyClaimError(f"cannot read {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise EfficacyClaimError(f"{name} must contain a JSON object")
    return value


def _file_sha256(path: Path, *, label: str) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise EfficacyClaimError(f"cannot read {label}: {exc}") from exc


def _verify_result_self_hash(value: Mapping[str, Any], *, label: str) -> None:
    declared = value.get("result_sha256")
    payload = dict(value)
    payload.pop("result_sha256", None)
    actual = sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    _require(declared == actual, f"{label} result self-hash drifted")


def _verify_source_bindings(
    root: Path, value: Mapping[str, Any], *, label: str,
) -> None:
    bindings = value.get("source_bindings")
    _require(
        isinstance(bindings, Mapping) and bool(bindings),
        f"{label} source bindings are absent",
    )
    for name, declared in bindings.items():
        path = root / str(name)
        try:
            actual = sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise EfficacyClaimError(
                f"{label} cannot read source-bound file {name}: {exc}"
            ) from exc
        _require(
            declared == actual,
            f"{label} source binding drifted for {name}",
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EfficacyClaimError(message)


def _close(observed: Any, expected: float, *, label: str) -> float:
    try:
        value = float(observed)
    except (TypeError, ValueError) as exc:
        raise EfficacyClaimError(f"{label} is not numeric") from exc
    if not math.isclose(value, expected, rel_tol=0.0, abs_tol=5e-5):
        raise EfficacyClaimError(
            f"{label} drifted: expected {expected}, observed {value}"
        )
    return value


def _per_query_mean_delta(
    rows: Sequence[Mapping[str, Any]], left: str, right: str,
) -> float:
    try:
        values = [
            float(row[left]["f1"]) - float(row[right]["f1"])
            for row in rows
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise EfficacyClaimError(
            f"per-query F1 rows cannot compare {left} vs {right}"
        ) from exc
    if not values:
        raise EfficacyClaimError("per-query F1 ledger is empty")
    return sum(values) / len(values)


def build_snapshot(root: str | Path = DEFAULT_ROOT) -> dict[str, Any]:
    """Return a validated, JSON-serializable efficacy snapshot."""

    repo = Path(root).resolve()
    substrate = _load(repo, "substrate_bench_results.json")
    p5 = _load(repo, "ab_p5_full_results.json")
    p5_musique_s7 = _load(repo, "ab_p5_full_musique_s7.json")
    p5_musique_s13 = _load(repo, "ab_p5_full_musique_s13.json")
    p5_2wiki_s7 = _load(repo, "ab_p5_full_2wiki_s7.json")
    traversal = _load(repo, "traversal_bench_results.json")
    cert_musique = _load(repo, "cert_musique_result.json")
    cert_2wiki = _load(repo, "cert_2wiki_result.json")
    stale_musique = _load(repo, "stale_poisoning_musique_result.json")
    stale_2wiki = _load(repo, "stale_poisoning_2wiki_result.json")
    certified_cut = _load(repo, "certified_cut_comparison_result.json")
    title_anchor = _load(repo, "h3_title_anchor_result.json")
    qkv_routing = _load(repo, "qkv_routing_result.json")
    qkv_b1 = _load(repo, "qkv_b1_development_result.json")
    semantic_layer = _load(repo, "semantic_layer_result.json")
    semantic_2wiki = _load(repo, "semantic_2wiki_oracle_result.json")
    p1 = _load(repo, "EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json")
    p1_gate = _load(repo, "P1_GATE_DIAGNOSTIC_R2_2026-07-23.json")

    overall = substrate.get("aggregate", {}).get("overall", {})
    downstream = substrate.get("downstream_f1", {}).get("aggregate_f1_em", {})
    significance = substrate.get("significance", {})
    hswm = overall.get("hswm", {})
    cosine = overall.get("cosine", {})

    n_queries = int(substrate.get("n_queries", -1))
    _require(n_queries == 300, "substrate ladder must contain 300 queries")
    sup_hswm = _close(
        hswm.get("sup_recall_at_3"), 0.7061, label="HSWM sup_recall@3",
    )
    sup_cosine = _close(
        cosine.get("sup_recall_at_3"), 0.6697, label="cosine sup_recall@3",
    )
    ndcg_hswm = _close(hswm.get("ndcg10"), 0.8388, label="HSWM nDCG@10")
    ndcg_cosine = _close(
        cosine.get("ndcg10"), 0.8129, label="cosine nDCG@10",
    )
    f1_hswm = _close(downstream.get("hswm", {}).get("f1"), 0.5414,
                     label="HSWM downstream F1")
    f1_cosine = _close(downstream.get("cosine", {}).get("f1"), 0.4685,
                       label="cosine downstream F1")
    f1_direct = _close(downstream.get("direct", {}).get("f1"), 0.6903,
                       label="direct-LLM downstream F1")
    p_sup = float(significance.get("sup_recall_at_3", {}).get(
        "hswm_vs_cosine", {},
    ).get("p_hswm_gt_arm", 1.0))
    p_ndcg = float(significance.get("ndcg10", {}).get(
        "hswm_vs_cosine", {},
    ).get("p_hswm_gt_arm", 1.0))
    _require(p_sup < 0.001 and p_ndcg < 0.001,
             "retrieval lift no longer clears p<0.001")
    _require(
        float(hswm.get("hit_at_3", 0.0)) < float(cosine.get("hit_at_3", 0.0))
        and float(hswm.get("mrr", 0.0)) < float(cosine.get("mrr", 0.0)),
        "the public caveat that cosine leads hit@3 and MRR no longer holds",
    )
    _require(
        substrate.get("hswm_judgment_counter_incl_cache_hits") == 300,
        "HSWM offline-judgment budget accounting drifted",
    )
    comparator_metrics: dict[str, dict[str, float]] = {}
    for arm in ("bm25", "ppr", "rrf"):
        arm_overall = overall.get(arm, {})
        arm_downstream = downstream.get(arm, {})
        comparator_metrics[arm] = {
            "sup_recall_at_3": float(arm_overall.get("sup_recall_at_3", math.nan)),
            "ndcg10": float(arm_overall.get("ndcg10", math.nan)),
            "downstream_f1": float(arm_downstream.get("f1", math.nan)),
        }
        _require(
            all(math.isfinite(value) for value in comparator_metrics[arm].values())
            and sup_hswm > comparator_metrics[arm]["sup_recall_at_3"]
            and ndcg_hswm > comparator_metrics[arm]["ndcg10"]
            and f1_hswm > comparator_metrics[arm]["downstream_f1"],
            f"HSWM no longer leads {arm} on all three published headline metrics",
        )

    replications = p5.get("per_dataset_replication", {})
    _require(replications == {"musique": False, "2wiki": True},
             "P5 dataset replication status drifted")
    worst_seed = _close(p5.get("worst_seed_delta_f1"), -0.2566,
                        label="P5 worst-seed delta F1")
    _require(len(p5.get("runs", [])) == 3,
             "P5 must retain exactly three checked-in runs")
    p5_runs = (
        ("musique_s7", p5_musique_s7, -0.2566),
        ("musique_s13", p5_musique_s13, -0.2317),
        ("2wiki_s7", p5_2wiki_s7, 0.0414),
    )
    run_deltas: dict[str, float] = {}
    for label, result, expected in p5_runs:
        run_deltas[label] = _close(
            result.get("delta", {}).get("f1_hswm_minus_direct"), expected,
            label=f"{label} F1 delta",
        )
        _require(
            result.get("llm_call_parity", {}).get("hswm_judgment_calls") == 100
            and result.get("llm_call_parity", {}).get("direct_rerank_calls") == 100
            and result.get("llm_call_parity", {}).get("parity_ok") is True,
            f"{label} LLM budget parity drifted",
        )
    two_wiki_p = _close(
        p5_2wiki_s7.get("delta", {}).get("p_hswm_gt_direct_f1"),
        0.084,
        label="2wiki_s7 paired-bootstrap p",
    )
    per_query = p5.get("per_query_by_run")
    _require(
        isinstance(per_query, Mapping) and len(per_query) == 3
        and all(isinstance(rows, list) for rows in per_query.values()),
        "P5 per-query ledger must contain three run lists",
    )
    per_query_rows = [row for rows in per_query.values() for row in rows]
    _require(
        len(per_query_rows) == 300
        and all(isinstance(row, Mapping) for row in per_query_rows),
        "P5 per-query ledger must contain 300 rows",
    )
    raw_delta_hswm_cosine = _close(
        _per_query_mean_delta(per_query_rows, "hswm", "cosine"),
        0.07283366666666666,
        label="raw per-query HSWM-minus-cosine F1 delta",
    )
    raw_delta_hswm_direct = _close(
        _per_query_mean_delta(per_query_rows, "hswm", "direct"),
        -0.148971,
        label="raw per-query HSWM-minus-direct F1 delta",
    )

    grid = traversal.get("grid_hopdrop_robustness", {})
    _require(grid.get("any_traversal_config_beats_static_hopdrop") is False,
             "a traversal configuration now beats static hop-drop")
    selected_traversal = str(traversal.get("selection", {}).get("selected", ""))
    static_hop_drop = _close(
        grid.get("static_hop_drop", {}).get("sup_recall_at_3"),
        0.2409,
        label="static support-recall hop-drop",
    )
    traversal_hop_drop = _close(
        grid.get("traversal_by_hparam", {}).get(
            selected_traversal, {},
        ).get("hop_drop", {}).get("sup_recall_at_3"),
        0.3539,
        label="selected traversal support-recall hop-drop",
    )
    _require(
        cert_musique.get("chosen_mu") == 0.0
        and cert_2wiki.get("chosen_mu") == 0.0,
        "real-data traversal is no longer certified OFF",
    )

    wrong_write_cost: dict[str, float] = {}
    for result, expected_baseline, expected_wrong, expected_cost in (
        (stale_musique, 0.6306, 0.5037, 12.69),
        (stale_2wiki, 0.78, 0.47, 31.0),
    ):
        dataset = str(result.get("dataset"))
        _require(result.get("kill_i", {}).get("survives") is False,
                 f"{dataset}: kill(i) status drifted")
        _require(result.get("kill_ii", {}).get("fires") is False,
                 f"{dataset}: kill(ii) status drifted")
        _require(result.get("kill_iii", {}).get("fires") is True,
                 f"{dataset}: kill(iii) status drifted")
        _require(result.get("kill_iii", {}).get("arm_a_vs_e_bit_exact") is True,
                 f"{dataset}: separated graded arm is no longer bit-exact")
        baseline = _close(
            result.get("per_dose", {}).get("0.1", {}).get(
                "a", {},
            ).get("cur_hop2_3"),
            expected_baseline,
            label=f"{dataset} full-dose primary current recall",
        )
        wrong = _close(
            result.get(
                "collateral_H_T3b_current_recall_after_WRONG_supersede", {},
            ).get("0.1"),
            expected_wrong,
            label=f"{dataset} wrong-write full-dose primary current recall",
        )
        wrong_write_cost[dataset] = round(
            _close(
                (baseline - wrong) * 100.0,
                expected_cost,
                label=f"{dataset} wrong-write primary recall cost points",
            ),
            2,
        )

    _require(certified_cut.get("verdict") == "PASS",
             "certified cut conformance no longer passes")
    controls = certified_cut.get("valid_controls", {})
    mutants = certified_cut.get("unique_adversarial_attacks", {})
    _require(
        controls.get("attempts") == 40
        and controls.get("cre_admitted") == 40
        and controls.get("cre_oracle_bit_exact") == 40
        and controls.get("golden_matches") is True,
        "certified cut positive-control accounting drifted",
    )
    _require(
        len(mutants) == 9
        and all(
            item.get("payload") is False and item.get("kernel_calls") == 0
            for item in mutants.values()
        ),
        "certified cut mutant accounting drifted",
    )
    scope = certified_cut.get("scope_fault_conformance", {})
    _require(
        scope.get("attempts") == 400
        and scope.get("cre_pre_kernel_refusals") == 400
        and scope.get("cre_payloads") == 0,
        "certified cut scope-fault accounting drifted",
    )
    _require(
        "does not measure" in str(certified_cut.get("non_claim", "")),
        "certified cut efficacy non-claim was removed",
    )
    _require(title_anchor.get("verdict") == "H3_REFUTED_OR_INCONCLUSIVE",
             "B1 title-anchor H3 verdict drifted")

    _verify_result_self_hash(qkv_routing, label="QKV routing")
    _require(
        qkv_routing.get("status") == "PASS"
        and qkv_routing.get("n_programs") == 64
        and qkv_routing.get("counts", {}).get("ordered_k2_exact") == 64
        and qkv_routing.get("counts", {}).get(
            "matched_k1_reaches_k2_target"
        ) == 0
        and all(qkv_routing.get("gates", {}).values()),
        "synthetic ordered QKV routing teeth drifted",
    )
    _verify_result_self_hash(qkv_b1, label="B1-QKV development")
    _require(
        qkv_b1.get("status") == "B1_QKV_REAL_DATA_GATE_FAILED",
        "B1-QKV real-data development verdict drifted",
    )
    qkv_datasets = {
        str(item.get("dataset")): item for item in qkv_b1.get("datasets", ())
        if isinstance(item, Mapping)
    }
    _require(
        set(qkv_datasets) == {"musique", "2wiki"}
        and all(item.get("verdict") == "FAIL" for item in qkv_datasets.values()),
        "B1-QKV must retain both failed dataset gates",
    )
    qkv_deltas: dict[str, dict[str, float]] = {}
    for dataset, expected_ndcg, expected_asr in (
        ("musique", -0.015238, -0.04),
        ("2wiki", -0.035466, 0.010204),
    ):
        comparisons = qkv_datasets[dataset].get("qkv_k2_minus", {})
        qkv_deltas[dataset] = {
            "ndcg10_k2_minus_k1": _close(
                comparisons.get("matched_k1", {}).get("ndcg10", {}).get(
                    "mean_delta"
                ),
                expected_ndcg,
                label=f"{dataset} B1-QKV K2-minus-K1 nDCG",
            ),
            "asr10_k2_minus_k1": _close(
                comparisons.get("matched_k1", {}).get("asr10", {}).get(
                    "mean_delta"
                ),
                expected_asr,
                label=f"{dataset} B1-QKV K2-minus-K1 ASR",
            ),
        }

    _verify_result_self_hash(semantic_layer, label="semantic-layer synthetic")
    _verify_source_bindings(repo, semantic_layer, label="semantic-layer synthetic")
    semantic_counts = semantic_layer.get("counts", {})
    _require(
        semantic_layer.get("verdict")
        == "SYNTHETIC_HETEROGENEOUS_TYPED_LAYER_MECHANISM_PASS"
        and semantic_layer.get("all_gates_pass") is True
        and semantic_layer.get("n_cases") == 128
        and semantic_layer.get("n_unique_semantic_templates") == 4
        and semantic_counts.get("typed_exact") == 128
        and semantic_counts.get("homogeneous_repeat_exact") == 64
        and semantic_counts.get("branch_erasure_atomic_refused") == 128
        and semantic_counts.get("receipt_envelope_hash_chain_valid") == 128
        and all(semantic_layer.get("gates", {}).values()),
        "heterogeneous semantic-layer synthetic gates drifted",
    )

    _verify_result_self_hash(semantic_2wiki, label="2Wiki semantic executor")
    _verify_source_bindings(repo, semantic_2wiki, label="2Wiki semantic executor")
    semantic_cohort = semantic_2wiki.get("cohort", {})
    semantic_primary = semantic_2wiki.get("primary", {})
    semantic_full = semantic_2wiki.get("full_development_refusal_counted", {})
    semantic_controls = semantic_2wiki.get("controls", {})
    _require(
        semantic_2wiki.get("status") == "DEVELOPMENT_EXECUTOR_COVERAGE_PROBE"
        and semantic_cohort.get("segment_qids") == 200
        and semantic_cohort.get("eligible") == 132
        and semantic_cohort.get("excluded") == 68
        and semantic_cohort.get("operator_counts") == {
            "ARGMAX_DATE": 30,
            "ARGMIN_DATE": 75,
            "LIFESPAN_ARGMAX": 2,
            "SET_OVERLAP_BOOL": 25,
        }
        and semantic_primary == {
            "exact": 132, "n": 132, "refused": 0, "supported": 132,
        }
        and semantic_full.get("n") == 200
        and semantic_full.get("exact") == 132
        and math.isclose(
            float(semantic_full.get("exact_rate", math.nan)),
            0.66, rel_tol=0.0, abs_tol=1e-12,
        ),
        "2Wiki evaluator-supplied semantic executor primary accounting drifted",
    )
    for control, expected_exact, expected_refused in (
        ("REDUCER_INVERT", 0, 0),
        ("TYPE_ERASED", 80, 2),
        ("RESOLVE_OFF", 109, 23),
        ("BRANCH_ERASURE", 0, 132),
        ("TYPE_NULL", 0, 132),
        ("EVIDENCE_NULL", 0, 132),
        ("K1_TRUNCATE", 0, 132),
    ):
        row = semantic_controls.get(control, {})
        _require(
            row.get("exact") == expected_exact
            and row.get("refused") == expected_refused,
            f"2Wiki semantic control {control} drifted",
        )
    _require(
        semantic_2wiki.get("boundary", {}).get("answer_join_claim")
        == "ordering_check_only_not_information_isolation",
        "2Wiki semantic answer-information boundary drifted",
    )

    _require(
        p1.get("schema_version") == "hswm-p1-closed-loop-evidence/v1"
        and p1.get("verdict") == "FAIL",
        "P1 closed-loop verdict boundary drifted",
    )
    p1_measurement = p1.get("measurement", {})
    p1_primary = _close(
        p1_measurement.get("value"), 0.0, label="P1 A1-minus-A2 recall@10",
    )
    p1_lower = _close(
        p1_measurement.get("bootstrap95_lower"), 0.0,
        label="P1 paired bootstrap lower bound",
    )
    p1_slope = _close(
        p1_measurement.get("secondary_a1_linear_slope"), -0.02708333333333333,
        label="P1 A1 recall@10 slope",
    )
    expected_later = {
        "A1_tagged_commit": 0.16510416666666666,
        "A2_no_commit": 0.16510416666666666,
        "A3_shuffled_M": 0.16510416666666666,
        "A4_uniform_commit": 0.16510416666666666,
    }
    p1_later = p1_measurement.get("later_episode_mean_recall10", {})
    for arm_id, expected in expected_later.items():
        _close(p1_later.get(arm_id), expected, label=f"P1 {arm_id} later recall@10")
    _require(
        p1.get("kill_conditions") == {
            "K1_primary_failed": True,
            "K2_shuffled_not_worse": True,
            "K3_uniform_not_worse": True,
            "K4_canary_regression": False,
            "K5_tag_utility_nonpositive": True,
        },
        "P1 kill-condition ledger drifted",
    )
    _require(
        p1.get("budget") == {
            "logical_answer_calls": 800,
            "answer_cache": {"COMPLETE": 200, "ERROR": 0, "STARTED": 0},
            "fresh_gate_llm_calls": 0,
            "graph_construction_llm_calls": 0,
        },
        "P1 answer-call budget ledger drifted",
    )
    _require(
        p1.get("gold_boundary") == {
            "gold_sent_to_answer_model": False,
            "gold_opened_only_post_answer": True,
            "per_question_gold_values_published": False,
        },
        "P1 sealed-gold boundary drifted",
    )

    p1_prereg = p1.get("preregistration", {})
    p1_prereg_path = str(p1_prereg.get("path", ""))
    _require(
        p1_prereg_path == "PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json",
        "P1 preregistration path drifted",
    )
    p1_prereg_sha = _file_sha256(repo / p1_prereg_path, label=p1_prereg_path)
    _require(
        p1_prereg.get("sha256") == p1_prereg_sha,
        "P1 preregistration file binding drifted",
    )

    p1_split = p1.get("split_manifest")
    _require(isinstance(p1_split, Mapping), "P1 split manifest is absent")
    p1_split_sha = sha256(json.dumps(
        p1_split, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    _require(
        p1.get("split_manifest_sha256") == p1_split_sha,
        "P1 split-manifest self-binding drifted",
    )

    p1_receipt = p1.get("experiment_receipt")
    _require(isinstance(p1_receipt, Mapping), "P1 experiment receipt is absent")
    p1_unsigned = dict(p1_receipt)
    p1_receipt_id = p1_unsigned.pop("receipt_id", None)
    p1_actual_receipt_id = sha256(json.dumps(
        p1_unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    _require(
        p1_receipt_id == p1_actual_receipt_id,
        "P1 experiment receipt self-hash drifted",
    )
    _require(
        p1_receipt.get("preregistration_sha256") == p1_prereg_sha
        and p1_receipt.get("split_manifest_sha256") == p1_split_sha,
        "P1 experiment receipt provenance binding drifted",
    )
    p1_arms = p1_receipt.get("arms")
    _require(isinstance(p1_arms, list) and len(p1_arms) == 4,
             "P1 four-arm receipt is incomplete")
    expected_arm_ids = {
        "A1_tagged_commit", "A2_no_commit", "A3_shuffled_M", "A4_uniform_commit",
    }
    _require(
        {str(arm.get("arm_id")) for arm in p1_arms if isinstance(arm, Mapping)}
        == expected_arm_ids,
        "P1 arm identities drifted",
    )
    candidate_count = 0
    activation_count = 0
    for arm in p1_arms:
        _require(isinstance(arm, Mapping), "P1 arm receipt is malformed")
        _require(
            arm.get("starting_snapshot_id") == arm.get("final_snapshot_id"),
            f"P1 arm {arm.get('arm_id')} unexpectedly activated learned state",
        )
        episodes = arm.get("episodes")
        _require(isinstance(episodes, list) and len(episodes) == 5,
                 f"P1 arm {arm.get('arm_id')} episode ledger drifted")
        for episode in episodes:
            _require(isinstance(episode, Mapping), "P1 episode receipt is malformed")
            if episode.get("candidate_id") is not None:
                candidate_count += 1
                _require(
                    episode.get("fsm_final_state") == "rejected",
                    "P1 candidate is no longer recorded as rejected",
                )
            if episode.get("activation_receipt_id") is not None:
                activation_count += 1
    _require(
        candidate_count == 12 and activation_count == 0,
        "P1 candidate or activation count drifted",
    )

    p1_evidence_sha = _file_sha256(
        repo / "EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json",
        label="P1 evidence",
    )
    _require(
        p1_gate.get("schema_version") == "hswm-p1-posthoc-gate-diagnostic/v1"
        and p1_gate.get("scientific_status")
        == "POSTHOC_DIAGNOSTIC_NOT_A_NEW_ARM_OUTCOME",
        "P1 posthoc diagnostic boundary drifted",
    )
    p1_gate_unsigned = dict(p1_gate)
    p1_gate_declared_sha = p1_gate_unsigned.pop("diagnostic_sha256", None)
    p1_gate_actual_sha = sha256(json.dumps(
        p1_gate_unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    _require(
        p1_gate_declared_sha == p1_gate_actual_sha,
        "P1 gate diagnostic self-hash drifted",
    )
    _require(
        p1_gate.get("source_evidence_sha256") == p1_evidence_sha
        and p1_gate.get("frozen_split_manifest_sha256") == p1_split_sha,
        "P1 gate diagnostic provenance binding drifted",
    )
    _require(
        p1_gate.get("summary") == {
            "candidates": 12,
            "fresh_gate_passes": 0,
            "nonzero_unseen_delta": 0,
        },
        "P1 gate diagnostic summary drifted",
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "retrieval_substrate": {
            "status": "MEASURED_POSITIVE_WITH_BUDGET_CAVEAT",
            "n_queries": n_queries,
            "hswm": {
                "sup_recall_at_3": sup_hswm,
                "ndcg10": ndcg_hswm,
                "downstream_f1": f1_hswm,
            },
            "cosine": {
                "sup_recall_at_3": sup_cosine,
                "ndcg10": ndcg_cosine,
                "downstream_f1": f1_cosine,
            },
            "listed_zero_llm_comparators": comparator_metrics,
            "delta_hswm_minus_cosine": {
                "sup_recall_at_3": round(sup_hswm - sup_cosine, 4),
                "ndcg10": round(ndcg_hswm - ndcg_cosine, 4),
                "downstream_f1": round(f1_hswm - f1_cosine, 4),
            },
            "raw_per_query_mean_delta_downstream_f1": round(
                raw_delta_hswm_cosine, 6,
            ),
            "displayed_delta_definition": (
                "subtraction of four-decimal displayed aggregate means"
            ),
            "paired_bootstrap_p_hswm_gt_cosine": {
                "sup_recall_at_3": p_sup,
                "ndcg10": p_ndcg,
            },
            "caveat": (
                "HSWM uses 100 offline LLM judgments per run (300 total); "
                "the listed retrieval baselines use none"
            ),
        },
        "cognitive_uplift_vs_direct_llm": {
            "status": "PREREGISTERED_CROSS_DATASET_CLAIM_FAILED",
            "pooled_hswm_f1": f1_hswm,
            "pooled_direct_f1": f1_direct,
            "pooled_delta": round(f1_hswm - f1_direct, 4),
            "raw_per_query_mean_delta": round(raw_delta_hswm_direct, 6),
            "displayed_delta_definition": (
                "subtraction of four-decimal displayed aggregate means"
            ),
            "worst_seed_delta": worst_seed,
            "dataset_replication": replications,
            "per_run_delta_hswm_minus_direct": run_deltas,
            "2wiki_positive_run_paired_bootstrap_p": two_wiki_p,
        },
        "query_time_traversal": {
            "status": "CERTIFIED_OFF_ON_MUSIQUE_AND_2WIKI",
            "musique_mu": cert_musique["chosen_mu"],
            "2wiki_mu": cert_2wiki["chosen_mu"],
            "selected_grid_configuration": selected_traversal,
            "support_recall_hop_drop": {
                "static": static_hop_drop,
                "selected_traversal": traversal_hop_drop,
            },
            "any_grid_configuration_beats_static_hopdrop": False,
        },
        "p1_closed_macro_weight_loop": {
            "status": "ENGINEERING_COMPLETE_CAUSAL_EFFICACY_REJECTED",
            "verdict": "FAIL",
            "a1_minus_a2_mean_paired_recall10": p1_primary,
            "bootstrap95_lower": p1_lower,
            "a1_linear_slope": p1_slope,
            "later_episode_mean_recall10": expected_later,
            "candidates_staged": candidate_count,
            "fresh_gate_passes": 0,
            "activations": activation_count,
            "experiment_receipt_id": p1_receipt_id,
            "boundary": (
                "The outcome-to-credit-to-candidate loop executed, but no "
                "candidate changed fresh top-10 retrieval or became active"
            ),
        },
        "graded_supersession": {
            "status": "POINTWISE_CAPABILITY_SURVIVES_ONE_FIELD_NOVELTY_RETRACTED",
            "kill_i_fired_both": True,
            "kill_ii_fired_both": False,
            "kill_iii_fired_both": True,
            "wrong_write_primary_recall_cost_points": wrong_write_cost,
        },
        "compiler_and_certified_readout": {
            "status": "LOCAL_CONFORMANCE_PASS_NOT_EFFICACY",
            "valid_controls": 40,
            "scope_fault_refusals": 400,
            "scope_fault_payloads": 0,
            "unique_mutant_refusals": 9,
        },
        "h3_relational_composition": {
            "b1_title_anchor": "REFUTED_OR_INCONCLUSIVE",
            "b3_evidence_bound": "NOT_YET_MEASURED",
        },
        "qkv_structure": {
            "synthetic_ordered_routing": "PASS_64_OF_64",
            "b1_real_data_development": "CROSS_DATASET_GATE_FAILED",
            "k2_minus_matched_k1": qkv_deltas,
            "heterogeneous_semantic_fixture": {
                "status": "PASS_128_NAMESPACE_CASES_4_UNIQUE_TEMPLATES",
                "typed_exact": semantic_counts["typed_exact"],
                "homogeneous_association_erased_exact": semantic_counts[
                    "homogeneous_repeat_exact"
                ],
                "branch_erasure_atomic_refused": semantic_counts[
                    "branch_erasure_atomic_refused"
                ],
            },
            "2wiki_evaluator_supplied_memory": {
                "status": "EXECUTOR_COVERAGE_NOT_EFFICACY",
                "conditional_exact": semantic_primary["exact"],
                "conditional_n": semantic_primary["n"],
                "full_development_refusal_counted_exact_rate": semantic_full[
                    "exact_rate"
                ],
                "type_erased_exact": semantic_controls["TYPE_ERASED"]["exact"],
                "resolver_off_exact": semantic_controls["RESOLVE_OFF"]["exact"],
            },
            "boundary": (
                "Supplied heterogeneous typed programs execute coherently, but "
                "the deployable no-label arm remains absent and current "
                "title-value recurrence does not establish reasoning uplift"
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    snapshot = build_snapshot(args.root)
    print(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
