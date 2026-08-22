from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = (
    ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v3.json"
)


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_handoff() -> dict[str, object]:
    payload = json.loads(
        HANDOFF_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
    )
    assert type(payload) is dict
    return payload


def test_effect_authority_handoff_is_a_closed_non_evidentiary_kg() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v3"
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["structural_status"] == "STRUCTURAL_1_6_9_CLEAR"
    assert payload["github_provenance_status"] == (
        "REQUEST_DISTINCT_ENGINEERING_CLEAR"
    )
    assert payload["registration_authority_status"] == (
        "SOURCE_PREREGISTRATION_THROUGH_B_CLEAR"
    )
    assert payload["current_run_authority_status"] == "OPEN"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["future_beacon_selected"] is False
    assert payload["preregistration_created"] is False
    assert payload["confirmatory_dispatched"] is False
    assert payload["candidate_produced"] is False
    assert payload["event_10_composed"] is False

    projection = payload["architecture_projection"]
    assert type(projection) is dict
    assert projection["H"] == "TARGET_IDENTITY_UNCHANGED_NO_NEW_COGNITION_EVIDENCE"
    assert projection["W"] == "NO_LEARNED_WEIGHT_RESULT"
    assert projection["A"] == "NO_ACTIVATION_READOUT_EFFICACY_RESULT"
    assert projection["outcome_bound_causal_learning_loop"] == "NOT_ADVANCED"
    assert "CURRENT_RUN_AUTHORITY_OPEN" in projection["Pi"]

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

    authority_classes = {
        "USER_PRIMARY",
        "SECONDARY_AI_PROPOSED",
        "SYSTEM_DERIVED",
    }
    assert all(node["authority_class"] in authority_classes for node in nodes)

    checkpoint_uid = payload["bundle_uid"]
    superseded_uid = payload["supersedes_bundle_uid_for_continuation"]
    assert {
        "from_uid": checkpoint_uid,
        "type": "SUPERSEDES_FOR_CONTINUATION",
        "to_uid": superseded_uid,
    } in relations
    assert next(node for node in nodes if node["uid"] == superseded_uid)[
        "status"
    ] == "SUPERSEDED_FOR_CONTINUATION_ONLY"


def test_effect_authority_handoff_gates_and_contract_pins_are_exact() -> None:
    payload = _load_handoff()

    resolved_gates = payload["resolved_gates"]
    open_gates = payload["open_gates"]
    assert type(resolved_gates) is list
    assert type(open_gates) is list
    assert {gate["uid"] for gate in resolved_gates} == {
        "sym:Gate:hswm-s2s-request-distinct-github-receipts",
        "sym:Gate:hswm-s2s-registration-b-runtime-authority",
    }
    assert all(gate["status"] == "ENGINEERING_CLEAR" for gate in resolved_gates)
    assert {gate["uid"] for gate in open_gates} == {
        "sym:Blocker:hswm-s2s-current-invocation-evidence",
        "sym:Blocker:hswm-s2s-current-run-stage-authority",
        "sym:Blocker:hswm-s2s-exact-workflow-contract",
        "sym:Blocker:hswm-s2s-durable-external-evidence-envelope",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    assert all(gate["severity"] == "P0" for gate in open_gates)

    frozen = payload["frozen_contracts"]
    assert type(frozen) is dict
    assert frozen == {
        "effect_version": "3.22.1",
        "typescript_version": "5.9.3",
        "node_version": "24.13.0",
        "confirmatory_policy_schema_version": (
            "hswm-swm0w-s2s-confirmatory-operational-policy/v4"
        ),
        "confirmatory_event_schema_version": (
            "hswm-swm0w-s2s-confirmatory-control-event/v4"
        ),
        "github_observation_schema_version": (
            "hswm-swm0w-s2s-github-observation-receipt/v2"
        ),
        "github_download_schema_version": (
            "hswm-swm0w-s2s-github-artifact-download-receipt/v2"
        ),
        "registration_commit_authority_evidence_schema_version": (
            "hswm-swm0w-s2s-registration-commit-authority-evidence/v1"
        ),
        "resource_policy_sha256": (
            "b2c631ff80922800d06ac7e31c0632e02e1b560a31759cd0d11ae0a39c374351"
        ),
    }


def test_effect_authority_handoff_paths_and_hashes_are_exact() -> None:
    payload = _load_handoff()
    bindings = payload["artifact_bindings"]
    nodes = payload["nodes"]
    assert type(bindings) is list
    assert type(nodes) is list

    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    assert payload["handoff_path"] in paths

    for binding in bindings:
        assert set(binding) == {"path", "role", "sha256"}
        relative = binding["path"]
        expected = binding["sha256"]
        assert type(relative) is str
        assert type(expected) is str
        assert relative == Path(relative).as_posix()
        assert not relative.startswith("/")
        assert ".." not in Path(relative).parts
        path = ROOT / relative
        assert path.is_file()
        assert not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    for node in nodes:
        for key in ("source_path", "plan_path"):
            if key not in node:
                continue
            relative = node[key]
            assert type(relative) is str
            assert relative == Path(relative).as_posix()
            assert not relative.startswith("/")
            assert ".." not in Path(relative).parts
            path = ROOT / relative
            assert path.is_file()
            assert not path.is_symlink()

    assert payload["protected_unrelated_paths"] == [
        "src/hswm/experiments/continual_live.py",
        "tests/test_hswm_continual_live.py",
    ]
    nonclaims = payload["nonclaims"]
    assert type(nonclaims) is list
    assert all(type(nonclaim) is str for nonclaim in nonclaims)
    assert any("not a preregistration" in nonclaim for nonclaim in nonclaims)
    assert any(
        "do not establish learned set-to-set efficacy" in nonclaim
        for nonclaim in nonclaims
    )
