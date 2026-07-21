#!/usr/bin/env python3
"""
PROM 검색 P2b — REAL KG data: lexical vs semantic consensus (overlapping gold).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node P2b-real-kg-gfs
Gold = Neo4j home canon 0.25, cycle prom16-gfs-2026-05-21 의 :SUPPORTED_BY consensus.
       13 unique RF, 8 consensus, **OVERLAPPING**(한 RF 여러 consensus = hypergraph, not partition).

핵심: 현 PROM Step4 합의탐지는 문자열동일성 → disjoint partition. 하지만 실 gold 는
      overlapping hypergraph (RF C2 가 sm/cb/hdfs/ec 4개 동시 소속). partition 모델은
      구조적으로 이걸 표현 불가 = HSWM(Hypergraph Semantic Weight Map)이 올바른 형태.
      metric = pairwise 공동소속(co-membership) recall/precision (overlapping-safe).

자가비판: C1 precision 동반, numerology MC-null, C2 gold=AI-curated(약한 순환) 명시.
a-priori τ=0.50 (결과 전 잠금).
"""
import json, sys, itertools, statistics, random
from pathlib import Path

TAU = 0.50
NULL_PERMS = 2000
SEED = 333
HERE = Path(__file__).parent

def norm(s): return " ".join(s.lower().split())

def load_gold():
    g = json.loads((HERE / "data" / "real_gold_gfs.json").read_text())
    rfs = [f["rf"] for f in g["findings"]]
    texts = [f["text"] for f in g["findings"]]
    clusters = [set(f["clusters"]) for f in g["findings"]]
    return rfs, texts, clusters

def gold_co_pairs(clusters):
    """overlapping gold: pair (i,j) is 'same' if they share >=1 consensus cluster."""
    idx = range(len(clusters))
    same, diff = [], []
    for i, j in itertools.combinations(idx, 2):
        (same if clusters[i] & clusters[j] else diff).append((i, j))
    return set(same), set(diff)

def lexical_pairs(texts):
    """현 PROM: 정규화 문자열 동일 pair."""
    ps = set()
    for i, j in itertools.combinations(range(len(texts)), 2):
        if norm(texts[i]) == norm(texts[j]):
            ps.add((i, j))
    return ps

def cosine(texts):
    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(SEED)
    m = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    emb = m.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return emb @ emb.T

def semantic_pairs(cos, tau):
    ps = set()
    n = cos.shape[0]
    for i, j in itertools.combinations(range(n), 2):
        if cos[i][j] >= tau:
            ps.add((i, j))
    return ps

def rp(pred, gold_same):
    tp = len(pred & gold_same)
    recall = tp / len(gold_same) if gold_same else 0.0
    precision = tp / len(pred) if pred else 0.0
    return recall, precision

def main():
    rfs, texts, clusters = load_gold()
    gold_same, gold_diff = gold_co_pairs(clusters)

    lex = lexical_pairs(texts)
    lex_r, lex_p = rp(lex, gold_same)

    cos = cosine(texts)
    sem = semantic_pairs(cos, TAU)
    sem_r, sem_p = rp(sem, gold_same)

    # MC-null: permute gold cluster assignment(shuffle clusters over RFs), recompute recall
    rng = random.Random(SEED)
    nulls = []
    base = clusters[:]
    for _ in range(NULL_PERMS):
        perm = base[:]; rng.shuffle(perm)
        gs, _ = gold_co_pairs(perm)
        nulls.append(rp(sem, gs)[0])
    nmean = statistics.mean(nulls); nstd = statistics.pstdev(nulls) or 1e-9
    z = (sem_r - nmean) / nstd

    # cosine separation on gold same vs diff
    same_cos = [float(cos[i][j]) for i, j in gold_same]
    diff_cos = [float(cos[i][j]) for i, j in gold_diff]
    sep = (statistics.mean(same_cos) - statistics.mean(diff_cos)) if same_cos and diff_cos else 0.0

    sweep = {}
    for t in [0.30, 0.40, 0.50, 0.60, 0.70]:
        s = semantic_pairs(cos, t)
        r, p = rp(s, gold_same)
        sweep[f"{t:.2f}"] = {"recall": round(r, 4), "precision": round(p, 4)}

    gap = sem_r - lex_r
    ev = {
        "experiment": "prom_consensus_real_gfs",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "P2b-real-kg-gfs",
        "a_priori": {"tau": TAU, "null_perms": NULL_PERMS, "seed": SEED},
        "gold": {"source": "Neo4j 0.25 prom16-gfs-2026-05-21 :SUPPORTED_BY", "n_rf": len(rfs),
                 "n_clusters": 8, "overlapping": True,
                 "gold_same_pairs": len(gold_same), "gold_diff_pairs": len(gold_diff),
                 "curated_by": "AI (parent Claude Step4 KARMA) — weak circularity per C2"},
        "lexical_current_prom": {"recall": round(lex_r, 4), "precision": round(lex_p, 4),
                                 "note": "partition model cannot represent overlapping hypergraph gold"},
        "semantic": {"recall": round(sem_r, 4), "precision": round(sem_p, 4), "tau": TAU},
        "novel_gap_semantic_minus_lexical": round(gap, 4),
        "mc_null": {"null_mean_recall": round(nmean, 4), "null_std": round(nstd, 4), "z": round(z, 3)},
        "cosine_separation_same_minus_diff": round(sep, 4),
        "tau_sweep": sweep,
        "structural_finding": "real PROM consensus is OVERLAPPING (hypergraph); current Step4 partition-by-string-equality is structurally wrong shape. HSWM = correct form.",
        "prereg": {"metric": "consensus_recall_goldset", "baseline": 0.4,
                   "novel_metric": "semantic_minus_lexical_consensus_recall_gap",
                   "novel_threshold": 0.15, "direction": "higher"},
        "_facts": {"novel_gap_ge_threshold": gap >= 0.15, "semantic_above_null": z > 3.0,
                   "precision_ok": sem_p >= 0.5},
    }
    out = HERE / "evidence" / "EVIDENCE_prom_consensus_real_gfs_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
