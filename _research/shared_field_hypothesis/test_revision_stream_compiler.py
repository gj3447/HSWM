from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import revision_stream_compiler as compiler  # noqa: E402


def _event(
    event_id: str,
    revision_id: str,
    fact_id: str,
    operation: str,
    value: str,
    valid_time: str,
    observed_at: str,
    *,
    supersedes: tuple[str, ...] = (),
    contradicts: tuple[str, ...] = (),
    compensates: tuple[str, ...] = (),
    evidence_id: str | None = None,
    evidence_payload: str | None = None,
    source_id: str = "source-fixture",
    source_payload: str = "frozen synthetic revision block",
) -> dict:
    evidence_id = evidence_id or f"evidence-{event_id}"
    return {
        "event_id": event_id,
        "revision_id": revision_id,
        "fact_id": fact_id,
        "operation": operation,
        "value": value,
        "valid_time": valid_time,
        "observed_at": observed_at,
        "evidence": [
            {
                "evidence_id": evidence_id,
                "payload": evidence_payload or f"observation for {event_id}",
            }
        ],
        "source": {"source_id": source_id, "payload": source_payload},
        "supersedes": list(supersedes),
        "contradicts": list(contradicts),
        "compensates": list(compensates),
    }


def _source() -> dict:
    events = [
        _event(
            "e01-weather-keep",
            "weather-v1",
            "weather",
            "KEEP",
            "rain",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
        ),
        _event(
            "e02-weather-supersede",
            "weather-v2",
            "weather",
            "SUPERSEDE",
            "sun",
            "2026-01-02T00:00:00Z",
            "2026-01-04T00:00:00Z",
            supersedes=("weather-v1",),
        ),
        _event(
            "e03-weather-contradict",
            "weather-v3",
            "weather",
            "CONTRADICT",
            "cloud",
            "2026-01-05T00:00:00Z",
            "2026-01-05T00:00:00Z",
            contradicts=("weather-v2",),
        ),
        _event(
            "e04-weather-resolve",
            "weather-v4",
            "weather",
            "SUPERSEDE",
            "sun with haze",
            "2026-01-06T00:00:00Z",
            "2026-01-06T00:00:00Z",
            supersedes=("weather-v2", "weather-v3"),
        ),
        _event(
            "e05-weather-compensate",
            "weather-v5",
            "weather",
            "COMPENSATE",
            "sun",
            "2026-01-07T00:00:00Z",
            "2026-01-07T00:00:00Z",
            compensates=("e04-weather-resolve",),
        ),
        _event(
            "e10-route-keep",
            "route-v1",
            "route",
            "KEEP",
            "north",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
        ),
        _event(
            "e11-route-supersede",
            "route-v2",
            "route",
            "SUPERSEDE",
            "east",
            "2026-01-02T00:00:00Z",
            "2026-01-02T00:00:00Z",
            supersedes=("route-v1",),
        ),
        _event(
            "e12-route-compensate",
            "route-v3",
            "route",
            "COMPENSATE",
            "north-east",
            "2026-01-03T00:00:00Z",
            "2026-01-03T00:00:00Z",
            compensates=("e11-route-supersede",),
        ),
        _event(
            "e20-branch-a",
            "alpha-v1",
            "alpha",
            "KEEP",
            "A",
            "2026-01-02T00:00:00Z",
            "2026-01-02T00:00:00Z",
        ),
        _event(
            "e21-branch-b",
            "beta-v1",
            "beta",
            "KEEP",
            "B",
            "2026-01-02T00:00:00Z",
            "2026-01-02T00:00:00Z",
        ),
    ]
    return {
        "schema": compiler.SOURCE_SCHEMA,
        "stream_id": "revision-fixture-001",
        "events": events,
        "query_times": [
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
            "2026-01-05T00:00:00Z",
            "2026-01-06T00:00:00Z",
            "2026-01-07T00:00:00Z",
        ],
        "branches": [
            {
                "branch_id": "branch-independent-facts",
                "event_ids": ["e20-branch-a", "e21-branch-b"],
                "expectation": "CONFLUENT",
                "nonconfluence_reason": None,
            },
            {
                "branch_id": "branch-ordered-compensation",
                "event_ids": ["e11-route-supersede", "e12-route-compensate"],
                "expectation": "NON_CONFLUENT",
                "nonconfluence_reason": (
                    "compensation is causally downstream of the superseded event; "
                    "reverse delivery must be refused"
                ),
            },
        ],
    }


def _compile(payload: dict | None = None) -> compiler.CompiledRevisionStream:
    return compiler.compile_revision_stream(
        compiler.canonical_json_bytes(payload if payload is not None else _source())
    )


def _replace_event(payload: dict, event_id: str, replacement: dict) -> None:
    index = next(
        index for index, event in enumerate(payload["events"]) if event["event_id"] == event_id
    )
    payload["events"][index] = replacement


def test_same_source_is_byte_and_digest_identical_with_bound_ids() -> None:
    source = compiler.canonical_json_bytes(_source())
    first = compiler.compile_revision_stream(source)
    second = compiler.compile_revision_stream(source)

    assert first.canonical_bytes == second.canonical_bytes
    assert first.compiled_sha256 == second.compiled_sha256
    assert first.stream_sha256 == second.stream_sha256
    assert first.oracle_sha256 == second.oracle_sha256

    event = first.document["events"][0]
    assert event["event_id"] == "e01-weather-keep"
    assert event["revision_id"] == "weather-v1"
    assert event["fact_id"] == "weather"
    assert len(event["event_sha256"]) == 64
    assert len(event["revision_sha256"]) == 64
    assert len(event["fact_sha256"]) == 64
    assert len(event["evidence"][0]["evidence_sha256"]) == 64
    assert len(event["source"]["source_sha256"]) == 64
    assert first.document["gold_oracle_basis"].endswith("never similarity")
    assert len(first.document["oracles"]) == len(_source()["query_times"])


def test_compiled_stream_tamper_is_refused_by_replay_verifier() -> None:
    source = compiler.canonical_json_bytes(_source())
    compiled = compiler.compile_revision_stream(source)
    tampered = compiled.document
    tampered["events"][0]["value"] = "tampered"

    with pytest.raises(compiler.RevisionCompileError, match="tamper/drift"):
        compiler.verify_compiled_revision_stream(
            source, compiler.canonical_json_bytes(tampered)
        )


def test_repeated_revision_sequence_and_stale_current_as_of_oracles() -> None:
    compiled = _compile()
    weather_events = [
        event for event in compiled.document["events"] if event["fact_id"] == "weather"
    ]
    assert [event["revision_sequence"] for event in weather_events] == [1, 2, 3, 4, 5]
    assert [event["operation"] for event in weather_events] == [
        "KEEP",
        "SUPERSEDE",
        "CONTRADICT",
        "SUPERSEDE",
        "COMPENSATE",
    ]

    query_time = "2026-01-02T00:00:00Z"
    current = compiled.current("weather", query_time)
    as_of = compiled.as_of("weather", query_time)
    assert [item["revision_id"] for item in current["current"]] == ["weather-v2"]
    assert current["stale_revision_ids"] == ["weather-v1"]
    assert [item["revision_id"] for item in as_of["current"]] == ["weather-v1"]
    assert as_of["stale_revision_ids"] == []
    assert current["cut_sha256"] != as_of["cut_sha256"]


def test_contradiction_is_explicit_then_preserved_after_resolution_and_compensation() -> None:
    compiled = _compile()
    conflict = compiled.current("weather", "2026-01-05T00:00:00Z")
    assert conflict["status"] == "CONTRADICTED"
    assert [item["revision_id"] for item in conflict["current"]] == [
        "weather-v2",
        "weather-v3",
    ]
    assert conflict["contradiction_history"] == [["weather-v2", "weather-v3"]]

    compensated = compiled.current("weather", "2026-01-07T00:00:00Z")
    assert compensated["status"] == "CURRENT"
    assert [item["revision_id"] for item in compensated["current"]] == ["weather-v5"]
    assert compensated["stale_revision_ids"] == [
        "weather-v1",
        "weather-v2",
        "weather-v3",
        "weather-v4",
    ]
    assert compensated["contradiction_history"] == [["weather-v2", "weather-v3"]]
    assert compensated["history_event_ids"] == [
        "e01-weather-keep",
        "e02-weather-supersede",
        "e03-weather-contradict",
        "e04-weather-resolve",
        "e05-weather-compensate",
    ]


def test_registered_branch_permutations_prove_or_explain_confluence() -> None:
    branches = {item["branch_id"]: item for item in _compile().document["branches"]}
    commutative = branches["branch-independent-facts"]
    assert commutative["observed_confluent"] is True
    assert len(commutative["permutations"]) == 2
    assert len({item["outcome_sha256"] for item in commutative["permutations"]}) == 1

    ordered = branches["branch-ordered-compensation"]
    assert ordered["observed_confluent"] is False
    assert ordered["nonconfluence_reason"].startswith("compensation is causally")
    assert len({item["outcome_sha256"] for item in ordered["permutations"]}) == 2


def test_duplicate_event_id_with_tampered_payload_fails_closed() -> None:
    payload = _source()
    duplicate = copy.deepcopy(payload["events"][1])
    duplicate["value"] = "tampered"
    payload["events"].insert(2, duplicate)
    with pytest.raises(compiler.DuplicateIDError, match="differing payloads"):
        _compile(payload)


def test_reused_evidence_or_source_id_with_tampered_payload_fails_closed() -> None:
    payload = _source()
    payload["events"][1]["evidence"][0] = {
        "evidence_id": payload["events"][0]["evidence"][0]["evidence_id"],
        "payload": "different evidence bytes",
    }
    with pytest.raises(compiler.DuplicateIDError, match="evidence_id"):
        _compile(payload)

    payload = _source()
    payload["events"][1]["source"]["payload"] = "tampered source bytes"
    with pytest.raises(compiler.DuplicateIDError, match="source_id"):
        _compile(payload)


@pytest.mark.parametrize("missing", ["evidence", "valid_time", "observed_at"])
def test_missing_evidence_or_time_is_refused(missing: str) -> None:
    payload = _source()
    del payload["events"][0][missing]
    with pytest.raises(compiler.RevisionCompileError):
        _compile(payload)


def test_empty_evidence_bad_operation_and_bad_time_are_refused() -> None:
    payload = _source()
    payload["events"][0]["evidence"] = []
    with pytest.raises(compiler.RevisionCompileError, match="non-empty"):
        _compile(payload)

    payload = _source()
    payload["events"][0]["operation"] = "DELETE"
    with pytest.raises(compiler.OperationError, match="operation"):
        _compile(payload)

    payload = _source()
    payload["events"][0]["observed_at"] = "2025-12-31T00:00:00Z"
    with pytest.raises(compiler.TemporalError, match="precedes"):
        _compile(payload)


def test_cycle_invalid_supersede_and_ambiguous_cut_are_refused() -> None:
    common_time = "2026-01-01T00:00:00Z"
    cycle = {
        "schema": compiler.SOURCE_SCHEMA,
        "stream_id": "cycle",
        "events": [
            _event(
                "e1",
                "r1",
                "fact",
                "SUPERSEDE",
                "one",
                common_time,
                common_time,
                supersedes=("r2",),
            ),
            _event(
                "e2",
                "r2",
                "fact",
                "SUPERSEDE",
                "two",
                common_time,
                common_time,
                supersedes=("r1",),
            ),
        ],
        "query_times": [common_time],
        "branches": [],
    }
    with pytest.raises(compiler.RevisionGraphError, match="cycle"):
        _compile(cycle)

    payload = _source()
    replacement = _event(
        "e03-weather-contradict",
        "weather-v3",
        "weather",
        "SUPERSEDE",
        "cloud",
        "2026-01-05T00:00:00Z",
        "2026-01-05T00:00:00Z",
        supersedes=("weather-v1",),
    )
    _replace_event(payload, "e03-weather-contradict", replacement)
    with pytest.raises(compiler.RevisionGraphError, match="non-current"):
        _compile(payload)

    ambiguous = {
        "schema": compiler.SOURCE_SCHEMA,
        "stream_id": "ambiguous",
        "events": [
            _event("e1", "r1", "fact", "KEEP", "one", common_time, common_time),
            _event("e2", "r2", "fact", "KEEP", "two", common_time, common_time),
        ],
        "query_times": [common_time],
        "branches": [],
    }
    with pytest.raises(compiler.AmbiguousCutError, match="ambiguous current cut"):
        _compile(ambiguous)


def test_noncanonical_json_and_misdeclared_branches_are_refused() -> None:
    pretty = json.dumps(_source(), ensure_ascii=False, indent=2).encode("utf-8")
    with pytest.raises(compiler.CanonicalJSONError, match="not canonical"):
        compiler.compile_revision_stream(pretty)

    payload = _source()
    payload["branches"][0]["expectation"] = "NON_CONFLUENT"
    payload["branches"][0]["nonconfluence_reason"] = "invented"
    with pytest.raises(compiler.ConfluenceError, match="all permutations agree"):
        _compile(payload)

    payload = _source()
    payload["branches"][1]["expectation"] = "CONFLUENT"
    payload["branches"][1]["nonconfluence_reason"] = None
    with pytest.raises(compiler.ConfluenceError, match="declared commutative"):
        _compile(payload)

    payload = _source()
    payload["branches"][1]["nonconfluence_reason"] = None
    with pytest.raises(compiler.ConfluenceError, match="explicit reason"):
        _compile(payload)
