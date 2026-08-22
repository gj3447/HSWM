from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = (
    ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json"
)
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
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


def test_v6_is_an_engineering_checkpoint_not_a_scientific_verdict() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v6"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-observation-authority-implemented-2026-08-22"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringDesignCheckpoint:"
        "hswm-swm0w-s2s-observation-authority-design-2026-08-22"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["implementation_status"] == (
        "OBSERVATION_SLICE_ENGINEERING_CLEAR"
    )
    assert payload["observation_revalidation_status"] == (
        "ENGINEERING_CLEAR_INTERNAL_CONSISTENCY_NOT_ORIGIN"
    )
    assert payload["workflow_runs_for_head_status"] == (
        "ENGINEERING_CLEAR_MULTIPLICITY_PRESERVING"
    )
    assert payload["workflow_source_bytes_status"] == "OPEN"
    assert payload["current_run_authority_status"] == "OPEN"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["workspace_parent_commit"] == (
        "1e620fba8e8eaf147f81a95c0bf05b8553e23d9c"
    )
    assert payload["workspace_code_commit"] == (
        "98f9e7c14933cad4ccccc352e94aeb904f035ade"
    )
    assert payload["future_beacon_selected"] is False
    assert payload["preregistration_created"] is False
    assert payload["confirmatory_dispatched"] is False
    assert payload["candidate_produced"] is False
    assert payload["event_10_composed"] is False
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"

    projection = payload["architecture_projection"]
    assert type(projection) is dict
    assert projection == {
        "H": "TARGET_IDENTITY_UNCHANGED_NO_NEW_COGNITION_EVIDENCE",
        "W": "NO_LEARNED_WEIGHT_RESULT",
        "A": "NO_ACTIVATION_READOUT_EFFICACY_RESULT",
        "F": "NO_CONFIRMATORY_FUNCTION_OR_NUMERIC_RESULT",
        "Pi": (
            "RETAINED_OBSERVATION_INTERNAL_CONSISTENCY_AND_MULTIPLICITY_"
            "PRESERVING_HEAD_QUERY_IMPLEMENTED_GITHUB_ORIGIN_WORKFLOW_"
            "SOURCE_BYTES_AND_CURRENT_RUN_AUTHORITY_OPEN"
        ),
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }

    nodes = payload["nodes"]
    relations = payload["relations"]
    assert type(nodes) is list
    assert type(relations) is list
    assert all(type(node) is dict for node in nodes)
    assert all(type(relation) is dict for relation in relations)
    uids = [node["uid"] for node in nodes]
    assert len(uids) == len(set(uids))
    uid_set = set(uids)
    assert all(relation["from_uid"] in uid_set for relation in relations)
    assert all(relation["to_uid"] in uid_set for relation in relations)
    assert not any(relation["type"] == "EVIDENCE_FOR" for relation in relations)
    assert all(node.get("scientific_status") != "PASS" for node in nodes)
    assert {
        "from_uid": payload["bundle_uid"],
        "type": "SUPERSEDES_FOR_CONTINUATION",
        "to_uid": payload["supersedes_bundle_uid_for_continuation"],
    } in relations
    predecessor = next(
        node
        for node in nodes
        if node["uid"] == payload["supersedes_bundle_uid_for_continuation"]
    )
    assert predecessor["status"] == "SUPERSEDED_FOR_CONTINUATION_ONLY"


def test_v6_revalidation_contract_matches_the_verified_boundary() -> None:
    payload = _load_handoff()
    boundaries = payload["implemented_boundaries"]
    assert type(boundaries) is dict
    validation = boundaries["observation_revalidation"]
    assert type(validation) is dict

    assert validation["status"] == (
        "ENGINEERING_CLEAR_INTERNAL_CONSISTENCY_NOT_ORIGIN"
    )
    assert validation["entrypoints"] == [
        "validateS2SGitHubWorkflowRunObservation",
        "validateS2SGitHubWorkflowAttemptJobsObservation",
        "validateS2SGitHubWorkflowRunsForHeadObservation",
    ]
    assert validation["execution_model"] == (
        "LAZY_EFFECT_WITH_NO_SERVICE_REQUIREMENT"
    )
    assert validation["pure_kernel"] == (
        "POST_SNAPSHOT_RECOMPUTATION_THROUGH_EXISTING_EITHER_CONSTRUCTORS"
    )
    assert validation["jobs_attempt"] == 1
    assert validation["raw_reader_calls_per_execution"] == 1
    assert validation["raw_reader_invocation"] == "DETACHED"
    assert validation["raw_body_max_bytes"] == 8 * 1024 * 1024
    assert validation["shared_backing_policy"] == (
        "REJECT_SAME_AND_CROSS_REALM_SHARED_ARRAY_BUFFER_BY_INTRINSIC_BRAND"
    )
    assert validation["expected_identity_source"] == (
        "INDEPENDENT_VALIDATOR_ARGUMENT"
    )
    assert validation["returns_caller_object"] is False
    assert validation["establishes_github_origin"] is False
    assert validation["universal_proxy_detection_claimed"] is False
    assert validation["self_consistent_fabrication_is_accepted"] is True
    assert validation["error_reasons"] == [
        "INVALID_ARGUMENT",
        "WRAPPER_REJECTED",
        "RECEIPT_REJECTED",
        "RAW_BODY_REJECTED",
        "RAW_BODY_DRIFT",
        "RECOMPUTATION_REJECTED",
        "RECEIPT_SELF_HASH_MISMATCH",
        "RECEIPT_MISMATCH",
    ]


def test_v6_run_roster_preserves_multiplicity_without_granting_authority() -> None:
    payload = _load_handoff()
    boundaries = payload["implemented_boundaries"]
    assert type(boundaries) is dict
    runs = boundaries["workflow_runs_for_head"]
    assert type(runs) is dict

    assert runs["status"] == "ENGINEERING_CLEAR_MULTIPLICITY_PRESERVING"
    assert runs["kind"] == "WORKFLOW_RUNS_FOR_HEAD"
    assert runs["workflow_id"] == "swm0w-s2s-confirmatory.yml"
    assert runs["endpoint_template"] == (
        "/repos/gj3447/HSWM/actions/workflows/"
        "swm0w-s2s-confirmatory.yml/runs?branch=main&event=push&"
        "head_sha=<lowercase-40-hex>&per_page=100"
    )
    assert runs["total_count_rule"] == (
        "total_count === workflow_runs.length <= 100"
    )
    assert runs["accepted_multiplicities"] == [0, 1, "N_UP_TO_100"]
    assert runs["sort_key"] == "RUN_ID_ASCENDING"
    assert runs["duplicate_run_ids"] == "REJECT"
    assert runs["row_identity"] == [
        "REQUESTED_HEAD_SHA",
        "REPOSITORY_GJ3447_HSWM",
        "HEAD_REPOSITORY_GJ3447_HSWM",
    ]
    assert runs["observer_decides_uniqueness"] is False
    assert runs["timestamp_source"] == (
        "Effect.Clock_FOR_ALL_FIVE_JSON_OBSERVATION_LIVE_METHODS"
    )
    assert runs["zip_download_clock_migrated"] is False
    assert runs["workflow_contract_hash_changed"] is False
    assert runs["observed_path_suffix_at_main_accepted"] is True
    assert runs["path_representation_authority_decided"] is False

    versions = payload["frozen_versions"]
    assert type(versions) is dict
    assert versions["workflow_contract_sha256"] == (
        "45e14e0e3d2a0ca0b652c2d39741b264968d4ecdb2d0ff5b74eabd0aa8904050"
    )
    assert versions["workflow_file_sha256_status"] == (
        "OPEN_UNTIL_REVIEWED_WORKFLOW_BYTES_EXIST"
    )


def test_v6_next_slice_remains_fail_closed() -> None:
    payload = _load_handoff()
    authority = payload["remaining_run_authority"]
    assert type(authority) is dict

    assert authority["status"] == "OPEN"
    assert authority["acquisition_bracket"] == [
        "RUN_START",
        "ATTEMPT_ONE_JOBS",
        "WORKFLOW_RUNS_FOR_B",
        "RUN_END",
    ]
    assert authority["requires_exactly_one_run"] is True
    assert authority["requires_distinct_request_ids"] is True
    assert authority["requires_authentic_registration_b"] is True
    assert authority["requires_authentic_current_invocation"] is True
    assert authority["requires_reviewed_workflow_source_binding"] is True
    assert authority["required_production_issuance_policy"] == (
        "FAIL_CLOSED_WHILE_WORKFLOW_SOURCE_BYTES_OPEN"
    )
    assert authority["positive_pre_workflow_test_authority"] == (
        "TEST_ONLY_SEALED_NOT_ROOT_EXPORTED"
    )

    open_gates = payload["open_gates"]
    resolved_gates = payload["resolved_gates"]
    assert type(open_gates) is list
    assert type(resolved_gates) is list
    assert {item["uid"] for item in open_gates} == {
        "sym:Blocker:hswm-s2s-workflow-source-bytes-manifest-binding",
        "sym:Blocker:hswm-s2s-trusted-current-run-observation",
        "sym:Blocker:hswm-s2s-current-run-stage-authority",
        "sym:Blocker:hswm-s2s-stage-specific-artifact-permits",
        "sym:Blocker:hswm-s2s-durable-external-evidence-envelope",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    resolved = {item["uid"]: item["status"] for item in resolved_gates}
    assert resolved[
        "sym:Gate:hswm-s2s-observation-revalidation-internal-consistency"
    ] == (
        "ENGINEERING_CLEAR_INTERNAL_CONSISTENCY_NOT_ORIGIN"
    )


def test_v6_paths_hashes_verification_and_nonclaims_are_exact() -> None:
    payload = _load_handoff()
    latest_bindings = _latest_binding_hashes(payload)
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json" not in paths

    for binding in bindings:
        assert set(binding) == {"path", "role", "sha256"}
        relative = binding["path"]
        expected = binding["sha256"]
        assert type(relative) is str
        assert type(expected) is str
        assert SHA256_PATTERN.fullmatch(expected)
        assert relative == Path(relative).as_posix()
        assert not relative.startswith("/")
        assert ".." not in Path(relative).parts
        path = ROOT / relative
        assert path.is_file()
        assert not path.is_symlink()
        current_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if current_sha256 != expected:
            assert latest_bindings[relative] == current_sha256

    verification = payload["verification"]
    assert type(verification) is dict
    assert verification["effect_tests"] == "179/179 PASS"
    assert verification["effect_test_suites"] == "15/15 PASS"
    assert verification["focused_tests"] == "50/50 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS"
    assert verification["independent_audits"] == (
        "TWO_READ_ONLY_AUDITS_NO_REMAINING_IMPLEMENTATION_BLOCKER"
    )

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert type(nonclaims) is list
    assert any("does not authenticate GitHub origin" in item for item in nonclaims)
    assert any("does not establish unique current-run authority" in item for item in nonclaims)
    assert any("not a preregistration" in item for item in nonclaims)
    assert any("no event-10" in item for item in nonclaims)
