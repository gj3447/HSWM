"""ooptdd behavior receipt — weight_field.py actual-coverage battery (A5 side finding).

Premise being closed: PROM_OOPTDD_PROGRAMME_REVIEW_2026-07-24 prediction #2 measured
`weight_field 0/11 (shallow binding)` — receipt_cosine_floor binds weight_field.py by
sha but exercises only `_unit`, so ALL 11 single-fault mutants of weight_field survive
that receipt. Source binding is not actual coverage. Re-measured 2026-07-28 against
sha 29c9b95d4c8e...: still 0/11.

This receipt is the declared battery: one check per mutant cell, each computing the
expected value through an INDEPENDENT re-implementation (plain loops / math.log), so
a fault in weight_field's formula cannot move the expectation with it.

The 11 cells (ooptdd.mutate.collect_sites on weight_field.py @ 29c9b95d4c8e):

  cell  site                  meaning                                  killed by
  ----  --------------------  ---------------------------------------  ---------
   1    binop@54.11 Add->Sub  combine: alpha - lam*log(b) sign flip     W1 (+W5)
   2    binop@54.19 Mult->Add combine: alpha + (lam + log b) shift      W1 (+W5)
   3    binop@80.32 Add->Sub  _ranks: arange(1, n-1) rank vector        W2 (+W3)
   4    binop@90.11 Add->Sub  rrf: outer term join a+b+c -> (a+b)-c     W3
   5    binop@90.11 Add->Sub  rrf: inner term join -> (a-b)+c           W3
   6    binop@90.18 Add->Sub  rrf: 1/(k - rank_cos)                     W3
   7    binop@90.43 Add->Sub  rrf: 1/(k - rank_freq)                    W3
   8    binop@90.68 Add->Sub  rrf: 1/(k - rank_rec)                     W3
   9    cmp@112.34.0 NotEq->Eq  WeightField M-shape guard inverted      W4a
  10    cmp@114.40.0 Lt->LtE    lam guard rejects lam == 0              W4b
  11    cmp@122.15.0 NotEq->Eq  target_emb shape guard inverted         W4c

Declared exclusions: none — all 11 are semantic faults, none equivalent.

ooptdd gates: (1) pre-run locked trace (LOCK below, hashed statically by the
harness) (2) real execution (3) positive readback (4) source binding (sha printed)
(5) negative oracle (corrupted combine breaks W1; corrupted rrf breaks W3; a
one-directional guard checker is rejected by negW4).

Run:  PYTHONPATH=<HSWM repo root> python receipt_weight_field.py   (exit 0 = valid)
Intended home: receipts/receipt_weight_field.py in GIT/HSWM (then plain
`uv run python receipts/receipt_weight_field.py` works; chain via
`python -m ooptdd.run_receipt receipts/receipt_weight_field.py
  --source weight_field.py --mutation-target weight_field.py --max-mutants 11`).
"""
from __future__ import annotations

import hashlib
import math
import os
import sys
from types import SimpleNamespace

import numpy as np

# Runnable both from receipts/ inside the repo and from an external lane dir
# with PYTHONPATH pointing at the repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.getcwd(), os.path.dirname(_HERE)):
    if os.path.exists(os.path.join(_cand, "weight_field.py")) and _cand not in sys.path:
        sys.path.insert(0, _cand)

import weight_field as wf
from hypergraph import Hypergraph
from weight_field import WeightField, _ranks, combine, rrf_scorer

LOCK = {
    "W1_combine_algebra": "combine(alpha,b,lam) == alpha + lam*log(clip(b,1e-6)) elementwise (independent math.log recompute; rows at b=1, b=e, b<clip)",
    "W2_rank_vector": "_ranks(scores) == descending 1..n positions (independent argsort-free recompute on distinct scores)",
    "W3_rrf_exact": "rrf_scorer == sum_i 1/(60 + rank_i) over cosine/frequency/recency (independent rank + reciprocal recompute, tol 1e-12)",
    "W4_guard_battery": "each __init__ guard fires BOTH ways: valid input constructs AND invalid input raises ValueError (M shape / lam>=0 incl lam==0 / target_emb shape)",
    "W5_field_wiring": "WeightField.value == independent cos+bilinear+combine recompute (field reads THIS formula, not a copy)",
    "negative_oracle": "sign-flipped combine breaks W1; sign-flipped rrf denominator breaks W3; a checker that skips the reject-invalid direction is refused by negW4",
}

LOCK_CHECKS = {
    "W1_combine_algebra": "w1_ok",
    "W2_rank_vector": "w2_ok",
    "W3_rrf_exact": "w3_ok",
    "W4_guard_battery": ["w4a_ok", "w4b_ok", "w4c_ok"],
    "W5_field_wiring": "w5_ok",
    "negative_oracle": ["negw1_breaks", "negw3_breaks", "negw4_breaks"],
}

TOL = 1e-12


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


# ---------- independent re-implementations (expectation side) ----------

def _expected_combine(alpha, b, lam):
    out = []
    for a, bb in zip(alpha, b):
        out.append(a + lam * math.log(max(float(bb), 1e-6)))
    return np.array(out)


def _expected_ranks(scores):
    """1 = best, descending; distinct scores only (stable order irrelevant)."""
    out = np.empty(len(scores))
    for i, s in enumerate(scores):
        out[i] = 1 + sum(1 for t in scores if t > s)
    return out


def _expected_rrf(cs, fs, rs, k=60.0):
    rc, rf, rr = _expected_ranks(cs), _expected_ranks(fs), _expected_ranks(rs)
    return np.array([1.0 / (k + rc[i]) + 1.0 / (k + rf[i]) + 1.0 / (k + rr[i])
                     for i in range(len(cs))])


def _guard_ok(construct_valid, reject_invalid):
    """Bidirectional guard verdict — one-directional evidence is refused."""
    return bool(construct_valid) and bool(reject_invalid)


def main() -> int:
    repo = os.path.dirname(os.path.abspath(wf.__file__))
    print(f"source binding: weight_field.py sha256[:12] = {_sha(wf.__file__)} ({wf.__file__})")

    rng = np.random.default_rng(7)

    # ---- W1: combine algebra (cells 1-2) ----
    alpha = np.array([0.2, -0.1, 0.5, 0.0])
    b = np.array([1.0, math.e, 1e-9, 2.5])          # b=1 (log=0), b=e (log=1), clip row
    lam = 0.15
    got = combine(alpha, b, lam)
    exp = _expected_combine(alpha, b, lam)
    w1_ok = bool(np.max(np.abs(got - exp)) < TOL)
    print(f"W1 combine algebra: max|got-exp| = {np.max(np.abs(got - exp)):.2e} -> {w1_ok}")

    # ---- W2: rank vector (cell 3) ----
    scores = np.array([0.3, 0.9, 0.1, 0.5])
    w2_got = _ranks(scores)
    w2_exp = _expected_ranks(scores)
    w2_ok = bool(np.array_equal(w2_got, w2_exp))
    print(f"W2 _ranks: got {w2_got.tolist()} exp {w2_exp.tolist()} -> {w2_ok}")

    # ---- W3: RRF exact (cells 4-8, re-covers 3) ----
    d = 4
    pooled = rng.standard_normal((3, d))
    q = rng.standard_normal(d)
    fake_hg = SimpleNamespace(edge_freq=np.array([5.0, 1.0, 3.0]),
                              edge_recency=np.array([0.2, 0.9, 0.5]))
    edges = np.arange(3)
    got_rrf = rrf_scorer(fake_hg, q, edges, pooled=pooled)
    # independent cosine for the expectation
    pe = pooled / np.clip(np.linalg.norm(pooled, axis=-1, keepdims=True), 1e-12, None)
    cs = pe @ (q / max(np.linalg.norm(q), 1e-12))
    exp_rrf = _expected_rrf(cs, fake_hg.edge_freq, fake_hg.edge_recency)
    w3_ok = bool(np.max(np.abs(got_rrf - exp_rrf)) < TOL)
    print(f"W3 rrf exact: max|got-exp| = {np.max(np.abs(got_rrf - exp_rrf)):.2e} -> {w3_ok}")

    # ---- W4: guard battery (cells 9-11) ----
    hg = Hypergraph(
        node_emb=rng.standard_normal((5, d)),
        members=[np.array([0, 1]), np.array([2]), np.array([3, 4])],
        edge_freq=np.array([1.0, 2.0, 3.0]),
        edge_recency=np.array([0.1, 0.5, 0.9]),
    )

    def _constructs(**kw):
        try:
            WeightField(hg, **kw)
            return True
        except ValueError:
            return False

    # W4a — M shape guard (cell 9)
    w4a_ok = _guard_ok(_constructs(M=np.eye(d)),
                       not _constructs(M=np.zeros((d, d + 1))))
    # W4b — lam guard, lam==0 must be legal (cell 10)
    w4b_ok = _guard_ok(_constructs(lam=0.0), not _constructs(lam=-0.5))
    # W4c — target_emb shape guard (cell 11)
    w4c_ok = _guard_ok(_constructs(target_emb=rng.standard_normal((hg.M, d))),
                       not _constructs(target_emb=rng.standard_normal((hg.M + 1, d))))
    print(f"W4 guards: M-shape={w4a_ok} lam(0 legal, <0 refused)={w4b_ok} target_emb-shape={w4c_ok}")

    # ---- W5: field wiring (redundant kill cover for cells 1-2) ----
    field = WeightField(hg, M=np.eye(d), lam=0.15)
    got_v = field.value(q)
    pooled_hg = hg.pooled_emb("mean")
    peh = pooled_hg / np.clip(np.linalg.norm(pooled_hg, axis=-1, keepdims=True), 1e-12, None)
    qu = q / max(np.linalg.norm(q), 1e-12)
    alpha_exp = (peh @ np.eye(d)) @ qu
    exp_v = _expected_combine(alpha_exp, hg.base_salience, 0.15)
    w5_ok = bool(np.max(np.abs(got_v - exp_v)) < TOL)
    print(f"W5 field wiring: max|value-exp| = {np.max(np.abs(got_v - exp_v)):.2e} -> {w5_ok}")

    # ---- negative oracles ----
    # negW1: sign-flipped combine (the cell-1 fault, applied locally) must be caught
    corrupted_combine = alpha - lam * np.log(np.clip(b, 1e-6, None))
    negw1_breaks = bool(np.max(np.abs(corrupted_combine - exp)) >= TOL)
    print(f"negW1: sign-flipped combine max dev = {np.max(np.abs(corrupted_combine - exp)):.2e} -> {'breaks' if negw1_breaks else 'FAILED-to-break'}")

    # negW3: sign-flipped rrf denominator (the cell-6 fault) must be caught
    rc = _expected_ranks(cs)
    corrupted_rrf = np.array([1.0 / (60.0 - rc[i]) + 1.0 / (60.0 + _expected_ranks(fake_hg.edge_freq)[i])
                              + 1.0 / (60.0 + _expected_ranks(fake_hg.edge_recency)[i]) for i in range(3)])
    negw3_breaks = bool(np.max(np.abs(corrupted_rrf - exp_rrf)) >= TOL)
    print(f"negW3: sign-flipped rrf denom max dev = {np.max(np.abs(corrupted_rrf - exp_rrf)):.2e} -> {'breaks' if negw3_breaks else 'FAILED-to-break'}")

    # negW4: a one-directional guard checker (ignoring reject-invalid) must be refused
    negw4_breaks = not _guard_ok(True, False) and not _guard_ok(False, True)
    print(f"negW4: one-directional guard evidence -> {'refused' if negw4_breaks else 'ACCEPTED (vacuous)'}")

    ok = (w1_ok and w2_ok and w3_ok and w4a_ok and w4b_ok and w4c_ok and w5_ok
          and negw1_breaks and negw3_breaks and negw4_breaks)
    print("\nRECEIPT:", "VALID" if ok else "INVALID",
          f"| W1={w1_ok} W2={w2_ok} W3={w3_ok} W4a={w4a_ok} W4b={w4b_ok} W4c={w4c_ok} "
          f"W5={w5_ok} negW1={negw1_breaks} negW3={negw3_breaks} negW4={negw4_breaks}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
