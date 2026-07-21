#!/usr/bin/env python3
"""
PROM 검색 ML2 — 제대로 된 multi-layer A/B (balanced gold, USER "여러 층" 가설).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML2-multilayer-ab-badiou
Gold = prom-24-badiou-expanded (24 RF, 10 consensus), 2축 role×topic hypergraph, 균형(GFS 미지배).

3 arms (동일 gold, 동일 co-membership 판정틀):
  A single-layer   : raw RF-text cosine, co-member = cos>=τ.  (P2b 방식)
  B multi BLIND    : KMeans(K) on RF embeddings → centroid=층. project → co-member = ∃층 both>=t. (무감독)
  C multi STRUCTURED: 층 = 10 consensus thesis(3 role + 7 topic) 앵커. (gold축 유래 = 상한/feasibility)

핵심 질문: role-cluster(cross-topic, 단일 텍스트 임베딩이 못 봄)를 다층이 되살리나?
  → separation(same−diff)·MC-null z 로 arm 간 비교. A가 못 살린 걸 B/C가 살리면 USER 가설 지지.
자가비판: C=gold축 유래 상한(거의 tautological). 진짜 판정 = B(blind) > A 인가. a-priori τ=0.5,t=0.35,K=10,seed=333.
"""
import json, sys, itertools, statistics, random
from pathlib import Path

TAU = 0.50
LAYER_T = 0.35
K_BLIND = 10
NULL_PERMS = 2000
SEED = 333
HERE = Path(__file__).parent

ROLE_ANCHORS = {
    "primary": "primary canonical exposition of Badiou's own doctrine and primary text",
    "secondary": "secondary scholarly consensus and commentary from multiple schools of interpreters",
    "critique": "critical adversarial objections and ranked critiques from opposing philosophers",
}
TOPIC_ANCHORS = {
    "event": "the event as violation of the ZFC foundation regularity axiom, self-membership",
    "forcing": "Cohen forcing, generic filter, ground model, the forcing-event paradox",
    "ethics": "ethics of truth, the three figures of evil, simulacrum betrayal disaster, anti-Levinas",
    "inaesthetics": "inaesthetics, art as a truth procedure, poem theater cinema dance",
    "lacan": "the link to Lacan, psychoanalysis, the subject, suture, antiphilosophy",
    "low": "Logics of Worlds, complete Heyting algebra, topos of sheaves, transcendental",
    "pedagogy": "antiphilosophy as pedagogical method, self-negation, Nietzsche Wittgenstein Lacan seminars",
}

def load():
    g = json.loads((HERE / "data" / "gold_badiou24.json").read_text())
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
    return (tp / len(gold_same) if gold_same else 0.0), (tp / len(pred) if pred else 0.0)

def mc_null_z(pred, clusters, base_recall):
    rng = random.Random(SEED)
    nulls = []
    for _ in range(NULL_PERMS):
        perm = clusters[:]; rng.shuffle(perm)
        gs, _ = gold_pairs(perm)
        nulls.append(rp(pred, gs)[0])
    m = statistics.mean(nulls); s = statistics.pstdev(nulls) or 1e-9
    return (base_recall - m) / s, m

def coact_pairs(W, n, t):
    pred = set()
    for i, j in itertools.combinations(range(n), 2):
        if any(W[i][L] >= t and W[j][L] >= t for L in range(W.shape[1])):
            pred.add((i, j))
    return pred

def shared_sim(W, i, j):
    return max(min(float(W[i][L]), float(W[j][L])) for L in range(W.shape[1]))

def arm_report(pred, sim_fn, gold_same, gold_diff, clusters):
    r, p = rp(pred, gold_same)
    same = [sim_fn(i, j) for i, j in gold_same]
    diff = [sim_fn(i, j) for i, j in gold_diff]
    sep = (statistics.mean(same) - statistics.mean(diff)) if same and diff else 0.0
    z, nmean = mc_null_z(pred, clusters, r)
    return {"recall": round(r, 4), "precision": round(p, 4),
            "separation_same_minus_diff": round(sep, 4),
            "mc_null_z": round(z, 3), "null_mean": round(nmean, 4)}

def main():
    rfs, texts, clusters = load()
    n = len(rfs)
    gold_same, gold_diff = gold_pairs(clusters)

    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    emb = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    cos = emb @ emb.T

    # --- Arm A: single layer ---
    A_pred = {(i, j) for i, j in itertools.combinations(range(n), 2) if cos[i][j] >= TAU}
    A = arm_report(A_pred, lambda i, j: float(cos[i][j]), gold_same, gold_diff, clusters)

    # --- Arm B: blind KMeans layers ---
    km = KMeans(n_clusters=K_BLIND, random_state=SEED, n_init=10).fit(emb)
    cent = km.cluster_centers_
    cent = cent / (np.linalg.norm(cent, axis=1, keepdims=True) + 1e-9)
    WB = emb @ cent.T
    B_pred = coact_pairs(WB, n, LAYER_T)
    B = arm_report(B_pred, lambda i, j: shared_sim(WB, i, j), gold_same, gold_diff, clusters)

    # --- Arm C: structured (gold-axis) layers ---
    anchor_texts = list(ROLE_ANCHORS.values()) + list(TOPIC_ANCHORS.values())
    aemb = model.encode(anchor_texts, normalize_embeddings=True, convert_to_numpy=True)
    WC = emb @ aemb.T
    C_pred = coact_pairs(WC, n, LAYER_T)
    C = arm_report(C_pred, lambda i, j: shared_sim(WC, i, j), gold_same, gold_diff, clusters)

    ev = {
        "experiment": "prom_multilayer_ab_badiou24",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "ML2-multilayer-ab-badiou",
        "a_priori": {"tau": TAU, "layer_t": LAYER_T, "k_blind": K_BLIND, "seed": SEED},
        "gold": {"n_rf": n, "gold_same_pairs": len(gold_same), "gold_diff_pairs": len(gold_diff),
                 "same_frac": round(len(gold_same) / (len(gold_same) + len(gold_diff)), 3),
                 "axes": "role(3) x topic(7)", "balanced_vs_gfs": "GFS same_frac 0.87 → badiou 확인값 아래"},
        "arm_A_single_layer": A,
        "arm_B_multi_blind_kmeans": B,
        "arm_C_multi_structured_goldaxis": C,
        "hypothesis_test": {
            "B_beats_A_separation": B["separation_same_minus_diff"] > A["separation_same_minus_diff"],
            "B_beats_A_null_z": B["mc_null_z"] > A["mc_null_z"],
            "C_beats_A_separation": C["separation_same_minus_diff"] > A["separation_same_minus_diff"],
            "any_multi_above_null_z3": max(B["mc_null_z"], C["mc_null_z"]) > 3.0,
        },
        "caveat": "C 층=gold축 유래(상한). 진짜 USER 가설 판정=B(blind) 가 A(single) 이기나. C는 '여러 층이 원리상 성립하면 얼마나 되나' 천장.",
        "prereg": {"metric": "blind_multilayer_null_z", "baseline_single_layer_null_z": None,
                   "novel_metric": "B_separation_minus_A_separation", "novel_threshold": 0.0, "direction": "higher"},
    }
    out = HERE / "evidence" / "EVIDENCE_prom_multilayer_ab_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
