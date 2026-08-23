from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json"
BRIDGE_PATH = (
    ROOT
    / "src/hswm/effect-runtime/src/s2s-stage-read-replay-durable-profile.ts"
)
RECOVERY_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-file.ts"
REPLAY_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts"
LIVE_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/s2s-live-artifact.test.ts"
PUBLIC_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/public-api.test.ts"
ROOT_INDEX_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
PACKAGE_PATH = ROOT / "src/hswm/effect-runtime/package.json"
V12_TEST_PATH = ROOT / "tests/test_hswm_swm0w_s2s_effect_handoff_v12.py"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V12_SHA256 = (
    "d1a959a1d9d3b976fc0171c97d3afb44765cd4830077a411b93e704844686888"
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


def test_v13_is_duplicate_key_safe_and_a_pi_only_engineering_checkpoint() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    payload = _load_handoff()
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v13"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-local-durable-replay-profile-integrated-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-stage-read-replay-core-implemented-2026-08-23"
    )
    assert payload["workspace_parent_commit"] == (
        "e8c9cd527be3b72b91c9acc093aeffcab41caa31"
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
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )

    for flag in (
        "stage_artifact_read_replay_core_implemented",
        "local_create_only_stage_read_replay_profile_attachment_integration",
        "recovery_authenticity_process_local_implemented",
        "single_selected_source_read_snapshot_implemented",
        "test_only_three_stage_dry_run_implemented",
    ):
        assert payload[flag] is True
    for flag in (
        "durable_artifact_read_replay_attachment_implemented",
        "complete_replay_attachment_profiles_closed",
        "production_stage_artifact_read_replay_emitted",
        "github_origin_stage_artifact_read_replay_observed",
        "full_registration_source_snapshot_implemented",
        "nested_replay_cross_attachment_semantics_closed",
        "failure_unknown_void_profiles_closed",
        "closed_stage_programs_implemented",
        "mandatory_upload_postconditions_implemented",
        "external_shared_durable_store_deployed",
        "external_durable_root_authenticated",
        "genuine_current_run_capability_issued",
        "genuine_stage_artifact_capability_issued",
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
        "F": "NO_CONFIRMATORY_FUNCTION_OR_NUMERIC_RESULT",
        "Pi": (
            "LOCAL_CREATE_ONLY_RESERVED_REPLAY_PROFILE_BINDING_AND_"
            "RECOVERY_PRESERVATION_IMPLEMENTED_COMPLETE_STAGE_"
            "COMPOSITION_AND_EXTERNAL_ORIGIN_OPEN"
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


def test_v13_source_contains_the_lazy_root_private_durable_bridge() -> None:
    bridge = BRIDGE_PATH.read_text(encoding="utf-8")
    recovery = RECOVERY_PATH.read_text(encoding="utf-8")
    replay = REPLAY_PATH.read_text(encoding="utf-8")
    public_test = PUBLIC_TEST_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")

    for literal in (
        "export const commitS2SStageReadReplayProfileAttachments",
        "Effect.suspend(() =>",
        "S2SDurableEvidenceFileStore",
        "isAuthenticS2SDurableEvidenceRecovery",
        '"PREDECESSOR_ENVELOPE_MISMATCH"',
        "validateS2SStageArtifactReadReplay",
        "validateS2SCandidateReadReplayPair",
        'logicalName: "input/registration_read.zip"',
        'operation: "CONFIRM_READ_REGISTRATION"',
        'operation: "ADJUDICATE_READ_CANDIDATE_FIRST"',
        'operation: "ADJUDICATE_REREAD_CANDIDATE"',
        'operation: "ADJUDICATE_READ_REGISTRATION"',
        "recoveredPublicationMatches",
    ):
        assert literal in bridge
    assert bridge.count("store.commit(") == 1
    assert "AUTHENTIC_DURABLE_EVIDENCE_RECOVERIES" in recovery
    assert "AUTHENTIC_DURABLE_EVIDENCE_RECOVERIES.add(recovery)" in recovery
    assert "snapshotSourceArchiveFromRecovery" in replay
    assert "validateDecodedReplayWithPreparedSource" in replay

    for private_name in (
        "commitS2SStageReadReplayProfileAttachments",
        "S2SStageReadReplayDurableProfileError",
        "isAuthenticS2SDurableEvidenceRecovery",
        "validateS2SCurrentRunStageEvidenceForArtifactReplay",
    ):
        assert private_name not in root_index
        assert f'"{private_name}" in PublicApi' in public_test
    assert "S2SStageReadReplayDurablePublication" not in root_index
    assert "S2SStageReadReplayDurablePublication" in public_test


def test_v13_real_local_store_regression_covers_the_exact_vertical_chain() -> None:
    test_source = LIVE_TEST_PATH.read_text(encoding="utf-8")
    for literal in (
        "preserves fully validated replay carriers through one create-only three-stage chain",
        "makeS2SDurableEvidenceFileStoreLayer(durableRoot)",
        'left: { reason: "PREDECESSOR_ENVELOPE_MISMATCH" }',
        'left: { reason: "REPLAY_OPERATION_MISMATCH" }',
        '"StageReadReplayProfileCommitted"',
        '"StageReadReplayProfileAlreadyCommitted"',
        '["REGISTER", "CONFIRM", "ADJUDICATE"]',
        "isAuthenticS2SDurableEvidenceRecovery(restarted)",
        "accessor input must remain inert",
    ):
        assert literal in test_source

    vertical = _load_handoff()["implemented_boundaries"]["local_vertical_test"]
    assert vertical["authority"] == "TEST_ONLY_NON_AUTHORIZING"
    assert vertical["store"] == "ACTUAL_LOCAL_CREATE_ONLY_FILE_STORE_LAYER"
    assert vertical["stage_chain"] == ["REGISTER", "CONFIRM", "ADJUDICATE"]
    assert vertical["layer_restart_recovery"] is True
    assert vertical["other_profile_attachment_semantics_validated"] is False


def test_v13_resolved_and_open_gates_preserve_the_occam_boundary() -> None:
    payload = _load_handoff()
    resolved = {gate["uid"]: gate for gate in payload["resolved_gates"]}
    assert set(resolved) == {
        "sym:ResolvedGate:s2s-file-recovery-process-local-provenance",
        "sym:ResolvedGate:s2s-selected-source-single-snapshot",
        "sym:ResolvedGate:s2s-local-replay-profile-create-only-binding",
        "sym:ResolvedGate:s2s-local-three-stage-recovery-preservation",
    }
    assert all(gate["status"] == "ENGINEERING_CLEAR" for gate in resolved.values())

    open_gates = {gate["uid"]: gate for gate in payload["open_gates"]}
    assert {
        "sym:OpenGate:s2s-thin-golden-stage-composition",
        "sym:OpenGate:s2s-other-nested-profile-semantics",
        "sym:OpenGate:s2s-closed-stage-programs-and-upload-postconditions",
        "sym:OpenGate:s2s-external-durable-root-and-github-origin",
        "sym:OpenGate:s2s-workflow-source-prereg-and-future-seed",
        "sym:OpenGate:s2s-scientific-qbr-verdict",
    } <= set(open_gates)
    assert all(gate["status"] == "OPEN" for gate in open_gates.values())

    audit = payload["critical_path_audit"]
    assert audit["target_identity"] == "CONSTITUTIONAL_H_W_A_F_PI_LOOP_UNCHANGED"
    assert audit["current_numeric_core"] == (
        "T16_P_CAP18_DS870_ROLE_AWARE_S2S_ENGINEERING_IMPLEMENTED"
    )
    assert audit["current_scientific_status"] == "UNJUDGED"
    assert audit["next_claim_critical_slice"] == (
        "ONE_NON_AUTHORIZING_GOLDEN_PUBLIC_SEED_NUMERIC_ORACLE_TO_"
        "MANDATORY_UPLOAD_READBACK_DRY_RUN"
    )
    assert audit["generalized_hostile_matrix"] == (
        "DEFER_UNLESS_VERTICAL_SLICE_EXPOSES_CONCRETE_FAILURE"
    )

    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_V13_HANDOFF_V13_KG_IMMUTABLE_V12_AND_EFFECT_SKILL"
    )
    assert order[2] == (
        "COMPOSE_ONE_NON_AUTHORIZING_GOLDEN_PUBLIC_SEED_NUMERIC_ORACLE_TO_"
        "LOCAL_UPLOAD_READBACK_VERTICAL_PATH"
    )
    assert order[-1] == (
        "DO_NOT_FREEZE_PREREGISTER_SELECT_FUTURE_SEED_DISPATCH_OR_VERDICT_"
        "FOR_ENGINEERING_PROGRESS"
    )

    nonclaims = payload["nonclaims"]
    assert any("not a complete stage program" in item for item in nonclaims)
    assert any("not cross-process authentication" in item for item in nonclaims)
    assert any("not GitHub-origin" in item for item in nonclaims)
    assert any("not HSWM cognition" in item for item in nonclaims)
    assert any("no source freeze" in item for item in nonclaims)
    assert any("outcome-bound causal-learning loop" in item for item in nonclaims)


def test_v13_bindings_pin_v12_and_rebind_all_changed_checkpoint_surfaces() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)
    latest_bindings = _latest_binding_hashes(payload)
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V12_SHA256
    )
    assert predecessor["bundle_uid"] == payload[
        "supersedes_bundle_uid_for_continuation"
    ]

    bindings = payload["artifact_bindings"]
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    required_paths = {
        "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json",
        payload["handoff_path"],
        "src/hswm/effect-runtime/src/s2s-evidence-file.ts",
        "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts",
        "src/hswm/effect-runtime/src/s2s-stage-read-replay-durable-profile.ts",
        "src/hswm/effect-runtime/test/public-api.test.ts",
        "src/hswm/effect-runtime/test/s2s-evidence-file.test.ts",
        "src/hswm/effect-runtime/test/s2s-live-artifact.test.ts",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v12.py",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v13.py",
    }
    assert required_paths <= set(paths)
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json" not in paths
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

    predecessor_binding = next(
        binding
        for binding in bindings
        if binding["path"] == PREDECESSOR_PATH.relative_to(ROOT).as_posix()
    )
    assert predecessor_binding["sha256"] == IMMUTABLE_V12_SHA256
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
    assert "_latest_binding_hashes" in V12_TEST_PATH.read_text(encoding="utf-8")


def test_v13_indexes_versions_and_verification_are_exact() -> None:
    payload = _load_handoff()
    verification = payload["verification"]
    assert verification["effect_tests_final"] == "263/263 PASS"
    assert verification["effect_test_suites_final"] == "21/21 PASS"
    assert verification["focused_durable_replay_profile_tests"] == "34/34 PASS"
    assert verification["focused_test_suites"] == "3/3 PASS"
    assert verification["v13_kg_tests"] == "6/6 PASS"
    assert verification["v1_through_v13_handoff_chain_tests"] == "62/62 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS_NEW_INTERNAL_MODULE_INCLUDED"
    assert verification["diff_check"] == "PASS"
    assert verification["independent_reaudit"] == "GO_NO_COMMIT_BLOCKING_P0"
    assert "no production stage program" in verification["claim_boundary"]
    assert "no GitHub-origin evidence" in verification["claim_boundary"]
    assert "no scientific verdict" in verification["claim_boundary"]

    assert payload["frozen_versions"] == {
        "typescript": "5.9.3",
        "effect": "3.22.1",
        "node": "24.13.0",
        "vitest": "3.2.7",
    }

    handoff_name = Path(payload["handoff_path"]).name
    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        text = index_path.read_text(encoding="utf-8")
        assert "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v13.json" in text
        assert handoff_name in text

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
