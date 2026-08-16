"""Deterministic non-redundant source-policy environment for HSWM P1v3.

The base PhantomWiki articles remain immutable inputs.  Each experimental case
derives a balanced conflict packet: true matching records carry one opaque
source class and deterministic decoy records carry another.  The class names
have no intrinsic trust meaning.  Only training outcome evidence may justify a
typed lesson that names the authoritative class.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import RetrievedDocumentV1
from p1v2_prompt_parity import ARM_IDS
from p1v2_typed_lesson import (
    LessonCompilePolicyV1,
    TypedLessonV1,
    compile_typed_lesson,
    render_lesson_context,
    retrieve_lessons,
)
from p1v2_type6_environment import (
    parse_type6_question,
    retrieve_exact_attribute_documents,
)


SCHEMA_VERSION = "hswm-p1v3-policy-conflict-case/v1"
DEFAULT_TRUSTED_CLASS = "RHO"
DEFAULT_DISTRACTOR_CLASS = "TAU"
_SOURCE_CLASS = re.compile(r"^[A-Z][A-Z0-9_]{1,15}$")


class PolicyEnvironmentError(ValueError):
    pass


def _class_code(value: str, label: str) -> str:
    if not isinstance(value, str) or _SOURCE_CLASS.fullmatch(value) is None:
        raise PolicyEnvironmentError(f"{label} must be an opaque uppercase class code")
    return value


def _classified_text(source_class: str, text: str) -> str:
    return f"[SOURCE_CLASS={source_class}]\n{text}"


def _derived_source_id(
    *, base_source_id: str, source_class: str, text: str
) -> str:
    return "policy:" + canonical_sha256({
        "base_source_id": base_source_id,
        "source_class": source_class,
        "derived_text": text,
    })[:32]


@dataclass(frozen=True)
class PolicyConflictCaseV1:
    case_id: str
    question: str
    documents: tuple[RetrievedDocumentV1, ...]
    expected_answers: tuple[str, ...]
    trusted_source_ids: tuple[str, ...]
    distractor_source_ids: tuple[str, ...]
    trusted_class: str
    distractor_class: str
    derivation_sha256: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or not self.case_id or not self.question:
            raise PolicyEnvironmentError("policy case identity is invalid")
        _class_code(self.trusted_class, "trusted_class")
        _class_code(self.distractor_class, "distractor_class")
        if self.trusted_class == self.distractor_class:
            raise PolicyEnvironmentError("source classes must differ")
        document_ids = tuple(document.source_id for document in self.documents)
        if (
            not self.documents
            or len(set(document_ids)) != len(document_ids)
            or tuple(sorted(document_ids)) != document_ids
            or not self.expected_answers
            or len(set(self.expected_answers)) != len(self.expected_answers)
        ):
            raise PolicyEnvironmentError("policy case cut is empty or non-canonical")
        trusted = set(self.trusted_source_ids)
        distractor = set(self.distractor_source_ids)
        if (
            not trusted
            or len(trusted) != len(distractor)
            or trusted & distractor
            or trusted | distractor != set(document_ids)
        ):
            raise PolicyEnvironmentError("policy case must be a balanced conflict cut")
        unsigned = self.unsigned()
        if canonical_sha256(unsigned) != self.derivation_sha256:
            raise PolicyEnvironmentError("policy case derivation hash drifted")

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "question": self.question,
            "documents": [document.canonical() for document in self.documents],
            "expected_answers": list(self.expected_answers),
            "trusted_source_ids": list(self.trusted_source_ids),
            "distractor_source_ids": list(self.distractor_source_ids),
            "trusted_class": self.trusted_class,
            "distractor_class": self.distractor_class,
        }

    def public(self) -> dict[str, object]:
        """Return the answer- and policy-blind packet supplied to all arms."""

        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "question": self.question,
            "documents": [document.canonical() for document in self.documents],
            "document_count": len(self.documents),
            "derivation_sha256": self.derivation_sha256,
        }

    def sealed(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "expected_answers": list(self.expected_answers),
            "trusted_source_ids": list(self.trusted_source_ids),
            "distractor_source_ids": list(self.distractor_source_ids),
            "trusted_class": self.trusted_class,
            "distractor_class": self.distractor_class,
            "derivation_sha256": self.derivation_sha256,
        }


def build_policy_conflict_case(
    *,
    case_id: str,
    question: str,
    articles: Sequence[Mapping[str, Any]],
    trusted_class: str = DEFAULT_TRUSTED_CLASS,
    distractor_class: str = DEFAULT_DISTRACTOR_CLASS,
    maximum_true_documents: int = 4,
) -> PolicyConflictCaseV1:
    """Derive one balanced conflict packet without mutating its base articles."""

    trusted_class = _class_code(trusted_class, "trusted_class")
    distractor_class = _class_code(distractor_class, "distractor_class")
    if trusted_class == distractor_class:
        raise PolicyEnvironmentError("source classes must differ")
    if not isinstance(maximum_true_documents, int) or maximum_true_documents <= 0:
        raise PolicyEnvironmentError("maximum_true_documents must be positive")
    if not case_id:
        raise PolicyEnvironmentError("case_id must be non-empty")
    query = parse_type6_question(question)
    true_base = retrieve_exact_attribute_documents(
        question, articles, top_k=len(articles)
    )
    if len(true_base) > maximum_true_documents:
        raise PolicyEnvironmentError("true answer count exceeds the conflict-case cut")
    true_titles = {document.title for document in true_base}
    decoy_candidates = sorted(
        (
            RetrievedDocumentV1(
                source_id="base:" + canonical_sha256({
                    "title": article["title"], "text": article["article"]
                })[:32],
                title=article["title"],
                text=article["article"],
            )
            for article in articles
            if isinstance(article, Mapping)
            and isinstance(article.get("title"), str)
            and isinstance(article.get("article"), str)
            and article["title"] not in true_titles
        ),
        key=lambda document: document.source_id,
    )
    if len(decoy_candidates) < len(true_base):
        raise PolicyEnvironmentError("not enough deterministic decoy candidates")

    derived: list[RetrievedDocumentV1] = []
    trusted_ids: list[str] = []
    distractor_ids: list[str] = []
    for base in true_base:
        text = _classified_text(trusted_class, base.text)
        source_id = _derived_source_id(
            base_source_id=base.source_id,
            source_class=trusted_class,
            text=text,
        )
        derived.append(RetrievedDocumentV1(source_id, base.title, text))
        trusted_ids.append(source_id)
    for base in decoy_candidates[:len(true_base)]:
        forged_claim = f"The {query.attribute} of {base.title} is {query.value}."
        text = _classified_text(distractor_class, base.text + "\n" + forged_claim)
        source_id = _derived_source_id(
            base_source_id=base.source_id,
            source_class=distractor_class,
            text=text,
        )
        derived.append(RetrievedDocumentV1(source_id, base.title, text))
        distractor_ids.append(source_id)
    derived.sort(key=lambda document: document.source_id)

    unsigned: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "question": question,
        "documents": [document.canonical() for document in derived],
        "expected_answers": sorted(true_titles),
        "trusted_source_ids": sorted(trusted_ids),
        "distractor_source_ids": sorted(distractor_ids),
        "trusted_class": trusted_class,
        "distractor_class": distractor_class,
    }
    return PolicyConflictCaseV1(
        case_id=case_id,
        question=question,
        documents=tuple(derived),
        expected_answers=tuple(sorted(true_titles)),
        trusted_source_ids=tuple(sorted(trusted_ids)),
        distractor_source_ids=tuple(sorted(distractor_ids)),
        trusted_class=trusted_class,
        distractor_class=distractor_class,
        derivation_sha256=canonical_sha256(unsigned),
    )


def render_policy_training_transcript(case: PolicyConflictCaseV1) -> str:
    payload = {
        "schema_version": "hswm-p1v3-policy-training-transcript/v1",
        "training_case_id": case.case_id,
        "question": case.question,
        "documents": [document.canonical() for document in case.documents],
        "verified_complete_answer_set": list(case.expected_answers),
        "evidence_id": "policy-training-evidence:" + case.derivation_sha256,
        "forbidden_uses": ["future_episode", "heldout_gold", "evaluation_label"],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compile_policy_oracle_lesson(
    training_case: PolicyConflictCaseV1,
    *,
    forbidden_identifiers: Sequence[str] = (),
) -> TypedLessonV1:
    episode_id = "policy-training:" + training_case.case_id
    evidence_id = "policy-training-evidence:" + training_case.derivation_sha256
    instruction = (
        "When supplied records contain conflicting answer candidates, treat "
        f"SOURCE_CLASS={training_case.trusted_class} as authoritative, ignore "
        f"SOURCE_CLASS={training_case.distractor_class} claims for the final "
        f"answer, and cite only {training_case.trusted_class} records."
    )
    recorded = {
        "schema_version": "hswm-p1v2-operational-verdict/v1",
        "source_episode_ids": [episode_id],
        "evidence_ids": [evidence_id],
        "verdict_type": "GENERALIZATION",
        "scope_predicate": {
            "all_terms": ["who is", "the person whose"],
            "any_terms": ["occupation", "hobby", "date of birth", "gender"],
            "excluded_terms": [],
        },
        "instruction": instruction,
        "polarity": "DO",
        "confidence": 1.0,
        "supersedes": [],
    }
    lesson = compile_typed_lesson(
        recorded,
        LessonCompilePolicyV1(
            allowed_episode_ids=(episode_id,),
            allowed_evidence_ids=(evidence_id,),
            forbidden_identifiers=tuple(forbidden_identifiers),
        ),
    )
    verify_policy_oracle_admission(
        lesson,
        trusted_class=training_case.trusted_class,
        distractor_class=training_case.distractor_class,
    )
    return lesson


def verify_policy_oracle_admission(
    lesson: TypedLessonV1,
    *,
    trusted_class: str,
    distractor_class: str,
) -> str:
    """Accept only the frozen conflict policy; reject an inverted lesson."""

    lesson.verify()
    trusted_class = _class_code(trusted_class, "trusted_class")
    distractor_class = _class_code(distractor_class, "distractor_class")
    instruction = " ".join(lesson.instruction.upper().split())
    required = (
        "CONFLICT",
        f"SOURCE_CLASS={trusted_class} AS AUTHORITATIVE",
        f"IGNORE SOURCE_CLASS={distractor_class}",
        f"ONLY {trusted_class} RECORDS",
    )
    forbidden = (
        f"SOURCE_CLASS={distractor_class} AS AUTHORITATIVE",
        f"IGNORE SOURCE_CLASS={trusted_class}",
        f"ONLY {distractor_class} RECORDS",
    )
    if (
        lesson.polarity != "DO"
        or any(term not in instruction for term in required)
        or any(term in instruction for term in forbidden)
    ):
        raise PolicyEnvironmentError("lesson contradicts the frozen source policy")
    return canonical_sha256({
        "schema_version": "hswm-p1v3-policy-oracle-admission/v1",
        "lesson_id": lesson.lesson_id,
        "trusted_class": trusted_class,
        "distractor_class": distractor_class,
        "required_semantics": list(required),
        "forbidden_semantics": list(forbidden),
    })


def build_policy_memory_contexts(
    *,
    question: str,
    admitted_lesson: TypedLessonV1,
    raw_training_transcript: str,
) -> dict[str, str]:
    selection = retrieve_lessons(question, (admitted_lesson,), top_k=1)
    if selection.selected_lesson_ids != (admitted_lesson.lesson_id,):
        raise PolicyEnvironmentError("policy lesson scope does not bind the question")
    contexts = {
        "T1_typed_lesson": render_lesson_context(selection, (admitted_lesson,)),
        "T2_raw_transcript": raw_training_transcript,
        "T3_no_memory": "",
        "T4_shuffled_or_removed": "",
    }
    if set(contexts) != set(ARM_IDS):
        raise PolicyEnvironmentError("memory arm cut drifted")
    return contexts


__all__ = [
    "DEFAULT_DISTRACTOR_CLASS",
    "DEFAULT_TRUSTED_CLASS",
    "PolicyConflictCaseV1",
    "PolicyEnvironmentError",
    "build_policy_conflict_case",
    "build_policy_memory_contexts",
    "compile_policy_oracle_lesson",
    "render_policy_training_transcript",
    "verify_policy_oracle_admission",
]
