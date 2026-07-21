#!/usr/bin/env python3
"""
PROM 검색 ML1 — USER 가설: "레이어가 여러 층이 아니어서 P2b가 실패했다."

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML1-multilayer-hypothesis
P2b(단일층: recommendation 텍스트 1개 임베딩) = cosine separation −0.038(음수), z=0.19(랜덤무구별).
진단: 단일층이 overlapping hypergraph(한 RF가 thesis 여럿 소속)를 뭉갰다.
가설: 각 RF를 8개 thesis 층에 투영(multi-layer co-activation) → 겹침 구조 되살아난다.

측정:
  single_layer (P2b 재현): raw recommendation cosine, co-member = cos>=τ.
  multi_layer: RF를 8 thesis-anchor 층에 투영(w_i^L=cos(RF_i, thesis_L)).
               co-member(i,j) = ∃L: w_i^L>=t AND w_j^L>=t (같은 thesis 場 공동활성).
               shared-field sim(i,j) = max_L min(w_i^L, w_j^L).
  둘 다: overlapping gold 대비 recall/precision + separation(same−diff) + MC-null z.

자가비판: 층 앵커 = gold consensus thesis 유래 = feasibility/upper-bound(blind 층 발견 아님, C2).
         이게 통과해야 "multi-layer가 원리상 겹침을 살린다"가 성립 — 그 다음이 blind 층.
a-priori: τ=0.50(P2b동일), layer_t=0.35.
"""
import json, sys, itertools, statistics, random
from pathlib import Path

TAU = 0.50
LAYER_T = 0.35
NULL_PERMS = 2000
SEED = 333
HERE = Path(__file__).parent

# 8 thesis 층 앵커 (consensus 이름서 유래 = gold-derived, feasibility test)
THESES = {
    "sm": "GFS single-master architecture was superseded by distributed metadata like Colossus",
    "cb": "Colossus and Bigtable provide the distributed metadata layer replacing the single master",
    "ra": "GFS record-append semantics are error-prone at-least-once and were retracted",
    "hdfs": "HDFS is a direct open-source clone of the GFS architecture",
    "ec": "erasure coding replaces 3x replication for the capacity tier",
    "lw": "the lakehouse and WORM object store is a reincarnation of the GFS lineage",
    "aw": "AI training workloads re-converge on the original GFS design constraints",
    "sf": "the GFS 64MB chunk size causes a small-file pathology",
}

def norm(s): return " ".join(s.lower().split())

def load():
    g = json.loads((HERE / "data" / "real_gold_gfs.json").read_text())
    rfs = [f["rf"] for f in g["findings"]]
    texts = [f["text"] for f in g["findings"]]
    clusters = [set(f["clusters"]) for f in g["findings"]]
    return rfs, texts, clusters

def gold_pairs(clusters):
    same, diff = set(), set()
    for i, j in itertools.combinations(range(len(clusters)), 2):
        (same if clusters[i] & clusters[j] else diff).add((i, j))
    return same, diff

def rp(pred, gold_same):
    tp = len(pred & gold_same)
    r = tp / len(gold_same) if gold_same else 0.0
    p = tp / len(pred) if pred else 0.0
    return r, p

def main():
    rfs, texts, clusters = load()
    gold_same, gold_diff = gold_pairs(clusters)
    n = len(rfs)

    from sentence_transformers import SentenceTransformer
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    rf_emb = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    layer_names = list(THESES)
    layer_emb = model.encode([THESES[k] for k in layer_names], normalize_embeddings=True, convert_to_numpy=True)

    # ---- single layer (P2b 재현) ----
    cos = rf_emb @ rf_emb.T
    single = {(i, j) for i, j in itertools.combinations(range(n), 2) if cos[i][j] >= TAU}
    s_r, s_p = rp(single, gold_same)
    s_same = [float(cos[i][j]) for i, j in gold_same]
    s_diff = [float(cos[i][j]) for i, j in gold_diff]
    s_sep = statistics.mean(s_same) - statistics.mean(s_diff)

    # ---- multi layer ----
    W = rf_emb @ layer_emb.T   # (n, 8) 층별 가중
    def shared(i, j):
        return max(min(float(W[i][L]), float(W[j][L])) for L in range(len(layer_names)))
    def coact(i, j):
        return any(W[i][L] >= LAYER_T and W[j][L] >= LAYER_T for L in range(len(layer_names)))
    multi = {(i, j) for i, j in itertools.combinations(range(n), 2) if coact(i, j)}
    m_r, m_p = rp(multi, gold_same)
    m_same = [shared(i, j) for i, j in gold_same]
    m_diff = [shared(i, j) for i, j in gold_diff]
    m_sep = statistics.mean(m_same) - statistics.mean(m_diff)

    # ---- MC-null on multi recall ----
    rng = random.Random(SEED)
    nulls = []
    for _ in range(NULL_PERMS):
        perm = clusters[:]; rng.shuffle(perm)
        gs, _ = gold_pairs(perm)
        nulls.append(rp(multi, gs)[0])
    nmean = statistics.mean(nulls); nstd = statistics.pstdev(nulls) or 1e-9
    m_z = (m_r - nmean) / nstd

    ev = {
        "experiment": "prom_consensus_multilayer_gfs",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "ML1-multilayer-hypothesis",
        "a_priori": {"tau": TAU, "layer_t": LAYER_T, "null_perms": NULL_PERMS, "seed": SEED},
        "gold": {"n_rf": n, "overlapping": True, "gold_same_pairs": len(gold_same),
                 "gold_diff_pairs": len(gold_diff), "n_layers": len(layer_names)},
        "single_layer_P2b": {"recall": round(s_r, 4), "precision": round(s_p, 4),
                             "separation_same_minus_diff": round(s_sep, 4)},
        "multi_layer": {"recall": round(m_r, 4), "precision": round(m_p, 4),
                        "separation_same_minus_diff": round(m_sep, 4),
                        "mc_null_z": round(m_z, 3), "null_mean": round(nmean, 4)},
        "hypothesis_test": {
            "separation_flipped_positive": (s_sep < 0) and (m_sep > 0),
            "multi_sep_gt_single_sep": m_sep > s_sep,
            "multi_above_null_z3": m_z > 3.0,
        },
        "caveat": "층 앵커=gold thesis 유래=feasibility/upper-bound. 통과=multi-layer 원리 성립→차기 blind 층 발견(internet+KG 유래). 미통과=multi-layer도 안 됨.",
        "prereg": {"metric": "multilayer_consensus_recall", "baseline_single_layer_z": 0.19,
                   "novel_metric": "multilayer_separation_same_minus_diff", "novel_threshold": 0.0,
                   "direction": "higher", "single_layer_separation": -0.0381},
    }
    out = HERE / "evidence" / "EVIDENCE_prom_consensus_multilayer_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
