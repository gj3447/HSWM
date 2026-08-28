"""Pure, fail-closed production-integrity vector validation for DNRD-5.

This module does not execute a block, resolve a real Permit, admit a state
transition, call a model, or issue a scientific terminal.  It validates the
byte-level contract that future independent producer and judge implementations
must both consume before any such work is eligible.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes as canonical_json_bytes,
    canonical_sha256,
    parse_canonical,
)


SCHEMA_VERSION = "hswm-dnrd5-production-contract-vector/v1"
CANONICAL_JSON_ENCODING = "hswm-canonical-json/v1 exact compact UTF-8 with UTF-16 key order, safe integers, and no suffix"
SYNTHETIC_FIXTURE_TERMINAL = "SYNTHETIC_CONTRACT_FIXTURE_ONLY_NOT_EXECUTION_OR_INTEGRITY_EVIDENCE"
STRUCTURAL_FIXTURE_SCOPE = "STRUCTURAL_ONLY_NO_EXECUTION_OR_INTEGRITY_EVIDENCE"
BLOCK_COUNT = 300
BLOCK_ID_PREFIX = "DNRD5-BLOCK-"
BLOCK_ID_WIDTH = 4
BLOCK_ID_START = 1
CALLS_PER_BLOCK = 9
TOTAL_GENERATION_CALLS = BLOCK_COUNT * CALLS_PER_BLOCK
ARMS = (
    "ACTIVE",
    "OUTCOME_INDEPENDENT_SHAM",
    "DELAYED_NO_CREDIT",
    "EXACT_W0_ROLLBACK",
)
CALL_GRAMMAR = (
    "PRE_OUTCOME_TRAJECTORY",
    "PROPOSAL_OPAQUE_SLOT_1",
    "PROPOSAL_OPAQUE_SLOT_2",
    "PROPOSAL_OPAQUE_SLOT_3",
    "PROPOSAL_OPAQUE_SLOT_4",
    "FRESH_PROBE_OPAQUE_SLOT_1",
    "FRESH_PROBE_OPAQUE_SLOT_2",
    "FRESH_PROBE_OPAQUE_SLOT_3",
    "FRESH_PROBE_OPAQUE_SLOT_4",
)
CHRONOLOGY_EVENTS = (
    "STUDY_AND_TASK_COMMITMENTS",
    "PROBE_AND_PLACEBO_COMMITMENTS",
    "W0_AND_FOUR_FORKS",
    "ARM_ASSIGNMENT",
    "EPISODE_AND_TRAJECTORY_CONTRACT",
    "TRAJECTORY_SEAL",
    "EVALUATOR_RELEASE_AND_HIDDEN_OUTCOME",
    "ESCROW_PLACEBO_AND_FEEDBACK_ASSIGNMENTS",
    "FOUR_PROPOSALS",
    "VALIDATION_CREDIT_TRANSITIONS_AND_RESTORE",
    "FOUR_BEHAVIOR_PROJECTIONS",
    "FOUR_PROBE_RESPONSE_SEALS",
    "FOUR_BLIND_PROBE_OUTCOMES",
    "DELAYED_OUTCOME_AUDIT_RELEASE",
    "BLOCK_SEAL",
)
SEAL_CHAIN_GENESIS_SHA256 = "0" * 64
_HEX = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")


class ContractRefusal(ValueError):
    """The submitted production-integrity vector is not safe to hand off."""


def parse_canonical_json(raw: bytes) -> dict[str, Any]:
    """Decode one canonical object, rejecting duplicate keys and alternate bytes."""
    try:
        value = parse_canonical(raw)
    except CanonicalJsonError as error:
        raise ContractRefusal("contract must use exact compact canonical-json/v1 bytes") from error
    if type(value) is not dict:
        raise ContractRefusal("contract root must be an object")
    return value


def _object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ContractRefusal(f"{label} key set drifted")
    return value


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise ContractRefusal(f"{label} must be lowercase SHA-256")
    return value


def _git(value: Any, label: str) -> str:
    if type(value) is not str or _GIT.fullmatch(value) is None:
        raise ContractRefusal(f"{label} must be lowercase Git SHA-1")
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or not value or len(value) > 256:
        raise ContractRefusal(f"{label} must be a nonempty identifier")
    return value


def expand_ordered_block_ids(template: Mapping[str, Any]) -> tuple[str, ...]:
    """Deterministically expand the frozen 300-block universe without 300 JSON rows."""
    values = _object(template, {"prefix", "width", "start", "count", "ordered_ids_sha256"}, "block_universe")
    prefix = _identifier(values["prefix"], "block_universe.prefix")
    width, start, count = values["width"], values["start"], values["count"]
    if (prefix, width, start, count) != (BLOCK_ID_PREFIX, BLOCK_ID_WIDTH, BLOCK_ID_START, BLOCK_COUNT):
        raise ContractRefusal("block_universe must be DNRD5-BLOCK-0001 through DNRD5-BLOCK-0300")
    ids = tuple(f"{prefix}{ordinal:0{width}d}" for ordinal in range(start, start + count))
    if tuple(sorted(ids)) != ids or len(set(ids)) != BLOCK_COUNT:
        raise ContractRefusal("expanded block IDs are not unique and strictly ordered")
    if canonical_sha256(list(ids)) != _sha(values["ordered_ids_sha256"], "block_universe.ordered_ids_sha256"):
        raise ContractRefusal("block universe digest does not match deterministic expansion")
    return ids


def expand_call_ledger(block_ids: Sequence[str]) -> tuple[dict[str, Any], ...]:
    """Expand the fixed nine-call grammar into its exactly 2,700 logical rows."""
    rows = tuple(
        {"block_id": block_id, "ordinal": ordinal, "call": call}
        for block_id in block_ids
        for ordinal, call in enumerate(CALL_GRAMMAR, start=1)
    )
    if len(rows) != TOTAL_GENERATION_CALLS:
        raise ContractRefusal("call ledger expansion does not equal 2,700 calls")
    return rows


def _validate_bindings(value: Any) -> None:
    bindings = _object(value, {"source", "preregistration", "runtime"}, "bindings")
    source = _object(bindings["source"], {"commit", "tree", "manifest_sha256"}, "bindings.source")
    prereg = _object(bindings["preregistration"], {"commit", "tree", "sha256"}, "bindings.preregistration")
    runtime = _object(bindings["runtime"], {"manifest_sha256", "model_sha256", "evaluator_sha256"}, "bindings.runtime")
    for entry, label in ((source, "bindings.source"), (prereg, "bindings.preregistration")):
        _git(entry["commit"], f"{label}.commit")
        _git(entry["tree"], f"{label}.tree")
    for entry, keys, label in ((source, ("manifest_sha256",), "bindings.source"), (prereg, ("sha256",), "bindings.preregistration"), (runtime, ("manifest_sha256", "model_sha256", "evaluator_sha256"), "bindings.runtime")):
        for key in keys:
            _sha(entry[key], f"{label}.{key}")


def _validate_chronology(value: Any) -> None:
    chronology = _object(value, {"seals", "chronology_sha256"}, "chronology")
    seals = chronology["seals"]
    if type(seals) is not list or len(seals) != len(CHRONOLOGY_EVENTS):
        raise ContractRefusal("chronology requires the complete ordered R2 seal sequence")
    normalized: list[dict[str, Any]] = []
    previous = SEAL_CHAIN_GENESIS_SHA256
    for ordinal, item in enumerate(seals, start=1):
        seal = _object(item, {"ordinal", "event", "previous_seal_sha256", "sha256"}, "chronology.seal")
        if type(seal["ordinal"]) is not int or seal["ordinal"] != ordinal or seal["event"] != CHRONOLOGY_EVENTS[ordinal - 1]:
            raise ContractRefusal("chronology seal order drifted")
        if seal["previous_seal_sha256"] != previous:
            raise ContractRefusal("chronology seal chain predecessor drifted")
        normalized.append(dict(seal))
        _sha(seal["sha256"], "chronology seal")
        previous = seal["sha256"]
    if canonical_sha256(normalized) != _sha(chronology["chronology_sha256"], "chronology.chronology_sha256"):
        raise ContractRefusal("chronology digest mismatch")


def _validate_assignment(value: Any, block_ids: Sequence[str]) -> None:
    assignment = _object(value, {"future_randomness_sha256", "assignment_commitment_sha256", "per_block_assignment_sha256", "opaque_clone_count", "permutation_domain"}, "assignment")
    for key in ("future_randomness_sha256", "assignment_commitment_sha256", "per_block_assignment_sha256"):
        _sha(assignment[key], f"assignment.{key}")
    if assignment["opaque_clone_count"] != 4 or assignment["permutation_domain"] != list(ARMS):
        raise ContractRefusal("assignment must bind four opaque clones to exact canonical arms")
    derived = canonical_sha256({"block_ids": list(block_ids), "arms": list(ARMS), "future_randomness_sha256": assignment["future_randomness_sha256"], "assignment_commitment_sha256": assignment["assignment_commitment_sha256"]})
    if assignment["per_block_assignment_sha256"] != derived:
        raise ContractRefusal("per-block assignment digest does not bind universe, arms, and future randomness")


def _validate_w0(value: Any) -> None:
    w0 = _object(value, {"clone_root_sha256", "clone_readset_sha256", "rollback_root_sha256", "rollback_readset_sha256"}, "w0")
    roots, readsets = w0["clone_root_sha256"], w0["clone_readset_sha256"]
    if type(roots) is not list or type(readsets) is not list or len(roots) != 4 or len(readsets) != 4:
        raise ContractRefusal("w0 requires four clone roots and readsets")
    for digest in [*roots, *readsets]:
        _sha(digest, "w0 clone digest")
    if len(set(roots)) != 1 or len(set(readsets)) != 1:
        raise ContractRefusal("four W0 clones must be behaviorally identical")
    if w0["rollback_root_sha256"] != roots[0] or w0["rollback_readset_sha256"] != readsets[0]:
        raise ContractRefusal("rollback must exactly restore W0 root and readset")


def _validate_permit(value: Any) -> None:
    permit = _object(value, {"actor_principal", "authorizer_principal", "state_custodian_principal", "restore_custodian_principal", "credit_adjudicator_principal", "authorization_record_custodian_principal", "decision", "grant_sha256", "revocation_status", "current_resolution_sha256"}, "permit")
    authorizer = _identifier(permit["authorizer_principal"], "permit.authorizer_principal")
    for key in ("actor_principal", "state_custodian_principal", "restore_custodian_principal", "credit_adjudicator_principal", "authorization_record_custodian_principal"):
        if authorizer == _identifier(permit[key], f"permit.{key}"):
            raise ContractRefusal("Permit authorizer inequality failed")
    if permit["decision"] != "GRANTED" or permit["revocation_status"] != "CHECKED_NOT_REVOKED":
        raise ContractRefusal("Permit must be granted and checked not revoked")
    _sha(permit["grant_sha256"], "permit.grant_sha256")
    _sha(permit["current_resolution_sha256"], "permit.current_resolution_sha256")


def _validate_hash_bundle(value: Any, keys: tuple[str, ...], label: str) -> None:
    bundle = _object(value, set(keys), label)
    for key in keys:
        _sha(bundle[key], f"{label}.{key}")


def validate_production_contract_vector(raw: bytes) -> dict[str, Any]:
    """Validate and return a synthetic structural-fixture projection only."""
    contract = parse_canonical_json(raw)
    required = {
        "schema_version", "canonical_json_encoding", "case_id", "fixture_scope", "expected_terminal", "bindings", "block_universe", "arms", "call_ledger", "commitments", "chronology", "assignment", "w0", "permit", "input_hashes", "forbidden_input_flags", "blind_evaluator", "analysis",
    }
    root = _object(contract, required, "contract")
    if root["schema_version"] != SCHEMA_VERSION or root["canonical_json_encoding"] != CANONICAL_JSON_ENCODING:
        raise ContractRefusal("contract schema or canonical encoding drifted")
    _identifier(root["case_id"], "case_id")
    if root["fixture_scope"] != STRUCTURAL_FIXTURE_SCOPE:
        raise ContractRefusal("fixture scope must deny execution and integrity evidence")
    if root["expected_terminal"] != SYNTHETIC_FIXTURE_TERMINAL:
        raise ContractRefusal("accepted fixture may be synthetic structural evidence only")
    _validate_bindings(root["bindings"])
    block_ids = expand_ordered_block_ids(root["block_universe"])
    if root["arms"] != list(ARMS):
        raise ContractRefusal("arm labels must equal the exact canonical four-arm sequence")
    ledger = _object(root["call_ledger"], {"calls_per_block", "total_generation_calls", "grammar", "expanded_sha256"}, "call_ledger")
    if ledger["calls_per_block"] != CALLS_PER_BLOCK or ledger["total_generation_calls"] != TOTAL_GENERATION_CALLS or ledger["grammar"] != list(CALL_GRAMMAR):
        raise ContractRefusal("nine-call-per-block grammar or 2,700-call total drifted")
    expanded = expand_call_ledger(block_ids)
    if ledger["expanded_sha256"] != canonical_sha256(list(expanded)):
        raise ContractRefusal("expanded 2,700-call ledger digest mismatch")
    _validate_hash_bundle(root["commitments"], ("task_sha256", "probe_sha256", "placebo_sha256", "evaluator_sha256"), "commitments")
    _validate_chronology(root["chronology"])
    _validate_assignment(root["assignment"], block_ids)
    _validate_w0(root["w0"])
    _validate_permit(root["permit"])
    _validate_hash_bundle(root["input_hashes"], ("trajectory_request_sha256", "trajectory_response_sha256", "proposal_request_sha256", "proposal_response_sha256", "probe_request_sha256", "probe_response_sha256", "evaluator_input_sha256", "evaluator_output_sha256"), "input_hashes")
    flags = _object(root["forbidden_input_flags"], {"arms_hidden_from_model", "clone_ids_hidden_from_model", "outcome_hidden_from_sham", "probe_hidden_from_proposals", "network_denied", "undeclared_files_denied", "cache_denied", "cross_session_denied"}, "forbidden_input_flags")
    if any(value is not True for value in flags.values()):
        raise ContractRefusal("every forbidden-input flag must be true")
    blind = _object(root["blind_evaluator"], {"arm_hidden", "clone_hidden", "order_hidden", "score_sha256"}, "blind_evaluator")
    if blind["arm_hidden"] is not True or blind["clone_hidden"] is not True or blind["order_hidden"] is not True:
        raise ContractRefusal("evaluator blindness failed")
    _sha(blind["score_sha256"], "blind_evaluator.score_sha256")
    analysis = _object(root["analysis"], {"expected_block_ids_sha256", "analysis_input_sha256", "analysis_output_sha256"}, "analysis")
    if analysis["expected_block_ids_sha256"] != root["block_universe"]["ordered_ids_sha256"]:
        raise ContractRefusal("analysis expected block universe does not bind vector universe")
    _validate_hash_bundle(analysis, ("expected_block_ids_sha256", "analysis_input_sha256", "analysis_output_sha256"), "analysis")
    return {
        "analysis_expected_block_ids": list(block_ids),
        "analysis_expected_block_ids_sha256": analysis["expected_block_ids_sha256"],
        "case_id": root["case_id"],
        "expanded_call_count": len(expanded),
        "expanded_call_ledger_sha256": ledger["expanded_sha256"],
        "fixture_scope": STRUCTURAL_FIXTURE_SCOPE,
        "integrity_status": SYNTHETIC_FIXTURE_TERMINAL,
        "actual_per_block_evidence_validated": False,
        "scientific_terminal_issued": False,
    }
