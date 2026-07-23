"""Deterministic compiler and gold oracle for evolving-revision task blocks.

This is fixture infrastructure, not an HSWM revision arm.  It compiles a strict,
canonical JSON source block into an operation stream whose labels and temporal
answers are independent of retrieval scores.  The compiler is deliberately
small and pure: there is no clock, model call, similarity threshold, filesystem
write, or mutable global registry in the trusted path.

Source schema (``hswm-revision-source/v1``)
------------------------------------------------
The top-level object has exactly ``schema``, ``stream_id``, ``events``,
``query_times``, and ``branches``.  Every event has exactly these fields::

    event_id revision_id fact_id operation value valid_time observed_at
    evidence source supersedes contradicts compensates

``evidence`` is a non-empty list of ``{"evidence_id", "payload"}`` objects and
``source`` is one ``{"source_id", "payload"}`` object.  Relation lists contain
revision IDs for SUPERSEDE/CONTRADICT and event IDs for COMPENSATE.  All times
are canonical UTC RFC3339 strings.  JSON objects and arrays must already be in
the repository's canonical form; accepting a merely equivalent encoding would
make the frozen-source hash ambiguous.

Operation semantics
-------------------
KEEP introduces a revision.  SUPERSEDE retires active revisions and introduces
their replacement.  CONTRADICT introduces an explicitly competing revision and
preserves the conflict in history.  COMPENSATE retires the active revision
created by a prior event and introduces a compensating revision, while retaining
the original event and link.  Multiple live heads are accepted only when every
pair is explicitly connected by CONTRADICT; an unlabelled multi-head cut fails
closed as ambiguous.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


SOURCE_SCHEMA = "hswm-revision-source/v1"
COMPILED_SCHEMA = "hswm-revision-stream/v1"
OPERATIONS = frozenset({"KEEP", "SUPERSEDE", "CONTRADICT", "COMPENSATE"})
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOP_KEYS = frozenset({"schema", "stream_id", "events", "query_times", "branches"})
_EVENT_KEYS = frozenset(
    {
        "event_id",
        "revision_id",
        "fact_id",
        "operation",
        "value",
        "valid_time",
        "observed_at",
        "evidence",
        "source",
        "supersedes",
        "contradicts",
        "compensates",
    }
)
_EVIDENCE_KEYS = frozenset({"evidence_id", "payload"})
_SOURCE_KEYS = frozenset({"source_id", "payload"})
_BRANCH_KEYS = frozenset(
    {"branch_id", "event_ids", "expectation", "nonconfluence_reason"}
)


class RevisionCompileError(ValueError):
    """Base class for a source block that cannot define a gold oracle."""


class CanonicalJSONError(RevisionCompileError):
    """Input bytes are not the one accepted canonical JSON representation."""


class DuplicateIDError(RevisionCompileError):
    """One stable ID was reused for different content."""


class TemporalError(RevisionCompileError):
    """A timestamp is missing, malformed, or causally inconsistent."""


class OperationError(RevisionCompileError):
    """An operation label or its relation fields are invalid."""


class RevisionGraphError(RevisionCompileError):
    """The supersession/compensation graph is cyclic or refers to bad targets."""


class AmbiguousCutError(RevisionCompileError):
    """A cut contains unregistered competing current revisions."""


class ConfluenceError(RevisionCompileError):
    """A registered branch disagrees with its confluence declaration."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the repository-local canonical JSON representation."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CanonicalJSONError(f"value is not canonical JSON data: {exc}") from exc


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _duplicate_rejector(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalJSONError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise CanonicalJSONError(f"non-finite JSON number: {value}")


def load_canonical_source(source: bytes) -> dict[str, Any]:
    """Parse bytes only when they are already strict canonical JSON."""
    if not isinstance(source, bytes):
        raise CanonicalJSONError("source must be bytes, not a decoded/mutable object")
    if source.startswith(b"\xef\xbb\xbf"):
        raise CanonicalJSONError("UTF-8 BOM is not canonical")
    try:
        text = source.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except CanonicalJSONError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CanonicalJSONError(f"invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CanonicalJSONError("source must contain one JSON object")
    if canonical_json_bytes(value) != source:
        raise CanonicalJSONError(
            "source is valid JSON but not canonical (sorted keys, compact separators, "
            "UTF-8 literals, and no trailing newline required)"
        )
    return value


def _exact_keys(value: Any, keys: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RevisionCompileError(f"{label} must be an object")
    actual = frozenset(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise RevisionCompileError(f"{label} fields differ: missing={missing}, extra={extra}")
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise RevisionCompileError(f"{label} must match {_ID_RE.pattern}")
    return value


def _canonical_time(value: Any, label: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise TemporalError(f"{label} must be a canonical UTC RFC3339 string ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise TemporalError(f"{label} is not RFC3339: {value!r}") from exc
    if parsed.tzinfo != timezone.utc:
        raise TemporalError(f"{label} must use UTC")
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise TemporalError(f"{label} is not canonical: expected {canonical!r}")
    return value, parsed


def _sorted_unique_ids(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RevisionCompileError(f"{label} must be an array")
    ids = tuple(_identifier(item, f"{label}[]") for item in value)
    if tuple(sorted(ids)) != ids or len(set(ids)) != len(ids):
        raise CanonicalJSONError(f"{label} must be strictly ID-sorted and duplicate-free")
    return ids


@dataclass(frozen=True)
class _Event:
    raw: Mapping[str, Any]
    event_id: str
    revision_id: str
    fact_id: str
    operation: str
    value: Any
    valid_time: str
    observed_at: str
    valid_dt: datetime
    observed_dt: datetime
    evidence: tuple[Mapping[str, Any], ...]
    source: Mapping[str, Any]
    supersedes: tuple[str, ...]
    contradicts: tuple[str, ...]
    compensates: tuple[str, ...]
    dependencies: tuple[str, ...] = ()


@dataclass
class _FoldState:
    active: dict[str, set[str]] = field(default_factory=dict)
    included_revisions: dict[str, set[str]] = field(default_factory=dict)
    history_events: dict[str, list[str]] = field(default_factory=dict)
    contradictions: set[tuple[str, str]] = field(default_factory=set)
    compensated_events: set[str] = field(default_factory=set)

    def clone(self) -> "_FoldState":
        return _FoldState(
            active={key: set(value) for key, value in self.active.items()},
            included_revisions={key: set(value) for key, value in self.included_revisions.items()},
            history_events={key: list(value) for key, value in self.history_events.items()},
            contradictions=set(self.contradictions),
            compensated_events=set(self.compensated_events),
        )


@dataclass(frozen=True)
class CompiledRevisionStream:
    """Immutable bytes plus independent stream/oracle content digests."""

    canonical_bytes: bytes
    source_sha256: str
    stream_sha256: str
    oracle_sha256: str

    @property
    def compiled_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    @property
    def document(self) -> dict[str, Any]:
        # A fresh object prevents callers from mutating the digest-bound bytes.
        return json.loads(self.canonical_bytes.decode("utf-8"))

    def current(self, fact_id: str, query_time: str) -> Mapping[str, Any]:
        return self._lookup("current", fact_id, query_time)

    def as_of(self, fact_id: str, query_time: str) -> Mapping[str, Any]:
        return self._lookup("as_of", fact_id, query_time)

    def _lookup(self, cut: str, fact_id: str, query_time: str) -> Mapping[str, Any]:
        for oracle in self.document["oracles"]:
            if oracle["query_time"] == query_time:
                for answer in oracle[cut]:
                    if answer["fact_id"] == fact_id:
                        return answer
                raise KeyError(fact_id)
        raise KeyError(query_time)


def _parse_event(raw: Any, index: int) -> _Event:
    item = _exact_keys(raw, _EVENT_KEYS, f"events[{index}]")
    event_id = _identifier(item["event_id"], f"events[{index}].event_id")
    revision_id = _identifier(item["revision_id"], f"events[{index}].revision_id")
    fact_id = _identifier(item["fact_id"], f"events[{index}].fact_id")
    operation = item["operation"]
    if operation not in OPERATIONS:
        raise OperationError(f"event {event_id}: operation must be one of {sorted(OPERATIONS)}")
    valid_time, valid_dt = _canonical_time(item["valid_time"], f"event {event_id}.valid_time")
    observed_at, observed_dt = _canonical_time(
        item["observed_at"], f"event {event_id}.observed_at"
    )
    if observed_dt < valid_dt:
        raise TemporalError(f"event {event_id}: observed_at precedes valid_time")

    evidence_raw = item["evidence"]
    if not isinstance(evidence_raw, list) or not evidence_raw:
        raise RevisionCompileError(f"event {event_id}: evidence must be a non-empty array")
    evidence: list[Mapping[str, Any]] = []
    evidence_ids: list[str] = []
    for evidence_index, evidence_item in enumerate(evidence_raw):
        ev = _exact_keys(
            evidence_item, _EVIDENCE_KEYS, f"event {event_id}.evidence[{evidence_index}]"
        )
        evidence_ids.append(
            _identifier(ev["evidence_id"], f"event {event_id}.evidence[].evidence_id")
        )
        # Force JSON encodability and finite numbers now, not during output.
        canonical_json_bytes(ev["payload"])
        evidence.append(ev)
    if evidence_ids != sorted(evidence_ids) or len(set(evidence_ids)) != len(evidence_ids):
        raise CanonicalJSONError(
            f"event {event_id}: evidence must be strictly evidence_id-sorted and unique"
        )

    source = _exact_keys(item["source"], _SOURCE_KEYS, f"event {event_id}.source")
    _identifier(source["source_id"], f"event {event_id}.source.source_id")
    canonical_json_bytes(source["payload"])

    supersedes = _sorted_unique_ids(item["supersedes"], f"event {event_id}.supersedes")
    contradicts = _sorted_unique_ids(item["contradicts"], f"event {event_id}.contradicts")
    compensates = _sorted_unique_ids(item["compensates"], f"event {event_id}.compensates")
    nonempty = {
        "SUPERSEDE": supersedes,
        "CONTRADICT": contradicts,
        "COMPENSATE": compensates,
    }
    if operation == "KEEP" and any((supersedes, contradicts, compensates)):
        raise OperationError(f"event {event_id}: KEEP cannot carry relation targets")
    if operation != "KEEP":
        expected = nonempty[operation]
        others = [value for key, value in nonempty.items() if key != operation]
        if not expected or any(others):
            raise OperationError(
                f"event {event_id}: {operation} must use only its matching non-empty relation"
            )
    if operation == "COMPENSATE" and len(compensates) != 1:
        raise OperationError(f"event {event_id}: COMPENSATE requires exactly one event target")

    canonical_json_bytes(item["value"])
    return _Event(
        raw=item,
        event_id=event_id,
        revision_id=revision_id,
        fact_id=fact_id,
        operation=operation,
        value=item["value"],
        valid_time=valid_time,
        observed_at=observed_at,
        valid_dt=valid_dt,
        observed_dt=observed_dt,
        evidence=tuple(evidence),
        source=source,
        supersedes=supersedes,
        contradicts=contradicts,
        compensates=compensates,
    )


def _parse_source(source: bytes) -> tuple[dict[str, Any], list[_Event], list[datetime]]:
    document = load_canonical_source(source)
    _exact_keys(document, _TOP_KEYS, "source")
    if document["schema"] != SOURCE_SCHEMA:
        raise RevisionCompileError(f"schema must be {SOURCE_SCHEMA}")
    _identifier(document["stream_id"], "stream_id")

    raw_events = document["events"]
    if not isinstance(raw_events, list) or not raw_events:
        raise RevisionCompileError("events must be a non-empty array")
    events = [_parse_event(raw, index) for index, raw in enumerate(raw_events)]
    event_ids = [event.event_id for event in events]
    if event_ids != sorted(event_ids):
        raise CanonicalJSONError("events must be sorted by event_id")

    # Exact duplicate retries collapse; same ID/different intent is a conflict.
    deduped: dict[str, _Event] = {}
    for event in events:
        prior = deduped.get(event.event_id)
        if prior is not None:
            if canonical_json_bytes(prior.raw) != canonical_json_bytes(event.raw):
                raise DuplicateIDError(f"event_id {event.event_id!r} has differing payloads")
            continue
        deduped[event.event_id] = event
    events = list(deduped.values())

    query_times = document["query_times"]
    if not isinstance(query_times, list) or not query_times:
        raise RevisionCompileError("query_times must be a non-empty array")
    parsed_times = [
        _canonical_time(value, f"query_times[{index}]")[1]
        for index, value in enumerate(query_times)
    ]
    if parsed_times != sorted(parsed_times) or len(set(parsed_times)) != len(parsed_times):
        raise CanonicalJSONError("query_times must be strictly chronological and unique")

    branches = document["branches"]
    if not isinstance(branches, list):
        raise RevisionCompileError("branches must be an array")
    branch_ids: list[str] = []
    seen_branch_events: set[str] = set()
    known_event_ids = set(deduped)
    for index, raw_branch in enumerate(branches):
        branch = _exact_keys(raw_branch, _BRANCH_KEYS, f"branches[{index}]")
        branch_id = _identifier(branch["branch_id"], f"branches[{index}].branch_id")
        branch_ids.append(branch_id)
        branch_events = _sorted_unique_ids(branch["event_ids"], f"branch {branch_id}.event_ids")
        if len(branch_events) < 2 or len(branch_events) > 6:
            raise RevisionCompileError(f"branch {branch_id}: event_ids size must be in [2, 6]")
        unknown = set(branch_events) - known_event_ids
        if unknown:
            raise RevisionGraphError(f"branch {branch_id}: unknown events {sorted(unknown)}")
        overlap = seen_branch_events.intersection(branch_events)
        if overlap:
            raise RevisionGraphError(
                f"branch events may be registered once; {sorted(overlap)} are duplicated"
            )
        seen_branch_events.update(branch_events)
        expectation = branch["expectation"]
        reason = branch["nonconfluence_reason"]
        if expectation == "CONFLUENT":
            if reason is not None:
                raise ConfluenceError(f"branch {branch_id}: confluent branch reason must be null")
        elif expectation == "NON_CONFLUENT":
            if not isinstance(reason, str) or not reason.strip():
                raise ConfluenceError(
                    f"branch {branch_id}: non-confluence requires an explicit reason"
                )
        else:
            raise ConfluenceError(
                f"branch {branch_id}: expectation must be CONFLUENT or NON_CONFLUENT"
            )
    if branch_ids != sorted(branch_ids) or len(set(branch_ids)) != len(branch_ids):
        raise CanonicalJSONError("branches must be strictly branch_id-sorted and unique")
    return document, events, parsed_times


def _bind_registry(
    registry: dict[str, bytes], identifier: str, payload: Any, label: str
) -> None:
    encoded = canonical_json_bytes(payload)
    prior = registry.get(identifier)
    if prior is not None and prior != encoded:
        raise DuplicateIDError(f"{label} {identifier!r} has differing payloads")
    registry[identifier] = encoded


def _link_events(events: list[_Event]) -> tuple[list[_Event], dict[str, _Event]]:
    by_event = {event.event_id: event for event in events}
    by_revision: dict[str, _Event] = {}
    evidence_registry: dict[str, bytes] = {}
    source_registry: dict[str, bytes] = {}
    for event in events:
        prior = by_revision.get(event.revision_id)
        if prior is not None:
            raise DuplicateIDError(
                f"revision_id {event.revision_id!r} is emitted by both "
                f"{prior.event_id!r} and {event.event_id!r}"
            )
        by_revision[event.revision_id] = event
        for evidence in event.evidence:
            _bind_registry(
                evidence_registry,
                evidence["evidence_id"],
                evidence["payload"],
                "evidence_id",
            )
        _bind_registry(
            source_registry, event.source["source_id"], event.source["payload"], "source_id"
        )

    linked: list[_Event] = []
    for event in events:
        dependencies: set[str] = set()
        for target_revision in event.supersedes + event.contradicts:
            target = by_revision.get(target_revision)
            if target is None:
                raise RevisionGraphError(
                    f"event {event.event_id}: unknown target revision {target_revision!r}"
                )
            if target.fact_id != event.fact_id:
                raise RevisionGraphError(
                    f"event {event.event_id}: target {target_revision!r} belongs to another fact"
                )
            if target.event_id == event.event_id:
                raise RevisionGraphError(f"event {event.event_id}: self-target is invalid")
            if target.valid_dt > event.valid_dt or target.observed_dt > event.observed_dt:
                raise TemporalError(
                    f"event {event.event_id}: target {target.event_id} is temporally later"
                )
            dependencies.add(target.event_id)
        for target_event_id in event.compensates:
            target = by_event.get(target_event_id)
            if target is None:
                raise RevisionGraphError(
                    f"event {event.event_id}: unknown compensated event {target_event_id!r}"
                )
            if target.fact_id != event.fact_id or target.event_id == event.event_id:
                raise RevisionGraphError(
                    f"event {event.event_id}: compensated event must be a prior event of same fact"
                )
            if target.valid_dt > event.valid_dt or target.observed_dt > event.observed_dt:
                raise TemporalError(
                    f"event {event.event_id}: compensated event {target.event_id} is later"
                )
            dependencies.add(target.event_id)
        linked.append(
            _Event(**{**event.__dict__, "dependencies": tuple(sorted(dependencies))})
        )
    return linked, by_event


def _topological(events: Iterable[_Event]) -> list[_Event]:
    event_list = list(events)
    by_id = {event.event_id: event for event in event_list}
    indegree = {event.event_id: 0 for event in event_list}
    followers: dict[str, set[str]] = {event.event_id: set() for event in event_list}
    for event in event_list:
        for dependency in event.dependencies:
            if dependency not in by_id:
                continue
            indegree[event.event_id] += 1
            followers[dependency].add(event.event_id)
    ready = sorted(
        (event for event in event_list if indegree[event.event_id] == 0),
        key=lambda event: (event.observed_dt, event.valid_dt, event.event_id),
    )
    result: list[_Event] = []
    while ready:
        event = ready.pop(0)
        result.append(event)
        for follower_id in sorted(followers[event.event_id]):
            indegree[follower_id] -= 1
            if indegree[follower_id] == 0:
                ready.append(by_id[follower_id])
                ready.sort(key=lambda item: (item.observed_dt, item.valid_dt, item.event_id))
    if len(result) != len(event_list):
        cycle = sorted(event_id for event_id, degree in indegree.items() if degree)
        raise RevisionGraphError(f"revision dependency cycle: {cycle}")
    return result


def _apply(state: _FoldState, event: _Event, by_event: Mapping[str, _Event]) -> None:
    active = state.active.setdefault(event.fact_id, set())
    if event.operation == "SUPERSEDE":
        missing = set(event.supersedes) - active
        if missing:
            raise RevisionGraphError(
                f"event {event.event_id}: supersedes non-current revisions {sorted(missing)}"
            )
        active.difference_update(event.supersedes)
    elif event.operation == "CONTRADICT":
        missing = set(event.contradicts) - active
        if missing:
            raise RevisionGraphError(
                f"event {event.event_id}: contradicts non-current revisions {sorted(missing)}"
            )
        for target in event.contradicts:
            state.contradictions.add(tuple(sorted((target, event.revision_id))))
    elif event.operation == "COMPENSATE":
        target_event_id = event.compensates[0]
        if target_event_id in state.compensated_events:
            raise RevisionGraphError(
                f"event {event.event_id}: event {target_event_id!r} already compensated"
            )
        target_revision = by_event[target_event_id].revision_id
        if target_revision not in active:
            raise RevisionGraphError(
                f"event {event.event_id}: compensated revision {target_revision!r} is not current"
            )
        active.remove(target_revision)
        state.compensated_events.add(target_event_id)

    active.add(event.revision_id)
    state.included_revisions.setdefault(event.fact_id, set()).add(event.revision_id)
    state.history_events.setdefault(event.fact_id, []).append(event.event_id)


def _pairwise_contradicted(active: set[str], contradictions: set[tuple[str, str]]) -> bool:
    return all(
        tuple(sorted(pair)) in contradictions for pair in itertools.combinations(sorted(active), 2)
    )


def _fact_answer(
    fact_id: str,
    state: _FoldState,
    revisions: Mapping[str, _Event],
) -> dict[str, Any]:
    active = state.active.get(fact_id, set())
    if len(active) > 1 and not _pairwise_contradicted(active, state.contradictions):
        raise AmbiguousCutError(
            f"fact {fact_id}: ambiguous current cut {sorted(active)} lacks pairwise CONTRADICT"
        )
    included = state.included_revisions.get(fact_id, set())
    historical_pairs = [
        list(pair)
        for pair in sorted(state.contradictions)
        if pair[0] in included or pair[1] in included
    ]
    current = [
        {
            "revision_id": revision_id,
            "revision_sha256": _sha256(
                {
                    "fact_id": fact_id,
                    "revision_id": revision_id,
                    "value": revisions[revision_id].value,
                }
            ),
            "value": revisions[revision_id].value,
        }
        for revision_id in sorted(active)
    ]
    answer: dict[str, Any] = {
        "fact_id": fact_id,
        "fact_sha256": _sha256({"fact_id": fact_id}),
        "status": "ABSENT" if not active else ("CONTRADICTED" if len(active) > 1 else "CURRENT"),
        "current": current,
        "stale_revision_ids": sorted(included - active),
        "history_event_ids": list(state.history_events.get(fact_id, [])),
        "contradiction_history": historical_pairs,
    }
    answer["cut_sha256"] = _sha256(answer)
    return answer


def _fold_answers(
    events: Sequence[_Event],
    by_event: Mapping[str, _Event],
    revisions: Mapping[str, _Event],
    fact_ids: Sequence[str],
) -> list[dict[str, Any]]:
    state = _FoldState()
    for event in events:
        _apply(state, event, by_event)
    return [_fact_answer(fact_id, state, revisions) for fact_id in fact_ids]


def _state_signature(state: _FoldState) -> dict[str, Any]:
    return {
        "active": {key: sorted(value) for key, value in sorted(state.active.items())},
        "included_revisions": {
            key: sorted(value) for key, value in sorted(state.included_revisions.items())
        },
        "history_events": {
            # Branch delivery order is not semantic history order.  The
            # canonical stream records one sequence separately; confluence is
            # judged over the same event set and derived state.
            key: sorted(value) for key, value in sorted(state.history_events.items())
        },
        "contradictions": [list(pair) for pair in sorted(state.contradictions)],
        "compensated_events": sorted(state.compensated_events),
    }


def _compile_branches(
    branch_sources: Sequence[Mapping[str, Any]],
    ordered: Sequence[_Event],
    by_event: Mapping[str, _Event],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    order_index = {event.event_id: index for index, event in enumerate(ordered)}
    for branch in branch_sources:
        branch_id = branch["branch_id"]
        branch_ids = tuple(branch["event_ids"])
        branch_set = set(branch_ids)
        ancestors: set[str] = set()
        pending = list(branch_ids)
        while pending:
            event_id = pending.pop()
            for dependency in by_event[event_id].dependencies:
                if dependency not in branch_set and dependency not in ancestors:
                    ancestors.add(dependency)
                    pending.append(dependency)
        prefix = [event for event in ordered if event.event_id in ancestors]
        permutations: list[dict[str, Any]] = []
        outcomes: set[str] = set()
        errors = 0
        for permutation in itertools.permutations(branch_ids):
            state = _FoldState()
            try:
                for event in prefix:
                    _apply(state, event, by_event)
                for event_id in permutation:
                    _apply(state, by_event[event_id], by_event)
                outcome_payload: dict[str, Any] = {
                    "status": "STATE",
                    "state": _state_signature(state),
                }
            except RevisionCompileError as exc:
                errors += 1
                outcome_payload = {
                    "status": "REJECTED_ORDER",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            digest = _sha256(outcome_payload)
            outcomes.add(digest)
            permutations.append({"order": list(permutation), "outcome_sha256": digest})

        observed_confluent = len(outcomes) == 1 and errors == 0
        expectation = branch["expectation"]
        if expectation == "CONFLUENT" and not observed_confluent:
            raise ConfluenceError(
                f"branch {branch_id}: declared commutative but permutations diverge/reject"
            )
        if expectation == "NON_CONFLUENT" and len(outcomes) == 1:
            raise ConfluenceError(
                f"branch {branch_id}: registered non-confluence reason but all permutations agree"
            )
        compiled = {
            "branch_id": branch_id,
            "event_ids": list(branch_ids),
            "canonical_event_order": sorted(branch_ids, key=order_index.__getitem__),
            "expectation": expectation,
            "nonconfluence_reason": branch["nonconfluence_reason"],
            "observed_confluent": observed_confluent,
            "permutations": permutations,
        }
        compiled["branch_sha256"] = _sha256(compiled)
        result.append(compiled)
    return result


def compile_revision_stream(source: bytes) -> CompiledRevisionStream:
    """Compile one canonical source block into deterministic stream/oracle bytes."""
    source_document, parsed_events, parsed_query_times = _parse_source(source)
    linked_events, _ = _link_events(parsed_events)
    ordered = _topological(linked_events)
    by_event = {event.event_id: event for event in linked_events}
    revisions = {event.revision_id: event for event in linked_events}
    fact_ids = sorted({event.fact_id for event in linked_events})

    # Validate the complete canonical execution before emitting any oracle.
    _fold_answers(ordered, by_event, revisions, fact_ids)

    per_fact_sequence: dict[str, int] = {}
    compiled_events: list[dict[str, Any]] = []
    for sequence, event in enumerate(ordered, start=1):
        per_fact_sequence[event.fact_id] = per_fact_sequence.get(event.fact_id, 0) + 1
        evidence = [
            {
                "evidence_id": item["evidence_id"],
                "evidence_sha256": _sha256(
                    {"evidence_id": item["evidence_id"], "payload": item["payload"]}
                ),
            }
            for item in event.evidence
        ]
        source_binding = {
            "source_id": event.source["source_id"],
            "source_sha256": _sha256(
                {
                    "source_id": event.source["source_id"],
                    "payload": event.source["payload"],
                }
            ),
        }
        compiled_event: dict[str, Any] = {
            "sequence": sequence,
            "revision_sequence": per_fact_sequence[event.fact_id],
            "event_id": event.event_id,
            "revision_id": event.revision_id,
            "fact_id": event.fact_id,
            "operation": event.operation,
            "value": event.value,
            "valid_time": event.valid_time,
            "observed_at": event.observed_at,
            "supersedes": list(event.supersedes),
            "contradicts": list(event.contradicts),
            "compensates": list(event.compensates),
            "dependencies": list(event.dependencies),
            "fact_sha256": _sha256({"fact_id": event.fact_id}),
            "revision_sha256": _sha256(
                {
                    "fact_id": event.fact_id,
                    "revision_id": event.revision_id,
                    "value": event.value,
                }
            ),
            "evidence": evidence,
            "source": source_binding,
        }
        compiled_event["event_sha256"] = _sha256(compiled_event)
        compiled_events.append(compiled_event)

    oracles: list[dict[str, Any]] = []
    for query_time, query_dt in zip(source_document["query_times"], parsed_query_times):
        current_events = [event for event in ordered if event.valid_dt <= query_dt]
        as_of_events = [
            event
            for event in current_events
            if event.observed_dt <= query_dt
        ]
        current = _fold_answers(current_events, by_event, revisions, fact_ids)
        as_of = _fold_answers(as_of_events, by_event, revisions, fact_ids)
        oracle = {
            "query_time": query_time,
            "current": current,
            "as_of": as_of,
            "current_cut_sha256": _sha256(current),
            "as_of_cut_sha256": _sha256(as_of),
        }
        oracles.append(oracle)

    branches = _compile_branches(source_document["branches"], ordered, by_event)
    stream_sha256 = _sha256(compiled_events)
    oracle_sha256 = _sha256(oracles)
    output = {
        "schema": COMPILED_SCHEMA,
        "stream_id": source_document["stream_id"],
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "stream_sha256": stream_sha256,
        "oracle_sha256": oracle_sha256,
        "events": compiled_events,
        "query_times": list(source_document["query_times"]),
        "oracles": oracles,
        "branches": branches,
        "history_preserved": True,
        "gold_oracle_basis": "operation/value/time/evidence/source labels; never similarity",
    }
    encoded = canonical_json_bytes(output)
    return CompiledRevisionStream(
        canonical_bytes=encoded,
        source_sha256=output["source_sha256"],
        stream_sha256=stream_sha256,
        oracle_sha256=oracle_sha256,
    )


def verify_compiled_revision_stream(
    source: bytes, compiled_bytes: bytes
) -> CompiledRevisionStream:
    """Recompile the bound source and reject any stored-byte drift."""
    expected = compile_revision_stream(source)
    if not isinstance(compiled_bytes, bytes) or compiled_bytes != expected.canonical_bytes:
        raise RevisionCompileError(
            "compiled revision stream tamper/drift: bytes do not match deterministic replay"
        )
    return expected


compile_source_block = compile_revision_stream


__all__ = [
    "AmbiguousCutError",
    "CanonicalJSONError",
    "COMPILED_SCHEMA",
    "CompiledRevisionStream",
    "ConfluenceError",
    "DuplicateIDError",
    "OperationError",
    "OPERATIONS",
    "RevisionCompileError",
    "RevisionGraphError",
    "SOURCE_SCHEMA",
    "TemporalError",
    "canonical_json_bytes",
    "compile_revision_stream",
    "compile_source_block",
    "load_canonical_source",
    "verify_compiled_revision_stream",
]
