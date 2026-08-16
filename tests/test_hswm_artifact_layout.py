"""Layout convention tests (root-tidy follow-up).

New artifacts default to per-kind subdirectories; legacy root artifacts remain
resolvable through the fallback reader.  See docs/research/ARTIFACT_LAYOUT.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import hswm_artifact_layout as legacy_layout
from hswm.artifacts import layout

REPO = Path(__file__).resolve().parents[1]


def test_legacy_layout_import_resolves_to_canonical_objects():
    assert legacy_layout.default_artifact_path is layout.default_artifact_path
    assert legacy_layout.resolve_artifact_path is layout.resolve_artifact_path
    assert legacy_layout.REPO_ROOT == layout.REPO_ROOT == REPO


def test_classify_artifact_kinds():
    assert layout.classify_artifact("EVIDENCE_X_2026-01-01.json") == "evidence"
    assert layout.classify_artifact("PREREG_X_2026-01-01.json") == "prereg"
    assert layout.classify_artifact("PREREG_X_2026-01-01.md") == "prereg"
    assert layout.classify_artifact("H3_B3_RUN_MANIFEST_2026-01-01.json") == "manifest"
    assert layout.classify_artifact("B1_X_RESULTS_2026-01-01.md") == "results"
    assert layout.classify_artifact("substrate_bench_results.json") is None
    assert layout.classify_artifact("README.md") is None


def test_default_artifact_path_uses_kind_subdir(tmp_path, monkeypatch):
    monkeypatch.setenv("HSWM_ARTIFACT_ROOT", str(tmp_path))
    path = layout.default_artifact_path("EVIDENCE_X_2026-01-01.json")
    assert path == tmp_path / "evidence" / "EVIDENCE_X_2026-01-01.json"
    assert path.parent.is_dir()


def test_env_override_redirects_output_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HSWM_ARTIFACT_ROOT", str(tmp_path))
    path = layout.default_artifact_path("PREREG_X_2026-01-01.json")
    assert tmp_path in path.parents
    monkeypatch.delenv("HSWM_ARTIFACT_ROOT")
    plain = layout.default_artifact_path("PREREG_X_2026-01-01.json", create=False)
    assert plain == layout.REPO_ROOT / "prereg" / "PREREG_X_2026-01-01.json"


def test_default_root_is_independent_of_current_working_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("HSWM_ARTIFACT_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert layout.artifact_root() == REPO


def test_installed_layout_requires_explicit_artifact_root(tmp_path, monkeypatch):
    monkeypatch.setattr(layout, "REPO_ROOT", None)
    monkeypatch.delenv("HSWM_ARTIFACT_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="require HSWM_ARTIFACT_ROOT"):
        layout.artifact_root()

    monkeypatch.setenv("HSWM_ARTIFACT_ROOT", str(tmp_path))
    assert layout.artifact_root() == tmp_path


def test_resolve_prefers_subdir_then_legacy_root(tmp_path):
    name = "EVIDENCE_X_2026-01-01.json"
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / name).write_text("{}", encoding="utf-8")
    (tmp_path / name).write_text("{}", encoding="utf-8")
    assert layout.resolve_artifact_path(name, root=tmp_path) == tmp_path / "evidence" / name
    (tmp_path / "evidence" / name).unlink()
    assert layout.resolve_artifact_path(name, root=tmp_path) == tmp_path / name
    with pytest.raises(FileNotFoundError):
        layout.resolve_artifact_path("EVIDENCE_MISSING_2026-01-01.json", root=tmp_path)


def test_legacy_root_artifacts_still_resolve():
    # Root-locked artifact kept at root by the tidy: must keep resolving.
    path = layout.resolve_artifact_path("EVIDENCE_B1_IDENTITY_UNLOCK_2026-07-22.json")
    assert path == REPO / "EVIDENCE_B1_IDENTITY_UNLOCK_2026-07-22.json"
    assert path.is_file()


def test_moved_subdir_artifacts_resolve_via_fallback():
    # Artifact moved to a subdir by the tidy: resolves at the new location.
    path = layout.resolve_artifact_path("PREREG_P1V3V4_L1_CAUSAL_LESSON_2026-07-25.json")
    assert path == REPO / "prereg" / "PREREG_P1V3V4_L1_CAUSAL_LESSON_2026-07-25.json"
    assert path.is_file()


def test_tracked_writers_route_through_helper():
    for script in (
        "_research/efficacy/b2_routing_signal.py",
        "_research/efficacy/e1_conditional_traversal.py",
        "_research/bookscale/c1_prelude_bookscale.py",
    ):
        src = (REPO / script).read_text(encoding="utf-8")
        assert "from hswm.artifacts.layout import default_artifact_path" in src, script
        assert 'default_artifact_path("EVIDENCE_' in src, script


def test_verify_loader_resolves_root_and_subdir(tmp_path):
    from scripts.verify_efficacy_claims import _load

    payload = {"schema_version": "fixture/v1", "value": 1}
    name = "EVIDENCE_FIXTURE_2026-01-01.json"
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    assert _load(tmp_path, name) == payload  # legacy root location
    (tmp_path / name).unlink()
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / name).write_text(json.dumps(payload), encoding="utf-8")
    assert _load(tmp_path, name) == payload  # new subdir location
