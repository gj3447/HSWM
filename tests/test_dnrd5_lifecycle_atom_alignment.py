"""Independent Python checks for DNRD-5 lifecycle/atom alignment."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dnrd5.lifecycle_atom_alignment import (
    CANONICAL_SCHEMA_SHA256,
    EXPECTED_TERMINAL,
    LifecycleAtomAlignmentRefusal,
    build_lifecycle_atom_alignment_bytes,
    validate_lifecycle_atom_alignment,
)


ROOT = Path(__file__).parents[1]
LIFECYCLE_PATH = ROOT / "_research/dnrd5/vectors/lifecycle_contract_v1.json"
ALIGNMENT_PATH = ROOT / "_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json"
ALIGNMENT_SHA256 = "0e3ba180d8a3be3c2ed83ffe932965f8500862e02bdb07d953bf67a483f5c807"


def _alignment() -> bytes:
    return ALIGNMENT_PATH.read_bytes()


def _lifecycle() -> bytes:
    return LIFECYCLE_PATH.read_bytes()


def _mutated(mutate) -> bytes:
    value = deepcopy(parse_canonical(_alignment()))
    mutate(value)
    return canonical_bytes(value)


def test_exact_alignment_vector_binds_the_shared_59_projection_lifecycle() -> None:
    raw = _alignment()
    assert raw == build_lifecycle_atom_alignment_bytes(_lifecycle())
    assert not raw.endswith(b"\n")
    summary = validate_lifecycle_atom_alignment(raw, _lifecycle())
    assert summary.event_count == 15
    assert summary.artifact_count == 59
    assert summary.artifact_kind_count == 27
    assert summary.generation_call_count == 9
    assert summary.direct_projection_count == 46
    assert summary.aggregated_slot_count == 4
    assert summary.derived_projection_count == 4
    assert summary.semantic_adapter_count == 4
    assert summary.missing_kind_count == 1
    assert summary.unbound_projection_count == 59
    assert summary.vector_sha256 == ALIGNMENT_SHA256


def test_alignment_keeps_projection_instrument_separate_from_atom_and_science() -> None:
    summary = validate_lifecycle_atom_alignment(_alignment(), _lifecycle())
    assert summary.terminal == EXPECTED_TERMINAL
    assert summary.atom_closure_established is False
    assert summary.source_a_eligible is False
    assert summary.occurrence_established is False
    assert summary.scientific_terminal_issued is False


def test_special_mappings_expose_four_to_one_derived_and_adapter_semantics() -> None:
    vector = parse_canonical(_alignment())
    mappings = {row["artifactKind"]: row for row in vector["kindMappings"]}

    assignment = mappings["ARM_ASSIGNMENT"]
    assert assignment["projectionCount"] == 4
    assert assignment["canonicalAtomCount"] == 1
    assert assignment["canonicalKind"] == "block_assignment"
    assert assignment["mappingMode"] == "FOUR_SLOT_PROJECTION_OF_ONE_ATOM"
    assert "fork_incidence" in assignment["sourceCanonicalKinds"]

    transition = mappings["ARM_TRANSITION"]
    assert transition["canonicalKind"] is None
    assert transition["mappingMode"] == "DERIVED_MULTI_ATOM_PROJECTION"
    assert set(transition["sourceCanonicalKinds"]) >= {
        "candidate_validation",
        "credit_decision",
        "transition_receipt",
        "macro_disposition",
        "restore_transaction",
    }

    probe = mappings["PROBE_RESPONSE_SEAL"]
    assert probe["canonicalKind"] == "probe_trajectory"
    assert probe["mappingMode"] == "SEMANTIC_ADAPTER_REQUIRED"

    audit = mappings["DELAYED_AUDIT_RELEASE"]
    assert audit["canonicalKind"] is None
    assert audit["canonicalAtomCount"] is None
    assert audit["sourceCanonicalKinds"] == []
    assert audit["mappingMode"] == "CANONICAL_KIND_MISSING"


def test_support_and_block_seal_gaps_are_explicit_and_schema_bound() -> None:
    vector = parse_canonical(_alignment())
    assert vector["canonicalSchemaSha256"] == CANONICAL_SCHEMA_SHA256
    assert [row["canonicalKind"] for row in vector["requiredCanonicalSupport"]] == [
        "permit_policy",
        "authorization_decision",
        "capability_issuance",
        "revocation_status",
        "evaluator_capability",
        "grant_snapshot",
        "capability_consumption",
        "restore_policy",
        "macro_disposition",
        "projection_policy",
    ]
    block_seal = vector["blockSealCurrentContract"]
    assert block_seal["closureStatus"] == "INSUFFICIENT_FOR_PRODUCTION_BLOCK_CLOSURE"
    assert block_seal["typedReferences"][-1] == {
        "role": "probe-outcome",
        "targetKinds": ["probe_outcome"],
        "minimum": 4,
        "maximum": 4,
    }
    assert {
        "COMPLETE_NINE_CALL_LEDGER",
        "FIFTEEN_EVENT_CHRONOLOGY",
        "ACTUAL_CONTENT_BYTES",
        "DELAYED_AUDIT_RELEASE_CANONICAL_KIND_AND_AUTHORITY",
    } <= set(block_seal["missingBindings"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.__setitem__("extra", True),
        lambda value: value.__setitem__("canonicalSchemaSha256", "0" * 64),
        lambda value: value.__setitem__("expectedTerminal", "SOURCE_A_QUALIFIED"),
        lambda value: value["observedLifecycle"].__setitem__("artifactCount", 58),
        lambda value: value["kindMappings"][7].__setitem__("canonicalAtomCount", 4),
        lambda value: value["kindMappings"][19].__setitem__("canonicalKind", "macro_disposition"),
        lambda value: value["kindMappings"][23].__setitem__("mappingMode", "DIRECT_NONAUTHORITATIVE_PROJECTION"),
        lambda value: value["kindMappings"][0].__setitem__("authorityBoundary", "EFFECT_AUTHORIZING"),
        lambda value: value["kindMappings"][0].__setitem__("closureReady", True),
        lambda value: value["requiredCanonicalSupport"].pop(),
        lambda value: value["blockSealCurrentContract"]["missingBindings"].pop(),
        lambda value: value["hardNonclaims"].clear(),
    ],
)
def test_alignment_identity_mapping_authority_and_gap_mutations_fail(mutate) -> None:
    with pytest.raises(LifecycleAtomAlignmentRefusal):
        validate_lifecycle_atom_alignment(_mutated(mutate), _lifecycle())


def test_transport_suffix_duplicate_keys_and_lifecycle_substitution_fail() -> None:
    with pytest.raises(LifecycleAtomAlignmentRefusal):
        validate_lifecycle_atom_alignment(_alignment() + b"\n", _lifecycle())
    with pytest.raises(LifecycleAtomAlignmentRefusal):
        validate_lifecycle_atom_alignment(b'{"_tag":"x","_tag":"x"}', _lifecycle())
    changed_lifecycle = _lifecycle().replace(
        b'"DNRD5-BLOCK-0001"', b'"DNRD5-BLOCK-0002"', 1
    )
    with pytest.raises((LifecycleAtomAlignmentRefusal, ValueError)):
        validate_lifecycle_atom_alignment(_alignment(), changed_lifecycle)
