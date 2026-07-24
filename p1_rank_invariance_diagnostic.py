"""Post-hoc rank-actuation diagnosis for the frozen P1 slow-weight run.

This script does not rerun the answer model or produce a new arm outcome. It
replays frozen retrieval from staged snapshot bytes and measures where the
learning signal was lost: edge/path overlap, score movement, top-k movement,
and the rank-10 boundary margin.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
from typing import Mapping, Sequence

import numpy as np

from hswm_weight_snapshot import canonical_sha256, parse_candidate, parse_snapshot
from p1_phantom_environment import (
    SEED_K,
    TOP_K,
    PhantomP1Environment,
    _relation_quality,
)
from p1_weighted_walk import walk_scores_weighted_strict
from r1_predicate_alias import query_term_closure


SCHEMA_VERSION = "hswm-p1-posthoc-rank-invariance/v1"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _blob(connection: sqlite3.Connection, query: str, key: str) -> bytes:
    row = connection.execute(query, (key,)).fetchone()
    if row is None:
        raise RuntimeError(f"missing frozen row {key}")
    value = row[0]
    return value if isinstance(value, bytes) else bytes(value)


def _score_probe(environment, question: Mapping[str, object], snapshot):
    static = environment.doc_vectors @ environment.query_vectors[str(question["id"])]
    seeds = tuple(int(index) for index in np.argsort(-static, kind="stable")[:SEED_K])
    query_terms = query_term_closure(str(question["question"]))
    result = walk_scores_weighted_strict(
        static,
        environment.graph,
        seeds=seeds,
        edge_log_salience=snapshot.weight_map(),
        relation_quality=lambda arc: _relation_quality(
            query_terms, arc, environment.alias_index
        ),
    )
    scores = np.asarray(result.k2_scores, dtype=np.float64)
    order = np.argsort(-scores, kind="stable")
    paths = {path.target: path for path in result.selected_paths}
    return scores, order, paths


def rank_change_metrics(
    base_scores: Sequence[float],
    candidate_scores: Sequence[float],
    base_order: Sequence[int],
    candidate_order: Sequence[int],
) -> dict[str, object]:
    """Return exact rank-actuation metrics for one frozen query."""

    base = np.asarray(base_scores, dtype=np.float64)
    candidate = np.asarray(candidate_scores, dtype=np.float64)
    before = np.asarray(base_order, dtype=np.int64)
    after = np.asarray(candidate_order, dtype=np.int64)
    if base.shape != candidate.shape or before.shape != after.shape:
        raise ValueError("score and order shapes must match")
    if base.ndim != 1 or len(base) <= TOP_K:
        raise ValueError("rank probe requires a one-dimensional top-k boundary")
    delta = candidate - base
    max_abs = float(np.max(np.abs(delta)))
    boundary_gap = float(base[before[TOP_K - 1]] - base[before[TOP_K]])
    membership_changed = set(map(int, before[:TOP_K])) != set(map(int, after[:TOP_K]))
    order_changed = not np.array_equal(before[:TOP_K], after[:TOP_K])
    changed_targets = int(np.count_nonzero(delta != 0.0))
    ratio = None if boundary_gap <= 0.0 else max_abs / boundary_gap
    return {
        "max_abs_score_delta": max_abs,
        "changed_targets": changed_targets,
        "rank10_11_gap": boundary_gap,
        "max_delta_to_boundary_gap": ratio,
        "top10_membership_changed": membership_changed,
        "top10_order_changed": order_changed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--experiment-directory", type=Path, required=True)
    parser.add_argument("--embedding-cache-folder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    environment = PhantomP1Environment(
        dataset_root=args.dataset_root,
        work_directory=args.experiment_directory,
        answerer=object(),
        embedding_cache_folder=args.embedding_cache_folder,
    )
    candidate_rows = []
    for arm in evidence["experiment_receipt"]["arms"]:
        database = args.experiment_directory / "arms" / f"{arm['arm_id']}.weights.sqlite3"
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            for episode in arm["episodes"]:
                candidate_id = episode["candidate_id"]
                if candidate_id is None:
                    continue
                candidate_record = parse_candidate(_blob(
                    connection,
                    "SELECT canonical_candidate FROM staged_weight_candidates "
                    "WHERE candidate_id = ?",
                    candidate_id,
                ))
                staged = connection.execute(
                    "SELECT snapshot_id FROM staged_weight_candidates WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchone()
                if staged is None:
                    raise RuntimeError(f"missing staged snapshot {candidate_id}")
                base = parse_snapshot(_blob(
                    connection,
                    "SELECT canonical_snapshot FROM weight_snapshots WHERE snapshot_id = ?",
                    str(episode["base_snapshot_id"]),
                ))
                candidate = parse_snapshot(_blob(
                    connection,
                    "SELECT canonical_snapshot FROM weight_snapshots WHERE snapshot_id = ?",
                    str(staged[0]),
                ))
                touched = {delta.edge_id for delta in candidate_record.deltas}
                query_rows = []
                for question in environment.gate_questions[int(episode["episode_index"]) - 1]:
                    base_scores, base_order, base_paths = _score_probe(
                        environment, question, base
                    )
                    candidate_scores, candidate_order, candidate_paths = _score_probe(
                        environment, question, candidate
                    )
                    metrics = rank_change_metrics(
                        base_scores, candidate_scores, base_order, candidate_order
                    )
                    selected_edges = {
                        edge_id
                        for path in tuple(base_paths.values()) + tuple(candidate_paths.values())
                        for edge_id in path.edge_ids
                    }
                    query_rows.append({
                        **metrics,
                        "touched_selected_path": bool(touched & selected_edges),
                    })
                ratios = [
                    float(row["max_delta_to_boundary_gap"])
                    for row in query_rows
                    if row["max_delta_to_boundary_gap"] is not None
                ]
                deltas = [
                    abs(delta.after_log_salience - delta.before_log_salience)
                    for delta in candidate_record.deltas
                ]
                candidate_rows.append({
                    "arm_id": arm["arm_id"],
                    "episode_index": episode["episode_index"],
                    "candidate_id": candidate_id,
                    "candidate_edges": len(touched),
                    "candidate_l1": math.fsum(deltas),
                    "candidate_max_abs_log_delta": max(deltas),
                    "fresh_queries": len(query_rows),
                    "queries_with_touched_selected_path": sum(
                        bool(row["touched_selected_path"]) for row in query_rows
                    ),
                    "queries_with_any_score_change": sum(
                        int(row["changed_targets"]) > 0 for row in query_rows
                    ),
                    "queries_with_top10_order_change": sum(
                        bool(row["top10_order_changed"]) for row in query_rows
                    ),
                    "queries_with_top10_membership_change": sum(
                        bool(row["top10_membership_changed"]) for row in query_rows
                    ),
                    "max_abs_score_delta": max(
                        float(row["max_abs_score_delta"]) for row in query_rows
                    ),
                    "min_rank10_11_gap": min(
                        float(row["rank10_11_gap"]) for row in query_rows
                    ),
                    "max_delta_to_boundary_gap": max(ratios) if ratios else None,
                })

    output = {
        "schema_version": SCHEMA_VERSION,
        "scientific_status": "POSTHOC_MECHANISM_DIAGNOSTIC_NOT_A_NEW_ARM_OUTCOME",
        "source_evidence_sha256": _sha(args.evidence),
        "frozen_split_manifest_sha256": environment.split_manifest_sha256,
        "candidates": candidate_rows,
        "summary": {
            "candidates": len(candidate_rows),
            "fresh_query_evaluations": sum(row["fresh_queries"] for row in candidate_rows),
            "touched_selected_path_evaluations": sum(
                row["queries_with_touched_selected_path"] for row in candidate_rows
            ),
            "score_change_evaluations": sum(
                row["queries_with_any_score_change"] for row in candidate_rows
            ),
            "top10_order_changes": sum(
                row["queries_with_top10_order_change"] for row in candidate_rows
            ),
            "top10_membership_changes": sum(
                row["queries_with_top10_membership_change"] for row in candidate_rows
            ),
            "max_abs_score_delta": max(
                row["max_abs_score_delta"] for row in candidate_rows
            ),
            "max_delta_to_boundary_gap": max(
                (
                    row["max_delta_to_boundary_gap"]
                    for row in candidate_rows
                    if row["max_delta_to_boundary_gap"] is not None
                ),
                default=None,
            ),
        },
    }
    output["diagnostic_sha256"] = canonical_sha256(output)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(output["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
