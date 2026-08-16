"""Typed semantic-layer QKV routing with evidence and atomic refusal.

This research kernel is intentionally *not* a homogeneous vector stack.  Its
four layers change both the meaning and the arity of the unresolved state::

    PERSON
      --EXPAND(child)----------------> BRANCH_SET_PERSON
      --MAP_ONE(birth_date)----------> BRANCH_SET_PERSON_DATE
      --REDUCE_SELECT(ARGMIN/ARGMAX)--> SELECTED_PERSON
      --LOOKUP_ONE(birthplace)-------> CITY

The reducer is the QKV-like semantic tooth: ISO dates are Keys and the Persons
bound to the same branch IDs are Values.  No branch vectors are averaged.
Every fact is bound to exact source selectors.  Any missing, ambiguous,
ill-typed, or tied operation refuses the whole query atomically: the caller's
static byte payload is returned unchanged and the public receipt contains no
partial steps.

This module accepts neither evaluator rows nor expected terminal labels.  It
proves only deterministic execution of a frozen synthetic semantic program.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
import unicodedata
from typing import Any, Literal, Sequence

from qkv_routing import ExactSelectorV1


SCHEMA_VERSION = "hswm-semantic-layer-routing/v1"
RECEIPT_SCHEMA_VERSION = "hswm-semantic-layer-route-receipt/v1"

PERSON = "PERSON"
DATE = "DATE"
CITY = "CITY"
BRANCH_SET_PERSON = "BRANCH_SET_PERSON"
BRANCH_SET_PERSON_DATE = "BRANCH_SET_PERSON_DATE"
SELECTED_PERSON = "SELECTED_PERSON"
BRANCH_SET_PERSON_DATE_ERASED = "BRANCH_SET_PERSON_DATE_ERASED"

OperatorKind = Literal["EXPAND", "MAP_ONE", "REDUCE_SELECT", "LOOKUP_ONE"]
ReducerKind = Literal["ARGMIN", "ARGMAX"]
Arity = Literal["ONE", "MANY"]
RouteStatus = Literal["PASS", "REFUSED"]
RefusalCode = Literal[
    "LAYER_ORDER_MISMATCH",
    "TYPE_MISMATCH",
    "ARITY_MISMATCH",
    "INVALID_REDUCER",
    "NO_KEY_MATCH",
    "AMBIGUOUS_KEY_MATCH",
    "MISSING_BRANCH",
    "AMBIGUOUS_BRANCH",
    "INVALID_REDUCER_KEY",
    "TIED_REDUCER_KEY",
    "MISSING_BRANCH_ASSOCIATION",
]
ControlMode = Literal["FULL", "BRANCH_ERASURE"]


class SemanticIntegrityError(ValueError):
    """An immutable fact, program, or content hash is malformed."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalized(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(text.replace("_", " ").replace("-", " ").split())


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SemanticIntegrityError(f"{label} must be non-empty text")


@dataclass(frozen=True)
class TypedFactV1:
    """One typed subject/predicate/value fact with a single source preimage."""

    fact_id: str
    source_id: str
    subject_id: str
    subject_type: str
    predicate: str
    object_id: str
    object_type: str
    subject_selector: ExactSelectorV1
    predicate_selector: ExactSelectorV1
    object_selector: ExactSelectorV1

    def __post_init__(self) -> None:
        for label, value in (
            ("fact_id", self.fact_id),
            ("source_id", self.source_id),
            ("subject_id", self.subject_id),
            ("subject_type", self.subject_type),
            ("predicate", self.predicate),
            ("object_id", self.object_id),
            ("object_type", self.object_type),
        ):
            _require_text(value, label)
        selectors = (
            self.subject_selector, self.predicate_selector, self.object_selector,
        )
        if any(not isinstance(item, ExactSelectorV1) for item in selectors):
            raise SemanticIntegrityError("fact selectors must be ExactSelectorV1")
        if any(item.source_id != self.source_id for item in selectors):
            raise SemanticIntegrityError("fact selectors must share the fact source_id")
        source_hashes = {item.source_text_sha256 for item in selectors}
        if len(source_hashes) != 1:
            raise SemanticIntegrityError("fact selectors must bind one source preimage")
        if _normalized(self.subject_selector.exact) != _normalized(self.subject_id):
            raise SemanticIntegrityError("subject selector and subject_id disagree")
        if _normalized(self.predicate_selector.exact) != _normalized(self.predicate):
            raise SemanticIntegrityError("predicate selector and predicate disagree")
        if _normalized(self.object_selector.exact) != _normalized(self.object_id):
            raise SemanticIntegrityError("object selector and object_id disagree")


@dataclass(frozen=True)
class SemanticMemoryV1:
    facts: tuple[TypedFactV1, ...]
    memory_sha256: str


def make_semantic_memory(facts: Sequence[TypedFactV1]) -> SemanticMemoryV1:
    """Canonicalize facts so input order cannot alter execution or receipts."""

    if isinstance(facts, (str, bytes)):
        raise SemanticIntegrityError("facts must be a sequence of TypedFactV1")
    rows = tuple(facts)
    if not rows or any(not isinstance(row, TypedFactV1) for row in rows):
        raise SemanticIntegrityError("memory needs at least one TypedFactV1")
    fact_ids = tuple(row.fact_id for row in rows)
    if len(fact_ids) != len(set(fact_ids)):
        raise SemanticIntegrityError("fact_id values must be unique")
    ordered = tuple(sorted(rows, key=lambda row: (
        row.subject_type, row.subject_id, _normalized(row.predicate),
        row.object_type, row.object_id, row.fact_id,
    )))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "facts": tuple(asdict(row) for row in ordered),
    }
    return SemanticMemoryV1(ordered, _digest(payload))


def _require_memory(memory: SemanticMemoryV1) -> None:
    if not isinstance(memory, SemanticMemoryV1):
        raise SemanticIntegrityError("memory must be SemanticMemoryV1")
    if memory != make_semantic_memory(memory.facts):
        raise SemanticIntegrityError("memory order or SHA-256 is inconsistent")


@dataclass(frozen=True)
class SemanticLayerV1:
    layer_id: str
    operator: OperatorKind
    input_type: str
    output_type: str
    input_arity: Arity
    output_arity: Arity
    predicate: str | None = None
    reducer: ReducerKind | str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("layer_id", self.layer_id),
            ("operator", self.operator),
            ("input_type", self.input_type),
            ("output_type", self.output_type),
            ("input_arity", self.input_arity),
            ("output_arity", self.output_arity),
        ):
            _require_text(value, label)
        if self.predicate is not None:
            _require_text(self.predicate, "predicate")
        if self.reducer is not None:
            _require_text(self.reducer, "reducer")


@dataclass(frozen=True)
class SemanticProgramV1:
    """Frozen query program containing no evaluator supervision fields."""

    initial_person_id: str
    layers: tuple[SemanticLayerV1, ...]

    def __post_init__(self) -> None:
        _require_text(self.initial_person_id, "initial_person_id")
        if not isinstance(self.layers, tuple) or not self.layers:
            raise SemanticIntegrityError("layers must be a non-empty tuple")
        if any(not isinstance(layer, SemanticLayerV1) for layer in self.layers):
            raise SemanticIntegrityError("layers must contain SemanticLayerV1")
        layer_ids = tuple(layer.layer_id for layer in self.layers)
        if len(layer_ids) != len(set(layer_ids)):
            raise SemanticIntegrityError("layer_id values must be unique")

    @property
    def program_sha256(self) -> str:
        return _digest({
            "schema_version": "hswm-semantic-layer-program/v1",
            "initial_person_id": self.initial_person_id,
            "layers": tuple(asdict(layer) for layer in self.layers),
        })


def make_semantic_program(
    initial_person_id: str, *, reducer: ReducerKind | str = "ARGMIN",
) -> SemanticProgramV1:
    """Build the frozen heterogeneous four-layer program."""

    return SemanticProgramV1(initial_person_id, (
        SemanticLayerV1(
            "expand-child", "EXPAND", PERSON, BRANCH_SET_PERSON,
            "ONE", "MANY", predicate="child",
        ),
        SemanticLayerV1(
            "map-birth-date", "MAP_ONE", BRANCH_SET_PERSON,
            BRANCH_SET_PERSON_DATE, "MANY", "MANY", predicate="birth_date",
        ),
        SemanticLayerV1(
            "reduce-date", "REDUCE_SELECT", BRANCH_SET_PERSON_DATE,
            SELECTED_PERSON, "MANY", "ONE", reducer=reducer,
        ),
        SemanticLayerV1(
            "lookup-birthplace", "LOOKUP_ONE", SELECTED_PERSON, CITY,
            "ONE", "ONE", predicate="birthplace",
        ),
    ))


@dataclass(frozen=True)
class PersonStateV1:
    person_id: str


@dataclass(frozen=True)
class PersonBranchV1:
    branch_id: str
    person_id: str
    expand_fact_id: str


@dataclass(frozen=True)
class BranchSetPersonStateV1:
    branches: tuple[PersonBranchV1, ...]


@dataclass(frozen=True)
class PersonDateBranchV1:
    branch_id: str
    person_id: str
    date_key: str
    expand_fact_id: str
    date_fact_id: str


@dataclass(frozen=True)
class BranchSetPersonDateStateV1:
    branches: tuple[PersonDateBranchV1, ...]


@dataclass(frozen=True)
class ErasedBranchSetPersonDateStateV1:
    """Typed reducer inputs after destroying every Date-to-Person binding."""

    date_keys: tuple[str, ...]
    person_values: tuple[str, ...]


@dataclass(frozen=True)
class SelectedPersonStateV1:
    branch_id: str
    person_id: str
    date_key: str
    expand_fact_id: str
    date_fact_id: str
    reducer: str


@dataclass(frozen=True)
class CityStateV1:
    city_id: str
    birthplace_fact_id: str
    selected_branch_id: str


SemanticState = (
    PersonStateV1 | BranchSetPersonStateV1 | BranchSetPersonDateStateV1 |
    ErasedBranchSetPersonDateStateV1 | SelectedPersonStateV1 | CityStateV1
)


def _state_type(state: SemanticState) -> str:
    if isinstance(state, PersonStateV1):
        return PERSON
    if isinstance(state, BranchSetPersonStateV1):
        return BRANCH_SET_PERSON
    if isinstance(state, BranchSetPersonDateStateV1):
        return BRANCH_SET_PERSON_DATE
    if isinstance(state, ErasedBranchSetPersonDateStateV1):
        return BRANCH_SET_PERSON_DATE_ERASED
    if isinstance(state, SelectedPersonStateV1):
        return SELECTED_PERSON
    if isinstance(state, CityStateV1):
        return CITY
    raise SemanticIntegrityError("unknown semantic state")


def _state_digest(state: SemanticState) -> str:
    return _digest({"state_type": _state_type(state), "state": asdict(state)})


@dataclass(frozen=True)
class BranchLineageV1:
    branch_id: str
    person_id: str
    expand_fact_id: str
    date_fact_id: str | None
    date_key: str | None


@dataclass(frozen=True)
class ReducerPairV1:
    branch_id: str
    date_key: str
    person_value: str
    selected: bool


@dataclass(frozen=True)
class EvidenceFactReceiptV1:
    """The exact source-bound preimages selected by one semantic layer."""

    fact_id: str
    subject_selector: ExactSelectorV1
    predicate_selector: ExactSelectorV1
    object_selector: ExactSelectorV1


@dataclass(frozen=True)
class SemanticStepReceiptV1:
    depth: int
    layer_id: str
    operator: str
    input_type: str
    output_type: str
    input_arity: str
    output_arity: str
    input_count: int
    output_count: int
    query_sha256: str
    key_sha256: str
    value_sha256: str
    input_state_sha256: str
    output_state_sha256: str
    selected_fact_ids: tuple[str, ...]
    evidence_facts: tuple[EvidenceFactReceiptV1, ...]
    branch_lineage: tuple[BranchLineageV1, ...]
    reducer_pairs: tuple[ReducerPairV1, ...]
    selected_branch_id: str | None
    previous_step_sha256: str
    step_sha256: str


@dataclass(frozen=True)
class SemanticRouteReceiptV1:
    schema_version: str
    memory_sha256: str
    program_sha256: str
    control: ControlMode
    status: RouteStatus
    refusal_code: RefusalCode | None
    refusal_layer_id: str | None
    initial_type: str
    terminal_type: str | None
    terminal_value_id: str | None
    ablation_state_type: str | None
    ablation_state_sha256: str | None
    static_payload_sha256: str
    final_payload_sha256: str
    steps: tuple[SemanticStepReceiptV1, ...]
    evaluator_labels_seen: int
    receipt_sha256: str
    research_only: bool = True


_EXPECTED = (
    ("EXPAND", PERSON, BRANCH_SET_PERSON, "ONE", "MANY"),
    ("MAP_ONE", BRANCH_SET_PERSON, BRANCH_SET_PERSON_DATE, "MANY", "MANY"),
    ("REDUCE_SELECT", BRANCH_SET_PERSON_DATE, SELECTED_PERSON, "MANY", "ONE"),
    ("LOOKUP_ONE", SELECTED_PERSON, CITY, "ONE", "ONE"),
)


def _preflight_program(
    program: SemanticProgramV1,
) -> tuple[RefusalCode, str | None] | None:
    if len(program.layers) != len(_EXPECTED):
        return "LAYER_ORDER_MISMATCH", None
    for layer, expected in zip(program.layers, _EXPECTED, strict=True):
        operator, input_type, output_type, input_arity, output_arity = expected
        if layer.operator != operator:
            return "LAYER_ORDER_MISMATCH", layer.layer_id
        if (layer.input_type, layer.output_type) != (input_type, output_type):
            return "TYPE_MISMATCH", layer.layer_id
        if (layer.input_arity, layer.output_arity) != (input_arity, output_arity):
            return "ARITY_MISMATCH", layer.layer_id
        if layer.operator == "REDUCE_SELECT":
            if layer.reducer not in {"ARGMIN", "ARGMAX"}:
                return "INVALID_REDUCER", layer.layer_id
            if layer.predicate is not None:
                return "LAYER_ORDER_MISMATCH", layer.layer_id
        elif layer.reducer is not None or layer.predicate is None:
            return "LAYER_ORDER_MISMATCH", layer.layer_id
    return None


def _lineage(state: SemanticState) -> tuple[BranchLineageV1, ...]:
    if isinstance(state, BranchSetPersonStateV1):
        return tuple(BranchLineageV1(
            item.branch_id, item.person_id, item.expand_fact_id, None, None,
        ) for item in state.branches)
    if isinstance(state, BranchSetPersonDateStateV1):
        return tuple(BranchLineageV1(
            item.branch_id, item.person_id, item.expand_fact_id,
            item.date_fact_id, item.date_key,
        ) for item in state.branches)
    if isinstance(state, SelectedPersonStateV1):
        return (BranchLineageV1(
            state.branch_id, state.person_id, state.expand_fact_id,
            state.date_fact_id, state.date_key,
        ),)
    return ()


def _state_count(state: SemanticState) -> int:
    if isinstance(state, (BranchSetPersonStateV1, BranchSetPersonDateStateV1)):
        return len(state.branches)
    return 1


def _make_step(
    *, depth: int, layer: SemanticLayerV1, before: SemanticState,
    after: SemanticState, query_payload: Any, key_payload: Any,
    value_payload: Any, fact_ids: tuple[str, ...],
    evidence_facts: tuple[TypedFactV1, ...] = (),
    reducer_pairs: tuple[ReducerPairV1, ...] = (),
    selected_branch_id: str | None = None, previous_step_sha256: str,
) -> SemanticStepReceiptV1:
    evidence_receipts = tuple(EvidenceFactReceiptV1(
        fact_id=item.fact_id,
        subject_selector=item.subject_selector,
        predicate_selector=item.predicate_selector,
        object_selector=item.object_selector,
    ) for item in evidence_facts)
    if tuple(item.fact_id for item in evidence_receipts) != fact_ids:
        raise SemanticIntegrityError("selected fact IDs and evidence receipts disagree")
    payload = {
        "depth": depth,
        "layer_id": layer.layer_id,
        "operator": layer.operator,
        "input_type": layer.input_type,
        "output_type": layer.output_type,
        "input_arity": layer.input_arity,
        "output_arity": layer.output_arity,
        "input_count": _state_count(before),
        "output_count": _state_count(after),
        "query_sha256": _digest(query_payload),
        "key_sha256": _digest(key_payload),
        "value_sha256": _digest(value_payload),
        "input_state_sha256": _state_digest(before),
        "output_state_sha256": _state_digest(after),
        "selected_fact_ids": fact_ids,
        "evidence_facts": tuple(asdict(item) for item in evidence_receipts),
        "branch_lineage": tuple(asdict(item) for item in _lineage(after)),
        "reducer_pairs": tuple(asdict(item) for item in reducer_pairs),
        "selected_branch_id": selected_branch_id,
        "previous_step_sha256": previous_step_sha256,
    }
    step_sha256 = _digest(payload)
    return SemanticStepReceiptV1(
        depth=depth, layer_id=layer.layer_id, operator=layer.operator,
        input_type=layer.input_type, output_type=layer.output_type,
        input_arity=layer.input_arity, output_arity=layer.output_arity,
        input_count=payload["input_count"], output_count=payload["output_count"],
        query_sha256=payload["query_sha256"], key_sha256=payload["key_sha256"],
        value_sha256=payload["value_sha256"],
        input_state_sha256=payload["input_state_sha256"],
        output_state_sha256=payload["output_state_sha256"],
        selected_fact_ids=fact_ids, evidence_facts=evidence_receipts,
        branch_lineage=_lineage(after),
        reducer_pairs=reducer_pairs, selected_branch_id=selected_branch_id,
        previous_step_sha256=previous_step_sha256, step_sha256=step_sha256,
    )


def _seal_receipt(
    *, memory: SemanticMemoryV1, program: SemanticProgramV1,
    static_payload: bytes, final_payload: bytes, status: RouteStatus,
    refusal_code: RefusalCode | None, refusal_layer_id: str | None,
    terminal_type: str | None, terminal_value_id: str | None,
    steps: tuple[SemanticStepReceiptV1, ...],
    control: ControlMode = "FULL",
    ablation_state: ErasedBranchSetPersonDateStateV1 | None = None,
) -> SemanticRouteReceiptV1:
    payload = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "memory_sha256": memory.memory_sha256,
        "program_sha256": program.program_sha256,
        "control": control,
        "status": status,
        "refusal_code": refusal_code,
        "refusal_layer_id": refusal_layer_id,
        "initial_type": PERSON,
        "terminal_type": terminal_type,
        "terminal_value_id": terminal_value_id,
        "ablation_state_type": (
            None if ablation_state is None else _state_type(ablation_state)
        ),
        "ablation_state_sha256": (
            None if ablation_state is None else _state_digest(ablation_state)
        ),
        "static_payload_sha256": sha256(static_payload).hexdigest(),
        "final_payload_sha256": sha256(final_payload).hexdigest(),
        "steps": tuple(asdict(step) for step in steps),
        "evaluator_labels_seen": 0,
        "research_only": True,
    }
    receipt_sha256 = _digest(payload)
    return SemanticRouteReceiptV1(
        schema_version=RECEIPT_SCHEMA_VERSION,
        memory_sha256=memory.memory_sha256,
        program_sha256=program.program_sha256,
        control=control,
        status=status, refusal_code=refusal_code,
        refusal_layer_id=refusal_layer_id, initial_type=PERSON,
        terminal_type=terminal_type, terminal_value_id=terminal_value_id,
        ablation_state_type=payload["ablation_state_type"],
        ablation_state_sha256=payload["ablation_state_sha256"],
        static_payload_sha256=payload["static_payload_sha256"],
        final_payload_sha256=payload["final_payload_sha256"],
        steps=steps, evaluator_labels_seen=0,
        receipt_sha256=receipt_sha256,
    )


def _refuse(
    memory: SemanticMemoryV1, program: SemanticProgramV1,
    static_payload: bytes, code: RefusalCode, layer_id: str | None,
    *, control: ControlMode = "FULL",
    ablation_state: ErasedBranchSetPersonDateStateV1 | None = None,
) -> tuple[bytes, SemanticRouteReceiptV1]:
    receipt = _seal_receipt(
        memory=memory, program=program, static_payload=static_payload,
        final_payload=static_payload, status="REFUSED", refusal_code=code,
        refusal_layer_id=layer_id, terminal_type=None, terminal_value_id=None,
        steps=(), control=control, ablation_state=ablation_state,
    )
    return static_payload, receipt


def _fact_key(fact: TypedFactV1) -> dict[str, str]:
    return {
        "fact_id": fact.fact_id, "subject_id": fact.subject_id,
        "subject_type": fact.subject_type, "predicate": _normalized(fact.predicate),
        "object_type": fact.object_type,
    }


def _addressed(
    memory: SemanticMemoryV1, subject_id: str, predicate: str,
) -> tuple[TypedFactV1, ...]:
    return tuple(
        fact for fact in memory.facts
        if fact.subject_id == subject_id
        and _normalized(fact.predicate) == _normalized(predicate)
    )


def _unique_typed_fact(
    memory: SemanticMemoryV1, *, subject_id: str, predicate: str,
    subject_type: str, object_type: str,
) -> tuple[TypedFactV1 | None, RefusalCode | None]:
    addressed = _addressed(memory, subject_id, predicate)
    eligible = tuple(
        fact for fact in addressed
        if fact.subject_type == subject_type and fact.object_type == object_type
    )
    if not eligible:
        return None, "TYPE_MISMATCH" if addressed else "NO_KEY_MATCH"
    if len(eligible) != 1:
        return None, "AMBIGUOUS_KEY_MATCH"
    return eligible[0], None


def _reduce_branch_state(
    state: BranchSetPersonDateStateV1 | ErasedBranchSetPersonDateStateV1,
    reducer: str,
) -> tuple[
    SelectedPersonStateV1 | None,
    RefusalCode | None,
    tuple[ReducerPairV1, ...],
]:
    """One reducer entry point for intact and association-erased states."""

    if isinstance(state, ErasedBranchSetPersonDateStateV1):
        # Both typed bags remain, but there is no admissible K->V association.
        # Caller order may not reconstruct the destroyed binding.
        return None, "MISSING_BRANCH_ASSOCIATION", ()
    parsed = tuple((date.fromisoformat(item.date_key), item) for item in state.branches)
    extreme = (
        min(item[0] for item in parsed)
        if reducer == "ARGMIN" else max(item[0] for item in parsed)
    )
    winners = tuple(item for key, item in parsed if key == extreme)
    if len(winners) != 1:
        return None, "TIED_REDUCER_KEY", ()
    winner = winners[0]
    selected = SelectedPersonStateV1(
        branch_id=winner.branch_id, person_id=winner.person_id,
        date_key=winner.date_key, expand_fact_id=winner.expand_fact_id,
        date_fact_id=winner.date_fact_id, reducer=reducer,
    )
    reducer_pairs = tuple(ReducerPairV1(
        branch_id=item.branch_id, date_key=item.date_key,
        person_value=item.person_id, selected=item.branch_id == winner.branch_id,
    ) for item in state.branches)
    return selected, None, reducer_pairs


def execute_semantic_layers(
    memory: SemanticMemoryV1,
    program: SemanticProgramV1,
    *,
    static_payload: bytes,
    control: ControlMode = "FULL",
) -> tuple[bytes, SemanticRouteReceiptV1]:
    """Execute the frozen semantic stack or return the exact static payload.

    Runtime refusal is query-atomic.  Even when a late layer fails, the public
    receipt contains no partial steps and no intermediate state escapes.
    """

    _require_memory(memory)
    if not isinstance(program, SemanticProgramV1):
        raise SemanticIntegrityError("program must be SemanticProgramV1")
    if not isinstance(static_payload, bytes):
        raise TypeError("static_payload must be bytes")
    if control not in {"FULL", "BRANCH_ERASURE"}:
        raise SemanticIntegrityError("unsupported semantic control mode")
    preflight = _preflight_program(program)
    if preflight is not None:
        code, layer_id = preflight
        return _refuse(memory, program, static_payload, code, layer_id)

    state: SemanticState = PersonStateV1(program.initial_person_id)
    steps: list[SemanticStepReceiptV1] = []
    previous = _digest({
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "memory_sha256": memory.memory_sha256,
        "program_sha256": program.program_sha256,
    })

    # 1. PERSON -> BRANCH_SET_PERSON (one-to-many)
    layer = program.layers[0]
    addressed = _addressed(memory, program.initial_person_id, layer.predicate or "")
    eligible = tuple(
        fact for fact in addressed
        if fact.subject_type == PERSON and fact.object_type == PERSON
    )
    if not eligible:
        code: RefusalCode = "TYPE_MISMATCH" if addressed else "MISSING_BRANCH"
        return _refuse(memory, program, static_payload, code, layer.layer_id)
    if len(eligible) < 2:
        return _refuse(
            memory, program, static_payload, "MISSING_BRANCH", layer.layer_id,
        )
    child_ids = tuple(fact.object_id for fact in eligible)
    if len(child_ids) != len(set(child_ids)):
        return _refuse(
            memory, program, static_payload, "AMBIGUOUS_BRANCH", layer.layer_id,
        )
    branches = tuple(sorted((
        PersonBranchV1(
            branch_id="hswm:semantic_branch:v1:" + _digest({
                "program_sha256": program.program_sha256,
                "expand_fact_id": fact.fact_id,
                "person_id": fact.object_id,
            }),
            person_id=fact.object_id,
            expand_fact_id=fact.fact_id,
        ) for fact in eligible
    ), key=lambda item: (item.person_id, item.branch_id)))
    after = BranchSetPersonStateV1(branches)
    step = _make_step(
        depth=1, layer=layer, before=state, after=after,
        query_payload={
            "person_id": program.initial_person_id,
            "predicate": layer.predicate, "required_value_type": PERSON,
        },
        key_payload=tuple(_fact_key(fact) for fact in eligible),
        value_payload=tuple(asdict(item) for item in branches),
        fact_ids=tuple(fact.fact_id for fact in eligible),
        evidence_facts=eligible,
        previous_step_sha256=previous,
    )
    steps.append(step)
    previous = step.step_sha256
    state = after

    # 2. BRANCH_SET_PERSON -> BRANCH_SET_PERSON_DATE (many-to-many)
    layer = program.layers[1]
    assert isinstance(state, BranchSetPersonStateV1)
    dated: list[PersonDateBranchV1] = []
    selected_date_facts: list[TypedFactV1] = []
    for branch in state.branches:
        fact, refusal = _unique_typed_fact(
            memory, subject_id=branch.person_id,
            predicate=layer.predicate or "", subject_type=PERSON,
            object_type=DATE,
        )
        if refusal is not None:
            return _refuse(
                memory, program, static_payload, refusal, layer.layer_id,
            )
        assert fact is not None
        try:
            date.fromisoformat(fact.object_id)
        except ValueError:
            return _refuse(
                memory, program, static_payload, "INVALID_REDUCER_KEY",
                layer.layer_id,
            )
        selected_date_facts.append(fact)
        dated.append(PersonDateBranchV1(
            branch_id=branch.branch_id, person_id=branch.person_id,
            date_key=fact.object_id, expand_fact_id=branch.expand_fact_id,
            date_fact_id=fact.fact_id,
        ))
    after_dates = BranchSetPersonDateStateV1(tuple(dated))
    step = _make_step(
        depth=2, layer=layer, before=state, after=after_dates,
        query_payload={
            "branches": tuple(item.branch_id for item in state.branches),
            "predicate": layer.predicate, "required_value_type": DATE,
        },
        key_payload=tuple(_fact_key(fact) for fact in selected_date_facts),
        value_payload=tuple(asdict(item) for item in after_dates.branches),
        fact_ids=tuple(fact.fact_id for fact in selected_date_facts),
        evidence_facts=tuple(selected_date_facts),
        previous_step_sha256=previous,
    )
    steps.append(step)
    previous = step.step_sha256
    state = after_dates

    # Registered ablation: the real typed executor has completed EXPAND and
    # MAP_ONE, then branch IDs and Person-Date pairings are erased immediately
    # before reduction.  Query atomicity discards those successful internal
    # steps from the public refusal receipt; the reducer may not invent a
    # caller-order pairing between the remaining typed bags.
    if control == "BRANCH_ERASURE":
        erased = ErasedBranchSetPersonDateStateV1(
            date_keys=tuple(sorted(item.date_key for item in state.branches)),
            person_values=tuple(sorted(item.person_id for item in state.branches)),
        )
        selected, refusal, _pairs = _reduce_branch_state(
            erased, str(program.layers[2].reducer),
        )
        assert selected is None and refusal == "MISSING_BRANCH_ASSOCIATION"
        return _refuse(
            memory, program, static_payload, refusal,
            program.layers[2].layer_id, control=control,
            ablation_state=erased,
        )

    # 3. DATE Keys select the bound PERSON Value (many-to-one).
    layer = program.layers[2]
    assert isinstance(state, BranchSetPersonDateStateV1)
    reducer = str(layer.reducer)
    selected, refusal, reducer_pairs = _reduce_branch_state(state, reducer)
    if refusal is not None:
        return _refuse(
            memory, program, static_payload, refusal, layer.layer_id,
        )
    assert selected is not None
    step = _make_step(
        depth=3, layer=layer, before=state, after=selected,
        query_payload={
            "reducer": reducer,
            "required_key_type": DATE, "required_value_type": PERSON,
        },
        key_payload=tuple({
            "branch_id": item.branch_id, "date_key": item.date_key,
        } for item in state.branches),
        value_payload=tuple({
            "branch_id": item.branch_id, "person_value": item.person_id,
        } for item in state.branches),
        fact_ids=(), reducer_pairs=reducer_pairs,
        selected_branch_id=selected.branch_id,
        previous_step_sha256=previous,
    )
    steps.append(step)
    previous = step.step_sha256
    state = selected

    # 4. SELECTED_PERSON -> CITY (one-to-one)
    layer = program.layers[3]
    assert isinstance(state, SelectedPersonStateV1)
    birthplace, refusal = _unique_typed_fact(
        memory, subject_id=state.person_id, predicate=layer.predicate or "",
        subject_type=PERSON, object_type=CITY,
    )
    if refusal is not None:
        return _refuse(memory, program, static_payload, refusal, layer.layer_id)
    assert birthplace is not None
    city = CityStateV1(
        city_id=birthplace.object_id, birthplace_fact_id=birthplace.fact_id,
        selected_branch_id=state.branch_id,
    )
    step = _make_step(
        depth=4, layer=layer, before=state, after=city,
        query_payload={
            "selected_person": state.person_id,
            "predicate": layer.predicate, "required_value_type": CITY,
        },
        key_payload=_fact_key(birthplace),
        value_payload={
            "city_id": birthplace.object_id,
            "object_selector": asdict(birthplace.object_selector),
        },
        fact_ids=(birthplace.fact_id,), evidence_facts=(birthplace,),
        selected_branch_id=state.branch_id,
        previous_step_sha256=previous,
    )
    steps.append(step)

    final_payload = city.city_id.encode("utf-8")
    receipt = _seal_receipt(
        memory=memory, program=program, static_payload=static_payload,
        final_payload=final_payload, status="PASS", refusal_code=None,
        refusal_layer_id=None, terminal_type=CITY,
        terminal_value_id=city.city_id, steps=tuple(steps), control=control,
    )
    return final_payload, receipt


__all__ = [
    "BRANCH_SET_PERSON",
    "BRANCH_SET_PERSON_DATE", "BRANCH_SET_PERSON_DATE_ERASED", "CITY", "DATE",
    "PERSON", "SELECTED_PERSON",
    "BranchLineageV1", "ControlMode", "EvidenceFactReceiptV1", "ReducerPairV1",
    "ErasedBranchSetPersonDateStateV1", "SemanticIntegrityError",
    "SemanticLayerV1", "SemanticMemoryV1", "SemanticProgramV1",
    "SemanticRouteReceiptV1", "SemanticStepReceiptV1", "TypedFactV1",
    "execute_semantic_layers", "make_semantic_memory", "make_semantic_program",
]
