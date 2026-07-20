"""Recorded embedding artifact contract teeth; no model or GPU required."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os

import numpy as np
import pytest

import bge_m3_embed as emb


def _snapshot(
    tmp_path,
    *,
    model: str = emb.FROZEN_MODEL_ID,
    revision: str = emb.FROZEN_MODEL_REVISION,
    hf_symlinks: bool = False,
):
    repository = tmp_path / ("models--" + model.replace("/", "--"))
    snapshot = repository / "snapshots" / revision
    snapshot.mkdir(parents=True)
    payloads = {
        "config.json": json.dumps({
            "_name_or_path": model,
            "model_type": "xlm-roberta",
            "architectures": ["XLMRobertaModel"],
            "torch_dtype": "bfloat16",
        }).encode(),
        "tokenizer_config.json": json.dumps({
            "name_or_path": model,
            "tokenizer_class": "XLMRobertaTokenizerFast",
            "model_max_length": 8192,
        }).encode(),
        "tokenizer.json": b'{"version":"1"}',
        "model.safetensors": b"fixture-weights",
    }
    if hf_symlinks:
        blobs = repository / "blobs"
        blobs.mkdir()
        for name, payload in payloads.items():
            digest = sha256(payload).hexdigest()
            (blobs / digest).write_bytes(payload)
            (snapshot / name).symlink_to(f"../../blobs/{digest}")
    else:
        for name, payload in payloads.items():
            (snapshot / name).write_bytes(payload)
    return snapshot


def _records():
    return (
        emb.EmbeddingInputV1("a", "query", "Alpha"),
        emb.EmbeddingInputV1("b", "paragraph", "Beta"),
    )


def test_loader_sorts_stable_ids_and_forbids_extra_fields(tmp_path):
    path = tmp_path / "input.jsonl"
    path.write_text(
        "\n".join((
            json.dumps({"id": "b", "kind": "paragraph", "text": "Beta"}),
            json.dumps({"id": "a", "kind": "query", "text": "Alpha"}),
        )), encoding="utf-8",
    )
    records = emb.load_jsonl(str(path))
    assert [record.id for record in records] == ["a", "b"]

    path.write_text(json.dumps({
        "id": "x", "kind": "paragraph", "text": "X", "gold": True,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="keys must be exactly"):
        emb.load_jsonl(str(path))


def test_embed_records_normalizes_and_rejects_bad_batches():
    records = _records()

    def encoder(texts):
        return np.asarray([[3.0, 4.0] for _ in texts], dtype=np.float32)

    values = emb.embed_records(records, encoder, batch_size=1)
    np.testing.assert_allclose(values, [[0.6, 0.8], [0.6, 0.8]])
    assert np.allclose(np.linalg.norm(values, axis=1), 1.0)

    with pytest.raises(ValueError, match="invalid batch shape"):
        emb.embed_records(records, lambda texts: np.ones((1, 3)))


def test_npz_receipt_is_self_verifying_and_first_write_wins(tmp_path, monkeypatch):
    records = _records()
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    attestation = emb.attest_model_snapshot(
        _snapshot(tmp_path), expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    monkeypatch.setattr(
        emb, "FROZEN_WEIGHT_BLOB_SHA256", attestation["weight_blob_sha256"],
    )
    output = tmp_path / "vectors.npz"
    receipt = tmp_path / "receipt.json"
    row = emb.write_artifact(
        str(output), str(receipt), records, vectors,
        model_attestation=attestation,
        max_length=emb.FROZEN_MAX_LENGTH, dtype_name=emb.FROZEN_DTYPE,
        batch_size=emb.FROZEN_BATCH_SIZE, elapsed_s=1.25,
    )
    frozen = np.load(output, allow_pickle=False)
    assert frozen["ids"].tolist() == ["a", "b"]
    assert frozen["vectors"].shape == (2, 2)
    assert row["input_sha256"] == emb.input_sha256(records)
    assert row["max_norm_error"] == 0.0
    assert row["max_length"] == 8192
    assert row["dtype"] == "bfloat16"
    assert row["batch_size"] == 32
    assert row["model_attestation"]["config_sha256"]
    assert row["model_attestation"]["tokenizer_config_sha256"]
    assert emb.load_embedding_receipt(
        receipt, artifact_path=output, expected_records=records,
        expected_producer_code_sha256=emb._file_sha256(emb.__file__),
    ) == row
    with pytest.raises(FileExistsError, match="first-write-wins"):
        emb.write_artifact(
            str(output), str(receipt), records, vectors,
            model_attestation=attestation,
            max_length=emb.FROZEN_MAX_LENGTH, dtype_name=emb.FROZEN_DTYPE,
            batch_size=emb.FROZEN_BATCH_SIZE, elapsed_s=1.25,
        )


def test_receipt_tamper_and_artifact_tamper_fail_load(tmp_path, monkeypatch):
    records = _records()
    vectors = np.eye(2, dtype=np.float32)
    attestation = emb.attest_model_snapshot(
        _snapshot(tmp_path), expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    monkeypatch.setattr(
        emb, "FROZEN_WEIGHT_BLOB_SHA256", attestation["weight_blob_sha256"],
    )
    output = tmp_path / "vectors.npz"
    receipt = tmp_path / "receipt.json"
    row = emb.write_artifact(
        str(output), str(receipt), records, vectors,
        model_attestation=attestation, max_length=emb.FROZEN_MAX_LENGTH,
        dtype_name=emb.FROZEN_DTYPE, batch_size=emb.FROZEN_BATCH_SIZE,
        elapsed_s=0.1,
    )

    changed = deepcopy(row)
    changed["elapsed_s"] = 9.0
    receipt.write_text(emb.canonical_json(changed) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="self-hash"):
        emb.load_embedding_receipt(receipt, artifact_path=output)

    receipt.write_text(emb.canonical_json(row) + "\n", encoding="utf-8")
    output.write_bytes(output.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="output hash"):
        emb.load_embedding_receipt(receipt, artifact_path=output)


def test_batch_size_is_frozen_in_the_producer(tmp_path, monkeypatch):
    records = _records()
    attestation = emb.attest_model_snapshot(
        _snapshot(tmp_path), expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    monkeypatch.setattr(
        emb, "FROZEN_WEIGHT_BLOB_SHA256", attestation["weight_blob_sha256"],
    )
    with pytest.raises(ValueError, match="batch_size is frozen"):
        emb.write_artifact(
            str(tmp_path / "vectors.npz"), str(tmp_path / "receipt.json"),
            records, np.eye(2, dtype=np.float32), model_attestation=attestation,
            max_length=emb.FROZEN_MAX_LENGTH, dtype_name=emb.FROZEN_DTYPE,
            batch_size=2, elapsed_s=0.1,
        )


def test_publication_race_rolls_back_uncommitted_artifact(tmp_path, monkeypatch):
    records = _records()
    attestation = emb.attest_model_snapshot(
        _snapshot(tmp_path), expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    monkeypatch.setattr(
        emb, "FROZEN_WEIGHT_BLOB_SHA256", attestation["weight_blob_sha256"],
    )
    real_link = os.link
    calls = 0

    def racing_link(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise FileExistsError("attacker won receipt publication")
        return real_link(source, target)

    monkeypatch.setattr(emb.os, "link", racing_link)
    output = tmp_path / "vectors.npz"
    receipt = tmp_path / "receipt.json"
    with pytest.raises(FileExistsError, match="first-write-wins"):
        emb.write_artifact(
            str(output), str(receipt), records, np.eye(2, dtype=np.float32),
            model_attestation=attestation, max_length=emb.FROZEN_MAX_LENGTH,
            dtype_name=emb.FROZEN_DTYPE, batch_size=emb.FROZEN_BATCH_SIZE,
            elapsed_s=0.1,
        )
    assert not output.exists()
    assert not receipt.exists()


def test_model_attestation_rejects_arbitrary_label_and_wrong_frozen_weight(
    tmp_path,
):
    other = _snapshot(tmp_path, model="Other/model")
    with pytest.raises(ValueError, match="cache repository"):
        emb.attest_model_snapshot(
            other, expected_model=emb.FROZEN_MODEL_ID,
            expected_revision=emb.FROZEN_MODEL_REVISION,
        )

    forged = _snapshot(tmp_path / "forged")
    attestation = emb.attest_model_snapshot(
        forged, expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    with pytest.raises(ValueError, match="preregistered content"):
        emb.write_artifact(
            str(tmp_path / "bad.npz"), str(tmp_path / "bad.json"), _records(),
            np.eye(2, dtype=np.float32), model_attestation=attestation,
            max_length=emb.FROZEN_MAX_LENGTH, dtype_name=emb.FROZEN_DTYPE,
            batch_size=emb.FROZEN_BATCH_SIZE, elapsed_s=0.1,
        )


def test_hf_blob_symlinks_are_bound_but_external_symlink_is_rejected(tmp_path):
    snapshot = _snapshot(tmp_path / "valid", hf_symlinks=True)
    attestation = emb.attest_model_snapshot(
        snapshot, expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    assert {row["storage"] for row in attestation["metadata_files"]} == {"hf_blob"}

    attacked = _snapshot(tmp_path / "attacked")
    outside = tmp_path / "outside-tokenizer.json"
    outside.write_text("{}", encoding="utf-8")
    (attacked / "tokenizer.json").unlink()
    (attacked / "tokenizer.json").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes its repository"):
        emb.attest_model_snapshot(
            attacked, expected_model=emb.FROZEN_MODEL_ID,
            expected_revision=emb.FROZEN_MODEL_REVISION,
        )


def test_attestation_recompute_detects_snapshot_mutation_and_missing_tokenizer(tmp_path):
    snapshot = _snapshot(tmp_path / "mutable")
    attestation = emb.attest_model_snapshot(
        snapshot, expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    emb.validate_model_attestation(attestation, verify_files=True)
    (snapshot / "tokenizer.json").write_text('{"version":"2"}', encoding="utf-8")
    with pytest.raises(ValueError, match="no longer matches"):
        emb.validate_model_attestation(attestation, verify_files=True)

    missing = _snapshot(tmp_path / "missing")
    (missing / "tokenizer_config.json").unlink()
    with pytest.raises(ValueError, match="tokenizer_config"):
        emb.attest_model_snapshot(
            missing, expected_model=emb.FROZEN_MODEL_ID,
            expected_revision=emb.FROZEN_MODEL_REVISION,
        )


def test_attestation_self_hash_rejects_field_tampering(tmp_path):
    attestation = emb.attest_model_snapshot(
        _snapshot(tmp_path), expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    tampered = deepcopy(attestation)
    tampered["config_identity"]["model_type"] = "fake"
    with pytest.raises(ValueError, match="self-hash"):
        emb.validate_model_attestation(tampered)


def test_standalone_attestation_writer_is_canonical_and_first_write(tmp_path):
    snapshot = _snapshot(tmp_path)
    attestation = emb.attest_model_snapshot(
        snapshot, expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    output = tmp_path / "model-attestation.json"
    file_digest = emb.write_model_attestation(output, attestation)

    expected = (emb.canonical_json(attestation) + "\n").encode("utf-8")
    assert output.read_bytes() == expected
    assert file_digest == sha256(expected).hexdigest()
    assert emb.validate_model_attestation(
        json.loads(output.read_text(encoding="utf-8")), verify_files=True,
    ) == attestation
    with pytest.raises(FileExistsError, match="first-write-wins"):
        emb.write_model_attestation(output, attestation)


def test_standalone_attestation_writer_rechecks_live_files(tmp_path):
    snapshot = _snapshot(tmp_path)
    attestation = emb.attest_model_snapshot(
        snapshot, expected_model=emb.FROZEN_MODEL_ID,
        expected_revision=emb.FROZEN_MODEL_REVISION,
    )
    (snapshot / "tokenizer.json").write_text(
        '{"version":"changed"}', encoding="utf-8",
    )
    output = tmp_path / "must-not-exist.json"
    with pytest.raises(ValueError, match="no longer matches"):
        emb.write_model_attestation(output, attestation)
    assert not output.exists()


def test_attest_only_cli_never_loads_the_encoder(tmp_path, monkeypatch, capsys):
    snapshot = _snapshot(tmp_path)
    output = tmp_path / "cli-attestation.json"

    def forbidden_encoder(*_args, **_kwargs):
        raise AssertionError("attest-only must not load torch/transformers")

    monkeypatch.setattr(emb, "_transformers_encoder", forbidden_encoder)
    emb.main([
        "--attest-only",
        "--model", str(snapshot),
        "--model-id", emb.FROZEN_MODEL_ID,
        "--model-revision", emb.FROZEN_MODEL_REVISION,
        "--attestation-out", str(output),
    ])

    summary = json.loads(capsys.readouterr().out)
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert summary["schema_version"] == emb.MODEL_ATTESTATION_SCHEMA_VERSION
    assert summary["attestation_id"] == artifact["attestation_id"]
    assert summary["file_sha256"] == sha256(output.read_bytes()).hexdigest()
    assert emb.validate_model_attestation(artifact, verify_files=True) == artifact
