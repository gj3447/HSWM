"""Real-loopback transport tests for the DNRD-5 byte-observing gateway."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any, Iterator

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dnrd5.provider_gateway import (
    BOUNDARY_STATUS,
    Dnrd5ProviderCall,
    Dnrd5ProviderConfig,
    Dnrd5ProviderGateway,
    ProviderGatewayExecutionError,
    ProviderGatewayRefusal,
    read_provider_attempt_ledger,
    validate_completed_block_gateway_evidence,
    validate_provider_attempt_ledger_closed,
    validate_provider_receipt,
)


MODEL = "test-model-v1"
API_KEY = "private-test-key-must-never-persist"


class _RecordingServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, response_status: int, response_body: bytes) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.response_status = response_status
        self.response_body = response_body
        self.observations: list[dict[str, Any]] = []


class _Handler(BaseHTTPRequestHandler):
    server: _RecordingServer

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        self.server.observations.append(
            {
                "path": self.path,
                "headers": {key.casefold(): value for key, value in self.headers.items()},
                "body": body,
            }
        )
        self.send_response(self.server.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Request-Id", "provider-request-fixture")
        self.send_header("Content-Length", str(len(self.server.response_body)))
        self.end_headers()
        self.wfile.write(self.server.response_body)

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def _server(
    *, status: int = 200, body: bytes | None = None
) -> Iterator[_RecordingServer]:
    response = body or canonical_bytes(
        {
            "id": "completion-fixture",
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": '{"answer":"nonce-0123456789abcdef"}',
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 5,
                "total_tokens": 16,
            },
        }
    )
    active = _RecordingServer(status, response)
    thread = threading.Thread(target=active.serve_forever, daemon=True)
    thread.start()
    try:
        yield active
    finally:
        active.shutdown()
        active.server_close()
        thread.join(timeout=5)


def _config(server: _RecordingServer) -> Dnrd5ProviderConfig:
    host, port = server.server_address
    return Dnrd5ProviderConfig(
        endpoint=f"http://{host}:{port}/v1/chat/completions",
        expected_model=MODEL,
        api_key=API_KEY,
        timeout_milliseconds=5_000,
    )


def _call(call_id: str = "opaque-call-001") -> Dnrd5ProviderCall:
    return Dnrd5ProviderCall(
        block_id="DNRD5-BLOCK-0001",
        call_id=call_id,
        call_class="PRE_OUTCOME_TRAJECTORY",
        session_id="opaque-session-001",
        worker_id="opaque-worker-001",
        private_binding_sha256="a" * 64,
        request_nonce="b" * 64,
        rng_bytes=b"rng-fixture-001",
        model_identity_bytes=canonical_bytes(
            {"model": MODEL, "weights": "fixture-not-attested"}
        ),
        runtime_identity_bytes=canonical_bytes(
            {"runtime": "loopback-fixture", "version": "1"}
        ),
        isolation_bytes=canonical_bytes(
            {
                "network": "PROVIDER_ENDPOINT_ONLY_DECLARATION",
                "osProcessIsolation": "NOT_PROVEN_BY_THIS_FIXTURE",
            }
        ),
        instruction_bytes=b"Choose one hypothesis and return its training token.",
        model_input_bytes=canonical_bytes(
            {
                "publicTask": {
                    "hypotheses": ["H0", "H1"],
                    "trainingInput": "nonce-1111111111111111",
                },
                "behaviorProjection": {"status": "W0"},
            }
        ),
        response_schema_bytes=canonical_bytes(
            {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "pattern": "^nonce-[0-9a-f]{16}$",
                    }
                },
                "required": ["answer"],
                "additionalProperties": False,
            }
        ),
        max_output_tokens=64,
    )


def _content(call: Dnrd5ProviderCall, result: Any) -> dict[str, bytes]:
    return {
        "requestProjection": result.request_projection_bytes,
        "request": result.request_bytes,
        "response": result.response_bytes,
        "rng": call.rng_bytes,
        "modelIdentity": call.model_identity_bytes,
        "runtimeIdentity": call.runtime_identity_bytes,
        "isolation": call.isolation_bytes,
        "instruction": call.instruction_bytes,
        "modelInput": call.model_input_bytes,
        "responseSchema": call.response_schema_bytes,
    }


def _block_call(ordinal: int, call_class: str) -> Dnrd5ProviderCall:
    base = _call(f"opaque-call-{ordinal:03d}")
    model_input_by_class = {
        "PRE_OUTCOME_TRAJECTORY": {
            "publicTask": {"task": "fixture"},
            "behaviorProjection": {"state": "fixture"},
        },
        "REVISION_PROPOSAL": {
            "sealedTrajectory": {"trajectory": "fixture"},
            "assignedFeedback": {"feedbackBit": ordinal & 1},
            "revisionRequest": {"target": "fixture"},
        },
        "FRESH_PROBE": {
            "behaviorProjection": {"state": "fixture"},
            "freshProbe": {"input": "nonce-1111111111111111"},
        },
    }
    return replace(
        base,
        call_class=call_class,
        session_id=f"opaque-session-{ordinal:03d}",
        worker_id=f"opaque-worker-{ordinal:03d}",
        private_binding_sha256=sha256(
            f"private-binding-{ordinal}".encode()
        ).hexdigest(),
        request_nonce=sha256(f"request-nonce-{ordinal}".encode()).hexdigest(),
        rng_bytes=f"rng-fixture-{ordinal:03d}".encode(),
        model_input_bytes=canonical_bytes(model_input_by_class[call_class]),
    )


def test_real_loopback_gateway_sends_and_seals_the_exact_constructed_bytes(
    tmp_path: Path,
) -> None:
    with _server() as server:
        root = tmp_path / "evidence"
        gateway = Dnrd5ProviderGateway.create(root, _config(server))
        call = _call()
        result = gateway.execute(call)

        assert len(server.observations) == 1
        observed = server.observations[0]
        assert observed["path"] == "/v1/chat/completions"
        assert observed["body"] == result.request_bytes
        assert observed["headers"]["authorization"] == f"Bearer {API_KEY}"
        assert observed["headers"]["cache-control"] == "no-store"
        assert observed["headers"]["x-hswm-dnrd5-request-nonce"] == "b" * 64

        request = parse_canonical(result.request_bytes)
        assert request["seed"] == int.from_bytes(
            sha256(call.rng_bytes).digest()[:6], "big"
        )
        assert request["messages"][1]["content"] == canonical_bytes(
            {
                "contractVersion": "hswm-dnrd5-model-input-envelope/v1",
                "callClass": call.call_class,
                "instruction": call.instruction_bytes.decode(),
                "input": parse_canonical(call.model_input_bytes),
            }
        ).decode()
        model_visible = result.request_bytes.decode()
        for hidden in (
            call.block_id,
            call.call_id,
            call.session_id,
            call.worker_id,
            call.private_binding_sha256,
            call.request_nonce,
        ):
            assert hidden not in model_visible

        checked = validate_provider_receipt(
            result.receipt_bytes, _content(call, result)
        )
        assert checked["boundaryStatus"] == BOUNDARY_STATUS
        assert checked["providerRequestId"] == "provider-request-fixture"
        assert checked["requestHeaders"]["authorization"] == "PRESENT_REDACTED"

        ledger = read_provider_attempt_ledger(root)
        assert [record["recordType"] for record in ledger] == ["START", "TERMINAL"]
        assert ledger[0]["terminal"] == "DURABLY_VISIBLE_BEFORE_SINGLE_DISPATCH"
        assert ledger[1]["outcome"] == "SUCCEEDED"
        assert ledger[1]["startRecordSha256"] == ledger[0]["recordSha256"]

        for path in (root / "content").iterdir():
            assert path.name == sha256(path.read_bytes()).hexdigest()
        all_durable_bytes = (root / "attempts.jsonl").read_bytes() + b"".join(
            path.read_bytes() for path in (root / "content").iterdir()
        )
        assert API_KEY.encode() not in all_durable_bytes


def test_consumed_call_id_cannot_retry_after_success(tmp_path: Path) -> None:
    with _server() as server:
        root = tmp_path / "evidence"
        gateway = Dnrd5ProviderGateway.create(root, _config(server))
        call = _call()
        gateway.execute(call)
        recovered = Dnrd5ProviderGateway(root, _config(server))
        with pytest.raises(ProviderGatewayRefusal, match="already consumed"):
            recovered.execute(call)
        assert len(server.observations) == 1
        assert len(read_provider_attempt_ledger(root)) == 2


def test_unterminated_start_irrecoverably_closes_root_to_later_dispatch(
    tmp_path: Path,
) -> None:
    with _server() as server:
        root = tmp_path / "evidence"
        gateway = Dnrd5ProviderGateway.create(root, _config(server))
        gateway.execute(_call())
        first_line = (root / "attempts.jsonl").read_bytes().splitlines(keepends=True)[0]
        (root / "attempts.jsonl").write_bytes(first_line)

        with pytest.raises(ProviderGatewayRefusal, match="irrecoverably incomplete"):
            validate_provider_attempt_ledger_closed(root)
        with pytest.raises(ProviderGatewayRefusal, match="irrecoverably incomplete"):
            Dnrd5ProviderGateway(root, _config(server))
        with pytest.raises(ProviderGatewayRefusal, match="no later call"):
            gateway.execute(_block_call(2, "REVISION_PROPOSAL"))
        assert len(server.observations) == 1
        assert [record["recordType"] for record in read_provider_attempt_ledger(root)] == [
            "START"
        ]


def test_receipt_rejects_response_descriptor_content_and_keyset_mutation(
    tmp_path: Path,
) -> None:
    with _server() as server:
        gateway = Dnrd5ProviderGateway.create(
            tmp_path / "evidence", _config(server)
        )
        call = _call()
        result = gateway.execute(call)
        content = _content(call, result)
        forged = dict(content)
        forged["response"] = content["response"] + b" "
        with pytest.raises(ProviderGatewayRefusal, match="response descriptor"):
            validate_provider_receipt(result.receipt_bytes, forged)
        extra = dict(content)
        extra["undeclared"] = b"hidden"
        with pytest.raises(ProviderGatewayRefusal, match="key set"):
            validate_provider_receipt(result.receipt_bytes, extra)


def test_observed_http_failure_is_terminal_and_nonretryable(tmp_path: Path) -> None:
    with _server(status=503, body=b'{"error":"unavailable"}') as server:
        root = tmp_path / "evidence"
        gateway = Dnrd5ProviderGateway.create(root, _config(server))
        call = _call()
        with pytest.raises(
            ProviderGatewayExecutionError, match="status is not exactly 200"
        ) as caught:
            gateway.execute(call)
        assert caught.value.failure_code == "HTTP_STATUS_NOT_200"
        ledger = read_provider_attempt_ledger(root)
        assert [record["recordType"] for record in ledger] == ["START", "TERMINAL"]
        assert ledger[1]["outcome"] == "FAILED"
        assert ledger[1]["failureCode"] == "HTTP_STATUS_NOT_200"
        assert ledger[1]["observedResponse"] is not None
        with pytest.raises(ProviderGatewayRefusal, match="already consumed"):
            gateway.execute(call)
        assert len(server.observations) == 1


def test_concurrent_same_call_has_one_durable_start_and_one_http_dispatch(
    tmp_path: Path,
) -> None:
    with _server() as server:
        gateway = Dnrd5ProviderGateway.create(
            tmp_path / "evidence", _config(server)
        )
        call = _call()
        outcomes: list[str] = []

        def invoke() -> None:
            try:
                gateway.execute(call)
                outcomes.append("SUCCEEDED")
            except ProviderGatewayRefusal:
                outcomes.append("REFUSED")

        threads = [threading.Thread(target=invoke) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert sorted(outcomes) == ["REFUSED", "SUCCEEDED"]
        assert len(server.observations) == 1
        ledger = read_provider_attempt_ledger(tmp_path / "evidence")
        assert [record["recordType"] for record in ledger] == ["START", "TERMINAL"]


def test_call_inputs_are_exact_and_response_schema_is_closed(tmp_path: Path) -> None:
    with _server() as server:
        gateway = Dnrd5ProviderGateway.create(
            tmp_path / "evidence", _config(server)
        )
        bad_schema = deepcopy(parse_canonical(_call().response_schema_bytes))
        bad_schema["additionalProperties"] = True
        bad = replace(
            _call("opaque-call-bad-schema"),
            response_schema_bytes=canonical_bytes(bad_schema),
        )
        with pytest.raises(ProviderGatewayRefusal, match="closed required"):
            gateway.execute(bad)
        assert server.observations == []
        assert read_provider_attempt_ledger(tmp_path / "evidence") == ()


def test_hidden_identity_and_answer_material_are_refused_before_dispatch(
    tmp_path: Path,
) -> None:
    with _server() as server:
        gateway = Dnrd5ProviderGateway.create(
            tmp_path / "evidence", _config(server)
        )
        base = _call("opaque-call-hidden-input")
        leaked = replace(
            base,
            model_input_bytes=canonical_bytes(
                {
                    "publicTask": {"theta": 1},
                    "behaviorProjection": {"status": "W0"},
                }
            ),
        )
        with pytest.raises(ProviderGatewayRefusal, match="forbidden hidden key"):
            gateway.execute(leaked)
        identity_leak = replace(
            base,
            instruction_bytes=(
                "Do the task for " + base.call_id
            ).encode(),
        )
        with pytest.raises(ProviderGatewayRefusal, match="call identity"):
            gateway.execute(identity_leak)
        assert server.observations == []
        assert read_provider_attempt_ledger(tmp_path / "evidence") == ()


def test_schema_invalid_model_content_consumes_call_and_fails_terminally(
    tmp_path: Path,
) -> None:
    invalid_response = canonical_bytes(
        {
            "id": "completion-invalid-schema",
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": '{"answer":"wrong","extra":true}',
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 4,
                "completion_tokens": 2,
                "total_tokens": 6,
            },
        }
    )
    with _server(body=invalid_response) as server:
        root = tmp_path / "evidence"
        gateway = Dnrd5ProviderGateway.create(root, _config(server))
        with pytest.raises(ProviderGatewayExecutionError) as caught:
            gateway.execute(_call())
        assert caught.value.failure_code == "MODEL_CONTENT_SCHEMA_INVALID"
        ledger = read_provider_attempt_ledger(root)
        assert ledger[1]["outcome"] == "FAILED"
        assert ledger[1]["failureCode"] == "MODEL_CONTENT_SCHEMA_INVALID"
        assert ledger[1]["observedResponse"] is not None


def test_completed_block_validator_closes_exact_one_four_four_gateway_calls(
    tmp_path: Path,
) -> None:
    classes = [
        "PRE_OUTCOME_TRAJECTORY",
        *(["REVISION_PROPOSAL"] * 4),
        *(["FRESH_PROBE"] * 4),
    ]
    with _server() as server:
        root = tmp_path / "evidence"
        gateway = Dnrd5ProviderGateway.create(root, _config(server))
        for ordinal, call_class in enumerate(classes, start=1):
            gateway.execute(_block_call(ordinal, call_class))
        summary = validate_completed_block_gateway_evidence(
            root, "DNRD5-BLOCK-0001"
        )
        assert summary.generation_call_count == 9
        assert summary.trajectory_call_count == 1
        assert summary.revision_call_count == 4
        assert summary.probe_call_count == 4
        assert len(set(summary.receipt_sha256s)) == 9
        assert summary.first_start_ordinal == 1
        assert summary.last_terminal_ordinal == 18
        assert summary.terminal.startswith("NINE_CLIENT_OBSERVED_CALLS_CLOSED")
        assert len(server.observations) == 9


def test_incomplete_block_cannot_be_promoted_to_completed_gateway_evidence(
    tmp_path: Path,
) -> None:
    with _server() as server:
        root = tmp_path / "evidence"
        gateway = Dnrd5ProviderGateway.create(root, _config(server))
        gateway.execute(_block_call(1, "PRE_OUTCOME_TRAJECTORY"))
        with pytest.raises(ProviderGatewayRefusal, match="exactly nine"):
            validate_completed_block_gateway_evidence(
                root, "DNRD5-BLOCK-0001"
            )
