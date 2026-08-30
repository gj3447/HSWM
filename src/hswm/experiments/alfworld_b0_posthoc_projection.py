"""Derive one aggregate-only diagnostic from a sealed ALFWorld B0 archive.

This is a posthoc observability repair, not a retry, outcome, or efficacy
analysis.  It never extracts the archive and delegates calibration receipt
validation to the already tested B0 public projector.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from typing import Any, Mapping

from _research.dnrd5 import canonical_json as canonical_json_module
from _research.dnrd5.canonical_json import canonical_bytes
from . import alfworld_b0_calibration as calibration_module
from . import alfworld_b0_live as live_module
from . import continual_live as continual_live_module
from .alfworld_b0_calibration import (
    COMPLETE_STATUS,
    INCONCLUSIVE_STATUS,
    public_projection as calibration_public_projection,
)
from .alfworld_b0_live import LIVE_SCHEMA
from .continual_live import (
    ContinualLiveError,
    _sha256_file,
    _tar_member_bytes,
    _tar_member_sha256,
    _tar_regular_members,
)


POSTHOC_SCHEMA = "hswm-alfworld-b0-posthoc-derived-public/v1"
POSTHOC_ROLE = "POSTHOC_DERIVED_PUBLIC_DIAGNOSTIC_FROM_SEALED_B0_ARTIFACT_NO_RERUN"
SCIENTIFIC_STATUS = (
    "POSTHOC_OPERATIONAL_DIAGNOSTIC_ONLY_G0_NOT_PASSED_"
    "G1_NOT_EVALUATED_NO_HSWM_EFFICACY"
)
CLAIM_CEILING = (
    "NO_RERUN_NO_NEW_OUTCOME_NO_LEARNING_NO_REVISION_"
    "NO_G0_PASS_NO_G1_NO_HSWM_EFFICACY_CLAIM"
)
MAX_ARCHIVE_BYTES = 16_000_000
MAX_EXPANDED_BYTES = 16_000_000
MAX_CONTENT_MEMBER_BYTES = 4_000_000
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ERROR_CLASS = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_CALIBRATION_TOTAL_FIELDS = {
    "actor_call_count",
    "environment_step_count",
    "input_token_count",
    "output_token_count",
    "token_preflight_token_count",
    "issued_completion_post_count",
    "issued_tokenize_post_count",
    "issued_http_post_count",
    "validated_model_response_count",
    "completed_episode_count",
    "wall_microseconds",
}
_ISSUED_FIELDS = {
    "issued_tokenize_post_count",
    "issued_completion_post_count",
    "issued_http_post_count",
}
_FORBIDDEN_KEYS = {
    "opaque_uid",
    "task_group_uid",
    "relative_path",
    "action",
    "observation",
    "outcome",
    "actor_trace",
    "episode_prefix",
    "inner_private_receipt",
}
_PROJECTION_SOURCES = (
    "_research/dnrd5/canonical_json.py",
    "src/hswm/experiments/alfworld_b0_calibration.py",
    "src/hswm/experiments/alfworld_b0_live.py",
    "src/hswm/experiments/alfworld_b0_posthoc_projection.py",
    "src/hswm/experiments/continual_live.py",
)


class AlfworldB0PosthocProjectionError(RuntimeError):
    """The sealed archive cannot support the bounded derived projection."""


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise AlfworldB0PosthocProjectionError(f"{label} is not a SHA-256 digest")
    return value


def _error_class(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _ERROR_CLASS.fullmatch(value) is None:
        raise AlfworldB0PosthocProjectionError(f"{label} is not a bounded error class")
    return value


def _canonical_object(raw: bytes, label: str) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AlfworldB0PosthocProjectionError(
                    f"{label} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AlfworldB0PosthocProjectionError(
            f"{label} is not strict JSON"
        ) from error
    if not isinstance(value, dict) or canonical_bytes(value) + b"\n" != raw:
        raise AlfworldB0PosthocProjectionError(
            f"{label} is not one canonical newline-delimited object"
        )
    return value


def _nonnegative_ints(
    value: object, expected: set[str], label: str
) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != expected:
        raise AlfworldB0PosthocProjectionError(f"{label} field set drifted")
    if any(type(item) is not int or item < 0 for item in value.values()):
        raise AlfworldB0PosthocProjectionError(f"{label} contains an invalid count")
    return {key: int(value[key]) for key in sorted(expected)}


def _assert_no_private_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _FORBIDDEN_KEYS or key.startswith("raw_") or key.endswith("_path"):
                raise AlfworldB0PosthocProjectionError(
                    "derived public projection contains a private field"
                )
            _assert_no_private_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_private_keys(item)


def projection_source_binding(repo: Path) -> dict[str, object]:
    """Bind the derived projector to one clean committed source closure."""

    if not repo.is_absolute() or repo.is_symlink() or not repo.is_dir():
        raise AlfworldB0PosthocProjectionError("projection repository is invalid")

    def git(*args: str) -> bytes:
        completed = subprocess.run(
            ("git", "-C", str(repo), *args),
            check=False,
            capture_output=True,
        )
        if completed.returncode or completed.stderr:
            raise AlfworldB0PosthocProjectionError("projection git binding failed")
        return completed.stdout

    if git("status", "--porcelain").strip():
        raise AlfworldB0PosthocProjectionError(
            "projection repository must be a clean checkout"
        )
    commit = git("rev-parse", "HEAD").decode("ascii", "strict").strip()
    tree = git("rev-parse", "HEAD^{tree}").decode("ascii", "strict").strip()
    if _HEX40.fullmatch(commit) is None or _HEX40.fullmatch(tree) is None:
        raise AlfworldB0PosthocProjectionError("projection source identity is invalid")
    sources: dict[str, str] = {}
    loaded_sources = {
        "_research/dnrd5/canonical_json.py": Path(canonical_json_module.__file__),
        "src/hswm/experiments/alfworld_b0_calibration.py": Path(
            calibration_module.__file__
        ),
        "src/hswm/experiments/alfworld_b0_live.py": Path(live_module.__file__),
        "src/hswm/experiments/alfworld_b0_posthoc_projection.py": Path(__file__),
        "src/hswm/experiments/continual_live.py": Path(continual_live_module.__file__),
    }
    for relative in _PROJECTION_SOURCES:
        path = repo / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or loaded_sources[relative].resolve(strict=True)
            != path.resolve(strict=True)
        ):
            raise AlfworldB0PosthocProjectionError("projection source is unavailable")
        raw = path.read_bytes()
        if git("show", f"HEAD:{relative}") != raw:
            raise AlfworldB0PosthocProjectionError(
                "projection source differs from committed bytes"
            )
        sources[relative] = _digest(raw)
    return {"commit": commit, "tree": tree, "source_code_sha256": sources}


def _validate_projection_source_binding(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "commit",
        "tree",
        "source_code_sha256",
    }:
        raise AlfworldB0PosthocProjectionError("projection source binding is invalid")
    sources = value.get("source_code_sha256")
    if (
        not isinstance(value.get("commit"), str)
        or _HEX40.fullmatch(str(value["commit"])) is None
        or not isinstance(value.get("tree"), str)
        or _HEX40.fullmatch(str(value["tree"])) is None
        or not isinstance(sources, dict)
        or set(sources) != set(_PROJECTION_SOURCES)
    ):
        raise AlfworldB0PosthocProjectionError("projection source identity drifted")
    for digest in sources.values():
        _sha(digest, "projection source digest")
    return {
        "commit": value["commit"],
        "tree": value["tree"],
        "source_code_sha256": {key: sources[key] for key in sorted(sources)},
    }
def _validate_original_public(
    value: Mapping[str, object],
    *,
    raw_private_sha256: str,
    expected_source_commit: str,
    expected_protocol_sha256: str,
) -> dict[str, str]:
    expected = {
        "schema_version",
        "status",
        "claim_ceiling",
        "execution",
        "selection_commitments",
        "resource_totals",
        "private_receipt_sha256",
        "public_projection_sha256",
    }
    unsigned = {key: item for key, item in value.items() if key != "public_projection_sha256"}
    execution = value.get("execution")
    if (
        set(value) != expected
        or value.get("schema_version") != LIVE_SCHEMA
        or value.get("status") not in {COMPLETE_STATUS, INCONCLUSIVE_STATUS}
        or value.get("claim_ceiling")
        != "EXPLORATORY_B0_CALIBRATION_ONLY_G0_NOT_PASSED_NOT_G1"
        or not isinstance(value.get("selection_commitments"), dict)
        or value.get("resource_totals") != {}
        or value.get("private_receipt_sha256") != raw_private_sha256
        or value.get("public_projection_sha256") != _digest(canonical_bytes(unsigned))
        or not isinstance(execution, dict)
        or set(execution) != {"commit", "tree", "protocol_sha256"}
        or execution.get("commit") != expected_source_commit
        or execution.get("protocol_sha256") != expected_protocol_sha256
        or not isinstance(execution.get("tree"), str)
        or _HEX40.fullmatch(str(execution["tree"])) is None
    ):
        raise AlfworldB0PosthocProjectionError(
            "original live public projection binding drifted"
        )
    return {
        "commit": expected_source_commit,
        "tree": str(execution["tree"]),
        "protocol_sha256": expected_protocol_sha256,
    }


def _validate_calibration_aggregate(
    value: Mapping[str, object], issued_counts: object
) -> dict[str, object]:
    totals = _nonnegative_ints(
        value.get("resource_totals"),
        _CALIBRATION_TOTAL_FIELDS,
        "calibration resource totals",
    )
    issued = _nonnegative_ints(issued_counts, _ISSUED_FIELDS, "outer issued counts")
    if (
        any(issued[key] != totals[key] for key in _ISSUED_FIELDS)
        or issued["issued_http_post_count"]
        != issued["issued_tokenize_post_count"]
        + issued["issued_completion_post_count"]
    ):
        raise AlfworldB0PosthocProjectionError(
            "outer issued counts differ from sealed calibration totals"
        )
    split_counts = _nonnegative_ints(
        value.get("split_counts"), {"train", "valid_seen"}, "split counts"
    )
    success_counts = _nonnegative_ints(
        value.get("success_counts"), {"train", "valid_seen"}, "success counts"
    )
    invalid_counts = _nonnegative_ints(
        value.get("invalid_counts"), {"train", "valid_seen"}, "invalid counts"
    )
    for split in ("train", "valid_seen"):
        if success_counts[split] + invalid_counts[split] > split_counts[split]:
            raise AlfworldB0PosthocProjectionError("calibration split counts are impossible")
    if split_counts["train"] > 8 or split_counts["valid_seen"] > 4:
        raise AlfworldB0PosthocProjectionError("calibration split bounds drifted")
    failure_class = _error_class(value.get("failure_class"), "calibration failure class")
    status = value.get("status")
    headroom = value.get("headroom_classification")
    if headroom not in {
        "INCONCLUSIVE_MEASUREMENT_NOT_READY_WITHOUT_HEADROOM_CLASSIFICATION",
        "FLOOR_OR_INSTRUMENT_REPAIR",
        "CANDIDATE_HEADROOM",
        "SATURATION_OR_INSUFFICIENT_HEADROOM",
    }:
        raise AlfworldB0PosthocProjectionError("calibration headroom class drifted")
    if status == INCONCLUSIVE_STATUS:
        if (
            value.get("confidence_intervals") is not None
            or headroom
            != "INCONCLUSIVE_MEASUREMENT_NOT_READY_WITHOUT_HEADROOM_CLASSIFICATION"
            or failure_class is None
        ):
            raise AlfworldB0PosthocProjectionError(
                "inconclusive calibration aggregate semantics drifted"
            )
    elif status == COMPLETE_STATUS:
        if not isinstance(value.get("confidence_intervals"), dict) or failure_class is not None:
            raise AlfworldB0PosthocProjectionError(
                "complete calibration aggregate semantics drifted"
            )
    else:
        raise AlfworldB0PosthocProjectionError("calibration status drifted")
    return {
        "status": status,
        "split_counts": split_counts,
        "success_counts": success_counts,
        "invalid_counts": invalid_counts,
        "confidence_intervals": value.get("confidence_intervals"),
        "resource_totals": totals,
        "headroom_classification": headroom,
        "failure_class": failure_class,
    }


def project_sealed_b0_archive(
    artifacts_tar: Path,
    *,
    expected_artifacts_sha256: str,
    expected_artifacts_bytes: int,
    expected_source_commit: str,
    expected_protocol_sha256: str,
    projection_execution: Mapping[str, object],
) -> dict[str, object]:
    """Validate the sealed occurrence and return one aggregate-only diagnostic."""

    _sha(expected_artifacts_sha256, "expected artifact archive SHA-256")
    _sha(expected_protocol_sha256, "expected protocol SHA-256")
    if _HEX40.fullmatch(expected_source_commit) is None:
        raise AlfworldB0PosthocProjectionError("expected source commit is invalid")
    projection_binding = _validate_projection_source_binding(projection_execution)
    if (
        not artifacts_tar.is_absolute()
        or artifacts_tar.is_symlink()
        or not artifacts_tar.is_file()
        or type(expected_artifacts_bytes) is not int
        or not 1 <= expected_artifacts_bytes <= MAX_ARCHIVE_BYTES
        or artifacts_tar.stat().st_size != expected_artifacts_bytes
        or _sha256_file(artifacts_tar) != expected_artifacts_sha256
    ):
        raise AlfworldB0PosthocProjectionError("sealed artifact archive binding drifted")
    try:
        archive_context = tarfile.open(artifacts_tar, "r:")
    except (OSError, tarfile.TarError) as error:
        raise AlfworldB0PosthocProjectionError("sealed artifact archive is unreadable") from error
    try:
        with archive_context as archive:
            members = _tar_regular_members(archive)
            if sum(member.size for member in members.values()) > MAX_EXPANDED_BYTES:
                raise AlfworldB0PosthocProjectionError(
                    "sealed artifact expanded byte bound exceeded"
                )
            private_raw = _tar_member_bytes(
                archive, members, "outputs/b0.private.json"
            )
            public_raw = _tar_member_bytes(
                archive, members, "outputs/b0.public.json"
            )
            marker_raw = _tar_member_bytes(archive, members, "outputs/b0.start.json")
            outer_private = _canonical_object(private_raw, "outer private receipt")
            original_public = _canonical_object(public_raw, "original public receipt")
            marker = _canonical_object(marker_raw, "start marker")
            execution = _validate_original_public(
                original_public,
                raw_private_sha256=_digest(private_raw),
                expected_source_commit=expected_source_commit,
                expected_protocol_sha256=expected_protocol_sha256,
            )
            selection_commitments = original_public.get("selection_commitments")
            expected_selection_fields = {
                "private_selection_sha256",
                "public_selection_sha256",
                "selection_digest_sha256",
                "pool_manifest_sha256",
                "local_locator_sha256",
            }
            if (
                not isinstance(selection_commitments, dict)
                or set(selection_commitments) != expected_selection_fields
            ):
                raise AlfworldB0PosthocProjectionError(
                    "original selection commitments drifted"
                )
            for digest in selection_commitments.values():
                _sha(digest, "selection commitment")
            base_outer_fields = {
                "schema_version",
                "status",
                "start_marker_sha256",
                "inner_private_receipt",
                "issued_counts",
                "lease_blobs",
            }
            if frozenset(outer_private) not in {
                frozenset(base_outer_fields),
                frozenset(base_outer_fields | {"error_type", "terminal"}),
            }:
                raise AlfworldB0PosthocProjectionError(
                    "outer private receipt field set drifted"
                )
            if (
                outer_private.get("schema_version") != LIVE_SCHEMA
                or outer_private.get("status") != original_public.get("status")
                or outer_private.get("start_marker_sha256") != _digest(marker_raw)
                or marker.get("schema_version") != LIVE_SCHEMA + "-start-marker"
                or marker.get("terminal")
                != "PRE_LEASE_PRE_ENV_PRE_MODEL_BINDING_SEALED"
                or not isinstance(marker.get("execution_source_sha256"), dict)
                or marker["execution_source_sha256"].get("commit")
                != expected_source_commit
                or marker["execution_source_sha256"].get("tree") != execution["tree"]
                or marker["execution_source_sha256"].get("_protocol")
                != expected_protocol_sha256
                or marker.get("selected_assets")
                != {
                    "selected_file_count": 12,
                    "valid_unseen_selected_file_count": 0,
                }
                or marker.get("selection") != selection_commitments
            ):
                raise AlfworldB0PosthocProjectionError(
                    "outer private receipt or start marker binding drifted"
                )
            inner_private = outer_private.get("inner_private_receipt")
            if not isinstance(inner_private, dict):
                raise AlfworldB0PosthocProjectionError(
                    "sealed occurrence has no nested calibration receipt to project"
                )
            calibration_public = calibration_public_projection(inner_private)
            calibration_commitments = calibration_public.get("commitments")
            if (
                not isinstance(calibration_commitments, dict)
                or calibration_commitments.get("protocol_binding_sha256")
                != expected_protocol_sha256
                or calibration_commitments.get("private_run_receipt_sha256")
                != inner_private.get("private_receipt_sha256")
                or calibration_commitments.get("selection_digest_sha256")
                != selection_commitments["selection_digest_sha256"]
                or calibration_commitments.get("private_selection_receipt_sha256")
                != selection_commitments["private_selection_sha256"]
            ):
                raise AlfworldB0PosthocProjectionError(
                    "nested calibration commitments drifted"
                )
            calibration = _validate_calibration_aggregate(
                calibration_public, outer_private.get("issued_counts")
            )
            if outer_private.get("status") not in {
                calibration.get("status"),
                INCONCLUSIVE_STATUS,
            }:
                raise AlfworldB0PosthocProjectionError(
                    "outer and calibration terminal statuses are incompatible"
                )
            lease_blobs = outer_private.get("lease_blobs")
            if not isinstance(lease_blobs, dict):
                raise AlfworldB0PosthocProjectionError("lease evidence map is invalid")
            stage_counts = {"startup": 0, "final": 0}
            content_digests: set[str] = set()
            preservation_error: str | None = None
            for key, digest in lease_blobs.items():
                if key == "preservation_error":
                    preservation_error = _error_class(digest, "lease preservation error")
                    continue
                if (
                    not isinstance(key, str)
                    or ":" not in key
                    or key.split(":", 1)[0] not in stage_counts
                ):
                    raise AlfworldB0PosthocProjectionError(
                        "lease evidence key is invalid"
                    )
                stage = key.split(":", 1)[0]
                digest = _sha(digest, "lease evidence digest")
                member = members.get("outputs/content/" + digest)
                if (
                    member is None
                    or member.size > MAX_CONTENT_MEMBER_BYTES
                    or _tar_member_sha256(archive, member) != digest
                ):
                    raise AlfworldB0PosthocProjectionError(
                        "lease evidence content binding drifted"
                    )
                stage_counts[stage] += 1
                content_digests.add(digest)
    except ContinualLiveError as error:
        raise AlfworldB0PosthocProjectionError(
            "sealed artifact archive member contract drifted"
        ) from error

    outer_failure = _error_class(outer_private.get("error_type"), "outer failure class")
    outer_terminal = outer_private.get("terminal")
    if outer_terminal is not None and (
        not isinstance(outer_terminal, str) or _ERROR_CLASS.fullmatch(outer_terminal) is None
    ):
        raise AlfworldB0PosthocProjectionError("outer terminal class is invalid")
    value: dict[str, object] = {
        "schema_version": POSTHOC_SCHEMA,
        "record_role": POSTHOC_ROLE,
        "status": outer_private["status"],
        "scientific_status": SCIENTIFIC_STATUS,
        "claim_ceiling": CLAIM_CEILING,
        "source_archive": {
            "sha256": expected_artifacts_sha256,
            "bytes": expected_artifacts_bytes,
        },
        "execution": execution,
        "projection_execution": projection_binding,
        "source_commitments": {
            "original_live_public_file_sha256": _digest(public_raw),
            "original_live_public_projection_sha256": original_public[
                "public_projection_sha256"
            ],
            "outer_private_receipt_file_sha256": _digest(private_raw),
            "inner_private_receipt_sha256": inner_private["private_receipt_sha256"],
            "inner_calibration_public_projection_sha256": calibration_public[
                "public_projection_sha256"
            ],
            "start_marker_file_sha256": _digest(marker_raw),
        },
        "outer_terminal": {
            "status": outer_private["status"],
            "terminal_class": outer_terminal,
            "failure_class": outer_failure,
        },
        "calibration_aggregate": calibration,
        "lease_evidence": {
            "startup_reference_count": stage_counts["startup"],
            "final_reference_count": stage_counts["final"],
            "unique_content_count": len(content_digests),
            "preservation_error_class": preservation_error,
        },
        "failure_counts": {
            "outer_failure": int(outer_failure is not None),
            "calibration_invalid_episodes": sum(
                int(item) for item in calibration["invalid_counts"].values()
            ),
        },
        "limitations": [
            "This projection was derived after the sealed occurrence solely to repair aggregate observability.",
            "It is not a retry, a new outcome, a G0 pass, a G1 result, or evidence of HSWM efficacy.",
            "It contains no game, task-group, path, trajectory, action, observation, outcome, or error-message content.",
        ],
    }
    _assert_no_private_keys(value)
    value["derived_public_projection_sha256"] = _digest(canonical_bytes(value))
    return value


def _write_exclusive(path: Path, value: Mapping[str, object]) -> None:
    if not path.is_absolute() or not path.parent.is_dir() or path.exists():
        raise AlfworldB0PosthocProjectionError(
            "derived output must use a fresh absolute path with an existing parent"
        )
    raw = canonical_bytes(dict(value)) + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-tar", required=True, type=Path)
    parser.add_argument("--expected-artifacts-sha256", required=True)
    parser.add_argument("--expected-artifacts-bytes", required=True, type=int)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        projection = project_sealed_b0_archive(
            args.artifacts_tar,
            expected_artifacts_sha256=args.expected_artifacts_sha256,
            expected_artifacts_bytes=args.expected_artifacts_bytes,
            expected_source_commit=args.expected_source_commit,
            expected_protocol_sha256=args.expected_protocol_sha256,
            projection_execution=projection_source_binding(args.repo),
        )
        _write_exclusive(args.output, projection)
    except Exception as error:
        print("B0_POSTHOC_PROJECTION_FAILED:" + type(error).__name__)
        return 2
    print("B0_POSTHOC_PROJECTION_WRITTEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
