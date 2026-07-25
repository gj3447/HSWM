"""Multi-class source-policy conflict cases for HSWM F3-r2 (ADD-only module).

The frozen p1v3 policy environment builds balanced TWO-class conflict
packets (p1v3_policy_environment.py, untouched).  This module adds the
multi-class variant used by the F3-r2 harder-verdict design: one trusted
class plus K>=2 distractor classes, one deterministic decoy per distractor
class, so the donor's verdict task ("which class was authoritative?") has
K+1 candidates instead of 2.  Nothing here modifies the two-class path;
the module is new so no existing receipt's module-sha binding is touched.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Mapping, Sequence
from typing import Any

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import RetrievedDocumentV1
from p1v2_type6_environment import (
    parse_type6_question,
    retrieve_exact_attribute_documents,
)
from p1v3_policy_environment import PolicyEnvironmentError


MULTI_SCHEMA_VERSION = "hswm-p1v3-policy-conflict-case-multi/v1"
_CLASS_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,15}$")


def _class_code(value: str, label: str) -> str:
    if not isinstance(value, str) or _CLASS_CODE.fullmatch(value) is None:
        raise PolicyEnvironmentError(f"{label} must be an opaque uppercase class code")
    return value


def _classified_text(source_class: str, text: str) -> str:
    return f"[SOURCE_CLASS={source_class}]\n{text}"


def _derived_source_id(*, base_source_id: str, source_class: str, text: str) -> str:
    return "policy:" + canonical_sha256({
        "base_source_id": base_source_id,
        "source_class": source_class,
        "derived_text": text,
    })[:32]


@dataclass(frozen=True)
class PolicyConflictCaseMultiV1:
    case_id: str
    question: str
    documents: tuple[RetrievedDocumentV1, ...]
    expected_answers: tuple[str, ...]
    trusted_class: str
    distractor_classes: tuple[str, ...]
    trusted_source_ids: tuple[str, ...]
    derivation_sha256: str
    schema_version: str = MULTI_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != MULTI_SCHEMA_VERSION or not self.case_id or not self.question:
            raise PolicyEnvironmentError("multi policy case identity is invalid")
        _class_code(self.trusted_class, "trusted_class")
        if len(self.distractor_classes) < 2:
            raise PolicyEnvironmentError("multi case needs at least two distractor classes")
        for klass in self.distractor_classes:
            _class_code(klass, "distractor_classes")
        if self.trusted_class in self.distractor_classes:
            raise PolicyEnvironmentError("source classes must differ")
        if len(set(self.distractor_classes)) != len(self.distractor_classes):
            raise PolicyEnvironmentError("distractor classes must be distinct")
        document_ids = tuple(document.source_id for document in self.documents)
        if (
            not self.documents
            or len(set(document_ids)) != len(document_ids)
            or tuple(sorted(document_ids)) != document_ids
            or not self.expected_answers
            or len(set(self.expected_answers)) != len(self.expected_answers)
        ):
            raise PolicyEnvironmentError("multi policy case cut is empty or non-canonical")
        if len(self.documents) != len(self.trusted_source_ids) + len(self.distractor_classes):
            raise PolicyEnvironmentError("multi case document cut drifted")
        if canonical_sha256(self.unsigned()) != self.derivation_sha256:
            raise PolicyEnvironmentError("multi policy case derivation hash drifted")

    @property
    def candidate_classes(self) -> tuple[str, ...]:
        return tuple(sorted((self.trusted_class,) + self.distractor_classes))

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "question": self.question,
            "documents": [document.canonical() for document in self.documents],
            "expected_answers": list(self.expected_answers),
            "trusted_class": self.trusted_class,
            "distractor_classes": list(self.distractor_classes),
            "trusted_source_ids": list(self.trusted_source_ids),
        }


def build_policy_conflict_case_multi(
    *,
    case_id: str,
    question: str,
    articles: Sequence[Mapping[str, Any]],
    trusted_class: str,
    distractor_classes: Sequence[str],
    maximum_true_documents: int = 1,
) -> PolicyConflictCaseMultiV1:
    """Derive one multi-class conflict packet (1 true doc + K decoys)."""

    trusted_class = _class_code(trusted_class, "trusted_class")
    distractor_classes = tuple(distractor_classes)
    if len(distractor_classes) < 2:
        raise PolicyEnvironmentError("need at least two distractor classes")
    for klass in distractor_classes:
        _class_code(klass, "distractor_classes")
    if trusted_class in distractor_classes:
        raise PolicyEnvironmentError("source classes must differ")
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
    if len(decoy_candidates) < len(distractor_classes):
        raise PolicyEnvironmentError("not enough deterministic decoy candidates")

    derived: list[RetrievedDocumentV1] = []
    trusted_ids: list[str] = []
    for base in true_base:
        text = _classified_text(trusted_class, base.text)
        source_id = _derived_source_id(
            base_source_id=base.source_id, source_class=trusted_class, text=text)
        derived.append(RetrievedDocumentV1(source_id, base.title, text))
        trusted_ids.append(source_id)
    for klass, base in zip(distractor_classes, decoy_candidates):
        forged_claim = f"The {query.attribute} of {base.title} is {query.value}."
        text = _classified_text(klass, base.text + "\n" + forged_claim)
        source_id = _derived_source_id(
            base_source_id=base.source_id, source_class=klass, text=text)
        derived.append(RetrievedDocumentV1(source_id, base.title, text))
    derived.sort(key=lambda document: document.source_id)

    unsigned: dict[str, object] = {
        "schema_version": MULTI_SCHEMA_VERSION,
        "case_id": case_id,
        "question": question,
        "documents": [document.canonical() for document in derived],
        "expected_answers": sorted(true_titles),
        "trusted_class": trusted_class,
        "distractor_classes": list(distractor_classes),
        "trusted_source_ids": sorted(trusted_ids),
    }
    return PolicyConflictCaseMultiV1(
        case_id=case_id,
        question=question,
        documents=tuple(derived),
        expected_answers=tuple(sorted(true_titles)),
        trusted_class=trusted_class,
        distractor_classes=tuple(distractor_classes),
        trusted_source_ids=tuple(sorted(trusted_ids)),
        derivation_sha256=canonical_sha256(unsigned),
    )


__all__ = [
    "MULTI_SCHEMA_VERSION",
    "PolicyConflictCaseMultiV1",
    "build_policy_conflict_case_multi",
]
