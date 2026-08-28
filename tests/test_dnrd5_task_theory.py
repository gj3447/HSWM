from __future__ import annotations

from copy import deepcopy
from fractions import Fraction

import pytest

from _research.dnrd5 import task_theory as theory


def test_exact_2x2x2_identification_and_control_laws() -> None:
    table = theory.exact_truth_table()
    summary = theory.exact_identification_summary(table)
    assert len(table) == 8
    assert summary["case_count"] == 8
    assert summary["genuine_feedback_marginal"] == {"p0": Fraction(1, 2), "p1": Fraction(1, 2)}
    assert summary["placebo_feedback_marginal"] == {"p0": Fraction(1, 2), "p1": Fraction(1, 2)}
    assert "NOT_ASSUMED_FAIR_OR_RANDOM" in summary["choice_status"]
    assert "IDENTICAL_LAWS" in summary["pooled_law_status"]
    for stratum in summary["conditional_by_choice"].values():
        assert stratum["case_count"] == 4
        assert stratum["genuine_feedback_p1"] == Fraction(1, 2)
        assert stratum["placebo_feedback_p1"] == Fraction(1, 2)
    for law in summary["paired_d_laws"].values():
        assert law == {"p_d0": Fraction(1, 2), "p_d1": Fraction(1, 2), "oracle_mean": Fraction(1, 2)}
    assert summary["planning_delta"] == Fraction(15, 100)
    assert summary["planning_delta_is_not_theoretical_oracle_mean"] is True
    assert "production probe RNG" in summary["idealized_w0_policy_assumption"]
    assert "does not prove" in summary["sha_nonclaim"]
    assert "fixed algorithm" in summary["mechanism_nonclaim"]


@pytest.mark.parametrize("theta,choice", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_genuine_correctness_and_choice_uniquely_identify_theta(theta: int, choice: int) -> None:
    correctness = int(theta == choice)
    assert theory.infer_theta(choice, correctness) == theta


def test_truth_table_mutations_and_invalid_inference_are_refused() -> None:
    table = [dict(row) for row in theory.exact_truth_table()]
    mutated = deepcopy(table)
    mutated[0]["sham_probe_score"] ^= 1
    with pytest.raises(theory.TheoryRefusal, match="sham probe score"):
        theory.validate_truth_table(mutated)
    mutated = deepcopy(table)
    mutated[0]["sham_disposition"] ^= 1
    with pytest.raises(theory.TheoryRefusal, match="sham disposition inference"):
        theory.validate_truth_table(mutated)
    mutated = deepcopy(table)
    mutated[1] = dict(mutated[0])
    with pytest.raises(theory.TheoryRefusal, match="duplicates|omits"):
        theory.validate_truth_table(mutated)
    with pytest.raises(theory.TheoryRefusal, match="chosen_hypothesis"):
        theory.infer_theta(True, 1)
    with pytest.raises(theory.TheoryRefusal, match="genuine_correctness"):
        theory.infer_theta(0, 2)
