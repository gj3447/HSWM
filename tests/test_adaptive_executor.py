from __future__ import annotations

import sys
from pathlib import Path

from hswm.cells.adaptive_executor import execute
from hswm.cells.openai import UnknownModelOutcome
from hswm.cells.runtime import InvokeCellEffect, make_packet


def command(argv, *, outcome=None):
    value = {"kind": "command", "cell_id": "command-cell", "input_type": "token/v1",
             "output_type": "text/v1", "argv": argv}
    if outcome is not None:
        value["outcome"] = outcome
    return value


def test_command_passes_json_on_stdin_and_marks_success(tmp_path: Path):
    result = execute(command([sys.executable, "-c", "import sys; print(sys.stdin.read())"]),
                     {"hello": "world"}, workspace=tmp_path, timeout=2, output_limit=200)
    assert result["status"] == "SUCCEEDED" and result["success"] is None
    assert result["output"] == '{"hello":"world"}\n'
    assert result["metadata"]["kind"] == "command"


def test_command_failure_timeout_and_output_cap_are_bounded(tmp_path: Path):
    failed = execute(command([sys.executable, "-c", "import sys; sys.exit(7)"], outcome="exit_code"), {},
                     workspace=tmp_path, timeout=2, output_limit=20)
    assert failed["status"] == "FAILED" and failed["success"] is False
    noisy = execute(command([sys.executable, "-c", "print('x' * 1000)"]), {},
                    workspace=tmp_path, timeout=2, output_limit=10)
    assert len(noisy["output"].encode()) == 10 and noisy["metadata"]["output_truncated"]
    timed_out = execute(command([sys.executable, "-c", "import time; time.sleep(2)"]), {},
                        workspace=tmp_path, timeout=0.05, output_limit=20)
    assert timed_out["status"] == "UNKNOWN" and timed_out["success"] is None


def test_exit_code_outcome_requires_explicit_declaration(tmp_path: Path):
    scored = execute(command([sys.executable, "-c", "pass"], outcome="exit_code"), {},
                     workspace=tmp_path, timeout=2, output_limit=20)
    assert scored["status"] == "SUCCEEDED" and scored["success"] is True
    try:
        execute(command([sys.executable, "-c", "pass"], outcome="anything"), {},
                workspace=tmp_path, timeout=2, output_limit=20)
    except ValueError as error:
        assert "outcome" in str(error)
    else:
        raise AssertionError("invalid outcome was accepted")


def test_timeout_kills_descendant_that_keeps_the_stdout_pipe_open(tmp_path: Path):
    script = ("import subprocess, sys; "
              "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)']); "
              "print('leader-exited')")
    result = execute(command([sys.executable, "-c", script]), {}, workspace=tmp_path,
                     timeout=0.05, output_limit=100)
    assert result["status"] == "UNKNOWN" and result["duration_seconds"] < 1


class FakePort:
    def __init__(self, mode="success"):
        self.mode = mode
        self.effect: InvokeCellEffect | None = None

    def invoke(self, effect: InvokeCellEffect):
        self.effect = effect
        if self.mode == "unknown":
            raise UnknownModelOutcome("after send")
        return make_packet(packet_id="packet", packet_type=effect.expected_output_type,
                           payload={"text": "model answer"}, provenance={"fake": True})


def test_llm_uses_typed_effect_and_never_awards_success(tmp_path: Path):
    port = FakePort()
    cell = {"kind": "llm", "cell_id": "llm-cell", "input_type": "token/v1",
            "output_type": "text/v1", "base_url": "https://unused.invalid", "model": "fake"}
    result = execute(cell, {"prompt": "hello"}, workspace=tmp_path, timeout=2,
                     output_limit=200, port=port)
    assert result["status"] == "SUCCEEDED" and result["success"] is None
    assert port.effect is not None and port.effect.input.packet_type == "token/v1"
    unknown = execute(cell, {"prompt": "hello"}, workspace=tmp_path, timeout=2,
                      output_limit=200, port=FakePort("unknown"))
    assert unknown["status"] == "UNKNOWN" and unknown["success"] is None
