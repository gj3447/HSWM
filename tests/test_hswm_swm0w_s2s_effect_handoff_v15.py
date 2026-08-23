from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_GOLDEN_VERTICAL_COMPOSITION_IMPLEMENTED_"
    "NEXT_SESSION_2026-08-23.md"
)
UPLOAD_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-test-only-golden-upload.ts"
)
STORE_PATH = (
    ROOT
    / "src/hswm/effect-runtime/src/s2s-test-only-golden-artifact-store.ts"
)
COMPOSITION_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-golden-numeric-dry-run.ts"
)
ROOT_INDEX_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V14_SHA256 = (
    "fd9816501dc44feaf2d580bfd4f9e2454501643f6ccd0476668161725abc5be0"
)
CODE_COMMIT = "6ae27edb13b37985d0987b3b2b64bb9ec7efded3"
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


def test_v15_is_duplicate_key_safe_pi_only_implementation_checkpoint() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    payload = _load_handoff()
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v15"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-test-only-golden-local-vertical-composition-"
        "implemented-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringDesignCheckpoint:"
        "hswm-swm0w-s2s-golden-local-vertical-composition-2026-08-23"
    )
    assert payload["workspace_parent_commit"] == (
        "579e3f2828d029a8e782eba0462197a686058d13"
    )
    assert payload["workspace_primary_implementation_commit"] == CODE_COMMIT
    assert payload["workspace_code_commit"] == CODE_COMMIT
    assert payload["workspace_head_before_v15_handoff_finalization"] == (
        "029c50c06728d9f2c23e1e7376dc9d3f4103f593"
    )
    assert payload["separately_committed_unrelated_change"] == {
        "commit": "029c50c06728d9f2c23e1e7376dc9d3f4103f593",
        "parent": CODE_COMMIT,
        "subject": "chore(codex): harden HSWM MCP and research skill",
        "affects_golden_implementation": False,
        "paths": [
            ".codex/config.toml",
            ".agents/skills/hswm-research-readout/SKILL.md",
            ".agents/skills/hswm-research-readout/agents/openai.yaml",
        ],
    }
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )
    skill = payload["effect_skill_influence"]
    assert skill == {
        "version_route": "EFFECT_3_22_1_V3",
        "architecture_route": "FUNCTIONAL_CORE_EFFECT_SHELL",
        "service_model": "CONTEXT_TAG_AND_LAYER",
        "composition_model": "LAZY_EFFECT_WITH_REQUIRED_ENVIRONMENT",
        "failure_model": "TYPED_TAGGED_ERRORS_NO_DEFECT_RECOVERY_CLAIM",
        "resource_model": (
            "SCOPED_LAYERS_SEMAPHORE_SERIALIZATION_AND_INTERRUPTIBLE_"
            "PROCESS_LIFETIMES"
        ),
        "verification_model": (
            "EFFECT_VITEST_STRICT_TYPESCRIPT_BUILD_AND_PACK"
        ),
        "verification_influence_only_not_runtime_dependency": True,
    }

    for flag in (
        "golden_local_vertical_composition_implemented",
        "local_test_only_golden_artifact_store_implemented",
        "test_only_golden_upload_postcondition_schema_implemented",
        "local_test_only_upload_readback_vertical_slice_implemented",
        "golden_verifier_executor_runtime_exact_binding_implemented",
        "void_immediate_terminal_branch_implemented",
        "fresh_same_root_layer_recovery_implemented",
        "root_private_public_export_containment_implemented",
        "live_golden_success_candidate_observed",
        "live_golden_success_adjudication_observed",
    ):
        assert payload[flag] is True
    for flag in (
        "production_carriers_accept_local_test_receipts",
        "stage_upload_postcondition_schema_implemented",
        "mandatory_upload_postconditions_implemented",
        "all_healthy_success_attachment_occurrences_real",
        "complete_replay_attachment_profiles_closed",
        "full_registration_source_snapshot_implemented",
        "nested_replay_cross_attachment_semantics_closed",
        "failure_unknown_void_profiles_closed",
        "closed_stage_programs_implemented",
        "production_terminal_finalizer_implemented",
        "external_shared_durable_store_deployed",
        "external_durable_root_authenticated",
        "independent_process_restart_recovery_observed",
        "genuine_current_run_capability_issued",
        "genuine_stage_artifact_capability_issued",
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
        "F": (
            "UNCHANGED_NO_CONFIRMATORY_FUNCTION_OR_SCIENTIFIC_RESULT_"
            "TEST_ONLY_NUMERIC_CELL_EXERCISED"
        ),
        "Pi": (
            "LOCAL_TEST_ONLY_GOLDEN_ARTIFACT_POSTCONDITION_CREATE_ONLY_UPLOAD_"
            "TWO_CANDIDATE_READBACKS_FRESH_SAME_ROOT_LAYER_RECOVERY_AND_ROOT_"
            "PRIVATE_NUMERIC_COMPOSITION_IMPLEMENTED_PRODUCTION_BOUNDARIES_OPEN"
        ),
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }


def test_v15_codec_and_store_contracts_are_exact_and_non_production() -> None:
    payload = _load_handoff()
    codec = payload["test_only_golden_upload_contract"]
    store = payload["test_only_golden_artifact_store"]
    upload_source = UPLOAD_PATH.read_text(encoding="utf-8")
    store_source = STORE_PATH.read_text(encoding="utf-8")

    assert codec["schema_version"] == (
        "hswm-swm0w-s2s-test-only-golden-upload-postcondition/v1"
    )
    assert codec["classification"] == "TEST_ONLY_NON_AUTHORIZING"
    assert codec["origin"] == "LOCAL_TEST_LAYER"
    assert codec["roles"] == ["GOLDEN_CANDIDATE", "GOLDEN_ADJUDICATION"]
    assert codec["candidate"] == {
        "publication_key": "s2s-test-only-golden-candidate.zip",
        "postcondition_publication_key": (
            "s2s-test-only-golden-candidate-upload-postcondition.zip"
        ),
        "member_name": "numeric_candidate.json",
        "member_maximum_bytes": 60 * 1_048_576,
        "archive_maximum_bytes": 64 * 1_048_576,
    }
    assert codec["adjudication"] == {
        "publication_key": "s2s-test-only-golden-adjudication.zip",
        "postcondition_publication_key": (
            "s2s-test-only-golden-adjudication-upload-postcondition.zip"
        ),
        "member_name": "numeric_adjudication.json",
        "member_maximum_bytes": 3 * 1_048_576,
        "archive_maximum_bytes": 4 * 1_048_576,
    }
    assert codec["postcondition_member_maximum_bytes"] == 4 * 1_024
    assert codec["postcondition_archive_maximum_bytes"] == 8 * 1_024

    assert store["root_contract"] == (
        "PREEXISTING_CALLER_OWNED_ABSOLUTE_NON_SYMLINK_EXACT_0700_DEVICE_"
        "INODE_BOUND"
    )
    assert store["publication_contract"] == (
        "FIXED_0400_FILES_ONE_HARD_LINK_CREATE_ONLY_ATTEMPT_FSYNC_NO_RETRY"
    )
    assert store["methods"] == [
        "publishGoldenArtifact",
        "readBackGoldenArtifact",
        "recoverGoldenArtifactWithFreshLayer",
    ]
    assert set(store["typed_failure_reasons"]) == {
        "ROOT_UNSAFE",
        "PUBLISH_FAILED",
        "PUBLICATION_OUTCOME_UNKNOWN",
        "READBACK_FAILED",
        "READBACK_MISMATCH",
        "POSTCONDITION_INVALID",
        "RECOVERY_MISMATCH",
        "CREATE_ONLY_CONFLICT",
    }
    assert store["receipt_authenticity"] == "PROCESS_LOCAL_WEAKMAP_MODULE_ISSUED"
    assert store["fresh_recovery_scope"] == (
        "NEW_FILE_LAYER_SAME_EXPLICIT_ROOT_SAME_PROCESS_MODULE_AUTHORITY"
    )
    assert payload["design_delta_from_v14"] == {
        "reason": (
            "V14_REQUIRED_GENUINELY_FRESH_LAYER_RECOVERY_WHILE_DESCRIBING_"
            "ONLY_PUBLISH_AND_READBACK_METHODS"
        ),
        "minimal_resolution": (
            "ADD_RECOVER_GOLDEN_ARTIFACT_WITH_FRESH_LAYER_METHOD_THAT_BUILDS_"
            "A_NEW_FILE_LAYER_OVER_THE_SAME_EXPLICIT_ROOT_PER_CALL"
        ),
        "production_scope_expanded": False,
        "root_export_added": False,
        "authority_weakened": False,
    }

    for literal in (
        codec["schema_version"],
        codec["candidate"]["publication_key"],
        codec["adjudication"]["publication_key"],
        'Schema.Literal(\n  "GOLDEN_CANDIDATE",\n  "GOLDEN_ADJUDICATION"',
    ):
        assert literal in upload_source
    for literal in (
        "new WeakMap<object, ReceiptAuthority>()",
        "recoverGoldenArtifactWithFreshLayer",
        "makeS2STestOnlyGoldenArtifactStoreFileLayer",
        '"PUBLICATION_OUTCOME_UNKNOWN"',
        '"CREATE_ONLY_CONFLICT"',
    ):
        assert literal in store_source


def test_v15_root_private_composition_and_live_observation_are_exact() -> None:
    payload = _load_handoff()
    composition = payload["golden_numeric_composition"]
    observation = payload["live_golden_observation"]
    result = observation["result"]
    source = COMPOSITION_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")

    assert composition["entrypoint"] == "runS2SGoldenNumericDryRun"
    assert composition["root_package_exported"] is False
    assert composition["candidate_second_readback_feeds_adjudication"] is True
    assert composition["void_policy"] == (
        "IMMEDIATE_TYPED_TERMINAL_BEFORE_ADJUDICATION_EVIDENCE_BIND_OR_"
        "ADJUDICATION_UPLOAD"
    )
    assert composition["production_job_sequence_used"] is False
    assert composition["production_events_or_profiles_created"] is False
    assert "runS2SGoldenNumericDryRun" not in root_index
    for literal in (
        "const verification = yield* verifier.verify",
        'executor.confirm(',
        "const candidateFirst = yield* store.readBackGoldenArtifact",
        "const candidateSecond = yield* store.readBackGoldenArtifact",
        "recoverGoldenArtifactWithFreshLayer(candidateReceipt)",
        "const adjudicationInput = Uint8Array.from(",
        "projectOpaqueNumericAdjudication(",
        'projection.left.reason === "NUMERIC_OUTCOME_VOID"',
        "recoverGoldenArtifactWithFreshLayer(adjudicationReceipt)",
    ):
        assert literal in source

    assert observation["discriminant"] == "COMPLETED_NON_VOID"
    assert observation["source_class"] == (
        "LOCAL_CODEX_SESSION_JSONL_COMMAND_EXECUTION"
    )
    assert observation["command_execution_id"] == (
        "exec-ffc19ae0-2c38-4364-9c11-0868c97f68ff"
    )
    assert observation["process_id"] == "54735"
    assert observation["capture_recovery_status"] == (
        "EXACT_COMMAND_EXECUTION_STDOUT_RECOVERED_FROM_LOCAL_CODEX_SESSION_JSONL"
    )
    assert observation["initial_final_output_handoff_capture"] == (
        "MISSED_THEN_RECOVERED"
    )
    assert observation["workload_rerun"] is False
    assert observation["source_record_repository_bound"] is False
    assert observation["launch_request_recorded_at"] == (
        "2026-08-23T05:19:18.299Z"
    )
    assert observation["command_execution_completed_at"] == (
        "2026-08-23T06:45:02.374Z"
    )
    assert observation["duration_seconds"] == "5143.758772480"
    assert observation["command_execution_status"] == "completed"
    assert observation["exit_code"] == 0
    assert observation["stderr_byte_length"] == 0
    assert observation["command_source_byte_length"] == 2741
    assert observation["command_source_sha256"] == (
        "c752074c36d84f32860aa3888ad069da28e0b7647ed54e5abc546be14b3f9a5f"
    )
    assert observation["result_json_line_with_lf_byte_length"] == 2496
    assert observation["result_json_line_with_lf_sha256"] == (
        "f3e7f2f40a43d81cc76664358c607216a7511a7729c54cb7b8be52d14c612de1"
    )
    assert observation["whole_stdout_byte_length"] == 2961
    assert observation["whole_stdout_sha256"] == (
        "dcba1356fa5c36d12c7401c1b7fcbb77b580869e4362eee46b90ef7924398e21"
    )
    assert observation["code_commit"] == CODE_COMMIT
    assert observation["artifact_bytes_retained"] is False
    assert observation["raw_local_archives_retained"] is False
    assert observation["production_authority_created"] is False

    assert result["_tag"] == "S2SGoldenNumericDryRunCompleted"
    assert result["classification"] == "TEST_ONLY_NON_AUTHORIZING"
    assert result["origin"] == "LOCAL_TEST_LAYER"
    assert result["scientificStatus"] == "NUMERIC_CANDIDATE_ONLY_UNJUDGED"
    assert result["numericCandidateOutcome"] == "CANDIDATE_PASS_AWAITING_BUNDLE"
    assert result["numericCandidateReasonCodes"] == [
        "CANDIDATE_Q_B_R_LCBS_MEET_GATES"
    ]
    candidate_sha256 = result["candidateArtifact"]["memberRawSha256"]
    assert candidate_sha256 == result["confirm"]["outputRawBytesSha256"]
    assert candidate_sha256 == result["adjudicate"]["inputRawBytesSha256"]
    assert result["adjudicationArtifact"]["memberRawSha256"] == result[
        "adjudicate"
    ]["outputRawBytesSha256"]
    assert result["confirm"]["runtimeSourceIdentityReceiptSha256"] == result[
        "adjudicate"
    ]["runtimeSourceIdentityReceiptSha256"]
    assert result["confirm"]["runtimeSourceIdentityReceiptSha256"] == (
        "6bf549e41c71b6c6b08f9808f5a9977002c26f166b383b162823598e09120c7e"
    )

    start_line = (
        json.dumps(
            observation["start_event"],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )
    result_line = (
        json.dumps(result, ensure_ascii=True, separators=(",", ":")).encode(
            "ascii"
        )
        + b"\n"
    )
    assert len(start_line) == 465
    assert len(result_line) == observation["result_json_line_with_lf_byte_length"]
    assert hashlib.sha256(result_line).hexdigest() == observation[
        "result_json_line_with_lf_sha256"
    ]
    stdout = start_line + result_line
    assert len(stdout) == observation["whole_stdout_byte_length"]
    assert hashlib.sha256(stdout).hexdigest() == observation[
        "whole_stdout_sha256"
    ]


def test_v15_inventory_open_gates_and_nonclaims_remain_narrow() -> None:
    payload = _load_handoff()
    inventory = payload["healthy_success_profile_inventory"]
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
    assert inventory["test_only_golden_artifacts_count_as_production_slots"] is False

    open_gates = {gate["uid"]: gate for gate in payload["open_gates"]}
    assert {
        "sym:OpenGate:s2s-production-carrier-semantic-connector",
        "sym:OpenGate:s2s-stage-upload-postconditions",
        "sym:OpenGate:s2s-complete-healthy-success-profiles",
        "sym:OpenGate:s2s-production-terminal-finalizer",
        "sym:OpenGate:s2s-external-durable-root-and-github-origin",
        "sym:OpenGate:s2s-workflow-source-prereg-and-future-seed",
        "sym:OpenGate:s2s-scientific-qbr-verdict",
    } <= set(open_gates)
    assert all(gate["status"] == "OPEN" for gate in open_gates.values())

    nonclaims = payload["nonclaims"]
    for phrase in (
        "not a production confirmatory event",
        "not a complete healthy-success profile",
        "not external durability",
        "not independent-process restart recovery",
        "not GitHub-origin evidence",
        "not preregistration",
        "not a scientific verdict",
        "not HSWM cognition",
        "outcome-bound causal-learning loop did not advance",
    ):
        assert any(phrase in item for item in nonclaims)

    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_V15_HANDOFF_V15_KG_IMMUTABLE_V14_AND_EFFECT_SKILL"
    )
    assert any("DO_NOT_RELABEL_LOCAL_TEST_RECEIPTS" in item for item in order)
    assert order[-1] == (
        "DO_NOT_FREEZE_PREREGISTER_SELECT_FUTURE_SEED_DISPATCH_COMPOSE_"
        "EVENT_10_OR_JUDGE_QBR_FOR_ENGINEERING_PROGRESS"
    )


def test_v15_graph_is_connected_without_scientific_evidence_edges() -> None:
    payload = _load_handoff()
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
    checkpoint = payload["bundle_uid"]
    touched = {
        relation["to_uid"]
        for relation in relations
        if relation["from_uid"] == checkpoint
    }
    assert {
        "sym:CanonicalTarget:hswm-constitution-2026-08-20",
        "sym:CodeCheckpoint:6ae27edb13b37985d0987b3b2b64bb9ec7efded3",
        "sym:EngineeringObservation:s2s-test-only-golden-completed-non-void",
    } <= touched


def test_v15_bindings_indexes_verification_and_successor_compatibility() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)
    latest_bindings = _latest_binding_hashes(payload)
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V14_SHA256
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
        "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v14.json",
        payload["handoff_path"],
        "docs/canon/HSWM_CONSTITUTION_2026-08-20.md",
        "src/hswm/effect-runtime/src/s2s-test-only-golden-upload.ts",
        "src/hswm/effect-runtime/src/s2s-test-only-golden-artifact-store.ts",
        "src/hswm/effect-runtime/src/s2s-golden-numeric-dry-run.ts",
        "src/hswm/effect-runtime/test/s2s-test-only-golden-upload.test.ts",
        "src/hswm/effect-runtime/test/s2s-test-only-golden-artifact-store.test.ts",
        "src/hswm/effect-runtime/test/s2s-golden-numeric-dry-run.test.ts",
        "README.md",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v14.py",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v15.py",
    }
    assert required_paths <= set(paths)
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json" not in paths
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
    assert verification["effect_tests_final"] == "287/287 PASS"
    assert verification["effect_test_suites_final"] == "24/24 PASS"
    assert verification["focused_new_effect_tests"] == "24/24 PASS"
    assert verification["v15_kg_tests"] == "6/6 PASS"
    assert verification["v1_through_v15_handoff_chain_tests"] == "73/73 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS"
    assert verification["live_golden_run"] == "COMPLETED_NON_VOID_EXIT_0"
    assert verification["independent_reaudit"] == "GO_NO_P0_P1_P2"
    assert verification["diff_check"] == "PASS"
    assert verification["separately_committed_unrelated_change_preserved"] == (
        "PASS"
    )
    assert "no production lifecycle authority" in verification["claim_boundary"]
    assert "no scientific verdict" in verification["claim_boundary"]

    handoff_name = Path(payload["handoff_path"]).name
    for index_path in (
        ROOT / "README.md",
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        text = index_path.read_text(encoding="utf-8")
        assert "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json" in text
        assert handoff_name in text

    assert "_latest_binding_hashes" in (
        ROOT / "tests/test_hswm_swm0w_s2s_effect_handoff_v14.py"
    ).read_text(encoding="utf-8")
    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
