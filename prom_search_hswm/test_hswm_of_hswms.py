#!/usr/bin/env python3
"""
ML8 — HSWM-of-HSWMs 실측: 재귀 2-level 구조가 문맥(cross-chapter coverage)을 높이나.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML8-hswm-of-hswms
USER 심화 정전: "가중 복층 HSWM이 다른 HSWM과 연결=문맥 생김, 많을수록 좋다, 트리로도 형성."
구조: L2=paragraph 청크 / L1=章-HSWM(각 章=한 하네스문서, centroid) / 트리=book→章→para,
      + 章간 sibling weight-semantic 엣지(centroid cosine).

가설(반증가능): 개념이 여러 章에 흩어질 때, 계층 라우팅(HSWM-of-HSWMs)이 flat보다
  cross-chapter coverage(문맥)를 높인다 — 단 *가중*일 때만(blind uniform 라우팅은 무관 章에 낭비).

방법 4종 (top-k 예산 동일):
  flat            : 전 para 코사인 top-k (단일층 baseline).
  hier_weighted   : 章-HSWM 코사인으로 가중 → 예산을 관련 章들에 비례배분 → 章내 top.
  hier_blind      : 예산을 전 章에 균등배분(blind, 무관 章에 낭비).
  hier_sibling    : hier_weighted + top章과 강한 sibling엣지 章도 포함(HSWM↔HSWM 문맥전파).
지표: recall@k + **chapter_coverage@k**(gold 있는 章 중 top-k에 대표된 비율=문맥). k=20,40.
"""
import json, sys, re, statistics
from pathlib import Path

BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
SEED = 333
CONCEPTS = [("harness", "harness 하네스 에이전트 스캐폴딩"), ("RAG", "검색 증강 생성 RAG 리트리벌"),
            ("多 Agent", "다중 에이전트 협업 오케스트레이션"), ("KV Cache", "컨텍스트 KV 캐시 프롬프트 캐싱"),
            ("Coding Agent", "코딩 에이전트 코드 생성 파일시스템"), ("评估", "에이전트 평가 통계 판정"),
            ("上下文", "상하문 맥락 관리 압축"), ("记忆", "사용자 기억 메모리 지식베이스")]
KS = [20, 40]

def chunk_book():
    chunks, chap = [], []
    for f in sorted(BOOK.glob("chapter*.md")):
        cid = f.stem  # chapter1..chapter10
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            t = " ".join(para.split())
            if len(t) >= 90 and not t.startswith("#") and not t.startswith("!["):
                chunks.append(t); chap.append(cid)
    return chunks, chap

def main():
    chunks, chap = chunk_book()
    chapters = sorted(set(chap))
    import numpy as np, torch
    from sentence_transformers import SentenceTransformer
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E = model.encode(chunks, normalize_embeddings=True, convert_to_numpy=True, batch_size=64)
    idx_by_chap = {c: [i for i, x in enumerate(chap) if x == c] for c in chapters}
    # L1 = 章-HSWM centroid (normalized)
    cent = {c: (E[idx_by_chap[c]].mean(0)) for c in chapters}
    cent = {c: v / (np.linalg.norm(v) + 1e-9) for c, v in cent.items()}
    cent_mat = np.stack([cent[c] for c in chapters])
    # sibling weight-semantic edges (章-章 centroid cosine)
    sib = cent_mat @ cent_mat.T

    Q = model.encode([q for _, q in CONCEPTS], normalize_embeddings=True, convert_to_numpy=True)

    def flat_topk(qv, k):
        s = E @ qv
        return list(np.argsort(-s)[:k])

    def hier_topk(qv, k, mode):
        chsc = {c: float(cent[c] @ qv) for c in chapters}
        if mode == "blind":
            budget = {c: max(1, k // len(chapters)) for c in chapters}
        else:  # weighted
            pos = {c: max(0.0, chsc[c]) for c in chapters}
            tot = sum(pos.values()) or 1e-9
            budget = {c: int(round(k * pos[c] / tot)) for c in chapters}
            if mode == "sibling":
                topc = max(chapters, key=lambda c: chsc[c])
                for j, c in enumerate(chapters):
                    if c != topc and sib[chapters.index(topc)][j] > 0.6:
                        budget[c] = max(budget[c], 2)  # 강한 sibling 章 문맥 주입
        picked = []
        for c in chapters:
            b = budget.get(c, 0)
            if b <= 0:
                continue
            ci = idx_by_chap[c]
            s = E[ci] @ qv
            for i in list(np.argsort(-s)[:b]):
                picked.append(ci[i])
        # 예산 초과/미달 보정: qv 유사도로 정렬해 정확히 k개
        picked = sorted(set(picked), key=lambda i: -float(E[i] @ qv))[:k]
        return picked

    methods = {"flat": lambda qv, k: flat_topk(qv, k),
               "hier_weighted": lambda qv, k: hier_topk(qv, k, "weighted"),
               "hier_blind": lambda qv, k: hier_topk(qv, k, "blind"),
               "hier_sibling": lambda qv, k: hier_topk(qv, k, "sibling")}

    agg = {m: {k: {"recall": [], "cov": []} for k in KS} for m in methods}
    per = []
    for qi, (anchor, qtext) in enumerate(CONCEPTS):
        gold = [i for i, t in enumerate(chunks) if anchor.lower() in t.lower()]
        gold_chaps = set(chap[i] for i in gold)
        row = {"concept": anchor, "gold_chunks": len(gold), "gold_chapters": len(gold_chaps)}
        for m in methods:
            for k in KS:
                got = methods[m](Q[qi], k)
                hit = [i for i in got if i in set(gold)]
                recall = len(hit) / len(gold) if gold else 0.0
                cov = len(set(chap[i] for i in hit)) / len(gold_chaps) if gold_chaps else 0.0
                agg[m][k]["recall"].append(recall); agg[m][k]["cov"].append(cov)
                row[f"{m}_cov@{k}"] = round(cov, 3)
        per.append(row)

    means = {m: {k: {"recall": round(statistics.mean(agg[m][k]["recall"]), 4),
                     "coverage": round(statistics.mean(agg[m][k]["cov"]), 4)} for k in KS} for m in methods}
    ev = {
        "experiment": "hswm_of_hswms_ml8",
        "tree": "LakatosTree_PromSearchHSWM_20260721", "node": "ML8-hswm-of-hswms",
        "structure": {"L1_chapters": len(chapters), "L2_chunks": len(chunks),
                      "concepts": len(CONCEPTS), "corpus": "ai-agent-book"},
        "metric_note": "chapter_coverage@k = 개념이 흩어진 章 중 top-k에 대표된 비율 = 문맥. recall@k도 병기.",
        "means": means,
        "per_concept": per,
        "hypothesis_test": {
            "hier_weighted_cov_gt_flat@20": means["hier_weighted"][20]["coverage"] > means["flat"][20]["coverage"],
            "hier_sibling_cov_gt_flat@20": means["hier_sibling"][20]["coverage"] > means["flat"][20]["coverage"],
            "weighted_cov_gt_blind@20": means["hier_weighted"][20]["coverage"] > means["hier_blind"][20]["coverage"],
            "cov_gain_weighted_over_flat@20": round(means["hier_weighted"][20]["coverage"] - means["flat"][20]["coverage"], 4),
            "cov_gain_sibling_over_flat@20": round(means["hier_sibling"][20]["coverage"] - means["flat"][20]["coverage"], 4),
        },
        "verdict_note": "hier가 flat보다 coverage 높으면 'HSWM-of-HSWMs가 문맥 높인다' 지지. weighted>blind면 가중규칙 재확인. gold=anchor-string(crude), recall은 낮게 나옴(비교는 상대).",
    }
    out = HERE / "evidence" / "EVIDENCE_hswm_of_hswms_ml8_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
