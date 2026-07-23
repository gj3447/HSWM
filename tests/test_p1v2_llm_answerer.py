from __future__ import annotations

import json

import pytest

from p1_llm_answerer import P1AnswererConfigV1, RetrievedDocumentV1
from p1v2_l0_harness import render_answer_prompt
from p1v2_llm_answerer import P1V2AnswerError, RecordedP1V2Answerer


def _config():
    return P1AnswererConfigV1(
        endpoint="http://127.0.0.1:18002/v1",
        model="fixed-model",
        model_revision="revision-1",
        deployment_receipt_sha256="1" * 64,
    )


def _response(content, *, model="fixed-model"):
    return json.dumps({
        "model": model,
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(content)},
        }],
        "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
    })


def _call(answerer, *, key="a" * 64, prompt=None):
    documents = (RetrievedDocumentV1("source:1", "Alice", "Alice is a scientist."),)
    question = "Who is a scientist?"
    return answerer.answer(
        arm_id="T1_typed_lesson",
        question=question,
        documents=documents,
        user_prompt=prompt or render_answer_prompt(question, documents, "Enumerate all matches."),
        idempotency_key=key,
    )


def test_recorded_answer_replays_once_and_has_no_evaluator_channel(tmp_path):
    calls = []

    def transport(endpoint, body, timeout):
        calls.append((endpoint, body, timeout))
        return _response({"answers": ["Alice"], "support_source_ids": ["source:1"]})

    with RecordedP1V2Answerer(
        tmp_path / "p1v2.sqlite3",
        config=_config(),
        count_user_prompt_tokens=lambda _text: 20,
        tokenizer_identity="fixture-byte-tokenizer:v1",
        transport=transport,
    ) as answerer:
        first = _call(answerer)
        second = _call(answerer)

    assert first == second
    assert first.answers == ("Alice",)
    assert first.request_sha256 == "a" * 64
    assert len(calls) == 1
    request_text = json.dumps(calls[0][1], sort_keys=True).casefold()
    assert "gold_answer" not in request_text
    assert "evaluation_label" not in request_text
    assert "solution_trace" not in request_text


def test_answer_rejects_prompt_cut_drift_and_unknown_support(tmp_path):
    def transport(_endpoint, _body, _timeout):
        return _response({"answers": ["Mallory"], "support_source_ids": ["missing"]})

    with RecordedP1V2Answerer(
        tmp_path / "p1v2.sqlite3",
        config=_config(),
        count_user_prompt_tokens=lambda _text: 20,
        tokenizer_identity="fixture-character-tokenizer:v1",
        transport=transport,
    ) as answerer:
        documents = (RetrievedDocumentV1("source:1", "Alice", "Alice text"),)
        drifted = render_answer_prompt("Different question", documents, "lesson")
        with pytest.raises(P1V2AnswerError, match="retrieval cut"):
            _call(answerer, prompt=drifted)
        with pytest.raises(P1V2AnswerError, match="unknown source"):
            _call(answerer)
        with pytest.raises(P1V2AnswerError, match="prior P1v2 call failed"):
            _call(answerer)


def test_answer_rejects_noncanonical_prompt_and_model_drift(tmp_path):
    documents = (
        RetrievedDocumentV1("source:1", "Alice", "Alice is a scientist."),
    )
    noncanonical = json.dumps({
        "schema_version": "hswm-p1v2-answer-input/v1",
        "question": "Who is a scientist?",
        "documents": [documents[0].canonical()],
        "memory_context": "lesson",
    }, indent=2)

    with RecordedP1V2Answerer(
        tmp_path / "p1v2.sqlite3",
        config=_config(),
        count_user_prompt_tokens=lambda _text: 20,
        tokenizer_identity="fixture-character-tokenizer:v1",
        transport=lambda *_args: _response(
            {"answers": ["Alice"], "support_source_ids": ["source:1"]},
            model="drifted-model",
        ),
    ) as answerer:
        with pytest.raises(P1V2AnswerError, match="not canonical"):
            _call(answerer, prompt=noncanonical)
        with pytest.raises(P1V2AnswerError, match="model drifted"):
            _call(answerer, key="b" * 64)
