"""T4 — stale-poisoning falsifier (spec §4/§8 H-T3, scoped first pass).

This is a falsifier, not a novelty demonstration.  In particular, arm (e)
tests whether a separated revision store can reproduce the graded pointwise
readout without putting revision state inside Hypergraph/WeightField.  If it
can, the retrieval capability is not unique to a one-field representation.

Design (prereg constants below; spec §2.2 fixes the injection so the designer
has no degrees of freedom over the (c)-vs-(d) effect size):
  For every query with ≥2 gold paragraphs, inject ONE contradicting stale twin
  of its hardest gold bridge (same entity members; embedding synthesized from
  the bridge's own cached bge-m3 vector so that cos(query, stale) is within
  STALE_COS_TOL of cos(query, bridge) — a maximally confusable stale fact),
  then supersede it at each dose in B_DOSE_GRID.

Arms:
  (a) pointwise W = cosine + λ_b·log b   (the deployed supersession readout)
  (b) bi-temporal hard filter (Zep/Graphiti-faithful): stale EXCLUDED from
      current-mode candidates; audit-mode = point-in-time ⇒ audit-recall 1.0
      BY CONSTRUCTION (acknowledged upfront — no weakened rival, house rule)
  (c) traversal probe μ=0.4, κ=0        (ablation: no supersession conductance)
  (d) traversal probe μ=0.4, κ=1        (the design: b damps propagation)
  (e) separated-graded: immutable revision metadata lives OUTSIDE
      Hypergraph/WeightField and the readout applies λ_b·log(revision strength)
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
                     cannot (rank constant) — the prereg metric where graded
                     supersession can BEAT the binary filter

Kill conditions (spec §4 v2):
  (i)  (d) fails to beat (c) on stale_support by >2×SE  ⇒ supersession-in-
       traversal contributes nothing ⇒ novelty sentence DIES
  (ii) (b) matches (d) on current_recall AND audit AND dose-response (all 3)
       ⇒ graded decay collapses into filter+audit-mode ⇒ retract
  (iii) (d) fails to beat (e) by >2×SE on every prereg metric ⇒ record the
        separated-graded win; a/e bit-equivalence additionally kills any claim
        that dose-graded pointwise retrieval requires one-field storage

H-T3b (co-published collateral): supersede the CORRECT bridge at each dose and
measure current_recall damage — "one wrong write, four corruptions" is the dual
of "one write, four effects" and MUST ship next to any positive claim.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from hashlib import sha256

import numpy as np

import traversal as tv
import world_builder as wb
import readouts
from hypergraph import Hypergraph
from weight_field import WeightField

STALE_PER_Q = 1
STALE_COS_TOL = 0.02
B_DOSE_GRID = (0.5, 0.25, 0.1)
PROBE_MU = 0.4
K_METRIC = 10
LAM_B = 0.15            # weight_field.combine default — the deployed λ_b
PRIMARY_HOPS = frozenset((2, 3))


@dataclass
class PoisonedWorld:
    hg: Hypergraph                 # M + n_inj edges; base_salience carries the dose
    unit_emb: np.ndarray
    stale_of: dict[int, int]       # query idx -> injected stale edge id
    bridge_of: dict[int, int]      # query idx -> the poisoned gold bridge edge id
    cos_err: float                 # max |cos(q,stale) - cos(q,bridge)| achieved
    revisions: tuple["SeparatedRevision", ...] = ()
    write_receipts: tuple["SupersedeWriteReceipt", ...] = ()


@dataclass(frozen=True)
class SeparatedRevision:
    """Arm (e) revision record, intentionally outside Hypergraph/WeightField.

    ``current_pointer`` is the immutable pointer from the stale revision to the
    currently accepted edge.  ``strength`` is graded rather than a binary
    valid/invalid flag.  The record is consumed only by the separated readout.
    """

    revision_id: str
    edge_id: int
    current_pointer: int
    strength: float


@dataclass(frozen=True)
class SupersedeWriteReceipt:
    """Deterministic receipt proving the experiment used readouts.supersede."""

    write_id: str
    scope: str
    edge_id: int
    decay: float
    before: float
    after: float
    write_path: str = "readouts.supersede"


def _supersede_with_receipt(field: WeightField, edge_id: int, decay: float,
                            *, write_id: str, scope: str) -> SupersedeWriteReceipt:
    before = float(field.hg.base_salience[edge_id])
    readouts.supersede(field, edge_id, decay=decay)
    after = float(field.hg.base_salience[edge_id])
    return SupersedeWriteReceipt(write_id=write_id, scope=scope, edge_id=edge_id,
                                 decay=float(decay), before=before, after=after)


def inject(world: wb.BuiltWorld, q_embs: np.ndarray, dose: float,
           seed: int = 0) -> PoisonedWorld:
    """Inject one stale twin per eligible query; supersede it to b=dose.

    Arm (a)'s state is written through the public ``readouts.supersede`` path.
    Arm (e)'s mirror is an immutable external revision tuple and never mutates
    the Hypergraph or WeightField it reads.
    """
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
    ue = np.vstack([unit, np.stack(new_emb)]) if n_inj else unit.copy()
    hg2.unit_emb = ue                                    # type: ignore[attr-defined]
    write_field = WeightField(hg2, lam=LAM_B)
    write_field._pooled = ue
    receipts = []
    revisions = []
    for qi, eid in stale_of.items():
        receipts.append(_supersede_with_receipt(
            write_field, eid, dose,
            write_id=f"inject:q{qi}:e{eid}:b{dose:g}", scope="injected_stale"))
        revisions.append(SeparatedRevision(
            revision_id=f"revision:q{qi}:e{eid}", edge_id=eid,
            current_pointer=bridge_of[qi], strength=float(dose)))
    return PoisonedWorld(hg=hg2, unit_emb=ue, stale_of=stale_of,
                         bridge_of=bridge_of, cos_err=max_err,
                         revisions=tuple(revisions), write_receipts=tuple(receipts))


def _field(pw: PoisonedWorld, with_b: bool) -> WeightField:
    f = WeightField(pw.hg if with_b else _b1(pw.hg), lam=LAM_B)
    f._pooled = pw.unit_emb
    return f


def _b1(hg: Hypergraph) -> Hypergraph:
    hg2 = Hypergraph(node_emb=hg.node_emb, members=hg.members,
                     edge_freq=hg.edge_freq, edge_recency=hg.edge_recency)
    hg2.unit_emb = hg.unit_emb          # type: ignore[attr-defined]
    return hg2                          # base_salience reset to ones


def _separated_graded_value(pw: PoisonedWorld, qe: np.ndarray) -> np.ndarray:
    """Arm (e): base relevance plus an external, graded revision readout.

    The field is constructed over a b≡1 Hypergraph. Revision strength is then
    applied outside WeightField, which is the strongest separated control in
    the preregistration.  On this fixture it should be bit-identical to arm (a)
    while having a different state boundary.
    """
    score = _field(pw, with_b=False).value(qe)
    strength = np.ones(pw.hg.M, dtype=np.float64)
    for revision in pw.revisions:
        strength[revision.edge_id] = revision.strength
    return score + LAM_B * np.log(np.clip(strength, 1e-6, None))


def _rank_of(scores: np.ndarray, eid: int) -> int:
    order = np.argsort(-scores, kind="stable")
    return int(np.flatnonzero(order == eid)[0]) + 1


def _midranks(values: np.ndarray | list[float] | tuple[float, ...]) -> np.ndarray:
    """Tie-correct ranks: every equal-value group gets its mean position."""
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("midranks requires a 1-D sequence")
    order = np.argsort(x, kind="stable")
    ranks = np.empty(x.size, dtype=np.float64)
    sorted_x = x[order]
    start = 0
    while start < x.size:
        stop = start + 1
        while stop < x.size and sorted_x[stop] == sorted_x[start]:
            stop += 1
        ranks[order[start:stop]] = (start + stop - 1) / 2.0
        start = stop
    return ranks


def _spearman_midrank(x: np.ndarray | list[float] | tuple[float, ...],
                      y: np.ndarray | list[float] | tuple[float, ...]) -> float:
    """Spearman rho with midranks; constant variables have prereg value 0."""
    rx, ry = _midranks(x), _midranks(y)
    if rx.size != ry.size:
        raise ValueError("Spearman inputs must have equal length")
    if rx.size == 0 or np.ptp(rx) == 0 or np.ptp(ry) == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def arm_scores(arm: str, pw: PoisonedWorld, qe: np.ndarray,
               index: tv.TraversalIndex,
               trip_receipts: list[tv.TraversalReceipt] | None = None) -> np.ndarray:
    if arm == "a":                       # pointwise deployed field (b active)
        return _field(pw, with_b=True).value(qe)
    if arm == "b":                       # bi-temporal: pure relevance, stale filtered
        s = _field(pw, with_b=False).value(qe)
        s[list(pw.stale_of.values())] = -np.inf
        return s
    if arm in ("c", "d"):                # traversal probes (forced μ; mechanism falsifier)
        f = _field(pw, with_b=True)
        kappa = 0 if arm == "c" else 1
        ids, sc, rc = tv.traverse(f, qe, k=pw.hg.M, mu=PROBE_MU, kappa=kappa, index=index)
        if trip_receipts is not None:
            trip_receipts.append(rc)
        out = np.empty(pw.hg.M)
        out[ids] = sc
        return out
    if arm == "e":                       # external revision metadata, graded at readout
        return _separated_graded_value(pw, qe)
    raise ValueError(arm)


def _paired_advantage(values: list[float]) -> dict:
    """One-sided paired >2×SE verdict; positive means arm (d) beats arm (e)."""
    a = np.asarray(values, dtype=np.float64)
    mean = float(a.mean()) if a.size else 0.0
    se = (float(a.std(ddof=1)) / np.sqrt(a.size)) if a.size > 1 else 0.0
    return {"n": int(a.size),
            "mean_advantage_d_vs_e": round(mean, 4), "2se": round(2 * se, 4),
            "beats_over_2se": bool(mean > 2 * se)}


def _trip_summary(receipts: list[tv.TraversalReceipt]) -> dict:
    reasons: dict[str, int] = {}
    for rc in receipts:
        if rc.abstained:
            reason = rc.abstain_reason or "unspecified"
            reasons[reason] = reasons.get(reason, 0) + 1
    finite_neff = [float(rc.n_eff) for rc in receipts if np.isfinite(rc.n_eff)]
    return {
        "calls": len(receipts),
        "trips": sum(rc.abstained for rc in receipts),
        "trip_rate": round(sum(rc.abstained for rc in receipts) / max(len(receipts), 1), 4),
        "reasons": dict(sorted(reasons.items())),
        "mean_n_eff_when_measured": (round(float(np.mean(finite_neff)), 4)
                                      if finite_neff else None),
        "greedy_path_entries": sum(len(rc.paths) for rc in receipts),
    }


def _write_summary(receipts: tuple[SupersedeWriteReceipt, ...] | list[SupersedeWriteReceipt]) -> dict:
    canonical = [receipt.__dict__ for receipt in receipts]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return {
        "count": len(canonical),
        "write_path": "readouts.supersede",
        "all_applied_exactly": all(np.isclose(r.after, r.before * r.decay,
                                                rtol=0.0, atol=0.0)
                                     for r in receipts),
        "sha256": sha256(payload.encode()).hexdigest(),
    }


def run(world: wb.BuiltWorld, q_embs: np.ndarray, dataset: str,
        *, write_result: bool = True) -> dict:
    arms = ("a", "b", "c", "d", "e")
    eligible = [(qi, q) for qi, q in enumerate(world.queries) if q.gold.size >= 2]
    hop_composition: dict[int, int] = {}
    for _qi, q in eligible:
        hop_composition[q.hop] = hop_composition.get(q.hop, 0) + 1
    n_primary = sum(n for hop, n in hop_composition.items() if hop in PRIMARY_HOPS)
    if n_primary == 0:
        raise ValueError("H-T3 prereg primary population requires at least one hop-2/3 query")
    per_dose: dict[float, dict] = {}
    raw_by_dose: dict[float, dict] = {}
    trip_by_dose: dict[str, dict] = {}
    write_by_dose: dict[str, dict] = {}
    stale_rank_by_dose: dict[str, dict[int, list[int]]] = {m: {} for m in arms}

    for dose in B_DOSE_GRID:
        pw = inject(world, q_embs, dose)
        index = tv.build_index(pw.hg)
        res = {m: {"stale": [], "cur_hop2_3": [], "cur_all_hops": [],
                   "audit": []} for m in arms}
        trips = {m: {"current": [], "audit": []} for m in ("c", "d")}
        eq_current_abs, eq_audit_abs = [], []
        eq_current_order, eq_audit_order = [], []
        for qi, stale_eid in pw.stale_of.items():
            qe = q_embs[qi]
            gold = world.queries[qi].gold
            current_scores: dict[str, np.ndarray] = {}
            audit_scores: dict[str, np.ndarray] = {}
            for m in arms:
                current_trip_sink = trips[m]["current"] if m in trips else None
                s = arm_scores(m, pw, qe, index, current_trip_sink)
                current_scores[m] = s
                top = np.argsort(-s, kind="stable")[:K_METRIC]
                res[m]["stale"].append(1.0 if stale_eid in top else 0.0)
                cur_recall = float(np.intersect1d(top, gold).size) / gold.size
                res[m]["cur_all_hops"].append(cur_recall)
                if world.queries[qi].hop in PRIMARY_HOPS:
                    res[m]["cur_hop2_3"].append(cur_recall)
                stale_rank_by_dose[m].setdefault(qi, []).append(_rank_of(s, stale_eid))
                if m == "b":
                    res[m]["audit"].append(1.0)          # point-in-time, by construction
                    res[m].setdefault("audit_rank", []).append(1.0)
                else:                                    # audit query = stale's own embedding
                    audit_trip_sink = trips[m]["audit"] if m in trips else None
                    sa = arm_scores(m, pw, pw.unit_emb[stale_eid], index,
                                    audit_trip_sink)
                    audit_scores[m] = sa
                    res[m]["audit"].append(1.0 if stale_eid in np.argsort(-sa)[:K_METRIC] else 0.0)
                    # reachability ≠ top-10: graded audit is dose-dependent
                    # (the λ·log b penalty applies to the audit query too) —
                    # report the mean rank so that honesty is visible
                    res[m].setdefault("audit_rank", []).append(float(_rank_of(sa, stale_eid)))
            cur_delta = np.abs(current_scores["a"] - current_scores["e"])
            audit_delta = np.abs(audit_scores["a"] - audit_scores["e"])
            eq_current_abs.append(float(cur_delta.max(initial=0.0)))
            eq_audit_abs.append(float(audit_delta.max(initial=0.0)))
            eq_current_order.append(bool(np.array_equal(
                np.argsort(-current_scores["a"], kind="stable"),
                np.argsort(-current_scores["e"], kind="stable"))))
            eq_audit_order.append(bool(np.array_equal(
                np.argsort(-audit_scores["a"], kind="stable"),
                np.argsort(-audit_scores["e"], kind="stable"))))
        raw_by_dose[dose] = res
        per_dose[dose] = {m: {k: round(float(np.mean(v)), 4) for k, v in r.items()}
                          for m, r in res.items()}
        for m in arms:
            # Compatibility alias, now explicitly bound to the prereg primary.
            per_dose[dose][m]["cur"] = per_dose[dose][m]["cur_hop2_3"]
        per_dose[dose]["_n"] = len(pw.stale_of)
        per_dose[dose]["_n_all_hops"] = len(pw.stale_of)
        per_dose[dose]["_n_primary_hop2_3"] = n_primary
        per_dose[dose]["_cos_err_max"] = round(pw.cos_err, 4)
        per_dose[dose]["_a_e_equivalence"] = {
            "current_max_abs": max(eq_current_abs, default=0.0),
            "audit_max_abs": max(eq_audit_abs, default=0.0),
            "current_rank_bit_exact": all(eq_current_order),
            "audit_rank_bit_exact": all(eq_audit_order),
        }
        trip_by_dose[str(dose)] = {
            m: {mode: _trip_summary(receipts) for mode, receipts in modes.items()}
            for m, modes in trips.items()
        }
        write_by_dose[str(dose)] = _write_summary(pw.write_receipts)

    # ---- dose-response Spearman (dose ↓ ⇒ rank should sink ⇒ negative correlation
    #      between dose and rank; graded arms only) ----
    def spearman_by_query(m: str) -> dict[int, float]:
        by_query = {}
        doses = np.array(B_DOSE_GRID)
        for qi, ranks in stale_rank_by_dose[m].items():
            r = np.array(ranks, dtype=float)
            if np.ptp(r) == 0:
                by_query[qi] = 0.0
                continue
            by_query[qi] = _spearman_midrank(doses, r)
        return by_query

    rho_by_query = {m: spearman_by_query(m) for m in arms}
    dose_rho = {m: (round(float(np.mean(list(rhos.values()))), 4) if rhos else 0.0)
                for m, rhos in rho_by_query.items()}

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
    b_cur = per_dose[B_DOSE_GRID[-1]]["b"]["cur_hop2_3"]
    d_cur = per_dose[B_DOSE_GRID[-1]]["d"]["cur_hop2_3"]
    graded_expresses_dose = dose_rho["d"] < -0.5
    kill_ii_fires = (b_cur >= d_cur - 0.02) and not graded_expresses_dose

    # kill (iii): prereg says arm (d) must beat the strongest separated-graded
    # control on at least one metric by >2×SE.  Primary point = full dose 0.1;
    # dose-response is paired per query over all three doses.
    primary = raw_by_dose[B_DOSE_GRID[-1]]
    kill_iii_metrics = {
        "stale_suppression": _paired_advantage([
            e - d for e, d in zip(primary["e"]["stale"], primary["d"]["stale"])
        ]),
        "current_recall": _paired_advantage([
            d - e for d, e in zip(primary["d"]["cur_hop2_3"],
                                  primary["e"]["cur_hop2_3"])
        ]),
        "historical_audit_recall": _paired_advantage([
            d - e for d, e in zip(primary["d"]["audit"], primary["e"]["audit"])
        ]),
        "dose_response": _paired_advantage([
            rho_by_query["e"][qi] - rho_by_query["d"][qi]
            for qi in sorted(set(rho_by_query["d"]) & set(rho_by_query["e"]))
        ]),
    }
    d_beats_e = any(metric["beats_over_2se"] for metric in kill_iii_metrics.values())
    equivalence_by_dose = {
        str(dose): per_dose[dose]["_a_e_equivalence"] for dose in B_DOSE_GRID
    }
    a_e_bit_exact = all(
        eq["current_max_abs"] == 0.0 and eq["audit_max_abs"] == 0.0
        and eq["current_rank_bit_exact"] and eq["audit_rank_bit_exact"]
        for eq in equivalence_by_dose.values()
    )

    # ---- H-T3b collateral: supersede the CORRECT bridge, measure damage ----
    collateral = {}
    collateral_all_hops = {}
    collateral_write_by_dose = {}
    for dose in B_DOSE_GRID:
        hg3 = Hypergraph(node_emb=world.hg.node_emb, members=world.hg.members,
                         edge_freq=world.hg.edge_freq, edge_recency=world.hg.edge_recency)
        hg3.unit_emb = world.hg.unit_emb                 # type: ignore[attr-defined]
        pw3 = PoisonedWorld(hg=hg3, unit_emb=world.hg.unit_emb, stale_of={},
                            bridge_of={}, cos_err=0.0)
        field3 = _field(pw3, with_b=True)
        cur_hop2_3, cur_all_hops = [], []
        wrong_write_receipts = []
        for qi, q in enumerate(world.queries):
            if q.gold.size < 2:
                continue
            qe = q_embs[qi] / max(np.linalg.norm(q_embs[qi]), 1e-12)
            bridge = int(q.gold[int(np.argmin(world.hg.unit_emb[q.gold] @ qe))])
            old = hg3.base_salience[bridge]
            wrong_write_receipts.append(_supersede_with_receipt(
                field3, bridge, dose,
                write_id=f"collateral:q{qi}:e{bridge}:b{dose:g}",
                scope="wrong_supersede_gold_bridge"))
            s = field3.value(q_embs[qi])
            top = np.argsort(-s, kind="stable")[:K_METRIC]
            cur_recall = float(np.intersect1d(top, q.gold).size) / q.gold.size
            cur_all_hops.append(cur_recall)
            if q.hop in PRIMARY_HOPS:
                cur_hop2_3.append(cur_recall)
            hg3.base_salience[bridge] = old  # isolate each synthetic wrong-write trial
        collateral[dose] = round(float(np.mean(cur_hop2_3)), 4)
        collateral_all_hops[dose] = round(float(np.mean(cur_all_hops)), 4)
        collateral_write_by_dose[str(dose)] = _write_summary(wrong_write_receipts)

    report = {
        "dataset": dataset,
        "n_poisoned_queries": per_dose[B_DOSE_GRID[0]]["_n"],
        "metric_population": {
            "primary": "hop in {2,3} (preregistered current-fact/H-T3b population)",
            "n_primary_hop2_3": n_primary,
            "n_all_hops": len(eligible),
            "hop_composition_all": {str(k): v for k, v in sorted(hop_composition.items())},
            "cur_alias": "cur == cur_hop2_3; cur_all_hops is reported separately",
        },
        "per_dose": {str(k): v for k, v in per_dose.items()},
        "dose_response_spearman_midrank(dose→rank; graded expected rho<0)": dose_rho,
        "kill_i": {"survives": kill_i_survives,
                   "mean_stale_suppression_d_vs_c": round(float(diff.mean()), 4),
                   "2se": round(2 * se, 4),
                   "meaning": "novelty tooth ALIVE (d beats c)" if kill_i_survives
                              else "KILL(i): supersession-in-traversal adds nothing over kappa=0"},
        "kill_ii": {"fires": bool(kill_ii_fires),
                    "current_population": "hop2-3", "n_current": n_primary,
                    "meaning": "KILL(ii): filter+audit catches up on all 3 → retract" if kill_ii_fires
                               else "kill(ii) does not fire (graded arm keeps a metric the filter cannot express)"},
        "kill_iii": {
            "fires": not d_beats_e,
            "primary_dose": B_DOSE_GRID[-1],
            "current_population": "hop2-3",
            "metrics": kill_iii_metrics,
            "arm_a_vs_e_bit_exact": a_e_bit_exact,
            "meaning": ("KILL(iii): separated-graded arm (e) is not beaten on any prereg "
                        "metric by >2se; one-field-only retrieval capability retracts"
                        if not d_beats_e else
                        "kill(iii) does not fire: arm (d) beats (e) on a prereg metric"),
        },
        "arm_a_vs_e_equivalence_receipt": equivalence_by_dose,
        "pointwise_current_recall_delta_vs_hard_filter": {
            str(dose): round(per_dose[dose]["a"]["cur_hop2_3"]
                             - per_dose[dose]["b"]["cur_hop2_3"], 4)
            for dose in B_DOSE_GRID
        },
        "pointwise_current_recall_delta_vs_hard_filter_all_hops": {
            str(dose): round(per_dose[dose]["a"]["cur_all_hops"]
                             - per_dose[dose]["b"]["cur_all_hops"], 4)
            for dose in B_DOSE_GRID
        },
        "collateral_H_T3b_current_recall_after_WRONG_supersede": collateral,
        "collateral_H_T3b_current_recall_after_WRONG_supersede_all_hops": collateral_all_hops,
        "actual_supersede_write_receipts": {
            "injected_stale": write_by_dose,
            "wrong_supersede_collateral": collateral_write_by_dose,
            "collateral_trial_reset": "direct restore after measurement; not a production write",
        },
        "traversal_trip_receipts": trip_by_dose,
        "scope": "traversal arms are FORCED-μ probes (deployment refused μ>0 in T5); "
                 "pointwise arm (a) is the deployed readout; arm (e) is the external-state control",
    }
    if write_result:
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
