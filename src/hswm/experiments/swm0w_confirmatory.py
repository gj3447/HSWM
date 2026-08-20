"""Operational chronology and sealed-run adapter for the SWM-0W scalar gate.

This module is deliberately narrower than the scientific protocol.  It checks
one preregistration hash DAG, one source-freeze commit pair, one GitHub Actions
registration carrier, and one exact future Quicknet pulse before constructing
the protocol-owned ``ConfirmatoryAdmissionV1``.  It never turns Git commit
timestamps into evidence and never upgrades the beacon module's deliberately
false ``chronology_claim_allowed`` field.

The strongest chronology statement produced here is conditional:
``GITHUB_OPERATIONAL_CHRONOLOGY_OBSERVED``.  GitHub's control plane, hosted
runner, TLS/API responses, and the pinned local Node executable remain trusted.
A structurally valid admission object made by hand is not evidence.  The
``confirm`` command emits only a candidate package.  Only a later
``adjudicate`` job may map its protocol candidate to PASS/KILL/INCONCLUSIVE,
after re-querying GitHub, observing the completed confirm job, downloading the
exact immutable candidate archive by id, checking the server digest, and
replaying all 20 task receipts and the reducer without training.  A reader must
repeat those live GitHub queries; embedded API JSON and self-hashes alone are
not external authority.  The matching-run list proves only the sole surviving
GitHub record: because a repository owner can delete workflow runs, it is not
an absolute append-only proof that no deleted historical execution existed.
Likewise, a missing/unreadable adjudication artifact is VOID/no evidence and
can never be interpreted as PASS; runner, action, or artifact-service outages
can prevent any receipt from being published at all.

No preregistration, future round, or result is created at import time.  The CLI
writes only explicit output paths and the online path requires an explicit
flag.  Confirmatory execution is single-process and has no post-pulse resume.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from hswm.experiments import swm0w_beacon as beacon
from hswm.experiments import swm0w_protocol as protocol
from hswm.experiments import swm0w_task_family as task_family


PREREGISTRATION_SCHEMA = "hswm-swm0w-preregistration/v1"
REGISTRATION_CORE_SCHEMA = "hswm-swm0w-registration-core/v1"
TRACKED_BYTES_SCHEMA = "hswm-swm0w-tracked-bytes-manifest/v1"
REGISTRATION_CARRIER_SCHEMA = "hswm-swm0w-registration-carrier/v1"
GITHUB_CHRONOLOGY_SCHEMA = "hswm-swm0w-github-operational-chronology/v1"
CANDIDATE_BUNDLE_SCHEMA = "hswm-swm0w-candidate-result-bundle/v1"
ADJUDICATION_SCHEMA = "hswm-swm0w-evidence-adjudication/v1"
OPERATIONAL_VOID_SCHEMA = "hswm-swm0w-operational-void/v1"
EVIDENCE_TRUST_BOUNDARY = (
    "GITHUB_OPERATIONAL_CHRONOLOGY_REPLAYED;PINNED_NODE_BLS_RECEIPT_REPLAYED;"
    "SOLE_SURVIVING_MATCHING_WORKFLOW_RUN_REPLAYED;"
    "REPOSITORY_OWNER_HAS_NOT_DELETED_MATCHING_RUNS;"
    "HOSTED_RUNNER_GITHUB_CONTROL_PLANE_TLS_AND_LOCAL_PYTHON_REMAIN_TRUSTED;"
    "NOT_AN_ABSOLUTE_CRYPTOGRAPHIC_TIMESTAMP"
)
CANDIDATE_TRUST_BOUNDARY = (
    "CANDIDATE_ONLY_NOT_AUTHORITATIVE;ADJUDICATION_MUST_REQUERY_GITHUB_AND_"
    "DOWNLOAD_THE_IMMUTABLE_CANDIDATE_ARTIFACT_BY_EXACT_ID_AND_DIGEST"
)

EXPECTED_REPOSITORY = "gj3447/HSWM"
EXPECTED_REF = "refs/heads/main"
EXPECTED_EVENT = "push"
WORKFLOW_PATH = ".github/workflows/swm0w-confirmatory.yml"
PREREGISTRATION_PATH = "prereg/PREREG_SWM0W_SCALAR_GATE_V1.json"
CLAIM_SCOPE = "FIXED_THREE_SINGLETON_ROLE_SCALAR_PRECURSOR_ONLY"
REGISTRATION_COMMIT_RULE = "DIRECT_CHILD_ADD_ONLY"
CHRONOLOGY_PROVIDER = "GITHUB_ACTIONS_OPERATIONAL_V1"
CHRONOLOGY_STATUS = "GITHUB_OPERATIONAL_CHRONOLOGY_OBSERVED"
RUNTIME_TRUST_STATUS = "TRUSTED_GITHUB_HOSTED_OS_AND_PINNED_NODE_RUNTIME_REQUIRED"

NODE_VERSION = "v24.13.0"
NODE_ARCHIVE_SHA256 = "e798599612f4bb71333a3397ab0d095fd62214e115aea45aa858a145fc72d67e"
NODE_EXECUTABLE_SHA256 = (
    "53fb205ae78805130177e24bcb459a69a1518c8d98f8965f31d85aae7ea840fc"
)
RUNNER_LABEL = "ubuntu-24.04"
RUNNER_OS = "Linux"
RUNNER_ARCH = "X64"

MINIMUM_DECLARED_LEAD_SECONDS = 900
MINIMUM_ARTIFACT_LEAD_SECONDS = 60
MAX_DECLARED_TO_RUN_CREATED_SECONDS = 600
NETWORK_RETRY_COUNT = 3
NETWORK_RETRY_DELAY_SECONDS = 5
WAIT_POLL_SECONDS = 15
MAX_REGISTRATION_ARCHIVE_BYTES = 4 * 1024 * 1024
MAX_CANDIDATE_ARCHIVE_BYTES = 64 * 1024 * 1024
REGISTRATION_ARCHIVE_MEMBERS = (
    "github_run.json",
    "github_workflow_runs.json",
    "registration_carrier.json",
)
CANDIDATE_ARCHIVE_MEMBERS = ("candidate_bundle.json",)
BEACON_OFFLINE_FIXTURE_SCHEMA = "hswm-swm0w-drand-official-pulse-fixture/v1"

REQUIRED_SOURCE_PATHS = (
    WORKFLOW_PATH,
    "src/hswm/experiments/swm0w_beacon.py",
    "src/hswm/experiments/swm0w_confirmatory.py",
    "src/hswm/experiments/swm0w_operator.py",
    "src/hswm/experiments/swm0w_protocol.py",
    "src/hswm/experiments/swm0w_task_family.py",
    "src/hswm/experiments/swm0w_worlds.py",
    "tools/swm0w_drand/package.json",
    "tools/swm0w_drand/package-lock.json",
    "tools/swm0w_drand/verify-beacon.mjs",
    "uv.lock",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_EXPERIMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RFC3339_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class SWM0WConfirmatoryError(ValueError):
    """Raised before any drifted chronology can authorize measurement."""


def canonical_json(value: Any) -> str:
    """Use the beacon canonicalizer for every cross-layer hash."""

    return beacon.canonical_json(value)


def canonical_sha256(value: Any) -> str:
    return beacon.canonical_sha256(value)


def file_sha256_bytes(value: bytes) -> str:
    if type(value) is not bytes:
        raise SWM0WConfirmatoryError("file hashing requires exact bytes")
    return sha256(value).hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SWM0WConfirmatoryError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _load_json_bytes(value: bytes, name: str) -> Any:
    if type(value) is not bytes:
        raise SWM0WConfirmatoryError(f"{name} must be exact bytes")
    try:
        return json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                SWM0WConfirmatoryError(
                    f"{name} contains a forbidden numeric token: {token}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SWM0WConfirmatoryError(f"{name} is not valid UTF-8 JSON") from exc


def parse_canonical_json_object_bytes(value: bytes, *, name: str) -> dict[str, Any]:
    parsed = _load_json_bytes(value, name)
    if type(parsed) is not dict:
        raise SWM0WConfirmatoryError(f"{name} must be one exact JSON object")
    if value != (canonical_json(parsed) + "\n").encode("utf-8"):
        raise SWM0WConfirmatoryError(f"{name} must be canonical JSON plus one newline")
    return parsed


def _freeze_json(value: Any) -> Any:
    """Detach and recursively freeze one already validated JSON value."""

    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise SWM0WConfirmatoryError("JSON object keys must be exact strings")
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or type(value) in {str, int, bool, float}:
        if type(value) is float and not math.isfinite(value):
            raise SWM0WConfirmatoryError("JSON values must be finite")
        return value
    raise SWM0WConfirmatoryError(f"unsupported JSON value type: {type(value)!r}")


def _exact_json_equal(actual: Any, expected: Any) -> bool:
    """Compare JSON values without Python's bool/int or int/float coercions."""

    if type(actual) is not type(expected):
        return False
    if type(actual) is dict:
        return set(actual) == set(expected) and all(
            type(key) is str and _exact_json_equal(actual[key], expected[key])
            for key in actual
        )
    if type(actual) is list:
        return len(actual) == len(expected) and all(
            _exact_json_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    if actual is None or type(actual) in {str, int, bool}:
        return actual == expected
    if type(actual) is float:
        return math.isfinite(actual) and actual.hex() == expected.hex()
    return False


def _require_exact_json(actual: Any, expected: Any, name: str) -> None:
    if not _exact_json_equal(actual, expected):
        raise SWM0WConfirmatoryError(
            f"{name} differs in value or exact JSON primitive/container type"
        )


def _require_exact_keys(
    value: Any, expected: Sequence[str], name: str
) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != set(expected):
        raise SWM0WConfirmatoryError(f"{name} keys do not match the frozen schema")
    return value


def _require_sha256(value: Any, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise SWM0WConfirmatoryError(f"{name} must be lowercase SHA-256")
    return value


def _require_git_sha(value: Any, name: str) -> str:
    if type(value) is not str or not _GIT_SHA_RE.fullmatch(value):
        raise SWM0WConfirmatoryError(f"{name} must be a 40-character Git object id")
    return value


def _require_experiment_id(value: Any) -> str:
    if type(value) is not str or not _EXPERIMENT_RE.fullmatch(value):
        raise SWM0WConfirmatoryError("experiment_id has an invalid form")
    return value


def _require_int(value: Any, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise SWM0WConfirmatoryError(f"{name} must be an integer >= {minimum}")
    return value


def _require_string(value: Any, name: str) -> str:
    if type(value) is not str or not value:
        raise SWM0WConfirmatoryError(f"{name} must be a nonempty string")
    return value


def _timestamp(value: Any, name: str) -> int:
    if type(value) is not str or not _RFC3339_RE.fullmatch(value):
        raise SWM0WConfirmatoryError(f"{name} must be second-resolution UTC RFC3339")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise SWM0WConfirmatoryError(f"{name} is not a real UTC timestamp") from exc
    return int(parsed.timestamp())


def _run_git(
    repo_root: Path,
    arguments: Sequence[str],
    *,
    input_bytes: bytes | None = None,
) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            input=input_bytes,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise SWM0WConfirmatoryError("Git is unavailable") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()[-500:]
        raise SWM0WConfirmatoryError(f"Git validation failed: {detail}")
    return completed.stdout


def validate_artifact_archive(
    archive_bytes: bytes,
    *,
    expected_digest: str,
    expected_members: Sequence[str],
    maximum_bytes: int,
) -> Mapping[str, bytes]:
    """Validate GitHub's immutable ZIP bytes before exposing any member."""

    if type(archive_bytes) is not bytes:
        raise SWM0WConfirmatoryError("artifact archive must be exact bytes")
    if not 1 <= len(archive_bytes) <= maximum_bytes:
        raise SWM0WConfirmatoryError("artifact archive exceeds its frozen size bound")
    digest = _require_sha256(expected_digest, "artifact archive digest")
    if file_sha256_bytes(archive_bytes) != digest:
        raise SWM0WConfirmatoryError("downloaded archive/API digest mismatch")
    if type(expected_members) not in {tuple, list}:
        raise SWM0WConfirmatoryError("expected archive members must be ordered names")
    expected = tuple(expected_members)
    if (
        not expected
        or tuple(sorted(expected)) != expected
        or len(set(expected)) != len(expected)
    ):
        raise SWM0WConfirmatoryError(
            "expected artifact members must be unique and sorted"
        )
    try:
        with ZipFile(BytesIO(archive_bytes), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if tuple(sorted(names)) != expected or len(set(names)) != len(names):
                raise SWM0WConfirmatoryError(
                    "artifact archive member set/order differs from the frozen layout"
                )
            total = 0
            result: dict[str, bytes] = {}
            for info in infos:
                name = info.filename
                path = Path(name)
                unix_mode = (info.external_attr >> 16) & 0o170000
                if (
                    info.is_dir()
                    or path.is_absolute()
                    or "\\" in name
                    or "\x00" in name
                    or any(part in {"", ".", ".."} for part in path.parts)
                    or unix_mode not in {0, 0o100000}
                    or info.file_size < 0
                    or info.file_size > maximum_bytes
                ):
                    raise SWM0WConfirmatoryError("unsafe artifact archive member")
                total += info.file_size
                if total > maximum_bytes:
                    raise SWM0WConfirmatoryError(
                        "expanded artifact archive exceeds its frozen size bound"
                    )
                payload = archive.read(info)
                if len(payload) != info.file_size:
                    raise SWM0WConfirmatoryError("artifact member size mismatch")
                result[name] = payload
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise SWM0WConfirmatoryError("artifact is not a valid bounded ZIP") from exc
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class TrackedBytesManifestV1:
    commit: str
    tree_oid: str
    rows: tuple[tuple[str, str, str, str], ...]
    manifest_sha256: str

    def __post_init__(self) -> None:
        _require_git_sha(self.commit, "tracked commit")
        _require_git_sha(self.tree_oid, "tracked tree")
        if type(self.rows) is not tuple or not self.rows:
            raise SWM0WConfirmatoryError("tracked manifest requires immutable rows")
        paths: list[str] = []
        for row in self.rows:
            if type(row) is not tuple or len(row) != 4:
                raise SWM0WConfirmatoryError("tracked manifest row shape drift")
            mode, object_type, path, digest = row
            if type(mode) is not str or not re.fullmatch(r"[0-7]{6}", mode):
                raise SWM0WConfirmatoryError("tracked file mode is invalid")
            if type(object_type) is not str or object_type not in {"blob", "commit"}:
                raise SWM0WConfirmatoryError("unsupported tracked object type")
            if type(path) is not str or not path or "\x00" in path:
                raise SWM0WConfirmatoryError("tracked path is invalid")
            _require_sha256(digest, "tracked object sha256")
            paths.append(path)
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise SWM0WConfirmatoryError("tracked paths must be unique and sorted")
        _require_sha256(self.manifest_sha256, "tracked manifest sha256")
        if self.manifest_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WConfirmatoryError("tracked manifest hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "commit": self.commit,
            "rows": [
                {
                    "mode": mode,
                    "object_type": object_type,
                    "path": path,
                    "sha256": digest,
                }
                for mode, object_type, path, digest in self.rows
            ],
            "schema_version": TRACKED_BYTES_SCHEMA,
            "tree_oid": self.tree_oid,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "manifest_sha256": self.manifest_sha256}

    def path_sha256(self) -> dict[str, str]:
        return {path: digest for _, _, path, digest in self.rows}


def tracked_bytes_manifest(repo_root: Path, commit: str) -> TrackedBytesManifestV1:
    """Hash exact tracked object bytes at one commit, not mutable worktree bytes."""

    root = Path(repo_root).resolve()
    selected = _require_git_sha(commit, "source commit")
    tree_oid = _run_git(root, ["rev-parse", f"{selected}^{{tree}}"])
    tree = _require_git_sha(tree_oid.decode("ascii").strip(), "source tree")
    listing = _run_git(root, ["ls-tree", "-r", "-z", "--full-tree", selected])
    objects: list[tuple[str, str, str, str]] = []
    for raw in listing.split(b"\x00"):
        if not raw:
            continue
        try:
            metadata, path_bytes = raw.split(b"\t", 1)
            mode_bytes, type_bytes, oid_bytes = metadata.split(b" ", 2)
            mode = mode_bytes.decode("ascii")
            object_type = type_bytes.decode("ascii")
            oid = oid_bytes.decode("ascii")
            path = path_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise SWM0WConfirmatoryError(
                "Git tree contains an unsupported entry"
            ) from exc
        _require_git_sha(oid, f"Git object for {path}")
        if object_type not in {"blob", "commit"}:
            raise SWM0WConfirmatoryError(
                f"unsupported tracked object type for {path}: {object_type}"
            )
        objects.append((mode, object_type, path, oid))

    blob_oids = [oid for _, kind, _, oid in objects if kind == "blob"]
    batch_payload = _run_git(
        root,
        ["cat-file", "--batch"],
        input_bytes=("\n".join(blob_oids) + "\n").encode("ascii"),
    )
    blob_bytes: dict[str, bytes] = {}
    cursor = 0
    for expected_oid in blob_oids:
        header_end = batch_payload.find(b"\n", cursor)
        if header_end < 0:
            raise SWM0WConfirmatoryError("truncated Git batch object header")
        header = batch_payload[cursor:header_end].decode("ascii", errors="strict")
        parts = header.split()
        if len(parts) != 3 or parts[0] != expected_oid or parts[1] != "blob":
            raise SWM0WConfirmatoryError("Git batch object identity/type drift")
        try:
            size = int(parts[2])
        except ValueError as exc:
            raise SWM0WConfirmatoryError("Git batch object size is invalid") from exc
        start = header_end + 1
        end = start + size
        if (
            size < 0
            or end >= len(batch_payload)
            or batch_payload[end : end + 1] != b"\n"
        ):
            raise SWM0WConfirmatoryError("truncated Git batch object payload")
        blob_bytes[expected_oid] = batch_payload[start:end]
        cursor = end + 1
    if cursor != len(batch_payload):
        raise SWM0WConfirmatoryError("unexpected trailing Git batch bytes")

    entries: list[tuple[str, str, str, str]] = []
    for mode, object_type, path, oid in objects:
        # A gitlink tracks the referenced commit id, not mutable checkout bytes.
        payload = blob_bytes[oid] if object_type == "blob" else oid.encode("ascii")
        entries.append((mode, object_type, path, sha256(payload).hexdigest()))
    rows = tuple(sorted(entries, key=lambda row: row[2]))
    unsigned = {
        "commit": selected,
        "rows": [
            {
                "mode": mode,
                "object_type": object_type,
                "path": path,
                "sha256": digest,
            }
            for mode, object_type, path, digest in rows
        ],
        "schema_version": TRACKED_BYTES_SCHEMA,
        "tree_oid": tree,
    }
    return TrackedBytesManifestV1(
        commit=selected,
        tree_oid=tree,
        rows=rows,
        manifest_sha256=canonical_sha256(unsigned),
    )


@dataclass(frozen=True, slots=True)
class ValidatedPreregistrationV1:
    payload: Mapping[str, Any]
    registration_core: Mapping[str, Any]
    commitment: beacon.FutureRoundCommitmentV1
    registration_core_sha256: str
    protocol_contract_sha256: str
    preregistration_sha256: str
    prereg_file_sha256: str
    source_manifest: TrackedBytesManifestV1

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping) or not isinstance(
            self.registration_core, Mapping
        ):
            raise SWM0WConfirmatoryError(
                "validated preregistration mappings are required"
            )
        if type(self.commitment) is not beacon.FutureRoundCommitmentV1:
            raise SWM0WConfirmatoryError(
                "validated preregistration needs exact commitment"
            )
        for field in (
            "registration_core_sha256",
            "protocol_contract_sha256",
            "preregistration_sha256",
            "prereg_file_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        if type(self.source_manifest) is not TrackedBytesManifestV1:
            raise SWM0WConfirmatoryError(
                "validated preregistration needs source manifest"
            )
        # Store recursively immutable detached values; a top-level mapping proxy
        # is insufficient because nested bindings are evidence too.
        object.__setattr__(
            self,
            "payload",
            _freeze_json(
                _load_json_bytes(canonical_json(self.payload).encode(), "payload")
            ),
        )
        object.__setattr__(
            self,
            "registration_core",
            _freeze_json(
                _load_json_bytes(
                    canonical_json(self.registration_core).encode(),
                    "registration core",
                )
            ),
        )

    @property
    def experiment_id(self) -> str:
        return str(self.registration_core["experiment_id"])

    @property
    def repository_binding(self) -> Mapping[str, Any]:
        value = self.registration_core["repository_binding"]
        if not isinstance(value, Mapping):
            raise AssertionError("validated repository binding changed type")
        return value

    @property
    def workflow_binding(self) -> Mapping[str, Any]:
        value = self.registration_core["workflow_binding"]
        if not isinstance(value, Mapping):
            raise AssertionError("validated workflow binding changed type")
        return value


def _validate_registration_core(
    value: Any, repo_root: Path
) -> tuple[Mapping[str, Any], TrackedBytesManifestV1, str]:
    core = _require_exact_keys(
        value,
        (
            "schema_version",
            "experiment_id",
            "claim_scope",
            "repository_binding",
            "workflow_binding",
            "protocol_contract",
            "execution_policy",
            "chronology_policy",
            "runtime_binding",
        ),
        "registration core",
    )
    if core["schema_version"] != REGISTRATION_CORE_SCHEMA:
        raise SWM0WConfirmatoryError("unsupported registration-core schema")
    _require_experiment_id(core["experiment_id"])
    if core["claim_scope"] != CLAIM_SCOPE:
        raise SWM0WConfirmatoryError("registration claim scope drift")

    repository = _require_exact_keys(
        core["repository_binding"],
        (
            "repository",
            "ref",
            "source_commit_a",
            "source_tree_oid",
            "tracked_bytes_manifest_sha256",
            "tracked_file_count",
            "required_file_sha256",
            "registration_commit_rule",
            "preregistration_path",
        ),
        "repository binding",
    )
    if (
        repository["repository"] != EXPECTED_REPOSITORY
        or repository["ref"] != EXPECTED_REF
        or repository["registration_commit_rule"] != REGISTRATION_COMMIT_RULE
        or repository["preregistration_path"] != PREREGISTRATION_PATH
    ):
        raise SWM0WConfirmatoryError("repository/ref/commit rule drift")
    source_commit = _require_git_sha(repository["source_commit_a"], "source_commit_a")
    source_tree = _require_git_sha(repository["source_tree_oid"], "source_tree_oid")
    expected_manifest_sha = _require_sha256(
        repository["tracked_bytes_manifest_sha256"],
        "tracked_bytes_manifest_sha256",
    )
    source_manifest = tracked_bytes_manifest(repo_root, source_commit)
    tracked_file_count = _require_int(
        repository["tracked_file_count"], "tracked_file_count", minimum=1
    )
    if (
        source_manifest.tree_oid != source_tree
        or source_manifest.manifest_sha256 != expected_manifest_sha
        or tracked_file_count != len(source_manifest.rows)
    ):
        raise SWM0WConfirmatoryError("registered tracked source bytes drift")
    required = repository["required_file_sha256"]
    if type(required) is not dict or set(required) != set(REQUIRED_SOURCE_PATHS):
        raise SWM0WConfirmatoryError("required source-path set drift")
    manifest_paths = source_manifest.path_sha256()
    for path in REQUIRED_SOURCE_PATHS:
        expected = _require_sha256(required[path], f"source sha256 for {path}")
        if manifest_paths.get(path) != expected:
            raise SWM0WConfirmatoryError(f"registered source bytes drift: {path}")

    workflow = _require_exact_keys(
        core["workflow_binding"],
        ("path", "sha256", "trigger_event", "trigger_ref", "jobs"),
        "workflow binding",
    )
    _require_exact_json(
        workflow,
        {
            "path": WORKFLOW_PATH,
            "sha256": required[WORKFLOW_PATH],
            "trigger_event": EXPECTED_EVENT,
            "trigger_ref": EXPECTED_REF,
            "jobs": ["register", "confirm", "adjudicate"],
        },
        "workflow binding",
    )

    frozen_contract = protocol.protocol_contract()
    _require_exact_json(
        core["protocol_contract"], frozen_contract, "scientific protocol contract"
    )
    protocol_contract_sha = protocol.canonical_sha256(frozen_contract)

    execution = _require_exact_keys(
        core["execution_policy"],
        (
            "task_count",
            "task_indices",
            "single_process",
            "run_attempt",
            "rerun_allowed",
            "reroll_allowed",
            "post_pulse_resume_allowed",
        ),
        "execution policy",
    )
    _require_exact_json(
        execution,
        {
            "task_count": beacon.TASK_COUNT,
            "task_indices": list(range(beacon.TASK_COUNT)),
            "single_process": True,
            "run_attempt": 1,
            "rerun_allowed": False,
            "reroll_allowed": False,
            "post_pulse_resume_allowed": False,
        },
        "execution policy",
    )

    chronology = _require_exact_keys(
        core["chronology_policy"],
        (
            "provider",
            "minimum_declared_lead_seconds",
            "minimum_registration_artifact_lead_seconds",
            "maximum_declared_to_run_created_seconds",
            "claim",
        ),
        "chronology policy",
    )
    _require_exact_json(
        chronology,
        {
            "provider": CHRONOLOGY_PROVIDER,
            "minimum_declared_lead_seconds": MINIMUM_DECLARED_LEAD_SECONDS,
            "minimum_registration_artifact_lead_seconds": MINIMUM_ARTIFACT_LEAD_SECONDS,
            "maximum_declared_to_run_created_seconds": MAX_DECLARED_TO_RUN_CREATED_SECONDS,
            "claim": CHRONOLOGY_STATUS,
        },
        "chronology policy",
    )

    runtime = _require_exact_keys(
        core["runtime_binding"],
        (
            "runner",
            "runner_os",
            "runner_arch",
            "node_version",
            "node_archive_sha256",
            "node_executable_sha256",
            "runtime_trust_status",
        ),
        "runtime binding",
    )
    _require_exact_json(
        runtime,
        {
            "runner": RUNNER_LABEL,
            "runner_os": RUNNER_OS,
            "runner_arch": RUNNER_ARCH,
            "node_version": NODE_VERSION,
            "node_archive_sha256": NODE_ARCHIVE_SHA256,
            "node_executable_sha256": NODE_EXECUTABLE_SHA256,
            "runtime_trust_status": RUNTIME_TRUST_STATUS,
        },
        "runtime binding",
    )
    return core, source_manifest, protocol_contract_sha


def validate_preregistration_bytes(
    preregistration_bytes: bytes, *, repo_root: Path
) -> ValidatedPreregistrationV1:
    """Validate the noncyclic preregistration and exact commit-A bytes."""

    if type(preregistration_bytes) is not bytes:
        raise SWM0WConfirmatoryError("preregistration input must be exact bytes")
    payload = parse_canonical_json_object_bytes(
        preregistration_bytes, name="preregistration"
    )
    data = _require_exact_keys(
        payload,
        (
            "schema_version",
            "registration_core",
            "registration_core_sha256",
            "future_round_commitment",
            "preregistration_sha256",
        ),
        "preregistration",
    )
    if data["schema_version"] != PREREGISTRATION_SCHEMA:
        raise SWM0WConfirmatoryError("unsupported preregistration schema")
    core, source_manifest, contract_sha = _validate_registration_core(
        data["registration_core"], Path(repo_root)
    )
    core_sha = _require_sha256(
        data["registration_core_sha256"], "registration_core_sha256"
    )
    if core_sha != canonical_sha256(core):
        raise SWM0WConfirmatoryError("registration-core hash mismatch")
    commitment = beacon.parse_future_round_commitment(data["future_round_commitment"])
    if (
        commitment.experiment_id != core["experiment_id"]
        or commitment.registration_evidence_sha256 != core_sha
    ):
        raise SWM0WConfirmatoryError("commitment does not bind the registration core")
    if commitment.round_time_unix - commitment.registered_at_unix < (
        MINIMUM_DECLARED_LEAD_SECONDS
    ):
        raise SWM0WConfirmatoryError("future round lacks the registered lead time")
    prereg_sha = _require_sha256(
        data["preregistration_sha256"], "preregistration_sha256"
    )
    unsigned = dict(data)
    del unsigned["preregistration_sha256"]
    if prereg_sha != canonical_sha256(unsigned):
        raise SWM0WConfirmatoryError("preregistration self-hash mismatch")
    return ValidatedPreregistrationV1(
        payload=data,
        registration_core=core,
        commitment=commitment,
        registration_core_sha256=core_sha,
        protocol_contract_sha256=contract_sha,
        preregistration_sha256=prereg_sha,
        prereg_file_sha256=file_sha256_bytes(preregistration_bytes),
        source_manifest=source_manifest,
    )


def validate_registration_commit_pair(
    preregistration: ValidatedPreregistrationV1,
    *,
    repo_root: Path,
    registration_commit_b: str,
) -> str:
    """Require B to be A plus exactly one newly added preregistration file."""

    if type(preregistration) is not ValidatedPreregistrationV1:
        raise SWM0WConfirmatoryError("commit validation needs exact preregistration")
    root = Path(repo_root).resolve()
    commit_b = _require_git_sha(registration_commit_b, "registration_commit_b")
    commit_a = str(preregistration.repository_binding["source_commit_a"])
    parent_line = _run_git(root, ["rev-list", "--parents", "-n", "1", commit_b])
    parents = parent_line.decode("ascii").strip().split()
    if parents != [commit_b, commit_a]:
        raise SWM0WConfirmatoryError("registration commit B is not a direct child of A")
    diff = _run_git(
        root,
        [
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-z",
            commit_a,
            commit_b,
        ],
    ).split(b"\x00")
    entries = [item.decode("utf-8") for item in diff if item]
    if entries != ["A", PREREGISTRATION_PATH]:
        raise SWM0WConfirmatoryError(
            "registration commit must add only the exact preregistration path"
        )
    committed_bytes = _run_git(root, ["show", f"{commit_b}:{PREREGISTRATION_PATH}"])
    if file_sha256_bytes(committed_bytes) != preregistration.prereg_file_sha256:
        raise SWM0WConfirmatoryError("commit B preregistration bytes drift")
    return commit_b


def _validate_github_run(
    value: Mapping[str, Any],
    *,
    preregistration: ValidatedPreregistrationV1,
    registration_commit_b: str,
    expected_run_id: int,
) -> tuple[str, int]:
    if type(value) is not dict:
        raise SWM0WConfirmatoryError("GitHub run must be an exact JSON object")
    run_id = _require_int(value.get("id"), "GitHub run id", minimum=1)
    attempt = _require_int(value.get("run_attempt"), "GitHub run attempt", minimum=1)
    selected_expected_run_id = _require_int(
        expected_run_id, "expected GitHub run id", minimum=1
    )
    selected_commit = _require_git_sha(registration_commit_b, "registration_commit_b")
    if run_id != selected_expected_run_id or attempt != 1:
        raise SWM0WConfirmatoryError("only the exact first GitHub run is admissible")
    repository = value.get("repository")
    head_repository = value.get("head_repository")
    if (
        type(repository) is not dict
        or repository.get("full_name") != EXPECTED_REPOSITORY
        or type(head_repository) is not dict
        or head_repository.get("full_name") != EXPECTED_REPOSITORY
    ):
        raise SWM0WConfirmatoryError("GitHub run repository/fork binding drift")
    if (
        value.get("event") != EXPECTED_EVENT
        or value.get("head_branch") != "main"
        or value.get("head_sha") != selected_commit
        or value.get("path") != WORKFLOW_PATH
    ):
        raise SWM0WConfirmatoryError("GitHub run event/ref/head/workflow drift")
    created_at = _require_string(value.get("created_at"), "run.created_at")
    created_unix = _timestamp(created_at, "run.created_at")
    commitment = preregistration.commitment
    if not (
        commitment.registered_at_unix
        <= created_unix
        <= commitment.registered_at_unix + MAX_DECLARED_TO_RUN_CREATED_SECONDS
    ):
        raise SWM0WConfirmatoryError(
            "GitHub run time is outside declared-registration skew"
        )
    if created_unix > commitment.round_time_unix - MINIMUM_ARTIFACT_LEAD_SECONDS:
        raise SWM0WConfirmatoryError(
            "GitHub run was not created before the pulse deadline"
        )
    return created_at, created_unix


def _github_run_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    repository = value.get("repository")
    head_repository = value.get("head_repository")
    return {
        "created_at": value.get("created_at"),
        "event": value.get("event"),
        "head_repository": (
            None
            if not isinstance(head_repository, Mapping)
            else head_repository.get("full_name")
        ),
        "head_branch": value.get("head_branch"),
        "head_sha": value.get("head_sha"),
        "id": value.get("id"),
        "path": value.get("path"),
        "repository": (
            None if not isinstance(repository, Mapping) else repository.get("full_name")
        ),
        "run_attempt": value.get("run_attempt"),
    }


def _validate_sole_surviving_workflow_run(
    value: Mapping[str, Any],
    *,
    preregistration: ValidatedPreregistrationV1,
    registration_commit_b: str,
    expected_run_id: int,
) -> dict[str, Any]:
    """Bind the sole live matching run visible in GitHub's control plane.

    GitHub permits repository owners to delete workflow-run records.  This is
    therefore a sole-*surviving*-run check under the explicit repository-owner
    trust boundary, not an absolute append-only historical uniqueness proof.
    """

    data = _require_exact_keys(
        value, ("total_count", "workflow_runs"), "workflow-runs API response"
    )
    total_count = _require_int(
        data["total_count"], "workflow-runs total_count", minimum=0
    )
    rows = data["workflow_runs"]
    if type(rows) is not list or total_count != 1 or len(rows) != 1:
        raise SWM0WConfirmatoryError(
            "selected run is not the sole surviving workflow/head match"
        )
    selected = rows[0]
    if type(selected) is not dict:
        raise SWM0WConfirmatoryError("workflow-runs row must be an exact object")
    _validate_github_run(
        selected,
        preregistration=preregistration,
        registration_commit_b=registration_commit_b,
        expected_run_id=expected_run_id,
    )
    projection = {
        "filter": {
            "branch": "main",
            "event": EXPECTED_EVENT,
            "head_sha": registration_commit_b,
            "workflow": Path(WORKFLOW_PATH).name,
        },
        "selected_run": _github_run_projection(selected),
        "total_count": total_count,
        "trust_boundary": "REPOSITORY_OWNER_HAS_NOT_DELETED_MATCHING_RUNS",
    }
    return projection


@dataclass(frozen=True, slots=True)
class RegistrationCarrierV1:
    experiment_id: str
    repository: str
    ref: str
    event: str
    workflow_path: str
    workflow_sha256: str
    run_id: int
    run_attempt: int
    run_created_at: str
    run_api_sha256: str
    workflow_runs_api_sha256: str
    workflow_run_uniqueness_sha256: str
    source_commit_a: str
    registration_commit_b: str
    registration_core_sha256: str
    protocol_contract_sha256: str
    commitment_sha256: str
    preregistration_sha256: str
    prereg_file_sha256: str
    future_round: int
    round_time_unix: int
    registered_at_unix: int
    chronology_status: str
    carrier_sha256: str

    def __post_init__(self) -> None:
        _require_experiment_id(self.experiment_id)
        if (
            self.repository != EXPECTED_REPOSITORY
            or self.ref != EXPECTED_REF
            or self.event != EXPECTED_EVENT
            or self.workflow_path != WORKFLOW_PATH
            or self.chronology_status != CHRONOLOGY_STATUS
        ):
            raise SWM0WConfirmatoryError("registration carrier fixed fields drift")
        _require_int(self.run_id, "carrier run_id", minimum=1)
        _require_int(self.run_attempt, "carrier run_attempt", minimum=1)
        if self.run_attempt != 1:
            raise SWM0WConfirmatoryError("registration carrier must bind attempt one")
        _timestamp(self.run_created_at, "carrier run_created_at")
        for field in (
            "workflow_sha256",
            "run_api_sha256",
            "workflow_runs_api_sha256",
            "workflow_run_uniqueness_sha256",
            "registration_core_sha256",
            "protocol_contract_sha256",
            "commitment_sha256",
            "preregistration_sha256",
            "prereg_file_sha256",
            "carrier_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        _require_git_sha(self.source_commit_a, "source_commit_a")
        _require_git_sha(self.registration_commit_b, "registration_commit_b")
        _require_int(self.future_round, "future_round", minimum=1)
        _require_int(self.round_time_unix, "round_time_unix", minimum=1)
        _require_int(self.registered_at_unix, "registered_at_unix", minimum=1)
        if self.round_time_unix != beacon.quicknet_round_time(self.future_round):
            raise SWM0WConfirmatoryError("carrier future round/time mismatch")
        if self.carrier_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WConfirmatoryError("registration carrier hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "chronology_status": self.chronology_status,
            "commitment_sha256": self.commitment_sha256,
            "event": self.event,
            "experiment_id": self.experiment_id,
            "future_round": self.future_round,
            "prereg_file_sha256": self.prereg_file_sha256,
            "preregistration_sha256": self.preregistration_sha256,
            "protocol_contract_sha256": self.protocol_contract_sha256,
            "ref": self.ref,
            "registered_at_unix": self.registered_at_unix,
            "registration_commit_b": self.registration_commit_b,
            "registration_core_sha256": self.registration_core_sha256,
            "repository": self.repository,
            "round_time_unix": self.round_time_unix,
            "run_api_sha256": self.run_api_sha256,
            "run_attempt": self.run_attempt,
            "run_created_at": self.run_created_at,
            "run_id": self.run_id,
            "schema_version": REGISTRATION_CARRIER_SCHEMA,
            "source_commit_a": self.source_commit_a,
            "workflow_path": self.workflow_path,
            "workflow_run_uniqueness_sha256": self.workflow_run_uniqueness_sha256,
            "workflow_runs_api_sha256": self.workflow_runs_api_sha256,
            "workflow_sha256": self.workflow_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "carrier_sha256": self.carrier_sha256}


def parse_registration_carrier(value: Mapping[str, Any]) -> RegistrationCarrierV1:
    data = _require_exact_keys(
        value,
        (
            "schema_version",
            "chronology_status",
            "commitment_sha256",
            "event",
            "experiment_id",
            "future_round",
            "prereg_file_sha256",
            "preregistration_sha256",
            "protocol_contract_sha256",
            "ref",
            "registered_at_unix",
            "registration_commit_b",
            "registration_core_sha256",
            "repository",
            "round_time_unix",
            "run_api_sha256",
            "run_attempt",
            "run_created_at",
            "run_id",
            "source_commit_a",
            "workflow_path",
            "workflow_run_uniqueness_sha256",
            "workflow_runs_api_sha256",
            "workflow_sha256",
            "carrier_sha256",
        ),
        "registration carrier",
    )
    if data["schema_version"] != REGISTRATION_CARRIER_SCHEMA:
        raise SWM0WConfirmatoryError("unsupported registration-carrier schema")
    fields = dict(data)
    del fields["schema_version"]
    return RegistrationCarrierV1(**fields)


def build_registration_carrier(
    preregistration: ValidatedPreregistrationV1,
    *,
    repo_root: Path,
    registration_commit_b: str,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    expected_run_id: int,
) -> RegistrationCarrierV1:
    """Construct the exact pre-pulse bytes later uploaded as one artifact."""

    if type(github_run) is not dict or type(github_workflow_runs) is not dict:
        raise SWM0WConfirmatoryError(
            "carrier requires exact GitHub run and workflow-runs objects"
        )
    commit_b = validate_registration_commit_pair(
        preregistration,
        repo_root=repo_root,
        registration_commit_b=registration_commit_b,
    )
    created_at, _ = _validate_github_run(
        github_run,
        preregistration=preregistration,
        registration_commit_b=commit_b,
        expected_run_id=expected_run_id,
    )
    uniqueness_projection = _validate_sole_surviving_workflow_run(
        github_workflow_runs,
        preregistration=preregistration,
        registration_commit_b=commit_b,
        expected_run_id=expected_run_id,
    )
    if not _exact_json_equal(
        _github_run_projection(github_run),
        uniqueness_projection["selected_run"],
    ):
        raise SWM0WConfirmatoryError("run endpoint/workflow-runs identity drift")
    unsigned = {
        "chronology_status": CHRONOLOGY_STATUS,
        "commitment_sha256": preregistration.commitment.commitment_sha256,
        "event": EXPECTED_EVENT,
        "experiment_id": preregistration.experiment_id,
        "future_round": preregistration.commitment.round,
        "prereg_file_sha256": preregistration.prereg_file_sha256,
        "preregistration_sha256": preregistration.preregistration_sha256,
        "protocol_contract_sha256": preregistration.protocol_contract_sha256,
        "ref": EXPECTED_REF,
        "registered_at_unix": preregistration.commitment.registered_at_unix,
        "registration_commit_b": commit_b,
        "registration_core_sha256": preregistration.registration_core_sha256,
        "repository": EXPECTED_REPOSITORY,
        "round_time_unix": preregistration.commitment.round_time_unix,
        "run_api_sha256": canonical_sha256(github_run),
        "run_attempt": 1,
        "run_created_at": created_at,
        "run_id": expected_run_id,
        "schema_version": REGISTRATION_CARRIER_SCHEMA,
        "source_commit_a": preregistration.repository_binding["source_commit_a"],
        "workflow_path": WORKFLOW_PATH,
        "workflow_run_uniqueness_sha256": canonical_sha256(uniqueness_projection),
        "workflow_runs_api_sha256": canonical_sha256(github_workflow_runs),
        "workflow_sha256": preregistration.workflow_binding["sha256"],
    }
    return RegistrationCarrierV1(
        experiment_id=preregistration.experiment_id,
        repository=EXPECTED_REPOSITORY,
        ref=EXPECTED_REF,
        event=EXPECTED_EVENT,
        workflow_path=WORKFLOW_PATH,
        workflow_sha256=str(preregistration.workflow_binding["sha256"]),
        run_id=expected_run_id,
        run_attempt=1,
        run_created_at=created_at,
        run_api_sha256=unsigned["run_api_sha256"],
        workflow_runs_api_sha256=unsigned["workflow_runs_api_sha256"],
        workflow_run_uniqueness_sha256=unsigned["workflow_run_uniqueness_sha256"],
        source_commit_a=str(preregistration.repository_binding["source_commit_a"]),
        registration_commit_b=commit_b,
        registration_core_sha256=preregistration.registration_core_sha256,
        protocol_contract_sha256=preregistration.protocol_contract_sha256,
        commitment_sha256=preregistration.commitment.commitment_sha256,
        preregistration_sha256=preregistration.preregistration_sha256,
        prereg_file_sha256=preregistration.prereg_file_sha256,
        future_round=preregistration.commitment.round,
        round_time_unix=preregistration.commitment.round_time_unix,
        registered_at_unix=preregistration.commitment.registered_at_unix,
        chronology_status=CHRONOLOGY_STATUS,
        carrier_sha256=canonical_sha256(unsigned),
    )


def registration_artifact_name(carrier: RegistrationCarrierV1) -> str:
    if type(carrier) is not RegistrationCarrierV1:
        raise SWM0WConfirmatoryError("artifact naming requires exact carrier")
    return f"swm0w-register-{carrier.experiment_id}-{carrier.registration_commit_b}"


def parse_registration_archive(
    archive_bytes: bytes, *, expected_digest: str
) -> tuple[RegistrationCarrierV1, Mapping[str, Any], Mapping[str, Any]]:
    members = validate_artifact_archive(
        archive_bytes,
        expected_digest=expected_digest,
        expected_members=REGISTRATION_ARCHIVE_MEMBERS,
        maximum_bytes=MAX_REGISTRATION_ARCHIVE_BYTES,
    )
    carrier_raw = parse_canonical_json_object_bytes(
        members["registration_carrier.json"], name="registration carrier"
    )
    run_raw = _load_json_bytes(members["github_run.json"], "registered run snapshot")
    workflow_runs_raw = _load_json_bytes(
        members["github_workflow_runs.json"], "registered workflow-runs snapshot"
    )
    if type(run_raw) is not dict or type(workflow_runs_raw) is not dict:
        raise SWM0WConfirmatoryError(
            "registration archive JSON members must be objects"
        )
    carrier = parse_registration_carrier(carrier_raw)
    if carrier.run_api_sha256 != canonical_sha256(run_raw):
        raise SWM0WConfirmatoryError("archived carrier/run snapshot link drift")
    if carrier.workflow_runs_api_sha256 != canonical_sha256(workflow_runs_raw):
        raise SWM0WConfirmatoryError(
            "archived carrier/workflow-runs snapshot link drift"
        )
    return carrier, _freeze_json(run_raw), _freeze_json(workflow_runs_raw)


def _validate_carrier_links(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
) -> None:
    expected = {
        "experiment_id": preregistration.experiment_id,
        "source_commit_a": preregistration.repository_binding["source_commit_a"],
        "workflow_sha256": preregistration.workflow_binding["sha256"],
        "registration_core_sha256": preregistration.registration_core_sha256,
        "protocol_contract_sha256": preregistration.protocol_contract_sha256,
        "commitment_sha256": preregistration.commitment.commitment_sha256,
        "preregistration_sha256": preregistration.preregistration_sha256,
        "prereg_file_sha256": preregistration.prereg_file_sha256,
        "future_round": preregistration.commitment.round,
        "round_time_unix": preregistration.commitment.round_time_unix,
        "registered_at_unix": preregistration.commitment.registered_at_unix,
    }
    if any(getattr(carrier, field) != value for field, value in expected.items()):
        raise SWM0WConfirmatoryError("registration carrier/preregistration link drift")


def _validate_artifact_api(
    carrier: RegistrationCarrierV1,
    artifact: Mapping[str, Any],
    *,
    expected_artifact_id: int,
    expected_artifact_digest: str,
) -> tuple[str, int]:
    if type(artifact) is not dict:
        raise SWM0WConfirmatoryError("artifact API value must be an exact JSON object")
    artifact_id = _require_int(artifact.get("id"), "artifact id", minimum=1)
    selected_artifact_id = _require_int(
        expected_artifact_id, "expected artifact id", minimum=1
    )
    artifact_size = _require_int(
        artifact.get("size_in_bytes"), "registration artifact size", minimum=1
    )
    digest = _require_sha256(expected_artifact_digest, "artifact digest")
    if (
        artifact_id != selected_artifact_id
        or artifact.get("name") != registration_artifact_name(carrier)
        or artifact.get("digest") != f"sha256:{digest}"
        or artifact.get("expired") is not False
        or artifact_size > MAX_REGISTRATION_ARCHIVE_BYTES
    ):
        raise SWM0WConfirmatoryError("registration artifact identity/digest drift")
    workflow_run = artifact.get("workflow_run")
    if type(workflow_run) is not dict:
        raise SWM0WConfirmatoryError("artifact lacks exact workflow-run binding")
    workflow_run_id = _require_int(
        workflow_run.get("id"), "artifact workflow_run.id", minimum=1
    )
    workflow_head_sha = _require_git_sha(
        workflow_run.get("head_sha"), "artifact workflow_run.head_sha"
    )
    if (
        workflow_run_id != carrier.run_id
        or workflow_head_sha != carrier.registration_commit_b
    ):
        raise SWM0WConfirmatoryError("artifact does not bind registration commit B")
    created_at = _require_string(artifact.get("created_at"), "artifact.created_at")
    created_unix = _timestamp(created_at, "artifact.created_at")
    if created_unix > carrier.round_time_unix - MINIMUM_ARTIFACT_LEAD_SECONDS:
        raise SWM0WConfirmatoryError("registration artifact missed the pulse deadline")
    if created_unix < _timestamp(carrier.run_created_at, "carrier.run_created_at"):
        raise SWM0WConfirmatoryError("artifact timestamp predates its GitHub run")
    return created_at, created_unix


def validate_registration_artifact(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    *,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    artifact: Mapping[str, Any],
    downloaded_archive_bytes: bytes,
    expected_artifact_id: int,
    expected_artifact_digest: str,
) -> None:
    """Read back the exact uploaded ZIP and its GitHub-managed metadata."""

    _validate_carrier_links(preregistration, carrier)
    members = validate_artifact_archive(
        downloaded_archive_bytes,
        expected_digest=expected_artifact_digest,
        expected_members=REGISTRATION_ARCHIVE_MEMBERS,
        maximum_bytes=MAX_REGISTRATION_ARCHIVE_BYTES,
    )
    if artifact.get("size_in_bytes") != len(downloaded_archive_bytes):
        raise SWM0WConfirmatoryError("registration artifact API/archive size drift")
    archived_carrier_bytes = members["registration_carrier.json"]
    expected_carrier_bytes = (canonical_json(carrier.canonical()) + "\n").encode(
        "utf-8"
    )
    if archived_carrier_bytes != expected_carrier_bytes:
        raise SWM0WConfirmatoryError("archived registration carrier bytes drift")
    archived_run = _load_json_bytes(members["github_run.json"], "archived GitHub run")
    archived_workflow_runs = _load_json_bytes(
        members["github_workflow_runs.json"], "archived workflow-runs snapshot"
    )
    if type(archived_run) is not dict or type(archived_workflow_runs) is not dict:
        raise SWM0WConfirmatoryError("archived GitHub API values must be objects")
    if carrier.run_api_sha256 != canonical_sha256(archived_run):
        raise SWM0WConfirmatoryError("registration carrier/run snapshot hash drift")
    if carrier.workflow_runs_api_sha256 != canonical_sha256(archived_workflow_runs):
        raise SWM0WConfirmatoryError(
            "registration carrier/workflow-runs snapshot hash drift"
        )
    archived_created, _ = _validate_github_run(
        archived_run,
        preregistration=preregistration,
        registration_commit_b=carrier.registration_commit_b,
        expected_run_id=carrier.run_id,
    )
    _validate_github_run(
        github_run,
        preregistration=preregistration,
        registration_commit_b=carrier.registration_commit_b,
        expected_run_id=carrier.run_id,
    )
    archived_uniqueness = _validate_sole_surviving_workflow_run(
        archived_workflow_runs,
        preregistration=preregistration,
        registration_commit_b=carrier.registration_commit_b,
        expected_run_id=carrier.run_id,
    )
    live_uniqueness = _validate_sole_surviving_workflow_run(
        github_workflow_runs,
        preregistration=preregistration,
        registration_commit_b=carrier.registration_commit_b,
        expected_run_id=carrier.run_id,
    )
    uniqueness_sha = canonical_sha256(archived_uniqueness)
    if (
        uniqueness_sha != carrier.workflow_run_uniqueness_sha256
        or canonical_sha256(live_uniqueness) != uniqueness_sha
        or not _exact_json_equal(
            _github_run_projection(archived_run),
            archived_uniqueness["selected_run"],
        )
        or not _exact_json_equal(
            _github_run_projection(github_run), live_uniqueness["selected_run"]
        )
    ):
        raise SWM0WConfirmatoryError("workflow-run uniqueness binding drift")
    if (
        not _exact_json_equal(
            _github_run_projection(github_run), _github_run_projection(archived_run)
        )
        or github_run.get("created_at") != archived_created
    ):
        raise SWM0WConfirmatoryError(
            "live GitHub run identity changed from registration"
        )
    _validate_artifact_api(
        carrier,
        artifact,
        expected_artifact_id=expected_artifact_id,
        expected_artifact_digest=expected_artifact_digest,
    )


@dataclass(frozen=True, slots=True)
class GitHubChronologyReceiptV1:
    experiment_id: str
    run_id: int
    run_attempt: int
    run_created_at: str
    registration_job_id: int
    registration_job_started_at: str
    registration_job_completed_at: str
    artifact_id: int
    artifact_name: str
    artifact_digest: str
    artifact_created_at: str
    source_commit_a: str
    registration_commit_b: str
    registration_carrier_sha256: str
    preregistration_sha256: str
    registration_core_sha256: str
    commitment_sha256: str
    future_round: int
    round_time_unix: int
    run_api_sha256: str
    workflow_run_uniqueness_sha256: str
    jobs_api_sha256: str
    artifact_api_sha256: str
    chronology_status: str
    trust_boundary: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        _require_experiment_id(self.experiment_id)
        for field in ("run_id", "registration_job_id", "artifact_id", "future_round"):
            _require_int(getattr(self, field), field, minimum=1)
        _require_int(self.run_attempt, "chronology run_attempt", minimum=1)
        _require_int(self.round_time_unix, "chronology round_time_unix", minimum=1)
        if self.run_attempt != 1:
            raise SWM0WConfirmatoryError("chronology receipt must bind run attempt one")
        for field in (
            "run_created_at",
            "registration_job_started_at",
            "registration_job_completed_at",
            "artifact_created_at",
        ):
            _timestamp(getattr(self, field), field)
        _require_string(self.artifact_name, "chronology artifact_name")
        for field in (
            "artifact_digest",
            "registration_carrier_sha256",
            "preregistration_sha256",
            "registration_core_sha256",
            "commitment_sha256",
            "run_api_sha256",
            "workflow_run_uniqueness_sha256",
            "jobs_api_sha256",
            "artifact_api_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        _require_git_sha(self.source_commit_a, "source_commit_a")
        _require_git_sha(self.registration_commit_b, "registration_commit_b")
        if self.round_time_unix != beacon.quicknet_round_time(self.future_round):
            raise SWM0WConfirmatoryError("chronology round/time mismatch")
        if (
            self.chronology_status != CHRONOLOGY_STATUS
            or self.trust_boundary != RUNTIME_TRUST_STATUS
        ):
            raise SWM0WConfirmatoryError("chronology status/trust boundary drift")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WConfirmatoryError("GitHub chronology receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "artifact_api_sha256": self.artifact_api_sha256,
            "artifact_created_at": self.artifact_created_at,
            "artifact_digest": self.artifact_digest,
            "artifact_id": self.artifact_id,
            "artifact_name": self.artifact_name,
            "chronology_status": self.chronology_status,
            "commitment_sha256": self.commitment_sha256,
            "experiment_id": self.experiment_id,
            "future_round": self.future_round,
            "jobs_api_sha256": self.jobs_api_sha256,
            "preregistration_sha256": self.preregistration_sha256,
            "receipt_schema": GITHUB_CHRONOLOGY_SCHEMA,
            "registration_carrier_sha256": self.registration_carrier_sha256,
            "registration_commit_b": self.registration_commit_b,
            "registration_core_sha256": self.registration_core_sha256,
            "registration_job_completed_at": self.registration_job_completed_at,
            "registration_job_id": self.registration_job_id,
            "registration_job_started_at": self.registration_job_started_at,
            "round_time_unix": self.round_time_unix,
            "run_api_sha256": self.run_api_sha256,
            "run_attempt": self.run_attempt,
            "run_created_at": self.run_created_at,
            "run_id": self.run_id,
            "source_commit_a": self.source_commit_a,
            "trust_boundary": self.trust_boundary,
            "workflow_run_uniqueness_sha256": self.workflow_run_uniqueness_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def parse_github_chronology_receipt(
    value: Mapping[str, Any],
) -> GitHubChronologyReceiptV1:
    expected = (
        "artifact_api_sha256",
        "artifact_created_at",
        "artifact_digest",
        "artifact_id",
        "artifact_name",
        "chronology_status",
        "commitment_sha256",
        "experiment_id",
        "future_round",
        "jobs_api_sha256",
        "preregistration_sha256",
        "receipt_schema",
        "registration_carrier_sha256",
        "registration_commit_b",
        "registration_core_sha256",
        "registration_job_completed_at",
        "registration_job_id",
        "registration_job_started_at",
        "round_time_unix",
        "run_api_sha256",
        "run_attempt",
        "run_created_at",
        "run_id",
        "source_commit_a",
        "trust_boundary",
        "workflow_run_uniqueness_sha256",
        "receipt_sha256",
    )
    data = _require_exact_keys(value, expected, "GitHub chronology receipt")
    if data["receipt_schema"] != GITHUB_CHRONOLOGY_SCHEMA:
        raise SWM0WConfirmatoryError("unsupported GitHub chronology schema")
    fields = dict(data)
    del fields["receipt_schema"]
    return GitHubChronologyReceiptV1(**fields)


def _registration_job(
    carrier: RegistrationCarrierV1,
    jobs_api: Mapping[str, Any],
) -> tuple[int, str, str, Mapping[str, Any]]:
    if type(jobs_api) is not dict:
        raise SWM0WConfirmatoryError("GitHub jobs must be an exact JSON object")
    rows = jobs_api.get("jobs")
    if type(rows) is not list:
        raise SWM0WConfirmatoryError("GitHub jobs API lacks a jobs list")
    selected = [
        row for row in rows if type(row) is dict and row.get("name") == "register"
    ]
    if len(selected) != 1:
        raise SWM0WConfirmatoryError("GitHub run must contain exactly one register job")
    job = selected[0]
    job_run_id = _require_int(job.get("run_id"), "register.run_id", minimum=1)
    job_attempt = _require_int(
        job.get("run_attempt"), "register.run_attempt", minimum=1
    )
    head_sha = _require_git_sha(job.get("head_sha"), "register.head_sha")
    if (
        job_run_id != carrier.run_id
        or job_attempt != 1
        or head_sha != carrier.registration_commit_b
        or job.get("conclusion") != "success"
        or job.get("status") != "completed"
    ):
        raise SWM0WConfirmatoryError("registration job identity/conclusion drift")
    job_id = _require_int(job.get("id"), "registration job id", minimum=1)
    started_at = _require_string(job.get("started_at"), "register.started_at")
    completed_at = _require_string(job.get("completed_at"), "register.completed_at")
    started = _timestamp(started_at, "register.started_at")
    completed = _timestamp(completed_at, "register.completed_at")
    run_created = _timestamp(carrier.run_created_at, "carrier.run_created_at")
    if not run_created <= started <= completed < carrier.round_time_unix:
        raise SWM0WConfirmatoryError("registration job did not finish before the pulse")
    projection = {
        "completed_at": completed_at,
        "conclusion": job.get("conclusion"),
        "head_sha": head_sha,
        "id": job_id,
        "name": job.get("name"),
        "run_attempt": job_attempt,
        "run_id": job_run_id,
        "started_at": started_at,
        "status": job.get("status"),
    }
    return job_id, started_at, completed_at, projection


def build_github_chronology_receipt(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    *,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    github_jobs: Mapping[str, Any],
    artifact: Mapping[str, Any],
    downloaded_archive_bytes: bytes,
    expected_artifact_id: int,
    expected_artifact_digest: str,
) -> GitHubChronologyReceiptV1:
    """Bind server-managed run/job/artifact timestamps without using Git dates."""

    if any(
        type(item) is not dict
        for item in (github_run, github_workflow_runs, github_jobs, artifact)
    ):
        raise SWM0WConfirmatoryError("chronology inputs must be exact JSON objects")
    validate_registration_artifact(
        preregistration,
        carrier,
        github_run=github_run,
        github_workflow_runs=github_workflow_runs,
        artifact=artifact,
        downloaded_archive_bytes=downloaded_archive_bytes,
        expected_artifact_id=expected_artifact_id,
        expected_artifact_digest=expected_artifact_digest,
    )
    job_id, job_started, job_completed, job_projection = _registration_job(
        carrier, github_jobs
    )
    artifact_created, artifact_created_unix = _validate_artifact_api(
        carrier,
        artifact,
        expected_artifact_id=expected_artifact_id,
        expected_artifact_digest=expected_artifact_digest,
    )
    if not (
        _timestamp(job_started, "register.started_at")
        <= artifact_created_unix
        <= _timestamp(job_completed, "register.completed_at")
    ):
        raise SWM0WConfirmatoryError(
            "registration artifact was not created inside the register job"
        )
    unsigned = {
        "artifact_api_sha256": canonical_sha256(artifact),
        "artifact_created_at": artifact_created,
        "artifact_digest": expected_artifact_digest,
        "artifact_id": expected_artifact_id,
        "artifact_name": registration_artifact_name(carrier),
        "chronology_status": CHRONOLOGY_STATUS,
        "commitment_sha256": carrier.commitment_sha256,
        "experiment_id": carrier.experiment_id,
        "future_round": carrier.future_round,
        "jobs_api_sha256": canonical_sha256(job_projection),
        "preregistration_sha256": carrier.preregistration_sha256,
        "receipt_schema": GITHUB_CHRONOLOGY_SCHEMA,
        "registration_carrier_sha256": carrier.carrier_sha256,
        "registration_commit_b": carrier.registration_commit_b,
        "registration_core_sha256": carrier.registration_core_sha256,
        "registration_job_completed_at": job_completed,
        "registration_job_id": job_id,
        "registration_job_started_at": job_started,
        "round_time_unix": carrier.round_time_unix,
        "run_api_sha256": canonical_sha256(_github_run_projection(github_run)),
        "run_attempt": 1,
        "run_created_at": carrier.run_created_at,
        "run_id": carrier.run_id,
        "source_commit_a": carrier.source_commit_a,
        "trust_boundary": RUNTIME_TRUST_STATUS,
        "workflow_run_uniqueness_sha256": carrier.workflow_run_uniqueness_sha256,
    }
    return GitHubChronologyReceiptV1(
        experiment_id=carrier.experiment_id,
        run_id=carrier.run_id,
        run_attempt=1,
        run_created_at=carrier.run_created_at,
        registration_job_id=job_id,
        registration_job_started_at=job_started,
        registration_job_completed_at=job_completed,
        artifact_id=expected_artifact_id,
        artifact_name=registration_artifact_name(carrier),
        artifact_digest=expected_artifact_digest,
        artifact_created_at=artifact_created,
        source_commit_a=carrier.source_commit_a,
        registration_commit_b=carrier.registration_commit_b,
        registration_carrier_sha256=carrier.carrier_sha256,
        preregistration_sha256=carrier.preregistration_sha256,
        registration_core_sha256=carrier.registration_core_sha256,
        commitment_sha256=carrier.commitment_sha256,
        future_round=carrier.future_round,
        round_time_unix=carrier.round_time_unix,
        run_api_sha256=unsigned["run_api_sha256"],
        workflow_run_uniqueness_sha256=carrier.workflow_run_uniqueness_sha256,
        jobs_api_sha256=unsigned["jobs_api_sha256"],
        artifact_api_sha256=unsigned["artifact_api_sha256"],
        chronology_status=CHRONOLOGY_STATUS,
        trust_boundary=RUNTIME_TRUST_STATUS,
        receipt_sha256=canonical_sha256(unsigned),
    )


def parse_task_seed_binding(value: Mapping[str, Any]) -> beacon.TaskSeedBindingV1:
    data = _require_exact_keys(
        value,
        (
            "schema_version",
            "commitment_sha256",
            "verifier_receipt_sha256",
            "chain_hash",
            "round",
            "randomness",
            "seed_domain",
            "task_seed_hex",
            "chronology_status",
            "chronology_claim_allowed",
            "binding_sha256",
        ),
        "task-seed binding",
    )
    if data["schema_version"] != beacon.BINDING_SCHEMA:
        raise SWM0WConfirmatoryError("unsupported task-seed binding schema")
    seeds = data["task_seed_hex"]
    if type(seeds) is not list:
        raise SWM0WConfirmatoryError("task-seed binding seeds must be an ordered list")
    return beacon.TaskSeedBindingV1(
        commitment_sha256=data["commitment_sha256"],
        verifier_receipt_sha256=data["verifier_receipt_sha256"],
        chain_hash=data["chain_hash"],
        round=data["round"],
        randomness=data["randomness"],
        seed_domain=data["seed_domain"],
        task_seed_hex=tuple(seeds),
        chronology_status=data["chronology_status"],
        chronology_claim_allowed=data["chronology_claim_allowed"],
        binding_sha256=data["binding_sha256"],
    )


def _validate_chronology_links(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    chronology: GitHubChronologyReceiptV1,
) -> None:
    _validate_carrier_links(preregistration, carrier)
    expected = {
        "experiment_id": carrier.experiment_id,
        "run_id": carrier.run_id,
        "run_attempt": carrier.run_attempt,
        "run_created_at": carrier.run_created_at,
        "source_commit_a": carrier.source_commit_a,
        "registration_commit_b": carrier.registration_commit_b,
        "registration_carrier_sha256": carrier.carrier_sha256,
        "preregistration_sha256": carrier.preregistration_sha256,
        "registration_core_sha256": carrier.registration_core_sha256,
        "commitment_sha256": carrier.commitment_sha256,
        "future_round": carrier.future_round,
        "round_time_unix": carrier.round_time_unix,
    }
    if any(getattr(chronology, field) != value for field, value in expected.items()):
        raise SWM0WConfirmatoryError("GitHub chronology/carrier link drift")


def _validate_pinned_node_runtime_receipt(
    verifier_receipt: Mapping[str, Any], *, required_mode: str
) -> None:
    if required_mode not in {"online", "offline"}:
        raise AssertionError("internal verifier mode drift")
    if verifier_receipt.get("mode") != required_mode:
        raise SWM0WConfirmatoryError(
            f"cryptographic verification requires exact {required_mode} mode"
        )
    verifier = verifier_receipt.get("verifier")
    if type(verifier) is not dict:
        raise SWM0WConfirmatoryError("beacon receipt lacks verifier provenance")
    if (
        verifier.get("runtime_engine") != "Node.js"
        or verifier.get("runtime_version") != NODE_VERSION
        or verifier.get("runtime_exec_sha256") != NODE_EXECUTABLE_SHA256
        or verifier.get("runtime_trust_status") != beacon.RUNTIME_TRUST_STATUS
    ):
        raise SWM0WConfirmatoryError(
            "executed Node runtime differs from preregistration"
        )


def _validate_pinned_node_receipt(verifier_receipt: Mapping[str, Any]) -> None:
    _validate_pinned_node_runtime_receipt(
        verifier_receipt,
        required_mode="online",
    )


@dataclass(frozen=True, slots=True)
class _BLSReplayEvidence:
    fixture_sha256: str
    stable_projection_sha256: str
    ordered_task_seed_binding_sha256: str

    def __post_init__(self) -> None:
        for field in self.__dataclass_fields__:
            _require_sha256(getattr(self, field), f"BLS replay {field}")


def _replay_committed_pulse_bls(
    preregistration: ValidatedPreregistrationV1,
    verifier_receipt: Mapping[str, Any],
    task_seed_binding: beacon.TaskSeedBindingV1,
) -> _BLSReplayEvidence:
    """Rerun pinned drand-client BLS on an exact bounded offline pulse fixture."""

    if type(verifier_receipt) is not dict:
        raise SWM0WConfirmatoryError("BLS replay requires an exact verifier receipt")
    if type(task_seed_binding) is not beacon.TaskSeedBindingV1:
        raise SWM0WConfirmatoryError("BLS replay requires an exact seed binding")
    online_pulse = beacon.validate_verifier_receipt(
        verifier_receipt, preregistration.commitment
    )
    _validate_pinned_node_receipt(verifier_receipt)
    fixture = {
        "chain_hash": beacon.QUICKNET_CHAIN_HASH,
        "pulse": {
            "randomness": online_pulse.randomness,
            "round": online_pulse.round,
            "signature": online_pulse.signature,
        },
        "schema_version": BEACON_OFFLINE_FIXTURE_SCHEMA,
        "source_url": (f"{beacon.QUICKNET_BASE_URL}/public/{online_pulse.round}"),
    }
    fixture_bytes = (canonical_json(fixture) + "\n").encode("utf-8")
    if len(fixture_bytes) > beacon.MAX_OFFLINE_FIXTURE_BYTES:
        raise SWM0WConfirmatoryError("BLS replay fixture exceeds the frozen bound")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix="swm0w-bls-replay-", suffix=".json", delete=False
        ) as stream:
            stream.write(fixture_bytes)
            temporary_path = Path(stream.name)
        replay_receipt, replay_binding = beacon.verify_and_bind_offline(
            preregistration.commitment,
            pulse_file=temporary_path,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    replay_pulse = beacon.validate_verifier_receipt(
        replay_receipt, preregistration.commitment
    )
    _validate_pinned_node_runtime_receipt(
        replay_receipt,
        required_mode="offline",
    )
    expected_pulse = {
        "randomness": online_pulse.randomness,
        "round": online_pulse.round,
        "round_time_unix": online_pulse.round_time_unix,
        "signature": online_pulse.signature,
    }
    _require_exact_json(replay_receipt["pulse"], expected_pulse, "BLS replay pulse")
    if (
        replay_pulse.randomness != online_pulse.randomness
        or replay_pulse.signature != online_pulse.signature
        or replay_binding.task_seed_hex != task_seed_binding.task_seed_hex
    ):
        raise SWM0WConfirmatoryError(
            "BLS replay pulse or derived ordered task seeds drift"
        )
    ordered_sha = protocol.ordered_task_seed_binding_sha256(
        replay_binding.task_seed_bytes()
    )
    if ordered_sha != protocol.ordered_task_seed_binding_sha256(
        task_seed_binding.task_seed_bytes()
    ):
        raise SWM0WConfirmatoryError("BLS replay ordered-seed binding drift")
    stable_receipt = dict(replay_receipt)
    stable_receipt.pop("receipt_sha256", None)
    stable_receipt.pop("verified_at_unix", None)
    return _BLSReplayEvidence(
        fixture_sha256=file_sha256_bytes(fixture_bytes),
        stable_projection_sha256=canonical_sha256(stable_receipt),
        ordered_task_seed_binding_sha256=ordered_sha,
    )


def admit_verified_seed_bundle(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    chronology: GitHubChronologyReceiptV1,
    *,
    verifier_receipt: Mapping[str, Any],
    task_seed_binding: beacon.TaskSeedBindingV1,
) -> protocol.ConfirmatoryAdmissionV1:
    """Construct protocol admission only after all source/time/seed links pass."""

    if type(verifier_receipt) is not dict:
        raise SWM0WConfirmatoryError(
            "admission requires an exact verifier receipt object"
        )
    if type(task_seed_binding) is not beacon.TaskSeedBindingV1:
        raise SWM0WConfirmatoryError("admission requires exact task-seed binding")
    _validate_chronology_links(preregistration, carrier, chronology)
    _validate_pinned_node_receipt(verifier_receipt)
    beacon.validate_task_seed_bundle_links(
        preregistration.commitment,
        verifier_receipt,
        task_seed_binding,
    )
    if (
        task_seed_binding.round != preregistration.commitment.round
        or task_seed_binding.commitment_sha256
        != preregistration.commitment.commitment_sha256
        or len(task_seed_binding.task_seed_bytes()) != protocol.TASK_COUNT
    ):
        raise SWM0WConfirmatoryError("verified task seeds differ from preregistration")
    ordered_seed_sha = protocol.ordered_task_seed_binding_sha256(
        task_seed_binding.task_seed_bytes()
    )
    unsigned = {
        "admission_status": CHRONOLOGY_STATUS,
        "commitment_sha256": preregistration.commitment.commitment_sha256,
        "experiment_id": preregistration.experiment_id,
        "future_round": preregistration.commitment.round,
        "github_chronology_receipt_sha256": chronology.receipt_sha256,
        "preregistration_sha256": preregistration.preregistration_sha256,
        "prereg_file_sha256": preregistration.prereg_file_sha256,
        "protocol_contract_sha256": preregistration.protocol_contract_sha256,
        "registration_commit_b": carrier.registration_commit_b,
        "registration_core_sha256": preregistration.registration_core_sha256,
        "schema_version": protocol.ADMISSION_RECEIPT_SCHEMA,
        "source_commit_a": carrier.source_commit_a,
        "task_seed_binding_sha256": ordered_seed_sha,
        "validated": True,
        "workflow_sha256": carrier.workflow_sha256,
    }
    return protocol.validate_admission_receipt(
        {**unsigned, "receipt_sha256": protocol.canonical_sha256(unsigned)}
    )


def _validated_task_receipts(
    values: Sequence[protocol.TaskReceipt | Mapping[str, Any]],
) -> tuple[protocol.TaskReceipt, ...]:
    result: list[protocol.TaskReceipt] = []
    for value in values:
        if type(value) is protocol.TaskReceipt:
            parsed = protocol.validate_task_receipt(value.canonical())
        elif type(value) is dict:
            parsed = protocol.validate_task_receipt(value)
        else:
            raise SWM0WConfirmatoryError("bundle task receipt has an invalid type")
        result.append(parsed)
    if len(result) != protocol.TASK_COUNT:
        raise SWM0WConfirmatoryError("final bundle requires exactly 20 task receipts")
    if tuple(row.task_index for row in result) != tuple(range(protocol.TASK_COUNT)):
        raise SWM0WConfirmatoryError("task receipts are not in exact seed order")
    return tuple(result)


def _validate_tasks_against_beacon_seeds(
    tasks: Sequence[protocol.TaskReceipt],
    task_seed_binding: beacon.TaskSeedBindingV1,
) -> None:
    """Rebuild task identity/variance from beacon seeds without fitting models."""

    if type(task_seed_binding) is not beacon.TaskSeedBindingV1:
        raise SWM0WConfirmatoryError("task replay requires an exact seed binding")
    if len(tasks) != protocol.TASK_COUNT:
        raise SWM0WConfirmatoryError("task replay requires all 20 receipts")
    seeds = task_seed_binding.task_seed_bytes()
    if len(seeds) != protocol.TASK_COUNT:
        raise SWM0WConfirmatoryError("task replay requires all 20 beacon seeds")
    for index, (receipt, seed) in enumerate(zip(tasks, seeds)):
        if type(receipt) is not protocol.TaskReceipt:
            raise SWM0WConfirmatoryError("task replay requires exact task receipts")
        rebuilt = task_family.build_task_from_external_seed(seed)
        variance = protocol.exact_test_variance(rebuilt)
        if (
            receipt.task_index != index
            or receipt.task_seed_sha256 != sha256(seed).hexdigest()
            or receipt.task_uid != rebuilt.task_uid
            or receipt.task_sha256 != rebuilt.task_sha256
            or receipt.exact_variance != variance
            or variance.case_count != protocol.TEST_CASE_COUNT
        ):
            raise SWM0WConfirmatoryError(
                f"task {index} identity/variance does not derive from its beacon seed"
            )


def build_candidate_bundle(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    chronology: GitHubChronologyReceiptV1,
    *,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    github_jobs: Mapping[str, Any],
    artifact: Mapping[str, Any],
    verifier_receipt: Mapping[str, Any],
    task_seed_binding: beacon.TaskSeedBindingV1,
    admission: protocol.ConfirmatoryAdmissionV1,
    task_receipts: Sequence[protocol.TaskReceipt | Mapping[str, Any]],
    final_receipt: protocol.FinalReceipt | Mapping[str, Any],
) -> dict[str, Any]:
    """Build a candidate package; this function never emits an evidence verdict."""

    if any(
        type(item) is not dict
        for item in (
            github_run,
            github_workflow_runs,
            github_jobs,
            artifact,
            verifier_receipt,
        )
    ):
        raise SWM0WConfirmatoryError("candidate inputs must be exact JSON objects")
    tasks = _validated_task_receipts(task_receipts)
    _validate_tasks_against_beacon_seeds(tasks, task_seed_binding)
    parsed_final = (
        protocol.validate_final_receipt(final_receipt.canonical())
        if type(final_receipt) is protocol.FinalReceipt
        else protocol.validate_final_receipt(final_receipt)
    )
    recomputed = protocol.finalize_protocol(
        tasks,
        mode=protocol.RunMode.CONFIRMATORY,
        optimizer=protocol.CONFIRMATORY_OPTIMIZER,
        admission=admission,
        thresholds=protocol.CONFIRMATORY_THRESHOLDS,
    )
    if recomputed.canonical() != parsed_final.canonical():
        raise SWM0WConfirmatoryError(
            "final protocol reducer does not replay from tasks"
        )
    if parsed_final.admission != admission:
        raise SWM0WConfirmatoryError("final protocol receipt admission drift")
    if parsed_final.ordered_task_seed_binding_sha256 != (
        protocol.ordered_task_seed_binding_sha256(task_seed_binding.task_seed_bytes())
    ):
        raise SWM0WConfirmatoryError("final receipt ordered-seed binding drift")
    if parsed_final.mode is not protocol.RunMode.CONFIRMATORY:
        raise SWM0WConfirmatoryError("candidate package requires confirmatory mode")
    unsigned = {
        "beacon_task_seed_binding": task_seed_binding.canonical(),
        "confirmatory_admission": admission.canonical(),
        "github_api_evidence": {
            "artifact": _load_json_bytes(canonical_json(artifact).encode(), "artifact"),
            "jobs": _load_json_bytes(canonical_json(github_jobs).encode(), "jobs"),
            "run": _load_json_bytes(canonical_json(github_run).encode(), "run"),
            "workflow_runs": _load_json_bytes(
                canonical_json(github_workflow_runs).encode(), "workflow runs"
            ),
        },
        "github_operational_chronology": chronology.canonical(),
        "preregistration": _load_json_bytes(
            canonical_json(preregistration.payload).encode(), "preregistration"
        ),
        "protocol_final_receipt": parsed_final.canonical(),
        "registration_carrier": carrier.canonical(),
        "protocol_candidate_outcome": parsed_final.outcome.value,
        "schema_version": CANDIDATE_BUNDLE_SCHEMA,
        "task_receipts_in_seed_order": [row.canonical() for row in tasks],
        "trust_boundary": CANDIDATE_TRUST_BOUNDARY,
        "verifier_receipt": _load_json_bytes(
            canonical_json(verifier_receipt).encode(), "verifier receipt"
        ),
    }
    return {**unsigned, "bundle_sha256": canonical_sha256(unsigned)}


def validate_candidate_bundle(
    value: Mapping[str, Any],
    *,
    repo_root: Path,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    github_jobs: Mapping[str, Any],
    registration_artifact: Mapping[str, Any],
    registration_archive_bytes: bytes,
    registration_artifact_id: int,
    registration_artifact_digest: str,
) -> dict[str, Any]:
    """Replay a candidate package without training or promoting its outcome."""

    if any(
        type(item) is not dict
        for item in (
            value,
            github_run,
            github_workflow_runs,
            github_jobs,
            registration_artifact,
        )
    ):
        raise SWM0WConfirmatoryError("candidate validation requires exact JSON objects")
    data = _require_exact_keys(
        value,
        (
            "schema_version",
            "beacon_task_seed_binding",
            "confirmatory_admission",
            "github_api_evidence",
            "github_operational_chronology",
            "preregistration",
            "protocol_candidate_outcome",
            "protocol_final_receipt",
            "registration_carrier",
            "task_receipts_in_seed_order",
            "trust_boundary",
            "verifier_receipt",
            "bundle_sha256",
        ),
        "candidate result bundle",
    )
    if data["schema_version"] != CANDIDATE_BUNDLE_SCHEMA:
        raise SWM0WConfirmatoryError("unsupported candidate-bundle schema")
    digest = _require_sha256(data["bundle_sha256"], "bundle_sha256")
    unsigned = dict(data)
    del unsigned["bundle_sha256"]
    if digest != canonical_sha256(unsigned):
        raise SWM0WConfirmatoryError("candidate bundle hash mismatch")
    if data["trust_boundary"] != CANDIDATE_TRUST_BOUNDARY:
        raise SWM0WConfirmatoryError("candidate trust boundary drift")

    prereg_bytes = (canonical_json(data["preregistration"]) + "\n").encode("utf-8")
    preregistration = validate_preregistration_bytes(prereg_bytes, repo_root=repo_root)
    carrier = parse_registration_carrier(data["registration_carrier"])
    validate_registration_commit_pair(
        preregistration,
        repo_root=repo_root,
        registration_commit_b=carrier.registration_commit_b,
    )
    _require_exact_keys(
        data["github_api_evidence"],
        ("artifact", "jobs", "run", "workflow_runs"),
        "embedded GitHub evidence",
    )
    chronology_recorded = parse_github_chronology_receipt(
        data["github_operational_chronology"]
    )
    # Only the caller's fresh API responses and raw immutable artifact ZIP are
    # authoritative.  The embedded snapshots are audit context, not authority.
    chronology = build_github_chronology_receipt(
        preregistration,
        carrier,
        github_run=github_run,
        github_workflow_runs=github_workflow_runs,
        github_jobs=github_jobs,
        artifact=registration_artifact,
        downloaded_archive_bytes=registration_archive_bytes,
        expected_artifact_id=registration_artifact_id,
        expected_artifact_digest=registration_artifact_digest,
    )
    if chronology != chronology_recorded:
        raise SWM0WConfirmatoryError(
            "GitHub chronology does not replay from API evidence"
        )

    binding = parse_task_seed_binding(data["beacon_task_seed_binding"])
    verifier_receipt = data["verifier_receipt"]
    if type(verifier_receipt) is not dict:
        raise SWM0WConfirmatoryError("verifier receipt must be an exact object")
    admission = admit_verified_seed_bundle(
        preregistration,
        carrier,
        chronology,
        verifier_receipt=verifier_receipt,
        task_seed_binding=binding,
    )
    recorded_admission = protocol.validate_admission_receipt(
        data["confirmatory_admission"]
    )
    if admission != recorded_admission:
        raise SWM0WConfirmatoryError("confirmatory admission does not replay")
    tasks = _validated_task_receipts(data["task_receipts_in_seed_order"])
    _validate_tasks_against_beacon_seeds(tasks, binding)
    final = protocol.validate_final_receipt(data["protocol_final_receipt"])
    replay = protocol.finalize_protocol(
        tasks,
        mode=protocol.RunMode.CONFIRMATORY,
        optimizer=protocol.CONFIRMATORY_OPTIMIZER,
        admission=admission,
        thresholds=protocol.CONFIRMATORY_THRESHOLDS,
    )
    if replay != final:
        raise SWM0WConfirmatoryError("protocol final receipt does not replay")
    if data["protocol_candidate_outcome"] != final.outcome.value:
        raise SWM0WConfirmatoryError("candidate outcome label differs from reducer")
    return {
        "admission_receipt_sha256": admission.receipt_sha256,
        "bundle_sha256": digest,
        "chronology_receipt_sha256": chronology.receipt_sha256,
        "protocol_final_receipt_sha256": final.receipt_sha256,
        "task_count": len(tasks),
        "candidate_outcome": final.outcome.value,
    }


def candidate_artifact_name(carrier: RegistrationCarrierV1) -> str:
    if type(carrier) is not RegistrationCarrierV1:
        raise SWM0WConfirmatoryError("candidate artifact naming requires exact carrier")
    return f"swm0w-candidate-{carrier.experiment_id}-{carrier.registration_commit_b}"


def _confirm_job(
    carrier: RegistrationCarrierV1,
    github_jobs: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if type(github_jobs) is not dict:
        raise SWM0WConfirmatoryError("GitHub jobs must be an exact JSON object")
    rows = github_jobs.get("jobs")
    if type(rows) is not list:
        raise SWM0WConfirmatoryError("GitHub jobs API lacks an exact jobs list")
    selected = [
        row for row in rows if type(row) is dict and row.get("name") == "confirm"
    ]
    if len(selected) != 1:
        raise SWM0WConfirmatoryError("GitHub run must contain exactly one confirm job")
    job = selected[0]
    labels = job.get("labels")
    job_run_id = _require_int(job.get("run_id"), "confirm.run_id", minimum=1)
    job_attempt = _require_int(job.get("run_attempt"), "confirm.run_attempt", minimum=1)
    job_head_sha = _require_git_sha(job.get("head_sha"), "confirm.head_sha")
    if (
        job_run_id != carrier.run_id
        or job_attempt != 1
        or job_head_sha != carrier.registration_commit_b
        or job.get("status") != "completed"
        or job.get("conclusion") != "success"
        or type(labels) is not list
        or any(type(label) is not str or not label for label in labels)
        or RUNNER_LABEL not in labels
        or type(job.get("runner_name")) is not str
        or not job.get("runner_name")
        or job.get("runner_group_name") != "GitHub Actions"
    ):
        raise SWM0WConfirmatoryError("confirm job identity/runtime/conclusion drift")
    job_id = _require_int(job.get("id"), "confirm job id", minimum=1)
    started_at = _require_string(job.get("started_at"), "confirm.started_at")
    completed_at = _require_string(job.get("completed_at"), "confirm.completed_at")
    started = _timestamp(started_at, "confirm.started_at")
    completed = _timestamp(completed_at, "confirm.completed_at")
    if not started <= completed:
        raise SWM0WConfirmatoryError("confirm job timestamps are reversed")
    projection = {
        "completed_at": completed_at,
        "conclusion": "success",
        "head_sha": job_head_sha,
        "id": job_id,
        "labels": list(labels),
        "name": "confirm",
        "run_attempt": job_attempt,
        "run_id": job_run_id,
        "runner_group_name": job.get("runner_group_name"),
        "runner_name": job.get("runner_name"),
        "started_at": started_at,
        "status": "completed",
    }
    return job, projection


def _validate_candidate_artifact_api(
    carrier: RegistrationCarrierV1,
    artifact: Mapping[str, Any],
    *,
    confirm_job: Mapping[str, Any],
    expected_artifact_id: int,
    expected_artifact_digest: str,
) -> tuple[str, int]:
    artifact_id = _require_int(artifact.get("id"), "candidate artifact id", minimum=1)
    selected_artifact_id = _require_int(
        expected_artifact_id, "expected candidate artifact id", minimum=1
    )
    digest = _require_sha256(expected_artifact_digest, "candidate artifact digest")
    size = _require_int(
        artifact.get("size_in_bytes"), "candidate artifact size", minimum=1
    )
    workflow_run = artifact.get("workflow_run")
    if (
        artifact_id != selected_artifact_id
        or artifact.get("name") != candidate_artifact_name(carrier)
        or artifact.get("digest") != f"sha256:{digest}"
        or artifact.get("expired") is not False
        or size > MAX_CANDIDATE_ARCHIVE_BYTES
        or type(workflow_run) is not dict
    ):
        raise SWM0WConfirmatoryError("candidate artifact identity/digest/source drift")
    workflow_run_id = _require_int(
        workflow_run.get("id"), "candidate workflow_run.id", minimum=1
    )
    workflow_head_sha = _require_git_sha(
        workflow_run.get("head_sha"), "candidate workflow_run.head_sha"
    )
    if (
        workflow_run_id != carrier.run_id
        or workflow_head_sha != carrier.registration_commit_b
    ):
        raise SWM0WConfirmatoryError("candidate artifact workflow source drift")
    created_at = _require_string(
        artifact.get("created_at"), "candidate artifact.created_at"
    )
    created = _timestamp(created_at, "candidate artifact.created_at")
    started = _timestamp(confirm_job.get("started_at"), "confirm.started_at")
    completed = _timestamp(confirm_job.get("completed_at"), "confirm.completed_at")
    if not (
        started <= created <= completed
        and carrier.round_time_unix <= created
        and carrier.round_time_unix <= completed
    ):
        raise SWM0WConfirmatoryError(
            "candidate artifact is outside the post-pulse completed confirm job"
        )
    return created_at, size


_OUTCOME_TO_EVIDENCE = {
    protocol.ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE: "PASS",
    protocol.ProtocolOutcome.CANDIDATE_KILL_AWAITING_BUNDLE: "KILL",
    protocol.ProtocolOutcome.CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE: "INCONCLUSIVE",
    protocol.ProtocolOutcome.VOID: "VOID",
}


@dataclass(frozen=True, slots=True)
class EvidenceAdjudicationV1:
    experiment_id: str
    run_id: int
    run_attempt: int
    source_commit_a: str
    registration_commit_b: str
    workflow_sha256: str
    preregistration_sha256: str
    registration_core_sha256: str
    commitment_sha256: str
    future_round: int
    github_chronology_receipt_sha256: str
    workflow_run_uniqueness_sha256: str
    confirm_job_id: int
    confirm_job_started_at: str
    confirm_job_completed_at: str
    confirm_job_api_sha256: str
    candidate_artifact_id: int
    candidate_artifact_name: str
    candidate_artifact_digest: str
    candidate_artifact_created_at: str
    candidate_artifact_api_sha256: str
    candidate_archive_sha256: str
    candidate_file_sha256: str
    candidate_bundle_sha256: str
    candidate_protocol_receipt_sha256: str
    candidate_protocol_outcome: str
    bls_replay_fixture_sha256: str
    bls_replay_stable_projection_sha256: str
    bls_replay_ordered_task_seed_binding_sha256: str
    task_seed_binding_sha256: str
    task_count: int
    evidence_verdict: str
    reason_codes: tuple[str, ...]
    capacity_independent_phrase_allowed: bool
    trust_boundary: str
    validated: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        _require_experiment_id(self.experiment_id)
        for name in (
            "run_id",
            "future_round",
            "confirm_job_id",
            "candidate_artifact_id",
            "task_count",
        ):
            _require_int(getattr(self, name), name, minimum=1)
        _require_int(self.run_attempt, "adjudication run_attempt", minimum=1)
        if self.run_attempt != 1 or self.task_count != protocol.TASK_COUNT:
            raise SWM0WConfirmatoryError("adjudication run attempt/task count drift")
        _require_git_sha(self.source_commit_a, "source_commit_a")
        _require_git_sha(self.registration_commit_b, "registration_commit_b")
        for name in (
            "candidate_artifact_name",
            "candidate_protocol_outcome",
            "evidence_verdict",
            "trust_boundary",
        ):
            _require_string(getattr(self, name), f"adjudication {name}")
        for name in (
            "workflow_sha256",
            "preregistration_sha256",
            "registration_core_sha256",
            "commitment_sha256",
            "github_chronology_receipt_sha256",
            "workflow_run_uniqueness_sha256",
            "confirm_job_api_sha256",
            "candidate_artifact_digest",
            "candidate_artifact_api_sha256",
            "candidate_archive_sha256",
            "candidate_file_sha256",
            "candidate_bundle_sha256",
            "candidate_protocol_receipt_sha256",
            "bls_replay_fixture_sha256",
            "bls_replay_stable_projection_sha256",
            "bls_replay_ordered_task_seed_binding_sha256",
            "task_seed_binding_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        for name in (
            "confirm_job_started_at",
            "confirm_job_completed_at",
            "candidate_artifact_created_at",
        ):
            _timestamp(getattr(self, name), name)
        if (
            type(self.reason_codes) is not tuple
            or not self.reason_codes
            or any(type(item) is not str or not item for item in self.reason_codes)
        ):
            raise SWM0WConfirmatoryError(
                "adjudication reason codes must be an exact tuple"
            )
        try:
            outcome = protocol.ProtocolOutcome(self.candidate_protocol_outcome)
        except ValueError as exc:
            raise SWM0WConfirmatoryError(
                "adjudication candidate outcome is invalid"
            ) from exc
        expected_verdict = _OUTCOME_TO_EVIDENCE.get(outcome)
        if expected_verdict is None or self.evidence_verdict != expected_verdict:
            raise SWM0WConfirmatoryError("candidate/evidence verdict mapping drift")
        if type(self.capacity_independent_phrase_allowed) is not bool:
            raise SWM0WConfirmatoryError("adjudication phrase flag must be exact bool")
        if self.capacity_independent_phrase_allowed and self.evidence_verdict != "PASS":
            raise SWM0WConfirmatoryError("capacity phrase requires evidence PASS")
        if (
            self.bls_replay_ordered_task_seed_binding_sha256
            != self.task_seed_binding_sha256
        ):
            raise SWM0WConfirmatoryError("adjudication BLS/task-seed binding drift")
        if self.trust_boundary != EVIDENCE_TRUST_BOUNDARY or self.validated is not True:
            raise SWM0WConfirmatoryError("adjudication trust/validation status drift")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WConfirmatoryError("adjudication self-hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "candidate_archive_sha256": self.candidate_archive_sha256,
            "candidate_artifact_api_sha256": self.candidate_artifact_api_sha256,
            "candidate_artifact_created_at": self.candidate_artifact_created_at,
            "candidate_artifact_digest": self.candidate_artifact_digest,
            "candidate_artifact_id": self.candidate_artifact_id,
            "candidate_artifact_name": self.candidate_artifact_name,
            "candidate_bundle_sha256": self.candidate_bundle_sha256,
            "candidate_file_sha256": self.candidate_file_sha256,
            "candidate_protocol_outcome": self.candidate_protocol_outcome,
            "candidate_protocol_receipt_sha256": self.candidate_protocol_receipt_sha256,
            "capacity_independent_phrase_allowed": self.capacity_independent_phrase_allowed,
            "commitment_sha256": self.commitment_sha256,
            "bls_replay_fixture_sha256": self.bls_replay_fixture_sha256,
            "bls_replay_ordered_task_seed_binding_sha256": (
                self.bls_replay_ordered_task_seed_binding_sha256
            ),
            "bls_replay_stable_projection_sha256": (
                self.bls_replay_stable_projection_sha256
            ),
            "confirm_job_api_sha256": self.confirm_job_api_sha256,
            "confirm_job_completed_at": self.confirm_job_completed_at,
            "confirm_job_id": self.confirm_job_id,
            "confirm_job_started_at": self.confirm_job_started_at,
            "evidence_verdict": self.evidence_verdict,
            "experiment_id": self.experiment_id,
            "future_round": self.future_round,
            "github_chronology_receipt_sha256": self.github_chronology_receipt_sha256,
            "preregistration_sha256": self.preregistration_sha256,
            "reason_codes": list(self.reason_codes),
            "registration_commit_b": self.registration_commit_b,
            "registration_core_sha256": self.registration_core_sha256,
            "run_attempt": self.run_attempt,
            "run_id": self.run_id,
            "schema_version": ADJUDICATION_SCHEMA,
            "source_commit_a": self.source_commit_a,
            "task_count": self.task_count,
            "task_seed_binding_sha256": self.task_seed_binding_sha256,
            "trust_boundary": self.trust_boundary,
            "validated": self.validated,
            "workflow_sha256": self.workflow_sha256,
            "workflow_run_uniqueness_sha256": self.workflow_run_uniqueness_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def parse_evidence_adjudication(value: Mapping[str, Any]) -> EvidenceAdjudicationV1:
    if type(value) is not dict:
        raise SWM0WConfirmatoryError("adjudication receipt must be an exact object")
    expected = set(EvidenceAdjudicationV1.__dataclass_fields__) | {"schema_version"}
    if set(value) != expected or value["schema_version"] != ADJUDICATION_SCHEMA:
        raise SWM0WConfirmatoryError("adjudication receipt schema drift")
    fields = dict(value)
    del fields["schema_version"]
    reasons = fields.get("reason_codes")
    if type(reasons) is not list:
        raise SWM0WConfirmatoryError("adjudication reasons must be an ordered list")
    fields["reason_codes"] = tuple(reasons)
    return EvidenceAdjudicationV1(**fields)


def adjudicate_candidate_archive(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    *,
    repo_root: Path,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    github_jobs: Mapping[str, Any],
    registration_artifact: Mapping[str, Any],
    registration_archive_bytes: bytes,
    registration_artifact_id: int,
    registration_artifact_digest: str,
    candidate_artifact: Mapping[str, Any],
    candidate_archive_bytes: bytes,
    candidate_artifact_id: int,
    candidate_artifact_digest: str,
) -> EvidenceAdjudicationV1:
    """Promote one server-bound candidate only after complete no-training replay."""

    if any(
        type(item) is not dict
        for item in (
            github_run,
            github_workflow_runs,
            github_jobs,
            registration_artifact,
            candidate_artifact,
        )
    ):
        raise SWM0WConfirmatoryError(
            "adjudication API inputs must be exact JSON objects"
        )
    _validate_github_run(
        github_run,
        preregistration=preregistration,
        registration_commit_b=carrier.registration_commit_b,
        expected_run_id=carrier.run_id,
    )
    live_uniqueness = _validate_sole_surviving_workflow_run(
        github_workflow_runs,
        preregistration=preregistration,
        registration_commit_b=carrier.registration_commit_b,
        expected_run_id=carrier.run_id,
    )
    if canonical_sha256(live_uniqueness) != carrier.workflow_run_uniqueness_sha256:
        raise SWM0WConfirmatoryError("adjudication workflow-run uniqueness drift")
    confirm_job, job_projection = _confirm_job(carrier, github_jobs)
    created_at, candidate_archive_size = _validate_candidate_artifact_api(
        carrier,
        candidate_artifact,
        confirm_job=confirm_job,
        expected_artifact_id=candidate_artifact_id,
        expected_artifact_digest=candidate_artifact_digest,
    )
    members = validate_artifact_archive(
        candidate_archive_bytes,
        expected_digest=candidate_artifact_digest,
        expected_members=CANDIDATE_ARCHIVE_MEMBERS,
        maximum_bytes=MAX_CANDIDATE_ARCHIVE_BYTES,
    )
    if candidate_archive_size != len(candidate_archive_bytes):
        raise SWM0WConfirmatoryError("candidate artifact API/archive size drift")
    candidate_bytes = members["candidate_bundle.json"]
    candidate = parse_canonical_json_object_bytes(
        candidate_bytes, name="candidate bundle"
    )
    summary = validate_candidate_bundle(
        candidate,
        repo_root=repo_root,
        github_run=github_run,
        github_workflow_runs=github_workflow_runs,
        github_jobs=github_jobs,
        registration_artifact=registration_artifact,
        registration_archive_bytes=registration_archive_bytes,
        registration_artifact_id=registration_artifact_id,
        registration_artifact_digest=registration_artifact_digest,
    )
    binding = parse_task_seed_binding(candidate["beacon_task_seed_binding"])
    bls_replay = _replay_committed_pulse_bls(
        preregistration,
        candidate["verifier_receipt"],
        binding,
    )
    final = protocol.validate_final_receipt(candidate["protocol_final_receipt"])
    if (
        bls_replay.ordered_task_seed_binding_sha256
        != final.ordered_task_seed_binding_sha256
    ):
        raise SWM0WConfirmatoryError(
            "BLS replay seeds differ from the protocol final receipt"
        )
    outcome = final.outcome
    verdict = _OUTCOME_TO_EVIDENCE.get(outcome)
    if verdict is None:
        # A diagnostic protocol object in a result artifact is an integrity
        # failure, never evidence-level inconclusive or PASS.
        outcome = protocol.ProtocolOutcome.VOID
        verdict = "VOID"
        reasons = ("NON_CONFIRMATORY_CANDIDATE_OUTCOME",)
        phrase_allowed = False
    else:
        reasons = final.reason_codes
        phrase_allowed = (
            verdict == "PASS" and final.capacity_independent_phrase_candidate
        )
    unsigned = {
        "candidate_archive_sha256": file_sha256_bytes(candidate_archive_bytes),
        "candidate_artifact_api_sha256": canonical_sha256(candidate_artifact),
        "candidate_artifact_created_at": created_at,
        "candidate_artifact_digest": candidate_artifact_digest,
        "candidate_artifact_id": candidate_artifact_id,
        "candidate_artifact_name": candidate_artifact_name(carrier),
        "candidate_bundle_sha256": summary["bundle_sha256"],
        "candidate_file_sha256": file_sha256_bytes(candidate_bytes),
        "candidate_protocol_outcome": outcome.value,
        "candidate_protocol_receipt_sha256": final.receipt_sha256,
        "bls_replay_fixture_sha256": bls_replay.fixture_sha256,
        "bls_replay_ordered_task_seed_binding_sha256": (
            bls_replay.ordered_task_seed_binding_sha256
        ),
        "bls_replay_stable_projection_sha256": (bls_replay.stable_projection_sha256),
        "capacity_independent_phrase_allowed": phrase_allowed,
        "commitment_sha256": carrier.commitment_sha256,
        "confirm_job_api_sha256": canonical_sha256(job_projection),
        "confirm_job_completed_at": confirm_job["completed_at"],
        "confirm_job_id": confirm_job["id"],
        "confirm_job_started_at": confirm_job["started_at"],
        "evidence_verdict": verdict,
        "experiment_id": carrier.experiment_id,
        "future_round": carrier.future_round,
        "github_chronology_receipt_sha256": summary["chronology_receipt_sha256"],
        "preregistration_sha256": carrier.preregistration_sha256,
        "reason_codes": list(reasons),
        "registration_commit_b": carrier.registration_commit_b,
        "registration_core_sha256": carrier.registration_core_sha256,
        "run_attempt": 1,
        "run_id": carrier.run_id,
        "schema_version": ADJUDICATION_SCHEMA,
        "source_commit_a": carrier.source_commit_a,
        "task_count": protocol.TASK_COUNT,
        "task_seed_binding_sha256": final.ordered_task_seed_binding_sha256,
        "trust_boundary": EVIDENCE_TRUST_BOUNDARY,
        "validated": True,
        "workflow_sha256": carrier.workflow_sha256,
        "workflow_run_uniqueness_sha256": carrier.workflow_run_uniqueness_sha256,
    }
    fields = dict(unsigned)
    del fields["schema_version"]
    fields["reason_codes"] = tuple(fields["reason_codes"])
    return EvidenceAdjudicationV1(
        **fields,
        receipt_sha256=canonical_sha256(unsigned),
    )


def validate_evidence_adjudication(
    value: Mapping[str, Any],
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    **live_inputs: Any,
) -> EvidenceAdjudicationV1:
    """Re-query/re-download inputs are mandatory; embedded JSON is not authority."""

    recorded = parse_evidence_adjudication(value)
    replayed = adjudicate_candidate_archive(
        preregistration,
        carrier,
        **live_inputs,
    )
    # The helper's full receipt hash contains its wall-clock execution second,
    # so it is intentionally absent from the authoritative schema.  The exact
    # fixture, stable replay projection, ordered seeds, and every other field
    # are reproducible and must all compare equal.
    if recorded != replayed:
        raise SWM0WConfirmatoryError(
            "adjudication does not replay from live GitHub evidence"
        )
    return recorded


def build_operational_void_receipt(
    preregistration: ValidatedPreregistrationV1,
    *,
    registration_commit_b: str,
    run_id: int,
    confirm_needs_result: str,
    reason_code: str,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    github_jobs: Mapping[str, Any],
) -> dict[str, Any]:
    """Record a conservative workflow failure; this can never promote evidence."""

    allowed_results = {"failure", "cancelled", "skipped", "success"}
    allowed_reasons = {
        "REGISTER_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
        "CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
        "CANDIDATE_ARTIFACT_UNAVAILABLE",
        "ADJUDICATION_INTEGRITY_FAILURE",
    }
    if (
        confirm_needs_result not in allowed_results
        or reason_code not in allowed_reasons
    ):
        raise SWM0WConfirmatoryError("operational VOID reason/result drift")
    commit_b = _require_git_sha(registration_commit_b, "registration_commit_b")
    selected_run_id = _require_int(run_id, "run_id", minimum=1)
    if any(
        type(item) is not dict
        for item in (github_run, github_workflow_runs, github_jobs)
    ):
        raise SWM0WConfirmatoryError("operational VOID inputs must be exact objects")
    live_run_id = _require_int(github_run.get("id"), "VOID run.id", minimum=1)
    live_run_attempt = _require_int(
        github_run.get("run_attempt"), "VOID run.run_attempt", minimum=1
    )
    live_head_sha = _require_git_sha(github_run.get("head_sha"), "VOID run.head_sha")
    if (
        live_run_id != selected_run_id
        or live_head_sha != commit_b
        or live_run_attempt != 1
    ):
        raise SWM0WConfirmatoryError("operational VOID run identity drift")
    unsigned = {
        "confirm_needs_result": confirm_needs_result,
        "evidence_verdict": "VOID",
        "experiment_id": preregistration.experiment_id,
        "github_jobs_snapshot_sha256": canonical_sha256(github_jobs),
        "github_run_projection_sha256": canonical_sha256(
            _github_run_projection(github_run)
        ),
        "github_workflow_runs_snapshot_sha256": canonical_sha256(github_workflow_runs),
        "independent_validation_requirement": (
            "REQUERY_GITHUB_RUN_WORKFLOW_RUN_LIST_AND_JOBS;"
            "THIS_SELF_HASH_IS_NOT_EXTERNAL_AUTHORITY"
        ),
        "preregistration_sha256": preregistration.preregistration_sha256,
        "reason_codes": [reason_code],
        "registration_commit_b": commit_b,
        "run_attempt": live_run_attempt,
        "run_id": selected_run_id,
        "schema_version": OPERATIONAL_VOID_SCHEMA,
        "source_commit_a": preregistration.repository_binding["source_commit_a"],
        "validated": False,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def validate_operational_void_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    data = _require_exact_keys(
        value,
        (
            "confirm_needs_result",
            "evidence_verdict",
            "experiment_id",
            "github_jobs_snapshot_sha256",
            "github_run_projection_sha256",
            "github_workflow_runs_snapshot_sha256",
            "independent_validation_requirement",
            "preregistration_sha256",
            "reason_codes",
            "registration_commit_b",
            "run_attempt",
            "run_id",
            "schema_version",
            "source_commit_a",
            "validated",
            "receipt_sha256",
        ),
        "operational VOID receipt",
    )
    if (
        data["schema_version"] != OPERATIONAL_VOID_SCHEMA
        or data["evidence_verdict"] != "VOID"
        or data["validated"] is not False
        or data["confirm_needs_result"]
        not in {"failure", "cancelled", "skipped", "success"}
        or data["independent_validation_requirement"]
        != (
            "REQUERY_GITHUB_RUN_WORKFLOW_RUN_LIST_AND_JOBS;"
            "THIS_SELF_HASH_IS_NOT_EXTERNAL_AUTHORITY"
        )
    ):
        raise SWM0WConfirmatoryError("operational VOID fixed fields drift")
    _require_experiment_id(data["experiment_id"])
    _require_int(data["run_id"], "VOID run_id", minimum=1)
    run_attempt = _require_int(data["run_attempt"], "VOID run_attempt", minimum=1)
    if run_attempt != 1:
        raise SWM0WConfirmatoryError("operational VOID only records attempt one")
    _require_git_sha(data["registration_commit_b"], "VOID registration_commit_b")
    _require_git_sha(data["source_commit_a"], "VOID source_commit_a")
    for field in (
        "github_jobs_snapshot_sha256",
        "github_run_projection_sha256",
        "github_workflow_runs_snapshot_sha256",
        "preregistration_sha256",
    ):
        _require_sha256(data[field], f"VOID {field}")
    if (
        type(data["reason_codes"]) is not list
        or len(data["reason_codes"]) != 1
        or type(data["reason_codes"][0]) is not str
        or not data["reason_codes"][0]
    ):
        raise SWM0WConfirmatoryError("operational VOID reasons drift")
    digest = _require_sha256(data["receipt_sha256"], "receipt_sha256")
    unsigned = dict(data)
    del unsigned["receipt_sha256"]
    if digest != canonical_sha256(unsigned):
        raise SWM0WConfirmatoryError("operational VOID self-hash mismatch")
    return dict(data)


def wait_for_committed_round(
    commitment: beacon.FutureRoundCommitmentV1,
    *,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Wait in bounded polls; starting after the pulse is valid after registration."""

    if type(commitment) is not beacon.FutureRoundCommitmentV1:
        raise SWM0WConfirmatoryError("round wait requires exact commitment")
    while True:
        now = clock()
        if (
            isinstance(now, bool)
            or not isinstance(now, (int, float))
            or not math.isfinite(now)
        ):
            raise SWM0WConfirmatoryError("execution clock returned a non-finite time")
        remaining = commitment.round_time_unix - float(now)
        if remaining <= 0.0:
            return
        sleeper(min(float(WAIT_POLL_SECONDS), remaining))


def _verify_committed_pulse_with_fixed_retries(
    commitment: beacon.FutureRoundCommitmentV1,
    *,
    allow_network: bool,
    verifier: Callable[
        [beacon.FutureRoundCommitmentV1],
        tuple[Mapping[str, Any], beacon.TaskSeedBindingV1],
    ]
    | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[Mapping[str, Any], beacon.TaskSeedBindingV1]:
    if allow_network is not True:
        raise SWM0WConfirmatoryError("online beacon access requires explicit opt-in")

    def online(
        selected: beacon.FutureRoundCommitmentV1,
    ) -> tuple[Mapping[str, Any], beacon.TaskSeedBindingV1]:
        return beacon.verify_and_bind_online(selected, allow_network=True)

    selected_verifier = online if verifier is None else verifier
    last_error: Exception | None = None
    for attempt in range(NETWORK_RETRY_COUNT):
        try:
            receipt, binding = selected_verifier(commitment)
            if (
                not isinstance(receipt, Mapping)
                or type(binding) is not beacon.TaskSeedBindingV1
            ):
                raise SWM0WConfirmatoryError("beacon verifier returned invalid types")
            return receipt, binding
        except (beacon.SWM0WBeaconError, SWM0WConfirmatoryError) as exc:
            last_error = exc
            if attempt + 1 < NETWORK_RETRY_COUNT:
                sleeper(float(NETWORK_RETRY_DELAY_SECONDS))
    raise SWM0WConfirmatoryError(
        "exact committed Quicknet round was unavailable or rejected; reroll forbidden"
    ) from last_error


def execute_confirmatory_once(
    preregistration: ValidatedPreregistrationV1,
    carrier: RegistrationCarrierV1,
    *,
    github_run: Mapping[str, Any],
    github_workflow_runs: Mapping[str, Any],
    github_jobs: Mapping[str, Any],
    artifact: Mapping[str, Any],
    downloaded_archive_bytes: bytes,
    expected_artifact_id: int,
    expected_artifact_digest: str,
    allow_network: bool,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
    verifier: Callable[
        [beacon.FutureRoundCommitmentV1],
        tuple[Mapping[str, Any], beacon.TaskSeedBindingV1],
    ]
    | None = None,
) -> dict[str, Any]:
    """Wait, verify and execute exactly once; return no resumable partial state."""

    chronology = build_github_chronology_receipt(
        preregistration,
        carrier,
        github_run=github_run,
        github_workflow_runs=github_workflow_runs,
        github_jobs=github_jobs,
        artifact=artifact,
        downloaded_archive_bytes=downloaded_archive_bytes,
        expected_artifact_id=expected_artifact_id,
        expected_artifact_digest=expected_artifact_digest,
    )
    wait_for_committed_round(
        preregistration.commitment,
        clock=clock,
        sleeper=sleeper,
    )
    verifier_receipt, task_seed_binding = _verify_committed_pulse_with_fixed_retries(
        preregistration.commitment,
        allow_network=allow_network,
        verifier=verifier,
        sleeper=sleeper,
    )
    admission = admit_verified_seed_bundle(
        preregistration,
        carrier,
        chronology,
        verifier_receipt=verifier_receipt,
        task_seed_binding=task_seed_binding,
    )
    seeds = task_seed_binding.task_seed_bytes()
    # This equality is checked before the first model fit.  The formula lives in
    # the protocol module and is not duplicated here.
    if admission.task_seed_binding_sha256 != protocol.ordered_task_seed_binding_sha256(
        seeds
    ):
        raise SWM0WConfirmatoryError("admission/actual ordered seed preflight failed")
    tasks: list[protocol.TaskReceipt] = []
    for index, seed in enumerate(seeds):
        receipt = protocol.execute_task(
            seed,
            index,
            mode=protocol.RunMode.CONFIRMATORY,
            optimizer=protocol.CONFIRMATORY_OPTIMIZER,
        )
        tasks.append(protocol.validate_task_receipt(receipt.canonical()))
    final = protocol.finalize_protocol(
        tasks,
        mode=protocol.RunMode.CONFIRMATORY,
        optimizer=protocol.CONFIRMATORY_OPTIMIZER,
        admission=admission,
        thresholds=protocol.CONFIRMATORY_THRESHOLDS,
    )
    bundle = build_candidate_bundle(
        preregistration,
        carrier,
        chronology,
        github_run=github_run,
        github_workflow_runs=github_workflow_runs,
        github_jobs=github_jobs,
        artifact=artifact,
        verifier_receipt=verifier_receipt,
        task_seed_binding=task_seed_binding,
        admission=admission,
        task_receipts=tasks,
        final_receipt=final,
    )
    # Read-only validation repeats all links and reduction before any output is
    # allowed to become an artifact.
    return bundle


def atomic_write_canonical_json(path: Path, value: Mapping[str, Any]) -> str:
    """Create one immutable-intent file atomically; never overwrite evidence."""

    target = Path(path)
    if target.exists() or target.is_symlink():
        raise SWM0WConfirmatoryError("refusing to overwrite an existing output")
    if not target.parent.is_dir():
        raise SWM0WConfirmatoryError("output parent directory does not exist")
    payload = (canonical_json(value) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        target.chmod(0o444)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return file_sha256_bytes(payload)


def _read_bytes(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise SWM0WConfirmatoryError(f"required file is unavailable: {path}") from exc


def _read_json(path: str) -> Mapping[str, Any]:
    value = _load_json_bytes(_read_bytes(path), f"required JSON {path}")
    if type(value) is not dict:
        raise SWM0WConfirmatoryError(f"required JSON must be an object: {path}")
    return value


def _positive_cli_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return parsed


def _registration_cli_inputs(
    parser: argparse.ArgumentParser, *, include_jobs: bool
) -> None:
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--registration-archive", required=True)
    parser.add_argument("--run-json", required=True)
    parser.add_argument("--workflow-runs-json", required=True)
    if include_jobs:
        parser.add_argument("--jobs-json", required=True)
    parser.add_argument("--registration-artifact-json", required=True)
    parser.add_argument(
        "--registration-artifact-id", required=True, type=_positive_cli_int
    )
    parser.add_argument("--registration-artifact-digest", required=True)


def _validate_runner_environment() -> None:
    if (
        os.environ.get("RUNNER_OS") != RUNNER_OS
        or os.environ.get("RUNNER_ARCH") != RUNNER_ARCH
    ):
        raise SWM0WConfirmatoryError("GitHub runner OS/architecture drift")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser(
        "register-carrier", help="build the exact pre-pulse registration carrier"
    )
    register.add_argument("--repo-root", required=True)
    register.add_argument("--prereg", required=True)
    register.add_argument("--registration-commit", required=True)
    register.add_argument("--run-json", required=True)
    register.add_argument("--workflow-runs-json", required=True)
    register.add_argument("--run-id", required=True, type=_positive_cli_int)
    register.add_argument("--output", required=True)

    artifact_check = commands.add_parser(
        "validate-register-artifact", help="read back the uploaded carrier"
    )
    _registration_cli_inputs(artifact_check, include_jobs=False)

    confirm = commands.add_parser(
        "confirm", help="wait, verify the pulse, and execute the frozen suite once"
    )
    _registration_cli_inputs(confirm, include_jobs=True)
    confirm.add_argument("--output", required=True)
    confirm.add_argument("--allow-online-beacon", action="store_true")

    adjudicate = commands.add_parser(
        "adjudicate", help="promote one server-bound candidate without retraining"
    )
    _registration_cli_inputs(adjudicate, include_jobs=True)
    adjudicate.add_argument("--candidate-artifact-json", required=True)
    adjudicate.add_argument("--candidate-archive", required=True)
    adjudicate.add_argument(
        "--candidate-artifact-id", required=True, type=_positive_cli_int
    )
    adjudicate.add_argument("--candidate-artifact-digest", required=True)
    adjudicate.add_argument("--output", required=True)

    validate = commands.add_parser(
        "validate-adjudication",
        help="re-query inputs and revalidate an adjudication without training",
    )
    _registration_cli_inputs(validate, include_jobs=True)
    validate.add_argument("--candidate-artifact-json", required=True)
    validate.add_argument("--candidate-archive", required=True)
    validate.add_argument(
        "--candidate-artifact-id", required=True, type=_positive_cli_int
    )
    validate.add_argument("--candidate-artifact-digest", required=True)
    validate.add_argument("--receipt", required=True)

    void = commands.add_parser(
        "operational-void", help="record a failed/absent confirmatory execution as VOID"
    )
    void.add_argument("--repo-root", required=True)
    void.add_argument("--prereg", required=True)
    void.add_argument("--registration-commit", required=True)
    void.add_argument("--run-id", required=True, type=_positive_cli_int)
    void.add_argument("--run-json", required=True)
    void.add_argument("--workflow-runs-json", required=True)
    void.add_argument("--jobs-json", required=True)
    void.add_argument("--confirm-needs-result", required=True)
    void.add_argument("--reason-code", required=True)
    void.add_argument("--output", required=True)

    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    if args.command == "register-carrier":
        prereg = validate_preregistration_bytes(
            _read_bytes(args.prereg), repo_root=root
        )
        carrier = build_registration_carrier(
            prereg,
            repo_root=root,
            registration_commit_b=args.registration_commit,
            github_run=_read_json(args.run_json),
            github_workflow_runs=_read_json(args.workflow_runs_json),
            expected_run_id=args.run_id,
        )
        atomic_write_canonical_json(Path(args.output), carrier.canonical())
        print(carrier.carrier_sha256)
        return 0

    if args.command == "operational-void":
        prereg = validate_preregistration_bytes(
            _read_bytes(args.prereg), repo_root=root
        )
        receipt = build_operational_void_receipt(
            prereg,
            registration_commit_b=args.registration_commit,
            run_id=args.run_id,
            confirm_needs_result=args.confirm_needs_result,
            reason_code=args.reason_code,
            github_run=_read_json(args.run_json),
            github_workflow_runs=_read_json(args.workflow_runs_json),
            github_jobs=_read_json(args.jobs_json),
        )
        validate_operational_void_receipt(receipt)
        atomic_write_canonical_json(Path(args.output), receipt)
        print(receipt["receipt_sha256"])
        return 0

    prereg = validate_preregistration_bytes(_read_bytes(args.prereg), repo_root=root)
    registration_archive = _read_bytes(args.registration_archive)
    carrier, _, _ = parse_registration_archive(
        registration_archive,
        expected_digest=args.registration_artifact_digest,
    )
    run_json = _read_json(args.run_json)
    workflow_runs_json = _read_json(args.workflow_runs_json)
    registration_artifact_json = _read_json(args.registration_artifact_json)
    if args.command == "validate-register-artifact":
        validate_registration_artifact(
            prereg,
            carrier,
            github_run=run_json,
            github_workflow_runs=workflow_runs_json,
            artifact=registration_artifact_json,
            downloaded_archive_bytes=registration_archive,
            expected_artifact_id=args.registration_artifact_id,
            expected_artifact_digest=args.registration_artifact_digest,
        )
        print(carrier.carrier_sha256)
        return 0

    jobs_json = _read_json(args.jobs_json)
    if args.command == "confirm":
        _validate_runner_environment()
        bundle = execute_confirmatory_once(
            prereg,
            carrier,
            github_run=run_json,
            github_workflow_runs=workflow_runs_json,
            github_jobs=jobs_json,
            artifact=registration_artifact_json,
            downloaded_archive_bytes=registration_archive,
            expected_artifact_id=args.registration_artifact_id,
            expected_artifact_digest=args.registration_artifact_digest,
            allow_network=args.allow_online_beacon,
        )
        validate_candidate_bundle(
            bundle,
            repo_root=root,
            github_run=run_json,
            github_workflow_runs=workflow_runs_json,
            github_jobs=jobs_json,
            registration_artifact=registration_artifact_json,
            registration_archive_bytes=registration_archive,
            registration_artifact_id=args.registration_artifact_id,
            registration_artifact_digest=args.registration_artifact_digest,
        )
        atomic_write_canonical_json(Path(args.output), bundle)
        print(bundle["bundle_sha256"])
        return 0

    live_inputs = {
        "repo_root": root,
        "github_run": run_json,
        "github_workflow_runs": workflow_runs_json,
        "github_jobs": jobs_json,
        "registration_artifact": registration_artifact_json,
        "registration_archive_bytes": registration_archive,
        "registration_artifact_id": args.registration_artifact_id,
        "registration_artifact_digest": args.registration_artifact_digest,
        "candidate_artifact": _read_json(args.candidate_artifact_json),
        "candidate_archive_bytes": _read_bytes(args.candidate_archive),
        "candidate_artifact_id": args.candidate_artifact_id,
        "candidate_artifact_digest": args.candidate_artifact_digest,
    }
    if args.command == "adjudicate":
        _validate_runner_environment()
        receipt = adjudicate_candidate_archive(prereg, carrier, **live_inputs)
        atomic_write_canonical_json(Path(args.output), receipt.canonical())
    else:
        receipt = validate_evidence_adjudication(
            _read_json(args.receipt), prereg, carrier, **live_inputs
        )
    print(
        canonical_json(
            {
                "evidence_verdict": receipt.evidence_verdict,
                "receipt_sha256": receipt.receipt_sha256,
            }
        )
    )
    return 0


__all__ = [
    "CHRONOLOGY_STATUS",
    "ADJUDICATION_SCHEMA",
    "CANDIDATE_BUNDLE_SCHEMA",
    "EvidenceAdjudicationV1",
    "GITHUB_CHRONOLOGY_SCHEMA",
    "GitHubChronologyReceiptV1",
    "NODE_ARCHIVE_SHA256",
    "NODE_EXECUTABLE_SHA256",
    "NODE_VERSION",
    "OPERATIONAL_VOID_SCHEMA",
    "PREREGISTRATION_PATH",
    "PREREGISTRATION_SCHEMA",
    "REGISTRATION_CARRIER_SCHEMA",
    "REGISTRATION_CORE_SCHEMA",
    "REQUIRED_SOURCE_PATHS",
    "RegistrationCarrierV1",
    "SWM0WConfirmatoryError",
    "TrackedBytesManifestV1",
    "ValidatedPreregistrationV1",
    "admit_verified_seed_bundle",
    "atomic_write_canonical_json",
    "adjudicate_candidate_archive",
    "build_candidate_bundle",
    "build_operational_void_receipt",
    "build_github_chronology_receipt",
    "build_registration_carrier",
    "canonical_json",
    "canonical_sha256",
    "execute_confirmatory_once",
    "main",
    "parse_github_chronology_receipt",
    "parse_evidence_adjudication",
    "parse_canonical_json_object_bytes",
    "parse_registration_carrier",
    "parse_registration_archive",
    "parse_task_seed_binding",
    "registration_artifact_name",
    "tracked_bytes_manifest",
    "validate_artifact_archive",
    "validate_candidate_bundle",
    "validate_evidence_adjudication",
    "validate_operational_void_receipt",
    "validate_preregistration_bytes",
    "validate_registration_artifact",
    "validate_registration_commit_pair",
    "wait_for_committed_round",
]


if __name__ == "__main__":
    raise SystemExit(main())
