from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from f2_delta_w_credit import PoolShortfall, _validate_declared_cohort


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(root: Path, *, link_external: bool, corrupt: bool = False) -> Path:
    sealed = root / "f2_sealed_universes"
    replay = root / "r3_replay"
    bundled = sealed / "bundled"
    external = replay / "universes" / "external"
    (bundled / "questions").mkdir(parents=True)
    (external / "questions").mkdir(parents=True)
    (bundled / "articles.json").write_text("[]", encoding="utf-8")
    (bundled / "questions" / "type6.json").write_text("[]", encoding="utf-8")
    (external / "articles.json").write_text("[]", encoding="utf-8")
    (external / "questions" / "type6.json").write_text("[]", encoding="utf-8")
    (replay / "manifest.json").write_text("fixture\n", encoding="utf-8")
    if link_external:
        (sealed / "external").symlink_to(external, target_is_directory=True)
    article_hash = _sha256(external / "articles.json")
    if corrupt:
        article_hash = "0" * 64
    manifest = {
        "schema_version": "hswm-f2-sealed-cohort/v1",
        "bundled_universes": ["bundled"],
        "external_universes": [{
            "name": "external",
            "relative_target": "../r3_replay/universes/external",
            "sha256": {
                "articles.json": article_hash,
                "questions/type6.json": _sha256(
                    external / "questions" / "type6.json"
                ),
            },
        }],
        "replay_manifest": {
            "relative_path": "../r3_replay/manifest.json",
            "sha256": _sha256(replay / "manifest.json"),
        },
    }
    (sealed / "COHORT.v1.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return sealed


def test_declared_cohort_refuses_missing_external_hydration(tmp_path: Path) -> None:
    sealed = _write_fixture(tmp_path, link_external=False)
    with pytest.raises(PoolShortfall, match="external universe not hydrated"):
        _validate_declared_cohort(sealed)


def test_declared_cohort_accepts_resolved_content_locked_link(tmp_path: Path) -> None:
    sealed = _write_fixture(tmp_path, link_external=True)
    result = _validate_declared_cohort(sealed)
    assert result["declared_universe_count"] == 2
    assert result["external_universe_count"] == 1
    assert len(result["cohort_manifest_sha256"]) == 64


def test_declared_cohort_refuses_hash_drift(tmp_path: Path) -> None:
    sealed = _write_fixture(tmp_path, link_external=True, corrupt=True)
    with pytest.raises(PoolShortfall, match="hash mismatch"):
        _validate_declared_cohort(sealed)
