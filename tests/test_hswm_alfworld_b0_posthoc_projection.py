from __future__ import annotations

from hashlib import sha256
import io
from pathlib import Path
import tarfile

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments.alfworld_b0_calibration import (
    INCONCLUSIVE_STATUS,
    PRIVATE_RUN_SCHEMA,
)
from hswm.experiments.alfworld_b0_live import LIVE_SCHEMA
from hswm.experiments.alfworld_b0_posthoc_projection import (
    AlfworldB0PosthocProjectionError,
    POSTHOC_SCHEMA,
    project_sealed_b0_archive,
)


COMMIT = "a" * 40
TREE = "b" * 40
PROTOCOL = "c" * 64
PROJECTION_EXECUTION = {
    "commit": "1" * 40,
    "tree": "2" * 40,
    "source_code_sha256": {
        "_research/dnrd5/canonical_json.py": "3" * 64,
        "src/hswm/experiments/alfworld_b0_calibration.py": "4" * 64,
        "src/hswm/experiments/alfworld_b0_live.py": "5" * 64,
        "src/hswm/experiments/alfworld_b0_posthoc_projection.py": "6" * 64,
        "src/hswm/experiments/continual_live.py": "7" * 64,
    },
}
TOTALS = {
    "actor_call_count": 1,
    "environment_step_count": 0,
    "input_token_count": 0,
    "output_token_count": 0,
    "token_preflight_token_count": 0,
    "issued_completion_post_count": 0,
    "issued_tokenize_post_count": 1,
    "issued_http_post_count": 1,
    "validated_model_response_count": 0,
    "completed_episode_count": 0,
    "wall_microseconds": 120_000_000,
}


def _inner_private(
    *, protocol: str = PROTOCOL, selection_digest: str = "e" * 64
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": PRIVATE_RUN_SCHEMA,
        "record_role": "LOCAL_NONREPOSITORY_B0_CALIBRATION_RUN_RECEIPT_NOT_FOR_REDISTRIBUTION",
        "status": INCONCLUSIVE_STATUS,
        "claim_ceiling": "NO_LEARNING_NO_REVISION_NO_G0_PASS_NO_G1_NO_HSWM_EFFICACY_CLAIM",
        "protocol": {
            "uid": "private-protocol-uid",
            "version": "v1",
            "max_steps": 20,
            "binding_sha256": protocol,
        },
        "input_commitments": {
            "private_selection_receipt_sha256": "d" * 64,
            "selection_digest_sha256": selection_digest,
            "pool_manifest_path": "/private/pool",
            "local_locator_path": "/private/locator",
            "asset_root_path": "/private/assets",
        },
        "episode_prefix": [
            {
                "split": "train",
                "terminal": "INCONCLUSIVE",
                "opaque_uid": "SECRET-OPAQUE-UID",
                "relative_path": "SECRET/PATH",
                "actor_trace": [{"action": "SECRET-ACTION"}],
            }
        ],
        "terminal": {
            "status": INCONCLUSIVE_STATUS,
            "reason": "TRANSPORT_SCHEMA_OR_INTEGRITY_ERROR",
            "error_type": "ALFWorldB0ActorError",
        },
        "resource_totals": dict(TOTALS),
    }
    value["private_receipt_sha256"] = sha256(canonical_bytes(value)).hexdigest()
    return value


def _raw(value: dict[str, object]) -> bytes:
    return canonical_bytes(value) + b"\n"


def _add(archive: tarfile.TarFile, name: str, raw: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(raw)
    archive.addfile(member, io.BytesIO(raw))


def _archive(
    tmp_path: Path,
    *,
    issued_counts: dict[str, int] | None = None,
    public_private_sha: str | None = None,
    marker_sha: str | None = None,
    content_matches: bool = True,
    unsafe_link: bool = False,
    inner_protocol: str = PROTOCOL,
    inner_selection_digest: str = "e" * 64,
    compressed: bool = False,
) -> Path:
    selection = {
        "private_selection_sha256": "d" * 64,
        "public_selection_sha256": "f" * 64,
        "selection_digest_sha256": "e" * 64,
        "pool_manifest_sha256": "8" * 64,
        "local_locator_sha256": "9" * 64,
    }
    marker = {
        "schema_version": LIVE_SCHEMA + "-start-marker",
        "terminal": "PRE_LEASE_PRE_ENV_PRE_MODEL_BINDING_SEALED",
        "execution_source_sha256": {
            "commit": COMMIT,
            "tree": TREE,
            "_protocol": PROTOCOL,
        },
        "selected_assets": {
            "selected_file_count": 12,
            "valid_unseen_selected_file_count": 0,
        },
        "selection": selection,
    }
    marker_raw = _raw(marker)
    content_raw = b"sealed lease evidence"
    content_digest = sha256(content_raw).hexdigest()
    outer = {
        "schema_version": LIVE_SCHEMA,
        "status": INCONCLUSIVE_STATUS,
        "start_marker_sha256": marker_sha or sha256(marker_raw).hexdigest(),
        "inner_private_receipt": _inner_private(
            protocol=inner_protocol,
            selection_digest=inner_selection_digest,
        ),
        "issued_counts": issued_counts
        or {
            "issued_tokenize_post_count": 1,
            "issued_completion_post_count": 0,
            "issued_http_post_count": 1,
        },
        "lease_blobs": {"startup:metrics": content_digest},
    }
    private_raw = _raw(outer)
    public: dict[str, object] = {
        "schema_version": LIVE_SCHEMA,
        "status": INCONCLUSIVE_STATUS,
        "claim_ceiling": "EXPLORATORY_B0_CALIBRATION_ONLY_G0_NOT_PASSED_NOT_G1",
        "execution": {
            "commit": COMMIT,
            "tree": TREE,
            "protocol_sha256": PROTOCOL,
        },
        "selection_commitments": selection,
        "resource_totals": {},
        "private_receipt_sha256": public_private_sha
        or sha256(private_raw).hexdigest(),
    }
    public["public_projection_sha256"] = sha256(canonical_bytes(public)).hexdigest()
    path = tmp_path / "artifacts.tar"
    with tarfile.open(path, "w:gz" if compressed else "w") as archive:
        _add(archive, "outputs/b0.private.json", private_raw)
        _add(archive, "outputs/b0.public.json", _raw(public))
        _add(archive, "outputs/b0.start.json", marker_raw)
        _add(
            archive,
            "outputs/content/" + content_digest,
            content_raw if content_matches else b"tampered",
        )
        if unsafe_link:
            member = tarfile.TarInfo("outputs/unsafe-link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            archive.addfile(member)
    return path


def _project(path: Path) -> dict[str, object]:
    return project_sealed_b0_archive(
        path,
        expected_artifacts_sha256=sha256(path.read_bytes()).hexdigest(),
        expected_artifacts_bytes=path.stat().st_size,
        expected_source_commit=COMMIT,
        expected_protocol_sha256=PROTOCOL,
        projection_execution=PROJECTION_EXECUTION,
    )


def test_posthoc_projection_restores_only_validated_aggregates(tmp_path: Path) -> None:
    path = _archive(tmp_path)
    value = _project(path)
    assert value["schema_version"] == POSTHOC_SCHEMA
    assert value["status"] == INCONCLUSIVE_STATUS
    assert value["projection_execution"] == PROJECTION_EXECUTION
    aggregate = value["calibration_aggregate"]
    assert aggregate["resource_totals"] == TOTALS
    assert aggregate["split_counts"] == {"train": 1, "valid_seen": 0}
    assert aggregate["invalid_counts"] == {"train": 1, "valid_seen": 0}
    assert value["failure_counts"] == {
        "outer_failure": 0,
        "calibration_invalid_episodes": 1,
    }
    assert value["lease_evidence"] == {
        "startup_reference_count": 1,
        "final_reference_count": 0,
        "unique_content_count": 1,
        "preservation_error_class": None,
    }
    unsigned = {
        key: item
        for key, item in value.items()
        if key != "derived_public_projection_sha256"
    }
    assert value["derived_public_projection_sha256"] == sha256(
        canonical_bytes(unsigned)
    ).hexdigest()
    rendered = canonical_bytes(value).decode("utf-8")
    assert "SECRET" not in rendered
    assert "opaque_uid" not in rendered
    assert "/private/" not in rendered
    assert "G0_NOT_PASSED" in rendered
    assert "G1_NOT_EVALUATED" in rendered


def test_posthoc_projection_requires_exact_archive_binding(tmp_path: Path) -> None:
    path = _archive(tmp_path)
    with pytest.raises(AlfworldB0PosthocProjectionError, match="archive binding"):
        project_sealed_b0_archive(
            path,
            expected_artifacts_sha256="0" * 64,
            expected_artifacts_bytes=path.stat().st_size,
            expected_source_commit=COMMIT,
            expected_protocol_sha256=PROTOCOL,
            projection_execution=PROJECTION_EXECUTION,
        )


def test_posthoc_projection_rejects_outer_issued_count_drift(tmp_path: Path) -> None:
    path = _archive(
        tmp_path,
        issued_counts={
            "issued_tokenize_post_count": 1,
            "issued_completion_post_count": 1,
            "issued_http_post_count": 2,
        },
    )
    with pytest.raises(AlfworldB0PosthocProjectionError, match="issued counts differ"):
        _project(path)


@pytest.mark.parametrize(
    "options, match",
    (
        ({"public_private_sha": "0" * 64}, "public projection binding"),
        ({"marker_sha": "0" * 64}, "start marker binding"),
        ({"content_matches": False}, "content binding"),
        ({"unsafe_link": True}, "member contract"),
        ({"inner_protocol": "0" * 64}, "nested calibration commitments"),
        ({"inner_selection_digest": "0" * 64}, "nested calibration commitments"),
        ({"compressed": True}, "archive is unreadable"),
    ),
)
def test_posthoc_projection_rejects_tampered_or_unsafe_archives(
    tmp_path: Path, options: dict[str, object], match: str
) -> None:
    path = _archive(tmp_path, **options)
    with pytest.raises(AlfworldB0PosthocProjectionError, match=match):
        _project(path)
