#!/usr/bin/env python3
"""
실험 B-2 (step 3 변주) — measurement-driven entity gating. T5b(blind union) 반증 후속.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node T5c-vunione-gated.
T5b 발견: blind max(edge,entity)는 비변별 hub(hallward deg11)가 엉뚱 finding 승격 → gap −0.028.
가설(문제이동): entity를 **idf로 hub 억제 + edge에 보너스로만 가산**하면 그 해악이 사라지고
  edge_only를 넘거나 최소 tie. = 7cmd measurement-driven conditional dispatch(변별적일 때만 기여)와 동형.

게이팅 설계 (사전 고정, λ 스윕 없음 — researcher DoF 통제):
  idf(e)     = log(N_findings / deg(e))            # hub 억제(deg↑ → idf↓). deg=N이면 0.
  idf_norm   = idf / max_idf                         # [0,1]
  ent_sig(f) = max over e∈members(f) of idf_norm(e)·entity_cos(e)   # 변별적 entity의 정렬만
  score(f)   = edge_cos(f) + LAMBDA · ent_sig(f)     # edge 지배 유지, entity는 보너스
  LAMBDA = 0.3 (사전 고정 단일값. n=18라 별도 split 튜닝 불가 → 하이퍼파라미터 미검증 caveat 명시).

비교: edge_only(baseline 0.644) vs v_union_e_blind(0.616, refuted) vs v_union_e_gated(신규).
metric = vunione_gated_minus_edgeonly_recall_gap. gap>0.02 & MC-null z≥3 → progressive.
정직: 이겨도 λ 미튜닝 = down-payment(더 큰 벤치 필요), 져도 entity 채널 이 task서 무익 확정.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hswm_hypergraph import build_hypergraph, load_badiou_findings
from hswm_hypergraph_readout import _cos

HERE = Path(__file__).parent
SEED = 333
K_AT = 5
MC_PERM = 200
LAMBDA = 0.3
ROLE = {"primary", "secondary", "critique"}


def topics(clusters):
    return {c for c in clusters if c not in ROLE}


def _lcg(seed):
    state = seed % 2147483647 or 1
    while True:
        state = (state * 48271) % 2147483647
        yield state / 2147483647


def permute(labels, rnd):
    a = list(labels)
    for i in range(len(a) - 1, 0, -1):
        j = int(next(rnd) * (i + 1))
        a[i], a[j] = a[j], a[i]
    return a


def entity_idf(hg):
    """entity vid -> idf_norm ([0,1]). deg = incident finding 수. hub↓."""
    N = len(hg.edges)
    idf = {}
    for vid, v in hg.vertices.items():
        deg = len(v.incident_edges) or 1
        idf[vid] = math.log(N / deg)
    mx = max(idf.values()) or 1.0
    return {vid: val / mx for vid, val in idf.items()}


def finding_scores(hg, fids, qvec, arm, idf_norm):
    edge_cos = {fid: _cos(qvec, hg.edges[fid].embedding) for fid in fids}
    if arm == "edge_only":
        return dict(edge_cos)

    node_max = {}   # blind: max entity cos
    ent_sig = {}    # gated: max idf_norm·cos
    for fid in fids:
        vals_blind, vals_gated = [], []
        for vid in hg.edges[fid].members:
            ec = _cos(qvec, hg.vertices[vid].embedding)
            vals_blind.append(ec)
            vals_gated.append(idf_norm.get(vid, 0.0) * ec)
        if vals_blind:
            node_max[fid] = max(vals_blind)
            ent_sig[fid] = max(vals_gated)

    if arm == "node_only":
        return dict(node_max)
    if arm == "v_union_e_blind":
        return {fid: max(edge_cos[fid], node_max.get(fid, -1.0)) for fid in fids}
    if arm == "v_union_e_gated":
        return {fid: edge_cos[fid] + LAMBDA * ent_sig.get(fid, 0.0) for fid in fids}
    raise ValueError(arm)


def recall_mrr(scores, gold, k):
    ranked = sorted(scores, key=lambda f: -scores[f])
    if not gold:
        return None, None
    topk = set(ranked[:k])
    rec = len(topk & gold) / len(gold)
    rr = 0.0
    for rank, fid in enumerate(ranked, 1):
        if fid in gold:
            rr = 1.0 / rank
            break
    return rec, rr


def eval_arm(hg, findings, gold_topics, arm, idf_norm, k=K_AT):
    recs, rrs = [], []
    for qf in findings:
        qid = qf["rf"]
        qvec = hg.edges[qid].embedding
        gold = {f["rf"] for f in findings if f["rf"] != qid
                and gold_topics[f["rf"]] & gold_topics[qid]}
        if not gold:
            continue
        pool = [f["rf"] for f in findings if f["rf"] != qid]
        sc = finding_scores(hg, pool, qvec, arm, idf_norm)
        rec, rr = recall_mrr(sc, gold, k)
        recs.append(rec); rrs.append(rr)
    return statistics.mean(recs), statistics.mean(rrs), len(recs)


def main():
    findings = load_badiou_findings()
    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    def embed(texts):
        return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True).tolist()

    hg = build_hypergraph(findings, embed=embed, topic_vertices=False)
    idf_norm = entity_idf(hg)
    gold_topics = {f["rf"]: topics(f["clusters"]) for f in findings}

    arms = {}
    for arm in ("node_only", "edge_only", "v_union_e_blind", "v_union_e_gated"):
        rec, rr, n = eval_arm(hg, findings, gold_topics, arm, idf_norm)
        arms[arm] = {"recall_at_5": round(rec, 4), "mrr": round(rr, 4), "n_queries": n}

    gap = arms["v_union_e_gated"]["recall_at_5"] - arms["edge_only"]["recall_at_5"]

    rnd = _lcg(SEED)
    fids = [f["rf"] for f in findings]
    null_recs = []
    for _ in range(MC_PERM):
        perm = permute([gold_topics[fid] for fid in fids], rnd)
        gt = dict(zip(fids, perm))
        rec, _, _ = eval_arm(hg, findings, gt, "v_union_e_gated", idf_norm)
        null_recs.append(rec)
    nmean = statistics.mean(null_recs)
    nsd = statistics.pstdev(null_recs) or 1e-9
    z = (arms["v_union_e_gated"]["recall_at_5"] - nmean) / nsd

    verdict = ("progressive" if gap > 0.02 and z >= 3.0
               else "equivalent" if abs(gap) <= 0.02
               else "degenerating")

    ev = {
        "experiment": "vunione_gated_readout_ab_stepB2",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "T5c-vunione-gated",
        "design": "measurement-driven entity gating (idf hub-suppression + edge-dominant bonus). "
                  "entity-only graph, gold=topic held-out, leave-one-out, LAMBDA=0.3 fixed (untuned).",
        "arms": arms,
        "preregistered_metric": "vunione_gated_minus_edgeonly_recall_gap",
        "gap_gated_minus_edgeonly": round(gap, 4),
        "gap_blind_minus_edgeonly": round(
            arms["v_union_e_blind"]["recall_at_5"] - arms["edge_only"]["recall_at_5"], 4),
        "mc_null": {"perms": MC_PERM, "null_mean_recall": round(nmean, 4),
                     "null_sd": round(nsd, 4), "z": round(z, 3),
                     "novel_metric": "vunione_gated_recall_above_mc_null_z", "threshold": 3.0},
        "verdict": verdict,
        "honest_note": "T5b blind(-0.028)와 직접 대조. gated>edge_only면 hub억제가 fix(단 λ untuned=down-payment). "
                       "gated≈edge_only(|gap|≤0.02)면 entity 채널은 이 task/데이터서 무익 확정(정직 null). "
                       "판정=결정론 사전등록 대조, eureka 자기채점 아님.",
    }
    out = HERE / "evidence" / "EVIDENCE_vunione_gated_stepB2_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
