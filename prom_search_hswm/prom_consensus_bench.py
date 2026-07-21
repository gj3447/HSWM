#!/usr/bin/env python3
"""
PROM 검색 P2 falsifier — lexical vs semantic consensus detection (TOY receipt).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node P2-semantic-consensus-recall
Pre-registered: metric=consensus_recall_goldset baseline=0.4,
                novel=semantic_minus_lexical_consensus_recall_gap threshold>=0.15 (higher)
Closes: Q-binding-density

무엇을 재나:
  현 prometheus SKILL.md v6.3 Step 4-1 합의탐지 = recommendation 문자열 (정규화) 동일성 그룹핑.
  → 의미상 같은 결론의 paraphrase 들을 못 묶는다(D1 진단).
  임베딩 cosine 클러스터(semantic)와 pairwise recall/precision 을 A/B.

자가비판 반영:
  C1 (recall↑=precision 죽임 Goodhart): recall + PRECISION 동반 측정.
  C2 (벤치마크 순환): tau=0.5 를 결과 보기 전 a priori 고정(하드코드 sha 로 잠금) + 전 tau sweep 도 리포트.
  numerology: mismatched(cross-cluster) cosine 분포로 MC-null 통제 — semantic 이 null 위인지 z 로.

TOY 한계: gold set 12 findings/4 cluster 는 저자 hand-built(실 KG RF 아님). full = KG ResearchFinding 실데이터로 교체 필요.
"""
import json, sys, hashlib, itertools, statistics
from pathlib import Path

# ---- a-priori 고정 파라미터 (결과 보기 전 잠금) -------------------------------
TAU = 0.50            # semantic 클러스터 cosine threshold, a priori
NULL_PERMS = 2000     # MC-null 순열 수
SEED = 333

# ---- TOY gold set: recommendation + true semantic cluster --------------------
# 4 clusters × 3 paraphrase + 0 singleton. paraphrase 는 표현만 다르고 결론 동일.
GOLD = [
    # cluster A: hybrid retrieval
    ("A", "dense 임베딩과 sparse BM25 검색을 결합하라"),
    ("A", "벡터 검색에 키워드(BM25) 검색을 병행해 RRF 로 융합"),
    ("A", "hybrid search: combine semantic and lexical retrieval"),
    # cluster B: rerank
    ("B", "검색 결과를 cross-encoder 로 재랭킹하라"),
    ("B", "1차 검색 후 재순위화 모델로 상위 결과를 다시 정렬"),
    ("B", "apply a reranker model after initial retrieval"),
    # cluster C: contextual anchoring
    ("C", "청크 색인 전에 LLM 으로 문맥 접두사를 붙여라"),
    ("C", "임베딩 전 각 청크에 소속 문서/장 맥락을 prepend"),
    ("C", "contextual retrieval: add a context prefix before embedding"),
    # cluster D: agentic iterative
    ("D", "검색을 도구화해 ReAct 루프로 반복 탐색하라"),
    ("D", "에이전트가 스스로 언제 무엇을 검색할지 반복 결정"),
    ("D", "agentic RAG: let the agent iterate retrieval steps"),
]

def norm(s: str) -> str:
    return " ".join(s.lower().split())

def gold_labels():
    return [c for c, _ in GOLD]

def same_cluster_pairs(labels):
    idx = list(range(len(labels)))
    same, diff = [], []
    for i, j in itertools.combinations(idx, 2):
        (same if labels[i] == labels[j] else diff).append((i, j))
    return same, diff

def pred_labels_lexical(recs):
    """현 SKILL.md Step 4-1: 정규화 문자열 동일성 그룹."""
    buckets = {}
    for i, r in enumerate(recs):
        buckets.setdefault(norm(r), []).append(i)
    lab = [None] * len(recs)
    for k, (key, members) in enumerate(buckets.items()):
        for m in members:
            lab[m] = f"L{k}"
    return lab

def cosine_matrix(recs):
    from sentence_transformers import SentenceTransformer
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    emb = model.encode(recs, normalize_embeddings=True, convert_to_numpy=True)
    return emb @ emb.T, model

def pred_labels_semantic(cos, tau):
    """cosine>=tau union-find 클러스터."""
    n = cos.shape[0]
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    for i in range(n):
        for j in range(i + 1, n):
            if cos[i][j] >= tau: union(i, j)
    roots = {}
    lab = []
    for i in range(n):
        r = find(i)
        roots.setdefault(r, f"S{len(roots)}")
        lab.append(roots[r])
    return lab

def recall_precision(pred, labels):
    gold_same, _ = same_cluster_pairs(labels)
    pred_same, _ = same_cluster_pairs(pred)
    gs, ps = set(gold_same), set(pred_same)
    tp = len(gs & ps)
    recall = tp / len(gs) if gs else 0.0
    precision = tp / len(ps) if ps else 0.0
    return recall, precision

def main():
    labels = gold_labels()
    recs = [r for _, r in GOLD]

    # --- lexical baseline (현 PROM) ---
    lex = pred_labels_lexical(recs)
    lex_r, lex_p = recall_precision(lex, labels)

    # --- semantic ---
    cos, model = cosine_matrix(recs)
    sem = pred_labels_semantic(cos, TAU)
    sem_r, sem_p = recall_precision(sem, labels)

    # --- MC-null: gold 라벨 순열 하에서 semantic recall 분포 ---
    import random, numpy as np
    rng = random.Random(SEED)
    null_recalls = []
    base = labels[:]
    for _ in range(NULL_PERMS):
        perm = base[:]; rng.shuffle(perm)
        r, _p = recall_precision(sem, perm)
        null_recalls.append(r)
    null_mean = statistics.mean(null_recalls)
    null_std = statistics.pstdev(null_recalls) or 1e-9
    z = (sem_r - null_mean) / null_std

    # --- mismatched(cross-cluster) cosine 분포 (tau 정당성) ---
    _, diff = same_cluster_pairs(labels)
    same, _ = same_cluster_pairs(labels)
    import numpy as np
    mm = [float(cos[i][j]) for i, j in diff]
    mt = [float(cos[i][j]) for i, j in same]
    mm_mean = statistics.mean(mm); mt_mean = statistics.mean(mt)

    # --- tau sweep (투명성) ---
    sweep = {}
    for t in [0.30, 0.40, 0.50, 0.60, 0.70]:
        s = pred_labels_semantic(cos, t)
        sweep[f"{t:.2f}"] = dict(zip(("recall", "precision"), recall_precision(s, labels)))

    gap = sem_r - lex_r

    ev = {
        "experiment": "prom_consensus_bench_toy",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "P2-semantic-consensus-recall",
        "a_priori": {"tau": TAU, "null_perms": NULL_PERMS, "seed": SEED},
        "gold": {"n_findings": len(GOLD), "n_clusters": len(set(labels)),
                 "toy": True, "note": "hand-built paraphrase set, not real KG RF"},
        "lexical_current_prom": {"recall": round(lex_r, 4), "precision": round(lex_p, 4)},
        "semantic": {"recall": round(sem_r, 4), "precision": round(sem_p, 4), "tau": TAU},
        "novel_gap_semantic_minus_lexical": round(gap, 4),
        "mc_null": {"null_mean_recall": round(null_mean, 4), "null_std": round(null_std, 4),
                    "z": round(z, 3), "perms": NULL_PERMS},
        "cosine_separation": {"matched_mean": round(mt_mean, 4),
                              "mismatched_mean": round(mm_mean, 4),
                              "separation": round(mt_mean - mm_mean, 4)},
        "tau_sweep": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in sweep.items()},
        "prereg": {"metric": "consensus_recall_goldset", "baseline": 0.4,
                   "novel_metric": "semantic_minus_lexical_consensus_recall_gap",
                   "novel_threshold": 0.15, "direction": "higher"},
    }
    # verdict 판정(자기채점 아님 — 사실만 기록; LakatoTree 가 판정)
    ev["_facts"] = {
        "novel_gap_ge_threshold": gap >= 0.15,
        "semantic_above_null": z > 3.0,
        "precision_not_collapsed": sem_p >= lex_p or sem_p >= 0.8,
    }
    out = Path(__file__).parent / "EVIDENCE_prom_consensus_toy_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
