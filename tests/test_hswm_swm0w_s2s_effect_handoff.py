from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = (
    ROOT / "ontology/evidence/HSWM_SWM0W_S2S_EFFECT_HANDOFF.v1.json"
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


def test_effect_handoff_is_a_closed_non_evidentiary_kg_projection() -> None:
    payload = _load_handoff()

    assert payload["schema_version"] == "hswm-engineering-handoff-kg/v1"
    assert payload["status"] == "BLOCKED_PRE_PREREG"
    assert payload["control_core_status"] == "EXACT_BYTE_AUDIT_CLEAR"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["remote_kg_publication_status"] == "NOT_ATTEMPTED"
    assert payload["future_beacon_selected"] is False
    assert payload["confirmatory_dispatched"] is False

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

    blockers = [node for node in nodes if node.get("kind") == "BLOCKER"]
    resolved = [node for node in blockers if node.get("status") == "RESOLVED"]
    open_blockers = [node for node in blockers if node.get("status") == "OPEN"]
    assert {node["uid"] for node in resolved} == {
        "sym:Blocker:hswm-s2s-source-a-commit-type",
        "sym:Blocker:hswm-s2s-prereg-path-absent-at-a",
        "sym:Blocker:hswm-s2s-prereg-immutable-byte-snapshot",
        "sym:Blocker:hswm-s2s-pulse-cross-event-chronology",
        "sym:Blocker:hswm-s2s-confirm-command-slack",
        "sym:Blocker:hswm-s2s-positive-artifact-bytes",
    }
    assert {node["uid"] for node in open_blockers} == {
        "sym:Blocker:hswm-s2s-live-effect-adapters",
        "sym:Blocker:hswm-s2s-three-job-chronology",
    }
    assert all(blocker.get("severity") == "P0" for blocker in blockers)
    assert all(type(blocker.get("blocking_gate")) is str for blocker in blockers)
    assert all(type(blocker.get("failure_mode")) is str for blocker in blockers)
    assert all(type(blocker.get("target_paths")) is list for blocker in blockers)
    assert all(type(blocker.get("acceptance_tests")) is list for blocker in blockers)
    assert all(node.get("scientific_status") != "PASS" for node in nodes)
    assert not any(relation["type"] == "EVIDENCE_FOR" for relation in relations)

    checkpoint_uid = payload["bundle_uid"]
    for blocker in resolved:
        assert {
            "from_uid": checkpoint_uid,
            "type": "CONTAINS",
            "to_uid": blocker["uid"],
        } in relations
    for blocker in open_blockers:
        assert {
            "from_uid": blocker["uid"],
            "type": "BLOCKS",
            "to_uid": checkpoint_uid,
        } in relations

    authority_classes = {
        "USER_PRIMARY",
        "SECONDARY_AI_PROPOSED",
        "SYSTEM_DERIVED",
    }
    assert all(node["authority_class"] in authority_classes for node in nodes)


def test_effect_handoff_paths_and_source_hashes_are_exact() -> None:
    payload = _load_handoff()
    nodes = payload["nodes"]
    assert type(nodes) is list

    referenced = [payload["handoff_path"]]
    for node in nodes:
        assert type(node) is dict
        referenced.extend(
            node[key] for key in ("source_path", "plan_path") if key in node
        )

    for relative in referenced:
        assert type(relative) is str
        path = ROOT / relative
        assert path.is_file()
        assert not path.is_symlink()

    for node in nodes:
        assert type(node) is dict
        if "source_sha256" not in node:
            continue
        source_path = node["source_path"]
        source_sha256 = node["source_sha256"]
        assert type(source_path) is str
        assert type(source_sha256) is str
        assert hashlib.sha256((ROOT / source_path).read_bytes()).hexdigest() == (
            source_sha256
        )

    bindings = payload["artifact_bindings"]
    assert type(bindings) is list
    paths = [binding["path"] for binding in bindings]
    roles = [binding["role"] for binding in bindings]
    assert len(paths) == len(set(paths))
    assert len(roles) == len(set(roles))
    is_python_sdist = (ROOT / "PKG-INFO").is_file()
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
        if not path.exists():
            assert is_python_sdist
            assert relative.startswith("src/hswm/effect-runtime/")
            continue
        assert path.is_file()
        assert not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    blockers = [node for node in nodes if node.get("kind") == "BLOCKER"]
    for blocker in blockers:
        target_paths = blocker["target_paths"]
        assert type(target_paths) is list
        for relative in target_paths:
            assert type(relative) is str
            assert relative == Path(relative).as_posix()
            assert not relative.startswith("/")
            assert ".." not in Path(relative).parts
