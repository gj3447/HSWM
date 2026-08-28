"""DNRD-5 lifecycle-projection to canonical-atom alignment contract.

The R2 lifecycle is a chronology of bounded projection records.  It is not a
canonical-atom admission history.  This module makes that distinction
machine-checkable against the exact shared 59-artifact lifecycle vector and
records the remaining adapter/support/block-closure gaps.  It performs no
model call, Permit resolution, admission, occurrence, or scientific analysis.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from _research.dnrd5.canonical_json import (
    CONTRACT_VERSION as CANONICAL_JSON_VERSION,
    canonical_bytes,
    parse_canonical,
)
from _research.dnrd5.lifecycle_contract import (
    LIFECYCLE_VERSION,
    SCHEMA_VERSION,
    validate_lifecycle_vector,
)


ALIGNMENT_VERSION = "hswm-dnrd5-lifecycle-atom-alignment/v1"
ALIGNMENT_SCOPE = "KIND_CARDINALITY_AND_PROJECTION_BOUNDARY_ONLY"
ALIGNMENT_STATUS = "STRUCTURAL_ALIGNMENT_GAPS_EXPOSED_NOT_ATOM_CLOSURE"
EXPECTED_TERMINAL = (
    "ALIGNMENT_CONTRACT_VALIDATED_ACTUAL_ATOM_AND_BYTE_CLOSURE_REQUIRED_"
    "SOURCE_A_FORBIDDEN"
)
LIFECYCLE_VECTOR_SHA256 = (
    "179225541585267214a6cc5b358551c39597c66e546adf46bebad121550763cc"
)
CANONICAL_SCHEMA_SHA256 = (
    "03c44dec6907d16955927a2ab2886c03db97f1dd5746bc5f343ce853864592a0"
)

DIRECT_GAP = "ATOM_KEY_OWNER_PROVENANCE_TYPED_REFS_UNBOUND"
NONAUTHORITATIVE = "NON_AUTHORITATIVE_LIFECYCLE_PROJECTION_ONLY"

_DIRECT_KIND_COUNTS: tuple[tuple[str, int, str], ...] = (
    ("STUDY_RANDOMNESS", 1, "study_randomness"),
    ("BLOCK_SPEC", 1, "block_spec"),
    ("EVALUATOR_COMMITMENT", 1, "evaluator_commitment"),
    ("PROBE_COMMITMENT", 1, "probe_commitment"),
    ("PLACEBO_COMMITMENT", 1, "placebo_commitment"),
    ("W0_SNAPSHOT", 1, "w0_snapshot"),
    ("FORK_INCIDENCE", 4, "fork_incidence"),
    ("EPISODE_ACTIVATION", 1, "episode_activation"),
    ("TRAJECTORY_CONTRACT", 1, "trajectory_contract"),
    ("TRAJECTORY_SEAL", 1, "trajectory_seal"),
    ("EVALUATOR_RELEASE", 1, "evaluator_release"),
    ("HIDDEN_OUTCOME", 1, "hidden_outcome"),
    ("OUTCOME_CREDIT_ESCROW", 1, "outcome_credit_escrow"),
    ("PLACEBO_RECEIPT", 1, "placebo_receipt"),
    ("FEEDBACK_ASSIGNMENT", 4, "feedback_assignment"),
    ("REVISION_PROPOSAL", 4, "revision_proposal"),
    ("CANDIDATE_VALIDATION", 4, "candidate_validation"),
    ("CREDIT_DECISION", 4, "credit_decision"),
    ("TRANSITION_RECEIPT", 3, "transition_receipt"),
    ("RESTORE_TRANSACTION", 1, "restore_transaction"),
    ("BEHAVIOR_PROJECTION", 4, "behavior_projection"),
    ("PROBE_OUTCOME", 4, "probe_outcome"),
    ("BLOCK_SEAL", 1, "block_seal"),
)

_LIFECYCLE_KIND_ORDER = (
    "STUDY_RANDOMNESS",
    "BLOCK_SPEC",
    "EVALUATOR_COMMITMENT",
    "PROBE_COMMITMENT",
    "PLACEBO_COMMITMENT",
    "W0_SNAPSHOT",
    "FORK_INCIDENCE",
    "ARM_ASSIGNMENT",
    "EPISODE_ACTIVATION",
    "TRAJECTORY_CONTRACT",
    "TRAJECTORY_SEAL",
    "EVALUATOR_RELEASE",
    "HIDDEN_OUTCOME",
    "OUTCOME_CREDIT_ESCROW",
    "PLACEBO_RECEIPT",
    "FEEDBACK_ASSIGNMENT",
    "REVISION_PROPOSAL",
    "CANDIDATE_VALIDATION",
    "CREDIT_DECISION",
    "ARM_TRANSITION",
    "TRANSITION_RECEIPT",
    "RESTORE_TRANSACTION",
    "BEHAVIOR_PROJECTION",
    "PROBE_RESPONSE_SEAL",
    "PROBE_OUTCOME",
    "DELAYED_AUDIT_RELEASE",
    "BLOCK_SEAL",
)

_SUPPORT_KINDS: tuple[tuple[str, str], ...] = (
    ("permit_policy", "PERMISSION_INVARIANT"),
    ("authorization_decision", "CURRENT_AUTHORIZATION"),
    ("capability_issuance", "SCOPED_EFFECT_CAPABILITY"),
    ("revocation_status", "CURRENT_REVOCATION"),
    ("evaluator_capability", "EVALUATOR_RELEASE_AUTHORITY"),
    ("grant_snapshot", "TRANSITION_GRANT_SNAPSHOT"),
    ("capability_consumption", "ONE_SHOT_EFFECT_CONSUMPTION"),
    ("restore_policy", "ROLLBACK_AUTHORIZATION"),
    ("macro_disposition", "ADMITTED_SUCCESSOR_STATE"),
    ("projection_policy", "BEHAVIOR_READSET_BOUNDARY"),
)

_BLOCK_SEAL_REFS = (
    ("block", ("block_spec",), 1, 1),
    ("assignment", ("block_assignment",), 1, 1),
    ("probe-outcome", ("probe_outcome",), 4, 4),
)

_BLOCK_SEAL_MISSING = (
    "ADMITTED_BLOCK_ATOM_SET",
    "COMPLETE_NINE_CALL_LEDGER",
    "FIFTEEN_EVENT_CHRONOLOGY",
    "ACTUAL_CONTENT_BYTES",
    "PROVIDER_GATEWAY_LEDGER",
    "LIFECYCLE_PROJECTION_TO_CANONICAL_ATOM_BINDINGS",
    "DELAYED_AUDIT_RELEASE_CANONICAL_KIND_AND_AUTHORITY",
)

_HARD_NONCLAIMS = (
    "NO_CANONICAL_ATOM_UID_OWNER_PROVENANCE_OR_TYPED_REFERENCE_IS_BOUND",
    "NO_ACTUAL_PRODUCTION_BYTES_OR_PROVIDER_CALL_IS_PRESENT",
    "NO_PERMIT_ADMISSION_OCCURRENCE_CAUSAL_LEARNING_OR_SCIENTIFIC_RESULT_IS_ESTABLISHED",
    "LIFECYCLE_AND_KG_PROJECTIONS_ARE_NOT_HSWM_COGNITION_OR_LEARNING",
)


class LifecycleAtomAlignmentRefusal(ValueError):
    """The alignment vector or its bound lifecycle is not the exact contract."""


@dataclass(frozen=True)
class LifecycleAtomAlignmentSummary:
    event_count: int
    artifact_count: int
    artifact_kind_count: int
    generation_call_count: int
    direct_projection_count: int
    aggregated_slot_count: int
    derived_projection_count: int
    semantic_adapter_count: int
    missing_kind_count: int
    unbound_projection_count: int
    vector_sha256: str
    terminal: str
    atom_closure_established: bool = False
    source_a_eligible: bool = False
    occurrence_established: bool = False
    scientific_terminal_issued: bool = False


def _direct_mapping(artifact_kind: str, count: int, canonical_kind: str) -> dict[str, Any]:
    return {
        "artifactKind": artifact_kind,
        "projectionCount": count,
        "mappingMode": "DIRECT_NONAUTHORITATIVE_PROJECTION",
        "canonicalKind": canonical_kind,
        "canonicalAtomCount": count,
        "sourceCanonicalKinds": [canonical_kind],
        "authorityBoundary": NONAUTHORITATIVE,
        "gapCode": DIRECT_GAP,
        "closureReady": False,
    }


def _kind_mappings() -> list[dict[str, Any]]:
    direct = {
        artifact_kind: _direct_mapping(artifact_kind, count, canonical_kind)
        for artifact_kind, count, canonical_kind in _DIRECT_KIND_COUNTS
    }
    direct["ARM_ASSIGNMENT"] = {
        "artifactKind": "ARM_ASSIGNMENT",
        "projectionCount": 4,
        "mappingMode": "FOUR_SLOT_PROJECTION_OF_ONE_ATOM",
        "canonicalKind": "block_assignment",
        "canonicalAtomCount": 1,
        "sourceCanonicalKinds": ["study_randomness", "block_spec", "fork_incidence", "block_assignment"],
        "authorityBoundary": NONAUTHORITATIVE,
        "gapCode": "FOUR_ROWS_LACK_ONE_ASSIGNMENT_REF_AND_FOUR_DISTINCT_FORK_REFS",
        "closureReady": False,
    }
    direct["ARM_TRANSITION"] = {
        "artifactKind": "ARM_TRANSITION",
        "projectionCount": 4,
        "mappingMode": "DERIVED_MULTI_ATOM_PROJECTION",
        "canonicalKind": None,
        "canonicalAtomCount": None,
        "sourceCanonicalKinds": [
            "candidate_validation",
            "credit_decision",
            "capability_consumption",
            "transition_receipt",
            "macro_disposition",
            "restore_transaction",
        ],
        "authorityBoundary": NONAUTHORITATIVE,
        "gapCode": "ARM_DEPENDENT_SOURCE_ATOM_BINDING_CONTRACT_ABSENT",
        "closureReady": False,
    }
    direct["PROBE_RESPONSE_SEAL"] = {
        "artifactKind": "PROBE_RESPONSE_SEAL",
        "projectionCount": 4,
        "mappingMode": "SEMANTIC_ADAPTER_REQUIRED",
        "canonicalKind": "probe_trajectory",
        "canonicalAtomCount": 4,
        "sourceCanonicalKinds": ["probe_commitment", "behavior_projection", "probe_trajectory"],
        "authorityBoundary": NONAUTHORITATIVE,
        "gapCode": "RESPONSE_SEAL_BYTES_NOT_EQUIVALENT_TO_PROBE_TRAJECTORY_ATOM",
        "closureReady": False,
    }
    direct["DELAYED_AUDIT_RELEASE"] = {
        "artifactKind": "DELAYED_AUDIT_RELEASE",
        "projectionCount": 1,
        "mappingMode": "CANONICAL_KIND_MISSING",
        "canonicalKind": None,
        "canonicalAtomCount": None,
        "sourceCanonicalKinds": [],
        "authorityBoundary": NONAUTHORITATIVE,
        "gapCode": "AUDIT_RELEASE_REQUIRES_SUCCESSOR_SCHEMA_KIND_OWNER_AND_AUTHORITY_REFS",
        "closureReady": False,
    }
    return [direct[kind] for kind in _LIFECYCLE_KIND_ORDER]


def _arm_transition_profiles() -> list[dict[str, Any]]:
    common = ["candidate_validation", "credit_decision"]
    admitted = [
        *common,
        "capability_consumption",
        "transition_receipt",
        "macro_disposition",
    ]
    return [
        {
            "arm": "ACTIVE",
            "effectStatus": "ADMITTED_GENUINE_OUTCOME_SUCCESSOR",
            "requiredSourceCanonicalKinds": admitted,
        },
        {
            "arm": "OUTCOME_INDEPENDENT_SHAM",
            "effectStatus": "ADMITTED_MATCHED_PLACEBO_SUCCESSOR",
            "requiredSourceCanonicalKinds": admitted,
        },
        {
            "arm": "DELAYED_NO_CREDIT",
            "effectStatus": "QUARANTINED_NO_ADMISSION",
            "requiredSourceCanonicalKinds": common,
        },
        {
            "arm": "EXACT_W0_ROLLBACK",
            "effectStatus": "ADMITTED_THEN_RESTORED_EXACT_W0",
            "requiredSourceCanonicalKinds": [*admitted, "restore_transaction"],
        },
    ]


def _lifecycle_observation(lifecycle_raw: bytes) -> tuple[dict[str, Any], Counter[str]]:
    summary = validate_lifecycle_vector(lifecycle_raw)
    try:
        parsed = parse_canonical(lifecycle_raw)
    except ValueError as error:  # pragma: no cover - already refused above
        raise LifecycleAtomAlignmentRefusal("lifecycle bytes are not canonical") from error
    events = parsed["lifecycle"]["events"]
    counts: Counter[str] = Counter(
        artifact["kind"]
        for event in events
        for artifact in event["artifacts"]
    )
    if tuple(counts) != _LIFECYCLE_KIND_ORDER:
        raise LifecycleAtomAlignmentRefusal("lifecycle artifact kind order drifted")
    observed = {
        "eventCount": summary.event_count,
        "generationCallCount": summary.generation_call_count,
        "artifactCount": summary.artifact_count,
        "artifactKindCount": len(counts),
        "kindCounts": [
            {"artifactKind": kind, "count": counts[kind]}
            for kind in _LIFECYCLE_KIND_ORDER
        ],
    }
    return observed, counts


def build_lifecycle_atom_alignment_vector(lifecycle_raw: bytes) -> dict[str, Any]:
    observed, _ = _lifecycle_observation(lifecycle_raw)
    return {
        "_tag": "Dnrd5LifecycleAtomAlignment",
        "contractVersion": ALIGNMENT_VERSION,
        "canonicalJsonVersion": CANONICAL_JSON_VERSION,
        "schemaVersion": SCHEMA_VERSION,
        "canonicalSchemaSha256": CANONICAL_SCHEMA_SHA256,
        "lifecycleContractVersion": LIFECYCLE_VERSION,
        "lifecycleVectorSha256": sha256(lifecycle_raw).hexdigest(),
        "scope": ALIGNMENT_SCOPE,
        "status": ALIGNMENT_STATUS,
        "expectedTerminal": EXPECTED_TERMINAL,
        "observedLifecycle": observed,
        "kindMappings": _kind_mappings(),
        "armTransitionProfiles": _arm_transition_profiles(),
        "requiredCanonicalSupport": [
            {
                "canonicalKind": kind,
                "closureRole": role,
                "lifecycleArtifactPresent": False,
            }
            for kind, role in _SUPPORT_KINDS
        ],
        "blockSealCurrentContract": {
            "canonicalKind": "block_seal",
            "typedReferences": [
                {
                    "role": role,
                    "targetKinds": list(targets),
                    "minimum": minimum,
                    "maximum": maximum,
                }
                for role, targets, minimum, maximum in _BLOCK_SEAL_REFS
            ],
            "closureStatus": "INSUFFICIENT_FOR_PRODUCTION_BLOCK_CLOSURE",
            "missingBindings": list(_BLOCK_SEAL_MISSING),
        },
        "postBlockCanonicalKinds": ["block_analysis", "study_analysis"],
        "hardNonclaims": list(_HARD_NONCLAIMS),
    }


def build_lifecycle_atom_alignment_bytes(lifecycle_raw: bytes) -> bytes:
    return canonical_bytes(build_lifecycle_atom_alignment_vector(lifecycle_raw))


def validate_lifecycle_atom_alignment(
    alignment_raw: bytes,
    lifecycle_raw: bytes,
) -> LifecycleAtomAlignmentSummary:
    try:
        parsed = parse_canonical(alignment_raw)
    except ValueError as error:
        raise LifecycleAtomAlignmentRefusal(
            "alignment is not exact canonical-json/v1"
        ) from error
    expected = build_lifecycle_atom_alignment_vector(lifecycle_raw)
    if parsed != expected or alignment_raw != canonical_bytes(expected):
        raise LifecycleAtomAlignmentRefusal(
            "alignment identity, mapping, boundary, or lifecycle binding drifted"
        )

    observed = parsed["observedLifecycle"]
    mappings = parsed["kindMappings"]
    by_mode = Counter(mapping["mappingMode"] for mapping in mappings)
    count_by_mode = Counter()
    for mapping in mappings:
        if mapping["authorityBoundary"] != NONAUTHORITATIVE or mapping["closureReady"] is not False:
            raise LifecycleAtomAlignmentRefusal(
                "a lifecycle projection was promoted to authority or closure"
            )
        count_by_mode[mapping["mappingMode"]] += mapping["projectionCount"]

    if (
        by_mode != Counter(
            {
                "DIRECT_NONAUTHORITATIVE_PROJECTION": 23,
                "FOUR_SLOT_PROJECTION_OF_ONE_ATOM": 1,
                "DERIVED_MULTI_ATOM_PROJECTION": 1,
                "SEMANTIC_ADAPTER_REQUIRED": 1,
                "CANONICAL_KIND_MISSING": 1,
            }
        )
        or sum(count_by_mode.values()) != 59
        or observed != expected["observedLifecycle"]
    ):
        raise LifecycleAtomAlignmentRefusal(
            "alignment mode or lifecycle cardinality arithmetic drifted"
        )

    return LifecycleAtomAlignmentSummary(
        event_count=observed["eventCount"],
        artifact_count=observed["artifactCount"],
        artifact_kind_count=observed["artifactKindCount"],
        generation_call_count=observed["generationCallCount"],
        direct_projection_count=count_by_mode["DIRECT_NONAUTHORITATIVE_PROJECTION"],
        aggregated_slot_count=count_by_mode["FOUR_SLOT_PROJECTION_OF_ONE_ATOM"],
        derived_projection_count=count_by_mode["DERIVED_MULTI_ATOM_PROJECTION"],
        semantic_adapter_count=count_by_mode["SEMANTIC_ADAPTER_REQUIRED"],
        missing_kind_count=count_by_mode["CANONICAL_KIND_MISSING"],
        unbound_projection_count=sum(count_by_mode.values()),
        vector_sha256=sha256(alignment_raw).hexdigest(),
        terminal=EXPECTED_TERMINAL,
    )


def write_lifecycle_atom_alignment_vector(
    path: Path,
    lifecycle_path: Path,
) -> str:
    raw = build_lifecycle_atom_alignment_bytes(lifecycle_path.read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return sha256(raw).hexdigest()


if __name__ == "__main__":
    root = Path(__file__).parents[2]
    lifecycle_path = root / "_research/dnrd5/vectors/lifecycle_contract_v1.json"
    output = root / "_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json"
    print(write_lifecycle_atom_alignment_vector(output, lifecycle_path))
