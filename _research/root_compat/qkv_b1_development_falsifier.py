"""Development-only real-data falsifier for the B1-QKV query update.

Policy selection uses the relation/evidence-disjoint validation half of each
existing development segment.  The held development test half compares K2 to
matched K1, cosine, and five degree-preserving value/topology shuffles.  Fresh
paths are rejected by :mod:`qkv_b1_probe` and are not accepted by this CLI.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import bge_m3_embed as bge
import composition as comp
import metrics
import qkv_b1_probe as probe
import relation_eval as reval
from world_ir import canonical_json


SCHEMA_VERSION = "hswm-qkv-b1-development-falsifier/v1"
SPLIT_SEED = 42
BOOTSTRAP_SEED = 20260720
N_BOOTSTRAP = 10_000
SHUFFLE_SEEDS = (0, 1, 2, 3, 4)
PRIMARY_THRESHOLDS = {"ndcg10": 0.02, "asr10": 0.03}
POLICY_GRID = tuple(
    probe.QKVB1PolicyV1(
        seed_k=seed_k, hops=2, gamma=gamma,
        temperature=temperature, max_fanout=16,
    )
    for seed_k in (3, 10)
    for temperature in (0.05, 0.10, 0.20)
    for gamma in (0.10, 0.25, 0.50, 1.00)
)


class DevelopmentFalsifierError(RuntimeError):
    pass


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(value, dtype="<f8"))
    return sha256(array.tobytes(order="C")).hexdigest()


def _raw_rows_for_segment(
    dataset: probe.DevelopmentDatasetV1,
    raw_sidecar_path: str | Path,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[str, ...]]:
    segment = json.loads(Path(dataset.segment_path).read_text(encoding="utf-8"))
    if segment.get("split") != "development" or segment.get("dataset") != dataset.dataset:
        raise DevelopmentFalsifierError("segment identity/split drift")
    qids = tuple(str(row["qid"]) for row in segment["evaluation_rows"])
    if len(qids) != len(set(qids)):
        raise DevelopmentFalsifierError("segment qids must be unique")

    raw_path = Path(raw_sidecar_path)
    wrapper = json.loads(raw_path.read_text(encoding="utf-8"))
    rows = wrapper.get("rows")
    if wrapper.get("dataset") != dataset.dataset or not isinstance(rows, list):
        raise DevelopmentFalsifierError("raw relation sidecar identity drift")
    rows_digest = sha256(canonical_json(tuple(rows)).encode("utf-8")).hexdigest()
    if rows_digest != wrapper.get("rows_sha256"):
        raise DevelopmentFalsifierError("raw relation sidecar digest mismatch")
    by_qid = {
        str(row.get("id", row.get("_id", ""))): row for row in rows
    }
    try:
        selected = tuple(by_qid[qid] for qid in qids)
    except KeyError as exc:
        raise DevelopmentFalsifierError(
            f"raw sidecar lacks development qid {exc.args[0]}"
        ) from exc
    return selected, qids


def _split_bindings(
    dataset: probe.DevelopmentDatasetV1,
    raw_sidecar_path: str | Path,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[str, ...], dict[str, Any]]:
    raw_rows, all_qids = _raw_rows_for_segment(dataset, raw_sidecar_path)
    suite = reval.build_relation_evaluation_suite(
        dataset.dataset, raw_rows,
        split_spec=(("val", 0.5), ("test", 0.5)), seed=SPLIT_SEED,
    )
    examples = {item.qid: item for item in suite.examples}
    assignments = {item.occurrence_id: item for item in suite.assignments}
    split_by_qid: dict[str, str] = {}
    component_by_qid: dict[str, str] = {}
    for qid in all_qids:
        example = examples[qid]
        assignment = assignments[example.occurrence_id]
        split_by_qid[qid] = assignment.split
        component_by_qid[qid] = assignment.component_id

    val = tuple(
        index for index, query in enumerate(dataset.queries)
        if split_by_qid[query.qid] == "val"
    )
    test = tuple(
        index for index, query in enumerate(dataset.queries)
        if split_by_qid[query.qid] == "test"
    )
    if not val or not test:
        raise DevelopmentFalsifierError("development split is empty after fail-closed drops")
    components = tuple(component_by_qid[item.qid] for item in dataset.queries)
    return val, test, components, {
        "suite_id": suite.suite_id,
        "raw_snapshot_sha256": suite.raw_snapshot_sha256,
        "raw_sidecar_path": str(raw_sidecar_path),
        "raw_sidecar_sha256": _file_sha256(raw_sidecar_path),
        "split_seed": SPLIT_SEED,
        "grouping": "union(relation_template_id, exact_evidence_content_id)",
        "val_queries": len(val),
        "test_queries": len(test),
    }


def _static_matrix(
    dataset: probe.DevelopmentDatasetV1, indices: Sequence[int],
) -> np.ndarray:
    return np.stack([
        dataset.key_vectors @ dataset.queries[index].query_vector
        for index in indices
    ])


def _score_matrix(
    dataset: probe.DevelopmentDatasetV1,
    indices: Sequence[int],
    policy: probe.QKVB1PolicyV1,
    *,
    graph: comp.CompositionGraphV1 | None = None,
) -> tuple[np.ndarray, tuple[probe.QKVB1ReceiptV1, ...]]:
    selected_graph = dataset.graph if graph is None else graph
    rows: list[np.ndarray] = []
    receipts: list[probe.QKVB1ReceiptV1] = []
    for index in indices:
        query = dataset.queries[index]
        scores, receipt = probe.score_qkv_b1(
            query.query_vector, dataset.key_vectors, selected_graph, policy,
            value_vectors=dataset.value_vectors,
        )
        rows.append(scores)
        receipts.append(receipt)
    return np.stack(rows), tuple(receipts)


def _metric_arrays(
    matrix: np.ndarray,
    dataset: probe.DevelopmentDatasetV1,
    indices: Sequence[int],
) -> dict[str, np.ndarray]:
    rows: list[dict[str, float]] = []
    for row_index, query_index in enumerate(indices):
        query = dataset.queries[query_index]
        gold = np.asarray(query.gold_ordinals, dtype=np.int64)
        order = np.argsort(-matrix[row_index], kind="stable")
        top = set(int(item) for item in order[:probe.K_METRIC])
        gold_set = set(query.gold_ordinals)
        rows.append({
            "ndcg10": float(metrics.ndcg_at_k(
                matrix[row_index], gold, np.arange(matrix.shape[1]),
                k=probe.K_METRIC, seed=query_index + 1,
            )),
            "asr10": float(gold_set.issubset(top)),
            "support_recall10": len(gold_set & top) / len(gold_set),
        })
    return {
        name: np.asarray([row[name] for row in rows], dtype=np.float64)
        for name in ("ndcg10", "asr10", "support_recall10")
    }


def _means(values: Mapping[str, np.ndarray]) -> dict[str, float]:
    return {
        name: round(float(row.mean()), 6) for name, row in values.items()
    }


def _receipt_summary(
    receipts: Sequence[probe.QKVB1ReceiptV1], policy: probe.QKVB1PolicyV1,
) -> dict[str, Any]:
    n = len(receipts)
    roots = tuple(item.receipt_sha256 for item in receipts)
    return {
        "apply_coverage": round(sum(item.applied for item in receipts) / n, 6),
        "fallback_rate": round(sum(not item.applied for item in receipts) / n, 6),
        "full_depth_apply_rate": round(
            sum(len(item.layers) == policy.hops for item in receipts) / n, 6,
        ),
        "trip_reasons": {
            reason: sum(item.trip_reason == reason for item in receipts)
            for reason in sorted({item.trip_reason for item in receipts if item.trip_reason})
        },
        "receipt_root_sha256": sha256(
            canonical_json(roots).encode("utf-8")
        ).hexdigest(),
    }


def _cluster_bootstrap(
    delta: np.ndarray,
    components: Sequence[str],
    *,
    seed: int,
    n_bootstrap: int = N_BOOTSTRAP,
) -> dict[str, Any]:
    values = np.asarray(delta, dtype=np.float64)
    component_array = np.asarray(tuple(components), dtype=object)
    if values.ndim != 1 or values.size == 0 or values.size != component_array.size:
        raise ValueError("delta and components must be non-empty and aligned")
    keys = tuple(sorted(set(str(item) for item in component_array)))
    grouped = {
        key: np.flatnonzero(component_array == key) for key in keys
    }
    rng = np.random.default_rng(seed)
    draws = np.empty(n_bootstrap, dtype=np.float64)
    for draw in range(n_bootstrap):
        chosen = rng.integers(0, len(keys), len(keys))
        sample = np.concatenate([values[grouped[keys[int(item)]]] for item in chosen])
        draws[draw] = float(sample.mean())
    return {
        "mean_delta": round(float(values.mean()), 6),
        "ci95": [
            round(float(np.percentile(draws, 2.5)), 6),
            round(float(np.percentile(draws, 97.5)), 6),
        ],
        "n_components": len(keys),
        "n_bootstrap": n_bootstrap,
        "seed": seed,
    }


def _arm(
    matrix: np.ndarray,
    metrics_by_query: Mapping[str, np.ndarray],
    receipts: Sequence[probe.QKVB1ReceiptV1] | None = None,
    policy: probe.QKVB1PolicyV1 | None = None,
) -> dict[str, Any]:
    value = {
        "metrics": _means(metrics_by_query),
        "score_matrix_sha256": _array_sha256(matrix),
    }
    if receipts is not None and policy is not None:
        value["runtime"] = _receipt_summary(receipts, policy)
    return value


def _select_policy(
    dataset: probe.DevelopmentDatasetV1,
    val: Sequence[int],
) -> tuple[probe.QKVB1PolicyV1, list[dict[str, Any]]]:
    surface: list[tuple[float, float, probe.QKVB1PolicyV1, dict[str, float]]] = []
    for policy in POLICY_GRID:
        matrix, _ = _score_matrix(dataset, val, policy)
        means = _means(_metric_arrays(matrix, dataset, val))
        surface.append((means["ndcg10"], means["asr10"], policy, means))
    selected = max(surface, key=lambda item: (
        item[0], item[1], -item[2].gamma, -item[2].seed_k,
        -item[2].temperature,
    ))[2]
    top = sorted(surface, key=lambda item: (
        item[0], item[1], -item[2].gamma, -item[2].seed_k,
        -item[2].temperature,
    ), reverse=True)[:8]
    return selected, [{"policy": asdict(policy), "metrics": means}
                      for _ndcg, _asr, policy, means in top]


def _edge_pairs(graph: comp.CompositionGraphV1) -> set[tuple[int, int]]:
    return {(item.source_target, item.target_target) for item in graph.arcs}


def _edge_multiset(graph: comp.CompositionGraphV1) -> Counter[tuple[int, int]]:
    return Counter(
        (item.source_target, item.target_target) for item in graph.arcs
    )


def _degree_preserving_value_shuffle(
    graph: comp.CompositionGraphV1,
    seed: int,
    *,
    max_attempts: int = 200,
) -> comp.CompositionGraphV1:
    """Permute target Values while preserving multigraph in/out degrees.

    ``composition.degree_preserving_shuffle`` assumes unique endpoint pairs,
    while B1 legitimately retains multiple exact receipts for one pair.  This
    local null keeps every source occurrence and the complete target multiset,
    gives duplicate null arcs distinct identities, and rejects self loops.
    """

    if seed < 0 or max_attempts < 1:
        raise ValueError("seed must be non-negative and max_attempts positive")
    sources = np.asarray(
        [item.source_target for item in graph.arcs], dtype=np.int64,
    )
    targets = np.asarray(
        [item.target_target for item in graph.arcs], dtype=np.int64,
    )
    if targets.size < 2:
        raise DevelopmentFalsifierError("degree-preserving null needs two arcs")
    rng = np.random.default_rng(seed)
    selected: np.ndarray | None = None
    for _ in range(max_attempts):
        candidate = targets[rng.permutation(targets.size)]
        if np.array_equal(candidate, targets) or np.any(candidate == sources):
            continue
        selected = candidate
        break
    if selected is None:
        raise DevelopmentFalsifierError(
            f"seed {seed}: no self-loop-free multigraph value permutation"
        )
    arcs = tuple(
        comp.EvidenceArcV1(
            source_target=int(source), target_target=int(target),
            source_id=f"NULL_QKV_VALUE_SHUFFLE:{seed}:{index}",
            selector_start=0,
            selector_end=len(f"NULL_VALUE_{index}"),
            selector_exact=f"NULL_VALUE_{index}",
            anchor_label="NULL_QKV_VALUE_SHUFFLE",
        )
        for index, (source, target) in enumerate(
            zip(sources, selected, strict=True)
        )
    )
    return comp.make_graph(graph.target_ids, arcs, is_null_control=True)


def evaluate_dataset(
    dataset: probe.DevelopmentDatasetV1,
    raw_sidecar_path: str | Path,
) -> dict[str, Any]:
    val, test, components, split_receipt = _split_bindings(
        dataset, raw_sidecar_path,
    )
    selected, selection_surface = _select_policy(dataset, val)
    k1_policy = replace(selected, hops=1)
    static = _static_matrix(dataset, test)
    k1_matrix, k1_receipts = _score_matrix(dataset, test, k1_policy)
    k2_matrix, k2_receipts = _score_matrix(dataset, test, selected)
    static_metrics = _metric_arrays(static, dataset, test)
    k1_metrics = _metric_arrays(k1_matrix, dataset, test)
    k2_metrics = _metric_arrays(k2_matrix, dataset, test)
    test_components = tuple(components[index] for index in test)

    comparisons: dict[str, Any] = {}
    for name, comparator in (("matched_k1", k1_metrics), ("cosine", static_metrics)):
        comparisons[name] = {
            metric: _cluster_bootstrap(
                k2_metrics[metric] - comparator[metric], test_components,
                seed=BOOTSTRAP_SEED + offset,
            )
            for offset, metric in enumerate(("ndcg10", "asr10", "support_recall10"))
        }

    real_pairs = _edge_multiset(dataset.graph)
    null_rows: list[dict[str, Any]] = []
    nulls_pass = True
    for null_seed in SHUFFLE_SEEDS:
        null_graph = _degree_preserving_value_shuffle(dataset.graph, null_seed)
        null_pairs = _edge_multiset(null_graph)
        changed_fraction = (
            1.0 - sum((real_pairs & null_pairs).values()) / sum(real_pairs.values())
            if real_pairs else 0.0
        )
        valid = bool(real_pairs and null_pairs != real_pairs)
        null_matrix, null_receipts = _score_matrix(
            dataset, test, selected, graph=null_graph,
        )
        null_metrics = _metric_arrays(null_matrix, dataset, test)
        inference = {
            metric: _cluster_bootstrap(
                k2_metrics[metric] - null_metrics[metric], test_components,
                seed=BOOTSTRAP_SEED + 100 * (null_seed + 1) + offset,
            )
            for offset, metric in enumerate(("ndcg10", "asr10", "support_recall10"))
        }
        primary_better = all(
            inference[name]["mean_delta"] > 0
            and inference[name]["ci95"][0] > 0
            for name in PRIMARY_THRESHOLDS
        )
        nulls_pass = nulls_pass and valid and primary_better
        null_rows.append({
            "seed": null_seed,
            "valid": valid,
            "changed_edge_fraction": round(changed_fraction, 6),
            "topology_sha256": null_graph.topology_sha256,
            "arm": _arm(null_matrix, null_metrics, null_receipts, selected),
            "real_k2_minus_null": inference,
            "primary_better": primary_better,
        })

    gamma0 = replace(selected, gamma=0.0)
    gamma0_matrix, gamma0_receipts = _score_matrix(dataset, test, gamma0)
    gamma0_identity = bool(gamma0_matrix.tobytes() == static.tobytes())
    gamma0_receipt_identity = all(
        item.static_score_sha256 == item.final_score_sha256
        and not item.applied for item in gamma0_receipts
    )

    primary_gate: dict[str, bool] = {}
    for name in PRIMARY_THRESHOLDS:
        threshold = PRIMARY_THRESHOLDS[name]
        for comparison in ("matched_k1", "cosine"):
            row = comparisons[comparison][name]
            primary_gate[f"{name}_vs_{comparison}"] = bool(
                row["mean_delta"] >= threshold and row["ci95"][0] > 0
            )
    apply_coverage = sum(item.applied for item in k2_receipts) / len(k2_receipts)
    gates = {
        **primary_gate,
        "beats_every_degree_preserving_null": nulls_pass,
        "apply_coverage_at_least_0_50": apply_coverage >= 0.50,
        "gamma0_static_bit_identity": gamma0_identity and gamma0_receipt_identity,
    }
    passed = all(gates.values())
    return {
        "dataset": dataset.dataset,
        "verdict": "PASS" if passed else "FAIL",
        "n_targets": len(dataset.target_ids),
        "n_evidence_arcs": len(dataset.graph.arcs),
        "n_exact_queries": len(dataset.queries),
        "dropped_query_ids": list(dataset.dropped_query_ids),
        "split_receipt": split_receipt,
        "selected_policy": asdict(selected),
        "selection_top8": selection_surface,
        "arms": {
            "cosine": _arm(static, static_metrics),
            "qkv_k1": _arm(k1_matrix, k1_metrics, k1_receipts, k1_policy),
            "qkv_k2": _arm(k2_matrix, k2_metrics, k2_receipts, selected),
        },
        "qkv_k2_minus": comparisons,
        "degree_preserving_nulls": null_rows,
        "gamma0": {
            "score_bit_identical_to_cosine": gamma0_identity,
            "receipts_static_and_unapplied": gamma0_receipt_identity,
            "score_matrix_sha256": _array_sha256(gamma0_matrix),
        },
        "gates": gates,
    }


def run_experiment(
    development_segment_paths: Sequence[str | Path],
    embedding_npz_path: str | Path,
    raw_sidecars: Mapping[str, str | Path],
) -> dict[str, Any]:
    datasets = probe.load_development_datasets(
        development_segment_paths, embedding_npz_path,
    )
    if {item.dataset for item in datasets} != {"musique", "2wiki"}:
        raise DevelopmentFalsifierError("both development datasets are required")
    reports = [evaluate_dataset(item, raw_sidecars[item.dataset]) for item in datasets]
    reports.sort(key=lambda item: item["dataset"])
    passed = all(item["verdict"] == "PASS" for item in reports)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if passed else "B1_QKV_REAL_DATA_GATE_FAILED",
        "scope": "development-only exploratory; no fresh segment or B3 extraction",
        "policy_grid": [asdict(item) for item in POLICY_GRID],
        "primary_thresholds": PRIMARY_THRESHOLDS,
        "bootstrap": {
            "resampling_unit": "relation/evidence component",
            "n_draws": N_BOOTSTRAP,
            "base_seed": BOOTSTRAP_SEED,
        },
        "embedding_model": {
            "model": bge.FROZEN_MODEL_ID,
            "revision": bge.FROZEN_MODEL_REVISION,
            "artifact_path": str(embedding_npz_path),
            "artifact_sha256": _file_sha256(embedding_npz_path),
        },
        "datasets": reports,
        "implementation": {
            "qkv_b1_probe.py": _file_sha256(Path(probe.__file__)),
            "qkv_b1_development_falsifier.py": _file_sha256(Path(__file__)),
        },
        "conclusion": (
            "B1-QKV clears the frozen real-data development mechanism gate"
            if passed else
            "B1-QKV query updates execute, but do not establish cross-dataset "
            "real-data retrieval uplift"
        ),
        "forbidden_claims": [
            "fresh confirmatory efficacy",
            "B3 claim-level QKV efficacy",
            "answer reasoning uplift",
            "general cognitive uplift",
            "neural network equivalence",
        ],
        "research_only": True,
    }
    result["result_sha256"] = sha256(
        canonical_json(result).encode("utf-8")
    ).hexdigest()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--musique-development", required=True)
    parser.add_argument("--2wiki-development", required=True)
    parser.add_argument("--embedding-npz", required=True)
    parser.add_argument("--musique-raw", required=True)
    parser.add_argument("--2wiki-raw", required=True)
    parser.add_argument("--out", default="qkv_b1_development_result.json")
    args = parser.parse_args(argv)
    result = run_experiment(
        (args.musique_development, args.__dict__["2wiki_development"]),
        args.embedding_npz,
        {"musique": args.musique_raw, "2wiki": args.__dict__["2wiki_raw"]},
    )
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"], "out": args.out,
        "result_sha256": result["result_sha256"],
    }, sort_keys=True))
    # A failed scientific gate is a valid completed experiment, not a process
    # failure.  Integrity exceptions still produce a non-zero exit naturally.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["evaluate_dataset", "run_experiment"]
