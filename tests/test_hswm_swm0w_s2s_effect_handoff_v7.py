from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = (
    ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json"
)
PREDECESSOR_PATH = (
    ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json"
)
SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-run-authority.ts"
ROOT_INDEX_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
PACKAGE_PATH = ROOT / "src/hswm/effect-runtime/package.json"
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


def test_v7_is_a_pi_engineering_checkpoint_not_a_scientific_verdict() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v7"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-current-run-authority-implemented-2026-08-22"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-observation-authority-implemented-2026-08-22"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["design_status"] == "V6_RUN_AUTHORITY_GATE_IMPLEMENTED"
    assert payload["implementation_status"] == (
        "CURRENT_RUN_ACQUISITION_POLICY_SLICE_ENGINEERING_CLEAR_"
        "PRODUCTION_CLOSED"
    )
    assert payload["structural_status"] == "STRUCTURAL_1_6_9_CLEAR"
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )
    assert payload["effect_skill_application_status"] == (
        "APPLIED_TO_IMPLEMENTATION_AND_VERIFICATION_NOT_A_RUNTIME_DEPENDENCY"
    )
    assert payload["github_provenance_status"] == (
        "LIVE_COMPOSITION_IMPLEMENTED_DORMANT_GITHUB_ORIGIN_NOT_OBSERVED"
    )
    assert payload["workflow_source_bytes_status"] == "OPEN"
    assert payload["workflow_api_path_status"] == "OPEN_REVIEW_REQUIRED"
    assert payload["current_run_acquisition_status"] == (
        "ENGINEERING_CLEAR_NONAUTHORIZING_OBSERVER"
    )
    assert payload["current_run_authority_status"] == (
        "IMPLEMENTED_NOT_ISSUED_WORKFLOW_SOURCE_OPEN"
    )
    assert payload["stage_permit_status"] == "OPEN"
    assert payload["durable_evidence_envelope_status"] == "OPEN"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["workspace_parent_commit"] == (
        "6fb5fc394ae034713a60fe1a6e6712e00d919e3b"
    )
    assert payload["workspace_code_commit"] == (
        "dd381f341c08057356ba3e70c83fca33714094b6"
    )
    assert payload["genuine_current_run_capability_issued"] is False
    assert payload["github_origin_established"] is False
    assert payload["future_beacon_selected"] is False
    assert payload["preregistration_created"] is False
    assert payload["confirmatory_dispatched"] is False
    assert payload["candidate_produced"] is False
    assert payload["event_10_composed"] is False
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"

    assert payload["architecture_projection"] == {
        "H": "TARGET_IDENTITY_UNCHANGED_NO_NEW_COGNITION_EVIDENCE",
        "W": "NO_LEARNED_WEIGHT_RESULT",
        "A": "NO_ACTIVATION_READOUT_EFFICACY_RESULT",
        "F": "NO_CONFIRMATORY_FUNCTION_OR_NUMERIC_RESULT",
        "Pi": (
            "AUTHENTIC_INPUT_BOUND_CURRENT_RUN_ACQUISITION_REVALIDATION_"
            "STAGE_POLICY_AND_CLOSED_LAYER_IMPLEMENTED_PRODUCTION_"
            "ISSUANCE_GITHUB_ORIGIN_FINITE_PERMITS_AND_DURABILITY_OPEN"
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


def test_v7_current_run_bracket_and_policy_match_the_implementation() -> None:
    payload = _load_handoff()
    boundaries = payload["implemented_boundaries"]
    assert type(boundaries) is dict
    boundary = boundaries["current_run_acquisition_and_policy"]
    assert type(boundary) is dict

    assert boundary["status"] == (
        "ENGINEERING_CLEAR_SHARED_CORE_NONAUTHORIZING_POSITIVE_PROBE"
    )
    assert boundary["module"] == (
        "src/hswm/effect-runtime/src/s2s-run-authority.ts"
    )
    assert boundary["root_package_exported"] is False
    assert boundary["production_constructor"] == (
        "makeS2SCurrentRunStageAuthorityLiveLayer"
    )
    assert boundary["production_constructor_inputs"] == [
        "AUTHENTIC_REGISTRATION_B_CAPABILITY",
        "GITHUB_LIVE_TRANSPORT_CONFIG",
    ]
    assert boundary["production_layer_environment"] == "never"
    assert boundary["authentic_input_binding"] == [
        "REGISTRATION_SOURCE_A_EQUALS_INVOCATION_PUSH_BEFORE",
        "REGISTRATION_B_EQUALS_INVOCATION_PUSH_AFTER",
        "INVOCATION_COMMIT_EQUALS_WORKFLOW_SOURCE_COMMIT_EQUALS_B",
        "INVOCATION_CONTRACT_SHA256_EQUALS_CHECKED_IN_CONTRACT_SHA256",
    ]
    assert boundary["acquisition_bracket"] == [
        "RUN_START",
        "ATTEMPT_ONE_JOBS",
        "WORKFLOW_RUNS_FOR_B",
        "RUN_END",
    ]
    assert boundary["standalone_revalidation_immediate_after_each_read"] is True
    assert boundary["aggregate_timeout_millis"] == 480_000
    assert boundary["retry_count"] == 0
    assert boundary["parallel_reads"] is False
    assert boundary["interruption_preserved"] is True
    assert boundary["defects_preserved"] is True
    assert boundary["request_id_policy"] == (
        "FOUR_CASE_SENSITIVE_PAIRWISE_DISTINCT"
    )
    assert boundary["timestamp_policy"] == (
        "INVOCATION_CAPTURE_LE_START_LE_JOBS_LE_ROSTER_LE_END"
    )
    assert boundary["roster_policy"] == (
        "EXACTLY_ONE_EXACT_B_ROW_WITH_AUTHENTIC_INVOCATION_RUN_ID"
    )
    assert boundary["identity_stability"] == (
        "FULL_RUN_IDENTITY_START_ROSTER_END"
    )
    assert boundary["direct_run_state"] == (
        "START_AND_END_IN_PROGRESS_WITH_NULL_CONCLUSION"
    )
    assert boundary["roster_state"] == (
        "NONTERMINAL_LAG_ALLOWED_TERMINAL_CONTRADICTION_REJECTED"
    )
    assert boundary["job_policy"] == {
        "exact_fixed_jobs": ["register", "confirm", "adjudicate"],
        "current_job": (
            "AUTHENTIC_INVOCATION_JOB_IN_PROGRESS_NULL_CONCLUSION_"
            "NULL_COMPLETED_AT"
        ),
        "predecessors": "COMPLETED_SUCCESS_ONCE_AND_CHRONOLOGICALLY_ORDERED",
        "later_jobs": "NONTERMINAL_AND_INACTIVE",
        "runner_label_claimed": False,
    }
    assert boundary["workflow_api_path_policy"] == {
        "test_representations": [
            ".github/workflows/swm0w-s2s-confirmatory.yml",
            ".github/workflows/swm0w-s2s-confirmatory.yml@main",
        ],
        "production_representation_decided": False,
    }


def test_v7_capability_claims_and_production_closure_remain_exact() -> None:
    payload = _load_handoff()
    boundary = payload["implemented_boundaries"][
        "current_run_acquisition_and_policy"
    ]
    assert type(boundary) is dict

    evidence = boundary["evidence_claims"]
    assert evidence == {
        "schema_version": "hswm-swm0w-s2s-current-run-stage-evidence/v1",
        "authority_scope": "PROCESS_LOCAL_STAGE_ENTRY",
        "uniqueness_claim": "ROSTER_OBSERVATION_INSTANT_ONLY",
        "historical_uniqueness_claimed": False,
        "cross_execution_replay_prevention_claimed": False,
        "durable_commit_requires_fresh_terminal_observation": True,
    }

    capability = boundary["capability_containment"]
    assert capability == {
        "issuer": "PRIVATE",
        "registry": "MODULE_GLOBAL_WEAKMAP",
        "inspector_requires_exact_issued_object": True,
        "context_tag_alone_is_authority": False,
        "layer_scope_revocation_claimed": False,
        "one_use_spending_claimed": False,
    }

    production = boundary["production_closure"]
    assert production == {
        "workflow_source_policy": "OPEN_UNTIL_WORKFLOW_BYTES_EXIST",
        "invocation_event_file_io_occurs": True,
        "github_observer_constructed": False,
        "github_transport_configured": False,
        "github_calls": 0,
        "genuine_issuer_executed": False,
        "genuine_capability_issued": False,
        "result": "WORKFLOW_SOURCE_BYTES_OPEN",
    }

    probe = boundary["test_probe"]
    assert probe == {
        "name": "probeS2SRunAuthorityAcquisitionForTest",
        "result_type": "Effect<void,S2SCurrentRunError,never>",
        "requires_authentic_registration_and_invocation": True,
        "observer": "CALLER_SUPPLIED_TEST_OBSERVER",
        "uses_shared_acquisition_revalidation_classifier": True,
        "calls_issuer": False,
        "inserts_authority_weakmap": False,
        "returns_candidate_evidence_or_token": False,
        "establishes_github_origin": False,
    }

    threat = boundary["threat_boundary"]
    assert threat["trusted_same_process_runtime_assumed"] is True
    assert threat["ambient_globals_monkeypatch_resistance_claimed"] is False
    assert threat["private_source_import_resistance_claimed"] is False

    open_gate_uids = {item["uid"] for item in payload["open_gates"]}
    assert open_gate_uids == {
        "sym:Blocker:hswm-s2s-workflow-source-bytes-manifest-binding",
        "sym:Blocker:hswm-s2s-workflow-api-path-selection",
        "sym:Blocker:hswm-s2s-current-run-github-origin-and-genuine-issuance",
        "sym:Blocker:hswm-s2s-stage-specific-finite-permits",
        "sym:Blocker:hswm-s2s-terminal-reobservation-and-rerun-invalidation",
        "sym:Blocker:hswm-s2s-durable-external-evidence-envelope",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    resolved_gates = payload["resolved_gates"]
    open_gates = payload["open_gates"]
    assert type(resolved_gates) is list
    assert type(open_gates) is list
    assert len(resolved_gates) == len(
        {item["uid"] for item in resolved_gates}
    )
    assert len(open_gates) == len(open_gate_uids)
    assert {item["uid"] for item in resolved_gates}.isdisjoint(open_gate_uids)
    assert {item["uid"]: item["status"] for item in resolved_gates} == {
        "sym:Gate:hswm-s2s-request-distinct-github-receipts": (
            "ENGINEERING_CLEAR"
        ),
        "sym:Gate:hswm-s2s-registration-b-runtime-authority": (
            "ENGINEERING_CLEAR"
        ),
        "sym:Gate:hswm-s2s-workflow-identity-contract-v1": (
            "ENGINEERING_CLEAR_SOURCE_BYTES_OPEN"
        ),
        "sym:Gate:hswm-s2s-current-invocation-runtime-authority": (
            "ENGINEERING_CLEAR_PROCESS_LOCAL"
        ),
        "sym:Gate:hswm-s2s-observation-revalidation-internal-consistency": (
            "ENGINEERING_CLEAR_INTERNAL_CONSISTENCY_NOT_ORIGIN"
        ),
        "sym:Gate:hswm-s2s-workflow-runs-for-head": (
            "ENGINEERING_CLEAR_MULTIPLICITY_PRESERVING"
        ),
        "sym:Gate:hswm-s2s-current-run-acquisition-policy-mechanics": (
            "ENGINEERING_CLEAR_NONAUTHORIZING_OBSERVER"
        ),
        "sym:Gate:hswm-s2s-current-run-production-layer-containment": (
            "ENGINEERING_CLEAR_DORMANT_WORKFLOW_SOURCE_OPEN"
        ),
    }
    assert {
        item["uid"]: {
            "severity": item["severity"],
            "failure_mode": item["failure_mode"],
        }
        for item in open_gates
    } == {
        "sym:Blocker:hswm-s2s-workflow-source-bytes-manifest-binding": {
            "severity": "P0",
            "failure_mode": (
                "Reviewed workflow bytes, one literal workflow-file hash, "
                "and the matching exact source-A manifest row do not exist."
            ),
        },
        "sym:Blocker:hswm-s2s-workflow-api-path-selection": {
            "severity": "P0",
            "failure_mode": (
                "The production policy has not selected the exact unsuffixed "
                "or at-main workflow API path representation."
            ),
        },
        "sym:Blocker:hswm-s2s-current-run-github-origin-and-genuine-issuance": {
            "severity": "P0",
            "failure_mode": (
                "The pinned Live observer and private issuer are implemented "
                "but have never executed; the positive probe uses a "
                "non-authorizing test observer and proves neither GitHub "
                "origin nor genuine issuance."
            ),
        },
        "sym:Blocker:hswm-s2s-stage-specific-finite-permits": {
            "severity": "P0",
            "failure_mode": (
                "observeRoleArtifact(runId, headSha, role) still accepts "
                "caller-selected identity; no fixed no-identity stage methods "
                "atomically consume finite permits bound to the authentic "
                "stage/current numeric GitHub job ID, and no single ledger "
                "seeded with all four bracket request IDs carries atomically "
                "through permit issuance plus every artifact metadata/"
                "download/readback operation."
            ),
        },
        "sym:Blocker:hswm-s2s-terminal-reobservation-and-rerun-invalidation": {
            "severity": "P0",
            "failure_mode": (
                "No fresh terminal observation contract or rerun invalidation "
                "rule guards a later durable commit."
            ),
        },
        "sym:Blocker:hswm-s2s-durable-external-evidence-envelope": {
            "severity": "P0",
            "failure_mode": (
                "No create-only content-addressed external evidence envelope "
                "stores the complete replay closure or prevents "
                "cross-execution replay."
            ),
        },
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer": {
            "severity": "P0",
            "failure_mode": (
                "No closed stage composition fixes executable entrypoints and "
                "mandatory-upload postconditions before YAML; no independently "
                "reviewed workflow, terminal rerun-safe finalizer, full "
                "failure/VOID review before source freeze, complete VOID "
                "matrix, or event-10 authority exists."
            ),
        },
    }


def test_v7_exact_continuation_retains_permits_ledger_and_workflow_order() -> None:
    payload = _load_handoff()

    assert payload["next_session_order"] == [
        "READ_CONSTITUTION_V7_HANDOFF_V7_KG_IMMUTABLE_V6_AND_EFFECT_SKILL",
        "PRESERVE_PROTECTED_CONTINUAL_LIVE_USER_CHANGES_AND_TREAT_"
        "DD381F3_AS_CODE_CHECKPOINT",
        "REPLACE_CALLER_SELECTED_OBSERVE_ROLE_ARTIFACT_WITH_FIXED_NO_"
        "IDENTITY_STAGE_METHODS_AND_ATOMIC_FINITE_ONE_USE_PERMITS",
        "SEED_ONE_BOUNDED_REQUEST_ID_LEDGER_WITH_ALL_FOUR_BRACKET_IDS_AND_"
        "CARRY_IT_ATOMICALLY_THROUGH_PERMIT_ISSUANCE_AND_EVERY_ARTIFACT_"
        "METADATA_DOWNLOAD_READBACK_REJECTING_REUSE",
        "ADD_CONTENT_ADDRESSED_CREATE_ONLY_DURABLE_ENVELOPE_AND_CLOSED_"
        "REGISTER_CONFIRM_ADJUDICATE_PROGRAMS_FIX_ENTRYPOINTS_AND_"
        "MANDATORY_UPLOAD_POSTCONDITIONS_BEFORE_YAML",
        "AUTHOR_AND_INDEPENDENTLY_REVIEW_EXACT_THREE_JOB_WORKFLOW_AGAINST_"
        "CLOSED_SURFACES_WITHOUT_PREREGISTRATION_THEN_PIN_RAW_SHA_"
        "CONTRACT_DIGEST_SOURCE_A_MANIFEST_ROW_AND_API_PATH_BEFORE_"
        "GENUINE_ISSUANCE",
        "IMPLEMENT_TERMINAL_FINALIZER_WITH_FRESH_LAST_ATTEMPT_ONE_CHECK_"
        "AND_RERUN_INVALIDATION_IMMEDIATELY_BEFORE_CREATE_ONLY_PUBLICATION",
        "INDEPENDENTLY_ADVERSARIALLY_REVIEW_FULL_FAILURE_VOID_MATRIX_"
        "BEFORE_SOURCE_FREEZE_PREREG_BEACON_DISPATCH_OR_EVENT_10",
    ]

    constraints = payload["next_boundary_constraints"]
    assert constraints == {
        "artifact_api": {
            "current": "observeRoleArtifact(runId,headSha,role)",
            "required": "FIXED_NO_IDENTITY_STAGE_SPECIFIC_OPERATIONS",
            "caller_selected_identity_allowed": False,
        },
        "finite_permit": {
            "authority_source": "INSPECTED_GENUINE_CURRENT_RUN_CAPABILITY",
            "binds": ["AUTHENTIC_STAGE", "CURRENT_NUMERIC_GITHUB_JOB_ID"],
            "consumption": "ATOMIC_ONE_USE_WITH_EXPLICIT_PROCESS_SCOPE",
        },
        "request_id_ledger": {
            "seed": "ALL_FOUR_CURRENT_RUN_BRACKET_REQUEST_IDS",
            "shared_scope": [
                "PERMIT_ISSUANCE",
                "ARTIFACT_METADATA",
                "ARTIFACT_DOWNLOAD",
                "ARTIFACT_READBACK",
            ],
            "update": "ATOMIC",
            "reuse": "REJECT",
        },
        "workflow_order": (
            "FIX_CLOSED_STAGE_ENTRYPOINTS_AND_MANDATORY_UPLOAD_"
            "POSTCONDITIONS_BEFORE_AUTHORING_YAML"
        ),
        "activation_order": (
            "INDEPENDENTLY_REVIEW_WORKFLOW_THEN_PIN_RAW_SHA_CONTRACT_"
            "MANIFEST_ROW_AND_API_PATH_BEFORE_GENUINE_ISSUANCE"
        ),
        "final_review": (
            "FULL_FAILURE_VOID_MATRIX_BEFORE_SOURCE_FREEZE_PREREG_"
            "BEACON_DISPATCH_OR_EVENT_10"
        ),
    }

    finite_gate = next(
        item
        for item in payload["open_gates"]
        if item["uid"] == "sym:Blocker:hswm-s2s-stage-specific-finite-permits"
    )
    assert "observeRoleArtifact" in finite_gate["failure_mode"]
    assert "four bracket request IDs" in finite_gate["failure_mode"]
    composition_gate = next(
        item
        for item in payload["open_gates"]
        if item["uid"] == "sym:Blocker:hswm-s2s-composition-workflow-finalizer"
    )
    assert "entrypoints and mandatory-upload postconditions before YAML" in (
        composition_gate["failure_mode"]
    )
    assert "full failure/VOID" in composition_gate["failure_mode"]


def test_v7_source_and_public_surface_preserve_authority_containment() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")
    package = _load_json(PACKAGE_PATH)

    assert source.count("S2S_CURRENT_RUN_STAGE_SNAPSHOTS.set(") == 1
    assert source.index("observeWorkflowRun(runId)") < source.index(
        ".observeWorkflowAttemptJobs("
    )
    assert source.index(".observeWorkflowAttemptJobs(") < source.index(
        ".observeWorkflowRunsForHead("
    )
    assert source.index(".observeWorkflowRunsForHead(") < source.rindex(
        "observeAndRevalidateRun("
    )
    assert "WORKFLOW_SOURCE_BYTES_OPEN" in source

    probe_start = source.index("export const probeS2SRunAuthorityAcquisitionForTest")
    probe_source = source[probe_start:]
    assert ".pipe(Effect.asVoid)" in probe_source
    assert "issueCurrentRunStageAuthority(" not in probe_source
    assert "S2S_CURRENT_RUN_STAGE_SNAPSHOTS.set(" not in probe_source

    for private_name in (
        "S2SCurrentRunStage",
        "inspectS2SCurrentRunStageAuthority",
        "makeS2SCurrentRunStageAuthorityLiveLayer",
        "probeS2SRunAuthorityAcquisitionForTest",
    ):
        assert private_name not in root_index
    assert "s2s-run-authority" not in root_index
    assert package["exports"] == {
        ".": {
            "types": "./dist/index.d.ts",
            "default": "./dist/index.js",
        }
    }


def test_v7_paths_hashes_verification_and_nonclaims_are_exact() -> None:
    payload = _load_handoff()
    latest_bindings = _latest_binding_hashes(payload)
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json" not in paths
    assert {binding["path"]: binding["role"] for binding in bindings} == {
        "docs/operations/HSWM_SWM0W_S2S_RUN_AUTHORITY_IMPLEMENTED_"
        "NEXT_SESSION_2026-08-22.md": (
            "NEXT_SESSION_CURRENT_RUN_AUTHORITY_IMPLEMENTATION_HANDOFF"
        ),
        "ontology/evidence/README.md": "LOCAL_KG_CURRENT_CONTINUATION_INDEX_V7",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md": (
            "TYPESCRIPT_EFFECT_RESEARCH_CONTINUATION_INDEX_V7"
        ),
        "src/hswm/effect-runtime/README.md": (
            "EFFECT_RUNTIME_CURRENT_CONTINUATION_INDEX_V7"
        ),
        "tests/test_hswm_swm0w_s2s_effect_handoff_v7.py": (
            "LOCAL_KG_V7_CLOSURE_REGRESSIONS"
        ),
        "docs/operations/HSWM_SWM0W_S2S_OBSERVATION_AUTHORITY_IMPLEMENTED_"
        "NEXT_SESSION_2026-08-22.md": (
            "IMMUTABLE_V6_IMPLEMENTATION_HANDOFF_PREDECESSOR"
        ),
        "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json": (
            "IMMUTABLE_V6_KG_PREDECESSOR"
        ),
        "src/hswm/effect-runtime/src/s2s-run-authority.ts": (
            "CURRENT_RUN_ACQUISITION_POLICY_AND_CAPABILITY_IMPLEMENTATION"
        ),
        "src/hswm/effect-runtime/test/s2s-run-authority.test.ts": (
            "CURRENT_RUN_HOSTILE_POLICY_AND_CONTAINMENT_REGRESSIONS"
        ),
        "src/hswm/effect-runtime/test/support/s2s-authority-fixtures.ts": (
            "CURRENT_RUN_EXACT_REVIEWED_TEST_FIXTURE_SUPPORT"
        ),
        "src/hswm/effect-runtime/src/s2s-live-github.ts": (
            "BOUND_OBSERVATION_AND_STANDALONE_REVALIDATION_DEPENDENCY"
        ),
        "src/hswm/effect-runtime/src/s2s-invocation.ts": (
            "AUTHENTIC_CURRENT_INVOCATION_INPUT_DEPENDENCY"
        ),
        "src/hswm/effect-runtime/src/s2s-preregistration.ts": (
            "AUTHENTIC_REGISTRATION_B_INPUT_DEPENDENCY"
        ),
        "src/hswm/effect-runtime/src/s2s-workflow-contract.ts": (
            "FIXED_WORKFLOW_IDENTITY_AND_STAGE_POLICY_DEPENDENCY"
        ),
        "src/hswm/effect-runtime/src/index.ts": (
            "ROOT_EXPORT_CONTAINMENT_SURFACE_V7"
        ),
        "src/hswm/effect-runtime/package.json": (
            "EXACT_SINGLE_ROOT_PACKAGE_EXPORT_MAP_V7"
        ),
    }

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
    assert verification["effect_tests"] == "208/208 PASS"
    assert verification["effect_test_suites"] == "16/16 PASS"
    assert verification["focused_current_run_tests"] == "29/29 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS"
    assert verification["independent_audits"] == (
        "THREE_READ_ONLY_AUDITS_NO_REMAINING_BLOCKER_IN_DECLARED_SCOPE"
    )

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert type(nonclaims) is list
    assert any("does not establish GitHub origin" in item for item in nonclaims)
    assert any("no genuine current-run capability" in item for item in nonclaims)
    assert any("not historical or global uniqueness" in item for item in nonclaims)
    assert any("not a preregistration" in item for item in nonclaims)
    assert any("no event-10" in item for item in nonclaims)


def test_v7_predecessor_is_immutable_and_successor_chain_is_unique() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)

    assert predecessor["bundle_uid"] == payload[
        "supersedes_bundle_uid_for_continuation"
    ]
    predecessor_binding = next(
        binding
        for binding in payload["artifact_bindings"]
        if binding["path"]
        == "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v6.json"
    )
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        predecessor_binding["sha256"]
    )
    v6_successors = [
        candidate
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != PREDECESSOR_PATH
        if (
            candidate := _load_json(path)
        ).get("supersedes_bundle_uid_for_continuation")
        == predecessor["bundle_uid"]
    ]
    assert [candidate["bundle_uid"] for candidate in v6_successors] == [
        payload["bundle_uid"]
    ]

    current_path = HANDOFF_PATH
    for successor in _successor_chain(payload):
        successor_bindings = successor["artifact_bindings"]
        assert type(successor_bindings) is list
        binding = next(
            entry
            for entry in successor_bindings
            if entry["path"] == current_path.relative_to(ROOT).as_posix()
        )
        assert binding["sha256"] == hashlib.sha256(
            current_path.read_bytes()
        ).hexdigest()
        version = successor["schema_version"].removeprefix(
            "hswm-engineering-handoff-kg/v"
        )
        assert version.isdigit()
        current_path = HANDOFF_PATH.parent / (
            f"HSWM_SWM0W_S2S_EFFECT_HANDOFF.v{version}.json"
        )
