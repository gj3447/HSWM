from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import pytest

from hswm.infrastructure import legacy_replay


def _git(
    repository: Path,
    *arguments: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=check,
        capture_output=True,
        text=True,
        input=input_text,
        env={
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        },
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", "-A")
    _git(
        repository,
        "-c",
        "user.name=HSWM test",
        "-c",
        "user.email=hswm-test@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )
    return _git(repository, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture()
def replay_repository(tmp_path: Path) -> dict[str, object]:
    repository = tmp_path / "source"
    repository.mkdir()
    _git(repository, "init", "-q")

    old_sources = {
        "legacy_alpha.py": b"VALUE = 'alpha'\n",
        "legacy_beta.py": b"VALUE = 'beta'\n",
    }
    for relative, content in old_sources.items():
        (repository / relative).write_bytes(content)
    (repository / "pyproject.toml").write_text(
        "[project]\nname = 'legacy-replay-fixture'\nversion = '0'\n",
        encoding="utf-8",
    )
    source_commit = _commit(repository, "legacy root layout")

    for relative in old_sources:
        (repository / relative).unlink()
    canonical_sources = {
        "src/hswm/alpha.py": old_sources["legacy_alpha.py"],
        "scripts/beta.py": old_sources["legacy_beta.py"],
    }
    for relative, content in canonical_sources.items():
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    first_manifest = "ontology/migrations/PYTHON_ROOT_MIGRATION.v1.json"
    second_manifest = "ontology/migrations/PYTHON_ROOT_MIGRATION.w2.json"
    _write_json(
        repository / first_manifest,
        {
            "source_commit": source_commit,
            "migrations": [
                {
                    "old_path": "legacy_alpha.py",
                    "canonical_path": "src/hswm/alpha.py",
                    "source_sha256": sha256(old_sources["legacy_alpha.py"]).hexdigest(),
                    "destination_kind": "package-module",
                }
            ],
        },
    )
    _write_json(
        repository / second_manifest,
        {
            "source_commit": source_commit,
            "migrations": [
                {
                    "old_path": "legacy_beta.py",
                    "canonical_path": "scripts/beta.py",
                    "source_sha256": sha256(old_sources["legacy_beta.py"]).hexdigest(),
                    "destination_kind": "maintenance-script",
                }
            ],
        },
    )
    _write_json(
        repository / "ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json",
        {"python_root_migrations": [first_manifest, second_manifest]},
    )
    current_head = _commit(repository, "ontology migration")
    return {
        "repository": repository,
        "source_commit": source_commit,
        "current_head": current_head,
        "old_sources": old_sources,
        "first_manifest": first_manifest,
    }


def test_list_uses_only_ontology_selected_manifests(
    replay_repository: dict[str, object],
) -> None:
    repository = replay_repository["repository"]
    assert isinstance(repository, Path)
    result = legacy_replay.list_migrations(repository)

    assert result["schema_version"] == legacy_replay.LIST_SCHEMA_VERSION
    assert result["count"] == 2
    assert [entry["old_path"] for entry in result["entries"]] == [
        "legacy_alpha.py",
        "legacy_beta.py",
    ]
    assert {entry["source_commit"] for entry in result["entries"]} == {
        replay_repository["source_commit"]
    }


def test_verify_proves_ancestry_and_exact_git_blob(
    replay_repository: dict[str, object],
) -> None:
    repository = replay_repository["repository"]
    assert isinstance(repository, Path)

    all_result = legacy_replay.verify_migrations(repository)
    one_result = legacy_replay.verify_migrations(repository, "legacy_beta.py")

    assert all_result["schema_version"] == legacy_replay.VERIFY_SCHEMA_VERSION
    assert all_result["repository_head"] == replay_repository["current_head"]
    assert all_result["count"] == 2
    assert all(entry["verified"] for entry in all_result["entries"])
    assert one_result["count"] == 1
    assert one_result["entries"][0]["old_path"] == "legacy_beta.py"
    assert one_result["entries"][0]["observed_source_sha256"] == sha256(
        replay_repository["old_sources"]["legacy_beta.py"]
    ).hexdigest()


def test_verify_refuses_manifest_digest_mismatch(
    replay_repository: dict[str, object],
) -> None:
    repository = replay_repository["repository"]
    manifest_relative = replay_repository["first_manifest"]
    assert isinstance(repository, Path)
    assert isinstance(manifest_relative, str)
    manifest_path = repository / manifest_relative
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["migrations"][0]["source_sha256"] = "0" * 64
    _write_json(manifest_path, manifest)

    with pytest.raises(legacy_replay.LegacyReplayError, match="SHA-256 mismatch"):
        legacy_replay.verify_migrations(repository, "legacy_alpha.py")


def test_verify_refuses_commit_outside_head_ancestry(
    replay_repository: dict[str, object],
) -> None:
    repository = replay_repository["repository"]
    manifest_relative = replay_repository["first_manifest"]
    source_commit = replay_repository["source_commit"]
    assert isinstance(repository, Path)
    assert isinstance(manifest_relative, str)
    assert isinstance(source_commit, str)
    source_tree = _git(repository, "rev-parse", f"{source_commit}^{{tree}}").stdout.strip()
    sibling = _git(
        repository,
        "-c",
        "user.name=HSWM test",
        "-c",
        "user.email=hswm-test@example.invalid",
        "commit-tree",
        source_tree,
        input_text="unrelated legacy state\n",
    ).stdout.strip()
    manifest_path = repository / manifest_relative
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_commit"] = sibling
    _write_json(manifest_path, manifest)

    with pytest.raises(legacy_replay.LegacyReplayError, match="not reachable from HEAD"):
        legacy_replay.verify_migrations(repository, "legacy_alpha.py")


def test_materialize_creates_clean_detached_standalone_clone_and_receipt(
    replay_repository: dict[str, object],
    tmp_path: Path,
) -> None:
    repository = replay_repository["repository"]
    source_commit = replay_repository["source_commit"]
    old_sources = replay_repository["old_sources"]
    assert isinstance(repository, Path)
    assert isinstance(source_commit, str)
    assert isinstance(old_sources, dict)
    destination = tmp_path / "detached-replay"
    source_status_before = _git(repository, "status", "--porcelain=v1").stdout

    receipt = legacy_replay.materialize_workspace(
        repository, "legacy_alpha.py", destination,
    )

    assert source_status_before == ""
    assert _git(repository, "status", "--porcelain=v1").stdout == ""
    assert destination.is_dir()
    assert (destination / ".git").is_dir()
    assert _git(destination, "rev-parse", "HEAD").stdout.strip() == source_commit
    assert _git(destination, "symbolic-ref", "-q", "HEAD", check=False).returncode == 1
    assert _git(
        destination, "status", "--porcelain=v1", "--untracked-files=all",
    ).stdout == ""
    assert not (destination / ".git/objects/info/alternates").exists()
    for relative, expected in old_sources.items():
        assert (destination / relative).read_bytes() == expected

    receipt_path = destination / ".git" / legacy_replay.RECEIPT_NAME
    stored_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert stored_receipt == receipt
    assert receipt["schema_version"] == legacy_replay.RECEIPT_SCHEMA_VERSION
    assert receipt["status"] == "VERIFIED"
    assert receipt["workspace_kind"] == "detached-standalone-clone"
    assert receipt["source_commit"] == source_commit
    assert receipt["requested_old_path"] == "legacy_alpha.py"
    assert receipt["pre_materialization_verification_count"] == 2
    assert [row["old_path"] for row in receipt["verified_sources"]] == [
        "legacy_alpha.py",
        "legacy_beta.py",
    ]
    claimed_receipt_sha256 = receipt["receipt_sha256"]
    unhashed_receipt = {**receipt, "receipt_sha256": ""}
    assert claimed_receipt_sha256 == sha256(
        legacy_replay._canonical_json(unhashed_receipt).encode("utf-8")
    ).hexdigest()
    _git(destination, "fsck", "--connectivity-only")


def test_materialize_refuses_checkout_file_digest_mismatch(
    replay_repository: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = replay_repository["repository"]
    assert isinstance(repository, Path)
    destination = tmp_path / "tampered-replay"
    original_git = legacy_replay._git
    tampered = False

    def tampering_git(
        git_repository: Path,
        *arguments: str,
        **options: object,
    ) -> subprocess.CompletedProcess[object]:
        nonlocal tampered
        result = original_git(git_repository, *arguments, **options)
        if (
            not tampered
            and Path(git_repository) == destination
            and "checkout" in arguments
        ):
            (destination / "legacy_alpha.py").write_bytes(b"tampered\n")
            tampered = True
        return result

    monkeypatch.setattr(legacy_replay, "_git", tampering_git)
    with pytest.raises(legacy_replay.LegacyReplayError, match="checkout file SHA-256"):
        legacy_replay.materialize_workspace(
            repository, "legacy_alpha.py", destination,
        )
    assert not (destination / ".git" / legacy_replay.RECEIPT_NAME).exists()


def test_materialize_refuses_dirty_checkout(
    replay_repository: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = replay_repository["repository"]
    assert isinstance(repository, Path)
    destination = tmp_path / "dirty-replay"
    original_git = legacy_replay._git
    dirtied = False

    def dirtying_git(
        git_repository: Path,
        *arguments: str,
        **options: object,
    ) -> subprocess.CompletedProcess[object]:
        nonlocal dirtied
        if (
            not dirtied
            and Path(git_repository) == destination
            and arguments[:1] == ("status",)
        ):
            (destination / "unexpected.txt").write_text("dirty\n", encoding="utf-8")
            dirtied = True
        return original_git(git_repository, *arguments, **options)

    monkeypatch.setattr(legacy_replay, "_git", dirtying_git)
    with pytest.raises(legacy_replay.LegacyReplayError, match="checkout is not clean"):
        legacy_replay.materialize_workspace(
            repository, "legacy_alpha.py", destination,
        )
    assert not (destination / ".git" / legacy_replay.RECEIPT_NAME).exists()


@pytest.mark.parametrize("case", ["equal", "inside", "ancestor", "existing", "missing-parent"])
def test_materialize_refuses_unsafe_destination(
    replay_repository: dict[str, object],
    tmp_path: Path,
    case: str,
) -> None:
    repository = replay_repository["repository"]
    assert isinstance(repository, Path)
    if case == "equal":
        destination = repository
    elif case == "inside":
        destination = repository / "new-replay"
    elif case == "ancestor":
        destination = tmp_path
    elif case == "existing":
        destination = tmp_path / "existing"
        destination.mkdir()
    else:
        destination = tmp_path / "missing-parent" / "replay"

    with pytest.raises(legacy_replay.LegacyReplayError, match="destination"):
        legacy_replay.materialize_workspace(
            repository, "legacy_alpha.py", destination,
        )


def test_materialize_refuses_broken_symlink_destination(
    replay_repository: dict[str, object],
    tmp_path: Path,
) -> None:
    repository = replay_repository["repository"]
    assert isinstance(repository, Path)
    destination = tmp_path / "broken-link"
    destination.symlink_to(tmp_path / "does-not-exist")

    with pytest.raises(legacy_replay.LegacyReplayError, match="must not exist"):
        legacy_replay.materialize_workspace(
            repository, "legacy_alpha.py", destination,
        )


def test_cli_emits_json_and_refuses_unknown_path(
    replay_repository: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = replay_repository["repository"]
    assert isinstance(repository, Path)

    assert legacy_replay.main(["--repo", str(repository), "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["count"] == 2

    assert legacy_replay.main(
        ["--repo", str(repository), "verify", "not-migrated.py"]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown migrated old_path" in captured.err
