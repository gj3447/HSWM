"""T3 teeth: certified μ machinery + degree-preserving null gate (offline).

_corpus_rows() builds a synthetic corpus with REAL bridge structure (entity
chains across paragraphs) so select_mu has something honest to certify against,
and shuffle_world destroys exactly that structure while preserving degrees.
"""
import numpy as np

import traversal as tv
import traversal_cert as tc
import world_builder as wb


def _corpus_rows(seed=0, n_chains=12, noise=24):
    """Synthetic corpus: chains A_i -> B_i -> C_i (paragraph about A mentions B;
    about B mentions C) + noise paragraphs. Query i asks about A_i topic with
    gold = {A_i, B_i} paragraphs (2-hop shape)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_chains):
        a, b, c = f"Alpha Keep {i}", f"Bram Vale {i}", f"Cinder Peak {i}"
        pa = {"idx": 0, "title": a,
              "paragraph_text": f"{a} stands north. Lord of {a} rode to {b} each spring. {b} kept the oath.",
              "is_supporting": True}
        pb = {"idx": 1, "title": b,
              "paragraph_text": f"{b} lies east of the river. Scouts of {b} watched {c} burn.",
              "is_supporting": True}
        pc = {"idx": 2, "title": c,
              "paragraph_text": f"{c} is a mountain of ash and old fire.", "is_supporting": False}
        noise_p = {"idx": 3, "title": f"Dull Fen {rng.integers(noise)}",
                   "paragraph_text": "Reeds and mud and quiet water lie here for many miles.",
                   "is_supporting": False}
        rows.append({"id": f"2hop__chain{i}", "hop": "2hop",
                     "question": f"Where did the lord of {a} ride each spring?",
                     "answer": b, "paragraphs": [pa, pb, pc, noise_p]})
    return rows


def test_corpus_world_shape():
    w = wb.build(_corpus_rows())
    assert w.stats["gold_recall_structural"] == 1.0
    assert all(q.gold.size == 2 for q in w.queries)
    assert w.stats["density_mean_deg_over_M"] < 0.2   # sparse regime, not a clique


def test_shuffle_preserves_degrees_destroys_semantics():
    w = wb.build(_corpus_rows())
    w2 = tc.shuffle_world(w, seed=1)
    deg = np.bincount(np.concatenate(w.hg.members), minlength=w.hg.N)
    deg2 = np.bincount(np.concatenate(w2.hg.members), minlength=w2.hg.N)
    assert np.array_equal(deg, deg2)                  # per-node degree bit-exact
    assert [m.size for m in w.hg.members] == [m.size for m in w2.hg.members]  # arity bit-exact
    same = sum(1 for a, b in zip(w.hg.members, w2.hg.members) if np.array_equal(a, b))
    assert same < w.hg.M * 0.5                        # semantics actually destroyed
    for m in w2.hg.members:
        assert m.size >= 1 and np.unique(m).size == m.size   # no dup within edge


def test_select_mu_returns_grid_value_and_diag():
    w = wb.build(_corpus_rows())
    q_e = wb.hash_embed([q.question for q in w.queries], wb.DEFAULT_DIM)
    field = tc.make_field(w)
    idx = tv.build_index(w.hg)
    mu, diag = tc.select_mu(field, w, list(range(0, len(w.queries), 2)), q_e, idx)
    assert mu in tc.MU_GRID
    assert diag["chosen_mu"] == mu
    assert ("certified" in diag) and ("val_mean_mu0" in diag)
    if mu > 0:
        assert diag["certified"] is True              # μ>0 only ever via certification


def test_null_gate_has_teeth():
    """H-T2: no seed may certify μ>0 on a degree-preserving shuffled world."""
    w = wb.build(_corpus_rows())
    q_e = wb.hash_embed([q.question for q in w.queries], wb.DEFAULT_DIM)
    out = tc.null_gate(w, q_e, seeds=(0, 1, 2))
    assert out["verdict"] == "NO_GAIN", out
    assert all(m == 0.0 for m in out["chosen_mu_per_seed"])
