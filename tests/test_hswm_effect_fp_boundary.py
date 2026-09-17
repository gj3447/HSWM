"""Self-contained Effect-boundary projection shape and claim-ceiling checks.

Source replay and live lint checks remain in the companion repository module.
This engineering projection does not prove cognition, learning or efficacy.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from scripts import build_hswm_effect_fp_boundary_ontology as builder


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / builder.ONTOLOGY_PATH


def _load() -> dict:
    return json.loads(ONTOLOGY.read_text(encoding="utf-8"))


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
