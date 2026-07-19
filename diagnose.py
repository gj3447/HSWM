"""Diagnostic: WHY didn't the learned weight beat cosine? Two experiments.

A) Real-KG CAPACITY SWEEP — cosine(0p) / diag(d) / lowrank(d*r) / full-bilinear
   (d^2 ~590k) / mlp. Report TRAIN vs TEST nDCG. If big models have high train,
   low test => overfitting. If nothing beats cosine => ceiling (no residual).

C) Synthetic HEADROOM knob — sweep `deviation` (how far the hidden relevance map
   is from identity/cosine). dev=0: cosine is optimal, learning cannot help.
   dev->1: a learnable non-cosine signal exists. Shows learning DOES beat cosine
   exactly when there is something cosine can't capture — isolating that the real
   KG simply has no such residual.
"""
from __future__ import annotations

import numpy as np

import metrics
import synth
from learned import train_bilinear
from learned_v2 import score_model, train_model
from neo4j_loader import load_members
from real_run import build_loo_dataset
from weight_field import WeightField


def _eval(model, ds, qs, seed, kind):
    pooled = ds.hg.pooled_emb("mean")
    vals = []
    for q in qs:
        if ds.gold[int(q)].size == 0:
            continue
        pool = synth.candidate_pool(ds, int(q), 60, seed)
        if kind == "bilinear":
            sc = WeightField(ds.hg, M=model).value(ds.query_emb[int(q)], pool)
        else:
            sc = score_model(model, pooled[pool], ds.query_emb[int(q)])
        vals.append(metrics.ndcg_at_k(sc, ds.gold[int(q)], pool, k=10, seed=seed))
    return float(np.mean(vals)) if vals else 0.0


def real_capacity_sweep(seeds=(0, 1, 2)):
    node_emb, members = load_members()
    d = node_emb.shape[1]
    caps = [("cosine", {}, 0), ("diag", {}, d), ("lowrank", {"rank": 8}, d * 8),
            ("lowrank", {"rank": 32}, d * 32), ("mlp", {"hidden": 64}, 3 * d * 64)]
    agg = {}
    for seed in seeds:
        ds, train_q, test_q = build_loo_dataset(node_emb, members, seed)
        for name, kw, nparams in caps:
            model, info = train_model(name, ds, train_q, seed, **kw)
            key = f"{name}" + (f"-r{kw['rank']}" if "rank" in kw else
                               f"-h{kw['hidden']}" if "hidden" in kw else "")
            tr = _eval(model, ds, train_q, seed, name)
            te = _eval(model, ds, test_q, seed, name)
            agg.setdefault(key, {"train": [], "test": [], "params": nparams})
            agg[key]["train"].append(tr)
            agg[key]["test"].append(te)
        M = train_bilinear(ds, train_q, pool_size=60, seed=seed)
        agg.setdefault("full-bilinear", {"train": [], "test": [], "params": d * d})
        agg["full-bilinear"]["train"].append(_eval(M, ds, train_q, seed, "bilinear"))
        agg["full-bilinear"]["test"].append(_eval(M, ds, test_q, seed, "bilinear"))
    return {k: {"params": v["params"], "train": round(float(np.mean(v["train"])), 4),
                "test": round(float(np.mean(v["test"])), 4),
                "overfit_gap": round(float(np.mean(v["train"]) - np.mean(v["test"])), 4)}
            for k, v in agg.items()}


def headroom_sweep(devs=(0.0, 0.25, 0.5, 0.75, 1.0), seed=0):
    rows = {}
    for dev in devs:
        ds = synth.generate("semantics", seed=seed, deviation=dev, n_queries=400)
        rng = np.random.default_rng(seed * 13 + 1)
        perm = rng.permutation(ds.Q)
        ntr = int(ds.Q * 0.6)
        train_q, test_q = perm[:ntr], perm[ntr:]
        row = {}
        for name, kw in [("cosine", {}), ("lowrank", {"rank": 16}), ("mlp", {"hidden": 64})]:
            model, _ = train_model(name, ds, train_q, seed, **kw)
            row[name + (f"-r{kw['rank']}" if "rank" in kw else
                        f"-h{kw['hidden']}" if "hidden" in kw else "")] = round(
                _eval(model, ds, test_q, seed, name), 4)
        rows[f"dev={dev}"] = row
    return rows


def main():
    import json
    print("=== (A) REAL-KG CAPACITY SWEEP (train vs test nDCG@10) ===")
    a = real_capacity_sweep()
    print(f"{'model':<16}{'params':>10}{'train':>9}{'test':>9}{'overfit':>9}")
    for k, v in a.items():
        print(f"{k:<16}{v['params']:>10}{v['train']:>9}{v['test']:>9}{v['overfit_gap']:>9}")
    print("\n=== (C) SYNTHETIC HEADROOM SWEEP (test nDCG@10; dev=0 -> cosine optimal) ===")
    c = headroom_sweep()
    print(json.dumps(c, indent=2))


if __name__ == "__main__":
    main()
