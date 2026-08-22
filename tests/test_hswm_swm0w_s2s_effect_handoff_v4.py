from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = (
    ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json"
)
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


def test_invocation_authority_handoff_is_a_closed_non_evidentiary_kg() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v4"
    assert payload["bundle_uid"] == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-invocation-authority-handoff-2026-08-22"
    )
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["structural_status"] == "STRUCTURAL_1_6_9_CLEAR"
    assert payload["workflow_contract_status"] == (
        "IDENTITY_AND_STAGE_CONTRACT_V1_ENGINEERING_CLEAR_SOURCE_BYTES_OPEN"
    )
    assert payload["current_invocation_authority_status"] == (
        "ENGINEERING_CLEAR_PROCESS_LOCAL"
    )
    assert payload["current_run_authority_status"] == "OPEN"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["workspace_code_commit"] == (
        "5fe203815bdba2b3cdbf6d5d67f739b23c63b084"
    )
    assert payload["workspace_parent_commit"] == (
        "7f2754b5a60651893aed6501636ee732ffc5634c"
    )
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
    assert "CURRENT_RUN_STAGE_AUTHORITY_OPEN" in projection["Pi"]

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
    predecessor_uid = payload["supersedes_bundle_uid_for_continuation"]
    assert predecessor_uid == (
        "sym:EngineeringCheckpoint:"
        "hswm-swm0w-s2s-effect-authority-handoff-2026-08-22"
    )
    assert {
        "from_uid": checkpoint_uid,
        "type": "SUPERSEDES_FOR_CONTINUATION",
        "to_uid": predecessor_uid,
    } in relations
    assert next(node for node in nodes if node["uid"] == predecessor_uid)[
        "status"
    ] == "SUPERSEDED_FOR_CONTINUATION_ONLY"


def test_invocation_authority_gates_contracts_and_vectors_are_exact() -> None:
    payload = _load_handoff()

    resolved = payload["resolved_gates"]
    prepared = payload["prepared_boundaries"]
    open_gates = payload["open_gates"]
    assert type(resolved) is list
    assert type(prepared) is list
    assert type(open_gates) is list
    assert {gate["uid"] for gate in resolved} == {
        "sym:Gate:hswm-s2s-request-distinct-github-receipts",
        "sym:Gate:hswm-s2s-registration-b-runtime-authority",
        "sym:Gate:hswm-s2s-workflow-identity-contract-v1",
        "sym:Gate:hswm-s2s-current-invocation-runtime-authority",
    }
    assert all(gate["status"] == "ENGINEERING_CLEAR" for gate in resolved)
    assert {boundary["uid"] for boundary in prepared} == {
        "sym:Boundary:hswm-s2s-registration-workflow-row-inspector"
    }
    assert prepared[0]["status"] == (
        "IMPLEMENTED_FAIL_CLOSED_ACTUAL_BINDING_OPEN"
    )
    assert {gate["uid"] for gate in open_gates} == {
        "sym:Blocker:hswm-s2s-workflow-source-bytes-manifest-binding",
        "sym:Blocker:hswm-s2s-trusted-current-run-observation",
        "sym:Blocker:hswm-s2s-current-run-stage-authority",
        "sym:Blocker:hswm-s2s-stage-specific-artifact-permits",
        "sym:Blocker:hswm-s2s-durable-external-evidence-envelope",
        "sym:Blocker:hswm-s2s-composition-workflow-finalizer",
    }
    assert all(gate["severity"] == "P0" for gate in open_gates)

    frozen = payload["frozen_contracts"]
    assert type(frozen) is dict
    assert frozen["effect_version"] == "3.22.1"
    assert frozen["typescript_version"] == "5.9.3"
    assert frozen["node_version"] == "24.13.0"
    assert frozen["workflow_contract_schema_version"] == (
        "hswm-swm0w-s2s-workflow-contract/v1"
    )
    assert frozen["workflow_contract_sha256"] == (
        "45e14e0e3d2a0ca0b652c2d39741b264968d4ecdb2d0ff5b74eabd0aa8904050"
    )
    assert frozen["workflow_file_sha256_status"] == (
        "OPEN_UNTIL_REVIEWED_WORKFLOW_BYTES_EXIST"
    )
    assert frozen["current_invocation_evidence_schema_version"] == (
        "hswm-swm0w-s2s-current-invocation-evidence/v1"
    )

    vectors = payload["known_test_vectors"]
    assert type(vectors) is dict
    assert vectors["current_invocation"] == {
        "environment_projection_sha256": (
            "f196682960f5cfead7bcbe3cb13f20e130a387b2ddae390ef63059784280205e"
        ),
        "raw_event_body_sha256": (
            "7f38bb7246cb0358345d10ad76e052ad24bcec0a79c5dd0a5a86e95395dcbbcb"
        ),
        "event_projection_sha256": (
            "4bab7836a7a8b31465b233973636538851a58bd0703752df9191f5ed144140c2"
        ),
        "receipt_sha256": (
            "08ea8dc16d5843947fab1488f4273f60d5bb38747460af5c0c38ea978426e5d6"
        ),
        "scope": "TEST_FIXTURE_ONLY_NOT_LIVE_EVIDENCE",
    }


def test_invocation_paths_hashes_and_nonclaims_are_exact_or_successor_bound() -> None:
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
    assert "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v4.json" not in paths

    latest_bindings = _latest_binding_hashes(payload)
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
        current_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if current_sha256 != expected:
            assert latest_bindings[relative] == current_sha256

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
    assert any("not a workflow-file hash" in nonclaim for nonclaim in nonclaims)
    assert any(
        "do not establish learned set-to-set efficacy" in nonclaim
        for nonclaim in nonclaims
    )
