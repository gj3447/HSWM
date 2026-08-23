from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json"
ENVELOPE_SOURCE_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-evidence-envelope.ts"
)
STORE_SOURCE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-file.ts"
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


def _successors(payload: dict[str, object]) -> list[dict[str, object]]:
    return [
        candidate
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != HANDOFF_PATH
        if (candidate := _load_json(path)).get(
            "supersedes_bundle_uid_for_continuation"
        )
        == payload["bundle_uid"]
    ]


def test_v9_is_a_pi_structural_checkpoint_not_a_scientific_verdict() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v9"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-durable-evidence-substrate-implemented-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-stage-artifact-permits-implemented-2026-08-22"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["design_status"] == (
        "V8_CONTENT_ADDRESSED_DURABLE_EVIDENCE_SUBSTRATE_IMPLEMENTED"
    )
    assert payload["implementation_status"] == (
        "STRUCTURAL_ENVELOPE_AND_SHARED_POSIX_CLAIM_ENGINEERING_CLEAR_"
        "STAGE_PROGRAMS_OPEN"
    )
    assert payload["structural_status"] == "STRUCTURAL_1_6_9_CLEAR"
    assert payload["functional_runtime_status"] == (
        "USER_PRIMARY_TYPESCRIPT_EFFECT_V3_ACTIVE"
    )
    assert payload["effect_skill_application_status"] == (
        "APPLIED_TO_IMPLEMENTATION_AND_VERIFICATION_NOT_A_RUNTIME_DEPENDENCY"
    )
    assert payload["durable_evidence_envelope_status"] == (
        "STRUCTURAL_V1_ENGINEERING_CLEAR_COMPLETE_ATTACHMENT_PROFILE_OPEN"
    )
    assert payload["durable_claim_store_status"] == (
        "ENGINEERING_CLEAR_CALLER_PROVISIONED_SHARED_POSIX_ROOT_REQUIRED"
    )
    assert payload["closed_stage_program_status"] == "OPEN"
    assert payload["mandatory_upload_postcondition_status"] == "OPEN"
    assert payload["workflow_source_bytes_status"] == "OPEN"
    assert payload["workflow_api_path_status"] == "OPEN_ONE_LITERAL_REQUIRED"
    assert payload["terminal_finalizer_status"] == "OPEN"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["workspace_parent_commit"] == (
        "d94a47385470841c5b28a494e125915fecf12803"
    )
    assert payload["workspace_code_commit"] == (
        "893648720007d1c64ffc090a56372a13bb0fd5a8"
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
            "CANONICAL_PREDECESSOR_LINKED_STRUCTURAL_ENVELOPE_AND_CREATE_ONLY_"
            "SHARED_POSIX_STAGE_CLAIM_SUBSTRATE_IMPLEMENTED_REPLAY_PROFILE_"
            "AND_STAGE_PROGRAMS_OPEN"
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


def test_v9_structural_envelope_contract_is_exact() -> None:
    boundary = _load_handoff()["implemented_boundaries"][
        "structural_evidence_envelope"
    ]
    assert type(boundary) is dict

    assert boundary == {
        "status": "ENGINEERING_CLEAR_STRUCTURAL_NOT_COMPLETE_REPLAY_CLOSURE",
        "module": "src/hswm/effect-runtime/src/s2s-evidence-envelope.ts",
        "root_package_exported": False,
        "schema_versions": {
            "envelope": "hswm-swm0w-s2s-evidence-envelope/v1",
            "claim": "hswm-swm0w-s2s-evidence-claim/v1",
        },
        "claim_scope": "ONE_REGISTRATION_COMMIT_PER_STAGE",
        "stages": ["REGISTER", "CONFIRM", "ADJUDICATE"],
        "identity": {
            "experiment_fixed": True,
            "source_a_differs_from_registration_b": True,
            "workflow_attempt": 1,
            "workflow_head_equals_registration_b": True,
            "workflow_contract_digest_exact": True,
            "workflow_api_path_representations_temporarily_allowed": 2,
        },
        "limits": {
            "attachments": 96,
            "attachment_bytes": 67108864,
            "total_attachment_bytes": 268435456,
            "manifest_bytes": 1048576,
            "claim_bytes": 16384,
        },
        "attachment_binding": [
            "LOGICAL_NAME",
            "ROLE",
            "OPTIONAL_SCHEMA_VERSION",
            "MEDIA_TYPE",
            "BYTE_LENGTH",
            "RAW_SHA256",
        ],
        "ordering": "ASCII_LOGICAL_NAME_UNIQUE_LOGICAL_NAME_AND_ROLE",
        "predecessor_topology": {
            "REGISTER": None,
            "CONFIRM": "REGISTER_MANIFEST_AND_CLAIM",
            "ADJUDICATE": "CONFIRM_MANIFEST_AND_CLAIM",
        },
        "canonicality": (
            "CANONICAL_CORE_SELF_RECEIPT_PLUS_RAW_FILE_CONTENT_ADDRESS"
        ),
        "defensive_snapshot_reads": True,
        "authentic_snapshot_weakset_authority_claimed": False,
        "duplicate_content_hash_across_descriptors_allowed": True,
        "workflow_file_bytes_revalidated_here": False,
        "complete_attachment_profile_owned_by_future_stage_programs": True,
    }


def test_v9_posix_claim_store_contract_is_exact() -> None:
    boundary = _load_handoff()["implemented_boundaries"][
        "durable_posix_claim_store"
    ]
    assert type(boundary) is dict

    assert boundary == {
        "status": "ENGINEERING_CLEAR_WITH_EXPLICIT_POSIX_PRECONDITIONS",
        "module": "src/hswm/effect-runtime/src/s2s-evidence-file.ts",
        "service": "S2SDurableEvidenceFileStore",
        "root_package_exported": False,
        "root": {
            "caller_preprovisioned": True,
            "absolute": True,
            "mode": "0700",
            "shared_external_durable_required_for_cross_process_claim": True,
            "parent_durability_owned_by_caller": True,
            "hostile_same_uid_excluded": True,
        },
        "publication_order": [
            "ATTACHMENT_OBJECTS",
            "MANIFEST_OBJECT",
            "CREATE_ONLY_B_STAGE_CLAIM",
            "FULL_CHAIN_READBACK",
        ],
        "atomicity": "EXCLUSIVE_TEMP_FSYNC_0400_HARD_LINK_CAS_DIRECTORY_FSYNC",
        "claim_key": "FIXED_EXPERIMENT_REGISTRATION_B_STAGE",
        "identical_claim": "ALREADY_COMMITTED",
        "divergent_claim": "CLAIM_CONFLICT",
        "same_digest_different_bytes": "CONTENT_ADDRESS_CORRUPTION",
        "predecessor_required_before_successor_write": True,
        "recovery": (
            "FULL_REGISTER_THROUGH_REQUESTED_STAGE_CONTENT_AND_LINEAGE_VALIDATION"
        ),
        "committed_readback_failure": "COMMITTED_READBACK_FAILED_RECONCILE",
        "effect_semantics": {
            "commit_and_recover_lazy": True,
            "layer_semaphore_permits": 1,
            "filesystem_transactions_uninterruptible": True,
            "claim_cas_and_full_readback_one_terminal_region": True,
        },
        "cross_layer_or_process_cas": True,
        "concurrent_regression_scope": "INDEPENDENT_LAYERS_ONE_PROCESS",
        "different_roots_coordinate": False,
        "orphan_content_possible": True,
        "garbage_collection_implemented": False,
        "publication_outcome_unknown_possible": True,
        "internal_filesystem_deadline": False,
        "acceptance_limits_are_memory_budget": False,
    }


def test_v9_source_and_root_surface_preserve_the_claimed_boundary() -> None:
    envelope_source = ENVELOPE_SOURCE_PATH.read_text(encoding="utf-8")
    store_source = STORE_SOURCE_PATH.read_text(encoding="utf-8")
    root_index = ROOT_INDEX_PATH.read_text(encoding="utf-8")
    package = _load_json(PACKAGE_PATH)

    for literal in (
        '"hswm-swm0w-s2s-evidence-envelope/v1"',
        '"hswm-swm0w-s2s-evidence-claim/v1"',
        "S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS = 96",
        "S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENT_BYTES =",
        "64 * 1_048_576",
        "S2S_EVIDENCE_ENVELOPE_MAX_TOTAL_ATTACHMENT_BYTES =",
        "256 * 1_048_576",
        "S2S_EVIDENCE_ENVELOPE_MAX_MANIFEST_BYTES = 1_048_576",
        "S2S_EVIDENCE_CLAIM_MAX_BYTES = 16_384",
        "AUTHENTIC_ENVELOPE_SNAPSHOTS = new WeakSet",
        "validateS2SEvidenceEnvelopeSnapshot",
        "buildS2SEvidenceClaim",
        "validateS2SEvidenceClaimForEnvelope",
        "complete replay closure",
    ):
        assert literal in envelope_source

    for literal in (
        "export class S2SDurableEvidenceFileStore",
        '"COMMITTED_READBACK_FAILED"',
        '"PUBLICATION_OUTCOME_UNKNOWN"',
        '"CLAIM_CONFLICT"',
        '"CONTENT_ADDRESS_CORRUPTION"',
        "Effect.makeSemaphore(1)",
        "Effect.suspend(() =>",
        "Effect.uninterruptible",
        "publishCreateOnly",
        "recoverCommittedClaim",
        "pre-provisioned, shared durable",
        "hard-link/fsync semantics",
    ):
        assert literal in store_source

    attachment_publication = store_source.index("publishedAttachmentHashes")
    manifest_publication = store_source.index(
        "prepared.envelope.manifestRawSha256", attachment_publication
    )
    terminal_region = store_source.index(
        "return yield* Effect.uninterruptible", manifest_publication
    )
    claim_publication = store_source.index("const claimOutcome", terminal_region)
    final_recovery = store_source.index(
        "recoverCommittedClaim", claim_publication
    )
    assert attachment_publication < manifest_publication
    assert manifest_publication < terminal_region < claim_publication < final_recovery

    for private_name in (
        "S2SDurableEvidenceFileStore",
        "makeS2SDurableEvidenceFileStoreLayer",
        "buildS2SEvidenceEnvelope",
        "validateS2SEvidenceEnvelope",
        "buildS2SEvidenceClaim",
        "validateS2SEvidenceClaim",
    ):
        assert private_name not in root_index
    assert "s2s-evidence-envelope" not in root_index
    assert "s2s-evidence-file" not in root_index
    assert package["exports"] == {
        ".": {
            "types": "./dist/index.d.ts",
            "default": "./dist/index.js",
        }
    }


def test_v9_gate_transition_and_continuation_order_are_exact() -> None:
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
        "sym:Gate:hswm-s2s-structural-evidence-envelope-v1"
    ] == "ENGINEERING_CLEAR_NOT_COMPLETE_REPLAY_CLOSURE"
    assert resolved_by_uid[
        "sym:Gate:hswm-s2s-shared-posix-create-only-stage-claim"
    ] == "ENGINEERING_CLEAR_DEPLOYMENT_OPEN"
    assert set(open_by_uid) == {
        "sym:Blocker:hswm-s2s-complete-stage-replay-attachment-profiles",
        "sym:Blocker:hswm-s2s-closed-stage-programs-and-upload-postconditions",
        "sym:Blocker:hswm-s2s-external-shared-durable-store-deployment",
        "sym:Blocker:hswm-s2s-workflow-source-bytes-manifest-binding",
        "sym:Blocker:hswm-s2s-workflow-api-path-selection",
        "sym:Blocker:hswm-s2s-current-run-github-origin-and-genuine-issuance",
        "sym:Blocker:hswm-s2s-terminal-reobservation-and-rerun-invalidation",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    assert all(item["severity"] == "P0" for item in opened)

    assert payload["next_session_order"] == [
        "READ_CONSTITUTION_V9_HANDOFF_V9_KG_IMMUTABLE_V8_AND_EFFECT_SKILL",
        "PRESERVE_PROTECTED_CONTINUAL_LIVE_USER_CHANGES_AND_TREAT_8936487_AS_CODE_CHECKPOINT",
        "ADD_ROOT_PRIVATE_BOUNDED_CURRENT_RUN_REPLAY_SNAPSHOT_AND_FREEZE_REGISTER_SOURCE_PREREG_SNAPSHOT_CONTRACT",
        "PIN_PROTOCOL_CONFIG_RETAIN_RAW_DRAND_BYTES_ADD_PYTHON_PEAK_RSS_AND_RESOLVE_3_MIB_4_MIB_CAP",
        "FREEZE_EXACT_THREE_STAGE_ATTACHMENT_PROFILES_THEN_IMPLEMENT_SIX_PREPARE_ASSERT_UPLOAD_ENTRYPOINTS",
        "WIRE_ONE_REVIEWED_EXTERNAL_SHARED_DURABLE_ROOT_AND_RECONCILE_COMMITTED_READBACK_FAILURE",
        "IMPLEMENT_FRESH_TERMINAL_ATTEMPT_ONE_REOBSERVATION_AND_RERUN_INVALIDATION_IMMEDIATELY_BEFORE_CLAIM_CAS",
        "ADVERSARIALLY_REVIEW_COMPLETE_STAGE_FINALIZER_FAILURE_INTERRUPTION_UNKNOWN_AND_VOID_MATRIX",
        "AUTHOR_AND_REVIEW_EXACT_THREE_JOB_WORKFLOW_THEN_PIN_RAW_SHA_CONTRACT_DIGEST_SOURCE_A_ROW_AND_ONE_API_PATH",
        "DO_NOT_CREATE_SOURCE_FREEZE_PREREG_BEACON_DISPATCH_CANDIDATE_ADJUDICATION_OR_EVENT_10_FOR_ENGINEERING_PROGRESS",
    ]


def test_v9_paths_hashes_verification_indexes_and_nonclaims_are_exact() -> None:
    payload = _load_handoff()
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json" not in paths
    assert {binding["path"]: binding["role"] for binding in bindings} == {
        "docs/operations/HSWM_SWM0W_S2S_DURABLE_EVIDENCE_SUBSTRATE_IMPLEMENTED_NEXT_SESSION_2026-08-23.md": "NEXT_SESSION_DURABLE_EVIDENCE_SUBSTRATE_HANDOFF",
        "ontology/evidence/README.md": "LOCAL_KG_CURRENT_CONTINUATION_INDEX_V9",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md": "TYPESCRIPT_EFFECT_RESEARCH_CONTINUATION_INDEX_V9",
        "src/hswm/effect-runtime/README.md": "EFFECT_RUNTIME_CURRENT_CONTINUATION_INDEX_V9",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v9.py": "LOCAL_KG_V9_CLOSURE_REGRESSIONS",
        "docs/operations/HSWM_SWM0W_S2S_STAGE_ARTIFACT_PERMITS_IMPLEMENTED_NEXT_SESSION_2026-08-22.md": "IMMUTABLE_V8_IMPLEMENTATION_HANDOFF_PREDECESSOR",
        "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json": "IMMUTABLE_V8_KG_PREDECESSOR",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v8.py": "V8_SUCCESSOR_AWARE_CHAIN_REGRESSION",
        "src/hswm/effect-runtime/src/s2s-evidence-envelope.ts": "CANONICAL_STRUCTURAL_ENVELOPE_AND_CLAIM_IMPLEMENTATION",
        "src/hswm/effect-runtime/src/s2s-evidence-file.ts": "CREATE_ONLY_POSIX_CONTENT_AND_CLAIM_STORE_IMPLEMENTATION",
        "src/hswm/effect-runtime/src/s2s-workflow-contract.ts": "WORKFLOW_IDENTITY_DEPENDENCY",
        "src/hswm/effect-runtime/src/index.ts": "ROOT_EXPORT_CONTAINMENT_SURFACE_V9",
        "src/hswm/effect-runtime/package.json": "EXACT_SINGLE_ROOT_PACKAGE_EXPORT_MAP_V9",
        "src/hswm/effect-runtime/test/s2s-evidence-envelope.test.ts": "STRUCTURAL_ENVELOPE_HOSTILE_REGRESSIONS",
        "src/hswm/effect-runtime/test/s2s-evidence-file.test.ts": "DURABLE_POSIX_STORE_HOSTILE_REGRESSIONS",
        "src/hswm/effect-runtime/test/public-api.test.ts": "ROOT_PRIVATE_SURFACE_REGRESSIONS_V9",
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
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    verification = payload["verification"]
    assert verification["effect_tests"] == "234/234 PASS"
    assert verification["effect_test_suites"] == "18/18 PASS"
    assert verification["focused_envelope_tests"] == "10/10 PASS"
    assert verification["focused_file_store_tests"] == "6/6 PASS"
    assert verification["focused_public_api_tests"] == "2/2 PASS"
    assert verification["focused_total"] == "18/18 PASS"
    assert verification["typescript"] == "STRICT_CHECK_PASS"
    assert verification["build"] == "PASS"
    assert verification["pack_dry_run"] == "PASS"
    assert verification["scratch_cleanup"] == "PASS_NO_LONG_LIVED_WORKER"
    assert verification["v9_kg_tests"] == "7/7 PASS"
    assert verification["v1_through_v9_handoff_chain_tests"] == "36/36 PASS"
    assert verification["independent_audits"] == (
        "PURE_ENVELOPE_AND_FILE_STORE_READ_ONLY_AUDITS_NO_BLOCKER_IN_DECLARED_SCOPE"
    )

    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        index_text = index_path.read_text(encoding="utf-8")
        assert (
            "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v9.json" in index_text
            or "HSWM_SWM0W_S2S_DURABLE_EVIDENCE_SUBSTRATE_IMPLEMENTED" in index_text
        )

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert type(nonclaims) is list
    assert any("not complete replay evidence" in item for item in nonclaims)
    assert any("Different roots" in item for item in nonclaims)
    assert any("runner-local" in item for item in nonclaims)
    assert any("hostile same-UID" in item for item in nonclaims)
    assert any("COMMITTED_READBACK_FAILED" in item for item in nonclaims)
    assert any("independent Layers" in item for item in nonclaims)
    assert any("not an exactly-once" in item for item in nonclaims)
    assert any("not a preregistration" in item for item in nonclaims)
    assert any("no event-10" in item for item in nonclaims)


def test_v9_predecessor_is_immutable_and_successor_chain_is_unique() -> None:
    payload = _load_handoff()
    predecessor = _load_json(PREDECESSOR_PATH)

    assert predecessor["bundle_uid"] == payload[
        "supersedes_bundle_uid_for_continuation"
    ]
    predecessor_binding = next(
        binding
        for binding in payload["artifact_bindings"]
        if binding["path"]
        == "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v8.json"
    )
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        predecessor_binding["sha256"]
    )
    v8_successors = [
        candidate
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != PREDECESSOR_PATH
        if (candidate := _load_json(path)).get(
            "supersedes_bundle_uid_for_continuation"
        )
        == predecessor["bundle_uid"]
    ]
    assert [candidate["bundle_uid"] for candidate in v8_successors] == [
        payload["bundle_uid"]
    ]
    assert _successors(payload) == []
