#!/usr/bin/env python3
"""
실험 B (step 3) — T5 V∪E readout 판정: 하이퍼엣지 1급 채점 + 정점 확장이 findings-only를 이기나.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node T5-vunione-firstclass-readout (사전등록됨).
사전등록 예측: metric=vunione_minus_edgeonly_recall_gap, baseline 0, direction higher, noise 0.02,
  novel=vunione_recall_above_mc_null_z ≥ 3, credence 0.4.

설계 (정직):
  - 그래프 = **entity-only** (topic_vertices=False) — gold==topic이라 topic 정점화하면 leakage.
    entity는 텍스트서 lexicon 추출(내용 유래, gold와 독립).
  - gold = topic-cluster 공동멤버십 (held-out, 그래프에 안 들어감). role축 제외.
  - leave-one-out: query=각 finding text. gold=같은 topic 공유 다른 findings.
  - 3 arm 모두 **finding-level 랭킹**으로 집계(같은 23 findings를 랭킹 → candidate inflation 중화):
      edge_only : finding score = 그 엣지 cosine.
      node_only : finding score = max cosine over 그 finding에 incident한 entity 정점 (구조 hop).
                  공유 entity 없으면 도달 불가(-inf).
      v_union_e : max(edge cosine, max incident-entity 정점 cosine) = 값채널 V + 관계 E 합류.
  - metric = mean recall@5 + mean MRR. gap = v_union_e − edge_only.
  - MC-null: topic 라벨을 findings 간 순열(K=200)해 v_union_e recall 귀무분포 → z.

판정은 이 스크립트가(자기채점 아님 — 결정론 + 사전등록 대조). eureka 남용 회피.
"""
from __future__ import annotations

import json
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
ROLE = {"primary", "secondary", "critique"}


def topics(clusters):
    return {c for c in clusters if c not in ROLE}


def _lcg(seed):
    """결정론 PRNG (Math.random 금지 환경 무관, 재현). Park-Miller."""
    state = seed % 2147483647 or 1
    while True:
        state = (state * 48271) % 2147483647
        yield state / 2147483647


def permute(labels, rnd):
    """Fisher-Yates 결정론 셔플 (labels 얕은 복사 순열)."""
    a = list(labels)
    for i in range(len(a) - 1, 0, -1):
        j = int(next(rnd) * (i + 1))
        a[i], a[j] = a[j], a[i]
    return a


def finding_scores(hg, fids, qvec, arm):
    """arm별 finding-id -> score. 도달 불가 finding은 제외(랭킹서 최하)."""
    edge_cos = {fid: _cos(qvec, hg.edges[fid].embedding) for fid in fids}
    if arm == "edge_only":
        return dict(edge_cos)
    # 각 finding에 incident한 entity 정점의 max cosine
    node_reach = {}
    for fid in fids:
        vs = [hg.vertices[vid].embedding for vid in hg.edges[fid].members]
        if vs:
            node_reach[fid] = max(_cos(qvec, ve) for ve in vs)
    if arm == "node_only":
        return dict(node_reach)
    if arm == "v_union_e":
        out = {}
        for fid in fids:
            cands = [edge_cos[fid]]
            if fid in node_reach:
                cands.append(node_reach[fid])
            out[fid] = max(cands)
        return out
    raise ValueError(arm)


def recall_mrr(scores, gold, k):
    """gold 집합에 대한 recall@k, MRR. scores: fid->score (미포함=최하)."""
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


def eval_arm(hg, findings, gold_topics, arm, k=K_AT):
    """leave-one-out 평균 recall@k, MRR. gold_topics: fid->set(topic)."""
    recs, rrs = [], []
    for qf in findings:
        qid = qf["rf"]
        qvec = hg.edges[qid].embedding
        gold = {f["rf"] for f in findings if f["rf"] != qid
                and gold_topics[f["rf"]] & gold_topics[qid]}
        if not gold:
            continue
        pool = [f["rf"] for f in findings if f["rf"] != qid]
        sc = finding_scores(hg, pool, qvec, arm)
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

    # entity-only 그래프 (leakage 차단)
    hg = build_hypergraph(findings, embed=embed, topic_vertices=False)
    gold_topics = {f["rf"]: topics(f["clusters"]) for f in findings}

    arms = {}
    for arm in ("node_only", "edge_only", "v_union_e"):
        rec, rr, n = eval_arm(hg, findings, gold_topics, arm)
        arms[arm] = {"recall_at_5": round(rec, 4), "mrr": round(rr, 4), "n_queries": n}

    gap = arms["v_union_e"]["recall_at_5"] - arms["edge_only"]["recall_at_5"]

    # MC-null: topic 라벨 순열 → v_union_e recall 귀무분포
    rnd = _lcg(SEED)
    fids = [f["rf"] for f in findings]
    null_recs = []
    for _ in range(MC_PERM):
        perm = permute([gold_topics[fid] for fid in fids], rnd)
        gt = dict(zip(fids, perm))
        rec, _, _ = eval_arm(hg, findings, gt, "v_union_e")
        null_recs.append(rec)
    nmean = statistics.mean(null_recs)
    nsd = statistics.pstdev(null_recs) or 1e-9
    z = (arms["v_union_e"]["recall_at_5"] - nmean) / nsd

    verdict = ("progressive" if gap > 0.02 and z >= 3.0
               else "equivalent" if abs(gap) <= 0.02
               else "degenerating")

    ev = {
        "experiment": "vunione_readout_ab_stepB",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "T5-vunione-firstclass-readout",
        "design": "entity-only graph (leakage-free), gold=topic co-membership held-out, "
                  "leave-one-out, finding-level aggregation (candidate-inflation neutral)",
        "graph": {"V_entity": len(hg.vertices), "E_findings": len(hg.edges)},
        "arms": arms,
        "preregistered_metric": "vunione_minus_edgeonly_recall_gap",
        "gap_vunione_minus_edgeonly": round(gap, 4),
        "gap_vunione_minus_nodeonly": round(
            arms["v_union_e"]["recall_at_5"] - arms["node_only"]["recall_at_5"], 4),
        "mc_null": {"perms": MC_PERM, "null_mean_recall": round(nmean, 4),
                     "null_sd": round(nsd, 4), "z": round(z, 3),
                     "novel_metric": "vunione_recall_above_mc_null_z", "threshold": 3.0},
        "verdict": verdict,
        "honest_note": "candidate inflation 중화(세 arm 같은 23 findings 랭킹). "
                       "gap<=0.02면 V정점이 findings-only에 못 더함(equivalent) = 정직한 null 가능. "
                       "판정은 사전등록 대조 — eureka 자기채점 아님.",
    }
    out = HERE / "evidence" / "EVIDENCE_vunione_readout_stepB_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
