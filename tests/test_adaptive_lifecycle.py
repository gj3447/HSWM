from __future__ import annotations

import sys
import threading

import pytest

from hswm.cells.adaptive_runtime import AdaptiveRuntime
from hswm.cells.conditional import Reject
from hswm.cells.runtime import make_packet


def program(leaf: dict) -> dict:
    return {
        "schema_version": "hswm-adaptive-program/v1", "graph_id": "lifecycle-test",
        "root": "root", "context_domain": {"kind": ["x"]},
        "cells": [
            {"cell_id": "root", "kind": "router", "owner": "router-owner",
             "input_type": "token/v1", "output_type": "text/v1"},
            leaf,
        ],
        "relations": [{"uid": "route", "source": "root", "members": [leaf["cell_id"]],
                       "reads": ["kind"], "cost_hint": 0}],
    }


def test_timeout_unknown_holds_lease_and_same_episode_never_reexecutes(tmp_path):
    leaf = {"cell_id": "slow", "kind": "command", "owner": "command-owner",
            "input_type": "token/v1", "output_type": "text/v1",
            "argv": [sys.executable, "-c", "import time; time.sleep(2)"]}
    runtime = AdaptiveRuntime(program(leaf), tmp_path / "state.sqlite", tmp_path)
    first = runtime.run("task", {"kind": "x"}, episode_id="timeout-1", budget=0.05)
    assert first["status"] == "UNKNOWN" and first["result"]["success"] is None
    replay = runtime.run("task", {"kind": "x"}, episode_id="timeout-1", budget=0.05)
    assert replay["replayed"] is True and replay["status"] == "UNKNOWN"
    with pytest.raises(Reject, match="another episode"):
        runtime.run("task", {"kind": "x"}, episode_id="timeout-2", budget=0.05)
    runtime.feedback("timeout-1", success=False, source="test:explicit")
    assert runtime._get("runtime:lease")["payload"]["episode"] is None


class BlockingPort:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def invoke(self, effect):
        self.calls += 1
        self.started.set()
        assert self.release.wait(2)
        return make_packet(packet_id="fake-output", packet_type=effect.expected_output_type,
                           payload={"text": "done"}, provenance={"test": "blocking-port"})


def test_flock_blocks_feedback_restore_then_feedback_learns_exactly_once(tmp_path):
    leaf = {"cell_id": "model", "kind": "llm", "owner": "model-owner",
            "input_type": "token/v1", "output_type": "text/v1",
            "base_url": "https://unused.invalid", "model": "fake"}
    port = BlockingPort()
    runtime = AdaptiveRuntime(program(leaf), tmp_path / "state.sqlite", tmp_path, port=port)
    result: dict = {}

    def run():
        result.update(runtime.run("task", {"kind": "x"}, episode_id="live-1", budget=2))

    worker = threading.Thread(target=run)
    worker.start()
    assert port.started.wait(1)
    with pytest.raises(Reject, match="runtime is executing"):
        runtime.feedback("live-1", success=True, source="test:feedback")
    with pytest.raises(Reject, match="runtime is executing"):
        runtime.restore("relation:route", 1, event_id="restore-during-run")
    port.release.set()
    worker.join(2)
    assert not worker.is_alive() and result["status"] == "SUCCEEDED"
    assert result["result"]["success"] is None
    recorded = runtime.feedback("live-1", success=True, source="test:feedback")
    route = runtime._get("relation:route")
    assert recorded["status"] == "FEEDBACK_RECORDED" and route["payload"]["model"]["n"] == 1
    event_count = len(runtime.store.events(runtime.graph_id))
    assert runtime.feedback("live-1", success=True, source="test:feedback") == recorded
    assert len(runtime.store.events(runtime.graph_id)) == event_count and port.calls == 1
