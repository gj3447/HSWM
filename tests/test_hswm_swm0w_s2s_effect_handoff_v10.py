from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json"
PROFILE_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-profile.ts"
RUN_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-run-authority.ts"
PREREG_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-preregistration.ts"
PYTHON_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-live-python.ts"
PYTHON_EVIDENCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-python-evidence.ts"
JOB_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-job-sequence.ts"
ARTIFACT_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-live-artifact.ts"
ASSET_SOURCE_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-protocol-config-asset.ts"
)
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


def test_v10_is_a_pi_prerequisite_checkpoint_not_a_scientific_verdict() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v10"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-replay-prerequisites-implemented-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-durable-evidence-substrate-implemented-2026-08-23"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["design_status"] == (
        "V9_REPLAY_PREREQUISITES_AND_TOP_LEVEL_SUCCESS_PROFILE_IMPLEMENTED"
    )
    assert payload["implementation_status"] == (
        "REPLAY_PREREQUISITES_ENGINEERING_CLEAR_"
        "NESTED_REPLAY_AND_STAGE_PROGRAMS_OPEN"
    )
    assert payload["structural_status"] == "STRUCTURAL_1_6_9_CLEAR"
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )
    assert payload["effect_skill_application_status"] == (
        "APPLIED_TO_IMPLEMENTATION_AND_VERIFICATION_NOT_A_RUNTIME_DEPENDENCY"
    )
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["workspace_parent_commit"] == (
        "d2aa5e74a8e408510b7a74b06c20f048f6072ec4"
    )
    assert payload["workspace_code_commit"] == (
        "443f17fa081c78ca17e978ca87c691cf12300101"
    )
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"

    for flag in (
        "complete_replay_attachment_profiles_closed",
        "closed_stage_programs_implemented",
        "mandatory_upload_postconditions_implemented",
        "external_shared_durable_store_deployed",
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
            "REPLAY_INPUT_RETENTION_CAP_COHERENCE_AND_TOP_LEVEL_"
            "HEALTHY_SUCCESS_ATTACHMENT_ROSTERS_IMPLEMENTED_"
            "NESTED_REPLAY_AND_STAGE_PROGRAMS_OPEN"
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


def test_v10_replay_prerequisite_boundaries_are_exact() -> None:
    boundaries = _load_handoff()["implemented_boundaries"]

    assert boundaries["protocol_config_asset"] == {
        "status": "ENGINEERING_CLEAR_FIXED_PACKAGED_ASSET",
        "module": "src/hswm/effect-runtime/src/s2s-protocol-config-asset.ts",
        "asset_path": "src/hswm/effect-runtime/assets/adopted-protocol-config.json",
        "service": "S2SAdoptedProtocolConfigAsset",
        "root_package_exported": False,
        "byte_length": 1973,
        "maximum_bytes": 65536,
        "raw_sha256": (
            "315dad65a8882c4b7c5fb73d295df28b58b0696e25b1b790a342b40ced8d10c4"
        ),
        "receipt_sha256": (
            "a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb"
        ),
        "io_contract": "LAZY_FIXED_MODULE_RELATIVE_O_NOFOLLOW_REGULAR_FILE_IDENTITY",
        "canonical_json_revalidated": True,
        "packaged": True,
    }

    assert boundaries["current_run_replay_snapshot"] == {
        "status": "ENGINEERING_CLEAR_RETAINED_BYTE_CONSISTENCY_NOT_ORIGIN",
        "module": "src/hswm/effect-runtime/src/s2s-run-authority.ts",
        "effect": "snapshotS2SCurrentRunReplay",
        "required_service": "S2SCurrentRunStage",
        "root_package_exported": False,
        "selector_arguments": 0,
        "authority_bearer_returned": False,
        "maximum_raw_bytes": 5242880,
        "component_caps": {
            "invocation_event": 1048576,
            "github_observations": 4,
            "each_github_observation": 1048576,
        },
        "revalidated": [
            "CURRENT_INVOCATION_EVENT_AND_EVIDENCE",
            "CURRENT_RUN_EVIDENCE_SELF_RECEIPT",
            "RUN_START_RAW_OBSERVATION",
            "JOBS_RAW_OBSERVATION",
            "RUNS_FOR_HEAD_RAW_OBSERVATION",
            "RUN_END_RAW_OBSERVATION",
            "RECEIPT_REQUEST_ID_TIMESTAMP_BINDINGS",
        ],
        "github_origin_established": False,
    }

    assert boundaries["registration_replay_projection"] == {
        "status": "ENGINEERING_CLEAR_PARTIAL_REPLAY_FULL_SOURCE_SNAPSHOT_OPEN",
        "module": "src/hswm/effect-runtime/src/s2s-preregistration.ts",
        "accessor": "inspectS2SRegistrationReplaySnapshot",
        "root_package_exported": False,
        "repository_io_on_inspection": False,
        "authority_bearer_returned": False,
        "retained": [
            "REGISTRATION_COMMIT_AUTHORITY_EVIDENCE",
            "PREREGISTRATION_DOCUMENT",
            "PREREGISTRATION_CANONICAL_BYTES",
            "PREREGISTRATION_FILE_SHA256",
            "CONDITIONAL_WORKFLOW_MANIFEST_BINDING",
        ],
        "full_registration_source_snapshot_complete": False,
    }

    assert boundaries["numeric_and_transport_caps"] == {
        "github_json_bytes": 1048576,
        "numeric_candidate_bytes": 62914560,
        "numeric_adjudication_bytes": 3145728,
        "adjudication_archive_bytes": 4194304,
        "adjudication_cap_enforced_by": [
            "PYTHON_STDOUT_PROCESS_LIMIT",
            "PYTHON_EXECUTION_EVIDENCE_BINDER",
            "ADJUDICATION_CARRIER_PREPARATION",
            "ADJUDICATION_ARTIFACT_MEMBER_READBACK",
        ],
        "empty_forged_executor_output_rejected": True,
    }


def test_v10_top_level_success_profile_and_source_containment_are_exact() -> None:
    payload = _load_handoff()
    profile = payload["implemented_boundaries"]["success_attachment_profile"]
    assert profile == {
        "status": "ENGINEERING_CLEAR_TOP_LEVEL_HEALTHY_SUCCESS_ONLY",
        "module": "src/hswm/effect-runtime/src/s2s-evidence-profile.ts",
        "schema_version": "hswm-swm0w-s2s-success-stage-attachment-profile/v1",
        "schema_version_durably_bound": False,
        "root_package_exported": False,
        "exact_counts": {"REGISTER": 13, "CONFIRM": 17, "ADJUDICATE": 18},
        "logical_names": {
            "REGISTER": [
                "authority/current_invocation_event.json",
                "authority/current_invocation_evidence.json",
                "authority/current_run_replay.zip",
                "authority/registration_commit_evidence.json",
                "config/operational_policy.json",
                "config/protocol_config.json",
                "config/workflow_contract.json",
                "source/pilot_adoption_receipt.json",
                "source/preregistration.json",
                "source/registration_source.zip",
                "source/workflow.yml",
                "upload/registration_archive.zip",
                "upload/registration_postcondition.zip",
            ],
            "CONFIRM": [
                "authority/current_invocation_event.json",
                "authority/current_invocation_evidence.json",
                "authority/current_run_replay.zip",
                "input/registration_read.zip",
                "numeric/confirm_request.json",
                "numeric/python_execution.json",
                "numeric/python_golden_replay.zip",
                "numeric/python_invocation.json",
                "numeric/python_rss.json",
                "numeric/python_runtime.json",
                "randomness/confirm_drand_execution.json",
                "randomness/confirm_drand_fixture.json",
                "randomness/confirm_drand_pulse.json",
                "randomness/confirm_drand_request.json",
                "randomness/confirm_drand_verification.json",
                "upload/candidate_archive.zip",
                "upload/candidate_postcondition.zip",
            ],
            "ADJUDICATE": [
                "authority/current_invocation_event.json",
                "authority/current_invocation_evidence.json",
                "authority/current_run_replay.zip",
                "input/candidate_first_read.zip",
                "input/candidate_reread.zip",
                "input/registration_read.zip",
                "numeric/python_execution.json",
                "numeric/python_golden_replay.zip",
                "numeric/python_invocation.json",
                "numeric/python_rss.json",
                "numeric/python_runtime.json",
                "randomness/adjudicate_drand_execution.json",
                "randomness/adjudicate_drand_fixture.json",
                "randomness/adjudicate_drand_pulse.json",
                "randomness/adjudicate_drand_request.json",
                "randomness/adjudicate_drand_verification.json",
                "upload/adjudication_archive.zip",
                "upload/adjudication_postcondition.zip",
            ],
        },
        "descriptor_checks": [
            "EXACT_SORTED_LOGICAL_NAME",
            "UNIQUE_ROLE",
            "EXACT_SCHEMA_VERSION",
            "EXACT_MEDIA_TYPE",
            "NARROW_PER_ATTACHMENT_MAXIMUM",
        ],
        "nested_zip_semantics_validated": False,
        "cross_attachment_semantics_validated": False,
        "failure_void_profiles_implemented": False,
        "complete_replay_evidence_claimed": False,
    }

    source = PROFILE_SOURCE_PATH.read_text(encoding="utf-8")
    run_source = RUN_SOURCE_PATH.read_text(encoding="utf-8")
    prereg_source = PREREG_SOURCE_PATH.read_text(encoding="utf-8")
    python_source = PYTHON_SOURCE_PATH.read_text(encoding="utf-8")
    python_evidence = PYTHON_EVIDENCE_PATH.read_text(encoding="utf-8")
    job_source = JOB_SOURCE_PATH.read_text(encoding="utf-8")
    artifact_source = ARTIFACT_SOURCE_PATH.read_text(encoding="utf-8")
    asset_source = ASSET_SOURCE_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")
    package = _load_json(PACKAGE_PATH)

    for literal in (
        '"hswm-swm0w-s2s-success-stage-attachment-profile/v1"',
        "S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES",
        "buildS2SSuccessStageEvidenceEnvelope",
        "validateS2SSuccessStageEvidenceEnvelope",
        'profileError(\n          "UNKNOWN"',
    ):
        assert literal in source
    assert "snapshotS2SCurrentRunReplay: Effect.Effect" in run_source
    assert "S2S_CURRENT_RUN_REPLAY_MAX_RAW_BYTES" in run_source
    assert "inspectS2SRegistrationReplaySnapshot" in prereg_source
    assert "S2S_NUMERIC_ADJUDICATION_MAX_BYTES = 3 * 1_048_576" in python_source
    assert "validateS2SPythonRssTelemetryBytes" in python_source
    assert "input.output.byteLength > maximumOutputBytes" in python_evidence
    assert "S2S_NUMERIC_ADJUDICATION_MAX_BYTES" in job_source
    assert "S2S_NUMERIC_ADJUDICATION_MAX_BYTES" in artifact_source
    assert "O_NOFOLLOW" in asset_source

    for private_name in (
        "S2SAdoptedProtocolConfigAsset",
        "snapshotS2SCurrentRunReplay",
        "inspectS2SRegistrationReplaySnapshot",
        "S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES",
        "buildS2SSuccessStageEvidenceEnvelope",
    ):
        assert private_name not in root_index
    assert package["exports"] == {
        ".": {"types": "./dist/index.d.ts", "default": "./dist/index.js"}
    }
    assert "assets" in package["files"]


def test_v10_gate_transition_and_continuation_order_are_exact() -> None:
    payload = _load_handoff()
    resolved = payload["resolved_gates"]
    opened = payload["open_gates"]
    resolved_by_uid = {item["uid"]: item["status"] for item in resolved}
    open_by_uid = {item["uid"]: item for item in opened}
    assert len(resolved_by_uid) == len(resolved)
    assert len(open_by_uid) == len(opened)
    assert resolved_by_uid.keys().isdisjoint(open_by_uid.keys())
    assert resolved_by_uid[
        "sym:Gate:hswm-s2s-current-run-replay-snapshot"
    ] == "ENGINEERING_CLEAR_RETAINED_BYTE_CONSISTENCY"
    assert resolved_by_uid[
        "sym:Gate:hswm-s2s-top-level-healthy-success-attachment-profile"
    ] == "ENGINEERING_CLEAR_NESTED_SEMANTICS_OPEN"
    assert set(open_by_uid) == {
        "sym:Blocker:hswm-s2s-complete-artifact-read-replay-trace",
        "sym:Blocker:hswm-s2s-full-registration-source-snapshot",
        "sym:Blocker:hswm-s2s-nested-replay-and-cross-attachment-semantics",
        "sym:Blocker:hswm-s2s-failure-unknown-and-void-profiles",
        "sym:Blocker:hswm-s2s-closed-stage-programs-and-upload-postconditions",
        "sym:Blocker:hswm-s2s-external-shared-durable-store-deployment",
        "sym:Blocker:hswm-s2s-workflow-source-bytes-and-api-path",
        "sym:Blocker:hswm-s2s-current-run-github-origin-and-genuine-issuance",
        "sym:Blocker:hswm-s2s-terminal-reobservation-and-rerun-invalidation",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    assert all(item["severity"] == "P0" for item in opened)
    assert payload["next_session_order"] == [
        "READ_CONSTITUTION_V10_HANDOFF_V10_KG_IMMUTABLE_V9_AND_EFFECT_SKILL",
        "PRESERVE_PROTECTED_CONTINUAL_LIVE_CHANGES_AND_TREAT_443F17F_AS_CODE_CHECKPOINT",
        "RETAIN_COMPLETE_BOUNDED_ARTIFACT_LOOKUP_TRACE_AND_SHARE_ONE_CURRENT_RUN_SERVICE",
        "IMPLEMENT_FULL_REGISTRATION_SOURCE_SNAPSHOT_AND_REPLAY_SCHEMAS",
        "BIND_PROFILE_VERSION_AND_VALIDATE_NESTED_AND_CROSS_ATTACHMENT_SEMANTICS",
        "FREEZE_FAILURE_INTERRUPTION_UNKNOWN_UPLOAD_AND_VOID_PROFILES",
        "IMPLEMENT_SIX_ROOT_PRIVATE_PREPARE_ASSERT_UPLOAD_PROGRAMS",
        "WIRE_REVIEWED_EXTERNAL_SHARED_DURABLE_ROOT_AND_RECONCILE_COMMITTED_READBACK_FAILURE",
        "IMPLEMENT_TERMINAL_REOBSERVATION_AND_RERUN_INVALIDATION",
        "AUTHOR_REVIEW_AND_PIN_WORKFLOW_BYTES_SOURCE_A_ROW_AND_ONE_API_PATH_LAST",
        "DO_NOT_CREATE_SOURCE_FREEZE_PREREG_BEACON_DISPATCH_CANDIDATE_ADJUDICATION_OR_EVENT_10_FOR_ENGINEERING_PROGRESS",
    ]


def test_v10_paths_hashes_verification_indexes_and_nonclaims_are_exact() -> None:
    payload = _load_handoff()
    latest_bindings = _latest_binding_hashes(payload)
    bindings = payload["artifact_bindings"]
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json" not in paths
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
    assert verification["effect_tests_final"] == "243/243 PASS"
    assert verification["effect_test_suites_final"] == "20/20 PASS"
    assert verification["focused_post_audit_tests"] == "49/49 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS_ASSET_INCLUDED"
    assert verification["scratch_cleanup"] == "PASS_NO_LONG_LIVED_WORKER"
    assert verification["independent_audit"] == (
        "TWO_CAP_BYPASSES_FOUND_AND_FIXED_NO_REMAINING_BLOCKER_IN_DECLARED_SCOPE"
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
    assert any("top-level healthy-success" in item for item in nonclaims)
    assert any("full registration source snapshot" in item for item in nonclaims)
    assert any("absence-pair" in item for item in nonclaims)
    assert any("not an enforced memory limit" in item for item in nonclaims)
    assert any("not a remote Neo4j" in item for item in nonclaims)
    assert any("no event-10" in item for item in nonclaims)


def test_v10_predecessor_is_immutable_and_successor_chain_is_unique() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)
    assert predecessor["bundle_uid"] == payload[
        "supersedes_bundle_uid_for_continuation"
    ]
    predecessor_binding = next(
        binding
        for binding in payload["artifact_bindings"]
        if binding["path"]
        == "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json"
    )
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        predecessor_binding["sha256"]
    )
    v9_successors = [
        candidate
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != PREDECESSOR_PATH
        if (candidate := _load_json(path)).get(
            "supersedes_bundle_uid_for_continuation"
        )
        == predecessor["bundle_uid"]
    ]
    assert [candidate["bundle_uid"] for candidate in v9_successors] == [
        payload["bundle_uid"]
    ]
    current_path = HANDOFF_PATH
    for successor in _successor_chain(payload):
        successor_bindings = successor["artifact_bindings"]
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
