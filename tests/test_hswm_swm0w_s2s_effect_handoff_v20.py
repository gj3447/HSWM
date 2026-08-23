from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v20.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v19.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_ASSERTION_SHELL_ARCHITECTURE_AUDIT_"
    "NEXT_SESSION_2026-08-23.md"
)
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V19_SHA256 = (
    "3eff0091c5ba7904a837f4aa8b9dc9b5fe6f815e77cd6b821f7542d18e0f90aa"
)
IMPLEMENTATION_COMMIT = "36b4c9bd45796631e1a9c891eb2f32659da5122a"
DOCUMENTATION_PARENT = "9ae8cd22833087491e6f368e6a29795f462eb90b"
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


def test_v20_is_duplicate_key_safe_unique_v19_successor_and_design_only() -> None:
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

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v20"
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        predecessor["bundle_uid"]
    )
    assert payload["workspace_documentation_parent"] == DOCUMENTATION_PARENT
    assert payload["workspace_code_commit"] == IMPLEMENTATION_COMMIT
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["runtime_implementation_changed"] is False
    verification = payload["verification"]
    assert verification["historical_handoff_tests_collected"] == 99
    assert verification["typescript_shell_tests_executed"] is False
    assert verification["kg_contract_tests_close_runtime_gate"] is False
    assert verification[
        "future_runtime_gate_requires_actual_typescript_deferred_test_clock_"
        "interruption_and_layer_recreation_tests"
    ] is True
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_NO_TOPOLOGY_OR_LIVING_HARNESS_EVIDENCE",
        "W": "UNCHANGED_NO_LEARNED_SEMANTIC_WEIGHT_RESULT",
        "A": "UNCHANGED_NO_ACTIVATION_OR_READOUT_RESULT",
        "F": "UNCHANGED_NO_FUNCTION_CELL_OR_SCIENTIFIC_VERDICT",
        "Pi": "UNCHANGED_V19_IMPLEMENTATION_OPEN_SHELL_BOUNDARY_AUDITED_ONLY",
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }


def test_v20_records_process_continuity_as_an_open_prerequisite() -> None:
    payload = _load_handoff()
    gate = payload["workflow_process_continuity_gate"]
    assert gate["status"] == "OPEN_BEFORE_WORKFLOW_WIRING"
    assert gate["code_policy"] == (
        "PRIVATE_PRODUCTION_PROCESS_CONTINUITY_POLICY_"
        "OPEN_UNTIL_TOPOLOGY_FROZEN"
    )
    assert gate["independent_from_workflow_source_policy"] is True
    assert gate[
        "evaluated_before_config_authority_capability_claim_transport_observer_and_io"
    ] is True
    assert gate["conflict"] == (
        "V16_SEPARATE_UPLOAD_STEP_VERSUS_PROCESS_LOCAL_WEAKMAP_BEARERS"
    )
    assert gate["ordinary_step_process_continuity_assumed"] is False
    assert gate["serialized_capability_restores_authority"] is False
    assert gate["allowed_review_candidates"] == [
        "ONE_TRUSTED_LONG_LIVED_PROCESS_AND_EFFECT_ROOT_SCOPE",
        "INDEPENDENTLY_AUTHENTICATED_DETERMINISTIC_POST_ACTION_REACQUISITION",
    ]
    assert gate["candidate_acceptance_requirements"] == {
        "long_lived_process": [
            "REVIEWED_REPLACEMENT_FOR_SEPARATE_PINNED_UPLOAD_STEP_OR_"
            "AUTHENTICATED_IPC",
            "ROOT_REMAINS_ALIVE_THROUGH_UPLOAD_ASSERTION_AND_COMPLETION",
            "PINNED_ACTION_RESULT_INDEPENDENTLY_VERIFIED",
        ],
        "reacquisition": [
            "INDEPENDENT_ROOT_OF_TRUST",
            "DURABLE_ONE_SLOT_CREATE_ONLY_CAS",
            "ANTI_REPLENISHMENT",
            "RESTART_AND_WORKER_REPLAY_RULES",
            "AUTHENTICATED_RAW_INPUT_RECONSTRUCTION",
        ],
    }
    assert gate["determinism_alone_authenticates"] is False
    assert gate["candidate_selected"] is False
    assert gate["workflow_wiring_authorized"] is False

    open_gates = payload["open_gates"]
    assert open_gates[0] == {
        "uid": "sym:OpenGate:s2s-workflow-process-continuity",
        "priority": "BEFORE_WORKFLOW_WIRING",
        "status": "OPEN",
        "required_closure": (
            "FREEZE_REVIEWED_SAME_PROCESS_ROOT_WITH_UPLOAD_STEP_REPLACEMENT_"
            "OR_AUTHENTICATED_IPC_OR_REACQUISITION_WITH_INDEPENDENT_ROOT_OF_"
            "TRUST_DURABLE_ONE_SLOT_CAS_ANTI_REPLENISHMENT_AND_RESTART_WORKER_"
            "REPLAY_RULES"
        ),
    }


def test_v20_freezes_effect_shell_completion_and_timing_contracts() -> None:
    payload = _load_handoff()
    shell = payload["production_assertion_shell_contract"]
    lifecycle = payload["effect_v3_lifecycle"]
    completion = payload["postcondition_and_completion_contract"]

    assert shell["module_target"] == (
        "src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts"
    )
    assert shell["root_layer_constructor_inputs"] == [
        "OPAQUE_PREPARED_CAPABILITY",
        "S2S_GITHUB_LIVE_TRANSPORT_CONFIG",
    ]
    assert shell["service_operation"] == "ZERO_ARGUMENT_ASSERT_AND_RECOVER"
    assert shell["caller_supplied_selectors_or_observer"] is False
    assert shell["observer"] == "INTERNAL_S2S_GITHUB_OBSERVER_LIVE_ONLY"
    assert shell["transport"] == "INTERNAL_S2S_GITHUB_HTTP_TRANSPORT_LIVE_ONLY"
    assert shell["external_observer_or_transport_requirement_exposed"] is False
    assert shell["validated_attempt_ordinals"] == [1, 2, 3]
    assert shell["settle_milliseconds"] == 10_000
    assert shell["maximum_settles"] == 2
    assert shell["effect_retry_allowed"] is False
    assert shell["derived_external_cap_milliseconds"] == 1_760_000
    assert shell["whole_assertion_timeout_milliseconds"] == 1_800_000
    assert shell["whole_assertion_timeout_milliseconds"] > (
        shell["derived_external_cap_milliseconds"]
    )
    assert shell["validation_and_finalization_margin_milliseconds"] == 40_000
    assert shell["success_counts"] == {
        "observer_calls": [8, 10, 12],
        "stored_observations": [7, 9, 11],
        "permit_ledger_entries": [12, 14, 16],
    }

    assert lifecycle == {
        "version": "3.22.1",
        "service": "CONTEXT_TAG_ROOT_PRIVATE",
        "layer": "LAYER_SCOPED",
        "layer_claim": "EFFECT_ACQUIRE_RELEASE",
        "one_use_operation": "EFFECT_ACQUIRE_USE_RELEASE",
        "timeout": "EFFECT_TIMEOUT_FAIL",
        "clock": (
            "SHELL_ONE_EFFECT_CLOCK_WITH_TEST_CLOCK_"
            "TRANSPORT_NATIVE_WATCHDOG_SEPARATE"
        ),
        "finalizer_error_channel": "NEVER",
        "layer_memoization_is_authority": False,
    }

    assert completion["existing_public_builder_remains_test_only"] is True
    assert completion["caller_selectable_trusted_mode"] is False
    assert completion["structural_postcondition_is_authority"] is False
    assert completion["opaque_completion_registry"] == "MODULE_PRIVATE_WEAKMAP"
    assert completion["completion_after_strict_revalidation"] is True
    assert completion["completion_registration_and_spent_success_transition"] == (
        "ONE_MASKED_SUCCESSFUL_RELEASE_PROGRAM_WITH_NO_INTERRUPTIBLE_GAP"
    )
    assert completion["foreign_layer_finalizer_may_close_in_flight_lease"] is False
    assert completion["serialized_or_reconstructed_completion_accepted"] is False
    assert completion["cross_process_replay_prevention_claimed"] is False
    assert completion["external_exactly_once_claimed"] is False

    clock = payload["clock_boundary_audit"]
    assert clock["deadline_model"] == (
        "TWO_TIER_SHELL_EFFECT_CLOCK_AND_INNER_TRANSPORT_WALL_CLOCK_WATCHDOG"
    )
    assert clock["shell_effect_sleep_and_timeout_share_clock"] is True
    assert clock["native_transport_set_timeout_watchdog_retained"] is True
    assert clock["native_transport_watchdog_is_shell_logical_clock"] is False

    assert payload["shell_outcome_mapping"] == {
        "COMPLETE_STRICT_READBACK_AND_POSTCONDITION": (
            "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
        ),
        "THREE_VALID_BRACKETED_ABSENCES": (
            "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION"
        ),
        "DUPLICATE_IDENTITY_RUN_HEAD_REQUERY_EXPIRY_OR_TIME_DRIFT": (
            "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY"
        ),
        "TRANSPORT_DOWNLOAD_PHASE_OR_WHOLE_TIMEOUT_OR_FINAL_RUN_UNKNOWN": (
            "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN"
        ),
        "DEFINITIVE_RECEIPT_SCHEMA_ZIP_DIGEST_MEMBER_OR_POSTCONDITION_REJECTION": (
            "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE"
        ),
        "DEFECT_OR_INTERRUPTION": (
            "PRESERVE_EFFECT_CAUSE_VOID_PERMIT_NO_OUTCOME"
        ),
        "EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH_EMITTABLE_BY_THIS_SHELL": (
            False
        ),
        "COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED_EMITTABLE_BY_THIS_SHELL": (
            False
        ),
    }


def test_v20_keeps_every_production_and_scientific_result_open() -> None:
    payload = _load_handoff()
    for flag in (
        "production_same_stage_upload_assertion_shell_implemented",
        "production_upload_assertion_replay_snapshot_implemented",
        "production_assertion_completion_capability_implemented",
        "production_assertion_permit_evidence_sealed",
        "workflow_process_continuity_resolved",
        "complete_stage_profile_commit_bridge_implemented",
        "external_shared_durable_store_feasibility_proved",
        "genuine_current_run_capability_issued",
        "genuine_prepared_stage_carrier_capability_issued",
        "genuine_stage_upload_assertion_scope_issued",
        "github_origin_established",
        "workflow_source_frozen",
        "preregistration_created",
        "confirmatory_dispatched",
        "event_10_composed",
        "scientific_verdict_produced",
    ):
        assert payload[flag] is False

    nodes = payload["nodes"]
    relations = payload["relations"]
    uids = [node["uid"] for node in nodes]
    assert len(uids) == len(set(uids))
    uid_set = set(uids)
    assert all(relation["from_uid"] in uid_set for relation in relations)
    assert all(relation["to_uid"] in uid_set for relation in relations)
    assert not any(relation["type"] == "EVIDENCE_FOR" for relation in relations)
    assert all(node.get("scientific_status") != "PASS" for node in nodes)


def test_v20_artifact_bindings_handoff_and_indexes_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V19_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    for required in (
        str(PREDECESSOR_PATH.relative_to(ROOT)),
        str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "tests/test_hswm_swm0w_s2s_effect_handoff_v20.py",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
    ):
        assert required in paths

    latest = _latest_binding_hashes(payload)
    for relative_path, expected in latest.items():
        assert SHA256_PATTERN.fullmatch(expected)
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    handoff = HANDOFF_DOC_PATH.read_text(encoding="utf-8")
    for literal in (
        IMPLEMENTATION_COMMIT,
        "Effect `3.22.1`",
        "1,760,000 ms",
        "process-continuity",
        "Never serialize a bearer",
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


def test_v20_next_session_starts_at_process_decision_then_live_shell() -> None:
    payload = _load_handoff()
    assert payload["next_session_entrypoint"] == {
        "plan_path": str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "first_code_target": (
            "src/hswm/effect-runtime/src/s2s-live-github.ts"
        ),
        "primary_code_target": (
            "src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts"
        ),
        "first_test_target": (
            "src/hswm/effect-runtime/test/s2s-stage-upload-assertion.test.ts"
        ),
        "required_skill": "effect-ts-functional",
        "first_decision": "WORKFLOW_PROCESS_CONTINUITY_TOPOLOGY",
        "first_implementation_gate": (
            "ROOT_PRIVATE_PRODUCTION_EFFECT_ASSERTION_RECONCILIATION_SHELL_"
            "COMPLETION_AND_REPLAY"
        ),
        "production_layer_rule": (
            "GATE_CLOSED_WHILE_WORKFLOW_SOURCE_OR_PROCESS_CONTINUITY_IS_OPEN"
        ),
    }
    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_V16_V19_V20_HANDOFFS_AND_KGS_AND_EFFECT_SKILL"
    )
    assert "PRESERVE_THE_TWO_DIRTY_CONTINUAL_LIVE_PATHS" in order
    assert "DO_NOT_SERIALIZE_OR_RECONSTRUCT_AUTHORITY_ACROSS_STEPS" in order
    assert order[-1] == (
        "KEEP_WORKFLOW_FREEZE_PREREGISTRATION_DISPATCH_EVENT_10_AND_"
        "SCIENTIFIC_JUDGMENT_DOWNSTREAM"
    )
