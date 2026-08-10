"""F0 semantic-harness tests — deterministic, no model/LLM.

Validates the matched-vs-mismatched null control so the real embedding run only
adds a data point. # KG: ATOM_Skill_longinus  (F0 semantic metric)
"""

from __future__ import annotations

from run_f0_semantic import _load_pairs, _shift, run_semantic
from semantic_score import mock_cosines


def test_shift_cyclic():
    assert _shift([1, 2, 3], 1) == [2, 3, 1]
    assert _shift(["a", "b"], 1) == ["b", "a"]


def test_gap_positive_with_specific_proxy():
    # node_content is derived from the same commander as its doc_prose, so even a
    # crude char-set proxy should score matched > mismatched (specificity detected).
    pairs = _load_pairs()
    regen = {p["field_id"]: p["node_content"] for p in pairs}
    r = run_semantic(pairs, regen, mock_cosines)
    assert r["mean_matched"] > r["mean_mismatched"]
    assert r["gap"] > 0.0
    assert r["n_pairs"] == len(pairs)


def test_constant_scorer_zero_gap():
    # a scorer blind to content produces no gap — the null the control must catch.
    pairs = _load_pairs()
    regen = {p["field_id"]: "x" for p in pairs}
    r = run_semantic(pairs, regen, lambda preds, golds: [0.5] * len(preds))
    assert r["gap"] == 0.0


def test_perfect_specific_scorer_full_gap():
    pairs = _load_pairs()
    fids = [p["field_id"] for p in pairs]
    golds = [p["doc_prose"] for p in pairs]
    regen = {fids[i]: golds[i] for i in range(len(fids))}  # regen == its own gold
    exact = lambda preds, gs: [1.0 if preds[i] == gs[i] else 0.0 for i in range(len(preds))]
    r = run_semantic(pairs, regen, exact)
    assert r["mean_matched"] == 1.0
    assert r["mean_mismatched"] == 0.0  # cyclically shifted golds never equal pred
    assert r["gap"] == 1.0
