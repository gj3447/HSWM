"""Leakage-safe relation/composition evaluation metadata for HSWM.

This module is deliberately an *evaluation sidecar*.  It recovers reasoning
labels supplied by MuSiQue (``question_decomposition``) and 2WikiMultihopQA
(``evidences``), but none of those records is a compiler input.  Builder and
compiler call sites should run :func:`assert_compiler_payload_clean` before
accepting an untyped payload.

There is no network loader here.  Callers must acquire and freeze raw rows
outside the compiler, then pass them to :func:`build_relation_evaluation_suite`.
The suite binds the exact ordered raw snapshot with SHA-256.  All normalization,
grouping, and splitting below is pure and deterministic.

Dataset references (schema only):
* MuSiQue ``question_decomposition`` supplies subquestion, answer, dependency,
  and supporting-paragraph metadata.
* 2WikiMultihopQA ``evidences`` is an ordered list of
  ``[subject, relation, object]`` triples.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from hashlib import sha256
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from world_ir import canonical_json, content_id


SCHEMA_VERSION = "hswm-relation-eval/v1"
SUPPORTED_DATASETS = frozenset({"musique", "2wiki"})

# These keys carry answer/evaluation supervision and must never cross the
# compiler boundary.  The first six are the minimum contract; the remainder
# cover aliases and dataset-specific spellings seen in the same raw records.
FORBIDDEN_COMPILER_KEYS = frozenset({
    "question",
    "answer",
    "is_supporting",
    "hop",
    "evidences",
    "question_decomposition",
    "answer_aliases",
    "golden_answers",
    "supporting_facts",
    "evidences_id",
    "answer_id",
    "paragraph_support_idx",
    "support_paragraph",
    "gold",
    "gold_target_ids",
})

_SPACE_RE = re.compile(r"\s+")
_DEPENDENCY_RE = re.compile(r"#\s*(\d+)")


class RelationEvaluationError(ValueError):
    """A malformed or unsupported raw evaluation record."""


class EvaluationLabelLeakageError(RelationEvaluationError):
    """Evaluation-only fields were found in a compiler-facing payload."""

    def __init__(self, paths: tuple[str, ...]):
        self.paths = paths
        super().__init__(
            "evaluation-only keys in compiler payload: " + ", ".join(paths)
        )


@dataclass(frozen=True)
class RelationStepV1:
    """One gold composition step, available only to the evaluator."""

    ordinal: int
    step_id: str
    question: str
    answer: str
    dependencies: tuple[str, ...]
    subject: str
    relation: str
    object: str
    relation_template: str
    evidence_content_ids: tuple[str, ...]


@dataclass(frozen=True)
class RelationExampleV1:
    """Normalized QA and relation labels for one dataset occurrence."""

    occurrence_id: str
    qid: str
    dataset: str
    question: str
    answer: str
    hop: int
    steps: tuple[RelationStepV1, ...]
    relation_chain: tuple[str, ...]
    relation_chain_id: str
    relation_template_id: str
    evidence_content_ids: tuple[str, ...]
    raw_row_sha256: str


@dataclass(frozen=True)
class SplitAssignmentV1:
    occurrence_id: str
    split: str
    component_id: str


@dataclass(frozen=True)
class RelationEvaluationSuiteV1:
    """Immutable relation-label sidecar bound to one raw-row snapshot."""

    schema_version: str
    suite_id: str
    dataset: str
    raw_snapshot_sha256: str
    split_spec: tuple[tuple[str, float], ...]
    split_seed: int
    examples: tuple[RelationExampleV1, ...]
    assignments: tuple[SplitAssignmentV1, ...]

    def split_for(self, occurrence_id: str) -> str:
        for assignment in self.assignments:
            if assignment.occurrence_id == occurrence_id:
                return assignment.split
        raise KeyError(occurrence_id)


def _norm_text(value: Any) -> str:
    return _SPACE_RE.sub(" ", unicodedata.normalize("NFKC", str(value))).strip()


def _norm_label(value: Any) -> str:
    return _norm_text(value).casefold()


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RelationEvaluationError(f"{path} must be a mapping")
    return value


def _require_text(row: Mapping[str, Any], key: str, path: str,
                  *, allow_empty: bool = False) -> str:
    if key not in row:
        raise RelationEvaluationError(f"{path}.{key} is required")
    value = _norm_text(row[key])
    if not value and not allow_empty:
        raise RelationEvaluationError(f"{path}.{key} must not be empty")
    return value


def _require_raw_text(row: Mapping[str, Any], key: str, path: str) -> str:
    """Validate text without rewriting bytes used for evidence identity."""
    if key not in row or not isinstance(row[key], str):
        raise RelationEvaluationError(f"{path}.{key} must be a string")
    value = row[key]
    if not _norm_text(value):
        raise RelationEvaluationError(f"{path}.{key} must not be empty")
    return value


def _as_records(value: Any, path: str) -> list[dict[str, Any]]:
    """Accept both JSON record lists and HF struct-of-lists encodings."""
    if isinstance(value, Mapping):
        columns = {str(key): val for key, val in value.items()}
        lengths = {
            len(val) for val in columns.values()
            if isinstance(val, Sequence) and not isinstance(val, (str, bytes))
        }
        if not lengths:
            return [dict(columns)]
        if len(lengths) != 1 or any(
            not isinstance(val, Sequence) or isinstance(val, (str, bytes))
            for val in columns.values()
        ):
            raise RelationEvaluationError(f"{path} columns must have equal lengths")
        length = next(iter(lengths))
        return [{key: val[index] for key, val in columns.items()} for index in range(length)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        records: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            records.append(dict(_require_mapping(item, f"{path}[{index}]")))
        return records
    raise RelationEvaluationError(f"{path} must be a record list or struct-of-lists")


def _paragraph_records(value: Any, path: str) -> list[dict[str, Any]]:
    records = _as_records(value, path)
    out: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        title = _require_raw_text(record, "title", f"{path}[{index}]")
        text_key = "paragraph_text" if "paragraph_text" in record else "text"
        text = _require_raw_text(record, text_key, f"{path}[{index}]")
        out.append({**record, "title": title, "paragraph_text": text})
    return out


def _paragraph_content_id(dataset: str, title: str,
                          text: str | tuple[str, ...]) -> str:
    # Exact evidence identity: no case folding or whitespace rewriting occurs
    # after the raw strings have passed the schema-level text check.
    return content_id("eval_evidence", {
        "dataset": dataset,
        "kind": "paragraph",
        "title": title,
        "text": text,
    })


def _triple_content_id(subject: str, relation: str, object_: str) -> str:
    return content_id("eval_evidence", {
        "dataset": "2wiki",
        "kind": "triple",
        "subject": subject,
        "relation": relation,
        "object": object_,
    })


def _row_digest(row: Mapping[str, Any]) -> str:
    return sha256(canonical_json(row).encode("utf-8")).hexdigest()


def _occurrence_id(dataset: str, qid: str, row_digest: str) -> str:
    return content_id("eval_occurrence", {
        "dataset": dataset,
        "qid": qid,
        "raw_row_sha256": row_digest,
    })


def _redact_entities(text: str, values: set[str]) -> str:
    normalized = _norm_label(text)
    normalized = _DEPENDENCY_RE.sub("<dep>", normalized)
    # Longest first prevents a short alias from partially consuming a longer
    # entity label.  Escaped literal replacement avoids regex interpretation.
    for value in sorted({_norm_label(v) for v in values if _norm_label(v)},
                        key=lambda item: (-len(item), item)):
        normalized = re.sub(re.escape(value), "<entity>", normalized,
                            flags=re.IGNORECASE)
    return _SPACE_RE.sub(" ", normalized).strip()


def _musique_relation_template(question: str, redactions: set[str]) -> str:
    """Variableize MuSiQue's native ``subject >> relation`` notation.

    Some converted fixtures expose natural-language subquestions instead; the
    generic redactor remains a deterministic fallback for those records.
    """
    if ">>" not in question:
        return _redact_entities(question, redactions)
    subject, relation = question.split(">>", 1)
    marker = "<dep>" if _DEPENDENCY_RE.search(subject) else "<entity>"
    relation = _redact_entities(relation, redactions)
    if not relation:
        raise RelationEvaluationError("MuSiQue relation after '>>' must not be empty")
    return f"{marker} >> {relation}"


def _musique_support(step: Mapping[str, Any], paragraphs: list[dict[str, Any]],
                     path: str) -> tuple[str, str]:
    support = step.get("support_paragraph")
    if isinstance(support, Mapping):
        title = _require_raw_text(support, "title", f"{path}.support_paragraph")
        text_key = "paragraph_text" if "paragraph_text" in support else "text"
        text = _require_raw_text(support, text_key, f"{path}.support_paragraph")
        return title, text
    if "paragraph_support_idx" not in step:
        raise RelationEvaluationError(
            f"{path} needs support_paragraph or paragraph_support_idx"
        )
    try:
        support_idx = int(step["paragraph_support_idx"])
    except (TypeError, ValueError) as exc:
        raise RelationEvaluationError(f"{path}.paragraph_support_idx must be an int") from exc
    by_idx: dict[int, dict[str, Any]] = {}
    for ordinal, paragraph in enumerate(paragraphs):
        try:
            idx = int(paragraph.get("idx", ordinal))
        except (TypeError, ValueError) as exc:
            raise RelationEvaluationError(f"paragraphs[{ordinal}].idx must be an int") from exc
        by_idx[idx] = paragraph
    if support_idx not in by_idx:
        raise RelationEvaluationError(
            f"{path}.paragraph_support_idx={support_idx} has no paragraph"
        )
    paragraph = by_idx[support_idx]
    return str(paragraph["title"]), str(paragraph["paragraph_text"])


def normalize_musique_row(row: Mapping[str, Any]) -> RelationExampleV1:
    """Recover MuSiQue dependency-chain labels without exposing them to build."""
    row = _require_mapping(row, "row")
    qid = _norm_text(row.get("id", row.get("_id", "")))
    if not qid:
        raise RelationEvaluationError("row.id is required")
    question = _require_text(row, "question", "row")
    answer = _require_text(row, "answer", "row")
    raw_steps = _as_records(row.get("question_decomposition"),
                            "row.question_decomposition")
    if not raw_steps:
        raise RelationEvaluationError("row.question_decomposition must not be empty")
    paragraphs = _paragraph_records(row.get("paragraphs", ()), "row.paragraphs") \
        if row.get("paragraphs") is not None else []

    prepared: list[tuple[dict[str, Any], str, str, str, str]] = []
    redactions = {answer}
    for ordinal, raw_step in enumerate(raw_steps):
        path = f"row.question_decomposition[{ordinal}]"
        step_question = _require_text(raw_step, "question", path)
        step_answer = _require_text(raw_step, "answer", path)
        title, paragraph_text = _musique_support(raw_step, paragraphs, path)
        prepared.append((raw_step, step_question, step_answer, title, paragraph_text))
        redactions.update((step_answer, title))

    step_ids = tuple(_norm_text(raw_step.get("id", ordinal + 1))
                     for ordinal, (raw_step, *_rest) in enumerate(prepared))
    if any(not step_id for step_id in step_ids):
        raise RelationEvaluationError("MuSiQue step ids must not be empty")
    if len(set(step_ids)) != len(step_ids):
        raise RelationEvaluationError("MuSiQue step ids must be unique")
    step_position = {step_id: ordinal for ordinal, step_id in enumerate(step_ids)}

    steps: list[RelationStepV1] = []
    for ordinal, (raw_step, step_question, step_answer, title, paragraph_text) in enumerate(prepared):
        step_id = step_ids[ordinal]
        dependencies_list: list[str] = []
        for match in _DEPENDENCY_RE.finditer(step_question):
            reference = int(match.group(1))
            # MuSiQue #N is a one-based decomposition *position*, not the raw
            # (often six-digit) step id.  An out-of-range reference may still
            # name a raw id in a converted dataset, which we accept explicitly.
            if 1 <= reference <= len(step_ids):
                dependency_id = step_ids[reference - 1]
            elif match.group(1) in step_position:
                dependency_id = match.group(1)
            else:
                raise RelationEvaluationError(
                    f"MuSiQue step {step_id!r} references unknown step #{reference}"
                )
            if dependency_id not in dependencies_list:
                dependencies_list.append(dependency_id)
        dependencies = tuple(dependencies_list)
        evidence_id = _paragraph_content_id("musique", title, paragraph_text)
        relation_template = _musique_relation_template(step_question, redactions)
        steps.append(RelationStepV1(
            ordinal=ordinal,
            step_id=step_id,
            question=step_question,
            answer=step_answer,
            dependencies=dependencies,
            subject="",
            relation=relation_template,
            object=step_answer,
            relation_template=relation_template,
            evidence_content_ids=(evidence_id,),
        ))

    for step in steps:
        if any(step_position[dependency] >= step.ordinal for dependency in step.dependencies):
            raise RelationEvaluationError(
                f"MuSiQue step {step.step_id!r} has a forward/cyclic dependency"
            )

    relation_chain = tuple(step.relation_template for step in steps)
    topology = tuple(
        (step.ordinal, tuple(step_position[dep] for dep in step.dependencies),
         step.relation_template)
        for step in steps
    )
    chain_id = content_id("relation_chain", {
        "dataset": "musique", "relations": relation_chain,
    })
    template_id = content_id("relation_template", {
        "dataset": "musique", "topology": topology,
    })
    digest = _row_digest(row)
    evidence_ids = tuple(sorted({eid for step in steps for eid in step.evidence_content_ids}))
    return RelationExampleV1(
        occurrence_id=_occurrence_id("musique", qid, digest),
        qid=qid,
        dataset="musique",
        question=question,
        answer=answer,
        hop=len(steps),
        steps=tuple(steps),
        relation_chain=relation_chain,
        relation_chain_id=chain_id,
        relation_template_id=template_id,
        evidence_content_ids=evidence_ids,
        raw_row_sha256=digest,
    )


def _evidence_triples(value: Any, path: str) -> list[tuple[str, str, str]]:
    if isinstance(value, Mapping):
        subject_key = next((key for key in ("subject", "subject_entity", "fact")
                            if key in value), None)
        relation_key = next((key for key in ("relation", "predicate") if key in value), None)
        object_key = next((key for key in ("object", "object_entity", "entity")
                           if key in value), None)
        if subject_key is None or relation_key is None or object_key is None:
            raise RelationEvaluationError(
                f"{path} needs subject/fact, relation/predicate, and object/entity columns"
            )
        columns = (value[subject_key], value[relation_key], value[object_key])
        if any(not isinstance(column, Sequence) or isinstance(column, (str, bytes))
               for column in columns):
            raise RelationEvaluationError(f"{path} columns must be sequences")
        if len({len(column) for column in columns}) != 1:
            raise RelationEvaluationError(f"{path} columns must have equal lengths")
        candidates = list(zip(*columns, strict=True))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        candidates = list(value)
    else:
        raise RelationEvaluationError(f"{path} must be triples or a struct-of-lists")

    triples: list[tuple[str, str, str]] = []
    for index, candidate in enumerate(candidates):
        if (not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes))
                or len(candidate) != 3):
            raise RelationEvaluationError(f"{path}[{index}] must be a 3-item sequence")
        if any(not isinstance(item, str) or not _norm_text(item) for item in candidate):
            raise RelationEvaluationError(f"{path}[{index}] must contain non-empty strings")
        triple = tuple(candidate)
        triples.append((triple[0], triple[1], triple[2]))
    if not triples:
        raise RelationEvaluationError(f"{path} must not be empty")
    return triples


def _context_paragraphs(value: Any) -> list[tuple[str, tuple[str, ...]]]:
    if isinstance(value, Mapping):
        titles = value.get("title")
        sentences = value.get("sentences")
        if (not isinstance(titles, Sequence) or isinstance(titles, (str, bytes))
                or not isinstance(sentences, Sequence) or isinstance(sentences, (str, bytes))
                or len(titles) != len(sentences)):
            raise RelationEvaluationError("row.context title/sentences columns must align")
        candidates = zip(titles, sentences, strict=True)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        candidates = value
    else:
        raise RelationEvaluationError("row.context must be pairs or a struct-of-lists")
    out: list[tuple[str, tuple[str, ...]]] = []
    for index, candidate in enumerate(candidates):
        if (not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes))
                or len(candidate) != 2):
            raise RelationEvaluationError(f"row.context[{index}] must be [title, sentences]")
        if not isinstance(candidate[0], str) or not _norm_text(candidate[0]):
            raise RelationEvaluationError(f"row.context[{index}].title must be non-empty text")
        title = candidate[0]
        sentence_value = candidate[1]
        if (not isinstance(sentence_value, Sequence)
                or isinstance(sentence_value, (str, bytes))):
            raise RelationEvaluationError(f"row.context[{index}].sentences must be a sequence")
        if any(not isinstance(sentence, str) or not _norm_text(sentence)
               for sentence in sentence_value):
            raise RelationEvaluationError(f"row.context[{index}] contains empty text")
        sentences = tuple(sentence_value)
        if not sentences:
            raise RelationEvaluationError(f"row.context[{index}] contains empty text")
        out.append((title, sentences))
    return out


def _supporting_titles(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        titles = value.get("title")
        if not isinstance(titles, Sequence) or isinstance(titles, (str, bytes)):
            raise RelationEvaluationError("row.supporting_facts.title must be a sequence")
        if any(not isinstance(title, str) or not _norm_text(title) for title in titles):
            raise RelationEvaluationError("row.supporting_facts.title contains empty text")
        return set(titles)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        out: set[str] = set()
        for index, candidate in enumerate(value):
            if (not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes))
                    or len(candidate) < 1):
                raise RelationEvaluationError(
                    f"row.supporting_facts[{index}] must start with a title"
                )
            if not isinstance(candidate[0], str) or not _norm_text(candidate[0]):
                raise RelationEvaluationError(
                    f"row.supporting_facts[{index}] title must be non-empty text"
                )
            out.add(candidate[0])
        return out
    raise RelationEvaluationError("row.supporting_facts must be pairs or a struct-of-lists")


def normalize_2wiki_row(row: Mapping[str, Any]) -> RelationExampleV1:
    """Recover the ordered 2Wiki evidence path and its variableized template."""
    row = _require_mapping(row, "row")
    qid = _norm_text(row.get("_id", row.get("id", "")))
    if not qid:
        raise RelationEvaluationError("row._id or row.id is required")
    question = _require_text(row, "question", "row")
    answer = _require_text(row, "answer", "row")
    qtype = _norm_label(row.get("type", "unspecified")) or "unspecified"
    triples = _evidence_triples(row.get("evidences"), "row.evidences")

    evidence_ids: set[str] = set()
    if "context" in row and "supporting_facts" in row:
        contexts = _context_paragraphs(row["context"])
        support_titles = _supporting_titles(row["supporting_facts"])
        available_titles = {title for title, _ in contexts}
        missing = support_titles - available_titles
        if missing:
            raise RelationEvaluationError(
                f"supporting_facts titles missing from context: {sorted(missing)}"
            )
        for title, sentences in contexts:
            if title in support_titles:
                evidence_ids.add(_paragraph_content_id("2wiki", title, sentences))

    variable_for: dict[str, str] = {}

    def variable(entity: str) -> str:
        key = _norm_label(entity)
        if key not in variable_for:
            variable_for[key] = f"v{len(variable_for)}"
        return variable_for[key]

    steps: list[RelationStepV1] = []
    topology: list[tuple[str, str, str]] = []
    for ordinal, (subject, relation, object_) in enumerate(triples):
        relation_label = _norm_label(relation)
        template = f"{variable(subject)}-[{relation_label}]->{variable(object_)}"
        triple_id = _triple_content_id(subject, relation, object_)
        evidence_ids.add(triple_id)
        topology.append((variable(subject), relation_label, variable(object_)))
        dependencies = ()
        if ordinal:
            prior_objects = {_norm_label(item[2]): str(index) for index, item in enumerate(triples[:ordinal])}
            prior_subjects = {_norm_label(item[0]): str(index) for index, item in enumerate(triples[:ordinal])}
            linked = prior_objects.get(_norm_label(subject)) or prior_subjects.get(_norm_label(subject))
            dependencies = () if linked is None else (linked,)
        steps.append(RelationStepV1(
            ordinal=ordinal,
            step_id=str(ordinal),
            question="",
            answer=object_,
            dependencies=dependencies,
            subject=subject,
            relation=relation,
            object=object_,
            relation_template=template,
            evidence_content_ids=(triple_id,),
        ))

    relation_chain = tuple(_norm_label(relation) for _, relation, _ in triples)
    chain_id = content_id("relation_chain", {
        "dataset": "2wiki", "relations": relation_chain,
    })
    template_id = content_id("relation_template", {
        "dataset": "2wiki", "question_type": qtype, "topology": tuple(topology),
    })
    digest = _row_digest(row)
    return RelationExampleV1(
        occurrence_id=_occurrence_id("2wiki", qid, digest),
        qid=qid,
        dataset="2wiki",
        question=question,
        answer=answer,
        hop=len(steps),
        steps=tuple(steps),
        relation_chain=relation_chain,
        relation_chain_id=chain_id,
        relation_template_id=template_id,
        evidence_content_ids=tuple(sorted(evidence_ids)),
        raw_row_sha256=digest,
    )


def normalize_relation_rows(dataset: str, rows: Sequence[Mapping[str, Any]]) \
        -> tuple[RelationExampleV1, ...]:
    """Normalize and canonicalize raw rows; exact duplicates are deduplicated."""
    if dataset not in SUPPORTED_DATASETS:
        raise RelationEvaluationError(
            f"unsupported dataset {dataset!r}; expected one of {sorted(SUPPORTED_DATASETS)}"
        )
    normalizer = normalize_musique_row if dataset == "musique" else normalize_2wiki_row
    unique: dict[str, RelationExampleV1] = {}
    for index, row in enumerate(rows):
        try:
            example = normalizer(row)
        except RelationEvaluationError as exc:
            raise RelationEvaluationError(f"rows[{index}]: {exc}") from exc
        previous = unique.get(example.occurrence_id)
        if previous is not None and previous != example:
            raise RelationEvaluationError(
                f"rows[{index}] conflicts at occurrence {example.occurrence_id}"
            )
        unique[example.occurrence_id] = example
    if not unique:
        raise RelationEvaluationError("rows must not be empty")
    return tuple(sorted(unique.values(), key=lambda item: item.occurrence_id))


class _UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def split_relation_examples(
    examples: Sequence[RelationExampleV1],
    split_spec: tuple[tuple[str, float], ...] = (("val", 0.5), ("test", 0.5)),
    seed: int = 0,
) -> tuple[SplitAssignmentV1, ...]:
    """Split union components of relation template *and* exact evidence.

    Consequently, neither a relation template nor an exact gold evidence
    paragraph/triple can occur in more than one split.  The component allocator
    is deterministic, input-order invariant, and approximately size-balanced;
    it never breaks a component merely to fill an empty split.
    """
    examples = tuple(sorted(examples, key=lambda item: item.occurrence_id))
    if not examples:
        raise RelationEvaluationError("examples must not be empty")
    names = tuple(name for name, _ in split_spec)
    if len(names) < 2 or len(set(names)) != len(names) or any(not name for name in names):
        raise RelationEvaluationError("split names must contain at least two unique values")
    if any(not math.isfinite(weight) or weight <= 0 for _, weight in split_spec):
        raise RelationEvaluationError("split weights must be finite and positive")
    if len({item.occurrence_id for item in examples}) != len(examples):
        raise RelationEvaluationError("occurrence IDs must be unique before splitting")

    union_find = _UnionFind(len(examples))
    first_template: dict[str, int] = {}
    first_evidence: dict[str, int] = {}
    for index, example in enumerate(examples):
        prior = first_template.setdefault(example.relation_template_id, index)
        union_find.union(index, prior)
        for evidence_id in example.evidence_content_ids:
            prior = first_evidence.setdefault(evidence_id, index)
            union_find.union(index, prior)

    components: dict[int, list[int]] = {}
    for index in range(len(examples)):
        components.setdefault(union_find.find(index), []).append(index)

    component_records: list[tuple[str, tuple[int, ...]]] = []
    for members in components.values():
        member_ids = tuple(examples[index].occurrence_id for index in sorted(members))
        component_id = content_id("eval_split_component", {"members": member_ids})
        component_records.append((component_id, tuple(sorted(members))))
    component_records.sort(
        key=lambda item: (
            -len(item[1]),
            sha256(f"{seed}:{item[0]}".encode("utf-8")).hexdigest(),
            item[0],
        )
    )

    total_weight = sum(weight for _, weight in split_spec)
    target = {
        name: len(examples) * weight / total_weight for name, weight in split_spec
    }
    counts = {name: 0 for name in names}
    chosen: dict[int, tuple[str, str]] = {}
    for component_id, members in component_records:
        size = len(members)

        def allocation_key(name: str) -> tuple[float, str, str]:
            fill = (counts[name] + size) / target[name]
            tie = sha256(f"{seed}:{component_id}:{name}".encode("utf-8")).hexdigest()
            return fill, tie, name

        split = min(names, key=allocation_key)
        counts[split] += size
        for member in members:
            chosen[member] = (split, component_id)

    return tuple(
        SplitAssignmentV1(
            occurrence_id=example.occurrence_id,
            split=chosen[index][0],
            component_id=chosen[index][1],
        )
        for index, example in enumerate(examples)
    )


def build_relation_evaluation_suite(
    dataset: str,
    rows: Sequence[Mapping[str, Any]],
    split_spec: tuple[tuple[str, float], ...] = (("val", 0.5), ("test", 0.5)),
    seed: int = 0,
) -> RelationEvaluationSuiteV1:
    """Build an immutable, content-addressed held-out relation suite."""
    raw_snapshot_sha256 = sha256(canonical_json(tuple(rows)).encode("utf-8")).hexdigest()
    examples = normalize_relation_rows(dataset, rows)
    assignments = split_relation_examples(examples, split_spec, seed)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "raw_snapshot_sha256": raw_snapshot_sha256,
        "split_spec": split_spec,
        "split_seed": seed,
        "examples": examples,
        "assignments": assignments,
    }
    return RelationEvaluationSuiteV1(
        schema_version=SCHEMA_VERSION,
        suite_id=content_id("relation_eval_suite", payload),
        dataset=dataset,
        raw_snapshot_sha256=raw_snapshot_sha256,
        split_spec=split_spec,
        split_seed=seed,
        examples=examples,
        assignments=assignments,
    )


def _walk_payload(value: Any, path: str, seen: set[int]) -> list[str]:
    if isinstance(value, (str, bytes, int, float, bool, type(None))):
        return []
    identity = id(value)
    if identity in seen:
        return []
    seen.add(identity)
    found: list[str] = []
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            child_path = f"{path}.{field.name}" if path else field.name
            if field.name.casefold() in FORBIDDEN_COMPILER_KEYS:
                found.append(child_path)
            found.extend(_walk_payload(getattr(value, field.name), child_path, seen))
    elif isinstance(value, Mapping):
        for key in sorted(value, key=lambda item: str(item)):
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in FORBIDDEN_COMPILER_KEYS:
                found.append(child_path)
            found.extend(_walk_payload(value[key], child_path, seen))
    elif isinstance(value, Sequence):
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]" if path else f"[{index}]"
            found.extend(_walk_payload(item, child_path, seen))
    return found


def find_evaluation_label_paths(payload: Any) -> tuple[str, ...]:
    """Return deterministic paths of QA-only keys in a compiler payload."""
    return tuple(sorted(set(_walk_payload(payload, "", set()))))


def assert_compiler_payload_clean(payload: Any) -> None:
    """Fail closed if evaluation supervision is mixed into compiler input."""
    paths = find_evaluation_label_paths(payload)
    if paths:
        raise EvaluationLabelLeakageError(paths)
