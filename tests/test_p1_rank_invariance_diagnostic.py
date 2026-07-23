from __future__ import annotations

import math

from p1_rank_invariance_diagnostic import rank_change_metrics


def test_rank_change_metrics_separates_score_order_and_membership() -> None:
    base = [1.0 - index * 0.1 for index in range(12)]
    before = list(range(12))
    candidate = list(base)
    candidate[10] += 0.15
    after = sorted(range(12), key=lambda index: (-candidate[index], index))

    result = rank_change_metrics(base, candidate, before, after)

    assert result["changed_targets"] == 1
    assert result["top10_membership_changed"] is True
    assert result["top10_order_changed"] is True
    assert math.isclose(result["rank10_11_gap"], 0.1)
    assert math.isclose(result["max_abs_score_delta"], 0.15)
    assert math.isclose(result["max_delta_to_boundary_gap"], 1.5)


def test_rank_change_metrics_detects_rank_invariant_perturbation() -> None:
    base = [1.0 - index * 0.1 for index in range(12)]
    before = list(range(12))
    candidate = list(base)
    candidate[0] += 1e-4

    result = rank_change_metrics(base, candidate, before, before)

    assert result["changed_targets"] == 1
    assert result["top10_membership_changed"] is False
    assert result["top10_order_changed"] is False
    assert math.isclose(result["max_abs_score_delta"], 1e-4)
