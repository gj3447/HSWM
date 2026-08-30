from __future__ import annotations

import json
from pathlib import Path

import pytest

from hswm.experiments import alfworld_b0_live as live
from hswm.experiments.alfworld_b0_live import (
    AlfworldB0LiveError,
    LivePaths,
    VOID_STATUS,
    _public,
    run_live,
)
from hswm.experiments.alfworld_b0_dgx import MODEL_REVISION
from hswm.experiments.alfworld_b0_calibration import (
    DGX_RUNTIME_QUALIFICATION,
    VLLM_METRICS_QUALIFICATION,
)


def _paths(tmp_path: Path) -> LivePaths:
    return LivePaths(*([tmp_path / "missing"] * 17))


def test_requires_hswm_run_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HSWM_OUTPUT_ROOT", raising=False)
    monkeypatch.delenv("HSWM_CACHE_ROOT", raising=False)
    with pytest.raises(AlfworldB0LiveError, match="hswm-run"):
        run_live(_paths(tmp_path))


def test_prelease_failure_seals_fresh_void_receipts_under_output_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output, cache = tmp_path / "out", tmp_path / "cache"
    output.mkdir(); cache.mkdir()
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output))
    monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache))
    private, public = run_live(_paths(tmp_path))
    assert private["status"] == public["status"] == VOID_STATUS
    assert (output / "b0.private.json").is_file()
    assert (output / "b0.public.json").is_file()
    assert json.loads((output / "b0.public.json").read_bytes())["status"] == VOID_STATUS
    with pytest.raises(AlfworldB0LiveError, match="fresh existing"):
        run_live(_paths(tmp_path))


def test_public_projection_excludes_private_identity_and_trace_fields() -> None:
    private = {
        "schema_version": "test", "status": "INCONCLUSIVE_MEASUREMENT_NOT_READY",
        "resource_totals": {"completion_call_count": 0},
        "inner": {"opaque_uid": "private-only", "actor_trace": []},
    }
    public = _public(private, status="INCONCLUSIVE_MEASUREMENT_NOT_READY", binding={}, selection={})
    rendered = json.dumps(public, sort_keys=True)
    assert "private-only" not in rendered and "opaque_uid" not in rendered


def test_committed_engineering_prerequisites_are_verified_before_selection() -> None:
    repository = Path(__file__).resolve().parents[1]
    protocol = (
        repository
        / "_research/causal_composition/preregistrations/"
        "alfworld_b0_calibration_2026-08-30/protocol.v1.json"
    )
    paths = LivePaths(repository, protocol, *([protocol] * 15))
    value = json.loads(protocol.read_bytes())
    binding = {
        str(DGX_RUNTIME_QUALIFICATION["path"]): str(
            DGX_RUNTIME_QUALIFICATION["file_sha256"]
        ),
        str(VLLM_METRICS_QUALIFICATION["path"]): str(
            VLLM_METRICS_QUALIFICATION["file_sha256"]
        ),
    }
    live._verify_engineering_prerequisites(paths, value, binding)


def test_prerequisite_failure_seals_void_before_selection_use(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output, cache = tmp_path / "out", tmp_path / "cache"
    output.mkdir()
    cache.mkdir()
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output))
    monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache))
    monkeypatch.setattr(
        live,
        "_verify_bindings",
        lambda _paths: (
            {},
            {"commit": "a" * 40, "tree": "b" * 40, "_protocol": "c" * 64},
        ),
    )
    monkeypatch.setattr(
        live,
        "_verify_engineering_prerequisites",
        lambda *_args: (_ for _ in ()).throw(AlfworldB0LiveError("drift")),
    )
    selection_used = False

    def selection(*_args: object) -> dict[str, object]:
        nonlocal selection_used
        selection_used = True
        return {}

    monkeypatch.setattr(live, "_verify_selection", selection)
    private, public = run_live(_paths(tmp_path))
    assert private["status"] == public["status"] == VOID_STATUS
    assert selection_used is False


def _complete_paths(tmp_path: Path) -> LivePaths:
    repo = tmp_path / "repo"; repo.mkdir()
    files = []
    for name in ("protocol", "private", "public", "pool", "locator", "python", "sudo", "bwrap"):
        path = tmp_path / name; path.write_bytes(b"{}")
        files.append(path)
    directories = []
    for name in ("asset", "upstream", "venv", "runtime", "locks"):
        path = tmp_path / name; path.mkdir()
        directories.append(path)
    hub = tmp_path / "hub"
    snapshot = hub / "models--Qwen--Qwen3.6-35B-A3B-FP8" / "snapshots" / MODEL_REVISION
    snapshot.mkdir(parents=True)
    return LivePaths(repo, files[0], files[1], files[2], files[3], files[4], directories[0], directories[1], directories[2], files[5], directories[3], files[6], files[7], snapshot, hub, directories[4] / "b0.lock", "hswm-alfworld-b0-fake-01")


class _Lease:
    def __init__(self, spec: object, *, fail_attest: bool = False) -> None:
        self.spec = spec; self.fail_attest = fail_attest
        self.startup = {"metrics": b"same", "version": b"same"}; self.final = None; self.calls = []
    def __enter__(self): return self
    def __exit__(self, *_args):
        self.final = {"metrics": b"same"}
    def attest(self, tokenize: int, completion: int):
        self.calls.append((tokenize, completion))
        if self.fail_attest: raise RuntimeError("attestation failed")
        return {"metrics": b"attest"}


def _patch_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live, "_verify_bindings", lambda _paths: ({}, {"commit": "a" * 40, "tree": "b" * 40, "_protocol": "c" * 64, "src/x.py": "d" * 64}))
    monkeypatch.setattr(
        live,
        "_verify_engineering_prerequisites",
        lambda _paths, _protocol, _binding: None,
    )
    monkeypatch.setattr(live, "_verify_selection", lambda _paths, _protocol: {"private_selection_sha256": "e" * 64, "public_selection_sha256": "f" * 64, "selection_digest_sha256": "1" * 64, "pool_manifest_sha256": "2" * 64, "local_locator_sha256": "3" * 64})
    monkeypatch.setattr(live, "dgx_sandbox_identity", lambda **_kwargs: {"profile": {}})


def test_full_fake_path_reaches_lease_and_seals_serialized_private_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output, cache = tmp_path / "out", tmp_path / "cache"; output.mkdir(); cache.mkdir()
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output)); monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache)); _patch_preflight(monkeypatch)
    leases = []
    def lease_factory(spec):
        lease = _Lease(spec); leases.append(lease); return lease
    launched = []

    class DgxRuntime:
        def __init__(self, sandbox, *, sudo):
            launched.append((sandbox, sudo))

        def launch(self):
            return "dgx-process"

    monkeypatch.setattr(live, "DgxB0AlfworldTextRuntime", DgxRuntime)

    def calibration(**kwargs):
        assert kwargs["runtime_launcher"]("sandbox") == "dgx-process"
        return {"status": "EXPLORATORY_B0_CALIBRATION_COMPLETE_G0_NOT_PASSED", "resource_totals": {"issued_tokenize_post_count": 2, "issued_completion_post_count": 2, "issued_http_post_count": 4}}, {}
    paths = _complete_paths(tmp_path)
    private, public = live.run_live(paths, lease_factory=lease_factory, calibration=calibration)
    assert len(leases) == 1 and leases[0].calls == [(2, 2)]
    assert launched == [("sandbox", paths.sudo)]
    assert private["inner_private_receipt"]["resource_totals"]["issued_completion_post_count"] == 2
    assert public["private_receipt_sha256"] == __import__("hashlib").sha256((output / "b0.private.json").read_bytes()).hexdigest()
    assert (output / "content").is_dir()


def test_post_calibration_attestation_failure_preserves_inner_prefix_and_lease_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output, cache = tmp_path / "out", tmp_path / "cache"; output.mkdir(); cache.mkdir()
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output)); monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache)); _patch_preflight(monkeypatch)
    def calibration(**_kwargs):
        return {"status": "EXPLORATORY_B0_CALIBRATION_COMPLETE_G0_NOT_PASSED", "resource_totals": {"issued_tokenize_post_count": 1, "issued_completion_post_count": 1, "issued_http_post_count": 2}}, {}
    private, _public = live.run_live(_complete_paths(tmp_path), lease_factory=lambda spec: _Lease(spec, fail_attest=True), calibration=calibration)
    assert private["status"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    assert private["inner_private_receipt"]["resource_totals"]["issued_tokenize_post_count"] == 1
    assert set(private["lease_blobs"]) == {"startup:metrics", "startup:version", "final:metrics"}
    assert len(list((output / "content").iterdir())) == 1
