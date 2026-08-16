from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

import scripts.validate_repository_ontology as repository_ontology
from scripts.validate_repository_ontology import (
    ONTOLOGY_PATH,
    OntologyError,
    concepts_for_path,
    load_legacy,
    repository_paths,
    validate_checkout,
    validate_graph,
    validate_root_surface,
)


ROOT = Path(__file__).resolve().parents[1]


def load_repository_ontology() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def test_repository_ontology_graph_is_closed() -> None:
    data = load_repository_ontology()
    validate_graph(data)
    assert len(data["concepts"]) == 10
    assert {row["uid"] for row in data["concepts"]} == {
        "hswm:repo:identity",
        "hswm:repo:substrate",
        "hswm:repo:field",
        "hswm:repo:cells",
        "hswm:repo:learning",
        "hswm:repo:boundary",
        "hswm:repo:evaluation",
        "hswm:repo:evidence",
        "hswm:repo:infrastructure",
        "hswm:repo:history",
    }


def test_every_checkout_path_has_an_ontology_concept() -> None:
    data = load_repository_ontology()
    _, legacy = load_legacy(data)
    paths, _ = repository_paths()
    unclassified = [path for path in paths if not concepts_for_path(path, data, legacy)]
    assert unclassified == []


def test_root_compatibility_surface_and_catalog_are_current() -> None:
    data = load_repository_ontology()
    result = validate_checkout(data)
    assert result["concepts"] == 10
    assert result["paths"] > 1_000
    assert result["legacy_root_paths"] == 93
    legacy = json.loads((ROOT / data["legacy_root_inventory"]).read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / data["path_catalog"]).read_text(encoding="utf-8"))
    assert legacy["$schema"] == "../../schemas/hswm_legacy_root_paths.v1.schema.json"
    assert catalog["$schema"] == "../schemas/hswm_path_catalog.v1.schema.json"


def test_python_root_migrations_are_pinned_and_root_count_only_decreases() -> None:
    data = load_repository_ontology()
    result = validate_checkout(data)
    assert result["python_root_migrations"] == 75
    assert len(list(ROOT.glob("*.py"))) == 73
    assert result["root_python_sha_locked"] == 63
    assert result["root_python_replay_locked"] == 10
    assert result["root_python_review_required"] == 0

    for relative in data["python_root_migrations"]:
        manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        for row in manifest["migrations"]:
            assert not (ROOT / row["old_path"]).exists()
            assert (ROOT / row["canonical_path"]).is_file()

    classification = json.loads(
        (ROOT / data["python_root_classification"]).read_text(encoding="utf-8")
    )
    assert classification["baseline_root_python_count"] == 144
    assert classification["observed_root_python_count"] == 73
    assert classification["counts"]["partition_total"] == 73

    replay = data["legacy_replay"]
    assert replay["source_of_truth"] == [
        "python_root_migrations",
        "asset_root_migrations",
    ]
    assert replay["workspace_kind"] == "detached-standalone-clone"
    assert (ROOT / replay["tool"]).is_file()


def test_asset_root_migrations_are_source_pinned_and_leave_no_root_alias() -> None:
    data = load_repository_ontology()
    result = validate_checkout(data)
    manifests = data.get("asset_root_migrations", [])
    expected_count = 0
    for relative in manifests:
        manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        assert manifest["$schema"] == (
            "../../schemas/hswm_root_asset_migrations.v1.schema.json"
        )
        assert manifest["schema_version"] == "hswm-root-asset-migrations/v1"
        assert manifest["status"] == "SOURCE_PINNED_PATH_MIGRATION"
        expected_count += len(manifest["migrations"])
        for row in manifest["migrations"]:
            assert "/" not in row["old_path"]
            assert not (ROOT / row["old_path"]).exists()
            assert (ROOT / row["canonical_path"]).is_file()

    assert expected_count == 128
    assert result["asset_root_migrations"] == expected_count


def test_w14_research_moves_keep_their_typed_concepts() -> None:
    data = load_repository_ontology()
    _, legacy = load_legacy(data)
    expected = {
        "docs/research/ABSORB_CONTRACT_v1.md": "hswm:repo:boundary",
        "docs/research/AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md": (
            "hswm:repo:identity"
        ),
        "docs/research/H3_C0_CHAIN_VIABILITY_DIAGNOSIS_2026-07-20.md": (
            "hswm:repo:cells"
        ),
        "docs/research/PROM_8_DYNAMIC_TWO_LANES_2026-07-22.md": (
            "hswm:repo:learning"
        ),
        "docs/research/WORLD_COMPILER_V2_OSS_PROM_2026-07-21.md": (
            "hswm:repo:substrate"
        ),
        "docs/research/core-development/EXISTENCE_SCOREBOARD.v1.md": (
            "hswm:repo:evaluation"
        ),
        "docs/research/core-development/HSWM_CORE_DEV.md": "hswm:repo:identity",
        "prereg/PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md": (
            "hswm:repo:learning"
        ),
        "scripts/f3v2_smoke_preflight.sh": "hswm:repo:boundary",
    }
    for path, concept in expected.items():
        assert concept in concepts_for_path(path, data, legacy)


def test_w13_typed_json_paths_retain_their_semantic_mounts() -> None:
    data = load_repository_ontology()
    expected = {
        "evidence/EVIDENCE_B1_IDENTITY_UNLOCK_2026-07-22.json": {
            "hswm:repo:evaluation", "hswm:repo:evidence", "hswm:repo:learning",
        },
        "manifests/H3_B3_RUN_MANIFEST_V5_2026-07-20.json": {
            "hswm:repo:boundary", "hswm:repo:cells", "hswm:repo:evidence",
        },
        "manifests/hswm_core_existence_harness.v1.json": {
            "hswm:repo:cells", "hswm:repo:evidence",
        },
        "manifests/P1_SPLIT_2026-07-23.json": {
            "hswm:repo:evidence", "hswm:repo:learning",
        },
        "receipts/RECEIPTS_B1_IDENTITY_UNLOCK_2026-07-22.json": {
            "hswm:repo:evidence", "hswm:repo:learning",
        },
        "prereg/PREREG_R1_T1_RETRY_2026-07-22.json": {
            "hswm:repo:boundary", "hswm:repo:evidence", "hswm:repo:learning",
        },
    }
    for path, concepts in expected.items():
        assert concepts <= set(concepts_for_path(path, data, set())), path


def test_transformer_analogy_requires_an_optimizer_equivalent() -> None:
    data = load_repository_ontology()
    analogy = data["learning_analogy"]
    assert analogy["mapping"]["training_data"] == "token/action/tool/outcome trajectories"
    assert analogy["mapping"]["parameters"] == "durable W, routing, and H"
    assert "Tokens count as training observations only" in analogy["necessary_condition"]
    assert analogy["status"] == "TARGET_ARCHITECTURE_NOT_CURRENT_EFFICACY"


def test_unknown_root_file_cannot_be_silently_classified_as_legacy() -> None:
    data = load_repository_ontology()
    _, legacy = load_legacy(data)
    assert "NEW_ROOT_RULEBOOK.md" not in legacy
    paths, _ = repository_paths()
    with pytest.raises(OntologyError, match="root surface drift"):
        validate_root_surface([*paths, "NEW_ROOT_RULEBOOK.md"], data, legacy)


def test_nested_distribution_is_not_mistaken_for_parent_git_checkout(
    tmp_path, monkeypatch
) -> None:
    checkout = tmp_path / "checkout"
    distribution = checkout / "sdist"
    distribution.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    (distribution / "README.md").write_text("distribution\n", encoding="utf-8")
    (distribution / "PKG-INFO").write_text("generated\n", encoding="utf-8")
    (distribution / "setup.cfg").write_text("[metadata]\n", encoding="utf-8")
    monkeypatch.setattr(repository_ontology, "REPO_ROOT", distribution)

    paths, from_git = repository_ontology.repository_paths()

    assert from_git is False
    assert paths == ["README.md"]
