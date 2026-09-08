"""Checkout-oriented local development wrapper for bounded HSWM profiles."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
import tomllib
from uuid import uuid4

from hswm.cells.adaptive_runtime import AdaptiveRuntime
from hswm.cells.adaptive_store import AdaptiveStoreError
from hswm.cells.conditional import Reject
from hswm.infrastructure.adaptive_cli import RUN_EXIT_CODES, _bool, _program


ROOT = Path(__file__).resolve().parents[3]
PROFILES = {
    "game": ROOT / "_research/causal_composition/examples/adaptive_game_development.v2.json",
    "maplelineage": ROOT / "_research/causal_composition/examples/adaptive_maplelineage_development.v1.json",
    "supullim": ROOT / "_research/causal_composition/examples/adaptive_supullim_development.v1.json",
    "reluvator": ROOT / "_research/causal_composition/examples/adaptive_reluvator_development.v1.json",
    "hswm": ROOT / "_research/causal_composition/examples/adaptive_hswm_development.v1.json",
}
ALIASES = {"the-excel-tycoon": "game", "버엑시": "game", "메이플리니지": "maplelineage"}
FOCI = {"game": ["session", "bridge", "career", "graph", "check"], "maplelineage": ["combat", "encounter"],
        "supullim": ["soop", "creator"], "reluvator": ["contracts", "mesh"],
        "hswm": ["runtime", "usl", "ontology", "docs"]}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({"status": "ERROR", "code": 2, "error": message}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)


def state_path(project: str, workspace: Path, explicit: Path | None) -> Path:
    project = ALIASES.get(project, project)
    if explicit is not None:
        return explicit if explicit.is_absolute() else workspace.resolve() / explicit
    suffix = sha256(str(workspace.resolve()).encode()).hexdigest()[:16]
    return ROOT / ".hswm-local/projects" / f"{project}-{suffix}.sqlite3"


def _common(command: argparse.ArgumentParser, project: str) -> None:
    command.add_argument("--workspace", type=Path, default=Path.cwd(),
                         help="local workspace used to isolate HSWM state, including remote-check profiles")
    command.add_argument("--state", type=Path)
    choices = FOCI[project]
    command.add_argument("--focus", choices=choices, default=choices[0])
    command.add_argument("--stage", choices=["development", "regression"], default="development")


def parser() -> argparse.ArgumentParser:
    result = _Parser(description="Run bounded local HSWM development profiles for a checkout.")
    projects = result.add_subparsers(dest="project", required=True)
    for project in PROFILES:
        project_parser = projects.add_parser(project, aliases=[key for key, value in ALIASES.items() if value == project],
                                             help=f"{project} checkout profile")
        actions = project_parser.add_subparsers(dest="action", required=True)
        plan = actions.add_parser("plan", help="select a local profile route")
        _common(plan, project)
        plan.add_argument("--route")
        plan.add_argument("--budget", type=float, default=60.0)
        run = actions.add_parser("run", help="run a bounded local profile episode")
        _common(run, project)
        run.add_argument("--task", required=True)
        run.add_argument("--episode", default=None)
        run.add_argument("--budget", type=float, default=60.0)
        run.add_argument("--frozen", action="store_true")
        run.add_argument("--route")
        status = actions.add_parser("status", help="summarize local state and feedback backlog")
        _common(status, project)
        feedback = actions.add_parser("feedback", help="record explicit local feedback")
        _common(feedback, project)
        feedback.add_argument("--episode", required=True)
        feedback.add_argument("--success", type=_bool, required=True)
        feedback.add_argument("--source", required=True)
    return result


def _validate_hswm_workspace(workspace: Path) -> None:
    manifest = workspace / "pyproject.toml"
    try:
        project = tomllib.loads(manifest.read_text(encoding="utf-8")).get("project", {})
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise Reject("hswm workspace must contain a readable HSWM pyproject.toml") from error
    if (not isinstance(project, dict) or project.get("name") != "hswm" or
            not (workspace / "src" / "hswm").is_dir() or not (workspace / "tests").is_dir() or
            not (workspace / "scripts").is_dir()):
        raise Reject("hswm workspace marker mismatch")


def _runtime(args: argparse.Namespace) -> AdaptiveRuntime:
    workspace = args.workspace.resolve()
    project = ALIASES.get(args.project, args.project)
    if project == "hswm":
        _validate_hswm_workspace(workspace)
    return AdaptiveRuntime(_program(PROFILES[project]), state_path(project, workspace, args.state), workspace)


def _status(runtime: AdaptiveRuntime) -> dict:
    graph = runtime.graph()
    atoms = graph["atoms"]
    episodes = [atom for atom in atoms if atom["kind"] == "episode"]
    relations = [atom for atom in atoms if atom["kind"] == "relation"]
    pending = []
    for atom in episodes:
        payload = atom["payload"]
        result = payload.get("result", {})
        if payload.get("feedback") is None and type(result.get("success")) is not bool:
            intent = payload.get("intent", {})
            pending.append({"episode": payload.get("episode_id"), "task": intent.get("task"),
                            "status": payload.get("status"), "started_at": payload.get("started_at")})
    pending.sort(key=lambda value: (value["started_at"] is None, value["started_at"] or 0), reverse=True)
    return {"schema_version": graph["schema_version"], "project": runtime.graph_id,
            "atom_kinds": dict(sorted(Counter(atom["kind"] for atom in atoms).items())),
            "episode_statuses": dict(sorted(Counter(atom["payload"].get("status", "UNKNOWN") for atom in episodes).items())),
            "pending_feedback": pending[:10], "event_count": len(graph["events"]),
            "relations": [{"uid": atom["uid"], "revision": atom["revision"],
                           "observations": atom["payload"].get("model", {}).get("n")}
                          for atom in relations],
            "claim": ("LOCAL_DEVELOPMENT_FEEDBACK_NOT_FIELD_OR_INFERENCE_AUTHORITY"
                      if runtime.graph_id == "hswm-reluvator-delltower-development-feedback-v1"
                      else "LOCAL_DEVELOPMENT_FEEDBACK_NOT_SELF_VALIDATION_OR_EFFICACY"
                      if runtime.graph_id == "hswm-self-development-feedback-v1"
                      else "LOCAL_DEVELOPMENT_FEEDBACK_NOT_GAME_OR_PLATFORM_AUTHORITY")}


def run(args: argparse.Namespace) -> dict:
    runtime = _runtime(args)
    context = {"focus": args.focus, "stage": args.stage}
    if args.action == "plan":
        return runtime.plan(context, budget=args.budget, force_route=args.route)
    if args.action == "run":
        return runtime.run(args.task, context, episode_id=args.episode or str(uuid4()), budget=args.budget,
                           learn=not args.frozen, force_route=args.route)
    if args.action == "feedback":
        return runtime.feedback(args.episode, success=args.success, source=args.source)
    return _status(runtime)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except (Reject, AdaptiveStoreError, OSError, ValueError) as error:
        print(json.dumps({"status": "ERROR", "code": 2, "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return RUN_EXIT_CODES.get(result.get("status"), 0) if args.action == "run" else 0


if __name__ == "__main__":
    raise SystemExit(main())
