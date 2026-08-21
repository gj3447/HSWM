"""Strict, result-agnostic adoption boundary for the SWM-0W-S2S pilot.

This module turns one *complete* canonical train/dev pilot artifact into a
candidate protocol configuration.  It does not run the pilot, acquire a
future seed, inspect a test split, contact GitHub, or make an efficacy or
chronology claim.  All GitHub values and the downloaded artifact ZIP are
independently supplied by the caller and are bound as provenance evidence.

The only accepted configuration is reconstructed from the pilot's three
strictly validated selections.  In particular, the pilot external-seed hash
is never accepted as the task-family seed commitment used by the protocol's
exclusion list.

Scientific status: ``ENGINEERING_ADOPTION_CANDIDATE_ONLY_UNJUDGED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import re
from typing import Any, Mapping
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

from hswm.experiments import swm0w_s2s_pilot as pilot
from hswm.experiments import swm0w_s2s_protocol as protocol
from hswm.experiments.swm0w_s2s_operator import ALL_ARMS, S2SArm
from hswm.experiments.swm0w_s2s_training import S2STrainingConfig


SCHEMA_VERSION = "hswm-swm0w-s2s-pilot-adoption/v1"
SCIENTIFIC_STATUS = "ENGINEERING_ADOPTION_CANDIDATE_ONLY_UNJUDGED"
ADOPTION_STATUS = "CANDIDATE_PROTOCOL_CONFIG_READY_FOR_PREREGISTRATION"
CLAIM_BOUNDARY = (
    "STRUCTURAL_PROVENANCE_ONLY_NO_EFFICACY_OR_CHRONOLOGY_CLAIM"
)
VERDICT = "NO_EFFICACY_OR_CHRONOLOGY_VERDICT"
GITHUB_EVIDENCE_ASSURANCE = (
    "CALLER_SUPPLIED_API_AND_ZIP_EVIDENCE_BOUND_NOT_LIVE_AUTHENTICATION"
)
RUNTIME_SUMMARY_VERSION = "hswm-swm0w-s2s-pilot-runtime-summary/v1"
RUNTIME_SUMMARY_ROLE = (
    "DETERMINISTIC_PROJECTION_OF_NONDETERMINISTIC_TELEMETRY_ONLY"
)
PREREG_RESOURCE_POLICY_STATUS = "PENDING_NOT_CHOSEN"

EXPECTED_REPOSITORY = "gj3447/HSWM"
EXPECTED_BRANCH = "main"
EXPECTED_EVENT = "workflow_dispatch"
EXPECTED_WORKFLOW_NAME = "SWM-0W-S2S train-dev development pilot"
EXPECTED_WORKFLOW_PATH = (
    ".github/workflows/swm0w-s2s-train-dev-pilot.yml"
)
EXPECTED_JOB_NAME = "fixed development roster"
EXPECTED_ARTIFACT_MEMBER = "pilot.json"
MAXIMUM_ARCHIVE_BYTES = 128 * 1024 * 1024
MAXIMUM_MEMBER_BYTES = 120 * 1024 * 1024
_ZIP_COMPRESSION_NAMES = {
    ZIP_STORED: "ZIP_STORED",
    ZIP_DEFLATED: "ZIP_DEFLATED",
}

_HEX = frozenset("0123456789abcdef")
_RFC3339_SECONDS = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


class SWM0WS2SPilotAdoptionError(ValueError):
    """Raised when candidate adoption evidence is incomplete or inconsistent."""


def canonical_json(value: Any) -> str:
    """Return the same float-free canonical JSON used by the pilot."""

    try:
        return pilot.canonical_json(value)
    except pilot.SWM0WS2SPilotError as exc:
        raise SWM0WS2SPilotAdoptionError(
            "adoption receipt is not exact float-free JSON"
        ) from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _exact_object(
    value: object, expected: tuple[str, ...], name: str
) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise SWM0WS2SPilotAdoptionError(f"{name} must be an exact JSON object")
    if set(value) != set(expected):
        raise SWM0WS2SPilotAdoptionError(f"{name} keys drifted")
    return value


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise SWM0WS2SPilotAdoptionError(
            f"{name} must be an exact integer >= {minimum}"
        )
    return value


def _nonempty_string(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise SWM0WS2SPilotAdoptionError(f"{name} must be an exact nonempty string")
    return value


def _sha256(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in _HEX for character in value)
    ):
        raise SWM0WS2SPilotAdoptionError(f"{name} must be a lowercase SHA-256")
    return value


def _git_sha(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 40
        or any(character not in _HEX for character in value)
    ):
        raise SWM0WS2SPilotAdoptionError(f"{name} must be a lowercase 40-hex commit")
    return value


def _timestamp(value: object, name: str) -> str:
    if type(value) is not str or _RFC3339_SECONDS.fullmatch(value) is None:
        raise SWM0WS2SPilotAdoptionError(
            f"{name} must be second-resolution UTC RFC3339"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise SWM0WS2SPilotAdoptionError(f"{name} is not a real UTC timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise SWM0WS2SPilotAdoptionError(f"{name} is not canonical UTC RFC3339")
    return value


def _timestamp_unix(value: str) -> int:
    return int(
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def _artifact_name(run_id: int) -> str:
    return f"swm0w-s2s-train-dev-pilot-{run_id}-1"


@dataclass(frozen=True, slots=True)
class GitHubRunEvidenceV1:
    run_id: int
    run_attempt: int
    head_sha: str
    head_branch: str
    workflow_name: str
    workflow_path: str
    event: str
    status: str
    conclusion: str
    repository: str

    def __post_init__(self) -> None:
        _integer(self.run_id, "run id", minimum=1)
        _integer(self.run_attempt, "run attempt", minimum=1)
        _git_sha(self.head_sha, "run head SHA")
        for field in (
            "head_branch",
            "workflow_name",
            "workflow_path",
            "event",
            "status",
            "conclusion",
            "repository",
        ):
            _nonempty_string(getattr(self, field), f"run {field}")
        if (
            self.run_attempt != 1
            or self.head_branch != EXPECTED_BRANCH
            or self.workflow_name != EXPECTED_WORKFLOW_NAME
            or self.workflow_path != EXPECTED_WORKFLOW_PATH
            or self.event != EXPECTED_EVENT
            or self.status != "completed"
            or self.conclusion != "success"
            or self.repository != EXPECTED_REPOSITORY
        ):
            raise SWM0WS2SPilotAdoptionError(
                "GitHub run identity, workflow, or conclusion drifted"
            )

    def canonical(self) -> dict[str, Any]:
        return {
            "conclusion": self.conclusion,
            "event": self.event,
            "head_branch": self.head_branch,
            "head_sha": self.head_sha,
            "id": self.run_id,
            "name": self.workflow_name,
            "path": self.workflow_path,
            "repository": self.repository,
            "run_attempt": self.run_attempt,
            "status": self.status,
        }


def _parse_run_evidence(value: object) -> GitHubRunEvidenceV1:
    data = _exact_object(
        value,
        (
            "conclusion",
            "event",
            "head_branch",
            "head_sha",
            "id",
            "name",
            "path",
            "repository",
            "run_attempt",
            "status",
        ),
        "GitHub run evidence",
    )
    return GitHubRunEvidenceV1(
        run_id=_integer(data["id"], "run id", minimum=1),
        run_attempt=_integer(data["run_attempt"], "run attempt", minimum=1),
        head_sha=_git_sha(data["head_sha"], "run head SHA"),
        head_branch=_nonempty_string(data["head_branch"], "run branch"),
        workflow_name=_nonempty_string(data["name"], "run workflow name"),
        workflow_path=_nonempty_string(data["path"], "run workflow path"),
        event=_nonempty_string(data["event"], "run event"),
        status=_nonempty_string(data["status"], "run status"),
        conclusion=_nonempty_string(data["conclusion"], "run conclusion"),
        repository=_nonempty_string(data["repository"], "run repository"),
    )


@dataclass(frozen=True, slots=True)
class GitHubJobEvidenceV1:
    job_id: int
    run_id: int
    run_attempt: int
    head_sha: str
    name: str
    status: str
    conclusion: str
    started_at: str
    completed_at: str
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        _integer(self.job_id, "job id", minimum=1)
        _integer(self.run_id, "job run id", minimum=1)
        _integer(self.run_attempt, "job run attempt", minimum=1)
        _git_sha(self.head_sha, "job head SHA")
        _timestamp(self.started_at, "job started_at")
        _timestamp(self.completed_at, "job completed_at")
        if _timestamp_unix(self.started_at) > _timestamp_unix(self.completed_at):
            raise SWM0WS2SPilotAdoptionError("job timestamps are reversed")
        if (
            type(self.labels) is not tuple
            or not self.labels
            or any(type(label) is not str or not label for label in self.labels)
            or len(set(self.labels)) != len(self.labels)
        ):
            raise SWM0WS2SPilotAdoptionError("job labels are not exact unique strings")
        if (
            self.run_attempt != 1
            or self.name != EXPECTED_JOB_NAME
            or self.status != "completed"
            or self.conclusion != "success"
            or self.labels != (pilot.WORKFLOW_RUNNER_IMAGE,)
        ):
            raise SWM0WS2SPilotAdoptionError(
                "GitHub job identity, runner, or conclusion drifted"
            )

    def canonical(self) -> dict[str, Any]:
        return {
            "completed_at": self.completed_at,
            "conclusion": self.conclusion,
            "head_sha": self.head_sha,
            "id": self.job_id,
            "labels": list(self.labels),
            "name": self.name,
            "run_attempt": self.run_attempt,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "status": self.status,
        }


def _parse_job_evidence(value: object) -> GitHubJobEvidenceV1:
    data = _exact_object(
        value,
        (
            "completed_at",
            "conclusion",
            "head_sha",
            "id",
            "labels",
            "name",
            "run_attempt",
            "run_id",
            "started_at",
            "status",
        ),
        "GitHub job evidence",
    )
    labels = data["labels"]
    if type(labels) is not list:
        raise SWM0WS2SPilotAdoptionError("job labels must be an exact JSON list")
    return GitHubJobEvidenceV1(
        job_id=_integer(data["id"], "job id", minimum=1),
        run_id=_integer(data["run_id"], "job run id", minimum=1),
        run_attempt=_integer(
            data["run_attempt"], "job run attempt", minimum=1
        ),
        head_sha=_git_sha(data["head_sha"], "job head SHA"),
        name=_nonempty_string(data["name"], "job name"),
        status=_nonempty_string(data["status"], "job status"),
        conclusion=_nonempty_string(data["conclusion"], "job conclusion"),
        started_at=_timestamp(data["started_at"], "job started_at"),
        completed_at=_timestamp(data["completed_at"], "job completed_at"),
        labels=tuple(_nonempty_string(label, "job label") for label in labels),
    )


@dataclass(frozen=True, slots=True)
class GitHubArtifactEvidenceV1:
    artifact_id: int
    name: str
    digest: str
    size_in_bytes: int
    created_at: str
    expires_at: str
    expired: bool
    workflow_run_id: int
    workflow_run_head_sha: str

    def __post_init__(self) -> None:
        _integer(self.artifact_id, "artifact id", minimum=1)
        _integer(self.size_in_bytes, "artifact size", minimum=1)
        _integer(self.workflow_run_id, "artifact workflow run id", minimum=1)
        _nonempty_string(self.name, "artifact name")
        if type(self.expired) is not bool:
            raise SWM0WS2SPilotAdoptionError("artifact expired must be an exact bool")
        if self.expired is not False:
            raise SWM0WS2SPilotAdoptionError("expired pilot artifacts are not adoptable")
        if type(self.digest) is not str or not self.digest.startswith("sha256:"):
            raise SWM0WS2SPilotAdoptionError("artifact digest must use sha256:<hex>")
        _sha256(self.digest.removeprefix("sha256:"), "artifact digest")
        _git_sha(self.workflow_run_head_sha, "artifact workflow head SHA")
        _timestamp(self.created_at, "artifact created_at")
        _timestamp(self.expires_at, "artifact expires_at")
        if _timestamp_unix(self.created_at) >= _timestamp_unix(self.expires_at):
            raise SWM0WS2SPilotAdoptionError(
                "artifact expiry must be strictly after creation"
            )

    def canonical(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "digest": self.digest,
            "expired": self.expired,
            "expires_at": self.expires_at,
            "id": self.artifact_id,
            "name": self.name,
            "size_in_bytes": self.size_in_bytes,
            "workflow_run": {
                "head_sha": self.workflow_run_head_sha,
                "id": self.workflow_run_id,
            },
        }


def _parse_artifact_evidence(value: object) -> GitHubArtifactEvidenceV1:
    data = _exact_object(
        value,
        (
            "created_at",
            "digest",
            "expired",
            "expires_at",
            "id",
            "name",
            "size_in_bytes",
            "workflow_run",
        ),
        "GitHub artifact evidence",
    )
    workflow_run = _exact_object(
        data["workflow_run"],
        ("head_sha", "id"),
        "artifact workflow-run evidence",
    )
    expired = data["expired"]
    if type(expired) is not bool:
        raise SWM0WS2SPilotAdoptionError("artifact expired must be an exact bool")
    return GitHubArtifactEvidenceV1(
        artifact_id=_integer(data["id"], "artifact id", minimum=1),
        name=_nonempty_string(data["name"], "artifact name"),
        digest=_nonempty_string(data["digest"], "artifact digest"),
        size_in_bytes=_integer(
            data["size_in_bytes"], "artifact size", minimum=1
        ),
        created_at=_timestamp(data["created_at"], "artifact created_at"),
        expires_at=_timestamp(data["expires_at"], "artifact expires_at"),
        expired=expired,
        workflow_run_id=_integer(
            workflow_run["id"], "artifact workflow run id", minimum=1
        ),
        workflow_run_head_sha=_git_sha(
            workflow_run["head_sha"], "artifact workflow head SHA"
        ),
    )


@dataclass(frozen=True, slots=True)
class ArtifactArchiveEvidenceV1:
    archive_sha256: str
    archive_size_in_bytes: int
    member_name: str
    member_sha256: str
    member_size_in_bytes: int
    compression: str

    def __post_init__(self) -> None:
        _sha256(self.archive_sha256, "archive SHA")
        _sha256(self.member_sha256, "artifact member SHA")
        _integer(self.archive_size_in_bytes, "archive size", minimum=1)
        _integer(self.member_size_in_bytes, "artifact member size", minimum=1)
        if (
            self.member_name != EXPECTED_ARTIFACT_MEMBER
            or self.compression not in set(_ZIP_COMPRESSION_NAMES.values())
        ):
            raise SWM0WS2SPilotAdoptionError("artifact ZIP layout drifted")

    def canonical(self) -> dict[str, Any]:
        return {
            "archive_sha256": self.archive_sha256,
            "archive_size_in_bytes": self.archive_size_in_bytes,
            "compression": self.compression,
            "member_name": self.member_name,
            "member_sha256": self.member_sha256,
            "member_size_in_bytes": self.member_size_in_bytes,
        }


@dataclass(frozen=True, slots=True)
class RuntimeTelemetrySummaryV1:
    runtime_telemetry_sha256: str
    admitted: bool
    admission_limit_ns: int
    projection_multiplier: int
    projected_stage2_fit_and_replay_ns: int
    admission_stage1_total_ns: int
    task_preparation_count: int
    task_preparation_total_ns: int
    task_preparation_max_ns: int
    stage1_cell_count: int
    stage1_fit_ns: int
    stage1_replay_ns: int
    stage1_total_ns: int
    stage2_cell_count: int
    stage2_fit_ns: int
    stage2_replay_ns: int
    stage2_total_ns: int
    selected_rate_stage2_cell_count: int
    selected_rate_stage2_fit_ns: int
    selected_rate_stage2_replay_ns: int
    selected_rate_stage2_total_ns: int
    max_peak_rss_kib: int
    github_job_elapsed_seconds: int
    archive_size_in_bytes: int
    member_size_in_bytes: int

    def __post_init__(self) -> None:
        _sha256(self.runtime_telemetry_sha256, "runtime telemetry SHA")
        if type(self.admitted) is not bool or self.admitted is not True:
            raise SWM0WS2SPilotAdoptionError(
                "adoptable runtime summary requires exact admitted=true"
            )
        integer_fields = (
            "admission_limit_ns",
            "projection_multiplier",
            "projected_stage2_fit_and_replay_ns",
            "admission_stage1_total_ns",
            "task_preparation_count",
            "task_preparation_total_ns",
            "task_preparation_max_ns",
            "stage1_cell_count",
            "stage1_fit_ns",
            "stage1_replay_ns",
            "stage1_total_ns",
            "stage2_cell_count",
            "stage2_fit_ns",
            "stage2_replay_ns",
            "stage2_total_ns",
            "selected_rate_stage2_cell_count",
            "selected_rate_stage2_fit_ns",
            "selected_rate_stage2_replay_ns",
            "selected_rate_stage2_total_ns",
            "max_peak_rss_kib",
            "github_job_elapsed_seconds",
            "archive_size_in_bytes",
            "member_size_in_bytes",
        )
        for field in integer_fields:
            _integer(getattr(self, field), f"runtime summary {field}")
        if (
            self.admission_limit_ns != pilot.ADMISSION_LIMIT_NS
            or self.projection_multiplier != pilot.PROJECTION_MULTIPLIER
            or self.task_preparation_count != len(pilot.TASK_DRAW_INDICES)
            or self.stage1_cell_count != pilot.EXPECTED_CELL_COUNT
            or self.stage2_cell_count != pilot.EXPECTED_CELL_COUNT
            or self.selected_rate_stage2_cell_count
            != len(pilot.PUBLIC_ARMS) * len(pilot.TASK_DRAW_INDICES)
            or self.archive_size_in_bytes < 1
            or self.member_size_in_bytes < 1
        ):
            raise SWM0WS2SPilotAdoptionError(
                "runtime summary fixed counts or envelope drifted"
            )
        if (
            self.stage1_fit_ns + self.stage1_replay_ns != self.stage1_total_ns
            or self.stage2_fit_ns + self.stage2_replay_ns != self.stage2_total_ns
            or self.selected_rate_stage2_fit_ns
            + self.selected_rate_stage2_replay_ns
            != self.selected_rate_stage2_total_ns
            or self.admission_stage1_total_ns != self.stage1_total_ns
            or self.projected_stage2_fit_and_replay_ns
            != self.stage1_total_ns * self.projection_multiplier
            or self.admitted
            != (
                self.projected_stage2_fit_and_replay_ns
                <= self.admission_limit_ns
            )
            or self.selected_rate_stage2_fit_ns > self.stage2_fit_ns
            or self.selected_rate_stage2_replay_ns > self.stage2_replay_ns
            or self.selected_rate_stage2_total_ns > self.stage2_total_ns
        ):
            raise SWM0WS2SPilotAdoptionError(
                "runtime summary deterministic arithmetic drifted"
            )

    def canonical(self) -> dict[str, Any]:
        return {
            "admission": {
                "admission_limit_ns": self.admission_limit_ns,
                "admitted": self.admitted,
                "integer_projection_multiplier": self.projection_multiplier,
                "projected_stage2_fit_and_replay_ns": (
                    self.projected_stage2_fit_and_replay_ns
                ),
                "stage1_fit_and_replay_elapsed_ns_sum": (
                    self.admission_stage1_total_ns
                ),
            },
            "artifact_sizes": {
                "archive_size_in_bytes": self.archive_size_in_bytes,
                "member_size_in_bytes": self.member_size_in_bytes,
            },
            "github_job_elapsed_seconds": self.github_job_elapsed_seconds,
            "max_peak_rss_kib": self.max_peak_rss_kib,
            "max_peak_rss_scope": (
                "TASK_PREPARATION_AND_ALL_STAGE1_STAGE2_CELL_TELEMETRY"
            ),
            "prereg_resource_policy_status": PREREG_RESOURCE_POLICY_STATUS,
            "runtime_telemetry_sha256": self.runtime_telemetry_sha256,
            "schema_version": RUNTIME_SUMMARY_VERSION,
            "selected_rate_stage2": {
                "cell_count": self.selected_rate_stage2_cell_count,
                "fit_elapsed_ns_sum": self.selected_rate_stage2_fit_ns,
                "fit_and_replay_elapsed_ns_sum": (
                    self.selected_rate_stage2_total_ns
                ),
                "replay_elapsed_ns_sum": self.selected_rate_stage2_replay_ns,
                "selection_source": (
                    "THREE_VALIDATED_PILOT_SELECTIONS_X_THREE_DRAWS"
                ),
            },
            "stage1": {
                "cell_count": self.stage1_cell_count,
                "fit_elapsed_ns_sum": self.stage1_fit_ns,
                "fit_and_replay_elapsed_ns_sum": self.stage1_total_ns,
                "replay_elapsed_ns_sum": self.stage1_replay_ns,
            },
            "stage2": {
                "cell_count": self.stage2_cell_count,
                "fit_elapsed_ns_sum": self.stage2_fit_ns,
                "fit_and_replay_elapsed_ns_sum": self.stage2_total_ns,
                "replay_elapsed_ns_sum": self.stage2_replay_ns,
            },
            "summary_role": RUNTIME_SUMMARY_ROLE,
            "task_preparation": {
                "draw_count": self.task_preparation_count,
                "elapsed_ns_max": self.task_preparation_max_ns,
                "elapsed_ns_sum": self.task_preparation_total_ns,
            },
        }


def _read_exact_pilot_member(
    archive_bytes: object,
) -> tuple[bytes, ArtifactArchiveEvidenceV1]:
    if type(archive_bytes) is not bytes:
        raise SWM0WS2SPilotAdoptionError("artifact ZIP must be exact bytes")
    if not 1 <= len(archive_bytes) <= MAXIMUM_ARCHIVE_BYTES:
        raise SWM0WS2SPilotAdoptionError("artifact ZIP exceeds its size boundary")
    try:
        with ZipFile(BytesIO(archive_bytes), "r") as archive:
            infos = archive.infolist()
            if len(infos) != 1 or infos[0].filename != EXPECTED_ARTIFACT_MEMBER:
                raise SWM0WS2SPilotAdoptionError(
                    "artifact ZIP must contain exactly pilot.json"
                )
            info = infos[0]
            if (
                info.is_dir()
                or info.flag_bits & 0x1
                or info.compress_type not in _ZIP_COMPRESSION_NAMES
                or info.file_size < 1
                or info.file_size > MAXIMUM_MEMBER_BYTES
                or info.filename.startswith("/")
                or "\\" in info.filename
                or "\x00" in info.filename
            ):
                raise SWM0WS2SPilotAdoptionError(
                    "artifact ZIP member is unsafe or not the frozen layout"
                )
            member = archive.read(info)
            if len(member) != info.file_size:
                raise SWM0WS2SPilotAdoptionError("artifact ZIP member size drifted")
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise SWM0WS2SPilotAdoptionError(
            "artifact evidence is not a valid bounded ZIP"
        ) from exc
    evidence = ArtifactArchiveEvidenceV1(
        archive_sha256=hashlib.sha256(archive_bytes).hexdigest(),
        archive_size_in_bytes=len(archive_bytes),
        member_name=EXPECTED_ARTIFACT_MEMBER,
        member_sha256=hashlib.sha256(member).hexdigest(),
        member_size_in_bytes=len(member),
        compression=_ZIP_COMPRESSION_NAMES[info.compress_type],
    )
    return member, evidence


@dataclass(frozen=True, slots=True)
class SelectedArmConfigV1:
    public_arm: str
    operator_arm: S2SArm
    learning_rate_decimal: str
    selection_receipt_sha256: str
    config: S2STrainingConfig

    def __post_init__(self) -> None:
        if type(self.public_arm) is not str or self.public_arm not in pilot.PUBLIC_ARMS:
            raise SWM0WS2SPilotAdoptionError("selected public arm drifted")
        if type(self.operator_arm) is not S2SArm:
            raise SWM0WS2SPilotAdoptionError("selected operator arm drifted")
        if pilot.PUBLIC_TO_OPERATOR_ARM[self.public_arm] != self.operator_arm.value:
            raise SWM0WS2SPilotAdoptionError("public/operator arm mapping drifted")
        if (
            type(self.learning_rate_decimal) is not str
            or self.learning_rate_decimal not in pilot.LEARNING_RATE_LABELS
            or self.config.learning_rate.hex()
            != pilot.LEARNING_RATE_HEX[self.learning_rate_decimal]
        ):
            raise SWM0WS2SPilotAdoptionError("selected learning-rate binding drifted")
        _sha256(self.selection_receipt_sha256, "selection receipt SHA")
        expected = S2STrainingConfig(
            seed=pilot.INITIALIZER_SEED,
            max_updates=pilot.STAGE2_MAX_UPDATES,
            learning_rate=float(self.learning_rate_decimal),
            beta1=pilot.BETA1,
            beta2=pilot.BETA2,
            epsilon=pilot.EPSILON,
            gradient_clip=pilot.GRADIENT_CLIP,
            patience=pilot.PATIENCE,
            min_delta=pilot.MIN_DELTA,
        )
        if self.config != expected:
            raise SWM0WS2SPilotAdoptionError(
                "selected config drifted from the fixed pilot contract"
            )

    def canonical(self) -> dict[str, Any]:
        return {
            "config": self.config.canonical(),
            "learning_rate_decimal": self.learning_rate_decimal,
            "operator_arm": self.operator_arm.value,
            "public_arm": self.public_arm,
            "selection_receipt_sha256": self.selection_receipt_sha256,
        }


def _expected_exclusion() -> dict[str, Any]:
    return {
        "exclusion_scope": "EXACT_PILOT_SEED_AND_DRAW_PROVENANCE_ONLY",
        "excluded_external_seed_sha256_hex": pilot.EXTERNAL_SEED_SHA256_HEX,
        "excluded_ordered_task_draw_indices": list(pilot.TASK_DRAW_INDICES),
        "future_semantic_collision_policy": (
            "RETAIN_AND_DISCLOSE_NEVER_FILTER_OR_REROLL"
        ),
        "recorded_pilot_ordered_task_manifest_sha256s": list(
            pilot.EXPECTED_TASK_MANIFEST_SHA256S
        ),
        "recorded_pilot_ordered_structural_task_sha256s": list(
            pilot.EXPECTED_STRUCTURAL_TASK_SHA256S
        ),
        "required": True,
    }


def _validate_environment(value: object, source_commit: str) -> str:
    if type(value) is not dict:
        raise SWM0WS2SPilotAdoptionError(
            "complete pilot must bind an exact numeric environment"
        )
    try:
        validated = pilot._validate_numeric_environment(value)
    except pilot.SWM0WS2SPilotError as exc:
        raise SWM0WS2SPilotAdoptionError(
            "pilot numeric environment is malformed"
        ) from exc
    if (
        validated["source_commit"] != source_commit
        or validated["python_version"] != pilot.WORKFLOW_PYTHON_VERSION
        or validated["runner_os"] != "Linux"
        or validated["runner_arch"] != "X64"
        or validated["platform_system"] != "Linux"
        or validated["thread_environment"] != pilot.WORKFLOW_FIXED_ENVIRONMENT
    ):
        raise SWM0WS2SPilotAdoptionError(
            "pilot environment drifted from the public workflow envelope"
        )
    return canonical_json(validated)


def _derive_selected_configs(
    deterministic: Mapping[str, Any],
) -> tuple[SelectedArmConfigV1, ...]:
    raw_selections = deterministic["selections"]
    if type(raw_selections) is not list or len(raw_selections) != len(ALL_ARMS):
        raise SWM0WS2SPilotAdoptionError(
            "complete pilot lacks all three derived selections"
        )
    rows: list[SelectedArmConfigV1] = []
    for public_arm, operator_arm, selection in zip(
        pilot.PUBLIC_ARMS, ALL_ARMS, raw_selections, strict=True
    ):
        if type(selection) is not dict or selection.get("public_arm") != public_arm:
            raise SWM0WS2SPilotAdoptionError("pilot selection order drifted")
        label = selection.get("selected_learning_rate_decimal")
        if type(label) is not str or label not in pilot.LEARNING_RATE_LABELS:
            raise SWM0WS2SPilotAdoptionError("pilot selected rate is unsupported")
        config = S2STrainingConfig(
            seed=pilot.INITIALIZER_SEED,
            max_updates=pilot.STAGE2_MAX_UPDATES,
            learning_rate=float(label),
            beta1=pilot.BETA1,
            beta2=pilot.BETA2,
            epsilon=pilot.EPSILON,
            gradient_clip=pilot.GRADIENT_CLIP,
            patience=pilot.PATIENCE,
            min_delta=pilot.MIN_DELTA,
        )
        rows.append(
            SelectedArmConfigV1(
                public_arm=public_arm,
                operator_arm=operator_arm,
                learning_rate_decimal=label,
                selection_receipt_sha256=_sha256(
                    selection.get("selection_receipt_sha256"),
                    "selection receipt SHA",
                ),
                config=config,
            )
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True, init=False)
class PilotAdoptionReceiptV1:
    source_commit: str
    pilot_artifact_self_sha256: str
    pilot_artifact_bytes_sha256: str
    deterministic_receipt_sha256: str
    environment_json: str
    environment_sha256: str
    task_batch_sha256: str
    task_seed_commitment_sha256: str
    pilot_external_seed_sha256_hex: str
    exclusion_json: str
    selected_configs: tuple[SelectedArmConfigV1, ...]
    protocol_config: protocol.S2SProtocolConfig
    github_run: GitHubRunEvidenceV1
    github_job: GitHubJobEvidenceV1
    github_artifact: GitHubArtifactEvidenceV1
    archive: ArtifactArchiveEvidenceV1
    runtime_summary: RuntimeTelemetrySummaryV1
    receipt_sha256: str

    def __init__(self, *_: object, **__: object) -> None:
        raise SWM0WS2SPilotAdoptionError(
            "adoption receipts can only be issued by evidence-replaying APIs"
        )

    def __post_init__(self) -> None:
        _git_sha(self.source_commit, "adoption source commit")
        for field in (
            "pilot_artifact_self_sha256",
            "pilot_artifact_bytes_sha256",
            "deterministic_receipt_sha256",
            "environment_sha256",
            "task_batch_sha256",
            "task_seed_commitment_sha256",
            "pilot_external_seed_sha256_hex",
            "receipt_sha256",
        ):
            _sha256(getattr(self, field), field)
        try:
            environment = json.loads(self.environment_json)
            exclusion = json.loads(self.exclusion_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SWM0WS2SPilotAdoptionError(
                "adoption bound JSON is malformed"
            ) from exc
        if (
            canonical_json(environment) != self.environment_json
            or canonical_json(exclusion) != self.exclusion_json
        ):
            raise SWM0WS2SPilotAdoptionError(
                "adoption bound JSON is not canonical"
            )
        if canonical_sha256(environment) != self.environment_sha256:
            raise SWM0WS2SPilotAdoptionError("environment hash mismatch")
        _validate_environment(environment, self.source_commit)
        if canonical_json(exclusion) != canonical_json(_expected_exclusion()):
            raise SWM0WS2SPilotAdoptionError("pilot exclusion provenance drifted")
        if (
            self.task_batch_sha256 != pilot.EXPECTED_TASK_BATCH_SHA256
            or self.task_seed_commitment_sha256
            != pilot.EXPECTED_SEED_COMMITMENT_SHA256
            or self.pilot_external_seed_sha256_hex
            != pilot.EXTERNAL_SEED_SHA256_HEX
            or self.task_seed_commitment_sha256
            == self.pilot_external_seed_sha256_hex
        ):
            raise SWM0WS2SPilotAdoptionError(
                "pilot task commitment and external-seed provenance were confused"
            )
        if (
            type(self.selected_configs) is not tuple
            or len(self.selected_configs) != len(ALL_ARMS)
            or tuple(row.public_arm for row in self.selected_configs)
            != pilot.PUBLIC_ARMS
            or tuple(row.operator_arm for row in self.selected_configs) != ALL_ARMS
        ):
            raise SWM0WS2SPilotAdoptionError(
                "adoption requires all three selected configs in fixed order"
            )
        if type(self.protocol_config) is not protocol.S2SProtocolConfig:
            raise SWM0WS2SPilotAdoptionError(
                "adoption protocol projection has the wrong type"
            )
        if type(self.runtime_summary) is not RuntimeTelemetrySummaryV1:
            raise SWM0WS2SPilotAdoptionError(
                "adoption runtime summary has the wrong type"
            )
        protocol.parse_protocol_config(self.protocol_config.canonical())
        expected_arm_configs = tuple(
            (row.operator_arm, row.config) for row in self.selected_configs
        )
        expected_exclusion = (
            (
                pilot.EXPECTED_SEED_COMMITMENT_SHA256,
                tuple(pilot.TASK_DRAW_INDICES),
            ),
        )
        if (
            self.protocol_config.arm_configs != expected_arm_configs
            or self.protocol_config.excluded_task_provenance != expected_exclusion
        ):
            raise SWM0WS2SPilotAdoptionError(
                "protocol projection drifted from the pilot selection or exclusion"
            )
        if (
            self.github_run.head_sha != self.source_commit
            or self.github_job.head_sha != self.source_commit
            or self.github_artifact.workflow_run_head_sha != self.source_commit
            or self.github_job.run_id != self.github_run.run_id
            or self.github_artifact.workflow_run_id != self.github_run.run_id
            or self.github_job.run_attempt != self.github_run.run_attempt
            or self.github_artifact.name != _artifact_name(self.github_run.run_id)
            or self.github_artifact.digest
            != f"sha256:{self.archive.archive_sha256}"
            or self.github_artifact.size_in_bytes
            != self.archive.archive_size_in_bytes
            or self.archive.member_sha256 != self.pilot_artifact_bytes_sha256
            or self.runtime_summary.archive_size_in_bytes
            != self.archive.archive_size_in_bytes
            or self.runtime_summary.member_size_in_bytes
            != self.archive.member_size_in_bytes
            or self.runtime_summary.github_job_elapsed_seconds
            != _timestamp_unix(self.github_job.completed_at)
            - _timestamp_unix(self.github_job.started_at)
        ):
            raise SWM0WS2SPilotAdoptionError(
                "GitHub, source, archive, and pilot provenance do not cross-bind"
            )
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SPilotAdoptionError("adoption receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return _adoption_unsigned(
            {
                "source_commit": self.source_commit,
                "pilot_artifact_self_sha256": self.pilot_artifact_self_sha256,
                "pilot_artifact_bytes_sha256": self.pilot_artifact_bytes_sha256,
                "deterministic_receipt_sha256": self.deterministic_receipt_sha256,
                "environment_json": self.environment_json,
                "environment_sha256": self.environment_sha256,
                "task_batch_sha256": self.task_batch_sha256,
                "task_seed_commitment_sha256": self.task_seed_commitment_sha256,
                "pilot_external_seed_sha256_hex": self.pilot_external_seed_sha256_hex,
                "exclusion_json": self.exclusion_json,
                "selected_configs": self.selected_configs,
                "protocol_config": self.protocol_config,
                "github_run": self.github_run,
                "github_job": self.github_job,
                "github_artifact": self.github_artifact,
                "archive": self.archive,
                "runtime_summary": self.runtime_summary,
            }
        )

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def _adoption_unsigned(values: Mapping[str, Any]) -> dict[str, Any]:
    environment = json.loads(values["environment_json"])
    exclusion = json.loads(values["exclusion_json"])
    github_run = values["github_run"]
    github_job = values["github_job"]
    github_artifact = values["github_artifact"]
    archive = values["archive"]
    protocol_config = values["protocol_config"]
    selected_configs = values["selected_configs"]
    runtime_summary = values["runtime_summary"]
    run = github_run.canonical()
    job = github_job.canonical()
    artifact = github_artifact.canonical()
    return {
        "adoption_status": ADOPTION_STATUS,
        "claim_boundary": CLAIM_BOUNDARY,
        "github_evidence": {
            "artifact": artifact,
            "artifact_api_projection_sha256": canonical_sha256(artifact),
            "assurance": GITHUB_EVIDENCE_ASSURANCE,
            "job": job,
            "job_api_projection_sha256": canonical_sha256(job),
            "run": run,
            "run_api_projection_sha256": canonical_sha256(run),
        },
        "pilot": {
            "artifact_bytes_sha256": values["pilot_artifact_bytes_sha256"],
            "artifact_self_sha256": values["pilot_artifact_self_sha256"],
            "contract_sha256": pilot.PILOT_CONTRACT_SHA256,
            "deterministic_receipt_sha256": values[
                "deterministic_receipt_sha256"
            ],
            "execution_bound_numeric_environment": environment,
            "execution_bound_numeric_environment_sha256": values[
                "environment_sha256"
            ],
            "future_confirmatory_exclusion": exclusion,
            "future_confirmatory_exclusion_sha256": canonical_sha256(exclusion),
            "pilot_external_seed_sha256_hex": values[
                "pilot_external_seed_sha256_hex"
            ],
            "source_commit": values["source_commit"],
            "stage2_cell_count": pilot.EXPECTED_CELL_COUNT,
            "stage2_replay_validated_count": pilot.EXPECTED_CELL_COUNT,
            "task_batch_sha256": values["task_batch_sha256"],
            "task_seed_commitment_sha256": values[
                "task_seed_commitment_sha256"
            ],
            "terminal_status": pilot.TERMINAL_COMPLETE,
        },
        "pilot_artifact_archive": archive.canonical(),
        "protocol_config_projection": protocol_config.canonical(),
        "runtime_telemetry_summary": runtime_summary.canonical(),
        "schema_version": SCHEMA_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "selected_arm_configs": [
            row.canonical() for row in selected_configs
        ],
        "verdict": VERDICT,
    }


def _derive_runtime_summary(
    runtime: Mapping[str, Any],
    selected: tuple[SelectedArmConfigV1, ...],
    job: GitHubJobEvidenceV1,
    archive: ArtifactArchiveEvidenceV1,
) -> RuntimeTelemetrySummaryV1:
    admission = runtime["admission"]
    task_preparation = runtime["task_preparation_runtime"]
    cells = runtime["cell_runtime"]
    if (
        type(admission) is not dict
        or admission.get("admitted") is not True
        or type(task_preparation) is not list
        or type(cells) is not list
    ):
        raise SWM0WS2SPilotAdoptionError(
            "complete pilot runtime telemetry cannot be summarized"
        )
    stage1 = [cell for cell in cells if cell["stage"] == pilot.STAGE1_NAME]
    stage2 = [cell for cell in cells if cell["stage"] == pilot.STAGE2_NAME]
    selected_rate_by_arm = {
        row.public_arm: row.learning_rate_decimal for row in selected
    }
    selected_stage2 = [
        cell
        for cell in stage2
        if cell["learning_rate_decimal"]
        == selected_rate_by_arm[cell["public_arm"]]
    ]

    def totals(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
        return (
            sum(row["fit_elapsed_ns"] for row in rows),
            sum(row["replay_elapsed_ns"] for row in rows),
            sum(row["fit_and_replay_elapsed_ns"] for row in rows),
        )

    stage1_fit, stage1_replay, stage1_total = totals(stage1)
    stage2_fit, stage2_replay, stage2_total = totals(stage2)
    selected_fit, selected_replay, selected_total = totals(selected_stage2)
    peak_rss_values = [
        *(row["peak_rss_kib_after"] for row in task_preparation),
        *(row["peak_rss_kib_after"] for row in cells),
    ]
    return RuntimeTelemetrySummaryV1(
        runtime_telemetry_sha256=_sha256(
            runtime["runtime_telemetry_sha256"], "runtime telemetry SHA"
        ),
        admitted=admission["admitted"],
        admission_limit_ns=admission["admission_limit_ns"],
        projection_multiplier=admission["integer_projection_multiplier"],
        projected_stage2_fit_and_replay_ns=admission[
            "projected_stage2_fit_and_replay_ns"
        ],
        admission_stage1_total_ns=admission[
            "stage1_fit_and_replay_elapsed_ns_sum"
        ],
        task_preparation_count=len(task_preparation),
        task_preparation_total_ns=sum(
            row["elapsed_ns"] for row in task_preparation
        ),
        task_preparation_max_ns=max(
            row["elapsed_ns"] for row in task_preparation
        ),
        stage1_cell_count=len(stage1),
        stage1_fit_ns=stage1_fit,
        stage1_replay_ns=stage1_replay,
        stage1_total_ns=stage1_total,
        stage2_cell_count=len(stage2),
        stage2_fit_ns=stage2_fit,
        stage2_replay_ns=stage2_replay,
        stage2_total_ns=stage2_total,
        selected_rate_stage2_cell_count=len(selected_stage2),
        selected_rate_stage2_fit_ns=selected_fit,
        selected_rate_stage2_replay_ns=selected_replay,
        selected_rate_stage2_total_ns=selected_total,
        max_peak_rss_kib=max(peak_rss_values),
        github_job_elapsed_seconds=(
            _timestamp_unix(job.completed_at) - _timestamp_unix(job.started_at)
        ),
        archive_size_in_bytes=archive.archive_size_in_bytes,
        member_size_in_bytes=archive.member_size_in_bytes,
    )


def _issue_receipt(
    values: Mapping[str, Any], receipt_sha256: str
) -> PilotAdoptionReceiptV1:
    receipt = object.__new__(PilotAdoptionReceiptV1)
    for field, value in values.items():
        object.__setattr__(receipt, field, value)
    object.__setattr__(receipt, "receipt_sha256", receipt_sha256)
    receipt.__post_init__()
    return receipt


def build_pilot_adoption_receipt(
    *,
    pilot_artifact_zip_bytes: bytes,
    github_run: Mapping[str, Any],
    github_job: Mapping[str, Any],
    github_artifact: Mapping[str, Any],
) -> PilotAdoptionReceiptV1:
    """Reconstruct a prereg-ready candidate config from exact supplied evidence.

    The function intentionally has no learning-rate, seed, threshold, verdict,
    or chronology override.  GitHub inputs are strict minimal API projections;
    callers must preserve them independently before invoking this boundary.
    """

    run = _parse_run_evidence(github_run)
    job = _parse_job_evidence(github_job)
    artifact_evidence = _parse_artifact_evidence(github_artifact)
    member_bytes, archive = _read_exact_pilot_member(pilot_artifact_zip_bytes)
    if (
        artifact_evidence.name != _artifact_name(run.run_id)
        or artifact_evidence.digest != f"sha256:{archive.archive_sha256}"
        or artifact_evidence.size_in_bytes != archive.archive_size_in_bytes
    ):
        raise SWM0WS2SPilotAdoptionError(
            "artifact API metadata does not describe the supplied exact ZIP"
        )
    try:
        parsed_pilot = pilot.parse_pilot_artifact_bytes(member_bytes)
    except pilot.SWM0WS2SPilotError as exc:
        raise SWM0WS2SPilotAdoptionError(
            "pilot ZIP member is not the exact canonical strict artifact"
        ) from exc
    deterministic = parsed_pilot["deterministic_receipt"]
    stage2 = deterministic["ordered_stage2_cell_receipts"]
    if (
        parsed_pilot["terminal_status"] != pilot.TERMINAL_COMPLETE
        or deterministic["completion"] != "COMPLETE_FIXED_DEVELOPMENT_ROSTER"
        or deterministic["selection_status"]
        != "COMPLETE_DEVELOPMENT_SELECTION"
        or type(stage2) is not list
        or len(stage2) != pilot.EXPECTED_CELL_COUNT
        or any(
            type(cell) is not dict or cell.get("replay_validated") is not True
            for cell in stage2
        )
    ):
        raise SWM0WS2SPilotAdoptionError(
            "only DEVELOPMENT_COMPLETE with all 27 replay-valid stage2 cells is adoptable"
        )
    if deterministic["contract_sha256"] != pilot.PILOT_CONTRACT_SHA256:
        raise SWM0WS2SPilotAdoptionError("pilot contract binding drifted")
    exclusion = deterministic["future_confirmatory_exclusion"]
    if canonical_json(exclusion) != canonical_json(_expected_exclusion()):
        raise SWM0WS2SPilotAdoptionError("pilot exclusion provenance drifted")
    task_bindings = deterministic["ordered_task_bindings"]
    if (
        type(task_bindings) is not list
        or len(task_bindings) != len(pilot.TASK_DRAW_INDICES)
        or any(
            type(binding) is not dict
            or binding.get("seed_commitment_sha256")
            != pilot.EXPECTED_SEED_COMMITMENT_SHA256
            for binding in task_bindings
        )
    ):
        raise SWM0WS2SPilotAdoptionError("pilot task seed commitment drifted")
    selected = _derive_selected_configs(deterministic)
    config = protocol.build_protocol_config(
        tuple((row.operator_arm, row.config) for row in selected),
        excluded_task_provenance=(
            (
                pilot.EXPECTED_SEED_COMMITMENT_SHA256,
                tuple(pilot.TASK_DRAW_INDICES),
            ),
        ),
    )
    environment = deterministic["execution_bound_numeric_environment"]
    environment_json = _validate_environment(environment, run.head_sha)
    environment_sha = deterministic[
        "execution_bound_numeric_environment_sha256"
    ]
    if (
        _sha256(environment_sha, "pilot environment SHA")
        != canonical_sha256(environment)
        or deterministic["task_batch_sha256"]
        != pilot.EXPECTED_TASK_BATCH_SHA256
    ):
        raise SWM0WS2SPilotAdoptionError(
            "pilot environment or task-batch binding drifted"
        )
    runtime_summary = _derive_runtime_summary(
        parsed_pilot["runtime_telemetry"], selected, job, archive
    )
    values = {
        "source_commit": run.head_sha,
        "pilot_artifact_self_sha256": _sha256(
            parsed_pilot["artifact_sha256"], "pilot artifact self SHA"
        ),
        "pilot_artifact_bytes_sha256": archive.member_sha256,
        "deterministic_receipt_sha256": _sha256(
            deterministic["deterministic_receipt_sha256"],
            "pilot deterministic receipt SHA",
        ),
        "environment_json": environment_json,
        "environment_sha256": environment_sha,
        "task_batch_sha256": deterministic["task_batch_sha256"],
        "task_seed_commitment_sha256": pilot.EXPECTED_SEED_COMMITMENT_SHA256,
        "pilot_external_seed_sha256_hex": pilot.EXTERNAL_SEED_SHA256_HEX,
        "exclusion_json": canonical_json(exclusion),
        "selected_configs": selected,
        "protocol_config": config,
        "github_run": run,
        "github_job": job,
        "github_artifact": artifact_evidence,
        "archive": archive,
        "runtime_summary": runtime_summary,
    }
    receipt_hash = canonical_sha256(_adoption_unsigned(values))
    return _issue_receipt(values, receipt_hash)


def canonical_receipt_bytes(
    receipt: PilotAdoptionReceiptV1,
    *,
    pilot_artifact_zip_bytes: bytes,
    github_run: Mapping[str, Any],
    github_job: Mapping[str, Any],
    github_artifact: Mapping[str, Any],
) -> bytes:
    """Issue canonical bytes only after replaying the exact source evidence."""

    if type(receipt) is not PilotAdoptionReceiptV1:
        raise SWM0WS2SPilotAdoptionError(
            "canonical serialization requires an exact adoption receipt"
        )
    replayed = validate_pilot_adoption_receipt(
        receipt.canonical(),
        pilot_artifact_zip_bytes=pilot_artifact_zip_bytes,
        github_run=github_run,
        github_job=github_job,
        github_artifact=github_artifact,
    )
    return (canonical_json(replayed.canonical()) + "\n").encode("utf-8")


def _loads_canonical_receipt_bytes(value: object) -> dict[str, Any]:
    if type(value) is not bytes:
        raise SWM0WS2SPilotAdoptionError("adoption receipt must be exact bytes")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise SWM0WS2SPilotAdoptionError(
                    "adoption receipt contains a duplicate key"
                )
            result[key] = item
        return result

    def reject_float(_: str) -> object:
        raise SWM0WS2SPilotAdoptionError(
            "adoption receipt cannot contain numeric floats"
        )

    try:
        parsed = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SWM0WS2SPilotAdoptionError(
            "adoption receipt is not canonical JSON"
        ) from exc
    if type(parsed) is not dict or value != (
        canonical_json(parsed) + "\n"
    ).encode("utf-8"):
        raise SWM0WS2SPilotAdoptionError(
            "adoption receipt bytes are not the exact canonical encoding"
        )
    return parsed


def validate_pilot_adoption_receipt(
    value: Mapping[str, Any],
    *,
    pilot_artifact_zip_bytes: bytes,
    github_run: Mapping[str, Any],
    github_job: Mapping[str, Any],
    github_artifact: Mapping[str, Any],
) -> PilotAdoptionReceiptV1:
    """Replay a receipt from its independently supplied source evidence."""

    if type(value) is not dict:
        raise SWM0WS2SPilotAdoptionError(
            "adoption receipt value must be an exact JSON object"
        )
    rebuilt = build_pilot_adoption_receipt(
        pilot_artifact_zip_bytes=pilot_artifact_zip_bytes,
        github_run=github_run,
        github_job=github_job,
        github_artifact=github_artifact,
    )
    if canonical_json(value) != canonical_json(rebuilt.canonical()):
        raise SWM0WS2SPilotAdoptionError(
            "adoption receipt does not exactly replay from supplied evidence"
        )
    return rebuilt


def parse_pilot_adoption_receipt_bytes(
    value: bytes,
    *,
    pilot_artifact_zip_bytes: bytes,
    github_run: Mapping[str, Any],
    github_job: Mapping[str, Any],
    github_artifact: Mapping[str, Any],
) -> PilotAdoptionReceiptV1:
    """Strictly parse canonical bytes and replay every external binding."""

    parsed = _loads_canonical_receipt_bytes(value)
    return validate_pilot_adoption_receipt(
        parsed,
        pilot_artifact_zip_bytes=pilot_artifact_zip_bytes,
        github_run=github_run,
        github_job=github_job,
        github_artifact=github_artifact,
    )


__all__ = [
    "ADOPTION_STATUS",
    "ArtifactArchiveEvidenceV1",
    "CLAIM_BOUNDARY",
    "GitHubArtifactEvidenceV1",
    "GitHubJobEvidenceV1",
    "GitHubRunEvidenceV1",
    "PilotAdoptionReceiptV1",
    "PREREG_RESOURCE_POLICY_STATUS",
    "RUNTIME_SUMMARY_ROLE",
    "RUNTIME_SUMMARY_VERSION",
    "RuntimeTelemetrySummaryV1",
    "SCHEMA_VERSION",
    "SCIENTIFIC_STATUS",
    "SWM0WS2SPilotAdoptionError",
    "SelectedArmConfigV1",
    "VERDICT",
    "build_pilot_adoption_receipt",
    "canonical_json",
    "canonical_receipt_bytes",
    "canonical_sha256",
    "parse_pilot_adoption_receipt_bytes",
    "validate_pilot_adoption_receipt",
]
