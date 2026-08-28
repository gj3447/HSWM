"""Focused checks for DNRD-5 exact combined-gate planning."""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_UP, getcontext
from fractions import Fraction
import json
import math
import subprocess
import sys

import pytest

from _research.dnrd5 import power_planning


def test_exact_combined_marginal_gate_has_dependence_robust_design_boundary() -> None:
    assert (
        power_planning.PLUS_PROBABILITY
        + power_planning.MINUS_PROBABILITY
        + power_planning.TIE_PROBABILITY
        == 1
    )
    assert power_planning.PLUS_PROBABILITY - power_planning.MINUS_PROBABILITY == Fraction(3, 20)
    assert power_planning.PLUS_PROBABILITY + power_planning.MINUS_PROBABILITY == Fraction(1, 2)
    before = power_planning.three_contrast_dependence_robust_lower_bound(297)
    at = power_planning.three_contrast_dependence_robust_lower_bound(298)
    assert before < Fraction(4, 5)
    assert at >= Fraction(4, 5)
    assert power_planning.required_blocks_for_dependence_robust_lower_bound() == 298
    assert power_planning.DESIGN_BLOCK_COUNT == 300
    assert power_planning.MAX_GENERATION_CALLS == 2700


def test_single_pass_probability_is_exact_fraction_and_row_is_canonical() -> None:
    probability = power_planning.single_contrast_pass_probability(298)
    assert isinstance(probability, Fraction)
    row = power_planning.exact_planning_row(298)
    assert row["marginal_pass_probability"] == {
        "numerator": probability.numerator,
        "denominator": probability.denominator,
    }
    assert row["three_contrast_dependence_robust_lower_bound_decimal"].startswith("0.8")


def test_exact_planning_rows_pin_the_cited_boundary_and_design_values() -> None:
    expected = {
        297: (
            "0.93300001337172905050635919247629394563364556451857",
            "0.79900004011518715151907757742888183690093669355571",
        ),
        298: (
            "0.93381399545931852526738183472102670349795427799898",
            "0.80144198637795557580214550416308011049386283399695",
        ),
        300: (
            "0.93541364013959095110759348693431218211575454408242",
            "0.80624092041877285332278046080293654634726363224725",
        ),
    }
    for blocks, (marginal, lower_bound) in expected.items():
        row = power_planning.exact_planning_row(blocks)
        assert row["marginal_pass_probability_decimal"] == marginal
        assert row["three_contrast_dependence_robust_lower_bound_decimal"] == lower_bound


def test_lcb_decimal_is_pinned_against_caller_rounding_context() -> None:
    context = getcontext()
    original = context.rounding
    try:
        context.rounding = ROUND_DOWN
        down = power_planning.asymptotic_lcb_decimal(100, 50, 274)
        context.rounding = ROUND_UP
        up = power_planning.asymptotic_lcb_decimal(100, 50, 274)
    finally:
        context.rounding = original
    assert down == up


def test_combined_discordance_threshold_is_a_monotone_tail() -> None:
    """The compressed exact sum may replace states only after this invariant holds."""
    blocks = 298
    for discordance in range(blocks + 1):
        threshold = power_planning._combined_minimum_wins(blocks, discordance)
        if threshold is None:
            continue
        assert threshold > discordance / 2
        assert power_planning.combined_marginal_gate_passes(threshold, discordance - threshold, blocks)
        assert not power_planning.combined_marginal_gate_passes(
            threshold - 1, discordance - threshold + 1, blocks
        )


def test_compressed_probability_matches_direct_multinomial_enumeration() -> None:
    blocks = 12
    numerator = 0
    for active_wins in range(blocks + 1):
        for control_wins in range(blocks - active_wins + 1):
            discordance = active_wins + control_wins
            exact_pass = (
                power_planning.EXACT_P_MULTIPLIER
                * power_planning._tail_fraction(active_wins, discordance)
                <= power_planning.BONFERRONI_FAMILYWISE_ALPHA
                and power_planning.asymptotic_lcb_decimal(active_wins, control_wins, blocks) > 0
            )
            assert power_planning.combined_marginal_gate_passes(
                active_wins, control_wins, blocks
            ) is exact_pass
            if exact_pass:
                ties = blocks - discordance
                numerator += (
                    math.comb(blocks, active_wins)
                    * math.comb(blocks - active_wins, control_wins)
                    * power_planning.PLUS_WEIGHT**active_wins
                    * power_planning.MINUS_WEIGHT**control_wins
                    * power_planning.TIE_WEIGHT**ties
                )
    direct = Fraction(numerator, power_planning.ALTERNATIVE_DENOMINATOR**blocks)
    assert power_planning.single_contrast_pass_probability(blocks) == direct


def test_normal_calculator_is_sensitivity_only() -> None:
    row = power_planning.normal_sensitivity_row(274, 0.15, 0.50, 0.0)
    assert row["calculation_label"] == power_planning.NORMAL_SENSITIVITY_LABEL
    assert row["joint_power_at_blocks"] == pytest.approx(0.800624, abs=0.000001)
    assert not any("conservative" in assumption.lower() for assumption in power_planning.ASSUMPTIONS)


def test_standard_table_separates_exact_design_from_normal_sensitivity() -> None:
    table = power_planning.standard_table()
    assert {row["blocks"] for row in table["exact_marginal_rows"]} == {64, 136, 274, 297, 298, 300}
    assert len(table["normal_sensitivity_rows"]) == 144
    assert all(row["calculation_label"] == power_planning.NORMAL_SENSITIVITY_LABEL for row in table["normal_sensitivity_rows"])


def test_invalid_exact_block_count_is_refused() -> None:
    with pytest.raises(ValueError, match="at least two"):
        power_planning.single_contrast_pass_probability(1)


def test_cli_is_deterministic_canonical_json() -> None:
    command = [sys.executable, "-m", "_research.dnrd5.power_planning", "--blocks", "297,298", "--q", "0.5", "--rho", "0"]
    first = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    second = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    assert first == second
    result = json.loads(first)
    assert result["calculation_label"] == power_planning.CALCULATION_LABEL
    assert result["design_block_count"] == 300
    assert result["max_generation_calls"] == 2700
    assert len(result["exact_marginal_rows"]) == 2
    assert len(result["normal_sensitivity_rows"]) == 4
    assert result["exact_marginal_rows"][0]["blocks"] == 297
    assert result["exact_marginal_rows"][1]["blocks"] == 298
