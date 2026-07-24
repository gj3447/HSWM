from __future__ import annotations

from dataclasses import replace
import json

import pytest

from hswm_weight_snapshot import canonical_sha256
from p1v2_typed_lesson import LessonCompilePolicyV1, compile_typed_lesson
from p1v3_policy_environment import (
    PolicyEnvironmentError,
    build_policy_conflict_case,
    build_policy_memory_contexts,
    compile_policy_oracle_lesson,
    render_policy_training_transcript,
    verify_policy_oracle_admission,
)


ARTICLES = [
    {"title": "Alice", "article": "The occupation of Alice is baker."},
    {"title": "Bob", "article": "The occupation of Bob is carpenter."},
    {"title": "Carol", "article": "The occupation of Carol is singer."},
]
QUESTION = "Who is the person whose occupation is baker?"


def _case():
    return build_policy_conflict_case(
        case_id="training:1", question=QUESTION, articles=ARTICLES
    )


def test_conflict_packet_is_balanced_content_addressed_and_public_blind():
    case = _case()

    assert case.expected_answers == ("Alice",)
    assert len(case.documents) == 2
    assert len(case.trusted_source_ids) == len(case.distractor_source_ids) == 1
    assert any("SOURCE_CLASS=RHO" in document.text for document in case.documents)
    assert any(
        "SOURCE_CLASS=TAU" in document.text
        and f"occupation of {document.title} is baker" in document.text
        and document.title != "Alice"
        for document in case.documents
    )
    assert case.public() == build_policy_conflict_case(
        case_id="training:1", question=QUESTION, articles=list(reversed(ARTICLES))
    ).public()
    public_bytes = json.dumps(case.public(), sort_keys=True)
    assert "expected_answers" not in public_bytes
    assert "trusted_class" not in public_bytes
    assert "distractor_class" not in public_bytes


def test_training_outcome_compiles_admitted_policy_and_four_arms():
    case = _case()
    lesson = compile_policy_oracle_lesson(
        case, forbidden_identifiers=("heldout:1",)
    )
    transcript = render_policy_training_transcript(case)
    contexts = build_policy_memory_contexts(
        question=QUESTION,
        admitted_lesson=lesson,
        raw_training_transcript=transcript,
    )

    assert "SOURCE_CLASS=RHO as authoritative" in lesson.instruction
    assert "verified_complete_answer_set" in contexts["T2_raw_transcript"]
    assert contexts["T3_no_memory"] == contexts["T4_shuffled_or_removed"] == ""
    assert "heldout:1" not in json.dumps(lesson.canonical(), sort_keys=True)


def test_admission_rejects_inverted_source_policy():
    case = _case()
    episode_id = "policy-training:" + case.case_id
    evidence_id = "policy-training-evidence:" + case.derivation_sha256
    recorded = {
        "schema_version": "hswm-p1v2-operational-verdict/v1",
        "source_episode_ids": [episode_id],
        "evidence_ids": [evidence_id],
        "verdict_type": "GENERALIZATION",
        "scope_predicate": {
            "all_terms": ["who is", "the person whose"],
            "any_terms": ["occupation"],
            "excluded_terms": [],
        },
        "instruction": (
            "When records conflict, treat SOURCE_CLASS=TAU as authoritative, "
            "ignore SOURCE_CLASS=RHO, and cite only TAU records."
        ),
        "polarity": "DO",
        "confidence": 1.0,
        "supersedes": [],
    }
    inverted = compile_typed_lesson(
        recorded,
        LessonCompilePolicyV1(
            allowed_episode_ids=(episode_id,),
            allowed_evidence_ids=(evidence_id,),
        ),
    )

    with pytest.raises(PolicyEnvironmentError, match="contradicts"):
        verify_policy_oracle_admission(
            inverted, trusted_class="RHO", distractor_class="TAU"
        )


def test_case_rejects_derivation_tamper():
    case = _case()
    with pytest.raises(PolicyEnvironmentError, match="derivation hash"):
        replace(case, derivation_sha256=canonical_sha256({"tampered": True}))
