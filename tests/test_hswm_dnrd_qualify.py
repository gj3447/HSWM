from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from _research.dnrd import execute as dnrd_execute
from _research.dnrd import qualify as dnrd_qualify
from _research.dnrd.live import HttpResponse, MODEL_ID
from _research.dnrd.qualify import QualificationError, run_qualification
from _research.dnrd.task_family import canonical_json


class RecordingTransport:
    def __init__(self, *, pretty_ordinals: set[int] | None = None, fail_on: int | None = None) -> None:
        self.pretty_ordinals = pretty_ordinals or set()
        self.fail_on = fail_on
        self.calls: list[dict[str, Any]] = []

    def request(self, **kwargs: Any) -> HttpResponse:
        self.calls.append(dict(kwargs))
        ordinal = len(self.calls)
        if ordinal == self.fail_on:
            return HttpResponse(500, b'{"error":"forced"}')
        body = json.loads(kwargs["body"])
        candidates = body["response_format"]["json_schema"]["schema"]["properties"]["response_token"]["enum"]
        requested = candidates[(ordinal + 1) % 2]
        content = json.dumps({"response_token": requested}, indent=2 if ordinal in self.pretty_ordinals else None)
        response = {
            "model": MODEL_ID,
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": ordinal, "completion_tokens": 1, "total_tokens": ordinal + 1},
        }
        raw = json.dumps(response, indent=2 if ordinal in self.pretty_ordinals else None).encode("utf-8")
        return HttpResponse(200, raw)


def test_three_disjoint_pretty_and_compact_calls_emit_exact_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "qualification.json"
    transport = RecordingTransport(pretty_ordinals={1, 3})

    result = run_qualification(
        endpoint="http://127.0.0.1:18000",
        api_key="private-test-key-must-never-persist",
        output_path=output,
        timeout_seconds=5,
        transport=transport,
    )

    raw = output.read_bytes()
    assert raw == canonical_json(result) + b"\n"
    assert json.loads(raw) == result
    assert b"private-test-key-must-never-persist" not in raw
    assert len(transport.calls) == 3
    assert all(call["url"] == "http://127.0.0.1:18000/v1/chat/completions" for call in transport.calls)
    assert all(call["headers"]["Authorization"] == "Bearer private-test-key-must-never-persist" for call in transport.calls)
    assert result["retry_count"] == 0
    assert result["future_seed_material_used"] is False
    assert result["experiment_occurrence"] is False
    assert result["raw_full_stdout_record_persisted"] is False
    calls = result["calls"]
    assert [call["ordinal"] for call in calls] == [1, 2, 3]
    assert [call["returned_token"] == call["requested_token"] for call in calls] == [True, True, True]
    assert {call["candidate_response_tokens"].index(call["requested_token"]) for call in calls} == {0, 1}
    tokens = {token for call in calls for token in call["candidate_response_tokens"]}
    assert len(tokens) == 6
    assert [source_file["path"] for source_file in result["source_files"]] == list(
        dnrd_execute.QUALIFICATION_SOURCE_PATHS
    )
    # This is a hermetic receipt round-trip test, not a production-runtime
    # preflight.  Bind its synthetic "official" identity to the interpreter
    # that produced the fixture so the test remains valid on CI's CPython 3.11;
    # production constants remain the fixed 3.12.13 / Unicode 15.0.0 pins.
    monkeypatch.setattr(
        dnrd_execute,
        "OFFICIAL_PYTHON_EXECUTABLE_SHA256",
        result["python_executable_sha256"],
    )
    monkeypatch.setattr(dnrd_execute, "OFFICIAL_PYTHON_VERSION", result["python_version"])
    monkeypatch.setattr(
        dnrd_execute, "OFFICIAL_UNICODE_DATA_VERSION", result["unicode_data_version"]
    )
    # The executor accepts the same exact canonical receipt that was written.
    loaded, loaded_raw, loaded_tokens = dnrd_execute._load_structured_output_qualification(
        SimpleNamespace(
            structured_output_qualification_path=output,
            structured_output_qualification_sha256=hashlib.sha256(raw).hexdigest(),
            model_endpoint="http://127.0.0.1:18000",
            python_executable_sha256=result["python_executable_sha256"],
            python_version=result["python_version"],
            unicode_data_version=result["unicode_data_version"],
        ),
        source_manifest={"files": result["source_files"]},
    )
    assert loaded == result
    assert loaded_raw == raw
    assert loaded_tokens == tokens


def test_failure_never_writes_success_artifact_and_never_retries(tmp_path: Path) -> None:
    output = tmp_path / "qualification.json"
    transport = RecordingTransport(fail_on=2)

    with pytest.raises(Exception):
        run_qualification(
            endpoint="http://127.0.0.1:18000",
            api_key="key",
            output_path=output,
            timeout_seconds=5,
            transport=transport,
        )

    assert not output.exists()
    assert len(transport.calls) == 2


def test_source_identity_drift_during_calls_refuses_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "qualification.json"
    transport = RecordingTransport()
    source_files = [
        {"path": path, "sha256": "a" * 64}
        for path in dnrd_execute.QUALIFICATION_SOURCE_PATHS
    ]
    drifted_source_files = [dict(item) for item in source_files]
    drifted_source_files[2]["sha256"] = "b" * 64
    snapshots = iter((source_files, drifted_source_files))
    monkeypatch.setattr(
        dnrd_qualify, "_qualification_source_files", lambda: next(snapshots)
    )

    with pytest.raises(QualificationError, match="source identities drifted"):
        run_qualification(
            endpoint="http://127.0.0.1:18000",
            api_key="key",
            output_path=output,
            timeout_seconds=5,
            transport=transport,
        )

    assert len(transport.calls) == 3
    assert not output.exists()


def test_python_runtime_identity_drift_during_calls_refuses_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "qualification.json"
    transport = RecordingTransport()
    identity = {
        "python_executable_sha256": "a" * 64,
        "python_version": "3.12.13",
        "unicode_data_version": "15.0.0",
    }
    drifted_identity = {**identity, "unicode_data_version": "15.0.1"}
    snapshots = iter((identity, drifted_identity))
    monkeypatch.setattr(
        dnrd_qualify,
        "_qualification_runtime_identity",
        lambda: next(snapshots),
    )

    with pytest.raises(QualificationError, match="Python/Unicode runtime identity drifted"):
        run_qualification(
            endpoint="http://127.0.0.1:18000",
            api_key="key",
            output_path=output,
            timeout_seconds=5,
            transport=transport,
        )

    assert len(transport.calls) == 3
    assert not output.exists()


def test_existing_output_is_not_overwritten_or_called(tmp_path: Path) -> None:
    output = tmp_path / "qualification.json"
    output.write_bytes(b"earlier immutable receipt\n")
    transport = RecordingTransport()

    with pytest.raises(QualificationError, match="refusing to overwrite"):
        run_qualification(
            endpoint="http://127.0.0.1:18000",
            api_key="key",
            output_path=output,
            timeout_seconds=5,
            transport=transport,
        )

    assert output.read_bytes() == b"earlier immutable receipt\n"
    assert transport.calls == []
