#!/usr/bin/env python3
"""
PROM 검색 ML4 — field-of-fields: 독립 소스 場 융합 (USER "여러 층" 마지막·정당 판정).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML4-fieldoffields-badiou
ML3 결론: 같은 텍스트를 층에 재투영 = 정보손실(refuted). 이번엔 *다른 모달리티* 場을 엮는다:
  발견: 이 KG는 RF마다 비-consensus 이웃이 균일(SubagentTaskSpec:3+Lesson:1)=구조場 판별력 0.
  → 진짜 KG-엣지 구조場 부재. 차선 독립場 = 텍스트서 뽑은 *인용-엔티티場*(학자이름 exact-match Jaccard,
    lexical=semantic 임베딩과 다른 신호. 특히 role축: secondary→Hallward/Bosteels, critique→Laruelle/Meillassoux).

3 arms + fusion (threshold-free AUC):
  A text場       : dense 임베딩 cosine (ML3 baseline, AUC~0.643).
  E entity場     : 인용학자 Jaccard.
  F fused        : RRF(text, entity) 및 weighted-sum α sweep — 융합이 텍스트 단독을 이기나.

USER 가설 지지 = F_auc > A_auc (독립場 추가가 도움). 자가비판: 엔티티도 텍스트서 추출(진짜 외부場 아님)
  이나 *모달리티 독립*(lexical vs semantic). 진짜 field-of-fields(internet場+KG場)의 최소 프록시.
"""
import json, sys, itertools, statistics, re
from pathlib import Path

HERE = Path(__file__).parent
SEED = 333

# 인용 학자/고유명 lexicon (badiou RF 텍스트 등장, role 판별 후보)
LEXICON = ["hallward", "bosteels", "bartlett", "clemens", "pluth", "feltham", "baki",
           "livingston", "norris", "bolz", "laruelle", "meillassoux", "brassier",
           "wolfendale", "zizek", "ranciere", "bensaid", "critchley", "toscano",
           "adorno", "lacan", "chiesa", "fink", "boucher", "watkin", "plotnitsky",
           "veilahti", "rorty", "nietzsche", "wittgenstein", "beckett", "mallarme",
           "celan", "levinas", "miller", "cohen", "mirimanoff", "grothendieck",
           "church", "kierkegaard", "paul", "antigone"]

def load():
    g = json.loads((HERE / "data" / "gold_badiou24.json").read_text())
    return ([f["text"] for f in g["findings"]], [set(f["clusters"]) for f in g["findings"]])

def entities(text):
    t = text.lower()
    return {e for e in LEXICON if e in t}

def gold_pairs(clusters):
    same, diff = [], []
    for i, j in itertools.combinations(range(len(clusters)), 2):
        (same if clusters[i] & clusters[j] else diff).append((i, j))
    return same, diff

def auc(ss, ds):
    if not ss or not ds:
        return 0.5
    w = t = 0
    for s in ss:
        for d in ds:
            if s > d: w += 1
            elif s == d: t += 1
    return (w + 0.5 * t) / (len(ss) * len(ds))

def arm_auc_sep(sim, same, diff):
    ss = [sim[(i, j)] for i, j in same]
    ds = [sim[(i, j)] for i, j in diff]
    return round(auc(ss, ds), 4), round(statistics.mean(ss) - statistics.mean(ds), 4)

def rank_map(sim, pairs):
    """pair→rank(0=best). 동점 평균순위."""
    ordered = sorted(pairs, key=lambda p: -sim[p])
    rk = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and sim[ordered[j + 1]] == sim[ordered[i]]:
            j += 1
        avg = (i + j) / 2.0
        for k in range(i, j + 1):
            rk[ordered[k]] = avg
        i = j + 1
    return rk

def main():
    texts, clusters = load()
    n = len(texts)
    same, diff = gold_pairs(clusters)
    allpairs = list(itertools.combinations(range(n), 2))

    from sentence_transformers import SentenceTransformer
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    cosT = E @ E.T

    ents = [entities(t) for t in texts]
    ent_counts = [len(e) for e in ents]

    text_sim = {(i, j): float(cosT[i][j]) for i, j in allpairs}
    def jac(a, b):
        return len(a & b) / len(a | b) if (a | b) else 0.0
    ent_sim = {(i, j): jac(ents[i], ents[j]) for i, j in allpairs}

    # RRF fusion (k=60)
    rt = rank_map(text_sim, allpairs); re_ = rank_map(ent_sim, allpairs)
    K = 60
    rrf = {p: 1.0 / (K + rt[p]) + 1.0 / (K + re_[p]) for p in allpairs}

    A_auc, A_sep = arm_auc_sep(text_sim, same, diff)
    E_auc, E_sep = arm_auc_sep(ent_sim, same, diff)
    R_auc, R_sep = arm_auc_sep(rrf, same, diff)

    # weighted-sum α sweep (normalize each sim to [0,1] via min-max)
    def norm(d):
        vs = list(d.values()); lo, hi = min(vs), max(vs)
        return {p: (v - lo) / (hi - lo + 1e-9) for p, v in d.items()}
    nt, ne = norm(text_sim), norm(ent_sim)
    sweep = {}
    best = (A_auc, 1.0)
    for a in [0.0, 0.25, 0.5, 0.75, 1.0]:
        fs = {p: a * nt[p] + (1 - a) * ne[p] for p in allpairs}
        au, _ = arm_auc_sep(fs, same, diff)
        sweep[f"alpha_{a:.2f}_text"] = au
        if au > best[0]:
            best = (au, a)

    ev = {
        "experiment": "prom_fieldoffields_badiou24",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "ML4-fieldoffields-badiou",
        "kg_structure_finding": "이 KG는 RF마다 비-consensus 이웃 균일(SubagentTaskSpec:3+Lesson:1) = 판별 구조場 부재. 엔티티場은 텍스트서 lexical 추출한 최소 독립-모달리티 프록시.",
        "gold": {"n_rf": n, "same_pairs": len(same), "diff_pairs": len(diff)},
        "entity_layer": {"lexicon_size": len(LEXICON), "mean_entities_per_rf": round(statistics.mean(ent_counts), 2),
                         "rfs_with_zero_entities": sum(1 for c in ent_counts if c == 0)},
        "arm_A_text_field": {"auc": A_auc, "separation": A_sep},
        "arm_E_entity_field": {"auc": E_auc, "separation": E_sep},
        "arm_F_fused_RRF": {"auc": R_auc, "separation": R_sep},
        "fused_weighted_sweep": sweep,
        "best_fused": {"auc": best[0], "alpha_text_weight": best[1]},
        "hypothesis_test": {
            "entity_alone_beats_null": E_auc > 0.55,
            "RRF_fusion_beats_text": R_auc > A_auc,
            "any_fusion_beats_text": best[0] > A_auc,
            "fusion_gain_over_text": round(best[0] - A_auc, 4),
        },
        "verdict_note": "F_auc > A_auc 면 USER field-of-fields 가설 이 프록시서 지지. <= 면 이 데이터/모달리티선 독립場도 무익.",
    }
    out = HERE / "evidence" / "EVIDENCE_prom_fieldoffields_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
