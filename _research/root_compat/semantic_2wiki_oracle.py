"""Development-only typed executor for 2Wiki comparison programs.

This module is deliberately an *evaluator-supplied-memory* probe.  The evidence
triples in the raw 2Wiki sidecar provide the facts and path shape.  Only the
reducer family is parsed from raw question text.  Consequently, a successful
run is an executor/ordering check, not an information-isolation or retrieval
result.

No file is opened at import time.  The CLI requires explicit raw-sidecar and
development-segment paths.  The answer field is rejected by
``compile_program``; :func:`run_development_probe` joins it only after the
terminal execution receipt has been sealed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Literal, Mapping, Sequence


SCHEMA_VERSION = "hswm-semantic-2wiki-oracle/v1"
RECEIPT_SCHEMA_VERSION = "hswm-semantic-2wiki-terminal-receipt/v1"
PROGRAM_SCHEMA_VERSION = "hswm-semantic-2wiki-program/v1"
ELIGIBLE_QTYPES = frozenset({"comparison", "bridge_comparison"})

Operator = Literal[
    "ARGMIN_DATE",
    "ARGMAX_DATE",
    "SET_OVERLAP_BOOL",
    "LIFESPAN_ARGMAX",
]
Control = Literal[
    "FULL",
    "REDUCER_INVERT",
    "VALUE_SWAP",
    "TYPE_ERASED",
    "RESOLVE_OFF",
    "BRANCH_ERASURE",
    "BRIDGE_ORDER_NULL",
    "TYPE_NULL",
    "EVIDENCE_NULL",
    "K1_TRUNCATE",
]

DATE_RELATIONS = frozenset({
    "date of birth", "date of death", "publication date", "inception",
})
COUNTRY_RELATIONS = frozenset({
    "country", "country of origin", "country of citizenship",
})

_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PAREN_RE = re.compile(r"\([^)]*\)")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_VALID_CONTROLS = frozenset({
    "FULL", "REDUCER_INVERT", "VALUE_SWAP", "TYPE_ERASED", "RESOLVE_OFF",
    "BRANCH_ERASURE", "BRIDGE_ORDER_NULL", "TYPE_NULL", "EVIDENCE_NULL",
    "K1_TRUNCATE",
})


class SemanticOracleError(ValueError):
    """Malformed evaluator memory or an unsupported semantic program."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nfkc(value: Any) -> str:
    return _SPACE_RE.sub(
        " ", unicodedata.normalize("NFKC", str(value)),
    ).strip()


def _label(value: Any) -> str:
    return _nfkc(value).casefold()


def _ascii_tokens(value: Any, *, strip_parenthetical: bool = False) -> tuple[str, ...]:
    text = str(value)
    if strip_parenthetical:
        text = _PAREN_RE.sub(" ", text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return tuple(_TOKEN_RE.findall(text))


def _lexical(value: Any) -> str:
    return " ".join(_ascii_tokens(value))


def _strict_entity(value: Any) -> str:
    """Exact resolver control: preserve punctuation, accents, and qualifiers."""

    return _label(value)


def _entity_tokens(value: Any) -> tuple[str, ...]:
    return _ascii_tokens(value, strip_parenthetical=True)


def _entities_alias(left: str, right: str) -> bool:
    """Conservative two-candidate resolver used by the development executor.

    It handles parenthetical disambiguators, punctuation/diacritic drift,
    extended suffix names, and initial-vs-full-name variants.  A match is never
    accepted unless it is unique among the current program's branches.
    """

    a, b = _entity_tokens(left), _entity_tokens(right)
    if not a or not b:
        return False
    if a == b or "".join(a) == "".join(b):
        return True
    set_a, set_b = set(a), set(b)
    if min(len(a), len(b)) >= 2 and (set_a <= set_b or set_b <= set_a):
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    cursor = 0
    for token in long:
        if cursor >= len(short):
            break
        wanted = short[cursor]
        compatible_initial = (
            token[:1] == wanted[:1] and (len(token) == 1 or len(wanted) == 1)
        )
        if token == wanted or compatible_initial:
            cursor += 1
    return cursor == len(short)


def _levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, 1):
        current = [row]
        for column, right_char in enumerate(right, 1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def _country_key(value: str) -> str:
    return "".join(_ascii_tokens(value))


def _country_equal(left: str, right: str, *, semantic: bool) -> bool:
    a, b = _country_key(left), _country_key(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return bool(
        semantic and min(len(a), len(b)) >= 5 and _levenshtein(a, b) <= 2
    )


def _require_text(row: Mapping[str, Any], key: str) -> str:
    if key not in row or not isinstance(row[key], str) or not _nfkc(row[key]):
        raise SemanticOracleError("MALFORMED_ROW", f"{key} must be non-empty text")
    return row[key]


def parse_operator(question: str) -> Operator:
    """Parse only the frozen reducer family from raw question text."""

    text = _label(question)
    matches: list[Operator] = []
    if re.search(r"\bsame\b", text):
        matches.append("SET_OVERLAP_BOOL")
    if re.search(r"\blonger\b", text):
        matches.append("LIFESPAN_ARGMAX")
    if re.search(r"\b(recent|recently|later|younger)\b", text):
        matches.append("ARGMAX_DATE")
    if re.search(r"\b(first|earlier|older)\b", text):
        matches.append("ARGMIN_DATE")
    if len(matches) != 1:
        code = "UNSUPPORTED_OPERATOR" if not matches else "AMBIGUOUS_OPERATOR"
        raise SemanticOracleError(
            code, f"question matched {len(matches)} frozen reducer families",
        )
    return matches[0]


@dataclass(frozen=True)
class EvidenceFactV1:
    fact_id: str
    subject: str
    predicate: str
    object: str
    object_type: Literal["Entity", "Date", "Country"]
    evidence_sha256: str


@dataclass(frozen=True)
class SemanticProgramV1:
    program_id: str
    qid: str
    compiler_input_sha256: str
    question_sha256: str
    operator: Operator
    facts: tuple[EvidenceFactV1, ...]


@dataclass(frozen=True)
class DateValueV1:
    raw: str
    iso_date: str
    ordinal: int
    precision: Literal["YEAR", "DAY"]
    fact_id: str


@dataclass(frozen=True)
class BranchV1:
    branch_id: str
    root_entity: str
    frontier_entity: str
    link_fact: EvidenceFactV1 | None
    property_facts: tuple[EvidenceFactV1, ...]
    lineage_sha256: str


def _fact_from_triple(triple: Any) -> EvidenceFactV1:
    if (
        not isinstance(triple, Sequence)
        or isinstance(triple, (str, bytes))
        or len(triple) != 3
        or any(not isinstance(item, str) or not _nfkc(item) for item in triple)
    ):
        raise SemanticOracleError(
            "MALFORMED_EVIDENCE", "each evidence must be a non-empty string triple",
        )
    subject, predicate, object_ = triple
    evidence_payload = {
        "dataset": "2wiki", "kind": "evaluator_triple",
        "subject": subject, "predicate": predicate, "object": object_,
    }
    evidence_sha256 = _digest(evidence_payload)
    return EvidenceFactV1(
        fact_id=f"evalfact:{evidence_sha256}",
        subject=subject,
        predicate=predicate,
        object=object_,
        object_type=_predicate_object_type(predicate),
        evidence_sha256=evidence_sha256,
    )


def _predicate_object_type(
    predicate: str,
) -> Literal["Entity", "Date", "Country"]:
    relation = _label(predicate)
    if relation in DATE_RELATIONS:
        return "Date"
    if relation in COUNTRY_RELATIONS:
        return "Country"
    return "Entity"


def _validate_fact(fact: EvidenceFactV1) -> None:
    evidence_payload = {
        "dataset": "2wiki", "kind": "evaluator_triple",
        "subject": fact.subject, "predicate": fact.predicate,
        "object": fact.object,
    }
    expected_sha256 = _digest(evidence_payload)
    if (
        fact.evidence_sha256 != expected_sha256
        or fact.fact_id != f"evalfact:{expected_sha256}"
    ):
        raise SemanticOracleError(
            "EVIDENCE_INTEGRITY", "fact digest or content ID drifted",
        )
    expected_type = _predicate_object_type(fact.predicate)
    if fact.object_type != expected_type:
        raise SemanticOracleError(
            "TYPE_MISMATCH",
            f"{fact.predicate!r} requires {expected_type}, got {fact.object_type}",
        )


def _program_id(program: SemanticProgramV1) -> str:
    facts = tuple(sorted(program.facts, key=lambda item: item.fact_id))
    payload = {
        "schema_version": PROGRAM_SCHEMA_VERSION,
        "qid": program.qid,
        "compiler_input_sha256": program.compiler_input_sha256,
        "question_sha256": program.question_sha256,
        "operator": program.operator,
        "facts": tuple(asdict(item) for item in facts),
    }
    return f"semantic-program:{_digest(payload)}"


def _replace_program_facts(
    program: SemanticProgramV1, facts: Sequence[EvidenceFactV1],
) -> SemanticProgramV1:
    changed = replace(program, facts=tuple(facts), program_id="pending")
    return replace(changed, program_id=_program_id(changed))


def compile_program(
    row_without_answer: Mapping[str, Any], *, compiler_input_sha256: str,
) -> SemanticProgramV1:
    """Compile evaluator facts while mechanically excluding the answer field."""

    if "answer" in row_without_answer:
        raise SemanticOracleError(
            "ANSWER_LEAKAGE", "compile_program rejects the answer field",
        )
    if not isinstance(compiler_input_sha256, str) or not _SHA256_RE.fullmatch(
        compiler_input_sha256
    ):
        raise SemanticOracleError(
            "INVALID_COMPILER_INPUT_HASH",
            "compiler_input_sha256 must be lowercase SHA-256",
        )
    qid = _nfkc(row_without_answer.get("id", row_without_answer.get("_id", "")))
    if not qid:
        raise SemanticOracleError("MALFORMED_ROW", "id or _id is required")
    question = _require_text(row_without_answer, "question")
    evidences = row_without_answer.get("evidences")
    if not isinstance(evidences, Sequence) or isinstance(evidences, (str, bytes)):
        raise SemanticOracleError("MALFORMED_EVIDENCE", "evidences must be triples")
    facts = tuple(sorted(
        (_fact_from_triple(item) for item in evidences),
        key=lambda item: item.fact_id,
    ))
    if len(facts) < 2 or len({item.fact_id for item in facts}) != len(facts):
        raise SemanticOracleError(
            "MALFORMED_EVIDENCE", "at least two unique evidence facts are required",
        )
    operator = parse_operator(question)
    payload = {
        "schema_version": PROGRAM_SCHEMA_VERSION,
        "qid": qid,
        "compiler_input_sha256": compiler_input_sha256,
        "question_sha256": sha256(question.encode("utf-8")).hexdigest(),
        "operator": operator,
        "facts": tuple(asdict(item) for item in facts),
    }
    return SemanticProgramV1(
        program_id=f"semantic-program:{_digest(payload)}",
        qid=qid,
        compiler_input_sha256=compiler_input_sha256,
        question_sha256=payload["question_sha256"],
        operator=operator,
        facts=facts,
    )


def _parse_date(fact: EvidenceFactV1) -> DateValueV1:
    if fact.object_type != "Date":
        raise SemanticOracleError(
            "TYPE_MISMATCH", "date parser requires a typed Date value",
        )
    raw = _nfkc(fact.object)
    parsed: date | None = None
    precision: Literal["YEAR", "DAY"] = "DAY"
    if re.fullmatch(r"\d{4}", raw):
        parsed = date(int(raw), 1, 1)
        precision = "YEAR"
    else:
        for fmt in ("%d %B %Y", "%B %d, %Y"):
            try:
                parsed = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
    if parsed is None:
        raise SemanticOracleError(
            "UNSUPPORTED_DATE", f"cannot parse date value {raw!r}",
        )
    return DateValueV1(
        raw=raw,
        iso_date=parsed.isoformat(),
        ordinal=parsed.toordinal(),
        precision=precision,
        fact_id=fact.fact_id,
    )


def _resolve_property_subject(
    subject: str, frontiers: Sequence[str], *, semantic: bool,
) -> int:
    if semantic:
        matches = [
            index for index, frontier in enumerate(frontiers)
            if _entities_alias(subject, frontier)
        ]
    else:
        matches = [
            index for index, frontier in enumerate(frontiers)
            if _strict_entity(subject) == _strict_entity(frontier)
        ]
    if len(matches) != 1:
        code = "AMBIGUOUS_ENTITY" if len(matches) > 1 else "UNRESOLVED_ENTITY"
        raise SemanticOracleError(
            code, f"property subject {subject!r} maps to {len(matches)} branches",
        )
    return matches[0]


def _make_branch(
    root: str,
    frontier: str,
    facts: Sequence[EvidenceFactV1],
    *,
    link_fact: EvidenceFactV1 | None = None,
) -> BranchV1:
    ordered = tuple(sorted(facts, key=lambda item: item.fact_id))
    if not ordered:
        raise SemanticOracleError("INCOMPLETE_BRANCH", "branch has no property facts")
    branch_payload = {
        "root_entity": root,
        "frontier_entity": frontier,
        "link_fact_id": None if link_fact is None else link_fact.fact_id,
        "property_fact_ids": tuple(item.fact_id for item in ordered),
    }
    branch_id = f"semantic-branch:{_digest({'root': root, 'frontier': frontier})}"
    return BranchV1(
        branch_id=branch_id,
        root_entity=root,
        frontier_entity=frontier,
        link_fact=link_fact,
        property_facts=ordered,
        lineage_sha256=_digest(branch_payload),
    )


def _build_branches(
    program: SemanticProgramV1, *, semantic_resolver: bool,
) -> tuple[str, tuple[BranchV1, ...]]:
    facts = tuple(sorted(program.facts, key=lambda item: item.fact_id))
    directors = tuple(item for item in facts if _label(item.predicate) == "director")
    properties = tuple(item for item in facts if _label(item.predicate) != "director")
    if directors:
        if len(directors) != 2 or not properties:
            raise SemanticOracleError(
                "MALFORMED_BRIDGE", "bridge needs exactly two director facts and properties",
            )
        director_rows = tuple(sorted(
            ((item.subject, item.object, item) for item in directors),
            key=lambda item: (_lexical(item[0]), item[2].fact_id),
        ))
        frontiers = tuple(item[1] for item in director_rows)
        if any(item[2].object_type != "Entity" for item in director_rows):
            raise SemanticOracleError(
                "TYPE_MISMATCH", "director link must produce an Entity",
            )
        assigned: list[list[EvidenceFactV1]] = [[], []]
        for fact in properties:
            assigned[_resolve_property_subject(
                fact.subject, frontiers, semantic=semantic_resolver,
            )].append(fact)
        branches = tuple(
            _make_branch(
                root, frontier, assigned[index], link_fact=director_fact,
            )
            for index, (root, frontier, director_fact) in enumerate(director_rows)
        )
        return "BRIDGE", tuple(sorted(branches, key=lambda item: item.branch_id))

    grouped: dict[str, list[EvidenceFactV1]] = {}
    display: dict[str, str] = {}
    for fact in properties:
        key = _strict_entity(fact.subject)
        grouped.setdefault(key, []).append(fact)
        display.setdefault(key, fact.subject)
    if len(grouped) != 2:
        raise SemanticOracleError(
            "MALFORMED_DIRECT", "direct comparison needs exactly two subjects",
        )
    branches = tuple(
        _make_branch(display[key], display[key], grouped[key]) for key in sorted(grouped)
    )
    return "DIRECT", tuple(sorted(branches, key=lambda item: item.branch_id))


def _swap_branch_values(branches: tuple[BranchV1, ...]) -> tuple[BranchV1, ...]:
    if len(branches) != 2:
        raise SemanticOracleError("INCOMPLETE_BRANCH", "value swap needs two branches")
    left, right = branches
    return (
        _make_branch(
            left.root_entity,
            left.frontier_entity,
            right.property_facts,
            link_fact=left.link_fact,
        ),
        _make_branch(
            right.root_entity,
            right.frontier_entity,
            left.property_facts,
            link_fact=right.link_fact,
        ),
    )


def _date_for_branch(branch: BranchV1) -> DateValueV1:
    date_facts = tuple(
        fact for fact in branch.property_facts if _label(fact.predicate) in DATE_RELATIONS
    )
    if len(date_facts) != 1:
        raise SemanticOracleError(
            "CARDINALITY_MISMATCH", "date selection needs exactly one date per branch",
        )
    return _parse_date(date_facts[0])


def _lifespan_for_branch(branch: BranchV1) -> tuple[int, tuple[DateValueV1, ...]]:
    by_relation: dict[str, list[EvidenceFactV1]] = {}
    for fact in branch.property_facts:
        by_relation.setdefault(_label(fact.predicate), []).append(fact)
    births = by_relation.get("date of birth", [])
    deaths = by_relation.get("date of death", [])
    if len(births) != 1 or len(deaths) != 1:
        raise SemanticOracleError(
            "CARDINALITY_MISMATCH", "lifespan needs one birth and one death",
        )
    birth, death = _parse_date(births[0]), _parse_date(deaths[0])
    duration = death.ordinal - birth.ordinal
    if duration <= 0:
        raise SemanticOracleError("INVALID_DURATION", "death must follow birth")
    return duration, (birth, death)


def _country_set(branch: BranchV1) -> tuple[str, ...]:
    values = tuple(sorted({
        fact.object for fact in branch.property_facts
        if _label(fact.predicate) in COUNTRY_RELATIONS
    }, key=_lexical))
    if not values:
        raise SemanticOracleError(
            "TYPE_MISMATCH", "set-overlap reducer needs country values",
        )
    if any(_label(fact.predicate) not in COUNTRY_RELATIONS for fact in branch.property_facts):
        raise SemanticOracleError(
            "TYPE_MISMATCH", "country branch contains a non-country property",
        )
    if any(fact.object_type != "Country" for fact in branch.property_facts):
        raise SemanticOracleError(
            "TYPE_MISMATCH", "country reducer requires typed Country values",
        )
    return values


def _reduce(
    operator: Operator,
    branches: tuple[BranchV1, ...],
    *,
    invert: bool,
    type_erased: bool,
) -> tuple[str, str, dict[str, Any]]:
    if len(branches) != 2:
        raise SemanticOracleError("INCOMPLETE_BRANCH", "reducer needs two branches")

    if operator in {"ARGMIN_DATE", "ARGMAX_DATE"}:
        if type_erased:
            keys = []
            for branch in branches:
                if len(branch.property_facts) != 1:
                    raise SemanticOracleError(
                        "TYPE_ERASED_UNSUPPORTED", "string reducer needs one scalar",
                    )
                keys.append(_lexical(branch.property_facts[0].object))
            key_receipts: list[Any] = keys
        else:
            dates = [_date_for_branch(branch) for branch in branches]
            keys = [item.ordinal for item in dates]
            key_receipts = [asdict(item) for item in dates]
        choose_max = operator == "ARGMAX_DATE"
        if invert:
            choose_max = not choose_max
        if keys[0] == keys[1]:
            raise SemanticOracleError("AMBIGUOUS_REDUCER", "date keys are tied")
        index = max(range(2), key=lambda item: keys[item]) if choose_max else min(
            range(2), key=lambda item: keys[item]
        )
        return branches[index].root_entity, "Entity", {
            "kind": "ARGMAX" if choose_max else "ARGMIN",
            "typed_keys": key_receipts,
            "selected_branch_id": branches[index].branch_id,
        }

    if operator == "LIFESPAN_ARGMAX":
        if type_erased:
            raise SemanticOracleError(
                "TYPE_ERASED_UNSUPPORTED", "strings cannot derive lifespan",
            )
        rows = [_lifespan_for_branch(branch) for branch in branches]
        keys = [item[0] for item in rows]
        if keys[0] == keys[1]:
            raise SemanticOracleError("AMBIGUOUS_REDUCER", "lifespans are tied")
        choose_max = not invert
        index = max(range(2), key=lambda item: keys[item]) if choose_max else min(
            range(2), key=lambda item: keys[item]
        )
        return branches[index].root_entity, "Entity", {
            "kind": "LIFESPAN_ARGMAX" if choose_max else "LIFESPAN_ARGMIN",
            "duration_days": keys,
            "date_inputs": [
                [asdict(value) for value in item[1]] for item in rows
            ],
            "selected_branch_id": branches[index].branch_id,
        }

    if operator == "SET_OVERLAP_BOOL":
        sets = [_country_set(branch) for branch in branches]
        semantic = not type_erased
        overlap = any(
            _country_equal(left, right, semantic=semantic)
            for left in sets[0] for right in sets[1]
        )
        if invert:
            overlap = not overlap
        return ("yes" if overlap else "no"), "Bool", {
            "kind": "SET_OVERLAP" if not invert else "SET_DISJOINT",
            "typed_keys": sets,
            "selected_branch_id": None,
        }

    raise SemanticOracleError("UNSUPPORTED_OPERATOR", str(operator))


def _seal_terminal(
    program: SemanticProgramV1,
    *,
    status: Literal["PASS", "REFUSED"],
    control: Control,
    refusal_code: str | None,
    refusal_detail: str | None,
    mode: str | None,
    output: str | None,
    output_type: str | None,
    branches: Sequence[BranchV1],
    operator_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    branch_rows = tuple(asdict(item) for item in branches) if status == "PASS" else ()
    evidence_ids = tuple(sorted({
        fact.fact_id for branch in branches for fact in branch.property_facts
    } | {
        branch.link_fact.fact_id
        for branch in branches if branch.link_fact is not None
    })) if status == "PASS" else ()
    layers: tuple[dict[str, Any], ...] = ()
    if status == "PASS":
        layers = (
            {"layer": "EVALUATOR_FACT_LOAD", "output_type": "EvidenceFactSet"},
            {"layer": "ENTITY_RESOLVE", "output_type": "BranchSet[Entity]"},
            {"layer": "TYPED_PROPERTY_MAP", "output_type": "BranchSet[TypedValue]"},
            {"layer": "TYPED_REDUCE", "output_type": output_type},
            {"layer": "EVIDENCE_BOUND_EMIT", "output_type": output_type},
        )
    payload: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "status": status,
        "control": control,
        "program_id": program.program_id,
        "qid": program.qid,
        "compiler_input_sha256": program.compiler_input_sha256,
        "operator": program.operator,
        "mode": mode,
        "output": output,
        "output_type": output_type,
        "refusal_code": refusal_code,
        "refusal_detail": refusal_detail,
        "layers": layers,
        "branches": branch_rows,
        "evidence_fact_ids": evidence_ids,
        "operator_receipt": dict(operator_receipt) if operator_receipt else None,
        "evaluator_supplied_memory": True,
        "answer_seen_by_executor": False,
        "research_only": True,
    }
    payload["receipt_sha256"] = _digest(payload)
    return payload


def execute_program(
    program: SemanticProgramV1, *, control: Control = "FULL",
) -> dict[str, Any]:
    """Execute one sanitized program and return a sealed terminal receipt."""

    if not isinstance(program, SemanticProgramV1):
        raise TypeError("program must be SemanticProgramV1")
    try:
        if control not in _VALID_CONTROLS:
            raise SemanticOracleError(
                "UNSUPPORTED_CONTROL", f"unknown control mode {control!r}",
            )
        if control in {"BRANCH_ERASURE", "K1_TRUNCATE"}:
            raise SemanticOracleError(control, f"registered {control} control")
        if program.program_id != _program_id(program):
            raise SemanticOracleError(
                "PROGRAM_INTEGRITY", "program ID does not bind canonical facts",
            )
        effective = program
        if control == "TYPE_NULL":
            candidates = tuple(
                index for index, fact in enumerate(program.facts)
                if _label(fact.predicate) != "director"
            )
            if not candidates:
                raise SemanticOracleError(
                    "TYPE_MISMATCH", "type mutation has no property fact",
                )
            index = candidates[0]
            rows = list(program.facts)
            original = rows[index]
            wrong_type = "Country" if original.object_type != "Country" else "Date"
            rows[index] = replace(original, object_type=wrong_type)
            effective = _replace_program_facts(program, rows)
        elif control == "EVIDENCE_NULL":
            rows = list(program.facts)
            rows[0] = replace(rows[0], evidence_sha256="0" * 64)
            effective = _replace_program_facts(program, rows)
        for fact in effective.facts:
            _validate_fact(fact)
        semantic_resolver = control != "RESOLVE_OFF"
        mode, branches = _build_branches(
            effective, semantic_resolver=semantic_resolver,
        )
        if control == "BRIDGE_ORDER_NULL" and mode == "BRIDGE":
            raise SemanticOracleError(
                "LAYER_ORDER_MISMATCH", "property map preceded director resolution",
            )
        if control == "VALUE_SWAP":
            branches = _swap_branch_values(branches)
        output, output_type, operator_receipt = _reduce(
            program.operator,
            branches,
            invert=control == "REDUCER_INVERT",
            type_erased=control == "TYPE_ERASED",
        )
        return _seal_terminal(
            effective,
            status="PASS",
            control=control,
            refusal_code=None,
            refusal_detail=None,
            mode=mode,
            output=output,
            output_type=output_type,
            branches=branches,
            operator_receipt=operator_receipt,
        )
    except SemanticOracleError as exc:
        return _seal_terminal(
            effective if "effective" in locals() else program,
            status="REFUSED",
            control=control,
            refusal_code=exc.code,
            refusal_detail=exc.detail,
            mode=None,
            output=None,
            output_type=None,
            branches=(),
            operator_receipt=None,
        )


def _answer_equal(left: str | None, right: str) -> bool:
    return left is not None and _lexical(left) == _lexical(right)


def _metric_row(receipt: Mapping[str, Any], answer: str) -> dict[str, Any]:
    # This function is intentionally called only after receipt_sha256 exists.
    if "receipt_sha256" not in receipt:
        raise RuntimeError("answer cannot be joined before terminal receipt seal")
    return {
        "terminal_receipt_sha256": receipt["receipt_sha256"],
        "supported": receipt["status"] == "PASS",
        "exact": receipt["status"] == "PASS" and _answer_equal(
            receipt.get("output"), answer,
        ),
    }


def _summarize_control(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "n": len(rows),
        "supported": sum(bool(item["supported"]) for item in rows),
        "refused": sum(not bool(item["supported"]) for item in rows),
        "exact": sum(bool(item["exact"]) for item in rows),
    }


def run_development_probe(
    *, raw_sidecar_path: str | Path, development_segment_path: str | Path,
) -> dict[str, Any]:
    """Run the finite development-only 2Wiki comparison executor probe."""

    raw_path = Path(raw_sidecar_path)
    segment_path = Path(development_segment_path)
    raw_wrapper = json.loads(raw_path.read_text(encoding="utf-8"))
    segment = json.loads(segment_path.read_text(encoding="utf-8"))
    rows = raw_wrapper.get("rows")
    if raw_wrapper.get("dataset") != "2wiki" or not isinstance(rows, list):
        raise SemanticOracleError("WRONG_DATASET", "raw sidecar must be 2wiki rows")
    expected_rows_sha = _digest(rows)
    if raw_wrapper.get("rows_sha256") != expected_rows_sha:
        raise SemanticOracleError("RAW_HASH_MISMATCH", "rows_sha256 does not match rows")
    if segment.get("dataset") != "2wiki" or segment.get("split") != "development":
        raise SemanticOracleError(
            "WRONG_SEGMENT", "only the 2wiki development segment is accepted",
        )
    evaluation_rows = segment.get("evaluation_rows")
    if not isinstance(evaluation_rows, list):
        raise SemanticOracleError("WRONG_SEGMENT", "evaluation_rows must be a list")
    qids = tuple(_nfkc(item.get("qid", "")) for item in evaluation_rows)
    if any(not qid for qid in qids) or len(qids) != len(set(qids)):
        raise SemanticOracleError("WRONG_SEGMENT", "segment qids must be unique")
    by_qid: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise SemanticOracleError("MALFORMED_ROW", "raw row must be a mapping")
        qid = _nfkc(row.get("id", row.get("_id", "")))
        if not qid or qid in by_qid:
            raise SemanticOracleError("MALFORMED_ROW", "raw qids must be unique")
        by_qid[qid] = row

    bindings: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
    terminal_rows: list[dict[str, Any]] = []
    metrics_by_control: dict[str, list[dict[str, Any]]] = {
        name: [] for name in (
            "FULL", "REDUCER_INVERT", "VALUE_SWAP", "TYPE_ERASED",
            "RESOLVE_OFF", "BRANCH_ERASURE", "BRIDGE_ORDER_NULL",
            "TYPE_NULL", "EVIDENCE_NULL", "K1_TRUNCATE",
        )
    }
    operators: dict[str, int] = {}
    qtypes: dict[str, int] = {}
    deterministic_repeat = 0
    deterministic_reverse = 0
    ordered_value_swap: list[dict[str, Any]] = []
    equality_value_swap: list[dict[str, Any]] = []
    bridge_order_rows: list[dict[str, Any]] = []

    for qid in qids:
        if qid not in by_qid:
            raise SemanticOracleError("MISSING_QID", f"raw sidecar lacks {qid}")
        row = by_qid[qid]
        qtype = _label(row.get("type", ""))
        if qtype not in ELIGIBLE_QTYPES:
            raw_row_sha = _digest(row)
            exclusions.append({
                "qid": qid,
                "raw_row_sha256": raw_row_sha,
                "reason": f"UNSUPPORTED_QTYPE_{qtype.upper() or 'MISSING'}",
            })
            continue
        qtypes[qtype] = qtypes.get(qtype, 0) + 1
        sanitized = {
            "id": qid,
            "question": row.get("question"),
            "evidences": row.get("evidences"),
        }
        program = compile_program(
            sanitized, compiler_input_sha256=_digest(sanitized),
        )
        operators[program.operator] = operators.get(program.operator, 0) + 1

        receipts = {
            control: execute_program(program, control=control)  # type: ignore[arg-type]
            for control in metrics_by_control
        }
        repeated = execute_program(program)
        reversed_program = replace(program, facts=tuple(reversed(program.facts)))
        reversed_receipt = execute_program(reversed_program)
        deterministic_repeat += int(repeated == receipts["FULL"])
        deterministic_reverse += int(reversed_receipt == receipts["FULL"])

        # The answer is first accessed after every terminal receipt above has
        # already been sealed.  This is an ordering check, not information
        # isolation: the evaluator evidences supplied the complete fact memory.
        answer = _require_text(row, "answer")
        raw_row_sha = _digest(row)
        bindings.append({"qid": qid, "raw_row_sha256": raw_row_sha})
        scored = {
            control: _metric_row(receipt, answer)
            for control, receipt in receipts.items()
        }
        for control, metric in scored.items():
            metrics_by_control[control].append(metric)
        if program.operator == "SET_OVERLAP_BOOL":
            equality_value_swap.append(scored["VALUE_SWAP"])
        else:
            ordered_value_swap.append(scored["VALUE_SWAP"])
        if qtype == "bridge_comparison":
            bridge_order_rows.append(scored["BRIDGE_ORDER_NULL"])
        terminal_rows.append({
            "qid": qid,
            "raw_row_sha256": raw_row_sha,
            "qtype": qtype,
            "operator": program.operator,
            "program_id": program.program_id,
            "terminal_receipt_sha256": receipts["FULL"]["receipt_sha256"],
            "full_supported": scored["FULL"]["supported"],
            "full_exact": scored["FULL"]["exact"],
        })

    bindings.sort(key=lambda item: item["qid"])
    exclusions.sort(key=lambda item: item["qid"])
    terminal_rows.sort(key=lambda item: item["qid"])
    controls = {
        name: _summarize_control(rows_) for name, rows_ in metrics_by_control.items()
    }
    controls["VALUE_SWAP_ORDERED_ONLY"] = _summarize_control(ordered_value_swap)
    controls["VALUE_SWAP_EQUALITY_ONLY"] = _summarize_control(equality_value_swap)
    controls["BRIDGE_ORDER_NULL_BRIDGE_ONLY"] = _summarize_control(bridge_order_rows)
    primary_by_operator = {
        operator: {
            "n": len(selected),
            "supported": sum(bool(item["full_supported"]) for item in selected),
            "refused": sum(not bool(item["full_supported"]) for item in selected),
            "exact": sum(bool(item["full_exact"]) for item in selected),
        }
        for operator in sorted(operators)
        for selected in [[
            item for item in terminal_rows if item["operator"] == operator
        ]]
    }
    primary_by_qtype = {
        qtype: {
            "n": len(selected),
            "supported": sum(bool(item["full_supported"]) for item in selected),
            "refused": sum(not bool(item["full_supported"]) for item in selected),
            "exact": sum(bool(item["full_exact"]) for item in selected),
        }
        for qtype in sorted(qtypes)
        for selected in [[
            item for item in terminal_rows if item["qtype"] == qtype
        ]]
    }

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "DEVELOPMENT_EXECUTOR_COVERAGE_PROBE",
        "scope": "2wiki_development_comparison_and_bridge_comparison_only",
        "boundary": {
            "memory_source": "evaluator_supplied_evidence_triples",
            "reducer_source": "raw_question_text_frozen_keyword_parser",
            "answer_join": "after_terminal_receipt_seal",
            "answer_join_claim": "ordering_check_only_not_information_isolation",
            "cohort_seal": (
                "selected_and_sealed_in_same_development_run_not_independent_prereg"
            ),
            "runtime_kernel": (
                "bespoke_2wiki_executor_not_semantic_layer_routing_core"
            ),
            "evidence_binding": (
                "evaluator_triple_content_hash_not_exact_source_selector"
            ),
            "control_semantics": {
                "TYPE_NULL": "actual required-property type-tag mutation",
                "EVIDENCE_NULL": "actual evidence-digest mutation",
                "BRANCH_ERASURE": "registered deliberate state ablation",
                "K1_TRUNCATE": "registered deliberate early-reduce ablation",
            },
            "allowed_claim": "typed executor coverage over evaluator-supplied memory",
            "forbidden_claims": [
                "raw-language program induction",
                "retrieval uplift",
                "HSWM reasoning uplift",
                "information isolation",
                "fresh confirmatory evidence",
            ],
        },
        "inputs": {
            "raw_sidecar_path": str(raw_path),
            "raw_sidecar_sha256": _file_sha256(raw_path),
            "raw_rows_sha256": expected_rows_sha,
            "development_segment_path": str(segment_path),
            "development_segment_sha256": _file_sha256(segment_path),
        },
        "cohort": {
            "segment_qids": len(qids),
            "eligible": len(bindings),
            "excluded": len(exclusions),
            "qtype_counts": dict(sorted(qtypes.items())),
            "operator_counts": dict(sorted(operators.items())),
            "bindings": bindings,
            "bindings_sha256": _digest(bindings),
            "exclusions": exclusions,
            "exclusions_sha256": _digest(exclusions),
            "exclusion_reason_counts": {
                reason: sum(item["reason"] == reason for item in exclusions)
                for reason in sorted({item["reason"] for item in exclusions})
            },
        },
        "primary": controls["FULL"],
        "full_development_refusal_counted": {
            "n": len(qids),
            "supported": controls["FULL"]["supported"],
            "refused": len(exclusions) + controls["FULL"]["refused"],
            "exact": controls["FULL"]["exact"],
            "exact_rate": controls["FULL"]["exact"] / len(qids),
        },
        "primary_by_operator": primary_by_operator,
        "primary_by_qtype": primary_by_qtype,
        "controls": controls,
        "determinism": {
            "n": len(bindings),
            "repeat_bit_identical": deterministic_repeat,
            "reverse_fact_order_bit_identical": deterministic_reverse,
        },
        "terminal_bindings": terminal_rows,
        "terminal_bindings_sha256": _digest(terminal_rows),
        "source_bindings": {
            "SEMANTIC_QKV_EXPERIMENT_PLAN_2026-07-20.md": _file_sha256(
                Path(__file__).resolve().parent
                / "SEMANTIC_QKV_EXPERIMENT_PLAN_2026-07-20.md"
            ),
            "semantic_2wiki_oracle.py": _file_sha256(Path(__file__).resolve()),
        },
        "research_only": True,
    }
    result["result_sha256"] = _digest(result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, help="2Wiki raw relation sidecar JSON")
    parser.add_argument(
        "--segment", required=True, help="2Wiki development-v4 segment JSON",
    )
    parser.add_argument("--out", required=True, help="output receipt JSON")
    args = parser.parse_args(argv)
    result = run_development_probe(
        raw_sidecar_path=args.raw,
        development_segment_path=args.segment,
    )
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "eligible": result["cohort"]["eligible"],
        "exact": result["primary"]["exact"],
        "result_sha256": result["result_sha256"],
        "out": args.out,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EvidenceFactV1",
    "SemanticOracleError",
    "SemanticProgramV1",
    "compile_program",
    "execute_program",
    "parse_operator",
    "run_development_probe",
]
