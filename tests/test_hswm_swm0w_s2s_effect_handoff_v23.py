from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v23.json"
PREDECESSOR_PATH = ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v22.json"
HANDOFF_DOC_PATH = (
    ROOT
    / "docs/operations/"
    "HSWM_SWM0_ROLE_AWARE_TYPESCRIPT_CORE_IMPLEMENTED_"
    "NEXT_SESSION_2026-08-23.md"
)
HANDOFF_GLOB = "HSWM_SWM0W_S2S_EFFECT_HANDOFF.v*.json"
IMMUTABLE_V22_SHA256 = (
    "b410fbf2193258bc4edefa8a9c29151eed342e434b9521798a651c741f2cede1"
)
WORKSPACE_PARENT = "1a8a1db806bac3f36cd88b566bf14bd90604ce1e"
IMPLEMENTATION_COMMIT = "a9aff88d37f5d0adaaf97c11fbfec643aa36eac0"
FIXTURE_SHA256 = "65234fd31745dec2f8f616b01bef329a40044d064448e169d87ebcfb361f4ef6"
FIXTURE_RECEIPT = "8c437d71ff8af403e546729eb24707ef8b331b2c9520f48df20ae8822b0d3d7b"
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


def test_v23_is_the_unique_v22_successor_and_records_the_bounded_delta() -> None:
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
    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v23"
    assert payload["supersedes_bundle_uid_for_continuation"] == (
        predecessor["bundle_uid"]
    )
    assert payload["workspace_parent_commit"] == WORKSPACE_PARENT
    assert payload["workspace_code_commit"] == IMPLEMENTATION_COMMIT
    assert payload["workspace_documentation_parent"] == IMPLEMENTATION_COMMIT
    assert payload["runtime_implementation_changed"] is True
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["architecture_projection"] == {
        "H": "ADVANCED_BOUNDED_COMPILED_PROJECTION_ONE_HYPEREDGE_SIX_EXPLICIT_ROLE_MEMBER_NODE_INCIDENCES_ENUMERATION_INDEPENDENT_NO_PERSISTENCE_PROVENANCE_OR_TOPOLOGY",
        "W": "ADVANCED_RECIPIENT_CONDITIONED_T16_FORWARD_OPERATOR_OVER_PYTHON_ARCHIVE_PARAMETER_PROJECTIONS_NO_TYPESCRIPT_TRAINING_CAUSAL_EFFICACY_FAST_SLOW_WEIGHT_OR_DURABILITY",
        "A": "ADVANCED_ONE_SIMULTANEOUS_SIX_BY_FOUR_TO_SIX_BY_TWO_SWEEP_NO_TOKEN_NATIVE_ROUTING_RECURRENCE_OR_TRAJECTORY",
        "F": "UNCHANGED_NO_LLM_FUNCTION_CELL_TYPED_TOKEN_GENERATION_OR_EFFICACY",
        "Pi": "ADVANCED_LOCAL_ENGINEERING_SCHEMA_HASH_SNAPSHOT_TYPED_FAILURE_AND_INTERVENTION_BOUNDARY_ONLY_NO_PRODUCTION_AUTHORITY_CAPABILITY_RESOURCE_ROOT_OR_PROCESS_CONTINUITY",
        "outcome_bound_causal_learning_loop": "NOT_ADVANCED_BY_T16_COMMIT_NO_COMPOSED_ELIGIBILITY_OUTCOME_DELTA_W_DELTA_H_OR_CHANGED_NEXT_BEHAVIOR",
    }


def test_v23_graph_maps_the_core_to_h_w_a_without_claiming_f_or_learning() -> None:
    payload = _load_handoff()
    nodes = payload["nodes"]
    relations = payload["relations"]
    assert type(nodes) is list
    assert type(relations) is list
    node_ids = {node["id"] for node in nodes}
    assert len(node_ids) == len(nodes)
    assert all(node["scientific_status"] == "UNJUDGED" for node in nodes)
    for relation in relations:
        assert relation["subject"] in node_ids
        assert relation["object"] in node_ids
    predicates = {relation["predicate"] for relation in relations}
    assert "EVIDENCE_FOR" not in predicates
    assert {
        "IMPLEMENTS_BOUNDED_PROJECTION_OF",
        "PROJECTS_H",
        "PROJECTS_W",
        "PROJECTS_A",
        "BOUNDED_BY",
        "VERIFIED_BY",
        "DEFERS",
        "SUPERSEDES_FOR_CONTINUATION",
    }.issubset(predicates)
    delta = payload["conceptual_delta"]
    assert delta["target_identity_closed"] is True
    assert delta["bounded_engineering_H_W_A_conjunction_exists"] is True
    assert delta["llm_function_cell_exists"] is False
    assert delta["outcome_causes_future_state_transition"] is False
    assert delta["complete_hswm_claimed"] is False


def test_v23_core_contract_and_hostile_boundary_are_exact() -> None:
    payload = _load_handoff()
    core = payload["typescript_role_aware_core"]
    assert core["implementation_commit"] == IMPLEMENTATION_COMMIT
    assert core["scope"] == {
        "hyperedges": 1,
        "roles": 3,
        "members_per_role": 2,
        "input_width": 4,
        "output_width": 2,
        "hidden_width": 16,
        "sweeps": 1,
        "parameters": 870,
        "parameter_bytes": 6960,
    }
    assert core["parameter_shapes"] == {
        "phi_w": [3, 4, 16],
        "psi_w": [3, 4, 16],
        "unary_w": [3, 2, 16],
        "pair_w": [3, 3, 2, 16],
        "q_w": [3, 2, 16],
        "out_b": [3, 2],
    }
    assert core["pure_typescript_numeric_center"] is True
    assert core["effect_boundary"] == ["Schema", "Either", "Data.TaggedError"]
    assert core["enumeration_order_semantic"] is False
    assert core["package_root_exported"] is False
    assert core["typescript_training_claimed"] is False

    boundary = payload["strict_boundary"]
    assert boundary["per_string_character_cap"] == 4096
    assert boundary["cumulative_string_and_key_character_cap"] == 16384
    assert boundary["fixed_base64_lengths"] == [2048, 2048, 1024, 3072, 1024, 64]
    assert boundary["q_receipt_base64_length"] == 1024
    assert boundary["proxy_or_accessor_traps_invoked"] is False
    q_restore = payload["q_restore_binding"]
    assert q_restore["private_original_q_snapshot_required"] is True
    assert q_restore["private_base_commitments_required"] is True
    assert q_restore["coherent_self_hashed_forgery_rejected"] is True
    assert q_restore["cross_model_replay_rejected"] is True

    core_source = (
        ROOT / "src/hswm/effect-runtime/src/swm0-role-aware-core.ts"
    ).read_text(encoding="utf-8")
    schema_source = (
        ROOT / "src/hswm/effect-runtime/src/swm0-role-aware-core-schema.ts"
    ).read_text(encoding="utf-8")
    root_source = (ROOT / "src/hswm/effect-runtime/src/index.ts").read_text(
        encoding="utf-8"
    )
    assert "interface QRestorationSnapshot" in core_source
    assert "stringCharacters" in core_source
    assert "Schema.length(encodedLength)" in schema_source
    assert "swm0-role-aware-core" not in root_source


def test_v23_fixture_is_exact_and_uses_the_authoritative_python_parser() -> None:
    payload = _load_handoff()
    fixture_contract = payload["python_parity_fixture"]
    fixture_path = ROOT / fixture_contract["path"]
    raw = fixture_path.read_bytes()
    assert len(raw) == fixture_contract["byte_length"] == 172400
    assert hashlib.sha256(raw).hexdigest() == fixture_contract["raw_sha256"]
    assert fixture_contract["raw_sha256"] == FIXTURE_SHA256
    fixture = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs)
    assert raw == (
        json.dumps(
            fixture,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    receipt = fixture.pop("receipt_sha256")
    canonical_unsigned = json.dumps(
        fixture,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    assert receipt == hashlib.sha256(canonical_unsigned).hexdigest()
    assert receipt == fixture_contract["receipt_sha256"] == FIXTURE_RECEIPT
    assert [model["projection"]["parameters_sha256"] for model in fixture["models"]] == [
        "02169d99cf2f376105851245dd99f30b627eba7d89a7e3f87e556284ede71c4b",
        "94548fc587c16d29764292857daa4960b5a75d6dec42ce09b2d5bcabe20aead1",
    ]
    assert [len(model["worlds"]) for model in fixture["models"]] == [6, 6]

    python_test = (
        ROOT / "tests/test_hswm_swm0_role_aware_core_fixture.py"
    ).read_text(encoding="utf-8")
    generator = (
        ROOT / "_research/swm0_role_aware_core/generate_parity_fixture.py"
    ).read_text(encoding="utf-8")
    assert "parse_learned_model_archive" in python_test
    assert 'pair["comparison"] == _comparison_record' in python_test
    assert "Frozen Python equation and explicit order mirrored byte-exactly by TS" in (
        generator
    )
    assert fixture_contract["role_cycle_claim"] == (
        "REGISTERED_NON_INVARIANT_PERTURBATION_NOT_TARGET_SCORED_DAMAGE"
    )


def test_v23_keeps_composition_learning_science_and_production_gates_open() -> None:
    payload = _load_handoff()
    assert payload["typescript_t16_core_implemented"] is True
    for key in (
        "typescript_t16_package_root_exported",
        "source_provenance_authenticated",
        "scalar_credit_operator_composition_implemented",
        "typescript_training_implemented",
        "llm_function_cell_implemented",
        "outcome_bound_causal_state_transition_implemented",
        "topology_learning_implemented",
        "role_cycle_target_scored_damage_proved",
        "workflow_process_continuity_resolved",
        "workflow_source_frozen",
        "github_origin_established",
        "preregistration_created",
        "confirmatory_dispatched",
        "event_10_composed",
        "scientific_verdict_produced",
    ):
        assert payload[key] is False
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert "NO_SCIENTIFIC_S2S_PASS" in payload["nonclaims"]
    assert "NO_COMPLETE_HSWM" in payload["nonclaims"]
    assert payload["next_session_order"][0] == (
        "READ_CONSTITUTION_OCCAM_S2S_V22_V23_AND_EFFECT_SKILL"
    )
    assert payload["next_session_order"][2] == (
        "AUDIT_INTERNAL_T16_AND_SCALAR_CREDIT_COMPOSITION_WITHOUT_CONFLATION"
    )
    assert payload["protected_user_changes"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]


def test_v23_artifact_bindings_handoff_indexes_and_verification_are_exact() -> None:
    payload = _load_handoff()
    assert hashlib.sha256(PREDECESSOR_PATH.read_bytes()).hexdigest() == (
        IMMUTABLE_V22_SHA256
    )
    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [entry["path"] for entry in bindings]
    assert len(paths) == len(set(paths))
    for required in (
        str(PREDECESSOR_PATH.relative_to(ROOT)),
        str(HANDOFF_DOC_PATH.relative_to(ROOT)),
        "src/hswm/effect-runtime/src/swm0-role-aware-core-schema.ts",
        "src/hswm/effect-runtime/src/swm0-role-aware-core.ts",
        "src/hswm/effect-runtime/test/swm0-role-aware-core.test.ts",
        "tests/fixtures/swm0_role_aware_core_python_v1.canonical.json",
        "tests/test_hswm_swm0_role_aware_core_fixture.py",
        "tests/test_hswm_swm0w_s2s_effect_handoff_v23.py",
        "ontology/evidence/README.md",
        "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        "src/hswm/effect-runtime/README.md",
    ):
        assert required in paths
    for entry in bindings:
        expected = entry["sha256"]
        assert SHA256_PATTERN.fullmatch(expected)
        actual = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        assert actual == expected

    assert payload["handoff_path"] == str(HANDOFF_DOC_PATH.relative_to(ROOT))
    handoff = HANDOFF_DOC_PATH.read_text(encoding="utf-8")
    for literal in (
        WORKSPACE_PARENT,
        IMPLEMENTATION_COMMIT,
        FIXTURE_SHA256,
        FIXTURE_RECEIPT,
        "30 Vitest files and 379 tests PASS",
        "84/84 PASS",
        "F1_R8_RESULTS_LOG.md",
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ):
        assert literal in handoff
    for index_path in (
        ROOT / "ontology/evidence/README.md",
        ROOT / "docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md",
        ROOT / "src/hswm/effect-runtime/README.md",
    ):
        index = index_path.read_text(encoding="utf-8")
        assert HANDOFF_PATH.name in index
        assert HANDOFF_DOC_PATH.name in index

    verification = payload["verification"]
    assert verification["effect_runtime_verify"] == "30_FILES_379_TESTS_PASS"
    assert verification["focused_typescript_core"] == "14_OF_14_PASS"
    assert verification["python_operator_training_protocol_fixture"] == (
        "84_OF_84_PASS"
    )
    assert verification["fixture_regeneration"] == "MATCH"
    assert verification["v23_contract_tests"] == "6_OF_6_PASS"
    assert verification["historical_handoff_chain_tests"] == "117_OF_117_PASS"
    assert verification["historical_handoff_tests_collected"] == 117
    assert verification["kg_contract_tests_close_scientific_gate"] is False
