from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.infrastructure import knowledge_map_projection as projection


ROOT = Path(__file__).resolve().parents[1]


def _coverage() -> dict:
    return json.loads((ROOT / projection.COVERAGE).read_text())


def _live() -> dict:
    return json.loads((ROOT / projection.ARTIFACTS / "live-resolution.json").read_text())


def test_snapshot_covers_each_fcl_and_constructive_obligation_without_efficacy_promotion() -> None:
    catalog, bundle = projection.compile_snapshot(ROOT)
    coverage = _coverage()["obligations"]
    assert {row["id"] for row in coverage} == {
        *(f"FCL-{index}" for index in range(1, 9)),
        *(f"CR-{index}" for index in range(8)),
    }
    assert len(coverage) == 16
    assert all(row["efficacy_status"] in {"UNJUDGED", "NOT_AN_EFFICACY_CLAIM"} for row in coverage)
    assert bundle["expected_counts"]["nodes"] > len(catalog["sources"])


def test_coverage_rejects_a_pointer_that_claims_another_existing_uid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coverage = _coverage()
    coverage["obligations"][0]["existing_uid"] = "sym:Concept:not-the-fcl-1-anchor"
    corrupt = tmp_path / "coverage.json"
    corrupt.write_text(json.dumps(coverage), encoding="utf-8")
    monkeypatch.setattr(projection, "COVERAGE", corrupt)
    with pytest.raises(ValueError, match="obligation source pointer UID mismatch"):
        projection.compile_snapshot(ROOT)


def test_historical_retirement_is_not_reclassified_as_a_current_entrypoint() -> None:
    catalog, _ = projection.compile_snapshot(ROOT)
    records = {record["path"]: record for record in catalog["sources"]}
    retired = "ontology/identity/hswm_core/HSWM_CORE_RESPONSIBILITY_ONTOLOGY.v1.json"
    assert records[retired]["navigation_status"] == "RETIRED_TARGET_FORMAT"
    assert records[retired]["navigation_status"] != "CURRENT_ENTRYPOINT"


def test_catalog_uses_git_cut_blob_not_a_worktree_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical = "docs/canon/HSWM_CONSTITUTION_2026-08-20.md"
    pinned = b"pinned historical document, deliberately unlike a worktree file\n"
    assert (ROOT / historical).read_bytes() != pinned
    original_blob = projection.blob

    def pinned_blob(path: str, root: Path = ROOT) -> bytes:
        return pinned if path == historical else original_blob(path, root)

    monkeypatch.setattr(projection, "blob", pinned_blob)
    catalog, _ = projection.compile_snapshot(ROOT)
    record = next(row for row in catalog["sources"] if row["path"] == historical)
    assert record["sha256"] == sha256(pinned).hexdigest()
    assert record["byte_length"] == len(pinned)


def test_only_uniquely_resolved_external_uids_become_anchors() -> None:
    _, bundle = projection.compile_snapshot(ROOT)
    live = _live()
    unresolved = {row["uid"] for row in live["records"] if row["resolution"] != "RESOLVED_UNIQUE"}
    anchors = {row["uid"] for row in bundle["anchors"]}
    assert projection.UID not in anchors
    assert not anchors & unresolved


@pytest.mark.parametrize(
    "resolution,match_case,error",
    [
        ("RESOLVED_UNIQUE", "two", "RESOLVED_UNIQUE requires exactly one identical UID"),
        ("RESOLVED_UNIQUE", "different", "RESOLVED_UNIQUE requires exactly one identical UID"),
        ("UNKNOWN_ENUM", "none", "ambiguous or invalid live identity"),
    ],
    ids=["two-matches", "different-uid", "unknown-resolution"],
)
def test_live_identity_records_fail_closed_on_bad_unique_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resolution: str, match_case: str, error: str
) -> None:
    live = _live()
    bad = live["records"][0]
    uid = bad["uid"]
    matches = {"two": [{"uid": uid}, {"uid": uid}], "different": [{"uid": "sym:Concept:another-node"}], "none": []}[match_case]
    live["records"][0] = {"uid": uid, "resolution": resolution, "matches": matches}
    (tmp_path / "live-resolution.json").write_text(json.dumps(live), encoding="utf-8")
    monkeypatch.setattr(projection, "ARTIFACTS", tmp_path)
    with pytest.raises(ValueError, match=error):
        projection.compile_snapshot(ROOT)


def test_topics_reject_uid_not_present_in_its_fixed_cut_entrypoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    topics = json.loads((ROOT / projection.TOPICS).read_text())
    topics["topics"][0]["existing_uids"].append("sym:Concept:not-in-fixed-cut-entrypoints")
    curated = tmp_path / "topics.json"
    curated.write_text(json.dumps(topics), encoding="utf-8")
    monkeypatch.setattr(projection, "TOPICS", curated)
    with pytest.raises(ValueError, match="topic UID absent from its fixed-cut entrypoints"):
        projection.compile_snapshot(ROOT)
