from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess

import pytest

from hswm.infrastructure import legacy_replay
import scripts.validate_repository_ontology as repository_ontology
from scripts.validate_repository_ontology import (
    ONTOLOGY_PATH,
    OntologyError,
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
    validate_graph(load_repository_ontology())


def test_adaptive_research_strategy_is_a_cross_cutting_bounded_projection() -> None:
    data = load_repository_ontology()
    strategy = data["adaptive_research_strategy"]

    assert strategy["status"] == (
        "TARGET_IDENTITY_FIXED_METHODS_ADAPTIVE_SCIENTIFICALLY_UNJUDGED"
    )
    assert strategy["bundle_uid"] == (
        "sym:AbstractNode:hswm-adaptive-research-strategy-ontology-2026-08-30"
    )
    assert strategy["cross_cutting_concepts"] == [
        "hswm:repo:identity",
        "hswm:repo:learning",
        "hswm:repo:evaluation",
        "hswm:repo:evidence",
    ]
    for key in ("canonical_direction", "methodology", "ontology_projection"):
        path = ROOT / strategy[key]
        assert path.is_file()
        assert not path.is_symlink()
    assert "not a guarantee" in data["nonclaims"][-1]


def test_checkout_summary_is_derived_from_the_frozen_baseline() -> None:
    data = load_repository_ontology()
    paths, from_git = repository_paths()
    entries = legacy_replay.load_migration_entries(ROOT)
    baseline, legacy = load_legacy(data, entries)
    result = validate_checkout(data)

    assert baseline["$schema"] == (
        "../../schemas/hswm_root_compatibility_baseline.v1.schema.json"
    )
    assert baseline["schema_version"] == "hswm-root-compatibility-baseline/v1"
    assert baseline["status"] == "FROZEN_BASELINE"
    assert baseline["source_commit"] == repository_ontology.ROOT_BASELINE_V1_COMMIT

    baseline_paths = set(baseline["paths"])
    migrated_paths = {entry.old_path for entry in entries}
    assert legacy == baseline_paths - migrated_paths

    assert result["paths"] == len(paths)
    assert result["legacy_root_paths"] == len(legacy)
    assert result["concepts"] == len(data["concepts"])
    assert result["from_git"] is from_git


def test_migration_entries_leave_only_canonical_files() -> None:
    data = load_repository_ontology()
    entries = legacy_replay.load_migration_entries(ROOT)
    result = validate_checkout(data)

    python_entries = [entry for entry in entries if entry.old_path.endswith(".py")]
    asset_entries = [entry for entry in entries if not entry.old_path.endswith(".py")]
    assert result["python_root_migrations"] == len(python_entries)
    assert result["asset_root_migrations"] == len(asset_entries)

    for entry in entries:
        old = ROOT / entry.old_path
        canonical = ROOT / entry.canonical_path
        assert not old.exists()
        assert not old.is_symlink()
        assert canonical.is_file()
        assert not canonical.is_symlink()


def test_frozen_migration_registry_is_additive() -> None:
    _, from_git = repository_paths()
    if not from_git:
        pytest.skip("frozen registry comparison requires the source Git objects")
    data = load_repository_ontology()
    baseline, _ = load_legacy(data)
    modified = copy.deepcopy(data)
    modified["python_root_migrations"] = modified["python_root_migrations"][1:]

    with pytest.raises(OntologyError, match="dropped frozen manifests"):
        repository_ontology._validate_frozen_baseline(modified, baseline)


def test_frozen_public_partition_cannot_absorb_a_locked_path() -> None:
    _, from_git = repository_paths()
    if not from_git:
        pytest.skip("frozen root comparison requires the source Git objects")
    data = load_repository_ontology()
    baseline, _ = load_legacy(data)
    modified = copy.deepcopy(baseline)
    moved = modified["paths"].pop(0)
    modified["source_public_paths"].append(moved)

    with pytest.raises(OntologyError, match="frozen ontology"):
        repository_ontology._validate_frozen_baseline(data, modified)


def test_current_public_surface_matches_the_frozen_partition() -> None:
    _, from_git = repository_paths()
    if not from_git:
        pytest.skip("frozen root comparison requires the source Git objects")
    data = load_repository_ontology()
    baseline, _ = load_legacy(data)
    modified = copy.deepcopy(data)
    modified["public_root_surface"] = modified["public_root_surface"][1:]

    with pytest.raises(OntologyError, match="current public root surface"):
        repository_ontology._validate_frozen_baseline(modified, baseline)


def test_baseline_path_cannot_escape_the_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(repository_ontology, "REPO_ROOT", repository)

    with pytest.raises(OntologyError, match="invalid root compatibility baseline"):
        load_legacy(
            {"root_compatibility_baseline": "../outside.json"},
            entries=(),
        )


def test_active_root_paths_must_be_regular_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    target = tmp_path / "README.md"
    target.write_text("outside\n", encoding="utf-8")
    (repository / "README.md").symlink_to(target)
    monkeypatch.setattr(repository_ontology, "REPO_ROOT", repository)

    with pytest.raises(OntologyError, match="not a regular file"):
        validate_root_surface(
            ["README.md"],
            {"public_root_surface": ["README.md"]},
            set(),
        )


def test_frozen_root_path_must_match_the_source_blob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "locked.py").write_text("current\n", encoding="utf-8")
    monkeypatch.setattr(repository_ontology, "REPO_ROOT", repository)
    monkeypatch.setattr(
        repository_ontology,
        "_git_blob",
        lambda _commit, _relative: b"frozen\n",
    )
    payload = {
        "source_commit": "0" * 40,
        "paths": ["locked.py"],
    }

    with pytest.raises(OntologyError, match="frozen root path changed"):
        repository_ontology._validate_active_baseline_bytes(payload, {"locked.py"})


def test_git_checkout_errors_do_not_fall_back_to_a_partial_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    monkeypatch.setattr(repository_ontology, "REPO_ROOT", repository)

    def fail_git(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["git"])

    monkeypatch.setattr(repository_ontology.subprocess, "run", fail_git)
    with pytest.raises(OntologyError, match="Git checkout metadata cannot be read"):
        repository_paths()


@pytest.mark.parametrize("allow_missing", [False, True])
def test_unknown_root_file_cannot_be_silently_classified_as_legacy(
    allow_missing: bool,
) -> None:
    data = load_repository_ontology()
    _, legacy = load_legacy(data)
    unexpected = "NEW_ROOT_RULEBOOK.md"
    assert unexpected not in legacy
    paths, _ = repository_paths()
    with pytest.raises(OntologyError, match="root surface drift"):
        validate_root_surface(
            [*paths, unexpected],
            data,
            legacy,
            allow_missing=allow_missing,
        )


def test_nested_distribution_is_not_mistaken_for_parent_git_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
