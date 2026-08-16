"""Pure PhantomWiki type-6 retrieval and L0 memory-arm construction.

The retriever parses only the public question and article text.  It never reads
the sealed answer sidecar.  Training gold may enter the raw transcript only
through an explicit training-evidence call after the split has been frozen.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from hswm_weight_snapshot import canonical_sha256
from p1_llm_answerer import RetrievedDocumentV1
from p1v2_prompt_parity import ARM_IDS
from p1v2_typed_lesson import (
    TypedLessonV1,
    render_lesson_context,
    retrieve_lessons,
)


_TYPE6 = re.compile(
    r"^Who is the person whose (?P<attribute>[^?]+?) is (?P<value>[^?]+)\?$"
)


class Type6EnvironmentError(ValueError):
    pass


@dataclass(frozen=True)
class AttributeQueryV1:
    attribute: str
    value: str


def parse_type6_question(question: str) -> AttributeQueryV1:
    if not isinstance(question, str):
        raise Type6EnvironmentError("question must be text")
    match = _TYPE6.fullmatch(question.strip())
    if match is None:
        raise Type6EnvironmentError("question is outside the frozen type-6 template")
    attribute = " ".join(match.group("attribute").casefold().split())
    value = " ".join(match.group("value").casefold().split())
    if not attribute or not value:
        raise Type6EnvironmentError("type-6 attribute and value must be non-empty")
    return AttributeQueryV1(attribute=attribute, value=value)


def _source_id(title: str) -> str:
    return "phantom:" + sha256(title.encode("utf-8")).hexdigest()[:32]


def retrieve_exact_attribute_documents(
    question: str,
    articles: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 10,
) -> tuple[RetrievedDocumentV1, ...]:
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        raise Type6EnvironmentError("top_k must be a positive integer")
    query = parse_type6_question(question)
    matches: list[RetrievedDocumentV1] = []
    for article in articles:
        if not isinstance(article, Mapping):
            raise Type6EnvironmentError("articles must be mappings")
        title = article.get("title")
        text = article.get("article")
        if not isinstance(title, str) or not title or not isinstance(text, str) or not text:
            raise Type6EnvironmentError("article title/text schema mismatch")
        expected = f"the {query.attribute} of {title.casefold()} is {query.value}."
        normalized_lines = {
            " ".join(line.casefold().split()) for line in text.splitlines()
        }
        if expected in normalized_lines:
            matches.append(RetrievedDocumentV1(
                source_id=_source_id(title), title=title, text=text
            ))
    matches.sort(key=lambda document: document.source_id)
    if not matches:
        raise Type6EnvironmentError("public question retrieved no exact attribute document")
    if len(matches) > top_k:
        raise Type6EnvironmentError(
            "exact attribute document count exceeds the frozen retrieval cut"
        )
    return tuple(matches)


def render_training_transcript(
    *,
    case_id: str,
    question: str,
    verified_gold_answers: Sequence[str],
    evidence_id: str,
) -> str:
    answers = tuple(sorted(verified_gold_answers))
    if (
        not case_id
        or not evidence_id
        or not answers
        or any(not isinstance(answer, str) or not answer for answer in answers)
        or len(set(answers)) != len(answers)
    ):
        raise Type6EnvironmentError("training transcript evidence is incomplete")
    payload = {
        "schema_version": "hswm-p1v2-raw-training-transcript/v1",
        "training_case_id": case_id,
        "question": question,
        "verified_complete_answer_set": list(answers),
        "operational_note": (
            "The verified outcome required inspecting every supplied document "
            "and retaining every exact attribute match instead of stopping early."
        ),
        "evidence_id": evidence_id,
        "forbidden_uses": ["future_episode", "heldout_gold", "evaluation_label"],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_l0_memory_contexts(
    *,
    question: str,
    admitted_lesson: TypedLessonV1,
    raw_training_transcript: str,
) -> dict[str, str]:
    selection = retrieve_lessons(question, (admitted_lesson,), top_k=1)
    if selection.selected_lesson_ids != (admitted_lesson.lesson_id,):
        raise Type6EnvironmentError("oracle lesson scope does not bind the target question")
    contexts = {
        "T1_typed_lesson": render_lesson_context(selection, (admitted_lesson,)),
        "T2_raw_transcript": raw_training_transcript,
        "T3_no_memory": "",
        "T4_shuffled_or_removed": "",
    }
    if set(contexts) != set(ARM_IDS):
        raise Type6EnvironmentError("memory arm set drifted")
    return contexts


def verify_type6_oracle_admission(lesson: TypedLessonV1) -> str:
    """Narrow L0 guard whose injected contradiction must be rejected."""

    lesson.verify()
    instruction = " ".join(lesson.instruction.casefold().split())
    required = ("every supplied document", "complete set", "do not stop")
    if lesson.polarity != "DO" or any(term not in instruction for term in required):
        raise Type6EnvironmentError("lesson contradicts the frozen L0 oracle action")
    forbidden = ("only the first", "single match", "one match")
    if any(term in instruction for term in forbidden):
        raise Type6EnvironmentError("lesson contradicts the frozen L0 oracle action")
    return canonical_sha256({
        "schema_version": "hswm-p1v2-type6-oracle-admission/v1",
        "lesson_id": lesson.lesson_id,
        "required_semantics": list(required),
        "forbidden_semantics": list(forbidden),
    })


__all__ = [
    "AttributeQueryV1",
    "Type6EnvironmentError",
    "build_l0_memory_contexts",
    "parse_type6_question",
    "render_training_transcript",
    "retrieve_exact_attribute_documents",
    "verify_type6_oracle_admission",
]
