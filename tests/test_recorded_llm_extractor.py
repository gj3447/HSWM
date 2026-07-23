"""Teeth for the recorded, evidence-preserving B3 LLM adapter."""
from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
import multiprocessing
from pathlib import Path
import threading
import time

import pytest

import claim_builder as cb
import recorded_llm_extractor as rx
from title_anchor_builder import ParagraphInputV1
from world_ir import sha256_text


def _paragraph(source_id: str = "src:green") -> ParagraphInputV1:
    return ParagraphInputV1(
        source_id=source_id,
        title="Green",
        text=(
            "Green is the fourth studio album by Steve Hillage and was "
            "recorded in London."
        ),
    )


def _config(**changes) -> rx.ExtractorConfigV1:
    base = rx.ExtractorConfigV1(
        endpoint="http://example.invalid/v1",
        model="fixture-model",
        model_revision="fixture-model@sha256:0123",
        max_concurrency=2,
    )
    return replace(base, **changes)


def _content(*, location: str = "London") -> str:
    return json.dumps({
        "claims": [{
            "subject": "Green",
            "predicate": "is the fourth studio album by",
            "arguments": [
                {"role": "artist", "exact": "Steve Hillage"},
                {"role": "location", "exact": location},
            ],
        }],
    }, ensure_ascii=False, separators=(",", ":"))


def _response(
    content: str | None = None,
    *,
    model: str = "fixture-model",
    finish_reason: str | None = "stop",
) -> str:
    return json.dumps({
        "id": "completion-fixture",
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content or _content()},
            "finish_reason": finish_reason,
        }],
        "usage": {"prompt_tokens": 101, "completion_tokens": 37,
                  "total_tokens": 138},
    }, ensure_ascii=False, separators=(",", ":"))


def test_request_is_query_blind_and_decoding_controls_are_frozen():
    request = rx.make_openai_request(_paragraph(), _config())

    assert request.body["temperature"] == 0
    assert request.body["response_format"] == {"type": "json_object"}
    assert request.body["chat_template_kwargs"] == {"enable_thinking": False}
    assert request.body["seed"] == 0
    serialized = json.dumps(request.body)
    for forbidden in ('"qid"', '"gold"', '"support"', '"hop"', '"answer"'):
        assert forbidden not in serialized
    assert "TITLE_JSON" in request.body["messages"][1]["content"]
    assert "TEXT_JSON" in request.body["messages"][1]["content"]

    with pytest.raises(ValueError, match="temperature is frozen"):
        _config(temperature=1)
    with pytest.raises(ValueError, match="disable_thinking"):
        _config(disable_thinking=False)
    with pytest.raises(ValueError, match="max_attempts"):
        _config(max_attempts=True)


def test_execution_controls_are_bound_into_config_and_request_identity():
    base = _config()
    assert rx.ExtractorConfigV1(
        endpoint="http://example.invalid/v1",
        model="fixture-model",
        model_revision="fixture-revision",
    ).max_tokens == 1024
    base_sha = rx.config_sha256(base)
    base_request = rx.make_openai_request(_paragraph(), base).request_id

    for changed in (
        _config(max_concurrency=3),
        _config(timeout_seconds=181.0),
        _config(max_attempts=3),
    ):
        assert rx.config_sha256(changed) != base_sha
        assert rx.make_openai_request(_paragraph(), changed).request_id != base_request


def test_nfkc_binder_maps_compatibility_quote_to_original_codepoint_span():
    source = "The ﬁle was archived."  # U+FB01 -> "fi" under NFKC
    bound = rx.bind_unique_nfkc_quote(source, "file")
    assert bound.exact == "ﬁle"
    assert source[bound.start:bound.end] == "ﬁle"
    assert bound.model_quote == "file"
    assert bound.offset_unit == rx.OFFSET_UNIT

    with pytest.raises(ValueError, match="ambiguous_quote"):
        rx.bind_unique_nfkc_quote("Paris met Paris.", "Paris")
    with pytest.raises(ValueError, match="hallucinated_quote"):
        rx.bind_unique_nfkc_quote("Green exists.", "green")  # no case repair


def test_valid_response_preserves_raw_receipts_and_compiles_offline():
    paragraph = _paragraph()
    raw_response = _response()
    record = rx.extract_paragraph(
        paragraph, _config(), lambda request: raw_response,
    )

    assert record.status == rx.ExtractionStatus.SUCCESS
    assert record.raw_response == raw_response
    assert record.raw_response_sha256 == sha256_text(raw_response)
    assert record.response_model == "fixture-model"
    assert record.finish_reason == "stop"
    assert json.loads(record.usage_json)["total_tokens"] == 138
    assert record.producer_sha256 == sha256_text(record.producer)
    assert record.prompt_sha256 == rx.prompt_sha256()
    assert record.config_sha256 == rx.config_sha256(_config())
    assert json.loads(record.config_json)["model"] == "fixture-model"
    assert json.loads(record.request_json)["model"] == "fixture-model"
    assert json.loads(record.source_input_json)["source_id"] == paragraph.source_id
    assert record.frozen_extraction is not None
    assert record.output_sha256 == record.frozen_extraction.output_sha256

    parsed = cb.parse_extraction_payload(paragraph, record.frozen_extraction)
    assert parsed.quarantines == ()
    assert len(parsed.observations) == 1
    observation = parsed.observations[0]
    assert observation.subject.exact == "Green"
    assert observation.predicate.exact == "is the fourth studio album by"
    assert [(item.role, item.exact) for item in observation.arguments] == [
        ("artist", "Steve Hillage"), ("location", "London"),
    ]


def test_missing_hallucinated_and_ambiguous_quotes_are_typed_quarantine():
    paragraph = ParagraphInputV1(
        "src:ambiguous", "Paris",
        "Paris was compared with Paris by Alice.",
    )
    content = json.dumps({
        "claims": [
            {
                "subject": "Alice",
                "predicate": "compared with",
                "arguments": [{"role": "place", "exact": "Paris"}],
            },
            {
                "subject": "Alice",
                "predicate": "compared with",
                "arguments": [{"role": "place", "exact": "Berlin"}],
            },
        ],
    }, separators=(",", ":"))
    record = rx.extract_paragraph(
        paragraph, _config(), lambda request: _response(content),
    )

    assert record.status == rx.ExtractionStatus.QUARANTINED
    assert {item.reason for item in record.quarantines} == {
        rx.QuoteRejectCode.AMBIGUOUS_QUOTE,
        rx.QuoteRejectCode.HALLUCINATED_QUOTE,
    }
    assert record.frozen_extraction is not None
    assert json.loads(record.frozen_extraction.payload_json)["claims"] == []
    assert all(item.quote_sha256 for item in record.quarantines)


def test_one_bad_claim_does_not_erase_a_separate_evidenced_claim():
    content = json.dumps({
        "claims": [
            {
                "subject": "Green",
                "predicate": "recorded in",
                "arguments": [{"role": "location", "exact": "London"}],
            },
            {
                "subject": "Green",
                "predicate": "recorded in",
                "arguments": [{"role": "location", "exact": "Mars"}],
            },
        ],
    }, separators=(",", ":"))
    record = rx.extract_paragraph(
        _paragraph(), _config(), lambda request: _response(content),
    )
    assert record.status == rx.ExtractionStatus.PARTIAL
    assert [item.reason for item in record.quarantines] == [
        rx.QuoteRejectCode.HALLUCINATED_QUOTE,
    ]
    assert len(json.loads(record.frozen_extraction.payload_json)["claims"]) == 1


def test_evaluation_fields_and_duplicate_json_keys_fail_closed():
    paragraph = _paragraph()
    request = rx.make_openai_request(paragraph, _config())
    leaked = json.dumps({
        "claims": [{
            "subject": "Green", "predicate": "recorded in",
            "arguments": [{"role": "location", "exact": "London"}],
            "gold": True,
        }],
    }, separators=(",", ":"))
    payload, quarantines = rx.adapt_quote_payload(
        paragraph, leaked, request_id=request.request_id, config=_config(),
    )
    assert json.loads(payload)["claims"] == []
    assert [item.reason for item in quarantines] == [
        rx.QuoteRejectCode.EVALUATION_LABEL_LEAKAGE,
    ]

    duplicate = '{"claims":[],"claims":[]}'
    _, quarantines = rx.adapt_quote_payload(
        paragraph, duplicate, request_id=request.request_id, config=_config(),
    )
    assert [item.reason for item in quarantines] == [
        rx.QuoteRejectCode.DUPLICATE_JSON_KEY,
    ]


def test_raw_qa_mapping_is_rejected_at_input_boundary(tmp_path: Path):
    raw_row = {
        "source_id": "src:x", "title": "X", "text": "X exists.",
        "question": "leak", "answer": "leak", "gold": True, "hop": 4,
    }
    with pytest.raises(TypeError, match="raw QA/gold/support rows are forbidden"):
        rx.run_extraction_batch(
            [raw_row], _config(), cache_path=tmp_path / "cache.jsonl",
            transport=lambda request: _response(),
        )


def test_record_id_is_stable_across_runtime_latency(monkeypatch: pytest.MonkeyPatch):
    ticks = iter([0, 2_000_000, 100_000_000, 109_000_000])
    monkeypatch.setattr(rx.time, "perf_counter_ns", lambda: next(ticks))
    first = rx.extract_paragraph(_paragraph(), _config(), lambda request: _response())
    second = rx.extract_paragraph(_paragraph(), _config(), lambda request: _response())
    assert first.latency_ms == 2
    assert second.latency_ms == 9
    assert first.record_id == second.record_id


def test_jsonl_cache_resumes_and_repairs_only_incomplete_tail(tmp_path: Path):
    cache_path = tmp_path / "extractions.jsonl"
    calls = 0

    def transport(request):
        nonlocal calls
        calls += 1
        return _response()

    first = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    assert calls == 1
    assert first.endpoint_calls == 1 and first.cache_hits == 0
    assert second.endpoint_calls == 0 and second.cache_hits == 1
    assert first.records[0].record_id == second.records[0].record_id
    physical = [
        json.loads(line)
        for line in cache_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [item["event_type"] for item in physical] == [
        rx.START_EVENT, rx.FINALIZE_EVENT,
    ]

    with cache_path.open("ab") as handle:
        handle.write(b'{"interrupted"')
    before = cache_path.read_bytes()
    with pytest.raises(rx.CacheCorruptionError, match="incomplete final line"):
        rx.load_attempt_journal_strict(cache_path)
    assert cache_path.read_bytes() == before
    records = rx.JSONLExtractionCache(cache_path).records()
    assert [item.record_id for item in records] == [first.records[0].record_id]
    assert cache_path.read_bytes().endswith(b"\n")


def test_start_is_fsynced_and_strictly_visible_before_transport(tmp_path: Path):
    cache_path = tmp_path / "pre-call-start.jsonl"
    observed = []

    def transport(_request):
        journal = rx.load_attempt_journal_strict(cache_path)
        observed.append(journal)
        assert len(journal.starts) == 1
        assert journal.starts[0].attempt_ordinal == 1
        assert journal.finalizes == ()
        assert journal.unmatched_starts == journal.starts
        return _response()

    result = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    assert result.endpoint_calls == 1
    assert len(observed) == 1
    journal = rx.load_attempt_journal_strict(cache_path)
    assert len(journal.starts) == len(journal.finalizes) == 1
    assert journal.unmatched_starts == ()
    assert journal.records[0].raw_response == _response()


def test_crash_after_start_consumes_ordinal_and_cap_blocks_third_call(
    tmp_path: Path,
):
    cache_path = tmp_path / "crash-gap.jsonl"
    calls = 0

    def crash_after_start(_request):
        nonlocal calls
        calls += 1
        raise KeyboardInterrupt("synthetic crash before FINALIZE")

    for expected_ordinal in (1, 2):
        with pytest.raises(KeyboardInterrupt, match="synthetic crash"):
            rx.run_extraction_batch(
                (_paragraph(),), _config(max_attempts=2),
                cache_path=cache_path, transport=crash_after_start,
            )
        journal = rx.load_attempt_journal_strict(cache_path)
        assert [item.attempt_ordinal for item in journal.starts] == list(
            range(1, expected_ordinal + 1)
        )
        assert journal.records == ()

    with pytest.raises(rx.AttemptCapExhaustedError, match="unmatched START"):
        rx.run_extraction_batch(
            (_paragraph(),), _config(max_attempts=2),
            cache_path=cache_path, transport=crash_after_start,
        )
    assert calls == 2


def test_nonblocking_run_lock_prevents_concurrent_speculative_retry(
    tmp_path: Path,
):
    cache_path = tmp_path / "concurrent-run.jsonl"
    entered = threading.Event()
    release = threading.Event()
    calls = 0
    call_lock = threading.Lock()
    raw = _response('{"claims":[', finish_reason="length")
    outcome = []

    def transport(_request):
        nonlocal calls
        with call_lock:
            calls += 1
            call_number = calls
        if call_number == 1:
            entered.set()
            assert release.wait(timeout=5)
        return raw

    def first_run():
        try:
            outcome.append(rx.run_extraction_batch(
                (_paragraph(),), _config(max_attempts=2),
                cache_path=cache_path, transport=transport,
            ))
        except BaseException as exc:  # test thread must report every failure
            outcome.append(exc)

    thread = threading.Thread(target=first_run)
    thread.start()
    assert entered.wait(timeout=5)
    with pytest.raises(rx.CacheRunLockedError, match="already active"):
        rx.run_extraction_batch(
            (_paragraph(),), _config(max_attempts=2),
            cache_path=cache_path, transport=transport,
        )
    assert calls == 1
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert len(outcome) == 1 and isinstance(outcome[0], rx.ExtractionBatchV1)

    second = rx.run_extraction_batch(
        (_paragraph(),), _config(max_attempts=2),
        cache_path=cache_path, transport=transport,
    )
    third = rx.run_extraction_batch(
        (_paragraph(),), _config(max_attempts=2),
        cache_path=cache_path, transport=transport,
    )
    assert calls == 2
    assert second.records[0].status == rx.ExtractionStatus.QUARANTINED
    assert third.endpoint_calls == 0 and third.cache_hits == 1


def test_nonblocking_run_lock_is_process_wide_before_endpoint_start(
    tmp_path: Path,
):
    context = multiprocessing.get_context("fork")
    cache_path = tmp_path / "process-run.jsonl"
    entered = context.Event()
    release = context.Event()
    calls = context.Value("i", 0)
    outcomes = context.Queue()
    raw = _response('{"claims":[', finish_reason="length")

    def transport(_request):
        with calls.get_lock():
            calls.value += 1
        entered.set()
        assert release.wait(timeout=5)
        return raw

    def worker():
        try:
            rx.run_extraction_batch(
                (_paragraph(),), _config(max_attempts=2),
                cache_path=cache_path, transport=transport,
            )
            outcomes.put("completed")
        except rx.CacheRunLockedError:
            outcomes.put("locked")
        except BaseException as exc:
            outcomes.put(f"error:{type(exc).__name__}:{exc}")

    owner = context.Process(target=worker)
    owner.start()
    assert entered.wait(timeout=5)
    contender = context.Process(target=worker)
    contender.start()
    contender.join(timeout=5)
    assert not contender.is_alive() and contender.exitcode == 0
    assert outcomes.get(timeout=2) == "locked"
    with calls.get_lock():
        assert calls.value == 1

    release.set()
    owner.join(timeout=5)
    assert not owner.is_alive() and owner.exitcode == 0
    assert outcomes.get(timeout=2) == "completed"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value.__setitem__("raw_response", "{}"),
            "raw response hash mismatch",
        ),
        (
            lambda value: value.__setitem__("producer", "forged-producer"),
            "frozen producer",
        ),
        (
            lambda value: value.__setitem__("response_model", "forged-model"),
            "response model",
        ),
        (
            lambda value: value.__setitem__("usage_json", "{\"total_tokens\":999}"),
            "usage does not match",
        ),
        (
            lambda value: value["frozen_extraction"].__setitem__(
                "payload_json", '{"claims":[]}'
            ),
            "frozen extraction differs",
        ),
    ],
)
def test_cache_reader_recomputes_retained_preimages(mutate, message):
    record = rx.extract_paragraph(
        _paragraph(), _config(), lambda request: _response(),
    )
    value = json.loads(rx._record_to_json(record))
    mutate(value)

    with pytest.raises(rx.CacheCorruptionError, match=message):
        rx._record_from_dict(value)


def test_cache_reader_replays_raw_content_not_self_consistent_forged_empty_output():
    record = rx.extract_paragraph(
        _paragraph(), _config(), lambda request: _response(),
    )
    empty_payload = json.dumps({
        "schema_version": cb.EXTRACTION_SCHEMA_VERSION, "claims": [],
    }, separators=(",", ":"))
    empty_frozen = cb.freeze_extraction(
        record.source_id, empty_payload, producer=record.producer,
        model_revision=record.model_revision,
        prompt_sha256=record.prompt_sha256,
        config_sha256=record.config_sha256,
    )
    forged = replace(
        record, frozen_extraction=empty_frozen,
        output_sha256=empty_frozen.output_sha256, record_id="",
    )
    forged = replace(forged, record_id=rx._record_id(forged))

    with pytest.raises(rx.CacheCorruptionError, match="frozen extraction differs"):
        rx._record_from_dict(json.loads(rx._record_to_json(forged)))


def test_response_model_mismatch_and_non_stop_finish_reason_fail_closed():
    mismatch = rx.extract_paragraph(
        _paragraph(), _config(),
        lambda request: _response(model="different-model"),
    )
    assert mismatch.status == rx.ExtractionStatus.ERROR
    assert mismatch.frozen_extraction is None
    assert mismatch.error_type == "ModelMismatch"
    assert [item.reason for item in mismatch.quarantines] == [
        rx.QuoteRejectCode.MODEL_MISMATCH,
    ]
    # A fail-closed mismatch receipt itself remains replay-verifiable.
    assert rx._record_from_dict(json.loads(rx._record_to_json(mismatch))) == mismatch

    truncated = rx.extract_paragraph(
        _paragraph(), _config(),
        lambda request: _response(finish_reason="length"),
    )
    assert truncated.status == rx.ExtractionStatus.ERROR
    assert truncated.finish_reason == "length"
    assert truncated.frozen_extraction is None
    assert truncated.error_type == rx.QuoteRejectCode.INVALID_OPENAI_RESPONSE.value
    assert [item.reason for item in truncated.quarantines] == [
        rx.QuoteRejectCode.INVALID_OPENAI_RESPONSE,
    ]
    assert rx._record_from_dict(json.loads(rx._record_to_json(truncated))) == truncated


@pytest.mark.parametrize(
    "bad_response",
    [
        _response(finish_reason="length"),
        json.dumps({
            "model": "fixture-model", "choices": [], "usage": {},
        }, separators=(",", ":")),
    ],
    ids=["finish-length", "invalid-envelope"],
)
def test_invalid_response_receipt_is_nonterminal_and_retried(
    tmp_path: Path, bad_response: str,
):
    cache_path = tmp_path / "finish-retry.jsonl"
    calls = 0

    def transport(request):
        nonlocal calls
        calls += 1
        return bad_response if calls == 1 else _response()

    first = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )

    assert first.records[0].status == rx.ExtractionStatus.ERROR
    assert first.records[0].frozen_extraction is None
    assert second.records[0].status == rx.ExtractionStatus.SUCCESS
    assert second.endpoint_calls == 1 and second.cache_hits == 0
    assert calls == 2
    attempts = rx.JSONLExtractionCache(cache_path).records()
    assert [item.status for item in attempts] == [
        rx.ExtractionStatus.ERROR, rx.ExtractionStatus.SUCCESS,
    ]


def test_final_length_attempt_terminalizes_as_empty_typed_quarantine(tmp_path: Path):
    cache_path = tmp_path / "length-cap.jsonl"
    calls = 0
    raw = _response('{"claims":[', finish_reason="length")

    def transport(request):
        nonlocal calls
        calls += 1
        return raw

    config = _config(max_attempts=2)
    first = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )
    third = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )

    assert first.records[0].status == rx.ExtractionStatus.ERROR
    capped = second.records[0]
    assert capped.status == rx.ExtractionStatus.QUARANTINED
    assert capped.raw_response == raw and capped.finish_reason == "length"
    assert capped.error_type is None and capped.frozen_extraction is not None
    assert json.loads(capped.frozen_extraction.payload_json)["claims"] == []
    assert [item.reason for item in capped.quarantines] == [
        rx.QuoteRejectCode.TRUNCATED_RESPONSE_AT_ATTEMPT_CAP,
    ]
    assert third.endpoint_calls == 0 and third.cache_hits == 1
    assert calls == 2
    assert len(rx.JSONLExtractionCache(cache_path).records()) == 2

    bad_quarantine = replace(
        capped.quarantines[0], reason=rx.QuoteRejectCode.INVALID_JSON,
    )
    provisional = replace(
        capped, quarantines=(bad_quarantine,), record_id="",
    )
    tampered = replace(provisional, record_id=rx._record_id(provisional))
    with pytest.raises(rx.CacheCorruptionError, match="quarantines differ"):
        rx._validate_record_preimages(tampered)


def test_length_at_cap_from_wrong_model_remains_error_and_never_calls_again(
    tmp_path: Path,
):
    cache_path = tmp_path / "wrong-model-length-cap.jsonl"
    calls = 0
    raw = _response(
        '{"claims":[', finish_reason="length", model="wrong-model",
    )

    def transport(_request):
        nonlocal calls
        calls += 1
        return raw

    config = _config(max_attempts=2)
    first = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )
    third = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )

    assert first.records[0].status == rx.ExtractionStatus.ERROR
    assert second.records[0].status == rx.ExtractionStatus.ERROR
    assert second.attempt_cap_exhausted == 1
    assert second.records[0].frozen_extraction is None
    assert all(
        item.reason != rx.QuoteRejectCode.TRUNCATED_RESPONSE_AT_ATTEMPT_CAP
        for item in second.records[0].quarantines
    )
    assert third.endpoint_calls == 0
    assert third.attempt_cap_exhausted == 1
    assert calls == 2
    assert len(rx.JSONLExtractionCache(cache_path).records()) == 2


def test_batch_concurrency_is_bounded_and_return_order_is_input_order(tmp_path: Path):
    paragraphs = tuple(
        ParagraphInputV1(
            f"src:{index}", f"Node {index}",
            f"Node {index} recorded in London.",
        )
        for index in range(5)
    )
    active = 0
    observed_max = 0
    lock = threading.Lock()

    def transport(request):
        nonlocal active, observed_max
        with lock:
            active += 1
            observed_max = max(observed_max, active)
        time.sleep(0.02)
        user_text = request.body["messages"][1]["content"]
        title = json.loads(user_text.split("TITLE_JSON=", 1)[1].split("\n", 1)[0])
        content = json.dumps({
            "claims": [{
                "subject": title,
                "predicate": "recorded in",
                "arguments": [{"role": "location", "exact": "London"}],
            }],
        }, separators=(",", ":"))
        with lock:
            active -= 1
        return _response(content)

    result = rx.run_extraction_batch(
        paragraphs, _config(max_concurrency=2),
        cache_path=tmp_path / "cache.jsonl", transport=transport,
    )
    assert observed_max == 2
    assert [item.source_id for item in result.records] == [
        item.source_id for item in paragraphs
    ]
    assert all(item.status == rx.ExtractionStatus.SUCCESS for item in result.records)


def test_transport_errors_are_recorded_but_not_terminal_cache_hits(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    calls = 0

    def transport(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("secret endpoint detail")
        return _response()

    first = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    assert first.records[0].status == rx.ExtractionStatus.ERROR
    assert first.records[0].error_type == "TimeoutError"
    assert "secret endpoint detail" not in first.records[0].quarantines[0].detail
    assert second.records[0].status == rx.ExtractionStatus.SUCCESS
    assert calls == 2


def test_urllib_http_error_preserves_raw_outcome_without_salvaging_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """A valid-looking model envelope on non-2xx is evidence, never output."""

    cache_path = tmp_path / "http-error-outcome.jsonl"
    raw_body = _response()
    response_headers = {
        "Retry-After": "7",
        "X-Model-Revision": "fixture-model@server",
    }
    calls = 0

    def fail_with_http_response(request, *, timeout):
        nonlocal calls
        calls += 1
        raise rx.urllib_error.HTTPError(
            request.full_url,
            503,
            "Service Unavailable",
            response_headers,
            BytesIO(raw_body.encode("utf-8")),
        )

    monkeypatch.setattr(rx.urllib_request, "urlopen", fail_with_http_response)
    config = _config(max_attempts=2)
    transport = rx.openai_compatible_transport()

    first = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )
    third = rx.run_extraction_batch(
        (_paragraph(),), config, cache_path=cache_path, transport=transport,
    )

    assert calls == 2
    assert [first.endpoint_calls, second.endpoint_calls, third.endpoint_calls] == [
        1, 1, 0,
    ]
    assert second.attempt_cap_exhausted == third.attempt_cap_exhausted == 1
    journal = rx.load_attempt_journal_strict(cache_path)
    assert len(journal.starts) == len(journal.finalizes) == 2
    assert journal.unmatched_starts == ()
    assert [record.attempt_ordinal for record in journal.records] == [1, 2]
    for record in journal.records:
        assert record.status == rx.ExtractionStatus.ERROR
        assert record.error_type == "HTTPStatusError"
        assert record.http_status == 503
        assert record.raw_response == raw_body
        assert record.raw_response_sha256 == sha256_text(raw_body)
        assert json.loads(record.response_headers_json) == [
            ["Retry-After", "7"],
            ["X-Model-Revision", "fixture-model@server"],
        ]
        assert record.response_model == ""
        assert record.finish_reason == ""
        assert json.loads(record.usage_json) == {}
        assert record.response_content_sha256 == sha256_text("")
        assert record.frozen_extraction is None
        assert record.output_sha256 == ""
        assert [item.reason for item in record.quarantines] == [
            rx.QuoteRejectCode.TRANSPORT_ERROR,
        ]
    assert third.records[0] == journal.records[-1]


def test_two_identical_empty_transport_failures_are_two_locked_attempts(tmp_path: Path):
    cache_path = tmp_path / "identical-errors.jsonl"
    calls = 0

    def transport(request):
        nonlocal calls
        calls += 1
        raise TimeoutError("same hidden failure")

    first = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    third = rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    attempts = rx.JSONLExtractionCache(cache_path).records()

    assert calls == 2
    assert first.endpoint_calls == second.endpoint_calls == 1
    assert second.attempt_cap_exhausted == 1
    assert [item.attempt_ordinal for item in attempts] == [1, 2]
    assert len({item.attempt_id for item in attempts}) == 2
    assert len({item.record_id for item in attempts}) == 2
    assert len({item.raw_response_sha256 for item in attempts}) == 1
    assert len({item.usage_json for item in attempts}) == 1
    assert first.records[0].attempt_id == attempts[0].attempt_id
    assert second.records[0].attempt_id == attempts[1].attempt_id
    assert third.endpoint_calls == 0
    assert third.attempt_cap_exhausted == 1
    assert third.records[0].status == rx.ExtractionStatus.ERROR


def test_cache_rejects_attempt_ordinal_gap(tmp_path: Path):
    cache_path = tmp_path / "attempt-gap.jsonl"

    def transport(request):
        raise TimeoutError("same failure")

    rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    rx.run_extraction_batch(
        (_paragraph(),), _config(), cache_path=cache_path, transport=transport,
    )
    lines = cache_path.read_text(encoding="utf-8").splitlines()
    cache_path.write_text("\n".join(lines[2:]) + "\n", encoding="utf-8")

    with pytest.raises(rx.CacheCorruptionError, match="physical order"):
        rx.JSONLExtractionCache(cache_path).records()


def _record_bound_to_start(
    start: rx.AttemptStartV1,
    record: rx.RecordedExtractionV1,
) -> rx.RecordedExtractionV1:
    provisional = replace(
        record,
        attempt_id=start.attempt_id,
        attempt_ordinal=start.attempt_ordinal,
        record_id="",
    )
    return replace(provisional, record_id=rx._record_id(provisional))


def test_journal_rejects_finalize_without_start_and_duplicate_result(
    tmp_path: Path,
):
    config = _config()
    paragraph = _paragraph()
    request = rx.make_openai_request(paragraph, config)
    start = rx._make_start((paragraph,), config, request, 1)
    record = _record_bound_to_start(
        start, rx.extract_paragraph(paragraph, config, lambda _: _response()),
    )
    finalize = rx._make_finalize(start, (record,))
    path = tmp_path / "journal-order.jsonl"

    path.write_text(rx._finalize_to_json(finalize) + "\n", encoding="utf-8")
    with pytest.raises(rx.CacheCorruptionError, match="no prior START"):
        rx.load_attempt_journal_strict(path)

    path.write_text(
        "\n".join((
            rx._start_to_json(start),
            rx._finalize_to_json(finalize),
            rx._finalize_to_json(finalize),
        )) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(rx.CacheCorruptionError, match="duplicated"):
        rx.load_attempt_journal_strict(path)


def test_journal_rejects_reverse_finalize_order_and_duplicate_root_key(
    tmp_path: Path,
):
    config = _config()
    paragraph = _paragraph()
    request = rx.make_openai_request(paragraph, config)
    first = rx._make_start((paragraph,), config, request, 1)
    second = rx._make_start((paragraph,), config, request, 2)
    record = _record_bound_to_start(
        first, rx.extract_paragraph(paragraph, config, lambda _: _response()),
    )
    finalize_first = rx._make_finalize(first, (record,))
    path = tmp_path / "reverse.jsonl"
    path.write_text(
        "\n".join((
            rx._start_to_json(first),
            rx._start_to_json(second),
            rx._finalize_to_json(finalize_first),
        )) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(rx.CacheCorruptionError, match="reverse physical"):
        rx.load_attempt_journal_strict(path)

    raw_start = rx._start_to_json(first)
    duplicate_root = raw_start[:-1] + ',"event_type":"START"}'
    path.write_text(duplicate_root + "\n", encoding="utf-8")
    with pytest.raises(rx.CacheCorruptionError, match="duplicate JSON key"):
        rx.load_attempt_journal_strict(path)


def test_batch_request_and_mixed_binding_preserve_per_source_receipts():
    green = _paragraph()
    paris = ParagraphInputV1(
        "src:paris", "Paris", "Paris was compared with Paris by Alice.",
    )
    config = _config(batch_size=2)
    request = rx.make_batch_openai_request((paris, green), config)
    assert request.body["temperature"] == 0
    assert request.body["response_format"] == {"type": "json_object"}
    assert request.body["chat_template_kwargs"] == {"enable_thinking": False}
    batch_input = json.loads(
        request.body["messages"][1]["content"].split("INPUT_JSON=", 1)[1]
    )
    assert [item["source_id"] for item in batch_input] == [
        "src:green", "src:paris",
    ]
    assert request.request_id == rx.make_batch_openai_request(
        (green, paris), config
    ).request_id

    content = json.dumps({
        "results": [
            {
                "source_id": "src:paris",
                "claims": [{
                    "subject": "Alice", "predicate": "compared with",
                    "arguments": [{"role": "place", "exact": "Paris"}],
                }],
            },
            {
                "source_id": "src:green",
                "claims": json.loads(_content())["claims"],
            },
        ],
    }, separators=(",", ":"))
    raw = _response(content)
    records = rx.extract_paragraph_batch(
        (paris, green), config, lambda batch_request: raw,
    )
    by_source = {record.source_id: record for record in records}
    assert by_source["src:green"].status == rx.ExtractionStatus.SUCCESS
    assert by_source["src:paris"].status == rx.ExtractionStatus.QUARANTINED
    assert [item.reason for item in by_source["src:paris"].quarantines] == [
        rx.QuoteRejectCode.AMBIGUOUS_QUOTE,
    ]
    assert {record.batch_request_id for record in records} == {request.request_id}
    assert {record.batch_size for record in records} == {2}
    assert len({record.request_id for record in records}) == 2
    assert all(record.raw_response == raw for record in records)
    assert all(record.prompt_sha256 == rx.batch_prompt_sha256() for record in records)

    frozen = by_source["src:green"].frozen_extraction
    assert frozen is not None
    parsed = cb.parse_extraction_payload(green, frozen)
    assert len(parsed.observations) == 1 and parsed.quarantines == ()


def test_batch_unknown_or_duplicate_source_ids_fail_closed():
    green = _paragraph()
    other = ParagraphInputV1(
        "src:other", "Other", "Other was recorded in Rome.",
    )
    config = _config(batch_size=2)
    request = rx.make_batch_openai_request((green, other), config)
    unknown = json.dumps({
        "results": [{"source_id": "src:invented", "claims": []}],
    }, separators=(",", ":"))
    adapted = rx.adapt_batch_quote_payloads(
        (green, other), unknown, request=request, config=config,
    )
    assert set(adapted) == {"src:green", "src:other"}
    assert all(json.loads(payload)["claims"] == [] for payload, _ in adapted.values())
    assert all(
        quarantines[0].reason == rx.QuoteRejectCode.SOURCE_ROUTING_ERROR
        for _, quarantines in adapted.values()
    )

    duplicate = json.dumps({
        "results": [
            {"source_id": "src:green", "claims": []},
            {"source_id": "src:green", "claims": []},
            {"source_id": "src:other", "claims": []},
        ],
    }, separators=(",", ":"))
    adapted = rx.adapt_batch_quote_payloads(
        (green, other), duplicate, request=request, config=config,
    )
    assert adapted["src:green"][1][0].reason == (
        rx.QuoteRejectCode.SOURCE_ROUTING_ERROR
    )
    assert adapted["src:other"][1] == ()


def test_batch_runner_packs_calls_resumes_and_preserves_input_order(tmp_path: Path):
    paragraphs = tuple(
        ParagraphInputV1(
            f"src:batch-{index}", f"Node {index}",
            f"Node {index} recorded in London.",
        )
        for index in range(5)
    )
    config = _config(batch_size=2, max_concurrency=2, max_tokens=2048)
    active = 0
    maximum = 0
    calls = 0
    lock = threading.Lock()

    def transport(request):
        nonlocal active, maximum, calls
        with lock:
            active += 1
            calls += 1
            maximum = max(maximum, active)
        batch_input = json.loads(
            request.body["messages"][1]["content"].split("INPUT_JSON=", 1)[1]
        )
        results = []
        for item in reversed(batch_input):
            results.append({
                "source_id": item["source_id"],
                "claims": [{
                    "subject": item["title"],
                    "predicate": "recorded in",
                    "arguments": [{"role": "location", "exact": "London"}],
                }],
            })
        time.sleep(0.02)
        with lock:
            active -= 1
        return _response(json.dumps({"results": results}, separators=(",", ":")))

    cache_path = tmp_path / "batch-cache.jsonl"
    first = rx.run_extraction_batch(
        tuple(reversed(paragraphs)), config,
        cache_path=cache_path, transport=transport,
    )
    second = rx.run_extraction_batch(
        tuple(reversed(paragraphs)), config,
        cache_path=cache_path, transport=transport,
    )
    assert first.endpoint_calls == 3
    assert second.endpoint_calls == 0 and second.cache_hits == 5
    assert calls == 3 and maximum == 2
    assert [record.source_id for record in first.records] == [
        item.source_id for item in reversed(paragraphs)
    ]
    assert all(record.status == rx.ExtractionStatus.SUCCESS for record in first.records)
    attempt_sizes = sorted(
        sum(item.attempt_id == attempt_id for item in first.records)
        for attempt_id in {item.attempt_id for item in first.records}
    )
    assert attempt_sizes == [1, 2, 2]
    assert all(item.attempt_ordinal == 1 for item in first.records)
    assert [record.record_id for record in first.records] == [
        record.record_id for record in second.records
    ]
