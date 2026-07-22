#!/usr/bin/env python3
"""P5: equal-compute single scalar vs role-separated multi-view late fusion.

Programme: LakatosTree_PromSearchHSWM_20260721
Branch: P5-onefield-vs-multiview-hardhop

The measurement deliberately keeps the expensive views identical between arms:

* title semantic score (anchor role)
* body semantic score (evidence role)
* n-ary entity-hypergraph propagation score (bridge role)

The control collapses the three normalized scores into one scalar before ranking.
The treatment preserves the three rankings and combines them only at readout with
query-only routing weights.  Therefore any delta is a fusion/representation delta,
not an embedding-call or candidate-scan delta.

This script must not be run until the sibling PREREG JSON contains a live
LakatoTree prediction receipt and ``registered_before_measurement=true``.
It emits a ``lakato-evidence-record/v1`` object with no authored verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np


TREE = "LakatosTree_PromSearchHSWM_20260721"
BRANCH = "P5-onefield-vs-multiview-hardhop"
CONJECTURE = (
    "On 2Wiki questions with four supporting passages, preserving anchor, evidence, "
    "and bridge scores as separate views until late readout beats an equal-compute "
    "single scalar without materially regressing two-support questions."
)

HERE = Path(__file__).resolve().parent
DATASET = Path("/Volumes/GM/bench/2wiki_dev.jsonl")
PREREG = HERE / "evidence" / "PREREG_p5_multiview_hardhop_20260722.json"
OUTPUT = HERE / "evidence" / "EVIDENCE_p5_multiview_hardhop_20260722.json"

N_Q = 400
SEED = 7331
TOP_K = 10
FULLCHAIN_K = 20
BOOTSTRAP_REPS = 2000
DF_MIN = 2
DF_MAX = 40
APPNP_ALPHA = 0.30
APPNP_STEPS = 10
RRF_K = 60

STOP = {
    "The", "A", "An", "In", "On", "At", "He", "She", "It", "They", "This",
    "That", "His", "Her", "When", "After", "Before", "There", "Their", "These",
    "Those", "As", "Of", "For", "And", "But", "Also", "However", "Its", "Who",
    "Which", "What", "Where", "Was", "Were", "Is", "Are", "Did", "Does",
}

COMPARISON_CUES = re.compile(
    r"\b(which|earlier|later|older|younger|more|less|both|same|difference|higher|lower)\b",
    re.IGNORECASE,
)
COMPOSITION_CUES = re.compile(
    r"\b(mother|father|parent|spouse|director|author|born|country|capital|member|owner)\b|\bof the\b",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def entities(text: str) -> set[str]:
    return {
        match.lower()
        for match in re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b", text)
        if match not in STOP and len(match) > 2
    }


def load_locked_sample(path: Path, n: int, seed: int):
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("answerable", True):
                rows.append(row)
    random.Random(seed).shuffle(rows)
    rows = rows[:n]
    if len(rows) != n:
        raise RuntimeError(f"expected {n} answerable rows, got {len(rows)}")

    titles: list[str] = []
    bodies: list[str] = []
    key_to_index: dict[str, int] = {}
    questions: list[str] = []
    gold: list[set[int]] = []
    support_counts: list[int] = []
    hop_types: list[str] = []
    row_ids: list[str] = []

    for row in rows:
        row_gold: set[int] = set()
        for paragraph in row["paragraphs"]:
            title = paragraph["title"]
            body = paragraph["paragraph_text"]
            key = hashlib.sha256(f"{title}\0{body}".encode()).hexdigest()
            if key not in key_to_index:
                key_to_index[key] = len(titles)
                titles.append(title)
                bodies.append(body)
            if paragraph.get("is_supporting"):
                row_gold.add(key_to_index[key])
        if len(row_gold) not in {2, 4}:
            raise RuntimeError(f"unexpected support count {len(row_gold)} for {row.get('id')}")
        questions.append(row["question"])
        gold.append(row_gold)
        support_counts.append(len(row_gold))
        hop_types.append(str(row.get("hop", "unknown")))
        row_ids.append(str(row["id"]))

    selected_ids_sha = hashlib.sha256("\n".join(row_ids).encode()).hexdigest()
    return titles, bodies, questions, gold, support_counts, hop_types, row_ids, selected_ids_sha


def build_hypergraph(titles: list[str], bodies: list[str]):
    texts = [f"{title}. {body}" for title, body in zip(titles, bodies)]
    entity_sets = [entities(text) for text in texts]
    inverted: defaultdict[str, list[int]] = defaultdict(list)
    for index, values in enumerate(entity_sets):
        for value in values:
            inverted[value].append(index)
    kept = sorted(
        value for value, members in inverted.items() if DF_MIN <= len(members) <= DF_MAX
    )
    n_docs = len(texts)
    if not kept:
        return np.zeros((n_docs, n_docs), dtype=np.float32), 0

    edge_index = {value: index for index, value in enumerate(kept)}
    incidence = np.zeros((n_docs, len(kept)), dtype=np.float32)
    for value in kept:
        for doc_index in inverted[value]:
            incidence[doc_index, edge_index[value]] = 1.0
    edge_degree = np.array([len(inverted[value]) for value in kept], dtype=np.float32)
    idf = np.array([math.log(n_docs / len(inverted[value])) for value in kept], dtype=np.float32)
    weighted = incidence * idf[None, :]
    theta = (weighted * (1.0 / edge_degree)[None, :]) @ incidence.T
    np.fill_diagonal(theta, 0.0)
    vertex_degree = theta.sum(axis=1)
    inv_sqrt = 1.0 / np.sqrt(np.maximum(vertex_degree, 1e-9))
    theta = (theta * inv_sqrt[:, None]) * inv_sqrt[None, :]
    return theta.astype(np.float32), len(kept)


def appnp(theta: np.ndarray, seeds: np.ndarray) -> np.ndarray:
    seed = np.maximum(seeds, 0.0).astype(np.float32)
    state = seed.copy()
    for _ in range(APPNP_STEPS):
        state = (1.0 - APPNP_ALPHA) * (theta @ state) + APPNP_ALPHA * seed
    return state


def route_weights(question: str) -> tuple[float, float, float, str]:
    """Question-only routing; no dataset hop label or gold is consulted."""
    if COMPARISON_CUES.search(question):
        return 1.25, 1.00, 1.25, "comparison"
    if COMPOSITION_CUES.search(question):
        return 1.00, 1.00, 1.50, "composition"
    return 1.00, 1.00, 1.25, "default"


def zscore(values: np.ndarray) -> np.ndarray:
    std = float(values.std())
    if std <= 1e-9:
        return np.zeros_like(values)
    return (values - float(values.mean())) / std


def rank_positions(values: np.ndarray) -> np.ndarray:
    order = np.argsort(-values, kind="stable")
    positions = np.empty(len(values), dtype=np.int32)
    positions[order] = np.arange(len(values), dtype=np.int32)
    return positions


def equal_compute_ranks(
    title_score: np.ndarray,
    body_score: np.ndarray,
    bridge_score: np.ndarray,
    weights: tuple[float, float, float],
):
    wt, wb, wg = weights
    early_score = wt * zscore(title_score) + wb * zscore(body_score) + wg * zscore(bridge_score)
    early = np.argsort(-early_score, kind="stable")

    title_rank = rank_positions(title_score)
    body_rank = rank_positions(body_score)
    bridge_rank = rank_positions(bridge_score)
    late_score = (
        wt / (RRF_K + 1.0 + title_rank)
        + wb / (RRF_K + 1.0 + body_rank)
        + wg / (RRF_K + 1.0 + bridge_rank)
    )
    late = np.argsort(-late_score, kind="stable")
    return early, late


def recall_at(ranking: Iterable[int], gold: set[int], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(list(ranking)[:k]) & gold) / len(gold)


def fullchain_at(ranking: Iterable[int], gold: set[int], k: int) -> float:
    return float(bool(gold) and gold <= set(list(ranking)[:k]))


def paired_bootstrap(values: list[float], reps: int, seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means = [sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps)]
    means.sort()
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def preregistration_guard(script_sha: str, dataset_sha: str) -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration is not server-confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks prediction receipt")
    if locked.get("script_sha256") != script_sha:
        raise RuntimeError("script changed after preregistration")
    if locked.get("dataset_sha256") != dataset_sha:
        raise RuntimeError("dataset changed after preregistration")
    expected = locked.get("locked_parameters", {})
    actual = {
        "n_q": N_Q,
        "seed": SEED,
        "top_k": TOP_K,
        "fullchain_k": FULLCHAIN_K,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "df_min": DF_MIN,
        "df_max": DF_MAX,
        "appnp_alpha": APPNP_ALPHA,
        "appnp_steps": APPNP_STEPS,
        "rrf_k": RRF_K,
    }
    if expected != actual:
        raise RuntimeError(f"locked parameter drift: {expected!r} != {actual!r}")
    return locked


def main() -> int:
    started_at = utc_now()
    script_path = Path(__file__).resolve()
    script_sha = sha256_file(script_path)
    if not DATASET.exists():
        raise RuntimeError(f"missing dataset: {DATASET}")
    dataset_sha = sha256_file(DATASET)
    locked = preregistration_guard(script_sha, dataset_sha)

    titles, bodies, questions, gold, support_counts, hop_types, row_ids, sample_sha = (
        load_locked_sample(DATASET, N_Q, SEED)
    )
    from sentence_transformers import SentenceTransformer, __version__ as st_version
    import torch

    torch.manual_seed(SEED)
    cache = Path("/Volumes/GM/hswm_lab/st_cache")
    cache.mkdir(parents=True, exist_ok=True)
    model_name = "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name, cache_folder=str(cache))
    title_emb = model.encode(
        titles, normalize_embeddings=True, convert_to_numpy=True, batch_size=128,
        show_progress_bar=False,
    ).astype(np.float32)
    body_emb = model.encode(
        bodies, normalize_embeddings=True, convert_to_numpy=True, batch_size=128,
        show_progress_bar=False,
    ).astype(np.float32)
    query_emb = model.encode(
        questions, normalize_embeddings=True, convert_to_numpy=True, batch_size=128,
        show_progress_bar=False,
    ).astype(np.float32)

    title_scores = (query_emb @ title_emb.T).astype(np.float32)
    body_scores = (query_emb @ body_emb.T).astype(np.float32)
    theta, n_hyperedges = build_hypergraph(titles, bodies)
    seed_scores = (0.5 * title_scores + 0.5 * body_scores).T.astype(np.float32)
    bridge_scores = appnp(theta, seed_scores).T

    per_query = []
    route_counts: defaultdict[str, int] = defaultdict(int)
    for index, question in enumerate(questions):
        wt, wb, wg, route = route_weights(question)
        route_counts[route] += 1
        early, late = equal_compute_ranks(
            title_scores[index], body_scores[index], bridge_scores[index], (wt, wb, wg)
        )
        row = {
            "id": row_ids[index],
            "hop_type": hop_types[index],
            "support_count": support_counts[index],
            "route": route,
            "early_recall10": recall_at(early, gold[index], TOP_K),
            "late_recall10": recall_at(late, gold[index], TOP_K),
            "early_fullchain20": fullchain_at(early, gold[index], FULLCHAIN_K),
            "late_fullchain20": fullchain_at(late, gold[index], FULLCHAIN_K),
        }
        row["recall10_delta"] = row["late_recall10"] - row["early_recall10"]
        row["fullchain20_delta"] = row["late_fullchain20"] - row["early_fullchain20"]
        per_query.append(row)

    hard4 = [row for row in per_query if row["support_count"] == 4]
    support2 = [row for row in per_query if row["support_count"] == 2]
    if not hard4 or not support2:
        raise RuntimeError("both 4-support and 2-support strata are required")

    def mean(rows: list[dict], key: str) -> float:
        return float(statistics.mean(row[key] for row in rows))

    hard4_recall_gain = mean(hard4, "recall10_delta")
    hard4_fullchain_gain = mean(hard4, "fullchain20_delta")
    support2_recall_gain = mean(support2, "recall10_delta")
    hard4_ci = paired_bootstrap(
        [row["recall10_delta"] for row in hard4], BOOTSTRAP_REPS, SEED + 1
    )
    support2_ci = paired_bootstrap(
        [row["recall10_delta"] for row in support2], BOOTSTRAP_REPS, SEED + 2
    )
    joint_pass_margin = min(
        hard4_recall_gain - 0.03,
        hard4_fullchain_gain - 0.02,
        support2_recall_gain + 0.01,
        hard4_ci[0],
    )

    by_hop = {}
    for hop_type in sorted(set(hop_types)):
        rows = [row for row in per_query if row["hop_type"] == hop_type]
        by_hop[hop_type] = {
            "n": len(rows),
            "early_recall10": round(mean(rows, "early_recall10"), 6),
            "late_recall10": round(mean(rows, "late_recall10"), 6),
            "late_minus_early_recall10": round(mean(rows, "recall10_delta"), 6),
        }

    finished_at = utc_now()
    evidence = {
        "schema": "lakato-evidence-record/v1",
        "programme": TREE,
        "branch": BRANCH,
        "conjecture": CONJECTURE,
        "preregistration": {
            "path": str(PREREG),
            "registered_at": locked["server_registered_at"],
            "registered_before_measurement": True,
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
            "script_sha256": script_sha,
        },
        "measurement": {
            "metric": "hard4_recall10_multiview_minus_early",
            "value": round(hard4_recall_gain, 6),
            "unit": "paired proportion delta",
            "scope": f"2Wiki held-out deterministic sample; four-support rows n={len(hard4)}",
            "noise_band": 0.02,
            "novel_metric": "joint_pass_margin",
            "novel_value": round(joint_pass_margin, 6),
            "subgroups": {
                "hard4": {
                    "n": len(hard4),
                    "early_recall10": round(mean(hard4, "early_recall10"), 6),
                    "late_recall10": round(mean(hard4, "late_recall10"), 6),
                    "recall10_gain": round(hard4_recall_gain, 6),
                    "recall10_gain_bootstrap95": [round(value, 6) for value in hard4_ci],
                    "early_fullchain20": round(mean(hard4, "early_fullchain20"), 6),
                    "late_fullchain20": round(mean(hard4, "late_fullchain20"), 6),
                    "fullchain20_gain": round(hard4_fullchain_gain, 6),
                },
                "support2_guardrail": {
                    "n": len(support2),
                    "early_recall10": round(mean(support2, "early_recall10"), 6),
                    "late_recall10": round(mean(support2, "late_recall10"), 6),
                    "recall10_gain": round(support2_recall_gain, 6),
                    "recall10_gain_bootstrap95": [round(value, 6) for value in support2_ci],
                },
                "by_dataset_hop_label": by_hop,
            },
            "pre_registered_checks": {
                "hard4_recall_gain_ge_0_03": hard4_recall_gain >= 0.03,
                "hard4_fullchain_gain_ge_0_02": hard4_fullchain_gain >= 0.02,
                "support2_regression_ge_minus_0_01": support2_recall_gain >= -0.01,
                "hard4_bootstrap_lower_gt_0": hard4_ci[0] > 0.0,
            },
        },
        "provenance": {
            "grounded": True,
            "inputs": [
                {"kind": "source", "path": str(DATASET), "sha256": dataset_sha},
                {"kind": "harness", "path": str(script_path), "sha256": script_sha},
                {"kind": "preregistration", "path": str(PREREG), "sha256": sha256_file(PREREG)},
            ],
            "data_manifest": {
                "dataset": "2WikiMultihopQA validation JSONL",
                "dataset_rows": 12576,
                "selected_rows": N_Q,
                "selected_ids_sha256": sample_sha,
                "seed": SEED,
                "pool_documents": len(titles),
                "four_support_rows": len(hard4),
                "two_support_rows": len(support2),
            },
            "equal_compute": {
                "verified": True,
                "shared_views": ["title_cosine", "body_cosine", "nary_entity_appnp"],
                "scored_query_document_pairs_per_arm": N_Q * len(titles) * 3,
                "difference_only": "early normalized scalar sum vs weighted reciprocal-rank late readout",
                "reader_calls": 0,
            },
        },
        "harness": {
            "command": (
                "/Users/lagyeongjun/CD/bhgman_tool/.venv/bin/python "
                "HSWM/prom_search_hswm/prom_p5_multiview_hardhop.py"
            ),
            "cwd": str(HERE.parents[1]),
            "git_head": git_head(),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": np.__version__,
                "sentence_transformers": st_version,
                "model": model_name,
                "model_cache": str(cache),
                "hf_home": os.environ.get("HF_HOME", ""),
            },
            "started_at": started_at,
            "finished_at": finished_at,
            "exit_code": 0,
        },
        "findings": [
            {
                "proposal": "Keep anchor/evidence/bridge fields separate until readout only if the hard4 preregistered margin is positive.",
                "supported_by": ["measurement.hard4", "provenance.equal_compute"],
            },
            {
                "proposal": "Treat any benefit limited to one 2Wiki stratum as domain-conditional rather than a general HSWM upgrade.",
                "supported_by": ["measurement.by_dataset_hop_label"],
            },
        ],
        "limitations": [
            "One benchmark and one deterministic sample; no answer generator is used.",
            "Query routing is fixed lexical patterning, not a learned ParallaxRAG-style gate.",
            "Entity extraction is capitalization-based and English-specific.",
            "Direct-edge deletion and private-ID anti-memorization remain a separate falsifier.",
        ],
        "diagnostics": {
            "route_counts": dict(sorted(route_counts.items())),
            "hyperedges": n_hyperedges,
            "top_k": TOP_K,
            "fullchain_k": FULLCHAIN_K,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "evidence": str(OUTPUT),
        "evidence_sha256": sha256_file(OUTPUT),
        "metric_value": evidence["measurement"]["value"],
        "novel_value": evidence["measurement"]["novel_value"],
        "hard4_n": len(hard4),
        "support2_n": len(support2),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
