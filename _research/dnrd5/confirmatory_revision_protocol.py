"""Fail-closed readiness gate for a real DNRD-5 revision occurrence.

This is deliberately *not* a runner, an evaluator, a Permit issuer, or an
analysis module.  It validates the pre-outcome commitments that an independent
producer and an independent judge must possess before a 300-block occurrence
can begin.  In particular, passing this gate is not evidence that an outcome
is true, that people or services are independent, or that a revision improves
an LLM.  Those claims require the later sealed raw artifacts and a separately
operated evaluator/judge.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from _research.dnrd5.canonical_json import CanonicalJsonError, canonical_sha256, parse_canonical
from _research.dnrd5.randomization import ARMS, BLOCK_COUNT, CALLS_PER_BLOCK, TOTAL_CALLS


SCHEMA_VERSION = "hswm-dnrd5-confirmatory-revision-readiness/v1"
STATUS = "PRE_OUTCOME_READINESS_ONLY_NOT_EXECUTION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LLM_IMPROVEMENT"
REQUIRED_SEALS = (
    "STUDY_BINDING",
    "TASK_AND_PRIVATE_COMMITMENTS",
    "W0_AND_OPAQUE_FORKS",
    "FUTURE_RANDOMNESS_AND_ASSIGNMENT",
    "MODEL_RUNTIME_AND_DECODING",
    "INDEPENDENT_EVALUATOR_AND_JUDGE",
    "IMMUTABLE_EVIDENCE_DESTINATION",
)
REQUIRED_CONTROLS = (
    "OUTCOME_INDEPENDENT_SHAM",
    "DELAYED_NO_CREDIT",
    "EXACT_W0_ROLLBACK",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")


class ConfirmatoryProtocolRefusal(ValueError):
    """Raised when a proposed run lacks a pre-outcome causal safeguard."""


def _object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ConfirmatoryProtocolRefusal(f"{label} key set drifted")
    return value


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ConfirmatoryProtocolRefusal(f"{label} must be lowercase SHA-256")
    return value


def _git(value: Any, label: str) -> str:
    if type(value) is not str or _GIT.fullmatch(value) is None:
        raise ConfirmatoryProtocolRefusal(f"{label} must be lowercase Git SHA-1")
    return value


def _id(value: Any, label: str) -> str:
    if type(value) is not str or not value or len(value) > 256:
        raise ConfirmatoryProtocolRefusal(f"{label} must be a nonempty bounded identifier")
    return value


def _descriptor(value: Any, label: str) -> Mapping[str, Any]:
    descriptor = _object(value, {"sha256", "byte_length"}, label)
    _sha(descriptor["sha256"], f"{label}.sha256")
    if type(descriptor["byte_length"]) is not int or descriptor["byte_length"] < 1:
        raise ConfirmatoryProtocolRefusal(f"{label}.byte_length must be positive")
    return descriptor


def _principal_separation(value: Any) -> Mapping[str, Any]:
    roles = _object(
        value,
        {
            "transition_executor",
            "revision_proposer",
            "outcome_evaluator",
            "credit_adjudicator",
            "independent_judge",
            "permit_authorizer",
        },
        "principals",
    )
    parsed = {name: _id(principal, f"principals.{name}") for name, principal in roles.items()}
    # Role names are not proof of independence, but identity collapse defeats
    # the minimum owner/evaluator/adjudicator separation outright.
    if len(set(parsed.values())) != len(parsed):
        raise ConfirmatoryProtocolRefusal("required principal identities collapse")
    return parsed


def validate_confirmatory_readiness(raw: bytes) -> dict[str, Any]:
    """Validate a pre-outcome-only manifest and return a bounded projection.

    The manifest is intentionally small: it binds executable artifacts by
    descriptor rather than copying secrets, hidden answers, model weights, or
    private evaluator material into a public repository.
    """

    try:
        value = parse_canonical(raw)
    except CanonicalJsonError as error:
        raise ConfirmatoryProtocolRefusal("manifest must be exact canonical JSON") from error
    root = _object(
        value,
        {
            "schema_version", "status", "study_id", "study_binding", "source", "artifacts",
            "call_budget", "arms", "control_contract", "seals", "principals", "evaluator",
            "evidence_destination", "claim_ceiling",
        },
        "manifest",
    )
    if root["schema_version"] != SCHEMA_VERSION or root["status"] != STATUS:
        raise ConfirmatoryProtocolRefusal("manifest schema or bounded status drifted")
    _id(root["study_id"], "study_id")
    _sha(root["study_binding"], "study_binding")
    source = _object(root["source"], {"commit", "tree", "protocol_sha256"}, "source")
    _git(source["commit"], "source.commit")
    _git(source["tree"], "source.tree")
    _sha(source["protocol_sha256"], "source.protocol_sha256")

    artifacts = _object(
        root["artifacts"],
        {
            "task_generator", "probe_commitment", "placebo_commitment", "w0_forks",
            "assignment", "model_runtime", "decoding", "evaluator_program", "judge_program",
            "permit_policy", "analysis_program",
        },
        "artifacts",
    )
    for name, descriptor in artifacts.items():
        _descriptor(descriptor, f"artifacts.{name}")

    call_budget = _object(root["call_budget"], {"block_count", "calls_per_block", "total_calls", "retry"}, "call_budget")
    if (call_budget["block_count"], call_budget["calls_per_block"], call_budget["total_calls"]) != (BLOCK_COUNT, CALLS_PER_BLOCK, TOTAL_CALLS):
        raise ConfirmatoryProtocolRefusal("call budget must remain exactly 300 x 9 = 2700")
    if call_budget["retry"] != "FORBIDDEN_NO_REPLACEMENT_NO_RESUME":
        raise ConfirmatoryProtocolRefusal("retry/replacement/resume must be forbidden")
    if tuple(root["arms"]) != ARMS:
        raise ConfirmatoryProtocolRefusal("arms must be the exact randomized four-arm order")

    controls = _object(root["control_contract"], {"sham", "delayed", "rollback"}, "control_contract")
    if (controls["sham"], controls["delayed"], controls["rollback"]) != REQUIRED_CONTROLS:
        raise ConfirmatoryProtocolRefusal("control contract must retain sham, delayed-credit, and exact rollback")

    seals = root["seals"]
    if type(seals) is not list or tuple(seals) != REQUIRED_SEALS:
        raise ConfirmatoryProtocolRefusal("all required pre-outcome seals must be complete and ordered")
    principals = _principal_separation(root["principals"])
    evaluator = _object(
        root["evaluator"],
        {
            "blind_to", "hidden_answer_custody", "outcome_source", "judge_source",
            "post_seal_write_access", "independent_reimplementation_required",
        },
        "evaluator",
    )
    if tuple(evaluator["blind_to"]) != ("arm", "clone", "probe_order", "canonical_state", "feedback_source"):
        raise ConfirmatoryProtocolRefusal("evaluator blindness contract drifted")
    if evaluator["hidden_answer_custody"] != "SEPARATE_PRIVATE_CUSTODY_COMMITTED_PRE_OUTCOME":
        raise ConfirmatoryProtocolRefusal("hidden answer must be separately held and committed pre-outcome")
    if evaluator["outcome_source"] != "INDEPENDENT_EXECUTABLE_EVALUATOR":
        raise ConfirmatoryProtocolRefusal("outcome source must be an independently executable evaluator")
    if evaluator["judge_source"] != "INDEPENDENT_POST_SEAL_REIMPLEMENTATION":
        raise ConfirmatoryProtocolRefusal("judge must independently reimplement post-seal verification")
    if evaluator["post_seal_write_access"] is not False or evaluator["independent_reimplementation_required"] is not True:
        raise ConfirmatoryProtocolRefusal("evaluator/judge must not be able to alter sealed occurrence evidence")

    destination = _object(root["evidence_destination"], {"append_only", "immutable_raw_artifacts", "external_to_runner", "pre_outcome_seal_required"}, "evidence_destination")
    if any(destination[key] is not True for key in destination):
        raise ConfirmatoryProtocolRefusal("evidence destination must be external append-only immutable pre-outcome storage")
    ceiling = _object(root["claim_ceiling"], {"passing_readiness_establishes", "passing_readiness_does_not_establish"}, "claim_ceiling")
    if ceiling["passing_readiness_establishes"] != "STRUCTURAL_PRE_OUTCOME_ELIGIBILITY_ONLY":
        raise ConfirmatoryProtocolRefusal("readiness must retain structural-only ceiling")
    if ceiling["passing_readiness_does_not_establish"] != "EXECUTION_OUTCOME_TRUTH_CAUSAL_CREDIT_OR_LLM_BEHAVIOR_IMPROVEMENT":
        raise ConfirmatoryProtocolRefusal("readiness nonclaim drifted")

    # This digest makes the exact public declaration easy for a future runner
    # and separately built judge to bind, without treating it as a result.
    return {
        "schema_version": SCHEMA_VERSION,
        "study_id": root["study_id"],
        "manifest_sha256": canonical_sha256(value),
        "pre_outcome_seals": list(REQUIRED_SEALS),
        "block_count": BLOCK_COUNT,
        "total_calls": TOTAL_CALLS,
        "principal_ids": principals,
        "readiness_status": STATUS,
        "execution_occurred": False,
        "outcome_truth_established": False,
        "causal_credit_established": False,
        "llm_revision_improvement_established": False,
    }
