from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v22.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v21.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0_OCCAM_CORE_AND_S2S_PROCESS_TOPOLOGY_DECISION_"
    "NEXT_SESSION_2026-08-23.md"
)
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V21_SHA256 = (
    "563f6a144841a04684c63f11e40c47f7df07aac33f69f8b499193b41f05a084b"
)
WORKSPACE_PARENT = "dccfca28ae938e1438016adca9398b52f2bcb755"
RUNTIME_CODE_COMMIT = "0fe779164b13d844428d66f977d22d51054d272f"
PINNED_UPLOAD_ACTION = (
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
)
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


def test_v22_is_duplicate_key_safe_unique_v21_successor_and_design_only() -> None:
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

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v22"
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        predecessor["bundle_uid"]
    )
    assert payload["workspace_parent_commit"] == WORKSPACE_PARENT
    assert payload["workspace_code_commit"] == RUNTIME_CODE_COMMIT
    assert payload["workspace_documentation_parent"] == WORKSPACE_PARENT
    assert payload["runtime_implementation_changed"] is False
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_FIRST_TYPESCRIPT_ROLE_AWARE_CORE_TARGET_FROZEN",
        "W": "UNCHANGED_SCALAR_RUNTIME_VERSUS_LEARNED_OPERATOR_GAP_EXPLICIT",
        "A": "UNCHANGED_RECIPIENT_SPECIFIC_TYPESCRIPT_ONE_SWEEP_OPEN",
        "F": "UNCHANGED_NO_FUNCTION_CELL_OR_EFFICACY_RESULT",
        "Pi": "DESIGN_ONLY_EVIDENCE_BRANCH_TOPOLOGY_SELECTED_NOT_IMPLEMENTED",
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }


def test_v22_restores_the_role_aware_typescript_core_to_the_critical_path() -> None:
    payload = _load_handoff()
    audit = payload["critical_path_audit"]
    assert audit["workflow_process_continuity_is_next_occam_core_gate"] is False
    assert audit["workflow_process_continuity_is_evidence_branch_gate"] is True
    assert audit["existing_typescript_H_has_role_bearing_incidences"] is True
    assert audit["existing_typescript_W_is_scalar_score_only"] is True
    assert audit["python_t16_is_role_aware_recipient_conditioned_one_sweep"] is True
    assert audit["canonical_reusable_typescript_H_W_A_conjunction_exists"] is False
    assert audit["next_code_target"] == (
        "src/hswm/effect-runtime/src/swm0-role-aware-core.ts"
    )

    contract = payload["typescript_occam_core_contract"]
    assert contract["model_semantics"] == "FROZEN_PYTHON_T16_PORT_NOT_NEW_MODEL"
    assert contract["scope"] == {
        "hyperedges": 1,
        "roles": 3,
        "members_per_role": 2,
        "input_width": 4,
        "output_width": 2,
        "sweeps": 1,
        "parameters": 870,
    }
    assert contract["parameter_shapes"] == {
        "phi_w": [3, 4, 16],
        "psi_w": [3, 4, 16],
        "unary_w": [3, 2, 16],
        "pair_w": [3, 3, 2, 16],
        "q_w": [3, 2, 16],
        "out_b": [3, 2],
    }
    assert contract["pure_numeric_core"] is True
    assert contract["effect_boundary"] == (
        "STRICT_SCHEMA_IO_TYPED_FAILURE_RESOURCE_AND_COMPOSITION_SHELL"
    )
    assert contract["typescript_training_claimed"] is False
    assert contract["scientific_pass_claimed"] is False
    assert payload["core_falsification_matrix"][0] == (
        "INDEPENDENT_PYTHON_NUMPY_PARITY_MULTIPLE_ARCHIVES_AND_WORLDS"
    )
    assert "NO_RECURRENCE_OPTIMIZER_VERDICT_CREDIT_OR_TOPOLOGY_UPDATE" in (
        payload["core_falsification_matrix"]
    )


def test_v22_selects_background_effect_root_ipc_without_closing_continuity() -> None:
    payload = _load_handoff()
    gate = payload["workflow_process_continuity_gate"]
    assert gate["selected_candidate"] == (
        "BACKGROUND_LONG_LIVED_EFFECT_ROOT_PLUS_AUTHENTICATED_ONE_SHOT_IPC"
    )
    assert gate["candidate_selected"] is True
    assert gate["workflow_process_continuity_resolved"] is False
    assert gate["workflow_wiring_authorized"] is False
    assert gate["production_policy_open"] is True
    assert gate["pinned_upload_action"] == PINNED_UPLOAD_ACTION
    assert gate["preserves_v16_external_action_invariant"] is True
    assert gate["step_sequence"] == [
        "BACKGROUND_ROOT_PREPARE_AND_READY",
        "FOREGROUND_EXACT_PINNED_UPLOAD_ACTION",
        "ALWAYS_RUN_AUTHENTICATED_RECONCILE",
        "ROOT_INDEPENDENT_OBSERVE_VALIDATE_COMPLETE_OR_VOID",
        "EXPLICIT_WAIT_OR_CANCEL_AND_CLEANUP",
    ]
    assert gate["ipc_carries"] == [
        "PROTOCOL_VERSION",
        "ONE_SHOT_NONCE",
        "ROOT_PID_BINDING",
        "RUN_ATTEMPT_STAGE_JOB_BINDING",
        "MONOTONIC_CONTROL_TRANSITION",
    ]
    for forbidden in (
        "BEARER",
        "PERMIT",
        "ARTIFACT_SELECTOR",
        "ARTIFACT_ID",
        "DIGEST",
        "MEMBER_ROSTER",
        "OBSERVER",
        "TRUSTED_CODEC_MODE",
    ):
        assert forbidden in gate["ipc_forbidden"]
    assert gate["action_outputs_used_as_evidence"] is False
    assert gate["blind_upload_retry_authorized"] is False
    assert gate["official_source_evidence_is_hosted_execution_evidence"] is False

    deferred = payload["deterministic_reacquisition_candidate"]
    assert deferred["status"] == "DEFERRED_NOT_REJECTED_IN_PRINCIPLE"
    assert deferred["determinism_alone_authenticates"] is False
    assert deferred["authenticated_durable_root_exists"] is False
    assert deferred["complete_stage_cas_exists"] is False
    assert deferred["independent_current_stage_byte_reconstruction_exists"] is False


def test_v22_records_blocking_contradictions_and_keeps_results_open() -> None:
    payload = _load_handoff()
    contradictions = payload["blocking_contradictions"]
    assert contradictions["whole_assertion_timeout_milliseconds"] == 1_800_000
    assert contradictions["register_job_timeout_milliseconds"] == 1_200_000
    assert contradictions["adjudicate_job_timeout_milliseconds"] == 1_800_000
    assert contradictions["current_timeout_inequality_is_feasible"] is False
    assert contradictions["hosted_background_root_ipc_proved"] is False
    assert contradictions["shared_external_posix_proved"] is False
    assert contradictions["future_s2s_workflow_source_exists"] is False

    for key in (
        "typescript_t16_core_implemented",
        "workflow_process_continuity_resolved",
        "workflow_source_frozen",
        "external_shared_durable_store_feasibility_proved",
        "complete_stage_profile_commit_bridge_implemented",
        "github_origin_established",
        "preregistration_created",
        "confirmatory_dispatched",
        "event_10_composed",
        "scientific_verdict_produced",
    ):
        assert payload[key] is False
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert "NO_COMPLETE_HSWM" in payload["nonclaims"]
    assert "NO_SCIENTIFIC_S2S_PASS" in payload["nonclaims"]


def test_v22_artifact_bindings_handoff_and_indexes_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V21_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    for required in (
        str(PREDECESSOR_PATH.relative_to(ROOT)),
        str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "docs/canon/HSWM_CONSTITUTION_2026-08-20.md",
        "docs/research/HSWM_OCCAM_CORE_2026-08-20.md",
        "src/hswm/effect-runtime/src/contracts.ts",
        "src/hswm/effect-runtime/src/domain.ts",
        "src/hswm/experiments/swm0w_s2s_operator.py",
        "src/hswm/experiments/swm0w_s2s_protocol.py",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v22.py",
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

    verification = payload["verification"]
    assert verification["runtime_implementation_changed"] is False
    assert verification["v22_contract_tests"] == "6/6 PASS"
    assert verification["historical_handoff_chain_tests"] == "111/111 PASS"
    assert verification["historical_handoff_tests_collected"] == 111
    assert verification["three_independent_read_only_audits"] == (
        "PROCESS_SOURCE_REACQUISITION_AND_OCCAM_CRITICAL_PATH_COMPLETE"
    )
    assert verification["kg_contract_tests_close_runtime_gate"] is False
    assert verification["hosted_github_run_executed"] is False

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    handoff = HANDOFF_DOC_PATH.read_text(encoding="utf-8")
    for literal in (
        WORKSPACE_PARENT,
        RUNTIME_CODE_COMMIT,
        PINNED_UPLOAD_ACTION,
        "TypeScript `5.9.3`",
        "Candidate selection is not process-continuity resolution",
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


def test_v22_resumes_at_typescript_core_then_returns_to_the_evidence_branch() -> None:
    payload = _load_handoff()
    assert payload["next_session_entrypoint"] == {
        "plan_path": str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "required_skill": "effect-ts-functional",
        "first_action_kind": "IMPLEMENT_VALIDATED_OCCAM_CORE_SLICE",
        "first_code_target": "src/hswm/effect-runtime/src/swm0-role-aware-core.ts",
        "first_test_target": (
            "src/hswm/effect-runtime/test/swm0-role-aware-core.test.ts"
        ),
        "python_role": "INDEPENDENT_FROZEN_NUMERIC_SOURCE_ORACLE",
        "workflow_wiring_authorized": False,
        "evidence_branch_resume_gate": (
            "TIMING_REPAIR_THEN_HOSTED_BACKGROUND_ROOT_IPC_FEASIBILITY"
        ),
    }
    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_OCCAM_S2S_V16_V20_V21_V22_AND_EFFECT_SKILL"
    )
    assert order[2] == "IMPLEMENT_PURE_TYPESCRIPT_T16_ROLE_AWARE_CORE"
    assert order[3] == "GENERATE_INDEPENDENT_PYTHON_PARITY_FIXTURES"
    assert order[4] == "RUN_HOSTILE_CORE_FALSIFICATION_MATRIX"
    assert order[5] == "KEEP_PRODUCTION_WORKFLOW_AND_PROCESS_GATES_CLOSED"
    assert order[6] == (
        "REVIEW_SCALAR_CREDIT_RUNTIME_COMPOSITION_ONLY_AFTER_CORE_PARITY"
    )
    assert order[-1] == (
        "KEEP_PREREG_RANDOMNESS_DISPATCH_EVENT10_JUDGMENT_SWM1_AND_"
        "CAUSAL_LEARNING_DOWNSTREAM"
    )
    assert payload["protected_user_changes"] == [
        {
            "path": "src/hswm/experiments/continual_live.py",
            "included_in_v22_checkpoint": False,
        },
        {
            "path": "tests/test_hswm_continual_live.py",
            "included_in_v22_checkpoint": False,
        },
    ]
