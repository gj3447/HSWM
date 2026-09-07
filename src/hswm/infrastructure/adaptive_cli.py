"""Local CLI for the bounded adaptive hypergraph runtime."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from uuid import uuid4

from hswm.cells.adaptive_runtime import AdaptiveRuntime
from hswm.cells.adaptive_store import AdaptiveStoreError
from hswm.cells.conditional import Reject, parse_json

MAX_PROGRAM_BYTES = 1_000_000
RUN_EXIT_CODES = {"SUCCEEDED": 0, "FAILED": 1, "UNKNOWN": 3, "WITHHOLD": 4, "RUNNING": 5}

class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({"status": "ERROR", "code": 2, "error": message}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)


def _json_object(text: str, label: str) -> dict:
    value = parse_json(text)
    if not isinstance(value, dict):
        raise Reject(f"{label} must be a JSON object")
    return value


def _program(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_PROGRAM_BYTES + 1)
        if len(raw) > MAX_PROGRAM_BYTES:
            raise Reject("program exceeds 1000000 byte bound")
        return _json_object(raw.decode("utf-8"), "program")
    except (OSError, UnicodeDecodeError) as error:
        raise Reject(f"cannot read program: {path}") from error


def _bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def parser() -> argparse.ArgumentParser:
    result = _Parser(description="Run a local, bounded adaptive hypergraph program.")
    result.add_argument("--program", type=Path, required=True, help="strict JSON adaptive-program file")
    result.add_argument("--state", type=Path, default=Path(".hswm-local/runtime.sqlite3"), help="local SQLite state file")
    result.add_argument("--workspace", type=Path, default=Path.cwd(), help="workspace for declared command cells")
    commands = result.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="select an eligible route without executing it")
    plan.add_argument("--context", required=True, help="strict JSON object matching the declared context")
    plan.add_argument("--budget", type=float, default=60.0)
    plan.add_argument("--cell", help="router cell id to inspect; default is the root router")
    plan.add_argument("--route", help="force an eligible relation uid")
    plan.add_argument("--allow", action="append", help="allowed cell id; repeat to allow several")
    run = commands.add_parser("run", help="execute one bounded episode")
    run.add_argument("--context", required=True, help="strict JSON object matching the declared context")
    run.add_argument("--task", required=True)
    run.add_argument("--episode", default=None, help="stable episode id; generated when omitted")
    run.add_argument("--budget", type=float, default=60.0)
    run.add_argument("--max-calls", type=int, default=16)
    run.add_argument("--frozen", action="store_true", help="do not update local relation models")
    run.add_argument("--route", help="force an eligible relation uid")
    run.add_argument("--allow", action="append", help="allowed cell id; repeat to allow several")
    commands.add_parser("graph", help="print local immutable heads and rewrite events")
    commands.add_parser("status", help="summarize local atom and episode state")
    feedback = commands.add_parser("feedback", help="record explicit feedback for an episode")
    feedback.add_argument("--episode", required=True)
    feedback.add_argument("--success", type=_bool, required=True)
    feedback.add_argument("--source", required=True)
    restore = commands.add_parser("restore", help="restore a prior relation revision")
    restore.add_argument("--relation", required=True, help="relation uid, with or without relation: prefix")
    restore.add_argument("--revision", type=int, required=True)
    restore.add_argument("--event", default=None, help="stable restore event id; generated when omitted")
    return result


def run(args: argparse.Namespace) -> dict:
    workspace = args.workspace.resolve()
    state = args.state if args.state.is_absolute() else workspace / args.state
    runtime = AdaptiveRuntime(_program(args.program), state, workspace)
    if args.command == "plan":
        return runtime.plan(_json_object(args.context, "context"), cell_id=args.cell, budget=args.budget,
                            allowed=args.allow, force_route=args.route)
    if args.command == "run":
        return runtime.run(args.task, _json_object(args.context, "context"),
                           episode_id=args.episode or str(uuid4()), budget=args.budget,
                           max_calls=args.max_calls, allowed=args.allow,
                           learn=not args.frozen, force_route=args.route)
    if args.command == "graph":
        return runtime.graph()
    if args.command == "status":
        graph = runtime.graph()
        atoms = graph["atoms"]
        relations = [atom for atom in atoms if atom["kind"] == "relation"]
        episodes = [atom for atom in atoms if atom["kind"] == "episode"]
        return {"schema_version": graph["schema_version"], "graph_id": graph["graph_id"],
                "atom_kinds": dict(sorted(Counter(atom["kind"] for atom in atoms).items())),
                "episode_statuses": dict(sorted(Counter(atom["payload"].get("status", "UNKNOWN") for atom in episodes).items())),
                "relations": [{"uid": atom["uid"], "revision": atom["revision"],
                               "active": atom["payload"].get("active"),
                               "reads": atom["payload"].get("reads"),
                               "observations": atom["payload"].get("model", {}).get("n")}
                              for atom in relations],
                "event_count": len(graph["events"]),
                "claim": "LOCAL_RUNTIME_STATE_NOT_REFERENCE_KG"}
    if args.command == "feedback":
        return runtime.feedback(args.episode, success=args.success, source=args.source)
    uid = args.relation if args.relation.startswith("relation:") else "relation:" + args.relation
    return runtime.restore(uid, args.revision, event_id=args.event or str(uuid4()))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except (Reject, AdaptiveStoreError, OSError, ValueError) as error:
        print(json.dumps({"status": "ERROR", "code": 2, "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return RUN_EXIT_CODES.get(result.get("status"), 0) if args.command == "run" else 0


if __name__ == "__main__":
    raise SystemExit(main())
