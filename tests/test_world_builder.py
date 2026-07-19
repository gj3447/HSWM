"""World builder (T4.5) teeth: structural gold recall, bridges, dedup, determinism,
hop parsing, stats publication, end-to-end traversal integration — all OFFLINE
(fixture rows in the ab_p5_full normalized schema; no network)."""
import numpy as np

import traversal as tv
import world_builder as wb
from weight_field import WeightField


def _rows():
    """8-row fixture with an engineered 2-hop bridge:
    Q asks about Stormhold Castle; its para mentions Harlan Vex; Harlan Vex's own
    para mentions Ember Dragon — castle→harlan→dragon is walkable via shared
    title-entities."""
    P = {
        "castle": {"idx": 0, "title": "Stormhold Castle",
                   "paragraph_text": "Stormhold Castle was built by Harlan Vex above the northern cliffs. "
                                     "Harlan Vex sealed the gates in winter.", "is_supporting": True},
        "harlan": {"idx": 1, "title": "Harlan Vex",
                   "paragraph_text": "Harlan Vex was a wizard who feared the Ember Dragon. "
                                     "The Ember Dragon haunted his dreams.", "is_supporting": True},
        "dragon": {"idx": 2, "title": "Ember Dragon",
                   "paragraph_text": "The Ember Dragon slept beneath the mountain for a century.",
                   "is_supporting": False},
        "noise1": {"idx": 3, "title": "Willow Market",
                   "paragraph_text": "Willow Market sold river fish and lamp oil every morning.",
                   "is_supporting": False},
        "noise2": {"idx": 4, "title": "Glass Harbor",
                   "paragraph_text": "Glass Harbor traded with Willow Market across the bay.",
                   "is_supporting": False},
    }
    rows = [
        {"id": "2hop__castle_harlan", "hop": "2hop", "question": "Who built the castle feared by whom?",
         "answer": "Ember Dragon", "paragraphs": [P["castle"], P["harlan"], P["noise1"], P["noise2"]]},
        {"id": "3hop1__x_y_z", "question": "Where did the dragon sleep?", "answer": "mountain",
         "paragraphs": [dict(P["dragon"], is_supporting=True), P["noise1"],
                        dict(P["harlan"], is_supporting=False)]},
    ]
    # 6 filler rows reusing paragraphs (dedup exercise) with unique questions
    for i in range(6):
        rows.append({"id": f"2hop__fill{i}", "hop": "2hop", "question": f"filler {i}?",
                     "answer": "x", "paragraphs": [dict(P["noise1"], is_supporting=True), P["noise2"]]})
    return rows


def test_structural_gold_recall_and_dedup():
    w = wb.build(_rows())
    assert w.stats["n_edges"] == 5                      # paragraphs deduped across 8 rows
    for q in w.queries:
        assert q.gold.size >= 1
        assert q.gold.max() < w.hg.M                    # every gold maps to a real edge
    assert w.stats["gold_recall_structural"] == 1.0


def test_every_edge_has_title_entity_arity_ge_1():
    w = wb.build(_rows())
    for j, mem in enumerate(w.hg.members):
        assert mem.size >= 1
        title = w.unit_texts[j].split(" :: ")[0]
        assert wb._norm_ent(title) in {w.entities[i] for i in mem}


def test_bridge_is_walkable_castle_to_dragon():
    """Seed mass on the castle edge must reach the dragon edge within 2 hops
    (castle mentions Harlan Vex; Harlan Vex's para mentions Ember Dragon)."""
    w = wb.build(_rows())
    idx = tv.build_index(w.hg)
    eid = {w.unit_texts[j].split(" :: ")[0]: j for j in range(w.hg.M)}
    a = np.zeros(w.hg.M)
    a[eid["Stormhold Castle"]] = 1.0
    for _ in range(2):
        n = np.bincount(idx.node_idx, weights=a[idx.edge_idx], minlength=idx.N) / idx.deg_node
        a = np.bincount(idx.edge_idx, weights=n[idx.node_idx], minlength=idx.M) / idx.arity
    assert a[eid["Ember Dragon"]] > 0.0
    assert a[eid["Glass Harbor"]] == 0.0               # no shared entity path from castle


def test_sparse_not_dense():
    """The world must be a sparse entity graph, not a dense para-para clique
    (add1584: dense graph ⇒ diffusion = low-pass smoother ⇒ traversal loses)."""
    w = wb.build(_rows())
    assert w.stats["density_mean_deg_over_M"] < 0.5
    assert w.stats["node_degree"]["max"] <= w.hg.M     # sanity


def test_deterministic():
    a, b = wb.build(_rows()), wb.build(_rows())
    assert a.entities == b.entities
    assert all(np.array_equal(x, y) for x, y in zip(a.hg.members, b.hg.members))
    assert np.array_equal(a.hg.unit_emb, b.hg.unit_emb)


def test_hop_parsing():
    w = wb.build(_rows())
    by_id = {q.qid: q.hop for q in w.queries}
    assert by_id["2hop__castle_harlan"] == 2           # from row['hop']
    assert by_id["3hop1__x_y_z"] == 3                  # fallback: from row['id']
    r = {"id": "no-digits", "question": "?", "paragraphs": [
        {"idx": 0, "title": "A", "paragraph_text": "B c.", "is_supporting": True},
        {"idx": 1, "title": "B", "paragraph_text": "A d.", "is_supporting": True}]}
    assert wb.parse_hop(r) == 2                        # fallback: #supporting


def test_stats_published_before_results():
    w = wb.build(_rows())
    for key in ("n_edges", "n_nodes", "nnz", "arity", "node_degree", "top_hubs",
                "density_mean_deg_over_M", "queries_per_hop", "mention_misses_df_gate",
                "embedder"):
        assert key in w.stats, key
    assert w.stats["embedder"] == "hash_embed STAND-IN"  # honesty flag until real model injected


def test_end_to_end_traversal_on_built_world():
    w = wb.build(_rows())
    f = WeightField(w.hg, M=None)
    f._pooled = w.hg.unit_emb                          # score UNITS (paragraph view), not member-mean
    q_emb = wb.hash_embed(["Who built the castle feared by whom?"], wb.DEFAULT_DIM)[0]
    ids0, s0, rc0 = tv.traverse(f, q_emb, k=5, mu=0.0)
    assert rc0.abstained and np.isfinite(s0).all()     # certified floor path
    ids1, s1, rc1 = tv.traverse(f, q_emb, k=5, mu=0.4)
    assert np.isfinite(s1).all()                       # full path NaN-free (abstain allowed)
