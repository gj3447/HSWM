from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v24.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v23.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_TEST_ONLY_HOSTED_PROCESS_CONTINUITY_IMPLEMENTED_"
    "NEXT_SESSION_2026-08-23.md"
)
WORKFLOW_PATH = (
    ROOT / ".github/workflows/s2s-test-only-hosted-process-continuity.yml"
)
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V23_SHA256 = (
    "b32533b0064c916273c36da0b0158a2fbfaab6c42b2e73fa93dda9dfd69f1e1d"
)
WORKSPACE_PARENT = "d18adeeba9dffdf4fcb403c6c9b1f7b42b71cad9"
PRIMARY_IMPLEMENTATION_COMMIT = "9063716116943967143dc647292533a6defa51e7"
ACCEPTED_IMPLEMENTATION_COMMIT = "e729ef240fca3e6f961f5293b9f7667f6468b63e"
FAILED_RUN_ID = 32653755145
ACCEPTED_RUN_ID = 32654010771
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


def test_v24_is_the_unique_v23_successor_and_maps_only_the_pi_delta() -> None:
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
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v24"
    assert payload["workspace_parent_commit"] == WORKSPACE_PARENT
    assert payload["workspace_primary_implementation_commit"] == (
        PRIMARY_IMPLEMENTATION_COMMIT
    )
    assert payload["workspace_code_commit"] == ACCEPTED_IMPLEMENTATION_COMMIT
    assert payload["workspace_documentation_parent"] == ACCEPTED_IMPLEMENTATION_COMMIT
    assert payload["runtime_implementation_changed"] is True
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_FROM_V23_NO_CANONICAL_GRAPH_OR_TOPOLOGY_MUTATION",
        "W": "UNCHANGED_FROM_V23_T16_OPERATOR_REMAINS_PACKAGE_INTERNAL_AND_NOT_COMPOSED_WITH_SCALAR_CREDIT",
        "A": "UNCHANGED_FROM_V23_NO_TOKEN_TRAJECTORY_RECURRENCE_OR_ROUTING",
        "F": "UNCHANGED_NO_LLM_FUNCTION_CELL_TYPED_TOKEN_GENERATION_OR_EFFICACY",
        "Pi": "ADVANCED_TEST_ONLY_HOSTED_SCOPED_EFFECT_ROOT_AUTHENTICATED_IPC_PRIVATE_FILESYSTEM_AND_RUNNER_LIFECYCLE_MECHANICS",
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED_NO_ATTRIBUTED_OUTCOME_CREDIT_ACCEPTED_STATE_TRANSITION_OR_CHANGED_NEXT_BEHAVIOR",
    }


def test_v24_refuses_scalar_t16_conflation_and_keeps_production_closed() -> None:
    payload = _load_handoff()
    composition = payload["scalar_credit_composition"]
    assert composition["existing_scalar_role"] == "OUTCOME_CREDIT_THETA_LIKE_STATE"
    assert composition["t16_role"] == "RECIPIENT_CONDITIONED_FORWARD_OPERATOR_W"
    assert composition["decision"] == "REFUSED_NO_SAFE_COMPOSITION_CONTRACT"
    assert composition["existing_scalar_semantic_weight_reinterpreted"] is False
    assert composition["composition_implemented"] is False
    assert composition["package_root_export_authorized"] is False
    assert composition["python_integer_archive_direct_json_migration_safe"] is False

    assert payload["test_only_hosted_process_continuity_observed"] is True
    for key in (
        "workflow_process_continuity_resolved",
        "workflow_source_frozen",
        "github_origin_established",
        "external_shared_durable_store_feasibility_proved",
        "complete_stage_profile_commit_bridge_implemented",
        "preregistration_created",
        "confirmatory_dispatched",
        "event_10_composed",
        "scientific_verdict_produced",
        "production_assertion_shell_executed",
        "outcome_bound_causal_state_transition_implemented",
        "topology_learning_implemented",
    ):
        assert payload[key] is False

    timing = payload["timing_amendment_candidate"]
    assert timing["production_policy_changed"] is False
    assert timing["hosted_probe_validated_candidate_budgets"] is False
    assert timing["stage_job_timeout_minutes"] == {
        "REGISTER": 75,
        "CONFIRM": 245,
        "ADJUDICATE": 75,
    }
    assert payload["next_session_entrypoint"]["exact_next_gate"] == (
        "SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_V1"
    )


def test_v24_effect_protocol_and_workflow_boundary_are_exact() -> None:
    payload = _load_handoff()
    protocol = payload["test_only_hosted_process_protocol"]
    assert protocol["session_token_bytes"] == 32
    assert protocol["canonical_json_max_encoded_bytes"] == 2048
    assert protocol["attempt_stage_job_binding"] == [
        "1/REGISTER/register",
        "2/CONFIRM/confirm",
        "3/ADJUDICATE/adjudicate",
    ]
    assert protocol["one_effect_acquire_use_release_root_per_stage"] is True
    assert protocol["accepted_reconcile_commit_uninterruptible"] is True
    assert protocol["occurrence_committed_before_terminal_frame"] is True
    assert protocol["raw_token_uploaded_or_logged"] is False
    assert protocol["external_exactly_once_claimed"] is False

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert workflow.count("background: true") == 4
    assert workflow.count('ready_output="$(') == 4
    assert workflow.count("printf '%s\\n' \"$ready_output\" | tee") == 4
    assert workflow.count("wait: register_root") == 1
    assert workflow.count("wait: confirm_root") == 1
    assert workflow.count("wait: adjudicate_root") == 1
    assert workflow.count("cancel: cancelled_root") == 1
    assert "workflow_dispatch:" in workflow
    assert "  push:" not in workflow
    assert "  pull_request:" not in workflow
    assert "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f" in workflow

    package_root = (ROOT / "src/hswm/effect-runtime/src/index.ts").read_text(
        encoding="utf-8"
    )
    assert "s2s-test-only-hosted-process" not in package_root
    assert "s2s-hosted-process-continuity-contract" not in package_root


def test_v24_records_failed_and_accepted_hosted_occurrences_without_overclaim() -> None:
    payload = _load_handoff()
    occurrences = payload["hosted_occurrences"]
    failed = occurrences["failed_diagnostic"]
    assert failed == {
        "run_id": FAILED_RUN_ID,
        "url": f"https://github.com/gj3447/HSWM/actions/runs/{FAILED_RUN_ID}",
        "head_sha": PRIMARY_IMPLEMENTATION_COMMIT,
        "run_attempt": 1,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "conclusion": "cancelled",
        "continuity_job_id": 97229219015,
        "continuity_job_conclusion": "cancelled",
        "cancel_job_id": 97229219133,
        "cancel_job_conclusion": "failure",
        "artifact_count": 0,
        "diagnosis": "TEE_OPENED_ROOT_OWNED_EVIDENCE_PATH_BEFORE_DIRECTORY_CREATION",
        "repair_commit": ACCEPTED_IMPLEMENTATION_COMMIT,
        "accepted_as_feasibility_evidence": False,
    }

    accepted = occurrences["accepted"]
    assert accepted["run_id"] == ACCEPTED_RUN_ID
    assert accepted["head_sha"] == ACCEPTED_IMPLEMENTATION_COMMIT
    assert accepted["conclusion"] == "success"
    assert accepted["run_attempt"] == 1
    assert accepted["event"] == "workflow_dispatch"
    assert accepted["head_branch"] == "main"
    assert accepted["created_at"] == "2026-08-23T17:11:03Z"
    assert accepted["updated_at"] == "2026-08-23T17:11:58Z"
    assert accepted["jobs"] == [
        {
            "job_id": 97229862495,
            "name": "Three local shapes, two uploads, and diagnostics",
            "conclusion": "success",
        },
        {
            "job_id": 97229862414,
            "name": "Explicit runner cancel of the scoped root",
            "conclusion": "success",
            "background_root_step_conclusion": "cancelled",
        },
    ]
    assert accepted["stage_terminals"] == {
        "REGISTER": "RECONCILED_ACTION_SUCCESS",
        "CONFIRM": "RECONCILED_ACTION_FAILURE",
        "ADJUDICATE": "RECONCILED_ACTION_UNKNOWN_NO_RETRY",
    }
    assert accepted["production_authority_claimed"] is False
    assert accepted["production_completion_claimed"] is False
    assert accepted["scientific_result_claimed"] is False
    assert accepted["causal_learning_claimed"] is False


def test_v24_hosted_artifact_metadata_and_readback_are_exact() -> None:
    payload = _load_handoff()
    accepted = payload["hosted_occurrences"]["accepted"]
    artifacts = accepted["artifacts"]
    assert artifacts == [
        {
            "id": 9496963517,
            "name": "hswm-test-only-pc-32654010771-occurrence-evidence",
            "size_in_bytes": 14004,
            "digest": "sha256:814afae4c1fb85bdb3bf0d08204d206c303439c77be00969aca41ed3eb51019c",
            "created_at": "2026-08-23T17:11:56Z",
            "expires_at": "2026-08-24T17:11:55Z",
        },
        {
            "id": 9496963147,
            "name": "hswm-test-only-pc-32654010771-adjudicate-a3",
            "size_in_bytes": 1117,
            "digest": "sha256:9daf389973a27cf4e51c26f84b2352c687e1967ad4190389bb151db18ac65abf",
            "created_at": "2026-08-23T17:11:54Z",
            "expires_at": "2026-08-24T17:11:54Z",
        },
        {
            "id": 9496962072,
            "name": "hswm-test-only-pc-32654010771-register-a1",
            "size_in_bytes": 639,
            "digest": "sha256:d1eca6139a43a24d5aef2d276bed3c0b30b297adb440dfd49aee6a6d32b7c5ac",
            "created_at": "2026-08-23T17:11:50Z",
            "expires_at": "2026-08-24T17:11:49Z",
        },
        {
            "id": 9496957226,
            "name": "hswm-test-only-pc-32654010771-cancel-observation",
            "size_in_bytes": 357,
            "digest": "sha256:6b8c7170cae68b140cd4c8817de8733e94ed3509f994b7934cc7b7fd4e624513",
            "created_at": "2026-08-23T17:11:29Z",
            "expires_at": "2026-08-24T17:11:28Z",
        },
    ]
    readback = accepted["immediate_artifact_readback"]
    assert readback["json_files_parsed"] == 13
    assert readback["raw_token_path_or_text_found"] is False
    assert readback["register_inner_zip_sha256"] == (
        "2d1faaeb6ee046e25f548c3d5f750364aa37e46f95445c2e5a7da1bf1d91a53e"
    )
    assert readback["register_inner_members"] == ["control_receipt.json"]
    assert readback["adjudicate_inner_zip_sha256"] == (
        "1645e61bcc4849bd85231fc75a3c2b5ffa432c5b43d60489903c3a18a8cf9d7a"
    )
    assert readback["adjudicate_inner_members"] == [
        "control_receipt.json",
        "numeric_adjudication.json",
    ]
    assert readback["confirm_hosted_artifact_created"] is False
    assert readback["occurrence_ready_terminal_hashes_match"] is True
    assert readback["ephemeral_download_checked_into_repository"] is False


def test_v24_graph_bindings_indexes_and_verification_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V23_SHA256
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
    assert "EVIDENCE_FOR" not in predicates
    assert {
        "SUPERSEDES_FOR_CONTINUATION",
        "IMPLEMENTS_TEST_ONLY_MECHANICS_OF",
        "OBSERVED_IN_TEST_ONLY_HOSTED_RUN",
        "DOES_NOT_CLOSE",
        "REFUSES_IMPLICIT_COMPOSITION_WITH",
    }.issubset(predicates)

    bindings = payload["artifact_bindings"]
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    for required in (
        str(PREDECESSOR_PATH.relative_to(ROOT)),
        str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        str(WORKFLOW_PATH.relative_to(ROOT)),
        "src/hswm/effect-runtime/src/s2s-hosted-process-continuity-contract.ts",
        "src/hswm/effect-runtime/src/s2s-test-only-hosted-process-protocol.ts",
        "src/hswm/effect-runtime/src/s2s-test-only-hosted-process-root.ts",
        "src/hswm/effect-runtime/src/s2s-test-only-hosted-process-cli.ts",
        "src/hswm/effect-runtime/test/s2s-test-only-hosted-process-root.test.ts",
        "src/hswm/effect-runtime/test/s2s-test-only-hosted-process-workflow.test.ts",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v24.py",
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
        PRIMARY_IMPLEMENTATION_COMMIT,
        ACCEPTED_IMPLEMENTATION_COMMIT,
        str(FAILED_RUN_ID),
        str(ACCEPTED_RUN_ID),
        "34 Vitest files and 415 tests PASS",
        "F1_R8_RESULTS_LOG.md",
        "SWM0W_S2S_PRE_FREEZE_RESOURCE_POLICY_REVIEW_V1",
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
    assert verification["accepted_hosted_run"] == "SUCCESS"
    assert verification["accepted_hosted_jobs"] == "2_OF_2_SUCCESS"
    assert verification["accepted_hosted_artifacts"] == "4_OF_4_PRESENT_AND_READ_BACK"
    assert verification["v24_contract_tests"] == "6_OF_6_PASS"
    assert verification["historical_handoff_chain_tests"] == "123_OF_123_PASS"
    assert verification["historical_handoff_tests_collected"] == 123
    assert verification["kg_contract_tests_close_production_gate"] is False
    assert verification["kg_contract_tests_close_scientific_gate"] is False
