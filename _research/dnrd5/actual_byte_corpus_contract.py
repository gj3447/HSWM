"""Frozen, no-network wire format for the DNRD-5 actual-byte fixture.

This module intentionally contains only byte rules and immutable vocabulary.  It
does not import the TypeScript runtime, dispatch a provider, or make a research
claim.  The producer and independent judge may import this small contract but
must not import each other.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256

CORPUS_VERSION = "hswm-dnrd5-one-block-actual-byte-corpus/v1"
JUDGE_VERSION = "hswm-dnrd5-independent-actual-byte-judge/v2"
FIXTURE_TRANSPORT_VERSION = "hswm-dnrd5-fixture-transport-receipt/v1"
CANONICAL_JSON_VERSION = "hswm-canonical-json/v1"
SCHEMA_VERSION = "hswm:dnrd5:causal-macroplasticity:v2"
SCHEMA_SHA256 = "a921264c5d1b5d9186d291e6a17ddc0282ce4eaa8832b1a599b7237c23d4b357"
SCHEMA_BYTE_LENGTH = 31_298
LIFECYCLE_SHA256 = "179225541585267214a6cc5b358551c39597c66e546adf46bebad121550763cc"
ALIGNMENT_SHA256 = "0e3ba180d8a3be3c2ed83ffe932965f8500862e02bdb07d953bf67a483f5c807"
TERMINAL = "FIXTURE_BYTE_CLOSURE_VALIDATED_NOT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT"
FIXTURE_CLASS = "DETERMINISTIC_FIXTURE_NOT_TRANSPORT_OR_PROVIDER_OBSERVATION"
ATOM_MEDIA_TYPE = "application/vnd.hswm.canonical-atom-v2+json"
JOURNAL_MEDIA_TYPE = "application/vnd.hswm.canonical-atom-v2-state-journal+json"
JSON_MEDIA_TYPE = "application/vnd.hswm.dnrd5.fixture+json"
ROOT_MEDIA_TYPE = "application/vnd.hswm.dnrd5.actual-byte-corpus-manifest+json"
RECEIPT_MEDIA_TYPE = "application/vnd.hswm.dnrd5-v2.transition-receipt+json"
RECEIPT_SEAL_VERSION = "hswm-dnrd5-v2-receipt-seal/v1"
POSTCOMMIT_RECEIPT_IDENTITY_VERSION = "hswm-dnrd5-v2-postcommit-receipt-identity/v1"
EVIDENCE_BINDING_VERSION = "hswm-dnrd5-fixture-evidence-binding/v1"
EVIDENCE_CLAIM_BOUNDARY = "NOT_SOURCE_BUILD_IMPORT_PERMIT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT"
BLOCK_MANIFEST_VERSION = "hswm-dnrd5-fixture-block-evidence-manifest/v1"
BLOCK_SEAL_VERSION = "hswm-dnrd5-fixture-block-seal/v1"
ROLES = (
    "request-projection", "transmitted-request", "observed-response", "rng",
    "model-identity", "runtime-identity", "isolation-statement", "instruction",
    "model-input", "response-schema",
)
CALL_CLASSES = ("PRE_OUTCOME_TRAJECTORY",) + ("REVISION_PROPOSAL",) * 4 + ("FRESH_PROBE",) * 4
ARMS = ("ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK")

def descriptor(raw: bytes, media_type: str) -> dict[str, Any]:
    return {"mediaType": media_type, "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}

def descriptor_id(value: Mapping[str, Any]) -> str:
    return f"{value['mediaType']}|{value['byteLength']}|{value['sha256']}"

def atom_key_id(key: Mapping[str, str]) -> str:
    return "|".join((key["schemaVersion"], key["lineageId"], key["atomUid"], str(key["revisionId"])))

def blob_path(root: Path, digest: str) -> Path:
    return root / "blobs" / digest

def fixture_root_manifest(core: Mapping[str, Any], descriptor_index: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the one canonical root object; its own descriptor is never indexed."""
    return {
        "_tag": "Dnrd5OneBlockActualByteCorpus",
        "contractVersion": CORPUS_VERSION,
        "canonicalJsonVersion": CANONICAL_JSON_VERSION,
        "fixtureClass": FIXTURE_CLASS,
        "expectedTerminal": TERMINAL,
        "core": core,
        "descriptorIndex": sorted(descriptor_index, key=descriptor_id),
        "rootDerivation": "CANONICAL_MANIFEST_BYTES_SHA256_V1",
    }

def root_descriptor(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return descriptor(canonical_bytes(manifest), ROOT_MEDIA_TYPE)

def schema_source_path(repository_root: Path) -> Path:
    return repository_root / "src/hswm/effect-runtime/dist/canonical-atom-v2-dnrd5-v2-schema.js"
