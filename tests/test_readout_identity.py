"""The 4-fold identification: retrieval = plan = supersession read ONE field.

This is the structural crux of PROM_16 §미개척 triple — the identification itself.
These tests prove the three readouts are coherent views of the same W(e|c), and
that supersession is non-destructive (down-weight, never delete).
"""
import numpy as np

from hypergraph import Hypergraph
import readouts
from weight_field import WeightField


def _field(seed=0):
    rng = np.random.default_rng(seed)
    emb = rng.standard_normal((8, 4))
    members = [[0, 1], [2, 3], [4, 5], [1, 6], [3, 7], [0, 5, 6]]
    hg = Hypergraph(node_emb=emb, members=members,
                    edge_freq=np.ones(6), edge_recency=np.linspace(0, 1, 6))
    return hg, WeightField(hg, M=None)


def test_retrieve_matches_field_order():
    hg, field = _field()
    q = hg.node_emb[0]
    w = field.value(q)
    top = readouts.retrieve(field, q, k=3)
    assert top.tolist() == np.argsort(-w, kind="stable")[:3].tolist()


def test_plan_argmax_equals_retrieve_top_equals_dispatch():
    hg, field = _field()
    q = hg.node_emb[2]
    top1 = readouts.retrieve(field, q, k=1)[0]
    edges, probs = readouts.plan(field, q)
    plan_argmax = int(edges[int(np.argmax(probs))])
    assert plan_argmax == int(top1)
    assert readouts.dispatch(field, q) == int(top1)


def test_plan_is_a_distribution():
    hg, field = _field()
    _, probs = readouts.plan(field, hg.node_emb[1])
    assert np.isclose(probs.sum(), 1.0)
    assert (probs >= 0).all()


def test_supersede_is_nondestructive_and_lowers_rank():
    hg, field = _field()
    q = hg.node_emb[0]
    before = readouts.retrieve(field, q, k=hg.M).tolist()
    target = before[0]                         # the currently top edge
    m_before = hg.M                            # edge count sanity
    readouts.supersede(field, target, decay=0.001)  # heavy down-weight, NOT delete
    after = readouts.retrieve(field, q, k=hg.M).tolist()
    # still present (nothing deleted): same number of edges, target still scorable
    assert hg.M == m_before
    assert target in after
    # its rank strictly worsened (moved later) — one write, felt by the retrieval readout
    assert after.index(target) > before.index(target)


def test_supersede_also_lowers_plan_probability():
    hg, field = _field()
    q = hg.node_emb[4]
    edges, p_before = readouts.plan(field, q)
    idx = int(np.where(edges == readouts.retrieve(field, q, k=1)[0])[0][0])
    target = int(edges[idx])
    prob_before = p_before[idx]
    readouts.supersede(field, target, decay=0.001)
    edges2, p_after = readouts.plan(field, q)
    idx2 = int(np.where(edges2 == target)[0][0])
    # same field -> supersession felt by the PLAN readout too (the identification)
    assert p_after[idx2] < prob_before
