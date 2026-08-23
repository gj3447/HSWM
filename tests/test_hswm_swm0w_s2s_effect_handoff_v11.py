from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v10.json"
SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-live-artifact.ts"
GITHUB_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-live-github.ts"
TRACE_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/s2s-live-artifact.test.ts"
GITHUB_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/s2s-live-github.test.ts"
LAYER_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/s2s-run-authority.test.ts"
ROOT_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/public-api.test.ts"
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


def test_v11_is_a_pi_engineering_checkpoint_not_a_scientific_verdict() -> None:
    payload = _load_handoff()
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v11"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-lookup-trace-shared-layer-implemented-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-replay-prerequisites-implemented-2026-08-23"
    )
    assert payload["workspace_parent_commit"] == (
        "9bd414c5fc063c5ff57afcf745ebaa28c7c13a64"
    )
    assert payload["workspace_primary_implementation_commit"] == (
        "84f9eb663759f100193c4b77145fd372de8549b9"
    )
    assert payload["workspace_code_commit"] == (
        "91b1153bb496737a4c1163b417efc833f74e1418"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["successful_artifact_lookup_trace_implemented"] is True
    assert payload["shared_current_run_stage_layer_implemented"] is True
    assert payload["legacy_stage_artifact_reads_layer_signature_compatible"] is True
    for flag in (
        "durable_artifact_read_replay_attachment_implemented",
        "live_shared_bearer_observed",
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
            "COMPLETE_BOUNDED_SUCCESSFUL_LOOKUP_RAW_TRACE_AND_ONE_CURRENT_RUN_"
            "COMBINED_LAYER_IMPLEMENTED_DURABLE_REPLAY_FORMAT_AND_STAGE_PROGRAMS_OPEN"
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


def test_v11_trace_and_shared_layer_boundaries_are_exact() -> None:
    boundaries = _load_handoff()["implemented_boundaries"]
    assert boundaries["successful_artifact_lookup_trace"] == {
        "status": (
            "ENGINEERING_CLEAR_BOUNDED_RAW_SUCCESS_PATH_RETENTION_"
            "NOT_DURABLE_REPLAY_ATTACHMENT"
        ),
        "module": "src/hswm/effect-runtime/src/s2s-live-artifact.ts",
        "result_type": "S2SValidatedStageArtifactRead",
        "field": "successfulLookupTrace",
        "schema_version": (
            "hswm-swm0w-s2s-artifact-successful-lookup-trace/v1"
        ),
        "root_package_exported": False,
        "successful_attempt_ordinals": [1, 2, 3],
        "fixed_observations": ["INITIAL_WORKFLOW_RUN", "WORKFLOW_JOBS"],
        "per_attempt_observations": ["RUN_ARTIFACTS", "WORKFLOW_RUN"],
        "prior_absence_attempts_retained_on_later_success": True,
        "classification_sequence_exact": True,
        "trace_tuple_attempts_frozen": True,
        "defensive_raw_body_reads": True,
        "permit_retry_or_replenishment_added": False,
        "durably_serialized": False,
        "aggregate_self_hash_present": False,
        "cross_attachment_bound": False,
    }
    assert boundaries["shared_current_run_and_artifact_reads_layer"] == {
        "status": "ENGINEERING_CLEAR_CLOSED_GRAPH_DORMANT",
        "module": "src/hswm/effect-runtime/src/s2s-live-artifact.ts",
        "factory": "makeS2SCurrentRunAndStageArtifactReadsLiveLayer",
        "composition": (
            "ONE_CURRENT_RUN_LAYER_NODE_SEQUENTIALLY_SHARED_VIA_"
            "LAYER_PROVIDE_MERGE"
        ),
        "sharing_scope": "ONE_RETURNED_COMBINED_LAYER_BUILD_MEMO_MAP_AND_SCOPE",
        "separate_builds_share": False,
        "separate_builds_may_attempt_reacquisition": True,
        "successful_reuse_claimed": False,
        "requirements": "never",
        "outputs_exact": ["S2SCurrentRunStage", "S2SStageArtifactReads"],
        "constructor_arity": 2,
        "observer_override_parameter": False,
        "root_package_exported": False,
        "legacy_factory": "makeS2SStageArtifactReadsLiveLayer",
        "legacy_requirements": "never",
        "legacy_output_exact": "S2SStageArtifactReads",
        "legacy_constructor_arity": 2,
        "workflow_source_open_failure_precedes_artifact_io": True,
        "live_successfully_built": False,
        "cross_process_singleton_claimed": False,
    }
    assert boundaries["package_root_containment"] == {
        "status": "ENGINEERING_CLEAR",
        "package_exports": ["."],
        "trace_types_exported_from_root": False,
        "combined_layer_exported_from_root": False,
        "validated_read_types_exported_from_root": False,
        "permit_mutators_exported_from_root": False,
    }
    assert boundaries["github_json_metadata_cap"] == {
        "status": "ENGINEERING_CLEAR_EXACT_BOUNDARY_REGRESSION",
        "module": "src/hswm/effect-runtime/src/s2s-live-github.ts",
        "maximum_bytes": 1_048_576,
        "exact_maximum_valid_padded_json_accepted": True,
        "maximum_plus_one_rejected": True,
        "aggregate_replay_fit_claimed": False,
    }


def test_v11_source_contains_the_trace_and_one_node_layer_graph() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    github_source = GITHUB_SOURCE_PATH.read_text(encoding="utf-8")
    trace_test = TRACE_TEST_PATH.read_text(encoding="utf-8")
    github_test = GITHUB_TEST_PATH.read_text(encoding="utf-8")
    layer_test = LAYER_TEST_PATH.read_text(encoding="utf-8")
    root_test = ROOT_TEST_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")
    package = _load_json(PACKAGE_PATH)

    for literal in (
        '"hswm-swm0w-s2s-artifact-successful-lookup-trace/v1"',
        "S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_MAX_RAW_BYTES",
        "successfulLookupTrace: makeSuccessfulLookupTrace(pairs, classified)",
        "successfulAttemptOrdinal: 1 as const",
        "successfulAttemptOrdinal: 2 as const",
        "successfulAttemptOrdinal: 3 as const",
        "makeS2SCurrentRunAndStageArtifactReadsLiveLayer",
        "Layer.provideMerge(currentRunLive)",
        "Layer.provide(currentRunLive)",
    ):
        assert literal in source
    assert 'positivePoll?: 1 | 2 | 3 | null' in trace_test
    assert "complete bounded raw lookup trace" in trace_test
    assert "Aggregate replay owns a separate total budget" in github_source
    assert "pins the exact one-MiB GitHub JSON acceptance boundary" in github_test
    assert "S2S_GITHUB_JSON_MAX_BYTES + 1" in github_test
    assert "SHARED_STAGE_LAYER_OUTPUT_IS_EXACT" in layer_test
    assert "makeS2SCurrentRunAndStageArtifactReadsLiveLayer" in root_test
    for private_name in (
        "S2SStageArtifactReads",
        "S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION",
        "makeS2SCurrentRunAndStageArtifactReadsLiveLayer",
        "claimS2SStageArtifactPermitScope",
    ):
        assert private_name not in root_index
    assert package["exports"] == {
        ".": {"types": "./dist/index.d.ts", "default": "./dist/index.js"}
    }


def test_v11_byte_budget_contradiction_is_explicit_and_arithmetic_is_exact() -> None:
    budgets = _load_handoff()["byte_budgets"]
    mib = 1_048_576
    lookup = budgets["successful_lookup_trace"]
    assert budgets["github_json_each"] == mib
    assert lookup == {
        "fixed_observation_count": 2,
        "maximum_attempt_count": 3,
        "observations_per_attempt": 2,
        "maximum_observation_count": 8,
        "maximum_raw_body_bytes": 8 * mib,
        "ordinal_maximum_raw_body_bytes": {
            "1": 4 * mib,
            "2": 6 * mib,
            "3": 8 * mib,
        },
        "counts_receipt_raw_body_lengths_only": True,
        "receipt_json_zip_framing_and_downloaded_archive_bytes_excluded": True,
    }
    assert lookup["maximum_observation_count"] == (
        lookup["fixed_observation_count"]
        + lookup["maximum_attempt_count"] * lookup["observations_per_attempt"]
    )
    assert budgets["validated_read_derived_maximum_json_body_count"] == 11
    assert budgets["validated_read_derived_maximum_json_body_bytes"] == 11 * mib
    assert budgets["registration_read_raw_component_maximum_before_framing_bytes"] == (
        15 * mib
    )
    assert budgets["candidate_read_raw_component_maximum_before_framing_bytes"] == (
        75 * mib
    )
    assert budgets["candidate_over_profile_before_framing_bytes"] == 59 * mib
    assert budgets["candidate_over_envelope_attachment_before_framing_bytes"] == (
        11 * mib
    )
    assert budgets["stage_read_replay_profile_bytes"] == 16 * mib
    assert budgets["evidence_attachment_bytes"] == 64 * mib
    assert budgets["evidence_total_attachment_bytes"] == 256 * mib
    assert budgets["budget_reconciliation_status"] == (
        "P0_OPEN_REPRESENTATION_OR_CAP_DECISION_REQUIRED"
    )


def test_v11_gate_transition_order_and_nonclaims_are_exact() -> None:
    payload = _load_handoff()
    resolved = payload["resolved_gates"]
    opened = payload["open_gates"]
    resolved_by_uid = {item["uid"]: item["status"] for item in resolved}
    open_by_uid = {item["uid"]: item for item in opened}
    assert len(resolved_by_uid) == len(resolved)
    assert len(open_by_uid) == len(opened)
    assert resolved_by_uid.keys().isdisjoint(open_by_uid.keys())
    assert resolved_by_uid == {
        "sym:Gate:hswm-s2s-bounded-successful-artifact-lookup-trace": (
            "ENGINEERING_CLEAR_RAW_HISTORY_RETAINED_NOT_DURABLE_ENCODING"
        ),
        "sym:Gate:hswm-s2s-shared-current-run-stage-layer": (
            "ENGINEERING_CLEAR_ONE_LAYER_NODE_PER_COMBINED_BUILD_GRAPH_DORMANT"
        ),
        "sym:Gate:hswm-s2s-stage-artifact-reads-layer-compatibility": (
            "ENGINEERING_CLEAR_REQUIREMENTS_OUTPUT_AND_ARITY_PRESERVED"
        ),
    }
    assert all(item["severity"] == "P0" for item in opened)
    for uid in (
        "sym:Blocker:hswm-s2s-stage-artifact-read-replay-byte-budget",
        "sym:Blocker:hswm-s2s-durable-artifact-read-replay-encoding-and-bindings",
        "sym:Blocker:hswm-s2s-artifact-read-replay-hostile-and-phase-matrix",
        "sym:Blocker:hswm-s2s-full-registration-source-snapshot",
        "sym:Blocker:hswm-s2s-closed-stage-programs-and-upload-postconditions",
        "sym:Blocker:hswm-s2s-workflow-source-bytes-and-api-path",
    ):
        assert uid in open_by_uid
    assert payload["next_session_order"][:5] == [
        "READ_CONSTITUTION_V11_HANDOFF_V11_KG_IMMUTABLE_V10_AND_EFFECT_SKILL",
        "PRESERVE_PROTECTED_CONTINUAL_LIVE_CHANGES_AND_TREAT_91B1153_AS_CODE_CHECKPOINT",
        "FREEZE_STAGE_ARTIFACT_READ_REPLAY_REPRESENTATION_AND_COHERENT_WORST_CASE_BYTE_BUDGETS",
        "IMPLEMENT_UNKNOWN_INPUT_SELF_HASHED_CROSS_BOUND_STAGE_ARTIFACT_READ_REPLAY_VALIDATOR",
        "ADD_HOSTILE_ALIAS_SUBSTITUTION_REORDERING_EXACT_CAP_AND_EVERY_PHASE_BURN_MATRIX",
    ]
    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert any("not a durable replay ZIP" in item for item in nonclaims)
    assert any("Only the successful lookup phase" in item for item in nonclaims)
    assert any("not an Effect Schema decoder" in item for item in nonclaims)
    assert any("not a receipt JSON" in item for item in nonclaims)
    assert any("one Layer build graph" in item for item in nonclaims)
    assert any("may attempt reacquisition or fail closed" in item for item in nonclaims)
    assert any("not the GitHub observer" in item for item in nonclaims)
    assert any("not GitHub-origin evidence" in item for item in nonclaims)
    assert any("not same-process cryptographic isolation" in item for item in nonclaims)
    assert any("does not prove production ten-second" in item for item in nonclaims)
    assert any("not a remote Neo4j" in item for item in nonclaims)
    assert any("no source freeze" in item for item in nonclaims)


def test_v11_bindings_predecessor_chain_indexes_and_verification_are_exact() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)
    assert predecessor["bundle_uid"] == payload[
        "supersedes_bundle_uid_for_continuation"
    ]
    bindings = payload["artifact_bindings"]
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json" not in paths
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
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    predecessor_binding = next(
        binding for binding in bindings if binding["path"] == PREDECESSOR_PATH.relative_to(ROOT).as_posix()
    )
    assert predecessor_binding["sha256"] == hashlib.sha256(
        PREDECESSOR_PATH.read_bytes()
    ).hexdigest()
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

    verification = payload["verification"]
    assert verification["effect_tests_final"] == "245/245 PASS"
    assert verification["effect_test_suites_final"] == "20/20 PASS"
    assert verification["focused_trace_layer_and_public_tests"] == "56/56 PASS"
    assert verification["exact_github_metadata_cap_tests"] == "33/33 PASS"
    assert verification["combined_focused_tests"] == "89/89 PASS"
    assert verification["v11_kg_tests"] == "6/6 PASS"
    assert verification["v1_through_v11_handoff_chain_tests"] == "50/50 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS_ASSET_INCLUDED"
    assert verification["diff_check"] == "PASS"

    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        text = index_path.read_text(encoding="utf-8")
        assert "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json" in text
        assert Path(payload["handoff_path"]).name in text or "v11" in text
