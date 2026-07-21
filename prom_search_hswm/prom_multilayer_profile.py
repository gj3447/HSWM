#!/usr/bin/env python3
"""
PROM 검색 ML3 — 과활성 없는 multi-layer: 층-프로파일 벡터 유사도 (USER "여러 층" 공정 재판).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML3-multilayer-profile-badiou
ML2 실패원인 = binary co-activation(∃층 both>=t)이 과활성 → null 붙음. 이번엔 continuous:
  각 RF → 층-프로파일 p_i = [cos(RF_i, L_1..K)] (K차원). 유사도 = cosine(p_i, p_j).
  threshold 없이 AUC(same-pair sim > diff-pair sim 확률)로 arm 비교 = 공정.

3 arms (동일 gold, threshold-free AUC + separation):
  A single-layer : raw RF-text cosine.
  B multi BLIND  : KMeans(K) 층 → 프로파일 cosine.
  C multi STRUCT : 3 role + 7 topic 앵커 층 → 프로파일 cosine. (gold축 유래=상한)

USER 가설 지지 = B(또는 C) AUC > A AUC (다층 프로파일이 role×topic 구조를 단일층보다 잘 분리).
자가비판: C=상한. 진짜 판정=B(blind)>A 인가. a-priori K=10, seed=333. threshold-free라 τ 튜닝 없음.
"""
import json, sys, itertools, statistics, random
from pathlib import Path

K_BLIND = 10
SEED = 333
HERE = Path(__file__).parent

ROLE = ["primary canonical exposition of Badiou's own doctrine and primary text",
        "secondary scholarly consensus and commentary from multiple schools of interpreters",
        "critical adversarial objections and ranked critiques from opposing philosophers"]
TOPIC = ["the event as violation of the ZFC foundation regularity axiom, self-membership",
         "Cohen forcing, generic filter, ground model, the forcing-event paradox",
         "ethics of truth, the three figures of evil, simulacrum betrayal disaster, anti-Levinas",
         "inaesthetics, art as a truth procedure, poem theater cinema dance",
         "the link to Lacan, psychoanalysis, the subject, suture, antiphilosophy",
         "Logics of Worlds, complete Heyting algebra, topos of sheaves, transcendental",
         "antiphilosophy as pedagogical method, self-negation, Nietzsche Wittgenstein Lacan seminars"]

def load():
    g = json.loads((HERE / "data" / "gold_badiou24.json").read_text())
    return ([f["text"] for f in g["findings"]], [set(f["clusters"]) for f in g["findings"]])

def gold_pairs(clusters):
    same, diff = [], []
    for i, j in itertools.combinations(range(len(clusters)), 2):
        (same if clusters[i] & clusters[j] else diff).append((i, j))
    return same, diff

def auc(same_sims, diff_sims):
    """P(random same-pair sim > random diff-pair sim). threshold-free 분리력."""
    if not same_sims or not diff_sims:
        return 0.5
    wins = ties = 0
    for s in same_sims:
        for d in diff_sims:
            if s > d: wins += 1
            elif s == d: ties += 1
    return (wins + 0.5 * ties) / (len(same_sims) * len(diff_sims))

def null_auc_z(sim_of, clusters, observed_auc):
    """gold 라벨 순열 하 AUC 분포 → observed 가 위인지 z."""
    rng = random.Random(SEED)
    n = len(clusters)
    allpairs = list(itertools.combinations(range(n), 2))
    simcache = {(i, j): sim_of(i, j) for i, j in allpairs}
    nulls = []
    for _ in range(2000):
        perm = clusters[:]; rng.shuffle(perm)
        s, d = [], []
        for i, j in allpairs:
            (s if perm[i] & perm[j] else d).append(simcache[(i, j)])
        nulls.append(auc(s, d))
    m = statistics.mean(nulls); sd = statistics.pstdev(nulls) or 1e-9
    return (observed_auc - m) / sd, m

def arm(sim_of, same, diff, clusters):
    ss = [sim_of(i, j) for i, j in same]
    ds = [sim_of(i, j) for i, j in diff]
    a = auc(ss, ds)
    sep = statistics.mean(ss) - statistics.mean(ds)
    z, nmean = null_auc_z(sim_of, clusters, a)
    return {"auc": round(a, 4), "separation": round(sep, 4), "auc_null_z": round(z, 3),
            "auc_null_mean": round(nmean, 4)}

def main():
    texts, clusters = load()
    n = len(texts)
    same, diff = gold_pairs(clusters)

    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)

    def cos_rows(M):
        Mn = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
        return Mn @ Mn.T

    # A: single-layer raw text cosine
    cosT = E @ E.T
    A = arm(lambda i, j: float(cosT[i][j]), same, diff, clusters)

    # B: blind KMeans layer-profiles
    km = KMeans(n_clusters=K_BLIND, random_state=SEED, n_init=10).fit(E)
    C_ = km.cluster_centers_; C_ = C_ / (np.linalg.norm(C_, axis=1, keepdims=True) + 1e-9)
    PB = E @ C_.T                    # (n, K) 프로파일
    cosB = cos_rows(PB)
    B = arm(lambda i, j: float(cosB[i][j]), same, diff, clusters)

    # C: structured (role+topic) layer-profiles
    anchors = model.encode(ROLE + TOPIC, normalize_embeddings=True, convert_to_numpy=True)
    PC = E @ anchors.T
    cosC = cos_rows(PC)
    Cr = arm(lambda i, j: float(cosC[i][j]), same, diff, clusters)

    ev = {
        "experiment": "prom_multilayer_profile_badiou24",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "ML3-multilayer-profile-badiou",
        "method": "layer-profile vector cosine (continuous, threshold-free AUC) — ML2 binary co-activation 과활성 수정",
        "a_priori": {"k_blind": K_BLIND, "seed": SEED},
        "gold": {"n_rf": n, "same_pairs": len(same), "diff_pairs": len(diff), "axes": "role(3)xtopic(7)"},
        "arm_A_single_layer": A,
        "arm_B_multi_blind_profile": B,
        "arm_C_multi_structured_profile": Cr,
        "hypothesis_test": {
            "B_auc_gt_A_auc": B["auc"] > A["auc"],
            "C_auc_gt_A_auc": Cr["auc"] > A["auc"],
            "B_separation_gt_A": B["separation"] > A["separation"],
            "best_multi_above_null_z3": max(B["auc_null_z"], Cr["auc_null_z"]) > 3.0,
        },
        "caveat": "C 층=gold축 유래(상한). 공정 판정=B(blind) AUC > A(single) AUC 인가. AUC=threshold-free 분리력.",
        "prereg": {"metric": "blind_multilayer_auc", "baseline_single_layer_auc": None,
                   "novel_metric": "B_auc_minus_A_auc", "novel_threshold": 0.0, "direction": "higher"},
    }
    out = HERE / "evidence" / "EVIDENCE_prom_multilayer_profile_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
