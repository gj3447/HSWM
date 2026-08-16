"""Recorded fixed OpenAI-compatible answerer for the HSWM P1 loop.

The request schema contains only the question and retrieved documents.  Sealed
answers, traces, labels, and evaluator state are not representable.  Every
request is content-addressed and first-written to SQLite before transport; a
crash after START is fail-closed as indeterminate rather than silently called
again.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable, Mapping, Sequence
from urllib import request as urllib_request

from hswm_weight_snapshot import canonical_json_bytes, canonical_sha256


ANSWER_SCHEMA_VERSION = "hswm-p1-llm-answer/v1"
PROMPT_VERSION = "hswm-p1-answer-prompt/v1"
SYSTEM_PROMPT = """You answer questions using only the supplied retrieved documents.
Return one strict JSON object with exactly two keys: "answers" and
"support_source_ids". answers is a deduplicated JSON array of the shortest exact
answer strings supported by the documents. support_source_ids is a deduplicated
JSON array containing only supplied source_id values actually used. Do not emit
reasoning, markdown, outside knowledge, or any other keys. If the documents do
not support an answer, return both arrays empty."""


class P1AnswerError(RuntimeError):
    pass


class IndeterminateAnswerError(P1AnswerError):
    pass


class _DuplicateKey(ValueError):
    pass


def _strict_loads(raw: str, label: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise _DuplicateKey(key)
            out[key] = value
        return out

    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (json.JSONDecodeError, _DuplicateKey) as error:
        raise P1AnswerError(f"{label} is not strict JSON: {error}") from error


@dataclass(frozen=True, order=True)
class RetrievedDocumentV1:
    source_id: str
    title: str
    text: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.title or not self.text:
            raise P1AnswerError("retrieved document fields must be non-empty")

    def canonical(self) -> dict[str, str]:
        return {"source_id": self.source_id, "title": self.title, "text": self.text}


@dataclass(frozen=True)
class P1AnswererConfigV1:
    endpoint: str
    model: str
    model_revision: str
    deployment_receipt_sha256: str
    timeout_seconds: float = 180.0
    max_tokens: int = 256
    seed: int = 9173
    temperature: int = 0
    disable_thinking: bool = True

    def __post_init__(self) -> None:
        if not self.endpoint.startswith(("http://", "https://")):
            raise P1AnswerError("endpoint must be HTTP(S)")
        if not self.endpoint.rstrip("/").endswith("/v1"):
            raise P1AnswerError("endpoint path must end in /v1")
        if not self.model or not self.model_revision:
            raise P1AnswerError("model identity must be non-empty")
        if (
            len(self.deployment_receipt_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.deployment_receipt_sha256)
        ):
            raise P1AnswerError("deployment receipt must be a lowercase SHA-256")
        if self.timeout_seconds <= 0 or self.max_tokens <= 0:
            raise P1AnswerError("timeout and max_tokens must be positive")
        if self.temperature != 0 or not self.disable_thinking:
            raise P1AnswerError("P1 answerer requires temperature=0 and thinking disabled")

    def canonical(self) -> dict[str, object]:
        return {
            "endpoint": self.endpoint.rstrip("/"),
            "model": self.model,
            "model_revision": self.model_revision,
            "deployment_receipt_sha256": self.deployment_receipt_sha256,
            "timeout_seconds": self.timeout_seconds,
            "max_tokens": self.max_tokens,
            "seed": self.seed,
            "temperature": self.temperature,
            "disable_thinking": self.disable_thinking,
        }


@dataclass(frozen=True)
class AnswerReceiptV1:
    receipt_id: str
    request_sha256: str
    response_sha256: str
    content_sha256: str
    response_model: str
    answers: tuple[str, ...]
    support_source_ids: tuple[str, ...]
    usage: Mapping[str, int]
    deployment_receipt_sha256: str
    schema_version: str = ANSWER_SCHEMA_VERSION

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_sha256": self.request_sha256,
            "response_sha256": self.response_sha256,
            "content_sha256": self.content_sha256,
            "response_model": self.response_model,
            "answers": list(self.answers),
            "support_source_ids": list(self.support_source_ids),
            "usage": dict(self.usage),
            "deployment_receipt_sha256": self.deployment_receipt_sha256,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


Transport = Callable[[str, Mapping[str, object], float], str]


def urllib_transport(endpoint: str, body: Mapping[str, object], timeout: float) -> str:
    request = urllib_request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=canonical_json_bytes(body),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status = int(response.status)
    except Exception as error:
        raise P1AnswerError(f"answer transport failed: {type(error).__name__}") from error
    if status != 200:
        raise P1AnswerError(f"answer endpoint returned HTTP {status}")
    return raw


class RecordedP1Answerer:
    def __init__(
        self,
        path: str | Path,
        *,
        config: P1AnswererConfigV1,
        transport: Transport = urllib_transport,
    ) -> None:
        self.config = config
        self.transport = transport
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
            CREATE TABLE IF NOT EXISTS p1_answer_requests (
                request_sha256 TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('STARTED', 'COMPLETE', 'ERROR')),
                canonical_request BLOB NOT NULL,
                canonical_receipt BLOB,
                error_class TEXT
            )
            """
        )

    def _request(
        self, question: str, documents: Sequence[RetrievedDocumentV1]
    ) -> tuple[str, dict[str, object]]:
        if not isinstance(question, str) or not question:
            raise P1AnswerError("question must be non-empty text")
        docs = tuple(documents)
        if not docs or len({doc.source_id for doc in docs}) != len(docs):
            raise P1AnswerError("documents must be non-empty with unique source IDs")
        input_payload = {
            "schema_version": PROMPT_VERSION,
            "question": question,
            "documents": [doc.canonical() for doc in docs],
        }
        body: dict[str, object] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": canonical_json_bytes(input_payload).decode("utf-8"),
                },
            ],
            "temperature": 0,
            "top_p": 1.0,
            "seed": self.config.seed,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        envelope = {
            "prompt_version": PROMPT_VERSION,
            "config": self.config.canonical(),
            "request_body": body,
        }
        return canonical_sha256(envelope), body

    def _receipt_from_raw(
        self,
        request_sha: str,
        raw: str,
        allowed_source_ids: frozenset[str],
    ) -> AnswerReceiptV1:
        response = _strict_loads(raw, "OpenAI response")
        try:
            choices = response["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise TypeError
            choice = choices[0]
            if choice.get("finish_reason") != "stop":
                raise P1AnswerError("answer response did not finish with stop")
            content = choice["message"]["content"]
            response_model = response["model"]
            usage_value = response.get("usage") or {}
        except (KeyError, TypeError, AttributeError) as error:
            raise P1AnswerError("OpenAI response schema mismatch") from error
        if not isinstance(content, str) or not isinstance(response_model, str):
            raise P1AnswerError("OpenAI response content/model schema mismatch")
        if response_model != self.config.model:
            raise P1AnswerError("answer response model differs from frozen model")
        payload = _strict_loads(content, "answer content")
        if not isinstance(payload, dict) or set(payload) != {"answers", "support_source_ids"}:
            raise P1AnswerError("answer content must have exactly two frozen keys")
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
            raise P1AnswerError("answer arrays are invalid or cite an unknown source")
        if not isinstance(usage_value, Mapping):
            raise P1AnswerError("usage must be an object")
        usage: dict[str, int] = {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage_value.get(key, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise P1AnswerError("usage counters must be non-negative integers")
            usage[key] = value
        unsigned = {
            "schema_version": ANSWER_SCHEMA_VERSION,
            "request_sha256": request_sha,
            "response_sha256": canonical_sha256(response),
            "content_sha256": canonical_sha256(payload),
            "response_model": response_model,
            "answers": answers,
            "support_source_ids": support,
            "usage": usage,
            "deployment_receipt_sha256": self.config.deployment_receipt_sha256,
        }
        return AnswerReceiptV1(
            receipt_id=canonical_sha256(unsigned),
            request_sha256=request_sha,
            response_sha256=str(unsigned["response_sha256"]),
            content_sha256=str(unsigned["content_sha256"]),
            response_model=response_model,
            answers=tuple(answers),
            support_source_ids=tuple(support),
            usage=usage,
            deployment_receipt_sha256=self.config.deployment_receipt_sha256,
        )

    @staticmethod
    def _parse_cached(raw: bytes) -> AnswerReceiptV1:
        value = _strict_loads(raw.decode("utf-8"), "cached answer receipt")
        receipt = AnswerReceiptV1(
            receipt_id=value["receipt_id"],
            request_sha256=value["request_sha256"],
            response_sha256=value["response_sha256"],
            content_sha256=value["content_sha256"],
            response_model=value["response_model"],
            answers=tuple(value["answers"]),
            support_source_ids=tuple(value["support_source_ids"]),
            usage=value["usage"],
            deployment_receipt_sha256=value["deployment_receipt_sha256"],
            schema_version=value["schema_version"],
        )
        if receipt.receipt_id != canonical_sha256(receipt.unsigned()):
            raise P1AnswerError("cached answer receipt digest mismatch")
        return receipt

    def answer(
        self, question: str, documents: Sequence[RetrievedDocumentV1]
    ) -> AnswerReceiptV1:
        request_sha, body = self._request(question, documents)
        request_raw = canonical_json_bytes(body)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM p1_answer_requests WHERE request_sha256 = ?",
                (request_sha,),
            ).fetchone()
            if row is not None:
                if bytes(row["canonical_request"]) != request_raw:
                    raise P1AnswerError("request identity carries different bytes")
                if row["status"] == "COMPLETE":
                    return self._parse_cached(bytes(row["canonical_receipt"]))
                if row["status"] == "STARTED":
                    raise IndeterminateAnswerError("prior answer call has no final receipt")
                raise P1AnswerError(f"prior answer call failed: {row['error_class']}")
            self._connection.execute(
                """
                INSERT INTO p1_answer_requests(
                    request_sha256, status, canonical_request
                ) VALUES (?, 'STARTED', ?)
                """,
                (request_sha, request_raw),
            )
        try:
            raw = self.transport(
                self.config.endpoint, body, self.config.timeout_seconds
            )
            receipt = self._receipt_from_raw(
                request_sha,
                raw,
                frozenset(document.source_id for document in documents),
            )
        except BaseException as error:
            with self._lock:
                self._connection.execute(
                    """
                    UPDATE p1_answer_requests SET status = 'ERROR', error_class = ?
                    WHERE request_sha256 = ? AND status = 'STARTED'
                    """,
                    (type(error).__name__, request_sha),
                )
            raise
        with self._lock:
            updated = self._connection.execute(
                """
                UPDATE p1_answer_requests
                SET status = 'COMPLETE', canonical_receipt = ?
                WHERE request_sha256 = ? AND status = 'STARTED'
                """,
                (canonical_json_bytes(receipt.canonical()), request_sha),
            )
            if updated.rowcount != 1:
                raise P1AnswerError("answer finalization lost its START receipt")
        return receipt

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def cache_stats(self) -> dict[str, int]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT status, COUNT(*) AS n FROM p1_answer_requests GROUP BY status"
            ).fetchall()
        counts = {"STARTED": 0, "COMPLETE": 0, "ERROR": 0}
        counts.update({str(row["status"]): int(row["n"]) for row in rows})
        return counts

    def __enter__(self) -> "RecordedP1Answerer":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = [
    "AnswerReceiptV1",
    "IndeterminateAnswerError",
    "P1AnswerError",
    "P1AnswererConfigV1",
    "RecordedP1Answerer",
    "RetrievedDocumentV1",
    "SYSTEM_PROMPT",
    "urllib_transport",
]
