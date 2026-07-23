from __future__ import annotations

import errno
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
    anchor = Path(opened["reservation"]["anchor_path"])
    assert anchor.is_file()
    assert anchor.stat().st_ino == output.stat().st_ino
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
    opened = life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    anchor = Path(opened["reservation"]["anchor_path"])
    reserved_inode = anchor.stat().st_ino
    output.unlink()
    output.write_text('{"cherry_picked":true}\n', encoding="utf-8")
    assert output.stat().st_ino != reserved_inode
    with pytest.raises(life.ArtifactLifecycleError, match="inode/device changed"):
        life.close_append_log(
            open_receipt_path=opened_path,
            close_receipt_path=tmp_path / "CLOSE.json",
            validation={"schema": "fixture/v1", "records": 1},
        )


def test_append_close_rejects_removed_identity_anchor(tmp_path):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    opened = life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    output.write_text('{"ok":true}\n', encoding="utf-8")
    Path(opened["reservation"]["anchor_path"]).unlink()

    with pytest.raises(life.ArtifactLifecycleError, match="identity anchor"):
        life.close_append_log(
            open_receipt_path=opened_path,
            close_receipt_path=tmp_path / "CLOSE.json",
            validation={"schema": "fixture/v1", "records": 1},
        )


def test_append_close_rejects_replaced_identity_anchor(tmp_path):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    opened = life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    output.write_text('{"ok":true}\n', encoding="utf-8")
    anchor = Path(opened["reservation"]["anchor_path"])
    anchor.unlink()
    anchor.write_text('{"replacement":true}\n', encoding="utf-8")

    with pytest.raises(life.ArtifactLifecycleError, match="identity anchor"):
        life.close_append_log(
            open_receipt_path=opened_path,
            close_receipt_path=tmp_path / "CLOSE.json",
            validation={"schema": "fixture/v1", "records": 1},
        )


def test_append_close_rejects_output_symlink_substitution(tmp_path):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    opened = life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    anchor = Path(opened["reservation"]["anchor_path"])
    output.unlink()
    output.symlink_to(anchor)
    with pytest.raises(life.ArtifactLifecycleError, match="inode/device changed"):
        life.close_append_log(
            open_receipt_path=opened_path,
            close_receipt_path=tmp_path / "CLOSE.json",
            validation={"schema": "fixture/v1", "records": 1},
        )

    with pytest.raises(life.ArtifactLifecycleError, match="not a regular file"):
        life.file_sha256(output)


def test_append_open_anchor_collision_is_first_write_wins(tmp_path):
    output = tmp_path / "extractions.jsonl"
    anchor = tmp_path / ".extractions.jsonl.hswm-open-anchor"
    anchor.write_text("existing evidence\n", encoding="utf-8")

    with pytest.raises(life.ArtifactLifecycleError, match="anchor must be nonexistent"):
        life.open_append_log(
            output_path=output, open_receipt_path=tmp_path / "OPEN.json",
            stage="development", artifact_kind="extraction_jsonl",
            authorization=_parents("development"), input_sha256=SHA,
            config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
            producer_code_sha256="2" * 64,
        )

    assert not output.exists()
    assert anchor.read_text(encoding="utf-8") == "existing evidence\n"


def test_append_open_refuses_unsupported_hardlinks_and_cleans_up(
    tmp_path, monkeypatch,
):
    output = tmp_path / "extractions.jsonl"

    def unsupported_link(*args, **kwargs):
        raise OSError(errno.EOPNOTSUPP, "hard links unsupported")

    monkeypatch.setattr(life.os, "link", unsupported_link)
    with pytest.raises(life.ArtifactLifecycleError, match="cannot create.*anchor"):
        life.open_append_log(
            output_path=output, open_receipt_path=tmp_path / "OPEN.json",
            stage="development", artifact_kind="extraction_jsonl",
            authorization=_parents("development"), input_sha256=SHA,
            config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
            producer_code_sha256="2" * 64,
        )

    assert not output.exists()
    assert not (tmp_path / ".extractions.jsonl.hswm-open-anchor").exists()


def test_append_open_receipt_collision_cleans_only_new_artifacts(tmp_path):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    opened_path.write_text("existing receipt\n", encoding="utf-8")

    with pytest.raises(life.ArtifactLifecycleError, match="first-write-wins"):
        life.open_append_log(
            output_path=output, open_receipt_path=opened_path,
            stage="development", artifact_kind="extraction_jsonl",
            authorization=_parents("development"), input_sha256=SHA,
            config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
            producer_code_sha256="2" * 64,
        )

    assert not output.exists()
    assert not (tmp_path / ".extractions.jsonl.hswm-open-anchor").exists()
    assert opened_path.read_text(encoding="utf-8") == "existing receipt\n"


def test_artifact_hash_fallback_without_o_nofollow_rejects_symlinks(
    tmp_path, monkeypatch,
):
    target = tmp_path / "target.json"
    target.write_text('{"ok":true}\n', encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    monkeypatch.delattr(life.os, "O_NOFOLLOW", raising=False)

    assert life.file_sha256(target) == life.file_sha256(target)
    with pytest.raises(life.ArtifactLifecycleError, match="not a regular file"):
        life.file_sha256(link)


@pytest.mark.parametrize("replace_path", [False, True])
def test_append_close_rejects_mutation_during_hash(
    tmp_path, monkeypatch, replace_path,
):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    output.write_bytes(b'{"initial":true}\n' + b"x" * (1024 * 1024))
    original_read = life.os.read
    mutated = False

    def mutate_after_read(descriptor, count):
        nonlocal mutated
        chunk = original_read(descriptor, count)
        if not mutated:
            mutated = True
            if replace_path:
                output.unlink()
                output.write_text('{"replacement":true}\n', encoding="utf-8")
            else:
                with output.open("ab") as handle:
                    handle.write(b'{"late":true}\n')
                    handle.flush()
                    os.fsync(handle.fileno())
        return chunk

    monkeypatch.setattr(life.os, "read", mutate_after_read)
    with pytest.raises(life.ArtifactLifecycleError, match="changed while hashing"):
        life.close_append_log(
            open_receipt_path=opened_path,
            close_receipt_path=tmp_path / "CLOSE.json",
            validation={"schema": "fixture/v1", "records": 1},
        )
    assert not (tmp_path / "CLOSE.json").exists()


def test_append_close_revalidates_after_receipt_publication(tmp_path, monkeypatch):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    closed_path = tmp_path / "CLOSE.json"
    life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    output.write_text('{"ok":true}\n', encoding="utf-8")
    original_write_once = life._write_once

    def write_then_mutate(path, value):
        digest = original_write_once(path, value)
        if Path(path) == closed_path:
            with output.open("ab") as handle:
                handle.write(b'{"late":true}\n')
                handle.flush()
                os.fsync(handle.fileno())
        return digest

    monkeypatch.setattr(life, "_write_once", write_then_mutate)
    with pytest.raises(life.ArtifactLifecycleError, match="output changed"):
        life.close_append_log(
            open_receipt_path=opened_path, close_receipt_path=closed_path,
            validation={"schema": "fixture/v1", "records": 1},
        )
    assert closed_path.is_file()


def test_load_close_rejects_output_replaced_after_close(tmp_path):
    output = tmp_path / "extractions.jsonl"
    opened_path = tmp_path / "OPEN.json"
    closed_path = tmp_path / "CLOSE.json"
    opened = life.open_append_log(
        output_path=output, open_receipt_path=opened_path,
        stage="development", artifact_kind="extraction_jsonl",
        authorization=_parents("development"), input_sha256=SHA,
        config_sha256="f" * 64, deployment_attestation_sha256="1" * 64,
        producer_code_sha256="2" * 64,
    )
    output.write_text('{"ok":true}\n', encoding="utf-8")
    life.close_append_log(
        open_receipt_path=opened_path, close_receipt_path=closed_path,
        validation={"schema": "fixture/v1", "records": 1},
    )
    anchor = Path(opened["reservation"]["anchor_path"])
    assert anchor.samefile(output)
    output.unlink()
    output.write_text('{"replacement":true}\n', encoding="utf-8")

    with pytest.raises(life.ArtifactLifecycleError, match="inode/device changed"):
        life.load_close_receipt(closed_path, open_receipt_path=opened_path)


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
