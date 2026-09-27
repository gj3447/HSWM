"""Focused coverage for the isolated Inspect saved-output adapter."""

from __future__ import annotations

import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

pytest.importorskip("inspect_ai", reason="Inspect comparison runs in its isolated uv environment")
from inspect_ai.log import read_eval_log


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = ROOT / "_research" / "inspect_comparison_v1"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, RESEARCH_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


paired_eval = load_module("paired_eval")
semantic_locality_adapter = load_module("semantic_locality_adapter")
live_eval = load_module("live_eval")


def write_jsonl(path: Path, records: list[dict[str, str]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def test_load_rejects_duplicate_and_incomplete_pairs(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.jsonl"
    record = {"id": "one", "input": "p", "target": "yes", "baseline": "no", "candidate": "yes"}
    write_jsonl(path, [record, record])
    with pytest.raises(ValueError, match="duplicate id"):
        paired_eval.load_paired_jsonl(path)

    path.write_text('{"id":"two","input":"p","target":"yes","baseline":"no"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="missing=.*candidate"):
        paired_eval.load_paired_jsonl(path)

    path.write_text(
        '{"id":"two","id":"two-again","input":"p","target":"yes","baseline":"no","candidate":"yes"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        paired_eval.load_paired_jsonl(path)

    write_jsonl(path, [{**record, "id": "   "}])
    with pytest.raises(ValueError, match="id.*non-whitespace"):
        paired_eval.load_paired_jsonl(path)

    write_jsonl(path, [{**record, "candidate": "\t"}])
    with pytest.raises(ValueError, match="candidate.*non-whitespace"):
        paired_eval.load_paired_jsonl(path)


def test_inspect_writes_logs_and_scores_both_arms(tmp_path: Path) -> None:
    path = tmp_path / "paired.jsonl"
    write_jsonl(
        path,
        [
            {"id": "one", "input": "p1", "target": "yes", "baseline": "no", "candidate": "yes"},
            {"id": "two", "input": "p2", "target": "no", "baseline": "no", "candidate": "no"},
        ],
    )
    baseline, candidate = paired_eval.run(path, tmp_path / "logs")
    baseline_log, candidate_log = read_eval_log(baseline.location), read_eval_log(candidate.location)
    assert baseline_log.results.scores[0].metrics["accuracy"].value == 0.5
    assert candidate_log.results.scores[0].metrics["accuracy"].value == 1.0


def test_inspect_error_status_fails_the_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "paired.jsonl"
    write_jsonl(path, [{"id": "one", "input": "p", "target": "yes", "baseline": "yes", "candidate": "yes"}])
    monkeypatch.setattr(
        paired_eval,
        "eval",
        lambda *args, **kwargs: [SimpleNamespace(status="success"), SimpleNamespace(status="error")],
    )
    with pytest.raises(RuntimeError, match="error"):
        paired_eval.run(path, tmp_path / "logs")


def test_source_adapter_rejects_target_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "observations.jsonl"
    write_jsonl(
        source,
        [
            {"id": "1", "arm": "full", "expected": "yes", "decision": "yes"},
            {"id": "1", "arm": "role_swap", "expected": "no", "decision": "no"},
        ],
    )
    with pytest.raises(ValueError, match="target mismatch"):
        semantic_locality_adapter.convert(source, tmp_path / "paired.jsonl", "full", "role_swap")


def test_source_adapter_retains_invalid_decision_as_a_failure(tmp_path: Path) -> None:
    source = tmp_path / "observations.jsonl"
    output = tmp_path / "paired.jsonl"
    write_jsonl(
        source,
        [
            {"id": "1", "arm": "full", "expected": "yes", "decision": "yes", "valid": False},
            {"id": "1", "arm": "role_swap", "expected": "yes", "decision": "yes", "valid": True},
        ],
    )
    assert semantic_locality_adapter.convert(source, output, "full", "role_swap") == 1
    pair = paired_eval.load_paired_jsonl(output)[0]
    assert pair.baseline == semantic_locality_adapter.INVALID_SAVED_OUTPUT
    baseline, candidate = paired_eval.run(output, tmp_path / "logs")
    assert read_eval_log(baseline.location).results.scores[0].metrics["accuracy"].value == 0.0
    assert read_eval_log(candidate.location).results.scores[0].metrics["accuracy"].value == 1.0


def live_input() -> dict[str, object]:
    return {
        "relation": {"semanticText": "original", "disposition": "binary", "uncertainty": "fixture", "exceptionRefs": []},
        "roles": [
            {"role": "subject", "ordinal": 0, "referenceType": "LOCAL_SEMANTIC_INPUT"},
            {"role": "context", "ordinal": 1, "referenceType": "LOCAL_SEMANTIC_INPUT"},
            {"role": "exception", "ordinal": 2, "referenceType": "LOCAL_SEMANTIC_INPUT"},
        ],
        "priorEvidence": [],
        "fields": {"subject": {"dax": 0, "wug": 1, "zif": 0}, "context": {"pel": 0}, "exception": {"nub": 0}},
    }


def test_live_bridge_callable_hides_evaluator_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    example = live_eval.LiveExample("heldout-1", "heldout", live_input(), "1")
    execution = live_eval.Execution("http://127.0.0.1:8001", "qwen3-4b-real", 32, 3, 0)
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured.update(json.loads(kwargs["input"]))
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps({
                "valid": True, "answer": "1", "error_kind": None, "request_sha256": "a" * 64,
                "response_sha256": "b" * 64, "model": "qwen3-4b-real", "usage": None,
                "latency_ms": 1.0, "model_calls": 1,
            }),
        )

    monkeypatch.setattr(live_eval.subprocess, "run", fake_run)
    assert live_eval.evaluate_relation("candidate relation", example, execution, ("fake-bridge",))["answer"] == "1"
    assert set(captured) == {"input", "relation_text", "execution"}
    assert captured["relation_text"] == "candidate relation"
    assert "target" not in json.dumps(captured)
    assert "heldout-1" not in json.dumps(captured)


def test_live_preflight_rejects_noninteger_bits_roles_and_execution() -> None:
    float_bit = live_input()
    float_bit["fields"]["subject"]["dax"] = 0.0
    with pytest.raises(ValueError, match="must be 0 or 1"):
        live_eval.validate_local_semantic_input(float_bit)

    boolean_ordinal = live_input()
    boolean_ordinal["roles"][0]["ordinal"] = False
    with pytest.raises(ValueError, match="ordered roles"):
        live_eval.validate_local_semantic_input(boolean_ordinal)

    with pytest.raises(ValueError, match="bridge range"):
        live_eval._validate_execution(live_eval.Execution("http://127.0.0.1:8001", "model", 1.0, 3, 0))


def test_live_task_scores_invalid_bridge_output_as_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    examples = [
        live_eval.LiveExample("one", "heldout", live_input(), "1"),
        live_eval.LiveExample("two", "heldout", live_input(), "0"),
    ]
    execution = live_eval.Execution("http://127.0.0.1:8001", "qwen3-4b-real", 32, 3, 0)

    def fake_evaluate(relation, example, execution, bridge_command):
        if relation == "baseline":
            return {"valid": False, "answer": None, "error_kind": "HTTP_503", "request_sha256": None, "response_sha256": None, "model": execution.model, "usage": None, "latency_ms": 1.0, "model_calls": 1}
        return {"valid": True, "answer": example.target, "error_kind": None, "request_sha256": "a" * 64, "response_sha256": "b" * 64, "model": execution.model, "usage": None, "latency_ms": 1.0, "model_calls": 1}

    monkeypatch.setattr(live_eval, "evaluate_relation", fake_evaluate)
    baseline, candidate = live_eval.run_live(examples, "baseline", "candidate", execution, tmp_path / "logs", ("fake",))
    assert read_eval_log(baseline.location).results.scores[0].metrics["accuracy"].value == 0.0
    assert read_eval_log(candidate.location).results.scores[0].metrics["accuracy"].value == 1.0


def test_live_inspect_uses_the_actual_typescript_bridge_and_http_fixture(tmp_path: Path) -> None:
    received: list[dict[str, object]] = []

    class FixtureHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/v1/chat/completions"
            body = self.rfile.read(int(self.headers["content-length"]))
            request = json.loads(body)
            received.append(request)
            response = {
                "model": "fixture-model",
                "choices": [{"finish_reason": "stop", "message": {"content": '{"answer":1}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            }
            encoded = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        example = live_eval.LiveExample("heldout-1", "heldout", live_input(), "1")
        execution = live_eval.Execution(f"http://127.0.0.1:{server.server_port}", "fixture-model", 32, 3, 0)
        baseline, candidate = live_eval.run_live([example], "baseline relation", "candidate relation", execution, tmp_path / "logs")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert len(received) == 2
    assert all("target" not in json.dumps(request) and "heldout-1" not in json.dumps(request) for request in received)
    assert read_eval_log(baseline.location).results.scores[0].metrics["accuracy"].value == 1.0
    assert read_eval_log(candidate.location).results.scores[0].metrics["accuracy"].value == 1.0
