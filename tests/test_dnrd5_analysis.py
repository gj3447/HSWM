"""Frozen-vector and arithmetic tests for DNRD-5 sealed-result analysis."""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_FLOOR, getcontext
from pathlib import Path

import pytest

from _research.dnrd5 import analysis


VECTOR_PATH = Path(__file__).parents[1] / "_research/dnrd5/vectors/analysis_v1.json"


def _expand(case: dict[str, object]) -> list[dict[str, int | str]]:
    if "raw_blocks" in case:
        return case["raw_blocks"]  # type: ignore[return-value]
    blocks: list[dict[str, int | str]] = []
    for run in case["runs"]:  # type: ignore[index]
        for index in range(run["count"]):  # type: ignore[index]
            blocks.append(
                {
                    "block_id": f"{run['prefix']}-{index:03d}",
                    "ACTIVE": run["ACTIVE"],
                    "OUTCOME_INDEPENDENT_SHAM": run["OUTCOME_INDEPENDENT_SHAM"],
                    "DELAYED_NO_CREDIT": run["DELAYED_NO_CREDIT"],
                    "EXACT_W0_ROLLBACK": run["EXACT_W0_ROLLBACK"],
                }
            )
    return sorted(blocks, key=lambda block: str(block["block_id"]))


@pytest.fixture(scope="module")
def cases() -> dict[str, dict[str, object]]:
    vector = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    return {case["name"]: case for case in vector["cases"]}


def test_all_tie_and_known_tail_exact_fractions(cases: dict[str, dict[str, object]]) -> None:
    tied = analysis.contrast_summary(_expand(cases["all_tie"]), "OUTCOME_INDEPENDENT_SHAM")
    assert tied["discordance"] == 0
    assert tied["exact_one_sided_p"] == {"numerator": 1, "denominator": 1}
    assert tied["bonferroni_adjusted_p"] == {"numerator": 1, "denominator": 1}
    tail = analysis.contrast_summary(_expand(cases["known_small_tail"]), "OUTCOME_INDEPENDENT_SHAM")
    assert tail["active_wins"] == 2
    assert tail["control_wins"] == 1
    assert tail["exact_one_sided_p"] == {"numerator": 1, "denominator": 2}
    assert tail["bonferroni_adjusted_p"] == {"numerator": 1, "denominator": 1}


def test_go_and_mechanism_incomplete_decisions(cases: dict[str, dict[str, object]]) -> None:
    go_blocks = _expand(cases["go"])
    result = analysis.analyze_study(go_blocks, expected_block_ids=[block["block_id"] for block in go_blocks])
    assert result["decision"] == "ARITHMETIC_GO_PENDING_INTEGRITY"
    assert result["requires_production_judge_integrity_gate"] is True
    incomplete_blocks = _expand(cases["mechanism_incomplete"])
    incomplete = analysis.analyze_study(
        incomplete_blocks, expected_block_ids=[block["block_id"] for block in incomplete_blocks]
    )
    assert incomplete["decision"] == "ARITHMETIC_PRIMARY_SIGNAL_MECHANISM_INCOMPLETE_PENDING_INTEGRITY"
    assert Decimal(incomplete["summaries"]["OUTCOME_INDEPENDENT_SHAM"]["asymptotic_lcb_decimal"]) > 0
    assert incomplete["summaries"]["DELAYED_NO_CREDIT"]["asymptotic_lcb_decimal"] == "0"
    no_go_blocks = _expand(cases["valid_no_go"])
    assert (
        analysis.analyze_study(no_go_blocks, expected_block_ids=[block["block_id"] for block in no_go_blocks])["decision"]
        == "ARITHMETIC_NO_GO_PENDING_INTEGRITY"
    )


@pytest.mark.parametrize(
    "case_name",
    ["invalid_duplicate", "invalid_nonbinary", "invalid_extra_field", "invalid_count"],
)
def test_invalid_frozen_vector_cases_are_refused(cases: dict[str, dict[str, object]], case_name: str) -> None:
    case = cases[case_name]
    with pytest.raises(analysis.AnalysisValidationError, match=case["expected_error"]):
        if case_name == "invalid_count":
            blocks = _expand(case)
            analysis.analyze_study(blocks, expected_block_ids=[block["block_id"] for block in blocks])
        else:
            analysis.contrast_summary(_expand(case), "OUTCOME_INDEPENDENT_SHAM")


def test_labels_distinguish_exact_sharp_null_from_asymptotic_lcb(cases: dict[str, dict[str, object]]) -> None:
    blocks = _expand(cases["go"])
    result = analysis.analyze_study(blocks, expected_block_ids=[block["block_id"] for block in blocks])
    assert result["exactness_precondition_status"] == "NOT_VERIFIED_BY_THIS_ARITHMETIC_MODULE"
    sham = result["summaries"]["OUTCOME_INDEPENDENT_SHAM"]
    assert sham["exact_one_sided_p_label"] == "SHARP_NULL_EXACT_SIGN_BINOMIAL_TAIL"
    assert sham["asymptotic_lcb_label"] == "ASYMPTOTIC_NORMAL_BONFERRONI_LCB"
    assert sham["pinned_bonferroni_z_decimal"] == "2.128045234184984"
    assert sham["mean_difference_fraction"] == {"numerator": 1, "denominator": 1}
    assert sham["unbiased_sample_variance_fraction"] == {"numerator": 0, "denominator": 1}
    assert sham["asymptotic_lcb_decimal"] == "1.000000000000000"


def test_expected_block_universe_is_required_and_bound(cases: dict[str, dict[str, object]]) -> None:
    blocks = _expand(cases["go"])
    expected = [block["block_id"] for block in blocks]
    with pytest.raises(analysis.AnalysisValidationError, match="does not match"):
        analysis.analyze_study(blocks, expected_block_ids=["different-000", *expected[1:]])


def test_input_hashes_bind_universe_and_rows_and_survive_json_roundtrip(cases: dict[str, dict[str, object]]) -> None:
    blocks = _expand(cases["go"])
    expected = [block["block_id"] for block in blocks]
    baseline = analysis.analyze_study(blocks, expected_block_ids=expected)
    assert baseline["integrity_status"] == "ARITHMETIC_ONLY_PENDING_PRODUCTION_JUDGE_INTEGRITY"
    assert json.loads(json.dumps(baseline, sort_keys=True, separators=(",", ":"), allow_nan=False)) == baseline

    changed_rows = [dict(block) for block in blocks]
    changed_rows[0]["OUTCOME_INDEPENDENT_SHAM"] = 1
    rows_changed = analysis.analyze_study(changed_rows, expected_block_ids=expected)
    assert rows_changed["observed_blocks_sha256"] != baseline["observed_blocks_sha256"]
    assert rows_changed["expected_block_ids_sha256"] == baseline["expected_block_ids_sha256"]

    changed_universe_blocks = [dict(block) for block in blocks]
    changed_universe_blocks[0]["block_id"] = "alt-000"
    changed_universe_blocks.sort(key=lambda block: str(block["block_id"]))
    changed_universe = [block["block_id"] for block in changed_universe_blocks]
    universe_changed = analysis.analyze_study(changed_universe_blocks, expected_block_ids=changed_universe)
    assert universe_changed["expected_block_ids_sha256"] != baseline["expected_block_ids_sha256"]


def test_decimal_output_and_decision_are_stable_under_global_rounding(cases: dict[str, dict[str, object]]) -> None:
    blocks = _expand(cases["nontrivial_large_tail"])
    before = analysis.contrast_summary(blocks, "OUTCOME_INDEPENDENT_SHAM")
    original_rounding = getcontext().rounding
    try:
        getcontext().rounding = ROUND_FLOOR
        after = analysis.contrast_summary(blocks, "OUTCOME_INDEPENDENT_SHAM")
    finally:
        getcontext().rounding = original_rounding
    assert before == after
    assert "mean_difference" not in before
    assert "asymptotic_lcb" not in before
    assert "unbiased_sample_variance" not in before


def test_nontrivial_large_tail_and_lcb_boundary_split(cases: dict[str, dict[str, object]]) -> None:
    tail = analysis.contrast_summary(_expand(cases["nontrivial_large_tail"]), "OUTCOME_INDEPENDENT_SHAM")
    assert tail["discordance"] == 300
    assert tail["active_wins"] == 180
    assert tail["control_wins"] == 120
    assert tail["exact_one_sided_p"]["denominator"] > 2**200
    boundary = analysis.contrast_summary(_expand(cases["all_tie"]), "OUTCOME_INDEPENDENT_SHAM")
    assert boundary["asymptotic_lcb_decimal"] == "0"
    split = analysis.contrast_summary(
        _expand(cases["lcb_positive_exact_p_fails"]), "OUTCOME_INDEPENDENT_SHAM"
    )
    assert split["bonferroni_adjusted_p"] == {"numerator": 3, "denominator": 32}
    assert Decimal(split["asymptotic_lcb_decimal"]) > 0
