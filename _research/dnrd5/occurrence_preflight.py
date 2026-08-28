"""Pure DNRD-5 Source-A and pre-marker occurrence-preflight contracts.

This module parses caller-supplied canonical bytes only.  It performs no I/O,
does not dispatch a provider call, and never establishes Git, CI, TLS, trusted
time, global nonce uniqueness, or external-authority facts.
"""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any, Mapping

from _research.dnrd5 import independent_randomization, randomization
from _research.dnrd5.canonical_json import CanonicalJsonError, canonical_bytes, canonical_sha256, parse_canonical


SOURCE_A_SCHEMA = "hswm-dnrd5-source-a-instrument-binding/v1"
PREMARKER_SCHEMA = "hswm-dnrd5-occurrence-premarker/v1"
SOURCE_A_SUCCESS = "SOURCE_A_INSTRUMENT_QUALIFIED_FUTURE_OCCURRENCE_EVIDENCE_REQUIRED"
SOURCE_A_REFUSAL = "SOURCE_A_STRUCTURAL_BINDING_REFUSAL_CALLER_DESCRIPTORS_ONLY"
PREMARKER_SUCCESS = "PREMARKER_VALIDATED_PENDING_ATOMIC_OCCURRENCE_MARKER"
PREMARKER_REFUSAL = "PREMARKER_STRUCTURAL_BINDING_REFUSAL_CALLER_DESCRIPTORS_ONLY"
NONCLAIM = (
    "PURE_PARSER_ONLY_NOT_GIT_CI_TLS_TRUSTED_TIME_GLOBAL_UNIQUENESS_"
    "CURRENTNESS_PROVIDER_DISPATCH_OR_OCCURRENCE_ATTESTATION"
)
FROZEN_RETAINED_ASSUMPTIONS = (
    "beacon_uniformity_and_prf_law_are_assumptions",
    "deterministic_potential_outcomes_are_not_proved_by_finite_replay",
    "clone_exchangeability_consistency_and_no_interference_are_assumptions",
    "evaluator_validity_and_blindness_require_occurrence_evidence",
    "normal_lcb_requires_separate_block_cluster_assumptions",
    "placebo_theta_u_given_complete_h_one_quarter_law_is_conditional_assumption",
    "custody_and_chronology_are_not_proved_by_caller_descriptors",
)
PLAN_MEDIA_TYPE = "application/vnd.hswm.dnrd5.randomization-plan-v1+json"
PLAN_ENCODING = randomization.CANONICAL_JSON_ENCODING
PLAN_BLOB_TRANSPORT = "CONTENT_ADDRESSED_BLOB_OUTSIDE_BOUNDED_CANONICAL_JSON_V1"
PLAN_MAX_BLOB_BYTES = 2_000_000
PLAN_JSON_KAT_MEDIA_TYPE = "application/vnd.hswm.dnrd5.plan-json-kat-v1+json"
PLAN_JSON_KAT_SHA256 = "012dcc2ebf71dd6b54dfceec9aeeb72673961c64830694ab7bb7c678deb6051f"
PLAN_JSON_KAT_BYTE_LENGTH = 3_618
PLAN_CROSS_LANGUAGE_STATUS = (
    "THREE_CODEC_IMPLEMENTATIONS_SHARED_KAT_AND_FULL_INDEPENDENT_TYPESCRIPT_"
    "300_BLOCK_2700_SLOT_REDERIVATION_SUPPORTED_NOT_SOURCE_BUILD_OR_EVIDENCE_"
    "SCHEMA_BOUND_NOT_SOURCE_FREEZE_NOT_OCCURRENCE_NOT_EFFICACY_NOT_SCIENTIFIC_RESULT"
)
ROOT_SCHEMA = "hswm-dnrd5-future-occurrence-root/v1"
ROOT_MEDIA_TYPE = "application/vnd.hswm.dnrd5.future-occurrence-root-v1+json"
ROOT_IDENTITY_BYTE_LENGTH = 510
HISTORICAL_R2_COMMIT = "7ff9454e3f274183bdd9c1465ad68b0ef91cb8ec"
HISTORICAL_R2_SHA256 = "660f97baefe5dbb46a3a5764255b1bbebca2baf72a4623e28ab2342c3196533a"
EXACTNESS_AMENDMENT_SHA256 = "a012a1d1ce35ffa56d2f6418fa9ac26010c385649f21d4237adda1f1f6e88b5d"
SOURCE_A_STRUCTURAL = "SOURCE_A_STRUCTURAL_BINDING_VALIDATED_CALLER_DESCRIPTORS_ONLY"
PREMARKER_STRUCTURAL = "PREMARKER_STRUCTURAL_BINDING_VALIDATED_CALLER_DESCRIPTORS_ONLY"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")


class OccurrencePreflightRefusal(ValueError):
    """Typed fail-closed source-A or pre-marker refusal."""

    def __init__(self, terminal: str, detail: str) -> None:
        super().__init__(f"{terminal}: {detail}")
        self.terminal = terminal
        self.detail = detail
        self.dispatch_authorized = False
        self.dispatch_budget = 0
        self.source_freeze_eligible = False


def _refuse(terminal: str, detail: str) -> None:
    raise OccurrencePreflightRefusal(terminal, detail)


def _canonical_object(raw: bytes, terminal: str, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        _refuse(terminal, f"{label} must be bytes")
    try:
        value = parse_canonical(raw)
    except CanonicalJsonError as error:
        _refuse(terminal, f"{label} is not exact canonical-json/v1: {error}")
    if type(value) is not dict:
        _refuse(terminal, f"{label} root must be an object")
    return value


def _object(value: Any, keys: set[str], terminal: str, label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _refuse(terminal, f"{label} key set drifted")
    return value


def _sha(value: Any, terminal: str, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _refuse(terminal, f"{label} must be lowercase SHA-256")
    return value


def _git(value: Any, terminal: str, label: str) -> str:
    if type(value) is not str or _GIT.fullmatch(value) is None:
        _refuse(terminal, f"{label} must be lowercase Git SHA-1")
    return value


def _descriptor(value: Any, terminal: str, label: str) -> Mapping[str, Any]:
    record = _object(value, {"media_type", "sha256", "byte_length"}, terminal, label)
    if type(record["media_type"]) is not str or not record["media_type"]:
        _refuse(terminal, f"{label}.media_type is invalid")
    _sha(record["sha256"], terminal, f"{label}.sha256")
    if type(record["byte_length"]) is not int or record["byte_length"] < 0:
        _refuse(terminal, f"{label}.byte_length is invalid")
    return record


def _source(value: Any, terminal: str, label: str) -> Mapping[str, Any]:
    record = _object(value, {"commit", "tree", "ci_receipt_sha256"}, terminal, label)
    _git(record["commit"], terminal, f"{label}.commit")
    _git(record["tree"], terminal, f"{label}.tree")
    _sha(record["ci_receipt_sha256"], terminal, f"{label}.ci_receipt_sha256")
    return record


def _same(left: Mapping[str, Any], right: Mapping[str, Any], terminal: str, label: str) -> None:
    if canonical_bytes(left) != canonical_bytes(right):
        _refuse(terminal, f"{label} drifted")


def _future_root_descriptor(
    source_a_binding_sha256: str,
    source_b_sha256: str,
    beacon_receipt_sha256: str,
    future_randomness_hex: str,
    study_binding_sha256: str,
) -> dict[str, Any]:
    content = {
        "schema_version": ROOT_SCHEMA,
        "source_a_binding_sha256": source_a_binding_sha256,
        "source_b_sha256": source_b_sha256,
        "beacon_receipt_sha256": beacon_receipt_sha256,
        "future_randomness_sha256": sha256(bytes.fromhex(future_randomness_hex)).hexdigest(),
        "study_binding_sha256": study_binding_sha256,
    }
    raw = canonical_bytes(content)
    return {"media_type": ROOT_MEDIA_TYPE, "sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}


def validate_source_a_instrument_binding(raw: bytes) -> dict[str, Any]:
    """Validate a caller's Source-A binding structure without qualifying it."""
    terminal = SOURCE_A_REFUSAL
    value = _canonical_object(raw, terminal, "source_a")
    keys = {
        "schema_version", "historical_r2", "exactness_amendment_sha256", "q0", "q_closure",
        "qualification_decisions", "source", "verifier", "source_b_preregistration_contract", "beacon_receipt_contract", "beacon_selection_contract", "study_binding_sha256",
        "block_universe", "canonical_json", "plan_descriptor_contract", "root_identity_contract", "expected_occurrence_descriptors",
        "retained_assumptions", "terminal", "nonclaim",
    }
    root = _object(value, keys, terminal, "source_a")
    if root["schema_version"] != SOURCE_A_SCHEMA or root["terminal"] != SOURCE_A_SUCCESS or root["nonclaim"] != NONCLAIM:
        _refuse(terminal, "source_a schema, success terminal, or nonclaim drifted")
    historical = _object(root["historical_r2"], {"commit", "file_sha256"}, terminal, "historical_r2")
    _git(historical["commit"], terminal, "historical_r2.commit")
    _sha(historical["file_sha256"], terminal, "historical_r2.file_sha256")
    if historical["commit"] != HISTORICAL_R2_COMMIT or historical["file_sha256"] != HISTORICAL_R2_SHA256 or root["exactness_amendment_sha256"] != EXACTNESS_AMENDMENT_SHA256:
        _refuse(terminal, "historical R2 or exactness amendment identity drifted")
    q0 = _object(root["q0"], {"protocol_sha256", "source", "start_marker_sha256"}, terminal, "q0")
    _sha(q0["protocol_sha256"], terminal, "q0.protocol_sha256")
    _source(q0["source"], terminal, "q0.source")
    _sha(q0["start_marker_sha256"], terminal, "q0.start_marker_sha256")
    closure = _object(root["q_closure"], {"evidence_root_sha256", "closure_sha256", "q0_sha256", "terminal"}, terminal, "q_closure")
    _sha(closure["evidence_root_sha256"], terminal, "q_closure.evidence_root_sha256")
    _sha(closure["closure_sha256"], terminal, "q_closure.closure_sha256")
    if closure["q0_sha256"] != canonical_sha256(q0):
        _refuse(terminal, "q_closure Q0 binding drifted")
    if closure["terminal"] != "REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY":
        _refuse(terminal, "q_closure terminal drifted")
    decisions = _object(root["qualification_decisions"], {"exactness", "lcb"}, terminal, "qualification_decisions")
    if decisions["exactness"] != "SUPPORTED_NOT_PROVED" or decisions["lcb"] != "SUPPORTED_NOT_PROVED":
        _refuse(terminal, "qualification decisions must remain support-not-proof")
    _source(root["source"], terminal, "source")
    verifier = _object(root["verifier"], {"source", "build_output_sha256", "import_graph_sha256", "corpus_sha256", "actual_byte_schema_sha256"}, terminal, "verifier")
    _source(verifier["source"], terminal, "verifier.source")
    for key in ("build_output_sha256", "import_graph_sha256", "corpus_sha256", "actual_byte_schema_sha256"):
        _sha(verifier[key], terminal, f"verifier.{key}")
    _descriptor(root["source_b_preregistration_contract"], terminal, "source_b_preregistration_contract")
    _descriptor(root["beacon_receipt_contract"], terminal, "beacon_receipt_contract")
    _descriptor(root["beacon_selection_contract"], terminal, "beacon_selection_contract")
    _sha(root["study_binding_sha256"], terminal, "study_binding_sha256")
    universe = _object(root["block_universe"], {"first", "last", "count", "ordered_ids_sha256", "calls_per_block", "total_calls", "arms"}, terminal, "block_universe")
    if (universe["first"], universe["last"], universe["count"], universe["calls_per_block"], universe["total_calls"], universe["arms"]) != ("DNRD5-BLOCK-0001", "DNRD5-BLOCK-0300", 300, 9, 2700, list(randomization.ARMS)):
        _refuse(terminal, "block universe or four-arm 2,700-call contract drifted")
    _sha(universe["ordered_ids_sha256"], terminal, "block_universe.ordered_ids_sha256")
    if universe["ordered_ids_sha256"] != canonical_sha256(list(randomization.expected_block_ids())):
        _refuse(terminal, "block_universe ordered IDs digest drifted")
    canonical = _object(root["canonical_json"], {"contract_version", "corpus_sha256"}, terminal, "canonical_json")
    if canonical["contract_version"] != "hswm-canonical-json/v1":
        _refuse(terminal, "canonical_json contract drifted")
    _sha(canonical["corpus_sha256"], terminal, "canonical_json.corpus_sha256")
    plan_contract = _object(root["plan_descriptor_contract"], {"media_type", "producer_schema", "independent_schema", "encoding", "codec_contract_version", "codec_kat_media_type", "codec_kat_sha256", "codec_kat_byte_length", "blob_transport", "max_blob_bytes", "cross_language_status"}, terminal, "plan_descriptor_contract")
    if (
        independent_randomization.CANONICAL_JSON_ENCODING != PLAN_ENCODING
        or plan_contract
        != {"media_type": PLAN_MEDIA_TYPE, "producer_schema": randomization.SCHEMA_VERSION, "independent_schema": independent_randomization.SCHEMA_VERSION, "encoding": PLAN_ENCODING, "codec_contract_version": PLAN_ENCODING, "codec_kat_media_type": PLAN_JSON_KAT_MEDIA_TYPE, "codec_kat_sha256": PLAN_JSON_KAT_SHA256, "codec_kat_byte_length": PLAN_JSON_KAT_BYTE_LENGTH, "blob_transport": PLAN_BLOB_TRANSPORT, "max_blob_bytes": PLAN_MAX_BLOB_BYTES, "cross_language_status": PLAN_CROSS_LANGUAGE_STATUS}
    ):
        _refuse(terminal, "plan descriptor contract drifted")
    root_contract = _object(root["root_identity_contract"], {"schema_version", "media_type", "byte_length"}, terminal, "root_identity_contract")
    if root_contract != {"schema_version": ROOT_SCHEMA, "media_type": ROOT_MEDIA_TYPE, "byte_length": ROOT_IDENTITY_BYTE_LENGTH}:
        _refuse(terminal, "root identity contract drifted")
    expected = _object(root["expected_occurrence_descriptors"], {"build", "runtime", "no_prior_dispatch"}, terminal, "expected_occurrence_descriptors")
    for key in expected:
        _descriptor(expected[key], terminal, f"expected_occurrence_descriptors.{key}")
    if root["retained_assumptions"] != list(FROZEN_RETAINED_ASSUMPTIONS):
        _refuse(terminal, "retained_assumptions must equal the frozen assumption profile")
    return {"terminal": SOURCE_A_STRUCTURAL, "claimed_terminal": SOURCE_A_SUCCESS, "dispatch_authorized": False, "dispatch_budget": 0, "source_freeze_eligible": False, "source_a_sha256": canonical_sha256(value), "nonclaim": NONCLAIM}


def validate_occurrence_premarker(source_a_raw: bytes, raw: bytes, producer_plan_raw: bytes, independent_plan_raw: bytes) -> dict[str, Any]:
    """Validate structural Phase-B bindings and rebuilt logical plans only."""
    source_a = validate_source_a_instrument_binding(source_a_raw)
    terminal = PREMARKER_REFUSAL
    value = _canonical_object(raw, terminal, "premarker")
    keys = {"schema_version", "source_a_binding_sha256", "source_b", "beacon", "actual_occurrence_descriptors", "producer_plan", "independent_plan", "terminal", "nonclaim"}
    root = _object(value, keys, terminal, "premarker")
    if root["schema_version"] != PREMARKER_SCHEMA or root["terminal"] != PREMARKER_SUCCESS or root["nonclaim"] != NONCLAIM:
        _refuse(terminal, "premarker schema, terminal, or nonclaim drifted")
    if root["source_a_binding_sha256"] != source_a["source_a_sha256"]:
        _refuse(terminal, "source_a byte binding mismatch")
    source_a_value = _canonical_object(source_a_raw, SOURCE_A_REFUSAL, "source_a")
    source_b = _object(root["source_b"], {"source", "source_a_binding_sha256", "preregistration_sha256", "preregistration_contract"}, terminal, "source_b")
    _source(source_b["source"], terminal, "source_b.source")
    if source_b["source_a_binding_sha256"] != source_a["source_a_sha256"]:
        _refuse(terminal, "Source-B does not bind exact Source-A bytes")
    _sha(source_b["preregistration_sha256"], terminal, "source_b.preregistration_sha256")
    _same(_descriptor(source_b["preregistration_contract"], terminal, "source_b.preregistration_contract"), source_a_value["source_b_preregistration_contract"], terminal, "Source-B preregistration contract")
    beacon = _object(root["beacon"], {"receipt_sha256", "future_randomness_hex", "study_binding_sha256", "source_b_sha256", "receipt_contract", "selection_contract", "caller_claimed_selected_after_source_b"}, terminal, "beacon")
    _sha(beacon["receipt_sha256"], terminal, "beacon.receipt_sha256")
    if type(beacon["future_randomness_hex"]) is not str or _SHA.fullmatch(beacon["future_randomness_hex"]) is None:
        _refuse(terminal, "beacon future randomness must be 32 lowercase hex bytes")
    if beacon["study_binding_sha256"] != source_a_value["study_binding_sha256"]:
        _refuse(terminal, "beacon study binding mismatch")
    _same(_descriptor(beacon["receipt_contract"], terminal, "beacon.receipt_contract"), source_a_value["beacon_receipt_contract"], terminal, "beacon receipt contract")
    _same(_descriptor(beacon["selection_contract"], terminal, "beacon.selection_contract"), source_a_value["beacon_selection_contract"], terminal, "beacon selection contract")
    if beacon["source_b_sha256"] != canonical_sha256(source_b) or beacon["caller_claimed_selected_after_source_b"] is not True:
        _refuse(terminal, "beacon/source-B chronology descriptor mismatch")
    actual = _object(root["actual_occurrence_descriptors"], {"build", "runtime", "root", "no_prior_dispatch"}, terminal, "actual_occurrence_descriptors")
    expected = source_a_value["expected_occurrence_descriptors"]
    for key in ("build", "runtime", "no_prior_dispatch"):
        checked = _descriptor(actual[key], terminal, f"actual_occurrence_descriptors.{key}")
        _same(checked, expected[key], terminal, f"actual {key} descriptor is not Source-A-bound")
    root_descriptor = _descriptor(actual["root"], terminal, "actual_occurrence_descriptors.root")
    derived_root = _future_root_descriptor(source_a["source_a_sha256"], beacon["source_b_sha256"], beacon["receipt_sha256"], beacon["future_randomness_hex"], beacon["study_binding_sha256"])
    if canonical_bytes(root_descriptor) != canonical_bytes(derived_root):
        _refuse(terminal, "actual root is not future-derived from Source-A and beacon")
    plan_contract = source_a_value["plan_descriptor_contract"]
    producer_descriptor = _descriptor(root["producer_plan"], terminal, "producer_plan")
    independent_descriptor = _descriptor(root["independent_plan"], terminal, "independent_plan")
    if type(producer_plan_raw) is not bytes or type(independent_plan_raw) is not bytes:
        _refuse(terminal, "legacy plan blobs must be bytes")
    if len(producer_plan_raw) > PLAN_MAX_BLOB_BYTES or len(independent_plan_raw) > PLAN_MAX_BLOB_BYTES:
        _refuse(terminal, "legacy plan blob exceeds frozen maximum")
    try:
        producer = randomization.derive_study_plan(future_randomness_hex=beacon["future_randomness_hex"], study_binding_sha256=beacon["study_binding_sha256"])
        independent = independent_randomization.derive_study_plan(future_randomness_hex=beacon["future_randomness_hex"], study_binding_sha256=beacon["study_binding_sha256"])
        producer_bytes = randomization.canonical_json_bytes(producer)
        independent_bytes = independent_randomization.canonical_json_bytes(independent)
    except Exception as error:
        _refuse(terminal, f"producer or independent 300-block plan refused: {error}")
    if producer_bytes != independent_bytes or producer_plan_raw != producer_bytes or independent_plan_raw != independent_bytes:
        _refuse(terminal, "producer and independent plans differ in declared legacy plan bytes")
    for descriptor, plan_bytes, label in ((producer_descriptor, producer_bytes, "producer_plan"), (independent_descriptor, independent_bytes, "independent_plan")):
        if descriptor["media_type"] != plan_contract["media_type"] or descriptor["byte_length"] != len(plan_bytes) or descriptor["sha256"] != sha256(plan_bytes).hexdigest():
            _refuse(terminal, f"{label} descriptor does not bind exact derived plan bytes")
    return {"terminal": PREMARKER_STRUCTURAL, "claimed_terminal": PREMARKER_SUCCESS, "dispatch_authorized": False, "dispatch_budget": 0, "source_freeze_eligible": False, "source_a_sha256": source_a["source_a_sha256"], "preflight_sha256": canonical_sha256(value), "nonclaim": NONCLAIM}
