"""Diagnostic learners: capacity-controlled + a real MLP, with early stopping.

Answers "왜 신경망처럼 학습을 못하는가": the v1 learner was a single 768x768
bilinear form (~590k params) trained on hundreds of examples -> overfit. Here we
sweep capacity and add an actual MLP, all with early-stopping on a val split, and
report TRAIN vs TEST so overfitting is visible.

Models (all score a hyperedge e for query q over pooled, unit-normed embeddings):
  cosine   : pe . q                              (0 params — baseline)
  diag     : sum_k w_k pe_k q_k                  (d params)   M = diag(w)
  lowrank  : (pe P) . (q P)                      (d*r params) M = P P^T, r small
  mlp      : MLP([pe; q; pe*q]) -> scalar        (~3d*h params) real neural net
"""
from __future__ import annotations

import numpy as np

import metrics
import synth


def unit(x):
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12, None)


def _softmax(s):
    z = s - s.max()
    e = np.exp(z)
    return e / e.sum()


def score_model(model, PE, q):
    """Scores for pooled edge embeddings PE (K,d) under query q (d,)."""
    PEu, qu = unit(PE), q / max(np.linalg.norm(q), 1e-12)
    k = model["kind"]
    if k == "cosine":
        return PEu @ qu
    if k == "diag":
        return (PEu * qu) @ model["w"]
    if k == "lowrank":
        P = model["P"]
        return (PEu @ P) @ (qu @ P)
    if k == "mlp":
        X = np.concatenate([PEu, np.tile(qu, (len(PEu), 1)), PEu * qu], axis=1)
        H = np.maximum(0, X @ model["W1"] + model["b1"])
        return (H @ model["W2"] + model["b2"]).ravel()
    raise ValueError(k)


def _items(ds, qs, pooled, pool_size, seed):
    out = []
    for q in qs:
        pool = synth.candidate_pool(ds, int(q), pool_size, seed)
        gold = np.intersect1d(ds.gold[int(q)], pool)
        if gold.size == 0:
            continue
        PE = unit(pooled[pool])
        qu = ds.query_emb[int(q)] / max(np.linalg.norm(ds.query_emb[int(q)]), 1e-12)
        goldpos = np.searchsorted(pool, gold)
        out.append((int(q), pool, PE, qu, goldpos))
    return out


def _val_ndcg(model, ds, val_items, seed):
    vals = []
    for q, pool, PE, qu, goldpos in val_items:
        sc = score_model(model, ds.hg.pooled_emb("mean")[pool], ds.query_emb[int(q)])
        vals.append(metrics.ndcg_at_k(sc, ds.gold[int(q)], pool, k=10, seed=seed))
    return float(np.mean(vals)) if vals else 0.0


def train_model(kind, ds, train_q, seed, rank=16, hidden=64,
                epochs=200, lr=0.3, l2=1e-3, patience=6, val_frac=0.25):
    d = ds.hg.d
    rng = np.random.default_rng(seed * 6151 + 17)
    pooled = ds.hg.pooled_emb("mean")
    train_q = np.array(train_q)
    rng.shuffle(train_q)
    n_val = max(1, int(len(train_q) * val_frac))
    val_q, tr_q = train_q[:n_val], train_q[n_val:]
    tr = _items(ds, tr_q, pooled, 60, seed)
    val = _items(ds, val_q, pooled, 60, seed)

    if kind == "cosine":
        return {"kind": "cosine"}, {"train_ndcg": None, "val_ndcg": _val_ndcg({"kind": "cosine"}, ds, val, seed)}
    if kind == "diag":
        model = {"kind": "diag", "w": np.ones(d)}
    elif kind == "lowrank":
        model = {"kind": "lowrank", "P": (np.eye(d, rank) + 0.05 * rng.standard_normal((d, rank)))}
    elif kind == "mlp":
        h = hidden
        model = {"kind": "mlp",
                 "W1": 0.1 * rng.standard_normal((3 * d, h)), "b1": np.zeros(h),
                 "W2": 0.1 * rng.standard_normal((h, 1)), "b2": np.zeros(1)}
    else:
        raise ValueError(kind)

    best_val, best_model, since = -1.0, None, 0
    for ep in range(epochs):
        grads = {kk: np.zeros_like(v) for kk, v in model.items() if kk != "kind"}
        for q, pool, PE, qu, goldpos in tr:
            s = score_model(model, pooled[pool], ds.query_emb[int(q)])
            p = _softmax(s)
            y = np.zeros_like(p)
            y[goldpos] = 1.0 / goldpos.size
            coeff = p - y                                    # (K,)
            if model["kind"] == "diag":
                grads["w"] += (PE * qu).T @ coeff
            elif model["kind"] == "lowrank":
                P = model["P"]
                a = qu @ P                                   # (r,)
                B = PE @ P                                   # (K,r)
                grads["P"] += np.outer(PE.T @ coeff, a) + np.outer(qu, B.T @ coeff)
            elif model["kind"] == "mlp":
                X = np.concatenate([PE, np.tile(qu, (len(PE), 1)), PE * qu], axis=1)
                Hpre = X @ model["W1"] + model["b1"]
                H = np.maximum(0, Hpre)
                grads["W2"] += H.T @ coeff[:, None]
                grads["b2"] += coeff.sum(keepdims=True)
                dH = np.outer(coeff, model["W2"].ravel()) * (Hpre > 0)
                grads["W1"] += X.T @ dH
                grads["b1"] += dH.sum(0)
        n = max(len(tr), 1)
        for kk in grads:
            g = grads[kk] / n + l2 * model[kk]
            model[kk] = model[kk] - lr * g
        if ep % 5 == 0 or ep == epochs - 1:
            v = _val_ndcg(model, ds, val, seed)
            if v > best_val + 1e-4:
                best_val, best_model, since = v, {k2: (v2.copy() if hasattr(v2, "copy") else v2)
                                                  for k2, v2 in model.items()}, 0
            else:
                since += 1
                if since >= patience:
                    break
    model = best_model or model
    tr_nd = float(np.mean([metrics.ndcg_at_k(score_model(model, pooled[p], ds.query_emb[int(q)]),
                                             ds.gold[int(q)], p, k=10, seed=seed)
                           for q, p, _, _, _ in tr])) if tr else 0.0
    return model, {"train_ndcg": round(tr_nd, 4), "val_ndcg": round(best_val, 4)}
