from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

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
    return LivePaths(*([tmp_path / "missing"] * 18))


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
    if not (repository / ".git").exists():
        pytest.skip("requires source-checkout Git history")
    protocol = (
        repository
        / "_research/causal_composition/preregistrations/"
        "alfworld_b0_calibration_2026-08-30/protocol.v1.json"
    )
    paths = LivePaths(repository, protocol, *([protocol] * 16))
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


def test_runtime_environment_reidentifies_qualified_symlinked_venv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _complete_paths(tmp_path)
    repository = tmp_path / "identity-repo"
    requirements = repository / "requirements.txt"
    contract = (
        repository
        / "_research/causal_composition/preregistrations/"
        "alfworld_b0_calibration_2026-08-30/runtime_qualification_contract.v1.json"
    )
    contract.parent.mkdir(parents=True)
    requirements.write_text("alfworld==0.5.0\n", encoding="utf-8")
    requirements_sha = sha256(requirements.read_bytes()).hexdigest()
    archive = tmp_path / "source.tar.gz"
    archive.write_bytes(b"archive")
    archive_sha = sha256(archive.read_bytes()).hexdigest()
    contract_value = {
        "execution_sources": {"arm64_requirements": "requirements.txt"},
        "runtime_profile": {
            "alfworld": {
                "source_archive_sha256": archive_sha,
                "extracted_tree_member_manifest_sha256": "a" * 64,
            },
            "requirements": {
                "arm64_pddl_only_path": "requirements.txt",
                "arm64_pddl_only_sha256": requirements_sha,
            },
        },
    }
    contract.write_bytes(live.canonical_bytes(contract_value) + b"\n")
    contract_sha = sha256(contract.read_bytes()).hexdigest()
    runtime_root = tmp_path / "runtime-root"
    actual_python = runtime_root / "bin/python3.9"
    actual_python.parent.mkdir(parents=True)
    actual_python.write_bytes(b"python")
    venv = tmp_path / "qualified-venv"
    python = venv / "bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(actual_python)
    packages = [{"name": "alfworld", "version": "0.5.0"}]
    key_versions = {"alfworld": "0.5.0"}
    monkeypatch.setattr(live, "_requirements", lambda _path: key_versions)
    monkeypatch.setattr(
        live,
        "installed_environment",
        lambda selected, *, required: (packages, key_versions),
    )
    observed: dict[str, object] = {}

    def verify_archive(selected: Path, upstream: Path, profile: object) -> None:
        observed.update(selected=selected, upstream=upstream, profile=profile)

    monkeypatch.setattr(live, "_verify_alfworld_archive_tree", verify_archive)
    paths = replace(
        paths,
        repo=repository,
        venv=venv,
        python=python,
        python_runtime_root=runtime_root,
        alfworld_source_archive=archive,
    )
    identity = live._verify_runtime_environment(
        paths,
        {
            "environment_runtime": {
                "arm64_pddl_only_requirements_path": "requirements.txt",
                "arm64_pddl_only_requirements_sha256": requirements_sha,
                "upstream_source_archive_sha256": archive_sha,
            }
        },
        {
            "qualification_contract": {"file_sha256": contract_sha},
            "source_code_sha256": {
                "arm64_requirements": requirements_sha,
                "qualification_contract": contract_sha,
            },
            "python": {"executable_sha256": sha256(b"python").hexdigest()},
            "packages": {
                "installed_package_count": 1,
                "installed_package_list_sha256": sha256(
                    live.canonical_bytes(packages)
                ).hexdigest(),
                "key_versions": key_versions,
            },
        },
    )
    assert identity == {
        "python_executable_sha256": sha256(b"python").hexdigest(),
        "installed_package_list_sha256": sha256(
            live.canonical_bytes(packages)
        ).hexdigest(),
        "alfworld_source_archive_sha256": archive_sha,
        "alfworld_extracted_tree_member_manifest_sha256": "a" * 64,
    }
    assert observed == {
        "selected": archive,
        "upstream": paths.upstream,
        "profile": {
            "source_archive_sha256": archive_sha,
            "extracted_tree_member_manifest_sha256": "a" * 64,
        },
    }


def test_runtime_environment_rejects_venv_parent_traversal(
    tmp_path: Path,
) -> None:
    paths = _complete_paths(tmp_path)
    actual_python = paths.python_runtime_root / "bin/python"
    actual_python.parent.mkdir(parents=True)
    actual_python.write_bytes(b"python")
    escaped_spelling = paths.venv / ".." / paths.python_runtime_root.name / "bin/python"
    with pytest.raises(AlfworldB0LiveError, match="venv entry"):
        live._verify_runtime_environment(
            replace(paths, python=escaped_spelling), {}, {}
        )


@pytest.mark.parametrize("drift", ("contract", "requirements"))
def test_runtime_environment_rejects_immutable_binding_drift(
    drift: str, tmp_path: Path
) -> None:
    repository = Path(__file__).resolve().parents[1]
    protocol_path = (
        repository
        / "_research/causal_composition/preregistrations/"
        "alfworld_b0_calibration_2026-08-30/protocol.v1.json"
    )
    runtime_path = (
        repository
        / "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_DGX_QUALIFICATION_2026-08-30.json"
    )
    protocol = json.loads(protocol_path.read_bytes())
    qualification = json.loads(runtime_path.read_bytes())
    if drift == "contract":
        qualification["qualification_contract"]["file_sha256"] = "0" * 64
    else:
        protocol["environment_runtime"]["arm64_pddl_only_requirements_sha256"] = "0" * 64
    paths = _complete_paths(tmp_path)
    runtime_root = tmp_path / "runtime-root-identity"
    actual_python = runtime_root / "bin/python"
    actual_python.parent.mkdir(parents=True)
    actual_python.write_bytes(b"python")
    venv = tmp_path / "venv-identity"
    python = venv / "bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(actual_python)
    with pytest.raises(AlfworldB0LiveError, match="binding drifted"):
        live._verify_runtime_environment(
            replace(
                paths,
                repo=repository,
                protocol=protocol_path,
                venv=venv,
                python=python,
                python_runtime_root=runtime_root,
            ),
            protocol,
            qualification,
        )


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


def test_main_maps_sudo_bubblewrap_and_source_archive_by_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[LivePaths] = []
    monkeypatch.setattr(
        live,
        "run_live",
        lambda paths: (
            captured.append(paths)
            or {"status": "EXPLORATORY_B0_CALIBRATION_COMPLETE_G0_NOT_PASSED"},
            {},
        ),
    )
    values = {
        name: tmp_path / name
        for name in (
            "repo",
            "protocol",
            "private-selection",
            "public-selection",
            "pool",
            "locator",
            "asset-root",
            "upstream",
            "venv",
            "python",
            "python-runtime-root",
            "sudo",
            "bubblewrap",
            "model-snapshot",
            "hf-hub",
            "alfworld-source-archive",
            "lock",
        )
    }
    argv = [item for name, path in values.items() for item in (f"--{name}", str(path))]
    argv.extend(("--container", "hswm-alfworld-b0-parser-test"))
    assert live.main(argv) == 0
    assert len(captured) == 1
    assert captured[0].sudo == values["sudo"]
    assert captured[0].bubblewrap == values["bubblewrap"]
    assert captured[0].alfworld_source_archive == values["alfworld-source-archive"]


def _complete_paths(tmp_path: Path) -> LivePaths:
    repo = tmp_path / "repo"; repo.mkdir()
    files = []
    for name in (
        "protocol",
        "private",
        "public",
        "pool",
        "locator",
        "python",
        "sudo",
        "bwrap",
        "archive",
    ):
        path = tmp_path / name; path.write_bytes(b"{}")
        files.append(path)
    directories = []
    for name in ("asset", "upstream", "venv", "runtime", "locks"):
        path = tmp_path / name; path.mkdir()
        directories.append(path)
    hub = tmp_path / "hub"
    snapshot = hub / "models--Qwen--Qwen3.6-35B-A3B-FP8" / "snapshots" / MODEL_REVISION
    snapshot.mkdir(parents=True)
    return LivePaths(
        repo=repo,
        protocol=files[0],
        private_selection=files[1],
        public_selection=files[2],
        pool=files[3],
        locator=files[4],
        asset_root=directories[0],
        upstream=directories[1],
        venv=directories[2],
        python=files[5],
        python_runtime_root=directories[3],
        bubblewrap=files[7],
        sudo=files[6],
        model_snapshot=snapshot,
        hf_hub=hub,
        alfworld_source_archive=files[8],
        lock=directories[4] / "b0.lock",
        container_name="hswm-alfworld-b0-fake-01",
    )


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
        lambda _paths, _protocol, _binding: {},
    )
    monkeypatch.setattr(
        live,
        "_verify_runtime_environment",
        lambda _paths, _protocol, _qualification: {},
    )
    monkeypatch.setattr(live, "_verify_selection", lambda _paths, _protocol: {"private_selection_sha256": "e" * 64, "public_selection_sha256": "f" * 64, "selection_digest_sha256": "1" * 64, "pool_manifest_sha256": "2" * 64, "local_locator_sha256": "3" * 64})
    monkeypatch.setattr(
        live,
        "_verify_selected_assets",
        lambda _paths: {
            "selected_file_count": 12,
            "valid_unseen_selected_file_count": 0,
        },
    )
    monkeypatch.setattr(live, "dgx_sandbox_identity", lambda **_kwargs: {"profile": {}})


def test_selected_assets_are_validated_as_private_preflight_aggregate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _complete_paths(tmp_path)
    rows = tuple(
        SimpleNamespace(
            split="train" if index < 8 else "valid_seen",
            opaque_uid=f"private-{index}",
        )
        for index in range(12)
    )
    pool_sha = sha256(paths.pool.read_bytes()).hexdigest()
    locator_sha = sha256(paths.locator.read_bytes()).hexdigest()
    monkeypatch.setattr(
        live, "verify_protocol", lambda _path: SimpleNamespace(max_steps=40)
    )
    monkeypatch.setattr(
        live,
        "verify_private_selection",
        lambda *_args, **_kwargs: (rows, "private", "selection"),
    )
    loaded: list[str] = []

    def load_binding(**kwargs: object) -> tuple[str, str, object, Path]:
        uid = str(kwargs["opaque_uid"])
        loaded.append(uid)
        return pool_sha, locator_sha, SimpleNamespace(opaque_uid=uid), tmp_path / uid

    validated: list[dict[str, object]] = []

    class FakeSandboxSpec:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def validate(self) -> None:
            validated.append(self.kwargs)

    monkeypatch.setattr(live, "load_local_game_binding", load_binding)
    monkeypatch.setattr(live, "LocalSandboxSpec", FakeSandboxSpec)
    assert live._verify_selected_assets(paths) == {
        "selected_file_count": 12,
        "valid_unseen_selected_file_count": 0,
    }
    assert loaded == [row.opaque_uid for row in rows]
    assert len(validated) == 12
    assert all(item["max_steps"] == 40 for item in validated)


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
    assert json.loads((output / "b0.start.json").read_bytes())["selected_assets"] == {
        "selected_file_count": 12,
        "valid_unseen_selected_file_count": 0,
    }


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
