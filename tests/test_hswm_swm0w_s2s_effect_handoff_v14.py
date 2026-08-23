from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json"
ORACLE_PATH = ROOT / "src/hswm/experiments/swm0w_s2s_numeric_oracle.py"
ORCHESTRATION_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-orchestration.ts"
LIVE_PYTHON_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-live-python.ts"
PYTHON_EVIDENCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-python-evidence.ts"
PROFILE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-profile.ts"
JOB_SEQUENCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-job-sequence.ts"
CONFIRMATORY_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-confirmatory.ts"
ROOT_INDEX_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V13_SHA256 = (
    "46f59d377d92cb0ed1e56aa4bbd42b9b26119f43feb590b114f41d41a1b7fd5d"
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


def test_v14_is_duplicate_key_safe_latest_design_only_checkpoint() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    payload = _load_handoff()
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v14"
    assert payload["bundle_uid"] == (
        "sym:EngineeringDesignCheckpoint:"
        "hswm-swm0w-s2s-golden-local-vertical-composition-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-local-durable-replay-profile-integrated-2026-08-23"
    )
    assert payload["workspace_parent_commit"] == (
        "d2d727e828fcb1daa462d5ce8a1a1a08594768af"
    )
    assert payload["workspace_primary_implementation_commit"] == (
        "8d9f254c11176a194f74610cfac422dfa67aae08"
    )
    assert payload["workspace_code_commit"] == (
        "8d9f254c11176a194f74610cfac422dfa67aae08"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["design_status"] == (
        "GOLDEN_NUMERIC_UPLOAD_HARNESS_AND_PRODUCTION_SEMANTIC_GAP_"
        "AUDITED_AND_FROZEN"
    )
    assert payload["implementation_status"] == (
        "NOT_STARTED_REUSES_EXISTING_COMPONENTS"
    )

    for flag in (
        "stage_artifact_read_replay_core_implemented",
        "local_create_only_stage_read_replay_profile_attachment_integration",
        "golden_numeric_component_path_audited",
        "healthy_success_profile_inventory_audited",
        "stage_upload_and_terminal_finalizer_boundaries_separated",
        "golden_local_vertical_composition_design_frozen",
        "production_carrier_local_receipt_semantic_gap_audited",
        "golden_verifier_executor_runtime_exact_binding_designed",
        "void_immediate_terminal_branch_designed",
    ):
        assert payload[flag] is True
    for flag in (
        "production_carriers_accept_local_test_receipts",
        "golden_local_vertical_composition_implemented",
        "live_golden_success_candidate_observed",
        "live_golden_success_adjudication_observed",
        "local_test_only_golden_artifact_store_implemented",
        "test_only_golden_upload_postcondition_schema_implemented",
        "stage_upload_postcondition_schema_implemented",
        "local_test_only_upload_readback_vertical_slice_implemented",
        "all_healthy_success_attachment_occurrences_real",
        "complete_replay_attachment_profiles_closed",
        "closed_stage_programs_implemented",
        "mandatory_upload_postconditions_implemented",
        "production_terminal_finalizer_implemented",
        "github_origin_established",
        "workflow_source_frozen",
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
        "F": "NO_GOLDEN_SUCCESS_OR_CONFIRMATORY_NUMERIC_RESULT",
        "Pi": (
            "UNCHANGED_DOCUMENTATION_ONLY_NEXT_LOCAL_GOLDEN_"
            "COMPOSITION_BOUNDARY_FROZEN"
        ),
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }

    nodes = payload["nodes"]
    relations = payload["relations"]
    assert type(nodes) is list
    assert type(relations) is list
    uids = [node["uid"] for node in nodes]
    assert len(uids) == len(set(uids))
    uid_set = set(uids)
    assert all(relation["from_uid"] in uid_set for relation in relations)
    assert all(relation["to_uid"] in uid_set for relation in relations)
    assert not any(relation["type"] == "EVIDENCE_FOR" for relation in relations)
    assert all(node.get("scientific_status") != "PASS" for node in nodes)


def test_v14_freezes_the_existing_effect_v3_numeric_function_cell_path() -> None:
    payload = _load_handoff()
    boundary = payload["typescript_effect_boundary"]
    golden = payload["golden_numeric_path"]
    oracle = ORACLE_PATH.read_text(encoding="utf-8")
    orchestration = ORCHESTRATION_PATH.read_text(encoding="utf-8")
    live_python = LIVE_PYTHON_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")

    assert payload["frozen_versions"] == {
        "typescript": "5.9.3",
        "effect": "3.22.1",
        "node": "24.13.0",
        "vitest": "3.2.7",
    }
    assert boundary["control_runtime"] == (
        "STRICT_TYPESCRIPT_EFFECT_V3_FUNCTIONAL_CORE_EFFECT_SHELL"
    )
    assert boundary["numeric_function_cell"] == (
        "PINNED_PYTHON_NUMPY_ORACLE_BEHIND_EFFECT_SERVICE"
    )
    assert boundary["direct_service_for_next_slice"] == "S2SPythonNumericExecutor"
    assert boundary["python_numeric_oracle_legacy_port_reused"] is False
    assert boundary["new_root_exports_allowed"] is False
    assert boundary["python_rewrite_authorized"] is False

    assert golden["purpose"] == "CROSS_LANGUAGE_TEST_VECTOR_NOT_CONFIRMATORY_EVIDENCE"
    assert golden["external_seed_hex"] == (
        "552e51d2ff75cb7c5df5b55a166aba12"
        "a277c2813bbdd69bc825286e7c26b6f0"
    )
    assert golden["confirm_request_self_sha256"] == (
        "16e4965054165863add0395397cbf3d68d1f3d472b7fc303e40056855368b1d1"
    )
    assert golden["confirm_request_document_sha256"] == (
        "294eb438fe042238bbe725d0473765f3634eb57876e5cae4807915db66034237"
    )
    assert golden["all_low_level_numeric_components_present"] is True
    assert golden["root_private_composition_present"] is False
    assert golden["successful_live_confirm_test_present"] is False
    assert golden["successful_live_adjudication_test_present"] is False
    assert golden["future_seed_required"] is False
    assert golden["preregistration_required"] is False
    assert golden["verifier_executor_runtime_source_receipt_exact_match_required"] is True
    for key in (
        "production_job_sequence_used",
        "production_confirmatory_events_synthesized",
        "production_artifact_evidence_synthesized",
        "production_success_profiles_written",
        "production_durable_evidence_store_used",
    ):
        assert golden[key] is False
    assert "BEFORE_ADJUDICATION_EVIDENCE_BIND" in golden["void_policy"]
    assert (
        "EXACT_COMPARE_GOLDEN_VERIFIER_AND_NUMERIC_EXECUTOR_RUNTIME_SOURCE_RECEIPTS"
        in golden["component_path"]
    )
    assert "prepareS2SCandidateCarrier" not in golden["component_path"]
    assert "prepareS2SAdjudicationCarrier" not in golden["component_path"]

    for literal in (
        "GOLDEN_EXTERNAL_SEED_HEX",
        golden["external_seed_hex"],
        golden["confirm_request_self_sha256"],
        golden["confirm_request_document_sha256"],
    ):
        assert literal in oracle
    for literal in (
        "export const buildPythonNumericConfirmRequest",
        "export const projectOpaqueNumericAdjudication",
        golden["confirm_request_self_sha256"],
        golden["confirm_request_document_sha256"],
    ):
        assert literal in orchestration
    for literal in (
        "export class S2SPythonGoldenVerifier",
        "export class S2SPythonNumericExecutor",
        "makeS2SPythonGoldenVerifierProcessLayer",
        "makeS2SPythonNumericExecutorProcessLayer",
    ):
        assert literal in live_python
    assert "runS2SGoldenNumericDryRun" not in root_index


def test_v14_profile_inventory_is_exact_and_keeps_partial_claims_narrow() -> None:
    payload = _load_handoff()
    inventory = payload["healthy_success_profile_inventory"]
    profile = PROFILE_PATH.read_text(encoding="utf-8")

    assert inventory["stage_occurrence_counts"] == {
        "REGISTER": 13,
        "CONFIRM": 17,
        "ADJUDICATE": 18,
        "TOTAL": 48,
    }
    assert inventory["classification_counts"] == {
        "CONSTRUCT_AND_VALIDATE": 20,
        "SEMANTIC_CORE_NO_ATTACHMENT_CODEC": 19,
        "MISSING_CARRIER_OR_SOURCE": 9,
    }
    assert sum(inventory["classification_counts"].values()) == 48
    family_keys = {
        "CONSTRUCT_AND_VALIDATE": "construct_and_validate_families",
        "SEMANTIC_CORE_NO_ATTACHMENT_CODEC": (
            "semantic_core_without_attachment_codec_families"
        ),
        "MISSING_CARRIER_OR_SOURCE": "missing_carrier_or_source_families",
    }
    for classification, family_key in family_keys.items():
        occurrences = []
        for family in inventory[family_key]:
            match = re.search(r"_X([0-9]+)$", family)
            assert match is not None, family
            occurrences.append(int(match.group(1)))
        assert sum(occurrences) == inventory["classification_counts"][classification]
    assert inventory["top_level_validator_scope"] == (
        "ROSTER_DESCRIPTOR_MEDIA_TYPE_AND_CAP_ONLY"
    )
    assert inventory["v13_non_replay_fixture_payload"] == "ONE_BYTE_SENTINEL"
    assert inventory["partial_vertical_claim_name"] == (
        "TEST_ONLY_NON_AUTHORIZING_GOLDEN_VERTICAL_REPLAY"
    )
    assert inventory["partial_vertical_completes_healthy_success_profile"] is False
    assert inventory["complete_profile_gate"] == (
        "ALL_48_REAL_RECOVERY_VALIDATED_WITH_SCHEMA_FAMILY_MUTATION_FAILURES"
    )

    for literal in (
        'const REGISTER = sortedProfile([',
        'const CONFIRM = sortedProfile([',
        'const ADJUDICATE = sortedProfile([',
        '"upload/registration_postcondition.zip"',
        '"upload/candidate_postcondition.zip"',
        '"upload/adjudication_postcondition.zip"',
        '"numeric/python_golden_replay.zip"',
        '"source/registration_source.zip"',
        '"source/workflow.yml"',
    ):
        assert literal in profile


def test_v14_freezes_only_the_local_upload_readback_slice() -> None:
    payload = _load_handoff()
    upload = payload["upload_readback_boundary"]
    next_slice = payload["frozen_next_slice"]
    job_sequence = JOB_SEQUENCE_PATH.read_text(encoding="utf-8")
    confirmatory = CONFIRMATORY_PATH.read_text(encoding="utf-8")
    orchestration = ORCHESTRATION_PATH.read_text(encoding="utf-8")
    python_evidence = PYTHON_EVIDENCE_PATH.read_text(encoding="utf-8")

    for literal in (
        "type S2SConfirmatoryEvent",
        "type S2SArtifactEvidence",
        "export const prepareS2SRegistrationCarrier",
        "export const prepareS2SCandidateCarrier",
        "export const prepareS2SAdjudicationCarrier",
    ):
        assert literal in job_sequence
    for literal in (
        "const ArtifactEvidenceSchema",
        "artifactId: ArtifactIdSchema",
        "retentionDays: PositiveSafeIntegerSchema",
        "apiDigestSha256: Sha256TextSchema",
        "const BeginRegistrationSchema",
        "futureBeaconRound: BeaconRoundSchema",
        "preregistrationSha256: Sha256TextSchema",
    ):
        assert literal in confirmatory
    assert 'document.numeric_replay.numeric_candidate_outcome === "VOID"' in orchestration
    assert '"NUMERIC_OUTCOME_VOID"' in orchestration
    assert "requestSelfSha256" in python_evidence
    assert "executor stdin hash must equal the bound request document hash" in python_evidence

    production = upload["production_stage_local_mandatory_boundary"]
    local = upload["test_only_golden_numeric_boundary"]
    terminal = upload["production_terminal_finalizer"]
    assert production["status"] == "OPEN_NOT_IN_NEXT_SLICE"
    assert production["fixed_stage_role_and_name_derived_internally"] is True
    assert local["status"] == "OPEN_DESIGN_FROZEN_NEXT_SLICE"
    assert local["roles"] == ["GOLDEN_CANDIDATE", "GOLDEN_ADJUDICATION"]
    assert local["classification"] == "TEST_ONLY_NON_AUTHORIZING"
    assert local["schema_distinct_from_production_stage_postcondition"] is True
    assert local["production_projection_adapter_provided"] is False
    assert local["production_profile_or_carrier_call_site_provided"] is False
    assert local[
        "production_validator_rejection_of_relabelled_test_bytes_claimed"
    ] is False
    assert local["publish_return_trusted_as_readback"] is False
    assert local["candidate_independent_read_count"] == 2
    assert local["fresh_layer_recovery_required"] is True
    assert terminal["status"] == "OPEN_NOT_IN_NEXT_SLICE"
    assert terminal["rerun_invalidation_required"] is True
    assert terminal["event_10_required"] is True
    assert upload["existing_confirmatory_artifact_store_skeleton_suitable"] is False
    assert upload["existing_github_observer_can_upload"] is False
    assert upload["external_exactly_once_claimed"] is False

    assert next_slice["entrypoint"] == "runS2SGoldenNumericDryRun"
    assert next_slice["effect_model"] == (
        "LAZY_EFFECT_TYPED_ERRORS_REQUIRED_SERVICES_TEST_LAYER"
    )
    assert next_slice["root_package_exported"] is False
    assert next_slice["test_artifact_store_backing"] == (
        "CREATE_ONLY_FILES_UNDER_EXPLICIT_CALLER_OWNED_TEMPORARY_ROOT"
    )
    assert next_slice["fresh_layer_reuses_same_explicit_root"] is True
    assert next_slice["in_memory_only_backing_allowed"] is False
    assert next_slice["required_services"] == [
        "S2SPythonGoldenVerifier",
        "S2SPythonNumericExecutor",
        "S2STestOnlyGoldenArtifactStore",
    ]
    assert next_slice["implicit_publish_retry"] is False
    assert next_slice[
        "verifier_executor_runtime_source_receipt_exact_match_required"
    ] is True
    assert next_slice["candidate_second_readback_feeds_adjudication"] is True
    assert next_slice["production_job_sequence_used"] is False
    assert next_slice["production_events_or_artifact_evidence_created"] is False
    assert next_slice["production_success_profile_committed"] is False
    assert next_slice["production_durable_evidence_store_used"] is False
    assert "BEFORE_ADJUDICATION_EVIDENCE_BIND" in next_slice["void_branch"]
    assert next_slice["event_10_emitted"] is False
    assert next_slice["scientific_verdict_emitted"] is False
    assert next_slice["default_test_suite_runs_real_60_cell_workload"] is False
    assert set(next_slice["required_typed_failures"]) == {
        "PUBLISH_FAILED",
        "PUBLICATION_OUTCOME_UNKNOWN",
        "READBACK_FAILED",
        "READBACK_MISMATCH",
        "POSTCONDITION_INVALID",
        "RECOVERY_MISMATCH",
        "CREATE_ONLY_CONFLICT",
        "RUNTIME_IDENTITY_MISMATCH",
    }

    resolved = payload["resolved_design_questions"]
    assert len(resolved) == 5
    assert {question["status"] for question in resolved} == {
        "DESIGN_CLEAR",
        "AUDITED",
        "AUDITED_INCOMPATIBLE",
    }
    open_gates = {gate["uid"] for gate in payload["open_gates"]}
    assert {
        "sym:OpenGate:s2s-test-only-golden-upload-contract",
        "sym:OpenGate:s2s-test-only-golden-artifact-store",
        "sym:OpenGate:s2s-golden-numeric-composition-root",
        "sym:OpenGate:s2s-production-carrier-semantic-connector",
        "sym:OpenGate:s2s-live-golden-success-run",
        "sym:OpenGate:s2s-complete-healthy-success-profiles",
        "sym:OpenGate:s2s-production-terminal-finalizer",
        "sym:OpenGate:s2s-scientific-qbr-verdict",
    } <= open_gates

    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_V14_HANDOFF_V14_KG_IMMUTABLE_V13_AND_EFFECT_SKILL"
    )
    assert order[2] == (
        "IMPLEMENT_DISTINCT_TEST_ONLY_GOLDEN_ARTIFACT_AND_UPLOAD_"
        "POSTCONDITION_CODEC_WITH_NO_PRODUCTION_PROJECTION_ADAPTER_OR_CALL_SITE"
    )
    assert order[-1] == (
        "DO_NOT_FREEZE_PREREGISTER_SELECT_FUTURE_SEED_DISPATCH_COMPOSE_"
        "EVENT_10_OR_VERDICT_FOR_ENGINEERING_PROGRESS"
    )

    nonclaims = payload["nonclaims"]
    assert any("no runtime implementation" in item for item in nonclaims)
    assert any("not future randomness" in item for item in nonclaims)
    assert any("Only 20 of 48" in item for item in nonclaims)
    assert any("not a GitHub artifact ID" in item for item in nonclaims)
    assert any("cannot honestly inhabit S2SArtifactEvidence" in item for item in nonclaims)
    assert any("not claimed to reject" in item for item in nonclaims)
    assert any("same explicit caller-owned temporary root" in item for item in nonclaims)
    assert any("NUMERIC_OUTCOME_VOID" in item for item in nonclaims)
    assert any("runtime-source identity" in item for item in nonclaims)
    assert any("not HSWM cognition" in item for item in nonclaims)
    assert any("outcome-bound causal-learning loop" in item for item in nonclaims)


def test_v14_bindings_chain_indexes_and_verification_are_exact() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)
    latest_bindings = _latest_binding_hashes(payload)
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V13_SHA256
    )
    assert predecessor["bundle_uid"] == payload[
        "supersedes_bundle_uid_for_continuation"
    ]

    successors = [
        candidate
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != PREDECESSOR_PATH
        if (candidate := _load_json(path)).get(
            "supersedes_bundle_uid_for_continuation"
        )
        == predecessor["bundle_uid"]
    ]
    assert [candidate["bundle_uid"] for candidate in successors] == [
        payload["bundle_uid"]
    ]

    bindings = payload["artifact_bindings"]
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    required_paths = {
        "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json",
        payload["handoff_path"],
        "docs/canon/HSWM_CONSTITUTION_2026-08-20.md",
        "src/hswm/effect-runtime/assets/adopted-protocol-config.json",
        "src/hswm/experiments/swm0w_s2s_numeric_oracle.py",
        "src/hswm/effect-runtime/src/s2s-orchestration.ts",
        "src/hswm/effect-runtime/src/s2s-live-python.ts",
        "src/hswm/effect-runtime/src/s2s-python-evidence.ts",
        "src/hswm/effect-runtime/src/s2s-confirmatory.ts",
        "src/hswm/effect-runtime/src/s2s-job-sequence.ts",
        "src/hswm/effect-runtime/src/s2s-evidence-profile.ts",
        "src/hswm/effect-runtime/src/s2s-zip.ts",
        "src/hswm/effect-runtime/src/s2s-evidence-file.ts",
        "src/hswm/effect-runtime/src/s2s-live-artifact.ts",
        "src/hswm/effect-runtime/src/s2s-stage-read-replay-durable-profile.ts",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v13.py",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v14.py",
    }
    assert required_paths <= set(paths)
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json" not in paths
    for binding in bindings:
        assert set(binding) == {"path", "role", "sha256"}
        relative = binding["path"]
        expected = binding["sha256"]
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
    assert verification["runtime_implementation_changed"] is False
    assert verification["live_golden_success_run_executed"] is False
    assert verification["v14_kg_tests"] == "5/5 PASS"
    assert verification["v1_through_v14_handoff_chain_tests"] == "67/67 PASS"
    assert verification["json_duplicate_key_check"] == "PASS"
    assert verification["artifact_binding_check"] == "PASS"
    assert verification["diff_check"] == "PASS"
    assert verification["protected_unrelated_paths_untouched"] == "PASS"
    assert "design checkpoint only" in verification["claim_boundary"]
    assert "no complete healthy-success profile" in verification["claim_boundary"]
    assert "no production upload/finalizer" in verification["claim_boundary"]
    assert "no scientific verdict" in verification["claim_boundary"]

    handoff_name = Path(payload["handoff_path"]).name
    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        text = index_path.read_text(encoding="utf-8")
        assert "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json" in text
        assert handoff_name in text

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
