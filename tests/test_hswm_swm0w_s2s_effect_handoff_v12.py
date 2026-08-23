from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json"
CONTRACT_PATH = (
    ROOT
    / "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay-contract.ts"
)
REPLAY_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts"
LIVE_ARTIFACT_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-live-artifact.ts"
PERMIT_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-stage-artifact-permits.ts"
ZIP_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-zip.ts"
PROFILE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-profile.ts"
PROFILE_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/s2s-evidence-profile.test.ts"
ROOT_TEST_PATH = ROOT / "src/hswm/effect-runtime/test/public-api.test.ts"
ROOT_INDEX_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
PACKAGE_PATH = ROOT / "src/hswm/effect-runtime/package.json"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V11_SHA256 = (
    "602e480359a120e9273172451e8a159d0700aae9fe2f2d9836584bf5627ba891"
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


def test_v12_is_duplicate_key_safe_and_a_pi_only_engineering_checkpoint() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    payload = _load_handoff()
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v12"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-stage-read-replay-core-implemented-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-lookup-trace-shared-layer-implemented-2026-08-23"
    )
    assert payload["workspace_parent_commit"] == (
        "9853060c4a6c838f8d25aaad24f97c2804adbd89"
    )
    assert payload["workspace_primary_implementation_commit"] == (
        "955beb04e0ad59b86af8dab7e2a83edde9383196"
    )
    assert payload["workspace_code_commit"] == (
        "955beb04e0ad59b86af8dab7e2a83edde9383196"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )
    assert payload["effect_skill_application_status"] == (
        "APPLIED_TO_VERSION_PINNED_PURE_CORE_LAZY_EFFECT_SHELL_AND_"
        "VERIFICATION_NOT_A_RUNTIME_DEPENDENCY"
    )

    for flag in (
        "successful_artifact_lookup_trace_implemented",
        "shared_current_run_stage_layer_implemented",
        "legacy_stage_artifact_reads_layer_signature_compatible",
        "stage_artifact_read_replay_core_implemented",
        "stage_read_replay_profile_caps_closed",
    ):
        assert payload[flag] is True
    for flag in (
        "durable_artifact_read_replay_attachment_implemented",
        "complete_replay_attachment_profiles_closed",
        "hostile_phase_matrix_complete",
        "production_stage_artifact_read_replay_emitted",
        "github_origin_stage_artifact_read_replay_observed",
        "live_shared_bearer_observed",
        "full_registration_source_snapshot_implemented",
        "nested_replay_cross_attachment_semantics_closed",
        "failure_unknown_void_profiles_closed",
        "closed_stage_programs_implemented",
        "mandatory_upload_postconditions_implemented",
        "external_shared_durable_store_deployed",
        "external_durable_root_authenticated",
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
        "F": "NO_CONFIRMATORY_FUNCTION_OR_NUMERIC_RESULT",
        "Pi": (
            "BOUNDED_STAGE_READ_REPLAY_SUCCESS_CORE_AND_EXACT_PROFILE_CAPS_"
            "IMPLEMENTED_DURABLE_EMISSION_HOSTILE_PHASE_MATRIX_AND_STAGE_"
            "PROGRAMS_OPEN"
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


def test_v12_representation_and_resource_arithmetic_are_exact() -> None:
    payload = _load_handoff()
    boundary = payload["implemented_boundaries"]["stage_artifact_read_replay_core"]
    assert boundary == {
        "status": (
            "ENGINEERING_CLEAR_LOCAL_SUCCESS_PATH_CORE_DURABLE_INTEGRATION_OPEN"
        ),
        "schema_version": "hswm-swm0w-s2s-stage-artifact-read-replay/v1",
        "representation": (
            "STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_"
            "PREDECESSOR_CONTENT_REFERENCE"
        ),
        "modules": {
            "contract": (
                "src/hswm/effect-runtime/src/"
                "s2s-stage-artifact-read-replay-contract.ts"
            ),
            "core": (
                "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts"
            ),
            "zip": "src/hswm/effect-runtime/src/s2s-zip.ts",
            "permit": (
                "src/hswm/effect-runtime/src/s2s-stage-artifact-permits.ts"
            ),
        },
        "carrier_members": [
            {"name": "manifest.json", "maximum_bytes": 1_048_576},
            {"name": "observations.bin", "maximum_bytes": 11_534_336},
        ],
        "member_count": 2,
        "stored_zip_framing_bytes": 264,
        "maximum_carrier_bytes": 12_583_176,
        "successful_attempt_ordinals": [1, 2, 3],
        "observation_counts_by_successful_attempt": {"1": 7, "2": 9, "3": 11},
        "aggregate_self_hash_validated": True,
        "raw_observations_reconstructed_and_revalidated": True,
        "predecessor_archive_embedded": False,
        "predecessor_content_reference_recovered_rehashed_and_revalidated": True,
        "current_run_full_workflow_lineage_bound": True,
        "predecessor_job_database_ids_bound": True,
        "permit_evidence_revalidated": True,
        "candidate_first_reread_fingerprint_equal": True,
        "candidate_permit_ledger_strict_prefix_extension": True,
        "module_authentic_validated_read_required_for_build": True,
        "pure_core_result": "Either",
        "effect_shell": "LAZY_EFFECT_SUSPEND_TYPED_ERROR",
        "root_package_exported": False,
        "production_emission_integrated": False,
        "hostile_phase_matrix_complete": False,
    }

    budgets = payload["byte_budgets"]
    replay = budgets["stage_artifact_read_replay"]
    assert replay == {
        "github_json_each_bytes": 1_048_576,
        "manifest_maximum_bytes": 1_048_576,
        "maximum_observation_count": 11,
        "observations_maximum_bytes": 11_534_336,
        "stored_zip_framing_bytes": 264,
        "carrier_maximum_bytes": 12_583_176,
        "former_coarse_profile_bytes": 16_777_216,
        "generic_attachment_maximum_bytes": 67_108_864,
        "generic_envelope_attachment_total_maximum_bytes": 268_435_456,
        "below_former_coarse_profile_bytes": 4_194_040,
        "below_generic_attachment_maximum_bytes": 54_525_688,
        "maximum_and_plus_one_regression_pinned": True,
        "downloaded_predecessor_archive_embedded": False,
        "downloaded_predecessor_archive_content_referenced": True,
    }
    assert replay["carrier_maximum_bytes"] == (
        replay["manifest_maximum_bytes"]
        + replay["observations_maximum_bytes"]
        + replay["stored_zip_framing_bytes"]
    )
    assert replay["observations_maximum_bytes"] == (
        replay["maximum_observation_count"] * replay["github_json_each_bytes"]
    )

    stage_totals = budgets["success_stage_attachment_totals"]
    assert stage_totals == {
        "REGISTER": {"attachment_count": 13, "maximum_bytes": 108_068_864},
        "CONFIRM": {"attachment_count": 17, "maximum_bytes": 112_484_616},
        "ADJUDICATE": {"attachment_count": 18, "maximum_bytes": 74_670_872},
    }
    assert all(
        stage["maximum_bytes"]
        <= replay["generic_envelope_attachment_total_maximum_bytes"]
        for stage in stage_totals.values()
    )

    chain = budgets["complete_success_chain"]
    assert chain == {
        "envelope_count": 3,
        "attachment_bytes": 295_224_352,
        "manifest_bytes": 3_145_728,
        "claim_bytes": 49_152,
        "maximum_content_bytes_before_filesystem_overhead_and_dedup": 298_419_232,
        "filesystem_overhead_excluded": True,
        "dedup_savings_excluded": True,
    }
    assert chain["attachment_bytes"] == sum(
        stage["maximum_bytes"] for stage in stage_totals.values()
    )
    assert chain["manifest_bytes"] == chain["envelope_count"] * 1_048_576
    assert chain["claim_bytes"] == chain["envelope_count"] * 16_384
    assert chain["maximum_content_bytes_before_filesystem_overhead_and_dedup"] == (
        chain["attachment_bytes"]
        + chain["manifest_bytes"]
        + chain["claim_bytes"]
    )


def test_v12_source_contains_the_effect_core_and_keeps_it_root_private() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    replay = REPLAY_PATH.read_text(encoding="utf-8")
    live_artifact = LIVE_ARTIFACT_PATH.read_text(encoding="utf-8")
    permit = PERMIT_PATH.read_text(encoding="utf-8")
    zip_source = ZIP_PATH.read_text(encoding="utf-8")
    profile = PROFILE_PATH.read_text(encoding="utf-8")
    profile_test = PROFILE_TEST_PATH.read_text(encoding="utf-8")
    root_test = ROOT_TEST_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")
    package = _load_json(PACKAGE_PATH)

    for literal in (
        '"hswm-swm0w-s2s-stage-artifact-read-replay/v1"',
        '"STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_PREDECESSOR_CONTENT_REFERENCE"',
        '"manifest.json"',
        '"observations.bin"',
        "S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_OBSERVATION_COUNT = 11 as const",
        "2 * (30 + 16 + 46) + 2 * (13 + 16) + 22",
        "S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES !== 12_583_176",
    ):
        assert literal in contract
    for literal in (
        "Schema.decodeUnknownEither",
        "Effect.suspend(() =>",
        "validateRecoveredPredecessorChain",
        "AUTHENTIC_REPLAY_SNAPSHOTS",
        "isExactPermitLedgerPrefix",
        "isAuthenticS2SValidatedStageArtifactRead",
        "buildS2SStoredZip",
        "validateS2SStageArtifactReadReplay",
        "buildS2SStageArtifactReadReplay",
        "validateS2SCandidateReadReplayPair",
        '"LEDGER_BINDING_MISMATCH"',
    ):
        assert literal in replay
    assert "AUTHENTIC_VALIDATED_STAGE_ARTIFACT_READS" in live_artifact
    assert "isAuthenticS2SValidatedStageArtifactRead" in live_artifact
    assert "validateS2SStageArtifactPermitEvidence" in permit
    assert "export const buildS2SStoredZip" in zip_source
    assert "S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES" in profile
    for literal in (
        "REGISTER: 108_068_864",
        "CONFIRM: 112_484_616",
        "ADJUDICATE: 74_670_872",
        "S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES).toBe(12_583_176)",
    ):
        assert literal in profile_test

    for private_name in (
        "isAuthenticS2SValidatedStageArtifactRead",
        "buildS2SStageArtifactReadReplay",
        "buildS2SStageArtifactReadReplayEffect",
        "validateS2SStageArtifactReadReplay",
        "validateS2SStageArtifactReadReplayEffect",
        "validateS2SCandidateReadReplayPair",
        "validateS2SCandidateReadReplayPairEffect",
        "S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES",
    ):
        assert f'"{private_name}" in PublicApi' in root_test
        assert private_name not in root_index
    assert package["exports"] == {
        ".": {"types": "./dist/index.d.ts", "default": "./dist/index.js"}
    }


def test_v12_resolved_and_open_gates_preserve_the_evidence_boundary() -> None:
    payload = _load_handoff()
    resolved = payload["resolved_gates"]
    opened = payload["open_gates"]
    resolved_by_uid = {item["uid"]: item["status"] for item in resolved}
    open_by_uid = {item["uid"]: item for item in opened}
    assert len(resolved_by_uid) == len(resolved)
    assert len(open_by_uid) == len(opened)
    assert resolved_by_uid.keys().isdisjoint(open_by_uid.keys())
    assert {
        "sym:Gate:hswm-s2s-stage-artifact-read-replay-representation-and-resource-contract": (
            "ENGINEERING_CLEAR_EXACT_STORED_ZIP_AND_PREDECESSOR_CONTENT_REFERENCE"
        ),
        "sym:Gate:hswm-s2s-stage-read-replay-success-profile-caps": (
            "ENGINEERING_CLEAR_EXACT_DERIVED_MAXIMUM_AND_PLUS_ONE_PINNED"
        ),
        "sym:Gate:hswm-s2s-stage-artifact-read-replay-success-core": (
            "ENGINEERING_CLEAR_LOCAL_PURE_CORE_AND_LAZY_EFFECT_SHELL"
        ),
    }.items() <= resolved_by_uid.items()
    assert (
        "sym:Blocker:hswm-s2s-stage-artifact-read-replay-byte-budget"
        not in open_by_uid
    )
    assert all(item["severity"] == "P0" for item in opened)
    for uid in (
        "sym:Blocker:hswm-s2s-durable-artifact-read-replay-attachment-integration",
        "sym:Blocker:hswm-s2s-artifact-read-replay-hostile-and-phase-matrix",
        "sym:Blocker:hswm-s2s-full-registration-source-snapshot",
        "sym:Blocker:hswm-s2s-nested-replay-and-cross-attachment-semantics",
        "sym:Blocker:hswm-s2s-failure-unknown-and-void-profiles",
        "sym:Blocker:hswm-s2s-closed-stage-programs-and-upload-postconditions",
        "sym:Blocker:hswm-s2s-external-shared-durable-store-deployment",
        "sym:Blocker:hswm-s2s-workflow-source-bytes-and-api-path",
        "sym:Blocker:hswm-s2s-current-run-github-origin-and-genuine-issuance",
        "sym:Blocker:hswm-s2s-terminal-reobservation-rerun-invalidation-and-finalizer",
    ):
        assert uid in open_by_uid

    assert payload["next_session_order"][:5] == [
        "READ_CONSTITUTION_V12_HANDOFF_V12_KG_IMMUTABLE_V11_AND_EFFECT_SKILL",
        "PRESERVE_PROTECTED_CONTINUAL_LIVE_CHANGES_AND_TREAT_955BEB0_AS_CODE_CHECKPOINT",
        "INTEGRATE_STAGE_READ_REPLAY_AS_CREATE_ONLY_DURABLE_PROFILE_ATTACHMENTS",
        "COMPLETE_HOSTILE_ALIAS_SUBSTITUTION_REORDERING_CAP_AND_EVERY_PHASE_BURN_MATRIX",
        "IMPLEMENT_FULL_REGISTRATION_SOURCE_SNAPSHOT",
    ]
    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert any("local replay core" in item for item in nonclaims)
    assert any("not a durably emitted" in item for item in nonclaims)
    assert any("hostile phase matrix" in item for item in nonclaims)
    assert any("process-local WeakSet" in item for item in nonclaims)
    assert any("not GitHub-origin evidence" in item for item in nonclaims)
    assert any("external durable-root authenticity" in item for item in nonclaims)
    assert any("not a resident-heap" in item for item in nonclaims)
    assert any("not HSWM cognition" in item for item in nonclaims)
    assert any("no source freeze" in item for item in nonclaims)
    assert any("outcome-bound causal" in item for item in nonclaims)


def test_v12_bindings_pin_immutable_v11_and_the_unique_successor() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)
    latest_bindings = _latest_binding_hashes(payload)
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V11_SHA256
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
        "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v11.json",
        payload["handoff_path"],
        "docs/operations/HSWM_SWM0W_S2S_STAGE_READ_REPLAY_REPRESENTATION_DECISION_2026-08-23.md",
        "src/hswm/effect-runtime/src/s2s-evidence-profile.ts",
        "src/hswm/effect-runtime/src/s2s-live-artifact.ts",
        "src/hswm/effect-runtime/src/s2s-stage-artifact-permits.ts",
        "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay-contract.ts",
        "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts",
        "src/hswm/effect-runtime/src/s2s-zip.ts",
        "src/hswm/effect-runtime/test/public-api.test.ts",
        "src/hswm/effect-runtime/test/s2s-evidence-profile.test.ts",
        "src/hswm/effect-runtime/test/s2s-live-artifact.test.ts",
        "src/hswm/effect-runtime/test/s2s-stage-artifact-permit-evidence.test.ts",
        "src/hswm/effect-runtime/test/s2s-zip.test.ts",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v12.py",
    }
    assert required_paths <= set(paths)
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json" not in paths
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
    assert predecessor_binding["sha256"] == IMMUTABLE_V11_SHA256
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


def test_v12_indexes_and_verification_are_exact() -> None:
    payload = _load_handoff()
    verification = payload["verification"]
    assert verification["effect_tests_final"] == "262/262 PASS"
    assert verification["effect_test_suites_final"] == "21/21 PASS"
    assert verification["focused_stage_read_replay_tests"] == "55/55 PASS"
    assert verification["v12_kg_tests"] == "6/6 PASS"
    assert verification["v1_through_v12_handoff_chain_tests"] == "56/56 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS_ASSET_INCLUDED"
    assert verification["diff_check"] == "PASS"
    assert verification["independent_reaudit"] == (
        "PASS_TARGETED_CORE_BOUNDARIES_HOSTILE_PHASE_MATRIX_REMAINS_OPEN"
    )
    assert "no durable attachment emission" in verification["claim_boundary"]
    assert "no GitHub-origin replay" in verification["claim_boundary"]
    assert "no scientific verdict" in verification["claim_boundary"]

    handoff_name = Path(payload["handoff_path"]).name
    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        text = index_path.read_text(encoding="utf-8")
        assert "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v12.json" in text
        assert handoff_name in text
