from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from _research.dnrd.execute import CORE_SOURCE_FILES
from _research.dnrd.prepare import (
    PreparationRefusal,
    generate_preregistration_b_ci_receipt,
    generate_source_ci_receipt,
    generate_source_manifest,
)
from _research.dnrd.task_family import canonical_json, commitment


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


def _source_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.invalid")
    for relative in CORE_SOURCE_FILES:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture {relative}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "source")
    commit = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    return repo, commit, tree


def _ci_api(run_id: int, commit: str, tree: str, updated: str) -> dict[str, object]:
    return {"id": run_id, "workflow_id": 3, "run_number": 4, "name": "CI", "path": ".github/workflows/ci.yml", "event": "push", "head_branch": "main", "head_sha": commit, "run_attempt": 1, "status": "completed", "conclusion": "success", "created_at": "2026-08-28T00:00:00Z", "run_started_at": "2026-08-28T00:00:01Z", "updated_at": updated, "pull_requests": [], "head_commit": {"id": commit, "tree_id": tree}, "repository": {"id": 1, "full_name": "gj3447/HSWM"}, "head_repository": {"id": 1, "full_name": "gj3447/HSWM"}}


def _list(api: dict[str, object]) -> bytes:
    return canonical_json({"total_count": 1, "workflow_runs": [api]})


def test_source_manifest_is_canonical_exact_closure_and_never_overwrites(tmp_path: Path) -> None:
    repo, _, _ = _source_repo(tmp_path)
    output = tmp_path / "source.json"
    digest = generate_source_manifest(repo_root=repo, output=output)
    raw = output.read_bytes()
    value = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == digest
    assert canonical_json(value) == raw
    assert [row["path"] for row in value["files"]] == sorted(CORE_SOURCE_FILES)
    assert all(
        row["sha256"] == hashlib.sha256((repo / row["path"]).read_bytes()).hexdigest()
        for row in value["files"]
    )
    with pytest.raises(PreparationRefusal, match="overwrite"):
        generate_source_manifest(repo_root=repo, output=output)


def test_source_ci_receipt_preserves_noncanonical_raw_api_bytes(tmp_path: Path) -> None:
    _, commit, tree = _source_repo(tmp_path)
    raw_path = tmp_path / "source-api.json"
    api = _ci_api(17, commit, tree, "2026-08-28T00:00:02Z")
    raw = json.dumps(api, indent=2).encode()
    raw_path.write_bytes(raw)
    list_path = tmp_path / "source-list.json"; list_path.write_bytes(_list(api))
    output = tmp_path / "source-ci.json"
    generate_source_ci_receipt(raw_response=raw_path, raw_list_response=list_path, output=output, source_a_commit=commit, source_a_tree=tree)
    value = json.loads(output.read_bytes())
    assert value["raw_response_utf8"].encode() == raw
    assert value["raw_response_sha256"] == hashlib.sha256(raw).hexdigest()
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    assert value["receipt_sha256"] == commitment(unsigned)


def test_source_ci_cli_accepts_exact_raw_api_bytes_on_stdin(tmp_path: Path) -> None:
    _, commit, tree = _source_repo(tmp_path)
    raw = json.dumps(_ci_api(19, commit, tree, "2026-08-28T00:00:02Z"), indent=1).encode()
    api = json.loads(raw)
    list_path = tmp_path / "stdin-list.json"; list_path.write_bytes(_list(api))
    output = tmp_path / "source-ci-stdin.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "_research.dnrd.prepare",
            "source-ci-receipt",
            "--raw-response",
            "-",
            "--raw-list-response", str(list_path),
            "--source-a-commit",
            commit,
            "--source-a-tree",
            tree,
            "--output",
            str(output),
        ],
        input=raw,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    value = json.loads(output.read_bytes())
    assert value["raw_response_utf8"].encode() == raw
    assert value["raw_response_sha256"] == hashlib.sha256(raw).hexdigest()


def test_b_ci_receipt_binds_detached_checkout_blob_and_completed_time(tmp_path: Path) -> None:
    repo, _, _ = _source_repo(tmp_path)
    prereg = repo / "prereg" / "dnrd.json"
    prereg.parent.mkdir()
    prereg.write_bytes(canonical_json({"frozen": True}))
    _git(repo, "add", "prereg/dnrd.json")
    _git(repo, "commit", "-m", "B")
    commit = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    _git(repo, "checkout", "--detach")
    api = _ci_api(18, commit, tree, "2026-08-28T00:00:03Z")
    raw = canonical_json(api)
    raw_path = tmp_path / "b-api.json"
    raw_path.write_bytes(raw)
    list_path = tmp_path / "b-list.json"; list_path.write_bytes(_list(api))
    output = tmp_path / "b-ci.json"
    generate_preregistration_b_ci_receipt(repo_root=repo, preregistration_path="prereg/dnrd.json", raw_response=raw_path, raw_list_response=list_path, output=output)
    value = json.loads(output.read_bytes())
    assert value["head_sha"] == commit
    assert value["head_tree_oid"] == tree
    assert value["preregistration_git_blob_oid"] == _git(repo, "rev-parse", "HEAD:prereg/dnrd.json")
    assert value["completed_at_unix"] == 1787875203


@pytest.mark.parametrize("field,value", [
    ("run_attempt", 2), ("event", "workflow_dispatch"), ("path", ".github/workflows/other.yml"),
    ("head_branch", "feature"), ("run_started_at", "2026-08-27T23:59:59Z"),
])
def test_source_ci_receipt_refuses_nonunique_selection_contract(tmp_path: Path, field: str, value: object) -> None:
    _, commit, tree = _source_repo(tmp_path)
    api = _ci_api(77, commit, tree, "2026-08-28T00:00:02Z")
    api[field] = value
    run, listing, output = tmp_path / "run.json", tmp_path / "list.json", tmp_path / "out.json"
    run.write_bytes(canonical_json(api)); listing.write_bytes(_list(api))
    with pytest.raises(PreparationRefusal):
        generate_source_ci_receipt(raw_response=run, raw_list_response=listing, output=output, source_a_commit=commit, source_a_tree=tree)


def test_source_ci_receipt_refuses_nonunique_or_mismatched_list(tmp_path: Path) -> None:
    _, commit, tree = _source_repo(tmp_path)
    api = _ci_api(78, commit, tree, "2026-08-28T00:00:02Z")
    run, listing, output = tmp_path / "run.json", tmp_path / "list.json", tmp_path / "out.json"
    run.write_bytes(canonical_json(api))
    listing.write_bytes(canonical_json({"total_count": 2, "workflow_runs": [api, api]}))
    with pytest.raises(PreparationRefusal, match="exactly one"):
        generate_source_ci_receipt(raw_response=run, raw_list_response=listing, output=output, source_a_commit=commit, source_a_tree=tree)
    changed = dict(api); changed["id"] = 79
    listing.write_bytes(canonical_json({"total_count": 1, "workflow_runs": [changed]}))
    with pytest.raises(PreparationRefusal, match="differs"):
        generate_source_ci_receipt(raw_response=run, raw_list_response=listing, output=output, source_a_commit=commit, source_a_tree=tree)
