from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json"
PERMIT_SOURCE_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-stage-artifact-permits.ts"
)
ARTIFACT_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-live-artifact.ts"
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


def test_v8_is_a_pi_engineering_checkpoint_not_a_scientific_verdict() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v8"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-stage-artifact-permits-implemented-2026-08-22"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-current-run-authority-implemented-2026-08-22"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["design_status"] == (
        "V7_STAGE_ARTIFACT_FINITE_PERMIT_GATE_IMPLEMENTED"
    )
    assert payload["implementation_status"] == (
        "STAGE_ARTIFACT_FINITE_PERMIT_LEDGER_SLICE_ENGINEERING_CLEAR_"
        "PRODUCTION_DORMANT"
    )
    assert payload["structural_status"] == "STRUCTURAL_1_6_9_CLEAR"
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )
    assert payload["effect_skill_application_status"] == (
        "APPLIED_TO_IMPLEMENTATION_AND_VERIFICATION_NOT_A_RUNTIME_DEPENDENCY"
    )
    assert payload["stage_permit_status"] == (
        "ENGINEERING_CLEAR_PROCESS_SLOT_SCOPED_PRODUCTION_DORMANT"
    )
    assert payload["workflow_source_bytes_status"] == "OPEN"
    assert payload["workflow_api_path_status"] == "OPEN_REVIEW_REQUIRED"
    assert payload["durable_evidence_envelope_status"] == "OPEN"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["workspace_parent_commit"] == (
        "9572be15b343a96ef8959e76b27d69b29ff0f91f"
    )
    assert payload["workspace_code_commit"] == (
        "01b96ae8080ef9e19100d4a2bd781192498136e4"
    )
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    for flag in (
        "genuine_current_run_capability_issued",
        "genuine_stage_artifact_capability_issued",
        "github_origin_established",
        "future_beacon_selected",
        "preregistration_created",
        "confirmatory_dispatched",
        "candidate_produced",
        "event_10_composed",
    ):
        assert payload[flag] is False

    assert payload["architecture_projection"] == {
        "H": "TARGET_IDENTITY_UNCHANGED_NO_NEW_COGNITION_EVIDENCE",
        "W": "NO_LEARNED_WEIGHT_RESULT",
        "A": "NO_ACTIVATION_READOUT_EFFICACY_RESULT",
        "F": "NO_CONFIRMATORY_FUNCTION_OR_NUMERIC_RESULT",
        "Pi": (
            "FIXED_STAGE_ARTIFACT_EFFECTS_AUTHORITY_DERIVED_FINITE_PERMITS_"
            "ATOMIC_BOUNDED_LEDGER_FRESH_REVALIDATION_AND_CLOSED_LAYER_"
            "IMPLEMENTED_PRODUCTION_DORMANT_DURABILITY_OPEN"
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


def test_v8_fixed_surface_permits_and_ledger_match_the_implementation() -> None:
    payload = _load_handoff()
    boundaries = payload["implemented_boundaries"]
    assert type(boundaries) is dict
    boundary = boundaries["stage_artifact_finite_permits"]
    assert type(boundary) is dict

    assert boundary["status"] == (
        "ENGINEERING_CLEAR_PROCESS_SLOT_SCOPED_NONAUTHORIZING_POSITIVE_PROBE"
    )
    assert boundary["modules"] == [
        "src/hswm/effect-runtime/src/s2s-stage-artifact-permits.ts",
        "src/hswm/effect-runtime/src/s2s-live-artifact.ts",
        "src/hswm/effect-runtime/src/s2s-live-github.ts",
    ]
    assert boundary["root_package_exported"] is False
    assert boundary["fixed_stage_surface"] == {
        "REGISTER": [],
        "CONFIRM": ["confirmReadRegistration"],
        "ADJUDICATE": [
            "adjudicateReadRegistration",
            "adjudicateReadCandidateFirst",
            "adjudicateRereadCandidate",
        ],
        "shape": "LAZY_ZERO_ARGUMENT_EFFECT_PROPERTIES",
        "caller_selected_identity_allowed": False,
        "intermediate_authority_or_unvalidated_bytes_exposed": False,
    }
    assert boundary["production_constructor"] == (
        "makeS2SStageArtifactReadsLiveLayer"
    )
    assert boundary["production_constructor_inputs"] == [
        "AUTHENTIC_REGISTRATION_B_CAPABILITY",
        "GITHUB_LIVE_TRANSPORT_CONFIG",
    ]
    assert boundary["production_layer_environment"] == "never"
    assert boundary["authority_identity"] == [
        "WORKFLOW_RUN_ID",
        "WORKFLOW_RUN_ATTEMPT_ONE",
        "REGISTRATION_COMMIT_B",
        "WORKFLOW_API_PATH",
        "WORKFLOW_RUN_CREATION_IDENTITY",
        "AUTHENTIC_STAGE",
        "CURRENT_NUMERIC_GITHUB_JOB_ID",
        "PREDECESSOR_NUMERIC_GITHUB_JOB_IDS",
    ]
    assert boundary["permit_state_machine"] == {
        "permit": "ISSUED_TO_IN_FLIGHT_TO_SPENT_SUCCESS_OR_SPENT_VOID",
        "stage": "ACTIVE_TO_IN_FLIGHT_TO_ACTIVE_COMPLETE_OR_VOID_THEN_CLOSED",
        "reservation": "ATOMIC_REF_MODIFY",
        "lifecycle": "EFFECT_ACQUIRE_USE_RELEASE",
        "wrong_stage_order_or_spent": "NO_MUTATION_NO_IO",
        "typed_failure_defect_or_interruption": "BURN_PERMIT_AND_VOID_STAGE",
        "refund_or_retry": False,
    }
    assert boundary["ledger"] == {
        "seed_phases": [
            "CURRENT_RUN_RUN_START",
            "CURRENT_RUN_JOBS",
            "CURRENT_RUN_RUNS_FOR_HEAD",
            "CURRENT_RUN_RUN_END",
        ],
        "capacities_including_seed": {
            "REGISTER": 4,
            "CONFIRM": 16,
            "ADJUDICATE": 40,
        },
        "admission": "ATOMIC_REF_MODIFY_AFTER_STANDALONE_REVALIDATION",
        "request_ids": "CASE_SENSITIVE_GLOBALLY_DISTINCT",
        "receipt_sha256": "GLOBALLY_DISTINCT",
        "timestamps": "MONOTONIC_NONDECREASING",
        "phase_topology": "EXACT_OPERATION_LOCAL",
        "eviction": False,
        "evidence_terminal_phase": "READBACK_RUN_END",
    }
    assert boundary["production_scope"] == {
        "authority_registry": "ROOT_PRIVATE_WEAKMAP",
        "same_exact_bearer_shares_spent_state": True,
        "another_bearer_can_replenish": False,
        "bounded_identity_slots": 1,
        "claim": "ONE_TRUSTED_WORKER_MODULE_COPY_PROCESS_IDENTITY_SLOT",
        "layer_lifetime_scope_claimed": False,
        "cross_worker_replay_prevention_claimed": False,
        "cross_module_copy_replay_prevention_claimed": False,
        "cross_process_replay_prevention_claimed": False,
        "durable_replay_prevention_claimed": False,
    }


def test_v8_fresh_binding_candidate_reread_and_claim_limits_are_exact() -> None:
    boundary = _load_handoff()["implemented_boundaries"][
        "stage_artifact_finite_permits"
    ]
    assert type(boundary) is dict

    assert boundary["fresh_binding"] == {
        "run_identity": "AUTHORITY_BOUND_ATTEMPT_ONE_B_PATH_AND_CREATION",
        "job_roster": "EXACT_THREE_JOBS_CURRENT_AND_PREDECESSOR_NUMERIC_IDS",
        "producer": "AUTHORITY_BOUND_PREDECESSOR_NUMERIC_JOB_ID",
        "artifact_list_raw_byte_validator": True,
        "single_artifact_raw_byte_validator": True,
        "absence_pairs_retained": 3,
    }
    assert boundary["candidate_reread"] == {
        "complete_independent_reads": 2,
        "fingerprint_fields": [
            "ARTIFACT_ID",
            "ARTIFACT_NAME",
            "ARTIFACT_SIZE_BYTES",
            "API_DIGEST_SHA256",
            "DOWNLOADED_ARCHIVE_SHA256",
            "VALIDATED_ARCHIVE_SHA256",
        ],
        "mismatch": "BURN_FINAL_PERMIT_AND_VOID_STAGE",
    }
    assert boundary["production_closure"] == {
        "workflow_source_policy": "OPEN_UNTIL_WORKFLOW_BYTES_EXIST",
        "invocation_event_file_io_occurs": True,
        "artifact_github_transport_configured": False,
        "artifact_github_calls": 0,
        "permit_scope_attached": False,
        "genuine_current_run_capability_issued": False,
        "genuine_stage_reads_issued": False,
        "result": "WORKFLOW_SOURCE_BYTES_OPEN",
    }
    assert boundary["test_probe"] == {
        "name": "probeS2SStageArtifactReadMechanicsForTest",
        "result_type": "Effect<void,TypedFailure,R>",
        "fixture_classification": "TEST_ONLY_NON_AUTHORIZING",
        "registry": "SEPARATE_TEST_ONLY_WEAKMAP",
        "same_fixture_replenishes": False,
        "production_authority_inspected_or_issued": False,
        "driver_closed_on_exit": True,
        "establishes_github_origin": False,
    }
    assert boundary["redirect_residual"] == {
        "status": "BOUNDED_NON_BLOCKING_CLAIM_BOUNDARY",
        "collision_may_be_detected_after_one_cdn_get": True,
        "cdn_github_authorization_header": False,
        "cdn_get_timed_byte_bounded_and_not_retried": True,
        "validated_bytes_or_evidence_escape": False,
        "final_run_read_after_collision": False,
        "stronger_no_downstream_io_claimed": False,
        "independent_cdn_request_id_or_cryptographic_origin_claimed": False,
    }
    assert boundary["later_hardening_not_gate_blockers"] == [
        "AGGREGATE_STAGE_OPERATION_DEADLINE",
        "REDIRECT_DOMAIN_AND_DNS_ALLOWLIST",
        "STREAM_CHUNK_COUNT_BOUND",
        "RECEIPT_HASH_REUSE_AND_TIMESTAMP_INVERSION_DIRECT_CORE_REGRESSIONS",
        "CONCURRENT_CLOSE_DURING_IN_FLIGHT_REGRESSION",
    ]


def test_v8_source_and_root_surface_preserve_the_claimed_boundary() -> None:
    permit_source = PERMIT_SOURCE_PATH.read_text(encoding="utf-8")
    artifact_source = ARTIFACT_SOURCE_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")
    package = _load_json(PACKAGE_PATH)

    assert 'type PermitStatus = "ISSUED" | "IN_FLIGHT" | "SPENT_SUCCESS" | "SPENT_VOID"' in permit_source
    assert 'type StageStatus = "ACTIVE" | "IN_FLIGHT" | "COMPLETE" | "VOID" | "CLOSED"' in permit_source
    assert "Ref.modify(scope.state" in permit_source
    assert "Effect.acquireUseRelease(" in permit_source
    assert "READBACK_RUN_END" in permit_source
    assert "PRODUCTION_SCOPES = new WeakMap" in permit_source
    assert "TEST_ONLY_SCOPES = new WeakMap" in permit_source
    assert "PRODUCTION_IDENTITY_SLOT" in permit_source
    assert "ledgerCapacityForStage" in permit_source
    assert 'stage === "REGISTER" ? 4 : stage === "CONFIRM" ? 16 : 40' in permit_source

    service_start = artifact_source.index(
        "export interface S2SRegisterStageArtifactReads"
    )
    service_end = artifact_source.index("const S2S_ARTIFACT_ABSENCE_OBSERVATION_COUNT")
    service = artifact_source[service_start:service_end]
    assert "observeRoleArtifact" not in service
    assert "confirmReadRegistration: Effect.Effect" in service
    assert "adjudicateReadRegistration: Effect.Effect" in service
    assert "adjudicateReadCandidateFirst: Effect.Effect" in service
    assert "adjudicateRereadCandidate: Effect.Effect" in service
    assert "(runId" not in service
    assert "makeS2SStageArtifactReadsLiveLayer" in artifact_source
    assert "probeS2SStageArtifactReadMechanicsForTest" in artifact_source
    probe = artifact_source[
        artifact_source.index("export const probeS2SStageArtifactReadMechanicsForTest") :
    ]
    assert "Effect.asVoid" in probe
    assert "makeS2SStageArtifactPermitTestScope" in probe
    assert "claimS2SStageArtifactPermitScope" not in probe

    for private_name in (
        "S2SStageArtifactReads",
        "makeS2SStageArtifactReadsLiveLayer",
        "probeS2SStageArtifactReadMechanicsForTest",
        "claimS2SStageArtifactPermitScope",
    ):
        assert private_name not in root_index
    assert "s2s-stage-artifact-permits" not in root_index
    assert package["exports"] == {
        ".": {
            "types": "./dist/index.d.ts",
            "default": "./dist/index.js",
        }
    }


def test_v8_gate_transition_and_continuation_order_are_exact() -> None:
    payload = _load_handoff()
    resolved = payload["resolved_gates"]
    opened = payload["open_gates"]
    assert type(resolved) is list
    assert type(opened) is list
    resolved_by_uid = {item["uid"]: item["status"] for item in resolved}
    open_by_uid = {item["uid"]: item for item in opened}
    assert len(resolved_by_uid) == len(resolved)
    assert len(open_by_uid) == len(opened)
    assert resolved_by_uid.keys().isdisjoint(open_by_uid.keys())
    assert resolved_by_uid[
        "sym:Gate:hswm-s2s-stage-specific-finite-permits"
    ] == "ENGINEERING_CLEAR_PROCESS_SLOT_SCOPED"
    assert set(open_by_uid) == {
        "sym:Blocker:hswm-s2s-workflow-source-bytes-manifest-binding",
        "sym:Blocker:hswm-s2s-workflow-api-path-selection",
        "sym:Blocker:hswm-s2s-current-run-github-origin-and-genuine-issuance",
        "sym:Blocker:hswm-s2s-terminal-reobservation-and-rerun-invalidation",
        "sym:Blocker:hswm-s2s-durable-external-evidence-envelope",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    assert all(item["severity"] == "P0" for item in opened)

    assert payload["next_session_order"] == [
        "READ_CONSTITUTION_V8_HANDOFF_V8_KG_IMMUTABLE_V7_AND_EFFECT_SKILL",
        "PRESERVE_PROTECTED_CONTINUAL_LIVE_USER_CHANGES_AND_TREAT_01B96AE_AS_CODE_CHECKPOINT",
        "IMPLEMENT_CONTENT_ADDRESSED_CREATE_ONLY_DURABLE_ENVELOPE_AND_CLOSED_STAGE_PROGRAMS_WITH_FIXED_ENTRYPOINTS_AND_MANDATORY_UPLOAD_POSTCONDITIONS_BEFORE_YAML",
        "IMPLEMENT_FRESH_TERMINAL_ATTEMPT_ONE_REOBSERVATION_AND_RERUN_INVALIDATION_IMMEDIATELY_BEFORE_CREATE_ONLY_PUBLICATION",
        "ADVERSARIALLY_REVIEW_COMPLETE_FAILURE_VOID_MATRIX_AND_PRESERVE_BOUNDED_REDIRECT_RESIDUAL_UNLESS_STRONGER_NO_IO_CLAIM_IS_REQUIRED",
        "AUTHOR_AND_REVIEW_EXACT_THREE_JOB_WORKFLOW_THEN_PIN_RAW_SHA_CONTRACT_DIGEST_SOURCE_A_MANIFEST_ROW_AND_ONE_API_PATH",
        "ADD_GENUINE_POSITIVE_PRODUCTION_LAYER_ISSUER_INSPECTOR_REGRESSION_ONLY_AFTER_ALL_SOURCE_BINDINGS_CLOSE",
        "DO_NOT_CREATE_SOURCE_FREEZE_PREREG_BEACON_DISPATCH_CANDIDATE_ADJUDICATION_OR_EVENT_10_FOR_ENGINEERING_PROGRESS",
    ]


def test_v8_paths_hashes_verification_indexes_and_nonclaims_are_exact() -> None:
    payload = _load_handoff()
    latest_bindings = _latest_binding_hashes(payload)
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json" not in paths
    assert {binding["path"]: binding["role"] for binding in bindings} == {
        "docs/operations/HSWM_SWM0W_S2S_STAGE_ARTIFACT_PERMITS_IMPLEMENTED_NEXT_SESSION_2026-08-22.md": "NEXT_SESSION_STAGE_ARTIFACT_PERMIT_IMPLEMENTATION_HANDOFF",
        "ontology/evidence/README.md": "LOCAL_KG_CURRENT_CONTINUATION_INDEX_V8",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md": "TYPESCRIPT_EFFECT_RESEARCH_CONTINUATION_INDEX_V8",
        "src/hswm/effect-runtime/README.md": "EFFECT_RUNTIME_CURRENT_CONTINUATION_INDEX_V8",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v8.py": "LOCAL_KG_V8_CLOSURE_REGRESSIONS",
        "docs/operations/HSWM_SWM0W_S2S_RUN_AUTHORITY_IMPLEMENTED_NEXT_SESSION_2026-08-22.md": "IMMUTABLE_V7_IMPLEMENTATION_HANDOFF_PREDECESSOR",
        "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json": "IMMUTABLE_V7_KG_PREDECESSOR",
        "src/hswm/effect-runtime/src/s2s-stage-artifact-permits.ts": "FINITE_PERMIT_AND_BOUNDED_LEDGER_IMPLEMENTATION",
        "src/hswm/effect-runtime/src/s2s-live-artifact.ts": "FIXED_STAGE_ARTIFACT_READ_AND_FRESH_REVALIDATION_IMPLEMENTATION",
        "src/hswm/effect-runtime/src/s2s-live-github.ts": "RAW_BYTE_ARTIFACT_VALIDATORS_AND_BOUNDED_DOWNLOAD_DEPENDENCY",
        "src/hswm/effect-runtime/src/s2s-run-authority.ts": "CURRENT_RUN_AUTHORITY_INPUT_DEPENDENCY",
        "src/hswm/effect-runtime/src/s2s-workflow-contract.ts": "FIXED_STAGE_OPERATION_ORDER_DEPENDENCY",
        "src/hswm/effect-runtime/src/index.ts": "ROOT_EXPORT_CONTAINMENT_SURFACE_V8",
        "src/hswm/effect-runtime/package.json": "EXACT_SINGLE_ROOT_PACKAGE_EXPORT_MAP_V8",
        "src/hswm/effect-runtime/test/s2s-live-artifact.test.ts": "FINITE_PERMIT_LEDGER_AND_READBACK_HOSTILE_REGRESSIONS",
        "src/hswm/effect-runtime/test/s2s-live-github.test.ts": "ARTIFACT_RAW_BYTE_VALIDATOR_AND_DOWNLOAD_REGRESSIONS",
        "src/hswm/effect-runtime/test/s2s-run-authority.test.ts": "PRODUCTION_CLOSURE_AND_AUTHORITY_REGRESSIONS_V8",
        "src/hswm/effect-runtime/test/public-api.test.ts": "ROOT_PRIVATE_SURFACE_REGRESSIONS_V8",
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
    assert verification["effect_tests"] == "218/218 PASS"
    assert verification["effect_test_suites"] == "16/16 PASS"
    assert verification["focused_stage_artifact_tests"] == "22/22 PASS"
    assert verification["focused_github_tests"] == "32/32 PASS"
    assert verification["focused_current_run_tests"] == "30/30 PASS"
    assert verification["focused_public_api_tests"] == "2/2 PASS"
    assert verification["focused_total"] == "86/86 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS"
    assert verification["independent_audits"] == (
        "TWO_READ_ONLY_AUDITS_NO_FINITE_PERMIT_GATE_BLOCKER_IN_DECLARED_SCOPE"
    )

    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        index_text = index_path.read_text(encoding="utf-8")
        assert any(
            (
                f"HSWM_SWM0W_S2S_EFFECT_HANDOFF.v{checkpoint['schema_version'].removeprefix('hswm-engineering-handoff-kg/v')}.json"
                in index_text
            )
            or Path(checkpoint["handoff_path"]).name in index_text
            for checkpoint in [payload, *_successor_chain(payload)]
        )

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert type(nonclaims) is list
    assert any("not GitHub or CDN origin" in item for item in nonclaims)
    assert any("not Layer-lifetime" in item for item in nonclaims)
    assert any("not durable" in item for item in nonclaims)
    assert any("one CDN GET" in item for item in nonclaims)
    assert any("not a preregistration" in item for item in nonclaims)
    assert any("no event-10" in item for item in nonclaims)


def test_v8_predecessor_is_immutable_and_successor_chain_is_unique() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)

    assert predecessor["bundle_uid"] == payload[
        "supersedes_bundle_uid_for_continuation"
    ]
    predecessor_binding = next(
        binding
        for binding in payload["artifact_bindings"]
        if binding["path"]
        == "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v7.json"
    )
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        predecessor_binding["sha256"]
    )
    v7_successors = [
        candidate
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != PREDECESSOR_PATH
        if (candidate := _load_json(path)).get(
            "supersedes_bundle_uid_for_continuation"
        )
        == predecessor["bundle_uid"]
    ]
    assert [candidate["bundle_uid"] for candidate in v7_successors] == [
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
