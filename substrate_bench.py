"""SUBSTRATE BENCH — HSWM vs strong *memory-substrate* baselines (right category).

User insight: HSWM is not a "hard deep-learning neural net"; it is a hypergraph-backed
semantic weight map (associative-memory structure). So the correct question is NOT
"does it answer better than an LLM" but "is it a better retrieval/organization
structure than other memory substrates". This bench compares, per query, how well each
substrate arm ranks that query's own candidate paragraph pool (~10 for 2wiki, ~20 for
musique) against the gold `is_supporting` flags.

Arms (ALL 0 LLM calls at inference except HSWM's *offline* training budget):
  cosine  — bge-m3 dense similarity (reuses ab_p5_full.Field, lam=0)          [emb, 0 LLM]
  bm25    — Okapi BM25, per-query corpus, pure lexical                        [0 emb, 0 LLM]
  ppr     — HippoRAG-lite: idf-weighted paragraph co-occurrence graph +
            query-seeded Personalized PageRank (spreading activation)         [0 emb, 0 LLM]
  rrf     — Reciprocal Rank Fusion of cosine (+) bm25                         [emb, 0 LLM]
  hswm    — ab_p5_full additive-j field, reconstructed from the run's cached
            offline judgments (100 LLM judgment calls spent OFFLINE to train) [emb, 100 LLM offline]

Budget asymmetry (reported prominently, NOT fair): only HSWM spends 100 offline LLM
judgment calls to train its field. cosine/rrf use embeddings only; bm25/ppr are pure
structure with zero embeddings and zero LLM. If a 0-LLM pure-structure arm matches or
beats the 100-LLM-baked HSWM, that is the more interesting result (structure works vs
LLM-baking works).

Retrieval metrics (cheap, no LLM), all arms x 300 queries (3 dataset+seed runs, 100 each):
  sup_recall@3, nDCG@10, hit@3, MRR (of first gold supporting paragraph).
Downstream F1 (frozen qwen3.6-27b reader, top-3 -> reader): reused from the stored runs
for cosine/hswm/direct; computed for bm25/ppr/rrf with a (query, top-3 id set) cache
(identical top-3 set => identical reader prompt => cache hit => 0 new LLM calls).

`direct` is shown as a labeled REFERENCE CEILING only: it is an *inference-time LLM
reasoner* (100 rerank calls AT inference), NOT a memory substrate — excluded from the
substrate ranking per the task framing.

NO commit / NO LakatoTree submit (parent does that). New file only; ab_p5_full.py untouched.
Output: printed tables + substrate_bench_results.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import string
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import ab_p5_full as A  # reuse Field / loaders / reader / metrics (offline, cache-backed)

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = A.DEFAULT_CACHE
RUNS = [
    ("musique", 7, "ab_p5_full_musique_s7.json"),
    ("musique", 13, "ab_p5_full_musique_s13.json"),
    ("2wiki", 7, "ab_p5_full_2wiki_s7.json"),
]
SUBSTRATE_ARMS = ["cosine", "bm25", "ppr", "rrf", "hswm"]  # direct excluded (reasoner)
METRICS = ["sup_recall_at_3", "ndcg10", "hit_at_3", "mrr"]

_STOP = set(
    "a an the of to in on at for and or but is are was were be been being as by with "
    "from into that this these those it its he she they them his her their who whom "
    "which what when where why how do does did has have had not no s t o m re ve ll d "
    "than then also which whose about over under between during after before".split()
)


# ---------------------------------------------------------------- tokenization
def tokens(text: str) -> list[str]:
    text = text.lower()
    text = "".join(ch if ch not in string.punctuation else " " for ch in text)
    return [w for w in text.split() if len(w) >= 2 and w not in _STOP]


def para_tokens(row: dict) -> list[list[str]]:
    return [tokens(p["title"] + " " + p["paragraph_text"]) for p in row["paragraphs"]]


def _idxs(row: dict) -> list[int]:
    return [p["idx"] for p in row["paragraphs"]]


# ---------------------------------------------------------------- BM25 (per-query corpus)
def bm25_order(row: dict, k1: float = 1.5, b: float = 0.75) -> list[int]:
    docs = para_tokens(row)
    idxs = _idxs(row)
    N = len(docs)
    dls = np.array([len(d) for d in docs], dtype=float)
    avgdl = float(dls.mean()) if N and dls.mean() > 0 else 1.0
    # df over this query's pool
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    q = set(tokens(row["question"]))
    tfs = [{} for _ in range(N)]
    for i, d in enumerate(docs):
        for t in d:
            tfs[i][t] = tfs[i].get(t, 0) + 1
    scores = np.zeros(N)
    for i in range(N):
        s = 0.0
        for t in q:
            f = tfs[i].get(t, 0)
            if f == 0:
                continue
            n_t = df.get(t, 0)
            idf = np.log(1.0 + (N - n_t + 0.5) / (n_t + 0.5))  # BM25+ nonneg idf
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dls[i] / avgdl))
        scores[i] = s
    return [idxs[i] for i in np.argsort(-scores, kind="stable")]


# ---------------------------------------------------------------- PPR (HippoRAG-lite)
def ppr_order(row: dict, restart: float = 0.15, iters: int = 60) -> list[int]:
    """Paragraphs are nodes. Edge weight(i,j) = sum of idf(shared token) — an
    idf-weighted co-occurrence graph so rare (entity-like) shared tokens dominate and
    stopword/common overlap contributes little. Query-seeded Personalized PageRank
    (spreading activation) ranks paragraphs by stationary mass. 0 LLM, 0 embeddings."""
    docs = para_tokens(row)
    idxs = _idxs(row)
    N = len(docs)
    if N == 0:
        return []
    if N == 1:
        return idxs
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    idf = {t: np.log(1.0 + N / c) for t, c in df.items()}
    sets = [set(d) for d in docs]

    W = np.zeros((N, N))
    for i in range(N):
        for j in range(i + 1, N):
            shared = sets[i] & sets[j]
            if not shared:
                continue
            w = float(sum(idf[t] for t in shared))
            W[i, j] = w
            W[j, i] = w

    # query seed: idf-weighted overlap of query terms with each paragraph
    q = set(tokens(row["question"]))
    seed = np.array([sum(idf.get(t, 0.0) for t in (q & sets[i])) for i in range(N)])
    if seed.sum() <= 0:
        seed = np.ones(N)
    seed = seed / seed.sum()

    # column-stochastic transition; dangling (isolated) columns teleport to seed
    col = W.sum(axis=0)
    M = np.zeros((N, N))
    for j in range(N):
        if col[j] > 0:
            M[:, j] = W[:, j] / col[j]
        else:
            M[:, j] = seed
    r = seed.copy()
    for _ in range(iters):
        r = restart * seed + (1 - restart) * (M @ r)
        s = r.sum()
        if s > 0:
            r = r / s
    return [idxs[i] for i in np.argsort(-r, kind="stable")]


# ---------------------------------------------------------------- RRF
def rrf_order(orders: dict[str, list[int]], all_idxs: list[int], K: int = 60) -> list[int]:
    rank = {name: {idx: pos for pos, idx in enumerate(o)} for name, o in orders.items()}
    score = {}
    for idx in all_idxs:
        score[idx] = sum(1.0 / (K + rank[name].get(idx, len(all_idxs))) for name in orders)
    return sorted(all_idxs, key=lambda i: (-score[i], all_idxs.index(i)))


# ---------------------------------------------------------------- retrieval metrics
def mrr(order: list[int], gold: set[int]) -> float:
    for pos, idx in enumerate(order):
        if idx in gold:
            return 1.0 / (pos + 1)
    return 0.0


def retrieval_metrics(order: list[int], gold: set[int], k: int = 3) -> dict:
    top = set(order[:k])
    return {
        "sup_recall_at_3": len(top & gold) / max(1, len(gold)),
        "ndcg10": A.ndcg_at_k(order, gold),
        "hit_at_3": 1.0 if top & gold else 0.0,
        "mrr": mrr(order, gold),
    }


# ---------------------------------------------------------------- HSWM field rebuild
def rebuild_hswm_field(dataset: str, seed: int, llm, cache) -> A.Field:
    """Reconstruct the exact additive-j field of the stored run: cached offline
    judgments (0 new LLM at temp 0) -> PCA fit -> additive train. Deterministic."""
    pool = A.load_pool(dataset, CACHE_DIR)
    train_rows, _ = A.split_pool(pool, 100, 100, seed)
    emb = A.Embedder("bge-m3", cache)
    field = A.Field(emb, 96)
    field.fit_pca(train_rows, seed)
    labeled, _ = A.hswm_offline_judgments(llm, train_rows, 100, 4)
    field.train_additive(labeled, seed)
    return field


# ---------------------------------------------------------------- main compute
def compute_retrieval() -> dict:
    cache = A.DiskCache(CACHE_DIR)
    # llm only needed to (re)read cached judgments for hswm field; temp 0, cache-backed
    llm = A.OpenAIChat("qwen3.6-27b", cache, "http://127.0.0.1:18001/v1", think=False)

    per_query: list[dict] = []  # flat, across all runs
    stored_hswm_check: dict = {}
    stored_direct: dict = {}  # dataset_seed -> per-query direct metrics+f1 (reference ceiling)

    for dataset, seed, stored_json in RUNS:
        tag = f"{dataset}_s{seed}"
        print(f"[retrieval] {tag}: rebuilding HSWM field (cached judgments) ...", flush=True)
        emb = A.Embedder("bge-m3", cache)
        field_cos = A.Field(emb, 96)  # cosine (lam=0) — no training needed
        field_hswm = rebuild_hswm_field(dataset, seed, llm, cache)

        pool = A.load_pool(dataset, CACHE_DIR)
        _, eval_rows = A.split_pool(pool, 100, 100, seed)

        # load stored per-query (for cosine/hswm cross-check + direct ceiling + reused F1)
        with open(os.path.join(HERE, stored_json)) as f:
            stored = json.load(f)
        stored_pq = {r["id"]: r for r in stored["per_query"]}

        hs_sr, hs_sr_stored = [], []
        for row in eval_rows:
            gold = {p["idx"] for p in row["paragraphs"] if p["is_supporting"]}
            idxs = _idxs(row)
            o_cos = field_cos.order(row, lam=0.0)
            o_bm = bm25_order(row)
            o_ppr = ppr_order(row)
            o_rrf = rrf_order({"cosine": o_cos, "bm25": o_bm}, idxs)
            o_hswm = field_hswm.order(row)
            orders = {"cosine": o_cos, "bm25": o_bm, "ppr": o_ppr,
                      "rrf": o_rrf, "hswm": o_hswm}
            rec = {"run": tag, "dataset": dataset, "seed": seed,
                   "id": row["id"], "hop": row["hop"], "n_gold": len(gold),
                   "pool": len(idxs)}
            for arm, o in orders.items():
                rec[arm] = retrieval_metrics(o, gold)
                rec[arm]["top3"] = o[:3]
            per_query.append(rec)

            # cross-check HSWM reconstruction vs stored aggregate inputs
            hs_sr.append(rec["hswm"]["sup_recall_at_3"])
            if row["id"] in stored_pq:
                hs_sr_stored.append(stored_pq[row["id"]]["hswm"]["sup_recall_at_k"])

            # stash direct ceiling (reasoner) + stored F1 for reused arms
            sp = stored_pq.get(row["id"], {})
            stored_direct[row["id"]] = {
                "run": tag,
                "direct": sp.get("direct", {}),
                "cosine_f1": sp.get("cosine", {}).get("f1"),
                "hswm_f1": sp.get("hswm", {}).get("f1"),
                "em": {a: sp.get(a, {}).get("em") for a in ("cosine", "hswm", "direct")},
            }

        stored_hswm_check[tag] = {
            "rebuilt_mean_sup_recall_at_3": round(float(np.mean(hs_sr)), 4),
            "stored_mean_sup_recall_at_k": round(float(np.mean(hs_sr_stored)), 4)
            if hs_sr_stored else None,
            "match": bool(hs_sr_stored)
            and abs(float(np.mean(hs_sr)) - float(np.mean(hs_sr_stored))) < 0.02,
        }
        print(f"[retrieval] {tag}: HSWM rebuild check {stored_hswm_check[tag]}", flush=True)

    return {"per_query": per_query,
            "hswm_rebuild_check": stored_hswm_check,
            "stored_direct": stored_direct,
            # counter increments on cache hits too (ChatBase._count); llm_wall_s ~0
            # confirms these were cached reads, not new judgment compute.
            "hswm_judgment_counter_incl_cache_hits": llm.calls.get("hswm_judgment", 0),
            "hswm_judgment_llm_wall_s": round(llm.wall_s, 2)}


# ---------------------------------------------------------------- aggregation + stats
def aggregate(per_query: list[dict]) -> dict:
    out = {"overall": {}, "by_dataset": {}}
    datasets = sorted({r["dataset"] for r in per_query})

    def agg_over(rows):
        d = {}
        for arm in SUBSTRATE_ARMS:
            d[arm] = {m: round(float(np.mean([r[arm][m] for r in rows])), 4) for m in METRICS}
        return d

    out["overall"] = agg_over(per_query)
    for ds in datasets:
        rows = [r for r in per_query if r["dataset"] == ds]
        out["by_dataset"][ds] = {"n": len(rows), **{"metrics": agg_over(rows)}}
    return out


def significance(per_query: list[dict]) -> dict:
    """Paired bootstrap: HSWM vs each other substrate arm, on sup_recall@3 and nDCG@10."""
    out = {}
    for metric in ("sup_recall_at_3", "ndcg10"):
        hs = [r["hswm"][metric] for r in per_query]
        out[metric] = {}
        for arm in SUBSTRATE_ARMS:
            if arm == "hswm":
                continue
            other = [r[arm][metric] for r in per_query]
            out[metric][f"hswm_vs_{arm}"] = {
                "mean_hswm": round(float(np.mean(hs)), 4),
                "mean_arm": round(float(np.mean(other)), 4),
                "mean_diff_hswm_minus_arm": round(float(np.mean(hs)) - float(np.mean(other)), 4),
                "p_hswm_gt_arm": round(A.paired_bootstrap_p(hs, other, seed=0), 4),
                "p_arm_gt_hswm": round(A.paired_bootstrap_p(other, hs, seed=0), 4),
            }
    return out


def rank_arms(agg: dict) -> dict:
    out = {}
    for metric in METRICS:
        pairs = sorted(SUBSTRATE_ARMS, key=lambda a: -agg["overall"][a][metric])
        out[metric] = [{"arm": a, "value": agg["overall"][a][metric]} for a in pairs]
    return out


# ---------------------------------------------------------------- downstream F1 (reader)
def compute_f1(per_query: list[dict], stored_direct: dict, max_new_calls: int,
               parallel: int = 4) -> dict:
    """New arms (bm25/ppr/rrf): top-3 -> frozen reader -> F1. Reader prompt is a pure
    function of the top-3 id SET (context iterates pool order filtered by set), so an
    identical top-3 set hits the shared disk cache => 0 new LLM. cosine/hswm F1 reused
    from stored runs. Budget-bounded: stops issuing NEW reader calls past max_new_calls
    (cache hits are free and always allowed)."""
    cache = A.DiskCache(CACHE_DIR)
    llm = A.OpenAIChat("qwen3.6-27b", cache, "http://127.0.0.1:18001/v1", think=False)

    # index rows to their pool for reader context
    pools = {}
    for dataset, seed, _ in RUNS:
        pool = A.load_pool(dataset, CACHE_DIR)
        _, ev = A.split_pool(pool, 100, 100, seed)
        for r in ev:
            pools[r["id"]] = r

    new_arms = ["bm25", "ppr", "rrf"]
    new_calls = [0]
    lock = threading.Lock()
    budget_hit = [False]

    def reader_cache_probe(row, order):
        chosen = set(order[:3])
        ctx = "\n\n".join(
            f"{p['title']}: {A._snip(p['paragraph_text'], 1200)}"
            for p in row["paragraphs"] if p["idx"] in chosen
        )
        prompt = A.READER_PROMPT.format(ctx=ctx, q=row["question"])
        key = json.dumps(["openai", "qwen3.6-27b", False, prompt, 256])
        return cache.get("chat", key) is not None

    results = {r["id"]: {} for r in per_query}

    def _one(rec):
        row = pools[rec["id"]]
        golds = [row["answer"]] + list(row.get("answer_aliases") or [])
        for arm in new_arms:
            order = rec[arm]["top3"] + [i for i in _idxs(row) if i not in rec[arm]["top3"]]
            cached = reader_cache_probe(row, order)
            if not cached:
                with lock:
                    if new_calls[0] >= max_new_calls:
                        budget_hit[0] = True
                        results[rec["id"]][arm] = None  # deferred (over budget)
                        continue
                    new_calls[0] += 1
            pred = A.read_answer(llm, f"reader_{arm}", row, order, 3)
            results[rec["id"]][arm] = {
                "f1": round(A.answer_f1(pred, golds), 4),
                "em": A.answer_em(pred, golds),
                "cached": cached,
            }

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        list(ex.map(_one, per_query))

    # aggregate F1: new arms from `results`, cosine/hswm/direct reused from stored
    f1_by_arm = {a: [] for a in ("cosine", "hswm", "bm25", "ppr", "rrf", "direct")}
    em_by_arm = {a: [] for a in ("cosine", "hswm", "bm25", "ppr", "rrf", "direct")}
    n_f1_new = {a: 0 for a in new_arms}
    for rec in per_query:
        qid = rec["id"]
        sd = stored_direct.get(qid, {})
        if sd.get("cosine_f1") is not None:
            f1_by_arm["cosine"].append(sd["cosine_f1"])
            em_by_arm["cosine"].append(sd["em"]["cosine"])
        if sd.get("hswm_f1") is not None:
            f1_by_arm["hswm"].append(sd["hswm_f1"])
            em_by_arm["hswm"].append(sd["em"]["hswm"])
        if sd.get("direct", {}).get("f1") is not None:
            f1_by_arm["direct"].append(sd["direct"]["f1"])
            em_by_arm["direct"].append(sd["direct"]["em"])
        for arm in new_arms:
            v = results[qid].get(arm)
            if v is not None:
                f1_by_arm[arm].append(v["f1"])
                em_by_arm[arm].append(v["em"])
                n_f1_new[arm] += 1

    agg_f1 = {a: {"f1": round(float(np.mean(v)), 4) if v else None,
                  "em": round(float(np.mean(em_by_arm[a])), 4) if em_by_arm[a] else None,
                  "n": len(v)} for a, v in f1_by_arm.items()}

    # paired F1 sig only where full coverage (n==300)
    sig = {}
    full = {a: v for a, v in f1_by_arm.items() if len(v) == len(per_query)}
    if "hswm" in full:
        for a in full:
            if a == "hswm":
                continue
            sig[f"hswm_vs_{a}"] = {
                "p_hswm_gt_arm": round(A.paired_bootstrap_p(full["hswm"], full[a], seed=0), 4),
                "p_arm_gt_hswm": round(A.paired_bootstrap_p(full[a], full["hswm"], seed=0), 4),
            }

    return {
        "aggregate_f1_em": agg_f1,
        "new_reader_calls_issued": new_calls[0],
        "new_arm_f1_coverage": n_f1_new,
        "budget_capped": budget_hit[0],
        "paired_f1_sig_hswm_vs": sig,
        "note": "cosine/hswm/direct F1 reused from stored runs; bm25/ppr/rrf F1 "
                "computed here (cache-shared with stored reader on identical top-3 sets).",
    }


# ---------------------------------------------------------------- reporting
def print_tables(res: dict) -> None:
    agg = res["aggregate"]
    print("\n" + "=" * 78)
    print("SUBSTRATE RETRIEVAL METRICS (mean; 300 queries = 3 runs x 100)")
    print("=" * 78)
    hdr = f"{'arm':<8}" + "".join(f"{m:>16}" for m in METRICS)
    print(hdr)
    for arm in SUBSTRATE_ARMS:
        row = agg["overall"][arm]
        print(f"{arm:<8}" + "".join(f"{row[m]:>16.4f}" for m in METRICS))
    for ds, blk in agg["by_dataset"].items():
        print(f"\n-- {ds} (n={blk['n']}) --")
        print(hdr)
        for arm in SUBSTRATE_ARMS:
            row = blk["metrics"][arm]
            print(f"{arm:<8}" + "".join(f"{row[m]:>16.4f}" for m in METRICS))

    print("\n" + "=" * 78)
    print("RANKING (overall)")
    print("=" * 78)
    for m in METRICS:
        chain = "  >  ".join(f"{r['arm']}={r['value']:.4f}" for r in res["ranking"][m])
        print(f"{m:<16}: {chain}")

    print("\n" + "=" * 78)
    print("HSWM (100 offline LLM) vs each substrate — paired bootstrap")
    print("=" * 78)
    for metric, blk in res["significance"].items():
        print(f"[{metric}]")
        for pair, v in blk.items():
            verdict = ("HSWM>" if v["p_hswm_gt_arm"] < 0.05 else
                       ("<HSWM" if v["p_arm_gt_hswm"] < 0.05 else "~tie"))
            print(f"  {pair:<16} diff={v['mean_diff_hswm_minus_arm']:+.4f}  "
                  f"p(hswm>arm)={v['p_hswm_gt_arm']:.3f}  "
                  f"p(arm>hswm)={v['p_arm_gt_hswm']:.3f}  -> {verdict}")

    if "downstream_f1" in res:
        f = res["downstream_f1"]
        print("\n" + "=" * 78)
        print("DOWNSTREAM F1 (frozen reader, top-3)  [direct = reasoner ceiling, not substrate]")
        print("=" * 78)
        for a, v in f["aggregate_f1_em"].items():
            tag = "  (reasoner-ceiling)" if a == "direct" else ""
            print(f"  {a:<8} F1={str(v['f1']):>7}  EM={str(v['em']):>7}  n={v['n']}{tag}")
        print(f"  new reader calls issued: {f['new_reader_calls_issued']}  "
              f"coverage(new arms): {f['new_arm_f1_coverage']}  capped={f['budget_capped']}")


# ---------------------------------------------------------------- driver
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f1", action="store_true", help="also compute downstream F1 for new arms")
    ap.add_argument("--max-new-calls", type=int, default=600,
                    help="cap on NEW reader calls (cache hits are free/unbounded)")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(HERE, "substrate_bench_results.json"))
    args = ap.parse_args()

    t0 = time.time()
    r = compute_retrieval()
    agg = aggregate(r["per_query"])
    sig = significance(r["per_query"])
    ranking = rank_arms(agg)

    ppr = agg["overall"]["ppr"]
    hswm = agg["overall"]["hswm"]
    pure_vs_baked = {
        "ppr_pure_structure_0_LLM": ppr,
        "hswm_100_offline_LLM": hswm,
        "ppr_matches_or_beats_hswm_on": [
            m for m in METRICS if ppr[m] >= hswm[m] - 0.005
        ],
    }

    result = {
        "label": "SUBSTRATE_BENCH",
        "note": "HSWM vs strong memory-substrate baselines (retrieval-structure category, "
                "NOT reasoner). direct = inference-time LLM reasoner shown as ceiling only.",
        "runs": [f"{d}_s{s}" for d, s, _ in RUNS],
        "n_queries": len(r["per_query"]),
        "budget_asymmetry": {
            "cosine": "bge-m3 embeddings, 0 LLM",
            "bm25": "pure lexical, 0 embeddings, 0 LLM",
            "ppr": "pure structure (idf co-occurrence graph + PPR), 0 embeddings, 0 LLM",
            "rrf": "cosine(+)bm25 fusion, embeddings, 0 LLM",
            "hswm": "bge-m3 embeddings + 100 OFFLINE LLM judgment calls to train additive-j field",
            "direct_reference_ceiling": "100 LLM rerank calls AT INFERENCE — reasoner, not substrate",
            "caveat": "ONLY HSWM (and direct) spend LLM budget. A 0-LLM pure-structure arm "
                      "(ppr/bm25) matching HSWM means structure carries it, not the 100 LLM judgments.",
        },
        "hswm_rebuild_check": r["hswm_rebuild_check"],
        "llm_new_calls_during_rebuild": r["llm_new_calls_during_rebuild"],
        "aggregate": agg,
        "ranking": ranking,
        "significance": sig,
        "pure_structure_vs_llm_baked": pure_vs_baked,
        "per_query": r["per_query"],
    }

    if args.f1:
        print("\n[f1] computing downstream F1 for new arms (reader on 18001) ...", flush=True)
        try:
            result["downstream_f1"] = compute_f1(
                r["per_query"], r["stored_direct"], args.max_new_calls, args.parallel)
        except Exception as e:  # never crash the whole bench on reader hiccup
            result["downstream_f1"] = {"error": str(e),
                                       "note": "retrieval metrics above are complete; F1 partial/failed"}
            print(f"[f1] BLOCKER: {e}", file=sys.stderr, flush=True)

    result["wall_clock_s"] = round(time.time() - t0, 1)
    with open(args.out, "w") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)

    print_tables(result)
    # one-line honest verdict
    over = agg["overall"]
    order_sr = sorted(SUBSTRATE_ARMS, key=lambda a: -over[a]["sup_recall_at_3"])
    hswm_rank = order_sr.index("hswm") + 1
    print("\n" + "=" * 78)
    print(f"HSWM rank among {len(SUBSTRATE_ARMS)} substrates on sup_recall@3: "
          f"#{hswm_rank} ({' > '.join(order_sr)})")
    print(f"pure-structure PPR (0 LLM) matches/beats HSWM (100 offline LLM) on: "
          f"{pure_vs_baked['ppr_matches_or_beats_hswm_on']}")
    print(f"[done] -> {args.out}  ({result['wall_clock_s']}s)")


if __name__ == "__main__":
    main()
