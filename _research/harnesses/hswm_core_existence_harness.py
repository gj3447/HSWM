#!/usr/bin/env python3
"""HSWM core 개발 harness (concentration overlay).

Speak-as: "HSWM core 개발" — build core + existence science + elevate plan.
Bans 333/p2p/public as main. Does not supersede F1 runbook/judge.
Never issues model POSTs. Plan is assumed imperfect (고도화 pillar).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "hswm-core-existence-harness-receipt/v1"
CONFIG_NAME = "hswm_core_existence_harness.v1.json"
CONFIG_PATH = Path("manifests") / CONFIG_NAME

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_CALL_FORBIDDEN = 2
EXIT_FOCUS_BREAK = 3
EXIT_T1_READYISH = 4


def _discover_repository_root(anchor: str | Path = __file__) -> Path:
    """Locate the HSWM checkout independently of this harness's depth."""
    resolved = Path(anchor).resolve(strict=True)
    start = resolved.parent if resolved.is_file() else resolved
    for candidate in (start, *start.parents):
        if (candidate / CONFIG_PATH).is_file():
            return candidate
    raise RuntimeError(f"cannot locate HSWM repository root from {resolved}")


REPO_ROOT = _discover_repository_root()


@dataclass
class Check:
    id: str
    status: str
    detail: str
    blocking: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _find_symposium_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "HSWM" / CONFIG_PATH).is_file():
            return p
        if p.name == "HSWM" and (p / CONFIG_PATH).is_file():
            return p.parent
    # A standalone clone is not required to be named exactly ``HSWM``.
    return REPO_ROOT


def _resolve_layout(candidate: Path) -> tuple[Path, Path]:
    """Return ``(outer_root, hswm_root)`` for monorepo or standalone layout."""

    resolved = candidate.resolve()
    if (resolved / CONFIG_PATH).is_file():
        return resolved.parent, resolved
    nested = resolved / "HSWM"
    if (nested / CONFIG_PATH).is_file():
        return resolved, nested
    raise FileNotFoundError(
        f"neither {resolved / CONFIG_PATH} nor {nested / CONFIG_PATH} exists"
    )


def load_config(hswm_dir: Path) -> dict[str, Any]:
    path = hswm_dir / CONFIG_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "hswm-core-existence-harness-config/v1":
        raise ValueError(f"bad schema: {data.get('schema_version')}")
    return data


def read_f1_decision(report: Path) -> str | None:
    if not report.is_file():
        return None
    text = report.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"`(A2_[^`]+)`", text)
    return m.group(1) if m else None


def scan_continuation_for_bans(continuation: Path, ban_keys: list[str]) -> list[str]:
    """Heuristic: recent top of CONTINUATION talking about banned mains."""
    if not continuation.is_file():
        return []
    text = continuation.read_text(encoding="utf-8", errors="replace")
    # only first ~120 lines (newest handoffs)
    head = "\n".join(text.splitlines()[:120])
    hits: list[str] = []
    patterns = {
        "333_committee_reconfig_as_main": r"333.*committee|committee-reconfig|epoch change",
        "p2p_webrtc_public_service": r"WebRTC|p2p.*public|public.*p2p",
        "kg_canonicalization_as_hswm_progress": r"kg-canonicalization|P5 HSWM 분리|uid 백필",
        "bhgman_mcp_surface_migration_as_hswm_progress": r"bhgman M9|static.skills.migration",
        "metahumo_launch_as_hswm_proof": r"metahumo.*launch|WORLD_FIRST_HSWM",
    }
    for key in ban_keys:
        pat = patterns.get(key)
        if not pat:
            continue
        if re.search(pat, head, re.I):
            # allow if same window also has strong F1 motion markers
            if re.search(r"F1 r8|try3-a2|development power|sealed-r8", head, re.I):
                continue
            hits.append(key)
    return hits


def diagnose(
    root: Path,
    config: dict[str, Any],
    *,
    hswm_root: Path | None = None,
    active_track: str,
    user_approved_focus: bool,
    identity: str | None,
    claimed_main: str | None,
) -> dict[str, Any]:
    hswm = hswm_root or root / "HSWM"
    pointers = config["pointers"]

    def resolve_pointer(value: str) -> Path:
        pointer = Path(value)
        if pointer.is_absolute():
            return pointer
        if pointer.parts and pointer.parts[0] == "HSWM":
            return hswm.joinpath(*pointer.parts[1:])
        return root / pointer

    scoreboard = resolve_pointer(pointers["scoreboard"])
    core_dev = resolve_pointer(pointers["canonical_name"])
    concentration_doc = resolve_pointer(pointers["human_entry"])
    f1_report = resolve_pointer(pointers["f1_report"])
    f1_op = resolve_pointer(pointers["f1_operator"])
    continuation = root / "docs" / "CONTINUATION.md"
    if not continuation.exists():
        continuation = hswm / "docs" / "CONTINUATION.md"

    checks: list[Check] = []

    for label, p in [
        ("core_dev_name", core_dev),
        ("scoreboard", scoreboard),
        ("config", hswm / CONFIG_PATH),
        ("concentration_doc", concentration_doc),
        ("f1_report", f1_report),
        ("f1_operator", f1_op),
    ]:
        checks.append(
            Check(
                id=f"local.{label}",
                status="PASS" if p.exists() else "FAIL",
                detail=str(p),
                blocking=label in {"config", "scoreboard", "core_dev_name"},
            )
        )

    # scoreboard must state X1 not measured and partial existence
    if scoreboard.is_file():
        sb = scoreboard.read_text(encoding="utf-8", errors="replace")
        need = ["X1", "NOT_MEASURED", "부분"]
        missing = [n for n in need if n not in sb]
        checks.append(
            Check(
                id="t0.scoreboard_honest",
                status="PASS" if not missing else "FAIL",
                detail="ok" if not missing else f"missing markers: {missing}",
                blocking=False,
            )
        )

    ladder = config["existence_ladder"]
    x1 = next(x for x in ladder if x["id"] == "X1_TYPED_LLM_FUNCTION_NETWORK")
    checks.append(
        Check(
            id="ladder.x1_primary",
            status="INFO",
            detail=f"X1 status={x1['status']} track={x1.get('track')}",
            blocking=False,
        )
    )

    # identity
    if identity in {"KEEP_A2", "FORCE_A3"}:
        checks.append(
            Check(
                id="identity.decision",
                status="PASS",
                detail=identity,
                blocking=False,
            )
        )
    else:
        checks.append(
            Check(
                id="identity.decision",
                status="BLOCKED",
                detail="pass --identity KEEP_A2 (recommended) or FORCE_A3",
                blocking=True,
            )
        )

    checks.append(
        Check(
            id="focus.user_approved",
            status="PASS" if user_approved_focus else "BLOCKED",
            detail="--user-approved-focus" if user_approved_focus else "focus window not opened",
            blocking=not user_approved_focus,
        )
    )

    # track validity
    tracks = config["tracks"]
    if active_track not in tracks:
        checks.append(
            Check(
                id="track.valid",
                status="FAIL",
                detail=f"unknown track {active_track}",
                blocking=True,
            )
        )
    else:
        t = tracks[active_track]
        checks.append(
            Check(
                id="track.valid",
                status="PASS",
                detail=f"{active_track} model_call={t['allows_model_call']} eta={t['eta_class']}",
                blocking=False,
            )
        )

    # ban scan
    ban_hits = scan_continuation_for_bans(
        continuation, config["hard_ban_until_x1_moves"]
    )
    if ban_hits and active_track.startswith("T1"):
        checks.append(
            Check(
                id="focus.continuation_ban_signal",
                status="WARN",
                detail=(
                    "recent CONTINUATION head matches ban patterns without F1 motion: "
                    + ", ".join(ban_hits)
                    + " — treat as focus risk, not auto-proof of violation"
                ),
                blocking=False,
            )
        )
    else:
        checks.append(
            Check(
                id="focus.continuation_ban_signal",
                status="PASS",
                detail="no strong ban-without-F1 signal in CONTINUATION head",
                blocking=False,
            )
        )

    if claimed_main:
        banned = set(config["hard_ban_until_x1_moves"])
        if claimed_main in banned:
            checks.append(
                Check(
                    id="focus.claimed_main_banned",
                    status="BLOCKED",
                    detail=f"claimed main {claimed_main} is hard-banned until X1 moves",
                    blocking=True,
                )
            )
        else:
            checks.append(
                Check(
                    id="focus.claimed_main_banned",
                    status="PASS",
                    detail=f"claimed main {claimed_main} not on hard ban list",
                    blocking=False,
                )
            )

    f1_decision = read_f1_decision(f1_report)
    checks.append(
        Check(
            id="f1.report_decision",
            status="PASS" if f1_decision else "WARN",
            detail=f1_decision or "unparsed",
            blocking=False,
        )
    )

    # next actions
    next_actions: list[str] = []
    if not user_approved_focus:
        next_actions.append("Open focus: re-run with --user-approved-focus")
    if identity not in {"KEEP_A2", "FORCE_A3"}:
        next_actions.append("Decide identity: --identity KEEP_A2 (default recommend) or FORCE_A3")
    if active_track == "T0_EXISTENCE_SCOREBOARD_CRYSTALLIZE":
        next_actions.append("Keep EXISTENCE_SCOREBOARD.v1.md as the public partial-existence answer")
        next_actions.append("Then switch --active-track T1_F1_TYPED_FUNCTION_NETWORK for real core win")
    elif active_track == "T1_F1_TYPED_FUNCTION_NETWORK":
        if identity == "KEEP_A2":
            next_actions.append(
                "On Dell: F1_R8_RUNBOOK §0–§3 zero-call with a2 v11 root; no model POST until lock freeze"
            )
            next_actions.append(
                "Run: python3 FINDINGS/hswm-f1-r8-try3-2026-07-28/f1_r8_operator_harness.py status --user-approved"
            )
        elif identity == "FORCE_A3":
            next_actions.append(
                "Owner rebind RUNBOOK/report/run IDs to a3 BEFORE any call (costly; only if you reject A2)"
            )
        next_actions.append("Success = sealed F1 metric line or registered clean INCONCLUSIVE — not Longinus rebind")
    elif active_track == "T2_CORE_RUNTIME_GAP":
        next_actions.append(
            "[BUILD] Only if T1 blocked >7d and user switched; prereg micro-gate; cannot unlock B22"
        )
    elif active_track == "T_ELEVATE_PLAN_REVIEW":
        next_actions.append(
            "[ELEVATE] Write a short plan review: keep T1 / slim F1 / T2 / identity — assume plan imperfect"
        )
        next_actions.append(
            "[ELEVATE] Do not weaken F1 oracles without explicit approval; replan is not silent metric rewrite"
        )

    if active_track == "T1_F1_TYPED_FUNCTION_NETWORK":
        next_actions.append(
            "[ELEVATE] If stuck >7d on rebind-only: switch to T_ELEVATE_PLAN_REVIEW, do not fake progress"
        )

    next_actions.append(
        "Daily (HSWM core 개발): Did BUILD or ELEVATE move X1/core — or only docs/333/Longinus?"
    )

    hard = [c for c in checks if c.blocking and c.status in {"FAIL", "BLOCKED"}]
    t0_ok = scoreboard.is_file()
    t1_unblocked = (
        user_approved_focus
        and identity in {"KEEP_A2", "FORCE_A3"}
        and active_track == "T1_F1_TYPED_FUNCTION_NETWORK"
        and not hard
    )

    focus_state = "FOCUS_OPEN" if user_approved_focus else "FOCUS_CLOSED"
    if hard:
        focus_state = "FOCUS_BLOCKED"

    pillars = config.get("dual_pillars", {})
    receipt = {
        "schema_version": SCHEMA,
        "generated_at": _utc_now(),
        "program_name": config.get("program_name", "HSWM core 개발"),
        "speak_as": config.get("speak_as", "HSWM core 개발"),
        "mode": "CONCENTRATION_DIAGNOSTIC_ONLY",
        "authority": config["authority"],
        "dual_pillars": pillars,
        "strategy_order": config["strategy_order"],
        "focus_window": config["focus_window"],
        "focus_state": focus_state,
        "active_track": active_track,
        "identity_decision": identity,
        "user_approved_focus": user_approved_focus,
        "model_call_allowed_by_this_harness": False,
        "existence_ladder": ladder,
        "primary_gap": {
            "id": "X1_TYPED_LLM_FUNCTION_NETWORK",
            "status": x1["status"],
            "why": "E2E neural glue replacement thesis not scientifically closed",
        },
        "partial_existence_already": [
            x["id"]
            for x in ladder
            if x["status"].startswith("SCIENTIFICALLY_SUPPORTED")
        ],
        "negative_existence_already": [
            x["id"] for x in ladder if x["status"].startswith("KILLED")
        ],
        "hard_ban_until_x1_moves": config["hard_ban_until_x1_moves"],
        "allowed_side_work": config["allowed_side_work"],
        "success_metrics": config["success_metrics_this_focus_window"],
        "f1_report_decision": f1_decision,
        "checks": [asdict(c) for c in checks],
        "next_actions": next_actions,
        "t0_scoreboard_present": t0_ok,
        "t1_human_gates_clear": t1_unblocked,
        "pointers": {k: str(resolve_pointer(v)) for k, v in pointers.items()},
    }
    return receipt


def print_status(r: dict[str, Any]) -> None:
    name = r.get("speak_as") or r.get("program_name") or "HSWM core 개발"
    print(f"=== {name} ===")
    print(f"generated_at: {r['generated_at']}")
    print(f"speak_as: {name}  (폐기된 외부 판정기/333/public 아님)")
    print(f"focus_state: {r['focus_state']}")
    print(f"active_track: {r['active_track']}")
    print(f"identity: {r.get('identity_decision')}")
    print(f"model_call_allowed_by_this_harness: {r['model_call_allowed_by_this_harness']}")
    pillars = r.get("dual_pillars") or {}
    if pillars:
        print()
        print("-- dual pillars (둘 다 core 개발) --")
        a = pillars.get("A_개발_build") or {}
        b = pillars.get("B_고도화_elevate") or {}
        if a:
            print(f"  BUILD:   {a.get('meaning', '')[:100]}")
        if b:
            print(f"  ELEVATE: {b.get('meaning', '')[:100]}")
    print()
    print("-- primary gap --")
    print(f"  {r['primary_gap']['id']}: {r['primary_gap']['status']}")
    print(f"  {r['primary_gap']['why']}")
    print()
    print("-- already real (scoped) --")
    for x in r["partial_existence_already"]:
        print(f"  + {x}")
    print("-- already negative (scoped) --")
    for x in r["negative_existence_already"]:
        print(f"  - {x}")
    print()
    print("-- checks --")
    for c in r["checks"]:
        if c["status"] in {"FAIL", "BLOCKED", "WARN", "INFO"} or c.get("blocking"):
            print(f"  [{c['status']:8}] {c['id']}: {c['detail']}")
    print()
    print("-- next --")
    for a in r["next_actions"]:
        print(f"  → {a}")
    print()
    print("Order: HSWM core 개발 → more core → later 333/p2p/public.")
    print("Plan imperfect → ELEVATE is allowed. F1 runbook/judge still own execution.")


def print_next(r: dict[str, Any]) -> None:
    for i, a in enumerate(r["next_actions"][:5], 1):
        print(f"{i}. {a}")


def print_bans(config: dict[str, Any]) -> None:
    print("HARD BAN until X1 moves (not main work):")
    for b in config["hard_ban_until_x1_moves"]:
        print(f"  ✗ {b}")
    print("ALLOWED side work:")
    for a in config["allowed_side_work"]:
        print(f"  ✓ {a}")


def print_ladder(config: dict[str, Any]) -> None:
    print("| id | status | core |")
    print("|---|---|---|")
    for x in config["existence_ladder"]:
        print(f"| {x['id']} | {x['status']} | {x['core_relevance'][:48]} |")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="HSWM core 개발 harness (build + existence + elevate)"
    )
    p.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "next", "bans", "ladder", "json", "name"],
    )
    p.add_argument("--symposium-root", type=Path, default=None)
    p.add_argument(
        "--active-track",
        default="T1_F1_TYPED_FUNCTION_NETWORK",
        help=(
            "T0_EXISTENCE_SCOREBOARD_CRYSTALLIZE | T1_F1_TYPED_FUNCTION_NETWORK | "
            "T2_CORE_RUNTIME_GAP | T_ELEVATE_PLAN_REVIEW"
        ),
    )
    p.add_argument("--user-approved-focus", action="store_true")
    p.add_argument(
        "--identity",
        choices=["KEEP_A2", "FORCE_A3"],
        default=None,
        help="Required for T1 unblocking; KEEP_A2 recommended",
    )
    p.add_argument(
        "--claimed-main",
        default=None,
        help="If you claim a main work item id from hard_ban list, harness blocks",
    )
    p.add_argument(
        "--allow-model-call-query",
        action="store_true",
        help="Always FORBIDDEN from this harness (exit 2)",
    )
    p.add_argument("--write-receipt", type=Path, default=None)
    args = p.parse_args(argv)

    try:
        root, hswm_root = _resolve_layout(
            args.symposium_root or _find_symposium_root()
        )
        config = load_config(hswm_root)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        return EXIT_CONFIG

    if args.allow_model_call_query:
        print("MODEL_CALL_FORBIDDEN_BY_CONCENTRATION_HARNESS")
        print("Use F1 runbook on Dell only after zero-call gates; this overlay never POSTs.")
        return EXIT_CALL_FORBIDDEN

    if args.command == "name":
        print(config.get("speak_as") or config.get("program_name") or "HSWM core 개발")
        print("pillars: BUILD (개발) + ELEVATE (고도화)")
        print("not: HSWM_LOCAL_RECORD ops, 333 p2p, public service as this program")
        print(
            "entry:",
            config.get("authority", {}).get(
                "canonical_entry",
                "HSWM/docs/research/core-development/HSWM_CORE_DEV.md",
            ),
        )
        return EXIT_OK
    if args.command == "bans":
        print_bans(config)
        return EXIT_OK
    if args.command == "ladder":
        print_ladder(config)
        return EXIT_OK

    receipt = diagnose(
        root,
        config,
        hswm_root=hswm_root,
        active_track=args.active_track,
        user_approved_focus=args.user_approved_focus,
        identity=args.identity,
        claimed_main=args.claimed_main,
    )

    if args.write_receipt:
        args.write_receipt.parent.mkdir(parents=True, exist_ok=True)
        args.write_receipt.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.command == "json":
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
    elif args.command == "next":
        print_next(receipt)
    else:
        print_status(receipt)

    hard = any(
        c["blocking"] and c["status"] in {"FAIL", "BLOCKED"} for c in receipt["checks"]
    )
    if hard:
        return EXIT_FOCUS_BREAK
    if receipt.get("t1_human_gates_clear") and args.active_track.startswith("T1"):
        return EXIT_T1_READYISH
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
