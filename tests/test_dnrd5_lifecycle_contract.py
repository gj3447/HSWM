"""Independent Python checks for the shared DNRD-5 lifecycle vector."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from _research.dnrd5.lifecycle_contract import (
    EXPECTED_TERMINAL,
    LifecycleContractRefusal,
    build_synthetic_lifecycle_vector,
    build_synthetic_lifecycle_vector_bytes,
    validate_lifecycle_vector,
)


VECTOR_PATH = (
    Path(__file__).parents[1]
    / "_research/dnrd5/vectors/lifecycle_contract_v1.json"
)
VECTOR_SHA256 = "179225541585267214a6cc5b358551c39597c66e546adf46bebad121550763cc"
LIFECYCLE_SHA256 = "8b4c5fcd2333fe5c1a499983837f7eaa33ba764ebddf2bca14cb94366ff0e9fc"


def _raw() -> bytes:
    return VECTOR_PATH.read_bytes()


def _mutated(mutate) -> bytes:
    value = deepcopy(build_synthetic_lifecycle_vector())
    mutate(value)
    return canonical_bytes(value)


def test_checked_in_vector_is_exact_deterministic_no_suffix_bytes() -> None:
    raw = _raw()
    assert raw == build_synthetic_lifecycle_vector_bytes()
    assert not raw.endswith(b"\n")
    summary = validate_lifecycle_vector(raw)
    assert summary.block_id == "DNRD5-BLOCK-0001"
    assert summary.event_count == 15
    assert summary.generation_call_count == 9
    assert summary.artifact_count == 59
    assert summary.lifecycle_sha256 == LIFECYCLE_SHA256
    assert summary.vector_sha256 == VECTOR_SHA256


def test_rehearsal_terminal_cannot_be_promoted_to_evidence() -> None:
    summary = validate_lifecycle_vector(_raw())
    assert summary.terminal == EXPECTED_TERMINAL
    assert summary.production_content_validated is False
    assert summary.occurrence_established is False
    assert summary.scientific_terminal_issued is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.__setitem__("extra", True),
        lambda value: value.__setitem__("expectedTerminal", "CAUSAL_MACROPLASTICITY_GO"),
        lambda value: value["lifecycle"].__setitem__("blockId", "DNRD5-BLOCK-0000"),
        lambda value: value["lifecycle"]["events"].__setitem__(
            1, value["lifecycle"]["events"][0]
        ),
        lambda value: value["lifecycle"]["events"][5].__setitem__(
            "generationCallCount", 0
        ),
        lambda value: value["lifecycle"]["events"][0].__setitem__("ordinal", True),
        lambda value: value["lifecycle"]["events"][0]["artifacts"][0][
            "content"
        ].__setitem__("sha256", "0" * 64),
        lambda value: value["artifactContents"][0]["content"].__setitem__(
            "kind", "BLOCK_SPEC"
        ),
        lambda value: value["artifactContents"].reverse(),
    ],
)
def test_identity_chain_descriptor_and_content_mutations_fail_closed(mutate) -> None:
    with pytest.raises(LifecycleContractRefusal):
        validate_lifecycle_vector(_mutated(mutate))


def test_alternate_bytes_and_duplicate_keys_fail_before_semantic_validation() -> None:
    with pytest.raises(LifecycleContractRefusal):
        validate_lifecycle_vector(_raw() + b"\n")
    with pytest.raises(LifecycleContractRefusal):
        validate_lifecycle_vector(b'{"_tag":"x","_tag":"x"}')
