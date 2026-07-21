#!/usr/bin/env python3
"""
PROM 검색 ML5 — 진짜 판정: REAL 독립 소스場 융합 (인터넷場 + 내부KG場).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML5-real-fields-ab
USER 정의: "PROM = 인터넷場 + 내부KG場의 HSWM 레이어를 쌓는". ML4는 lexical 프록시로 방향만 지지.
이번엔 REAL: web=WebSearch(2026-07-21) / kg=Neo4j 홈canon 노드. task=legend recall on ai-agent-book(中).

4 場 (동일 corpus·gold, query-expansion 방식):
  raw  : 질의 텍스트만 임베딩.
  web  : 실 웹검색 요약으로 확장한 질의 (인터넷場).
  kg   : 실 KG 노드 desc로 확장한 질의 (내부KG場).
  fused: RRF(raw, web, kg).
gold = anchor 포함 book 청크. metric = MRR(첫 gold 순위) + recall@10. per場 + fused.

USER field-of-fields 진짜 지지 = fused MRR > raw MRR (그리고 web/kg 각각 기여).
자가비판: web/kg는 서로 다른 실 소스(모달리티·출처 독립). RAG/evaluation의 kg는 우리 KG 빈약(현실 반영, per-concept 분해로 노출).
"""
import json, sys, re, statistics
from pathlib import Path

BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
SEED = 333
RRF_K = 60

def chunk_book():
    chunks = []
    for f in sorted(BOOK.glob("chapter*.md")):
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            t = " ".join(para.split())
            if len(t) >= 90 and not t.startswith("#") and not t.startswith("!["):
                chunks.append(t)
    return chunks

def rank(sim_row):
    """내림차순 인덱스 순위. return dict idx->rank(1=best)."""
    order = sorted(range(len(sim_row)), key=lambda i: -sim_row[i])
    return {idx: r + 1 for r, idx in enumerate(order)}

def mrr_recall(rankmap, gold_idx, k=10):
    if not gold_idx:
        return 0.0, 0
    best = min(rankmap[i] for i in gold_idx)
    rr = 1.0 / best
    rec = 1 if best <= k else 0
    return rr, rec

def main():
    src = json.loads((HERE / "data" / "sources_realfields.json").read_text())["concepts"]
    chunks = chunk_book()

    from sentence_transformers import SentenceTransformer
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    C = model.encode(chunks, normalize_embeddings=True, convert_to_numpy=True, batch_size=64)

    per = []
    agg = {"raw": [], "web": [], "kg": [], "fused": []}
    rec_agg = {"raw": 0, "web": 0, "kg": 0, "fused": 0}
    for c in src:
        anchor = c["anchor"].lower()
        gold = [i for i, t in enumerate(chunks) if anchor in t.lower()]
        reps = {
            "raw": c["query"],
            "web": c["query"] + " . " + c["web"],
            "kg": c["query"] + " . " + c["kg"],
        }
        Q = model.encode(list(reps.values()), normalize_embeddings=True, convert_to_numpy=True)
        sims = {name: (Q[i] @ C.T).tolist() for i, name in enumerate(reps)}
        ranks = {name: rank(sims[name]) for name in reps}
        # fused = RRF over raw+web+kg
        fused_score = {}
        for i in range(len(chunks)):
            fused_score[i] = sum(1.0 / (RRF_K + ranks[name][i]) for name in reps)
        fused_rank = {idx: r + 1 for r, idx in enumerate(sorted(range(len(chunks)), key=lambda i: -fused_score[i]))}

        row = {"concept": c["key"], "anchor": c["anchor"], "gold_chunks": len(gold)}
        for name in ("raw", "web", "kg"):
            rr, rec = mrr_recall(ranks[name], gold)
            row[name + "_mrr"] = round(rr, 4); row[name + "_rec@10"] = rec
            agg[name].append(rr); rec_agg[name] += rec
        frr, frec = mrr_recall(fused_rank, gold)
        row["fused_mrr"] = round(frr, 4); row["fused_rec@10"] = frec
        agg["fused"].append(frr); rec_agg["fused"] += frec
        per.append(row)

    n = len(src)
    means = {k: round(statistics.mean(v), 4) for k, v in agg.items()}
    ev = {
        "experiment": "prom_realfields_ab",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "ML5-real-fields-ab",
        "sources": {"web": "WebSearch 2026-07-21 (real internet)", "kg": "Neo4j home canon 0.25 (real internal KG)",
                    "corpus": "ai-agent-book chapters (Chinese)", "n_book_chunks": len(chunks), "n_concepts": n},
        "mean_MRR": means,
        "recall_at_10": {k: f"{v}/{n}" for k, v in rec_agg.items()},
        "per_concept": per,
        "hypothesis_test": {
            "web_beats_raw": means["web"] > means["raw"],
            "kg_beats_raw": means["kg"] > means["raw"],
            "fused_beats_raw": means["fused"] > means["raw"],
            "fused_beats_best_single": means["fused"] >= max(means["raw"], means["web"], means["kg"]),
            "fused_gain_over_raw": round(means["fused"] - means["raw"], 4),
        },
        "verdict_note": "fused_mrr > raw_mrr = USER field-of-fields(인터넷場+KG場) REAL 지지. per_concept로 어느 소스가 어디서 돕는지 분해.",
    }
    out = HERE / "evidence" / "EVIDENCE_prom_realfields_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
