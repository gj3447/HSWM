from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v17.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v16.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0W_S2S_SHARED_STAGE_ARTIFACT_SPEC_IMPLEMENTED_"
    "NEXT_SESSION_2026-08-23.md"
)
SPEC_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-stage-artifact-spec.ts"
POSTCONDITION_CONTRACT_PATH = (
    ROOT
    / "src/hswm/effect-runtime/src/"
    "s2s-stage-upload-postcondition-contract.ts"
)
PROFILE_PATH = ROOT / "src/hswm/effect-runtime/src/s2s-evidence-profile.ts"
PUBLIC_API_PATH = ROOT / "src/hswm/effect-runtime/src/index.ts"
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V16_SHA256 = (
    "7f0e4e9e51429390a9777963236872a08c500c75531628f929a331c522bb556b"
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


def test_v17_is_duplicate_key_safe_pi_only_implementation_checkpoint() -> None:
    try:
        json.loads('{"same": 1, "same": 2}', object_pairs_hook=_reject_duplicate_pairs)
    except ValueError as error:
        assert str(error) == "duplicate JSON key: same"
    else:
        raise AssertionError("duplicate-key guard did not fail closed")

    payload = _load_handoff()
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v17"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-shared-stage-artifact-specification-"
        "implemented-2026-08-23"
    )
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        "sym:EngineeringDesignCheckpoint:"
        "hswm-swm0w-s2s-stage-upload-assertion-2026-08-23"
    )
    assert payload["workspace_primary_implementation_commit"] == (
        "6c63ea77559da9ca9725eb99ac7e4c0241c5af3b"
    )
    assert payload["workspace_code_commit"] == (
        "242ff8a86ab47009a484354fd4e82737723c8a5b"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["architecture_projection"] == {
        "H": "UNCHANGED_NO_TOPOLOGY_OR_LIVING_HARNESS_EVIDENCE",
        "W": "UNCHANGED_NO_LEARNED_SEMANTIC_WEIGHT_RESULT",
        "A": "UNCHANGED_NO_ACTIVATION_OR_READOUT_RESULT",
        "F": "UNCHANGED_NO_FUNCTION_CELL_OR_SCIENTIFIC_VERDICT",
        "Pi": (
            "ROOT_PRIVATE_STAGE_ARTIFACT_POLICY_AND_POSTCONDITION_"
            "REPRESENTATION_BYTE_BUDGET_SKELETON_IMPLEMENTED"
        ),
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED",
    }


def test_v17_records_exact_shared_spec_and_distinct_postcondition_caps() -> None:
    payload = _load_handoff()
    implementation = payload["implemented_slice"]
    specs = payload["shared_stage_artifact_specification"]
    skeleton = payload["stage_upload_postcondition_contract_skeleton"]

    assert implementation["root_private_shared_specification"] is True
    assert implementation["stage_specific_literal_correlation_preserved"] is True
    assert implementation["live_artifact_policy_consumer_migrated"] is True
    assert implementation["predecessor_replay_consumer_migrated"] is True
    assert implementation["profile_descriptor_equivalence_verified"] is True
    assert implementation["package_root_exported"] is False

    expected = {
        "REGISTER": (
            "REGISTRATION",
            "register",
            "s2s-registration",
            "upload/registration_archive.zip",
            "upload/registration_postcondition.zip",
            4 * 1_048_576,
            [("control_receipt.json", 1_048_576)],
        ),
        "CONFIRM": (
            "CANDIDATE",
            "confirm",
            "s2s-candidate",
            "upload/candidate_archive.zip",
            "upload/candidate_postcondition.zip",
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
            spec["archive_maximum_bytes"],
            [
                (member["name"], member["maximum_bytes"])
                for member in spec["members"]
            ],
        ) == values
        assert spec["postcondition_carrier_maximum_bytes"] == 12_583_176
        assert spec["postcondition_profile_maximum_bytes"] == 16 * 1_048_576

    assert skeleton["members"] == ["manifest.json", "observations.bin"]
    assert skeleton["observation_counts"] == [7, 9, 11]
    assert skeleton["zip_framing_bytes"] == 264
    assert skeleton["carrier_maximum_bytes"] == 12_583_176
    assert skeleton["profile_occurrence_maximum_bytes"] == 16 * 1_048_576
    assert skeleton["effect_schema_implemented"] is False
    assert skeleton["strict_codec_and_reconstruction_implemented"] is False


def test_v17_keeps_every_production_and_scientific_gate_open() -> None:
    payload = _load_handoff()
    for flag in (
        "stage_upload_postcondition_schema_implemented",
        "stage_upload_postcondition_codec_implemented",
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

    inventory = payload["healthy_success_profile_inventory"]
    assert inventory == {
        "total_occurrences": 48,
        "construct_and_recover_validation": 20,
        "semantic_core_without_attachment_codec": 19,
        "missing_carrier_or_source": 9,
        "production_stage_upload_postcondition_occurrences_filled": 0,
        "inventory_changed_by_this_slice": False,
    }
    profile_source = PROFILE_PATH.read_text(encoding="utf-8")
    assert profile_source.count("hswm-swm0w-s2s-stage-upload-postcondition/v1") == 3

    nodes = payload["nodes"]
    relations = payload["relations"]
    uids = [node["uid"] for node in nodes]
    assert len(uids) == len(set(uids))
    uid_set = set(uids)
    assert all(relation["from_uid"] in uid_set for relation in relations)
    assert all(relation["to_uid"] in uid_set for relation in relations)
    assert not any(relation["type"] == "EVIDENCE_FOR" for relation in relations)
    assert all(node.get("scientific_status") != "PASS" for node in nodes)


def test_v17_sources_and_handoff_state_the_narrow_claim() -> None:
    payload = _load_handoff()
    spec_source = SPEC_PATH.read_text(encoding="utf-8")
    contract_source = POSTCONDITION_CONTRACT_PATH.read_text(encoding="utf-8")
    public_source = PUBLIC_API_PATH.read_text(encoding="utf-8")
    handoff_doc = HANDOFF_DOC_PATH.read_text(encoding="utf-8")

    for literal in (
        "S2S_STAGE_ARTIFACT_SPECS",
        "postconditionCarrierMaximumBytes",
        "postconditionProfileMaximumBytes",
        "satisfies Readonly",
    ):
        assert literal in spec_source
    assert "as \"upload/registration_archive.zip\"" not in (
        ROOT
        / "src/hswm/effect-runtime/src/s2s-stage-artifact-read-replay.ts"
    ).read_text(encoding="utf-8")
    assert "S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATION_COUNTS" in contract_source
    assert "S2S_STAGE_ARTIFACT_SPECS" not in public_source
    assert "s2s-stage-artifact-spec" not in public_source

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    for literal in (
        "12,583,176",
        "not a production postcondition codec",
        "291 passing Effect tests",
        "No entry belongs in `F1_R8_RESULTS_LOG.md`",
        "src/hswm/experiments/continual_live.py",
    ):
        assert literal in handoff_doc


def test_v17_artifact_bindings_and_immutable_v16_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V16_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    assert len(bindings) == 12
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))

    latest = _latest_binding_hashes(payload)
    for relative_path, expected in latest.items():
        assert SHA256_PATTERN.fullmatch(expected)
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected

    verification = payload["verification"]
    assert verification["runtime_implementation_changed"] is True
    assert verification["live_github_run_executed"] is False
    assert verification["effect_runtime_tests"] == "291/291 PASS"
    assert "Pi-only implementation checkpoint" in verification["claim_boundary"]
