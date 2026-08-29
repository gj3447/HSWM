"""Fail-closed DNRD-5 Q0 response-reproducibility qualification contract.

This is deliberately a qualification-only instrument.  It has no occurrence
block identifier, no 300-block population access, and no dispatch function.
It can freeze and verify the *shape* of a finite reproducibility probe before
Source A, but cannot turn its records into occurrence or causal evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    parse_canonical,
)
from _research.dnrd5.provider_gateway import CALL_CLASSES

Q0_SCHEMA = "hswm-dnrd5-q0-response-reproducibility/v1"
Q_START_MARKER_SCHEMA = "hswm-dnrd5-q-start-marker/v1"
Q_NAMESPACE = "DNRD5-Q-QUALIFICATION-ONLY/v1"
REPRODUCED = "REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY"
FALSIFIED = "FALSIFIED_RESPONSE_REPRODUCIBILITY_ON_FROZEN_QUALIFICATION_CORPUS"
INCONCLUSIVE = "INCONCLUSIVE_QUALIFICATION_EVIDENCE"
NONCLAIMS = (
    "NOT_A_DNRD5_300_BLOCK_OCCURRENCE_CALL_OR_PILOT_EFFECT_DATA",
    "NOT_PROOF_OF_PROVIDER_KERNEL_CACHE_SCHEDULING_OR_GLOBAL_DETERMINISM",
    "NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING",
    "NOT_FULL_RAW_ENVELOPE_USAGE_HEADER_OR_TIMING_REPRODUCIBILITY",
    "NOT_DEMONSTRATED_PRODUCTION_SHAPE_OR_SOURCE_A_QUALIFICATION",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")
_CASE = re.compile(r"^QCASE-[0-9]{3}$")
_ATTEMPT = re.compile(r"^DNRD5-Q-[0-9]{3}-R[0-9]{3}$")


class Q0QualificationRefusal(ValueError):
    """A Q0 plan, marker, or evidence sequence is not safely qualifiable."""


def _refuse(detail: str) -> None:
    raise Q0QualificationRefusal(detail)


def _object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _refuse(f"{label} key set drifted")
    return value


def _sha(value: Any, label: str, *, nonzero: bool = False) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _refuse(f"{label} must be lowercase SHA-256")
    if nonzero and value == "0" * 64:
        _refuse(f"{label} cannot be a placeholder")
    return value


def _canonical(raw: bytes, label: str) -> Mapping[str, Any]:
    if type(raw) is not bytes:
        _refuse(f"{label} must be exact bytes")
    try:
        value = parse_canonical(raw)
    except CanonicalJsonError as error:
        _refuse(f"{label} is not canonical-json/v1: {error}")
    if type(value) is not dict:
        _refuse(f"{label} must be an object")
    return value


def _source(value: Any, label: str) -> Mapping[str, Any]:
    source = _object(
        value, {"commit", "tree", "ci_receipt_sha256", "ci_terminal"}, label
    )
    if (
        type(source["commit"]) is not str
        or _GIT.fullmatch(source["commit"]) is None
        or source["commit"] == "0" * 40
    ):
        _refuse(f"{label}.commit must be a non-placeholder Git SHA-1")
    if (
        type(source["tree"]) is not str
        or _GIT.fullmatch(source["tree"]) is None
        or source["tree"] == "0" * 40
    ):
        _refuse(f"{label}.tree must be a non-placeholder Git SHA-1")
    _sha(source["ci_receipt_sha256"], f"{label}.ci_receipt_sha256", nonzero=True)
    if source["ci_terminal"] != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD":
        _refuse(f"{label}.ci_terminal must bind the first successful CI build")
    return source


def _derive_call_order(attempts: Sequence[str], seed: bytes) -> list[str]:
    """Domain-separated SHA-256 Fisher--Yates; copied by the independent judge."""
    ordered = list(attempts)
    counter = 0
    for index in range(len(ordered) - 1, 0, -1):
        stream = b""
        while len(stream) < 8:
            stream += sha256(
                b"HSWM-DNRD5-Q0-CALL-ORDER-V1\0" + seed + counter.to_bytes(8, "big")
            ).digest()
            counter += 1
        swap = int.from_bytes(stream[:8], "big") % (index + 1)
        ordered[index], ordered[swap] = ordered[swap], ordered[index]
    return ordered


def validate_q0_plan(raw: bytes) -> dict[str, Any]:
    """Validate immutable Q0 bytes; rejects Source-A/occurrence-shaped plans."""
    plan = _canonical(raw, "Q0")
    root = _object(
        plan,
        {
            "schema_version",
            "namespace",
            "source",
            "gateway_version",
            "corpus_manifest_sha256",
            "corpus",
            "replicates",
            "comparator",
            "call_order",
            "call_order_algorithm",
            "call_order_seed_hex",
            "call_order_seed_sha256",
            "budget",
            "zero_retry",
            "identities",
            "verifier",
            "evidence_root_genesis_sha256",
            "allowed_terminals",
            "nonclaims",
        },
        "Q0",
    )
    if root["schema_version"] != Q0_SCHEMA or root["namespace"] != Q_NAMESPACE:
        _refuse("Q0 schema or qualification-only namespace drifted")
    _source(root["source"], "Q0.source")
    if root["gateway_version"] != "hswm-dnrd5-q-provider-gateway/v1":
        _refuse("Q0 gateway version drifted")
    _sha(root["corpus_manifest_sha256"], "Q0 corpus manifest", nonzero=True)
    corpus = root["corpus"]
    if type(corpus) is not list or not 3 <= len(corpus) <= 256:
        _refuse("Q0 corpus must be a bounded nontrivial finite list")
    case_ids: list[str] = []
    classes: set[str] = set()
    for item in corpus:
        case = _object(
            item,
            {
                "case_id",
                "call_class",
                "request_sha256",
                "instruction_sha256",
                "model_input_sha256",
                "response_schema_sha256",
                "rng_sha256",
                "max_output_tokens",
            },
            "Q0 corpus case",
        )
        if type(case["case_id"]) is not str or _CASE.fullmatch(case["case_id"]) is None:
            _refuse("Q0 corpus case id drifted")
        case_ids.append(case["case_id"])
        if case["call_class"] not in CALL_CLASSES:
            _refuse("Q0 corpus call class drifted")
        classes.add(case["call_class"])
        for key in (
            "request_sha256",
            "instruction_sha256",
            "model_input_sha256",
            "response_schema_sha256",
            "rng_sha256",
        ):
            _sha(case[key], f"Q0 corpus {key}", nonzero=True)
        if type(case["max_output_tokens"]) is not int or case[
            "max_output_tokens"
        ] not in {64, 128, 256}:
            _refuse("Q0 corpus max_output_tokens must be one of the frozen values")
    if len(case_ids) != len(set(case_ids)) or classes != set(CALL_CLASSES):
        _refuse("Q0 corpus must uniquely cover all three gateway call classes")
    if type(root["replicates"]) is not int or not 2 <= root["replicates"] <= 32:
        _refuse("Q0 replicates must be fixed in [2,32]")
    if (
        root["comparator"]
        != "EXACT_REQUEST_RUNTIME_RNG_AND_MODEL_CONTENT_UTF8_STRUCTURED_EQUALITY"
    ):
        _refuse(
            "Q0 comparator must bind request/runtime/RNG and exact model-content bytes/structure"
        )
    expected_attempts = [
        f"DNRD5-Q-{case_id[-3:]}-R{replicate:03d}"
        for case_id in case_ids
        for replicate in range(1, root["replicates"] + 1)
    ]
    if (
        type(root["call_order"]) is not list
        or len(root["call_order"]) != len(expected_attempts)
        or set(root["call_order"]) != set(expected_attempts)
    ):
        _refuse("Q0 call order must be one frozen complete permutation")
    if root["call_order_algorithm"] != "FROZEN_SHA256_FISHER_YATES_V1":
        _refuse("Q0 randomized call-order algorithm drifted")
    if (
        type(root["call_order_seed_hex"]) is not str
        or _SHA.fullmatch(root["call_order_seed_hex"]) is None
    ):
        _refuse("Q0 call-order seed must be 32 lowercase hex bytes")
    _sha(root["call_order_seed_sha256"], "Q0 call-order seed", nonzero=True)
    seed = bytes.fromhex(root["call_order_seed_hex"])
    if sha256(seed).hexdigest() != root["call_order_seed_sha256"] or root[
        "call_order"
    ] != _derive_call_order(expected_attempts, seed):
        _refuse("Q0 call order is not the exact seeded Fisher-Yates permutation")
    if root["budget"] != len(expected_attempts) or root["zero_retry"] is not True:
        _refuse("Q0 budget or zero-retry contract drifted")
    identities = _object(
        root["identities"],
        {
            "endpoint_sha256",
            "model_identity_sha256",
            "runtime_identity_sha256",
            "tls_identity_sha256",
            "isolation_identity_sha256",
        },
        "Q0 identities",
    )
    for key, value in identities.items():
        _sha(value, f"Q0 identities.{key}", nonzero=True)
    verifier = _object(
        root["verifier"], {"source", "build_output_sha256"}, "Q0 verifier"
    )
    _source(verifier["source"], "Q0 verifier.source")
    _sha(
        verifier["build_output_sha256"], "Q0 verifier.build_output_sha256", nonzero=True
    )
    _sha(root["evidence_root_genesis_sha256"], "Q0 evidence root genesis", nonzero=True)
    if root["allowed_terminals"] != [REPRODUCED, FALSIFIED, INCONCLUSIVE]:
        _refuse("Q0 terminal set drifted")
    if tuple(root["nonclaims"]) != NONCLAIMS:
        _refuse("Q0 nonclaims drifted")
    return dict(root)


def validate_q_start_marker(raw: bytes, q0_raw: bytes) -> dict[str, Any]:
    """Bind Q0 before a separate qualification gateway can be started."""
    validate_q0_plan(q0_raw)
    marker = _canonical(raw, "Q_START_MARKER")
    root = _object(
        marker,
        {
            "schema_version",
            "namespace",
            "q0_sha256",
            "evidence_root_genesis_sha256",
            "terminal",
            "nonclaims",
        },
        "Q_START_MARKER",
    )
    if (
        root["schema_version"] != Q_START_MARKER_SCHEMA
        or root["namespace"] != Q_NAMESPACE
    ):
        _refuse("Q_START_MARKER schema or namespace drifted")
    if root["q0_sha256"] != sha256(q0_raw).hexdigest():
        _refuse("Q_START_MARKER does not bind exact Q0 bytes")
    plan = parse_canonical(q0_raw)
    if root["evidence_root_genesis_sha256"] != plan["evidence_root_genesis_sha256"]:
        _refuse("Q_START_MARKER evidence-root genesis drifted")
    if (
        root["terminal"]
        != "Q_START_MARKER_BOUND_BEFORE_ANY_QUALIFICATION_GATEWAY_START"
    ):
        _refuse("Q_START_MARKER terminal drifted")
    if tuple(root["nonclaims"]) != NONCLAIMS:
        _refuse("Q_START_MARKER nonclaims drifted")
    return dict(root)


def q0_plan_sha256(raw: bytes) -> str:
    validate_q0_plan(raw)
    return sha256(raw).hexdigest()


def make_q_start_marker(q0_raw: bytes) -> bytes:
    """Create canonical marker bytes; publishing/durability remains external."""
    plan = validate_q0_plan(q0_raw)
    return canonical_bytes(
        {
            "schema_version": Q_START_MARKER_SCHEMA,
            "namespace": Q_NAMESPACE,
            "q0_sha256": sha256(q0_raw).hexdigest(),
            "evidence_root_genesis_sha256": plan["evidence_root_genesis_sha256"],
            "terminal": "Q_START_MARKER_BOUND_BEFORE_ANY_QUALIFICATION_GATEWAY_START",
            "nonclaims": list(NONCLAIMS),
        }
    )


__all__ = [
    "FALSIFIED",
    "INCONCLUSIVE",
    "NONCLAIMS",
    "Q0_SCHEMA",
    "Q_NAMESPACE",
    "Q_START_MARKER_SCHEMA",
    "REPRODUCED",
    "Q0QualificationRefusal",
    "make_q_start_marker",
    "q0_plan_sha256",
    "validate_q0_plan",
    "validate_q_start_marker",
]
