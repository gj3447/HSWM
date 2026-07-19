"""doc_builder harness: shape-correct, deterministic, honest about drops."""
import numpy as np

import doc_builder as db

TEXT = "\n\n".join(
    f"The wizard Harlan walked the castle halls with his silver wand. "
    f"Harlan feared the dragon beneath the castle. Paragraph {i} tells more of "
    f"the wand, the dragon, and the castle secrets kept by wizard Harlan."
    for i in range(20)
)


def test_build_produces_all_levels_with_valid_incidence():
    doc = db.build(TEXT)
    assert len(doc.concepts) >= 3
    for level in db.LENGTH_ORDER:
        hg = doc.strata[level]
        assert hg.M == len(doc.unit_texts[level]) > 0
        assert hg.unit_emb.shape == (hg.M, db.DEFAULT_DIM)
        for mem in hg.members:
            assert mem.size > 0 and mem.max() < len(doc.concepts)


def test_arity_grows_with_level():
    doc = db.build(TEXT)
    mean_arity = {lv: float(np.mean([m.size for m in doc.strata[lv].members]))
                  for lv in db.LENGTH_ORDER}
    assert mean_arity["sentence"] <= mean_arity["paragraph"] <= mean_arity["chapter"]


def test_deterministic_across_calls():
    a, b = db.build(TEXT), db.build(TEXT)
    assert a.concepts == b.concepts
    for lv in db.LENGTH_ORDER:
        assert np.array_equal(a.strata[lv].unit_emb, b.strata[lv].unit_emb)
        assert all(np.array_equal(x, y) for x, y in zip(a.strata[lv].members, b.strata[lv].members))


def test_embeddings_unit_norm_and_pluggable():
    doc = db.build(TEXT)
    norms = np.linalg.norm(doc.strata["paragraph"].unit_emb, axis=1)
    assert np.allclose(norms, 1.0)
    # pluggable embed_fn is actually used
    calls = []
    def fake_embed(texts):
        calls.append(len(texts))
        return np.ones((len(texts), 8)) / np.sqrt(8)
    doc2 = db.build(TEXT, embed_fn=fake_embed)
    assert calls and doc2.strata["sentence"].unit_emb.shape[1] == 8


def test_conceptless_units_dropped_and_reported():
    text = TEXT + "\n\nZq zz aa.\n\n" + "Xy xw qq."  # junk paragraphs, no concepts
    doc = db.build(text)
    assert doc.dropped["paragraph"] >= 1


def test_too_sparse_text_raises():
    try:
        db.build("one two. three four.")
    except ValueError:
        return
    raise AssertionError("expected ValueError on conceptless text")
