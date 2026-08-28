"""Fail-closed contract-vector checks for the DNRD-5 production judge boundary."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from _research.dnrd5 import contracts


VECTOR_PATH = Path(__file__).parents[1] / "_research/dnrd5/vectors/production_contract_v1.json"


def _raw() -> bytes:
    return VECTOR_PATH.read_bytes()


def _value() -> dict[str, object]:
    return json.loads(_raw())


def _canonical(value: object) -> bytes:
    return contracts.canonical_json_bytes(value)


def test_accepted_fixture_is_structural_only_with_exact_universe_and_call_expansion() -> None:
    result = contracts.validate_production_contract_vector(_raw())
    assert result["integrity_status"] == contracts.SYNTHETIC_FIXTURE_TERMINAL
    assert result["fixture_scope"] == contracts.STRUCTURAL_FIXTURE_SCOPE
    assert result["actual_per_block_evidence_validated"] is False
    assert result["scientific_terminal_issued"] is False
    assert result["expanded_call_count"] == 2700
    ids = result["analysis_expected_block_ids"]
    assert ids[0] == "DNRD5-BLOCK-0001"
    assert ids[-1] == "DNRD5-BLOCK-0300"
    assert len(ids) == 300


def test_vector_is_exact_canonical_compact_json() -> None:
    assert contracts.parse_canonical_json(_raw())["schema_version"] == contracts.SCHEMA_VERSION
    with pytest.raises(contracts.ContractRefusal, match="compact canonical-json/v1"):
        contracts.parse_canonical_json(b" " + _raw())
    with pytest.raises(contracts.ContractRefusal, match="compact canonical-json/v1"):
        contracts.parse_canonical_json(b'{"a":1,"a":2}')


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda value: value["block_universe"].__setitem__("prefix", "OTHER-"), "block_universe must"),
        (lambda value: value.__setitem__("arms", ["ACTIVE"] * 4), "arm labels"),
        (lambda value: value["call_ledger"].__setitem__("total_generation_calls", 2699), "2,700-call total"),
        (lambda value: value["assignment"].__setitem__("opaque_clone_count", 3), "four opaque clones"),
        (lambda value: value["w0"].__setitem__("rollback_root_sha256", "f" * 64), "rollback"),
        (lambda value: value["permit"].__setitem__("authorizer_principal", "actor"), "authorizer inequality"),
        (lambda value: value["permit"].__setitem__("revocation_status", "REVOKED"), "checked not revoked"),
        (lambda value: value["forbidden_input_flags"].__setitem__("cache_denied", False), "forbidden-input"),
        (lambda value: value["blind_evaluator"].__setitem__("arm_hidden", False), "blindness"),
        (lambda value: value.__setitem__("expected_terminal", "CAUSAL_MACROPLASTICITY_GO"), "synthetic structural evidence only"),
    ],
)
def test_adversarial_mutations_fail_closed(mutate, match: str) -> None:
    value = deepcopy(_value())
    mutate(value)
    with pytest.raises(contracts.ContractRefusal, match=match):
        contracts.validate_production_contract_vector(_canonical(value))


def test_digest_bindings_reject_universe_assignment_and_ledger_drift() -> None:
    for section, key, match in (
        ("block_universe", "ordered_ids_sha256", "block universe digest"),
        ("assignment", "per_block_assignment_sha256", "per-block assignment digest"),
        ("call_ledger", "expanded_sha256", "expanded 2,700-call ledger"),
    ):
        value = deepcopy(_value())
        value[section][key] = "0" * 64
        with pytest.raises(contracts.ContractRefusal, match=match):
            contracts.validate_production_contract_vector(_canonical(value))


def test_call_grammar_has_one_shared_trajectory_four_proposals_and_four_probes() -> None:
    calls = contracts.expand_call_ledger(contracts.expand_ordered_block_ids(_value()["block_universe"]))
    first = calls[:9]
    assert [row["call"] for row in first] == list(contracts.CALL_GRAMMAR)
    assert sum(row["call"] == "PRE_OUTCOME_TRAJECTORY" for row in first) == 1
    assert sum(row["call"].startswith("PROPOSAL_OPAQUE_SLOT_") for row in first) == 4
    assert sum(row["call"].startswith("FRESH_PROBE_OPAQUE_SLOT_") for row in first) == 4
    assert all(arm not in row["call"] for row in first for arm in contracts.ARMS)


def test_chronology_requires_complete_r2_chain_and_rejects_boolean_ordinal() -> None:
    value = _value()
    seals = value["chronology"]["seals"]
    assert [seal["event"] for seal in seals] == list(contracts.CHRONOLOGY_EVENTS)
    for prior, current in zip(seals, seals[1:]):
        assert current["previous_seal_sha256"] == prior["sha256"]
    broken = deepcopy(value)
    broken["chronology"]["seals"][0]["ordinal"] = True
    with pytest.raises(contracts.ContractRefusal, match="order drifted"):
        contracts.validate_production_contract_vector(_canonical(broken))
    broken = deepcopy(value)
    broken["chronology"]["seals"][5]["previous_seal_sha256"] = "f" * 64
    with pytest.raises(contracts.ContractRefusal, match="chain predecessor"):
        contracts.validate_production_contract_vector(_canonical(broken))
