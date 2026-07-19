"""LLM-judgment weight loop — the CORRECT "learning" mechanism (user verdict 2026-07-19).

Reframe: the semantic weight field is NOT trained by SGD on structural labels.
The SUBJECT of learning is the LLM; the mechanism is the LLM's JUDGMENT FEEDBACK
LOOP. The LLM inspects the currently-surfaced candidates and judges relevance /
supersession; those judgments adjust the weights. This is gradient-free, online,
and — crucially — can inject NON-cosine relevance (supersede / refute / contextual
importance) that raw embedding cosine cannot capture.

Why this rescues the idea (see REAL_RUN_RESULTS §3, §6): on the real KG, cosine
was near-optimal because the task's relevance = topical similarity = cosine, so
SGD had no residual to learn. The LLM judgment supplies exactly the non-cosine
residual — the dev>=0.5 regime where the headroom sweep showed learning beats
cosine (0.91 vs 0.79). So the two are complementary:

    W(e | c) = cosine(e, c)      # fast, structural, aligned part (near-optimal, free)
             + judgment(e, c)     # non-cosine part, adjusted by the LLM's verdicts

Canon: agent feedback loop (verdict -> root cause -> lesson) = the training signal
(harness Correct axis); 나생문 (Naesengmoon) = the judge.

HONESTY: the default `judge` here is a SIMULATED oracle (it reads the synthetic
ground truth). It proves the LOOP MECHANISM — that judgments propagate into the
weight field and recover non-cosine relevance — NOT that a real LLM judges well.
The real judge is pluggable: pass a callable that calls an Agent / bhgman legion /
Naesengmoon. That real-LLM run is the follow-up.
"""
from __future__ import annotations

import numpy as np

import metrics
import synth


def _unit(x):
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12, None)


def simulated_oracle_judge(ds, q, edges):
    """Stand-in for the LLM judge: returns binary relevance for the surfaced edges.

    Reads ds.gold (the true, possibly non-cosine relevance). A REAL judge would
    instead be an LLM reading the query+edge text and judging relevance /
    supersession — capable of the same non-cosine calls.
    """
    goldset = set(int(g) for g in ds.gold[int(q)])
    return np.array([1.0 if int(e) in goldset else 0.0 for e in edges])


def _softmax(s):
    z = s - s.max()
    e = np.exp(z)
    return e / e.sum()


def run_judgment_loop(ds, train_q, test_q, seed=0, rounds=25, topk_probe=10,
                      lr=0.4, judge=simulated_oracle_judge):
    """LLM-judgment feedback loop over the weight field.

    Start at cosine (M = I). Each round: for each train query, surface the current
    top-`topk_probe` edges, ask the judge for verdicts, and nudge M toward the
    judged-relevant (one gradient-of-InfoNCE step using the JUDGE's labels — the
    judge, not a ground-truth loss, drives the weight adjustment). Track test nDCG.
    """
    d = ds.hg.d
    M = np.eye(d)                                   # round 0 == cosine
    pooled = _unit(ds.hg.pooled_emb("mean"))
    qn = _unit(ds.query_emb)
    all_edges = np.arange(ds.hg.M)

    def score(edges, qi):
        return (pooled[edges] @ M) @ qn[qi]

    def test_ndcg():
        vals = []
        for q in test_q:
            pool = synth.candidate_pool(ds, int(q), 60, seed)
            vals.append(metrics.ndcg_at_k(score(pool, int(q)), ds.gold[int(q)], pool,
                                          k=10, seed=seed))
        return float(np.mean(vals))

    traj = [round(test_ndcg(), 4)]                  # traj[0] = cosine baseline
    for _ in range(rounds):
        grad = np.zeros((d, d))
        n = 0
        for q in train_q:
            # surface current top-K candidates (what the LLM would be shown)
            pool = synth.candidate_pool(ds, int(q), 60, seed)
            s_pool = score(pool, int(q))
            probe = pool[np.argsort(-s_pool)[:topk_probe]]
            verdict = judge(ds, int(q), probe)      # LLM judgment on surfaced edges
            if verdict.sum() == 0:
                continue
            pe = pooled[probe]
            s = (pe @ M) @ qn[int(q)]
            p = _softmax(s)
            y = verdict / verdict.sum()             # judged-relevant = positives
            grad += np.outer(pe.T @ (p - y), qn[int(q)])
            n += 1
        if n:
            M = M - lr * (grad / n)
        traj.append(round(test_ndcg(), 4))
    return {"trajectory": traj, "cosine_baseline": traj[0], "after_loop": traj[-1],
            "gain": round(traj[-1] - traj[0], 4)}


def demo():
    import json
    out = {}
    for dev, tag in [(0.0, "dev0.0 (relevance == cosine; nothing to add)"),
                     (1.0, "dev1.0 (relevance != cosine; judgment must supply it)")]:
        ds = synth.generate("semantics", seed=1, deviation=dev, n_queries=300)
        rng = np.random.default_rng(7)
        perm = rng.permutation(ds.Q)
        ntr = int(ds.Q * 0.6)
        r = run_judgment_loop(ds, perm[:ntr], perm[ntr:], seed=1, rounds=25)
        out[tag] = r
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo()
