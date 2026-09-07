import json
from dataclasses import replace

import pytest

from hswm.cells.conditional import (
    Observation, Reject, Relation, Rule, dependencies, evaluate, parse_json,
    preview, synthesize,
)

DOMAIN = {("part", "ready"): [0, 1], ("part", "clean"): [0, 1]}


def eq(field, value=1):
    return {"op": "eq", "left": {"role": "part", "field": field}, "right": value}


def relation(ast, revision="r1"):
    return Relation("relation", revision, json.dumps(ast), "authored:test")


def run(rel, observations=None, **changes):
    reads = dependencies(parse_json(rel.ast_json), DOMAIN)
    args = dict(scope="test", expected_scope="test", revision="p1", expected_revision="p1",
                now=1, allowed_reads=set(DOMAIN), permitted={"join", "OBSERVE"},
                available={"join", "OBSERVE"}, costs={"join": 2, "OBSERVE": 1},
                budget=3, source="authored:test")
    args.update(changes)
    rule = Rule(0, rel.ref, "TRUE", reads, "join", reads)
    return preview([rel], [rule], DOMAIN, observations or {}, **args)


def obs(ready=1, clean=0):
    return {("part", "ready"): Observation(ready, "p1", 10, "obs:ready"),
            ("part", "clean"): Observation(clean, "p1", 10, "obs:clean")}


def kind(result):
    return result["hypothetical_next_step"]["kind"]


def test_relation_change_readset_action_and_restore():
    first = relation(eq("ready"))
    second = relation({"op": "all", "children": [eq("ready"), eq("clean")]}, "r2")
    before, after = run(first, obs()), run(second, obs())
    assert kind(before) == "ACTION_PROPOSAL"
    assert kind(after) == "WITHHOLD"
    assert len(before["hypothetical_read_set"]) == 1
    assert len(after["hypothetical_read_set"]) == 2
    assert before["preview_uid"] != after["preview_uid"]
    assert run(first, obs()) == before
    assert before["status"] == "DESIGN_ONLY_NO_EXECUTION"


@pytest.mark.parametrize("op,children,expected", [
    ("all", [eq("clean"), eq("ready")], "FALSE"),
    ("any", [eq("clean", 0), eq("ready")], "TRUE"),
    ("all", [eq("clean", 0), eq("ready")], "UNKNOWN"),
])
def test_kleene(op, children, expected):
    value, _ = evaluate({"op": op, "children": children}, DOMAIN,
                        {("part", "clean"): obs()[("part", "clean")]},
                        allowed_reads=DOMAIN, now=1, revision="p1")
    assert value == expected


def test_unknown_expiry_and_unused_unknown():
    rel = relation(eq("ready"))
    assert kind(run(rel)) == "OBSERVE"
    assert kind(run(rel, {("part", "ready"): obs()[("part", "ready")]})) == "ACTION_PROPOSAL"
    assert kind(run(rel, obs(), now=10)) == "OBSERVE"
    assert kind(run(rel, budget=0)) == "WITHHOLD"
    value, _ = evaluate({"op": "not", "child": eq("ready")}, DOMAIN, {},
                        allowed_reads=DOMAIN, now=1, revision="p1")
    assert value == "UNKNOWN"


@pytest.mark.parametrize("change", [dict(scope="other"), dict(revision="p2"),
    dict(exited=True), dict(conflict=True), dict(budget=0), dict(permitted=set()),
    dict(available=set())])
def test_current_checks(change):
    assert kind(run(relation(eq("ready")), obs(), **change)) == "WITHHOLD"


@pytest.mark.parametrize("ast", [eq("secret"), eq("ready", True),
    {**eq("ready"), "extra": 1}, {"op": "all", "children": []}])
def test_reject_invalid_ast(ast):
    with pytest.raises(Reject):
        dependencies(ast, DOMAIN)


def test_reject_duplicate_unauthorized_and_bad_observation():
    with pytest.raises(Reject):
        parse_json('{"op":"eq","op":"not"}')
    with pytest.raises(Reject):
        run(relation(eq("ready")), allowed_reads=set())
    with pytest.raises(Reject):
        run(relation(eq("ready")), {("part", "ready"): Observation(True, "p1", 10, "source")})


@pytest.mark.parametrize("raw", ["{", '{"op":"eq","n":NaN}', '{"op":"eq","n":Infinity}', '{"op":"eq","n":1e999}'])
def test_reject_malformed_or_nonfinite_json_as_one_boundary(raw):
    with pytest.raises(Reject):
        parse_json(raw)


def test_reject_malformed_rule_and_observation_at_preview_boundary():
    rel = relation(eq("ready"))
    reads = dependencies(eq("ready"), DOMAIN)
    args = dict(scope="s", expected_scope="s", revision="p1", expected_revision="p1",
                now=1, allowed_reads=DOMAIN, permitted={"join", "OBSERVE"},
                available={"join", "OBSERVE"}, costs={"join": 1, "OBSERVE": 1},
                budget=2, source="test")
    with pytest.raises(Reject):
        preview([rel], [Rule(0, [], "TRUE", reads, "join", reads)], DOMAIN, {}, **args)
    with pytest.raises(Reject):
        preview([rel], [Rule(0, rel.ref, [], reads, "join", reads)], DOMAIN, {}, **args)
    with pytest.raises(Reject):
        preview([rel], [Rule(0, rel.ref, "TRUE", reads, "join", [])], DOMAIN, {}, **args)
    with pytest.raises(Reject):
        preview([rel], [Rule(0, rel.ref, "TRUE", reads, "join", reads)], DOMAIN,
                {("part", "ready"): Observation(1, "p1", float("nan"), "source")}, **args)
    malformed = Relation("relation", "r1", "{", "authored:test")
    with pytest.raises(Reject, match="malformed JSON"):
        preview([malformed], [Rule(0, malformed.ref, "TRUE", reads, "join", reads)],
                DOMAIN, {}, **args)


def test_exact_reference_remove_and_priority_unknown_no_fallthrough():
    rel = relation(eq("ready"))
    reads = dependencies(eq("ready"), DOMAIN)
    rule = Rule(0, rel.ref, "TRUE", reads, "join", reads)
    args = dict(scope="s", expected_scope="s", revision="p1", expected_revision="p1",
                now=1, allowed_reads=DOMAIN, permitted={"join", "OBSERVE"},
                available={"join", "OBSERVE"}, costs={"join": 1, "OBSERVE": 1}, budget=2, source="test")
    with pytest.raises(Reject):
        preview([], [rule], DOMAIN, {}, **args)
    with pytest.raises(Reject):
        preview([replace(rel, revision="r2")], [rule], DOMAIN, {}, **args)
    later = replace(rule, priority=1, expected_truth="FALSE")
    assert kind(preview([rel], [later, rule], DOMAIN, {}, **args)) == "OBSERVE"


def examples():
    return [{"values": {("part", "ready"): r, ("part", "clean"): c},
             "outcome": bool(r and c), "source": f"authored:observed:{r}:{c}"}
            for r, c in [(0, 0), (0, 1), (1, 1), (1, 0)]]


def test_experience_generation_revision_and_preview():
    early = synthesize(DOMAIN, examples()[:3])
    assert eq("ready") in [c["relation_ast"] for c in early["candidates"]]
    revised = synthesize(DOMAIN, examples(), parent="r1")
    assert eq("ready") not in [c["relation_ast"] for c in revised["candidates"]]
    candidate = revised["candidates"][0]
    assert candidate["relation_ast"]["op"] == "all"
    assert candidate["parent_revision"] == "r1"
    assert kind(run(relation(candidate["relation_ast"], "r2"), obs())) == "WITHHOLD"
    assert candidate["credit"] == "UNIDENTIFIED_CREDIT"
    again = synthesize(DOMAIN, examples(), parent="r1")
    assert again == revised  # Honest rederivation, with enumeration charged again.
    assert again["examined"] > 0


def test_conflicting_experience_and_input_boundary():
    data = examples()
    data.append({**data[0], "outcome": True, "source": "authored:conflict"})
    assert synthesize(DOMAIN, data)["status"] == "REOPEN"
    with pytest.raises(Reject):
        synthesize(DOMAIN, [{**examples()[0], "hidden_rule": "answer"}])


def test_step_digest_trace_digest_and_rule_provenance_change_without_changing_static_uid():
    rel = relation(eq("ready"))
    false_preview = run(rel, {("part", "ready"): Observation(0, "p1", 10, "obs:ready")})
    true_preview = run(rel, {("part", "ready"): Observation(1, "p1", 10, "obs:ready")})
    assert false_preview["preview_uid"] == true_preview["preview_uid"]
    assert false_preview["step_input_digest"] != true_preview["step_input_digest"]
    assert false_preview["hypothetical_read_set"][0]["observation_digest"] != true_preview["hypothetical_read_set"][0]["observation_digest"]
    assert false_preview["selected_rule_provenance"] is None
    assert true_preview["selected_rule_provenance"]["priority"] == 0
    assert true_preview["evaluated_rule_provenance"][-1]["truth"] == "TRUE"


def test_synthesis_stop_reason_and_digest_bound_resume_reaches_later_candidates():
    domain = {("part", f"a{i}"): [0, 1] for i in range(9)}
    domain[("part", "z")] = [0, 1]
    data = [{"values": {key: value for key in domain}, "outcome": bool(value), "source": f"s:{value}"}
            for value in (0, 1)]
    first = synthesize(domain, data)
    assert first["stop_reason"] == "CANDIDATE_LIMIT"
    assert first["truncated"] and not first["search_complete"]
    assert all('"field": "z"' not in json.dumps(item["relation_ast"], sort_keys=True)
               for item in first["candidates"])
    second = synthesize(domain, data, resume_cursor=first["resume_cursor"])
    assert second["search_offset"] > 0
    assert any('"field": "z"' in json.dumps(item["relation_ast"], sort_keys=True)
               for item in second["candidates"])
    tampered = {**first["resume_cursor"], "offset": 999}
    with pytest.raises(Reject):
        synthesize(domain, data, resume_cursor=tampered)
    stale = [{**data[0], "source": "changed"}, data[1]]
    with pytest.raises(Reject):
        synthesize(domain, stale, resume_cursor=first["resume_cursor"])


def test_synthesis_search_budget_and_space_exhaustion_are_explicit():
    limited = synthesize(DOMAIN, examples(), search_budget=1)
    assert limited["stop_reason"] == "SEARCH_BUDGET"
    assert limited["truncated"] and limited["resume_cursor"] is not None
    exhausted = synthesize({("part", "one"): [0]}, [{"values": {("part", "one"): 0},
                                                         "outcome": True, "source": "s"}])
    assert exhausted["stop_reason"] == "SPACE_EXHAUSTED"
    assert exhausted["search_complete"] and exhausted["resume_cursor"] is None


def test_synthesis_domain_bound_prevents_materializing_unbounded_combinations():
    domain = {("part", f"f{i}"): [0, 1] for i in range(65)}
    example = {"values": {key: 0 for key in domain}, "outcome": False, "source": "s"}
    with pytest.raises(Reject, match="search domain bound"):
        synthesize(domain, [example])
