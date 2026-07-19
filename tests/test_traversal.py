"""Traversal harness (T1/T2) — spec PROM_TRAVERSAL_DESIGN §10 mandated tests.

- mu=0 AND gamma=0 each ⇒ bit-identical to retrieve() (structural floor)
- determinism: bit reproduction on same (COO, seed, γ, K, κ, μ)
- kept_mass ≥ 0.99 hard assert (synthetic world ONLY — real-world uses abstain)
- deg-0 node world is NaN-free
- supersede() interacts: κ=1 damps a stale bridge's activation, κ=0 ignores b
- F1 algebraic floor: W_trav ≥ W on every edge (R ≥ 0)
"""
import numpy as np

import readouts
import synth
import traversal as tv
from weight_field import WeightField


def _world(seed=0):
    ds = synth.generate("semantics", seed=seed, n_nodes=80, n_edges=140, n_queries=8)
    return ds, WeightField(ds.hg, M=None)


def test_mu0_and_gamma0_bit_identical_to_retrieve():
    ds, f = _world()
    q = ds.query_emb[0]
    base = readouts.retrieve(f, q, k=10)
    for kw in ({"mu": 0.0}, {"mu": 0.4, "gamma": 0.0}):
        ids, scores, rc = readouts.traverse(f, q, k=10, **kw)
        assert np.array_equal(ids, base), kw
        assert np.array_equal(scores, f.value(q)[ids])   # bit-identical, not approx
        assert rc.abstained and "certified floor" in rc.abstain_reason


def test_deterministic_bit_reproduction():
    ds, f = _world(seed=1)
    q = ds.query_emb[1]
    a = readouts.traverse(f, q, k=10, mu=0.4)
    b = readouts.traverse(f, q, k=10, mu=0.4)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
    assert a[2].kept_mass == b[2].kept_mass and a[2].paths == b[2].paths


def test_kept_mass_hard_assert_synthetic():
    ds, f = _world(seed=2)
    for qi in range(4):
        _, _, rc = readouts.traverse(f, ds.query_emb[qi], k=10, mu=0.4)
        if rc.kept_mass:                      # abstain before hops leaves it empty
            assert min(rc.kept_mass) >= 0.99, rc.kept_mass


def test_zero_degree_node_world_nan_free():
    ds, f = _world(seed=3)
    # add an orphan node bound to no hyperedge (real-KG loads produce these)
    ds.hg.node_emb = np.vstack([ds.hg.node_emb, ds.hg.node_emb[0]])
    idx = tv.build_index(ds.hg)
    assert idx.deg_node[-1] == 1.0            # clip ≥1 (0/0 NaN guard)
    f2 = WeightField(ds.hg, M=None)
    ids, scores, _ = readouts.traverse(f2, ds.query_emb[0], k=10, mu=0.4, index=idx)
    assert np.isfinite(scores).all()


def test_supersede_damps_traversal_only_at_kappa1():
    ds, f = _world(seed=4)
    q = ds.query_emb[2]
    idx = tv.build_index(ds.hg)
    seed_top = int(readouts.retrieve(f, q, k=1)[0])
    for _ in range(6):                        # heavy dose: b *= 0.5^6
        readouts.supersede(f, seed_top)

    def activation(kappa):
        s = tv._softmax_topm(f.value(q), tv.SEED_M)
        g = ds.hg.base_salience ** kappa
        a = s.copy()
        for _ in range(2):
            w_in = (a * g)[idx.edge_idx]
            n = np.bincount(idx.node_idx, weights=w_in, minlength=idx.N) / idx.deg_node
            at = np.bincount(idx.edge_idx, weights=n[idx.node_idx], minlength=idx.M) / idx.arity
            at /= max(at.sum(), 1e-12)
            a = 0.5 * s + 0.5 * at
        return a

    # κ=1: the superseded edge pushes less mass OUT than under κ=0 —
    # compare downstream mass routed through it (its members' received mass)
    mem = ds.hg.members[seed_top]
    n_k1 = np.bincount(idx.node_idx, weights=(activation(1) * ds.hg.base_salience)[idx.edge_idx],
                       minlength=idx.N)[mem].sum()
    n_k0 = np.bincount(idx.node_idx, weights=(activation(0) * np.ones(ds.hg.M))[idx.edge_idx],
                       minlength=idx.N)[mem].sum()
    assert n_k1 < n_k0                        # stale bridge sinks under κ=1


def test_f1_algebraic_floor_and_gamma_cap():
    ds, f = _world(seed=5)
    q = ds.query_emb[3]
    W = f.value(q)
    ids, scores, rc = readouts.traverse(f, q, k=ds.hg.M, mu=0.4)
    if not rc.abstained:
        # scores are W_trav sorted; reconstruct: every returned score ≥ its W
        assert (scores >= W[ids] - 1e-12).all()
    try:
        readouts.traverse(f, q, mu=0.4, gamma=0.6)
    except ValueError:
        pass
    else:
        raise AssertionError("gamma hard cap 0.5 not enforced")


def test_pointwise_readouts_untouched_by_traversal_import():
    """T2 guard: retrieve/plan/dispatch/supersede signatures & behavior unchanged."""
    ds, f = _world(seed=6)
    q = ds.query_emb[0]
    e, p = readouts.plan(f, q)
    assert np.isclose(p.sum(), 1.0)
    assert isinstance(readouts.dispatch(f, q), int)
    b0 = float(ds.hg.base_salience[3])
    readouts.supersede(f, 3)
    assert float(ds.hg.base_salience[3]) == b0 * 0.5
