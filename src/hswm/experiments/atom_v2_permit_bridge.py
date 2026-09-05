"""Subprocess bridge from the Python G1 instrument to the Atom v2 local Permit commit.

The TypeScript process ``canonical-atom-v2-local-permit-commit-process.js``
mints one ephemeral Ed25519 issuer, issues one signed Permit envelope that
binds an exact pre-state and post-state digest, and commits it through the
fsync'd no-replace local journal slot.  This module only builds the request,
runs the process without a shell, and fail-closed re-checks the receipt
against the bytes it handed over.

It is the real local owner/Permit admission path for one transition.  It is
not an authoritative, distributed, or trusted-time Permit, not canonical HSWM
admission, and not outcome truth, causal credit, learning, or efficacy
evidence.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping

from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


CONTRACT_VERSION = "hswm-local-permit-commit-process/v1"
CLAIM_BOUNDARY = (
    "ONE_SHOT_LOCAL_EPHEMERAL_KEY_PERMIT_COMMIT_OF_ONE_EXACT_STATE_TRANSITION_"
    "NOT_AUTHORITATIVE_NOT_DISTRIBUTED_NOT_TRUSTED_TIME_NOT_CANONICAL_HSWM_ADMISSION_"
    "NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY"
)
PROCESS_SCRIPT = Path("src/hswm/effect-runtime/dist/canonical-atom-v2-local-permit-commit-process.js")
MAX_OUTPUT_BYTES = 1_048_576
MAX_STATE_BYTES = 262_144
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_HEAD_KEYS = {"lineageId", "sequence", "stateDigest", "recordDigest"}
_RECEIPT_KEYS = {
    "recordSha256", "slotPath", "nonceDigest", "executionIntentDigest", "priorHead",
    "expectedNextHead", "verificationTime", "postStateSha256", "status",
}
_COMMIT_RESULT_KEYS = {
    "_tag", "contractVersion", "operation", "receipt", "envelopeSha256", "envelopeBytesBase64Url",
    "trustSnapshotPath", "trustSnapshotSha256", "preStateSha256", "postStateSha256",
    "commitStatus", "claimBoundary",
}
_RECOVER_RESULT_KEYS = {
    "_tag", "contractVersion", "operation", "commits", "head", "trustSnapshotPath",
    "trustSnapshotSha256", "commitStatus", "claimBoundary",
}


class AtomV2PermitBridgeError(RuntimeError):
    """The bridge request, process, or receipt failed closed."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise AtomV2PermitBridgeError(f"{label} must be a bounded identifier")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise AtomV2PermitBridgeError(f"{label} must be a SHA-256 hex digest")
    return value


def _head(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _HEAD_KEYS:
        raise AtomV2PermitBridgeError(f"{label} head shape is invalid")
    if type(value["sequence"]) is not int or value["sequence"] < 0:
        raise AtomV2PermitBridgeError(f"{label}.sequence is invalid")
    return {
        "lineageId": _identifier(value["lineageId"], f"{label}.lineageId"),
        "sequence": int(value["sequence"]),
        "stateDigest": _sha(value["stateDigest"], f"{label}.stateDigest"),
        "recordDigest": _sha(value["recordDigest"], f"{label}.recordDigest"),
    }


def transition_claims(
    *,
    lineage_id: str,
    permit_id: str,
    execution_id: str,
    execution_intent_sha256: str,
    permit_sha256: str,
    proposal_sha256: str,
    transition_invariant_sha256: str,
    prior_record_sha256: str,
    successor_record_sha256: str,
    pre_state_bytes: bytes,
    post_state_bytes: bytes,
    target_schema_version: str,
    target_atom_uid: str,
    authorization_ref: str,
    scope: str,
) -> dict[str, Any]:
    """Build the claims of one sequence-zero to sequence-one local transition."""

    for raw, label in ((pre_state_bytes, "pre-state"), (post_state_bytes, "post-state")):
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_STATE_BYTES:
            raise AtomV2PermitBridgeError(f"{label} bytes must be nonempty and bounded")
    return {
        "permitId": _identifier(permit_id, "permitId"),
        "executionId": _identifier(execution_id, "executionId"),
        "executionIntentDigest": _sha(execution_intent_sha256, "executionIntentDigest"),
        "permitDigest": _sha(permit_sha256, "permitDigest"),
        "proposalDigest": _sha(proposal_sha256, "proposalDigest"),
        "transitionInvariantDigest": _sha(transition_invariant_sha256, "transitionInvariantDigest"),
        "priorHead": {
            "lineageId": _identifier(lineage_id, "lineageId"),
            "sequence": 0,
            "stateDigest": sha256(pre_state_bytes).hexdigest(),
            "recordDigest": _sha(prior_record_sha256, "prior recordDigest"),
        },
        "expectedNextHead": {
            "lineageId": lineage_id,
            "sequence": 1,
            "stateDigest": sha256(post_state_bytes).hexdigest(),
            "recordDigest": _sha(successor_record_sha256, "successor recordDigest"),
        },
        "target": {
            "schemaVersion": _identifier(target_schema_version, "target.schemaVersion"),
            "lineageId": lineage_id,
            "atomUid": _identifier(target_atom_uid, "target.atomUid"),
        },
        "expectedRevision": "revision:0",
        "candidateRevision": "revision:1",
        "authorizationRef": _identifier(authorization_ref, "authorizationRef"),
        "scope": _identifier(scope, "scope"),
        "linearizationIndex": 1,
    }


@dataclass(frozen=True)
class LocalPermitCommitProcess:
    """One executable bridge: ``[runtime, script]`` fed canonical JSON on stdin."""

    runtime: str
    script: str
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, str) or not os.path.isabs(self.runtime):
            raise AtomV2PermitBridgeError("bridge runtime must be an absolute executable path")
        if not isinstance(self.script, str) or not os.path.isabs(self.script) or not Path(self.script).is_file():
            raise AtomV2PermitBridgeError("bridge script must be an absolute existing file")
        if not (isinstance(self.timeout_seconds, (int, float)) and 0 < self.timeout_seconds <= 3600):
            raise AtomV2PermitBridgeError("bridge timeout must be within (0, 3600] seconds")

    def describe(self) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "runtime": self.runtime,
            "script": self.script,
            "script_sha256": sha256(Path(self.script).read_bytes()).hexdigest(),
            "claim_boundary": CLAIM_BOUNDARY,
        }

    def _run(self, request: Mapping[str, Any]) -> dict[str, Any]:
        raw = canonical_json_bytes(request)
        try:
            completed = subprocess.run(
                [self.runtime, self.script],
                input=raw,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AtomV2PermitBridgeError(f"bridge process could not complete: {type(error).__name__}") from error
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", "replace").strip()[:512]
            raise AtomV2PermitBridgeError(f"bridge process refused (exit {completed.returncode}): {detail}")
        if len(completed.stdout) > MAX_OUTPUT_BYTES:
            raise AtomV2PermitBridgeError("bridge process output exceeds the bounded limit")
        try:
            result = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AtomV2PermitBridgeError("bridge process output is not JSON") from error
        if not isinstance(result, dict) or result.get("contractVersion") != CONTRACT_VERSION:
            raise AtomV2PermitBridgeError("bridge process output contract drifted")
        if result.get("claimBoundary") != CLAIM_BOUNDARY:
            raise AtomV2PermitBridgeError("bridge process claim boundary drifted")
        return result

    def commit(
        self,
        *,
        root_path: str | Path,
        trust_snapshot_path: str | Path,
        issuer: Mapping[str, Any],
        claims: Mapping[str, Any],
        pre_state_bytes: bytes,
        post_state_bytes: bytes,
        lifetime_ms: int = 60_000,
    ) -> dict[str, Any]:
        """Commit one exact transition; the receipt is re-checked against the bytes."""

        root = Path(root_path)
        snapshot = Path(trust_snapshot_path)
        if not root.is_absolute() or not snapshot.is_absolute():
            raise AtomV2PermitBridgeError("bridge root and trust snapshot paths must be absolute")
        if set(issuer) != {"keyId", "authorizer", "policyVersion", "revocationEpoch"}:
            raise AtomV2PermitBridgeError("issuer configuration shape is invalid")
        request = {
            "contractVersion": CONTRACT_VERSION,
            "operation": "commit",
            "rootPath": str(root),
            "trustSnapshotPath": str(snapshot),
            "issuer": dict(issuer),
            "lifetimeMs": int(lifetime_ms),
            "claims": dict(claims),
            "preStateBase64Url": _b64url(pre_state_bytes),
            "postStateBase64Url": _b64url(post_state_bytes),
        }
        result = self._run(request)
        if set(result) != _COMMIT_RESULT_KEYS or result["operation"] != "commit":
            raise AtomV2PermitBridgeError("bridge commit result shape drifted")
        receipt = result["receipt"]
        if not isinstance(receipt, Mapping) or set(receipt) != _RECEIPT_KEYS:
            raise AtomV2PermitBridgeError("bridge commit receipt shape drifted")
        prior = _head(receipt["priorHead"], "receipt.priorHead")
        successor = _head(receipt["expectedNextHead"], "receipt.expectedNextHead")
        pre_sha = sha256(pre_state_bytes).hexdigest()
        post_sha = sha256(post_state_bytes).hexdigest()
        if (
            prior["stateDigest"] != pre_sha
            or successor["stateDigest"] != post_sha
            or result["preStateSha256"] != pre_sha
            or result["postStateSha256"] != post_sha
            or receipt["postStateSha256"] != post_sha
            or prior != claims["priorHead"]
            or successor != claims["expectedNextHead"]
        ):
            raise AtomV2PermitBridgeError("bridge receipt does not bind the exact state bytes handed over")
        record_sha = _sha(receipt["recordSha256"], "receipt.recordSha256")
        slot = Path(str(receipt["slotPath"]))
        if not slot.is_absolute() or not slot.is_file() or sha256(slot.read_bytes()).hexdigest() != record_sha:
            raise AtomV2PermitBridgeError("bridge journal slot bytes do not match the receipt digest")
        if str(result["trustSnapshotPath"]) != str(snapshot) or not snapshot.is_file():
            raise AtomV2PermitBridgeError("bridge trust snapshot was not published beside the journal")
        if sha256(snapshot.read_bytes()).hexdigest() != _sha(result["trustSnapshotSha256"], "trustSnapshotSha256"):
            raise AtomV2PermitBridgeError("bridge trust snapshot digest drifted")
        try:
            envelope = base64.urlsafe_b64decode(str(result["envelopeBytesBase64Url"]) + "==")
        except (ValueError, TypeError) as error:
            raise AtomV2PermitBridgeError("bridge envelope bytes are malformed") from error
        if sha256(envelope).hexdigest() != _sha(result["envelopeSha256"], "envelopeSha256"):
            raise AtomV2PermitBridgeError("bridge envelope digest drifted")
        # The key is deliberately not ``record_sha256``: g1_micro treats any
        # mapping with that key as one of its own local records.
        summary = {
            "contract_version": CONTRACT_VERSION,
            "claim_boundary": CLAIM_BOUNDARY,
            "commit_status": str(result["commitStatus"]),
            "commit_record_sha256": record_sha,
            "slot_path": str(slot),
            "nonce_digest": _sha(receipt["nonceDigest"], "receipt.nonceDigest"),
            "execution_intent_sha256": _sha(receipt["executionIntentDigest"], "receipt.executionIntentDigest"),
            "prior_head": prior,
            "expected_next_head": successor,
            "verification_time": str(receipt["verificationTime"]),
            "envelope_sha256": str(result["envelopeSha256"]),
            "trust_snapshot_path": str(snapshot),
            "trust_snapshot_sha256": str(result["trustSnapshotSha256"]),
            "pre_state_sha256": pre_sha,
            "post_state_sha256": post_sha,
            "process": self.describe(),
        }
        return {**summary, "summary_sha256": canonical_sha256(summary)}

    def recover(self, *, root_path: str | Path, trust_snapshot_path: str | Path) -> dict[str, Any]:
        result = self._run({
            "contractVersion": CONTRACT_VERSION,
            "operation": "recover",
            "rootPath": str(Path(root_path)),
            "trustSnapshotPath": str(Path(trust_snapshot_path)),
        })
        if set(result) != _RECOVER_RESULT_KEYS or result["operation"] != "recover":
            raise AtomV2PermitBridgeError("bridge recover result shape drifted")
        commits = result["commits"]
        if not isinstance(commits, list):
            raise AtomV2PermitBridgeError("bridge recover commits are invalid")
        for item in commits:
            if not isinstance(item, Mapping) or set(item) != _RECEIPT_KEYS:
                raise AtomV2PermitBridgeError("bridge recovered receipt shape drifted")
        return result


def verify_commit_summary(summary: Mapping[str, Any]) -> None:
    """Re-check a stored commit summary's self-digest and retained slot bytes."""

    if not isinstance(summary, Mapping) or "summary_sha256" not in summary:
        raise AtomV2PermitBridgeError("commit summary is missing its digest")
    unsigned = dict(summary)
    digest = unsigned.pop("summary_sha256")
    if digest != canonical_sha256(unsigned):
        raise AtomV2PermitBridgeError("commit summary digest mismatch")
    if unsigned.get("contract_version") != CONTRACT_VERSION or unsigned.get("claim_boundary") != CLAIM_BOUNDARY:
        raise AtomV2PermitBridgeError("commit summary contract or claim boundary drifted")
    prior = _head(unsigned["prior_head"], "prior_head")
    successor = _head(unsigned["expected_next_head"], "expected_next_head")
    if prior["stateDigest"] != _sha(unsigned["pre_state_sha256"], "pre_state_sha256"):
        raise AtomV2PermitBridgeError("commit summary prior head does not bind its pre-state digest")
    if successor["stateDigest"] != _sha(unsigned["post_state_sha256"], "post_state_sha256"):
        raise AtomV2PermitBridgeError("commit summary next head does not bind its post-state digest")
    slot = Path(str(unsigned["slot_path"]))
    if slot.is_file() and sha256(slot.read_bytes()).hexdigest() != _sha(unsigned["commit_record_sha256"], "commit_record_sha256"):
        raise AtomV2PermitBridgeError("retained journal slot bytes differ from the commit summary")


def default_process(repo_root: str | Path, *, runtime: str | None = None) -> LocalPermitCommitProcess | None:
    """Locate Node and the built process; return None when either is absent."""

    script = Path(repo_root) / PROCESS_SCRIPT
    node = runtime or shutil.which("node")
    if node is None or not script.is_file():
        return None
    return LocalPermitCommitProcess(runtime=str(Path(node).resolve()), script=str(script.resolve()))
