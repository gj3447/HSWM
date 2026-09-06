"""Effect-runtime functional-boundary projection: determinism, shape, and lint-report freshness.

The bundle is engineering status only.  These tests prove the checked-in
projection is the deterministic build of its bound sources, that its graph
shape obeys the shared invariants, and that the current tree still satisfies the
boundary invariants (zero violations outside the lanes, a shrinking-only
allowlist) without pinning live files to the snapshot's exact counts (SR-5).
They do not prove HSWM cognition, learning, a migration-gate pass, or any
scientific claim.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts import build_hswm_effect_fp_boundary_ontology as builder
from scripts import upsert_hswm_effect_fp_boundary as publisher


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / builder.ONTOLOGY_PATH
RUNTIME = ROOT / "src/hswm/effect-runtime"


def _load() -> dict:
    return json.loads(ONTOLOGY.read_text(encoding="utf-8"))


def test_projection_is_the_deterministic_build_and_validates() -> None:
    data = builder.build_data()
    builder.validate_data(data)
    assert builder.encoded_data(data) == ONTOLOGY.read_bytes()
    assert data == _load()
    publisher.validate_data(data)


def test_bindings_match_the_checked_in_sources() -> None:
    data = _load()
    paths = [row["path"] for row in data["artifact_bindings"]]
    assert paths == [path.as_posix() for path in builder.SOURCE_BINDING_PATHS]
    for row in data["artifact_bindings"]:
        assert row["sha256"] == sha256((ROOT / row["path"]).read_bytes()).hexdigest()


def test_claim_decision_gap_roles_are_closed_and_honest() -> None:
    data = _load()
    nodes = {row["uid"]: row for row in data["nodes"]}
    roles = Counter(row["properties"].get("standard_graph_role") for row in data["nodes"])
    assert roles["CLAIM"] == roles["DECISION"] == 7
    assert roles["GAP"] == 6
    assert roles["QUALIFICATION_RUN"] == 2
    for row in data["nodes"]:
        properties = row["properties"]
        if properties.get("standard_graph_role") == "CLAIM":
            decision = nodes[properties["current_decision_uid"]]
            assert decision["properties"]["assesses_claim_uid"] == row["uid"]
    # The audit dispositions are recorded, not softened by the refactor.
    dispositions = {
        row["properties"]["assesses_claim_uid"].split("gate-claim-")[1].split("-2026")[0]: row["properties"]["evidence_disposition"]
        for row in data["nodes"]
        if row["properties"].get("standard_graph_role") == "DECISION"
    }
    assert dispositions == {
        "mg-1": "UNDERDETERMINED",
        "mg-2": "UNDERDETERMINED",
        "mg-3": "UNDERDETERMINED",
        "mg-4": "RED",
        "mg-5": "RED",
        "mg-6": "RED",
        "loop-ts": "RED",
    }
    assert data["status"].startswith("EFFECT_BOUNDARY_LINT_ENFORCED")
    assert "DECISIVE_LOOP_NOT_IN_TYPESCRIPT" in data["status"]
    assert "G0_NOT_PASSED_G1_LOCKED" in data["status"]


def test_relations_target_known_nodes_and_anchors() -> None:
    data = _load()
    owned = {row["uid"] for row in data["nodes"]}
    anchors = {row["uid"] for row in data["anchors"]}
    for row in data["relations"]:
        assert row["from_uid"] in owned
        assert row["to_uid"] in owned | anchors
    # Every package closes or narrows at least one gap, and every gap is touched.
    touched = {row["to_uid"] for row in data["relations"] if row["type"] in {"CLOSES", "NARROWS"} and "fp-gap" in row["to_uid"]}
    assert touched == {builder.gap_uid(gap["id"]) for gap in builder.FP_GAPS}


def test_bound_lint_report_is_internally_consistent() -> None:
    """The checked-in report is the snapshot the bundle binds; it must be self-consistent."""

    report = builder.load_lint_report()
    assert report["violations"] == 0
    assert report["stale_allowlist_entries"] == 0
    assert set(report["allowlist"]) == set(report["lanes"] and {f for files in report["lanes"].values() for f in files})
    for name, entry in report["allowlist"].items():
        assert entry["lane"] in report["lanes"]
        for rule in entry["rules"]:
            assert report["per_file"][name][rule] > 0, (name, rule)


def test_current_tree_still_satisfies_the_boundary_invariants() -> None:
    """Invariants only (SR-5): the live tree is not pinned to the snapshot's exact counts.

    The lint must report zero violations outside the lanes and no stale allowlist
    entries; the allowlist may only shrink relative to the bound snapshot.
    """

    snapshot = builder.load_lint_report()
    allowlist = builder.load_allowlist()
    assert set(allowlist["files"]) <= set(snapshot["allowlist"]), "the allowlist may only shrink"
    for name, entry in allowlist["files"].items():
        assert entry["lane"] in allowlist["lanes"]
        assert set(entry["rules"]) <= set(snapshot["allowlist"][name]["rules"]), name
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available; the lint runs in npm run check in the TypeScript CI lane")
    fresh = json.loads(
        subprocess.run(
            [node, "scripts/lint-effect-boundary.mjs", "--json"],
            cwd=RUNTIME,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    )
    assert fresh["violations"] == 0, "Effect boundary violated outside the exemption lanes"
    assert fresh["stale_allowlist_entries"] == 0, "allowlist carries a stale entry; drop it"
