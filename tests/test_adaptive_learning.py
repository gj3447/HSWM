import json

import pytest

from hswm.cells.adaptive_learning import (
    initial_model, predict, selection_score, suggest_guard, update_model,
)
from hswm.cells.conditional import Reject


FAST = {"route": "fast", "state": "ready"}
SLOW = {"route": "slow", "state": "ready"}


def test_local_contexts_diverge_after_observed_results():
    model = initial_model()
    for _ in range(8):
        model = update_model(model, FAST, success=True, cost=1)
        model = update_model(model, SLOW, success=False, cost=3)
    assert predict(model, FAST) > 0.7
    assert predict(model, SLOW) < 0.3
    assert model["scope"] == "OBSERVATIONAL_LOCAL_ADAPTATION"


def test_update_does_not_mutate_and_is_json_persistent():
    original = initial_model()
    updated = update_model(original, FAST, success=True, cost=2)
    assert original == initial_model()
    restored = json.loads(json.dumps(updated, allow_nan=False))
    assert predict(restored, FAST) == predict(updated, FAST)


def test_counterexample_changes_selection_and_cost_exploration_are_bounded():
    model = initial_model()
    for _ in range(6):
        model = update_model(model, FAST, success=True, cost=1)
    before = selection_score(model, FAST, cost_hint=1, budget=3, exploration=0.2, total_attempts=6)
    for _ in range(10):
        model = update_model(model, FAST, success=False, cost=2)
    after = selection_score(model, FAST, cost_hint=1, budget=3, exploration=0.2, total_attempts=16)
    assert after < before
    assert -1 <= selection_score(model, SLOW, cost_hint=99, budget=3, exploration=1, total_attempts=0) <= 1


def test_measured_cost_never_reduces_the_penalty_for_equal_success_history():
    cheap, expensive = initial_model(), initial_model()
    for _ in range(4):
        cheap = update_model(cheap, FAST, success=True, cost=1)
        expensive = update_model(expensive, FAST, success=True, cost=5)
    assert selection_score(cheap, FAST, cost_hint=1, budget=6) > selection_score(
        expensive, FAST, cost_hint=1, budget=6)


def test_suggest_guard_requires_mixed_public_history_and_keeps_proposal_boundary():
    domain = {("part", "ready"): [0, 1], ("part", "clean"): [0, 1]}
    examples = [{"values": {("part", "ready"): ready, ("part", "clean"): clean},
                 "outcome": bool(ready and clean), "source": f"public:{ready}:{clean}"}
                for ready, clean in [(0, 0), (0, 1), (1, 0), (1, 1)]]
    proposal = suggest_guard(domain, examples, parent="r1")
    assert proposal["status"] == "PROPOSED_NOT_ADMITTED"
    assert proposal["credit"] == "UNIDENTIFIED_CREDIT"
    assert proposal["parent_revision"] == "r1"


@pytest.mark.parametrize("context", [{}, {"x": float("inf")}, {"x": []}])
def test_rejects_nonfinite_or_non_scalar_context(context):
    with pytest.raises(Reject):
        predict(initial_model(), context)
