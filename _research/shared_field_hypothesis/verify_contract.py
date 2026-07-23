#!/usr/bin/env python3
"""Static, fail-closed design lock for the shared-field experiment.

Version 1 deliberately cannot admit a run.  It locks the comparison semantics
and mechanism source boundary while leaving every unavailable artifact visibly
null.  A later version may verify a run only after it derives budgets from an
event ledger and executable parameter inventory; self-reported counters are not
evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "hswm-shared-field-experiment/v1"
STATUS = "DESIGN_LOCKED_NOT_PREREGISTERED"
REFERENCE_COMMIT = "5085642a98a1eb58d65d7c8449a571b5c21f30d2"

MECHANISM_SOURCE_HASHES = {
    "ab_p5_full.py": "2fb1b9e024cea8a457fd6c89b8e2e7049fd4fd1b284477b35f1f561bbc3fef61",
    "doc_builder.py": "52c5ccee2487f62f6b6021ed6438477b7cdac8e84ffadd5f7fe031303adc79fc",
    "hypergraph.py": "3b72f7948196a4c865d5e35e78a2ac1ff9447b205bb07096fe9472a6462e8c34",
    "metrics.py": "de2d3339fd5feb11ea58bb865c5d713a27af2457e61d393fc0dd0f783574c9d0",
    "readouts.py": "62835b20877e696567d322ebade107db123273487e34ed66eb63bec8f3adc4ae",
    "field_snapshot.py": "17cd7251d6d0ff066b70dff89945cc46dac468040ceae0b9483f8b3e015b72f2",
    "stale_poisoning.py": "f5fd4b13dd263a5355324d67774bbd097d8368a92ec9aec96bdfc8a4b55ca36d",
    "traversal.py": "f6e82099315cf3504d08f8d488f0092e071c3d614ee556a865dc0d11f8140b1c",
    "traversal_cert.py": "d26cd1ab86e7bbf8f614fa917658440b58204784bde79674f857527be2f5638a",
    "weight_field.py": "29c9b95d4c8ec31c894c9aa74135b5cedbc55a471f21a4a47a6a62139aad542c",
    "world_builder.py": "a1082dbc4609df819f6395188897b6849d8d40854c993b9fb93882bb0f8fc40f",
    "world_compiler.py": "d11ed5c0e00567170e555cc773055fb58b67c0260dd945574e18ba71d52bcdc7",
    "world_ir.py": "89354d117d41c45e3ed0ee9390eb780950c2a7bb5ac0d7b63dba618854fe4f78",
    "prom_search_hswm/hswm_bond_readout.py": "41bca84d284f82f52a966c03c06e8b83debe30388dc41d8ce425f57ff61221f1",
    "prom_search_hswm/hswm_field_algebra.py": "573de075728aca74965acd945228233e9f736ee96f97dfb7aaa5fee3761cb9ca",
    "prom_search_hswm/hswm_hypergraph.py": "af902f614d9c3bb665c14ac7baa7c2a1570e58cc9aaf1353811d485c544d2c6a",
    "prom_search_hswm/hswm_open_composition.py": "ba92caafc992b2cd22913ba835b61726f9dad730cfd9ac640a2843603bdf866a",
    "prom_search_hswm/fsm/hswm_plasticity_loop.v1.json": "fec06c9c74952062acd8febab35039718094b79f0df522eb1b2e50ceafea8954",
}
VERIFIER_PATH = "_research/shared_field_hypothesis/verify_contract.py"
EXPECTED_SEMANTIC_LOCK_SHA256 = "af78b90a0ff2ac0211ec169bfd34b723d5f7edb9159b924055bf6eba6bad1ac5"
PREDECESSOR_KEYS = (
    "neutral_replay_receipt_sha256",
    "full_candidate_scorepack_sha256",
)
FROZEN_INPUT_KEYS = (
    "dataset_manifest_sha256",
    "split_manifest_sha256",
    "query_manifest_sha256",
    "candidate_manifest_sha256",
    "model_manifest_sha256",
    "topology_manifest_sha256",
    "revision_stream_sha256",
    "evaluator_sha256",
)


class ContractError(ValueError):
    """The design or attempted run violates the locked boundary."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ContractError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain one JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def semantic_lock(manifest: Mapping[str, Any]) -> str:
    """Digest the whole manifest, normalizing only its two self-bindings."""
    normalized = copy.deepcopy(dict(manifest))
    implementation = normalized.get("protocol_implementation")
    if isinstance(implementation, dict):
        implementation["verifier_sha256"] = "<VERIFIER_SHA256>"
        implementation["semantic_lock_sha256"] = "<SEMANTIC_LOCK_SHA256>"
    return _canonical_sha256(normalized)


def _safe_path(root: Path, relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved_root = root.resolve()
    candidate = (resolved_root / path).resolve()
    if not candidate.is_relative_to(resolved_root):
        return None
    return candidate


def _git_blob(root: Path, commit: str, relative: str) -> bytes | None:
    """Read a baseline blob when Git metadata is available; sdists return None."""
    probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return None
    read = subprocess.run(
        ["git", "-C", str(root), "show", f"{commit}:{relative}"],
        check=False,
        capture_output=True,
    )
    if read.returncode != 0:
        raise ContractError(f"cannot read baseline Git object {commit}:{relative}")
    return read.stdout


def _mapping(value: Any, label: str, errors: list[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be an object")
        return {}
    return value


def validate(root: Path, manifest_path: Path) -> list[str]:
    """Return every static design-lock, provenance, and no-result violation."""
    try:
        manifest = load_json(manifest_path)
    except ContractError as exc:
        return [str(exc)]

    errors: list[str] = []
    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if manifest.get("status") != STATUS:
        errors.append(f"status must remain {STATUS} in protocol v1")
    for forbidden in ("results", "observations", "winner", "measured_at"):
        if forbidden in manifest:
            errors.append(f"design-only manifest cannot contain {forbidden}")

    registration = _mapping(manifest.get("registration"), "registration", errors)
    expected_registration = {
        "authority": "repository-local design lock only",
        "locked_at": "2026-07-23",
        "registered_before_measurement": False,
        "prediction_receipt_sha256": None,
        "run_admission": "BLOCKED",
    }
    if dict(registration) != expected_registration:
        errors.append("registration must remain an explicitly unregistered blocked design")

    baseline = _mapping(manifest.get("mechanism_baseline"), "mechanism_baseline", errors)
    if baseline.get("reference_commit") != REFERENCE_COMMIT:
        errors.append("mechanism baseline commit drifted")
    if baseline.get("source_hashes") != MECHANISM_SOURCE_HASHES:
        errors.append("mechanism baseline source inventory drifted")
    for relative, expected in MECHANISM_SOURCE_HASHES.items():
        candidate = _safe_path(root, relative)
        if candidate is None or not candidate.is_file():
            errors.append(f"mechanism source missing or unsafe: {relative}")
            continue
        if sha256_file(candidate) != expected:
            errors.append(f"mechanism source drift: {relative}")
            continue
        try:
            baseline_blob = _git_blob(root, REFERENCE_COMMIT, relative)
        except ContractError as exc:
            errors.append(str(exc))
            continue
        if baseline_blob is not None and hashlib.sha256(baseline_blob).hexdigest() != expected:
            errors.append(f"mechanism baseline Git blob drift: {relative}")

    implementation = _mapping(
        manifest.get("protocol_implementation"), "protocol_implementation", errors
    )
    if implementation.get("verifier_path") != VERIFIER_PATH:
        errors.append("protocol verifier path drifted")
    verifier = _safe_path(root, VERIFIER_PATH)
    if verifier is None or not verifier.is_file():
        errors.append("protocol verifier is missing")
    elif implementation.get("verifier_sha256") != sha256_file(verifier):
        errors.append("protocol verifier SHA-256 drifted")
    actual_semantic_lock = semantic_lock(manifest)
    if actual_semantic_lock != EXPECTED_SEMANTIC_LOCK_SHA256:
        errors.append("protocol semantic lock drifted")
    if implementation.get("semantic_lock_sha256") != EXPECTED_SEMANTIC_LOCK_SHA256:
        errors.append("manifest semantic lock binding drifted")
    if implementation.get("run_verifier_capability") != (
        "UNIMPLEMENTED_ARTIFACT_DERIVATION"
    ):
        errors.append("protocol v1 cannot claim run-verifier capability")

    predecessors = _mapping(manifest.get("predecessors"), "predecessors", errors)
    if tuple(predecessors) != PREDECESSOR_KEYS or any(
        value is not None for value in predecessors.values()
    ):
        errors.append("v1 predecessors must remain present and visibly unresolved")
    frozen = _mapping(manifest.get("frozen_inputs"), "frozen_inputs", errors)
    if tuple(frozen) != FROZEN_INPUT_KEYS or any(value is not None for value in frozen.values()):
        errors.append("v1 frozen inputs must remain present and visibly unresolved")
    return errors


def verify_run(root: Path, manifest_path: Path, run_receipt_path: Path) -> dict[str, Any]:
    """Refuse every run until an artifact-derived verifier replaces protocol v1."""
    del run_receipt_path
    errors = validate(root, manifest_path)
    if errors:
        raise ContractError("invalid design lock: " + "; ".join(errors))
    raise ContractError(
        "protocol v1 cannot admit runs: event-ledger budget derivation and "
        "executable parameter inventory are unimplemented"
    )


__all__ = [
    "ContractError",
    "EXPECTED_SEMANTIC_LOCK_SHA256",
    "MECHANISM_SOURCE_HASHES",
    "REFERENCE_COMMIT",
    "SCHEMA",
    "STATUS",
    "load_json",
    "semantic_lock",
    "sha256_file",
    "validate",
    "verify_run",
]
