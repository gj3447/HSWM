from __future__ import annotations

import json
import sqlite3

import pytest

from hswm.cells.adaptive_store import AdaptiveStore, AdaptiveStoreError, SCHEMA_VERSION


def atom(uid: str, kind: str, owner: str, refs: list[dict] | None = None, payload: object = None) -> dict:
    return {"uid": uid, "kind": kind, "owner": owner, "refs": refs or [], "payload": payload if payload is not None else {}}


def initialized(tmp_path):
    store = AdaptiveStore(tmp_path / "adaptive.sqlite")
    store.initialize("g", "manifest-1", [
        atom("cue", "observation", "sense"),
        atom("policy", "relation", "learn", [{"role": "condition", "uid": "cue"}], {"action": "wait"}),
    ])
    return store


def test_atomic_rewrite_preserves_prior_revision_and_role_typed_refs(tmp_path) -> None:
    store = initialized(tmp_path)
    outcome = store.rewrite("g", event_id="event-1", expected={"policy": 1, "trace": 0}, source={"episode": "e1"}, atoms=[
        atom("policy", "relation", "learn", [{"role": "condition", "uid": "cue"}, {"role": "evidence", "uid": "trace"}], {"action": "act"}),
        atom("trace", "trajectory", "act", [{"role": "policy", "uid": "policy"}], {"status": "RUNNING"}),
    ])
    assert {item["uid"]: item["revision"] for item in outcome["produced"]} == {"policy": 2, "trace": 1}
    assert store.get_revision("g", "policy", 1)["payload"] == {"action": "wait"}
    assert store.get_revision("g", "policy", 2)["refs"][1] == {"role": "evidence", "uid": "trace"}
    assert store.head("g", "policy")["revision"] == 2
    assert store.events("g")[0]["consumed"][0]["revision"] == 1


def test_compare_and_swap_is_atomic_and_owner_is_immutable(tmp_path) -> None:
    store = initialized(tmp_path)
    with pytest.raises(AdaptiveStoreError, match="compare-and-swap"):
        store.rewrite("g", event_id="stale", expected={"policy": 0}, source={}, atoms=[atom("policy", "relation", "learn")])
    assert store.head("g", "policy")["revision"] == 1
    with pytest.raises(AdaptiveStoreError, match="owner is immutable"):
        store.rewrite("g", event_id="owner", expected={"policy": 1}, source={}, atoms=[atom("policy", "relation", "other")])
    with pytest.raises(AdaptiveStoreError, match="kind is immutable"):
        store.rewrite("g", event_id="kind", expected={"policy": 1}, source={}, atoms=[atom("policy", "command", "learn")])
    assert store.head("g", "policy")["revision"] == 1
    with pytest.raises(AdaptiveStoreError, match="manifest digest conflict"):
        store.initialize("g", "different", [atom("x", "x", "x")])


def test_event_idempotency_and_reference_resolution(tmp_path) -> None:
    store = initialized(tmp_path)
    first = store.rewrite("g", event_id="event-1", expected={"policy": 1}, source={"origin": "test"}, atoms=[atom("policy", "relation", "learn", payload={"action": "act"})])
    retry = store.rewrite("g", event_id="event-1", expected={"policy": 1}, source={"origin": "test"}, atoms=[atom("policy", "relation", "learn", payload={"action": "act"})])
    assert retry["produced"] == first["produced"]
    with pytest.raises(AdaptiveStoreError, match="different intent"):
        store.rewrite("g", event_id="event-1", expected={"policy": 2}, source={"origin": "test"}, atoms=[atom("policy", "relation", "learn")])
    with pytest.raises(AdaptiveStoreError, match="reference is unresolved"):
        store.rewrite("g", event_id="missing", expected={"new": 0}, source={}, atoms=[atom("new", "relation", "learn", [{"role": "missing", "uid": "absent"}])])
    assert SCHEMA_VERSION == "hswm-adaptive-hypergraph/v1"


def test_revision_body_digest_detects_sqlite_payload_tampering(tmp_path) -> None:
    path = tmp_path / "adaptive.sqlite"
    store = AdaptiveStore(path)
    store.initialize("g", "manifest-1", [atom("cue", "observation", "sense", payload={"value": "old"})])
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE adaptive_atoms SET payload_json=? WHERE graph_id=? AND uid=? AND revision=?",
            (json.dumps({"value": "tampered"}, separators=(",", ":")).encode(), "g", "cue", 1),
        )
    with pytest.raises(AdaptiveStoreError, match="digest mismatch"):
        store.get_revision("g", "cue", 1)
    with pytest.raises(AdaptiveStoreError, match="revision is invalid"):
        store.get_revision("g", "cue", True)
