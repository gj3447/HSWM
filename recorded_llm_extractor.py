"""Recorded, evidence-preserving LLM extraction orchestrator for B3.

This module is deliberately *outside* :mod:`claim_builder`.  It may call an
OpenAI-compatible endpoint, but its output crosses the trusted compiler
boundary only after every model quote has been bound to one unique source span.
The compiler itself remains offline and deterministic.

The model returns quote-only JSON::

    {"claims":[{
      "subject":"Green",
      "predicate":"was formed by",
      "arguments":[{"role":"founder","exact":"Steve Hillage"}]
    }]}

Offsets are never trusted from the model.  ``bind_unique_nfkc_quote`` resolves
each quote to exactly one Python-codepoint ``[start, end)`` span.  Missing or
ambiguous quotes are quarantined; there is no fuzzy, case-folded, or nearest
match repair.  The adapted payload is then frozen with
``claim_builder.freeze_extraction`` and can be re-verified by the compiler.

JSONL records preserve the exact raw response and all relevant preimages.  The
append path is protected by an advisory file lock, fsyncs completed records,
and truncates only an incomplete final line left by an interrupted writer.

Longinus ReferenceSite:
``HSWM/PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md``
sections 14-18 (S6 recorded LLM n-ary adapter and evidence receipts).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields, replace
from enum import StrEnum
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence
import unicodedata
from urllib import error as urllib_error
from urllib import request as urllib_request

from claim_builder import (
    EXTRACTION_SCHEMA_VERSION,
    FrozenExtractionV1,
    freeze_extraction,
)
from title_anchor_builder import ParagraphInputV1
from world_ir import canonical_json, content_id, sha256_text


SCHEMA_VERSION = "hswm-recorded-llm-extractor/v4"
JOURNAL_SCHEMA_VERSION = "hswm-recorded-llm-attempt-journal/v1"
START_EVENT = "START"
FINALIZE_EVENT = "FINALIZE"
QUOTE_SCHEMA_VERSION = "hswm-quote-claim-extraction/v1"
BINDER_VERSION = "unique-nfkc-codepoint-span/v1"
PRODUCER = "hswm-recorded-openai-compatible/v1"
OFFSET_UNIT = "unicode-codepoint-half-open-v1"

SYSTEM_PROMPT = """You are a query-blind evidence extraction component.
Return exactly one JSON object and no prose or markdown. Its only root key is
\"claims\". Each claim has exactly \"subject\", \"predicate\", and
\"arguments\". subject and predicate are non-empty exact contiguous quotes
from TEXT. arguments is a non-empty array; every item has exactly \"role\" and
\"exact\". exact is a non-empty exact contiguous quote from TEXT. A role is a
lower-case semantic token such as object, location, date, founder, recipient,
or collaborator. Choose quotes that occur exactly once after Unicode NFKC
normalization. Preserve n-ary facts as one claim. Never use outside knowledge.
Never emit questions, answers, gold labels, support labels, hop labels, IDs, or
offsets. Return at most 4 high-information claims; prefer explicit named-entity
relations over generic descriptions. If no evidenced claim exists, return
{\"claims\":[]}."""

USER_PROMPT_TEMPLATE = "TITLE_JSON={title_json}\nTEXT_JSON={text_json}"

BATCH_SYSTEM_PROMPT = """You are a query-blind evidence extraction component.
INPUT is a JSON array of at most 8 paragraph objects. Return exactly one JSON
object and no prose or markdown. Its only root key is \"results\". Return
exactly one result for every input, with exactly \"source_id\" and \"claims\";
copy source_id byte-for-byte from that input and never invent an ID. claims is
an array. Each claim has exactly \"subject\", \"predicate\", and \"arguments\".
subject and predicate are non-empty exact contiguous quotes from that result's
TEXT. arguments is a non-empty array; each has exactly \"role\" and \"exact\".
exact is a non-empty exact contiguous quote from that same TEXT. role is a
lower-case semantic token. Choose quotes that occur exactly once after Unicode
NFKC normalization. Preserve n-ary facts as one claim. Never transfer evidence
between inputs. Never use outside knowledge. Never emit questions, answers,
gold labels, support labels, hop labels, offsets, or any ID except the copied
source_id. Return at most 4 high-information claims per input; prefer explicit
named-entity relations over generic descriptions. If no evidenced claim exists
for one input, use an empty claims array for that source_id."""

BATCH_USER_PROMPT_TEMPLATE = "INPUT_JSON={input_json}"

_ROOT_KEYS = frozenset({"claims"})
_CLAIM_KEYS = frozenset({"subject", "predicate", "arguments"})
_ARGUMENT_KEYS = frozenset({"role", "exact"})
_ROLE_RE = re.compile(r"[a-z][a-z0-9_:-]{0,63}\Z")
_RESERVED_ROLES = frozenset({"subject", "predicate"})
_EVALUATION_KEYS = frozenset({
    "answer", "answers", "evaluation", "gold", "gold_id", "gold_ids",
    "hop", "hops", "is_supporting", "label", "labels", "qid", "query",
    "question", "questions", "support", "supporting", "supporting_fact",
    "supporting_facts", "target_answer",
})


class QuoteRejectCode(StrEnum):
    INVALID_OPENAI_RESPONSE = "invalid_openai_response"
    INVALID_JSON = "invalid_json"
    DUPLICATE_JSON_KEY = "duplicate_json_key"
    EVALUATION_LABEL_LEAKAGE = "evaluation_label_leakage"
    INVALID_ROOT_SCHEMA = "invalid_root_schema"
    INVALID_CLAIM_SCHEMA = "invalid_claim_schema"
    INVALID_ARGUMENT_SCHEMA = "invalid_argument_schema"
    INVALID_ROLE = "invalid_role"
    EMPTY_QUOTE = "empty_quote"
    MISSING_QUOTE = "missing_quote"
    HALLUCINATED_QUOTE = "hallucinated_quote"
    AMBIGUOUS_QUOTE = "ambiguous_quote"
    DUPLICATE_CLAIM = "duplicate_claim"
    SOURCE_ROUTING_ERROR = "source_routing_error"
    MODEL_MISMATCH = "model_mismatch"
    TRANSPORT_ERROR = "transport_error"
    TRUNCATED_RESPONSE_AT_ATTEMPT_CAP = "truncated_response_at_attempt_cap"


class ExtractionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    QUARANTINED = "quarantined"
    ERROR = "error"


class _DuplicateJSONKey(ValueError):
    pass


class CacheCorruptionError(ValueError):
    pass


class CacheRunLockedError(RuntimeError):
    """Another process already owns this cache's extraction run."""


class AttemptCapExhaustedError(CacheCorruptionError):
    """A durable START consumed the cap without a compiler-usable result."""


@dataclass(frozen=True)
class ExtractorConfigV1:
    endpoint: str
    model: str
    model_revision: str
    max_concurrency: int = 2
    timeout_seconds: float = 180.0
    max_tokens: int = 1024
    max_attempts: int = 2
    temperature: int = 0
    top_p: float = 1.0
    seed: int = 0
    disable_thinking: bool = True
    response_format: str = "json_object"
    max_claims: int = 4
    max_arguments_per_claim: int = 12
    max_quote_codepoints: int = 512
    batch_size: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not self.endpoint.strip():
            raise ValueError("endpoint must be non-empty")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be non-empty")
        if not isinstance(self.model_revision, str) or not self.model_revision.strip():
            raise ValueError("model_revision must be non-empty")
        if not 1 <= self.max_concurrency <= 32:
            raise ValueError("max_concurrency must be in [1, 32]")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if (
            not isinstance(self.max_attempts, int)
            or isinstance(self.max_attempts, bool)
            or not 1 <= self.max_attempts <= 8
        ):
            raise ValueError("max_attempts must be an integer in [1, 8]")
        if self.temperature != 0:
            raise ValueError("temperature is frozen at 0")
        if not self.disable_thinking:
            raise ValueError("disable_thinking must remain true")
        if self.response_format != "json_object":
            raise ValueError("response_format must remain json_object")
        if self.max_claims <= 0 or self.max_arguments_per_claim <= 0:
            raise ValueError("schema limits must be positive")
        if self.max_quote_codepoints <= 0:
            raise ValueError("max_quote_codepoints must be positive")
        if not 1 <= self.batch_size <= 8:
            raise ValueError("batch_size must be in [1, 8]")


@dataclass(frozen=True)
class OpenAIRequestV1:
    request_id: str
    endpoint: str
    body: dict[str, Any]
    timeout_seconds: float


@dataclass(frozen=True)
class TransportResponseV1:
    raw_response: str
    http_status: int = 200
    response_headers: tuple[tuple[str, str], ...] = ()


Transport = Callable[[OpenAIRequestV1], TransportResponseV1 | str | Mapping[str, Any]]


@dataclass(frozen=True)
class BoundQuoteV1:
    start: int
    end: int
    exact: str
    model_quote: str
    normalization: str = "NFKC"
    offset_unit: str = OFFSET_UNIT


@dataclass(frozen=True)
class ExtractionQuarantineV1:
    quarantine_id: str
    claim_index: int | None
    role_path: str
    reason: QuoteRejectCode
    detail: str
    quote_sha256: str | None


@dataclass(frozen=True)
class RecordedExtractionV1:
    schema_version: str
    record_id: str
    attempt_id: str
    attempt_ordinal: int
    request_id: str
    batch_request_id: str
    batch_size: int
    source_id: str
    source_text_sha256: str
    source_input_json: str
    source_input_sha256: str
    batch_input_json: str
    producer: str
    producer_sha256: str
    model: str
    model_revision: str
    response_model: str
    finish_reason: str
    prompt_sha256: str
    config_json: str
    config_sha256: str
    request_json: str
    request_sha256: str
    http_status: int | None
    response_headers_json: str
    raw_response: str
    raw_response_sha256: str
    response_content_sha256: str
    output_sha256: str
    usage_json: str
    latency_ms: int
    status: ExtractionStatus
    quarantines: tuple[ExtractionQuarantineV1, ...]
    frozen_extraction: FrozenExtractionV1 | None
    error_type: str | None = None


@dataclass(frozen=True)
class ExtractionBatchV1:
    records: tuple[RecordedExtractionV1, ...]
    cache_hits: int
    endpoint_calls: int
    attempt_cap_exhausted: int = 0


@dataclass(frozen=True)
class AttemptStartV1:
    """Durable proof that one endpoint call was authorized to start."""

    journal_schema_version: str
    event_type: str
    start_id: str
    attempt_id: str
    attempt_ordinal: int
    batch_request_id: str
    batch_size: int
    source_ids: tuple[str, ...]
    request_sha256: str
    config_sha256: str
    prompt_sha256: str
    max_attempts: int


@dataclass(frozen=True)
class AttemptFinalizeV1:
    """Atomic result event bound to one earlier :class:`AttemptStartV1`."""

    journal_schema_version: str
    event_type: str
    finalize_id: str
    start_id: str
    attempt_id: str
    attempt_ordinal: int
    batch_request_id: str
    records: tuple[RecordedExtractionV1, ...]


JournalEventV1 = AttemptStartV1 | AttemptFinalizeV1


@dataclass(frozen=True)
class AttemptJournalV1:
    events: tuple[JournalEventV1, ...]
    starts: tuple[AttemptStartV1, ...]
    finalizes: tuple[AttemptFinalizeV1, ...]
    records: tuple[RecordedExtractionV1, ...]

    @property
    def unmatched_starts(self) -> tuple[AttemptStartV1, ...]:
        finalized = {item.start_id for item in self.finalizes}
        return tuple(item for item in self.starts if item.start_id not in finalized)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _find_evaluation_key(value: Any, path: str = "$") -> tuple[str, str] | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_key(str(key))
            if normalized in _EVALUATION_KEYS:
                return f"{path}.{key}", normalized
            found = _find_evaluation_key(child, f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_evaluation_key(child, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def prompt_sha256() -> str:
    return sha256_text(SYSTEM_PROMPT + "\n" + USER_PROMPT_TEMPLATE)


def batch_prompt_sha256() -> str:
    return sha256_text(BATCH_SYSTEM_PROMPT + "\n" + BATCH_USER_PROMPT_TEMPLATE)


def _config_payload(config: ExtractorConfigV1) -> dict[str, Any]:
    # Authentication is intentionally absent.  Endpoint identity is retained
    # because two deployments with the same model name are distinct producers.
    return {
        "schema_version": SCHEMA_VERSION,
        "quote_schema_version": QUOTE_SCHEMA_VERSION,
        "binder_version": BINDER_VERSION,
        "endpoint": config.endpoint.rstrip("/"),
        "model": config.model,
        "model_revision": config.model_revision,
        "max_concurrency": config.max_concurrency,
        "timeout_seconds": config.timeout_seconds,
        "max_tokens": config.max_tokens,
        "max_attempts": config.max_attempts,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "seed": config.seed,
        "disable_thinking": config.disable_thinking,
        "response_format": config.response_format,
        "max_claims": config.max_claims,
        "max_arguments_per_claim": config.max_arguments_per_claim,
        "max_quote_codepoints": config.max_quote_codepoints,
        "batch_size": config.batch_size,
    }


def config_sha256(config: ExtractorConfigV1) -> str:
    return sha256_text(canonical_json(_config_payload(config)))


def _paragraph_payload(paragraph: ParagraphInputV1) -> dict[str, str]:
    return {
        "source_id": paragraph.source_id,
        "title": paragraph.title,
        "text": paragraph.text,
    }


def _validate_paragraph(paragraph: ParagraphInputV1) -> None:
    if not isinstance(paragraph, ParagraphInputV1):
        raise TypeError(
            "paragraph must be ParagraphInputV1; raw QA/gold/support rows are forbidden"
        )
    if not paragraph.source_id or not paragraph.title or not paragraph.text:
        raise ValueError("source_id, title, and text must be non-empty")


def make_openai_request(
    paragraph: ParagraphInputV1,
    config: ExtractorConfigV1,
) -> OpenAIRequestV1:
    """Build the frozen query-blind request for one paragraph."""

    _validate_paragraph(paragraph)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title_json=json.dumps(paragraph.title, ensure_ascii=False),
        text_json=json.dumps(paragraph.text, ensure_ascii=False),
    )
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "top_p": config.top_p,
        "seed": config.seed,
        "max_tokens": config.max_tokens,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    source_input_sha256 = sha256_text(canonical_json(_paragraph_payload(paragraph)))
    request_id = content_id("llm_extraction_request", {
        "source_input_sha256": source_input_sha256,
        "prompt_sha256": prompt_sha256(),
        "config_sha256": config_sha256(config),
    })
    return OpenAIRequestV1(
        request_id=request_id,
        endpoint=config.endpoint,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )


def make_batch_openai_request(
    paragraphs: Sequence[ParagraphInputV1],
    config: ExtractorConfigV1,
) -> OpenAIRequestV1:
    """Build one deterministic, query-blind request for up to eight sources."""

    if isinstance(paragraphs, (str, bytes)) or not isinstance(paragraphs, Sequence):
        raise TypeError("paragraphs must be a sequence of ParagraphInputV1")
    checked = tuple(paragraphs)
    if not 1 <= len(checked) <= 8:
        raise ValueError("a batch request must contain between 1 and 8 paragraphs")
    if len(checked) > config.batch_size:
        raise ValueError("batch request exceeds config.batch_size")
    for paragraph in checked:
        _validate_paragraph(paragraph)
    if len({item.source_id for item in checked}) != len(checked):
        raise ValueError("batch paragraph source_id values must be unique")
    ordered = tuple(sorted(checked, key=lambda item: item.source_id))
    batch_input = [_paragraph_payload(item) for item in ordered]
    user_prompt = BATCH_USER_PROMPT_TEMPLATE.format(
        input_json=canonical_json(batch_input)
    )
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": BATCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "top_p": config.top_p,
        "seed": config.seed,
        "max_tokens": config.max_tokens,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    batch_input_sha256 = sha256_text(canonical_json(batch_input))
    request_id = content_id("llm_batch_extraction_request", {
        "batch_input_sha256": batch_input_sha256,
        "prompt_sha256": batch_prompt_sha256(),
        "config_sha256": config_sha256(config),
    })
    return OpenAIRequestV1(
        request_id=request_id,
        endpoint=config.endpoint,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )


def _batch_item_request_id(
    request: OpenAIRequestV1,
    paragraph: ParagraphInputV1,
) -> str:
    return content_id("llm_batch_extraction_item", {
        "batch_request_id": request.request_id,
        "source_id": paragraph.source_id,
        "source_input_sha256": sha256_text(
            canonical_json(_paragraph_payload(paragraph))
        ),
    })


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def bind_unique_nfkc_quote(source_text: str, model_quote: str) -> BoundQuoteV1:
    """Resolve one quote to exactly one original-codepoint source span.

    Exact source occurrences are checked first.  Otherwise, matches are found
    in the NFKC-normalized text and mapped back only through normalization-safe
    original string boundaries.  Multiple candidate spans are always an error.
    """

    if not isinstance(source_text, str) or not isinstance(model_quote, str):
        raise TypeError("source_text and model_quote must be str")
    if not model_quote:
        raise ValueError(QuoteRejectCode.EMPTY_QUOTE.value)

    exact_candidates: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = source_text.find(model_quote, cursor)
        if start < 0:
            break
        exact_candidates.append((start, start + len(model_quote)))
        cursor = start + 1
    if len(exact_candidates) == 1:
        start, end = exact_candidates[0]
        return BoundQuoteV1(start, end, source_text[start:end], model_quote)
    if len(exact_candidates) > 1:
        raise ValueError(QuoteRejectCode.AMBIGUOUS_QUOTE.value)

    normalized_quote = _nfkc(model_quote)
    if not normalized_quote:
        raise ValueError(QuoteRejectCode.EMPTY_QUOTE.value)
    normalized_source = _nfkc(source_text)
    normalized_occurrences: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = normalized_source.find(normalized_quote, cursor)
        if start < 0:
            break
        normalized_occurrences.append((start, start + len(normalized_quote)))
        cursor = start + 1
    if not normalized_occurrences:
        raise ValueError(QuoteRejectCode.HALLUCINATED_QUOTE.value)

    # A boundary is admissible only when normalizing the original prefix gives
    # exactly the corresponding normalized prefix, preventing a compatibility
    # match from being mapped across an unstable normalization boundary.
    starts: dict[int, list[int]] = {}
    ends: dict[int, list[int]] = {}
    wanted_starts = {start for start, _ in normalized_occurrences}
    wanted_ends = {end for _, end in normalized_occurrences}
    for index in range(len(source_text) + 1):
        prefix = _nfkc(source_text[:index])
        normalized_index = len(prefix)
        if normalized_index in wanted_starts and prefix == normalized_source[:normalized_index]:
            starts.setdefault(normalized_index, []).append(index)
        if normalized_index in wanted_ends and prefix == normalized_source[:normalized_index]:
            ends.setdefault(normalized_index, []).append(index)

    candidates: set[tuple[int, int]] = set()
    for normalized_start, normalized_end in normalized_occurrences:
        for start in starts.get(normalized_start, ()):
            for end in ends.get(normalized_end, ()):
                if end > start and _nfkc(source_text[start:end]) == normalized_quote:
                    candidates.add((start, end))
    if not candidates:
        raise ValueError(QuoteRejectCode.MISSING_QUOTE.value)
    if len(candidates) != 1:
        raise ValueError(QuoteRejectCode.AMBIGUOUS_QUOTE.value)
    start, end = next(iter(candidates))
    return BoundQuoteV1(start, end, source_text[start:end], model_quote)


def _quarantine(
    request_id: str,
    *,
    claim_index: int | None,
    role_path: str,
    reason: QuoteRejectCode,
    detail: str,
    quote: str | None = None,
) -> ExtractionQuarantineV1:
    quote_digest = sha256_text(quote) if isinstance(quote, str) else None
    payload = {
        "request_id": request_id,
        "claim_index": claim_index,
        "role_path": role_path,
        "reason": reason.value,
        "detail": detail,
        "quote_sha256": quote_digest,
    }
    return ExtractionQuarantineV1(
        quarantine_id=content_id("llm_extraction_quarantine", payload),
        claim_index=claim_index,
        role_path=role_path,
        reason=reason,
        detail=detail,
        quote_sha256=quote_digest,
    )


def _parse_strict_json(raw_json: str) -> Any:
    return json.loads(raw_json, object_pairs_hook=_strict_object)


def _bind_role(
    paragraph: ParagraphInputV1,
    quote: Any,
    *,
    max_quote_codepoints: int,
) -> BoundQuoteV1:
    if not isinstance(quote, str) or not quote or len(quote) > max_quote_codepoints:
        raise ValueError(QuoteRejectCode.EMPTY_QUOTE.value)
    return bind_unique_nfkc_quote(paragraph.text, quote)


def adapt_quote_payload(
    paragraph: ParagraphInputV1,
    raw_content: str,
    *,
    request_id: str,
    config: ExtractorConfigV1,
) -> tuple[str, tuple[ExtractionQuarantineV1, ...]]:
    """Bind quote-only model JSON into the strict compiler extraction schema."""

    _validate_paragraph(paragraph)
    try:
        payload = _parse_strict_json(raw_content)
    except _DuplicateJSONKey as exc:
        quarantine = _quarantine(
            request_id, claim_index=None, role_path="$",
            reason=QuoteRejectCode.DUPLICATE_JSON_KEY, detail=str(exc),
        )
        empty = {"schema_version": EXTRACTION_SCHEMA_VERSION, "claims": []}
        return canonical_json(empty), (quarantine,)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        quarantine = _quarantine(
            request_id, claim_index=None, role_path="$",
            reason=QuoteRejectCode.INVALID_JSON, detail=str(exc),
        )
        empty = {"schema_version": EXTRACTION_SCHEMA_VERSION, "claims": []}
        return canonical_json(empty), (quarantine,)

    leaked = _find_evaluation_key(payload)
    if leaked is not None:
        path, key = leaked
        quarantine = _quarantine(
            request_id, claim_index=None, role_path=path,
            reason=QuoteRejectCode.EVALUATION_LABEL_LEAKAGE,
            detail=f"forbidden evaluation field {key!r} at {path}",
        )
        empty = {"schema_version": EXTRACTION_SCHEMA_VERSION, "claims": []}
        return canonical_json(empty), (quarantine,)
    if not isinstance(payload, dict) or frozenset(payload) != _ROOT_KEYS:
        quarantine = _quarantine(
            request_id, claim_index=None, role_path="$",
            reason=QuoteRejectCode.INVALID_ROOT_SCHEMA,
            detail=f"root keys must be {sorted(_ROOT_KEYS)}",
        )
        empty = {"schema_version": EXTRACTION_SCHEMA_VERSION, "claims": []}
        return canonical_json(empty), (quarantine,)
    claims = payload.get("claims")
    if not isinstance(claims, list) or len(claims) > config.max_claims:
        quarantine = _quarantine(
            request_id, claim_index=None, role_path="$.claims",
            reason=QuoteRejectCode.INVALID_ROOT_SCHEMA,
            detail=f"claims must be an array of at most {config.max_claims}",
        )
        empty = {"schema_version": EXTRACTION_SCHEMA_VERSION, "claims": []}
        return canonical_json(empty), (quarantine,)

    adapted: list[dict[str, Any]] = []
    quarantines: list[ExtractionQuarantineV1] = []
    seen_claims: set[str] = set()
    for claim_index, claim in enumerate(claims):
        if not isinstance(claim, dict) or frozenset(claim) != _CLAIM_KEYS:
            quarantines.append(_quarantine(
                request_id, claim_index=claim_index,
                role_path=f"$.claims[{claim_index}]",
                reason=QuoteRejectCode.INVALID_CLAIM_SCHEMA,
                detail=f"claim keys must be {sorted(_CLAIM_KEYS)}",
            ))
            continue
        arguments = claim.get("arguments")
        if (
            not isinstance(arguments, list) or not arguments
            or len(arguments) > config.max_arguments_per_claim
        ):
            quarantines.append(_quarantine(
                request_id, claim_index=claim_index,
                role_path=f"$.claims[{claim_index}].arguments",
                reason=QuoteRejectCode.INVALID_ARGUMENT_SCHEMA,
                detail=("arguments must be a non-empty array of at most "
                        f"{config.max_arguments_per_claim}"),
            ))
            continue

        role_specs: list[tuple[str, Any, str | None]] = [
            ("subject", claim.get("subject"), None),
            ("predicate", claim.get("predicate"), None),
        ]
        argument_error = False
        for argument_index, argument in enumerate(arguments):
            path = f"arguments[{argument_index}]"
            if not isinstance(argument, dict) or frozenset(argument) != _ARGUMENT_KEYS:
                quarantines.append(_quarantine(
                    request_id, claim_index=claim_index,
                    role_path=f"$.claims[{claim_index}].{path}",
                    reason=QuoteRejectCode.INVALID_ARGUMENT_SCHEMA,
                    detail=f"argument keys must be {sorted(_ARGUMENT_KEYS)}",
                ))
                argument_error = True
                break
            role = argument.get("role")
            if (
                not isinstance(role, str) or _ROLE_RE.fullmatch(role) is None
                or role in _RESERVED_ROLES
            ):
                quarantines.append(_quarantine(
                    request_id, claim_index=claim_index,
                    role_path=f"$.claims[{claim_index}].{path}.role",
                    reason=QuoteRejectCode.INVALID_ROLE,
                    detail="role must be a non-reserved lower-case role token",
                ))
                argument_error = True
                break
            role_specs.append((path, argument.get("exact"), role))
        if argument_error:
            continue

        bound: list[tuple[str, BoundQuoteV1, str | None]] = []
        bind_error = False
        for role_path, quote, semantic_role in role_specs:
            try:
                span = _bind_role(
                    paragraph, quote,
                    max_quote_codepoints=config.max_quote_codepoints,
                )
            except ValueError as exc:
                try:
                    reason = QuoteRejectCode(str(exc))
                except ValueError:
                    reason = QuoteRejectCode.MISSING_QUOTE
                quarantines.append(_quarantine(
                    request_id, claim_index=claim_index,
                    role_path=f"$.claims[{claim_index}].{role_path}",
                    reason=reason,
                    detail=("quote is not uniquely evidenced by the source under "
                            f"{BINDER_VERSION}"),
                    quote=quote if isinstance(quote, str) else None,
                ))
                bind_error = True
                break
            bound.append((role_path, span, semantic_role))
        if bind_error:
            continue

        subject = bound[0][1]
        predicate = bound[1][1]
        bound_arguments = [
            {
                "role": semantic_role,
                "start": span.start,
                "end": span.end,
                "exact": span.exact,
            }
            for _, span, semantic_role in bound[2:]
        ]
        bound_arguments.sort(
            key=lambda item: (item["start"], item["end"], item["role"], item["exact"])
        )
        adapted_claim = {
            "subject": {
                "start": subject.start, "end": subject.end,
                "exact": subject.exact,
            },
            "predicate": {
                "start": predicate.start, "end": predicate.end,
                "exact": predicate.exact,
            },
            "arguments": bound_arguments,
        }
        claim_digest = sha256_text(canonical_json(adapted_claim))
        if claim_digest in seen_claims:
            quarantines.append(_quarantine(
                request_id, claim_index=claim_index,
                role_path=f"$.claims[{claim_index}]",
                reason=QuoteRejectCode.DUPLICATE_CLAIM,
                detail="same evidence-bound claim occurs more than once",
            ))
            continue
        seen_claims.add(claim_digest)
        adapted.append(adapted_claim)

    adapted.sort(key=lambda item: (
        item["subject"]["start"], item["predicate"]["start"],
        sha256_text(canonical_json(item)),
    ))
    output = {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "claims": adapted,
    }
    return (
        canonical_json(output),
        tuple(sorted(quarantines, key=lambda item: item.quarantine_id)),
    )


def adapt_batch_quote_payloads(
    paragraphs: Sequence[ParagraphInputV1],
    raw_content: str,
    *,
    request: OpenAIRequestV1,
    config: ExtractorConfigV1,
) -> dict[str, tuple[str, tuple[ExtractionQuarantineV1, ...]]]:
    """Route and bind a batch response without ever guessing its source.

    Unknown IDs or result objects without an exact routing key quarantine the
    entire batch.  A missing or duplicated *known* ID quarantines that source;
    other uniquely routed sources may still cross the compiler boundary.
    """

    checked = tuple(sorted(paragraphs, key=lambda item: item.source_id))
    for paragraph in checked:
        _validate_paragraph(paragraph)
    expected = {item.source_id: item for item in checked}
    item_request_ids = {
        item.source_id: _batch_item_request_id(request, item) for item in checked
    }
    empty_payload = canonical_json({
        "schema_version": EXTRACTION_SCHEMA_VERSION, "claims": [],
    })

    def reject_all(
        reason: QuoteRejectCode, detail: str, role_path: str,
    ) -> dict[str, tuple[str, tuple[ExtractionQuarantineV1, ...]]]:
        return {
            source_id: (
                empty_payload,
                (_quarantine(
                    item_request_ids[source_id], claim_index=None,
                    role_path=role_path, reason=reason, detail=detail,
                ),),
            )
            for source_id in sorted(expected)
        }

    try:
        payload = _parse_strict_json(raw_content)
    except _DuplicateJSONKey as exc:
        return reject_all(QuoteRejectCode.DUPLICATE_JSON_KEY, str(exc), "$")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return reject_all(QuoteRejectCode.INVALID_JSON, str(exc), "$")

    leaked = _find_evaluation_key(payload)
    if leaked is not None:
        path, key = leaked
        return reject_all(
            QuoteRejectCode.EVALUATION_LABEL_LEAKAGE,
            f"forbidden evaluation field {key!r} at {path}", path,
        )
    if not isinstance(payload, dict) or frozenset(payload) != {"results"}:
        return reject_all(
            QuoteRejectCode.INVALID_ROOT_SCHEMA,
            "batch root keys must be ['results']", "$",
        )
    results = payload.get("results")
    if not isinstance(results, list) or len(results) > 8:
        return reject_all(
            QuoteRejectCode.INVALID_ROOT_SCHEMA,
            "results must be an array of at most 8 items", "$.results",
        )

    routed: dict[str, list[Any]] = {source_id: [] for source_id in expected}
    for result_index, result in enumerate(results):
        if not isinstance(result, dict) or frozenset(result) != {
            "source_id", "claims",
        }:
            return reject_all(
                QuoteRejectCode.SOURCE_ROUTING_ERROR,
                "every result must contain exactly source_id and claims",
                f"$.results[{result_index}]",
            )
        source_id = result.get("source_id")
        if not isinstance(source_id, str) or source_id not in expected:
            source_digest = sha256_text(source_id) if isinstance(source_id, str) else None
            return reject_all(
                QuoteRejectCode.SOURCE_ROUTING_ERROR,
                "result source_id is not an exact member of the request"
                + (f" (sha256={source_digest})" if source_digest else ""),
                f"$.results[{result_index}].source_id",
            )
        routed[source_id].append(result.get("claims"))

    output: dict[str, tuple[str, tuple[ExtractionQuarantineV1, ...]]] = {}
    for source_id in sorted(expected):
        matches = routed[source_id]
        item_request_id = item_request_ids[source_id]
        if len(matches) != 1:
            reason_detail = (
                "source_id is missing from batch response"
                if not matches else "source_id occurs more than once in batch response"
            )
            output[source_id] = (
                empty_payload,
                (_quarantine(
                    item_request_id, claim_index=None,
                    role_path="$.results", reason=QuoteRejectCode.SOURCE_ROUTING_ERROR,
                    detail=reason_detail,
                ),),
            )
            continue
        source_content = canonical_json({"claims": matches[0]})
        output[source_id] = adapt_quote_payload(
            expected[source_id], source_content,
            request_id=item_request_id, config=config,
        )
    return output


def _endpoint_url(endpoint: str) -> str:
    stripped = endpoint.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return stripped
    return stripped + "/chat/completions"


def _normalize_response_headers(
    headers: Any,
) -> tuple[tuple[str, str], ...]:
    """Retain the observed response-header sequence, including duplicates."""

    if headers is None:
        return ()
    items = headers.items() if hasattr(headers, "items") else headers
    try:
        normalized = tuple((name, value) for name, value in items)
    except (TypeError, ValueError) as exc:
        raise TypeError("response headers must be name/value pairs") from exc
    if any(
        not isinstance(name, str) or not isinstance(value, str)
        for name, value in normalized
    ):
        raise TypeError("response header names and values must be strings")
    return normalized


def _response_headers_json(response: TransportResponseV1) -> str:
    return canonical_json([
        [name, value]
        for name, value in _normalize_response_headers(response.response_headers)
    ])


def openai_compatible_transport(*, api_key: str | None = None) -> Transport:
    """Create the stdlib HTTP transport.  Credentials never enter receipts."""

    def send(request: OpenAIRequestV1) -> TransportResponseV1:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        encoded = canonical_json(request.body).encode("utf-8")
        http_request = urllib_request.Request(
            _endpoint_url(request.endpoint), data=encoded,
            headers=headers, method="POST",
        )
        try:
            with urllib_request.urlopen(
                http_request, timeout=request.timeout_seconds
            ) as response:
                raw = response.read().decode("utf-8")
                return TransportResponseV1(
                    raw_response=raw,
                    http_status=int(getattr(response, "status", 200)),
                    response_headers=_normalize_response_headers(
                        getattr(response, "headers", None)
                    ),
                )
        except urllib_error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            # HTTPError is also a response object.  Returning its observed
            # outcome preserves the body/status/headers in the append-only
            # FINALIZE receipt.  The extraction boundary below still rejects
            # every non-2xx outcome without parsing or salvaging model claims.
            return TransportResponseV1(
                raw_response=raw,
                http_status=int(exc.code),
                response_headers=_normalize_response_headers(exc.headers),
            )

    return send


def _coerce_transport_response(
    response: TransportResponseV1 | str | Mapping[str, Any],
) -> TransportResponseV1:
    if isinstance(response, TransportResponseV1):
        coerced = TransportResponseV1(
            raw_response=response.raw_response,
            http_status=response.http_status,
            response_headers=_normalize_response_headers(response.response_headers),
        )
    elif isinstance(response, str):
        coerced = TransportResponseV1(response)
    elif isinstance(response, Mapping):
        coerced = TransportResponseV1(canonical_json(dict(response)))
    else:
        raise TypeError("transport must return TransportResponseV1, str, or mapping")
    if not isinstance(coerced.raw_response, str):
        raise TypeError("transport raw_response must be str")
    if (
        isinstance(coerced.http_status, bool)
        or not isinstance(coerced.http_status, int)
        or not 100 <= coerced.http_status <= 599
    ):
        raise TypeError("transport http_status must be an integer in [100, 599]")
    return coerced


def _extract_openai_content(
    raw_response: str,
) -> tuple[str, str, str, str, tuple[QuoteRejectCode, str] | None]:
    """Return content/model/finish/usage, accepting only exact ``stop``."""

    try:
        envelope = _parse_strict_json(raw_response)
    except _DuplicateJSONKey as exc:
        return "", "", "", canonical_json({}), (
            QuoteRejectCode.DUPLICATE_JSON_KEY, str(exc),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return "", "", "", canonical_json({}), (
            QuoteRejectCode.INVALID_OPENAI_RESPONSE, str(exc),
        )
    if not isinstance(envelope, dict):
        return "", "", "", canonical_json({}), (
            QuoteRejectCode.INVALID_OPENAI_RESPONSE,
            "OpenAI response must be an object",
        )
    choices = envelope.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return "", "", "", canonical_json(envelope.get("usage", {})), (
            QuoteRejectCode.INVALID_OPENAI_RESPONSE,
            "OpenAI response must contain exactly one choice",
        )
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
    if not isinstance(content, str):
        return "", "", "", canonical_json(envelope.get("usage", {})), (
            QuoteRejectCode.INVALID_OPENAI_RESPONSE,
            "choice.message.content must be str",
        )
    response_model = envelope.get("model", "")
    if not isinstance(response_model, str):
        response_model = ""
    usage = envelope.get("usage", {})
    try:
        usage_json = canonical_json(usage)
    except (TypeError, ValueError):
        usage_json = canonical_json({})
    retained_finish_reason = finish_reason if isinstance(finish_reason, str) else ""
    if finish_reason != "stop":
        return content, response_model, retained_finish_reason, usage_json, (
            QuoteRejectCode.INVALID_OPENAI_RESPONSE,
            "choice.finish_reason must be exact 'stop'",
        )
    return content, response_model, finish_reason, usage_json, None


def _attempt_id(batch_request_id: str, attempt_ordinal: int) -> str:
    return content_id("recorded_llm_extraction_attempt", {
        "batch_request_id": batch_request_id,
        "attempt_ordinal": attempt_ordinal,
    })


def _record_id(record: RecordedExtractionV1) -> str:
    return content_id("recorded_llm_extraction", {
        "schema_version": record.schema_version,
        "attempt_id": record.attempt_id,
        "attempt_ordinal": record.attempt_ordinal,
        "request_id": record.request_id,
        "batch_request_id": record.batch_request_id,
        "batch_size": record.batch_size,
        "source_id": record.source_id,
        "source_text_sha256": record.source_text_sha256,
        "source_input_sha256": record.source_input_sha256,
        "producer_sha256": record.producer_sha256,
        "model": record.model,
        "model_revision": record.model_revision,
        "response_model": record.response_model,
        "finish_reason": record.finish_reason,
        "prompt_sha256": record.prompt_sha256,
        "config_sha256": record.config_sha256,
        "request_sha256": record.request_sha256,
        "http_status": record.http_status,
        "response_headers_sha256": sha256_text(record.response_headers_json),
        "raw_response_sha256": record.raw_response_sha256,
        "response_content_sha256": record.response_content_sha256,
        "output_sha256": record.output_sha256,
        "usage_sha256": sha256_text(record.usage_json),
        "status": record.status.value,
        "quarantine_ids": tuple(item.quarantine_id for item in record.quarantines),
        "error_type": record.error_type,
    })


def _make_record(
    paragraph: ParagraphInputV1,
    config: ExtractorConfigV1,
    request: OpenAIRequestV1,
    *,
    raw_response: str,
    response_content: str,
    response_model: str,
    finish_reason: str,
    usage_json: str,
    http_status: int | None,
    response_headers_json: str,
    latency_ms: int,
    status: ExtractionStatus,
    quarantines: tuple[ExtractionQuarantineV1, ...],
    frozen_extraction: FrozenExtractionV1 | None,
    error_type: str | None = None,
    item_request_id: str | None = None,
    receipt_prompt_sha256: str | None = None,
    batch_size: int = 1,
    batch_paragraphs: Sequence[ParagraphInputV1] | None = None,
) -> RecordedExtractionV1:
    source_input_json = canonical_json(_paragraph_payload(paragraph))
    source_input_sha256 = sha256_text(source_input_json)
    batch_members = tuple(sorted(
        batch_paragraphs or (paragraph,), key=lambda item: item.source_id,
    ))
    batch_input_json = canonical_json([
        _paragraph_payload(item) for item in batch_members
    ])
    config_json = canonical_json(_config_payload(config))
    request_json = canonical_json(request.body)
    provisional = RecordedExtractionV1(
        schema_version=SCHEMA_VERSION,
        record_id="",
        attempt_id=_attempt_id(request.request_id, 1),
        attempt_ordinal=1,
        request_id=item_request_id or request.request_id,
        batch_request_id=request.request_id,
        batch_size=batch_size,
        source_id=paragraph.source_id,
        source_text_sha256=sha256_text(paragraph.text),
        source_input_json=source_input_json,
        source_input_sha256=source_input_sha256,
        batch_input_json=batch_input_json,
        producer=PRODUCER,
        producer_sha256=sha256_text(PRODUCER),
        model=config.model,
        model_revision=config.model_revision,
        response_model=response_model,
        finish_reason=finish_reason,
        prompt_sha256=receipt_prompt_sha256 or prompt_sha256(),
        config_json=config_json,
        config_sha256=sha256_text(config_json),
        request_json=request_json,
        request_sha256=sha256_text(request_json),
        http_status=http_status,
        response_headers_json=response_headers_json,
        raw_response=raw_response,
        raw_response_sha256=sha256_text(raw_response),
        response_content_sha256=sha256_text(response_content),
        output_sha256=(
            frozen_extraction.output_sha256 if frozen_extraction is not None else ""
        ),
        usage_json=usage_json,
        latency_ms=max(0, int(latency_ms)),
        status=status,
        quarantines=quarantines,
        frozen_extraction=frozen_extraction,
        error_type=error_type,
    )
    return RecordedExtractionV1(
        **{**asdict(provisional), "record_id": _record_id(provisional),
           "status": provisional.status, "quarantines": provisional.quarantines,
           "frozen_extraction": provisional.frozen_extraction}
    )


def _attempt_cap_truncation(
    record: RecordedExtractionV1,
    config: ExtractorConfigV1,
) -> tuple[
    tuple[ExtractionQuarantineV1, ...],
    FrozenExtractionV1,
] | None:
    """Return the only compiler-admissible terminalization of a capped error.

    A response that reaches the exact output-token cap may contain a JSON
    prefix.  That prefix is never parsed or salvaged.  On the final frozen
    attempt only, an otherwise well-formed response from the exact requested
    model becomes an evidenced empty extraction plus a typed quarantine.  All
    transport failures, model mismatches, and other malformed envelopes remain
    non-admissible ERROR records.
    """

    if not (
        record.attempt_ordinal == config.max_attempts
        and record.http_status is not None
        and 200 <= record.http_status < 300
        and record.finish_reason == "length"
        and record.response_model == config.model
        and record.error_type in {
            QuoteRejectCode.INVALID_OPENAI_RESPONSE.value,
            None,
        }
    ):
        return None
    empty_payload = canonical_json({
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "claims": [],
    })
    quarantine = _quarantine(
        record.request_id,
        claim_index=None,
        role_path="$response",
        reason=QuoteRejectCode.TRUNCATED_RESPONSE_AT_ATTEMPT_CAP,
        detail=(
            "response reached the frozen output-token cap on the final "
            "attempt; raw response content was not compiled"
        ),
    )
    frozen = freeze_extraction(
        record.source_id,
        empty_payload,
        producer=PRODUCER,
        model_revision=config.model_revision,
        prompt_sha256=record.prompt_sha256,
        config_sha256=record.config_sha256,
    )
    return (quarantine,), frozen


def _terminalize_attempt_cap_truncation(
    record: RecordedExtractionV1,
    config: ExtractorConfigV1,
) -> RecordedExtractionV1:
    terminal = _attempt_cap_truncation(record, config)
    if terminal is None:
        return record
    quarantines, frozen = terminal
    return replace(
        record,
        status=ExtractionStatus.QUARANTINED,
        quarantines=quarantines,
        frozen_extraction=frozen,
        output_sha256=frozen.output_sha256,
        error_type=None,
    )


def extract_paragraph(
    paragraph: ParagraphInputV1,
    config: ExtractorConfigV1,
    transport: Transport,
) -> RecordedExtractionV1:
    """Call one endpoint and produce a complete immutable receipt."""

    request = make_openai_request(paragraph, config)
    start_ns = time.perf_counter_ns()
    try:
        transport_response = _coerce_transport_response(transport(request))
    except Exception as exc:  # transport boundary: errors become durable receipts
        latency_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
        quarantine = _quarantine(
            request.request_id, claim_index=None, role_path="$transport",
            reason=QuoteRejectCode.TRANSPORT_ERROR,
            detail=f"{type(exc).__name__}: transport call failed",
        )
        return _make_record(
            paragraph, config, request, raw_response="", response_content="",
            response_model="", finish_reason="", usage_json=canonical_json({}),
            http_status=None, response_headers_json=canonical_json([]),
            latency_ms=latency_ms, status=ExtractionStatus.ERROR,
            quarantines=(quarantine,), frozen_extraction=None,
            error_type=type(exc).__name__,
        )

    latency_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
    raw_response = transport_response.raw_response
    response_headers_json = _response_headers_json(transport_response)
    if not 200 <= transport_response.http_status < 300:
        quarantine = _quarantine(
            request.request_id, claim_index=None, role_path="$transport",
            reason=QuoteRejectCode.TRANSPORT_ERROR,
            detail=(
                "HTTPStatusError: non-success HTTP status "
                f"{transport_response.http_status}"
            ),
        )
        return _make_record(
            paragraph, config, request, raw_response=raw_response,
            response_content="", response_model="", finish_reason="",
            usage_json=canonical_json({}),
            http_status=transport_response.http_status,
            response_headers_json=response_headers_json,
            latency_ms=latency_ms, status=ExtractionStatus.ERROR,
            quarantines=(quarantine,), frozen_extraction=None,
            error_type="HTTPStatusError",
        )

    content, response_model, finish_reason, usage_json, envelope_issue = (
        _extract_openai_content(raw_response)
    )
    if envelope_issue is not None:
        reason, detail = envelope_issue
        quarantine = _quarantine(
            request.request_id, claim_index=None, role_path="$response",
            reason=reason, detail=detail,
        )
        return _make_record(
            paragraph, config, request, raw_response=raw_response,
            response_content=content, response_model=response_model,
            finish_reason=finish_reason,
            usage_json=usage_json, http_status=transport_response.http_status,
            response_headers_json=response_headers_json, latency_ms=latency_ms,
            status=ExtractionStatus.ERROR,
            quarantines=(quarantine,), frozen_extraction=None,
            error_type=reason.value,
        )

    if response_model != config.model:
        quarantine = _quarantine(
            request.request_id, claim_index=None, role_path="$.model",
            reason=QuoteRejectCode.MODEL_MISMATCH,
            detail="response model does not equal requested model",
        )
        return _make_record(
            paragraph, config, request, raw_response=raw_response,
            response_content=content, response_model=response_model,
            finish_reason=finish_reason, usage_json=usage_json,
            http_status=transport_response.http_status,
            response_headers_json=response_headers_json,
            latency_ms=latency_ms, status=ExtractionStatus.ERROR,
            quarantines=(quarantine,), frozen_extraction=None,
            error_type="ModelMismatch",
        )

    payload_json, quarantines = adapt_quote_payload(
        paragraph, content, request_id=request.request_id, config=config,
    )
    frozen = freeze_extraction(
        paragraph.source_id, payload_json, producer=PRODUCER,
        model_revision=config.model_revision,
        prompt_sha256=prompt_sha256(), config_sha256=config_sha256(config),
    )
    decoded_payload = json.loads(payload_json)
    accepted_count = len(decoded_payload["claims"])
    if quarantines and accepted_count:
        status = ExtractionStatus.PARTIAL
    elif quarantines:
        status = ExtractionStatus.QUARANTINED
    else:
        status = ExtractionStatus.SUCCESS
    return _make_record(
        paragraph, config, request, raw_response=raw_response,
        response_content=content, response_model=response_model,
        finish_reason=finish_reason,
        usage_json=usage_json, http_status=transport_response.http_status,
        response_headers_json=response_headers_json,
        latency_ms=latency_ms, status=status,
        quarantines=quarantines, frozen_extraction=frozen,
    )


def extract_paragraph_batch(
    paragraphs: Sequence[ParagraphInputV1],
    config: ExtractorConfigV1,
    transport: Transport,
) -> tuple[RecordedExtractionV1, ...]:
    """Call one endpoint for up to eight sources and return per-source receipts."""

    checked = tuple(sorted(paragraphs, key=lambda item: item.source_id))
    request = make_batch_openai_request(checked, config)
    item_ids = {
        item.source_id: _batch_item_request_id(request, item) for item in checked
    }
    start_ns = time.perf_counter_ns()
    try:
        transport_response = _coerce_transport_response(transport(request))
    except Exception as exc:
        latency_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
        records: list[RecordedExtractionV1] = []
        for paragraph in checked:
            item_request_id = item_ids[paragraph.source_id]
            quarantine = _quarantine(
                item_request_id, claim_index=None, role_path="$transport",
                reason=QuoteRejectCode.TRANSPORT_ERROR,
                detail=f"{type(exc).__name__}: transport call failed",
            )
            records.append(_make_record(
                paragraph, config, request, raw_response="", response_content="",
                response_model="", finish_reason="", usage_json=canonical_json({}),
                http_status=None, response_headers_json=canonical_json([]),
                latency_ms=latency_ms, status=ExtractionStatus.ERROR,
                quarantines=(quarantine,), frozen_extraction=None,
                error_type=type(exc).__name__, item_request_id=item_request_id,
                receipt_prompt_sha256=batch_prompt_sha256(),
                batch_size=len(checked),
                batch_paragraphs=checked,
            ))
        return tuple(records)

    latency_ms = (time.perf_counter_ns() - start_ns) // 1_000_000
    raw_response = transport_response.raw_response
    response_headers_json = _response_headers_json(transport_response)
    if not 200 <= transport_response.http_status < 300:
        records = []
        for paragraph in checked:
            item_request_id = item_ids[paragraph.source_id]
            quarantine = _quarantine(
                item_request_id, claim_index=None, role_path="$transport",
                reason=QuoteRejectCode.TRANSPORT_ERROR,
                detail=(
                    "HTTPStatusError: non-success HTTP status "
                    f"{transport_response.http_status}"
                ),
            )
            records.append(_make_record(
                paragraph, config, request, raw_response=raw_response,
                response_content="", response_model="", finish_reason="",
                usage_json=canonical_json({}),
                http_status=transport_response.http_status,
                response_headers_json=response_headers_json,
                latency_ms=latency_ms, status=ExtractionStatus.ERROR,
                quarantines=(quarantine,), frozen_extraction=None,
                error_type="HTTPStatusError", item_request_id=item_request_id,
                receipt_prompt_sha256=batch_prompt_sha256(),
                batch_size=len(checked), batch_paragraphs=checked,
            ))
        return tuple(records)

    content, response_model, finish_reason, usage_json, envelope_issue = (
        _extract_openai_content(raw_response)
    )
    if envelope_issue is not None:
        reason, detail = envelope_issue
        records = []
        for paragraph in checked:
            item_request_id = item_ids[paragraph.source_id]
            quarantine = _quarantine(
                item_request_id, claim_index=None, role_path="$response",
                reason=reason, detail=detail,
            )
            records.append(_make_record(
                paragraph, config, request, raw_response=raw_response,
                response_content=content, response_model=response_model,
                finish_reason=finish_reason,
                usage_json=usage_json,
                http_status=transport_response.http_status,
                response_headers_json=response_headers_json,
                latency_ms=latency_ms,
                status=ExtractionStatus.ERROR,
                quarantines=(quarantine,), frozen_extraction=None,
                error_type=reason.value,
                item_request_id=item_request_id,
                receipt_prompt_sha256=batch_prompt_sha256(),
                batch_size=len(checked),
                batch_paragraphs=checked,
            ))
        return tuple(records)

    if response_model != config.model:
        records = []
        for paragraph in checked:
            item_request_id = item_ids[paragraph.source_id]
            quarantine = _quarantine(
                item_request_id, claim_index=None, role_path="$.model",
                reason=QuoteRejectCode.MODEL_MISMATCH,
                detail="response model does not equal requested model",
            )
            records.append(_make_record(
                paragraph, config, request, raw_response=raw_response,
                response_content=content, response_model=response_model,
                finish_reason=finish_reason, usage_json=usage_json,
                http_status=transport_response.http_status,
                response_headers_json=response_headers_json,
                latency_ms=latency_ms, status=ExtractionStatus.ERROR,
                quarantines=(quarantine,), frozen_extraction=None,
                error_type="ModelMismatch", item_request_id=item_request_id,
                receipt_prompt_sha256=batch_prompt_sha256(),
                batch_size=len(checked), batch_paragraphs=checked,
            ))
        return tuple(records)

    adapted = adapt_batch_quote_payloads(
        checked, content, request=request, config=config,
    )
    records = []
    for paragraph in checked:
        item_request_id = item_ids[paragraph.source_id]
        payload_json, quarantines = adapted[paragraph.source_id]
        frozen = freeze_extraction(
            paragraph.source_id, payload_json, producer=PRODUCER,
            model_revision=config.model_revision,
            prompt_sha256=batch_prompt_sha256(),
            config_sha256=config_sha256(config),
        )
        accepted_count = len(json.loads(payload_json)["claims"])
        if quarantines and accepted_count:
            status = ExtractionStatus.PARTIAL
        elif quarantines:
            status = ExtractionStatus.QUARANTINED
        else:
            status = ExtractionStatus.SUCCESS
        records.append(_make_record(
            paragraph, config, request, raw_response=raw_response,
            response_content=content, response_model=response_model,
            finish_reason=finish_reason,
            usage_json=usage_json, http_status=transport_response.http_status,
            response_headers_json=response_headers_json,
            latency_ms=latency_ms, status=status,
            quarantines=quarantines, frozen_extraction=frozen,
            item_request_id=item_request_id,
            receipt_prompt_sha256=batch_prompt_sha256(),
            batch_size=len(checked),
            batch_paragraphs=checked,
        ))
    return tuple(records)


def _record_to_json(record: RecordedExtractionV1) -> str:
    return canonical_json(record)


def _canonical_preimage(raw_json: str, label: str) -> Any:
    try:
        value = _parse_strict_json(raw_json)
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CacheCorruptionError(f"cache {label} is invalid JSON") from exc
    if canonical_json(value) != raw_json:
        raise CacheCorruptionError(f"cache {label} is not canonical JSON")
    return value


def _paragraph_from_preimage(value: Any, label: str) -> ParagraphInputV1:
    if not isinstance(value, dict) or frozenset(value) != {
        "source_id", "title", "text",
    }:
        raise CacheCorruptionError(f"cache {label} has unexpected keys")
    if any(not isinstance(value[key], str) or not value[key] for key in value):
        raise CacheCorruptionError(f"cache {label} fields must be non-empty strings")
    return ParagraphInputV1(
        source_id=value["source_id"], title=value["title"], text=value["text"],
    )


def _config_from_preimage(record: RecordedExtractionV1) -> ExtractorConfigV1:
    value = _canonical_preimage(record.config_json, "config_json")
    expected_keys = {
        "schema_version", "quote_schema_version", "binder_version", "endpoint",
        "model", "model_revision", "max_concurrency", "timeout_seconds",
        "max_tokens", "max_attempts", "temperature", "top_p", "seed",
        "disable_thinking", "response_format", "max_claims",
        "max_arguments_per_claim", "max_quote_codepoints", "batch_size",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise CacheCorruptionError("cache config_json keys do not match schema")
    try:
        config = ExtractorConfigV1(
            endpoint=value["endpoint"], model=value["model"],
            model_revision=value["model_revision"],
            max_concurrency=value["max_concurrency"],
            timeout_seconds=value["timeout_seconds"],
            max_tokens=value["max_tokens"],
            max_attempts=value["max_attempts"],
            temperature=value["temperature"], top_p=value["top_p"],
            seed=value["seed"], disable_thinking=value["disable_thinking"],
            response_format=value["response_format"],
            max_claims=value["max_claims"],
            max_arguments_per_claim=value["max_arguments_per_claim"],
            max_quote_codepoints=value["max_quote_codepoints"],
            batch_size=value["batch_size"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CacheCorruptionError("cache config_json violates frozen policy") from exc
    if value != _config_payload(config):
        raise CacheCorruptionError("cache config_json preimage changed")
    if record.config_sha256 != sha256_text(record.config_json):
        raise CacheCorruptionError("cache config hash mismatch")
    if record.model != config.model or record.model_revision != config.model_revision:
        raise CacheCorruptionError("cache model does not match config")
    return config


def _reconstruct_request(
    record: RecordedExtractionV1,
    config: ExtractorConfigV1,
) -> tuple[ParagraphInputV1, tuple[ParagraphInputV1, ...], OpenAIRequestV1]:
    paragraph = _paragraph_from_preimage(
        _canonical_preimage(record.source_input_json, "source_input_json"),
        "source_input_json",
    )
    if record.source_id != paragraph.source_id:
        raise CacheCorruptionError("cache source_id does not match source preimage")
    if record.source_text_sha256 != sha256_text(paragraph.text):
        raise CacheCorruptionError("cache source text hash mismatch")
    if record.source_input_sha256 != sha256_text(record.source_input_json):
        raise CacheCorruptionError("cache source input hash mismatch")

    batch_value = _canonical_preimage(record.batch_input_json, "batch_input_json")
    if not isinstance(batch_value, list) or not batch_value:
        raise CacheCorruptionError("cache batch_input_json must be non-empty array")
    batch = tuple(
        _paragraph_from_preimage(item, f"batch_input_json[{index}]")
        for index, item in enumerate(batch_value)
    )
    if tuple(sorted(batch, key=lambda item: item.source_id)) != batch:
        raise CacheCorruptionError("cache batch input is not source_id sorted")
    if len({item.source_id for item in batch}) != len(batch):
        raise CacheCorruptionError("cache batch input has duplicate source_id")
    own = [item for item in batch if item.source_id == record.source_id]
    if len(own) != 1 or own[0] != paragraph:
        raise CacheCorruptionError("cache source preimage is not exact batch member")
    if record.batch_size != len(batch):
        raise CacheCorruptionError("cache batch_size does not match batch preimage")

    is_batch_request = record.request_id != record.batch_request_id
    if is_batch_request:
        request = make_batch_openai_request(batch, config)
        expected_request_id = _batch_item_request_id(request, paragraph)
        expected_prompt_sha256 = batch_prompt_sha256()
    else:
        if len(batch) != 1:
            raise CacheCorruptionError("cache direct request has multiple paragraphs")
        request = make_openai_request(paragraph, config)
        expected_request_id = request.request_id
        expected_prompt_sha256 = prompt_sha256()
    if (
        record.request_id != expected_request_id
        or record.batch_request_id != request.request_id
        or record.prompt_sha256 != expected_prompt_sha256
    ):
        raise CacheCorruptionError("cache request identity does not replay")

    body = _canonical_preimage(record.request_json, "request_json")
    expected_request_json = canonical_json(request.body)
    if body != request.body or record.request_json != expected_request_json:
        raise CacheCorruptionError("cache request body does not replay")
    if record.request_sha256 != sha256_text(record.request_json):
        raise CacheCorruptionError("cache request hash mismatch")
    if request.body.get("model") != config.model:
        raise CacheCorruptionError("cache request model does not match config")
    return paragraph, batch, request


def _adapted_status(
    payload_json: str,
    quarantines: tuple[ExtractionQuarantineV1, ...],
) -> ExtractionStatus:
    accepted_count = len(json.loads(payload_json)["claims"])
    if quarantines and accepted_count:
        return ExtractionStatus.PARTIAL
    if quarantines:
        return ExtractionStatus.QUARANTINED
    return ExtractionStatus.SUCCESS


def _validate_record_preimages(record: RecordedExtractionV1) -> None:
    """Rebuild request and compiler output from retained immutable preimages."""

    if record.schema_version != SCHEMA_VERSION:
        raise CacheCorruptionError("cache schema mismatch")
    if (
        isinstance(record.attempt_ordinal, bool)
        or record.attempt_ordinal <= 0
        or record.attempt_id
        != _attempt_id(record.batch_request_id, record.attempt_ordinal)
    ):
        raise CacheCorruptionError("cache attempt identity mismatch")
    if record.producer != PRODUCER:
        raise CacheCorruptionError("cache producer is not the frozen producer")
    if record.producer_sha256 != sha256_text(record.producer):
        raise CacheCorruptionError("cache producer hash mismatch")
    if record.latency_ms < 0:
        raise CacheCorruptionError("cache latency must be non-negative")
    if record.raw_response_sha256 != sha256_text(record.raw_response):
        raise CacheCorruptionError("cache raw response hash mismatch")

    usage = _canonical_preimage(record.usage_json, "usage_json")
    response_headers = _canonical_preimage(
        record.response_headers_json, "response_headers_json",
    )
    if (
        not isinstance(response_headers, list)
        or any(
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(item, str) for item in pair)
            for pair in response_headers
        )
    ):
        raise CacheCorruptionError("cache response headers must be string pairs")
    if record.http_status is not None and (
        isinstance(record.http_status, bool)
        or not isinstance(record.http_status, int)
        or not 100 <= record.http_status <= 599
    ):
        raise CacheCorruptionError("cache HTTP status is invalid")
    config = _config_from_preimage(record)
    if record.attempt_ordinal > config.max_attempts:
        raise CacheCorruptionError("cache attempt exceeds frozen max_attempts")
    paragraph, batch, request = _reconstruct_request(record, config)

    if record.http_status is None:
        if (
            not isinstance(record.error_type, str) or not record.error_type
            or record.raw_response or record.response_model or record.finish_reason
            or record.response_content_sha256 != sha256_text("") or usage != {}
            or response_headers != []
        ):
            raise CacheCorruptionError("cache transport error preimage mismatch")
        expected_quarantines = (_quarantine(
            record.request_id, claim_index=None, role_path="$transport",
            reason=QuoteRejectCode.TRANSPORT_ERROR,
            detail=f"{record.error_type}: transport call failed",
        ),)
        expected_status = ExtractionStatus.ERROR
        expected_frozen = None
        expected_error_type = record.error_type
    elif not 200 <= record.http_status < 300:
        # Retain a non-2xx body as evidence, even when it looks exactly like a
        # valid model response, but never derive model claims from it.
        if (
            record.response_content_sha256 != sha256_text("")
            or record.response_model or record.finish_reason or usage != {}
            or record.error_type != "HTTPStatusError"
        ):
            raise CacheCorruptionError("cache HTTP error preimage mismatch")
        expected_quarantines = (_quarantine(
            record.request_id, claim_index=None, role_path="$transport",
            reason=QuoteRejectCode.TRANSPORT_ERROR,
            detail=(
                "HTTPStatusError: non-success HTTP status "
                f"{record.http_status}"
            ),
        ),)
        expected_status = ExtractionStatus.ERROR
        expected_frozen = None
        expected_error_type = "HTTPStatusError"
    else:
        content, response_model, finish_reason, envelope_usage, envelope_issue = (
            _extract_openai_content(record.raw_response)
        )
        if record.response_content_sha256 != sha256_text(content):
            raise CacheCorruptionError("cache response content hash mismatch")
        if record.response_model != response_model:
            raise CacheCorruptionError("cache response model does not match raw response")
        if record.finish_reason != finish_reason:
            raise CacheCorruptionError("cache finish reason does not match raw response")
        if record.usage_json != envelope_usage:
            raise CacheCorruptionError("cache usage does not match raw response")

        if envelope_issue is not None:
            reason, detail = envelope_issue
            terminal = _attempt_cap_truncation(record, config)
            if terminal is not None:
                expected_quarantines, expected_frozen = terminal
                expected_status = ExtractionStatus.QUARANTINED
                expected_error_type = None
            else:
                expected_quarantines = (_quarantine(
                    record.request_id, claim_index=None, role_path="$response",
                    reason=reason, detail=detail,
                ),)
                expected_status = ExtractionStatus.ERROR
                expected_frozen = None
                expected_error_type = reason.value
        elif response_model != config.model:
            expected_quarantines = (_quarantine(
                record.request_id, claim_index=None, role_path="$.model",
                reason=QuoteRejectCode.MODEL_MISMATCH,
                detail="response model does not equal requested model",
            ),)
            expected_status = ExtractionStatus.ERROR
            expected_frozen = None
            expected_error_type = "ModelMismatch"
        else:
            if record.request_id == record.batch_request_id:
                payload_json, expected_quarantines = adapt_quote_payload(
                    paragraph, content, request_id=record.request_id, config=config,
                )
            else:
                adapted = adapt_batch_quote_payloads(
                    batch, content, request=request, config=config,
                )
                payload_json, expected_quarantines = adapted[record.source_id]
            expected_frozen = freeze_extraction(
                record.source_id, payload_json, producer=PRODUCER,
                model_revision=config.model_revision,
                prompt_sha256=record.prompt_sha256,
                config_sha256=record.config_sha256,
            )
            expected_status = _adapted_status(payload_json, expected_quarantines)
            expected_error_type = None

    if record.status != expected_status:
        raise CacheCorruptionError("cache status differs from raw response replay")
    if record.quarantines != expected_quarantines:
        raise CacheCorruptionError("cache quarantines differ from raw response replay")
    if record.frozen_extraction != expected_frozen:
        raise CacheCorruptionError("cache frozen extraction differs from raw response replay")
    if record.error_type != expected_error_type:
        raise CacheCorruptionError("cache error_type differs from raw response replay")
    expected_output_sha256 = (
        expected_frozen.output_sha256 if expected_frozen is not None else ""
    )
    if record.output_sha256 != expected_output_sha256:
        raise CacheCorruptionError("cache output hash mismatch")
    if record.record_id != _record_id(record):
        raise CacheCorruptionError("cache record identity mismatch")


def _record_from_dict(value: Any) -> RecordedExtractionV1:
    if not isinstance(value, dict):
        raise CacheCorruptionError("cache record must be an object")
    expected_keys = {field.name for field in fields(RecordedExtractionV1)}
    if set(value) != expected_keys:
        raise CacheCorruptionError("cache record keys do not match v3")
    try:
        quarantines = tuple(
            ExtractionQuarantineV1(
                quarantine_id=item["quarantine_id"],
                claim_index=item["claim_index"],
                role_path=item["role_path"],
                reason=QuoteRejectCode(item["reason"]),
                detail=item["detail"],
                quote_sha256=item["quote_sha256"],
            )
            for item in value["quarantines"]
        )
        frozen_value = value.get("frozen_extraction")
        frozen = (
            FrozenExtractionV1(**frozen_value)
            if isinstance(frozen_value, dict) else None
        )
        record = RecordedExtractionV1(
            schema_version=value["schema_version"],
            record_id=value["record_id"],
            attempt_id=value["attempt_id"],
            attempt_ordinal=value["attempt_ordinal"],
            request_id=value["request_id"],
            batch_request_id=value.get("batch_request_id", value["request_id"]),
            batch_size=int(value.get("batch_size", 1)),
            source_id=value["source_id"],
            source_text_sha256=value["source_text_sha256"],
            source_input_json=value["source_input_json"],
            source_input_sha256=value["source_input_sha256"],
            batch_input_json=value["batch_input_json"],
            producer=value["producer"],
            producer_sha256=value["producer_sha256"],
            model=value["model"],
            model_revision=value["model_revision"],
            response_model=value["response_model"],
            finish_reason=value["finish_reason"],
            prompt_sha256=value["prompt_sha256"],
            config_json=value["config_json"],
            config_sha256=value["config_sha256"],
            request_json=value["request_json"],
            request_sha256=value["request_sha256"],
            http_status=value["http_status"],
            response_headers_json=value["response_headers_json"],
            raw_response=value["raw_response"],
            raw_response_sha256=value["raw_response_sha256"],
            response_content_sha256=value["response_content_sha256"],
            output_sha256=value["output_sha256"],
            usage_json=value["usage_json"],
            latency_ms=int(value["latency_ms"]),
            status=ExtractionStatus(value["status"]),
            quarantines=quarantines,
            frozen_extraction=frozen,
            error_type=value.get("error_type"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CacheCorruptionError(f"invalid cache record: {exc}") from exc
    _validate_record_preimages(record)
    return record


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _start_identity_payload(start: AttemptStartV1) -> dict[str, Any]:
    return {
        "journal_schema_version": start.journal_schema_version,
        "event_type": start.event_type,
        "attempt_id": start.attempt_id,
        "attempt_ordinal": start.attempt_ordinal,
        "batch_request_id": start.batch_request_id,
        "batch_size": start.batch_size,
        "source_ids": start.source_ids,
        "request_sha256": start.request_sha256,
        "config_sha256": start.config_sha256,
        "prompt_sha256": start.prompt_sha256,
        "max_attempts": start.max_attempts,
    }


def _start_id(start: AttemptStartV1) -> str:
    return content_id("recorded_llm_extraction_start", _start_identity_payload(start))


def _finalize_id(finalize: AttemptFinalizeV1) -> str:
    return content_id("recorded_llm_extraction_finalize", {
        "journal_schema_version": finalize.journal_schema_version,
        "event_type": finalize.event_type,
        "start_id": finalize.start_id,
        "attempt_id": finalize.attempt_id,
        "attempt_ordinal": finalize.attempt_ordinal,
        "batch_request_id": finalize.batch_request_id,
        "record_ids": tuple(record.record_id for record in finalize.records),
    })


def _start_to_json(start: AttemptStartV1) -> str:
    return canonical_json(asdict(start))


def _finalize_to_json(finalize: AttemptFinalizeV1) -> str:
    return canonical_json(asdict(finalize))


def _start_from_dict(value: Any) -> AttemptStartV1:
    expected = {field.name for field in fields(AttemptStartV1)}
    if not isinstance(value, dict) or set(value) != expected:
        raise CacheCorruptionError("cache START keys do not match journal schema")
    try:
        source_ids = tuple(value["source_ids"])
        start = AttemptStartV1(
            journal_schema_version=value["journal_schema_version"],
            event_type=value["event_type"],
            start_id=value["start_id"],
            attempt_id=value["attempt_id"],
            attempt_ordinal=value["attempt_ordinal"],
            batch_request_id=value["batch_request_id"],
            batch_size=value["batch_size"],
            source_ids=source_ids,
            request_sha256=value["request_sha256"],
            config_sha256=value["config_sha256"],
            prompt_sha256=value["prompt_sha256"],
            max_attempts=value["max_attempts"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CacheCorruptionError(f"invalid cache START: {exc}") from exc
    if (
        start.journal_schema_version != JOURNAL_SCHEMA_VERSION
        or start.event_type != START_EVENT
    ):
        raise CacheCorruptionError("cache START schema or event type mismatch")
    if (
        isinstance(start.attempt_ordinal, bool)
        or not isinstance(start.attempt_ordinal, int)
        or start.attempt_ordinal <= 0
        or isinstance(start.max_attempts, bool)
        or not isinstance(start.max_attempts, int)
        or not 1 <= start.max_attempts <= 8
        or start.attempt_ordinal > start.max_attempts
    ):
        raise CacheCorruptionError("cache START attempt ordinal/cap is invalid")
    if (
        isinstance(start.batch_size, bool)
        or not isinstance(start.batch_size, int)
        or start.batch_size <= 0
        or len(start.source_ids) != start.batch_size
        or tuple(sorted(start.source_ids)) != start.source_ids
        or len(set(start.source_ids)) != len(start.source_ids)
        or any(not isinstance(item, str) or not item for item in start.source_ids)
    ):
        raise CacheCorruptionError("cache START source membership is invalid")
    if not isinstance(start.batch_request_id, str) or not start.batch_request_id:
        raise CacheCorruptionError("cache START batch_request_id is invalid")
    if any(
        not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None
        for digest in (
            start.request_sha256, start.config_sha256, start.prompt_sha256,
        )
    ):
        raise CacheCorruptionError("cache START digest is invalid")
    if start.attempt_id != _attempt_id(
        start.batch_request_id, start.attempt_ordinal,
    ):
        raise CacheCorruptionError("cache START attempt identity mismatch")
    if start.start_id != _start_id(start):
        raise CacheCorruptionError("cache START identity mismatch")
    return start


def _finalize_from_dict(value: Any) -> AttemptFinalizeV1:
    expected = {field.name for field in fields(AttemptFinalizeV1)}
    if not isinstance(value, dict) or set(value) != expected:
        raise CacheCorruptionError("cache FINALIZE keys do not match journal schema")
    try:
        raw_records = value["records"]
        if not isinstance(raw_records, list) or not raw_records:
            raise TypeError("records must be a non-empty array")
        records = tuple(_record_from_dict(item) for item in raw_records)
        finalize = AttemptFinalizeV1(
            journal_schema_version=value["journal_schema_version"],
            event_type=value["event_type"],
            finalize_id=value["finalize_id"],
            start_id=value["start_id"],
            attempt_id=value["attempt_id"],
            attempt_ordinal=value["attempt_ordinal"],
            batch_request_id=value["batch_request_id"],
            records=records,
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, CacheCorruptionError):
            raise
        raise CacheCorruptionError(f"invalid cache FINALIZE: {exc}") from exc
    if (
        finalize.journal_schema_version != JOURNAL_SCHEMA_VERSION
        or finalize.event_type != FINALIZE_EVENT
    ):
        raise CacheCorruptionError("cache FINALIZE schema or event type mismatch")
    if (
        isinstance(finalize.attempt_ordinal, bool)
        or not isinstance(finalize.attempt_ordinal, int)
        or finalize.attempt_ordinal <= 0
        or not isinstance(finalize.batch_request_id, str)
        or not finalize.batch_request_id
    ):
        raise CacheCorruptionError("cache FINALIZE attempt fields are invalid")
    if finalize.attempt_id != _attempt_id(
        finalize.batch_request_id, finalize.attempt_ordinal,
    ):
        raise CacheCorruptionError("cache FINALIZE attempt identity mismatch")
    if finalize.finalize_id != _finalize_id(finalize):
        raise CacheCorruptionError("cache FINALIZE identity mismatch")
    return finalize


def _make_start(
    paragraphs: Sequence[ParagraphInputV1],
    config: ExtractorConfigV1,
    request: OpenAIRequestV1,
    attempt_ordinal: int,
) -> AttemptStartV1:
    checked = tuple(sorted(paragraphs, key=lambda item: item.source_id))
    provisional = AttemptStartV1(
        journal_schema_version=JOURNAL_SCHEMA_VERSION,
        event_type=START_EVENT,
        start_id="",
        attempt_id=_attempt_id(request.request_id, attempt_ordinal),
        attempt_ordinal=attempt_ordinal,
        batch_request_id=request.request_id,
        batch_size=len(checked),
        source_ids=tuple(item.source_id for item in checked),
        request_sha256=sha256_text(canonical_json(request.body)),
        config_sha256=config_sha256(config),
        prompt_sha256=(
            prompt_sha256() if len(checked) == 1 and config.batch_size == 1
            else batch_prompt_sha256()
        ),
        max_attempts=config.max_attempts,
    )
    return replace(provisional, start_id=_start_id(provisional))


def _make_finalize(
    start: AttemptStartV1,
    records: Sequence[RecordedExtractionV1],
) -> AttemptFinalizeV1:
    provisional = AttemptFinalizeV1(
        journal_schema_version=JOURNAL_SCHEMA_VERSION,
        event_type=FINALIZE_EVENT,
        finalize_id="",
        start_id=start.start_id,
        attempt_id=start.attempt_id,
        attempt_ordinal=start.attempt_ordinal,
        batch_request_id=start.batch_request_id,
        records=tuple(records),
    )
    return replace(provisional, finalize_id=_finalize_id(provisional))


def _fsync_parent_directory(path: Path) -> None:
    """Persist a newly-created journal directory entry before endpoint use."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(path.parent, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class JSONLExtractionCache:
    """Append-only START/FINALIZE journal keyed by immutable request IDs."""

    _TERMINAL = frozenset({
        ExtractionStatus.SUCCESS,
        ExtractionStatus.PARTIAL,
        ExtractionStatus.QUARANTINED,
    })

    def __init__(self, path: str | Path):
        self.path = Path(path)
        lock_key = sha256_text(str(self.path.resolve()))
        self.run_lock_path = (
            Path(tempfile.gettempdir()) / "hswm-recorded-llm-locks"
            / f"{lock_key}.lock"
        )

    def _open_locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    @contextmanager
    def run_lock(self):
        """Own one cache run or fail immediately without making endpoint calls."""

        self.run_lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.run_lock_path.open("a+b")
        acquired = False
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError as exc:
                raise CacheRunLockedError(
                    f"extraction cache run is already active: {self.path}"
                ) from exc
            yield
        finally:
            try:
                if acquired:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    @staticmethod
    def _repair_tail(handle) -> bytes:
        handle.seek(0)
        data = handle.read()
        if data and not data.endswith(b"\n"):
            last_newline = data.rfind(b"\n")
            valid_length = last_newline + 1 if last_newline >= 0 else 0
            handle.seek(valid_length)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
            data = data[:valid_length]
        return data

    @staticmethod
    def _decode(data: bytes) -> AttemptJournalV1:
        events: list[JournalEventV1] = []
        for line_number, line in enumerate(data.splitlines(), 1):
            if not line:
                raise CacheCorruptionError(
                    f"blank extraction JSONL line {line_number} is forbidden"
                )
            try:
                raw_line = line.decode("utf-8")
                decoded = _parse_strict_json(raw_line)
            except (
                UnicodeDecodeError, json.JSONDecodeError, _DuplicateJSONKey,
                TypeError, ValueError,
            ) as exc:
                raise CacheCorruptionError(
                    f"invalid complete JSONL line {line_number}: {exc}"
                ) from exc
            if canonical_json(decoded) != raw_line:
                raise CacheCorruptionError(
                    f"non-canonical complete JSONL line {line_number}"
                )
            event_type = decoded.get("event_type") if isinstance(decoded, dict) else None
            try:
                if event_type == START_EVENT:
                    events.append(_start_from_dict(decoded))
                elif event_type == FINALIZE_EVENT:
                    events.append(_finalize_from_dict(decoded))
                else:
                    raise CacheCorruptionError(
                        "cache journal event_type must be START or FINALIZE"
                    )
            except CacheCorruptionError as exc:
                raise CacheCorruptionError(
                    f"invalid extraction JSONL line {line_number}: {exc}"
                ) from exc
        return JSONLExtractionCache._validate_journal(tuple(events))

    @staticmethod
    def _validate_finalize_records(
        start: AttemptStartV1,
        records: Sequence[RecordedExtractionV1],
    ) -> bool:
        checked = tuple(records)
        source_ids = tuple(item.source_id for item in checked)
        if (
            len(checked) != start.batch_size
            or source_ids != start.source_ids
            or len(set(source_ids)) != len(source_ids)
        ):
            raise CacheCorruptionError(
                "cache FINALIZE batch is incomplete or unordered"
            )
        if any(
            item.attempt_id != start.attempt_id
            or item.attempt_ordinal != start.attempt_ordinal
            or item.batch_request_id != start.batch_request_id
            or item.batch_size != start.batch_size
            or item.request_sha256 != start.request_sha256
            or item.config_sha256 != start.config_sha256
            or item.prompt_sha256 != start.prompt_sha256
            for item in checked
        ):
            raise CacheCorruptionError("cache FINALIZE does not bind its START")
        shared_fields = (
            "raw_response_sha256", "response_model", "finish_reason",
            "usage_json", "latency_ms", "config_sha256", "prompt_sha256",
            "request_sha256", "batch_input_json",
        )
        if any(
            len({getattr(item, field_name) for item in checked}) != 1
            for field_name in shared_fields
        ):
            raise CacheCorruptionError("cache FINALIZE batch receipts disagree")
        if any(
            _config_from_preimage(item).max_attempts != start.max_attempts
            for item in checked
        ):
            raise CacheCorruptionError("cache FINALIZE cap differs from START")
        terminal_members = [
            item.status in JSONLExtractionCache._TERMINAL for item in checked
        ]
        if any(terminal_members) != all(terminal_members):
            raise CacheCorruptionError(
                "cache FINALIZE mixes terminal and nonterminal rows"
            )
        return all(terminal_members)

    @staticmethod
    def _validate_journal(events: tuple[JournalEventV1, ...]) -> AttemptJournalV1:
        """Validate physical START order and one-way START-to-FINALIZE binding."""

        starts: list[AttemptStartV1] = []
        finalizes: list[AttemptFinalizeV1] = []
        records: list[RecordedExtractionV1] = []
        start_by_id: dict[str, AttemptStartV1] = {}
        finalized_attempts: set[str] = set()
        last_start_ordinal: dict[str, int] = {}
        metadata_by_batch: dict[str, tuple[Any, ...]] = {}
        terminal_batches: set[str] = set()

        for event in events:
            if isinstance(event, AttemptStartV1):
                batch_id = event.batch_request_id
                if batch_id in terminal_batches:
                    raise CacheCorruptionError(
                        "cache START follows a terminal FINALIZE"
                    )
                expected_ordinal = last_start_ordinal.get(batch_id, 0) + 1
                if event.attempt_ordinal != expected_ordinal:
                    raise CacheCorruptionError(
                        "cache START ordinals are not in physical order"
                    )
                if event.start_id in start_by_id:
                    raise CacheCorruptionError("cache START is duplicated")
                metadata = (
                    event.batch_size, event.source_ids, event.request_sha256,
                    event.config_sha256, event.prompt_sha256, event.max_attempts,
                )
                prior_metadata = metadata_by_batch.setdefault(batch_id, metadata)
                if metadata != prior_metadata:
                    raise CacheCorruptionError(
                        "cache START retry metadata changed"
                    )
                start_by_id[event.start_id] = event
                last_start_ordinal[batch_id] = event.attempt_ordinal
                starts.append(event)
                continue

            start = start_by_id.get(event.start_id)
            if start is None:
                raise CacheCorruptionError("cache FINALIZE has no prior START")
            if event.attempt_id in finalized_attempts:
                raise CacheCorruptionError("cache FINALIZE result is duplicated")
            if (
                event.attempt_id != start.attempt_id
                or event.attempt_ordinal != start.attempt_ordinal
                or event.batch_request_id != start.batch_request_id
            ):
                raise CacheCorruptionError("cache FINALIZE metadata differs from START")
            if last_start_ordinal[event.batch_request_id] != event.attempt_ordinal:
                raise CacheCorruptionError(
                    "cache FINALIZE is in reverse physical attempt order"
                )
            terminal = JSONLExtractionCache._validate_finalize_records(
                start, event.records,
            )
            finalized_attempts.add(event.attempt_id)
            if terminal:
                terminal_batches.add(event.batch_request_id)
            finalizes.append(event)
            records.extend(event.records)

        return AttemptJournalV1(
            events=events,
            starts=tuple(starts),
            finalizes=tuple(finalizes),
            records=tuple(records),
        )

    def journal(self) -> AttemptJournalV1:
        handle = self._open_locked()
        try:
            return self._decode(self._repair_tail(handle))
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def records(self) -> tuple[RecordedExtractionV1, ...]:
        return self.journal().records

    def get(self, request_id: str) -> RecordedExtractionV1 | None:
        matches = [
            record for record in self.records()
            if record.request_id == request_id and record.status in self._TERMINAL
        ]
        return matches[-1] if matches else None

    def reserve_attempt(
        self,
        paragraphs: Sequence[ParagraphInputV1],
        config: ExtractorConfigV1,
        request: OpenAIRequestV1,
    ) -> AttemptStartV1:
        """Append and fsync START before the caller is allowed to invoke HTTP."""

        checked = tuple(sorted(paragraphs, key=lambda item: item.source_id))
        if not checked:
            raise ValueError("attempt must contain at least one paragraph")
        if len(checked) > config.batch_size:
            raise ValueError("attempt exceeds frozen batch_size")
        if config.batch_size == 1:
            expected_request = make_openai_request(checked[0], config)
        else:
            expected_request = make_batch_openai_request(checked, config)
        if request != expected_request:
            raise ValueError("attempt request does not replay from source/config")

        handle = self._open_locked()
        try:
            journal = self._decode(self._repair_tail(handle))
            prior_starts = [
                item for item in journal.starts
                if item.batch_request_id == request.request_id
            ]
            terminal = any(
                item.batch_request_id == request.request_id
                and all(record.status in self._TERMINAL for record in item.records)
                for item in journal.finalizes
            )
            if terminal:
                raise CacheCorruptionError(
                    "frozen extraction already has a terminal FINALIZE"
                )
            next_ordinal = len(prior_starts) + 1
            if next_ordinal > config.max_attempts:
                raise AttemptCapExhaustedError(
                    "frozen extraction START cap is already exhausted"
                )
            start = _make_start(checked, config, request, next_ordinal)
            self._validate_journal((*journal.events, start))
            handle.seek(0, os.SEEK_END)
            handle.write((_start_to_json(start) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
            _fsync_parent_directory(self.path)
            return start
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def finalize_attempt(
        self,
        start: AttemptStartV1,
        records: Sequence[RecordedExtractionV1],
    ) -> tuple[RecordedExtractionV1, ...]:
        """Bind one complete raw result batch to its already-durable START."""

        checked = tuple(sorted(records, key=lambda item: item.source_id))
        if not checked:
            raise ValueError("attempt must contain at least one record")
        if (
            tuple(item.source_id for item in checked) != start.source_ids
            or any(item.batch_request_id != start.batch_request_id for item in checked)
        ):
            raise ValueError("attempt records do not match reserved START")
        config = _config_from_preimage(checked[0])
        assigned: list[RecordedExtractionV1] = []
        for record in checked:
            provisional = replace(
                record,
                attempt_id=start.attempt_id,
                attempt_ordinal=start.attempt_ordinal,
                record_id="",
            )
            provisional = _terminalize_attempt_cap_truncation(provisional, config)
            assigned_record = replace(
                provisional, record_id=_record_id(provisional),
            )
            _validate_record_preimages(assigned_record)
            assigned.append(assigned_record)
        finalize = _make_finalize(start, assigned)

        handle = self._open_locked()
        try:
            journal = self._decode(self._repair_tail(handle))
            self._validate_journal((*journal.events, finalize))
            handle.seek(0, os.SEEK_END)
            handle.write((_finalize_to_json(finalize) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
            _fsync_parent_directory(self.path)
            return tuple(assigned)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def append_attempt(
        self,
        records: Sequence[RecordedExtractionV1],
    ) -> tuple[RecordedExtractionV1, ...]:
        """Compatibility helper for offline fixtures; production reserves first."""

        checked = tuple(sorted(records, key=lambda item: item.source_id))
        if not checked:
            raise ValueError("attempt must contain at least one record")
        if any(item.record_id != _record_id(item) for item in checked):
            raise ValueError("record identity mismatch")
        batch_ids = {item.batch_request_id for item in checked}
        batch_sizes = {item.batch_size for item in checked}
        if (
            len(batch_ids) != 1 or len(batch_sizes) != 1
            or len(checked) != next(iter(batch_sizes))
            or len({item.source_id for item in checked}) != len(checked)
            or len({item.config_sha256 for item in checked}) != 1
        ):
            raise ValueError("attempt records do not form one complete batch call")
        config = _config_from_preimage(checked[0])
        _, batch, request = _reconstruct_request(checked[0], config)
        with self.run_lock():
            start = self.reserve_attempt(batch, config, request)
            return self.finalize_attempt(start, checked)

    def append(self, record: RecordedExtractionV1) -> bool:
        """Compatibility wrapper for a one-row endpoint attempt."""

        self.append_attempt((record,))
        return True


def load_attempt_journal_strict(path: str | Path) -> AttemptJournalV1:
    """Validate a frozen journal without locking, tail repair, or mutation.

    This is the artifact/CLOSE boundary. A complete final newline is required;
    compilation must refuse while ``unmatched_starts`` is non-empty.
    """

    source = Path(path)
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise CacheCorruptionError(f"cannot read extraction journal: {exc}") from exc
    if data and not data.endswith(b"\n"):
        raise CacheCorruptionError("extraction journal has an incomplete final line")
    return JSONLExtractionCache._decode(data)


def _execute_reserved_attempt(
    cache: JSONLExtractionCache,
    group: tuple[ParagraphInputV1, ...],
    request: OpenAIRequestV1,
    config: ExtractorConfigV1,
    sender: Transport,
) -> tuple[RecordedExtractionV1, ...]:
    """Durably reserve, then immediately start one endpoint call and finalize."""

    start = cache.reserve_attempt(group, config, request)
    if config.batch_size == 1:
        result = extract_paragraph(group[0], config, sender)
        records = (result,)
    else:
        records = extract_paragraph_batch(group, config, sender)
    return cache.finalize_attempt(start, records)


def run_extraction_batch(
    paragraphs: Sequence[ParagraphInputV1],
    config: ExtractorConfigV1,
    *,
    cache_path: str | Path,
    transport: Transport | None = None,
) -> ExtractionBatchV1:
    """Own one cache run nonblockingly, preserving in-process concurrency."""

    cache = JSONLExtractionCache(cache_path)
    with cache.run_lock():
        return _run_extraction_batch_locked(
            paragraphs, config, cache=cache, transport=transport,
        )


def _run_extraction_batch_locked(
    paragraphs: Sequence[ParagraphInputV1],
    config: ExtractorConfigV1,
    *,
    cache: JSONLExtractionCache,
    transport: Transport | None = None,
) -> ExtractionBatchV1:
    """Run/cache paragraph requests; optionally pack up to eight per HTTP call."""

    if isinstance(paragraphs, (str, bytes)) or not isinstance(paragraphs, Sequence):
        raise TypeError("paragraphs must be a sequence of ParagraphInputV1")
    checked = tuple(paragraphs)
    for paragraph in checked:
        _validate_paragraph(paragraph)
    source_ids = [paragraph.source_id for paragraph in checked]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("paragraph source_id values must be unique")

    sender = transport or openai_compatible_transport()
    records_by_source: dict[str, RecordedExtractionV1] = {}
    terminal_by_request: dict[str, RecordedExtractionV1] = {}
    latest_by_request: dict[str, RecordedExtractionV1] = {}
    max_attempt_by_batch: dict[str, int] = {}
    journal = cache.journal()
    cached_records = journal.records
    for record in cached_records:
        latest_by_request[record.request_id] = record
        if record.status in cache._TERMINAL:
            terminal_by_request[record.request_id] = record
    for start in journal.starts:
        max_attempt_by_batch[start.batch_request_id] = max(
            max_attempt_by_batch.get(start.batch_request_id, 0),
            start.attempt_ordinal,
        )
    ordered = tuple(sorted(checked, key=lambda item: item.source_id))
    groups = tuple(
        ordered[index:index + config.batch_size]
        for index in range(0, len(ordered), config.batch_size)
    )
    pending: list[tuple[tuple[ParagraphInputV1, ...], OpenAIRequestV1]] = []
    cache_hits = 0
    for group in groups:
        if config.batch_size == 1:
            request = make_openai_request(group[0], config)
            item_ids = (request.request_id,)
        else:
            request = make_batch_openai_request(group, config)
            item_ids = tuple(_batch_item_request_id(request, item) for item in group)
        cached_group = tuple(terminal_by_request.get(item_id) for item_id in item_ids)
        # Replay an incomplete deterministic group in full.  Otherwise a
        # process interruption would silently change each item's model context.
        if all(record is not None for record in cached_group):
            for paragraph, record in zip(group, cached_group, strict=True):
                assert record is not None
                records_by_source[paragraph.source_id] = record
                cache_hits += 1
        elif max_attempt_by_batch.get(request.request_id, 0) >= config.max_attempts:
            latest_group = tuple(latest_by_request.get(item_id) for item_id in item_ids)
            if any(record is None for record in latest_group):
                raise AttemptCapExhaustedError(
                    "attempt cap was consumed by unmatched START without FINALIZE"
                )
            for paragraph, record in zip(group, latest_group, strict=True):
                assert record is not None
                records_by_source[paragraph.source_id] = record
        else:
            pending.append((group, request))

    with ThreadPoolExecutor(max_workers=config.max_concurrency) as executor:
        futures = {}
        for group, request in pending:
            future = executor.submit(
                _execute_reserved_attempt,
                cache, group, request, config, sender,
            )
            futures[future] = group
        for future in as_completed(futures):
            assigned_records = future.result()
            for record in assigned_records:
                records_by_source[record.source_id] = record

    output_records = tuple(records_by_source[item.source_id] for item in checked)
    attempt_cap_exhausted = sum(
        record.status == ExtractionStatus.ERROR
        and (
            record.attempt_ordinal >= config.max_attempts
            or max_attempt_by_batch.get(record.batch_request_id, 0)
            >= config.max_attempts
        )
        for record in output_records
    )
    return ExtractionBatchV1(
        records=output_records,
        cache_hits=cache_hits,
        endpoint_calls=len(pending),
        attempt_cap_exhausted=attempt_cap_exhausted,
    )


def _load_paragraph_jsonl(path: Path) -> tuple[ParagraphInputV1, ...]:
    paragraphs: list[ParagraphInputV1] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or frozenset(value) != {
            "source_id", "title", "text",
        }:
            raise ValueError(
                f"input line {line_number} must contain only source_id/title/text"
            )
        paragraphs.append(ParagraphInputV1(**value))
    return tuple(paragraphs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", required=True, type=Path)
    parser.add_argument("--cache-jsonl", required=True, type=Path)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--max-concurrency", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    args = parser.parse_args(argv)

    paragraphs = _load_paragraph_jsonl(args.input_jsonl)
    config = ExtractorConfigV1(
        endpoint=args.endpoint, model=args.model,
        model_revision=args.model_revision,
        max_concurrency=args.max_concurrency,
        batch_size=args.batch_size,
        timeout_seconds=args.timeout_seconds, max_tokens=args.max_tokens,
        max_attempts=args.max_attempts,
    )
    api_key = os.environ.get(args.api_key_env)
    result = run_extraction_batch(
        paragraphs, config, cache_path=args.cache_jsonl,
        transport=openai_compatible_transport(api_key=api_key),
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "records": len(result.records),
        "cache_hits": result.cache_hits,
        "endpoint_calls": result.endpoint_calls,
        "attempt_cap_exhausted": result.attempt_cap_exhausted,
        "attempt_cap_terminal_sources": sum(
            any(
                quarantine.reason
                == QuoteRejectCode.TRUNCATED_RESPONSE_AT_ATTEMPT_CAP
                for quarantine in record.quarantines
            )
            for record in result.records
        ),
        "status_counts": {
            status.value: sum(record.status == status for record in result.records)
            for status in ExtractionStatus
        },
    }
    print(canonical_json(summary))
    return 0 if all(record.status != ExtractionStatus.ERROR for record in result.records) else 2


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
