from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.infrastructure.kg_anchor_revisions import (
    build_bound_anchor_revisions,
    validate_bound_anchor_revisions,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "ontology/identity/hswm_core/HSWM_HYPERGRAPH_LEARNING_PLAN_ONTOLOGY.v1.json"
WORKSHOP = ROOT / "ontology/identity/hswm_core/HSWM_WORKSHOP_C1_C3_ONTOLOGY.v1.json"


class _Result:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def data(self) -> list[dict]:
        return self._rows


class _Tx:
    def __init__(self, nodes: dict[str, dict]) -> None:
        self.nodes = nodes

    def run(self, _query: str, *, uid: str) -> _Result:
        return _Result([] if uid not in self.nodes else [{"uid": uid, "properties": self.nodes[uid]}])


def _write_owner(root: Path, relative: str, *, bundle_uid: str = "sym:AbstractNode:owner", uid: str = "sym:Concept:anchor", modern: bool = True) -> tuple[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"bundle_uid": bundle_uid, "nodes": [{"uid": uid}]}
    if modern:
        payload["artifact_bindings"] = []
    path.write_text(json.dumps(payload))
    return relative, sha256(path.read_bytes()).hexdigest()


def _source(relative: str, digest: str, *, uid: str = "sym:Concept:anchor") -> dict:
    return {
        "anchors": [{"uid": uid, "name": "anchor", "required_labels": ["Concept"]}],
        "artifact_bindings": [{"path": relative, "sha256": digest}],
    }


def test_current_plan_and_workshop_report_bound_and_explicitly_unpinned_anchors() -> None:
    plan = build_bound_anchor_revisions(json.loads(PLAN.read_text()), ROOT)
    workshop = build_bound_anchor_revisions(json.loads(WORKSHOP.read_text()), ROOT)
    assert plan["sym:Concept:hswm"]["pin_status"] == "UNPINNED_NO_BOUND_OWNER"
    assert any(item["pin_status"] == "PINNED_MODERN_RAW_BUNDLE_DIGEST" for item in plan.values())
    assert any(item["pin_status"] == "PINNED_LEGACY_IDENTITY_ONLY" for item in plan.values())
    assert all(item["pin_status"] == "PINNED_MODERN_RAW_BUNDLE_DIGEST" for item in workshop.values())


def test_modern_anchor_current_stale_and_wrong_bundle(tmp_path: Path) -> None:
    relative, digest = _write_owner(tmp_path, "ontology/owner.json")
    data = _source(relative, digest)
    revisions = build_bound_anchor_revisions(data, tmp_path)
    expected = revisions["sym:Concept:anchor"]
    current = {"sym:Concept:anchor": {
        "ontology_bundle_uid": expected["ontology_bundle_uid"],
        "ontology_projection_sha256": expected["ontology_projection_sha256"],
    }}
    report = validate_bound_anchor_revisions(_Tx(current), data, tmp_path)
    assert report["checked_pinned_anchors"] == 1

    stale = {"sym:Concept:anchor": {**current["sym:Concept:anchor"], "ontology_projection_sha256": "0" * 64}}
    with pytest.raises(RuntimeError, match="projection digest drift"):
        validate_bound_anchor_revisions(_Tx(stale), data, tmp_path)
    wrong = {"sym:Concept:anchor": {**current["sym:Concept:anchor"], "ontology_bundle_uid": "sym:AbstractNode:wrong"}}
    with pytest.raises(RuntimeError, match="bundle drift"):
        validate_bound_anchor_revisions(_Tx(wrong), data, tmp_path)


def test_path_traversal_and_fake_digest_fail_before_live_read(tmp_path: Path) -> None:
    data = _source("../outside.json", "0" * 64)
    with pytest.raises(ValueError, match="regular repository file"):
        build_bound_anchor_revisions(data, tmp_path)
    relative, digest = _write_owner(tmp_path, "ontology/owner.json")
    data = _source(relative, "0" * 64)
    with pytest.raises(ValueError, match="hash drift"):
        build_bound_anchor_revisions(data, tmp_path)


def test_unrelated_historical_json_drift_is_not_an_anchor_revision_dependency(tmp_path: Path) -> None:
    relative, digest = _write_owner(tmp_path, "ontology/owner.json")
    context_relative, _context_digest = _write_owner(
        tmp_path, "ontology/context.json", uid="sym:Concept:not-an-anchor"
    )
    data = _source(relative, digest)
    data["artifact_bindings"].append({"path": context_relative, "sha256": "0" * 64})
    revision = build_bound_anchor_revisions(data, tmp_path)["sym:Concept:anchor"]
    assert revision["pin_status"] == "PINNED_MODERN_RAW_BUNDLE_DIGEST"


def test_legacy_and_unknown_legacy_have_explicit_identity_only_or_unpinned_boundary(tmp_path: Path) -> None:
    relative, digest = _write_owner(tmp_path, "ontology/legacy.json", modern=False)
    data = _source(relative, digest)
    expected = build_bound_anchor_revisions(data, tmp_path)["sym:Concept:anchor"]
    assert expected["pin_status"] == "PINNED_LEGACY_IDENTITY_ONLY"
    report = validate_bound_anchor_revisions(_Tx({"sym:Concept:anchor": {
        "ontology_bundle_uid": expected["ontology_bundle_uid"],
        # A legacy publisher need not carry ontology_projection_sha256.
    }}), data, tmp_path)
    assert report["legacy_identity_only_anchors"] == ("sym:Concept:anchor",)

    unknown = {"anchors": data["anchors"]}
    report = validate_bound_anchor_revisions(_Tx({}), unknown, tmp_path)
    assert report["checked_pinned_anchors"] == 0
    assert report["unpinned_anchors"] == ("sym:Concept:anchor",)
