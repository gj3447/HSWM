from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v19.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v18.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_PREPARED_CARRIER_ASSERTION_MECHANICS_IMPLEMENTED_"
    "NEXT_SESSION_2026-08-23.md"
)
PREPARED_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-prepared-stage-carrier.ts"
)
ASSERTION_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts"
)
OUTCOME_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-stage-upload-outcome.ts"
POSTCONDITION_PATH = (
    ROOT / "src/hswm/effect-runtime/src/s2s-stage-upload-postcondition.ts"
)
PUBLIC_API_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
PROFILE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-profile.ts"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V18_SHA256 = (
    "38b4e2402320568997d982df261a6b835f6464da69ed3eb903c668b3d7f1bc2e"
)
CODE_COMMIT = "36b4c9bd45796631e1a9c891eb2f32659da5122a"
PARENT_COMMIT = "051e824bc60c340c3278f13d9acb2d2fd20166a6"
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


def test_v19_is_duplicate_key_safe_unique_v18_successor_and_pi_only() -> None:
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

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v19"
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        predecessor["bundle_uid"]
    )
    assert payload["workspace_parent_commit"] == PARENT_COMMIT
    assert payload["workspace_code_commit"] == CODE_COMMIT
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_NO_TOPOLOGY_OR_LIVING_HARNESS_EVIDENCE",
        "W": "UNCHANGED_NO_LEARNED_SEMANTIC_WEIGHT_RESULT",
        "A": "UNCHANGED_NO_ACTIVATION_OR_READOUT_RESULT",
        "F": "UNCHANGED_NO_FUNCTION_CELL_OR_SCIENTIFIC_VERDICT",
        "Pi": (
            "MODULE_AUTHENTIC_PREPARED_CARRIER_AND_ONE_USE_TEST_FALSIFIED_"
            "ASSERTION_MECHANICS_WITH_PURE_NONAUTHORIZING_OUTCOME_TAXONOMY_"
            "IMPLEMENTED"
        ),
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }


def test_v19_records_exact_process_local_mechanics_boundary() -> None:
    payload = _load_handoff()
    implementation = payload["implemented_slice"]
    prepared = payload["prepared_carrier_contract"]
    permit = payload["assertion_permit_mechanics"]
    taxonomy = payload["outcome_taxonomy"]

    for key in (
        "prepared_stage_carrier_capability_implemented",
        "production_and_test_registries_disjoint",
        "one_semantic_production_slot_anti_replenishing",
        "same_bytes_idempotent_different_bytes_conflict",
        "authentic_predecessor_replay_required",
        "atomic_assertion_permit_reservation",
        "burn_on_typed_failure_defect_interruption_and_nonhealthy",
        "exact_one_two_three_attempt_topology",
        "pure_upload_outcome_classifier_implemented",
        "test_only_fake_observer_probe_implemented",
    ):
        assert implementation[key] is True
    for key in (
        "production_observation_admission_implemented",
        "production_assertion_permit_use_implemented",
        "production_assertion_evidence_sealing_implemented",
        "production_context_tag_layer_implemented",
        "package_root_exported",
        "network_or_live_github_io_added",
        "production_authority_issued",
    ):
        assert implementation[key] is False

    assert prepared["schema_identifier"] == (
        "hswm-swm0w-s2s-prepared-stage-carrier/v1"
    )
    assert prepared["stages"] == ["REGISTER", "CONFIRM", "ADJUDICATE"]
    assert prepared["ordered_member_counts"] == {
        "REGISTER": 1,
        "CONFIRM": 2,
        "ADJUDICATE": 2,
    }
    assert prepared["test_scope"] == "TEST_ONLY_NON_AUTHORIZING"
    assert prepared["genuine_production_capability_issued"] is False

    assert permit["state_machine"] == [
        "ISSUED",
        "IN_FLIGHT",
        "SPENT_SUCCESS",
        "SPENT_VOID",
        "CLOSED",
    ]
    assert permit["successful_attempt_ordinals"] == [1, 2, 3]
    assert permit["complete_ledger_entry_counts"] == [12, 14, 16]
    assert permit["postcondition_observation_counts"] == [7, 9, 11]
    assert permit["fake_observer_call_counts"] == [8, 10, 12]
    assert permit["bounded_settle_counts"] == [0, 1, 2]
    assert permit["ledger_capacity"] == 16
    assert permit["production_use_error"] == "PRODUCTION_ASSERTION_SHELL_OPEN"
    assert permit["production_evidence_sealing_implemented"] is False

    assert taxonomy["literals"] == [
        "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED",
        "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
        "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION",
        "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
        "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
        "EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH",
        "COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED",
    ]
    assert taxonomy["healthy_count"] == 1
    assert taxonomy["definitive_failure_count"] == 1
    assert taxonomy["reconciliation_required_count"] == 5
    assert taxonomy["authority_scope"] == "NON_AUTHORIZING_PURE_CLASSIFIER"
    assert taxonomy["implicit_retry_authorized"] is False
    assert taxonomy["external_exactly_once_claimed"] is False


def test_v19_source_invariants_preserve_authority_and_effect_v3_shape() -> None:
    prepared = PREPARED_PATH.read_text(encoding="utf-8")
    assertion = ASSERTION_PATH.read_text(encoding="utf-8")
    outcome = OUTCOME_PATH.read_text(encoding="utf-8")
    postcondition = POSTCONDITION_PATH.read_text(encoding="utf-8")
    public_api = PUBLIC_API_PATH.read_text(encoding="utf-8")

    for literal in (
        "const PRODUCTION_CAPABILITIES = new WeakMap",
        "const TEST_ONLY_CAPABILITIES = new WeakMap",
        "let PRODUCTION_IDENTITY_SLOT",
        "inspectS2SCurrentRunStageAuthority",
        "inspectS2SStageArtifactReadReplaySnapshot",
        "PREPARATION_CONFLICT",
        "TEST_ONLY_NON_AUTHORIZING",
    ):
        assert literal in prepared

    for literal in (
        "Ref.modify",
        "Effect.acquireUseRelease",
        "PRODUCTION_ASSERTION_SHELL_OPEN",
        "closeTestScopeUnlessForeignUseIsInFlight",
        "appendS2SStageUploadAssertionLedgerEntryForTest",
        "useS2SStageUploadAssertionPermitForTest",
        "snapshotS2SStageUploadAssertionPermitEvidenceForTest",
        "probeS2SStageUploadAssertionMechanicsForTest",
    ):
        assert literal in assertion

    assert outcome.count('"ReconciliationRequired"') >= 2
    for literal in (
        "NON_AUTHORIZING_PURE_CLASSIFIER",
        "authorizationClaimed: false",
        "implicitRetryAuthorized: false",
        "externalExactlyOnceClaimed: false",
    ):
        assert literal in outcome

    assert 'evidence.authorityScope !== "TEST_ONLY_NON_AUTHORIZING"' in (
        postcondition
    )
    for module_name in (
        "s2s-prepared-stage-carrier",
        "s2s-stage-upload-assertion",
        "s2s-stage-upload-outcome",
    ):
        assert module_name not in public_api


def test_v19_keeps_live_profile_workflow_durability_and_science_open() -> None:
    payload = _load_handoff()
    assert payload["stage_upload_postcondition_schema_implemented"] is True
    assert payload["stage_upload_postcondition_codec_implemented"] is True
    assert payload["prepared_stage_carrier_capability_implemented"] is True
    assert payload["same_stage_upload_assertion_mechanics_implemented"] is True
    assert payload["pure_upload_outcome_classifier_implemented"] is True
    assert payload["test_only_fake_observer_probe_implemented"] is True
    for flag in (
        "production_same_stage_upload_assertion_shell_implemented",
        "production_upload_assertion_replay_snapshot_implemented",
        "production_assertion_permit_evidence_sealed",
        "complete_stage_profile_commit_bridge_implemented",
        "mandatory_upload_postconditions_implemented",
        "external_shared_durable_store_feasibility_proved",
        "external_shared_durable_store_deployed",
        "external_durable_root_authenticated",
        "independent_process_restart_recovery_observed",
        "genuine_current_run_capability_issued",
        "genuine_prepared_stage_carrier_capability_issued",
        "genuine_stage_artifact_capability_issued",
        "genuine_stage_upload_assertion_scope_issued",
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

    assert payload["open_gates"][0] == {
        "uid": "sym:OpenGate:s2s-stage-upload-assertion-shell",
        "priority": "NEXT",
        "status": "OPEN",
        "required_closure": (
            "ROOT_PRIVATE_PRODUCTION_EFFECT_ASSERT_RECONCILE_SHELL_REPLAY_"
            "SNAPSHOT_REAL_ARCHIVE_MEMBER_VALIDATION_BOUNDED_SETTLING_"
            "INTERRUPTION_AND_UNKNOWN_OUTCOME_DISCIPLINE"
        ),
    }
    nodes = payload["nodes"]
    relations = payload["relations"]
    uids = [node["uid"] for node in nodes]
    assert len(uids) == len(set(uids))
    uid_set = set(uids)
    assert all(relation["from_uid"] in uid_set for relation in relations)
    assert all(relation["to_uid"] in uid_set for relation in relations)
    assert not any(relation["type"] == "EVIDENCE_FOR" for relation in relations)
    assert all(node.get("scientific_status") != "PASS" for node in nodes)


def test_v19_artifact_bindings_verification_and_handoff_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V18_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    assert len(bindings) >= 15
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    for required in (
        str(PREDECESSOR_PATH.relative_to(ROOT)),
        str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        str(PREPARED_PATH.relative_to(ROOT)),
        str(ASSERTION_PATH.relative_to(ROOT)),
        str(OUTCOME_PATH.relative_to(ROOT)),
        "tests/test_hswm_swm0w_s2s_effect_handoff_v19.py",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
    ):
        assert required in paths
    latest = _latest_binding_hashes(payload)
    for relative_path, expected in latest.items():
        assert SHA256_PATTERN.fullmatch(expected)
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected

    verification = payload["verification"]
    assert verification["typescript_check"] == "PASS"
    assert verification["focused_slice_tests"] == "52/52 PASS"
    assert verification["new_mechanics_tests"] == "33/33 PASS"
    assert verification["effect_runtime_tests"] == "343/343 PASS"
    assert verification["effect_runtime_test_files"] == "29/29 PASS"
    assert verification["effect_build"] == "PASS"
    assert verification["package_dry_run"] == (
        "PASS_223_FILES_3_6_MB_UNPACKED"
    )
    assert verification["live_github_run_executed"] is False
    assert "Pi-only" in verification["claim_boundary"]

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    handoff = HANDOFF_DOC_PATH.read_text(encoding="utf-8")
    for literal in (
        CODE_COMMIT,
        "52/52",
        "343/343",
        "PRODUCTION_ASSERTION_SHELL_OPEN",
        "No entry belongs in `F1_R8_RESULTS_LOG.md`",
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ):
        assert literal in handoff


def test_v19_next_session_starts_at_live_shell_not_mechanics_rework() -> None:
    payload = _load_handoff()
    assert payload["next_session_entrypoint"] == {
        "plan_path": str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "first_code_target": (
            "src/hswm/effect-runtime/src/s2s-stage-upload-assertion.ts"
        ),
        "first_test_target": (
            "src/hswm/effect-runtime/test/s2s-stage-upload-assertion.test.ts"
        ),
        "required_skill": "effect-ts-functional",
        "first_gate": (
            "ROOT_PRIVATE_PRODUCTION_EFFECT_ASSERTION_RECONCILIATION_SHELL_"
            "AND_REPLAY_SNAPSHOT"
        ),
        "production_layer_rule": (
            "GATE_CLOSED_WHILE_WORKFLOW_SOURCE_BYTES_ARE_OPEN"
        ),
        "forbidden_claim": (
            "TEST_PROBE_SERIALIZED_TRUSTED_EVIDENCE_OR_CODEC_BYTES_CONFER_"
            "PRODUCTION_AUTHORITY"
        ),
    }
    order = payload["next_session_order"]
    assert order[0] == (
        "READ_CONSTITUTION_V16_DESIGN_V18_HANDOFF_V19_HANDOFF_V19_KG_"
        "AND_EFFECT_SKILL"
    )
    assert "PRESERVE_THE_TWO_DIRTY_CONTINUAL_LIVE_PATHS" in order
    assert "DO_NOT_REWORK_CLOSED_PREPARED_CARRIER_PERMIT_OR_TAXONOMY_MECHANICS" in (
        order
    )
    assert order[-1] == (
        "KEEP_WORKFLOW_FREEZE_PREREGISTRATION_DISPATCH_EVENT_10_AND_"
        "SCIENTIFIC_JUDGMENT_DOWNSTREAM"
    )
