from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm import prom9_f1_r8_environment as environment


SAFE_ENV = {
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "LC_ALL": "C.UTF-8",
    "OPENAI_API_KEY": "must-never-be-recorded",
    "HSWM_SPOOL_TOKEN": "also-must-never-be-recorded",
}
LABELS = {
    "spool_endpoint": "http://127.0.0.1:8010",
    "model_upstream_endpoint": "http://127.0.0.1:18002/v1/chat/completions",
    "model_deployment_receipt_sha256": "d" * 64,
    "model": "frozen-model-alias",
    "model_revision": "frozen-revision",
    "run_id": "f1-r8-development",
}


def _bundle(
    dependency: Path,
    *,
    environ: dict[str, str] | None = None,
    inline_limit_bytes: int = environment.DEFAULT_INLINE_LIMIT_BYTES,
    chunk_size_bytes: int = environment.DEFAULT_CHUNK_SIZE_BYTES,
) -> dict[str, object]:
    return environment.build_preimage_bundle(
        {"runner": dependency},
        environ=SAFE_ENV if environ is None else environ,
        labels=LABELS,
        inline_limit_bytes=inline_limit_bytes,
        chunk_size_bytes=chunk_size_bytes,
    )


def _dependency_file(bundle: dict[str, object]) -> dict[str, object]:
    dependency_receipt = bundle["dependency_receipt"]
    assert isinstance(dependency_receipt, dict)
    files = dependency_receipt["files"]
    assert isinstance(files, dict)
    value = files["runner"]
    assert isinstance(value, dict)
    return value


def test_bundle_is_deterministic_secret_blind_and_inline_exact(tmp_path: Path) -> None:
    dependency = tmp_path / "runner.py"
    raw = b"print('frozen')\n"
    dependency.write_bytes(raw)
    dependency.chmod(0o640)

    first = _bundle(dependency)
    second = _bundle(dependency)

    assert first == second
    assert environment.verify_preimage_bundle(first) == first[
        "compatibility_root_sha256"
    ]
    assert set(first) == {
        "schema_version",
        "environment_receipt",
        "dependency_receipt",
        "compatibility_root_sha256",
        "bundle_sha256",
    }
    environment_receipt = first["environment_receipt"]
    dependency_receipt = first["dependency_receipt"]
    assert isinstance(environment_receipt, dict)
    assert isinstance(dependency_receipt, dict)
    assert set(environment_receipt) == {
        "schema_version",
        "kind",
        "runtime",
        "environment_allowlist",
        "environment",
        "labels",
        "environment_root_sha256",
        "compatibility_root_sha256",
        "receipt_sha256",
    }
    assert set(dependency_receipt) == {
        "schema_version",
        "kind",
        "preimage_policy",
        "files",
        "dependency_root_sha256",
        "compatibility_root_sha256",
        "receipt_sha256",
    }

    encoded = canonical_json(first)
    assert "OPENAI_API_KEY" not in encoded
    assert "HSWM_SPOOL_TOKEN" not in encoded
    assert "must-never-be-recorded" not in encoded
    assert "also-must-never-be-recorded" not in encoded
    assert environment_receipt["environment_allowlist"] == list(
        environment.NONSECRET_ENV_ALLOWLIST
    )
    captured = environment_receipt["environment"]
    assert isinstance(captured, dict)
    assert captured["PYTHONHASHSEED"] == {"present": True, "value": "0"}
    assert captured["CUDA_VISIBLE_DEVICES"] == {"present": False, "value": None}

    file_preimage = _dependency_file(first)
    assert set(file_preimage) == {
        "resolved_path",
        "size_bytes",
        "mode",
        "sha256",
        "preimage",
    }
    assert file_preimage["mode"] == "0o640"
    assert file_preimage["sha256"] == hashlib.sha256(raw).hexdigest()
    representation = file_preimage["preimage"]
    assert isinstance(representation, dict)
    assert representation["kind"] == "inline-base64"
    assert base64.b64decode(representation["bytes_b64"], validate=True) == raw


def test_compatibility_root_ignores_paths_but_changes_with_bytes(tmp_path: Path) -> None:
    first_path = tmp_path / "one" / "runner.py"
    second_path = tmp_path / "two" / "runner.py"
    first_path.parent.mkdir()
    second_path.parent.mkdir()
    first_path.write_bytes(b"same-preimage")
    second_path.write_bytes(b"same-preimage")
    first_path.chmod(0o600)
    second_path.chmod(0o600)

    first = _bundle(first_path, environ={})
    relocated = _bundle(second_path, environ={})

    assert first["compatibility_root_sha256"] == relocated[
        "compatibility_root_sha256"
    ]
    assert first["bundle_sha256"] != relocated["bundle_sha256"]

    second_path.write_bytes(b"different-preimage")
    second_path.chmod(0o600)
    changed = _bundle(second_path, environ={})
    assert changed["compatibility_root_sha256"] != first[
        "compatibility_root_sha256"
    ]


def test_large_dependency_uses_streamed_chunk_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependency = tmp_path / "large.bin"
    raw = b"abcdefghij"
    dependency.write_bytes(raw)
    dependency.chmod(0o600)

    def forbid_read_bytes(_path: Path) -> bytes:
        raise AssertionError("large preimages must not use Path.read_bytes")

    monkeypatch.setattr(Path, "read_bytes", forbid_read_bytes)
    bundle = _bundle(
        dependency,
        environ={},
        inline_limit_bytes=4,
        chunk_size_bytes=4,
    )

    file_preimage = _dependency_file(bundle)
    representation = file_preimage["preimage"]
    assert isinstance(representation, dict)
    assert representation["kind"] == "streamed-chunk-manifest"
    assert "bytes_b64" not in representation
    assert [row["size_bytes"] for row in representation["chunks"]] == [4, 4, 2]
    assert [row["sha256"] for row in representation["chunks"]] == [
        hashlib.sha256(raw[0:4]).hexdigest(),
        hashlib.sha256(raw[4:8]).hexdigest(),
        hashlib.sha256(raw[8:10]).hexdigest(),
    ]
    assert representation["manifest_sha256"] == canonical_sha256(
        representation["chunks"]
    )
    assert environment.verify_preimage_bundle(bundle) == bundle[
        "compatibility_root_sha256"
    ]


def test_self_verifier_rejects_top_level_entry_and_chunk_drift(tmp_path: Path) -> None:
    dependency = tmp_path / "large.bin"
    dependency.write_bytes(b"abcdefghij")
    dependency.chmod(0o600)
    bundle = _bundle(
        dependency, environ={}, inline_limit_bytes=4, chunk_size_bytes=4
    )

    extra = copy.deepcopy(bundle)
    extra["unexpected"] = True
    with pytest.raises(environment.EnvironmentPreimageError, match="top-level"):
        environment.verify_preimage_bundle(extra)

    changed = copy.deepcopy(bundle)
    file_preimage = _dependency_file(changed)
    representation = file_preimage["preimage"]
    assert isinstance(representation, dict)
    representation["chunks"][0]["sha256"] = "0" * 64
    with pytest.raises(environment.EnvironmentPreimageError, match="manifest root"):
        environment.verify_preimage_bundle(changed)


def test_live_verifier_detects_dependency_mutation(tmp_path: Path) -> None:
    dependency = tmp_path / "runner.py"
    dependency.write_bytes(b"version-one")
    dependency.chmod(0o600)
    bundle = _bundle(dependency, environ={})

    assert environment.verify_preimage_bundle(
        bundle, verify_live=True, environ={}
    ) == bundle["compatibility_root_sha256"]

    dependency.write_bytes(b"version-two")
    dependency.chmod(0o600)
    with pytest.raises(environment.EnvironmentPreimageError, match="live dependency"):
        environment.verify_preimage_bundle(bundle, verify_live=True, environ={})


def test_private_write_is_atomic_0600_and_first_write_wins(tmp_path: Path) -> None:
    dependency = tmp_path / "runner.py"
    dependency.write_bytes(b"frozen")
    dependency.chmod(0o600)
    bundle = _bundle(dependency, environ={})
    output = tmp_path / "private" / "environment.bundle.json"

    raw_digest = environment.write_private_once(output, bundle)

    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    expected_bytes = (canonical_json(bundle) + "\n").encode("utf-8")
    assert hashlib.sha256(expected_bytes).hexdigest() == raw_digest
    assert output.read_bytes() == expected_bytes
    assert environment.load_private_receipt(output) == bundle
    with pytest.raises(environment.EnvironmentPreimageError, match="first-write-wins"):
        environment.write_private_once(output, bundle)
    assert not list(output.parent.glob(".environment.bundle.json.pending-*"))

    output.chmod(0o644)
    with pytest.raises(environment.EnvironmentPreimageError, match="permissions"):
        environment.load_private_receipt(output)


def test_private_write_race_never_publishes_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependency = tmp_path / "runner.py"
    dependency.write_bytes(b"frozen")
    dependency.chmod(0o600)
    bundle = _bundle(dependency, environ={})
    output = tmp_path / "lost-race.json"

    def lose_publication(_source: Path, _target: Path) -> None:
        raise FileExistsError("race")

    monkeypatch.setattr(environment.os, "link", lose_publication)
    with pytest.raises(environment.EnvironmentPreimageError, match="first-write-wins"):
        environment.write_private_once(output, bundle)
    assert not output.exists()
    assert not list(tmp_path.glob(".lost-race.json.pending-*"))


def test_symlink_dependency_and_unallowlisted_label_are_refused(tmp_path: Path) -> None:
    dependency = tmp_path / "runner.py"
    dependency.write_bytes(b"frozen")
    dependency.chmod(0o600)
    alias = tmp_path / "alias.py"
    alias.symlink_to(dependency)

    with pytest.raises(environment.EnvironmentPreimageError, match="symlink"):
        _bundle(alias, environ={})
    with pytest.raises(environment.EnvironmentPreimageError, match="allowlisted"):
        environment.build_preimage_bundle(
            {"runner": dependency},
            environ={},
            labels={"api_token": "secret"},
        )


def test_cli_captures_and_verifies_one_private_bundle(tmp_path: Path) -> None:
    dependency = tmp_path / "runner.py"
    dependency.write_bytes(b"frozen-cli")
    dependency.chmod(0o600)
    output = tmp_path / "bundle.json"
    process_environment = dict(os.environ)
    process_environment["OPENAI_API_KEY"] = "cli-secret-must-not-print"

    captured = subprocess.run(
        [
            sys.executable,
            "-m",
            "prom_search_hswm.prom9_f1_r8_environment",
            "capture",
            "--dependency",
            f"runner={dependency}",
            "--label",
            "run_id=f1-r8-development",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
    )
    assert captured.returncode == 0, captured.stderr
    summary = json.loads(captured.stdout)
    assert summary["status"] == "CAPTURED"
    assert summary["dependency_count"] == 1
    assert "cli-secret-must-not-print" not in captured.stdout + captured.stderr
    assert str(dependency) not in captured.stdout
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    verified = subprocess.run(
        [
            sys.executable,
            "-m",
            "prom_search_hswm.prom9_f1_r8_environment",
            "verify",
            "--input",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout) == {
        "status": "VERIFIED",
        "compatibility_root_sha256": summary["compatibility_root_sha256"],
        "live": False,
    }


def test_semantic_name_map_rejects_swaps_and_missing_paths(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    first.chmod(0o600)
    second.chmod(0o600)
    bundle = environment.build_preimage_bundle(
        {"first": first, "second": second}, environ={}
    )
    dependency = bundle["dependency_receipt"]
    assert isinstance(dependency, dict)
    assert environment.verify_named_dependency_paths(
        dependency, {"first": first, "second": second}
    ) == dependency["receipt_sha256"]

    with pytest.raises(environment.EnvironmentPreimageError, match="path drifted"):
        environment.verify_named_dependency_paths(
            dependency, {"first": second, "second": first}
        )
    missing = tmp_path / "missing.py"
    with pytest.raises(environment.EnvironmentPreimageError, match="unavailable"):
        environment.verify_named_dependency_paths(
            dependency, {"first": missing, "second": second}
        )


def test_r8_labels_and_live_repository_commit_are_exact() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    labels = environment.r8_environment_labels(
        spool_endpoint="http://127.0.0.1:8010",
        model_upstream_endpoint="http://127.0.0.1:18002/v1/chat/completions",
        model_deployment_receipt_sha256="d" * 64,
        model="model",
        model_revision="f" * 40,
        run_id="run",
        hswm_commit=commit,
        symposium_commit=commit,
    )
    assert set(labels) == set(environment.NONSECRET_LABEL_ALLOWLIST)
    assert environment.verify_repository_commit(repo_root, commit) == commit
    with pytest.raises(environment.EnvironmentPreimageError, match="model revision"):
        environment.r8_environment_labels(
            spool_endpoint="http://127.0.0.1:8010",
            model_upstream_endpoint="http://127.0.0.1:18002/v1/chat/completions",
            model_deployment_receipt_sha256="d" * 64,
            model="model",
            model_revision="revision",
            run_id="run",
            hswm_commit=commit,
            symposium_commit=commit,
        )
    with pytest.raises(environment.EnvironmentPreimageError, match="receipt label"):
        environment.r8_environment_labels(
            spool_endpoint="http://127.0.0.1:8010",
            model_upstream_endpoint="http://127.0.0.1:18002/v1/chat/completions",
            model_deployment_receipt_sha256="not-a-digest",
            model="model",
            model_revision="f" * 40,
            run_id="run",
            hswm_commit=commit,
            symposium_commit=commit,
        )
    with pytest.raises(environment.EnvironmentPreimageError, match="commit label"):
        environment.r8_environment_labels(
            spool_endpoint="http://127.0.0.1:8010",
            model_upstream_endpoint="http://127.0.0.1:18002/v1/chat/completions",
            model_deployment_receipt_sha256="d" * 64,
            model="model",
            model_revision="f" * 40,
            run_id="run",
            hswm_commit="not-a-commit",
            symposium_commit=commit,
        )
    with pytest.raises(environment.EnvironmentPreimageError, match="differs"):
        environment.verify_repository_commit(repo_root, "0" * 40)


def test_repository_dependency_blobs_are_exact_but_foreign_dirt_is_allowed(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "HSWM test"],
        check=True,
    )
    dependency = repo / "dependency.py"
    foreign = repo / "foreign.txt"
    dependency.write_text("VALUE = 1\n", encoding="utf-8")
    foreign.write_text("foreign baseline\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py", "foreign.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "freeze"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

    foreign.write_text("unrelated foreign drift\n", encoding="utf-8")
    assert environment.verify_repository_dependency_blobs(
        repo, commit, {"runner": dependency}
    ) == ("dependency.py",)
    subprocess.run(["git", "-C", str(repo), "add", "foreign.txt"], check=True)
    (repo / "untracked-foreign.txt").write_text(
        "untracked foreign drift\n", encoding="utf-8"
    )
    assert environment.verify_repository_dependency_blobs(
        repo, commit, {"runner": dependency}
    ) == ("dependency.py",)

    dependency.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(environment.EnvironmentPreimageError, match="blob differs"):
        environment.verify_repository_dependency_blobs(
            repo, commit, {"runner": dependency}
        )

    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    dependency.write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(environment.EnvironmentPreimageError, match="differs"):
        environment.verify_repository_dependency_blobs(
            repo, commit, {"runner": dependency}
        )

    untracked = repo / "untracked.py"
    untracked.write_text("VALUE = 3\n", encoding="utf-8")
    with pytest.raises(environment.EnvironmentPreimageError, match="absent"):
        environment.verify_repository_dependency_blobs(
            repo, commit, {"runner": untracked}
        )


@pytest.mark.parametrize(
    ("committed_mode", "live_mode"),
    [(0o755, 0o644), (0o644, 0o755)],
)
def test_repository_dependency_tree_mode_is_exact_with_core_filemode_false(
    tmp_path: Path, committed_mode: int, live_mode: int
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "HSWM test"],
        check=True,
    )
    dependency = repo / "dependency.py"
    dependency.write_text("VALUE = 1\n", encoding="utf-8")
    dependency.chmod(committed_mode)
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "freeze"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

    assert environment.verify_repository_dependency_blobs(
        repo, commit, {"runner": dependency}
    ) == ("dependency.py",)

    subprocess.run(
        ["git", "-C", str(repo), "config", "core.filemode", "false"],
        check=True,
    )
    dependency.chmod(live_mode)
    assert subprocess.run(
        ["git", "-C", str(repo), "diff", "--quiet", commit, "--", "dependency.py"],
        check=False,
    ).returncode == 0
    with pytest.raises(environment.EnvironmentPreimageError, match="mode differs"):
        environment.verify_repository_dependency_blobs(
            repo, commit, {"runner": dependency}
        )


def test_repository_dependency_committed_symlink_mode_is_refused(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "HSWM test"],
        check=True,
    )
    dependency = repo / "dependency.py"
    dependency.symlink_to("target.py")
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "freeze"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

    dependency.unlink()
    dependency.write_bytes(b"target.py")
    dependency.chmod(0o644)
    with pytest.raises(
        environment.EnvironmentPreimageError,
        match="unsupported committed tree mode 120000",
    ):
        environment.verify_repository_dependency_blobs(
            repo, commit, {"runner": dependency}
        )


def test_repository_dependency_parent_symlink_escape_is_refused(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "HSWM test"],
        check=True,
    )
    committed_parent = repo / "code"
    committed_parent.mkdir()
    dependency = committed_parent / "dependency.py"
    dependency.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "code/dependency.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "freeze"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

    committed_parent.rename(repo / "displaced-code")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "dependency.py").write_text("VALUE = 1\n", encoding="utf-8")
    committed_parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(environment.EnvironmentPreimageError, match="not canonical"):
        environment.verify_repository_dependency_blobs(
            repo, commit, {"runner": dependency}
        )


def test_repository_dependency_ignores_forged_git_index_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "HSWM test"],
        check=True,
    )
    dependency = repo / "dependency.py"
    dependency.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "freeze"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    forged_index = tmp_path / "forged-clean-index"
    shutil.copy2(repo / ".git" / "index", forged_index)

    dependency.write_text("VALUE = 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    dependency.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setenv("GIT_INDEX_FILE", str(forged_index))
    assert subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet", commit],
        check=False,
    ).returncode == 0
    with pytest.raises(environment.EnvironmentPreimageError, match="differs"):
        environment.verify_repository_dependency_blobs(
            repo, commit, {"runner": dependency}
        )


def test_repository_dependency_git_reads_ignore_replace_refs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "HSWM test"],
        check=True,
    )
    dependency = repo / "dependency.py"
    original = b"VALUE = 1\n"
    replacement = b"VALUE = 2\n"
    dependency.write_bytes(original)
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "original"], check=True)
    original_commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    dependency.write_bytes(replacement)
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "replacement"], check=True)
    replacement_commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    dependency.write_bytes(original)
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "HEAD", original_commit],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "replace", original_commit, replacement_commit],
        check=True,
    )

    naive_env = dict(os.environ)
    naive_env.pop("GIT_NO_REPLACE_OBJECTS", None)
    assert subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{original_commit}:dependency.py"],
        env=naive_env,
    ) == replacement
    assert environment.verify_repository_dependency_blobs(
        repo, original_commit, {"runner": dependency}
    ) == ("dependency.py",)


def test_repository_dependency_blob_reads_ignore_replace_refs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "HSWM test"],
        check=True,
    )
    dependency = repo / "dependency.py"
    original = b"VALUE = 1\n"
    replacement = b"VALUE = 2\n"
    dependency.write_bytes(original)
    subprocess.run(["git", "-C", str(repo), "add", "dependency.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "freeze"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    original_blob = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"{commit}:dependency.py"],
        text=True,
    ).strip()
    replacement_blob = subprocess.check_output(
        ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
        input=replacement,
    ).decode("ascii").strip()
    subprocess.run(
        ["git", "-C", str(repo), "replace", original_blob, replacement_blob],
        check=True,
    )

    naive_env = dict(os.environ)
    naive_env.pop("GIT_NO_REPLACE_OBJECTS", None)
    assert subprocess.check_output(
        ["git", "-C", str(repo), "cat-file", "blob", original_blob],
        env=naive_env,
    ) == replacement
    assert environment.verify_repository_dependency_blobs(
        repo, commit, {"runner": dependency}
    ) == ("dependency.py",)


def test_r8_dependency_path_inventory_covers_every_runtime_module(
    tmp_path: Path,
) -> None:
    tokenizer = tmp_path / "tokenizer"
    paths = environment.r8_dependency_paths(
        protocol_path=tmp_path / "protocol.json",
        judge_core_path=tmp_path / "judge.py",
        result_contract_path=tmp_path / "result-contract.json",
        tokenizer_dir=tokenizer,
        model_catalog_path=tmp_path / "model-catalog.json",
        model_weight_receipt_path=tmp_path / "model-weight.json",
        python_lock_path=tmp_path / "requirements.lock",
    )
    assert tuple(paths) == environment.R8_DEPENDENCY_NAMES
    module_dir = Path(environment.__file__).resolve().parent
    expected_code = {
        "runner": "prom9_f1_r8_runner.py",
        "private_output": "prom9_f1_r8_private_output.py",
        "environment": "prom9_f1_r8_environment.py",
        "lock_builder": "prom9_f1_r8_lock.py",
        "power_builder": "prom9_f1_r8_power.py",
        "power_cli": "prom9_f1_r8_power_cli.py",
        "prior_exposure": "prom9_f1_prior_exposure.py",
        "data_preparer_core": "prom9_prepare_2wiki_f1.py",
        "function_network_adapter": "prom_f1_function_network.py",
        "protocol_loader": "prom9_protocol.py",
        "terminal_transport_exporter": "prom9_f1_r8_transport_audit.py",
        "function_network": "hswm_function_network.py",
        "durable_transport": "hswm_f1_durable_transport.py",
        "result_spool": "hswm_result_spool.py",
        "call_receipt": "hswm_call_receipt.py",
        "function_registry": "hswm_function_registry.py",
        "token_meter": "hswm_token_meter.py",
        "typed_ports": "hswm_typed_ports.py",
        "token_envelope": "prom9_f1_envelope.py",
        "model_deployment_receipt_code": "model_deployment_receipt.py",
        "model_snapshot_attestation_core": "bge_m3_embed.py",
        "data_preparer": "prom9_f1_r8_source.py",
    }
    assert set(expected_code) == set(environment.R8_COMMIT_BOUND_DEPENDENCY_NAMES)
    assert all(
        paths[name] == module_dir / filename
        for name, filename in expected_code.items()
        if name not in {
            "model_deployment_receipt_code",
            "model_snapshot_attestation_core",
        }
    )
    assert paths["model_deployment_receipt_code"] == (
        module_dir.parent / "model_deployment_receipt.py"
    )
    assert paths["model_snapshot_attestation_core"] == (
        module_dir.parent / "bge_m3_embed.py"
    )
    assert len(paths) == 31
    assert "model_weight_receipt" not in paths
    assert paths["model_deployment_receipt"] == tmp_path / "model-weight.json"
