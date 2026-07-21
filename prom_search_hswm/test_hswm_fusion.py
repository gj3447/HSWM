#!/usr/bin/env python3
"""
ML6 — HSWM fusion 실검증: 가중/게이트 융합이 blind RRF(ML5 net-zero)를 이기나.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML6-hswm-fusion-impl
엔진 = hswm_fusion.py (PROM Step3/4 프리미티브). 데이터 = sources_realfields.json + ai-agent-book.
전략 4종: blind(=ML5) / confidence / agreement / gated_agreement.
예측(사전등록): gated_agreement/agreement가 multi-agent web-이득은 지키고 coding/rag/eval 노이즈場은
  down-weight/배제 → mean MRR > blind(0.917). = weakest-link 회피(Balancing-the-Blend) 실증.
metric = mean MRR (첫 gold 순위). anchor場=raw.
"""
import json, sys, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from hswm_fusion import fuse, _ranks_from_scores  # PROM 프리미티브

import re
BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
SEED = 333
STRATS = ["blind", "confidence", "agreement", "gated_agreement"]

def chunk_book():
    out = []
    for f in sorted(BOOK.glob("chapter*.md")):
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            t = " ".join(para.split())
            if len(t) >= 90 and not t.startswith("#") and not t.startswith("!["):
                out.append(t)
    return out

def mrr(scores, gold):
    if not gold:
        return 0.0
    rk = _ranks_from_scores(scores)
    return 1.0 / min(rk[i] for i in gold)

def main():
    src = json.loads((HERE / "data" / "sources_realfields.json").read_text())["concepts"]
    chunks = chunk_book()
    from sentence_transformers import SentenceTransformer
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    C = model.encode(chunks, normalize_embeddings=True, convert_to_numpy=True, batch_size=64)

    agg = {s: [] for s in STRATS}
    agg["raw_only"] = []
    per = []
    drop_log = {}
    for c in src:
        anchor = c["anchor"].lower()
        gold = [i for i, t in enumerate(chunks) if anchor in t.lower()]
        reps = {"raw": c["query"], "web": c["query"] + " . " + c["web"], "kg": c["query"] + " . " + c["kg"]}
        Q = model.encode(list(reps.values()), normalize_embeddings=True, convert_to_numpy=True)
        rankings = {name: (Q[i] @ C.T).tolist() for i, name in enumerate(reps)}

        row = {"concept": c["key"], "raw_only_mrr": round(mrr(rankings["raw"], gold), 3)}
        agg["raw_only"].append(mrr(rankings["raw"], gold))
        for s in STRATS:
            fused, w, dropped = fuse(rankings, strategy=s, anchor="raw", gate_threshold=0.2)
            m = mrr(fused, gold)
            agg[s].append(m); row[s + "_mrr"] = round(m, 3)
            if s == "gated_agreement":
                row["gated_dropped"] = dropped
                row["agree_weights"] = {k: round(v, 2) for k, v in
                                        fuse(rankings, "agreement", "raw")[1].items()}
        per.append(row)

    means = {s: round(statistics.mean(agg[s]), 4) for s in ["raw_only"] + STRATS}
    ev = {
        "experiment": "hswm_fusion_impl_ml6",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "ML6-hswm-fusion-impl",
        "engine": "hswm_fusion.py (PROM Step3/4 primitive)",
        "sources": {"web": "real WebSearch 2026-07-21", "kg": "real Neo4j home canon", "corpus_chunks": len(chunks)},
        "mean_MRR": means,
        "per_concept": per,
        "hypothesis_test": {
            "gated_beats_blind": means["gated_agreement"] > means["blind"],
            "agreement_beats_blind": means["agreement"] > means["blind"],
            "best_strategy": max(STRATS, key=lambda s: means[s]),
            "gated_gain_over_blind": round(means["gated_agreement"] - means["blind"], 4),
            "gated_vs_raw_only": round(means["gated_agreement"] - means["raw_only"], 4),
        },
        "note": "blind=ML5 재현(net-zero). gated/agreement가 노이즈場 배제/down-weight로 blind 이기면 HSWM fix 실증. anchor=raw 신뢰기준.",
    }
    out = HERE / "evidence" / "EVIDENCE_hswm_fusion_ml6_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
