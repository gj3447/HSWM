"""Content addressing and rule reproduction for the opaque v3 and v4 (G0-local) 2026-09-06 publications.

The public artifacts are retained records; their digests are pinned here.  The
aggregate decision is recomputed from the projection with the frozen rule so a
later reader can see exactly which clause failed.  Nothing here changes the
sealed terminal or promotes any scientific status.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from hswm.experiments import g1_opaque_v3


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results/raw/hswm_g1_opaque_identifiability_v3_2026-09-06"
NARRATIVE = ROOT / "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_2026-09-06.md"
PROJECTION = RAW / "public_redacted_projection.json"
VERIFICATION = RAW / "independent_verification.json"
EVIDENCE = ROOT / "evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_2026-09-06.json"
PINS = {
    "narrative": ("1c47b38daa48ad82cba8161babc1317829576a1bebc82ff2b6ea03b7c1a11519", 8147),
    "projection": ("bc099425d89dc606b65e257a08d7df52448f706c607a6e413c07ec575d7d0c69", 9271),
    "verification": ("b0d6f31818695bbf70ea99329d381663b9478d767209f9adb713934bb7c37eef", 1850),
    "evidence": ("91607907093c7621d7b2a4191cfe9df25cd5ad6866f1cdc057c73022855a0a9a", 8713),
}


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_public_artifacts_are_exactly_content_addressed() -> None:
    for name, path in (("narrative", NARRATIVE), ("projection", PROJECTION), ("verification", VERIFICATION), ("evidence", EVIDENCE)):
        digest, size = PINS[name]
        assert _sha(path) == digest, name
        assert path.stat().st_size == size, name
    evidence = json.loads(EVIDENCE.read_bytes())
    for name, path in (("narrative", NARRATIVE), ("redacted_projection", PROJECTION), ("independent_verification", VERIFICATION)):
        descriptor = evidence["public_artifacts"][name]
        assert descriptor["sha256"] == _sha(path) and descriptor["bytes"] == path.stat().st_size


def test_frozen_rule_reproduces_the_sealed_terminal_and_names_the_failing_clause() -> None:
    projection = json.loads(PROJECTION.read_bytes())
    result = projection["aggregate_result"]
    rule = projection["preregistered_identifiability_rule"]
    assert rule == g1_opaque_v3.IDENTIFIABILITY_RULE
    counts = result["branch_correct"]
    assert counts == {"ACTIVE": 32, "FORCED_OPPOSITE_FEEDBACK": 0, "NO_UPDATE": 16, "OUTCOME_INDEPENDENT_SHAM": 20, "REMOVE": 16, "RESTORE": 32}
    by_position = result["no_state_correct_by_position"]
    clauses = {
        "active": counts["ACTIVE"] >= rule["active_correct_min"],
        "restore": counts["RESTORE"] >= rule["restore_correct_min"],
        "forced_opposite": counts["FORCED_OPPOSITE_FEEDBACK"] <= rule["forced_opposite_correct_max"],
        "sham": counts["OUTCOME_INDEPENDENT_SHAM"] <= rule["outcome_independent_sham_correct_max"],
        "no_update": counts["NO_UPDATE"] <= rule["no_update_correct_max"],
        "remove": counts["REMOVE"] <= rule["remove_correct_max"],
        "per_stratum_ceiling": all(by_position[arm][pos] <= rule["no_state_arm_per_position_stratum_correct_max"] for arm in by_position for pos in ("1", "2")),
        "delta_state": result["delta_state"] >= rule["delta_state_min"],
        "remove_restore": result["exact_remove_and_restore_count"] == rule["exact_remove_and_restore"],
        "admissions": result["credit_and_admission"] == {"ACTIVE": 32, "FORCED_OPPOSITE_FEEDBACK": 32, "OUTCOME_INDEPENDENT_SHAM": 32},
        "permit_commits": result["atom_v2_permit_commits"] == rule["atom_v2_permit_commits"],
        "position_balance": result["correct_position_balance_stateful"] == rule["correct_position_balance"],
    }
    failing = sorted(name for name, ok in clauses.items() if not ok)
    assert failing == ["per_stratum_ceiling"]
    assert by_position["NO_UPDATE"] == {"1": 16, "2": 0} and by_position["REMOVE"] == {"1": 16, "2": 0}
    assert result["g0_local_identifiability_observed"] is False
    assert result["terminal"] == projection["terminal"] == "V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE"
    assert projection["claim_ceiling"] == "INSTRUMENT_VALIDATION_ONLY"
    assert projection["claim_boundary"]["g1"] == "NOT_EVALUATED" and projection["claim_boundary"]["live_kg_mutated"] is False


def test_publication_is_redacted_and_records_the_void_attempt() -> None:
    text = PROJECTION.read_text(encoding="utf-8") + EVIDENCE.read_text(encoding="utf-8")
    # Secret-bearing keys of the private bundle and reveal must not appear as JSON keys.
    for forbidden in ('"salt":', '"leakage_canary":', '"correct_action_code":', '"messages":', '"raw_request_json":', '"raw_response_json":', '"private_key":', '"token_ids":'):
        assert forbidden not in text, forbidden
    projection = json.loads(PROJECTION.read_bytes())
    aborted = projection["execution"]["aborted_attempts_same_family"]
    assert len(aborted) == 1 and aborted[0]["terminal"] == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    assert projection["custody"]["evaluator_separate_os_user_episodes"] == 32
    assert projection["custody"]["evaluator_ledger_readable_by_actor"] is False
    assert projection["custody"]["actor_holds_passwordless_sudo"] is True


RAW_V4 = ROOT / "results/raw/hswm_g1_opaque_identifiability_v4_2026-09-06"
NARRATIVE_V4 = ROOT / "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V4_RESULTS_2026-09-06.md"
EVIDENCE_V4 = ROOT / "evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V4_2026-09-06.json"
PINS_V4 = {
    "narrative": ("05b6fc9073a4d0280557ca4562402133810367caf41d0f7ad37cd818aa47b4f3", 4717),
    "projection": ("b1264019383ed67fc2f97ce1bff721cee1ca6be8d7c42e0a88753bccf4e910cc", 8782),
    "verification": ("77889993315bb924f5b21c33c9214191d06cec617580135c6da8314517979fb6", 1850),
    "evidence": ("2b73a944a8419206ab5656fce5bd75080125cd7f310e16db82da704b091928ce", 8252),
}


def test_v4_public_artifacts_are_content_addressed_and_the_control_clause_is_the_only_failure() -> None:
    for name, path in (("narrative", NARRATIVE_V4), ("projection", RAW_V4 / "public_redacted_projection.json"), ("verification", RAW_V4 / "independent_verification.json"), ("evidence", EVIDENCE_V4)):
        digest, size = PINS_V4[name]
        assert _sha(path) == digest and path.stat().st_size == size, name
    projection = json.loads((RAW_V4 / "public_redacted_projection.json").read_bytes())
    assert projection["preregistration"]["path"].endswith("g1_opaque_identifiability_v4_2026-09-06/protocol.v1.json")
    result = projection["aggregate_result"]
    assert result["branch_correct"] == {"ACTIVE": 32, "FORCED_OPPOSITE_FEEDBACK": 0, "NO_UPDATE": 16, "OUTCOME_INDEPENDENT_SHAM": 14, "REMOVE": 16, "RESTORE": 32}
    assert result["no_state_correct_by_position"]["NO_UPDATE"] == {"1": 16, "2": 0}
    assert result["no_state_correct_by_position"]["REMOVE"] == {"1": 16, "2": 0}
    assert result["delta_state"] >= 0.5 and result["g0_local_identifiability_observed"] is False
    assert projection["terminal"] == "V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE"
    assert projection["execution"]["aborted_attempts_same_family"] == []
