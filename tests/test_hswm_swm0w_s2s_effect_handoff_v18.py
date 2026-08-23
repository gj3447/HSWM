from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v18.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v17.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_STAGE_UPLOAD_POSTCONDITION_CODEC_IMPLEMENTED_"
    "NEXT_SESSION_2026-08-23.md"
)
CODEC_PATH = (
    ROOT
    / "src/hswm/effect-runtime/src/s2s-stage-upload-postcondition.ts"
)
CONTRACT_PATH = (
    ROOT
    / "src/hswm/effect-runtime/src/"
    "s2s-stage-upload-postcondition-contract.ts"
)
REPLAY_PATH = (
    ROOT
    / "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts"
)
PUBLIC_API_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
FOCUSED_TEST_PATH = (
    ROOT
    / "src/hswm/effect-runtime/test/"
    "s2s-stage-upload-postcondition.test.ts"
)
PROFILE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-profile.ts"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V17_SHA256 = (
    "21a1a002b067b1680767649b43735a4702c82abccf898692849bf91fad242859"
)
PRIMARY_IMPLEMENTATION_COMMIT = "1f45f4bad6907617cacac6525ea9edd8d9c7b6f4"
COMPATIBILITY_FOLLOWUP_COMMIT = "5e1809a2019d57eb8e82ce0c6de18f67ef18815e"
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


def test_v18_is_duplicate_key_safe_unique_successor_and_pi_only() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    predecessor = _load_json(PREDECESSOR_PATH)
    payload = _load_handoff()
    successors = [
        _load_json(path)
        for path in sorted(HANDOFF_PATH.parent.glob(HANDOFF_GLOB))
        if path != PREDECESSOR_PATH
        and _load_json(path).get("supersedes_bundle_uid_for_continuation")
        == predecessor["bundle_uid"]
    ]
    assert len(successors) == 1
    assert successors[0]["bundle_uid"] == payload["bundle_uid"]

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v18"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-stage-upload-postcondition-codec-"
        "implemented-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        predecessor["bundle_uid"]
    )
    assert payload["workspace_parent_commit"] == (
        "7411c802ad0a71ab3ff4a55df5a3b9bd7317908e"
    )
    assert payload["workspace_code_commit"] == COMPATIBILITY_FOLLOWUP_COMMIT
    assert payload["workspace_primary_implementation_commit"] == (
        PRIMARY_IMPLEMENTATION_COMMIT
    )
    assert payload["compatibility_followup_commit"] == (
        COMPATIBILITY_FOLLOWUP_COMMIT
    )
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_NO_TOPOLOGY_OR_LIVING_HARNESS_EVIDENCE",
        "W": "UNCHANGED_NO_LEARNED_SEMANTIC_WEIGHT_RESULT",
        "A": "UNCHANGED_NO_ACTIVATION_OR_READOUT_RESULT",
        "F": "UNCHANGED_NO_FUNCTION_CELL_OR_SCIENTIFIC_VERDICT",
        "Pi": (
            "STRICT_ROOT_PRIVATE_NON_AUTHORIZING_STAGE_UPLOAD_"
            "POSTCONDITION_CODEC_AND_RECONSTRUCTION_IMPLEMENTED"
        ),
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }


def test_v18_records_exact_non_authorizing_codec_contract() -> None:
    payload = _load_handoff()
    implementation = payload["implemented_slice"]
    contract = payload["stage_upload_postcondition_contract"]
    permit = payload["assertion_permit_boundary"]

    for key in (
        "strict_effect_schema",
        "stage_correlated_manifest_union",
        "strict_unknown_input_reconstruction",
        "canonical_manifest_and_self_hash",
        "deterministic_stored_zip_carrier",
        "raw_observation_replay",
        "archive_and_prepared_member_cross_binding",
        "deep_freeze_and_defensive_byte_copies",
        "lazy_effect_wrappers",
        "generic_register_current_run_validation",
        "predecessor_replay_register_exclusion_preserved",
        "shared_scalar_resource_limits",
    ):
        assert implementation[key] is True
    assert implementation["package_root_exported"] is False
    assert implementation["production_authority_issued"] is False

    assert contract["schema_identifier"] == (
        "hswm-swm0w-s2s-stage-upload-postcondition/v1"
    )
    assert contract["representation"] == (
        "STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_"
        "CURRENT_STAGE_ARCHIVE_REFERENCE"
    )
    assert contract["members"] == ["manifest.json", "observations.bin"]
    assert contract["manifest_top_level_key_count"] == 37
    assert len(contract["manifest_top_level_keys"]) == 37
    assert len(set(contract["manifest_top_level_keys"])) == 37
    assert contract["successful_attempt_observation_counts"] == {
        "1": 7,
        "2": 9,
        "3": 11,
    }
    assert contract["manifest_maximum_bytes"] == 1_048_576
    assert contract["observation_blob_maximum_bytes"] == 11 * 1_048_576
    assert contract["zip_framing_bytes"] == 264
    assert contract["carrier_maximum_bytes"] == 12_583_176
    assert contract["profile_occurrence_maximum_bytes"] == 16 * 1_048_576
    assert contract["validated_output_tag"] == (
        "ValidatedNonAuthorizingStageUploadPostcondition"
    )
    assert contract["stages"] == ["REGISTER", "CONFIRM", "ADJUDICATE"]
    assert contract["predecessor_tuple_lengths"] == [0, 1, 2]

    assert permit == {
        "schema_identifier": (
            "hswm-swm0w-s2s-stage-upload-assertion-permit-evidence/v1"
        ),
        "operation": "ASSERT_AND_RECOVER_CURRENT_STAGE_ARTIFACT",
        "ledger_capacity": 16,
        "ledger_entry_count_range": [12, 16],
        "builder_accepted_authority_scopes": ["TEST_ONLY_NON_AUTHORIZING"],
        "structural_recovery_decodable_authority_scopes": [
            "TEST_ONLY_NON_AUTHORIZING",
            "TRUSTED_SINGLE_MODULE_CURRENT_JOB",
        ],
        "structural_recovery_restores_authority": False,
        "cross_worker_replay_prevention_claimed": False,
        "cross_module_copy_replay_prevention_claimed": False,
        "cross_process_replay_prevention_claimed": False,
        "durable_replay_prevention_claimed": False,
    }


def test_v18_keeps_authority_profile_workflow_and_science_gates_open() -> None:
    payload = _load_handoff()
    assert payload["stage_upload_postcondition_schema_implemented"] is True
    assert payload["stage_upload_postcondition_codec_implemented"] is True
    for flag in (
        "prepared_stage_carrier_capability_implemented",
        "same_stage_upload_assertion_mechanics_implemented",
        "complete_stage_profile_commit_bridge_implemented",
        "mandatory_upload_postconditions_implemented",
        "external_shared_durable_store_feasibility_proved",
        "external_shared_durable_store_deployed",
        "external_durable_root_authenticated",
        "independent_process_restart_recovery_observed",
        "genuine_current_run_capability_issued",
        "genuine_stage_artifact_capability_issued",
        "github_origin_established",
        "workflow_source_frozen",
        "preregistration_created",
        "confirmatory_dispatched",
        "event_10_composed",
        "scientific_verdict_produced",
    ):
        assert payload[flag] is False

    assert payload["healthy_success_profile_inventory"] == {
        "total_occurrences": 48,
        "construct_and_recover_validation": 20,
        "semantic_core_without_attachment_codec": 19,
        "missing_carrier_or_source": 9,
        "production_stage_upload_postcondition_occurrences_filled": 0,
        "inventory_changed_by_this_slice": False,
    }
    profile_source = PROFILE_PATH.read_text(encoding="utf-8")
    assert profile_source.count(
        "hswm-swm0w-s2s-stage-upload-postcondition/v1"
    ) == 3

    closed = payload["closed_gates"]
    assert closed == [
        {
            "uid": "sym:ClosedGate:s2s-stage-upload-postcondition-codec",
            "status": "CLOSED_NON_AUTHORIZING_STRUCTURAL_ONLY",
            "closure": (
                "STRICT_SCHEMA_UNKNOWN_RECONSTRUCTION_SELF_HASH_"
                "DETERMINISTIC_CARRIER_OBSERVATION_REPLAY_AND_ARCHIVE_"
                "PREPARED_MEMBER_CROSS_BINDING"
            ),
        }
    ]
    assert payload["open_gates"][0]["uid"] == (
        "sym:OpenGate:s2s-prepared-carrier-and-assertion-permit"
    )
    assert payload["open_gates"][0]["priority"] == "NEXT"

    nodes = payload["nodes"]
    relations = payload["relations"]
    uids = [node["uid"] for node in nodes]
    assert len(uids) == len(set(uids))
    uid_set = set(uids)
    assert all(relation["from_uid"] in uid_set for relation in relations)
    assert all(relation["to_uid"] in uid_set for relation in relations)
    assert not any(relation["type"] == "EVIDENCE_FOR" for relation in relations)
    assert all(node.get("scientific_status") != "PASS" for node in nodes)


def test_v18_sources_and_handoff_state_the_narrow_boundary() -> None:
    payload = _load_handoff()
    codec_source = CODEC_PATH.read_text(encoding="utf-8")
    contract_source = CONTRACT_PATH.read_text(encoding="utf-8")
    replay_source = REPLAY_PATH.read_text(encoding="utf-8")
    public_source = PUBLIC_API_PATH.read_text(encoding="utf-8")
    focused_tests = FOCUSED_TEST_PATH.read_text(encoding="utf-8")
    handoff_doc = HANDOFF_DOC_PATH.read_text(encoding="utf-8")

    for literal in (
        "Schema.Union(",
        "RegisterManifestSchema",
        "ConfirmManifestSchema",
        "AdjudicateManifestSchema",
        "ValidatedNonAuthorizingStageUploadPostcondition",
        "TEST_ONLY_NON_AUTHORIZING",
        "STRUCTURAL_RECOVERY",
        "buildS2SStageUploadPostcondition",
        "reconstructS2SStageUploadPostcondition",
        "validateS2SStageUploadPostcondition",
    ):
        assert literal in codec_source
    for literal in (
        "12_583_176",
        "S2S_STAGE_UPLOAD_POSTCONDITION_MAX_OBSERVATION_COUNT = 11",
        "S2S_STAGE_UPLOAD_POSTCONDITION_ZIP_FRAMING_BYTES !== 264",
    ):
        assert literal in contract_source
    assert "validateS2SCurrentRunStageEvidence" in replay_source
    assert "predecessor artifact replay has no REGISTER consumer surface" in (
        replay_source
    )
    assert "s2s-stage-upload-postcondition" not in public_source
    assert "buildS2SStageUploadPostcondition" not in public_source

    for literal in (
        "round-trips every stage and successful attempt deterministically",
        "forged trusted build authority",
        "coherently regenerated reused IDs and nonmonotonic observations",
        "coherently resealed archive-reference mutation",
        "keeps REGISTER generic validation separate from predecessor replay",
    ):
        assert literal in focused_tests

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    for literal in (
        "1f45f4bad6907617cacac6525ea9edd8d9c7b6f4",
        "19/19",
        "310/310",
        "ValidatedNonAuthorizingStageUploadPostcondition",
        "No entry belongs in `F1_R8_RESULTS_LOG.md`",
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ):
        assert literal in handoff_doc


def test_v18_artifact_bindings_and_immutable_v17_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V17_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    assert len(bindings) == 19
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    assert str(PREDECESSOR_PATH.relative_to(ROOT)) in paths
    assert str(HANDOFF_DOC_PATH.relative_to(ROOT)) in paths
    assert str(FOCUSED_TEST_PATH.relative_to(ROOT)) in paths
    assert "tests/test_hswm_swm0w_s2s_effect_handoff_v18.py" in paths

    latest = _latest_binding_hashes(payload)
    for relative_path, expected in latest.items():
        assert SHA256_PATTERN.fullmatch(expected)
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected

    verification = payload["verification"]
    assert verification["runtime_implementation_changed"] is True
    assert verification["live_github_run_executed"] is False
    assert verification["typescript_check"] == "PASS"
    assert verification["focused_codec_tests"] == "19/19 PASS"
    assert verification["effect_runtime_tests"] == "310/310 PASS"
    assert verification["effect_runtime_test_files"] == "26/26 PASS"
    assert verification["effect_build"] == "PASS"
    assert verification["package_dry_run"] == (
        "PASS_208_FILES_APPROX_3_4_MB_UNPACKED"
    )
    assert verification["json_duplicate_key_check"] == "PASS"
    assert verification["artifact_binding_check"] == "PASS"
    assert verification["diff_check"] == "PASS"
    assert "Pi-only" in verification["claim_boundary"]


def test_v18_next_session_starts_at_authentic_capability_not_codec_rework() -> None:
    payload = _load_handoff()
    entrypoint = payload["next_session_entrypoint"]
    assert entrypoint == {
        "plan_path": str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "first_code_target": (
            "src/hswm/effect-runtime/src/"
            "s2s-stage-upload-assertion.ts"
        ),
        "first_test_target": (
            "src/hswm/effect-runtime/test/"
            "s2s-stage-upload-assertion.test.ts"
        ),
        "required_skill": "effect-ts-functional",
        "first_gate": (
            "MODULE_AUTHENTIC_PREPARED_CARRIER_CAPABILITY_ONE_USE_"
            "SAME_STAGE_ASSERTION_PERMIT_AND_PURE_OUTCOME_CLASSIFIER"
        ),
        "production_layer_rule": (
            "GATE_CLOSED_WHILE_WORKFLOW_SOURCE_BYTES_ARE_OPEN"
        ),
        "forbidden_claim": (
            "CODEC_BYTES_OR_SERIALIZED_PERMIT_EVIDENCE_CONFER_"
            "PRODUCTION_AUTHORITY"
        ),
    }
    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_V16_DESIGN_V17_HANDOFF_V18_HANDOFF_V18_KG_"
        "AND_EFFECT_SKILL"
    )
    assert "PRESERVE_THE_TWO_DIRTY_CONTINUAL_LIVE_PATHS" in order
    assert order[-1] == (
        "KEEP_WORKFLOW_FREEZE_PREREGISTRATION_DISPATCH_EVENT_10_AND_"
        "SCIENTIFIC_JUDGMENT_DOWNSTREAM"
    )
