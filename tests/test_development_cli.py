from __future__ import annotations

import json
from pathlib import Path

from hswm.infrastructure import development_cli


def profile() -> dict:
    return {
        "schema_version": "hswm-adaptive-program/v1", "graph_id": "development-test", "root": "router",
        "context_domain": {"focus": ["session", "bridge"], "stage": ["development", "regression"]},
        "cells": [
            {"cell_id": "router", "kind": "router", "owner": "route-owner", "input_type": "task", "output_type": "result"},
            {"cell_id": "worker", "kind": "command", "owner": "worker-owner", "input_type": "task", "output_type": "result", "argv": ["/bin/true"]},
        ],
        "relations": [{"uid": "main", "source": "router", "members": ["worker"], "reads": ["focus", "stage"], "cost_hint": 1}],
    }


def test_workspace_derived_state_is_stable_and_isolated(tmp_path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir(); second.mkdir()
    assert development_cli.state_path("game", first, None) == development_cli.state_path("game", first, None)
    assert development_cli.state_path("game", first, None) != development_cli.state_path("game", second, None)
    assert development_cli.state_path("game", first, Path("relative.sqlite3")) == first / "relative.sqlite3"


def test_game_profile_run_feedback_and_status(tmp_path, monkeypatch, capsys) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile()))
    monkeypatch.setattr(development_cli, "ROOT", tmp_path)
    monkeypatch.setitem(development_cli.PROFILES, "game", profile_path)
    common = ["game", "run", "--workspace", str(tmp_path), "--task", "quick command", "--episode", "e1"]
    assert development_cli.main(common) == 0
    episode = json.loads(capsys.readouterr().out)
    assert episode["status"] == "SUCCEEDED"
    assert development_cli.main(["game", "status", "--workspace", str(tmp_path)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["pending_feedback"][0]["episode"] == "e1"
    assert development_cli.main(["game", "feedback", "--workspace", str(tmp_path), "--episode", "e1", "--success", "true", "--source", "local-review"]) == 0
    assert json.loads(capsys.readouterr().out)["feedback"] == {"success": True, "source": "local-review"}
    assert development_cli.main(["game", "status", "--workspace", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["pending_feedback"] == []
    assert development_cli.main(["game", "status", "--workspace", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["relations"][0]["observations"] == 1


def test_plan_accepts_common_options_after_action(tmp_path, monkeypatch, capsys) -> None:
    profile_path = tmp_path / "profile.json"
    value = profile()
    value["context_domain"]["focus"] = ["soop", "creator"]
    profile_path.write_text(json.dumps(value))
    monkeypatch.setattr(development_cli, "ROOT", tmp_path)
    monkeypatch.setitem(development_cli.PROFILES, "supullim", profile_path)
    assert development_cli.main(["supullim", "plan", "--workspace", str(tmp_path), "--focus", "soop", "--budget", "5"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PLANNED"


def test_game_alias_reuses_existing_state_while_maplelineage_is_separate(tmp_path, monkeypatch, capsys) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile()))
    monkeypatch.setattr(development_cli, "ROOT", tmp_path)
    monkeypatch.setitem(development_cli.PROFILES, "game", profile_path)
    assert development_cli.main(["game", "run", "--workspace", str(tmp_path), "--task", "retain pending", "--episode", "existing", "--frozen"]) == 0
    capsys.readouterr()
    assert development_cli.main(["the-excel-tycoon", "status", "--workspace", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["pending_feedback"][0]["episode"] == "existing"
    assert development_cli.state_path("game", tmp_path, None) == development_cli.state_path("버엑시", tmp_path, None)
    assert development_cli.state_path("game", tmp_path, None) != development_cli.state_path("maplelineage", tmp_path, None)


def test_checked_in_profiles_declare_exactly_the_cli_foci() -> None:
    for project, path in development_cli.PROFILES.items():
        program = json.loads(path.read_text(encoding="utf-8"))
        assert program["context_domain"]["focus"] == development_cli.FOCI[project], project
        guarded = {route["guard"]["right"] for route in program["relations"] if route.get("guard")}
        assert guarded == set(development_cli.FOCI[project]), project


def test_game_profile_v2_keeps_v1_routes_and_adds_bounded_repository_checks() -> None:
    v1 = json.loads((development_cli.ROOT / "_research/causal_composition/examples/adaptive_game_development.v1.json").read_text())
    v2 = json.loads(development_cli.PROFILES["game"].read_text())
    assert v2["graph_id"] == "hswm-game-development-feedback-v2" != v1["graph_id"]
    assert v1["relations"] == v2["relations"][:len(v1["relations"])]
    assert {cell["cell_id"] for cell in v2["cells"]} == {"developer", "session", "bridge", "career", "graph", "check"}
    assert all(route["cost_hint"] <= 60 for route in v2["relations"] if route["guard"]["right"] != "check")
