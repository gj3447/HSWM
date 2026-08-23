from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v16.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v15.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_STAGE_UPLOAD_ASSERTION_DESIGN_NEXT_SESSION_2026-08-23.md"
)
PROFILE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-profile.ts"
RUN_AUTHORITY_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-run-authority.ts"
WORKFLOW_CONTRACT_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-workflow-contract.ts"
)
PRODUCTION_WORKFLOW_PATH = ROOT / ".github/workflows/swm0w-s2s-confirmatory.yml"
PRODUCTION_PREREG_PATH = ROOT / "prereg/PREREG_SWM0W_S2S_GATE_V1.json"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V15_SHA256 = (
    "391c824ce1814090a340838d1038756fb4bdec30beeac8215a8af70d58d32c26"
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


def test_v16_is_duplicate_key_safe_pi_only_design_checkpoint() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    payload = _load_handoff()
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v16"
    assert payload["bundle_uid"] == (
        "sym:EngineeringDesignCheckpoint:"
        "hswm-swm0w-s2s-stage-upload-assertion-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-test-only-golden-local-vertical-composition-"
        "implemented-2026-08-23"
    )
    assert payload["workspace_parent_commit"] == (
        "43f2198a1b89634e7f23726fbc6cbb6996da8e53"
    )
    assert payload["workspace_primary_implementation_commit"] == (
        "6ae27edb13b37985d0987b3b2b64bb9ec7efded3"
    )
    assert payload["workspace_code_commit"] == (
        "6ae27edb13b37985d0987b3b2b64bb9ec7efded3"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["design_status"] == (
        "PRODUCTION_INTENDED_STAGE_UPLOAD_POSTCONDITION_AND_SAME_STAGE_"
        "ASSERTION_BOUNDARY_AUDITED_AND_FROZEN"
    )
    assert payload["implementation_status"] == (
        "NOT_STARTED_STRICT_CODEC_AND_NON_AUTHORIZING_ASSERTION_MECHANICS_NEXT"
    )

    for flag in (
        "prior_golden_local_vertical_composition_implemented",
        "prior_local_test_only_upload_readback_vertical_slice_implemented",
        "production_carrier_local_receipt_semantic_gap_audited",
        "production_stage_upload_assertion_design_frozen",
        "prepare_external_action_assert_phase_ownership_frozen",
        "shared_stage_artifact_specification_designed",
        "stage_upload_postcondition_representation_frozen",
        "same_stage_observation_topology_frozen",
        "complete_stage_single_commit_recovery_rule_frozen",
        "external_shared_posix_feasibility_gate_identified",
    ):
        assert payload[flag] is True
    for flag in (
        "production_carriers_accept_local_test_receipts",
        "stage_upload_postcondition_schema_implemented",
        "same_stage_upload_assertion_mechanics_implemented",
        "prepared_stage_carrier_capability_implemented",
        "complete_stage_profile_commit_bridge_implemented",
        "mandatory_upload_postconditions_implemented",
        "all_healthy_success_attachment_occurrences_real",
        "external_shared_durable_store_feasibility_proved",
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
        "H": "TARGET_IDENTITY_UNCHANGED_NO_NEW_TOPOLOGY_OR_COGNITION_EVIDENCE",
        "W": "NO_LEARNED_SEMANTIC_WEIGHT_RESULT",
        "A": "NO_ACTIVATION_OR_READOUT_EFFICACY_RESULT",
        "F": "NO_CONFIRMATORY_FUNCTION_CELL_OR_SCIENTIFIC_RESULT",
        "Pi": (
            "DOCUMENTATION_ONLY_STAGE_LOCAL_UPLOAD_ASSERTION_AUTHORITY_"
            "TRANSACTION_OBSERVATION_REPLAY_CAP_AND_RECOVERY_BOUNDARY_FROZEN"
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


def test_v16_freezes_phase_ownership_and_fixed_stage_mapping() -> None:
    payload = _load_handoff()
    connector = payload["frozen_two_phase_connector"]
    action = payload["pinned_external_action_contract"]
    specs = payload["shared_stage_artifact_specification"]

    assert connector["shape"] == (
        "PREPARE_CARRIER_THEN_PINNED_EXTERNAL_ACTION_THEN_ASSERT_RECONCILE"
    )
    assert connector["effect_owns_upload_side_effect"] is False
    assert connector["workflow_owns_upload_side_effect"] is True
    assert connector["prepare_starts_from_authentic_current_stage_authority"] is True
    assert connector["assertion_starts_from_same_authority_and_prepared_capability"] is True
    assert connector["caller_selected_identity_or_policy_allowed"] is False
    assert connector["uploader_return_used_as_evidence"] is False
    assert connector["external_exactly_once_claimed"] is False
    assert connector["production_layer_gate"] == (
        "CLOSED_WHILE_WORKFLOW_SOURCE_BYTES_OPEN"
    )

    assert action == {
        "action": (
            "actions/upload-artifact@"
            "ea165f8d65b6e75b540449e92b4886f43607fa02"
        ),
        "if_no_files_found": "error",
        "compression_level": 0,
        "retention_days": 90,
        "overwrite": False,
        "include_hidden_files": False,
        "action_outputs": "UNTRUSTED_HINTS_OR_DIAGNOSTICS_ONLY",
        "internal_or_external_retry_count_claimed": False,
        "publication_exactly_once_claimed": False,
    }

    assert specs["root_private_symbol"] == "S2S_STAGE_ARTIFACT_SPECS"
    assert specs["package_root_exported"] is False
    expected = {
        "REGISTER": (
            "REGISTRATION",
            "register",
            "s2s-registration",
            "upload/registration_archive.zip",
            "upload/registration_postcondition.zip",
            "hswm-swm0w-s2s-registration-carrier/v1",
            4 * 1_048_576,
            [("control_receipt.json", 1_048_576)],
        ),
        "CONFIRM": (
            "CANDIDATE",
            "confirm",
            "s2s-candidate",
            "upload/candidate_archive.zip",
            "upload/candidate_postcondition.zip",
            "hswm-swm0w-s2s-candidate-carrier/v1",
            64 * 1_048_576,
            [
                ("control_receipt.json", 1_048_576),
                ("numeric_candidate.json", 60 * 1_048_576),
            ],
        ),
        "ADJUDICATE": (
            "ADJUDICATION",
            "adjudicate",
            "s2s-adjudication",
            "upload/adjudication_archive.zip",
            "upload/adjudication_postcondition.zip",
            "hswm-swm0w-s2s-adjudication-carrier/v1",
            4 * 1_048_576,
            [
                ("control_receipt.json", 1_048_576),
                ("numeric_adjudication.json", 3 * 1_048_576),
            ],
        ),
    }
    for stage, values in expected.items():
        spec = specs[stage]
        assert (
            spec["role"],
            spec["job"],
            spec["artifact_name"],
            spec["archive_logical_name"],
            spec["postcondition_logical_name"],
            spec["carrier_schema"],
            spec["archive_maximum_bytes"],
            [
                (member["name"], member["maximum_bytes"])
                for member in spec["members"]
            ],
        ) == values


def test_v16_freezes_replayable_postcondition_math_and_claim_limits() -> None:
    payload = _load_handoff()
    contract = payload["stage_upload_postcondition_contract"]
    observation = payload["same_stage_observation_contract"]
    recovery = payload["complete_stage_recovery_contract"]

    assert contract["schema_version"] == (
        "hswm-swm0w-s2s-stage-upload-postcondition/v1"
    )
    assert contract["representation"] == (
        "STORED_ZIP_COMPACT_MANIFEST_CONTIGUOUS_OBSERVATIONS_"
        "CURRENT_STAGE_ARCHIVE_REFERENCE"
    )
    assert contract["classification"] == (
        "PRODUCTION_INTENDED_STAGE_UPLOAD_POSTCONDITION"
    )
    assert contract["publication_claim"] == (
        "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED"
    )
    assert contract["members"] == ["manifest.json", "observations.bin"]
    assert contract["successful_attempt_ordinals"] == [1, 2, 3]
    assert contract["observation_counts"] == [7, 9, 11]
    assert contract["observation_blob_maximum_bytes"] == 11 * 1_048_576
    assert contract["zip_framing_bytes"] == 264
    assert contract["carrier_maximum_bytes"] == (
        contract["manifest_maximum_bytes"]
        + contract["observation_blob_maximum_bytes"]
        + contract["zip_framing_bytes"]
    )
    assert contract["carrier_maximum_bytes"] < contract[
        "profile_occurrence_maximum_bytes"
    ]
    for key in (
        "publisher_return_used_as_evidence",
        "historical_uniqueness_claimed",
        "external_exactly_once_claimed",
        "cross_worker_replay_prevention_claimed",
        "cross_module_copy_replay_prevention_claimed",
        "cross_process_replay_prevention_claimed",
        "durable_replay_prevention_claimed",
        "postcondition_embedded_in_uploaded_archive",
        "envelope_manifest_or_claim_hash_in_archive_reference",
    ):
        assert contract[key] is False
    assert contract["archive_members_equal_prepared_members_required"] is True
    assert contract["canonical_self_hash_required"] is True
    assert contract["strict_unknown_reconstruction_required"] is True

    assert observation["current_job_expected_status"] == "in_progress"
    assert observation["current_job_expected_conclusion"] is None
    assert observation["artifact_producer_job_id_available_from_github_api"] is False
    assert observation["bounded_absence_is_proof_of_nonpublication"] is False
    assert observation["independent_artifact_requery_and_download_required"] is True
    assert observation["fresh_final_run_bracket_required"] is True

    assert recovery["one_create_only_commit_per_stage_identity"] is True
    assert recovery["competing_partial_commits_allowed"] is False
    assert recovery["post_recovery_validation_identical_to_pre_commit"] is True
    assert recovery["register_requires_fake_predecessor_replay"] is False
    assert recovery["process_local_brand_is_durable_authentication"] is False
    assert recovery["committed_readback_failed_requires_reconciliation"] is True
    assert recovery["implicit_retry_allowed"] is False


def test_v16_keeps_production_sources_and_profile_occurrences_open() -> None:
    payload = _load_handoff()
    audited = payload["audited_current_state"]
    inventory = payload["healthy_success_profile_inventory"]
    feasibility = payload["external_shared_posix_feasibility_gate"]
    profile_source = PROFILE_PATH.read_text(encoding="utf-8")
    run_authority_source = RUN_AUTHORITY_PATH.read_text(encoding="utf-8")
    workflow_contract_source = WORKFLOW_CONTRACT_PATH.read_text(encoding="utf-8")
    handoff_doc = HANDOFF_DOC_PATH.read_text(encoding="utf-8")

    assert audited["production_carrier_builder_non_test_call_sites"] == 0
    assert audited["lifecycle_event_non_test_constructors"] == 0
    assert audited["existing_stage_artifact_operations"] == "PREDECESSOR_READS_ONLY"
    assert audited["register_existing_artifact_read_operation_count"] == 0
    assert audited["production_workflow_source_policy"] == (
        "OPEN_UNTIL_WORKFLOW_BYTES_EXIST"
    )
    assert audited["production_workflow_file_present"] is False
    assert audited["production_preregistration_present"] is False
    assert not PRODUCTION_WORKFLOW_PATH.exists()
    assert not PRODUCTION_PREREG_PATH.exists()
    assert "OPEN_UNTIL_WORKFLOW_BYTES_EXIST" in run_authority_source
    assert "OPEN_UNTIL_WORKFLOW_BYTES_EXIST" in workflow_contract_source

    assert inventory["classification_counts"] == {
        "CONSTRUCT_AND_VALIDATE": 20,
        "SEMANTIC_CORE_NO_ATTACHMENT_CODEC": 19,
        "MISSING_CARRIER_OR_SOURCE": 9,
    }
    assert inventory["production_stage_upload_postcondition_occurrences_filled"] == 0
    assert inventory["test_only_golden_occurrences_count_as_production"] is False
    assert profile_source.count("hswm-swm0w-s2s-stage-upload-postcondition/v1") == 3

    assert feasibility["priority"] == (
        "P0_AFTER_CODEC_AND_BEFORE_SIX_STAGE_PROGRAM_EXPANSION"
    )
    assert feasibility["status"] == "OPEN"
    assert feasibility["deployment_is_predecessor_to_codec"] is False
    assert feasibility[
        "feasibility_is_predecessor_to_broad_stage_program_implementation"
    ] is True

    for literal in (
        "prepare carrier -> external pinned upload step -> assert/reconcile",
        "S2S_STAGE_ARTIFACT_SPECS",
        "12,583,176",
        "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED",
        "No entry belongs in `F1_R8_RESULTS_LOG.md`",
    ):
        assert literal in handoff_doc


def test_v16_artifact_bindings_and_immutable_v15_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V15_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    assert len(bindings) == 13
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))

    latest = _latest_binding_hashes(payload)
    for relative_path, expected in latest.items():
        assert SHA256_PATTERN.fullmatch(expected)
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected

    verification = payload["verification"]
    assert verification["runtime_implementation_changed"] is False
    assert verification["live_github_run_executed"] is False
    assert "Documentation-only Pi design checkpoint" in verification[
        "claim_boundary"
    ]
