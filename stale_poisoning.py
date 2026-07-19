"""T4 — stale-poisoning falsifier (spec §4/§8 H-T3, scoped first pass).

The ONE surviving novelty corner (prior-art tribunal C1+C3) is the CONJUNCTION:
a single non-destructive supersede write re-routes retrieval AND multi-hop
propagation around stale knowledge while keeping it auditable. This file gives
that claim its teeth — it can KILL the claim, not just support it.

Design (prereg constants below; spec §2.2 fixes the injection so the designer
has no degrees of freedom over the (c)-vs-(d) effect size):
  For every query with ≥2 gold paragraphs, inject ONE contradicting stale twin
  of its hardest gold bridge (same entity members; embedding synthesized from
  the bridge's own cached bge-m3 vector so that cos(query, stale) is within
  STALE_COS_TOL of cos(query, bridge) — a maximally confusable stale fact),
  then supersede it at each dose in B_DOSE_GRID.

Arms (scoped — arm (e) separated-graded is DEFERRED, so kill (iii) stays OPEN):
  (a) pointwise W = cosine + λ_b·log b   (the deployed supersession readout)
  (b) bi-temporal hard filter (Zep/Graphiti-faithful): stale EXCLUDED from
      current-mode candidates; audit-mode = point-in-time ⇒ audit-recall 1.0
      BY CONSTRUCTION (acknowledged upfront — no weakened rival, house rule)
  (c) traversal probe μ=0.4, κ=0        (ablation: no supersession conductance)
  (d) traversal probe μ=0.4, κ=1        (the design: b damps propagation)
  NOTE: traversal certification REFUSED μ>0 on these worlds (T5) — (c)/(d) are
  MECHANISM PROBES of the falsifier, not deployed configurations.

Metrics (per dose, paired over queries):
  stale_support@10   injected stale edge appears in top-10  (lower = better)
  current_recall@10  true gold recovered in top-10          (higher = better)
  audit_recall@10    stale reachable when EXPLICITLY audited (query = stale's
                     own embedding); graded arms keep b>0 ⇒ reachable
                     (Eilu-va-Eilu); (b) = 1.0 by construction
  dose_response ρ    Spearman(dose, stale rank): graded decay expresses a
                     monotone dose→rank curve; a binary filter structurally
                     cannot (rank constant) — the prereg metric where one-field
                     graded supersession can BEAT the filter

Kill conditions (spec §4 v2):
  (i)  (d) fails to beat (c) on stale_support by >2×SE  ⇒ supersession-in-
       traversal contributes nothing ⇒ novelty sentence DIES
  (ii) (b) matches (d) on current_recall AND audit AND dose-response (all 3)
       ⇒ graded one-field decay collapses into filter+audit-mode ⇒ retract
  (iii) DEFERRED with arm (e)

H-T3b (co-published collateral): supersede the CORRECT bridge at each dose and
measure current_recall damage — "one wrong write, four corruptions" is the dual
of "one write, four effects" and MUST ship next to any positive claim.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass

import numpy as np

import traversal as tv
import world_builder as wb
from hypergraph import Hypergraph
from weight_field import WeightField

STALE_PER_Q = 1
STALE_COS_TOL = 0.02
B_DOSE_GRID = (0.5, 0.25, 0.1)
PROBE_MU = 0.4
K_METRIC = 10
LAM_B = 0.15            # weight_field.combine default — the deployed λ_b


@dataclass
class PoisonedWorld:
    hg: Hypergraph                 # M + n_inj edges; base_salience carries the dose
    unit_emb: np.ndarray
    stale_of: dict[int, int]       # query idx -> injected stale edge id
    bridge_of: dict[int, int]      # query idx -> the poisoned gold bridge edge id
    cos_err: float                 # max |cos(q,stale) - cos(q,bridge)| achieved


def inject(world: wb.BuiltWorld, q_embs: np.ndarray, dose: float,
           seed: int = 0) -> PoisonedWorld:
    """Inject one stale twin per eligible query; supersede it to b=dose."""
    rng = np.random.default_rng(seed * 7013 + 11)
    hg = world.hg
    unit = hg.unit_emb
    members = [m.copy() for m in hg.members]
    new_emb, stale_of, bridge_of = [], {}, {}
    max_err = 0.0
    for qi, q in enumerate(world.queries):
        if q.gold.size < 2:
            continue
        qe = q_embs[qi] / max(np.linalg.norm(q_embs[qi]), 1e-12)
        cos_gold = unit[q.gold] @ qe
        # threat model: the stale twin of the MOST retrievable gold ("this WAS
        # the answer once") — argmax-cos proxy for the spec's 'bridge' absent
        # hop-chain metadata. (argmin-cos was tried first and is a strawman:
        # the twin starts at the bottom, so no dose has anything to sink —
        # caught by the dose-monotonicity teeth test.)
        bridge = int(q.gold[int(np.argmax(cos_gold))])
        be = unit[bridge]
        # synthesize stale embedding near the bridge, cosine-to-query matched:
        # perturb in the subspace ⊥ query so cos(q, ·) barely moves
        for scale in (0.05, 0.02, 0.008):
            n = rng.standard_normal(be.size)
            n -= (n @ qe) * qe
            n /= max(np.linalg.norm(n), 1e-12)
            cand = be + scale * n
            cand /= max(np.linalg.norm(cand), 1e-12)
            err = abs(float(cand @ qe) - float(be @ qe))
            if err <= STALE_COS_TOL:
                break
        max_err = max(max_err, err)
        eid = hg.M + len(new_emb)
        members.append(hg.members[bridge].copy())        # contradicts the SAME fact
        new_emb.append(cand)
        stale_of[qi] = eid
        bridge_of[qi] = bridge
    n_inj = len(new_emb)
    hg2 = Hypergraph(node_emb=hg.node_emb, members=members,
                     edge_freq=np.concatenate([hg.edge_freq, np.ones(n_inj)]),
                     edge_recency=np.concatenate([hg.edge_recency, np.zeros(n_inj)]))
    hg2.base_salience[hg.M:] = dose                      # the supersede write(s)
    ue = np.vstack([unit, np.stack(new_emb)]) if n_inj else unit.copy()
    hg2.unit_emb = ue                                    # type: ignore[attr-defined]
    return PoisonedWorld(hg=hg2, unit_emb=ue, stale_of=stale_of,
                         bridge_of=bridge_of, cos_err=max_err)


def _field(pw: PoisonedWorld, with_b: bool) -> WeightField:
    f = WeightField(pw.hg if with_b else _b1(pw.hg), lam=LAM_B)
    f._pooled = pw.unit_emb
    return f


def _b1(hg: Hypergraph) -> Hypergraph:
    hg2 = Hypergraph(node_emb=hg.node_emb, members=hg.members,
                     edge_freq=hg.edge_freq, edge_recency=hg.edge_recency)
    hg2.unit_emb = hg.unit_emb          # type: ignore[attr-defined]
    return hg2                          # base_salience reset to ones


def _rank_of(scores: np.ndarray, eid: int) -> int:
    order = np.argsort(-scores, kind="stable")
    return int(np.flatnonzero(order == eid)[0]) + 1


def arm_scores(arm: str, pw: PoisonedWorld, qe: np.ndarray,
               index: tv.TraversalIndex) -> np.ndarray:
    if arm == "a":                       # pointwise deployed field (b active)
        return _field(pw, with_b=True).value(qe)
    if arm == "b":                       # bi-temporal: pure relevance, stale filtered
        s = _field(pw, with_b=False).value(qe)
        s[list(pw.stale_of.values())] = -np.inf
        return s
    if arm in ("c", "d"):                # traversal probes (forced μ; mechanism falsifier)
        f = _field(pw, with_b=True)
        kappa = 0 if arm == "c" else 1
        ids, sc, _rc = tv.traverse(f, qe, k=pw.hg.M, mu=PROBE_MU, kappa=kappa, index=index)
        out = np.empty(pw.hg.M)
        out[ids] = sc
        return out
    raise ValueError(arm)


def run(world: wb.BuiltWorld, q_embs: np.ndarray, dataset: str) -> dict:
    arms = ("a", "b", "c", "d")
    per_dose: dict[float, dict] = {}
    stale_rank_by_dose: dict[str, dict[int, list[int]]] = {m: {} for m in arms}

    for dose in B_DOSE_GRID:
        pw = inject(world, q_embs, dose)
        index = tv.build_index(pw.hg)
        res = {m: {"stale": [], "cur": [], "audit": []} for m in arms}
        for qi, stale_eid in pw.stale_of.items():
            qe = q_embs[qi]
            gold = world.queries[qi].gold
            for m in arms:
                s = arm_scores(m, pw, qe, index)
                top = np.argsort(-s, kind="stable")[:K_METRIC]
                res[m]["stale"].append(1.0 if stale_eid in top else 0.0)
                res[m]["cur"].append(float(np.intersect1d(top, gold).size) / gold.size)
                stale_rank_by_dose[m].setdefault(qi, []).append(_rank_of(s, stale_eid))
                if m == "b":
                    res[m]["audit"].append(1.0)          # point-in-time, by construction
                    res[m].setdefault("audit_rank", []).append(1.0)
                else:                                    # audit query = stale's own embedding
                    sa = arm_scores(m, pw, pw.unit_emb[stale_eid], index)
                    res[m]["audit"].append(1.0 if stale_eid in np.argsort(-sa)[:K_METRIC] else 0.0)
                    # reachability ≠ top-10: graded audit is dose-dependent
                    # (the λ·log b penalty applies to the audit query too) —
                    # report the mean rank so that honesty is visible
                    res[m].setdefault("audit_rank", []).append(float(_rank_of(sa, stale_eid)))
        per_dose[dose] = {m: {k: round(float(np.mean(v)), 4) for k, v in r.items()}
                          for m, r in res.items()}
        per_dose[dose]["_n"] = len(pw.stale_of)
        per_dose[dose]["_cos_err_max"] = round(pw.cos_err, 4)

    # ---- dose-response Spearman (dose ↓ ⇒ rank should sink ⇒ negative correlation
    #      between dose and rank; graded arms only) ----
    def spearman(m: str) -> float:
        rhos = []
        doses = np.array(B_DOSE_GRID)
        for qi, ranks in stale_rank_by_dose[m].items():
            r = np.array(ranks, dtype=float)
            if np.ptp(r) == 0:
                rhos.append(0.0)
                continue
            dr = np.argsort(np.argsort(doses)).astype(float)
            rr = np.argsort(np.argsort(r)).astype(float)
            rhos.append(float(np.corrcoef(dr, rr)[0, 1]))
        return round(float(np.mean(rhos)), 4) if rhos else 0.0

    dose_rho = {m: spearman(m) for m in arms}

    # ---- kill conditions (paired, worst dose = 0.1 as primary) ----
    pw = inject(world, q_embs, B_DOSE_GRID[-1])
    index = tv.build_index(pw.hg)
    d_c, d_d = [], []
    for qi, stale_eid in pw.stale_of.items():
        qe = q_embs[qi]
        sc = arm_scores("c", pw, qe, index)
        sd = arm_scores("d", pw, qe, index)
        topc = np.argsort(-sc, kind="stable")[:K_METRIC]
        topd = np.argsort(-sd, kind="stable")[:K_METRIC]
        d_c.append(1.0 if stale_eid in topc else 0.0)
        d_d.append(1.0 if stale_eid in topd else 0.0)
    diff = np.array(d_c) - np.array(d_d)                 # >0 means (d) suppresses more
    se = float(diff.std(ddof=1)) / max(np.sqrt(diff.size), 1.0)
    kill_i_survives = bool(float(diff.mean()) > 2 * se)

    # kill (ii): the filter collapses the novelty ONLY if it catches up on ALL
    # THREE metrics. Sign convention: ρ<0 = dose↓ ⇒ rank sinks = the graded arm
    # EXPRESSES dose-response, which the binary filter structurally cannot
    # (ρ_b ≡ 0) — so a clearly negative ρ_d BLOCKS kill (ii). (First cut had
    # the sign inverted — the better the graded arm expressed dose-response,
    # the harder it "died". Caught on the live run: ρ_a=−0.99, ρ_d=−0.88.)
    b_cur = per_dose[B_DOSE_GRID[-1]]["b"]["cur"]
    d_cur = per_dose[B_DOSE_GRID[-1]]["d"]["cur"]
    graded_expresses_dose = dose_rho["d"] < -0.5
    kill_ii_fires = (b_cur >= d_cur - 0.02) and not graded_expresses_dose

    # ---- H-T3b collateral: supersede the CORRECT bridge, measure damage ----
    collateral = {}
    for dose in B_DOSE_GRID:
        hg3 = Hypergraph(node_emb=world.hg.node_emb, members=world.hg.members,
                         edge_freq=world.hg.edge_freq, edge_recency=world.hg.edge_recency)
        hg3.unit_emb = world.hg.unit_emb                 # type: ignore[attr-defined]
        pw3 = PoisonedWorld(hg=hg3, unit_emb=world.hg.unit_emb, stale_of={},
                            bridge_of={}, cos_err=0.0)
        cur = []
        for qi, q in enumerate(world.queries):
            if q.gold.size < 2:
                continue
            qe = q_embs[qi] / max(np.linalg.norm(q_embs[qi]), 1e-12)
            bridge = int(q.gold[int(np.argmin(world.hg.unit_emb[q.gold] @ qe))])
            old = hg3.base_salience[bridge]
            hg3.base_salience[bridge] = dose             # the WRONG write
            s = _field(pw3, with_b=True).value(q_embs[qi])
            top = np.argsort(-s, kind="stable")[:K_METRIC]
            cur.append(float(np.intersect1d(top, q.gold).size) / q.gold.size)
            hg3.base_salience[bridge] = old
        collateral[dose] = round(float(np.mean(cur)), 4)

    baseline_cur = per_dose[B_DOSE_GRID[0]]              # for context in report
    report = {
        "dataset": dataset,
        "n_poisoned_queries": per_dose[B_DOSE_GRID[0]]["_n"],
        "per_dose": {str(k): v for k, v in per_dose.items()},
        "dose_response_spearman(dose→rank, graded arms should be ρ<0 or >0 monotone)": dose_rho,
        "kill_i": {"survives": kill_i_survives,
                   "mean_stale_suppression_d_vs_c": round(float(diff.mean()), 4),
                   "2se": round(2 * se, 4),
                   "meaning": "novelty tooth ALIVE (d beats c)" if kill_i_survives
                              else "KILL(i): supersession-in-traversal adds nothing over kappa=0"},
        "kill_ii": {"fires": bool(kill_ii_fires),
                    "meaning": "KILL(ii): filter+audit catches up on all 3 → retract" if kill_ii_fires
                               else "kill(ii) does not fire (graded arm keeps a metric the filter cannot express)"},
        "kill_iii": "DEFERRED (arm (e) separated-graded not implemented — OPEN)",
        "collateral_H_T3b_current_recall_after_WRONG_supersede": collateral,
        "scope": "traversal arms are FORCED-μ probes (deployment refused μ>0 in T5); "
                 "pointwise arm (a) is the deployed readout",
    }
    out = f"stale_poisoning_{dataset}_result.json"
    with open(out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    from traversal_cert import build_real_world
    ds = sys.argv[sys.argv.index("--dataset") + 1] if "--dataset" in sys.argv else "musique"
    world, q_e = build_real_world(ds)
    run(world, q_e, ds)
