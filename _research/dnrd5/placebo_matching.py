"""Exact public-envelope matching law for DNRD-5 genuine/placebo feedback.

This module proves a narrow algebraic fact: conditional on the complete frozen
model-visible pre-feedback history (including the chosen hypothesis and sealed
trajectory) and the explicit assumption that theta and the placebo remain
independent fair bits under that conditioning, the two model-visible feedback
envelopes have the same byte distribution.  Conditioning only on the public
choice is insufficient; an executable counterexample below fixes that limit.
This module does not establish the required production conditional law, that
releases occur in the declared timing class, or that a real capability, model
call, transition, or occurrence exists.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Any, Mapping

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)


STRATUM_SCHEMA = "hswm-dnrd5-public-feedback-stratum/v1"
PROJECTION_SCHEMA = "hswm-dnrd5-matched-feedback-projection/v1"
RELEASE_TIMING_CLASS = "POST_TRAJECTORY_SEAL_PRE_PROPOSAL_SEAL"
PROJECTION_STATUS = "SOURCE_TYPE_WITHHELD_MATCHED_PUBLIC_ENVELOPE"
LAW_ASSUMPTION = (
    "THETA_AND_PLACEBO_ARE_INDEPENDENT_FAIR_BITS_CONDITIONAL_ON_COMPLETE_"
    "MODEL_VISIBLE_PRE_FEEDBACK_HISTORY"
)
LAW_TERMINAL = (
    "EXACT_ENVELOPE_LAW_UNDER_STATED_LATENT_ASSUMPTION_NOT_RANDOMNESS_"
    "PROVENANCE_NOT_TIMING_OCCURRENCE_CAPABILITY_OR_SCIENTIFIC_RESULT"
)
CAPABILITY_PROJECTION = {
    "effectClass": "PROPOSAL_INPUT_ONLY",
    "mutationAuthority": "NOT_CARRIED_IN_MODEL_VISIBLE_FEEDBACK",
    "scopeClass": "ONE_BLOCK_ONE_TRAJECTORY_ONE_PROPOSAL",
    "valueDomain": "BINARY_CORRECTNESS",
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PlaceboMatchingRefusal(ValueError):
    """A feedback envelope or matching-law claim is not the frozen contract."""


@dataclass(frozen=True)
class ConditionalEnvelopeLaw:
    chosen_hypothesis: int
    fixed_model_visible_history: bool
    latent_case_count: int
    genuine_p0: Fraction
    genuine_p1: Fraction
    placebo_p0: Fraction
    placebo_p1: Fraction
    envelope_byte_length_0: int
    envelope_byte_length_1: int
    exact_byte_distribution_equal: bool


def _bit(value: Any, label: str) -> int:
    if type(value) is not int or value not in (0, 1):
        raise PlaceboMatchingRefusal(f"{label} must be integer 0 or 1")
    return value


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise PlaceboMatchingRefusal(f"{label} must be lowercase SHA-256")
    return value


def _exact(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise PlaceboMatchingRefusal(f"{label} key set drifted")
    return value


def public_stratum(
    *, public_core_commitment: str, chosen_hypothesis: int
) -> dict[str, Any]:
    """Build the exact public conditioning stratum for one sealed choice."""
    return {
        "schemaVersion": STRATUM_SCHEMA,
        "publicCoreCommitment": _sha(
            public_core_commitment, "public_core_commitment"
        ),
        "chosenHypothesis": _bit(chosen_hypothesis, "chosen_hypothesis"),
        "hypothesisCount": 2,
        "feedbackValueDomain": [0, 1],
    }


def feedback_projection(
    *,
    public_core_commitment: str,
    chosen_hypothesis: int,
    trajectory_commitment: str,
    feedback_bit: int,
) -> dict[str, Any]:
    """Build a source-blind model projection shared by genuine and placebo."""
    stratum = public_stratum(
        public_core_commitment=public_core_commitment,
        chosen_hypothesis=chosen_hypothesis,
    )
    return {
        "schemaVersion": PROJECTION_SCHEMA,
        "publicStratumSha256": canonical_sha256(stratum),
        "trajectoryCommitment": _sha(
            trajectory_commitment, "trajectory_commitment"
        ),
        "feedbackBit": _bit(feedback_bit, "feedback_bit"),
        "releaseTimingClass": RELEASE_TIMING_CLASS,
        "capabilityProjection": dict(CAPABILITY_PROJECTION),
        "projectionStatus": PROJECTION_STATUS,
    }


def feedback_projection_bytes(**kwargs: Any) -> bytes:
    return canonical_bytes(feedback_projection(**kwargs))


def validate_feedback_projection_bytes(
    raw: bytes,
    *,
    public_core_commitment: str,
    chosen_hypothesis: int,
    trajectory_commitment: str,
) -> dict[str, Any]:
    """Validate exact bytes while leaving the realized feedback bit unknown."""
    try:
        parsed = parse_canonical(raw)
    except CanonicalJsonError as error:
        raise PlaceboMatchingRefusal(
            "feedback projection is not exact canonical-json/v1"
        ) from error
    record = _exact(
        parsed,
        {
            "schemaVersion",
            "publicStratumSha256",
            "trajectoryCommitment",
            "feedbackBit",
            "releaseTimingClass",
            "capabilityProjection",
            "projectionStatus",
        },
        "feedback projection",
    )
    bit = _bit(record["feedbackBit"], "feedback projection bit")
    expected = feedback_projection(
        public_core_commitment=public_core_commitment,
        chosen_hypothesis=chosen_hypothesis,
        trajectory_commitment=trajectory_commitment,
        feedback_bit=bit,
    )
    if canonical_bytes(record) != canonical_bytes(expected):
        raise PlaceboMatchingRefusal(
            "feedback projection does not match the exact public stratum"
        )
    forbidden = (
        "active",
        "sham",
        "genuine",
        "placebo",
        "outcome",
        "theta",
        "arm",
        "fork",
        "clone",
        "probe",
        "answer",
        "capabilityid",
    )
    normalized = raw.decode("utf-8").lower().replace("_", "").replace("-", "")
    if any(token in normalized for token in forbidden):
        raise PlaceboMatchingRefusal(
            "model-visible feedback projection reveals source, arm, or hidden material"
        )
    return dict(record)


def exact_conditional_envelope_law() -> tuple[ConditionalEnvelopeLaw, ...]:
    """Enumerate both choices while holding all visible pre-feedback bytes fixed."""
    public_commitment = "a" * 64
    trajectory_commitment = "b" * 64
    summaries: list[ConditionalEnvelopeLaw] = []
    for choice in (0, 1):
        genuine: list[bytes] = []
        placebo: list[bytes] = []
        genuine_bits: list[int] = []
        placebo_bits: list[int] = []
        for theta in (0, 1):
            for placebo_bit in (0, 1):
                genuine_bit = int(choice == theta)
                genuine_bits.append(genuine_bit)
                placebo_bits.append(placebo_bit)
                genuine.append(
                    feedback_projection_bytes(
                        public_core_commitment=public_commitment,
                        chosen_hypothesis=choice,
                        trajectory_commitment=trajectory_commitment,
                        feedback_bit=genuine_bit,
                    )
                )
                placebo.append(
                    feedback_projection_bytes(
                        public_core_commitment=public_commitment,
                        chosen_hypothesis=choice,
                        trajectory_commitment=trajectory_commitment,
                        feedback_bit=placebo_bit,
                    )
                )
        by_bit = {
            bit: feedback_projection_bytes(
                public_core_commitment=public_commitment,
                chosen_hypothesis=choice,
                trajectory_commitment=trajectory_commitment,
                feedback_bit=bit,
            )
            for bit in (0, 1)
        }
        summaries.append(
            ConditionalEnvelopeLaw(
                chosen_hypothesis=choice,
                fixed_model_visible_history=True,
                latent_case_count=4,
                genuine_p0=Fraction(genuine_bits.count(0), 4),
                genuine_p1=Fraction(genuine_bits.count(1), 4),
                placebo_p0=Fraction(placebo_bits.count(0), 4),
                placebo_p1=Fraction(placebo_bits.count(1), 4),
                envelope_byte_length_0=len(by_bit[0]),
                envelope_byte_length_1=len(by_bit[1]),
                exact_byte_distribution_equal=Counter(genuine) == Counter(placebo),
            )
        )
    return tuple(summaries)


def choice_only_conditioning_counterexample() -> dict[str, Any]:
    """Show why a choice-only law fails when the sealed trajectory reveals theta.

    The example is deliberately not a production generator.  It holds the
    public choice fixed, sets the visible trajectory commitment as a function
    of theta, and leaves the placebo fair and independent.  Genuine and sham
    joint ``(trajectory, envelope)`` distributions then differ exactly.
    """
    public_commitment = "a" * 64
    choice = 0
    genuine: list[tuple[str, bytes]] = []
    placebo: list[tuple[str, bytes]] = []
    for theta in (0, 1):
        trajectory = canonical_sha256(
            {"counterexampleVisibleTheta": theta}
        )
        for placebo_bit in (0, 1):
            genuine.append(
                (
                    trajectory,
                    feedback_projection_bytes(
                        public_core_commitment=public_commitment,
                        chosen_hypothesis=choice,
                        trajectory_commitment=trajectory,
                        feedback_bit=int(choice == theta),
                    ),
                )
            )
            placebo.append(
                (
                    trajectory,
                    feedback_projection_bytes(
                        public_core_commitment=public_commitment,
                        chosen_hypothesis=choice,
                        trajectory_commitment=trajectory,
                        feedback_bit=placebo_bit,
                    ),
                )
            )
    return {
        "choiceOnlyConditioning": True,
        "trajectoryDependsOnTheta": True,
        "thetaMarginalFair": True,
        "placeboMarginalFairAndIndependent": True,
        "jointVisibleEnvelopeDistributionEqual": Counter(genuine)
        == Counter(placebo),
        "terminal": "COUNTEREXAMPLE_ONLY_NOT_A_PRODUCTION_DISTRIBUTION",
    }


def validate_exact_conditional_envelope_law() -> dict[str, Any]:
    """Fail closed unless both choice strata have the exact matched law."""
    laws = exact_conditional_envelope_law()
    for law in laws:
        if (
            law.latent_case_count != 4
            or not law.fixed_model_visible_history
            or law.genuine_p0 != Fraction(1, 2)
            or law.genuine_p1 != Fraction(1, 2)
            or law.placebo_p0 != Fraction(1, 2)
            or law.placebo_p1 != Fraction(1, 2)
            or law.envelope_byte_length_0 != law.envelope_byte_length_1
            or not law.exact_byte_distribution_equal
        ):
            raise PlaceboMatchingRefusal(
                "genuine/placebo conditional public-envelope law is not matched"
            )
    counterexample = choice_only_conditioning_counterexample()
    if counterexample["jointVisibleEnvelopeDistributionEqual"] is not False:
        raise PlaceboMatchingRefusal(
            "choice-only conditioning counterexample no longer distinguishes the laws"
        )
    return {
        "lawAssumption": LAW_ASSUMPTION,
        "choiceStrata": 2,
        "latentCasesPerStratum": 4,
        "exactByteDistributionEqualWithinEveryStratum": True,
        "completeModelVisibleHistoryConditioningRequired": True,
        "choiceOnlyConditioningSufficient": False,
        "sourceTypeAbsentFromProjection": True,
        "realRandomnessIndependenceEstablished": False,
        "actualReleaseTimingEstablished": False,
        "actualCapabilityMetadataEstablished": False,
        "terminal": LAW_TERMINAL,
    }
