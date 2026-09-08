from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from hswm.infrastructure import development_day_projection as projection


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture
def snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, str]:
    _git(tmp_path, "init"); _git(tmp_path, "config", "user.email", "test@example.invalid"); _git(tmp_path, "config", "user.name", "test")
    source = tmp_path / projection.PRIMARY_SOURCE_PATH
    source.parent.mkdir(parents=True); source.write_text("daily self development and KG request\n")
    (tmp_path / "implementation.md").write_text("implementation snapshot\n")
    _git(tmp_path, "add", "."); _git(tmp_path, "commit", "-m", "snapshot")
    commit = _git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.setattr(projection, "SOURCE_COMMIT", commit)
    return tmp_path, commit, source.read_text().rstrip("\n")


def bundle(root: Path, commit: str, quote: str) -> dict:
    primary = {"path": projection.PRIMARY_SOURCE_PATH, "sha256": sha256((root / projection.PRIMARY_SOURCE_PATH).read_bytes()).hexdigest()}
    impl = {"path": "implementation.md", "sha256": sha256((root / "implementation.md").read_bytes()).hexdigest()}
    def node(uid: str, props: dict) -> dict:
        return {"uid": uid, "labels": ["AbstractNode", "Concept"], "properties": {"name": uid, "description": "bounded test node", "source_commit": commit, **props}}
    source_uid = "sym:AbstractNode:development-day-primary-source"
    nodes = [
        node(projection.BUNDLE_UID, {"authority_class": "SECONDARY_AI", "ontology_authority": "SECONDARY_AI", "ontology_authority_class_v1": "SECONDARY_AI", "responsibility_owner": projection.OWNER, "source_paths": ["implementation.md"]}),
        node(source_uid, {"authority_class": "SECONDARY_AI", "ontology_authority": "SECONDARY_AI", "ontology_authority_class_v1": "SECONDARY_AI", "responsibility_owner": projection.OWNER, "role": "SOURCE_ARTIFACT", "standard_graph_role": "SOURCE_ARTIFACT", "source_paths": [projection.PRIMARY_SOURCE_PATH], "source_path": projection.PRIMARY_SOURCE_PATH, "source_sha256": primary["sha256"]}),
        node(projection.USER_UID, {"authority_class": "USER_PRIMARY", "ontology_authority": "USER_PRIMARY", "ontology_authority_class_v1": "USER_PRIMARY", "responsibility_owner": "user:hswm-development-direction", "role": "USER_DIRECT_REQUEST", "standard_graph_role": "USER_DIRECT_REQUEST", "status": "USER_REQUEST_RECORDED_NOT_EFFICACY", "source_path": projection.PRIMARY_SOURCE_PATH, "source_sha256": primary["sha256"], "verbatim_text": quote, "source_paths": [projection.PRIMARY_SOURCE_PATH]}),
    ]
    relations = [
        {"from_uid": projection.BUNDLE_UID, "to_uid": projection.USER_UID, "type": "HAS_CONCEPT", "authority_class": "SECONDARY_AI", "scope": "DEVELOPMENT_DAY", "status": "REFERENCE"},
        {"from_uid": projection.USER_UID, "to_uid": source_uid, "type": "HAS_SOURCE", "authority_class": "SECONDARY_AI", "scope": "DEVELOPMENT_DAY", "status": "REFERENCE"},
    ]
    return {"schema_version": projection.SCHEMA_VERSION, "bundle_uid": projection.BUNDLE_UID, "status": "ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY", "nonclaim": "NOT_EFFICACY", "authority_boundary": "SOURCE_PINNED", "source_accessed_on": "2026-09-08", "artifact_bindings": [primary, impl], "expected_counts": {"nodes": len(nodes), "anchors": 0, "relations": len(relations)}, "anchors": [], "nodes": nodes, "relations": relations}


def test_primary_quote_and_git_binding_fail_closed(snapshot: tuple[Path, str, str]) -> None:
    root, commit, quote = snapshot
    value = bundle(root, commit, quote)
    projection.validate_data(value, root)
    value["nodes"][2]["properties"]["verbatim_text"] = "changed"
    with pytest.raises(ValueError, match="quote/source"):
        projection.validate_data(value, root)
    value = bundle(root, commit, quote)
    value["artifact_bindings"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash drift"):
        projection.validate_data(value, root)
    value = bundle(root, commit, quote)
    value["nodes"][1]["properties"]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="HAS_SOURCE"):
        projection.validate_data(value, root)


def test_primary_promotion_endpoint_and_unreviewed_apply_refuse(snapshot: tuple[Path, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, commit, quote = snapshot
    value = bundle(root, commit, quote)
    value["nodes"][0]["properties"]["authority_class"] = "USER_PRIMARY"
    with pytest.raises(ValueError, match="authority promotion"):
        projection.validate_data(value, root)
    value = bundle(root, commit, quote)
    value["relations"][1]["to_uid"] = "missing"
    with pytest.raises(ValueError, match="endpoint"):
        projection.validate_data(value, root)
    value = bundle(root, commit, quote)
    value["relations"][1]["to_uid"] = projection.USER_UID
    with pytest.raises(ValueError, match="HAS_SOURCE"):
        projection.validate_data(value, root)
    value = bundle(root, commit, quote)
    ontology, config = root / "bundle.json", root / "config.yaml"
    ontology.write_text(json.dumps(value)); config.write_text("uri: bolt://example.invalid\nuser: x\npassword: x\ndatabase: neo4j\n")
    called: dict[str, object] = {}
    monkeypatch.setattr(projection.gateway, "publish", lambda *args: called.update(hit=True) or {})
    monkeypatch.setattr("sys.argv", ["projection", "--ontology", str(ontology), "--repo-root", str(root), "--apply", "--source-config", str(config)])
    with pytest.raises(SystemExit, match="SHA pin"):
        projection.main()
    assert not called
    monkeypatch.setattr(projection, "REVIEWED_ARTIFACT_SHA256", projection.digest(ontology))
    projection.main()
    assert called["hit"] is True
