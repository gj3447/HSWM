"""Exact-law and adversarial checks for DNRD-5 placebo matching."""

from __future__ import annotations

from copy import deepcopy

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from _research.dnrd5.placebo_matching import (
    LAW_ASSUMPTION,
    LAW_TERMINAL,
    PlaceboMatchingRefusal,
    choice_only_conditioning_counterexample,
    exact_conditional_envelope_law,
    feedback_projection,
    feedback_projection_bytes,
    validate_exact_conditional_envelope_law,
    validate_feedback_projection_bytes,
)


PUBLIC = "a" * 64
TRAJECTORY = "b" * 64


def _kwargs(bit: int = 0) -> dict[str, object]:
    return {
        "public_core_commitment": PUBLIC,
        "chosen_hypothesis": 1,
        "trajectory_commitment": TRAJECTORY,
        "feedback_bit": bit,
    }


def test_exact_conditional_distribution_matches_in_both_choice_strata() -> None:
    laws = exact_conditional_envelope_law()
    assert [law.chosen_hypothesis for law in laws] == [0, 1]
    for law in laws:
        assert law.fixed_model_visible_history is True
        assert law.genuine_p0 == law.genuine_p1 == law.placebo_p0 == law.placebo_p1
        assert law.envelope_byte_length_0 == law.envelope_byte_length_1
        assert law.exact_byte_distribution_equal is True
    status = validate_exact_conditional_envelope_law()
    assert status["lawAssumption"] == LAW_ASSUMPTION
    assert status["completeModelVisibleHistoryConditioningRequired"] is True
    assert status["choiceOnlyConditioningSufficient"] is False
    assert status["terminal"] == LAW_TERMINAL
    assert status["realRandomnessIndependenceEstablished"] is False
    assert status["actualReleaseTimingEstablished"] is False
    assert status["actualCapabilityMetadataEstablished"] is False


def test_choice_only_conditioning_fails_when_visible_trajectory_tracks_theta() -> None:
    counterexample = choice_only_conditioning_counterexample()
    assert counterexample == {
        "choiceOnlyConditioning": True,
        "trajectoryDependsOnTheta": True,
        "thetaMarginalFair": True,
        "placeboMarginalFairAndIndependent": True,
        "jointVisibleEnvelopeDistributionEqual": False,
        "terminal": "COUNTEREXAMPLE_ONLY_NOT_A_PRODUCTION_DISTRIBUTION",
    }


def test_projection_is_source_blind_and_exact_for_each_feedback_value() -> None:
    for bit in (0, 1):
        raw = feedback_projection_bytes(**_kwargs(bit))
        parsed = validate_feedback_projection_bytes(
            raw,
            public_core_commitment=PUBLIC,
            chosen_hypothesis=1,
            trajectory_commitment=TRAJECTORY,
        )
        assert parsed["feedbackBit"] == bit
        text = raw.decode().casefold()
        for forbidden in ("active", "sham", "genuine", "placebo", "theta", "fork", "clone"):
            assert forbidden not in text


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.__setitem__("extra", True),
        lambda value: value.__setitem__("schemaVersion", "alias"),
        lambda value: value.__setitem__("publicStratumSha256", "0" * 64),
        lambda value: value.__setitem__("trajectoryCommitment", "0" * 64),
        lambda value: value.__setitem__("feedbackBit", 2),
        lambda value: value.__setitem__("releaseTimingClass", "EARLY"),
        lambda value: value["capabilityProjection"].__setitem__("capabilityId", "active"),
        lambda value: value.__setitem__("projectionStatus", "ACTIVE"),
    ],
)
def test_envelope_metadata_source_and_stratum_drift_fail_closed(mutate) -> None:
    value = deepcopy(feedback_projection(**_kwargs()))
    mutate(value)
    with pytest.raises(PlaceboMatchingRefusal):
        validate_feedback_projection_bytes(
            canonical_bytes(value),
            public_core_commitment=PUBLIC,
            chosen_hypothesis=1,
            trajectory_commitment=TRAJECTORY,
        )


def test_noncanonical_bytes_and_wrong_expected_choice_fail_closed() -> None:
    raw = feedback_projection_bytes(**_kwargs())
    with pytest.raises(PlaceboMatchingRefusal):
        validate_feedback_projection_bytes(
            raw + b"\n",
            public_core_commitment=PUBLIC,
            chosen_hypothesis=1,
            trajectory_commitment=TRAJECTORY,
        )
    with pytest.raises(PlaceboMatchingRefusal):
        validate_feedback_projection_bytes(
            raw,
            public_core_commitment=PUBLIC,
            chosen_hypothesis=0,
            trajectory_commitment=TRAJECTORY,
        )
