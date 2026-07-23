from __future__ import annotations

import json

import pytest

from p1_llm_answerer import RetrievedDocumentV1
from p1v2_l0_harness import (
    L0AnswerReceiptV1,
    L0HarnessError,
    build_lakato_evidence_record,
    render_answer_prompt,
    run_l0_observation,
)
from p1v2_prompt_parity import (
    PromptParityError,
    build_prompt_parity_plan,
)


class WordPadder:
    tokenizer_identity = "fixture-word-tokenizer:v1"
    padding_identity = "fixture-inert-pad:v1"

    def count_prompt_tokens(self, prompt):
        return len(prompt.split())

    def pad_memory_context(self, memory_context, *, target_prompt_tokens, render_prompt):
        padded = memory_context
        while self.count_prompt_tokens(render_prompt(padded)) < target_prompt_tokens:
            padded += " inert"
        return padded


class BadPadder(WordPadder):
    def pad_memory_context(self, memory_context, *, target_prompt_tokens, render_prompt):
        return memory_context


class FakeAnswerer:
    adapter_identity = "fake-recorded-answerer:v1"

    def __init__(self, padder):
        self.padder = padder
        self.calls = []

    def answer(
        self,
        *,
        arm_id,
        question,
        documents,
        user_prompt,
        idempotency_key,
    ):
        payload = json.loads(user_prompt)
        assert set(payload) == {
            "schema_version", "question", "documents", "memory_context"
        }
        assert "gold_answer" not in user_prompt.casefold()
        assert "evaluation_label" not in user_prompt.casefold()
        self.calls.append((arm_id, question, tuple(documents), user_prompt))
        answers = ("Paris",) if "Use Paris" in payload["memory_context"] else ("Lyon",)
        return L0AnswerReceiptV1(
            arm_id=arm_id,
            request_sha256=idempotency_key,
            answers=answers,
            user_prompt_tokens=self.padder.count_prompt_tokens(user_prompt),
        )


def _plan(padder=None):
    documents = (
        RetrievedDocumentV1("source:1", "France", "Paris is the capital of France."),
    )
    question = "What is the capital of France?"
    contexts = {
        "T1_typed_lesson": "Use Paris for supported France capital questions.",
        "T2_raw_transcript": "A prior attempt discussed France but was inconclusive.",
        "T3_no_memory": "",
        "T4_shuffled_or_removed": "Use Rome for supported Italy capital questions.",
    }
    padder = padder or WordPadder()
    plan = build_prompt_parity_plan(
        contexts,
        render_prompt=lambda context: render_answer_prompt(
            question, documents, context
        ),
        padder=padder,
    )
    return question, documents, padder, plan


def _has_verdict_key(value):
    if isinstance(value, dict):
        return "verdict" in value or any(_has_verdict_key(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_verdict_key(item) for item in value)
    return False


def test_exact_prompt_parity_and_l0_observation_keep_gold_out_of_calls():
    question, documents, padder, plan = _plan()
    assert len({padder.count_prompt_tokens(prompt) for prompt in plan.rendered_prompts.values()}) == 1

    answerer = FakeAnswerer(padder)
    observation = run_l0_observation(
        case_id="case:1",
        question=question,
        documents=documents,
        sealed_gold_answers=("Paris",),
        parity_plan=plan,
        answerer=answerer,
    )

    assert len(answerer.calls) == 4
    assert observation["measurements"] == {
        "typed_minus_no_memory": 1,
        "typed_minus_raw_transcript": 1,
        "typed_minus_shuffled_or_removed": 1,
    }
    assert observation["budget"] == {
        "logical_model_calls": 4,
        "user_prompt_tokens_per_arm": plan.target_prompt_tokens,
        "token_parity": True,
    }
    assert observation["gold_boundary"]["gold_sent_to_answer_port"] is False


def test_bad_padder_and_bad_answer_receipt_fail_before_evidence():
    with pytest.raises(PromptParityError, match="instead of"):
        _plan(BadPadder())

    question, documents, padder, plan = _plan()

    class BadAnswerer(FakeAnswerer):
        def answer(self, **kwargs):
            receipt = super().answer(**kwargs)
            return L0AnswerReceiptV1(
                arm_id=receipt.arm_id,
                request_sha256=receipt.request_sha256,
                answers=receipt.answers,
                user_prompt_tokens=receipt.user_prompt_tokens + 1,
            )

    with pytest.raises(L0HarnessError, match="token parity"):
        run_l0_observation(
            case_id="case:bad",
            question=question,
            documents=documents,
            sealed_gold_answers=("Paris",),
            parity_plan=plan,
            answerer=BadAnswerer(padder),
        )


def test_lakato_evidence_record_has_provenance_and_no_verdict():
    question, documents, padder, plan = _plan()
    observation = run_l0_observation(
        case_id="case:1",
        question=question,
        documents=documents,
        sealed_gold_answers=("Paris",),
        parity_plan=plan,
        answerer=FakeAnswerer(padder),
    )
    evidence = build_lakato_evidence_record(
        programme="LakatosTree_HSWM_20260719",
        branch="P1v2-typed-verdict-lesson",
        conjecture="typed lessons change heldout behavior",
        preregistration_sha256="1" * 64,
        prediction_receipt_sha256="2" * 64,
        data_manifest_sha256="3" * 64,
        harness_command=("python", "p1v2_l0.py"),
        harness_cwd="/frozen/hswm",
        git_commit="4" * 40,
        environment={"python": "3.11"},
        observations=(observation,),
    )

    assert evidence["schema_version"] == "lakato-evidence-record/v1"
    assert evidence["grounded_status"] == "GROUNDED_MEASUREMENT_NO_SCIENTIFIC_VERDICT"
    assert not _has_verdict_key(evidence)
    assert len(evidence["evidence_sha256"]) == 64
