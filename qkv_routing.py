"""Deterministic evidence-bound ordered key/value routing.

This module is a deliberately small QKV-R1 mechanism probe.  It is not neural
attention and it does not parse natural-language questions.  A frozen query
program supplies an *ordered* tuple of relation slots.  At each step:

``Q_t = (current frontier, ordered relation[t])``
``K_e = (record source frontier, record predicate)``
``V_e = (record target frontier, two exact endpoint selectors)``

Exactly one key must match ``Q_t``.  Its value becomes the next frontier.  A
missing or ambiguous key refuses the whole query atomically: no partial steps
or intermediate frontier escape in the returned receipt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
import unicodedata
from typing import Any, Literal, Sequence


SCHEMA_VERSION = "hswm-qkv-routing/v1"
RECEIPT_SCHEMA_VERSION = "hswm-qkv-route-receipt/v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

RouteStatus = Literal["PASS", "PARTIAL", "REFUSED"]
RefusalCode = Literal["NO_KEY_MATCH", "AMBIGUOUS_KEY_MATCH"]


class QKVIntegrityError(ValueError):
    """An immutable graph/program contract is malformed or hash-inconsistent."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise QKVIntegrityError(f"{label} must be non-empty text")


@dataclass(frozen=True)
class ExactSelectorV1:
    """One exact codepoint span in an immutable source text preimage."""

    source_id: str
    start: int
    end: int
    exact: str
    source_text_sha256: str
    text_scope: str = "body"
    offset_unit: str = "unicode_codepoint"

    def __post_init__(self) -> None:
        _require_text(self.source_id, "selector source_id")
        _require_text(self.exact, "selector exact")
        if self.text_scope not in {"body", "title"}:
            raise QKVIntegrityError("selector text_scope must be body or title")
        if self.offset_unit != "unicode_codepoint":
            raise QKVIntegrityError("selector offset_unit must be unicode_codepoint")
        if not isinstance(self.start, int) or not isinstance(self.end, int):
            raise QKVIntegrityError("selector offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise QKVIntegrityError("selector must be a non-empty range")
        if self.end - self.start != len(self.exact):
            raise QKVIntegrityError("selector range and exact text length disagree")
        if not isinstance(self.source_text_sha256, str) or not _SHA256_RE.fullmatch(
            self.source_text_sha256
        ):
            raise QKVIntegrityError("selector source_text_sha256 must be lowercase SHA-256")


def bind_exact_selector(
    source_id: str,
    source_text: str,
    exact: str,
    *,
    start: int | None = None,
    text_scope: str = "body",
) -> ExactSelectorV1:
    """Bind an exact selector, rejecting absent or ambiguous implicit matches."""

    _require_text(source_id, "source_id")
    if not isinstance(source_text, str):
        raise QKVIntegrityError("source_text must be text")
    _require_text(exact, "exact")
    if start is None:
        first = source_text.find(exact)
        if first < 0:
            raise QKVIntegrityError("exact selector is absent from source text")
        if source_text.find(exact, first + 1) >= 0:
            raise QKVIntegrityError(
                "implicit exact selector is ambiguous; provide an explicit start"
            )
        start = first
    if not isinstance(start, int) or start < 0:
        raise QKVIntegrityError("selector start must be a non-negative integer")
    end = start + len(exact)
    if source_text[start:end] != exact:
        raise QKVIntegrityError("selector does not match its source text preimage")
    return ExactSelectorV1(
        source_id=source_id,
        start=start,
        end=end,
        exact=exact,
        source_text_sha256=sha256(source_text.encode("utf-8")).hexdigest(),
        text_scope=text_scope,
    )


@dataclass(frozen=True)
class EvidenceKVV1:
    """One evidence-bound key/value record.

    The two selectors bind the same value surface at the source and target
    endpoints.  The predicate is the semantic key; the target and selectors are
    the value carried into the next query state.
    """

    record_id: str
    source_frontier: str
    predicate: str
    target_frontier: str
    source_selector: ExactSelectorV1
    target_selector: ExactSelectorV1

    def __post_init__(self) -> None:
        for label, value in (
            ("record_id", self.record_id),
            ("source_frontier", self.source_frontier),
            ("predicate", self.predicate),
            ("target_frontier", self.target_frontier),
        ):
            _require_text(value, label)
        if self.source_frontier == self.target_frontier:
            raise QKVIntegrityError("self-routing records are forbidden")
        if self.source_selector.source_id != self.source_frontier:
            raise QKVIntegrityError("source selector is bound to another frontier")
        if self.target_selector.source_id != self.target_frontier:
            raise QKVIntegrityError("target selector is bound to another frontier")
        if _normalized(self.source_selector.exact) != _normalized(
            self.target_selector.exact
        ):
            raise QKVIntegrityError("value endpoint selectors do not identify one surface")


@dataclass(frozen=True)
class QKVGraphV1:
    records: tuple[EvidenceKVV1, ...]
    graph_sha256: str


def make_qkv_graph(records: Sequence[EvidenceKVV1]) -> QKVGraphV1:
    """Canonicalize records so caller iteration order cannot affect routing."""

    if isinstance(records, (str, bytes)):
        raise QKVIntegrityError("records must be a sequence of EvidenceKVV1")
    rows = tuple(records)
    if not rows or any(not isinstance(row, EvidenceKVV1) for row in rows):
        raise QKVIntegrityError("graph needs at least one EvidenceKVV1 record")
    record_ids = tuple(row.record_id for row in rows)
    if len(record_ids) != len(set(record_ids)):
        raise QKVIntegrityError("record_id values must be unique")
    ordered = tuple(sorted(rows, key=lambda row: (
        row.source_frontier,
        _normalized(row.predicate),
        row.target_frontier,
        row.record_id,
    )))
    graph_sha256 = _digest({
        "schema_version": SCHEMA_VERSION,
        "records": tuple(asdict(row) for row in ordered),
    })
    return QKVGraphV1(records=ordered, graph_sha256=graph_sha256)


def _require_graph(graph: QKVGraphV1) -> None:
    if not isinstance(graph, QKVGraphV1):
        raise QKVIntegrityError("graph must be QKVGraphV1")
    expected = make_qkv_graph(graph.records)
    if graph != expected:
        raise QKVIntegrityError("graph order or SHA-256 is inconsistent")


@dataclass(frozen=True)
class QueryProgramV1:
    """A query-only ordered relation program; it contains no answer labels."""

    initial_frontier: str
    relations: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.initial_frontier, "initial_frontier")
        if not isinstance(self.relations, tuple) or not self.relations:
            raise QKVIntegrityError("relations must be a non-empty tuple")
        for relation in self.relations:
            _require_text(relation, "relation")

    @property
    def program_sha256(self) -> str:
        return _digest({
            "schema_version": "hswm-qkv-query-program/v1",
            "initial_frontier": self.initial_frontier,
            "relations": self.relations,
        })


@dataclass(frozen=True)
class QueryStateV1:
    frontier: str
    relation_index: int
    relation: str | None

    def __post_init__(self) -> None:
        _require_text(self.frontier, "query-state frontier")
        if not isinstance(self.relation_index, int) or self.relation_index < 0:
            raise QKVIntegrityError("query-state relation_index must be non-negative")
        if self.relation is not None:
            _require_text(self.relation, "query-state relation")

    @property
    def state_sha256(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class EvidenceKeyV1:
    source_frontier: str
    predicate: str

    @property
    def key_sha256(self) -> str:
        return _digest({
            "source_frontier": self.source_frontier,
            "predicate_normalized": _normalized(self.predicate),
        })


@dataclass(frozen=True)
class EvidenceValueV1:
    target_frontier: str
    source_selector: ExactSelectorV1
    target_selector: ExactSelectorV1

    @property
    def value_sha256(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class RouteStepV1:
    depth: int
    record_id: str
    q_before: QueryStateV1
    q_before_sha256: str
    key: EvidenceKeyV1
    key_sha256: str
    value: EvidenceValueV1
    value_sha256: str
    q_after: QueryStateV1
    q_after_sha256: str


@dataclass(frozen=True)
class QKVRouteReceiptV1:
    schema_version: str
    receipt_id: str
    route_sha256: str
    graph_sha256: str
    program_sha256: str
    max_steps: int
    program_length: int
    status: RouteStatus
    refusal_code: RefusalCode | None
    refusal_depth: int | None
    initial_frontier: str
    final_frontier: str
    completed_steps: int
    steps: tuple[RouteStepV1, ...]
    research_only: bool = True


def _seal_receipt(
    *,
    graph: QKVGraphV1,
    program: QueryProgramV1,
    max_steps: int,
    status: RouteStatus,
    refusal_code: RefusalCode | None,
    refusal_depth: int | None,
    final_frontier: str,
    steps: tuple[RouteStepV1, ...],
) -> QKVRouteReceiptV1:
    route_payload = {
        "status": status,
        "refusal_code": refusal_code,
        "refusal_depth": refusal_depth,
        "initial_frontier": program.initial_frontier,
        "final_frontier": final_frontier,
        "completed_steps": len(steps),
        "steps": tuple(asdict(step) for step in steps),
    }
    route_sha256 = _digest(route_payload)
    payload = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "route_sha256": route_sha256,
        "graph_sha256": graph.graph_sha256,
        "program_sha256": program.program_sha256,
        "max_steps": max_steps,
        "program_length": len(program.relations),
        **route_payload,
        "research_only": True,
    }
    receipt_id = f"hswm:qkv_route_receipt:v1:{_digest(payload)}"
    return QKVRouteReceiptV1(
        schema_version=RECEIPT_SCHEMA_VERSION,
        receipt_id=receipt_id,
        route_sha256=route_sha256,
        graph_sha256=graph.graph_sha256,
        program_sha256=program.program_sha256,
        max_steps=max_steps,
        program_length=len(program.relations),
        status=status,
        refusal_code=refusal_code,
        refusal_depth=refusal_depth,
        initial_frontier=program.initial_frontier,
        final_frontier=final_frontier,
        completed_steps=len(steps),
        steps=steps,
    )


def route_qkv(
    graph: QKVGraphV1,
    program: QueryProgramV1,
    *,
    max_steps: int | None = None,
) -> QKVRouteReceiptV1:
    """Execute full or bounded ordered routing with atomic runtime refusal."""

    _require_graph(graph)
    if not isinstance(program, QueryProgramV1):
        raise QKVIntegrityError("program must be QueryProgramV1")
    limit = len(program.relations) if max_steps is None else max_steps
    if not isinstance(limit, int) or limit < 1 or limit > len(program.relations):
        raise QKVIntegrityError("max_steps must be in [1, len(relations)]")

    current = program.initial_frontier
    steps: list[RouteStepV1] = []
    for relation_index, relation in enumerate(program.relations[:limit]):
        candidates = tuple(
            record for record in graph.records
            if record.source_frontier == current
            and _normalized(record.predicate) == _normalized(relation)
        )
        if len(candidates) != 1:
            refusal_code: RefusalCode = (
                "NO_KEY_MATCH" if not candidates else "AMBIGUOUS_KEY_MATCH"
            )
            # Query-atomic refusal: discard every already-computed step and
            # restore the externally visible frontier to the initial state.
            return _seal_receipt(
                graph=graph,
                program=program,
                max_steps=limit,
                status="REFUSED",
                refusal_code=refusal_code,
                refusal_depth=relation_index + 1,
                final_frontier=program.initial_frontier,
                steps=(),
            )

        record = candidates[0]
        q_before = QueryStateV1(
            frontier=current,
            relation_index=relation_index,
            relation=relation,
        )
        key = EvidenceKeyV1(
            source_frontier=record.source_frontier,
            predicate=record.predicate,
        )
        value = EvidenceValueV1(
            target_frontier=record.target_frontier,
            source_selector=record.source_selector,
            target_selector=record.target_selector,
        )
        next_index = relation_index + 1
        next_relation = (
            program.relations[next_index]
            if next_index < len(program.relations) else None
        )
        q_after = QueryStateV1(
            frontier=value.target_frontier,
            relation_index=next_index,
            relation=next_relation,
        )
        steps.append(RouteStepV1(
            depth=relation_index + 1,
            record_id=record.record_id,
            q_before=q_before,
            q_before_sha256=q_before.state_sha256,
            key=key,
            key_sha256=key.key_sha256,
            value=value,
            value_sha256=value.value_sha256,
            q_after=q_after,
            q_after_sha256=q_after.state_sha256,
        ))
        current = value.target_frontier

    status: RouteStatus = "PASS" if limit == len(program.relations) else "PARTIAL"
    return _seal_receipt(
        graph=graph,
        program=program,
        max_steps=limit,
        status=status,
        refusal_code=None,
        refusal_depth=None,
        final_frontier=current,
        steps=tuple(steps),
    )


def route_full(graph: QKVGraphV1, program: QueryProgramV1) -> QKVRouteReceiptV1:
    """Execute every frozen relation slot."""

    return route_qkv(graph, program)


def route_k1(graph: QKVGraphV1, program: QueryProgramV1) -> QKVRouteReceiptV1:
    """Matched one-step ablation over the same graph and query program."""

    return route_qkv(graph, program, max_steps=1)


__all__ = [
    "EvidenceKVV1",
    "EvidenceKeyV1",
    "EvidenceValueV1",
    "ExactSelectorV1",
    "QKVGraphV1",
    "QKVIntegrityError",
    "QKVRouteReceiptV1",
    "QueryProgramV1",
    "QueryStateV1",
    "RouteStepV1",
    "bind_exact_selector",
    "make_qkv_graph",
    "route_full",
    "route_k1",
    "route_qkv",
]
