from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

import prom_search_hswm.hswm_result_spool as spool_module
from prom_search_hswm.hswm_result_spool import (
    ModelDeploymentBinding,
    RawHTTPResponse,
    ResultSpoolError,
    ResultSpoolService,
    SPOOL_IDENTITY_SCHEMA,
    SQLiteResultSpool,
    load_model_deployment_binding,
    normalize_upstream_endpoint,
)
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
import prom_search_hswm.prom9_f1_r8_runner as runner
import prom_search_hswm.f1_target_deployment_probe as probe_module


UPSTREAM = "http://127.0.0.1:18002/v1/chat/completions"
MODEL = "Qwen/Qwen3.6-35B-A3B-FP8"
REVISION = "95a723d08a9490559dae23d0cff1d9466213d989"
RECEIPT_SHA = "5" * 64
DEPLOYMENT_ID = f"hswm:model_deployment:v2:{RECEIPT_SHA}"


def _binding(**overrides: str) -> ModelDeploymentBinding:
    values = {
        "upstream_endpoint": UPSTREAM,
        "deployment_receipt_sha256": RECEIPT_SHA,
        "deployment_id": DEPLOYMENT_ID,
        "served_model": MODEL,
        "model_revision": REVISION,
    }
    values.update(overrides)
    return ModelDeploymentBinding(**values)


def _receipt() -> dict[str, object]:
    return {
        "endpoint": "http://127.0.0.1:18002/v1",
        "served_model": MODEL,
        "snapshot": {"resolved_revision": REVISION},
        "receipt_sha256": RECEIPT_SHA,
        "deployment_id": DEPLOYMENT_ID,
    }


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://user@127.0.0.1:18002/v1/chat/completions",
        "http://127.0.0.1:18002/v1/chat/completions?x=1",
        "http://127.0.0.1:18002/v1/chat/completions#fragment",
        "http://127.0.0.1:18002/v1/models",
        "http://127.0.0.1:18002/v1/chat/completions/",
        "ftp://127.0.0.1:18002/v1/chat/completions",
    ),
)
def test_upstream_endpoint_is_exact_credential_free_completions_url(
    endpoint: str,
) -> None:
    with pytest.raises(ResultSpoolError):
        normalize_upstream_endpoint(endpoint)
    assert normalize_upstream_endpoint(UPSTREAM) == UPSTREAM


def test_official_loader_is_live_only_without_snapshot_rehash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _receipt()
    path = tmp_path / "deployment.json"
    path.write_text(canonical_json(receipt) + "\n", encoding="utf-8")
    path.chmod(0o600)
    observed: dict[str, object] = {}

    class FakeDeploymentAttestationError(RuntimeError):
        pass

    def load(receipt_path, **kwargs):
        observed["path"] = Path(receipt_path)
        observed["kwargs"] = dict(kwargs)
        return receipt

    fake = types.ModuleType("model_deployment_receipt")
    fake.DeploymentAttestationError = FakeDeploymentAttestationError
    fake.load_deployment_receipt = load
    monkeypatch.setitem(sys.modules, "model_deployment_receipt", fake)

    assert load_model_deployment_binding(
        path,
        upstream_endpoint=UPSTREAM,
        served_model=MODEL,
        model_revision=REVISION,
    ) == _binding()
    assert observed == {
        "path": path,
        "kwargs": {
            "verify_snapshot": False,
            "verify_live_process": True,
        },
    }


@pytest.mark.parametrize(
    ("upstream", "model", "revision"),
    (
        ("http://127.0.0.1:18003/v1/chat/completions", MODEL, REVISION),
        (UPSTREAM, "alternate-model", REVISION),
        (UPSTREAM, MODEL, "alternate-revision"),
    ),
)
def test_receipt_endpoint_model_and_revision_mismatch_refuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    upstream: str,
    model: str,
    revision: str,
) -> None:
    receipt = _receipt()
    path = tmp_path / "deployment.json"
    path.write_text(canonical_json(receipt) + "\n", encoding="utf-8")
    path.chmod(0o600)

    class FakeDeploymentAttestationError(RuntimeError):
        pass

    fake = types.ModuleType("model_deployment_receipt")
    fake.DeploymentAttestationError = FakeDeploymentAttestationError
    fake.load_deployment_receipt = lambda *_args, **_kwargs: receipt
    monkeypatch.setitem(sys.modules, "model_deployment_receipt", fake)
    with pytest.raises(ResultSpoolError):
        load_model_deployment_binding(
            path,
            upstream_endpoint=upstream,
            served_model=model,
            model_revision=revision,
        )


def test_identity_v2_is_closed_and_dispatch_drift_leaves_no_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteResultSpool(tmp_path / "spool.sqlite3")
    upstream_calls = 0

    def upstream(*_args):
        nonlocal upstream_calls
        upstream_calls += 1
        return RawHTTPResponse(200, {}, b"{}")

    binding = _binding()
    service = ResultSpoolService(
        store,
        upstream_endpoint=UPSTREAM,
        deployment_binding=binding,
        deployment_receipt_path=tmp_path / "deployment.json",
        upstream_transport=upstream,
    )
    identity = service.identity()
    assert set(identity) == {
        "schema_version",
        "normalized_upstream_endpoint",
        "deployment_receipt_sha256",
        "deployment_id",
        "served_model",
        "model_revision",
        "db_identity",
        "audit",
        "identity_sha256",
    }
    assert identity["schema_version"] == SPOOL_IDENTITY_SCHEMA
    assert identity["identity_sha256"] == canonical_sha256(
        {key: value for key, value in identity.items() if key != "identity_sha256"}
    )

    def process_restarted(*_args, **_kwargs):
        raise ResultSpoolError("serving process no longer matches receipt")

    monkeypatch.setattr(
        spool_module, "load_model_deployment_binding", process_restarted
    )
    request = canonical_json({"model": MODEL, "messages": []}).encode("utf-8")
    with pytest.raises(ResultSpoolError, match="serving process"):
        service.execute("a" * 64, "b" * 64, request)
    assert upstream_calls == 0
    assert store.audit()["call_count"] == 0
    store.close()


def test_listener_startup_refuses_attestation_before_database_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "must-not-exist.sqlite3"

    def refuse(*_args, **_kwargs):
        raise ResultSpoolError("deployment mismatch")

    monkeypatch.setattr(spool_module, "load_model_deployment_binding", refuse)
    with pytest.raises(SystemExit) as raised:
        spool_module.main(
            [
                "--db",
                str(database),
                "--upstream",
                UPSTREAM,
                "--served-model",
                MODEL,
                "--model-revision",
                REVISION,
                "--model-deployment-receipt",
                str(tmp_path / "deployment.json"),
            ]
        )
    assert raised.value.code == 2
    assert not database.exists()


def test_request_served_model_mismatch_refuses_before_live_check_or_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteResultSpool(tmp_path / "spool.sqlite3")
    live_checks = 0

    def live(*_args, **_kwargs):
        nonlocal live_checks
        live_checks += 1
        return _binding()

    monkeypatch.setattr(spool_module, "load_model_deployment_binding", live)
    service = ResultSpoolService(
        store,
        upstream_endpoint=UPSTREAM,
        deployment_binding=_binding(),
        deployment_receipt_path=tmp_path / "deployment.json",
        upstream_transport=lambda *_args: pytest.fail("upstream dispatch occurred"),
    )
    request = canonical_json(
        {"model": "alternate-model", "messages": []}
    ).encode("utf-8")
    with pytest.raises(ResultSpoolError, match="request model"):
        service.execute("a" * 64, "b" * 64, request)
    assert live_checks == 0
    assert store.audit()["call_count"] == 0
    store.close()


def test_committed_byte_replay_survives_later_model_process_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteResultSpool(tmp_path / "spool.sqlite3")
    binding = _binding()
    upstream_calls = 0

    def upstream(*_args):
        nonlocal upstream_calls
        upstream_calls += 1
        return RawHTTPResponse(200, {"content-type": "application/json"}, b"{}")

    monkeypatch.setattr(
        spool_module,
        "load_model_deployment_binding",
        lambda *_args, **_kwargs: binding,
    )
    service = ResultSpoolService(
        store,
        upstream_endpoint=UPSTREAM,
        deployment_binding=binding,
        deployment_receipt_path=tmp_path / "deployment.json",
        upstream_transport=upstream,
    )
    request = canonical_json({"model": MODEL, "messages": []}).encode("utf-8")
    first = service.execute("a" * 64, "b" * 64, request)
    assert first.replayed is False

    def process_lost(*_args, **_kwargs):
        raise ResultSpoolError("serving process is gone")

    monkeypatch.setattr(
        spool_module, "load_model_deployment_binding", process_lost
    )
    replay = service.execute("a" * 64, "b" * 64, request)
    assert replay.replayed is True
    assert replay.body == first.body
    assert upstream_calls == 1
    assert store.audit()["status_counts"] == {"COMPLETE": 1}
    store.close()


def _preflight(binding: ModelDeploymentBinding) -> dict[str, object]:
    audit_unsigned = {
        "schema_version": spool_module.SPOOL_SCHEMA,
        "journal_mode": "wal",
        "synchronous": 2,
        "call_count": 0,
        "status_counts": {},
        "completed_root_sha256": canonical_sha256([]),
    }
    audit = {
        **audit_unsigned,
        "audit_sha256": canonical_sha256(audit_unsigned),
    }
    identity_unsigned = {
        "schema_version": SPOOL_IDENTITY_SCHEMA,
        "normalized_upstream_endpoint": binding.upstream_endpoint,
        "deployment_receipt_sha256": binding.deployment_receipt_sha256,
        "deployment_id": binding.deployment_id,
        "served_model": binding.served_model,
        "model_revision": binding.model_revision,
        "db_identity": {
            "resolved_path": "/private/spool.sqlite3",
            "st_dev": 7,
            "st_ino": 11,
        },
        "audit": audit,
    }
    identity = {
        **identity_unsigned,
        "identity_sha256": canonical_sha256(identity_unsigned),
    }
    unsigned = {
        "schema_version": runner.SPOOL_PREFLIGHT_SCHEMA,
        "run_id": "run",
        "execution_lock_sha256": "a" * 64,
        "db_genesis_sha256": "b" * 64,
        "endpoint": "http://127.0.0.1:8010",
        "upstream_endpoint": binding.upstream_endpoint,
        "deployment_receipt_sha256": binding.deployment_receipt_sha256,
        "deployment_id": binding.deployment_id,
        "served_model": binding.served_model,
        "model_revision": binding.model_revision,
        "endpoint_identity": identity,
    }
    return {**unsigned, "preflight_sha256": canonical_sha256(unsigned)}


def _rehash(value: dict[str, object], field: str) -> None:
    unsigned = dict(value)
    unsigned.pop(field, None)
    value[field] = canonical_sha256(unsigned)


def test_preflight_v2_rejects_missing_extra_and_nested_repeated_drift() -> None:
    binding = _binding()
    valid = _preflight(binding)
    expected = {
        "run_id": "run",
        "deployment_binding": binding,
        "execution_lock_sha256": "a" * 64,
        "db_genesis_sha256": "b" * 64,
        "endpoint": "http://127.0.0.1:8010",
    }
    assert runner._validate_spool_identity_preflight(valid, **expected) == valid[
        "preflight_sha256"
    ]
    for changed in ("missing", "extra"):
        candidate = copy.deepcopy(valid)
        if changed == "missing":
            candidate.pop("served_model")
        else:
            candidate["extra"] = True
        _rehash(candidate, "preflight_sha256")
        with pytest.raises(runner.R8RunnerRefusal, match="shape"):
            runner._validate_spool_identity_preflight(candidate, **expected)

    repeated = copy.deepcopy(valid)
    repeated["served_model"] = "alternate-model"
    _rehash(repeated, "preflight_sha256")
    with pytest.raises(runner.R8RunnerRefusal, match="frozen execution"):
        runner._validate_spool_identity_preflight(repeated, **expected)

    nested = copy.deepcopy(valid)
    identity = nested["endpoint_identity"]
    assert isinstance(identity, dict)
    identity["served_model"] = "alternate-model"
    _rehash(identity, "identity_sha256")
    _rehash(nested, "preflight_sha256")
    with pytest.raises(runner.R8RunnerRefusal, match="frozen execution"):
        runner._validate_spool_identity_preflight(nested, **expected)


def test_alternate_self_consistent_deployment_binding_differs_from_lock() -> None:
    binding = _binding()
    lock = {
        "upstream_endpoint": binding.upstream_endpoint,
        "deployment_receipt_sha256": binding.deployment_receipt_sha256,
        "deployment_id": binding.deployment_id,
        "served_model": binding.served_model,
        "model": binding.served_model,
        "model_revision": binding.model_revision,
    }
    runner._validate_deployment_binding(lock, binding)
    alternate_sha = "6" * 64
    alternate = _binding(
        deployment_receipt_sha256=alternate_sha,
        deployment_id=f"hswm:model_deployment:v2:{alternate_sha}",
    )
    with pytest.raises(runner.R8RunnerRefusal, match="frozen execution lock"):
        runner._validate_deployment_binding(lock, alternate)
    with pytest.raises(ResultSpoolError, match="deployment ID"):
        _binding(deployment_id=f"hswm:model_deployment:v2:{'7' * 64}")
    with pytest.raises(ResultSpoolError, match="40-hex"):
        _binding(model_revision="not-an-immutable-revision")


def test_schema_versions_advance_fail_closed() -> None:
    assert SPOOL_IDENTITY_SCHEMA.endswith("/v2")
    assert runner.SPOOL_PREFLIGHT_SCHEMA.endswith("/v2")
    assert runner.EXECUTION_LOCK_SCHEMA.endswith("/v4")
    assert runner.SEALED_LOCK_SCHEMA.endswith("/v6")
    assert runner.SUITE_DRAFT_SCHEMA.endswith("/v4")
    assert runner.SUITE_SCHEMA.endswith("/v4")


def test_control_plane_import_does_not_eagerly_load_snapshot_hasher() -> None:
    program = (
        "import sys; import prom_search_hswm.hswm_result_spool; "
        "assert 'model_deployment_receipt' not in sys.modules; "
        "assert 'bge_m3_embed' not in sys.modules; assert 'numpy' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_target_probe_cli_propagates_exact_deployment_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt_path = tmp_path / "deployment.json"
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        probe_module,
        "load_model_deployment_binding",
        lambda *_args, **_kwargs: _binding(),
    )

    def disconnect(*args):
        observed["args"] = args
        return {"probe": "disconnect_real_upstream", "pass": True}

    monkeypatch.setattr(probe_module, "probe_disconnect", disconnect)
    assert probe_module.main(
        [
            "--workdir",
            str(tmp_path / "probe"),
            "--upstream",
            UPSTREAM,
            "--model",
            MODEL,
            "--model-revision",
            REVISION,
            "--model-deployment-receipt",
            str(receipt_path),
            "--probe",
            "disconnect",
        ]
    ) == 0
    assert observed["args"][4] == receipt_path
    output = json.loads(
        (tmp_path / "probe/F1_TARGET_DEPLOYMENT_PROBE_RECEIPT.json").read_text()
    )
    assert output["schema_version"] == "hswm-f1-target-deployment-probe/v2"
    assert output["config"]["deployment_receipt_sha256"] == RECEIPT_SHA
    assert output["config"]["deployment_id"] == DEPLOYMENT_ID
