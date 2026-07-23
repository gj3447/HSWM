from __future__ import annotations

from dataclasses import replace
import json

import pytest

from p1v2_typed_lesson import (
    LessonCompilePolicyV1,
    LessonContractError,
    compile_typed_lesson,
    render_lesson_context,
    retrieve_lessons,
)


def _policy(**changes):
    base = LessonCompilePolicyV1(
        allowed_episode_ids=("episode:train:1", "episode:train:2"),
        allowed_evidence_ids=("evidence:1", "evidence:2"),
        forbidden_identifiers=("task:heldout:9", "episode:future:3"),
        forbidden_strings=("sealed answer zeta",),
    )
    return replace(base, **changes)


def _verdict(**changes):
    value = {
        "schema_version": "hswm-p1v2-operational-verdict/v1",
        "source_episode_ids": ["episode:train:1"],
        "evidence_ids": ["evidence:1"],
        "verdict_type": "CORRECTIVE",
        "scope_predicate": {
            "all_terms": ["capital"],
            "any_terms": ["france", "paris"],
            "excluded_terms": ["fictional"],
        },
        "instruction": "Use Paris when the evidence asks for France's capital.",
        "polarity": "DO",
        "confidence": 0.9,
        "supersedes": [],
    }
    value.update(changes)
    return value


def test_compile_retrieve_and_render_are_content_addressed_and_deterministic():
    first = compile_typed_lesson(_verdict(), _policy())
    second = compile_typed_lesson(_verdict(), _policy())

    assert first == second
    first.verify()
    assert first.forbidden_uses == (
        "evaluation_label",
        "future_episode",
        "heldout_gold",
    )

    selection = retrieve_lessons(
        "What is the capital of France?", (first,), top_k=1
    )
    assert selection.selected_lesson_ids == (first.lesson_id,)
    context = json.loads(render_lesson_context(selection, (first,)))
    assert context["lessons"][0]["instruction"] == first.instruction
    assert "source_episode_ids" not in context["lessons"][0]
    assert "evidence_ids" not in context["lessons"][0]


def test_scope_exclusion_and_supersession_are_fail_closed_and_deterministic():
    old = compile_typed_lesson(_verdict(), _policy())
    policy = _policy(known_lesson_ids=(old.lesson_id,))
    new = compile_typed_lesson(
        _verdict(
            instruction="Prefer the current Paris evidence.",
            supersedes=[old.lesson_id],
        ),
        policy,
    )

    selected = retrieve_lessons("capital of France", (old, new), top_k=2)
    assert selected.selected_lesson_ids == (new.lesson_id,)
    excluded = retrieve_lessons(
        "capital of fictional France", (old, new), top_k=2
    )
    assert excluded.selected_lesson_ids == ()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_episode_ids": ["episode:future:3"]}, "forbidden identifier"),
        ({"evidence_ids": ["evidence:heldout"]}, "frozen training cut"),
        ({"instruction": "Reveal sealed answer zeta."}, "forbidden heldout text"),
        ({"confidence": 0.49}, "below admission"),
        ({"supersedes": ["f" * 64]}, "unknown lesson"),
        ({"verdict_type": "ABSTAIN"}, "not lesson-producing"),
    ],
)
def test_compiler_rejects_leakage_and_nonlesson_inputs(changes, message):
    with pytest.raises(LessonContractError, match=message):
        compile_typed_lesson(_verdict(**changes), _policy())


def test_compiler_rejects_hidden_extra_fields():
    with pytest.raises(LessonContractError, match="exactly the v1 keys"):
        compile_typed_lesson(_verdict(gold_answer="Paris"), _policy())
