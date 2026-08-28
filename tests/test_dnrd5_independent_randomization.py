"""Cross-check independent DNRD-5 randomization consumer against producer bytes."""

from __future__ import annotations

import copy

import pytest

from _research.dnrd5 import independent_randomization as consumer
from _research.dnrd5 import randomization as producer


ENTROPY = "01" * 32
BINDING = "ab" * 32


def _duplicate_assignment(plan: dict[str, object]) -> None:
    assignment = plan["blocks"][0]["private_assignment"]
    first, second = tuple(assignment)[:2]
    assignment[first] = assignment[second]


def test_independent_consumer_matches_producer_exactly_for_all_300_blocks() -> None:
    produced = producer.derive_study_plan(future_randomness_hex=ENTROPY, study_binding_sha256=BINDING)
    consumed = consumer.derive_study_plan(future_randomness_hex=ENTROPY, study_binding_sha256=BINDING)
    assert consumer.canonical_json_bytes(consumed) == producer.canonical_json_bytes(produced)
    assert consumed["study_plan_sha256"] == produced["study_plan_sha256"]
    assert consumed["block_ids_sha256"] == produced["block_ids_sha256"]
    assert len(consumed["blocks"]) == 300
    assert sum(len(block["private_call_schedule"]) for block in consumed["blocks"]) == 2700


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["blocks"].reverse(),
        lambda p: p["blocks"][0]["sealed_fork_projection"]["forks"].reverse(),
        _duplicate_assignment,
        lambda p: p["blocks"][0]["private_call_schedule"][0].__setitem__("rng_seed_sha256", "00" * 32),
    ],
)
def test_post_randomness_mutations_fail_closed(mutate) -> None:
    plan = consumer.derive_study_plan(future_randomness_hex=ENTROPY, study_binding_sha256=BINDING)
    mutate(plan)
    with pytest.raises(consumer.IndependentRandomizationRefusal, match="exactly rederive"):
        consumer.validate_study_plan(plan, future_randomness_hex=ENTROPY, study_binding_sha256=BINDING)


def test_terminal_marker_limits_scope_and_no_caller_fork_order_api() -> None:
    assert "NOT_CHRONOLOGY" in consumer.TERMINAL_MARKER
    assert "NOT_EXECUTION" in consumer.TERMINAL_MARKER
    assert "NOT_SCIENTIFIC_RESULT" in consumer.TERMINAL_MARKER
    assert "fork_order" not in consumer.derive_block_plan.__annotations__
