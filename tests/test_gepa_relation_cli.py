"""End-to-end, test-only loopback regression for the GEPA-to-Inspect CLI."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import sys
import threading

import pytest

pytest.importorskip("gepa", reason="GEPA CLI runs in its isolated uv environment")
pytest.importorskip("inspect_ai", reason="Inspect CLI runs in its isolated uv environment")

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "_research" / "gepa_relation_comparison_v1"


@pytest.mark.skipif(shutil.which("node") is None, reason="fixture and bridge require Node")
def test_cli_uses_one_bounded_gepa_then_two_inspect_heldout_arms(tmp_path: Path) -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def do_POST(self) -> None:  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            reflection = "revised relation text" in body["messages"][0]["content"]
            if reflection:
                content = (
                    "The initial bit is 1 exactly when subject fields dax and wug differ. "
                    "Context flag pel equal to 1 flips that bit, while pel equal to 0 leaves it unchanged. "
                    "Finally, exception flag nub equal to 1 flips the bit; nub equal to 0 leaves it unchanged."
                )
            else:
                input_value = json.loads(body["messages"][1]["content"].split("\n")[0])
                fields = input_value["fields"]
                answer = fields["subject"]["dax"] ^ fields["subject"]["wug"] ^ fields["exception"]["nub"]
                if "pel never" not in input_value["relation"]["semanticText"]:
                    answer ^= fields["context"]["pel"]
                content = json.dumps({"answer": answer})
            response = json.dumps({
                "model": body["model"],
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 8, "total_tokens": 38},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        fixture, output = tmp_path / "fixture", tmp_path / "output"
        subprocess.run(
            ["node", str(ROOT / "_research/inspect_comparison_v1/prepare_fixture.mts"), str(fixture)],
            check=True, capture_output=True, text=True,
        )
        execution_path = fixture / "execution.json"
        execution = json.loads(execution_path.read_text())
        execution.update({"base_url": f"http://127.0.0.1:{server.server_port}", "model": "fixture-qwen"})
        execution_path.write_text(json.dumps(execution))
        completed = subprocess.run(
            [sys.executable, "runner.py", str(fixture), "--output-dir", str(output)],
            cwd=STUDY, capture_output=True, text=True, timeout=90,
        )
        assert completed.returncode == 0, completed.stderr[-4000:]
        report = json.loads((output / "comparison.json").read_text())
        assert len(requests) == 74
        assert sum("revised relation text" in item["messages"][0]["content"] for item in requests) == 2
        assert report["training_request_attempts"] == 32
        assert report["heldout_resource_counts"]["physical_model_calls"] == 40
        assert report["training_resource_counts"]["input_tokens"] > 0
        assert report["heldout_resource_counts"]["input_tokens"] > 0
        assert len(list((output / "inspect-logs").glob("*.eval"))) == 2
        heldout_ids = {json.loads(line)["id"] for line in (fixture / "heldout.jsonl").read_text().splitlines()}
        model_visible = "\n".join(json.dumps(item) for item in requests)
        assert not any(identifier in model_visible for identifier in heldout_ids)
        train = {row["id"]: row for line in (fixture / "train.jsonl").read_text().splitlines() if (row := json.loads(line))}
        for item in requests:
            if "revised relation text" in item["messages"][0]["content"]:
                feedback = json.loads(item["messages"][1]["content"])["training_feedback"]["current_candidate"]
                assert feedback
                for observed in feedback:
                    example = train[observed["case_id"]]
                    assert observed["training_input"]["fields"] == example["input"]["fields"]
                    assert observed["expected_answer"] == example["target"]
                    assert observed["observed_answer"] in ("0", "1", None)
            else:
                assert "target" not in item["messages"][1]["content"]
                assert "split" not in item["messages"][1]["content"]
    finally:
        server.shutdown()
        server.server_close()
