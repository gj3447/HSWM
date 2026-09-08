from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from hswm.infrastructure import development_work_projection as projection


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture
def snapshot_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "test")
    (tmp_path / "source.md").write_text("source snapshot\n")
    _git(tmp_path, "add", "source.md")
    _git(tmp_path, "commit", "-m", "snapshot")
    commit = _git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.setattr(projection, "SOURCE_COMMIT", commit)
    return tmp_path, commit


def bundle(root: Path, commit: str) -> dict:
    binding = {"path": "source.md", "sha256": sha256((root / "source.md").read_bytes()).hexdigest()}
    root_node = {
        "uid": projection.BUNDLE_UID,
        "labels": ["AbstractNode", "Concept"],
        "properties": {
            "name": "adaptive development snapshot",
            "description": "bounded engineering reference",
            "authority_class": "SECONDARY_AI",
            "standard_graph_role": "BUNDLE",
            "claim_boundary": "NOT_EFFICACY",
            "projection_nonclaim": "NOT_CANONICAL_STATE",
            "source_commit": commit,
            "source_paths": ["source.md"],
        },
    }
    work_node = {
        "uid": "sym:Concept:adaptive-development-work",
        "labels": ["AbstractNode", "Concept"],
        "properties": {
            "name": "adaptive work",
            "description": "local CLI and profile work",
            "authority_class": "SECONDARY_AI",
            "standard_graph_role": "ENGINEERING_REFERENCE",
            "claim_boundary": "NOT_EFFICACY",
            "projection_nonclaim": "NOT_CANONICAL_STATE",
            "source_commit": commit,
            "source_paths": ["source.md"],
        },
    }
    relations = [{
        "from_uid": projection.BUNDLE_UID,
        "type": "HAS_CONCEPT",
        "to_uid": work_node["uid"],
        "authority_class": "SECONDARY_AI",
        "scope": "ADAPTIVE_DEVELOPMENT_WORK",
        "status": "ENGINEERING_REFERENCE_NOT_EFFICACY",
    }]
    return {
        "schema_version": projection.SCHEMA_VERSION,
        "bundle_uid": projection.BUNDLE_UID,
        "status": "ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY",
        "nonclaim": "LOCAL_ENGINEERING_REFERENCE_NOT_EFFICACY",
        "authority_boundary": "SECONDARY_AI_BOUNDED_PROJECTION",
        "source_accessed_on": "2026-09-08",
        "artifact_bindings": [binding],
        "expected_counts": {"nodes": 2, "anchors": 0, "relations": 1},
        "anchors": [],
        "nodes": [root_node, work_node],
        "relations": relations,
    }


def test_snapshot_bindings_use_git_blobs_and_reject_hash_tampering(snapshot_repo: tuple[Path, str]) -> None:
    root, commit = snapshot_repo
    data = bundle(root, commit)
    projection.validate_data(data, root)
    # Current worktree changes cannot rewrite a source-commit snapshot.
    (root / "source.md").write_text("worktree drift\n")
    projection.validate_data(data, root)
    data["artifact_bindings"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source-commit artifact hash drift"):
        projection.validate_data(data, root)


def test_validation_rejects_endpoint_and_authority_drift(snapshot_repo: tuple[Path, str]) -> None:
    root, commit = snapshot_repo
    data = bundle(root, commit)
    data["relations"][0]["to_uid"] = "sym:Concept:missing"
    with pytest.raises(ValueError, match="endpoint"):
        projection.validate_data(data, root)
    data = bundle(root, commit)
    data["nodes"][1]["properties"]["authority_class"] = "USER_PRIMARY"
    with pytest.raises(ValueError, match="SECONDARY_AI"):
        projection.validate_data(data, root)


def test_apply_requires_exact_reviewed_bytes_then_calls_bounded_gateway(
    snapshot_repo: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, commit = snapshot_repo
    ontology = root / "bundle.json"
    ontology.write_text(json.dumps(bundle(root, commit)))
    config = root / "source.yaml"
    config.write_text("uri: bolt://example.invalid\nuser: test\npassword: not-used\ndatabase: neo4j\n")
    called: dict[str, object] = {}
    monkeypatch.setattr(projection.gateway, "publish", lambda data, config, sha: called.update(data=data, config=config, sha=sha) or {"created_nodes": 2})
    monkeypatch.setattr("sys.argv", ["projection", "--ontology", str(ontology), "--repo-root", str(root), "--apply", "--source-config", str(config)])
    with pytest.raises(SystemExit, match="SHA pin"):
        projection.main()
    assert not called
    monkeypatch.setattr(projection, "REVIEWED_ARTIFACT_SHA256", projection.digest(ontology))
    projection.main()
    assert called["sha"] == projection.digest(ontology)
    assert called["data"] == bundle(root, commit)
