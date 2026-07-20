"""Local deployment attestation teeth without a model or GPU."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os

import pytest

import model_deployment_receipt as mdr


MODEL = "Qwen/Qwen3.6-27B"
REVISION = "a" * 40
SERVED = "qwen3.6-27b"


def _snapshot(tmp_path, *, model: str = MODEL, revision: str = REVISION):
    snapshot = (
        tmp_path / ("models--" + model.replace("/", "--"))
        / "snapshots" / revision
    )
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text(json.dumps({
        "_name_or_path": model, "model_type": "qwen3",
        "architectures": ["Qwen3ForCausalLM"],
    }), encoding="utf-8")
    (snapshot / "tokenizer_config.json").write_text(json.dumps({
        "name_or_path": model, "tokenizer_class": "Qwen2TokenizerFast",
    }), encoding="utf-8")
    (snapshot / "tokenizer.json").write_text('{"version":"1"}', encoding="utf-8")
    (snapshot / "model.safetensors").write_bytes(b"qwen-fixture")
    return snapshot


def _process(snapshot, *, model: str = MODEL, revision: str = REVISION,
             served: str = SERVED):
    return {
        "schema_version": mdr.PROCESS_SCHEMA_VERSION,
        "pid": 4321,
        "process_start_ticks": "987654",
        "executable": "/usr/bin/python3",
        "executable_sha256": "1" * 64,
        "argv_sha256": "2" * 64,
        "argc": 9,
        "model_reference": model,
        "model_reference_kind": "repository_revision",
        "revision_binding": revision,
        "served_alias": served,
        "served_alias_explicit": True,
    }


def _receipt(tmp_path, monkeypatch):
    snapshot = _snapshot(tmp_path)
    catalog = {
        "object": "list",
        "data": [{"id": SERVED, "object": "model", "owned_by": "vllm"}],
    }
    monkeypatch.setattr(
        mdr, "_fetch_models", lambda endpoint, timeout_seconds: (
            json.dumps(catalog), catalog,
        ),
    )
    monkeypatch.setattr(
        mdr, "_process_attestation", lambda *args, **kwargs: _process(snapshot),
    )
    receipt = mdr.build_receipt(
        endpoint="http://127.0.0.1:18000/v1", served_model=SERVED,
        model_id=MODEL, model_revision=REVISION, snapshot_path=snapshot,
        server_pid=4321,
    )
    return snapshot, receipt


def test_write_once_is_atomic_first_write_and_load_verifies(tmp_path, monkeypatch):
    snapshot, receipt = _receipt(tmp_path, monkeypatch)
    path = tmp_path / "deployment.json"
    digest = mdr.write_once(path, receipt)
    assert len(digest) == 64
    assert mdr.load_deployment_receipt(
        path, snapshot_path=snapshot, verify_snapshot=True,
    ) == receipt
    assert path.read_text(encoding="utf-8") == mdr.canonical_json(receipt) + "\n"
    with pytest.raises(mdr.DeploymentAttestationError, match="first-write-wins"):
        mdr.write_once(path, receipt)


def test_write_once_does_not_publish_a_partial_file(tmp_path, monkeypatch):
    _snapshot_path, receipt = _receipt(tmp_path, monkeypatch)
    output = tmp_path / "deployment.json"

    def lose_publication(_source, _target):
        raise FileExistsError("race")

    monkeypatch.setattr(mdr.os, "link", lose_publication)
    with pytest.raises(mdr.DeploymentAttestationError, match="first-write-wins"):
        mdr.write_once(output, receipt)
    assert not output.exists()
    assert not list(tmp_path.glob(".deployment.json.pending-*"))


def test_process_args_require_exact_model_revision_and_served_alias(tmp_path):
    snapshot = _snapshot(tmp_path)
    binding = mdr._validate_process_args(
        (
            "vllm", "serve", MODEL, "--revision", REVISION,
            "--served-model-name", SERVED,
        ),
        expected_model_id=MODEL, expected_revision=REVISION,
        served_model=SERVED, snapshot_path=snapshot,
    )
    assert binding == {
        "model_reference": MODEL,
        "model_reference_kind": "repository_revision",
        "revision_binding": REVISION,
        "served_alias": SERVED,
        "served_alias_explicit": True,
    }

    path_binding = mdr._validate_process_args(
        ("vllm", "serve", str(snapshot), "--served-model-name=" + SERVED),
        expected_model_id=MODEL, expected_revision=REVISION,
        served_model=SERVED, snapshot_path=snapshot,
    )
    assert path_binding["model_reference"] == str(snapshot.resolve())
    assert path_binding["model_reference_kind"] == "snapshot_path"

    with pytest.raises(mdr.DeploymentAttestationError, match="immutable revision"):
        mdr._validate_process_args(
            ("vllm", "serve", MODEL, "--served-model-name", SERVED),
            expected_model_id=MODEL, expected_revision=REVISION,
            served_model=SERVED, snapshot_path=snapshot,
        )
    with pytest.raises(mdr.DeploymentAttestationError, match="alias"):
        mdr._validate_process_args(
            ("vllm", "serve", MODEL, "--revision", REVISION, "--note", SERVED),
            expected_model_id=MODEL, expected_revision=REVISION,
            served_model=SERVED, snapshot_path=snapshot,
        )


@pytest.mark.parametrize("args", [
    ("python", "-c", "pass", "--model", MODEL, "--revision", REVISION,
     "--served-model-name", SERVED),
    ("vllm", "serve", "Other/model", "--revision", REVISION,
     "--note", MODEL, "--served-model-name", SERVED),
    ("vllm", "serve", "Other/model", "--revision", REVISION,
     "--model-alias=" + MODEL, "--served-model-name", SERVED),
    ("vllm", "serve", MODEL, "--revision", REVISION,
     "--served-model-name-evil", SERVED),
])
def test_process_argv_substring_and_entrypoint_spoofs_fail(tmp_path, args):
    snapshot = _snapshot(tmp_path)
    with pytest.raises(mdr.DeploymentAttestationError):
        mdr._validate_process_args(
            args, expected_model_id=MODEL, expected_revision=REVISION,
            served_model=SERVED, snapshot_path=snapshot,
        )


def test_python_vllm_module_exact_options_are_supported(tmp_path):
    snapshot = _snapshot(tmp_path)
    binding = mdr._validate_process_args(
        (
            "/usr/bin/python3", "-m", "vllm.entrypoints.openai.api_server",
            "--model=" + MODEL, "--revision=" + REVISION,
            "--served-model-name=" + SERVED,
        ),
        expected_model_id=MODEL, expected_revision=REVISION,
        served_model=SERVED, snapshot_path=snapshot,
    )
    assert binding["model_reference_kind"] == "repository_revision"


def test_receipt_self_hash_and_snapshot_verifier_reject_tampering(
    tmp_path, monkeypatch,
):
    snapshot, receipt = _receipt(tmp_path, monkeypatch)
    tampered = deepcopy(receipt)
    tampered["server_process"]["served_alias"] = "forged"
    with pytest.raises(mdr.DeploymentAttestationError, match="alias"):
        mdr.validate_deployment_receipt(tampered)

    rehashed = deepcopy(receipt)
    rehashed["host"] = "forged-host"
    with pytest.raises(mdr.DeploymentAttestationError, match="self-hash"):
        mdr.validate_deployment_receipt(rehashed)

    (snapshot / "tokenizer.json").write_text('{"version":"2"}', encoding="utf-8")
    with pytest.raises(mdr.DeploymentAttestationError, match="snapshot"):
        mdr.validate_deployment_receipt(
            receipt, snapshot_path=snapshot, verify_snapshot=True,
        )


def test_build_receipt_rejects_duplicate_or_missing_live_model(tmp_path, monkeypatch):
    snapshot = _snapshot(tmp_path)
    monkeypatch.setattr(
        mdr, "_process_attestation", lambda *args, **kwargs: _process(snapshot),
    )
    duplicate = {"data": [{"id": SERVED}, {"id": SERVED}]}
    monkeypatch.setattr(
        mdr, "_fetch_models", lambda endpoint, timeout_seconds: (
            json.dumps(duplicate), duplicate,
        ),
    )
    with pytest.raises(mdr.DeploymentAttestationError, match="duplicate"):
        mdr.build_receipt(
            endpoint="http://127.0.0.1:18000/v1", served_model=SERVED,
            model_id=MODEL, model_revision=REVISION, snapshot_path=snapshot,
            server_pid=4321,
        )

    missing = {"data": [{"id": "another-model"}]}
    monkeypatch.setattr(
        mdr, "_fetch_models", lambda endpoint, timeout_seconds: (
            json.dumps(missing), missing,
        ),
    )
    with pytest.raises(mdr.DeploymentAttestationError, match="exactly once"):
        mdr.build_receipt(
            endpoint="http://127.0.0.1:18000/v1", served_model=SERVED,
            model_id=MODEL, model_revision=REVISION, snapshot_path=snapshot,
            server_pid=4321,
        )


def test_model_catalog_hash_is_canonical_and_auditable(tmp_path, monkeypatch):
    _snapshot_path, receipt = _receipt(tmp_path, monkeypatch)
    assert receipt["advertised_models"] == [SERVED]
    assert receipt["models_response_sha256"] == sha256(
        mdr.canonical_json(receipt["models_response"]).encode("utf-8")
    ).hexdigest()
    assert receipt["deployment_id"].endswith(receipt["receipt_sha256"])


def test_endpoint_and_proc_stat_parser_fail_closed():
    with pytest.raises(mdr.DeploymentAttestationError, match="credential-free"):
        mdr._normalize_endpoint("http://user:secret@127.0.0.1:18000/v1")
    with pytest.raises(mdr.DeploymentAttestationError, match="exactly /v1"):
        mdr._normalize_endpoint("http://127.0.0.1:18000/api")
    fields = ["S"] + [str(index) for index in range(4, 53)]
    raw = "4321 (vllm worker (rank 0)) " + " ".join(fields)
    assert mdr._process_start_ticks(raw) == fields[19]
    with pytest.raises(mdr.DeploymentAttestationError, match="stat schema"):
        mdr._process_start_ticks("broken")
