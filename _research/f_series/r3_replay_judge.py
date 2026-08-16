"""R3 replay judge — 서버 재현명령('python <script> <result_path>')용 순수 numpy 재채점기.

r3_dump_replay_artifacts.py 가 저장한 아티팩트(static 점수행렬 + rows 메타 + universe 원문)만으로
primary metric(sparse hard-hop walk−flat best-trace recall@10)을 재생성해 stdout 에
`metric=<값>` 한 줄만 출력한다(파서 계약, 부가정보는 stderr).

torch/네트워크/임베딩 모델 없음 — numpy 만 있는 컨테이너(HSWM_LOCAL_RECORD-01)에서 실행 가능.
argv 의 result_path 는 재현명령 형식상 전달되지만 본 judge 는 아티팩트 자급이라 무시한다.
결정론: np.load 바이트 동일 + IEEE per-op 동일 + argsort stable + Python random(seed 고정).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import REPO_ROOT

import numpy as np

import typed_composition as typed
from r1_predicate_alias import build_predicate_alias_index, query_term_closure
from r3_phantom_ingest import build_graph
from .t3_score_null import walk_scores_strict
from .r3_walk_regime import (
    TOP_K, SEED_K, HARD_HOP, UNIVERSES, best_trace_recall,
)

DATA = REPO_ROOT / "_research" / "r3_replay"


def rescore(uni: str) -> tuple[float, dict]:
    articles = json.loads(
        (DATA / "universes" / uni / "articles.json").read_text(encoding="utf-8"))
    target_ids, graph, _, _, _ = build_graph(articles)
    static_all = np.load(DATA / f"static_{uni}.npy")
    rows = json.loads((DATA / f"rows_{uni}.json").read_text(encoding="utf-8"))

    policy = typed.TypedCompositionPolicyV1(seed_k=SEED_K)
    alias_index = build_predicate_alias_index(
        [a.source_predicate.exact for a in graph.arcs]
        + [a.target_predicate.exact for a in graph.arcs
           if a.target_predicate is not None])

    per_query = []
    for qi, r in enumerate(rows):
        static = static_all[qi]
        order_flat = np.argsort(-static, kind="stable")[:TOP_K]
        flat_ids = [target_ids[i] for i in order_flat]
        seeds = tuple(int(i) for i in np.argsort(-static, kind="stable")[:SEED_K])
        q_terms = query_term_closure(r["question"])
        _, k2, _, _ = walk_scores_strict(
            q_terms, static, graph, policy, seeds=seeds, alias_index=alias_index)
        order_walk = np.argsort(-k2, kind="stable")[:TOP_K]
        walk_ids = [target_ids[i] for i in order_walk]
        golds = [set(g) for g in r["golds"]]
        per_query.append({
            "hop": r["hop"],
            "flat": best_trace_recall(flat_ids, golds),
            "walk": best_trace_recall(walk_ids, golds),
        })

    hard = [x for x in per_query if x["hop"] >= HARD_HOP]
    deltas = [x["walk"] - x["flat"] for x in hard]
    value = round(sum(deltas) / len(deltas), 6) if deltas else 0.0
    return value, {"n_hard": len(hard),
                   "flat_hard": round(sum(x["flat"] for x in hard) / len(hard), 6) if hard else 0.0,
                   "walk_hard": round(sum(x["walk"] for x in hard) / len(hard), 6) if hard else 0.0}


def main() -> int:
    per_uni = {}
    for uni in sorted(UNIVERSES):
        per_uni[uni] = rescore(uni)
    sparse = per_uni["sparse_t200_fk1"][0]
    dense = per_uni["dense_t200_fk9"][0]
    novel = round(sparse - dense, 6)
    print(f"metric={sparse}", flush=True)  # stdout 순수 — 서버 metric 파서 계약
    print(json.dumps({
        "novel_density_monotonicity": novel,
        "sparse": sparse, "dense": dense,
        "per_universe": {u: {"delta": v[0], **v[1]} for u, v in per_uni.items()},
    }, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
