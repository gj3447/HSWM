"""Durable OpenAI-compatible answer port for the P1v2 four-arm harness.

The public call accepts the already-rendered user prompt, never evaluator state.
It validates that prompt against the explicit question and retrieved document
cut, records START before transport, and replays a completed idempotency key
without another model call.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from hswm_weight_snapshot import canonical_json_bytes, canonical_sha256
from p1_llm_answerer import (
    P1AnswerError,
    P1AnswererConfigV1,
    RetrievedDocumentV1,
    Transport,
    urllib_transport,
)
from p1v2_l0_harness import L0AnswerReceiptV1
from p1v2_prompt_parity import ARM_IDS


PROMPT_SCHEMA_VERSION = "hswm-p1v2-answer-input/v1"
P1V2_SYSTEM_PROMPT = """You answer questions using only the supplied retrieved documents.
The memory_context may contain a prior operational lesson, a raw transcript, no
memory, or a control lesson. Treat it only as an answering instruction and never
as evidence. Return one strict JSON object with exactly two keys: "answers" and
"support_source_ids". answers is a deduplicated JSON array of the shortest exact
answer strings supported by the documents. support_source_ids is a deduplicated
JSON array containing only supplied source_id values actually used. Do not emit
reasoning, markdown, outside knowledge, or any other keys. If the documents do
not support an answer, return both arrays empty."""
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class P1V2AnswerError(P1AnswerError):
    pass


class P1V2IndeterminateAnswerError(P1V2AnswerError):
    pass


class _DuplicateKey(ValueError):
    pass


def _strict_loads(raw: str, label: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            if key in value:
                raise _DuplicateKey(key)
            value[key] = item
        return value

    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (json.JSONDecodeError, _DuplicateKey) as error:
        raise P1V2AnswerError(f"{label} is not strict JSON: {error}") from error


TokenCounter = Callable[[str], int]


class RecordedP1V2Answerer:
    def __init__(
        self,
        path: str | Path,
        *,
        config: P1AnswererConfigV1,
        count_user_prompt_tokens: TokenCounter,
        tokenizer_identity: str,
        transport: Transport = urllib_transport,
    ) -> None:
        if not callable(count_user_prompt_tokens):
            raise P1V2AnswerError("prompt token counter must be callable")
        if not isinstance(tokenizer_identity, str) or not tokenizer_identity.strip():
            raise P1V2AnswerError("tokenizer identity must be non-empty")
        self.config = config
        self.transport = transport
        self._count_user_prompt_tokens = count_user_prompt_tokens
        self.tokenizer_identity = tokenizer_identity.strip()
        self.adapter_identity = canonical_sha256({
            "schema_version": "hswm-p1v2-recorded-answerer/v1",
            "model": config.model,
            "model_revision": config.model_revision,
            "deployment_receipt_sha256": config.deployment_receipt_sha256,
            "tokenizer_identity": self.tokenizer_identity,
            "system_prompt_sha256": canonical_sha256({"prompt": P1V2_SYSTEM_PROMPT}),
        })
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(path), isolation_level=None, timeout=10.0, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA busy_timeout=10000")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS p1v2_answer_requests (
                idempotency_key TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('STARTED', 'COMPLETE', 'ERROR')),
                canonical_request BLOB NOT NULL,
                canonical_receipt BLOB,
                error_class TEXT
            )
            """
        )

    @staticmethod
    def _validate_user_prompt(
        user_prompt: str,
        *,
        question: str,
        documents: Sequence[RetrievedDocumentV1],
    ) -> None:
        if not isinstance(user_prompt, str) or not user_prompt:
            raise P1V2AnswerError("user prompt must be non-empty text")
        value = _strict_loads(user_prompt, "user prompt")
        required = {"schema_version", "question", "documents", "memory_context"}
        if not isinstance(value, dict) or set(value) != required:
            raise P1V2AnswerError("user prompt must contain exactly the frozen keys")
        if value["schema_version"] != PROMPT_SCHEMA_VERSION:
            raise P1V2AnswerError("user prompt schema version drifted")
        expected_documents = [document.canonical() for document in documents]
        if value["question"] != question or value["documents"] != expected_documents:
            raise P1V2AnswerError("user prompt differs from the explicit retrieval cut")
        if not isinstance(value["memory_context"], str):
            raise P1V2AnswerError("memory context must be text")
        if canonical_json_bytes(value).decode("utf-8") != user_prompt:
            raise P1V2AnswerError("user prompt bytes are not canonical")
        forbidden = {"gold_answer", "evaluation_label", "solution_trace", "sealed_gold"}
        lowered_keys = {key.casefold() for key in _recursive_keys(value)}
        if forbidden & lowered_keys:
            raise P1V2AnswerError("user prompt crossed the evaluator boundary")

    def _request_body(self, user_prompt: str) -> dict[str, object]:
        return {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": P1V2_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "top_p": 1.0,
            "seed": self.config.seed,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def _receipt_from_raw(
        self,
        *,
        arm_id: str,
        idempotency_key: str,
        raw: str,
        allowed_source_ids: frozenset[str],
        user_prompt_tokens: int,
    ) -> L0AnswerReceiptV1:
        response = _strict_loads(raw, "OpenAI response")
        try:
            choices = response["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise TypeError
            choice = choices[0]
            if choice.get("finish_reason") != "stop":
                raise P1V2AnswerError("answer response did not finish with stop")
            content = choice["message"]["content"]
            response_model = response["model"]
            usage = response["usage"]
        except (KeyError, TypeError, AttributeError) as error:
            raise P1V2AnswerError("OpenAI response schema mismatch") from error
        if not isinstance(content, str) or response_model != self.config.model:
            raise P1V2AnswerError("answer response content or model drifted")
        if (
            not isinstance(usage, Mapping)
            or not isinstance(usage.get("prompt_tokens"), int)
            or isinstance(usage.get("prompt_tokens"), bool)
            or usage["prompt_tokens"] != user_prompt_tokens
        ):
            raise P1V2AnswerError(
                "server prompt-token usage differs from the frozen tokenizer count"
            )
        payload = _strict_loads(content, "answer content")
        if not isinstance(payload, dict) or set(payload) != {
            "answers", "support_source_ids"
        }:
            raise P1V2AnswerError("answer content must have exactly two frozen keys")
        answers = payload["answers"]
        support = payload["support_source_ids"]
        if (
            not isinstance(answers, list)
            or not isinstance(support, list)
            or any(not isinstance(item, str) or not item for item in answers + support)
            or len(set(answers)) != len(answers)
            or len(set(support)) != len(support)
            or not set(support).issubset(allowed_source_ids)
        ):
            raise P1V2AnswerError("answer arrays are invalid or cite an unknown source")
        return L0AnswerReceiptV1(
            arm_id=arm_id,
            request_sha256=idempotency_key,
            answers=tuple(answers),
            user_prompt_tokens=user_prompt_tokens,
        )

    @staticmethod
    def _receipt_dict(receipt: L0AnswerReceiptV1) -> dict[str, object]:
        return {
            "schema_version": "hswm-p1v2-recorded-answer-receipt/v1",
            "arm_id": receipt.arm_id,
            "request_sha256": receipt.request_sha256,
            "answers": list(receipt.answers),
            "user_prompt_tokens": receipt.user_prompt_tokens,
            "logical_call_count": receipt.logical_call_count,
        }

    @staticmethod
    def _parse_cached(raw: bytes) -> L0AnswerReceiptV1:
        value = _strict_loads(raw.decode("utf-8"), "cached P1v2 receipt")
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "arm_id",
            "request_sha256",
            "answers",
            "user_prompt_tokens",
            "logical_call_count",
        }:
            raise P1V2AnswerError("cached P1v2 receipt schema mismatch")
        if value["schema_version"] != "hswm-p1v2-recorded-answer-receipt/v1":
            raise P1V2AnswerError("cached P1v2 receipt version drifted")
        return L0AnswerReceiptV1(
            arm_id=value["arm_id"],
            request_sha256=value["request_sha256"],
            answers=tuple(value["answers"]),
            user_prompt_tokens=value["user_prompt_tokens"],
            logical_call_count=value["logical_call_count"],
        )

    def answer(
        self,
        *,
        arm_id: str,
        question: str,
        documents: Sequence[RetrievedDocumentV1],
        user_prompt: str,
        idempotency_key: str,
    ) -> L0AnswerReceiptV1:
        if arm_id not in ARM_IDS:
            raise P1V2AnswerError("arm is outside the registered four-arm protocol")
        if not isinstance(question, str) or not question:
            raise P1V2AnswerError("question must be non-empty text")
        docs = tuple(documents)
        if not docs or len({document.source_id for document in docs}) != len(docs):
            raise P1V2AnswerError("documents must be non-empty with unique source IDs")
        if not isinstance(idempotency_key, str) or not _SHA256.fullmatch(idempotency_key):
            raise P1V2AnswerError("idempotency key must be a lowercase SHA-256")
        self._validate_user_prompt(user_prompt, question=question, documents=docs)
        user_prompt_tokens = self._count_user_prompt_tokens(user_prompt)
        if (
            not isinstance(user_prompt_tokens, int)
            or isinstance(user_prompt_tokens, bool)
            or user_prompt_tokens <= 0
        ):
            raise P1V2AnswerError("token counter must return a positive integer")
        body = self._request_body(user_prompt)
        request_envelope = {
            "idempotency_key": idempotency_key,
            "arm_id": arm_id,
            "adapter_identity": self.adapter_identity,
            "request_body": body,
        }
        request_raw = canonical_json_bytes(request_envelope)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM p1v2_answer_requests WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is not None:
                if bytes(row["canonical_request"]) != request_raw:
                    raise P1V2AnswerError("idempotency key carries different request bytes")
                if row["status"] == "COMPLETE":
                    return self._parse_cached(bytes(row["canonical_receipt"]))
                if row["status"] == "STARTED":
                    raise P1V2IndeterminateAnswerError(
                        "prior P1v2 call has no final receipt"
                    )
                raise P1V2AnswerError(
                    f"prior P1v2 call failed: {row['error_class']}"
                )
            self._connection.execute(
                """
                INSERT INTO p1v2_answer_requests(
                    idempotency_key, status, canonical_request
                ) VALUES (?, 'STARTED', ?)
                """,
                (idempotency_key, request_raw),
            )
        try:
            raw = self.transport(
                self.config.endpoint, body, self.config.timeout_seconds
            )
            receipt = self._receipt_from_raw(
                arm_id=arm_id,
                idempotency_key=idempotency_key,
                raw=raw,
                allowed_source_ids=frozenset(document.source_id for document in docs),
                user_prompt_tokens=user_prompt_tokens,
            )
        except BaseException as error:
            with self._lock:
                self._connection.execute(
                    """
                    UPDATE p1v2_answer_requests SET status = 'ERROR', error_class = ?
                    WHERE idempotency_key = ? AND status = 'STARTED'
                    """,
                    (type(error).__name__, idempotency_key),
                )
            raise
        with self._lock:
            updated = self._connection.execute(
                """
                UPDATE p1v2_answer_requests
                SET status = 'COMPLETE', canonical_receipt = ?
                WHERE idempotency_key = ? AND status = 'STARTED'
                """,
                (canonical_json_bytes(self._receipt_dict(receipt)), idempotency_key),
            )
            if updated.rowcount != 1:
                raise P1V2AnswerError("P1v2 answer finalization lost START receipt")
        return receipt

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "RecordedP1V2Answerer":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _recursive_keys(value: object):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _recursive_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _recursive_keys(item)


__all__ = [
    "P1V2AnswerError",
    "P1V2IndeterminateAnswerError",
    "P1V2_SYSTEM_PROMPT",
    "RecordedP1V2Answerer",
]
