"""Real-KG run: 4-fold identification demo + SECONDARY link-prediction falsifier.

Uses the cached SYMPOSIUM Neo4j hypergraph (neo4j_loader.py): real 768-dim
ResearchFinding embeddings + real :Hyperedge membership.

Two things happen:
  (1) 4-fold identification demo on the REAL hypergraph — retrieve / plan /
      supersede over one WeightField, on real nodes. Proves the mapper runs on
      real data (Inform axis = 場 정의역 populated).
  (2) SECONDARY link-prediction falsifier (learned bilinear M vs cosine +
      null-head), leakage-controlled: findings are split into CONTEXT (used only
      to pool hyperedges) and QUERY (held out; never in any pool). This is
      EXPLORATORY/confirmatory only — the KG is not a valid primary falsifier
      (DB_AND_FALSIFIER_DECISION §2.8). The primary run is WD50K (follow-up).

Prints only counts / metrics — never embeddings.
"""
from __future__ import annotations

import numpy as np

import metrics
import synth
from hypergraph import Hypergraph
from learned import train_bilinear
from neo4j_loader import load_members
from weight_field import HEURISTICS, WeightField
import readouts

POOL = 60
K = 10
MARGIN = 0.03
TOL = 0.01
CEIL = 0.85


def full_hypergraph(node_emb, members) -> Hypergraph:
    arity = np.array([len(m) for m in members], dtype=np.float64)
    return Hypergraph(node_emb=node_emb, members=members,
                      edge_freq=arity, edge_recency=np.full(len(members), 0.5))


def fourfold_demo(node_emb, members) -> dict:
    hg = full_hypergraph(node_emb, members)
    field = WeightField(hg, M=None)
    q = node_emb[members[0][0]]                       # query = a real finding embedding
    top = readouts.retrieve(field, q, k=5)
    disp = readouts.dispatch(field, q)
    before = readouts.retrieve(field, q, k=hg.M).tolist()
    target = before[0]
    readouts.supersede(field, target, decay=0.001)    # down-weight, not delete
    after = readouts.retrieve(field, q, k=hg.M).tolist()
    return {
        "n_nodes": hg.N, "n_hyperedges": hg.M,
        "retrieve_top5": top.tolist(), "dispatch_argmax": disp,
        "supersede_target": target,
        "rank_before": before.index(target), "rank_after": after.index(target),
        "still_present_after_supersede": target in after,
    }


def build_loo_dataset(node_emb, members, seed, ctx_frac=0.6):
    """Leakage-controlled split: CONTEXT findings pool the hyperedges; QUERY
    findings are held out (never in any pool). Returns a synth.Dataset + splits.
    """
    rng = np.random.default_rng(seed * 977 + 3)
    N = node_emb.shape[0]
    perm = rng.permutation(N)
    n_ctx = int(N * ctx_frac)
    ctx = set(perm[:n_ctx].tolist())

    # context-only member lists; record original membership for gold
    ctx_members, orig_of = [], []
    for m in members:
        cm = np.array([i for i in m.tolist() if i in ctx], dtype=np.int64)
        if cm.size >= 1:
            ctx_members.append(cm)
            orig_of.append(set(m.tolist()))
    if not ctx_members:
        raise RuntimeError("no surviving hyperedges")
    hg = Hypergraph(node_emb=node_emb, members=ctx_members,
                    edge_freq=np.array([len(m) for m in ctx_members], float),
                    edge_recency=np.full(len(ctx_members), 0.5))

    # gold per query finding = surviving hyperedges it originally belonged to
    gold = [np.array([], dtype=np.int64)] * N
    query_nodes = []
    for f in perm[n_ctx:].tolist():
        g = np.array([j for j, orig in enumerate(orig_of) if f in orig], dtype=np.int64)
        if g.size >= 1:
            gold[f] = g
            query_nodes.append(f)
    query_nodes = np.array(query_nodes, dtype=np.int64)
    ds = synth.Dataset(hg=hg, query_emb=node_emb, gold=gold, regime="real-kg-linkpred",
                       hidden_map=None)
    rng.shuffle(query_nodes)
    n_tr = int(len(query_nodes) * 0.6)
    return ds, query_nodes[:n_tr], query_nodes[n_tr:]


def _score(name, hg, q, pool, M_real, M_null):
    if name == "learned":
        return WeightField(hg, M=M_real).value(q, pool)
    if name == "null":
        return WeightField(hg, M=M_null).value(q, pool)
    if name == "cosine":
        return WeightField(hg, M=None).value(q, pool)
    return HEURISTICS[name](hg, q, pool)


def run_real_falsifier(node_emb, members, seeds=(0, 1, 2)) -> dict:
    scorers = ["learned", "null", "cosine", "frequency"]
    per_seed = {s: [] for s in scorers}
    per_seed_em = {s: [] for s in scorers}
    n_test_total = 0
    for seed in seeds:
        ds, train_q, test_q = build_loo_dataset(node_emb, members, seed)
        M_real = train_bilinear(ds, train_q, pool_size=POOL, seed=seed, shuffle_labels=False)
        M_null = train_bilinear(ds, train_q, pool_size=POOL, seed=seed, shuffle_labels=True)
        nd = {s: [] for s in scorers}
        em = {s: [] for s in scorers}
        for q in test_q:
            pool = synth.candidate_pool(ds, int(q), POOL, seed)
            for s in scorers:
                sc = _score(s, ds.hg, ds.query_emb[int(q)], pool, M_real, M_null)
                nd[s].append(metrics.ndcg_at_k(sc, ds.gold[int(q)], pool, k=K, seed=seed))
                em[s].append(metrics.answer_em(sc, ds.gold[int(q)], pool, seed=seed))
        n_test_total += len(test_q)
        for s in scorers:
            per_seed[s].append(float(np.mean(nd[s])))
            per_seed_em[s].append(float(np.mean(em[s])))

    m = {s: float(np.mean(per_seed[s])) for s in scorers}
    em = {s: float(np.mean(per_seed_em[s])) for s in scorers}
    best_heur = max(m["cosine"], m["frequency"])
    best_heur_name = "cosine" if m["cosine"] >= m["frequency"] else "frequency"

    # gates (mirror falsifier)
    lone = m["frequency"]
    verdict, reason = "INCONCLUSIVE", ""
    if lone >= best_heur - TOL and best_heur_name == "frequency":
        verdict, reason = "EXCLUDED", "arity-only shortcut solves it (manipulable)"
    elif best_heur >= CEIL:
        verdict, reason = "EXCLUDED", f"ceiling: best_heuristic {best_heur:.3f} >= {CEIL}"
    else:
        beats_heur = m["learned"] >= best_heur + MARGIN
        beats_null = m["learned"] >= m["null"] + MARGIN
        beats_cos = m["learned"] >= m["cosine"] + MARGIN
        worst_ok = min(per_seed["learned"]) >= min(per_seed[best_heur_name])
        answer_ok = em["learned"] >= em[best_heur_name]
        if beats_heur and beats_null and beats_cos and worst_ok and answer_ok:
            verdict, reason = "SUPPORTED", "learned beats heuristic+null+cosine by margin, no answer regress"
        elif (m["learned"] < best_heur - TOL) or (not beats_null) or (not beats_cos) or (not answer_ok):
            verdict = "REFUTED"
            reason = ("loses to heuristic; " if m["learned"] < best_heur - TOL else "") + \
                     ("null caught up; " if not beats_null else "") + \
                     ("cosine caught up; " if not beats_cos else "") + \
                     ("answer regressed; " if not answer_ok else "")
        else:
            verdict, reason = "INCONCLUSIVE", "mean gain present but not all clauses met"

    return {
        "verdict": verdict, "reason": reason, "n_test_queries": n_test_total,
        "mean_ndcg": {k: round(v, 4) for k, v in m.items()},
        "mean_answer_em": {k: round(v, 4) for k, v in em.items()},
        "best_heuristic": best_heur_name,
        "worst_seed_learned": round(min(per_seed["learned"]), 4),
        "worst_seed_best_heur": round(min(per_seed[best_heur_name]), 4),
    }


def real_judgment_loop_falsifier(node_emb, members, seeds=(0, 1, 2)):
    """Escalate-to-oracle (나생문 formal-cathedral-2): actually run the judgment
    loop on the REAL KG, not just synthetic. Prediction: on cosine-aligned real KG
    (dev≈0 regime) the loop does NOT help (there is no non-cosine residual for the
    judge — even a perfect oracle — to supply). Reports gain±range across seeds.
    Judge is still the simulated oracle (reads real gold); this bounds the BEST a
    real LLM judge could do given this gold, so a non-positive gain is informative.
    """
    from llm_judgment_loop import run_judgment_loop
    gains = []
    for seed in seeds:
        ds, train_q, test_q = build_loo_dataset(node_emb, members, seed)
        r = run_judgment_loop(ds, train_q, test_q, seed=seed, rounds=25)
        gains.append(r["gain"])
    return {"cosine_to_loop_gain_per_seed": gains,
            "mean_gain": round(float(np.mean(gains)), 4),
            "worst_seed_gain": round(float(min(gains)), 4),
            "verdict": "does not help on real KG (cosine-aligned)" if np.mean(gains) <= 0.01
                       else "positive gain — investigate"}


def main():
    import json
    node_emb, members = load_members()
    print("=== 4-FOLD IDENTIFICATION ON REAL KG ===")
    print(json.dumps(fourfold_demo(node_emb, members), indent=2))
    print("\n=== SECONDARY link-prediction falsifier (learned vs heuristic, LOO-clean) ===")
    print(json.dumps(run_real_falsifier(node_emb, members), indent=2, ensure_ascii=False))
    print("\n=== JUDGMENT-LOOP ON REAL KG (나생문 escalate-to-oracle) ===")
    print(json.dumps(real_judgment_loop_falsifier(node_emb, members), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
