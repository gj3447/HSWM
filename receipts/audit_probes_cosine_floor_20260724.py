"""Adversarial counterexample probes vs the cosine-floor LOCK (F1/F2/F3).

Mechanical side of the cross-model audit (auditor: grok-4 conceptual; this
script executes the 20 problem-space attacks). F1 formula, F2 val-selected
mean-nDCG floor, F3 exact zero-boost — same inline shape as the receipt.
Each probe prints ATTEMPT / OUTCOME / breaks anything?
"""
import numpy as np

rng_master = np.random.default_rng(20260724)
RESULTS = []


def Wscore(peu, qu, M, lam):
    resid = (peu @ M) @ qu
    return (peu @ qu) + lam * np.maximum(0.0, resid), resid


def f1_worst(E, Q, M, lam):
    worst = np.inf
    for q in range(Q.shape[0]):
        w, _ = Wscore(E, Q[q], M, lam)
        worst = min(worst, float(np.min(w - E @ Q[q])))
    return worst  # >= -tol means F1 holds


def f3_worst(E, Q, M, lam):
    worst = 0.0
    for q in range(Q.shape[0]):
        w, resid = Wscore(E, Q[q], M, lam)
        neg = resid <= 0.0
        if neg.any():
            worst = max(worst, float(np.max(np.abs((w - E @ Q[q])[neg]))))
    return worst  # <= 1e-12 means F3 holds (exact zero-boost)


def ndcg(scores, gold):
    order = np.argsort(-scores)
    gains = np.zeros(len(scores))
    gains[gold] = 1.0 / max(len(gold), 1)
    dcg = float(np.sum(gains[order] / np.log2(np.arange(2, len(scores) + 2))))
    ideal = float(np.sum((1.0 / max(len(gold), 1)) / np.log2(np.arange(2, 2 + min(len(gold), len(scores))))))
    return dcg / max(ideal, 1e-12)


def f2_holds(Etr, Qtr, Gtr, Ete, Qte, Gte, grid=(0, 0.5, 1, 2, 4, 8)):
    def mean_ndcg(E, Q, G, lam):
        vals = []
        for q in range(Q.shape[0]):
            w, _ = Wscore(E, Q[q], M_global, lam)
            vals.append(ndcg(w, G[q]))
        return float(np.mean(vals))
    best = -1.0
    for lam in grid:  # val selection, grid includes 0
        best = max(best, mean_ndcg(Etr, Qtr, Gtr, lam))
    cos_val = mean_ndcg(Etr, Qtr, Gtr, 0.0)
    lam_star = max(grid, key=lambda l: mean_ndcg(Etr, Qtr, Gtr, l))
    te_w = mean_ndcg(Ete, Qte, Gte, lam_star)
    te_c = mean_ndcg(Ete, Qte, Gte, 0.0)
    return te_w >= te_c - 1e-12, lam_star, te_w - te_c


def probe(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"EXCEPTION {type(e).__name__}: {e}"
    RESULTS.append((name, ok, detail))
    print(f"[{'holds' if ok else 'BREAKS'}] {name}: {detail}")


def norm_rows(X):
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


d, nE, nQ = 64, 40, 12
M_global = rng_master.normal(size=(d, d)) / np.sqrt(d)
E0 = norm_rows(rng_master.normal(size=(nE, d)))
Q0 = norm_rows(rng_master.normal(size=(nQ, d)))
G0 = [np.array([rng_master.integers(0, nE)]) for _ in range(nQ)]


# 1-4: degenerate embeddings
probe("zero-norm query", lambda: (f1_worst(np.vstack([E0, np.zeros(d)]), Q0, M_global, 1.0) >= -1e-9, "F1 worst finite"))
probe("zero-norm passage", lambda: (np.isfinite(f1_worst(np.vstack([np.zeros(d), E0[1:]]), Q0, M_global, 1.0)), "no NaN/inf in F1"))
probe("all-identical embeddings (cos=1)", lambda: (f1_worst(np.ones((nE, d)) / np.sqrt(d), Q0, M_global, 1.0) >= -1e-9, "F1 worst"))
probe("orthogonal embeddings (cos=0)", lambda: (f1_worst(np.eye(d)[:nE], np.eye(d)[nE:nE+nQ], M_global, 1.0) >= -1e-9, "F1 worst"))

# 5-8: lambda / residual regimes
probe("lambda=0 degenerate (W==cosine)", lambda: (abs(f1_worst(E0, Q0, M_global, 0.0)) < 1e-12 and f3_worst(E0, Q0, M_global, 0.0) <= 1e-12, "F1/F3 exact"))
probe("lambda=1e6 huge", lambda: (f1_worst(E0, Q0, M_global, 1e6) >= -1e-6, f"F1 worst={f1_worst(E0, Q0, M_global, 1e6):+.2e}"))
probe("all-resid<=0 (F3 full-cover)", lambda: (f3_worst(E0, Q0, np.zeros((d, d)), 4.0) <= 1e-12, "M=0 => resid=0 => exact zero-boost"))
probe("all-resid>0 (F3 vacuous side)", lambda: (f1_worst(E0, Q0, np.eye(d) * 5, 4.0) >= -1e-9, "F1 still holds when F3 has no edges"))

# 9-12: candidate-set pathologies
probe("duplicate gold candidates", lambda: (f1_worst(np.vstack([E0, E0[:5]]), Q0, M_global, 1.0) >= -1e-9, "F1 worst"))
probe("single candidate", lambda: (ndcg(Wscore(E0[:1], Q0[0], M_global, 1.0)[0], np.array([0])) == 1.0, "nDCG degenerate=1.0 no crash"))
probe("NaN embeddings", lambda: (not np.isfinite(f1_worst(np.vstack([E0, np.full(d, np.nan)]), Q0, M_global, 1.0)), "NaN propagates (loud, not silent-green)"))
probe("inf-scale embeddings", lambda: (np.isfinite(f1_worst(E0 * 1e8, Q0, M_global, 1.0)), "norm guard keeps finite"))

# 13-16: selection / structure traps
def _winner_curse():
    Etr, Qtr = norm_rows(rng_master.normal(size=(nE, d))), norm_rows(rng_master.normal(size=(nQ, d)))
    Ete, Qte = norm_rows(rng_master.normal(size=(nE, d))), norm_rows(rng_master.normal(size=(nQ, d)))
    Gtr = [np.array([rng_master.integers(0, nE)]) for _ in range(nQ)]
    Gte = [np.array([rng_master.integers(0, nE)]) for _ in range(nQ)]
    ok, lam_star, gap = f2_holds(Etr, Qtr, Gtr, Ete, Qte, Gte)
    return ok, f"lam*={lam_star} test gap={gap:+.4f} (winner's-curse probe)"
probe("winner's-curse (fresh val/test split)", _winner_curse)

def _per_query_scope():
    # known limitation: per-query nDCG can drop even when mean floor holds (receipt documents, does NOT claim)
    viol = 0
    for q in range(Q0.shape[0]):
        w, _ = Wscore(E0, Q0[q], M_global, 4.0)
        if ndcg(w, G0[q]) < ndcg(E0 @ Q0[q], G0[q]) - 1e-12:
            viol += 1
    return True, f"per-query violations={viol}/{nQ} — must be NOT-claimed (scope check)"
probe("per-query floor NOT claimed (scope)", _per_query_scope)
probe("quantized embeddings (int8)", lambda: (f1_worst(norm_rows(np.round(E0 * 15) / 15), Q0, M_global, 1.0) >= -1e-9, "F1 worst"))
probe("rank-1 adversarial M", lambda: (f1_worst(E0, Q0, np.outer(rng_master.normal(size=d), rng_master.normal(size=d)), 1.0) >= -1e-9, "F1 worst"))

# 17-20: structural / scale / seed
probe("M=identity (resid==cos)", lambda: (f1_worst(E0, Q0, np.eye(d), 2.0) >= -1e-9, "W=cos+lam*cos^+ >= cos"))
probe("two candidates only", lambda: (f1_worst(E0[:2], Q0, M_global, 1.0) >= -1e-9, "F1 worst"))
probe("high-dim d=4096 concentration", lambda: (f1_worst(norm_rows(rng_master.normal(size=(nE, 4096))), norm_rows(rng_master.normal(size=(nQ, 4096))), np.eye(4096), 1.0) >= -1e-9, "F1 worst"))
def _seed_sweep():
    worst = np.inf
    for s in range(10):
        r = np.random.default_rng(s)
        E = norm_rows(r.normal(size=(nE, d))); Q = norm_rows(r.normal(size=(nQ, d))); Ms = r.normal(size=(d, d)) / np.sqrt(d)
        for q in range(nQ):
            w, _ = Wscore(E, Q[q], Ms, 2.0)
            worst = min(worst, float(np.min(w - E @ Q[q])))
    return worst >= -1e-9, f"min over 10 seeds={worst:+.2e}"
probe("seed sweep x10", _seed_sweep)

holds = sum(1 for _, ok, _ in RESULTS if ok)
print(f"\n== {holds}/{len(RESULTS)} attacks absorbed; breaks: {[n for n, ok, _ in RESULTS if not ok] or 'none'}")
