from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v21.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v20.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_ASSERTION_SHELL_IMPLEMENTED_"
    "NEXT_SESSION_2026-08-23.md"
)
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V20_SHA256 = (
    "c020826320d580ae50df18ce86fb928746ecd0556447ad771ff7ced1aecd99b1"
)
CODE_PARENT = "f50d06f4ab86ec74553e774c3846d953e3c3fd28"
IMPLEMENTATION_COMMIT = "0fe779164b13d844428d66f977d22d51054d272f"
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


def test_v21_is_duplicate_key_safe_unique_v20_successor_and_pi_only() -> None:
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

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v21"
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        predecessor["bundle_uid"]
    )
    assert payload["workspace_parent_commit"] == CODE_PARENT
    assert payload["workspace_primary_implementation_commit"] == (
        IMPLEMENTATION_COMMIT
    )
    assert payload["workspace_code_commit"] == IMPLEMENTATION_COMMIT
    assert payload["workspace_documentation_parent"] == IMPLEMENTATION_COMMIT
    assert payload["runtime_implementation_changed"] is True
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_NO_TOPOLOGY_OR_LIVING_HARNESS_EVIDENCE",
        "W": "UNCHANGED_NO_LEARNED_SEMANTIC_WEIGHT_RESULT",
        "A": "UNCHANGED_NO_ACTIVATION_OR_READOUT_RESULT",
        "F": "UNCHANGED_NO_FUNCTION_CELL_OR_SCIENTIFIC_VERDICT",
        "Pi": (
            "ROOT_PRIVATE_ASSERT_RECONCILE_COMPLETION_AND_REPLAY_CODE_"
            "IMPLEMENTED_WITH_TEST_ONLY_NON_AUTHORIZING_EXECUTION"
        ),
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }


def test_v21_source_invariants_match_the_effect_v3_implementation() -> None:
    payload = _load_handoff()
    assertion = (
        ROOT
        / "src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts"
    ).read_text(encoding="utf-8")
    github = (
        ROOT / "src/hswm/effect-runtime/src/s2s-live-github.ts"
    ).read_text(encoding="utf-8")
    postcondition = (
        ROOT
        / "src/hswm/effect-runtime/src/s2s-stage-upload-postcondition.ts"
    ).read_text(encoding="utf-8")
    public_api = (
        ROOT / "src/hswm/effect-runtime/src/index.ts"
    ).read_text(encoding="utf-8")

    for literal in (
        "extends Context.Tag(",
        "readonly assertAndRecover: Effect.Effect<",
        "Layer.scoped(",
        "Effect.acquireRelease(",
        "Effect.acquireUseRelease(",
        "Effect.mapErrorCause(effect, Cause.map(mapFailure))",
        'Object.freeze({ status: "OPEN_UNTIL_TOPOLOGY_FROZEN" })',
        "requireS2SProductionWorkflowSourcePolicy()",
        "buildS2SStageUploadPostconditionFromProductionShell(buildInput)",
        "1_760_000 as const",
        "1_800_000 as const",
    ):
        assert literal in assertion
    assert "Clock.currentTimeMillis" in github
    assert "Date.now()" not in github
    assert "buildS2SStageUploadPostconditionFromProductionShell" in postcondition
    for private_name in (
        "S2SStageUploadAssertion",
        "makeS2SStageUploadAssertionLiveLayer",
        "makeS2SStageUploadAssertionTestLayer",
        "buildS2SStageUploadPostconditionFromProductionShell",
    ):
        assert private_name not in public_api

    implementation = payload["assertion_shell_implementation"]
    assert implementation["selector_free_zero_argument_service"] is True
    assert implementation["effect_v3_layer_scoped"] is True
    assert implementation["exact_layer_claim_required_through_finalize"] is True
    assert implementation["disjoint_production_and_test_registries"] is True
    assert implementation["package_root_exported"] is False
    clock = payload["clock_boundary_audit"]
    assert clock["remaining_direct_date_now_status"] == (
        "CLOSED_EFFECT_CLOCK_REGRESSION_VERIFIED"
    )
    assert clock["native_transport_set_timeout_watchdog_retained"] is True
    assert clock["native_transport_watchdog_is_shell_logical_clock"] is False


def test_v21_closes_the_inherited_matrix_only_for_test_semantics() -> None:
    predecessor = _load_json(PREDECESSOR_PATH)
    payload = _load_handoff()
    required = payload["required_falsification_matrix"]
    results = payload["falsification_matrix_results"]
    assert required == predecessor["required_falsification_matrix"]
    assert type(results) is dict
    assert set(results) == set(required)
    for requirement, result in results.items():
        assert requirement in required
        assert type(result) is dict
        assert result["status"] == "PASS_TEST_ONLY_NON_AUTHORIZING"
        assert result["test_path"].startswith(
            "src/hswm/effect-runtime/test/"
        )
        assert type(result["test_name"]) is str
        assert result["test_name"]
    assert payload["assertion_shell_falsification_gate_closed"] is True
    assert payload["test_only_full_semantics_executed"] is True
    assert payload["production_assertion_shell_executed"] is False

    gate = payload["workflow_process_continuity_gate"]
    assert gate["status"] == "OPEN_BEFORE_WORKFLOW_WIRING"
    assert gate["candidate_selected"] is False
    assert gate["workflow_wiring_authorized"] is False
    assert gate["production_root_executed_with_closed_workflow_source"] is False
    assert gate["evidence_kind"] == (
        "SOURCE_ORDER_PLUS_ZERO_ACCESS_PRODUCTION_WORKFLOW_GATE_AND_"
        "DIRECT_CLOSED_PREMISE_TEST_PROBE"
    )


def test_v21_splits_code_availability_from_production_occurrence() -> None:
    payload = _load_handoff()
    for flag in (
        "production_same_stage_upload_assertion_shell_implemented",
        "production_assertion_completion_capability_implemented",
        "production_upload_assertion_replay_snapshot_implemented",
        "production_assertion_permit_evidence_sealing_implemented",
    ):
        assert payload[flag] is True
    for flag in (
        "production_assertion_shell_executed",
        "genuine_production_assertion_completion_issued",
        "production_replay_snapshot_materialized",
        "production_assertion_permit_evidence_sealed_in_execution",
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


def test_v21_artifact_bindings_verification_handoff_and_indexes_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V20_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    for required in (
        str(PREDECESSOR_PATH.relative_to(ROOT)),
        str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "src/hswm/effect-runtime/src/s2s-live-github.ts",
        "src/hswm/effect-runtime/src/s2s-run-authority.ts",
        "src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts",
        "src/hswm/effect-runtime/src/s2s-stage-upload-postcondition.ts",
        "src/hswm/effect-runtime/test/s2s-live-github.test.ts",
        "src/hswm/effect-runtime/test/s2s-stage-upload-assertion.test.ts",
        "src/hswm/effect-runtime/test/s2s-stage-upload-postcondition.test.ts",
        "src/hswm/effect-runtime/test/support/s2s-three-stage-carrier-inputs.ts",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v21.py",
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
    assert verification["effect_runtime_check"] == "PASS"
    assert verification["typescript_test_files"] == 29
    assert verification["typescript_tests"] == "364/364 PASS"
    assert verification["assertion_shell_tests"] == "36/36 PASS"
    assert verification["effect_runtime_build"] == "PASS"
    assert verification["npm_pack_dry_run_files"] == 223
    assert verification["repository_pytest"] == "2057 passed, 3 skipped"
    assert verification["historical_handoff_chain_tests"] == "105/105 PASS"
    assert verification["typescript_shell_tests_executed"] is True
    assert verification["production_assertion_shell_executed"] is False
    assert verification["live_github_run_executed"] is False
    assert verification["kg_contract_tests_close_runtime_gate"] is False

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    handoff = HANDOFF_DOC_PATH.read_text(encoding="utf-8")
    for literal in (
        CODE_PARENT,
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


def test_v21_resumes_at_process_topology_then_posix_and_one_stage_commit() -> None:
    payload = _load_handoff()
    assert payload["next_session_entrypoint"] == {
        "plan_path": str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "required_skill": "effect-ts-functional",
        "first_action_kind": "REVIEWED_ARCHITECTURE_DECISION_NOT_CODE",
        "first_decision": "WORKFLOW_PROCESS_CONTINUITY_TOPOLOGY",
        "first_code_target": None,
        "workflow_wiring_authorized": False,
        "production_layer_rule": (
            "GATE_CLOSED_WHILE_WORKFLOW_SOURCE_OR_PROCESS_CONTINUITY_IS_OPEN"
        ),
        "next_executable_gate_after_topology": (
            "BOUNDED_SHARED_EXTERNAL_POSIX_FEASIBILITY"
        ),
        "next_program_after_feasibility": (
            "ONE_COMPLETE_STAGE_PROFILE_COMMIT_AND_INDEPENDENT_RECOVERY"
        ),
    }
    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_V16_V19_V20_V21_HANDOFFS_KGS_AND_EFFECT_SKILL"
    )
    assert order[2] == "FREEZE_WORKFLOW_PROCESS_CONTINUITY_BEFORE_WIRING"
    assert order[3] == "DO_NOT_SERIALIZE_OR_RECONSTRUCT_AUTHORITY_ACROSS_STEPS"
    assert order[4] == "KEEP_PRODUCTION_ASSERTION_ROOT_GATE_CLOSED"
    assert order[5] == "RUN_BOUNDED_SHARED_EXTERNAL_POSIX_FEASIBILITY"
    assert order[6] == (
        "IMPLEMENT_ONE_COMPLETE_STAGE_PROFILE_COMMIT_AND_INDEPENDENT_RECOVERY"
    )
    assert order[-1] == (
        "KEEP_WORKFLOW_FREEZE_PREREGISTRATION_DISPATCH_EVENT_10_AND_"
        "SCIENTIFIC_JUDGMENT_DOWNSTREAM"
    )
    assert payload["protected_user_changes"] == [
        {
            "path": "src/hswm/experiments/continual_live.py",
            "included_in_code_checkpoint": False,
            "included_in_v21_documentation_checkpoint": False,
        },
        {
            "path": "tests/test_hswm_continual_live.py",
            "included_in_code_checkpoint": False,
            "included_in_v21_documentation_checkpoint": False,
        },
    ]
