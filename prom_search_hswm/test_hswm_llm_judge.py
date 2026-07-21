#!/usr/bin/env python3
"""
ML7 — HSWM 완성: LLM-judge 場-품질 가중 (DAT식). PROM→HSWM의 마지막 크럭스.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML7-hswm-llm-judge
ML6: 값싼 통계 가중(agreement/confidence)은 blind를 못 이김(helpful/harmful 구분 불가).
DAT(arXiv:2503.23013): LLM이 각 場의 검색결과를 판정해 per-query 가중 → uniform 능가.
구현: 각 場의 top-1 검색청크를 vLLM(qwen3.6-27b, enable_thinking=false)이 "질의에 답하나 0-10" 판정
      → weight=score/10 → external-weighted RRF(hswm_fusion). 0점 場은 배제.
metric = mean MRR. llm_judge vs blind(=ML5) vs raw. LLM 판정은 evidence에 캐시(replay).
"""
import json, sys, subprocess, re, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from hswm_fusion import fuse, _ranks_from_scores

BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
SEED = 333
CM = "/tmp/cm-dgx-judge"   # ControlMaster 소켓 (재사용)

def chunk_book():
    out = []
    for f in sorted(BOOK.glob("chapter*.md")):
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            t = " ".join(para.split())
            if len(t) >= 90 and not t.startswith("#") and not t.startswith("!["):
                out.append(t)
    return out

def llm_relevance(query, passage):
    """vLLM 판정: 0-10 정수. ssh ControlMaster 재사용. 실패 시 None."""
    prompt = ("Rate on a 0-10 integer scale how well the passage answers or is relevant to the query. "
              "10=directly answers, 0=unrelated.\nQuery: " + query + "\nPassage: " + passage[:400] +
              "\nOutput ONLY the integer, nothing else.")
    payload = json.dumps({"model": "qwen3.6-27b",
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 16, "temperature": 0,
                          "chat_template_kwargs": {"enable_thinking": False}})
    try:
        r = subprocess.run(
            ["ssh", "-o", f"ControlPath={CM}", "dgx",
             "curl -s -m 45 http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d @-"],
            input=payload, capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        content = d["choices"][0]["message"]["content"]
        m = re.search(r"\d+", content)
        if m:
            return max(0, min(10, int(m.group())))
    except Exception as e:
        print(f"  llm_relevance fail: {e}", file=sys.stderr)
    return None

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

    agg = {"raw": [], "blind": [], "llm_judge": []}
    per = []
    for c in src:
        anchor = c["anchor"].lower()
        gold = [i for i, t in enumerate(chunks) if anchor in t.lower()]
        reps = {"raw": c["query"], "web": c["query"] + " . " + c["web"], "kg": c["query"] + " . " + c["kg"]}
        Q = model.encode(list(reps.values()), normalize_embeddings=True, convert_to_numpy=True)
        rankings = {name: (Q[i] @ C.T).tolist() for i, name in enumerate(reps)}

        # LLM-judge: 각 場 top-1 청크의 질의 관련도
        llm_w = {}
        judged = {}
        for name in reps:
            top1 = max(range(len(chunks)), key=lambda i: rankings[name][i])
            score = llm_relevance(c["query"], chunks[top1])
            llm_w[name] = (score / 10.0) if score is not None else 0.5
            judged[name] = {"top1_score_0_10": score, "top1_preview": chunks[top1][:60]}

        raw_mrr = mrr(rankings["raw"], gold)
        blind_fused, _, _ = fuse(rankings, strategy="blind")
        llm_fused, w_used, dropped = fuse(rankings, strategy="external", anchor="raw", external_weights=llm_w)
        row = {"concept": c["key"],
               "raw_mrr": round(raw_mrr, 3),
               "blind_mrr": round(mrr(blind_fused, gold), 3),
               "llm_judge_mrr": round(mrr(llm_fused, gold), 3),
               "llm_weights": {k: round(v, 2) for k, v in llm_w.items()},
               "dropped": dropped, "judged": judged}
        agg["raw"].append(raw_mrr)
        agg["blind"].append(mrr(blind_fused, gold))
        agg["llm_judge"].append(mrr(llm_fused, gold))
        per.append(row)
        print(f"  {c['key']:12s} raw={row['raw_mrr']} blind={row['blind_mrr']} llm={row['llm_judge_mrr']} w={row['llm_weights']}", file=sys.stderr)

    means = {k: round(statistics.mean(v), 4) for k, v in agg.items()}
    ev = {
        "experiment": "hswm_llm_judge_ml7",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "ML7-hswm-llm-judge",
        "method": "DAT-style LLM-judge per-field top-1 relevance → external-weighted RRF (qwen3.6-27b, thinking off)",
        "sources": {"web": "real WebSearch", "kg": "real Neo4j", "judge": "dgx vLLM qwen3.6-27b", "corpus_chunks": len(chunks)},
        "mean_MRR": means,
        "per_concept": per,
        "hypothesis_test": {
            "llm_judge_beats_blind": means["llm_judge"] > means["blind"],
            "llm_judge_beats_raw": means["llm_judge"] > means["raw"],
            "gain_over_blind": round(means["llm_judge"] - means["blind"], 4),
        },
        "caveat": "gold=anchor-string presence(crude, 52+ gold/concept, ceiling). LLM 판정은 top-1 청크 대상(DAT식). n=6 concept. 6*3=18 vLLM calls 캐시됨.",
    }
    out = HERE / "evidence" / "EVIDENCE_hswm_llm_judge_ml7_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
