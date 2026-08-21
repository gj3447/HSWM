from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from hswm.experiments import swm0w_s2s_pilot_adoption as adoption


REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = (
    REPO_ROOT
    / "artifacts"
    / "swm0w_s2s"
    / "pilot_adoption"
    / "32442437970"
)
EXPECTED_FILE_SHA256 = {
    "github_artifact.json": (
        "772f53455dc5ea82f07bb8add15d56a2c117ce36a053ebabdb90a120d069a12d"
    ),
    "github_job.json": (
        "e3ea8f05f4aa2b9c8199f6c30d60df9ee70c11f6e41abb9f3c69e0fcde701a3b"
    ),
    "github_run.json": (
        "80246cfdcdaa47c603c66d51d1d6dbaf5ef385d31474aa2ce0a8d624d03d049a"
    ),
    "pilot_adoption_receipt.json": (
        "fb34e5e9533409810f616815edc8565b244b5067a9bb70f643eb42d8bd044a78"
    ),
    "pilot_artifact.zip": (
        "b5a29cab118737f48083613f45a34212ae73f15a1321a597947d838c077f63c5"
    ),
}


def _bytes(name: str) -> bytes:
    return (BUNDLE / name).read_bytes()


def _json(name: str) -> dict[str, object]:
    value = json.loads(_bytes(name))
    assert type(value) is dict
    return value


def _replay() -> adoption.PilotAdoptionReceiptV1:
    return adoption.parse_pilot_adoption_receipt_bytes(
        _bytes("pilot_adoption_receipt.json"),
        pilot_artifact_zip_bytes=_bytes("pilot_artifact.zip"),
        github_run=_json("github_run.json"),
        github_job=_json("github_job.json"),
        github_artifact=_json("github_artifact.json"),
    )


def test_successful_pilot_adoption_bundle_replays_exactly() -> None:
    assert BUNDLE.is_dir()
    assert {path.name for path in BUNDLE.iterdir() if path.is_file()} == set(
        EXPECTED_FILE_SHA256
    )
    for name, expected in EXPECTED_FILE_SHA256.items():
        assert hashlib.sha256(_bytes(name)).hexdigest() == expected

    receipt = _replay()
    assert receipt.receipt_sha256 == (
        "97a752fea5ae45a311a2e8cf2376b391d76a8269dbab20f60688f543bcc5dea1"
    )
    assert receipt.protocol_config.receipt_sha256 == (
        "a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb"
    )
    assert receipt.source_commit == "75686549b1f6c65aea87ebd0f912a6e62909445a"
    assert tuple(
        (row.public_arm, row.learning_rate_decimal)
        for row in receipt.selected_configs
    ) == (("T16", "0.003"), ("P_CAP18", "0.001"), ("DEEPSETS_870", "0.001"))
    assert receipt.runtime_summary.stage2_cell_count == 27
    assert receipt.runtime_summary.selected_rate_stage2_cell_count == 9
    assert receipt.runtime_summary.selected_rate_stage2_total_ns == 424_904_259_742
    assert receipt.runtime_summary.max_peak_rss_kib == 171_108
    assert receipt.runtime_summary.github_job_elapsed_seconds == 1_361
    assert adoption.PREREG_RESOURCE_POLICY_STATUS == "PENDING_NOT_CHOSEN"
    assert adoption.VERDICT == "NO_EFFICACY_OR_CHRONOLOGY_VERDICT"


def test_bundle_archive_has_one_exact_uncompressed_member() -> None:
    with ZipFile(BUNDLE / "pilot_artifact.zip") as archive:
        assert archive.comment == b""
        assert archive.namelist() == ["pilot.json"]
        info = archive.getinfo("pilot.json")
        assert info.compress_type == ZIP_STORED
        assert info.file_size == 1_365_912
        member = archive.read(info)
    assert hashlib.sha256(member).hexdigest() == (
        "bea27c215394d647f76e36c17978731a5986475e439e78e7ff38de59c1ba5506"
    )


def test_bundle_replay_rejects_changed_receipt_or_archive() -> None:
    receipt = bytearray(_bytes("pilot_adoption_receipt.json"))
    receipt[100] ^= 1
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError):
        adoption.parse_pilot_adoption_receipt_bytes(
            bytes(receipt),
            pilot_artifact_zip_bytes=_bytes("pilot_artifact.zip"),
            github_run=_json("github_run.json"),
            github_job=_json("github_job.json"),
            github_artifact=_json("github_artifact.json"),
        )

    archive = bytearray(_bytes("pilot_artifact.zip"))
    archive[-1] ^= 1
    with pytest.raises(adoption.SWM0WS2SPilotAdoptionError):
        adoption.build_pilot_adoption_receipt(
            pilot_artifact_zip_bytes=bytes(archive),
            github_run=_json("github_run.json"),
            github_job=_json("github_job.json"),
            github_artifact=_json("github_artifact.json"),
        )
