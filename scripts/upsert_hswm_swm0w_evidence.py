#!/usr/bin/env python3
"""Validate and explicitly publish the additive SWM-0W evidence bundle.

The default operation is local and read-only.  Remote mutation requires
``--apply`` and an explicit Neo4j source configuration.  Existing ontology
anchors are read only; this publisher never writes USER_PRIMARY nodes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Mapping, Sequence

from hswm.experiments import swm0w_beacon as beacon
from hswm.experiments import swm0w_confirmatory as confirmatory
from hswm.experiments import swm0w_protocol as protocol


SCHEMA_VERSION = "hswm-swm0w-evidence-ontology/v1"
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
ANCHOR_UID = "sym:ImplementationPlan:hswm-swm0-nary-witness"
BUNDLE_UID = "sym:AbstractNode:hswm-swm0w-evidence-bundle-2026-08-20"
EXPERIMENT_UID = "sym:Experiment:hswm-swm0w-scalar-gate-2026-08-20"
CODE_UID = "sym:Artifact:hswm-swm0w-code-runtime-binding-2026-08-20"
PREREG_UID = "sym:Artifact:hswm-swm0w-preregistration-2026-08-20"
CANDIDATE_UID = "sym:Result:hswm-swm0w-candidate-result-2026-08-20"
ADJUDICATION_UID = "sym:Evidence:hswm-swm0w-pass-adjudication-2026-08-20"

SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
GIT_COMMIT_RE = re.compile(r"[0-9a-f]{40}")

FROZEN_LABELS = frozenset(
    {
        "AbstractNode",
        "Artifact",
        "Evidence",
        "Experiment",
        "ResearchArtifact",
        "Result",
    }
)
FROZEN_RELTYPES = frozenset(
    {
        "BINDS",
        "CONTAINS",
        "DERIVED_FROM",
        "EVIDENCE_FOR",
        "PRODUCED_BY",
        "REQUIRES",
        "TARGETS",
        "VALIDATES",
    }
)

PREREG_PATH = "prereg/PREREG_SWM0W_SCALAR_GATE_V1.json"
CANDIDATE_PATH = "results/raw/swm0w_scalar_gate_candidate_2026-08-20.json"
ADJUDICATION_PATH = (
    "evidence/EVIDENCE_SWM0W_SCALAR_GATE_ADJUDICATION_2026-08-20.json"
)
RESULT_REPORT_PATH = "results/SWM0W_SCALAR_GATE_RESULTS_2026-08-20.md"
PUBLISHER_PATH = "scripts/upsert_hswm_swm0w_evidence.py"
PUBLISHER_TEST_PATH = "tests/test_hswm_swm0w_ontology.py"
HUB_ONTOLOGY_PATH = (
    "ontology/identity/human_universal_body/"
    "HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json"
)

SOURCE_COMMIT_A = "130d2265befeeb0bb6542bdec1eb962b48c6c346"
REGISTRATION_COMMIT_B = "ec19a74cbcde409add819c8b566627c49582ea9a"

WORKFLOW_PATH = ".github/workflows/swm0w-confirmatory.yml"
RUNTIME_PATHS = (
    "src/hswm/experiments/swm0w_beacon.py",
    "src/hswm/experiments/swm0w_confirmatory.py",
    "src/hswm/experiments/swm0w_operator.py",
    "src/hswm/experiments/swm0w_protocol.py",
    "src/hswm/experiments/swm0w_task_family.py",
    "src/hswm/experiments/swm0w_worlds.py",
)
VERIFIER_PATHS = (
    "tools/swm0w_drand/package-lock.json",
    "tools/swm0w_drand/package.json",
    "tools/swm0w_drand/verify-beacon.mjs",
)
LOCK_PATH = "uv.lock"
MEASUREMENT_SOURCE_PATHS = (
    WORKFLOW_PATH,
    *RUNTIME_PATHS,
    *VERIFIER_PATHS,
    LOCK_PATH,
)
EXPECTED_BINDING_ROLES = {
    WORKFLOW_PATH: "CONFIRMATORY_WORKFLOW",
    **{path: "RUNTIME_SOURCE" for path in RUNTIME_PATHS},
    **{path: "BLS_VERIFIER_SOURCE" for path in VERIFIER_PATHS},
    LOCK_PATH: "PYTHON_LOCKFILE",
    PREREG_PATH: "PREREGISTRATION",
    CANDIDATE_PATH: "CANDIDATE_RESULT",
    ADJUDICATION_PATH: "EVIDENCE_ADJUDICATION",
    RESULT_REPORT_PATH: "RESULT_REPORT",
    PUBLISHER_PATH: "KG_PUBLISHER",
    PUBLISHER_TEST_PATH: "KG_PUBLISHER_TEST",
}

SYSTEM_PROPERTY_KEYS = frozenset({"createdAt"})


class SWM0WEvidenceError(ValueError):
    """Raised when the bundle, its artifacts, or remote readback is invalid."""


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SWM0WEvidenceError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    """Load UTF-8 JSON while rejecting duplicate keys and non-object roots."""

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SWM0WEvidenceError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise SWM0WEvidenceError(f"JSON artifact must be an object: {path}")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SWM0WEvidenceError(f"{field} must be a lowercase SHA-256")
    return value


def _require_commit(value: Any, field: str) -> str:
    if not isinstance(value, str) or not GIT_COMMIT_RE.fullmatch(value):
        raise SWM0WEvidenceError(f"{field} must be a full lowercase Git commit")
    return value


def _resolve_repo_file(repo_root: Path, relative: Any, field: str) -> tuple[str, Path]:
    if not isinstance(relative, str) or not relative:
        raise SWM0WEvidenceError(f"{field} must be a non-empty repository path")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or relative != pure.as_posix() or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise SWM0WEvidenceError(f"{field} is not a normalized repository path: {relative!r}")
    root = repo_root.resolve()
    candidate = repo_root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SWM0WEvidenceError(f"{field} escapes or is missing: {relative}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise SWM0WEvidenceError(f"{field} must be a non-symlink regular file: {relative}")
    return relative, resolved


def _run_git(repo_root: Path, arguments: Sequence[str], *, text: bool = False) -> Any:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=True,
            capture_output=True,
            text=text,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SWM0WEvidenceError(f"Git binding failed: {' '.join(arguments)}") from exc


def _head_commit(repo_root: Path) -> str:
    return _require_commit(
        _run_git(repo_root, ["rev-parse", "HEAD"], text=True).strip(),
        "HEAD",
    )


def _verify_tracked_head(repo_root: Path, relative: str, expected_sha256: str) -> None:
    _run_git(repo_root, ["ls-files", "--error-unmatch", "--", relative])
    head_bytes = _run_git(repo_root, ["show", f"HEAD:{relative}"])
    if sha256(head_bytes).hexdigest() != expected_sha256:
        raise SWM0WEvidenceError(f"working artifact is not byte-identical to HEAD: {relative}")


def _verify_historical_binding(
    repo_root: Path,
    commit: str,
    relative: str,
    expected_sha256: str,
) -> None:
    historical = _run_git(repo_root, ["show", f"{commit}:{relative}"])
    if sha256(historical).hexdigest() != expected_sha256:
        raise SWM0WEvidenceError(
            f"historical source hash mismatch at {commit}:{relative}"
        )


def read_flat_yaml(path: Path) -> dict[str, str]:
    """Read the flat Neo4j source config without exposing credentials."""

    config: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        config[key.strip()] = value.strip().strip('"').strip("'")
    required = {"uri", "user", "password", "database"}
    missing = required - config.keys()
    if missing:
        raise SWM0WEvidenceError(f"source config is missing keys: {sorted(missing)}")
    return config


def _is_neo4j_property(value: Any) -> bool:
    scalar_types = (str, bool, int, float)
    if value is None:
        return False
    if isinstance(value, scalar_types):
        return True
    if not isinstance(value, list):
        return False
    if not value:
        return True
    first_type = type(value[0])
    return first_type in scalar_types and all(type(item) is first_type for item in value)


def _parse_canonical_json_file(path: Path, name: str) -> dict[str, Any]:
    """Parse exact one-line canonical JSON bytes with duplicate-key rejection."""

    try:
        value = confirmatory.parse_canonical_json_object_bytes(
            path.read_bytes(), name=name
        )
    except (OSError, confirmatory.SWM0WConfirmatoryError) as exc:
        raise SWM0WEvidenceError(f"invalid canonical {name}: {path}") from exc
    if type(value) is not dict:
        raise SWM0WEvidenceError(f"{name} must be an exact object")
    return value


def _validate_candidate_self_hash(candidate: Mapping[str, Any]) -> str:
    expected_keys = {
        "beacon_task_seed_binding",
        "bundle_sha256",
        "confirmatory_admission",
        "github_api_evidence",
        "github_operational_chronology",
        "preregistration",
        "protocol_candidate_outcome",
        "protocol_final_receipt",
        "registration_carrier",
        "schema_version",
        "task_receipts_in_seed_order",
        "trust_boundary",
        "verifier_receipt",
    }
    if set(candidate) != expected_keys:
        raise SWM0WEvidenceError("candidate schema keys drift")
    if candidate.get("schema_version") != confirmatory.CANDIDATE_BUNDLE_SCHEMA:
        raise SWM0WEvidenceError("unexpected SWM-0W candidate schema")
    digest = _require_sha256(candidate.get("bundle_sha256"), "candidate bundle_sha256")
    unsigned = dict(candidate)
    del unsigned["bundle_sha256"]
    if canonical_sha256(unsigned) != digest:
        raise SWM0WEvidenceError("candidate bundle_sha256 mismatch")
    if "evidence_verdict" in candidate:
        raise SWM0WEvidenceError("candidate must not contain an evidence verdict")
    return digest


def _binding_map(data: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    rows = data.get("artifact_bindings")
    if not isinstance(rows, list):
        raise SWM0WEvidenceError("artifact_bindings must be a list")
    result: dict[str, dict[str, str]] = {}
    seen_roles: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SWM0WEvidenceError(f"artifact binding {index} must be an object")
        path = row.get("path")
        role = row.get("role")
        digest = _require_sha256(row.get("sha256"), f"artifact binding {index} sha256")
        if not isinstance(path, str) or not isinstance(role, str):
            raise SWM0WEvidenceError(f"artifact binding {index} has invalid path or role")
        if path in result or (role, path) in seen_roles:
            raise SWM0WEvidenceError(f"duplicate artifact binding: {path}")
        result[path] = {"path": path, "role": role, "sha256": digest}
        seen_roles.add((role, path))
    if {path: row["role"] for path, row in result.items()} != EXPECTED_BINDING_ROLES:
        raise SWM0WEvidenceError("artifact binding paths or roles differ from the frozen set")
    canonical_rows = sorted(result.values(), key=lambda row: (row["role"], row["path"]))
    expected_set_sha = _require_sha256(data.get("artifact_set_sha256"), "artifact_set_sha256")
    if canonical_sha256(canonical_rows) != expected_set_sha:
        raise SWM0WEvidenceError("artifact_set_sha256 mismatch")
    return result


def _validate_local_anchor(data: Mapping[str, Any], repo_root: Path) -> None:
    anchors = data.get("anchors")
    if not isinstance(anchors, list) or len(anchors) != 1:
        raise SWM0WEvidenceError("exactly one read-only SWM-0 anchor is required")
    anchor = anchors[0]
    expected = {
        "uid": ANCHOR_UID,
        "labels": ["Plan", "ImplementationPlan"],
        "properties": {
            "name": "SWM-0 — n-ary non-collapse witness",
            "authority_class": "SECONDARY_AI",
            "implementation_stage": "SWM-0",
        },
        "read_only": True,
    }
    if anchor != expected:
        raise SWM0WEvidenceError("read-only SWM-0 anchor contract drift")

    hub = load_json(repo_root / HUB_ONTOLOGY_PATH)
    matches = [row for row in hub.get("nodes", []) if row.get("uid") == ANCHOR_UID]
    if len(matches) != 1:
        raise SWM0WEvidenceError("local HUB ontology lacks one unique SWM-0 anchor")
    row = matches[0]
    if row.get("labels") != expected["labels"]:
        raise SWM0WEvidenceError("local SWM-0 anchor labels drifted")
    properties = row.get("properties", {})
    for key, value in expected["properties"].items():
        if properties.get(key) != value:
            raise SWM0WEvidenceError(f"local SWM-0 anchor property drift: {key}")


def _validate_cross_bindings(
    data: Mapping[str, Any],
    repo_root: Path,
    bindings: Mapping[str, Mapping[str, str]],
    *,
    verify_replay: bool,
) -> dict[str, Any]:
    """Replay all locally reproducible receipts and bind the live-evidence record."""

    try:
        prereg_bytes = (repo_root / PREREG_PATH).read_bytes()
        prereg_payload = _parse_canonical_json_file(
            repo_root / PREREG_PATH, "SWM-0W preregistration"
        )
        preregistration = confirmatory.validate_preregistration_bytes(
            prereg_bytes, repo_root=repo_root
        )
        candidate = _parse_canonical_json_file(
            repo_root / CANDIDATE_PATH, "SWM-0W candidate bundle"
        )
        adjudication_raw = _parse_canonical_json_file(
            repo_root / ADJUDICATION_PATH, "SWM-0W evidence adjudication"
        )
        report_text = (repo_root / RESULT_REPORT_PATH).read_text(encoding="utf-8")
        candidate_bundle_sha = _validate_candidate_self_hash(candidate)
        adjudication = confirmatory.parse_evidence_adjudication(adjudication_raw)

        if candidate["preregistration"] != prereg_payload:
            raise SWM0WEvidenceError("candidate embedded preregistration bytes drift")
        if preregistration.prereg_file_sha256 != bindings[PREREG_PATH]["sha256"]:
            raise SWM0WEvidenceError("preregistration file hash drift")
        if preregistration.repository_binding["source_commit_a"] != SOURCE_COMMIT_A:
            raise SWM0WEvidenceError("source commit A drift")

        required_sources = preregistration.repository_binding[
            "required_file_sha256"
        ]
        if (
            not isinstance(required_sources, Mapping)
            or set(required_sources) != set(MEASUREMENT_SOURCE_PATHS)
        ):
            raise SWM0WEvidenceError("preregistered measurement-source set drift")
        for path in MEASUREMENT_SOURCE_PATHS:
            digest = bindings[path]["sha256"]
            if required_sources[path] != digest:
                raise SWM0WEvidenceError(
                    f"preregistered source hash differs from KG binding: {path}"
                )
            _verify_historical_binding(repo_root, SOURCE_COMMIT_A, path, digest)

        carrier = confirmatory.parse_registration_carrier(
            candidate["registration_carrier"]
        )
        if carrier.registration_commit_b != REGISTRATION_COMMIT_B:
            raise SWM0WEvidenceError("registration commit B drift")
        confirmatory.validate_registration_commit_pair(
            preregistration,
            repo_root=repo_root,
            registration_commit_b=carrier.registration_commit_b,
        )

        chronology = confirmatory.parse_github_chronology_receipt(
            candidate["github_operational_chronology"]
        )
        confirmatory._validate_chronology_links(
            preregistration, carrier, chronology
        )

        github = candidate["github_api_evidence"]
        if type(github) is not dict or set(github) != {
            "artifact",
            "jobs",
            "run",
            "workflow_runs",
        }:
            raise SWM0WEvidenceError("embedded GitHub evidence schema drift")
        run = github["run"]
        workflow_runs = github["workflow_runs"]
        jobs = github["jobs"]
        artifact = github["artifact"]
        if any(type(row) is not dict for row in (run, workflow_runs, jobs, artifact)):
            raise SWM0WEvidenceError("embedded GitHub evidence must contain objects")
        confirmatory._validate_github_run(
            run,
            preregistration=preregistration,
            registration_commit_b=carrier.registration_commit_b,
            expected_run_id=carrier.run_id,
        )
        uniqueness = confirmatory._validate_sole_surviving_workflow_run(
            workflow_runs,
            preregistration=preregistration,
            registration_commit_b=carrier.registration_commit_b,
            expected_run_id=carrier.run_id,
        )
        uniqueness_sha = canonical_sha256(uniqueness)
        if (
            uniqueness_sha != carrier.workflow_run_uniqueness_sha256
            or uniqueness_sha != chronology.workflow_run_uniqueness_sha256
        ):
            raise SWM0WEvidenceError("workflow-run uniqueness receipt drift")
        if (
            canonical_sha256(confirmatory._github_run_projection(run))
            != chronology.run_api_sha256
        ):
            raise SWM0WEvidenceError("GitHub run projection hash drift")

        job_id, job_started, job_completed, job_projection = (
            confirmatory._registration_job(carrier, jobs)
        )
        if (
            job_id != chronology.registration_job_id
            or job_started != chronology.registration_job_started_at
            or job_completed != chronology.registration_job_completed_at
            or canonical_sha256(job_projection) != chronology.jobs_api_sha256
        ):
            raise SWM0WEvidenceError("registration-job receipt drift")
        artifact_created, artifact_created_unix = confirmatory._validate_artifact_api(
            carrier,
            artifact,
            expected_artifact_id=chronology.artifact_id,
            expected_artifact_digest=chronology.artifact_digest,
        )
        if (
            artifact_created != chronology.artifact_created_at
            or canonical_sha256(artifact) != chronology.artifact_api_sha256
            or not (
                confirmatory._timestamp(job_started, "register.started_at")
                <= artifact_created_unix
                <= confirmatory._timestamp(job_completed, "register.completed_at")
            )
        ):
            raise SWM0WEvidenceError("registration-artifact receipt drift")

        binding = confirmatory.parse_task_seed_binding(
            candidate["beacon_task_seed_binding"]
        )
        beacon.validate_task_seed_bundle_links(
            preregistration.commitment,
            candidate["verifier_receipt"],
            binding,
        )
        admission = protocol.validate_admission_receipt(
            candidate["confirmatory_admission"]
        )
        replayed_admission = confirmatory.admit_verified_seed_bundle(
            preregistration,
            carrier,
            chronology,
            verifier_receipt=candidate["verifier_receipt"],
            task_seed_binding=binding,
        )
        if admission != replayed_admission:
            raise SWM0WEvidenceError("confirmatory admission replay drift")

        raw_tasks = candidate["task_receipts_in_seed_order"]
        if type(raw_tasks) is not list:
            raise SWM0WEvidenceError("candidate task receipts must be a list")
        tasks = tuple(protocol.validate_task_receipt(row) for row in raw_tasks)
        confirmatory._validate_tasks_against_beacon_seeds(tasks, binding)
        final = protocol.validate_final_receipt(
            candidate["protocol_final_receipt"]
        )
        reduced = protocol.finalize_protocol(
            tasks,
            mode=protocol.RunMode.CONFIRMATORY,
            optimizer=protocol.CONFIRMATORY_OPTIMIZER,
            admission=admission,
            thresholds=protocol.CONFIRMATORY_THRESHOLDS,
        )
        if reduced != final:
            raise SWM0WEvidenceError("protocol reducer replay drift")
        if candidate["protocol_candidate_outcome"] != final.outcome.value:
            raise SWM0WEvidenceError("candidate outcome differs from reducer")
        if final.outcome is not protocol.ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE:
            raise SWM0WEvidenceError("this bundle is PASS-only")

        confirm_rows = [
            row
            for row in jobs.get("jobs", [])
            if type(row) is dict and row.get("name") == "confirm"
        ]
        if (
            len(confirm_rows) != 1
            or adjudication.confirm_job_id != confirm_rows[0].get("id")
            or adjudication.confirm_job_started_at
            != confirm_rows[0].get("started_at")
            or confirm_rows[0].get("run_id") != carrier.run_id
            or confirm_rows[0].get("head_sha") != carrier.registration_commit_b
        ):
            raise SWM0WEvidenceError("candidate/confirm-job identity binding drift")

        ordered_seed_sha = protocol.ordered_task_seed_binding_sha256(
            binding.task_seed_bytes()
        )
        candidate_file_sha = bindings[CANDIDATE_PATH]["sha256"]
        expected_adjudication = {
            "candidate_bundle_sha256": candidate_bundle_sha,
            "candidate_file_sha256": candidate_file_sha,
            "candidate_protocol_outcome": final.outcome.value,
            "candidate_protocol_receipt_sha256": final.receipt_sha256,
            "commitment_sha256": preregistration.commitment.commitment_sha256,
            "experiment_id": preregistration.experiment_id,
            "future_round": preregistration.commitment.round,
            "github_chronology_receipt_sha256": chronology.receipt_sha256,
            "preregistration_sha256": preregistration.preregistration_sha256,
            "registration_commit_b": carrier.registration_commit_b,
            "registration_core_sha256": preregistration.registration_core_sha256,
            "run_attempt": 1,
            "run_id": carrier.run_id,
            "source_commit_a": SOURCE_COMMIT_A,
            "task_count": protocol.TASK_COUNT,
            "task_seed_binding_sha256": ordered_seed_sha,
            "workflow_run_uniqueness_sha256": uniqueness_sha,
            "workflow_sha256": carrier.workflow_sha256,
        }
        for field, expected in expected_adjudication.items():
            if getattr(adjudication, field) != expected:
                raise SWM0WEvidenceError(
                    f"candidate/adjudication binding drift: {field}"
                )
        if (
            adjudication.candidate_archive_sha256
            != adjudication.candidate_artifact_digest
            or adjudication.candidate_artifact_name
            != confirmatory.candidate_artifact_name(carrier)
            or not (
                confirmatory._timestamp(
                    adjudication.confirm_job_started_at,
                    "confirm.started_at",
                )
                <= confirmatory._timestamp(
                    adjudication.candidate_artifact_created_at,
                    "candidate.created_at",
                )
                <= confirmatory._timestamp(
                    adjudication.confirm_job_completed_at,
                    "confirm.completed_at",
                )
            )
        ):
            raise SWM0WEvidenceError("candidate artifact adjudication receipt drift")
        if (
            adjudication.evidence_verdict != "PASS"
            or adjudication.validated is not True
            or adjudication.reason_codes != final.reason_codes
            or adjudication.capacity_independent_phrase_allowed is not True
            or final.capacity_independent_phrase_candidate is not True
        ):
            raise SWM0WEvidenceError("PASS adjudication semantics drift")
        required_report_tokens = (
            "Evidence verdict: **`PASS`**",
            "Bounded scientific status: **`SUPPORTED_NARROW`**",
            "Whole-HSWM scientific status: **`UNJUDGED`**",
            "candidate-only, non-authoritative",
            SOURCE_COMMIT_A,
            REGISTRATION_COMMIT_B,
            bindings[CANDIDATE_PATH]["sha256"],
            bindings[ADJUDICATION_PATH]["sha256"],
            adjudication.receipt_sha256,
        )
        missing_report_tokens = [
            token for token in required_report_tokens if token not in report_text
        ]
        if missing_report_tokens:
            raise SWM0WEvidenceError(
                f"bounded result report lacks exact claim tokens: {missing_report_tokens}"
            )

        if verify_replay:
            bls = confirmatory._replay_committed_pulse_bls(
                preregistration,
                candidate["verifier_receipt"],
                binding,
            )
            observed_bls = {
                "bls_replay_fixture_sha256": bls.fixture_sha256,
                "bls_replay_ordered_task_seed_binding_sha256": (
                    bls.ordered_task_seed_binding_sha256
                ),
                "bls_replay_stable_projection_sha256": (
                    bls.stable_projection_sha256
                ),
            }
            for field, observed in observed_bls.items():
                if getattr(adjudication, field) != observed:
                    raise SWM0WEvidenceError(
                        f"offline BLS adjudication replay drift: {field}"
                    )

        expected_internal = {
            "admission_receipt_sha256": admission.receipt_sha256,
            "bls_replay_fixture_sha256": adjudication.bls_replay_fixture_sha256,
            "bls_replay_ordered_task_seed_binding_sha256": (
                adjudication.bls_replay_ordered_task_seed_binding_sha256
            ),
            "bls_replay_stable_projection_sha256": (
                adjudication.bls_replay_stable_projection_sha256
            ),
            "candidate_archive_sha256": adjudication.candidate_archive_sha256,
            "candidate_bundle_sha256": candidate_bundle_sha,
            "candidate_file_sha256": candidate_file_sha,
            "candidate_protocol_receipt_sha256": final.receipt_sha256,
            "commitment_sha256": preregistration.commitment.commitment_sha256,
            "evidence_adjudication_receipt_sha256": adjudication.receipt_sha256,
            "github_chronology_receipt_sha256": chronology.receipt_sha256,
            "prereg_file_sha256": preregistration.prereg_file_sha256,
            "preregistration_sha256": preregistration.preregistration_sha256,
            "protocol_contract_sha256": preregistration.protocol_contract_sha256,
            "registration_carrier_sha256": carrier.carrier_sha256,
            "registration_commit_b": carrier.registration_commit_b,
            "registration_core_sha256": preregistration.registration_core_sha256,
            "source_commit_a": SOURCE_COMMIT_A,
            "task_seed_binding_sha256": ordered_seed_sha,
            "workflow_run_uniqueness_sha256": uniqueness_sha,
        }
        if data.get("internal_bindings") != expected_internal:
            raise SWM0WEvidenceError("ontology internal_bindings drift")

        return {
            **expected_internal,
            "candidate_outcome": final.outcome.value,
            "capacity_independent_phrase_allowed": True,
            "evidence_verdict": adjudication.evidence_verdict,
            "reason_codes": adjudication.reason_codes,
            "task_count": len(tasks),
            "trust_boundary": adjudication.trust_boundary,
            "validated": adjudication.validated,
        }
    except SWM0WEvidenceError:
        raise
    except (
        OSError,
        beacon.SWM0WBeaconError,
        confirmatory.SWM0WConfirmatoryError,
        protocol.SWM0WProtocolError,
    ) as exc:
        raise SWM0WEvidenceError("SWM-0W receipt replay failed") from exc


def _authority_scope(authority_class: str) -> str:
    if authority_class == "SECONDARY_AI":
        return "HSWM_SWM0W_SCALAR_GATE_PASS_EVIDENCE_2026_08_20"
    if authority_class == "SYSTEM_DERIVED":
        return "KG_PUBLICATION_DERIVATION"
    raise SWM0WEvidenceError(f"forbidden authority class: {authority_class}")


def _expected_node_properties(
    row: Mapping[str, Any], bundle_file_sha256: str
) -> dict[str, Any]:
    logical = row["properties"]
    labels = set(row["labels"])
    authority = logical["authority_class"]
    if authority != "SECONDARY_AI":
        raise SWM0WEvidenceError(f"new node is not SECONDARY_AI: {row['uid']}")
    upper_uid = (
        "sym:KG_KNOW:informationentity"
        if labels & {"Artifact", "Evidence", "ResearchArtifact", "Result"}
        else "sym:KG_KNOW:conceptualentity"
    )
    return {
        "uid": row["uid"],
        **logical,
        "ontology_bundle_uid": BUNDLE_UID,
        "ontology_bundle_file_sha256": bundle_file_sha256,
        "ontology_source_sha256": logical["source_sha256"],
        "ontology_kind_v1": logical["ontology_kind"],
        "ontology_plane_v1": logical["ontology_plane"],
        "ontology_domain_v1": logical["ontology_domain"],
        "ontology_upper_uid_v1": upper_uid,
        "ontology_semantic_roles_v1": logical.get("semantic_roles", []),
        "ontology_authority_class_v1": authority,
        "ontology_authority_scope_v1": _authority_scope(authority),
        "ontology_canonical_scope_v1": logical["canonical_scope"],
        "ontology_record_lifecycle_v1": logical["record_lifecycle"],
        "ontology_workflow_state_v1": "NOT_APPLICABLE",
        "ontology_epistemic_state_v1": logical["epistemic_state"],
        "ontology_review_required_v1": logical["review_required"],
    }


def _expected_relation_properties(row: Mapping[str, Any]) -> dict[str, Any]:
    authority = row["authority_class"]
    result = {
        "ontology_bundle_uid": BUNDLE_UID,
        "authority_class": authority,
        "authority": authority,
        "scope": _authority_scope(authority),
        "status": row["status"],
    }
    for key in ("claim_scope", "validation_scope"):
        if key in row:
            result[key] = row[key]
    return result


@dataclass(frozen=True)
class ValidatedBundle:
    data: dict[str, Any]
    ontology_path: Path
    bundle_file_sha256: str
    artifact_set_sha256: str
    artifact_hashes: tuple[tuple[str, str], ...]
    expected_nodes: Mapping[str, tuple[tuple[str, ...], Mapping[str, Any]]]
    expected_relations: tuple[Mapping[str, Any], ...]
    internal: Mapping[str, Any]
    replay_sha256: str
    head_commit: str


def _validate_claim_authority(
    nodes: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
    internal: Mapping[str, Any],
) -> None:
    """Keep candidate output separate from the sole evidence authority."""

    expected_uids = {
        BUNDLE_UID,
        EXPERIMENT_UID,
        CODE_UID,
        PREREG_UID,
        CANDIDATE_UID,
        ADJUDICATION_UID,
    }
    by_uid = {row["uid"]: row for row in nodes}
    if set(by_uid) != expected_uids:
        raise SWM0WEvidenceError("SWM-0W node UID set drift")
    candidate = by_uid[CANDIDATE_UID]["properties"]
    if (
        candidate.get("status") != "CANDIDATE_ONLY"
        or candidate.get("scientific_status") != "UNJUDGED"
        or candidate.get("candidate_protocol_outcome")
        != "CANDIDATE_PASS_AWAITING_BUNDLE"
        or candidate.get("canonical_set_to_set_w_claim") is not False
        or any(
            key in candidate
            for key in ("evidence_verdict", "verdict", "validated", "reason_codes", "trust_boundary")
        )
    ):
        raise SWM0WEvidenceError("candidate-only authority boundary drift")

    adjudication = by_uid[ADJUDICATION_UID]["properties"]
    expected_adjudication = {
        "evidence_verdict": internal["evidence_verdict"],
        "validated": internal["validated"],
        "reason_codes": list(internal["reason_codes"]),
        "trust_boundary": internal["trust_boundary"],
        "capacity_independent_phrase_allowed": internal[
            "capacity_independent_phrase_allowed"
        ],
    }
    if any(adjudication.get(key) != value for key, value in expected_adjudication.items()):
        raise SWM0WEvidenceError("evidence adjudication authority fields drift")
    if (
        adjudication.get("scientific_status") != "SUPPORTED_NARROW"
        or adjudication.get("claim_scope")
        != "FIXED_THREE_SINGLETON_ROLE_SCALAR_PRECURSOR_ONLY"
        or adjudication.get("canonical_set_to_set_w_claim") is not False
    ):
        raise SWM0WEvidenceError("evidence adjudication claim boundary drift")
    for uid, row in by_uid.items():
        if uid == ADJUDICATION_UID:
            continue
        forbidden = {
            "evidence_verdict",
            "validated",
            "reason_codes",
            "trust_boundary",
        } & set(row["properties"])
        if forbidden:
            raise SWM0WEvidenceError(
                f"non-adjudication node owns evidence authority fields: {uid}"
            )

    evidence_edges = [row for row in relations if row.get("type") == "EVIDENCE_FOR"]
    if evidence_edges != [
        {
            "from_uid": ADJUDICATION_UID,
            "type": "EVIDENCE_FOR",
            "to_uid": ANCHOR_UID,
            "authority_class": "SECONDARY_AI",
            "status": "ACTIVE",
            "claim_scope": "FIXED_THREE_SINGLETON_ROLE_SCALAR_PRECURSOR_ONLY",
        }
    ]:
        raise SWM0WEvidenceError("adjudication must be the sole EVIDENCE_FOR owner")


def validate_bundle(
    ontology_path: Path,
    repo_root: Path,
    *,
    require_tracked_head: bool = False,
    verify_replay: bool = True,
) -> ValidatedBundle:
    """Validate every local byte, internal digest, authority, and graph row."""

    repo_root = repo_root.resolve()
    ontology_path = ontology_path.resolve()
    try:
        ontology_relative = ontology_path.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise SWM0WEvidenceError("ontology bundle must live inside the repository") from exc
    data = load_json(ontology_path)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SWM0WEvidenceError(f"unsupported schema_version: {data.get('schema_version')!r}")
    if data.get("bundle_uid") != BUNDLE_UID:
        raise SWM0WEvidenceError("bundle_uid drift")
    _validate_local_anchor(data, repo_root)

    bindings = _binding_map(data)
    artifact_hashes: list[tuple[str, str]] = []
    for relative, row in sorted(bindings.items()):
        normalized, resolved = _resolve_repo_file(
            repo_root, relative, f"artifact binding {relative}"
        )
        observed = file_sha256(resolved)
        if observed != row["sha256"]:
            raise SWM0WEvidenceError(
                f"artifact SHA-256 mismatch: {relative} expected={row['sha256']} actual={observed}"
            )
        artifact_hashes.append((normalized, observed))

    internal = _validate_cross_bindings(
        data,
        repo_root,
        bindings,
        verify_replay=verify_replay,
    )
    bundle_file_digest = file_sha256(ontology_path)
    head_commit = _head_commit(repo_root)
    if require_tracked_head:
        for relative, digest in artifact_hashes:
            _verify_tracked_head(repo_root, relative, digest)
        _verify_tracked_head(repo_root, ontology_relative, bundle_file_digest)

    nodes = data.get("nodes")
    relations = data.get("relations")
    if not isinstance(nodes, list) or not nodes:
        raise SWM0WEvidenceError("nodes must be a non-empty list")
    if not isinstance(relations, list) or not relations:
        raise SWM0WEvidenceError("relations must be a non-empty list")
    node_uids = [row.get("uid") for row in nodes]
    anchor_uids = [row["uid"] for row in data["anchors"]]
    duplicates = [
        uid for uid, count in Counter(node_uids + anchor_uids).items() if count > 1
    ]
    if duplicates:
        raise SWM0WEvidenceError(f"duplicate node or anchor UIDs: {duplicates}")
    if BUNDLE_UID not in node_uids:
        raise SWM0WEvidenceError("bundle_uid must identify a new node")

    labels: set[str] = set()
    expected_nodes: dict[str, tuple[tuple[str, ...], Mapping[str, Any]]] = {}
    for row in nodes:
        if not isinstance(row, dict) or not isinstance(row.get("uid"), str):
            raise SWM0WEvidenceError("node rows require string UIDs")
        row_labels = row.get("labels")
        properties = row.get("properties")
        if not isinstance(row_labels, list) or not row_labels:
            raise SWM0WEvidenceError(f"node has invalid labels: {row['uid']}")
        if len(set(row_labels)) != len(row_labels):
            raise SWM0WEvidenceError(f"node has duplicate labels: {row['uid']}")
        if not isinstance(properties, dict) or not properties.get("name"):
            raise SWM0WEvidenceError(f"node has invalid properties: {row['uid']}")
        invalid = [key for key, value in properties.items() if not _is_neo4j_property(value)]
        if invalid:
            raise SWM0WEvidenceError(
                f"node has unsupported Neo4j properties {row['uid']}: {sorted(invalid)}"
            )
        labels.update(row_labels)
        expected_nodes[row["uid"]] = (
            tuple(row_labels),
            _expected_node_properties(row, bundle_file_digest),
        )
    unsafe_labels = sorted(label for label in labels if not SAFE_LABEL.fullmatch(label))
    if unsafe_labels or not labels <= FROZEN_LABELS:
        invalid_labels = unsafe_labels or sorted(labels - FROZEN_LABELS)
        raise SWM0WEvidenceError(
            f"labels are unsafe or outside frozen registry subset: {invalid_labels}"
        )

    known_uids = set(node_uids + anchor_uids)
    relation_keys: list[tuple[str, str, str]] = []
    relation_types: set[str] = set()
    expected_relations: list[Mapping[str, Any]] = []
    for row in relations:
        if not isinstance(row, dict):
            raise SWM0WEvidenceError("relation rows must be objects")
        key = (row.get("from_uid"), row.get("type"), row.get("to_uid"))
        if not all(isinstance(item, str) for item in key):
            raise SWM0WEvidenceError("relation endpoints and type must be strings")
        if key[0] not in known_uids or key[2] not in known_uids:
            raise SWM0WEvidenceError(f"relation has unknown endpoint: {key}")
        if row.get("authority_class") not in {"SECONDARY_AI", "SYSTEM_DERIVED"}:
            raise SWM0WEvidenceError(f"forbidden relation authority: {key}")
        relation_keys.append(key)
        relation_types.add(key[1])
        expected_relations.append(
            {
                "from_uid": key[0],
                "type": key[1],
                "to_uid": key[2],
                "properties": _expected_relation_properties(row),
            }
        )
    duplicate_relations = [
        key for key, count in Counter(relation_keys).items() if count > 1
    ]
    if duplicate_relations:
        raise SWM0WEvidenceError(f"duplicate relations: {duplicate_relations}")
    unsafe_relations = sorted(
        relation for relation in relation_types if not SAFE_RELATION.fullmatch(relation)
    )
    if unsafe_relations or not relation_types <= FROZEN_RELTYPES:
        raise SWM0WEvidenceError(
            "relations are unsafe or outside frozen registry subset: "
            f"{unsafe_relations or sorted(relation_types - FROZEN_RELTYPES)}"
        )
    _validate_claim_authority(nodes, relations, internal)
    replay_sha = internal["candidate_protocol_receipt_sha256"]

    return ValidatedBundle(
        data=data,
        ontology_path=ontology_path,
        bundle_file_sha256=bundle_file_digest,
        artifact_set_sha256=data["artifact_set_sha256"],
        artifact_hashes=tuple(artifact_hashes),
        expected_nodes=expected_nodes,
        expected_relations=tuple(expected_relations),
        internal=internal,
        replay_sha256=replay_sha,
        head_commit=head_commit,
    )


def _without_system_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in properties.items() if key not in SYSTEM_PROPERTY_KEYS}


def assert_exact_node(
    uid: str,
    expected_labels: Sequence[str],
    expected_properties: Mapping[str, Any],
    observed_labels: Sequence[str],
    observed_properties: Mapping[str, Any],
) -> None:
    """Reject ownership collisions and non-exact idempotent node states."""

    if set(observed_labels) != set(expected_labels):
        raise SWM0WEvidenceError(f"node label collision or drift: {uid}")
    cleaned = _without_system_properties(observed_properties)
    if cleaned != dict(expected_properties):
        raise SWM0WEvidenceError(f"node property collision or drift: {uid}")


def assert_exact_relation(
    key: tuple[str, str, str],
    expected_properties: Mapping[str, Any],
    observed_properties: Mapping[str, Any],
) -> None:
    """Reject relation hijacking and non-exact idempotent relation states."""

    cleaned = _without_system_properties(observed_properties)
    if cleaned != dict(expected_properties):
        raise SWM0WEvidenceError(f"relationship collision or drift: {key}")


def _registry_and_anchor_readback(tx: Any, bundle: ValidatedBundle) -> None:
    registry = tx.run(
        "MATCH (r:SchemaRegistry {uid:$uid}) "
        "RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations",
        uid=REGISTRY_UID,
    ).single()
    if not registry:
        raise SWM0WEvidenceError(f"KG schema registry not found: {REGISTRY_UID}")
    wanted_labels = {
        label for labels, _properties in bundle.expected_nodes.values() for label in labels
    }
    wanted_relations = {row["type"] for row in bundle.expected_relations}
    missing_labels = wanted_labels - set(registry["labels"] or [])
    missing_relations = wanted_relations - set(registry["relations"] or [])
    if missing_labels or missing_relations:
        raise SWM0WEvidenceError(
            f"unregistered schema tokens: labels={sorted(missing_labels)}, "
            f"relations={sorted(missing_relations)}"
        )

    rows = tx.run(
        "MATCH (n {uid:$uid}) "
        "RETURN labels(n) AS labels, properties(n) AS properties, elementId(n) AS eid",
        uid=ANCHOR_UID,
    ).data()
    if len(rows) != 1:
        raise SWM0WEvidenceError("remote SWM-0 anchor is missing or non-unique")
    row = rows[0]
    properties = row["properties"]
    if (
        set(row["labels"]) != {"Plan", "ImplementationPlan"}
        or properties.get("name") != "SWM-0 — n-ary non-collapse witness"
        or properties.get("ontology_authority_class_v1") != "SECONDARY_AI"
        or properties.get("implementation_stage") != "SWM-0"
    ):
        raise SWM0WEvidenceError("remote read-only SWM-0 anchor drift")


def _node_rows(tx: Any, uids: Sequence[str]) -> list[dict[str, Any]]:
    return tx.run(
        "MATCH (n) WHERE n.uid IN $uids "
        "RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties, "
        "elementId(n) AS eid",
        uids=list(uids),
    ).data()


def _relation_rows(tx: Any, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    relation_type = row["type"]
    if not SAFE_RELATION.fullmatch(relation_type):
        raise SWM0WEvidenceError(f"unsafe relationship type: {relation_type}")
    return tx.run(
        "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
        f"MATCH (a)-[r:{relation_type}]->(b) "
        "RETURN properties(r) AS properties, elementId(r) AS eid",
        from_uid=row["from_uid"],
        to_uid=row["to_uid"],
    ).data()


def _exact_remote_readback(tx: Any, bundle: ValidatedBundle) -> dict[str, int]:
    node_rows = _node_rows(tx, list(bundle.expected_nodes))
    counts = Counter(row["uid"] for row in node_rows)
    if set(counts) != set(bundle.expected_nodes) or any(count != 1 for count in counts.values()):
        raise SWM0WEvidenceError(f"exact node readback mismatch: {dict(counts)}")
    for row in node_rows:
        labels, properties = bundle.expected_nodes[row["uid"]]
        assert_exact_node(
            row["uid"], labels, properties, row["labels"], row["properties"]
        )

    relation_count = 0
    for relation in bundle.expected_relations:
        rows = _relation_rows(tx, relation)
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        if len(rows) != 1:
            raise SWM0WEvidenceError(f"exact relationship readback mismatch: {key}")
        assert_exact_relation(key, relation["properties"], rows[0]["properties"])
        relation_count += 1

    owned_nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$bundle_uid}) RETURN count(n) AS count",
        bundle_uid=BUNDLE_UID,
    ).single()["count"]
    owned_relations = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$bundle_uid}]->() RETURN count(r) AS count",
        bundle_uid=BUNDLE_UID,
    ).single()["count"]
    if owned_nodes != len(bundle.expected_nodes) or owned_relations != relation_count:
        raise SWM0WEvidenceError(
            "bundle ownership count drift: "
            f"nodes={owned_nodes} relations={owned_relations}"
        )
    return {"readback_nodes": owned_nodes, "readback_relations": owned_relations}


def _publish_transaction(tx: Any, bundle: ValidatedBundle) -> dict[str, int]:
    _registry_and_anchor_readback(tx, bundle)
    existing_rows = _node_rows(tx, list(bundle.expected_nodes))
    counts = Counter(row["uid"] for row in existing_rows)
    duplicates = {uid: count for uid, count in counts.items() if count > 1}
    if duplicates:
        raise SWM0WEvidenceError(f"duplicate remote KG UIDs: {duplicates}")
    existing = {row["uid"]: row for row in existing_rows}
    for uid, row in existing.items():
        labels, properties = bundle.expected_nodes[uid]
        assert_exact_node(uid, labels, properties, row["labels"], row["properties"])

    relation_existing: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for relation in bundle.expected_relations:
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        rows = _relation_rows(tx, relation)
        if len(rows) > 1:
            raise SWM0WEvidenceError(f"duplicate existing relationship: {key}")
        if rows:
            assert_exact_relation(key, relation["properties"], rows[0]["properties"])
        relation_existing[key] = rows

    created_nodes = 0
    for uid, (labels, properties) in bundle.expected_nodes.items():
        if uid in existing:
            continue
        label_clause = ":".join(labels)
        tx.run(
            f"CREATE (n:{label_clause}) "
            "SET n=$properties, n.createdAt=datetime() RETURN elementId(n) AS eid",
            properties=dict(properties),
        ).single()
        created_nodes += 1

    created_relations = 0
    for relation in bundle.expected_relations:
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        if relation_existing[key]:
            continue
        tx.run(
            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
            f"CREATE (a)-[r:{relation['type']}]->(b) "
            "SET r=$properties, r.createdAt=datetime() RETURN elementId(r) AS eid",
            from_uid=relation["from_uid"],
            to_uid=relation["to_uid"],
            properties=dict(relation["properties"]),
        ).single()
        created_relations += 1

    _exact_remote_readback(tx, bundle)
    return {
        "created_nodes": created_nodes,
        "created_relations": created_relations,
        "existing_nodes": len(bundle.expected_nodes) - created_nodes,
        "existing_relations": len(bundle.expected_relations) - created_relations,
    }


def _connect(config: Mapping[str, str]) -> Any:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover
        raise SWM0WEvidenceError("remote access requires the optional kg dependency") from exc
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    driver.verify_connectivity()
    return driver


def publish(bundle: ValidatedBundle, config: Mapping[str, str]) -> dict[str, int]:
    """Create missing owned rows, then read back from a new post-commit session."""

    driver = _connect(config)
    try:
        with driver.session(database=config["database"]) as write_session:
            write_result = write_session.execute_write(_publish_transaction, bundle)
        with driver.session(database=config["database"]) as read_session:
            read_result = read_session.execute_read(_exact_remote_readback, bundle)
        return {**write_result, **read_result}
    finally:
        driver.close()


def readback(bundle: ValidatedBundle, config: Mapping[str, str]) -> dict[str, int]:
    """Perform a registry/anchor check and exact read-only bundle readback."""

    driver = _connect(config)
    try:
        with driver.session(database=config["database"]) as session:
            def operation(tx: Any) -> dict[str, int]:
                _registry_and_anchor_readback(tx, bundle)
                return _exact_remote_readback(tx, bundle)

            return session.execute_read(operation)
    finally:
        driver.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ontology",
        type=Path,
        default=repo_root
        / "ontology"
        / "identity"
        / "human_universal_body"
        / "HSWM_SWM0W_EVIDENCE_BUNDLE.v1.json",
    )
    parser.add_argument("--source-config", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--readback-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    require_tracked = args.apply or args.readback_only
    bundle = validate_bundle(
        args.ontology,
        repo_root,
        require_tracked_head=require_tracked,
        verify_replay=True,
    )
    base = {
        "adjudication_receipt_sha256": bundle.internal[
            "evidence_adjudication_receipt_sha256"
        ],
        "artifact_set_sha256": bundle.artifact_set_sha256,
        "artifacts": len(bundle.artifact_hashes),
        "bundle_file_sha256": bundle.bundle_file_sha256,
        "candidate_file_sha256": bundle.internal["candidate_file_sha256"],
        "head_commit": bundle.head_commit,
        "nodes": len(bundle.expected_nodes),
        "registration_commit_b": bundle.internal["registration_commit_b"],
        "relations": len(bundle.expected_relations),
        "replay_sha256": bundle.replay_sha256,
        "scientific_status": "SUPPORTED_NARROW",
        "source_commit_a": bundle.internal["source_commit_a"],
        "verdict": bundle.internal["evidence_verdict"],
    }
    if not args.apply and not args.readback_only:
        print(json.dumps({**base, "status": "VALIDATED_ONLY"}, sort_keys=True))
        return 0
    if args.source_config is None:
        raise SystemExit("--apply/--readback-only requires --source-config")
    config = read_flat_yaml(args.source_config.expanduser())
    if args.readback_only:
        result = readback(bundle, config)
        status = "EXACT_READBACK_VERIFIED"
    else:
        result = publish(bundle, config)
        status = "APPLIED_AND_POSTCOMMIT_READ_BACK"
    print(json.dumps({**base, **result, "status": status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ADJUDICATION_UID",
    "ANCHOR_UID",
    "BUNDLE_UID",
    "CANDIDATE_UID",
    "CODE_UID",
    "EXPERIMENT_UID",
    "FROZEN_LABELS",
    "FROZEN_RELTYPES",
    "PREREG_UID",
    "REGISTRY_UID",
    "SCHEMA_VERSION",
    "SWM0WEvidenceError",
    "ValidatedBundle",
    "assert_exact_node",
    "assert_exact_relation",
    "canonical_sha256",
    "file_sha256",
    "load_json",
    "main",
    "readback",
    "validate_bundle",
]
