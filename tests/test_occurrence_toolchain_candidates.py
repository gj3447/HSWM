"""Integrity contract for discovery-only occurrence toolchain candidates."""

from __future__ import annotations

import json
from hashlib import sha256
import re
from pathlib import Path
from urllib.parse import urlparse


CANDIDATES_PATH = (
    Path(__file__).resolve().parents[1]
    / "_research/g0_occurrence/HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json"
)
QUALIFICATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "_research/g0_occurrence/HSWM_G0_EXTERNAL_AUDIT_QUALIFICATION.v1.json"
)

EXPECTED_SCHEMA_VERSION = "hswm-g0-occurrence-toolchain-candidates/v1"
EXPECTED_STATUS = "DISCOVERY_LOCK_ONLY_NOT_DOWNLOADED_NOT_QUALIFIED_NOT_EXECUTABLE_AUTHORITY"
REQUIRED_SOURCE_CANDIDATES = {
    "sigstore-cosign",
    "sigstore-rekor",
    "sigstore-timestamp-authority",
    "in-toto-golang",
    "openlineage",
    "ro-crate",
    "temporal-cli",
    "aws-cli",
    "openssl",
}
REQUIRED_SPECIFICATIONS = {
    "osf-api-v2",
    "dsse-v1",
    "in-toto-attestation-statement-v1",
    "rfc3161",
    "amazon-s3-object-lock",
    "temporal-workflow-id",
    "ro-crate-1.3",
    "openlineage-run-event-2-0-2",
}
CLAIM_CEILING_BLOCKERS = {
    "outcome truth",
    "CF-07",
    "G0",
    "G1",
    "Permit",
    "canonical admission",
    "causal credit",
    "learning evidence",
}


def _document() -> dict[str, object]:
    return json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))


def _is_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def test_candidate_document_is_explicitly_discovery_only() -> None:
    document = _document()

    assert document["schema_version"] == EXPECTED_SCHEMA_VERSION
    assert document["status"] == EXPECTED_STATUS
    assert document["selection_policy"] == {
        "published_standard_first": True,
        "official_implementation_first": True,
        "artifact_digest_required_before_execution": True,
        "license_bytes_required_before_execution": True,
        "external_credentials_and_control_domains_required": True,
        "drafts_cannot_promote": True,
    }


def test_published_specifications_are_unique_and_official_https_references() -> None:
    specifications = _document()["published_specifications"]
    assert isinstance(specifications, list)
    ids = [item["id"] for item in specifications]

    assert len(ids) == len(set(ids))
    assert REQUIRED_SPECIFICATIONS <= set(ids)
    assert all(_is_https_url(item["official_url"]) for item in specifications)


def test_source_candidates_are_unadopted_exact_source_discovery_records() -> None:
    candidates = _document()["official_source_candidates"]
    assert isinstance(candidates, list)
    ids = [item["id"] for item in candidates]

    assert len(ids) == len(set(ids))
    assert REQUIRED_SOURCE_CANDIDATES <= set(ids)
    for candidate in candidates:
        assert isinstance(candidate["version"], str) and candidate["version"]
        assert isinstance(candidate["license"], str) and candidate["license"]
        assert re.fullmatch(r"[0-9a-f]{40}", candidate["source_commit"])
        assert _is_https_url(candidate["repository"])
        assert _is_https_url(candidate["release_url"])
        assert candidate["artifact_integrity"] is None
        assert "ADOPTED" not in candidate["adoption_state"]


def test_claim_ceiling_and_external_blockers_remain_explicit() -> None:
    document = _document()
    boundary = document["claim_boundary"]
    assert isinstance(boundary, str)
    assert all(blocker in boundary for blocker in CLAIM_CEILING_BLOCKERS)

    blockers = document["external_blockers_at_observation_cut"]
    assert isinstance(blockers, list)
    assert len(blockers) == len(set(blockers))
    assert {
        "OSF_REGISTRATION_ACCOUNT_AND_IMMUTABLE_READBACK",
        "REKOR_INCLUSION_AND_SIGNED_ENTRY_VERIFICATION",
        "RFC3161_TSA_TRUST_ROOT_NONCE_AND_VERIFIED_TOKEN",
        "SEPARATE_ACCOUNT_WORM_COMPLIANCE_BUCKET_WITH_CONDITIONAL_CREATE_POLICY",
        "PRODUCTION_TEMPORAL_NAMESPACE_SERVER_SIGNAL_AUTHORIZATION_AND_COMPLETE_HISTORY_EXPORT",
        "INDEPENDENT_OUTCOME_CUSTODIAN_ACCOUNT_KEY_AND_ENDPOINT",
        "INDEPENDENT_EVALUATOR_B_CONTROL_DOMAIN_AND_SECOND_VERIFIER",
    } <= set(blockers)


def test_isolated_temporal_sdk_adapter_is_hash_locked_but_not_executed() -> None:
    adapters = _document()["isolated_locked_adapters"]
    assert isinstance(adapters, list) and len(adapters) == 1
    adapter = adapters[0]
    assert adapter["id"] == "temporal-python-sdk"
    assert adapter["version"] == "1.32.0"
    assert re.fullmatch(r"[0-9a-f]{40}", adapter["source_commit"])
    for field in ("lock_sha256", "sdist_sha256", "linux_x86_64_wheel_sha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", adapter[field])
    lock_path = CANDIDATES_PATH.parents[2] / adapter["lock_path"]
    assert sha256(lock_path.read_bytes()).hexdigest() == adapter["lock_sha256"]
    assert "NOT_EXECUTED" in adapter["adoption_state"]


def test_external_audit_qualification_gate_is_explicitly_blocked() -> None:
    qualification = json.loads(QUALIFICATION_PATH.read_text(encoding="utf-8"))

    assert set(qualification) == {
        "schema_version",
        "status",
        "toolchain_candidates_sha256",
        "cosign",
        "trusted_root",
        "auditor",
        "qualification_receipt_sha256",
    }
    assert qualification["schema_version"] == (
        "hswm-g0-external-audit-qualification/v1"
    )
    assert qualification["status"] == "BLOCKED"
    assert qualification["toolchain_candidates_sha256"] == sha256(
        CANDIDATES_PATH.read_bytes()
    ).hexdigest()
    assert qualification["cosign"] is None
    assert qualification["trusted_root"] is None
    assert qualification["auditor"] is None
    assert qualification["qualification_receipt_sha256"] is None
