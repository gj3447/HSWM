import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hswm.infrastructure.conditional_task_cli import (
    main, probe_request, replay_demo, synthesize_request,
)
from hswm.cells.conditional import Reject, digest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "_research/causal_composition/examples/conditional_task_demo.v1.json"


def example():
    return json.loads(EXAMPLE.read_text())


def test_demo_feedback_changes_relation_read_set_and_action_and_restore():
    report = replay_demo(example())
    assert report["status"] == "AUTHORED_EPISODE_REPLAY_NOT_EFFICACY"
    assert report["probe"]["selected_probe"]["probe_id"] == "ready-dirty"
    assert {p["relation_prediction"] for p in report["probe"]["selected_probe"]["predictions"]} == {"TRUE", "FALSE"}
    assert report["before"]["hypothetical_next_step"]["kind"] == "ACTION_PROPOSAL"
    assert report["after"]["hypothetical_next_step"]["kind"] == "WITHHOLD"
    assert len(report["before"]["hypothetical_read_set"]) == 1
    assert len(report["after"]["hypothetical_read_set"]) == 2
    assert report["restored"] == report["before"]
    assert report["canonical_revision"] is None
    assert report["credit"] == "UNIDENTIFIED_CREDIT"


def test_subsequent_feedback_never_reaches_proposal_selection():
    first = example()
    second = copy.deepcopy(first)
    second["subsequent_outcomes"][0]["outcome"] = True
    a, b = replay_demo(first), replay_demo(second)
    assert a["initial_candidates"] == b["initial_candidates"]
    assert a["probe"] == b["probe"]
    assert a["revised_candidates"] != b["revised_candidates"]
    first["subsequent_outcomes"] = []
    pending = replay_demo(first)
    assert pending["reason"] == "await_public_outcome" and pending["after"] is None


def test_no_permitted_probe_produces_no_revision():
    request = example()
    request["allowed_probe_ids"] = []
    result = replay_demo(request)
    assert result["probe"]["status"] == "WITHHOLD"
    assert result["after"] is None and result["revised_candidates"] is None


def test_outcome_mapping_required_and_query_distinct_from_probe():
    request = example()
    request["outcome_projection"]["kind"] = "UNDECLARED_CAUSAL_CREDIT"
    with pytest.raises(Reject, match="outcome projection"):
        replay_demo(request)
    request = example()
    request["query"][1]["value"] = 1
    result = replay_demo(request)
    assert result["probe"]["selected_probe"]["probe_id"] == "ready-dirty"
    assert result["after"]["hypothetical_next_step"]["kind"] == "ACTION_PROPOSAL"
    assert result["preview_query"] == {
        "role": "SAME_SUPPLIED_QUERY_BEFORE_AFTER_RESTORE", "digest": digest(request["query"])}


def test_standalone_json_commands_and_continuation(tmp_path, capsys):
    request = example()
    synthesis = {"domain": request["domain"], "examples": request["examples"], "candidate_limit": 1}
    source, output = tmp_path / "input.json", tmp_path / "first.json"
    source.write_text(json.dumps(synthesis))
    assert main(["synthesize", str(source), "--output", str(output)]) == 0
    first = json.loads(output.read_text())
    assert first["stop_reason"] == "CANDIDATE_LIMIT"
    assert main(["synthesize", str(source), "--resume-from", str(output)]) == 0
    next_page = json.loads(capsys.readouterr().out)
    assert next_page["search_offset"] > first["search_offset"]
    assert next_page["candidates"][0]["relation_ast"] != first["candidates"][0]["relation_ast"]
    preview_input = {"domain": request["domain"], "relation": request["initial_relation"],
                     "observations": request["query"], "action": request["action"], "checks": request["checks"]}
    source.write_text(json.dumps(preview_input))
    assert main(["preview", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["hypothetical_next_step"]["kind"] == "ACTION_PROPOSAL"
    candidates = synthesize_request({"domain": request["domain"], "examples": request["examples"]})["candidates"]
    probe = probe_request({"domain": request["domain"], "contexts": request["contexts"],
                          "allowed_reads": request["checks"]["allowed_reads"],
                          "allowed_probe_ids": request["allowed_probe_ids"], "budget": 1,
                          "candidates": [{"relation_ast": c["relation_ast"], "source": c["input_provenance_digest"]} for c in candidates]})
    assert probe["selected_probe"]["probe_id"] == "ready-dirty"


@pytest.mark.parametrize("raw", ["{", '{"domain":[],"domain":[]}', "[]", "null",
                                  '{"domain":[],"examples":[],"search_budget":NaN}'])
def test_cli_rejects_bad_input_without_traceback(tmp_path, capsys, raw):
    path = tmp_path / "bad.json"
    path.write_text(raw)
    assert main(["synthesize", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["status"] == "REJECTED"


def test_module_cli_supports_stdin_without_service_or_credentials():
    completed = subprocess.run([sys.executable, "-m", "hswm.infrastructure.conditional_task_cli", "demo", "-"],
                               input=EXAMPLE.read_text(), text=True, capture_output=True, cwd=ROOT, timeout=10)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["after"]["hypothetical_next_step"]["kind"] == "WITHHOLD"
