import sys

from hswm.cells.adaptive_runtime import AdaptiveRuntime


SUCCESS = "import sys; sys.exit(0)"
FAILURE = "import sys; sys.exit(1)"
TASK_DEPENDENT = (
    "import json,sys; payload=json.load(sys.stdin); "
    "print(json.dumps(payload['context'],sort_keys=True)); "
    "sys.exit(0 if payload['task'] == 'ok' else 1)"
)


def command(cell_id, code, *, outcome="exit_code", input_type="task", output_type="result"):
    cell = {"cell_id": cell_id, "kind": "command", "owner": "test-owner",
            "input_type": input_type, "output_type": output_type,
            "argv": [sys.executable, "-c", code]}
    if outcome is not None:
        cell["outcome"] = outcome
    return cell


def router(cell_id):
    return {"cell_id": cell_id, "kind": "router", "owner": "test-owner",
            "input_type": "task", "output_type": "result"}


def relation(uid, source, members, reads, cost=1):
    return {"uid": uid, "source": source, "members": members,
            "reads": reads, "cost_hint": cost}


def program(*, cells, relations, domain=None, graph_id="test-adaptive"):
    return {"schema_version": "hswm-adaptive-program/v1", "graph_id": graph_id,
            "root": "root", "context_domain": domain or {"mode": ["a", "b"]},
            "cells": cells, "relations": relations}


def runtime(tmp_path, spec):
    return AdaptiveRuntime(spec, tmp_path / "adaptive.sqlite", tmp_path)


def route_atom(active, uid):
    return next(atom for atom in active.graph()["atoms"] if atom["uid"] == "relation:" + uid)


def test_observed_subprocess_results_change_selection_and_replay_does_not_rerun(tmp_path):
    spec = program(cells=[router("root"), command("ok", SUCCESS), command("bad", FAILURE)],
                   relations=[relation("ok", "root", ["ok"], ["mode"]),
                              relation("bad", "root", ["bad"], ["mode"])])
    active = runtime(tmp_path, spec)
    for index in range(4):
        assert active.run("task", {"mode": "a"}, episode_id=f"ok-{index}", force_route="ok")["result"]["success"]
        assert not active.run("task", {"mode": "a"}, episode_id=f"bad-{index}", force_route="bad")["result"]["success"]
    planned = active.plan({"mode": "a"}, exploration=0)
    assert planned["selected"]["uid"] == "relation:ok"
    before = route_atom(active, "ok")["payload"]["model"]["n"]
    replay = active.run("task", {"mode": "a"}, episode_id="ok-0", force_route="ok")
    assert replay["replayed"] is True
    assert route_atom(active, "ok")["payload"]["model"]["n"] == before
    restarted = runtime(tmp_path, spec)
    assert restarted.plan({"mode": "a"}, exploration=0)["selected"]["uid"] == "relation:ok"


def test_nested_router_updates_its_own_and_parent_relation_from_one_result(tmp_path):
    spec = program(cells=[router("root"), router("inner"),
                          command("producer", SUCCESS, output_type="work"),
                          command("leaf", SUCCESS, input_type="work")],
                   relations=[relation("outer", "root", ["inner"], ["mode"]),
                              relation("inner", "inner", ["producer", "leaf"], ["mode"])], graph_id="nested")
    active = runtime(tmp_path, spec)
    report = active.run("task", {"mode": "a"}, episode_id="nested-1", exploration=0)
    assert report["result"]["success"] is True
    assert route_atom(active, "outer")["payload"]["model"]["n"] == 1
    assert route_atom(active, "inner")["payload"]["model"]["n"] == 1
    assert {visit["relation"] for visit in report["visits"]} >= {"relation:outer", "relation:inner"}
    assert [visit["cell"] for visit in report["visits"]] == ["producer", "leaf", "inner", "root"]


def test_four_distinct_observed_contexts_create_specialized_relation_with_new_read(tmp_path):
    spec = program(cells=[router("root"), command("leaf", TASK_DEPENDENT)],
                   relations=[relation("base", "root", ["leaf"], ["ready"])],
                   domain={"ready": [False, True], "clean": [False, True]}, graph_id="specialize")
    active = runtime(tmp_path, spec)
    episodes = [
        ({"ready": False, "clean": False}, "fail"),
        ({"ready": False, "clean": True}, "fail"),
        ({"ready": True, "clean": False}, "fail"),
        ({"ready": True, "clean": True}, "ok"),
    ]
    for index, (context, task) in enumerate(episodes):
        active.run(task, context, episode_id=f"specialize-{index}", force_route="base", exploration=0)
    base = route_atom(active, "base")
    specialized = [atom for atom in active.graph()["atoms"]
                   if atom["kind"] == "relation" and atom["payload"].get("parent_relation") == base["uid"]]
    assert len(specialized) == 1
    assert base["payload"]["reads"] == ["ready"]
    assert "clean" in specialized[0]["payload"]["reads"]
    assert specialized[0]["payload"]["guard"] is not None
    base_run = active.run("ok", {"ready": True, "clean": True}, episode_id="base-read",
                          force_route="base", learn=False, exploration=0)
    special_run = active.run("ok", {"ready": True, "clean": True}, episode_id="special-read",
                             force_route=specialized[0]["uid"], learn=False, exploration=0)
    assert base_run["result"]["output"].strip() == '{"ready": true}'
    assert special_run["result"]["output"].strip() == '{"clean": true, "ready": true}'


def test_frozen_episode_keeps_model_unchanged_and_restore_returns_prior_relation(tmp_path):
    spec = program(cells=[router("root"), command("leaf", SUCCESS)],
                   relations=[relation("base", "root", ["leaf"], ["mode"])], graph_id="restore")
    active = runtime(tmp_path, spec)
    active.run("task", {"mode": "a"}, episode_id="frozen", force_route="base", learn=False)
    assert route_atom(active, "base")["payload"]["model"]["n"] == 0
    active.run("task", {"mode": "a"}, episode_id="learned", force_route="base")
    learned = route_atom(active, "base")
    assert learned["revision"] > 1 and learned["payload"]["model"]["n"] == 1
    active.restore("relation:base", 1, event_id="restore-base")
    assert route_atom(active, "base")["payload"]["model"]["n"] == 0


def test_unscored_command_needs_one_explicit_feedback_before_local_update(tmp_path):
    spec = program(cells=[router("root"), command("leaf", SUCCESS, outcome=None)],
                   relations=[relation("base", "root", ["leaf"], ["mode"])], graph_id="feedback")
    active = runtime(tmp_path, spec)
    report = active.run("task", {"mode": "a"}, episode_id="manual", force_route="base")
    assert report["result"]["success"] is None
    assert route_atom(active, "base")["payload"]["model"]["n"] == 0
    feedback = active.feedback("manual", success=True, source="test:manual-feedback")
    assert feedback["learning_status"] == "WEIGHTS_UPDATED"
    assert route_atom(active, "base")["payload"]["model"]["n"] == 1
    active.feedback("manual", success=True, source="test:manual-feedback")
    assert route_atom(active, "base")["payload"]["model"]["n"] == 1
