"""Hypergraph structure: incidence = the field's support (Constrain axis)."""
import numpy as np
import pytest

from hypergraph import Hypergraph


def _hg():
    emb = np.array([[1.0, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [0, 1, 1]], dtype=float)
    return Hypergraph(node_emb=emb, members=[[0, 1], [2, 3, 4]],
                      edge_freq=[1, 2], edge_recency=[0.1, 0.9])


def test_dims():
    hg = _hg()
    assert (hg.N, hg.M, hg.d) == (5, 2, 3)


def test_incidence_matrix():
    H = _hg().incidence()
    assert H.shape == (2, 5)
    assert H[0].tolist() == [True, True, False, False, False]
    assert H[1].tolist() == [False, False, True, True, True]


def test_pooled_mean():
    hg = _hg()
    pooled = hg.pooled_emb("mean")
    assert np.allclose(pooled[0], [0.5, 0.5, 0.0])          # mean of nodes 0,1
    assert np.allclose(pooled[1], [1 / 3, 2 / 3, 2 / 3])    # mean of nodes 2,3,4


def test_base_salience_defaults_one():
    assert np.allclose(_hg().base_salience, [1.0, 1.0])


def test_arity_zero_rejected():
    with pytest.raises(ValueError):
        Hypergraph(node_emb=np.eye(3), members=[[0, 1], []],
                   edge_freq=[1, 1], edge_recency=[0.1, 0.2])


def test_out_of_range_member_rejected():
    with pytest.raises(ValueError):
        Hypergraph(node_emb=np.eye(3), members=[[0, 9]],
                   edge_freq=[1], edge_recency=[0.1])
