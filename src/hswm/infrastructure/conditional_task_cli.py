"""Local JSON CLI for conditional proposals and an authored episode replay.

Calls the same pure functions a future service can use. No tool executor,
canonical admission, graph database connection, or model endpoint is exposed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from hswm.cells.conditional import (
    Observation, Reject, Relation, Rule, dependencies, digest, parse_json, preview, synthesize,
)
from hswm.cells.probe import propose_probe


MAX_INPUT_BYTES = 1_048_576


def _object(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(optional):
        raise Reject("invalid JSON object fields")
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise Reject("expected nonempty text")
    return value


def _list(value):
    if not isinstance(value, list):
        raise Reject("expected JSON list")
    return value


def _key(row):
    return _text(row["role"]), _text(row["field"])


def _mapping(rows, required, value):
    result = {}
    for row in _list(rows):
        _object(row, {"role", "field"} | set(required))
        key = _key(row)
        if key in result:
            raise Reject("duplicate role/field")
        result[key] = value(row)
    return result


def _domain(rows):
    return _mapping(rows, {"values"}, lambda row: _list(row["values"]))


def _values(rows):
    return _mapping(rows, {"value"}, lambda row: row["value"])


def _reads(rows):
    result = []
    for row in _list(rows):
        if not isinstance(row, list) or len(row) != 2:
            raise Reject("expected [role, field] reference")
        result.append(tuple(_text(x) for x in row))
    if len(set(result)) != len(result):
        raise Reject("duplicate read reference")
    return frozenset(result)


def _history(rows):
    result = []
    for row in _list(rows):
        _object(row, {"values", "outcome", "source"})
        result.append({**row, "values": _values(row["values"])})
    return result


def _contexts(rows):
    result = []
    for row in _list(rows):
        _object(row, {"id", "values", "source", "cost"})
        result.append({**row, "values": _values(row["values"])})
    return result


def _checks(value):
    _object(value, {"scope", "expected_scope", "revision", "expected_revision", "now",
                    "allowed_reads", "permitted", "available", "costs", "budget", "source"},
            {"exited", "conflict"})
    return {**value, "allowed_reads": _reads(value["allowed_reads"]),
            "permitted": {_text(x) for x in _list(value["permitted"])},
            "available": {_text(x) for x in _list(value["available"])}}


def _relation(value):
    _object(value, {"uid", "revision", "ast", "source"})
    return Relation(_text(value["uid"]), _text(value["revision"]),
                    json.dumps(value["ast"], allow_nan=False), _text(value["source"]))


def _preview(relation, domain, observations, action, checks):
    reads = dependencies(parse_json(relation.ast_json), domain)
    rule = Rule(0, relation.ref, "TRUE", reads, _text(action), reads)
    return preview([relation], [rule], domain, observations, **checks)


def synthesize_request(request):
    _object(request, {"domain", "examples"},
            {"parent", "search_budget", "candidate_limit", "resume_cursor"})
    return synthesize(_domain(request["domain"]), _history(request["examples"]),
                      **{k: v for k, v in request.items() if k not in {"domain", "examples"}})


def preview_request(request):
    _object(request, {"domain", "relation", "observations", "action", "checks"})
    observations = _mapping(request["observations"], {"value", "revision", "expires_at", "source"},
                            lambda row: Observation(row["value"], row["revision"],
                                                    row["expires_at"], row["source"]))
    return _preview(_relation(request["relation"]), _domain(request["domain"]),
                    observations, request["action"], _checks(request["checks"]))


def probe_request(request):
    _object(request, {"domain", "candidates", "contexts", "allowed_reads", "allowed_probe_ids", "budget"})
    return propose_probe(request["candidates"], _domain(request["domain"]),
                         _contexts(request["contexts"]), allowed_reads=_reads(request["allowed_reads"]),
                         allowed_probe_ids={_text(x) for x in _list(request["allowed_probe_ids"])},
                         budget=request["budget"])


def replay_demo(request):
    """Replay separately declared public feedback after recording a probe plan.

    The CLI sees the whole fixture; this is not evaluator isolation or fresh
    environment execution. The synthesizer and selector receive only their
    declared public inputs and never the fixture's subsequent outcome record.
    """
    _object(request, {"schema_version", "domain", "examples", "initial_relation", "query",
                      "action", "checks", "contexts", "allowed_probe_ids", "probe_budget",
                      "subsequent_outcomes", "outcome_projection"})
    if request["schema_version"] != "hswm-conditional-demo/v1":
        raise Reject("demo schema version")
    projection = _object(request["outcome_projection"], {"kind", "source"})
    if projection["kind"] != "BOOLEAN_SUCCESS_IS_RELATION_TRUTH":
        raise Reject("unsupported task outcome projection")
    _text(projection["source"])
    domain, history = _domain(request["domain"]), _history(request["examples"])
    contexts, checks = _contexts(request["contexts"]), _checks(request["checks"])
    initial = _relation(request["initial_relation"])
    initial_candidates = synthesize(domain, history)
    if digest(parse_json(initial.ast_json)) not in {
            digest(c["relation_ast"]) for c in initial_candidates["candidates"]}:
        raise Reject("demo initial relation must be a current candidate")
    before_request = {"domain": request["domain"], "relation": request["initial_relation"],
                      "observations": request["query"], "action": request["action"],
                      "checks": request["checks"]}
    before = preview_request(before_request)
    probe = propose_probe(
        [{"relation_ast": c["relation_ast"], "source": c["input_provenance_digest"]}
         for c in initial_candidates["candidates"]], domain, contexts,
        allowed_reads=checks["allowed_reads"],
        allowed_probe_ids={_text(x) for x in _list(request["allowed_probe_ids"])},
        budget=request["probe_budget"])
    result = {"status": "AUTHORED_EPISODE_REPLAY_NOT_EFFICACY", "input_digest": digest(request),
              "initial_candidates": initial_candidates, "before": before, "probe": probe,
              "outcome_projection": projection,
              "preview_query": {"role": "SAME_SUPPLIED_QUERY_BEFORE_AFTER_RESTORE",
                                "digest": digest(request["query"])},
              "credit": "UNIDENTIFIED_CREDIT", "canonical_revision": None}
    if probe["status"] != "PROBE_PROPOSAL":
        return {**result, "revised_candidates": None, "after": None, "reason": "no_probe"}
    selected_id = probe["selected_probe"]["probe_id"]
    outcomes = {}
    for row in _list(request["subsequent_outcomes"]):
        _object(row, {"probe_id", "outcome", "source"})
        probe_id = _text(row["probe_id"])
        if probe_id in outcomes or type(row["outcome"]) is not bool:
            raise Reject("duplicate or malformed subsequent outcome")
        outcomes[probe_id] = {**row, "source": _text(row["source"])}
    if selected_id not in outcomes:
        return {**result, "revised_candidates": None, "after": None, "reason": "await_public_outcome"}
    selected_context = next(c for c in contexts if c["id"] == selected_id)
    outcome = outcomes[selected_id]
    # The relation's TRUE/FALSE prediction is a success predicate only in this
    # authored task's declared mapping. No causal credit follows from the match.
    revised = synthesize(domain, history + [{"values": selected_context["values"],
                         "outcome": outcome["outcome"], "source": outcome["source"]}], parent=digest(initial.ref))
    result.update({"subsequent_public_outcome": {**outcome, "probe_proposal_digest": probe["proposal_digest"]},
                   "revised_candidates": revised, "after": None})
    if revised["candidates"]:
        proposed = {"uid": initial.uid, "revision": "demo-proposal:" + revised["input_provenance_digest"],
                    "ast": revised["candidates"][0]["relation_ast"],
                    "source": revised["input_provenance_digest"]}
        result.update({"after": preview_request({**before_request, "relation": proposed}),
                       "restored": preview_request(before_request),
                       "selection": "FIRST_ENUMERATED_FOR_AUTHORED_DEMO_NOT_ADMITTED"})
    return result


def _load(path):
    if path == "-":
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise Reject("input exceeds 1 MiB")
    return parse_json(raw.decode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="HSWM conditional task proposals (local; no external actions)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [("synthesize", "Propose relations from public examples"),
                            ("preview", "Evaluate a selected relation and propose the next step"),
                            ("probe", "Choose a declared context where candidate predictions differ"),
                            ("demo", "Replay an authored public episode fixture")]:
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("input", help="JSON input file, or - for stdin")
        subparser.add_argument("--output", type=Path, help="Save JSON result (default: stdout)")
        if name == "synthesize":
            subparser.add_argument("--resume-from", help="Prior result JSON containing a resume_cursor")
    args = parser.parse_args(argv)
    try:
        request = _load(args.input)
        if args.command == "synthesize" and args.resume_from:
            if not isinstance(request, dict) or "resume_cursor" in request:
                raise Reject("resume cursor must have exactly one source")
            previous = _load(args.resume_from)
            if not isinstance(previous, dict) or not previous.get("resume_cursor"):
                raise Reject("prior result has no continuation")
            request = {**request, "resume_cursor": previous["resume_cursor"]}
        handler = {"synthesize": synthesize_request, "preview": preview_request,
                   "probe": probe_request, "demo": replay_demo}[args.command]
        result = handler(request)
        output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.output:
            # The named output is an ordinary proposal file, not durable admission.
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0
    except (Reject, OSError, UnicodeError) as error:
        print(json.dumps({"status": "REJECTED", "reason": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
