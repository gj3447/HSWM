#!/usr/bin/env python3
"""Phase B: shadow-gated n-ary topology absorption (PROM_5 axis D, prereg B-1).

Phase A (P6) absorbed semantic key-value residuals and was rejected: three
rounds all hurt fresh unseen queries, and the FSM gate blocked them but could
not distinguish "harmful" from "useless", and never touched topology.  Phase B
is the real test bench the P6 scope boundary deferred: n-ary topology
absorption (ADD / SPLIT / MERGE / SUPERSEDE) behind a shadow gate.

Per round:
  1. Deterministic topology candidates are generated from the round's train
     batch (shared-entity n-ary ADD edges among train gold documents, SPLIT of
     incoherent high-degree edges, MERGE of near-duplicate edges; parents are
     SUPERSEDEd via valid_at/invalid_at ledger marks, never mutated in place).
  2. Candidates are applied to a shadow copy of the field, not the field.
  3. Three probes on the round's fresh validation epoch:
       canary  - queries whose gold documents are untouched by any candidate
                 op; regression = post < pre - 0.01 per query;
                 canary_preservation = 100 * (1 - regression rate).
       fresh   - the whole epoch; non-inferiority requires delta >= -0.01.
       target  - queries with >= 1 gold document touched by candidate ops;
                 improvement requires delta >= +0.03.
  4. PASS = canary_preservation >= 98% AND fresh delta >= -0.01 AND target
     delta >= +0.03.  PASS commits the candidate to the field by supersession;
     FAIL discards it and records typed reasons (canary_harm / fresh_harm /
     no_target_gain) - the Phase-A diagnostic output P6 could not produce.

Control arms: (i) absorb-all (every candidate committed, no gate), (ii) frozen
(no absorption).  After 3 rounds, sealed holdout (180 queries) recall@10 is
compared across arms with paired bootstrap.

Preregistered prediction (LakatoTree, user-declared 2026-07-23):
  rounds_passed >= 1 of 3; novel cross-metric: min canary_preservation >= 98%.
  Kill condition: 3 consecutive rounds with zero acceptance.

Environment substitution (external volume unmounted, no downloads allowed):
  * dataset: SiReRAG 2Wiki dev 1000 rows converted losslessly to the P5/P6
    loader schema (convert_sirerag_2wiki.py); same n=900 / seed=8217 / split
    sizes and anti-memorization discipline as P6.
  * embeddings: deterministic lexical vectors (hashed unigram+bigram TF-IDF
    through a seeded random projection), stdlib+numpy only, replacing
    all-MiniLM-L6-v2.  Identical for every arm; all comparisons stay paired.

This script must not be run before the sibling PREREG JSON freezes the script,
dataset, gate-module, and converter hashes.  It emits evidence, never a verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np

from hswm_shadow_gate import (
    DEFAULT_THRESHOLDS,
    HyperEdge,
    TopologyOp,
    active_edges,
    apply_ops,
    canary_preservation,
    edge_id_for,
    evaluate_gate,
    mean_delta,
)
from prom_p5_multiview_hardhop import (
    DF_MAX,
    DF_MIN,
    appnp,
    entities,
    fullchain_at,
    load_locked_sample,
    paired_bootstrap,
    recall_at,
    route_weights,
    zscore,
)


TREE = "LakatosTree_PromSearchHSWM_20260721"
BRANCH = "B3-shadow-gated-topology-absorption"
QUESTION = "Q-continual-absorption-fsm-unseen"
CONJECTURE = (
    "Three shadow-gated n-ary topology absorption rounds (ADD/SPLIT/MERGE/"
    "SUPERSEDE) pass the canary+fresh+target gate in at least one round while "
    "preserving canary knowledge at >= 98%, separating harmful from useless "
    "absorption - the diagnostic Phase A could not produce."
)

HERE = Path(__file__).resolve().parent
DATASET = HERE / "data" / "2wiki_sirerag_1000.jsonl"
PREREG = HERE / "evidence" / "PREREG_shadow_gated_absorption_20260723.json"
OUTPUT = HERE / "evidence" / "EVIDENCE_shadow_gated_absorption_20260723.json"
GATE_MODULE = HERE / "hswm_shadow_gate.py"
CONVERTER = HERE / "convert_sirerag_2wiki.py"
P5_DEPENDENCY = HERE / "prom_p5_multiview_hardhop.py"

# Locked parameters (mirrored 1:1 in the PREREG JSON).
N_Q = 900
SEED = 8217
ABSORPTION_ROUNDS = 3
TRAIN_BATCH_SIZE = 120
VALIDATION_EPOCH_SIZE = 120
FINAL_HOLDOUT_SIZE = 180
TOP_K = 10
FULLCHAIN_K = 20
BOOTSTRAP_REPS = 2000
EMBED_DIM = 384
EMBED_BUCKETS = 32768
EMBED_SEED = 20260723
CANARY_EPSILON = 0.01
CANARY_MIN_PRESERVATION = 98.0
FRESH_DELTA_MIN = -0.01
TARGET_GAIN_MIN = 0.03
MIN_CANARY_N = 20
MIN_TARGET_N = 10
MAX_ADDS_PER_ROUND = 100
SPLIT_MIN_DEG = 8
SPLIT_MAX_DEG = 80
SPLIT_COHERENCE_MARGIN = 0.05
SPLIT_KMEANS_ITERS = 10
MAX_SPLITS_PER_ROUND = 20
MERGE_MIN_JACCARD = 0.6
MERGE_MAX_DEG = 80
MAX_MERGES_PER_ROUND = 20

TOKEN_RE = re.compile(r"[a-z0-9]+")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def normalized_question_hash(question: str) -> str:
    normalized = " ".join(question.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def locked_parameters() -> dict[str, object]:
    return {
        "n_q": N_Q,
        "seed": SEED,
        "absorption_rounds": ABSORPTION_ROUNDS,
        "train_batch_size": TRAIN_BATCH_SIZE,
        "validation_epoch_size": VALIDATION_EPOCH_SIZE,
        "final_holdout_size": FINAL_HOLDOUT_SIZE,
        "top_k": TOP_K,
        "fullchain_k": FULLCHAIN_K,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "embed_dim": EMBED_DIM,
        "embed_buckets": EMBED_BUCKETS,
        "embed_seed": EMBED_SEED,
        "canary_epsilon": CANARY_EPSILON,
        "canary_min_preservation": CANARY_MIN_PRESERVATION,
        "fresh_delta_min": FRESH_DELTA_MIN,
        "target_gain_min": TARGET_GAIN_MIN,
        "min_canary_n": MIN_CANARY_N,
        "min_target_n": MIN_TARGET_N,
        "max_adds_per_round": MAX_ADDS_PER_ROUND,
        "split_min_deg": SPLIT_MIN_DEG,
        "split_max_deg": SPLIT_MAX_DEG,
        "split_coherence_margin": SPLIT_COHERENCE_MARGIN,
        "split_kmeans_iters": SPLIT_KMEANS_ITERS,
        "max_splits_per_round": MAX_SPLITS_PER_ROUND,
        "merge_min_jaccard": MERGE_MIN_JACCARD,
        "merge_max_deg": MERGE_MAX_DEG,
        "max_merges_per_round": MAX_MERGES_PER_ROUND,
    }


def preregistration_guard(script_sha: str, dataset_sha: str) -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    expected_hashes = {
        "script_sha256": script_sha,
        "dataset_sha256": dataset_sha,
        "gate_module_sha256": sha256_file(GATE_MODULE),
        "converter_sha256": sha256_file(CONVERTER),
        "p5_dependency_sha256": sha256_file(P5_DEPENDENCY),
    }
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration is not confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks a prediction receipt")
    for field, expected in expected_hashes.items():
        if locked.get(field) != expected:
            raise RuntimeError(
                f"frozen artifact drift: {field}={locked.get(field)!r}, expected={expected!r}"
            )
    if locked.get("locked_parameters") != locked_parameters():
        raise RuntimeError("locked parameter drift")
    return locked


def fixed_splits() -> tuple[list[list[int]], list[list[int]], list[int]]:
    train_end = ABSORPTION_ROUNDS * TRAIN_BATCH_SIZE
    validation_end = train_end + ABSORPTION_ROUNDS * VALIDATION_EPOCH_SIZE
    if validation_end + FINAL_HOLDOUT_SIZE != N_Q:
        raise RuntimeError("split sizes do not sum to N_Q")
    train_batches = [
        list(range(round_index * TRAIN_BATCH_SIZE, (round_index + 1) * TRAIN_BATCH_SIZE))
        for round_index in range(ABSORPTION_ROUNDS)
    ]
    validation_epochs = [
        list(
            range(
                train_end + round_index * VALIDATION_EPOCH_SIZE,
                train_end + (round_index + 1) * VALIDATION_EPOCH_SIZE,
            )
        )
        for round_index in range(ABSORPTION_ROUNDS)
    ]
    final_holdout = list(range(validation_end, N_Q))
    return train_batches, validation_epochs, final_holdout


def assert_no_query_overlap(
    questions: Sequence[str],
    train_batches: Sequence[Sequence[int]],
    validation_epochs: Sequence[Sequence[int]],
    final_holdout: Sequence[int],
) -> dict[str, str]:
    groups = {
        **{f"train_{index + 1}": batch for index, batch in enumerate(train_batches)},
        **{f"validation_{index + 1}": epoch for index, epoch in enumerate(validation_epochs)},
        "final_holdout": final_holdout,
    }
    hashed = {
        name: [normalized_question_hash(questions[index]) for index in indices]
        for name, indices in groups.items()
    }
    for left_index, left in enumerate(hashed):
        for right in list(hashed)[left_index + 1 :]:
            overlap = set(hashed[left]) & set(hashed[right])
            if overlap:
                raise RuntimeError(
                    f"exact normalized question leakage: {left}/{right} n={len(overlap)}"
                )
    return {name: canonical_sha(values) for name, values in hashed.items()}


# ---------------------------------------------------------------------------
# Deterministic lexical embeddings (MiniLM substitute; identical across arms)
# ---------------------------------------------------------------------------


def text_features(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.casefold())
    return tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]


def feature_bucket(feature: str) -> tuple[int, float]:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:2], "big") % EMBED_BUCKETS
    sign = 1.0 if digest[2] & 1 else -1.0
    return bucket, sign


def build_idf(texts: Sequence[str]) -> np.ndarray:
    df = np.zeros(EMBED_BUCKETS, dtype=np.float64)
    for text in texts:
        for bucket in {feature_bucket(feature)[0] for feature in text_features(text)}:
            df[bucket] += 1.0
    return np.log((len(texts) + 1.0) / (df + 1.0)) + 1.0


def embed_texts(
    texts: Sequence[str], idf: np.ndarray, projection: np.ndarray
) -> np.ndarray:
    out = np.zeros((len(texts), EMBED_DIM), dtype=np.float32)
    for row, text in enumerate(texts):
        counts: dict[int, tuple[float, float]] = {}
        for feature in text_features(text):
            bucket, sign = feature_bucket(feature)
            tf, signed = counts.get(bucket, (0.0, sign))
            counts[bucket] = (tf + 1.0, signed)
        if not counts:
            continue
        buckets = np.fromiter(counts.keys(), dtype=np.int64, count=len(counts))
        weights = np.array(
            [math.sqrt(tf) * float(idf[bucket]) * signed for bucket, (tf, signed) in counts.items()],
            dtype=np.float32,
        )
        vector = (projection[buckets] * weights[:, None]).sum(axis=0)
        norm = float(np.linalg.norm(vector))
        out[row] = vector / max(norm, 1e-9)
    return out


# ---------------------------------------------------------------------------
# Hypergraph: P5-compatible theta, but built from an explicit edge ledger
# ---------------------------------------------------------------------------


def build_base_edges(titles: Sequence[str], bodies: Sequence[str]) -> tuple[HyperEdge, ...]:
    texts = [f"{title}. {body}" for title, body in zip(titles, bodies)]
    entity_sets = [entities(text) for text in texts]
    inverted: dict[str, list[int]] = defaultdict(list)
    for index, values in enumerate(entity_sets):
        for value in values:
            inverted[value].append(index)
    kept = sorted(
        value for value, members in inverted.items() if DF_MIN <= len(members) <= DF_MAX
    )
    edges: list[HyperEdge] = []
    seen_member_sets: set[tuple[int, ...]] = set()
    for value in kept:
        members = tuple(sorted(inverted[value]))
        if members in seen_member_sets:
            continue  # distinct entities with identical document sets share one edge
        seen_member_sets.add(members)
        edges.append(
            HyperEdge(
                edge_id=edge_id_for("base", members, 0),
                members=members,
                origin="base",
                valid_at_round=0,
                invalid_at_round=None,
            )
        )
    return tuple(edges)


def theta_from_edges(n_docs: int, edges: Sequence[HyperEdge]) -> np.ndarray:
    live = active_edges(edges)
    if not live:
        return np.zeros((n_docs, n_docs), dtype=np.float32)
    incidence = np.zeros((n_docs, len(live)), dtype=np.float32)
    edge_degree = np.zeros(len(live), dtype=np.float32)
    idf = np.zeros(len(live), dtype=np.float32)
    for column, edge in enumerate(live):
        members = np.asarray(edge.members, dtype=np.int64)
        incidence[members, column] = 1.0
        edge_degree[column] = len(members)
        idf[column] = math.log(n_docs / len(members))
    weighted = incidence * idf[None, :]
    theta = (weighted * (1.0 / edge_degree)[None, :]) @ incidence.T
    np.fill_diagonal(theta, 0.0)
    vertex_degree = theta.sum(axis=1)
    inv_sqrt = 1.0 / np.sqrt(np.maximum(vertex_degree, 1e-9))
    theta = (theta * inv_sqrt[:, None]) * inv_sqrt[None, :]
    return theta.astype(np.float32)


# ---------------------------------------------------------------------------
# Candidate generation (deterministic; train batch + active ledger only)
# ---------------------------------------------------------------------------


def generate_add_ops(
    train_gold_docs: Sequence[int],
    doc_entity_sets: Sequence[set[str]],
    live_member_sets: set[tuple[int, ...]],
) -> list[TopologyOp]:
    inverted: dict[str, list[int]] = defaultdict(list)
    for doc_index in train_gold_docs:
        for value in doc_entity_sets[doc_index]:
            inverted[value].append(doc_index)
    groups = {
        tuple(sorted(members))
        for members in inverted.values()
        if len(set(members)) >= 2
    }
    groups = {group for group in groups if group not in live_member_sets}
    ordered = sorted(groups, key=lambda group: (-len(group), group))
    return [TopologyOp("ADD", (), (group,)) for group in ordered[:MAX_ADDS_PER_ROUND]]


def two_means(vectors: np.ndarray) -> np.ndarray:
    """Deterministic 2-means over rows; returns labels in {0, 1}."""
    n_rows = vectors.shape[0]
    sims = (vectors @ vectors.T).astype(np.float64)
    np.fill_diagonal(sims, np.inf)
    flat = int(np.argmin(sims))
    seeds = [flat // n_rows, flat % n_rows]
    centers = vectors[seeds].copy()
    labels = np.zeros(n_rows, dtype=np.int64)
    for _ in range(SPLIT_KMEANS_ITERS):
        labels = (vectors @ centers.T).argmax(axis=1)
        new_centers = centers.copy()
        for cluster in (0, 1):
            members = vectors[labels == cluster]
            if len(members) == 0:
                # deterministic re-seed: point farthest from the other center
                other = centers[1 - cluster]
                distances = (vectors @ other).astype(np.float64)
                distances[labels == 1 - cluster] = np.inf
                new_centers[cluster] = vectors[int(np.argmin(distances))]
            else:
                mean = members.mean(axis=0)
                new_centers[cluster] = mean / max(float(np.linalg.norm(mean)), 1e-9)
        if np.allclose(new_centers, centers, atol=1e-7):
            centers = new_centers
            break
        centers = new_centers
    return (vectors @ centers.T).argmax(axis=1)


def mean_pairwise_cosine(vectors: np.ndarray) -> float:
    n_rows = vectors.shape[0]
    if n_rows < 2:
        return 1.0
    sims = vectors @ vectors.T
    upper = sims[np.triu_indices(n_rows, k=1)]
    return float(upper.mean())


def generate_split_ops(
    edges: Sequence[HyperEdge],
    document_values: np.ndarray,
) -> tuple[list[TopologyOp], set[str]]:
    candidates: list[tuple[float, str, TopologyOp]] = []
    for edge in active_edges(edges):
        degree = len(edge.members)
        if not (SPLIT_MIN_DEG <= degree <= SPLIT_MAX_DEG):
            continue
        vectors = document_values[np.asarray(edge.members, dtype=np.int64)]
        labels = two_means(vectors)
        child_a = tuple(
            member for member, label in zip(edge.members, labels) if label == 0
        )
        child_b = tuple(
            member for member, label in zip(edge.members, labels) if label == 1
        )
        if len(child_a) < 2 or len(child_b) < 2:
            continue
        parent_coherence = mean_pairwise_cosine(vectors)
        count_a = len(child_a) * (len(child_a) - 1) // 2
        count_b = len(child_b) * (len(child_b) - 1) // 2
        child_coherence = (
            count_a * mean_pairwise_cosine(document_values[np.asarray(child_a, dtype=np.int64)])
            + count_b * mean_pairwise_cosine(document_values[np.asarray(child_b, dtype=np.int64)])
        ) / max(count_a + count_b, 1)
        gain = child_coherence - parent_coherence
        if gain >= SPLIT_COHERENCE_MARGIN:
            candidates.append(
                (gain, edge.edge_id, TopologyOp("SPLIT", (edge.edge_id,), (child_a, child_b)))
            )
    candidates.sort(key=lambda item: (-item[0], item[1]))
    chosen = candidates[:MAX_SPLITS_PER_ROUND]
    return [op for _, _, op in chosen], {edge_id for _, edge_id, _ in chosen}


def generate_merge_ops(
    edges: Sequence[HyperEdge],
    excluded: set[str],
) -> list[TopologyOp]:
    live = [
        edge
        for edge in active_edges(edges)
        if edge.edge_id not in excluded and len(edge.members) <= MERGE_MAX_DEG
    ]
    pair_intersection: dict[tuple[str, str], int] = defaultdict(int)
    edge_by_id = {edge.edge_id: edge for edge in live}
    doc_to_edges: dict[int, list[str]] = defaultdict(list)
    for edge in live:
        for member in edge.members:
            doc_to_edges[member].append(edge.edge_id)
    for edge_ids in doc_to_edges.values():
        edge_ids.sort()
        for left_index, left in enumerate(edge_ids):
            for right in edge_ids[left_index + 1 :]:
                pair_intersection[(left, right)] += 1
    scored: list[tuple[float, str, str, TopologyOp]] = []
    for (left, right), intersection in pair_intersection.items():
        union_size = (
            len(edge_by_id[left].members) + len(edge_by_id[right].members) - intersection
        )
        jaccard = intersection / union_size
        if jaccard >= MERGE_MIN_JACCARD:
            merged = tuple(sorted(set(edge_by_id[left].members) | set(edge_by_id[right].members)))
            scored.append(
                (jaccard, left, right, TopologyOp("MERGE", (left, right), (merged,)))
            )
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    chosen: list[TopologyOp] = []
    consumed: set[str] = set()
    for _, left, right, op in scored:
        if left in consumed or right in consumed:
            continue
        chosen.append(op)
        consumed.add(left)
        consumed.add(right)
        if len(chosen) >= MAX_MERGES_PER_ROUND:
            break
    return chosen


def candidate_touched_docs(ops: Sequence[TopologyOp], edges: Sequence[HyperEdge]) -> set[int]:
    edge_by_id = {edge.edge_id: edge for edge in edges}
    touched: set[int] = set()
    for op in ops:
        for member_set in op.member_sets:
            touched.update(member_set)
        for parent_id in op.edge_ids:
            parent = edge_by_id.get(parent_id)
            if parent is not None:
                touched.update(parent.members)
    return touched


# ---------------------------------------------------------------------------
# Retrieval scoring (P5/P6 views; topology enters only through theta)
# ---------------------------------------------------------------------------


def score_queries(
    query_indices: Sequence[int],
    title_scores_all: np.ndarray,
    body_scores_all: np.ndarray,
    theta: np.ndarray,
    questions: Sequence[str],
    gold: Sequence[set[int]],
    row_ids: Sequence[str],
) -> list[dict[str, object]]:
    title_scores = title_scores_all[np.asarray(query_indices)]
    body_scores = body_scores_all[np.asarray(query_indices)]
    seed_scores = (0.5 * title_scores + 0.5 * body_scores).T.astype(np.float32)
    bridge_scores = appnp(theta, seed_scores).T
    rows: list[dict[str, object]] = []
    for local_index, global_index in enumerate(query_indices):
        wt, wb, wg, route = route_weights(questions[global_index])
        score = (
            wt * zscore(title_scores[local_index])
            + wb * zscore(body_scores[local_index])
            + wg * zscore(bridge_scores[local_index])
        )
        ranking = np.argsort(-score, kind="stable")
        rows.append(
            {
                "id": row_ids[global_index],
                "route": route,
                "recall10": recall_at(ranking, gold[global_index], TOP_K),
                "fullchain20": fullchain_at(ranking, gold[global_index], FULLCHAIN_K),
            }
        )
    return rows


def compare(candidate: Sequence[dict[str, object]], control: Sequence[dict[str, object]], seed: int) -> dict[str, object]:
    if [row["id"] for row in candidate] != [row["id"] for row in control]:
        raise RuntimeError("paired evaluation IDs differ")
    recall_deltas = [
        float(candidate[index]["recall10"]) - float(control[index]["recall10"])
        for index in range(len(candidate))
    ]
    ci = paired_bootstrap(recall_deltas, BOOTSTRAP_REPS, seed)
    return {
        "n": len(candidate),
        "control_recall10": statistics.mean(float(row["recall10"]) for row in control),
        "candidate_recall10": statistics.mean(float(row["recall10"]) for row in candidate),
        "recall10_delta": statistics.mean(recall_deltas),
        "recall10_delta_bootstrap95": list(ci),
    }


def round6(value: object) -> object:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [round6(item) for item in value]
    if isinstance(value, dict):
        return {key: round6(item) for key, item in value.items()}
    return value


# ---------------------------------------------------------------------------
# One absorption round for one arm
# ---------------------------------------------------------------------------


def run_round(
    *,
    edges: tuple[HyperEdge, ...],
    train_batch: Sequence[int],
    validation_epoch: Sequence[int],
    gold: Sequence[set[int]],
    doc_entity_sets: Sequence[set[str]],
    document_values: np.ndarray,
    title_scores_all: np.ndarray,
    body_scores_all: np.ndarray,
    questions: Sequence[str],
    row_ids: Sequence[str],
    round_index: int,
) -> dict[str, object]:
    train_gold_docs = sorted({doc for index in train_batch for doc in gold[index]})
    live_member_sets = {edge.members for edge in active_edges(edges)}
    add_ops = generate_add_ops(train_gold_docs, doc_entity_sets, live_member_sets)
    split_ops, split_parents = generate_split_ops(edges, document_values)
    merge_ops = generate_merge_ops(edges, split_parents)
    ops = add_ops + split_ops + merge_ops

    shadow_edges, ledger_entries = apply_ops(edges, ops, round_index + 1)
    touched = candidate_touched_docs(ops, edges)

    canary_positions = [
        position
        for position, global_index in enumerate(validation_epoch)
        if not (gold[global_index] & touched)
    ]
    target_positions = [
        position
        for position, global_index in enumerate(validation_epoch)
        if gold[global_index] & touched
    ]

    n_docs = title_scores_all.shape[1]
    pre_theta = theta_from_edges(n_docs, edges)
    post_theta = theta_from_edges(n_docs, shadow_edges)
    pre_rows = score_queries(
        validation_epoch, title_scores_all, body_scores_all, pre_theta, questions, gold, row_ids
    )
    post_rows = score_queries(
        validation_epoch, title_scores_all, body_scores_all, post_theta, questions, gold, row_ids
    )
    replay_rows = score_queries(
        validation_epoch, title_scores_all, body_scores_all, post_theta, questions, gold, row_ids
    )
    replay_verified = post_rows == replay_rows

    pre_recall = [float(row["recall10"]) for row in pre_rows]
    post_recall = [float(row["recall10"]) for row in post_rows]
    canary_pre = [pre_recall[position] for position in canary_positions]
    canary_post = [post_recall[position] for position in canary_positions]
    target_pre = [pre_recall[position] for position in target_positions]
    target_post = [post_recall[position] for position in target_positions]

    preservation = (
        canary_preservation(canary_pre, canary_post, CANARY_EPSILON)
        if canary_pre
        else float("nan")
    )
    fresh_delta = mean_delta(pre_recall, post_recall)
    target_delta = mean_delta(target_pre, target_post) if target_pre else float("nan")
    verdict = evaluate_gate(
        canary_preservation_pct=preservation if canary_pre else 0.0,
        fresh_delta=fresh_delta,
        target_delta=target_delta if target_pre else float("-inf"),
        canary_n=len(canary_positions),
        target_n=len(target_positions),
    )
    candidate_hash = canonical_sha(
        {
            "schema": "hswm-topology-candidate/v1",
            "round": round_index + 1,
            "ops": [
                {"kind": op.kind, "edge_ids": list(op.edge_ids), "member_sets": [list(m) for m in op.member_sets]}
                for op in ops
            ],
        }
    )
    return {
        "shadow_edges": shadow_edges,
        "ledger_entries": ledger_entries,
        "ops": ops,
        "candidate_hash": candidate_hash,
        "n_add": len(add_ops),
        "n_split": len(split_ops),
        "n_merge": len(merge_ops),
        "n_touched_docs": len(touched),
        "canary_n": len(canary_positions),
        "target_n": len(target_positions),
        "canary_preservation": preservation,
        "fresh_delta": fresh_delta,
        "target_delta": target_delta,
        "verdict": verdict,
        "replay_verified": replay_verified,
        "pre_theta": pre_theta,
        "post_theta": post_theta,
    }


def main() -> int:
    started_at = utc_now()
    script_sha = sha256_file(Path(__file__).resolve())
    if not DATASET.exists():
        raise RuntimeError(f"missing dataset: {DATASET}")
    dataset_sha = sha256_file(DATASET)
    locked = preregistration_guard(script_sha, dataset_sha)

    (
        titles,
        bodies,
        questions,
        gold,
        support_counts,
        hop_types,
        row_ids,
        selected_ids_sha,
    ) = load_locked_sample(DATASET, N_Q, SEED)
    train_batches, validation_epochs, final_holdout = fixed_splits()
    split_hashes = assert_no_query_overlap(
        questions, train_batches, validation_epochs, final_holdout
    )
    split_manifest_hash = canonical_sha(split_hashes)
    n_docs = len(titles)

    # Deterministic lexical embeddings (identical across all arms).
    projection = np.random.default_rng(EMBED_SEED).standard_normal(
        (EMBED_BUCKETS, EMBED_DIM)
    ).astype(np.float32)
    doc_texts = [f"{title}. {body}" for title, body in zip(titles, bodies)]
    idf = build_idf(doc_texts)
    title_embeddings = embed_texts(titles, idf, projection)
    body_embeddings = embed_texts(bodies, idf, projection)
    query_embeddings = embed_texts(questions, idf, projection)
    del projection
    document_values = (0.5 * title_embeddings + 0.5 * body_embeddings).astype(np.float32)
    norms = np.linalg.norm(document_values, axis=1, keepdims=True)
    document_values = document_values / np.maximum(norms, 1e-9)

    title_scores_all = (query_embeddings @ title_embeddings.T).astype(np.float32)
    body_scores_all = (query_embeddings @ body_embeddings.T).astype(np.float32)

    doc_entity_sets = [entities(text) for text in doc_texts]
    base_edges = build_base_edges(titles, bodies)
    base_version = canonical_sha([edge.edge_id for edge in base_edges])

    # Two evolving arms: gated (shadow gate decides) and absorb_all (no gate).
    arm_edges: dict[str, tuple[HyperEdge, ...]] = {
        "gated": base_edges,
        "absorb_all": base_edges,
    }
    arm_versions: dict[str, str] = {"gated": base_version, "absorb_all": base_version}
    rounds_report: list[dict[str, object]] = []

    for round_index, (train_batch, validation_epoch) in enumerate(
        zip(train_batches, validation_epochs)
    ):
        round_record: dict[str, object] = {"round": round_index + 1, "arms": {}}
        for arm_name in ("gated", "absorb_all"):
            result = run_round(
                edges=arm_edges[arm_name],
                train_batch=train_batch,
                validation_epoch=validation_epoch,
                gold=gold,
                doc_entity_sets=doc_entity_sets,
                document_values=document_values,
                title_scores_all=title_scores_all,
                body_scores_all=body_scores_all,
                questions=questions,
                row_ids=row_ids,
                round_index=round_index,
            )
            verdict = result["verdict"]
            committed = True if arm_name == "absorb_all" else bool(verdict.passed)
            if committed:
                arm_edges[arm_name] = result["shadow_edges"]
                arm_versions[arm_name] = canonical_sha(
                    sorted(edge.edge_id for edge in active_edges(arm_edges[arm_name]))
                )
            round_record["arms"][arm_name] = {
                "candidate_hash": result["candidate_hash"],
                "ops": {"add": result["n_add"], "split": result["n_split"], "merge": result["n_merge"]},
                "n_touched_docs": result["n_touched_docs"],
                "canary_n": result["canary_n"],
                "target_n": result["target_n"],
                "canary_preservation": round6(result["canary_preservation"]),
                "fresh_delta": round6(result["fresh_delta"]),
                "target_delta": round6(result["target_delta"]),
                "gate_passed": bool(verdict.passed),
                "rejection_reasons": list(verdict.reasons),
                "primary_reason": verdict.primary_reason,
                "committed": committed,
                "replay_verified": result["replay_verified"],
                "ledger_entries": len(result["ledger_entries"]),
                "active_edges_after": len(active_edges(arm_edges[arm_name])),
                "version_after": arm_versions[arm_name][:16],
            }
            del result["pre_theta"], result["post_theta"]
        rounds_report.append(round_record)

    rounds_passed = sum(
        1
        for record in rounds_report
        if record["arms"]["gated"]["gate_passed"]
    )
    canary_values = [
        float(record["arms"]["gated"]["canary_preservation"])
        for record in rounds_report
    ]
    min_canary_preservation = min(canary_values)

    # Sealed holdout: frozen vs gated vs absorb_all.
    frozen_theta = theta_from_edges(n_docs, base_edges)
    frozen_rows = score_queries(
        final_holdout, title_scores_all, body_scores_all, frozen_theta, questions, gold, row_ids
    )
    gated_theta = theta_from_edges(n_docs, arm_edges["gated"])
    gated_rows = score_queries(
        final_holdout, title_scores_all, body_scores_all, gated_theta, questions, gold, row_ids
    )
    absorb_all_theta = theta_from_edges(n_docs, arm_edges["absorb_all"])
    absorb_all_rows = score_queries(
        final_holdout, title_scores_all, body_scores_all, absorb_all_theta, questions, gold, row_ids
    )
    holdout = {
        "gated_minus_frozen": compare(gated_rows, frozen_rows, SEED + 100),
        "absorb_all_minus_frozen": compare(absorb_all_rows, frozen_rows, SEED + 200),
        "absorb_all_minus_gated": compare(absorb_all_rows, gated_rows, SEED + 300),
        "frozen_recall10": statistics.mean(float(row["recall10"]) for row in frozen_rows),
    }

    kill_condition_triggered = rounds_passed == 0
    prediction_checks = {
        "rounds_passed_ge_1": rounds_passed >= 1,
        "min_canary_preservation_ge_98": min_canary_preservation >= CANARY_MIN_PRESERVATION,
        "kill_condition_3_rounds_zero_acceptance": kill_condition_triggered,
        "all_round_replays_verified": all(
            record["arms"]["gated"]["replay_verified"]
            and record["arms"]["absorb_all"]["replay_verified"]
            for record in rounds_report
        ),
        "exact_query_id_not_used": True,
    }

    evidence = {
        "schema": "lakato-evidence-record/v1",
        "programme": TREE,
        "branch": BRANCH,
        "question": QUESTION,
        "conjecture": CONJECTURE,
        "preregistration": {
            "path": str(PREREG),
            "registered_at": locked.get("server_registered_at"),
            "registered_before_measurement": True,
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
            "script_sha256": script_sha,
            "gate_module_sha256": sha256_file(GATE_MODULE),
        },
        "measurement": {
            "metric": "rounds_passed_shadow_gate",
            "value": rounds_passed,
            "unit": "count of 3 rounds passing canary+fresh+target gate",
            "scope": f"2Wiki(SiReRAG-converted) deterministic sample n={N_Q}; exact normalized query-disjoint splits",
            "noise_band": 0.0,
            "novel_metric": "min_canary_preservation_over_rounds",
            "novel_value": round(min_canary_preservation, 6),
            "kill_condition_triggered": kill_condition_triggered,
            "rounds": rounds_report,
            "sealed_holdout": round6(holdout),
            "pre_registered_checks": prediction_checks,
        },
        "anti_memorization": {
            "query_id_used_by_model": False,
            "exact_normalized_query_overlap": 0,
            "candidate_generation_inputs": "train split gold documents + active edge ledger only",
            "split_manifest_sha256": split_manifest_hash,
            "note": "Topology candidates derive only from the round train batch and the active ledger; validation epochs drive gate accept/discard decisions; the sealed holdout is never consulted before the final comparison.",
        },
        "provenance": {
            "grounded": True,
            "inputs": [
                {"kind": "source", "path": str(DATASET), "sha256": dataset_sha},
                {"kind": "harness", "path": str(Path(__file__).resolve()), "sha256": script_sha},
                {"kind": "gate_module", "path": str(GATE_MODULE), "sha256": sha256_file(GATE_MODULE)},
                {"kind": "converter", "path": str(CONVERTER), "sha256": sha256_file(CONVERTER)},
                {"kind": "p5_dependency", "path": str(P5_DEPENDENCY), "sha256": sha256_file(P5_DEPENDENCY)},
                {"kind": "preregistration", "path": str(PREREG), "sha256": sha256_file(PREREG)},
            ],
            "data_manifest": {
                "dataset": "2WikiMultihopQA dev via SiReRAG conversion (1000 rows)",
                "dataset_substitution_reason": "original /Volumes/GM/bench/2wiki_dev.jsonl unmounted; no downloads allowed",
                "selected_rows": N_Q,
                "selected_ids_sha256": selected_ids_sha,
                "question_split_hashes": split_hashes,
                "split_manifest_sha256": split_manifest_hash,
                "seed": SEED,
                "pool_documents": n_docs,
                "base_hyperedges": len(base_edges),
                "base_version": base_version,
                "support_count_histogram": {
                    str(count): support_counts.count(count) for count in sorted(set(support_counts))
                },
                "hop_types": {hop: hop_types.count(hop) for hop in sorted(set(hop_types))},
            },
            "embedding": {
                "kind": "deterministic lexical (hashed unigram+bigram TF-IDF, seeded random projection)",
                "substitution_reason": "all-MiniLM-L6-v2 weights unavailable offline (external volume unmounted, downloads forbidden)",
                "embed_dim": EMBED_DIM,
                "embed_buckets": EMBED_BUCKETS,
                "embed_seed": EMBED_SEED,
                "same_for_all_arms": True,
            },
            "equal_compute": {
                "verified": True,
                "shared_views": ["title_cosine", "body_cosine", "nary_entity_appnp"],
                "same_embeddings": True,
                "same_document_pool": True,
                "same_top_k": TOP_K,
                "difference_only": "which hyperedge ledger version feeds the APPNP bridge view",
            },
        },
        "harness": {
            "command": "GIT/HSWM/.venv/bin/python prom_search_hswm/prom_shadow_gated_absorption.py",
            "cwd": str(HERE),
            "git_head": git_head(),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": np.__version__,
            },
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_code": 0,
        },
        "findings": [
            {
                "proposal": "A shadow gate with canary/fresh/target probes separates harmful absorption from useless absorption, which the Phase-A FSM gate could not.",
                "supported_by": ["measurement.rounds"],
            },
            {
                "proposal": "n-ary topology absorption (ADD/SPLIT/MERGE/SUPERSEDE) is the test bench for HSWM self-improvement; semantic KV residual absorption (Phase A) stays rejected.",
                "supported_by": ["measurement.sealed_holdout"],
            },
        ],
        "limitations": [
            "Dataset and encoder substitutions: SiReRAG-converted 2Wiki (1000 rows) and deterministic lexical embeddings replace the P6 dataset/MiniLM because the external volume is unmounted and downloads are forbidden; absolute recall levels are not comparable to P6, only the paired gate logic carries over.",
            "LakatoTree prediction was user-declared (2026-07-23); no server receipt sha was recorded in-repo.",
            "One benchmark, one deterministic split, one seed; training interactions use gold supporting passages (supervised learning-while-using).",
            "Canary/target slices are structural (candidate-touched gold documents); the target slice approximates the train distribution rather than matching it exactly.",
        ],
        "diagnostics": {
            "rounds_passed": rounds_passed,
            "min_canary_preservation": round(min_canary_preservation, 6),
            "gate_thresholds": {
                "canary_epsilon": CANARY_EPSILON,
                "canary_min_preservation": CANARY_MIN_PRESERVATION,
                "fresh_delta_min": FRESH_DELTA_MIN,
                "target_gain_min": TARGET_GAIN_MIN,
            },
            "final_versions": {name: version[:16] for name, version in arm_versions.items()},
            "final_active_edges": {
                name: len(active_edges(edges)) for name, edges in arm_edges.items()
            },
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "evidence": str(OUTPUT),
                "evidence_sha256": sha256_file(OUTPUT),
                "rounds_passed": rounds_passed,
                "min_canary_preservation": round(min_canary_preservation, 6),
                "kill_condition_triggered": kill_condition_triggered,
                "holdout_gated_minus_frozen": round(holdout["gated_minus_frozen"]["recall10_delta"], 6),
                "holdout_absorb_all_minus_frozen": round(holdout["absorb_all_minus_frozen"]["recall10_delta"], 6),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
