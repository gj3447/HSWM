"""Public evidence checks for the sealed opaque-action identifiability pilot."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = (
    ROOT
    / "results"
    / "raw"
    / "hswm_g1_opaque_identifiability_v2_2026-08-30"
)
PROJECTION = RESULT_DIR / "public_redacted_projection.json"
VERIFICATION = RESULT_DIR / "independent_verification.json"
NARRATIVE = ROOT / "results" / "HSWM_G1_OPAQUE_IDENTIFIABILITY_V2_RESULTS_2026-08-30.md"
EVIDENCE = ROOT / "evidence" / "EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V2_2026-08-30.json"
RESULTS_LOG = ROOT / "F1_R8_RESULTS_LOG.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_artifacts_are_exactly_content_addressed() -> None:
    assert _sha256(PROJECTION) == "afc7e1f56522f276376ef7f331962f737b4ff2eeda1dff10f6ebc3fa35232f65"
    assert PROJECTION.stat().st_size == 12363
    assert _sha256(VERIFICATION) == "fba4b80c6d54a53e58e4e3c75febaeb054a648c6e884623f7d989584357a588b"
    assert VERIFICATION.stat().st_size == 982
    assert _sha256(NARRATIVE) == "642506732b7f83ac7f0d5890098df391b4afe4d6674924cc2dfdb7e246211c62"
    assert NARRATIVE.stat().st_size == 9895
    assert _sha256(EVIDENCE) == "039081ad634787131d2e3c93e4dacca148cbeb2982a1db0842e35598f83b3297"
    assert EVIDENCE.stat().st_size == 6958

    evidence = _load(EVIDENCE)
    for name, path in {
        "narrative": NARRATIVE,
        "redacted_projection": PROJECTION,
        "independent_verification": VERIFICATION,
    }.items():
        descriptor = evidence["public_artifacts"][name]
        assert descriptor["sha256"] == _sha256(path)
        assert descriptor["bytes"] == path.stat().st_size


def test_preregistered_aggregate_decision_is_reproduced() -> None:
    projection = _load(PROJECTION)
    counts = projection["aggregate_result"]["branch_correct_counts"]
    assert counts == {
        "ACTIVE": 8,
        "FORCED_OPPOSITE_FEEDBACK": 0,
        "NO_UPDATE": 4,
        "REMOVE": 4,
        "RESTORE": 8,
    }

    delta_state = (
        (counts["ACTIVE"] + counts["RESTORE"]) / 16
        - (
            counts["FORCED_OPPOSITE_FEEDBACK"]
            + counts["NO_UPDATE"]
            + counts["REMOVE"]
        )
        / 24
    )
    rule = projection["preregistered_identifiability_rule"]
    assert delta_state == projection["aggregate_result"]["delta_state"]
    assert delta_state >= rule["delta_state_min"]
    assert counts["ACTIVE"] == rule["active_correct_required"]
    assert counts["FORCED_OPPOSITE_FEEDBACK"] == rule["forced_opposite_correct_required"]
    assert counts["RESTORE"] == rule["restore_correct_required"]
    assert counts["NO_UPDATE"] <= rule["no_update_correct_max"]
    assert counts["REMOVE"] <= rule["remove_correct_max"]
    assert counts["NO_UPDATE"] + counts["REMOVE"] <= rule["combined_no_state_correct_max"]
    assert rule["all_descriptive_thresholds_observed"] is True
    assert projection["terminal"] == "PILOT_COMPLETE_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE"


def test_public_verification_is_bound_to_execution_projection() -> None:
    projection = _load(PROJECTION)
    verification = _load(VERIFICATION)
    published = projection["independent_local_verification"]

    assert verification["bundle_sha256"] == projection["measurement"]["bundle_canonical_sha256"]
    assert verification["frozen_execution"]["registry_sha256"] == projection["execution"]["consumption_registry_sha256"]
    assert verification["final_runtime"]["receipt_sha256"] == projection["measurement"]["runtime_receipt_record_sha256"]
    assert verification["verification"] == published["overall"]
    assert verification["frozen_execution"]["verification"] == published["protocol_reveal_registry_binding"]
    assert verification["final_runtime"]["verification"] == published["final_runtime_and_restoration_join"]


def test_publication_is_redacted_and_preserves_the_claim_ceiling() -> None:
    public_files = [PROJECTION, VERIFICATION, NARRATIVE, EVIDENCE, RESULTS_LOG]
    public_text = "\n".join(path.read_text(encoding="utf-8") for path in public_files)
    forbidden_literals = (
        "correct_action_code",
        "leakage_canary",
        '"salt"',
        "/home/metahumotonic27",
        "192.168.",
        "container_inspect_json",
        "docker_ps_utf8",
        "gpu_compute_utf8",
        "listeners_utf8",
        "/mnt/hswm",
        "data-01",
    )
    assert all(value not in public_text for value in forbidden_literals)
    assert re.search(r"\bact_[0-9a-f]{8}\b", public_text) is None
    assert re.search(r"\bcue_[0-9a-f]{8}\b", public_text) is None
    assert {path.name for path in RESULT_DIR.iterdir()} == {
        "independent_verification.json",
        "public_redacted_projection.json",
    }

    evidence = _load(EVIDENCE)
    boundary = evidence["claim_boundary"]
    assert boundary["claim_ceiling"] == "EXPLORATORY_G0_IDENTIFIABILITY_ONLY"
    assert boundary["g0"] == "IDENTIFIABILITY_THRESHOLD_OBSERVED_BUT_GATE_NOT_PASSED"
    assert boundary["g1"] == "NOT_EVALUATED"
    assert boundary["causal_learning_efficacy_established"] is False
    assert boundary["reuse_first_comparator_evaluated"] is False
    assert boundary["eight_fcl_laws"] == "NOT_TESTED_OR_CHANGED"
    assert boundary["live_kg_mutated"] is False

    log = RESULTS_LOG.read_text(encoding="utf-8")
    assert "EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V2_2026-08-30.json" in log
    assert "G0 `NOT_PASSED`, G1 `NOT_EVALUATED`" in log
