from hashlib import sha256
from decimal import Decimal

import pytest

from _research.dgx_mi2.protocol import (
    ALL_SCHEDULES, PAIR_COUNT, SCHEDULE_COUNT, attempt_ids, block_order,
    endpoint_family_randomization, exact_margin_upper_tail_randomization, exact_upper_tail_randomization,
    extract_fixed_branch_margin, FULL_TRACE_SCHEMA, make_seed_material, margin_statistic,
    SCHEDULE_SELECTION_LIMIT, select_schedule, statistic, validate_schedule, Mi2Refusal,
)
from _research.dnrd5.canonical_json import canonical_bytes


def test_closed_schedule_domain_has_exactly_400_balanced_members() -> None:
    assert len(ALL_SCHEDULES) == SCHEDULE_COUNT == 400
    for schedule in ALL_SCHEDULES:
        assert len(schedule) == PAIR_COUNT
        assert schedule.count("ED") == schedule.count("DE") == 6
        assert schedule[:6].count("ED") == schedule[6:].count("ED") == 3


def test_csprng_material_selects_one_explicit_lexicographic_schedule_deterministically() -> None:
    raw = make_seed_material(bytes(range(1, 33)))
    first = select_schedule(raw)
    assert first == select_schedule(raw)
    index, schedule = first
    assert 0 <= index < 400 and schedule == ALL_SCHEDULES[index]


def test_selection_uses_direct_raw_draw_rejection_and_exact_modulo() -> None:
    accepted = SCHEDULE_SELECTION_LIMIT - 1
    index, schedule = select_schedule(make_seed_material(accepted.to_bytes(32, "big")))
    assert index == accepted % SCHEDULE_COUNT and schedule == ALL_SCHEDULES[index]
    assert select_schedule(make_seed_material(b"\0" * 32))[0] == 0
    with pytest.raises(Mi2Refusal, match="rejected tail"):
        select_schedule(make_seed_material(SCHEDULE_SELECTION_LIMIT.to_bytes(32, "big")))


@pytest.mark.parametrize("schedule", [("ED",) * 12, ("ED",) * 4 + ("DE",) * 8, ("ED",) * 6 + ("DE",) * 6])
def test_schedule_rejects_total_or_half_balance_drift(schedule: tuple[str, ...]) -> None:
    with pytest.raises(Mi2Refusal):
        validate_schedule(schedule)


def test_launch_order_is_twelve_adjacent_pairs_and_48_fixed_attempts() -> None:
    schedule = ALL_SCHEDULES[0]
    order = block_order(schedule)
    assert len(order) == 24
    assert len(attempt_ids(schedule)) == 48
    for index in range(12):
        pair = order[index * 2:index * 2 + 2]
        assert [row["launch_position"] for row in pair] == [1, 2]
        assert {row["arm"] for row in pair} == {"ASYNC_ENABLED", "ASYNC_DISABLED"}
    assert [row["absolute_launch_index"] for row in order] == list(range(1, 25))
    assert [row["absolute_launch_parity"] for row in order] == ["ODD", "EVEN"] * 12
    assert order[0]["prior_arm"] is None
    assert all(row["prior_arm"] == order[index - 1]["arm"] for index, row in enumerate(order[1:], 1))


def test_primary_randomization_uses_only_one_sha_per_fresh_launch() -> None:
    schedule = ALL_SCHEDULES[0]
    values = {f"P{index:02d}": (sha256(f"left-{index}".encode()).hexdigest(), sha256(f"right-{index}".encode()).hexdigest()) for index in range(1, 13)}
    result = exact_upper_tail_randomization(values, schedule)
    assert statistic(values, schedule) == result["observed_t"]
    assert result["statistic"] == "T_content=1/2*sum_c|N_E,c-N_D,c|"
    assert result["denominator"] == 400
    assert 0 < result["upper_tail_numerator"] <= 400
    assert result["p_value"].endswith("/400")


def test_fixed_branch_margin_requires_the_registered_prefix_and_candidates() -> None:
    prefix = b'{\n  "answer": "VISTA",\n  "rationale": "The first cue'
    chunks = [prefix[index:index + 1] for index in range(19)] + [prefix[19:]]
    rows = [{"token": "x", "bytes": list(chunk), "logprob": "0", "top_logprobs": []} for chunk in chunks]
    rows.append({"token": " indicates", "bytes": list(b" indicates"), "logprob": "-1", "top_logprobs": [
        {"token": " indicates", "bytes": list(b" indicates"), "logprob": "-1.5"},
        {"token": " explicitly", "bytes": list(b" explicitly"), "logprob": "-2.25"},
    ]})
    raw = canonical_bytes({"schema_version": FULL_TRACE_SCHEMA, "rows": rows})
    assert extract_fixed_branch_margin(raw) == Decimal("0.75")
    rows[-1]["top_logprobs"][0]["logprob"] = -1
    with pytest.raises(Mi2Refusal):
        extract_fixed_branch_margin(canonical_bytes({"schema_version": FULL_TRACE_SCHEMA, "rows": rows}))
    rows[-1]["top_logprobs"][0]["logprob"] = "-1.5"
    rows[0]["bytes"] = [ord("!")]
    with pytest.raises(Mi2Refusal):
        extract_fixed_branch_margin(canonical_bytes({"schema_version": FULL_TRACE_SCHEMA, "rows": rows}))


def test_margin_endpoint_can_detect_when_unique_content_has_content_p_one() -> None:
    schedule = ALL_SCHEDULES[0]
    content = {f"P{index:02d}": (sha256(f"unique-left-{index}".encode()).hexdigest(), sha256(f"unique-right-{index}".encode()).hexdigest()) for index in range(1, 13)}
    margins = {}
    for index, orientation in enumerate(schedule, 1):
        margins[f"P{index:02d}"] = (Decimal(1), Decimal(0)) if orientation == "ED" else (Decimal(0), Decimal(1))
    result = endpoint_family_randomization(content, margins, schedule)
    content_endpoint, margin_endpoint = result["endpoints"]
    assert content_endpoint["p_value"] == "400/400"
    # The observed assignment and its global arm complement have equal absolute
    # margin, so the exact inclusive two-sided-like tail contains two schedules.
    assert margin_endpoint["p_value"] == "2/400"
    assert result["family_label"] == "FINITE_RANDOMIZED_ARM_ASSOCIATION_DETECTED"
    no_association = endpoint_family_randomization(
        content, {pair: (Decimal(0), Decimal(0)) for pair in content}, schedule,
    )
    assert no_association["family_label"] == "FINITE_RANDOMIZED_NO_ARM_ASSOCIATION_DETECTED"


def test_global_arm_complement_makes_both_exact_tails_even_and_at_least_two() -> None:
    content = {
        f"P{index:02d}": (sha256(f"left-{index % 3}".encode()).hexdigest(), sha256(f"right-{index % 4}".encode()).hexdigest())
        for index in range(1, 13)
    }
    margins = {f"P{index:02d}": (Decimal(index), Decimal(-index)) for index in range(1, 13)}
    for schedule in ALL_SCHEDULES:
        complement = tuple("DE" if orientation == "ED" else "ED" for orientation in schedule)
        assert statistic(content, schedule) == statistic(content, complement)
        assert margin_statistic(margins, schedule) == margin_statistic(margins, complement)
        for result in (exact_upper_tail_randomization(content, schedule),
                       exact_margin_upper_tail_randomization(margins, schedule)):
            assert result["upper_tail_numerator"] >= 2
            assert result["upper_tail_numerator"] % 2 == 0
