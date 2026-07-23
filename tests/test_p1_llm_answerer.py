from __future__ import annotations

import json

import pytest

from p1_llm_answerer import (
    P1AnswerError,
    P1AnswererConfigV1,
    RecordedP1Answerer,
    RetrievedDocumentV1,
)


def _config():
    return P1AnswererConfigV1(
        endpoint="http://127.0.0.1:18002/v1",
        model="fixed-model",
        model_revision="revision-1",
        deployment_receipt_sha256="1" * 64,
    )


def _response(content):
    return json.dumps(
        {
            "model": "fixed-model",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(content)},
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
    )


def test_answer_is_recorded_replayed_and_request_has_no_gold_channel(tmp_path):
    calls = []

    def transport(endpoint, body, timeout):
        calls.append((endpoint, body, timeout))
        return _response(
            {"answers": ["Alice"], "support_source_ids": ["source:1"]}
        )

    documents = (
        RetrievedDocumentV1("source:1", "Alice", "Alice is Bob's mother."),
    )
    with RecordedP1Answerer(
        tmp_path / "answers.sqlite3", config=_config(), transport=transport
    ) as answerer:
        first = answerer.answer("Who is Bob's mother?", documents)
        second = answerer.answer("Who is Bob's mother?", documents)

    assert first == second
    assert first.answers == ("Alice",)
    assert first.support_source_ids == ("source:1",)
    assert len(calls) == 1
    request_text = json.dumps(calls[0][1], sort_keys=True).casefold()
    assert "gold" not in request_text
    assert "sealed" not in request_text
    assert "solution_trace" not in request_text


def test_answer_rejects_support_source_outside_retrieved_cut(tmp_path):
    def transport(_endpoint, _body, _timeout):
        return _response(
            {"answers": ["Mallory"], "support_source_ids": ["source:missing"]}
        )

    with RecordedP1Answerer(
        tmp_path / "answers.sqlite3", config=_config(), transport=transport
    ) as answerer:
        with pytest.raises(P1AnswerError, match="unknown source"):
            answerer.answer(
                "Who?", (RetrievedDocumentV1("source:1", "Alice", "Alice text"),)
            )
        with pytest.raises(P1AnswerError, match="prior answer call failed"):
            answerer.answer(
                "Who?", (RetrievedDocumentV1("source:1", "Alice", "Alice text"),)
            )
