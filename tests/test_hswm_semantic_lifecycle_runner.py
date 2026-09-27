"""End-to-end wiring checks; scripted predictions are not model performance."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
from threading import Thread

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "_research/hswm_semantic_lifecycle_v1/run.mjs"


def invoke(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["node", str(RUNNER), *args], cwd=cwd, text=True,
                          capture_output=True, check=False, timeout=120)


@pytest.fixture(scope="module")
def completed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    out = tmp_path_factory.mktemp("semantic-lifecycle") / "attempt"
    # Invocation outside the checkout also exercises source closure resolution.
    result = invoke("--output", str(out), "--transport", "scripted", cwd=out.parent)
    assert result.returncode == 0, result.stderr
    return out, json.loads((out / "summary.json").read_text())


def test_reopened_processes_consume_accepted_revision_with_matched_controls(completed) -> None:
    out, report = completed
    assert report["reopened"] and report["sharedEvidence"]
    assert report["httpModelRequests"] == 0
    assert report["claimCeiling"] == "SCRIPTED_WIRING_ONLY_NOT_MODEL_EFFICACY"
    assert report["outcomeAuthority"] == "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED"
    assert len(report["launches"]) == 12
    assert all(p["exitedBeforeNextStage"] for p in report["launches"])
    revisions = {r["arm"]: r for r in report["revisions"]}
    assert all(r["committed"] for r in revisions.values())
    assert revisions["evidence_only"]["semanticFieldsChanged"] == []
    assert revisions["sham"]["semanticFieldsChanged"] == ["semanticText"]
    assert "semanticText" in revisions["learned"]["semanticFieldsChanged"]
    heldout = {r["arm"]: r for r in report["evaluations"] if r["stage"] == "heldout"}
    assert {a: r["assessment"]["denominator"] for a, r in heldout.items()} == dict.fromkeys(heldout, 4)
    assert heldout["learned"]["assessment"]["correct"] == 4  # authored scripted oracle only
    assert heldout["frozen"]["assessment"]["correct"] < 4
    assert heldout["frozen"]["assessment"] == heldout["evidence_only"]["assessment"] == heldout["sham"]["assessment"]
    for arm, row in heldout.items():
        assert row["canonicalUnchanged"]
        assert row["processId"] != report["training"]["processId"]
        assert row["trace"]["relationKey"]["revisionId"] == (0 if arm == "frozen" else 1)
        assert row["trace"]["frameSha256"] == row["calls"][0]["frameSha256"]
    # All exported snapshots can reopen only if internal journal hard links survived.
    assert all((out / "states" / arm / "journal-slots").is_dir() for arm in heldout)


def test_wire_inputs_keep_evaluation_labels_and_split_identity_out(completed) -> None:
    out, report = completed
    for path in (out / "http").glob("*/*.request.json"):
        wire = json.loads(path.read_text())
        payload = json.loads(wire["messages"][1]["content"])
        event = json.loads(payload["frame"]["event"])
        assert set(event) == {"instruction", "cases"}
        for case in event["cases"]:
            assert set(case) == {"input", "context"}
            assert set(case["input"]) == {"power", "locked", "pressed", "manualRelease"}
        prior = payload["frame"]["priorEvidence"]
        if prior:
            assert len(json.loads(prior["observed"])["cases"]) == 8  # training only
        assert "headers" not in wire
    assert report["developmentUsedForSelection"] is False
    assert report["heldoutUsedForRevision"] is False


def test_bad_batch_and_refusal_stay_in_declared_denominator() -> None:
    module_url = (ROOT / "_research/hswm_semantic_lifecycle_v1/worker.mjs").as_uri()
    code = f"import {{assessBatch}} from {json.dumps(module_url)}; console.log(JSON.stringify([assessBatch('heldout',null),assessBatch('heldout','010'),assessBatch('heldout','0101extra')]))"
    result = subprocess.run(["node", "--input-type=module", "-e", code], cwd=ROOT,
                            text=True, capture_output=True, check=True, timeout=30)
    for score in json.loads(result.stdout):
        assert score["denominator"] == 4 and score["correct"] == 0 and score["parseFailures"] == 4


def test_invalid_cli_and_existing_output_are_not_silently_reused(completed, tmp_path) -> None:
    out, _ = completed
    summary = (out / "summary.json").read_bytes()
    duplicate = invoke("--output", str(out), "--transport", "scripted")
    assert duplicate.returncode != 0
    assert (out / "summary.json").read_bytes() == summary
    forbidden = tmp_path / "must-not-exist"
    invalid = invoke("--output", str(forbidden), "--transport", "http")
    assert invalid.returncode != 0 and not forbidden.exists()
    assert invoke("--help").returncode == 0


def test_http_faults_keep_failed_revision_and_invalid_predictions_in_report(tmp_path) -> None:
    """The local HTTP stub is a fault injector, not an LLM."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.loads(body["messages"][1]["content"])
            requests.append(payload["contract"])
            if payload["contract"] == "hswm-llm-semantic-learn/v1":
                # Exact exception preservation must refuse this revision.
                content = {"semanticText": "unadmitted", "disposition": "invalid",
                           "uncertainty": "unknown", "exceptionRefs": []}
            else:
                # Valid outer semantic shape, invalid task prediction: score every row.
                content = {"prediction": "not-a-bit-batch", "uncertainty": "unknown"}
            raw = json.dumps({"model": "http-fault-stub-not-an-llm", "choices": [
                {"message": {"content": json.dumps(content)}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cell = tmp_path / "cell.json"
    cell.write_text(json.dumps({"base_url": f"http://127.0.0.1:{server.server_port}/v1",
                                "model": "http-fault-stub-not-an-llm", "max_tokens": 128}))
    out = tmp_path / "http-fault-attempt"
    try:
        result = invoke("--output", str(out), "--transport", "http", "--cell", str(cell))
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert result.returncode == 0, result.stderr  # a completed diagnostic can contain failures
    report = json.loads((out / "summary.json").read_text())
    assert report["status"] == "COMPLETED_WITH_REVISION_FAILURES"
    assert report["sharedEvidence"] is False
    assert report["committedEvidenceBindingsValid"] and report["reopened"]
    assert report["httpModelRequests"] == len(requests) == 10
    assert report["revisionFailures"] == [{"arm": "learned", "disposition": "PROPOSAL_FAILED",
                                           "errorCode": "LLM_OUTPUT_INVALID"}]
    for row in report["evaluations"]:
        assert row["assessment"]["denominator"] == row["assessment"]["parseFailures"] == 4
        assert row["assessment"]["correct"] == 0
        assert row["before"]["relationKey"]["revisionId"] == (0 if row["arm"] in ("frozen", "learned") else 1)
