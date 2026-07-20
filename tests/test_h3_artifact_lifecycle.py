from __future__ import annotations

import os
from pathlib import Path

import pytest

import h3_artifact_lifecycle as life


SHA = "a" * 64


def _parents(stage: str) -> dict[str, str]:
    value = {
        "run_manifest_sha256": SHA,
        "protocol_sha256": "b" * 64,
        "code_root_sha256": "c" * 64,
        "preflight_receipt_sha256": "d" * 64,
    }
    if stage == "fresh":
        value["certificate_transition_sha256"] = "e" * 64
    return value


def test_append_log_open_close_binds_same_inode_and_refuses_reuse(tmp_path):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "EXTRACTION_OPEN.json"
    closed_path = tmp_path / "EXTRACTION_CLOSE.json"
    opened = life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    assert output.is_file() and output.stat().st_size == 0
    assert output.stat().st_ino == opened["reservation"]["inode"]
    with output.open("ab") as handle:
        handle.write(b'{"ok":true}\n')
        handle.flush()
        os.fsync(handle.fileno())
    closed = life.close_append_log(
        open_receipt_path=opened_path, close_receipt_path=closed_path,
        validation={"schema": "fixture/v1", "records": 1},
    )
    assert closed["outputs"]["output_sha256"] == life.file_sha256(output)
    assert life.load_close_receipt(
        closed_path, open_receipt_path=opened_path,
    ) == closed
    with pytest.raises(life.ArtifactLifecycleError, match="nonexistent"):
        life.open_append_log(
            output_path=output, open_receipt_path=tmp_path / "open2.json",
            stage="development", artifact_kind="extraction_jsonl",
            authorization=_parents("development"), input_sha256=SHA,
            config_sha256="f" * 64,
            deployment_attestation_sha256="1" * 64,
            producer_code_sha256="2" * 64,
        )


def test_append_close_rejects_replaced_inode(tmp_path):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    output.unlink()
    output.write_text('{"cherry_picked":true}\n', encoding="utf-8")
    with pytest.raises(life.ArtifactLifecycleError, match="inode/device changed"):
        life.close_append_log(
            open_receipt_path=opened_path,
            close_receipt_path=tmp_path / "CLOSE.json",
            validation={"schema": "fixture/v1", "records": 1},
        )


def test_fresh_open_requires_certificate_transition_parent(tmp_path):
    parents = _parents("development")
    with pytest.raises(life.ArtifactLifecycleError, match="certificate_transition"):
        life.open_append_log(
            output_path=tmp_path / "fresh.jsonl",
            open_receipt_path=tmp_path / "OPEN.json",
            stage="fresh", artifact_kind="extraction_jsonl",
            authorization=parents, input_sha256=SHA, config_sha256="f" * 64,
            deployment_attestation_sha256="1" * 64,
            producer_code_sha256="2" * 64,
        )
    assert not (tmp_path / "fresh.jsonl").exists()


def test_exclusive_bundle_publishes_without_replace_and_closes(tmp_path):
    run_dir = tmp_path / "embedding-run"
    artifact = run_dir / "embedding.npz"
    receipt = run_dir / "embedding.json"
    opened_path = tmp_path / "EMBED_OPEN.json"
    closed_path = tmp_path / "EMBED_CLOSE.json"
    life.open_exclusive_bundle(
        run_directory=run_dir,
        expected_outputs={"artifact": artifact, "receipt": receipt},
        open_receipt_path=opened_path, stage="fresh",
        artifact_kind="embedding_bundle", authorization=_parents("fresh"),
        input_sha256=SHA, config_sha256="f" * 64,
        deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    temporary = run_dir / "artifact.tmp"
    temporary.write_bytes(b"npz")
    life.publish_no_replace(temporary, artifact)
    receipt.write_text('{"receipt":true}\n', encoding="utf-8")
    collision = run_dir / "collision.tmp"
    collision.write_bytes(b"replacement")
    with pytest.raises(life.ArtifactLifecycleError, match="refusing to replace"):
        life.publish_no_replace(collision, artifact)
    closed = life.close_exclusive_bundle(
        open_receipt_path=opened_path, close_receipt_path=closed_path,
        validation={"schema": "fixture/v1", "records": 2},
    )
    assert set(closed["outputs"]) == {"artifact", "receipt"}
    assert life.load_close_receipt(
        closed_path, open_receipt_path=opened_path,
    ) == closed


def test_close_receipt_is_first_write_wins(tmp_path):
    output = tmp_path / "log.jsonl"
    opened_path = tmp_path / "OPEN.json"
    closed_path = tmp_path / "CLOSE.json"
    life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    output.write_text("{}\n", encoding="utf-8")
    life.close_append_log(
        open_receipt_path=opened_path, close_receipt_path=closed_path,
        validation={"schema": "fixture/v1", "records": 1},
    )
    with pytest.raises(life.ArtifactLifecycleError, match="first-write-wins"):
        life.close_append_log(
            open_receipt_path=opened_path, close_receipt_path=closed_path,
            validation={"schema": "fixture/v1", "records": 1},
        )

