from __future__ import annotations

import json

import pytest

from p1v2_type6_environment import (
    Type6EnvironmentError,
    build_l0_memory_contexts,
    parse_type6_question,
    render_training_transcript,
    retrieve_exact_attribute_documents,
    verify_type6_oracle_admission,
)
from p1v2_typed_lesson import LessonCompilePolicyV1, compile_typed_lesson


def _lesson(instruction=None):
    return compile_typed_lesson(
        {
            "schema_version": "hswm-p1v2-operational-verdict/v1",
            "source_episode_ids": ["training:1"],
            "evidence_ids": ["evidence:1"],
            "verdict_type": "GENERALIZATION",
            "scope_predicate": {
                "all_terms": ["who is", "the person whose"],
                "any_terms": ["occupation", "hobby", "date of birth", "gender"],
                "excluded_terms": [],
            },
            "instruction": instruction or (
                "Inspect every supplied document for the exact requested attribute "
                "value, return the complete set of matching document titles, and "
                "do not stop after the first match."
            ),
            "polarity": "DO",
            "confidence": 1.0,
            "supersedes": [],
        },
        LessonCompilePolicyV1(
            allowed_episode_ids=("training:1",),
            allowed_evidence_ids=("evidence:1",),
        ),
    )


def _articles():
    return [
        {
            "title": "Alice",
            "article": "# Alice\n\nThe occupation of Alice is futures trader.\n",
        },
        {
            "title": "Bob",
            "article": "# Bob\n\nThe occupation of Bob is futures trader.\n",
        },
        {
            "title": "Carol",
            "article": "# Carol\n\nThe occupation of Carol is baker.\n",
        },
    ]


def test_public_question_drives_exact_fixed_retrieval_without_gold():
    question = "Who is the person whose occupation is futures trader?"
    parsed = parse_type6_question(question)
    documents = retrieve_exact_attribute_documents(question, _articles())

    assert parsed.attribute == "occupation"
    assert parsed.value == "futures trader"
    assert {document.title for document in documents} == {"Alice", "Bob"}
    assert all(document.source_id.startswith("phantom:") for document in documents)


def test_training_transcript_and_typed_context_are_four_arm_and_sealed_safe():
    transcript = render_training_transcript(
        case_id="training:1",
        question="Who is the person whose occupation is baker?",
        verified_gold_answers=("Carol",),
        evidence_id="evidence:1",
    )
    contexts = build_l0_memory_contexts(
        question="Who is the person whose occupation is futures trader?",
        admitted_lesson=_lesson(),
        raw_training_transcript=transcript,
    )

    assert set(contexts) == {
        "T1_typed_lesson", "T2_raw_transcript", "T3_no_memory", "T4_shuffled_or_removed"
    }
    assert json.loads(contexts["T2_raw_transcript"])["training_case_id"] == "training:1"
    assert "Carol" in contexts["T2_raw_transcript"]
    assert "Alice" not in "".join(contexts.values())
    assert contexts["T3_no_memory"] == contexts["T4_shuffled_or_removed"] == ""
    assert len(verify_type6_oracle_admission(_lesson())) == 64


def test_retrieval_cap_and_contradicted_oracle_fail_closed():
    with pytest.raises(Type6EnvironmentError, match="retrieval cut"):
        retrieve_exact_attribute_documents(
            "Who is the person whose occupation is futures trader?",
            _articles(),
            top_k=1,
        )
    contradicted = _lesson(
        "Inspect every supplied document but return only the first matching title; "
        "do not stop after the first match and call that the complete set."
    )
    with pytest.raises(Type6EnvironmentError, match="contradicts"):
        verify_type6_oracle_admission(contradicted)
