"""The falsifier must have TEETH — it must be able to say EXCLUDED / not just win.

- frequency regime: relevance is a pure frequency shortcut -> the manipulation
  (or ceiling) gate MUST fire -> EXCLUDED. If this ever returns SUPPORTED, the
  harness is rigged and worthless.
- semantics regime: a real (non-shortcut) task -> the harness returns a genuine
  Verdict (SUPPORTED / REFUTED / INCONCLUSIVE), never EXCLUDED, and always
  reports the honest controls (null-head, param-free cosine).
"""
from falsifier import run_falsifier


def test_frequency_regime_is_excluded():
    v = run_falsifier("frequency", seeds=(0, 1))
    assert v.label == "EXCLUDED", (v.label, v.reason, v.numbers)


def test_semantics_regime_returns_genuine_verdict():
    v = run_falsifier("semantics", seeds=(0, 1))
    assert v.label in {"SUPPORTED", "REFUTED", "INCONCLUSIVE"}, (v.label, v.reason)
    # controls are always reported (honesty: a "win" must beat these, not just heuristics)
    assert "mean_null_head_ndcg" in v.numbers
    assert "mean_cosine_ndcg" in v.numbers
    assert "mean_best_heuristic_ndcg" in v.numbers
    # pool guarantees gold recallable (rerank-isolation precondition)
    assert v.numbers["gold_recall"] == 1.0


def test_verdict_carries_prereg_decision_flags():
    v = run_falsifier("semantics", seeds=(0, 1))
    if v.label in {"SUPPORTED", "REFUTED", "INCONCLUSIVE"}:
        for key in ("beats_heuristic_by_margin", "beats_null_head",
                    "beats_param_free_cosine", "worst_seed_ok", "significant",
                    "answer_not_regressed"):
            assert key in v.numbers
