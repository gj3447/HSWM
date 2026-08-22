from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = (
    ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json"
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


def _load_handoff() -> dict[str, object]:
    payload = json.loads(
        HANDOFF_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
    )
    assert type(payload) is dict
    return payload


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
    )
    assert type(payload) is dict
    return payload


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


def test_observation_design_handoff_is_closed_and_non_evidentiary() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v5"
    assert payload["bundle_uid"] == (
        "sym:EngineeringDesignCheckpoint:"
        "hswm-swm0w-s2s-observation-authority-design-2026-08-22"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["design_status"] == "FROZEN_SECONDARY_AI_PROPOSED"
    assert payload["implementation_status"] == "OPEN"
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )
    assert payload["effect_skill_application_status"] == (
        "APPLIED_TO_DESIGN_ONLY_NOT_A_RUNTIME_DEPENDENCY"
    )
    assert payload["github_provenance_status"] == (
        "REQUEST_DISTINCT_ENGINEERING_CLEAR"
    )
    assert payload["registration_authority_status"] == (
        "SOURCE_PREREGISTRATION_THROUGH_B_CLEAR"
    )
    assert payload["workflow_contract_status"] == (
        "IDENTITY_AND_STAGE_CONTRACT_V1_ENGINEERING_CLEAR_SOURCE_BYTES_OPEN"
    )
    assert payload["current_invocation_authority_status"] == (
        "ENGINEERING_CLEAR_PROCESS_LOCAL"
    )
    assert payload["observation_revalidation_status"] == (
        "DESIGN_FROZEN_IMPLEMENTATION_OPEN"
    )
    assert payload["workflow_runs_for_head_status"] == (
        "DESIGN_FROZEN_IMPLEMENTATION_OPEN"
    )
    assert payload["current_run_authority_status"] == "OPEN"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["workspace_parent_commit"] == (
        "3c0d3e4cb2e0f8be562f1009ae83fecd742feb99"
    )
    assert payload["workspace_code_commit"] == (
        "5fe203815bdba2b3cdbf6d5d67f739b23c63b084"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-invocation-authority-handoff-2026-08-22"
    )
    assert payload["future_beacon_selected"] is False
    assert payload["preregistration_created"] is False
    assert payload["confirmatory_dispatched"] is False
    assert payload["candidate_produced"] is False
    assert payload["event_10_composed"] is False

    projection = payload["architecture_projection"]
    assert type(projection) is dict
    assert projection == {
        "H": "TARGET_IDENTITY_UNCHANGED_NO_NEW_COGNITION_EVIDENCE",
        "W": "NO_LEARNED_WEIGHT_RESULT",
        "A": "NO_ACTIVATION_READOUT_EFFICACY_RESULT",
        "F": "NO_CONFIRMATORY_FUNCTION_OR_NUMERIC_RESULT",
        "Pi": "OBSERVATION_AUTHORITY_DESIGN_ONLY_IMPLEMENTATION_OPEN",
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
    assert all(
        node["authority_class"]
        in {"USER_PRIMARY", "SECONDARY_AI_PROPOSED", "SYSTEM_DERIVED"}
        for node in nodes
    )

    checkpoint_uid = payload["bundle_uid"]
    predecessor_uid = payload["supersedes_bundle_uid_for_continuation"]
    assert {
        "from_uid": checkpoint_uid,
        "type": "SUPERSEDES_FOR_CONTINUATION",
        "to_uid": predecessor_uid,
    } in relations
    assert {
        "from_uid": checkpoint_uid,
        "type": "SPECIFIES_PART_OF",
        "to_uid": (
            "sym:ArchitectureBoundary:"
            "hswm-swm0w-s2s-ts-control-python-oracle-v1"
        ),
    } in relations
    assert not any(
        relation["from_uid"] == checkpoint_uid
        and relation["type"] == "IMPLEMENTS_PART_OF"
        for relation in relations
    )
    predecessor = next(node for node in nodes if node["uid"] == predecessor_uid)
    assert predecessor["status"] == "SUPERSEDED_FOR_CONTINUATION_ONLY"

    versions = payload["frozen_versions"]
    assert type(versions) is dict
    assert versions == {
        "effect": "3.22.1",
        "typescript": "5.9.3",
        "node": "24.13.0",
        "github_api_selected": "2022-11-28",
        "github_observation_schema": (
            "hswm-swm0w-s2s-github-observation-receipt/v2"
        ),
        "workflow_contract_schema": "hswm-swm0w-s2s-workflow-contract/v1",
        "workflow_contract_sha256": (
            "45e14e0e3d2a0ca0b652c2d39741b264968d4ecdb2d0ff5b74eabd0aa8904050"
        ),
        "workflow_file_sha256_status": (
            "OPEN_UNTIL_REVIEWED_WORKFLOW_BYTES_EXIST"
        ),
    }

    resolved = payload["resolved_gates"]
    audited = payload["audited_design_boundaries"]
    prepared = payload["prepared_boundaries"]
    open_gates = payload["open_gates"]
    assert type(resolved) is list
    assert type(audited) is list
    assert type(prepared) is list
    assert type(open_gates) is list
    assert {item["uid"] for item in resolved} == {
        "sym:Gate:hswm-s2s-request-distinct-github-receipts",
        "sym:Gate:hswm-s2s-registration-b-runtime-authority",
        "sym:Gate:hswm-s2s-workflow-identity-contract-v1",
        "sym:Gate:hswm-s2s-current-invocation-runtime-authority",
    }
    assert all(item["status"] == "ENGINEERING_CLEAR" for item in resolved)
    assert {item["uid"] for item in audited} == {
        "sym:DesignBoundary:hswm-s2s-standalone-observation-revalidation-v1",
        "sym:DesignBoundary:hswm-s2s-workflow-runs-for-head-v1",
    }
    assert all(
        item["status"] == "DESIGN_ONLY_IMPLEMENTATION_OPEN" for item in audited
    )
    assert prepared == [
        {
            "uid": "sym:Boundary:hswm-s2s-registration-workflow-row-inspector",
            "status": "IMPLEMENTED_FAIL_CLOSED_ACTUAL_BINDING_OPEN",
        }
    ]
    assert {item["uid"] for item in open_gates} == {
        "sym:Blocker:hswm-s2s-workflow-source-bytes-manifest-binding",
        "sym:Blocker:hswm-s2s-trusted-current-run-observation",
        "sym:Blocker:hswm-s2s-current-run-stage-authority",
        "sym:Blocker:hswm-s2s-stage-specific-artifact-permits",
        "sym:Blocker:hswm-s2s-durable-external-evidence-envelope",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    assert all(item["severity"] == "P0" for item in open_gates)


def test_observation_revalidation_contract_is_exact() -> None:
    payload = _load_handoff()
    contracts = payload["design_contracts"]
    assert type(contracts) is dict
    validation = contracts["observation_revalidation"]
    assert type(validation) is dict

    assert validation["status"] == "DESIGN_ONLY_IMPLEMENTATION_OPEN"
    assert validation["entrypoints"] == [
        "validateS2SGitHubWorkflowRunObservation",
        "validateS2SGitHubWorkflowAttemptJobsObservation",
        "validateS2SGitHubWorkflowRunsForHeadObservation",
    ]
    assert validation["return_shape"] == (
        "Effect.Effect<TrustedObservation,"
        "S2SGitHubObservationValidationError>"
    )
    assert validation["execution_model"] == (
        "LAZY_EFFECT_WITH_NO_SERVICE_REQUIREMENT"
    )
    assert validation["pure_kernel"] == (
        "POST_SNAPSHOT_RECOMPUTATION_THROUGH_EXISTING_EITHER_CONSTRUCTORS"
    )
    assert validation["jobs_attempt"] == 1
    assert validation["wrapper_exact_keys"] == ["readRawBody", "receipt"]
    assert validation["receipt_exact_keys"] == [
        "apiVersion",
        "endpointPathAndQuery",
        "githubApiVersionSelected",
        "githubRequestId",
        "httpStatus",
        "kind",
        "observedAtUnixSeconds",
        "projection",
        "projectionSha256",
        "rawBodyByteLength",
        "rawBodySha256",
        "receiptSha256",
        "repository",
        "responseEtag",
        "schemaVersion",
    ]
    assert validation["raw_reader_calls"] == 1
    assert validation["raw_body_max_bytes"] == 8 * 1024 * 1024
    assert validation["array_exact_own_keys"] == (
        "INDICES_ZERO_THROUGH_LENGTH_MINUS_ONE_PLUS_"
        "INTRINSIC_NONENUMERABLE_LENGTH"
    )
    assert validation["array_rejects"] == [
        "HOLES",
        "EXTRA_PROPERTIES",
        "SYMBOLS",
        "ACCESSORS",
        "CUSTOM_PROTOTYPES",
    ]
    assert validation["universal_proxy_detection_claimed"] is False
    assert validation["returns_caller_object"] is False
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
    assert validation["establishes_github_origin"] is False
    assert validation[
        "designed_to_establish_internal_byte_receipt_consistency_if_implemented"
    ] is True
    assert "private production composition" in validation["origin_requirement"]


def test_workflow_runs_for_head_and_authority_separation_are_exact() -> None:
    payload = _load_handoff()
    contracts = payload["design_contracts"]
    assert type(contracts) is dict
    runs = contracts["workflow_runs_for_head"]
    authority = contracts["run_authority"]
    assert type(runs) is dict
    assert type(authority) is dict

    assert runs["status"] == "DESIGN_ONLY_IMPLEMENTATION_OPEN"
    assert runs["observation_schema_version"] == (
        "hswm-swm0w-s2s-github-observation-receipt/v2"
    )
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
        "Effect.Clock_FOR_ALL_JSON_OBSERVATION_LIVE_METHODS"
    )
    assert runs["zip_download_clock_migration_in_scope"] is False
    assert runs["workflow_filename_constant"] == (
        "S2S_CONFIRMATORY_WORKFLOW_ID"
    )
    assert runs["workflow_contract_hash_changes"] is False
    assert runs["api_path_representation_status"] == (
        "OPEN_SUFFIXED_AT_MAIN_MUST_NOT_BE_SILENTLY_REJECTED"
    )

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
    assert authority["status"] == "DESIGN_ONLY_IMPLEMENTATION_OPEN"


def test_observation_design_paths_hashes_and_nonclaims_are_exact() -> None:
    payload = _load_handoff()
    latest_bindings = _latest_binding_hashes(payload)
    bindings = payload["artifact_bindings"]
    nodes = payload["nodes"]
    assert type(bindings) is list
    assert type(nodes) is list

    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v5.json" not in paths

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

    for node in nodes:
        for key in ("source_path", "plan_path"):
            if key not in node:
                continue
            relative = node[key]
            assert type(relative) is str
            assert relative == Path(relative).as_posix()
            assert not relative.startswith("/")
            assert ".." not in Path(relative).parts
            path = ROOT / relative
            assert path.is_file()
            assert not path.is_symlink()

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert type(nonclaims) is list
    assert any("not implementation" in item for item in nonclaims)
    assert any("does not authenticate GitHub origin" in item for item in nonclaims)
    assert any("not a preregistration" in item for item in nonclaims)
    assert any("no event-10" in item for item in nonclaims)
