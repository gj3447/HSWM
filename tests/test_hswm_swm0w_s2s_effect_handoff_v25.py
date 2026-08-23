from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v25.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v24.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_DECISION_"
    "NEXT_SESSION_2026-08-23.md"
)
FUTURE_WORKFLOW_PATH = ROOT / ".github/workflows/swm0w-s2s-confirmatory.yml"
FUTURE_PREREG_PATH = ROOT / "prereg/PREREG_SWM0W_S2S_GATE_V1.json"
HISTORICAL_SCALAR_WORKFLOW_PATH = ROOT / ".github/workflows/swm0w-confirmatory.yml"
HISTORICAL_SCALAR_PREREG_PATH = ROOT / "prereg/PREREG_SWM0W_SCALAR_GATE_V1.json"
PILOT_RECEIPT_PATH = (
    ROOT
    / "artifacts/swm0w_s2s/pilot_adoption/32442437970/"
    "pilot_adoption_receipt.json"
)
ADOPTED_CONFIG_PATH = (
    ROOT / "src/hswm/effect-runtime/assets/adopted-protocol-config.json"
)
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V24_SHA256 = (
    "acbbae617b294ff6d335c881bc7d4049ca49b0f1baa64c39cf72b1a02ee7d4a6"
)
WORKSPACE_PARENT = "866b2fbd3fc98311c8a0254124dfc0444758adec"
RUNTIME_CODE_COMMIT = "e729ef240fca3e6f961f5293b9f7667f6468b63e"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
    )
    assert type(payload) is dict
    return payload


def _load_handoff() -> dict[str, object]:
    return _load_json(HANDOFF_PATH)


def _successor_chain(payload: dict[str, object]) -> list[dict[str, object]]:
    candidates = [
        _load_json(path)
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != HANDOFF_PATH
    ]
    by_predecessor: dict[object, list[dict[str, object]]] = {}
    for candidate in candidates:
        predecessor = candidate.get("supersedes_bundle_uid_for_continuation")
        if predecessor is not None:
            by_predecessor.setdefault(predecessor, []).append(candidate)

    chain: list[dict[str, object]] = []
    current_uid = payload["bundle_uid"]
    seen = {current_uid}
    while current_uid in by_predecessor:
        successors = by_predecessor[current_uid]
        assert len(successors) == 1
        successor = successors[0]
        successor_uid = successor["bundle_uid"]
        assert successor_uid not in seen
        chain.append(successor)
        seen.add(successor_uid)
        current_uid = successor_uid
    return chain


def _latest_binding_hashes(payload: dict[str, object]) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for checkpoint in [payload, *_successor_chain(payload)]:
        entries = checkpoint.get("artifact_bindings", [])
        assert type(entries) is list
        for entry in entries:
            assert type(entry) is dict
            path = entry["path"]
            digest = entry["sha256"]
            assert type(path) is str
            assert type(digest) is str
            bindings[path] = digest
    return bindings


def test_v25_is_the_unique_v24_successor_and_maps_only_a_pi_review_delta() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    predecessor = _load_json(PREDECESSOR_PATH)
    payload = _load_handoff()
    successors = [
        _load_json(path)
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != PREDECESSOR_PATH
        and _load_json(path).get("supersedes_bundle_uid_for_continuation")
        == predecessor["bundle_uid"]
    ]
    assert len(successors) == 1
    assert successors[0]["bundle_uid"] == payload["bundle_uid"]
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v25"
    assert payload["workspace_parent_commit"] == WORKSPACE_PARENT
    assert payload["workspace_code_commit"] == RUNTIME_CODE_COMMIT
    assert payload["workspace_documentation_parent"] == WORKSPACE_PARENT
    assert payload["runtime_implementation_changed"] is False
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_NO_CANONICAL_GRAPH_OR_TOPOLOGY_MUTATION",
        "W": "UNCHANGED_T16_OPERATOR_REMAINS_INTERNAL_UNTRAINED_AND_NOT_COMPOSED_WITH_SCALAR_CREDIT",
        "A": "UNCHANGED_NO_TOKEN_TRAJECTORY_RECURRENCE_ROUTING_OR_NEXT_BEHAVIOR",
        "F": "UNCHANGED_NO_LLM_FUNCTION_CELL_OR_EFFICACY_RESULT",
        "Pi": "REVIEW_ONLY_EXACT_75_245_75_BARRED_FROM_PRODUCTION_AND_PREREG_FREEZE_PENDING_CHRONOLOGY_AND_FULL_SCALE_TIMING_EVIDENCE",
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED_NO_ATTRIBUTED_OUTCOME_CREDIT_STATE_TRANSITION_ROLLBACK_OR_CHANGED_NEXT_BEHAVIOR",
    }


def test_v25_rejects_the_exact_candidate_for_freeze_without_rewriting_it() -> None:
    payload = _load_handoff()
    review = payload["resource_policy_review"]
    assert review["gate"] == "SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_V1"
    assert review["decision"] == (
        "REJECT_EXACT_75_245_75_PRODUCTION_FREEZE_REVISE_REQUIRED"
    )
    assert review["arithmetic_status"] == "LOCALLY_VALID_TEST_ONLY"
    assert review["candidate_stage_job_timeout_minutes"] == {
        "REGISTER": 75,
        "CONFIRM": 245,
        "ADJUDICATE": 75,
    }
    assert review["shared_nonpreparation_minutes"] == 55
    assert review["maximum_pulse_lead_minutes"] == 65
    assert review["register_candidate_exceeds_pulse_lead_minutes"] == 10
    assert review["workflow_p95_observed"] is False
    assert review["production_equivalent_twenty_task_profile_observed"] is False
    assert review["candidate_adopted"] is False
    assert review["replacement_policy_selected"] is False
    assert review["production_policy_changed"] is False
    assert review["production_workflow_mutated"] is False
    assert review["protocol_config_changed"] is False

    predecessor = _load_json(PREDECESSOR_PATH)
    old_candidate = predecessor["timing_amendment_candidate"]
    assert old_candidate["stage_job_timeout_minutes"] == (
        review["candidate_stage_job_timeout_minutes"]
    )
    assert old_candidate["production_policy_changed"] is False
    assert old_candidate["hosted_probe_validated_candidate_budgets"] is False


def test_v25_binds_the_disclosed_runtime_and_fixed_budget_claim_boundary() -> None:
    payload = _load_handoff()
    evidence = payload["reviewed_evidence"]
    assert evidence["accepted_pilot_run_id"] == 32442437970
    assert evidence["successful_pilot_workflow_count"] == 1
    assert evidence["github_job_elapsed_seconds"] == 1361
    assert evidence["selected_rate_nine_cell_fit_replay_nanoseconds"] == (
        424_904_259_742
    )
    assert evidence["projected_twenty_task_pre_evaluation_nanoseconds"] == (
        3_069_388_354_600
    )
    assert evidence["post_seed_work_cap_nanoseconds"] == 7_200_000_000_000
    assert evidence["observed_peak_rss_kib"] == 171_108
    assert evidence["selected_t16_draws_reaching_update_cap"] == 2
    assert evidence["selected_t16_draw_count"] == 3
    assert evidence["convergence_claim_allowed"] is False
    assert evidence["fixed_budget_estimator_only"] is True
    assert evidence["pilot_resource_policy_status"] == "PENDING_NOT_CHOSEN"

    receipt = _load_json(PILOT_RECEIPT_PATH)
    runtime = receipt["runtime_telemetry_summary"]
    assert runtime["github_job_elapsed_seconds"] == evidence["github_job_elapsed_seconds"]
    assert runtime["max_peak_rss_kib"] == evidence["observed_peak_rss_kib"]
    assert runtime["prereg_resource_policy_status"] == "PENDING_NOT_CHOSEN"
    assert runtime["selected_rate_stage2"]["fit_and_replay_elapsed_ns_sum"] == (
        evidence["selected_rate_nine_cell_fit_replay_nanoseconds"]
    )

    config = _load_json(ADOPTED_CONFIG_PATH)
    assert config["scientific_status"] == (
        "CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED"
    )
    assert config["task_count"] == 20
    arm_configs = {row["arm"]: row["config"] for row in config["arm_configs"]}
    assert arm_configs["T16"]["max_updates"] == 300
    assert arm_configs["T16"]["patience"] == 50
    assert all(settings["seed"] == 0 for settings in arm_configs.values())


def test_v25_keeps_scalar_history_and_future_s2s_authority_separate() -> None:
    payload = _load_handoff()
    surfaces = payload["policy_surfaces"]
    assert surfaces["typescript_s2s_policy_status"] == (
        "PROVISIONAL_HASH_PINNED_ENGINEERING_NOT_PREREGISTERED"
    )
    assert surfaces["typescript_s2s_job_timeout_minutes"] == {
        "REGISTER": 20,
        "CONFIRM": 210,
        "ADJUDICATE": 30,
    }
    assert surfaces["historical_scalar_workflow_status"] == (
        "IMMUTABLE_DISTINCT_NOT_S2S"
    )
    assert surfaces["future_s2s_workflow_status"] == "ABSENT_SOURCE_SHA_OPEN"
    assert surfaces["future_s2s_preregistration_status"] == "ABSENT"
    assert HISTORICAL_SCALAR_WORKFLOW_PATH.is_file()
    assert HISTORICAL_SCALAR_PREREG_PATH.is_file()
    assert not FUTURE_WORKFLOW_PATH.exists()
    assert not FUTURE_PREREG_PATH.exists()

    for key in (
        "workflow_process_continuity_resolved",
        "workflow_source_frozen",
        "github_origin_established",
        "external_shared_durable_store_feasibility_proved",
        "complete_stage_profile_commit_bridge_implemented",
        "preregistration_created",
        "future_randomness_opened",
        "confirmatory_dispatched",
        "event_10_composed",
        "scientific_verdict_produced",
        "production_assertion_shell_executed",
        "outcome_bound_causal_state_transition_implemented",
        "topology_learning_implemented",
    ):
        assert payload[key] is False


def test_v25_graph_bindings_indexes_and_verification_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V24_SHA256
    )
    nodes = payload["nodes"]
    relations = payload["relations"]
    node_ids = {node["id"] for node in nodes}
    assert len(node_ids) == len(nodes)
    assert all(node["scientific_status"] == "UNJUDGED" for node in nodes)
    for relation in relations:
        assert relation["subject"] in node_ids
        assert relation["object"] in node_ids
    predicates = {relation["predicate"] for relation in relations}
    assert "EVIDENCE_FOR_SCIENTIFIC_EFFICACY" not in predicates
    assert {
        "SUPERSEDES_FOR_CONTINUATION",
        "REJECTS_FOR_PRODUCTION_FREEZE",
        "RETAINS_AS_NON_AUTHORIZING_FIXTURE",
        "REQUIRES_BEFORE_PREREGISTRATION",
        "DOES_NOT_ADVANCE",
    }.issubset(predicates)

    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    for required in (
        str(PREDECESSOR_PATH.relative_to(ROOT)),
        str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "docs/research/HSWM_SWM0W_S2S_GATE_2026-08-20.md",
        "results/SWM0W_S2S_TRAIN_DEV_PILOT_ADOPTION_RESULTS_2026-08-21.md",
        "src/hswm/effect-runtime/src/s2s-confirmatory.ts",
        "src/hswm/effect-runtime/src/s2s-hosted-process-continuity-contract.ts",
        "src/hswm/effect-runtime/src/s2s-workflow-contract.ts",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v24.py",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v25.py",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
    ):
        assert required in paths
    for relative_path, expected in _latest_binding_hashes(payload).items():
        assert SHA256_PATTERN.fullmatch(expected)
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    handoff = HANDOFF_DOC_PATH.read_text(encoding="utf-8")
    for literal in (
        "REJECT_EXACT_75_245_75_PRODUCTION_FREEZE_REVISE_REQUIRED",
        "SWM0W_S2S_RESOURCE_POLICY_CHRONOLOGY_AND_TIMING_PROTOCOL_DESIGN_V1",
        "SWM0W_S2S_DISCLOSED_FULL_SCALE_RESOURCE_PROFILE_V1",
        "F1_R8_RESULTS_LOG.md",
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ):
        assert literal in handoff
    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        index = index_path.read_text(encoding="utf-8")
        assert HANDOFF_PATH.name in index
        assert HANDOFF_DOC_PATH.name in index

    verification = payload["verification"]
    assert verification["effect_runtime_verify"] == "34_FILES_415_TESTS_PASS"
    assert verification["v25_contract_tests"] == "6_OF_6_PASS"
    assert verification["historical_handoff_chain_tests"] == "131_OF_131_PASS"
    assert verification["historical_handoff_tests_collected"] == 131
    assert verification["production_workflow_or_prereg_mutated"] is False
    assert verification["heavy_timing_run_dispatched"] is False
    assert verification["kg_contract_tests_close_production_gate"] is False
    assert verification["kg_contract_tests_close_scientific_gate"] is False


def test_v25_freezes_the_next_design_gate_and_exact_nonclaims() -> None:
    payload = _load_handoff()
    entrypoint = payload["next_session_entrypoint"]
    assert entrypoint["required_skill"] == "effect-ts-functional"
    assert entrypoint["exact_next_gate"] == (
        "SWM0W_S2S_RESOURCE_POLICY_CHRONOLOGY_AND_TIMING_PROTOCOL_DESIGN_V1"
    )
    assert entrypoint["subsequent_evidence_gate"] == (
        "SWM0W_S2S_DISCLOSED_FULL_SCALE_RESOURCE_PROFILE_V1"
    )
    assert entrypoint["future_seed_open_authorized"] is False
    assert entrypoint["preregistration_write_authorized"] is False
    assert entrypoint["production_workflow_mutation_authorized"] is False
    assert entrypoint["heavy_timing_dispatch_authorized_before_design"] is False
    assert payload["protected_user_changes"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = set(payload["nonclaims"])
    assert {
        "NO_REPLACEMENT_RESOURCE_OR_ARCHIVE_POLICY_SELECTED",
        "NO_PRODUCTION_WORKFLOW_SOURCE_PREREGISTRATION_OR_FUTURE_RANDOMNESS",
        "NO_Q_B_R_EVENT10_OR_SCIENTIFIC_VERDICT",
        "NO_OUTCOME_BOUND_CAUSAL_LEARNING_OR_COMPLETE_HSWM",
        "NO_REMOTE_KG_PUBLICATION",
    }.issubset(nonclaims)
