from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.infrastructure import frontier_learning_projection as projection
from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphViewError


ROOT = Path(__file__).resolve().parents[1]


def fixture(root: Path) -> dict:
    source = root / "evidence.md"
    source.write_text("source-bound evidence\n")
    binding = {"path": "evidence.md", "sha256": sha256(source.read_bytes()).hexdigest()}
    bundle_uid = projection.BUNDLE_UID
    source_uid = "sym:CanonicalSource:frontier-paper"
    nodes = [
        {
            "uid": bundle_uid,
            "labels": ["AbstractNode", "ResearchArtifact"],
            "properties": {
                "name": "frontier bundle",
                "authority_class": "SECONDARY_AI",
                "standard_graph_role": "BUNDLE",
                "source_commit": "a" * 40,
                "source_paths": ["evidence.md"],
            },
        },
        {
            "uid": source_uid,
            "labels": ["CanonicalSource"],
            "properties": {
                "name": "source",
                "authority_class": "SECONDARY_AI",
                "standard_graph_role": "SOURCE_RECORD",
                "source_paths": ["evidence.md"],
            },
        },
    ]
    relations = [
        {
            "from_uid": bundle_uid,
            "type": "HAS_SOURCE",
            "to_uid": source_uid,
            "authority_class": "SECONDARY_AI",
            "scope": "FRONTIER_LEARNING_THEORY",
            "status": "REPORTED_SOURCE",
        }
    ]
    return {
        "schema_version": projection.SCHEMA_VERSION,
        "bundle_uid": bundle_uid,
        "status": "SOURCE_INDEX_NOT_EFFICACY_EVIDENCE",
        "nonclaim": "SOURCE_BOUND_RESEARCH_INDEX_NOT_LEARNING_EFFICACY",
        "artifact_bindings": [binding],
        "expected_counts": {"nodes": len(nodes), "anchors": 0, "relations": len(relations)},
        "anchors": [],
        "nodes": nodes,
        "relations": relations,
    }


def test_validation_rejects_binding_drift_and_non_relation_object(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    projection.validate_data(data, tmp_path)
    (tmp_path / "evidence.md").write_text("drift\n")
    with pytest.raises(ValueError, match="hash drift"):
        projection.validate_data(data, tmp_path)

    data = fixture(tmp_path)
    data["relations"] = ["not-a-relation"]
    with pytest.raises(ValueError, match="allowlist"):
        projection.validate_data(data, tmp_path)

    data = fixture(tmp_path)
    data["relations"].append(dict(data["relations"][0]))
    data["expected_counts"]["relations"] = 2
    with pytest.raises(KgBundleGraphViewError, match="duplicate relation"):
        projection.validate_data(data, tmp_path)


def test_export_writes_parseable_json_and_apply_refuses_unpinned_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture(tmp_path)
    ontology = tmp_path / "frontier.json"
    ontology.write_text(json.dumps(data))
    raw, parsed = projection._read_data(ontology)
    projection.validate_data(parsed, tmp_path)
    report = projection._export(projection._view(raw), tmp_path / "export", None)
    assert isinstance(report["conforms"], bool)
    assert isinstance(json.loads((tmp_path / "export" / "manifest.json").read_text())["shacl"]["conforms"], bool)
    assert isinstance(json.loads((tmp_path / "export" / "validation.json").read_text())["conforms"], bool)
    assert isinstance(json.loads((tmp_path / "export" / "prov.jsonld").read_text()), dict)

    monkeypatch.setattr(projection.gateway, "publish", lambda *_args: pytest.fail("must not publish"))
    monkeypatch.setattr("sys.argv", ["projection", "--ontology", str(ontology), "--repo-root", str(tmp_path), "--apply"])
    with pytest.raises(SystemExit, match="SHA pin"):
        projection.main()


def test_every_reported_paper_has_source_mechanism_bridge_falsifier_and_provenance() -> None:
    """Keep each literature item actionable without promoting it to HSWM evidence."""

    data = json.loads((ROOT / projection.DEFAULT_ARTIFACT).read_text())
    projection.validate_historical_snapshot(ROOT / projection.DEFAULT_ARTIFACT, repo_root=ROOT)
    nodes = {node["uid"]: node for node in data["nodes"]}
    outgoing: dict[str, list[dict]] = {}
    for relation in data["relations"]:
        outgoing.setdefault(relation["from_uid"], []).append(relation)

    papers = [
        node for node in data["nodes"]
        if node["properties"].get("standard_graph_role") == "LITERATURE_SOURCE"
    ]
    assert len(papers) == data["expected_counts"]["papers"] == 35
    required_provenance = {
        "url", "authors", "year", "source_date", "source_version", "source_verified_on",
        "source_status", "inspected_scope", "verification_note", "source_authority_class",
        "source_paths", "primary_artifact_path", "primary_artifact_json_pointer",
    }
    for paper in papers:
        properties = paper["properties"]
        assert required_provenance <= set(properties), paper["uid"]
        assert all(properties[key] not in (None, "", []) for key in required_provenance), paper["uid"]
        assert properties["source_authority_class"] == "EXTERNAL_PRIMARY_SOURCE_REPORTED"
        mechanisms = [
            nodes[edge["to_uid"]] for edge in outgoing[paper["uid"]]
            if edge["type"] == "HAS_CONCEPT"
            and nodes[edge["to_uid"]]["properties"].get("standard_graph_role") == "REPORTED_MECHANISM"
        ]
        assert len(mechanisms) == 1, paper["uid"]
        bridges = [
            nodes[edge["to_uid"]] for edge in outgoing[mechanisms[0]["uid"]]
            if edge["type"] == "SPECULATIVE_LINK"
            and nodes[edge["to_uid"]]["properties"].get("standard_graph_role") == "HSWM_BRIDGE_CANDIDATE"
        ]
        assert len(bridges) == 1, paper["uid"]
        falsifiers = [
            nodes[edge["to_uid"]] for edge in outgoing[bridges[0]["uid"]]
            if edge["type"] == "REQUIRES"
            and nodes[edge["to_uid"]]["properties"].get("standard_graph_role") == "PROPOSED_FALSIFIER"
        ]
        assert len(falsifiers) == 1, paper["uid"]
        assert any(
            edge["type"] == "TESTS" and edge["to_uid"] == bridges[0]["uid"]
            for edge in outgoing[falsifiers[0]["uid"]]
        ), paper["uid"]


def test_historical_snapshot_replays_exact_git_blobs_and_rejects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = ROOT / projection.DEFAULT_ARTIFACT
    report = projection.validate_historical_snapshot(artifact, repo_root=ROOT)
    assert report["artifact_bindings"] == 14
    assert report["historical_source_commit"] == "6e2e49f881ac96cd24cc3064d87273075be339a6"

    corrupt = json.loads(projection.HISTORICAL_SNAPSHOT.read_text())
    corrupt["artifact_bindings"][0]["sha256"] = "0" * 64
    corrupt_path = tmp_path / "corrupt-snapshot.json"
    corrupt_path.write_text(json.dumps(corrupt))
    with pytest.raises(ValueError, match="historical source hash drift"):
        projection.validate_historical_snapshot(artifact, corrupt_path, ROOT)

    corrupt = json.loads(projection.HISTORICAL_SNAPSHOT.read_text())
    corrupt["bundle_sha256"] = "0" * 64
    corrupt_path.write_text(json.dumps(corrupt))
    with pytest.raises(ValueError, match="ontology raw hash drift"):
        projection.validate_historical_snapshot(artifact, corrupt_path, ROOT)

    original_raw, original_data = projection._read_data(artifact)
    coordinated_raw = b'{"coordinated":"tamper"}'
    corrupt = json.loads(projection.HISTORICAL_SNAPSHOT.read_text())
    corrupt["bundle_sha256"] = sha256(coordinated_raw).hexdigest()
    corrupt_path.write_text(json.dumps(corrupt))
    monkeypatch.setattr(projection, "_read_data", lambda _path: (coordinated_raw, original_data))
    with pytest.raises(ValueError, match="reviewed artifact SHA pin"):
        projection.validate_historical_snapshot(artifact, corrupt_path, ROOT)
    monkeypatch.setattr(projection, "_read_data", lambda _path: (original_raw, original_data))

    original_blob = projection._git_blob
    monkeypatch.setattr(
        projection,
        "_git_blob",
        lambda repo, commit, path: b"mismatch" if path == projection.DEFAULT_ARTIFACT.as_posix()
        else original_blob(repo, commit, path),
    )
    with pytest.raises(ValueError, match="Git blob mismatch"):
        projection.validate_historical_snapshot(artifact, repo_root=ROOT)
    monkeypatch.setattr(projection, "_git_blob", original_blob)

    corrupt = json.loads(projection.HISTORICAL_SNAPSHOT.read_text())
    corrupt["source_commit"] = "0" * 40
    corrupt_path.write_text(json.dumps(corrupt))
    with pytest.raises(ValueError, match="commit is unavailable"):
        projection.validate_historical_snapshot(artifact, corrupt_path, ROOT)

    monkeypatch.setattr("sys.argv", ["projection", "--historical-snapshot", "--apply"])
    with pytest.raises(SystemExit, match="cannot be combined"):
        projection.main()
