#!/usr/bin/env python3
"""Development-only B2.2 action-space diagnostics over frozen B2.1 scorepacks.

The script prints JSON and never writes a result file.  It computes two distinct
posthoc quantities:

1. a per-query gold oracle that may reorder the frozen MERGED top-20; and
2. a conservative query-independent sparse suppression patch fitted on train
   only and read unchanged on calibration/test.

Neither quantity is preregistered evidence.  The v1 scorepacks contain only
top-20 final scores, so the script cannot establish full-candidate weight
behavior or a confirmatory HSWM claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Sequence

import numpy as np

from prom_b21_learned_router import (
    PRIMARY_SEED,
    SPLIT_SEEDS,
    component_membership,
    make_split,
    read_scorepack,
    sha256_file,
)


SCHEMA = "hswm-b22-action-space-diagnostic/v1"
SLOW_SCALE = 0.15
LEVELS = (math.log(0.9), math.log(0.7), math.log(0.5))
MAX_EDITS = 32
MIN_NONGOLD_COMPONENTS = 3


def _recall(record: dict, patch: dict[str, float]) -> float:
    ids = record["arms"]["merged"]["ids"]
    scores = record["arms"]["merged"]["scores"]
    rescored = [
        float(score) + SLOW_SCALE * patch.get(edge_id, 0.0)
        for edge_id, score in zip(ids, scores)
    ]
    order = sorted(range(len(ids)), key=lambda i: (-rescored[i], ids[i]))[:10]
    gold = set(record["gold"])
    return len(gold & {ids[i] for i in order}) / len(gold)


def _mean_recall(records: Sequence[dict], indices: Sequence[int],
                 patch: dict[str, float]) -> float:
    return float(np.mean([_recall(records[i], patch) for i in indices]))


def fit_static_patch(records: Sequence[dict], train: Sequence[int]) -> dict:
    """Greedy train-only diagnostic with a fully deterministic tie break."""
    membership = component_membership(records, train)
    train_gold: set[str] = set()
    nongold_components: dict[str, set[str]] = {}
    for i in train:
        record = records[i]
        gold = set(record["gold"])
        train_gold.update(gold)
        for edge_id in record["arms"]["merged"]["ids"]:
            if edge_id not in gold:
                nongold_components.setdefault(edge_id, set()).add(membership[i])
    eligible = sorted(
        edge_id
        for edge_id, components in nongold_components.items()
        if len(components) >= MIN_NONGOLD_COMPONENTS and edge_id not in train_gold
    )

    patch: dict[str, float] = {}
    current = _mean_recall(records, train, patch)
    for _ in range(MAX_EDITS):
        best: tuple[float, float, str, float, float] | None = None
        for edge_id in eligible:
            if edge_id in patch:
                continue
            for level in LEVELS:
                candidate = dict(patch)
                candidate[edge_id] = level
                value = _mean_recall(records, train, candidate)
                gain = value - current
                # max gain; then least magnitude; then lexical edge ID; then level.
                key = (gain, -abs(level), edge_id, level, value)
                if best is None:
                    best = key
                    continue
                if gain > best[0] + 1e-15:
                    best = key
                elif abs(gain - best[0]) <= 1e-15:
                    candidate_tie = (abs(level), edge_id, level)
                    best_tie = (abs(best[3]), best[2], best[3])
                    if candidate_tie < best_tie:
                        best = key
        if best is None or best[0] <= 1e-15:
            break
        _, _, edge_id, level, current = best
        patch[edge_id] = level
    return {
        "eligible_edges": len(eligible),
        "patch": patch,
        "patch_sha256": hashlib.sha256(json.dumps(
            patch, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }


def diagnose(path: Path, dataset: str) -> dict:
    scorepack = read_scorepack(path)
    if scorepack.get("dataset") != dataset or scorepack.get("salt") != "legacy":
        raise ValueError(f"unexpected scorepack identity: {path}")
    records = scorepack["records"]
    primary_split = make_split(records, dataset, PRIMARY_SEED)

    oracle = {}
    for part, indices in primary_split.items():
        base = []
        top20 = []
        has_tail_gold = 0
        for i in indices:
            record = records[i]
            ids = record["arms"]["merged"]["ids"]
            gold = set(record["gold"])
            base.append(len(gold & set(ids[:10])) / len(gold))
            top20.append(len(gold & set(ids[:20])) / len(gold))
            has_tail_gold += bool(gold & set(ids[10:20]))
        oracle[part] = {
            "n": len(indices),
            "merged_recall10": round(float(np.mean(base)), 6),
            "top20_rerank_gold_oracle_recall10": round(float(np.mean(top20)), 6),
            "oracle_headroom": round(float(np.mean(np.asarray(top20) - np.asarray(base))), 6),
            "queries_with_gold_in_ranks_11_20": has_tail_gold,
        }

    static = []
    for seed in SPLIT_SEEDS:
        split = make_split(records, dataset, seed)
        fitted = fit_static_patch(records, split["train"])
        patch = fitted.pop("patch")
        deltas = {}
        recalls = {}
        for part, indices in split.items():
            baseline = _mean_recall(records, indices, {})
            learned = _mean_recall(records, indices, patch)
            recalls[part] = round(learned, 6)
            deltas[part] = round(learned - baseline, 6)
        static.append({
            "seed": seed,
            **fitted,
            "edited_edges": len(patch),
            "level_counts": {
                str(level): count
                for level, count in sorted(Counter(patch.values()).items())
            },
            "recall10": recalls,
            "delta_vs_merged": deltas,
        })
    return {
        "scorepack_sha256": sha256_file(path),
        "top20_query_rerank_oracle": oracle,
        "train_only_static_sparse_suppression": static,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--2wiki", type=Path, required=True)
    parser.add_argument("--musique", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "schema": SCHEMA,
        "status": "DIAGNOSTIC_NO_CLAIM",
        "parameters": {
            "slow_scale": SLOW_SCALE,
            "levels": list(LEVELS),
            "max_edits": MAX_EDITS,
            "min_nongold_train_components": MIN_NONGOLD_COMPONENTS,
            "candidate_buffer": 20,
            "readout_k": 10,
        },
        "datasets": {
            "2wiki": diagnose(args.__dict__["2wiki"], "2wiki"),
            "musique": diagnose(args.musique, "musique"),
        },
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
