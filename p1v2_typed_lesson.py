"""Pure typed verdict-to-lesson compiler and deterministic lesson retrieval.

The module consumes an already-recorded operational verdict.  It performs no
model, network, filesystem, clock, random, gold, or scientific-judge work.  A
caller must provide explicit allow-lists for training episodes and evidence;
anything outside that cut fails closed before a lesson can be constructed.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Mapping, Sequence

from hswm_weight_snapshot import canonical_sha256


VERDICT_SCHEMA_VERSION = "hswm-p1v2-operational-verdict/v1"
LESSON_SCHEMA_VERSION = "hswm-p1v2-typed-lesson/v1"
COMPILER_RECEIPT_VERSION = "hswm-p1v2-lesson-compiler-receipt/v1"
SELECTION_SCHEMA_VERSION = "hswm-p1v2-lesson-selection/v1"
CONTEXT_SCHEMA_VERSION = "hswm-p1v2-lesson-context/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_VERDICT_TYPES = {"CORRECTIVE", "GENERALIZATION", "CONTRADICTION"}
_ALLOWED_POLARITIES = {"DO", "AVOID"}
_REQUIRED_VERDICT_KEYS = {
    "schema_version",
    "source_episode_ids",
    "evidence_ids",
    "verdict_type",
    "scope_predicate",
    "instruction",
    "polarity",
    "confidence",
    "supersedes",
}
_SCOPE_KEYS = {"all_terms", "any_terms", "excluded_terms"}


class LessonContractError(ValueError):
    """An untrusted verdict or lesson violates the frozen compiler contract."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LessonContractError(f"{label} must be non-empty text")
    return value.strip()


def _text_tuple(
    value: Any,
    label: str,
    *,
    allow_empty: bool = False,
    normalize: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise LessonContractError(f"{label} must be a list of text values")
    items = tuple(
        " ".join(_text(item, label).casefold().split()) if normalize
        else _text(item, label)
        for item in value
    )
    if not allow_empty and not items:
        raise LessonContractError(f"{label} must not be empty")
    if len(items) != len(set(items)):
        raise LessonContractError(f"{label} must contain unique values")
    return tuple(sorted(items))


@dataclass(frozen=True)
class ScopePredicateV1:
    all_terms: tuple[str, ...]
    any_terms: tuple[str, ...]
    excluded_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        all_terms = _text_tuple(self.all_terms, "all_terms", allow_empty=True, normalize=True)
        any_terms = _text_tuple(self.any_terms, "any_terms", allow_empty=True, normalize=True)
        excluded = _text_tuple(
            self.excluded_terms, "excluded_terms", allow_empty=True, normalize=True
        )
        if not all_terms and not any_terms:
            raise LessonContractError("scope predicate needs all_terms or any_terms")
        if (set(all_terms) | set(any_terms)) & set(excluded):
            raise LessonContractError("scope include and exclude terms must be disjoint")
        object.__setattr__(self, "all_terms", all_terms)
        object.__setattr__(self, "any_terms", any_terms)
        object.__setattr__(self, "excluded_terms", excluded)

    @classmethod
    def from_mapping(cls, value: Any) -> "ScopePredicateV1":
        if not isinstance(value, Mapping) or set(value) != _SCOPE_KEYS:
            raise LessonContractError("scope_predicate must contain exactly the v1 keys")
        if any(not isinstance(value[key], (list, tuple)) for key in _SCOPE_KEYS):
            raise LessonContractError("scope predicate terms must be lists")
        return cls(
            all_terms=tuple(value["all_terms"]),
            any_terms=tuple(value["any_terms"]),
            excluded_terms=tuple(value["excluded_terms"]),
        )

    def canonical(self) -> dict[str, list[str]]:
        return {
            "all_terms": list(self.all_terms),
            "any_terms": list(self.any_terms),
            "excluded_terms": list(self.excluded_terms),
        }

    def matches(self, query: str) -> bool:
        normalized = " ".join(_text(query, "query").casefold().split())
        if any(term in normalized for term in self.excluded_terms):
            return False
        if any(term not in normalized for term in self.all_terms):
            return False
        return not self.any_terms or any(term in normalized for term in self.any_terms)

    @property
    def specificity(self) -> int:
        return len(self.all_terms) * 2 + len(self.any_terms)


@dataclass(frozen=True)
class LessonCompilePolicyV1:
    allowed_episode_ids: tuple[str, ...]
    allowed_evidence_ids: tuple[str, ...]
    known_lesson_ids: tuple[str, ...] = ()
    forbidden_identifiers: tuple[str, ...] = ()
    forbidden_strings: tuple[str, ...] = ()
    minimum_confidence: float = 0.5
    required_forbidden_uses: tuple[str, ...] = (
        "evaluation_label",
        "future_episode",
        "heldout_gold",
    )

    def __post_init__(self) -> None:
        for field in (
            "allowed_episode_ids",
            "allowed_evidence_ids",
            "known_lesson_ids",
            "forbidden_identifiers",
            "forbidden_strings",
            "required_forbidden_uses",
        ):
            allow_empty = field not in {"allowed_episode_ids", "allowed_evidence_ids"}
            object.__setattr__(
                self,
                field,
                _text_tuple(getattr(self, field), field, allow_empty=allow_empty),
            )
        if not math.isfinite(self.minimum_confidence) or not 0 <= self.minimum_confidence <= 1:
            raise LessonContractError("minimum_confidence must be finite and in [0, 1]")

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": "hswm-p1v2-lesson-policy/v1",
            "allowed_episode_ids": list(self.allowed_episode_ids),
            "allowed_evidence_ids": list(self.allowed_evidence_ids),
            "known_lesson_ids": list(self.known_lesson_ids),
            "forbidden_identifiers": list(self.forbidden_identifiers),
            "forbidden_strings": list(self.forbidden_strings),
            "minimum_confidence": self.minimum_confidence,
            "required_forbidden_uses": list(self.required_forbidden_uses),
        }


@dataclass(frozen=True)
class TypedLessonV1:
    lesson_id: str
    source_episode_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    verdict_type: str
    scope_predicate: ScopePredicateV1
    instruction: str
    polarity: str
    confidence: float
    supersedes: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    compiler_receipt_sha256: str
    source_verdict_sha256: str
    schema_version: str = LESSON_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != LESSON_SCHEMA_VERSION:
            raise LessonContractError("unsupported lesson schema")
        object.__setattr__(
            self, "source_episode_ids", _text_tuple(self.source_episode_ids, "source_episode_ids")
        )
        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
        if self.verdict_type not in _ALLOWED_VERDICT_TYPES:
            raise LessonContractError("invalid lesson verdict_type")
        if not isinstance(self.scope_predicate, ScopePredicateV1):
            raise LessonContractError("scope_predicate must be ScopePredicateV1")
        object.__setattr__(self, "instruction", _text(self.instruction, "instruction"))
        if self.polarity not in _ALLOWED_POLARITIES:
            raise LessonContractError("invalid lesson polarity")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise LessonContractError("lesson confidence must be finite and in [0, 1]")
        object.__setattr__(
            self, "supersedes", _text_tuple(self.supersedes, "supersedes", allow_empty=True)
        )
        object.__setattr__(
            self,
            "forbidden_uses",
            _text_tuple(self.forbidden_uses, "forbidden_uses", allow_empty=True),
        )

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_episode_ids": list(self.source_episode_ids),
            "evidence_ids": list(self.evidence_ids),
            "verdict_type": self.verdict_type,
            "scope_predicate": self.scope_predicate.canonical(),
            "instruction": self.instruction,
            "polarity": self.polarity,
            "confidence": self.confidence,
            "supersedes": list(self.supersedes),
            "forbidden_uses": list(self.forbidden_uses),
            "compiler_receipt_sha256": self.compiler_receipt_sha256,
            "source_verdict_sha256": self.source_verdict_sha256,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "lesson_id": self.lesson_id}

    def verify(self) -> None:
        if not _SHA256.fullmatch(self.lesson_id):
            raise LessonContractError("lesson_id must be a lowercase SHA-256")
        if canonical_sha256(self.unsigned()) != self.lesson_id:
            raise LessonContractError("lesson_id does not bind canonical lesson bytes")
        for value in (self.compiler_receipt_sha256, self.source_verdict_sha256):
            if not _SHA256.fullmatch(value):
                raise LessonContractError("lesson provenance must use lowercase SHA-256")


def compile_typed_lesson(
    recorded_verdict: Mapping[str, Any],
    policy: LessonCompilePolicyV1,
) -> TypedLessonV1:
    """Compile one recorded operational verdict under an explicit sealed cut."""

    if not isinstance(recorded_verdict, Mapping):
        raise LessonContractError("recorded verdict must be a mapping")
    if set(recorded_verdict) != _REQUIRED_VERDICT_KEYS:
        raise LessonContractError("recorded verdict must contain exactly the v1 keys")
    if recorded_verdict.get("schema_version") != VERDICT_SCHEMA_VERSION:
        raise LessonContractError("unsupported operational verdict schema")

    serialized = json.dumps(
        recorded_verdict, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).casefold()
    for forbidden in policy.forbidden_identifiers:
        if forbidden.casefold() in serialized:
            raise LessonContractError("recorded verdict contains a forbidden identifier")
    for forbidden in policy.forbidden_strings:
        if forbidden.casefold() in serialized:
            raise LessonContractError("recorded verdict contains forbidden heldout text")

    episodes = _text_tuple(recorded_verdict["source_episode_ids"], "source_episode_ids")
    evidence = _text_tuple(recorded_verdict["evidence_ids"], "evidence_ids")
    if not set(episodes) <= set(policy.allowed_episode_ids):
        raise LessonContractError("source episode is outside the frozen training cut")
    if not set(evidence) <= set(policy.allowed_evidence_ids):
        raise LessonContractError("evidence is outside the frozen training cut")

    verdict_type = _text(recorded_verdict["verdict_type"], "verdict_type")
    if verdict_type not in _ALLOWED_VERDICT_TYPES:
        raise LessonContractError("verdict_type is not lesson-producing")
    polarity = _text(recorded_verdict["polarity"], "polarity")
    if polarity not in _ALLOWED_POLARITIES:
        raise LessonContractError("unsupported lesson polarity")
    instruction = _text(recorded_verdict["instruction"], "instruction")
    if len(instruction) > 2000:
        raise LessonContractError("instruction exceeds the v1 length cap")
    if isinstance(recorded_verdict["confidence"], bool):
        raise LessonContractError("confidence must be numeric")
    try:
        confidence = float(recorded_verdict["confidence"])
    except (TypeError, ValueError) as error:
        raise LessonContractError("confidence must be numeric") from error
    if not math.isfinite(confidence) or not policy.minimum_confidence <= confidence <= 1:
        raise LessonContractError("confidence is below admission or outside [0, 1]")
    supersedes = _text_tuple(
        recorded_verdict["supersedes"], "supersedes", allow_empty=True
    )
    if not set(supersedes) <= set(policy.known_lesson_ids):
        raise LessonContractError("supersedes references an unknown lesson")
    scope = ScopePredicateV1.from_mapping(recorded_verdict["scope_predicate"])

    source_verdict_sha256 = canonical_sha256(recorded_verdict)
    body = {
        "schema_version": LESSON_SCHEMA_VERSION,
        "source_episode_ids": list(episodes),
        "evidence_ids": list(evidence),
        "verdict_type": verdict_type,
        "scope_predicate": scope.canonical(),
        "instruction": instruction,
        "polarity": polarity,
        "confidence": confidence,
        "supersedes": list(supersedes),
        "forbidden_uses": list(policy.required_forbidden_uses),
        "source_verdict_sha256": source_verdict_sha256,
    }
    compiler_receipt_sha256 = canonical_sha256({
        "schema_version": COMPILER_RECEIPT_VERSION,
        "policy_sha256": canonical_sha256(policy.canonical()),
        "lesson_body_sha256": canonical_sha256(body),
        "source_verdict_sha256": source_verdict_sha256,
    })
    unsigned = {**body, "compiler_receipt_sha256": compiler_receipt_sha256}
    lesson = TypedLessonV1(
        lesson_id=canonical_sha256(unsigned),
        source_episode_ids=episodes,
        evidence_ids=evidence,
        verdict_type=verdict_type,
        scope_predicate=scope,
        instruction=instruction,
        polarity=polarity,
        confidence=confidence,
        supersedes=supersedes,
        forbidden_uses=policy.required_forbidden_uses,
        compiler_receipt_sha256=compiler_receipt_sha256,
        source_verdict_sha256=source_verdict_sha256,
    )
    lesson.verify()
    return lesson


@dataclass(frozen=True)
class LessonSelectionV1:
    query_sha256: str
    candidate_lesson_ids: tuple[str, ...]
    selected_lesson_ids: tuple[str, ...]
    top_k: int
    selection_receipt_sha256: str
    schema_version: str = SELECTION_SCHEMA_VERSION

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "query_sha256": self.query_sha256,
            "candidate_lesson_ids": list(self.candidate_lesson_ids),
            "selected_lesson_ids": list(self.selected_lesson_ids),
            "top_k": self.top_k,
            "selection_receipt_sha256": self.selection_receipt_sha256,
        }

    def verify(self) -> None:
        if not _SHA256.fullmatch(self.query_sha256):
            raise LessonContractError("selection query hash is invalid")
        if self.top_k <= 0 or len(self.selected_lesson_ids) > self.top_k:
            raise LessonContractError("selection top_k contract is invalid")
        if not set(self.selected_lesson_ids) <= set(self.candidate_lesson_ids):
            raise LessonContractError("selection references a non-candidate lesson")
        expected = canonical_sha256({
            "schema_version": self.schema_version,
            "query_sha256": self.query_sha256,
            "candidate_lesson_ids": list(self.candidate_lesson_ids),
            "selected_lesson_ids": list(self.selected_lesson_ids),
            "top_k": self.top_k,
        })
        if expected != self.selection_receipt_sha256:
            raise LessonContractError("selection receipt does not bind canonical inputs")


def retrieve_lessons(
    query: str,
    lessons: Sequence[TypedLessonV1],
    *,
    top_k: int,
) -> LessonSelectionV1:
    if top_k <= 0:
        raise LessonContractError("top_k must be positive")
    unique: dict[str, TypedLessonV1] = {}
    superseded: set[str] = set()
    for lesson in lessons:
        lesson.verify()
        if lesson.lesson_id in unique:
            raise LessonContractError("lesson IDs must be unique")
        unique[lesson.lesson_id] = lesson
        superseded.update(lesson.supersedes)
    ranked = sorted(
        (
            lesson for lesson in unique.values()
            if lesson.lesson_id not in superseded and lesson.scope_predicate.matches(query)
        ),
        key=lambda lesson: (
            -lesson.confidence,
            -lesson.scope_predicate.specificity,
            lesson.lesson_id,
        ),
    )
    selected = tuple(lesson.lesson_id for lesson in ranked[:top_k])
    query_sha256 = canonical_sha256({"query": _text(query, "query")})
    candidate_ids = tuple(sorted(unique))
    receipt = canonical_sha256({
        "schema_version": SELECTION_SCHEMA_VERSION,
        "query_sha256": query_sha256,
        "candidate_lesson_ids": list(candidate_ids),
        "selected_lesson_ids": list(selected),
        "top_k": top_k,
    })
    result = LessonSelectionV1(query_sha256, candidate_ids, selected, top_k, receipt)
    result.verify()
    return result


def render_lesson_context(
    selection: LessonSelectionV1,
    lessons: Sequence[TypedLessonV1],
) -> str:
    selection.verify()
    by_id = {lesson.lesson_id: lesson for lesson in lessons}
    if tuple(sorted(by_id)) != selection.candidate_lesson_ids:
        raise LessonContractError("selection candidate cut differs from available lessons")
    if any(lesson_id not in by_id for lesson_id in selection.selected_lesson_ids):
        raise LessonContractError("selection references an unavailable lesson")
    payload = {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "lessons": [
            {
                "lesson_id": lesson_id,
                "scope_predicate": by_id[lesson_id].scope_predicate.canonical(),
                "instruction": by_id[lesson_id].instruction,
                "polarity": by_id[lesson_id].polarity,
                "confidence": by_id[lesson_id].confidence,
            }
            for lesson_id in selection.selected_lesson_ids
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
