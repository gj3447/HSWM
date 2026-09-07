from __future__ import annotations

import json

from hswm.infrastructure import adaptive_cli


def program(argv: list[str] | None = None, outcome: str | None = None) -> dict:
    return {
        "schema_version": "hswm-adaptive-program/v1", "graph_id": "cli-test", "root": "router",
        "context_domain": {"mode": ["safe", "fast"]},
        "cells": [
            {"cell_id": "router", "kind": "router", "owner": "route-owner", "input_type": "task", "output_type": "result"},
            {"cell_id": "worker", "kind": "command", "owner": "worker-owner", "input_type": "task", "output_type": "result", "argv": argv or ["/bin/true"], **({"outcome": outcome} if outcome else {})},
        ],
        "relations": [{"uid": "main", "source": "router", "members": ["worker"], "reads": ["mode"], "cost_hint": 1}],
    }


def test_parser_exposes_required_local_commands() -> None:
    parsed = adaptive_cli.parser().parse_args(["--program", "program.json", "graph"])
    assert parsed.command == "graph"
    assert parsed.state.name == "runtime.sqlite3"


def test_plan_and_graph_emit_machine_json(tmp_path, capsys) -> None:
    program_path = tmp_path / "program.json"
    program_path.write_text(json.dumps(program()))
    state = tmp_path / "state.sqlite3"
    args = ["--program", str(program_path), "--state", str(state), "--workspace", str(tmp_path)]
    assert adaptive_cli.main(args + ["plan", "--context", '{"mode":"safe"}', "--budget", "5"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["status"] == "PLANNED"
    assert plan["selected"]["uid"] == "relation:main"
    assert adaptive_cli.main(args + ["run", "--context", '{"mode":"safe"}', "--task", "small local command", "--episode", "episode-1", "--frozen"]) == 0
    episode = json.loads(capsys.readouterr().out)
    assert episode["status"] == "SUCCEEDED"
    assert episode["learning"] == "FROZEN"
    assert adaptive_cli.main(args + ["graph"]) == 0
    graph = json.loads(capsys.readouterr().out)
    assert graph["graph_id"] == "cli-test"
    assert adaptive_cli.main(args + ["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["atom_kinds"]["relation"] == 1
    assert status["relations"][0]["reads"] == ["mode"]


def test_strict_context_failure_is_code_two(tmp_path, capsys) -> None:
    program_path = tmp_path / "program.json"
    program_path.write_text(json.dumps(program()))
    assert adaptive_cli.main(["--program", str(program_path), "--workspace", str(tmp_path), "plan", "--context", '{"mode":"safe","mode":"fast"}']) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["code"] == 2


def test_failed_checked_command_has_exit_code_one(tmp_path, capsys) -> None:
    program_path = tmp_path / "program.json"
    program_path.write_text(json.dumps(program(["/bin/false"], "exit_code")))
    result = adaptive_cli.main(["--program", str(program_path), "--workspace", str(tmp_path), "run",
                                "--context", '{"mode":"safe"}', "--task", "failure", "--episode", "failed", "--frozen"])
    assert result == 1
    assert json.loads(capsys.readouterr().out)["status"] == "FAILED"
