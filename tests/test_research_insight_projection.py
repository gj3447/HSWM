from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from hswm.infrastructure import research_insight_projection as projection


ROOT = Path(__file__).resolve().parents[1]


def fixture(root: Path) -> dict:
    source = root / "evidence.md"
    source.write_text("bound evidence\n")
    source_hash = sha256(source.read_bytes()).hexdigest()

    def node(uid: str, role: str, status: str, paths: list[str] | None = None) -> dict:
        return {
            "uid": uid,
            "labels": ["Insight"],
            "properties": {
                "name": uid,
                "description": "source-bound insight",
                "authority_class": "SECONDARY_AI",
                "epistemic_status": status,
                "record_lifecycle": "ACTIVE",
                "sensitivity": "non_secret",
                "claim_boundary": "local",
                "semantic_roles": [role],
                "insight_id": uid,
                "source_paths": ["evidence.md"] if paths is None else paths,
            },
        }

    nodes = [
        node("obs", "observation", "DERIVED_SOURCE_READING"),
        node("hyp", "hypothesis", "PROPOSED_UNTESTED"),
        node("rule", "proposed_rule", "PROPOSED_UNTESTED"),
        node("exp", "experiment", "PROPOSED_UNTESTED"),
    ]
    relations = [
        {
            "from_uid": "exp",
            "type": "TESTS",
            "to_uid": "hyp",
            "authority_class": "SECONDARY_AI",
            "scope": "local",
            "status": "PROJECTION_ONLY",
        },
        {
            "from_uid": "rule",
            "type": "DERIVED_FROM",
            "to_uid": "obs",
            "authority_class": "SECONDARY_AI",
            "scope": "local",
            "status": "PROJECTION_ONLY",
        },
        {
            "from_uid": "rule",
            "type": "MOTIVATES",
            "to_uid": "exp",
            "authority_class": "SECONDARY_AI",
            "scope": "local",
            "status": "PROJECTION_ONLY",
        },
    ]
    return {
        "schema_version": "hswm-research-insights/v1",
        "bundle_uid": projection.BUNDLE_UID,
        "status": "READ_ONLY_PROPOSAL_NOT_A_LIVE_KG_MUTATION",
        "authority_boundary": "SECONDARY_AI",
        "nonclaim": "No live KG mutation or research result.",
        "source_commit": "a" * 40,
        "artifact_bindings": [{"path": "evidence.md", "sha256": source_hash}],
        "expected_counts": {"nodes": len(nodes), "anchors": 0, "relations": len(relations)},
        "anchors": [],
        "nodes": nodes,
        "relations": relations,
    }


def test_valid_data_and_source_hash_tamper_are_distinguished(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    projection.validate_data(data, tmp_path)
    (tmp_path / "evidence.md").write_text("tampered\n")
    with pytest.raises(ValueError, match="hash drift"):
        projection.validate_data(data, tmp_path)


def test_checked_in_artifact_validates_against_its_exact_source_hashes() -> None:
    artifact = ROOT / projection.DEFAULT_ARTIFACT
    data = json.loads(artifact.read_text())
    projection.validate_data(data, ROOT)


@pytest.mark.parametrize("path", ["../evidence.md", "dir/../evidence.md", "./evidence.md"])
def test_rejects_non_normalized_artifact_paths(tmp_path: Path, path: str) -> None:
    data = fixture(tmp_path)
    data["artifact_bindings"][0]["path"] = path
    with pytest.raises(ValueError, match="normalized"):
        projection.validate_data(data, tmp_path)


def test_rejects_parent_symlink_in_artifact_binding(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evidence.md").write_text("bound evidence\n")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    data["artifact_bindings"][0] = {
        "path": "linked/evidence.md",
        "sha256": sha256((outside / "evidence.md").read_bytes()).hexdigest(),
    }
    data["nodes"][0]["properties"]["source_paths"] = ["linked/evidence.md"]
    with pytest.raises(ValueError, match="symlink"):
        projection.validate_data(data, tmp_path)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda data: data.__setitem__("authority_boundary", "PRIMARY_AI"), "authority"),
        (lambda data: data["nodes"][1]["properties"].__setitem__("authority_class", "PRIMARY_AI"), "provenance"),
        (lambda data: data["nodes"][1]["properties"].__setitem__("epistemic_status", "DERIVED_SOURCE_READING"), "prospective status"),
        (lambda data: data.__setitem__("source_commit", "not-a-commit"), "source commit"),
    ],
)
def test_rejects_authority_or_hypothesis_status_promotion(
    tmp_path: Path,
    mutate: object,
    match: str,
) -> None:
    data = fixture(tmp_path)
    mutate(data)  # type: ignore[operator]
    with pytest.raises(ValueError, match=match):
        projection.validate_data(data, tmp_path)


@pytest.mark.parametrize("mutation", ["dangling", "delete", "reverse_tests"])
def test_rejects_dangling_deleted_or_reverse_required_relations(
    tmp_path: Path,
    mutation: str,
) -> None:
    data = fixture(tmp_path)
    if mutation == "dangling":
        data["relations"][0]["to_uid"] = "missing"
    elif mutation == "delete":
        data["relations"].pop(0)
    else:
        data["relations"][0]["from_uid"] = "hyp"
        data["relations"][0]["to_uid"] = "exp"
    data["expected_counts"]["relations"] = len(data["relations"])
    with pytest.raises(ValueError, match="relation|links"):
        projection.validate_data(data, tmp_path)


def test_dry_run_cli_never_calls_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data = fixture(tmp_path)
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps(data))
    called = False

    def forbidden_publish(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("dry run must not publish")

    monkeypatch.setattr(projection.gateway, "publish", forbidden_publish)
    monkeypatch.setattr(sys, "argv", ["projection", "--ontology", str(artifact), "--repo-root", str(tmp_path)])
    projection.main()
    assert called is False
    assert json.loads(capsys.readouterr().out)["status"] == "VALIDATED_ONLY_NOT_PUBLISHED"


def test_apply_with_wrong_reviewed_sha_rejects_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = fixture(tmp_path)
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps(data))
    monkeypatch.setattr(projection, "EXPECTED_FILE_SHA256", "f" * 64)
    monkeypatch.setattr(projection.gateway, "publish", lambda *_args, **_kwargs: pytest.fail("must not publish"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["projection", "--ontology", str(artifact), "--repo-root", str(tmp_path), "--apply"],
    )
    with pytest.raises(SystemExit, match="SHA pin"):
        projection.main()
