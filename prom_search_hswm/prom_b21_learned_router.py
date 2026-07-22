#!/usr/bin/env python3
"""B2.1: conservative learned routing over federated HSWM fields.

This is an independent successor to the frozen B2 harness.  It keeps B2's
paragraph hyperedges, entity vertices, A/B fields, seam classes and score
formula, but compiles all query scores with NumPy.  The only learned state is a
small shared action-value ridge model.  The model sees observable ranking
statistics; query IDs, answers, dataset labels, gold documents and the
cross/in-field stratum are never features.

The important safety rule is executable: when a calibrated lower bound cannot
show that one single field is better than MERGED, the public action is ABSTAIN
and the executed action is MERGED.  ``best_single`` is an evaluation oracle
only and is never a fallback.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import platform
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from prom_b2_crossfield_merge import (  # noqa: E402
    LAM_B,
    LAM_V,
    MODEL_NAME,
    SEED as B2_SEED,
    attach_embeddings as b2_attach_embeddings,
    base_entities,
    build_field as b2_build_field,
    collect_texts as b2_collect_texts,
    compose as b2_compose,
    finding_text,
    merge as b2_merge,
    paragraphs_from_rows as b2_paragraphs_from_rows,
    rank_paragraphs as b2_rank_paragraphs,
    seam_arcs_between as b2_seam_arcs_between,
    sha256_file,
    stratify as b2_stratify,
)

TREE = "LakatosTree_PromSearchHSWM_20260721"
BRANCH = "B2.1r1-query-byte-equivalence-repair"
QUESTION = "Q-b21-learned-router-interference-control"
PREREG = HERE / "evidence" / "PREREG_b21r1_query_byte_repair_20260723.json"
DEFAULT_OUTPUT = HERE / "evidence" / "EVIDENCE_b21_learned_router_20260723.json"

PARTITION_SALTS = ("legacy", "b21-field-v1", "b21-field-v2")
TOP_KS = (5, 10, 20)
SPLIT_SEEDS = (7332, 7333, 7334)
PRIMARY_SALT = "legacy"
PRIMARY_K = 10
PRIMARY_SEED = 7332
RIDGE_LAMBDA = 1.0
CALIBRATION_ALPHA = 0.10
BOOTSTRAP_REPS = 5000
NOISE_BAND = 0.02
MAX_K = max(TOP_KS)
ARMS = ("a", "b", "merged")
ALL_ARMS = (*ARMS, "no_seam")
FROZEN_MODULES = (
    "prom_b2_crossfield_merge.py",
    "hswm_field_algebra.py",
    "hswm_hypergraph.py",
    "hswm_hypergraph_readout.py",
)


@dataclass(frozen=True)
class Paragraph:
    pid: str
    title: str
    body: str
    entities: tuple[str, ...]


@dataclass(frozen=True)
class Query:
    qid: str
    question: str
    gold: tuple[str, ...]
    answer_aliases: tuple[str, ...]


@dataclass
class RidgeModel:
    coef: np.ndarray
    mean: np.ndarray
    scale: np.ndarray
    feature_names: tuple[str, ...]
    ridge_lambda: float

    def predict(self, x: np.ndarray) -> np.ndarray:
        z = (np.asarray(x, dtype=np.float64) - self.mean) / self.scale
        z = np.column_stack([np.ones(len(z)), z])
        return z @ self.coef


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_pid(title: str, body: str) -> str:
    return "p" + hashlib.sha256(f"{title}\0{body}".encode("utf-8")).hexdigest()[:16]


def _answer_aliases(row: dict) -> tuple[str, ...]:
    vals: list[str] = []
    answer = row.get("answer")
    if answer is not None:
        vals.append(str(answer))
    vals.extend(str(x) for x in row.get("answer_aliases", []) if x is not None)
    return tuple(sorted({x.strip() for x in vals if x.strip()}, key=lambda x: (x.casefold(), x)))


def normalize_rows(raw: object, dataset: str) -> tuple[list[Query], dict[str, Paragraph]]:
    """Normalize 2Wiki or MuSiQue without title-only MuSiQue gold lookup."""
    rows = raw.get("rows", []) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError("dataset must be a list or {'rows': [...]} object")
    queries: list[Query] = []
    pool: dict[str, Paragraph] = {}
    for row_no, row in enumerate(rows):
        qid = str(row.get("id", f"row-{row_no}"))
        # Preserve the source bytes used by the frozen B2 scorer.  In particular,
        # three 2Wiki questions end in a space.  Stripping them creates a second
        # embedding-cache key whose different GPU batch can drift at float32 ulp
        # scale even though tokenization and ranked IDs are unchanged.
        question = str(row.get("question", ""))
        if not question.strip():
            continue
        gold: set[str] = set()
        if dataset == "2wiki":
            context = row.get("context", {})
            titles = context.get("title", [])
            sentences = context.get("sentences", [])
            if len(titles) != len(sentences):
                raise ValueError(f"2wiki {qid}: title/sentences length mismatch")
            by_title: dict[str, set[str]] = {}
            for title0, sents in zip(titles, sentences):
                title = str(title0)
                body = " ".join(str(s).strip() for s in sents).strip()
                pid = stable_pid(title, body)
                pool.setdefault(pid, Paragraph(pid, title, body,
                                                tuple(sorted(base_entities(finding_text(title, body))))))
                by_title.setdefault(title.casefold(), set()).add(pid)
            support_titles = row.get("supporting_facts", {}).get("title", [])
            for title0 in support_titles:
                matches = by_title.get(str(title0).casefold(), set())
                if len(matches) != 1:
                    raise ValueError(f"2wiki {qid}: ambiguous/missing support title {title0!r}")
                gold.update(matches)
        elif dataset == "musique":
            paragraphs = row.get("paragraphs", [])
            for p in paragraphs:
                # idx is the authority for deciding which row paragraph is gold;
                # content IDs may still deduplicate the closed retrieval corpus.
                if "idx" not in p:
                    raise ValueError(f"musique {qid}: paragraph missing idx")
                title = str(p.get("title", ""))
                body = str(p.get("paragraph_text", "")).strip()
                pid = stable_pid(title, body)
                pool.setdefault(pid, Paragraph(pid, title, body,
                                                tuple(sorted(base_entities(finding_text(title, body))))))
                if bool(p.get("is_supporting")):
                    gold.add(pid)
        else:
            raise ValueError(f"unknown dataset {dataset!r}")
        if gold:
            queries.append(Query(qid=qid, question=question, gold=tuple(sorted(gold)),
                                 answer_aliases=_answer_aliases(row)))
    if not queries or not pool:
        raise ValueError(f"{dataset}: no usable queries/paragraphs")
    return queries, {pid: pool[pid] for pid in sorted(pool)}


def field_label(title: str, salt: str) -> str:
    payload = title if salt == "legacy" else f"{salt}\0{title}"
    return "A" if int(hashlib.sha256(payload.encode("utf-8")).hexdigest(), 16) % 2 == 0 else "B"


def opaque_entity(name: str) -> str:
    return "entity_" + hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:12]


def privatize_text(text: str, entities: Iterable[str]) -> str:
    out = text
    for entity in sorted(set(entities), key=lambda x: (-len(x), x)):
        out = re.sub(rf"(?<!\w){re.escape(entity)}(?!\w)", opaque_entity(entity),
                     out, flags=re.IGNORECASE)
    return out


def _normalize_matrix(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return x / norms


def directory_manifest(path: Path) -> dict:
    """Content manifest for a local model snapshot, following symlink targets."""
    if not path.is_dir():
        raise RuntimeError(f"model snapshot is not a directory: {path}")
    files = []
    for item in sorted(x for x in path.rglob("*") if x.is_file()):
        files.append({"path": item.relative_to(path).as_posix(),
                      "bytes": item.stat().st_size, "sha256": sha256_file(item)})
    if not files:
        raise RuntimeError(f"model snapshot has no files: {path}")
    blob = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"sha256": hashlib.sha256(blob).hexdigest(), "n_files": len(files),
            "bytes": sum(x["bytes"] for x in files), "files": files}


def _bridge_scores(groups: dict[object, list[int]], edge_cos: np.ndarray) -> np.ndarray:
    """Exact B2 max-other-edge bridge for all queries at once."""
    bridge = np.zeros_like(edge_cos)
    qcols = np.arange(edge_cos.shape[1])
    for indices0 in groups.values():
        indices = np.asarray(sorted(set(indices0)), dtype=np.int64)
        if len(indices) < 2:
            continue
        vals = edge_cos[indices]
        top = np.max(vals, axis=0)
        arg = np.argmax(vals, axis=0)
        second = np.partition(vals, len(indices) - 2, axis=0)[len(indices) - 2]
        candidates = np.broadcast_to(top, vals.shape).copy()
        candidates[arg, qcols] = second
        # Frozen B2 initializes bridge=0 and accepts only strictly larger scores.
        candidates = np.maximum(candidates, 0.0)
        bridge[indices] = np.maximum(bridge[indices], candidates)
    return bridge


def _top_rows(scores: np.ndarray, indices: np.ndarray, edge_ids: Sequence[str], k: int) -> tuple[np.ndarray, np.ndarray]:
    """Stable score-desc/id-asc rankings. edge_ids are globally sorted."""
    local = scores[indices]
    order = np.argsort(-local, axis=0, kind="stable")[:k]
    ranked_indices = indices[order]
    ranked_scores = np.take_along_axis(local, order, axis=0)
    return ranked_indices.T, ranked_scores.T


def compile_scorepack(
    queries: Sequence[Query],
    pool: dict[str, Paragraph],
    embed_fn: Callable[[list[str]], Sequence[Sequence[float]]],
    *,
    dataset: str,
    salt: str,
    private_entities: bool = False,
    top_k: int = MAX_K,
) -> dict:
    """Compile B2-equivalent A/B/MERGED/NO_SEAM rankings with vectorized cosine."""
    if salt not in PARTITION_SALTS:
        raise ValueError(f"unregistered salt {salt}")
    edge_ids = sorted(pool)
    edge_pos = {pid: i for i, pid in enumerate(edge_ids)}
    labels = np.asarray([0 if field_label(pool[pid].title, salt) == "A" else 1
                         for pid in edge_ids], dtype=np.int8)

    vertex_keys: list[tuple[int, str]] = []
    vertex_pos: dict[tuple[int, str], int] = {}
    members: list[list[int]] = []
    groups_field: dict[tuple[int, str], list[int]] = {}
    groups_merged: dict[str, list[int]] = {}
    for edge_i, pid in enumerate(edge_ids):
        field_i = int(labels[edge_i])
        row_members: list[int] = []
        for entity in pool[pid].entities:
            key = (field_i, entity)
            if key not in vertex_pos:
                vertex_pos[key] = len(vertex_keys)
                vertex_keys.append(key)
            row_members.append(vertex_pos[key])
            groups_field.setdefault(key, []).append(edge_i)
            groups_merged.setdefault(entity, []).append(edge_i)
        members.append(row_members)

    edge_texts = [
        privatize_text(finding_text(pool[pid].title, pool[pid].body), pool[pid].entities)
        if private_entities else finding_text(pool[pid].title, pool[pid].body)
        for pid in edge_ids
    ]
    vertex_texts = [opaque_entity(entity) if private_entities else entity
                    for _, entity in vertex_keys]
    query_texts = [
        privatize_text(q.question, base_entities(q.question)) if private_entities else q.question
        for q in queries
    ]
    texts = sorted(set(edge_texts) | set(vertex_texts) | set(query_texts))
    embedded = _normalize_matrix(np.asarray(embed_fn(texts), dtype=np.float64))
    table = {text: embedded[i] for i, text in enumerate(texts)}
    e_mat = np.vstack([table[x] for x in edge_texts])
    v_mat = np.vstack([table[x] for x in vertex_texts]) if vertex_texts else np.empty((0, e_mat.shape[1]))
    q_mat = np.vstack([table[x] for x in query_texts])
    edge_cos = e_mat @ q_mat.T
    vertex_cos = v_mat @ q_mat.T if len(v_mat) else np.empty((0, len(q_mat)))

    v_chan = np.zeros_like(edge_cos)
    for edge_i, vertex_indices in enumerate(members):
        if vertex_indices:
            v_chan[edge_i] = np.max(vertex_cos[vertex_indices], axis=0)
    field_bridge = _bridge_scores(groups_field, edge_cos)
    merged_bridge = _bridge_scores(groups_merged, edge_cos)
    no_seam_scores = edge_cos + LAM_V * v_chan + LAM_B * field_bridge
    merged_scores = edge_cos + LAM_V * v_chan + LAM_B * merged_bridge

    idx_all = np.arange(len(edge_ids), dtype=np.int64)
    idx_a = idx_all[labels == 0]
    idx_b = idx_all[labels == 1]
    if not len(idx_a) or not len(idx_b):
        raise RuntimeError(f"{dataset}/{salt}: empty field")
    ranked: dict[str, tuple[np.ndarray, np.ndarray]] = {
        "a": _top_rows(no_seam_scores, idx_a, edge_ids, top_k),
        "b": _top_rows(no_seam_scores, idx_b, edge_ids, top_k),
        "merged": _top_rows(merged_scores, idx_all, edge_ids, top_k),
        "no_seam": _top_rows(no_seam_scores, idx_all, edge_ids, top_k),
    }

    records = []
    for qi, query in enumerate(queries):
        gold = set(query.gold)
        gold_fields = {"A" if labels[edge_pos[pid]] == 0 else "B" for pid in gold}
        arms = {}
        for arm, (ids_matrix, score_matrix) in ranked.items():
            ids = [edge_ids[int(i)] for i in ids_matrix[qi]]
            arms[arm] = {"ids": ids, "scores": [float(x) for x in score_matrix[qi]]}
        merged_fields = ["A" if labels[int(i)] == 0 else "B"
                         for i in ranked["merged"][0][qi]]
        records.append({
            "qid": query.qid,
            "qid_sha256": hashlib.sha256(query.qid.encode("utf-8")).hexdigest(),
            "question_sha256": hashlib.sha256(query.question.encode("utf-8")).hexdigest(),
            "query_token_count": len(query.question.split()),
            "query_entity_count": len(base_entities(query.question)),
            "gold": list(query.gold),
            "class": "cross_field" if gold_fields == {"A", "B"} else "in_field",
            "arms": arms,
            "merged_fields": merged_fields,
        })
    return {
        "schema": "hswm-b21-scorepack/v1",
        "dataset": dataset,
        "salt": salt,
        "condition": "private_entity" if private_entities else "base",
        "top_k": top_k,
        "model": MODEL_NAME,
        "lam_v": LAM_V,
        "lam_b": LAM_B,
        "n_queries": len(records),
        "n_paragraphs": len(edge_ids),
        "n_vertices": len(vertex_keys),
        "n_entity_classes": len(groups_merged),
        "edge_ids_sha256": hashlib.sha256("\n".join(edge_ids).encode("utf-8")).hexdigest(),
        "records": records,
    }


def recall_for(record: dict, arm: str, k: int) -> float:
    gold = set(record["gold"])
    if not gold:
        return 0.0
    return len(set(record["arms"][arm]["ids"][:k]) & gold) / len(gold)


STAT_NAMES = ("top1", "margin12", "mean", "std", "tail", "span", "entropy")


def _score_stats(values: Sequence[float], k: int) -> np.ndarray:
    x = np.asarray(values[:k], dtype=np.float64)
    if not len(x):
        return np.zeros(len(STAT_NAMES), dtype=np.float64)
    top1 = x[0]
    margin = x[0] - x[1] if len(x) > 1 else 0.0
    shifted = x - np.max(x)
    probs = np.exp(shifted)
    probs /= probs.sum()
    entropy = -float(np.sum(probs * np.log(probs + 1e-15))) / math.log(max(2, len(x)))
    return np.asarray([top1, margin, x.mean(), x.std(), x[-1], x[0] - x[-1], entropy])


def observable_features(record: dict, action: str, k: int) -> tuple[np.ndarray, tuple[str, ...]]:
    """A/B-equivariant action features. No target/private metadata is read."""
    if action not in ARMS:
        raise ValueError(action)
    stats = {a: _score_stats(record["arms"][a]["scores"], k) for a in ALL_ARMS}
    if action == "a":
        local, peer = stats["a"], stats["b"]
    elif action == "b":
        local, peer = stats["b"], stats["a"]
    else:
        local = stats["merged"]
        peer = (stats["a"] + stats["b"]) / 2.0
    single_hi = np.maximum(stats["a"], stats["b"])
    fields = record["merged_fields"][:k]
    pa = fields.count("A") / max(1, len(fields))
    balance = 1.0 - abs(2.0 * pa - 1.0)
    values = np.concatenate([
        np.asarray([1.0 if action == "merged" else 0.0]),
        local,
        peer,
        stats["merged"],
        stats["no_seam"],
        single_hi,
        local - stats["merged"],
        stats["merged"] - stats["no_seam"],
        np.asarray([balance, math.log1p(float(record["query_token_count"])),
                    float(record["query_entity_count"])]),
    ])
    names = (
        "is_merged",
        *(f"local_{x}" for x in STAT_NAMES),
        *(f"peer_{x}" for x in STAT_NAMES),
        *(f"merged_{x}" for x in STAT_NAMES),
        *(f"no_seam_{x}" for x in STAT_NAMES),
        *(f"single_hi_{x}" for x in STAT_NAMES),
        *(f"local_minus_merged_{x}" for x in STAT_NAMES),
        *(f"merged_minus_no_seam_{x}" for x in STAT_NAMES),
        "merged_field_balance", "log_query_tokens", "query_entity_count",
    )
    forbidden = ("qid", "gold", "answer", "class", "type", "support")
    if any(any(token in name for token in forbidden) for name in names):
        raise AssertionError("private/gold feature leaked into feature schema")
    return values, tuple(names)


def _fit_ridge(x: np.ndarray, y: np.ndarray, feature_names: tuple[str, ...], ridge_lambda: float,
               sample_weights: np.ndarray | None = None) -> RidgeModel:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    weights = (np.ones(len(x), dtype=np.float64) if sample_weights is None
               else np.asarray(sample_weights, dtype=np.float64))
    if len(weights) != len(x) or np.any(weights <= 0):
        raise ValueError("invalid ridge sample weights")
    mean = np.average(x, axis=0, weights=weights)
    scale = np.sqrt(np.average((x - mean) ** 2, axis=0, weights=weights))
    scale[scale < 1e-12] = 1.0
    z = (x - mean) / scale
    z = np.column_stack([np.ones(len(z)), z])
    root_w = np.sqrt(weights)[:, None]
    zw = z * root_w
    yw = y * root_w[:, 0]
    penalty = np.eye(z.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    coef = np.linalg.pinv(zw.T @ zw + penalty) @ zw.T @ yw
    return RidgeModel(coef=coef, mean=mean, scale=scale,
                      feature_names=feature_names, ridge_lambda=ridge_lambda)


def fit_shared_ridge(records: Sequence[dict], train_indices: Sequence[int], k: int, *,
                     ridge_lambda: float = RIDGE_LAMBDA,
                     target_permutation: Sequence[int] | None = None) -> RidgeModel:
    rows: list[np.ndarray] = []
    targets: list[float] = []
    weights: list[float] = []
    names: tuple[str, ...] | None = None
    source = list(train_indices) if target_permutation is None else list(target_permutation)
    if len(source) != len(train_indices):
        raise ValueError("target permutation length mismatch")
    component_size = {i: len(component) for component in gold_components(records, train_indices)
                      for i in component}
    for feature_i, target_i in zip(train_indices, source):
        for action in ARMS:
            x, names0 = observable_features(records[feature_i], action, k)
            names = names0 if names is None else names
            if names != names0:
                raise AssertionError("feature schema drift")
            rows.append(x)
            targets.append(recall_for(records[target_i], action, k))
            weights.append(1.0 / component_size[feature_i])
    assert names is not None
    return _fit_ridge(np.vstack(rows), np.asarray(targets), names, ridge_lambda,
                      np.asarray(weights))


def predict_utilities(model: RidgeModel, record: dict, k: int) -> dict[str, float]:
    matrix = np.vstack([observable_features(record, action, k)[0] for action in ARMS])
    vals = model.predict(matrix)
    return {action: float(vals[i]) for i, action in enumerate(ARMS)}


def conformal_advantage_radius(model: RidgeModel, records: Sequence[dict],
                               calibration_indices: Sequence[int], k: int,
                               alpha: float = CALIBRATION_ALPHA) -> float:
    # Repeated gold documents couple queries.  One worst over-estimation score
    # per gold-document connected component is the conformal exchangeability
    # unit; treating every query as IID would understate uncertainty.
    errors: list[float] = []
    for component in gold_components(records, calibration_indices):
        component_errors: list[float] = []
        for i in component:
            pred = predict_utilities(model, records[i], k)
            best = max(pred["a"], pred["b"])
            # Exact A/B ties have no name-free single-field choice.  Calibrate
            # both arms so the later ABSTAIN remains conservative/equivariant.
            chosen = [a for a in ("a", "b") if abs(pred[a] - best) <= 1e-12]
            for action in chosen:
                predicted_advantage = pred[action] - pred["merged"]
                true_advantage = (recall_for(records[i], action, k)
                                  - recall_for(records[i], "merged", k))
                component_errors.append(predicted_advantage - true_advantage)
        errors.append(max(component_errors))
    if not errors:
        raise ValueError("empty calibration split")
    ordered = sorted(errors)
    rank = min(len(ordered) - 1, max(0, math.ceil((len(ordered) + 1) * (1.0 - alpha)) - 1))
    return float(ordered[rank])


def route_or_abstain(model: RidgeModel, record: dict, k: int, radius: float) -> dict:
    pred = predict_utilities(model, record, k)
    if abs(pred["a"] - pred["b"]) <= 1e-12:
        return {"action": "ABSTAIN", "executed_action": "merged", "lcb": -1e30,
                "predicted": pred, "reason": "a_b_utility_tie"}
    single = min(("a", "b"), key=lambda a: (-pred[a], a))
    lcb = pred[single] - pred["merged"] - radius
    if lcb > 0.0:
        return {"action": single.upper(), "executed_action": single, "lcb": float(lcb),
                "predicted": pred}
    return {"action": "ABSTAIN", "executed_action": "merged", "lcb": float(lcb),
            "predicted": pred}


def gold_components(records: Sequence[dict], indices: Sequence[int]) -> list[list[int]]:
    parent = {i: i for i in indices}
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    owner: dict[str, int] = {}
    for i in indices:
        for pid in records[i]["gold"]:
            if pid in owner:
                union(i, owner[pid])
            else:
                owner[pid] = i
    out: dict[int, list[int]] = {}
    for i in indices:
        out.setdefault(find(i), []).append(i)
    return [sorted(v) for _, v in sorted(out.items())]


def component_membership(records: Sequence[dict], indices: Sequence[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for component in gold_components(records, indices):
        digest = hashlib.sha256("\n".join(
            records[i]["qid_sha256"] for i in component).encode("utf-8")).hexdigest()
        for i in component:
            out[i] = digest
    return out


def choose_component_count(records: Sequence[dict], indices: Sequence[int],
                           n_components: int, seed: int) -> tuple[list[int], list[int]]:
    """Select independent components, never query-count-fill with largest groups."""
    comps = gold_components(records, indices)
    if not 0 < n_components < len(comps):
        raise ValueError(f"invalid component count {n_components}/{len(comps)}")
    comps.sort(key=lambda c: hashlib.sha256(
        f"{seed}\0".encode("utf-8") + "\n".join(
            records[i]["qid_sha256"] for i in c).encode("utf-8")).hexdigest())
    selected = [i for comp in comps[:n_components] for i in comp]
    remaining = [i for comp in comps[n_components:] for i in comp]
    return sorted(selected), sorted(remaining)


def assert_split_disjoint(records: Sequence[dict], train: Sequence[int], calibration: Sequence[int], test: Sequence[int]) -> None:
    splits = [list(train), list(calibration), list(test)]
    qsets = [{records[i]["qid_sha256"] for i in part} for part in splits]
    gsets = [{p for i in part for p in records[i]["gold"]} for part in splits]
    for i in range(3):
        for j in range(i + 1, 3):
            if qsets[i] & qsets[j]:
                raise AssertionError("query overlap across split")
            if gsets[i] & gsets[j]:
                raise AssertionError("gold paragraph overlap across split")


def fixed_test_and_dev(records: Sequence[dict], dataset: str) -> tuple[list[int], list[int], dict]:
    all_indices = list(range(len(records)))
    if dataset == "2wiki":
        if len(records) != 500:
            raise RuntimeError(f"2wiki locked row count 500, got {len(records)}")
        order = all_indices[:]
        random.Random(B2_SEED).shuffle(order)
        dev = order[:400]
        candidates = order[400:]
        dev_gold = {p for i in dev for p in records[i]["gold"]}
        test = [i for i in candidates if not (set(records[i]["gold"]) & dev_gold)]
        excluded = [i for i in candidates if i not in set(test)]
        return sorted(test), sorted(dev), {"candidate_n": 100, "excluded_gold_overlap_n": len(excluded)}
    if dataset == "musique":
        if len(records) != 800:
            raise RuntimeError(f"musique locked row count 800, got {len(records)}")
        n_components = len(gold_components(records, all_indices))
        test_components = round(0.20 * n_components)
        test, dev = choose_component_count(records, all_indices, test_components, PRIMARY_SEED)
        return test, dev, {"total_components": n_components,
                           "test_components": test_components}
    raise ValueError(dataset)


def make_split(records: Sequence[dict], dataset: str, seed: int) -> dict[str, list[int]]:
    test, dev, _ = fixed_test_and_dev(records, dataset)
    dev_components = len(gold_components(records, dev))
    if dataset == "2wiki":
        cal_components = round(0.25 * dev_components)
    else:
        total_components = len(gold_components(records, list(range(len(records)))))
        cal_components = round(0.20 * total_components)
    calibration, train = choose_component_count(records, dev, cal_components, seed)
    assert_split_disjoint(records, train, calibration, test)
    return {"train": train, "calibration": calibration, "test": test}


def paired_cluster_bootstrap(values: list[float], cluster_ids: list[str], reps: int,
                             seed: int) -> tuple[float, float]:
    if not values or len(values) != len(cluster_ids):
        raise ValueError("cluster bootstrap shape mismatch")
    grouped: dict[str, list[float]] = {}
    for value, cluster in zip(values, cluster_ids):
        grouped.setdefault(cluster, []).append(value)
    clusters = sorted(grouped)
    sums = np.asarray([sum(grouped[c]) for c in clusters], dtype=np.float64)
    counts = np.asarray([len(grouped[c]) for c in clusters], dtype=np.float64)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(clusters), size=(reps, len(clusters)))
    estimates = np.sum(sums[sampled], axis=1) / np.sum(counts[sampled], axis=1)
    estimates.sort()
    return float(estimates[int(0.025 * reps)]), float(estimates[int(0.975 * reps)])


def _metric_block(values: list[float], baseline: list[float], cluster_ids: list[str],
                  seed: int) -> dict:
    delta = [a - b for a, b in zip(values, baseline)]
    ci = paired_cluster_bootstrap(delta, cluster_ids, BOOTSTRAP_REPS, seed)
    return {"n": len(values), "n_independent_components": len(set(cluster_ids)),
            "recall": round(float(np.mean(values)), 6),
            "baseline_recall": round(float(np.mean(baseline)), 6),
            "delta": round(float(np.mean(delta)), 6),
            "cluster_bootstrap95": [round(float(x), 6) for x in ci]}


def evaluate_router(scorepack: dict, split: dict[str, list[int]], k: int, seed: int,
                    *, shuffled: bool = False) -> dict:
    records = scorepack["records"]
    permutation = None
    if shuffled:
        permutation = list(split["train"])
        random.Random(seed + 100_003).shuffle(permutation)
    model = fit_shared_ridge(records, split["train"], k, target_permutation=permutation)
    radius = conformal_advantage_radius(model, records, split["calibration"], k)
    router: list[float] = []
    merged: list[float] = []
    best_single: list[float] = []
    cheap: list[float] = []
    oracle: list[float] = []
    classes: list[str] = []
    actions: dict[str, int] = {"A": 0, "B": 0, "ABSTAIN": 0}
    per_query = []
    membership = component_membership(records, split["test"])
    clusters: list[str] = []
    for i in split["test"]:
        rec = records[i]
        route = route_or_abstain(model, rec, k, radius)
        actions[route["action"]] += 1
        recalls = {a: recall_for(rec, a, k) for a in ARMS}
        r_router = recalls[route["executed_action"]]
        top1 = {a: rec["arms"][a]["scores"][0] for a in ARMS}
        cheap_action = min(ARMS, key=lambda a: (-top1[a], a))
        router.append(r_router)
        merged.append(recalls["merged"])
        best_single.append(max(recalls["a"], recalls["b"]))
        cheap.append(recalls[cheap_action])
        oracle.append(max(recalls.values()))
        classes.append(rec["class"])
        clusters.append(membership[i])
        per_query.append({"qid_sha256": rec["qid_sha256"], "class": rec["class"],
                          "router": r_router, "merged": recalls["merged"],
                          "best_single": max(recalls["a"], recalls["b"]),
                          "action": route["action"]})

    def subset(which: str | None) -> list[int]:
        return [i for i, c in enumerate(classes) if which is None or c == which]
    cross_idx = subset("cross_field")
    in_idx = subset("in_field")
    if not cross_idx or not in_idx:
        raise RuntimeError("test split requires both cross_field and in_field strata")
    pick = lambda xs, idx: [xs[i] for i in idx]
    overall = _metric_block(router, merged, clusters, seed + 1)
    cross_vs_single = _metric_block(pick(router, cross_idx), pick(best_single, cross_idx),
                                    pick(clusters, cross_idx), seed + 2)
    cross_vs_merged = _metric_block(pick(router, cross_idx), pick(merged, cross_idx),
                                    pick(clusters, cross_idx), seed + 3)
    in_vs_single = _metric_block(pick(router, in_idx), pick(best_single, in_idx),
                                 pick(clusters, in_idx), seed + 4)
    in_vs_merged = _metric_block(pick(router, in_idx), pick(merged, in_idx),
                                 pick(clusters, in_idx), seed + 5)
    gates = {
        "overall_ci_lower_gt_0": overall["cluster_bootstrap95"][0] > 0.0,
        "cross_gain_vs_best_single": (cross_vs_single["delta"] > NOISE_BAND
                                       and cross_vs_single["cluster_bootstrap95"][0] > 0.0),
        "cross_preserved_vs_merged": cross_vs_merged["delta"] >= -NOISE_BAND,
        "infield_no_harm_vs_best_single": in_vs_single["delta"] >= -NOISE_BAND,
        "infield_recovery_vs_merged": in_vs_merged["delta"] > 0.0,
        "nontrivial_acceptance": (actions["A"] + actions["B"]) > 0,
    }
    gates["joint_pass"] = all(gates.values())
    return {
        "shuffled_target": shuffled,
        "k": k,
        "seed": seed,
        "split": {key: len(value) for key, value in split.items()},
        "split_components": {key: len(gold_components(records, value))
                             for key, value in split.items()},
        "split_id_sha256": {key: hashlib.sha256("\n".join(
            records[i]["qid_sha256"] for i in value).encode("utf-8")).hexdigest()
            for key, value in split.items()},
        "calibration": {"alpha": CALIBRATION_ALPHA, "advantage_radius": round(radius, 8)},
        "actions": actions,
        "metrics": {"overall_vs_merged": overall, "cross_vs_best_single": cross_vs_single,
                    "cross_vs_merged": cross_vs_merged, "infield_vs_best_single": in_vs_single,
                    "infield_vs_merged": in_vs_merged,
                    "cheap_top1_recall": round(float(np.mean(cheap)), 6),
                    "oracle_recall": round(float(np.mean(oracle)), 6)},
        "gates": gates,
        "model": {"kind": "shared_action_value_ridge", "ridge_lambda": RIDGE_LAMBDA,
                  "n_features": len(model.feature_names),
                  "feature_schema_sha256": hashlib.sha256(
                      "\n".join(model.feature_names).encode("utf-8")).hexdigest()},
        "per_query_sha256": hashlib.sha256(json.dumps(per_query, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest(),
    }


def swap_fields(record: dict) -> dict:
    """Test helper: swap arbitrary A/B names while keeping MERGED invariant."""
    out = json.loads(json.dumps(record))
    out["arms"]["a"], out["arms"]["b"] = out["arms"]["b"], out["arms"]["a"]
    out["merged_fields"] = [{"A": "B", "B": "A"}[x] for x in out["merged_fields"]]
    return out


def write_scorepack(path: Path, scorepack: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(scorepack, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=buf, mode="wb", mtime=0) as handle:
        handle.write(payload)
    path.write_bytes(buf.getvalue())
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size,
            "payload_sha256": hashlib.sha256(payload).hexdigest()}


def read_scorepack(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def scorepack_filename(dataset: str, condition: str, salt: str, *, reproduction: bool = False) -> str:
    suffix = "_b2repro" if reproduction else ""
    safe_salt = salt.replace("-", "_")
    return f"b21_{dataset}_{condition}_{safe_salt}{suffix}.json.gz"


def _mean_delta(records: Sequence[dict], indices: Sequence[int], left: str, right: str, k: int) -> float:
    return float(np.mean([recall_for(records[i], left, k) - recall_for(records[i], right, k)
                          for i in indices]))


def frozen_b2_reference(rows: list[dict], embed_fn, top_k: int = MAX_K) -> dict:
    """Run the unmodified B2 scorer row by row for an exact equivalence receipt."""
    usable = []
    for row in rows:
        strat = b2_stratify(row)
        if strat is None:
            continue
        usable.append((row, *strat))
    pool = b2_paragraphs_from_rows([row for row, _, _ in usable])
    field_a, field_b = b2_build_field(pool, "A"), b2_build_field(pool, "B")
    merged = b2_merge(field_a, field_b, new_seam=b2_seam_arcs_between(field_a, field_b))
    no_seam = b2_compose([field_a, field_b])
    questions = [row["question"] for row, _, _ in usable]
    texts = b2_collect_texts([field_a, field_b, merged, no_seam], questions)
    table = dict(zip(texts, embed_fn(texts)))
    for field in (field_a, field_b, merged, no_seam):
        b2_attach_embeddings(field, table)
    fields = {"a": field_a, "b": field_b, "merged": merged, "no_seam": no_seam}
    records = []
    for row, klass, gold in usable:
        arms = {}
        for name, field in fields.items():
            ranking = b2_rank_paragraphs(field, table[row["question"]], top_k=top_k)
            arms[name] = {"ids": [x[0] for x in ranking],
                          "scores": [float(x[1]) for x in ranking]}
        records.append({"qid": str(row.get("id", "")), "class": klass,
                        "gold": sorted(gold), "arms": arms})
    return {"records": records}


def compare_b2_rankings(vectorized: dict, reference: dict, tolerance: float = 1e-9) -> dict:
    left, right = vectorized["records"], reference["records"]
    mismatched_ids = 0
    mismatched_qids = 0
    max_abs_score_error = 0.0
    comparisons = 0
    canonical_left = []
    canonical_right = []
    if len(left) != len(right):
        return {"pass": False, "reason": "row_count", "vectorized_n": len(left),
                "reference_n": len(right)}
    for a, b in zip(left, right):
        if a["qid"] != b["qid"]:
            mismatched_qids += 1
        row_l = {"qid": a["qid"], "arms": {}}
        row_r = {"qid": b["qid"], "arms": {}}
        for arm in ALL_ARMS:
            ids_l, ids_r = a["arms"][arm]["ids"], b["arms"][arm]["ids"]
            if ids_l != ids_r:
                mismatched_ids += 1
            scores_l = a["arms"][arm]["scores"]
            scores_r = b["arms"][arm]["scores"]
            if len(scores_l) != len(scores_r):
                mismatched_ids += 1
                continue
            for x, y in zip(scores_l, scores_r):
                max_abs_score_error = max(max_abs_score_error, abs(x - y))
                comparisons += 1
            row_l["arms"][arm] = {"ids": ids_l, "scores": [round(x, 9) for x in scores_l]}
            row_r["arms"][arm] = {"ids": ids_r, "scores": [round(x, 9) for x in scores_r]}
        canonical_left.append(row_l)
        canonical_right.append(row_r)
    encode = lambda x: hashlib.sha256(json.dumps(x, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"pass": mismatched_qids == 0 and mismatched_ids == 0
                    and max_abs_score_error <= tolerance,
            "n_queries": len(left), "n_arm_rankings": len(left) * len(ALL_ARMS),
            "n_score_comparisons": comparisons, "mismatched_qids": mismatched_qids,
            "mismatched_ranked_id_lists": mismatched_ids,
            "max_abs_score_error": max_abs_score_error, "tolerance": tolerance,
            "vectorized_digest": encode(canonical_left),
            "frozen_reference_digest": encode(canonical_right)}


def b2_reproduction(scorepack: dict, reference: dict | None = None) -> dict:
    records = scorepack["records"]
    cross = [i for i, r in enumerate(records) if r["class"] == "cross_field"]
    infield = [i for i, r in enumerate(records) if r["class"] == "in_field"]
    observed = {
        "cross_n": len(cross), "infield_n": len(infield),
        "cross_merged_minus_best_single": float(np.mean([
            recall_for(records[i], "merged", 10) - max(recall_for(records[i], "a", 10),
                                                        recall_for(records[i], "b", 10)) for i in cross])),
        "infield_merged_minus_best_single": float(np.mean([
            recall_for(records[i], "merged", 10) - max(recall_for(records[i], "a", 10),
                                                        recall_for(records[i], "b", 10)) for i in infield])),
        "cross_merged_minus_no_seam": _mean_delta(records, cross, "merged", "no_seam", 10),
    }
    expected = {"cross_n": 234, "infield_n": 166,
                "cross_merged_minus_best_single": 0.213675,
                "infield_merged_minus_best_single": -0.064759,
                "cross_merged_minus_no_seam": 0.034188}
    checks = {key: (observed[key] == value if key.endswith("_n")
                    else abs(observed[key] - value) <= 1e-6)
              for key, value in expected.items()}
    exact = compare_b2_rankings(scorepack, reference) if reference is not None else None
    return {"observed": {k: round(v, 6) if isinstance(v, float) else v for k, v in observed.items()},
            "expected": expected, "checks": checks, "exact_rowwise": exact,
            "pass": all(checks.values()) and (exact is None or exact["pass"])}


def locked_parameters() -> dict:
    return {
        "partition_salts": list(PARTITION_SALTS), "top_ks": list(TOP_KS),
        "split_seeds": list(SPLIT_SEEDS), "primary_salt": PRIMARY_SALT,
        "primary_k": PRIMARY_K, "primary_seed": PRIMARY_SEED,
        "ridge_lambda": RIDGE_LAMBDA, "calibration_alpha": CALIBRATION_ALPHA,
        "bootstrap_reps": BOOTSTRAP_REPS, "noise_band": NOISE_BAND,
        "lam_v": LAM_V, "lam_b": LAM_B, "model": MODEL_NAME,
        "standard_cells": 54, "private_entity_cells": 6,
        "split_scheme": "fixed_test_gold_component_disjoint_v1",
        "training_weight": "inverse_gold_component_size",
        "calibration_unit": "worst_error_per_gold_component",
        "bootstrap_unit": "gold_component",
        "private_control": "entity_surface_only_not_answer_mask",
    }


def preregistration_guard(data_paths: dict[str, Path], model_path: Path) -> tuple[dict, dict]:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration is not server-confirmed")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("missing LakatoTree prediction receipt")
    if locked.get("locked_parameters") != locked_parameters():
        raise RuntimeError("locked parameter drift")
    model_manifest = directory_manifest(model_path)
    expected = {"script_sha256": sha256_file(Path(__file__).resolve()),
                "dataset_2wiki_sha256": sha256_file(data_paths["2wiki"]),
                "dataset_musique_sha256": sha256_file(data_paths["musique"]),
                "model_snapshot_sha256": model_manifest["sha256"]}
    expected.update({f"{name}_sha256": sha256_file(HERE / name) for name in FROZEN_MODULES})
    for key, value in expected.items():
        if locked.get(key) != value:
            raise RuntimeError(f"frozen artifact drift: {key}")
    return locked, model_manifest


def validate_scorepack(scorepack: dict, *, dataset: str, salt: str, condition: str,
                       cohort: str, provenance: dict) -> None:
    expected = {"schema": "hswm-b21-scorepack/v1", "dataset": dataset, "salt": salt,
                "condition": condition, "top_k": MAX_K, "model": MODEL_NAME,
                "cohort": cohort, "provenance": provenance}
    for key, value in expected.items():
        if scorepack.get(key) != value:
            raise RuntimeError(f"stale/wrong scorepack: {key} mismatch")


class CachedSentenceEmbedder:
    def __init__(self, model_path: str, batch_size: int = 128):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_path, device="cuda")
        self.batch_size = batch_size
        self.cache: dict[str, np.ndarray] = {}

    def __call__(self, texts: list[str]) -> np.ndarray:
        missing = [x for x in texts if x not in self.cache]
        if missing:
            vectors = self.model.encode(missing, normalize_embeddings=True,
                                        convert_to_numpy=True, batch_size=self.batch_size,
                                        show_progress_bar=False)
            for text, vec in zip(missing, vectors):
                self.cache[text] = np.asarray(vec, dtype=np.float64)
        return np.vstack([self.cache[x] for x in texts])


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_full_experiment(data_paths: dict[str, Path], scorepack_dir: Path, model_path: str,
                        *, reuse_scorepacks: bool = False) -> dict:
    locked, model_manifest = preregistration_guard(data_paths, Path(model_path))
    raw = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in data_paths.items()}
    normalized = {name: normalize_rows(raw[name], name) for name in ("2wiki", "musique")}
    embedder = None
    manifests = []
    cases = []
    private_cases = []

    def obtain(dataset: str, salt: str, private: bool, *, reproduction: bool = False) -> dict:
        nonlocal embedder
        condition = "private_entity" if private else "base"
        cohort = "b2_reproduction400" if reproduction else "full_closed_corpus"
        provenance = {
            "script_sha256": locked["script_sha256"],
            "dataset_sha256": sha256_file(data_paths[dataset]),
            "model_snapshot_sha256": model_manifest["sha256"],
            "frozen_modules_sha256": {name: locked[f"{name}_sha256"]
                                      for name in FROZEN_MODULES},
            "locked_parameters_sha256": hashlib.sha256(json.dumps(
                locked_parameters(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest(),
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
        }
        path = scorepack_dir / scorepack_filename(dataset, condition, salt, reproduction=reproduction)
        if reuse_scorepacks and path.exists():
            pack = read_scorepack(path)
            validate_scorepack(pack, dataset=dataset, salt=salt, condition=condition,
                               cohort=cohort, provenance=provenance)
            payload = (json.dumps(pack, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")) + "\n").encode("utf-8")
            manifests.append({"path": str(path), "sha256": sha256_file(path),
                              "bytes": path.stat().st_size,
                              "payload_sha256": hashlib.sha256(payload).hexdigest(),
                              "dataset": dataset, "salt": salt,
                              "condition": condition, "reproduction": reproduction,
                              "reused": True})
        else:
            if embedder is None:
                embedder = CachedSentenceEmbedder(model_path)
            queries, pool = normalized[dataset]
            if reproduction:
                order = list(range(len(queries)))
                random.Random(B2_SEED).shuffle(order)
                # Frozen B2 pool is every paragraph in the selected rows.  We need
                # row ownership, unavailable after normalization, so reproduction
                # is compiled by a separately normalized raw subset below.
                source_rows = raw[dataset]["rows"] if isinstance(raw[dataset], dict) else raw[dataset]
                selected_rows = [source_rows[i] for i in order[:400]]
                chosen, chosen_pool = normalize_rows(selected_rows, dataset)
                pack = compile_scorepack(chosen, chosen_pool, embedder, dataset=dataset,
                                         salt=salt, private_entities=private)
            else:
                pack = compile_scorepack(queries, pool, embedder, dataset=dataset,
                                         salt=salt, private_entities=private)
            pack["cohort"] = cohort
            pack["provenance"] = provenance
            manifest = write_scorepack(path, pack)
            manifests.append({**manifest, "dataset": dataset, "salt": salt,
                              "condition": condition, "reproduction": reproduction})
        return pack

    repro_pack = obtain("2wiki", "legacy", False, reproduction=True)
    if embedder is None:
        embedder = CachedSentenceEmbedder(model_path)
    source_rows = raw["2wiki"]["rows"] if isinstance(raw["2wiki"], dict) else raw["2wiki"]
    repro_order = list(range(len(source_rows)))
    random.Random(B2_SEED).shuffle(repro_order)
    selected_rows = [source_rows[i] for i in repro_order[:400]]
    reference = frozen_b2_reference(selected_rows, embedder)
    reproduction = b2_reproduction(repro_pack, reference)
    if not reproduction["pass"]:
        raise RuntimeError(f"vectorized scorer failed frozen B2 reproduction: {reproduction}")

    for dataset in ("2wiki", "musique"):
        for salt in PARTITION_SALTS:
            pack = obtain(dataset, salt, False)
            for seed in SPLIT_SEEDS:
                split = make_split(pack["records"], dataset, seed)
                for k in TOP_KS:
                    result = evaluate_router(pack, split, k, seed)
                    negative = evaluate_router(pack, split, k, seed, shuffled=True)
                    result.update({"dataset": dataset, "salt": salt, "condition": "base",
                                   "shuffled_control_joint_pass": negative["gates"]["joint_pass"],
                                   "shuffled_control_overall_delta": negative["metrics"]["overall_vs_merged"]["delta"],
                                   "shuffled_control": negative})
                    cases.append(result)
        private_pack = obtain(dataset, PRIMARY_SALT, True)
        for seed in SPLIT_SEEDS:
            split = make_split(private_pack["records"], dataset, seed)
            result = evaluate_router(private_pack, split, PRIMARY_K, seed)
            result.update({"dataset": dataset, "salt": PRIMARY_SALT,
                           "condition": "private_entity"})
            private_cases.append(result)

    primary = [c for c in cases if c["salt"] == PRIMARY_SALT and c["k"] == PRIMARY_K
               and c["seed"] == PRIMARY_SEED]
    primary_by_dataset = {c["dataset"]: c for c in primary}
    standard_pass = sum(bool(c["gates"]["joint_pass"]) for c in cases)
    shuffled_pass = sum(bool(c["shuffled_control_joint_pass"]) for c in cases)
    private_primary = [c for c in private_cases if c["seed"] == PRIMARY_SEED]
    primary_passes = sum(bool(c["gates"]["joint_pass"]) for c in primary)
    private_by_dataset = {c["dataset"]: c for c in private_primary}
    private_no_harm_by_dataset = {
        dataset: private_by_dataset[dataset]["metrics"]["overall_vs_merged"]["delta"] >= -NOISE_BAND
        for dataset in ("2wiki", "musique")}
    private_no_harm = all(private_no_harm_by_dataset.values())
    private_joint_pass = all(c["gates"]["joint_pass"] for c in private_primary)
    domain_robustness = {}
    eligible_domains = []
    for dataset in ("2wiki", "musique"):
        domain_cases = [c for c in cases if c["dataset"] == dataset]
        domain_pass = sum(bool(c["gates"]["joint_pass"]) for c in domain_cases)
        domain_shuffled = sum(bool(c["shuffled_control_joint_pass"]) for c in domain_cases)
        domain_robustness[dataset] = {"n_cells": len(domain_cases),
                                      "joint_pass_n": domain_pass,
                                      "joint_pass_rate": domain_pass / len(domain_cases),
                                      "shuffled_joint_pass_n": domain_shuffled}
        if (primary_by_dataset[dataset]["gates"]["joint_pass"]
                and domain_pass >= math.ceil(0.50 * len(domain_cases))
                and domain_shuffled == 0 and private_no_harm_by_dataset[dataset]):
            eligible_domains.append(dataset)
    if shuffled_pass > 0:
        conclusion = "REJECTED_CONTROL_FAILURE"
    elif primary_passes == 2 and standard_pass >= math.ceil(0.80 * len(cases)) \
            and shuffled_pass == 0 and private_joint_pass:
        conclusion = "SUPPORTED_GENERAL"
    elif primary_passes == 2 and standard_pass >= math.ceil(0.50 * len(cases)) \
            and shuffled_pass == 0 and private_no_harm:
        conclusion = "SUPPORTED_NARROW"
    elif (primary_passes == 2 and standard_pass >= math.ceil(0.50 * len(cases))
          and not private_no_harm):
        conclusion = "SURFACE_DEPENDENT"
    elif len(eligible_domains) == 1:
        conclusion = "DOMAIN_CONDITIONAL"
    else:
        conclusion = "REJECTED"
    min_primary_delta = min(c["metrics"]["overall_vs_merged"]["delta"] for c in primary)
    return {
        "schema": "lakato-evidence-record/v1",
        "programme": TREE, "branch": BRANCH, "question": QUESTION,
        "measurement": {
            "metric": "min_over_datasets_primary_router_minus_merged_recall10",
            "value": min_primary_delta,
            "conclusion": conclusion,
            "primary": primary_by_dataset,
            "standard_matrix": {"n_cells": len(cases), "joint_pass_n": standard_pass,
                                "joint_pass_rate": standard_pass / len(cases),
                                "shuffled_joint_pass_n": shuffled_pass,
                                "by_dataset": domain_robustness},
            "private_entity_stress": {"n_cells": len(private_cases),
                                      "primary_no_harm": private_no_harm,
                                      "primary_joint_pass": private_joint_pass,
                                      "no_harm_by_dataset": private_no_harm_by_dataset,
                                      "cases": private_cases},
            "cases": cases,
        },
        "b2_reproduction": reproduction,
        "scorepacks": manifests,
        "preregistration": {"path": str(PREREG),
                            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
                            "registered_before_measurement": True,
                            "script_sha256": sha256_file(Path(__file__).resolve())},
        "provenance": {"inputs": [{"dataset": name, "path": str(path),
                                     "sha256": sha256_file(path)}
                                    for name, path in data_paths.items()]},
        "harness": {"git_head": _git_head(), "python": sys.version.split()[0],
                    "numpy": np.__version__, "platform": platform.platform(),
                    "model_path": model_path,
                    "model_snapshot": {key: model_manifest[key]
                                       for key in ("sha256", "n_files", "bytes")},
                    "finished_at": utc_now()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--2wiki", required=True, dest="two_wiki")
    parser.add_argument("--musique", required=True)
    parser.add_argument("--model-path", required=True,
                        help="local frozen SentenceTransformer snapshot path")
    parser.add_argument("--scorepack-dir", required=True)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--reuse-scorepacks", action="store_true")
    args = parser.parse_args()
    started = utc_now()
    evidence = run_full_experiment(
        {"2wiki": Path(args.two_wiki), "musique": Path(args.musique)},
        Path(args.scorepack_dir), args.model_path, reuse_scorepacks=args.reuse_scorepacks)
    evidence["harness"]["started_at"] = started
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "sha256": sha256_file(output),
                      "measurement": evidence["measurement"]["metric"],
                      "value": evidence["measurement"]["value"],
                      "conclusion": evidence["measurement"]["conclusion"],
                      "standard_matrix": evidence["measurement"]["standard_matrix"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
