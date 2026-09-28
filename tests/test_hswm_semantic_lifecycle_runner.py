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


def test_selection_adapter_accepts_actual_reopened_development_reports(completed) -> None:
    """The adapter consumes the actual report schema, not a hand-shaped substitute."""
    out, report = completed
    module_url = (ROOT / "src/hswm/effect-runtime/dist/semantic-lifecycle-selection.js").as_uri()
    code = f"""
import {{ readFileSync }} from 'node:fs';
import {{ selectLifecycleCandidate }} from {json.dumps(module_url)};
const report = JSON.parse(readFileSync(process.argv[1], 'utf8'));
const development = Object.fromEntries(report.evaluations
  .filter((row) => row.stage === 'development')
  .map((row) => [row.arm, row]));
const revisions = Object.fromEntries(report.revisions.map((row) => [row.arm, row]));
console.log(JSON.stringify(selectLifecycleCandidate(
  development.evidence_only, development.learned,
  revisions.evidence_only, revisions.learned,
  {{ allowance: '0', debit: '0' }}
)));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", code, str(out / "summary.json")],
                            cwd=ROOT, text=True, capture_output=True, check=True, timeout=30)
    selected = json.loads(result.stdout)
    assert selected["_tag"] == "Right"
    value = selected["right"]
    assert value["applicability"] == "APPLICABLE"
    assert value["selectedArm"] == "learned"
    assert value["guard"] == {"allowance": "0", "debit": "0", "totalMass": "4",
                               "currentObservedScore": "3", "candidateObservedScore": "4",
                               "requiredCandidateObservedScore": "3", "observedGuardPasses": True}


@pytest.fixture(scope="module")
def selected_completed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:
    out = tmp_path_factory.mktemp("semantic-lifecycle-selected") / "attempt"
    result = invoke("--output", str(out), "--transport", "scripted", "--allowance", "0", "--debit", "0",
                    cwd=out.parent)
    assert result.returncode == 0, result.stderr
    return out, json.loads((out / "summary.json").read_text())


def test_selected_mode_commits_development_choice_before_one_fresh_heldout_read(selected_completed) -> None:
    out, report = selected_completed
    selection = json.loads((out / "selection.json").read_text())
    assert report["selection"] == selection
    assert selection["selectedArm"] == "learned"
    assert selection["selectionSplit"] == "development"
    assert selection["heldoutUsed"] is False
    assert (selection["denominator"], selection["baselineCorrect"], selection["candidateCorrect"]) == (4, 3, 4)
    assert (selection["allowance"], selection["debit"]) == ("0", "0")
    # Four development child workers plus train/revise children; heldout is the
    # separately reopened selected runtime in the parent, not another arm sweep.
    assert len(report["launches"]) == 8
    heldout = [row for row in report["evaluations"] if row["stage"] == "heldout"]
    assert len(heldout) == 1
    row = heldout[0]
    assert row["arm"] == "learned"
    assert row["selectedBeforeHeldout"] is True
    assert row["executionBoundary"] == "FRESH_DURABLE_RUNTIME_IN_PARENT_AFTER_DEVELOPMENT_CHILDREN_EXIT"
    assert row["before"]["relationKey"]["revisionId"] == 1
    assert row["trace"]["relationKey"]["revisionId"] == 1
    assert row["trace"]["frameSha256"] == row["calls"][0]["frameSha256"]
    assert row["assessment"] == {"split": "heldout", "denominator": 4, "correct": 4,
                                 "incorrect": 0, "parseFailures": 0, "missingPredictions": 0,
                                 "unknownCaseIds": [], "observations": row["assessment"]["observations"]}
    # The final transport cannot precede selection: selected mode has exactly
    # one post-decision request directory.
    request = next((out / "http" / "heldout-selected").glob("*.request.json"))
    assert (out / "selection.json").stat().st_mtime_ns <= request.stat().st_mtime_ns
    wire = json.loads(request.read_text())
    frame = json.loads(wire["messages"][1]["content"])["frame"]
    assert frame["relation"]["key"]["revisionId"] == 1
    revisions = {row["arm"]: row for row in report["revisions"]}
    assert frame["relation"]["semantic"]["semanticText"] == revisions["learned"]["after"]["semantic"]["semanticText"]
    assert frame["relation"]["semantic"]["semanticText"] != report["training"]["state"]["semantic"]["semanticText"]


def test_selected_mode_strict_debit_tie_falls_back_to_frozen_without_heldout_reselection(tmp_path) -> None:
    out = tmp_path / "strict-tie"
    result = invoke("--output", str(out), "--transport", "scripted", "--allowance", "0", "--debit", "1")
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "summary.json").read_text())
    selection = json.loads((out / "selection.json").read_text())
    assert selection["selectedArm"] == "frozen"
    assert selection["baselineCorrect"] == 3 and selection["candidateCorrect"] == 4
    heldout = [row for row in report["evaluations"] if row["stage"] == "heldout"]
    assert len(heldout) == 1 and heldout[0]["arm"] == "frozen"
    assert heldout[0]["before"]["relationKey"]["revisionId"] == 0
    assert report["heldoutUsedForRevision"] is False
    assert all(row["stage"] == "development" or row["arm"] == "frozen" for row in report["evaluations"])


def test_selection_preparation_refuses_a_development_trace_with_a_forged_frame_binding(completed) -> None:
    """Selection re-reads the durable trace/frame; it does not trust a score row."""
    out, report = completed
    module_url = (ROOT / "src/hswm/effect-runtime/dist/semantic-lifecycle-selected-execution.js").as_uri()
    code = f"""
import {{ readFileSync }} from 'node:fs';
import {{ Effect }} from 'effect';
import {{ prepareLifecycleSelection }} from {json.dumps(module_url)};
import {{ NodePosixFileSystemLive }} from './dist/effect-posix-filesystem.js';
const out = process.argv[1];
const config = JSON.parse(readFileSync(out + '/config.json', 'utf8'));
const report = JSON.parse(readFileSync(out + '/summary.json', 'utf8'));
const development = Object.fromEntries(report.evaluations.filter(row => row.stage === 'development').map(row => [row.arm, row]));
const revisions = Object.fromEntries(report.revisions.map(row => [row.arm, row]));
const selection = candidateDevelopment => prepareLifecycleSelection(config, {{
  training: report.training, baselineDevelopment: development.frozen, candidateDevelopment,
  candidateRevision: revisions.learned, allowance: '0', debit: '0'
}}).pipe(Effect.either, Effect.provide(NodePosixFileSystemLive));
const forged = structuredClone(development.learned);
forged.trace.frameSha256 = '0'.repeat(64);
const forgedScore = structuredClone(development.learned);
forgedScore.assessment.correct = 0;
const clean = await Effect.runPromise(selection(development.learned));
const frame = await Effect.runPromise(selection(forged));
const score = await Effect.runPromise(selection(forgedScore));
console.log(JSON.stringify({{ clean: clean._tag, frame: frame._tag === 'Left' ? frame.left.code : null,
  score: score._tag === 'Left' ? score.left.code : null }}));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", code, str(out)],
                            cwd=ROOT / "src/hswm/effect-runtime", text=True,
                            capture_output=True, check=True, timeout=30)
    assert json.loads(result.stdout) == {"clean": "Right", "frame": "SELECTION_BINDING_FAILED",
                                         "score": "SELECTION_BINDING_FAILED"}


def test_bad_batch_and_refusal_stay_in_declared_denominator() -> None:
    module_url = (ROOT / "src/hswm/effect-runtime/dist/semantic-lifecycle-worker.js").as_uri()
    code = f"import {{assessBatch}} from {json.dumps(module_url)}; console.log(JSON.stringify([assessBatch('heldout',null).right,assessBatch('heldout','010').right,assessBatch('heldout','0101extra').right]))"
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


def test_selected_mode_refuses_failed_candidate_and_writes_decision_before_its_only_heldout_call(tmp_path) -> None:
    """A bad learned proposal cannot turn incomplete rows into a learned choice."""
    requests: list[tuple[str, bool]] = []
    out = tmp_path / "selected-http-fault"

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.loads(body["messages"][1]["content"])
            requests.append((payload["contract"], (out / "selection.json").exists()))
            if payload["contract"] == "hswm-llm-semantic-learn/v1":
                content = {"semanticText": "unadmitted", "disposition": "invalid",
                           "uncertainty": "unknown", "exceptionRefs": []}
            else:
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
    try:
        result = invoke("--output", str(out), "--transport", "http", "--cell", str(cell),
                        "--allowance", "0", "--debit", "0")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "summary.json").read_text())
    decision = json.loads((out / "selection.json").read_text())
    assert decision["selectedArm"] == "frozen"
    assert decision["reason"] == "CANDIDATE_NOT_COMMITTED"
    assert decision["denominator"] == 4
    assert (decision["baselineCorrect"], decision["candidateCorrect"]) == (0, 0)
    heldout = [row for row in report["evaluations"] if row["stage"] == "heldout"]
    assert len(heldout) == 1
    assert heldout[0]["arm"] == "frozen"
    assert heldout[0]["assessment"]["denominator"] == heldout[0]["assessment"]["parseFailures"] == 4
    # Seven actual HTTP requests: train, learned revise, four development rows,
    # and exactly one selected heldout row.  The latter observes the durable
    # decision; development cannot observe it.
    assert len(requests) == 7
    assert [present for _, present in requests[:-1]] == [False] * 6
    assert requests[-1][1] is True


def test_selected_mode_falls_back_when_a_committed_revision_has_no_semantic_change(tmp_path) -> None:
    """A new revision number alone is not evidence of a learned semantic update."""
    out = tmp_path / "selected-noop"

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            payload = json.loads(body["messages"][1]["content"])
            if payload["contract"] == "hswm-llm-semantic-learn/v1":
                # This is structurally valid and commits, but exactly repeats
                # the seeded semantic fields and declared exception reference.
                content = {"semanticText": "The door opens exactly when pressed is true.",
                           "disposition": "predict declared door state", "uncertainty": "fixture hypothesis",
                           "exceptionRefs": ["exception:door"]}
            else:
                content = {"prediction": "not-a-bit-batch", "uncertainty": "unknown"}
            raw = json.dumps({"model": "http-noop-stub-not-an-llm", "choices": [
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
                                "model": "http-noop-stub-not-an-llm", "max_tokens": 128}))
    try:
        result = invoke("--output", str(out), "--transport", "http", "--cell", str(cell),
                        "--allowance", "0", "--debit", "0")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "summary.json").read_text())
    decision = json.loads((out / "selection.json").read_text())
    revisions = {row["arm"]: row for row in report["revisions"]}
    assert revisions["learned"]["committed"] is True
    assert decision["reason"] == "UNCHANGED_SEMANTIC_FIELDS"
    heldout = [row for row in report["evaluations"] if row["stage"] == "heldout"]
    assert len(heldout) == 1 and heldout[0]["arm"] == "frozen"
