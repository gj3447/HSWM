"""ooptdd v3.0 — the DONE gate. One decision, and it cannot be reached alone.

Every anchor this system has to the world outside its own claims was, until
now, a command you could choose not to run:

  - `fire_drill anchor-check` is a separate CLI nobody's exit code depended on;
  - `run_receipt --anchor-tree` is opt-in, and on failure printed
    "anchor: FAILED (receipt verdict unaffected)" and returned the receipt's
    own exit code;
  - R2 auditor rotation is advisory by design;
  - R1/R3 degrade to `unverifiable` and chain anyway.

Each of those is individually defensible. Together they mean a receipt could
go green having touched nothing outside the process that authored it. That is
the ouroboros: not that the system verifies itself — every verifier does, and
must — but that the links pinning the loop to something external were all
optional. A bootstrap is safe exactly when one link is nailed down from
outside, and a nail you can decline to hammer is not a nail.

So this gate exists, and it is fail-closed on the outside world:

  1. chain verifies under STRICT repairs (unsigned skiplist entries do not
     absolve anything here, whatever the default rules allow)
  2. the battery in ooptdd.attacks finds no `local` miss, control intact
  3. the latest receipt record is VALID with lock_binding=verified
  4. the LakatoTree anchor MATCHES, and the local seq has not regressed below
     the anchored high-water mark (the truncation detector)
  5. optionally: cross-model audit upheld, census floors / ratchet held

An unreachable tree is NOT a pass. `--allow-unanchored` exists so you can see
the other four conditions while the tree is down, but it can never return 0 —
the whole point is that "I could not check with the outside" and "the outside
agreed" must not share an exit code.

  python -m ooptdd.gate receipts/receipt_cosine_floor.py \
      --tree LakatosTree_HSWM_20260719 --node d1-ooptdd-floor-scope-correction

Exit: 0 DONE, 1 NOT DONE, 2 could not run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ooptdd.attacks import LOCAL
from ooptdd.audit import audited_status
from ooptdd.census import census, check as census_check
from ooptdd.fire_drill import anchor_check, drill
from ooptdd.receipt_log import (
    load,
    load_repairs,
    registry_pubkeys_for,
    repairs_path_for,
    verify,
)

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")
DEFAULT_LAKATOS_URL = "http://127.0.0.1:55170"

PASS, FAIL, UNVERIFIABLE = "PASS", "FAIL", "UNVERIFIABLE"


class Conditions:
    """Accumulates gate conditions. UNVERIFIABLE is a failure, deliberately."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, name: str, status: str, detail: str) -> None:
        self.items.append({"condition": name, "status": status, "detail": detail})

    @property
    def done(self) -> bool:
        return all(i["status"] == PASS for i in self.items)

    def render(self) -> str:
        mark = {PASS: "✅", FAIL: "❌", UNVERIFIABLE: "⚠️ "}
        return "\n".join(f"  {mark[i['status']]} {i['condition']:<26} {i['detail']}"
                         for i in self.items)


def evaluate(receipt_id: str, log_path: str, tree: str | None, node: str | None,
             base_url: str, allow_unanchored: bool = False,
             require_audit: bool = False,
             census_floors: dict | None = None,
             census_baseline: dict | None = None) -> Conditions:
    c = Conditions()

    ok, errors = verify(log_path, strict_repairs=True)
    c.add("chain (strict repairs)", PASS if ok else FAIL,
          "verifies" if ok else f"{len(errors)} error(s): {errors[0][:90]}")

    code, summary = drill(log_path, strict_repairs=True, verbose=False)
    if not summary:
        c.add("tamper battery", UNVERIFIABLE, "battery could not run (empty chain)")
    else:
        missed = [r["attack"] for r in summary["results"]
                  if r["class"] == LOCAL and r["outcome"] == "MISSED"]
        c.add("tamper battery", PASS if (code == 0 and summary["control_ok"]) else FAIL,
              f"{summary['attacks']} attacks, battery {summary['battery'][:12]}…"
              + (f", MISSED {missed}" if missed else "")
              + (", control BROKEN" if not summary["control_ok"] else ""))

    records = load(log_path)
    receipts = [r for r in records if r.get("receipt_id") == receipt_id and r.get("kind") == "receipt"]
    if not receipts:
        c.add("receipt record", FAIL, f"no receipt record for {receipt_id}")
        return c
    latest = receipts[-1]
    c.add("verdict", PASS if latest.get("verdict") == "VALID" else FAIL,
          f"{latest.get('verdict')} at seq={latest.get('seq')}")
    binding = latest.get("lock_binding", "absent")
    c.add("lock binding", PASS if binding == "verified" else FAIL,
          f"{binding} — prose is {'bound to verdict-gating code' if binding == 'verified' else 'not machine-bound'}")

    # --- the external link ---------------------------------------------------
    if not (tree and node):
        c.add("external anchor", UNVERIFIABLE,
              "no --tree/--node given; nothing outside this process was consulted")
    else:
        acode, detail = anchor_check(tree, node, receipt_id, log_path, base_url)
        if acode == 2:
            c.add("external anchor", UNVERIFIABLE,
                  f"anchor unreachable or absent: {detail.get('error', 'no anchors')}")
        elif detail.get("truncation_detected"):
            c.add("external anchor", FAIL,
                  f"TRUNCATION: local seq {detail['local_seq']} < anchored high-water "
                  f"{detail['anchored_high_water']}")
        elif detail.get("broken_anchor_links"):
            c.add("external anchor", FAIL,
                  f"ANCHOR LINK BROKEN at {detail['broken_anchor_links']} — an anchor names a "
                  f"predecessor it does not extend")
        elif detail.get("prefix_inconsistent"):
            c.add("external anchor", FAIL,
                  f"PREFIX INCONSISTENT at {detail['prefix_inconsistent']} — head matches but "
                  f"earlier anchors do not; the tail was rehashed")
        else:
            c.add("external anchor", PASS if detail.get("match") else FAIL,
                  ("head matches tree anchor" if detail.get("match")
                   else "head does NOT match the tree anchor"))

    if require_audit:
        status = audited_status(log_path, receipt_id)
        c.add("cross-model audit", PASS if status == "audited" else FAIL,
              f"{status} (author == auditor makes VALID meaningless — P1)")

    if census_floors or census_baseline:
        repairs = load_repairs(repairs_path_for(log_path), registry_pubkeys_for(log_path))
        cen = census(records, repairs)
        cok, problems = census_check(cen, census_floors, census_baseline)
        c.add("census", PASS if cok else FAIL,
              "within floors / no regression" if cok else f"{len(problems)} breach(es): {problems[0][:80]}")

    if allow_unanchored:
        for item in c.items:
            if item["condition"] == "external anchor" and item["status"] == UNVERIFIABLE:
                item["detail"] += "  [--allow-unanchored: reported, still not DONE]"
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description="ooptdd DONE gate (anchor is a condition, not a command)")
    ap.add_argument("receipt", help="receipt path or receipt_id")
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--tree", default=None, help="LakatoTree tree holding the chain-head anchor")
    ap.add_argument("--node", default=None, help="LakatoTree node tag")
    ap.add_argument("--url", default=DEFAULT_LAKATOS_URL)
    ap.add_argument("--allow-unanchored", action="store_true",
                    help="report the other conditions with the tree down; can never exit 0")
    ap.add_argument("--require-audit", action="store_true", help="also require an upheld cross-model audit")
    ap.add_argument("--ratchet", default=None, help="previous census json; coverage may not decrease")
    ap.add_argument("--min-coverage", action="append", default=[], metavar="DIM=RATIO")
    ap.add_argument("--json", default=None, help="write the gate decision to this path")
    args = ap.parse_args()

    receipt_id = os.path.splitext(os.path.basename(args.receipt))[0]
    if not os.path.exists(args.log):
        print(f"{args.log}: no chain", file=sys.stderr)
        return 2

    floors = {}
    for spec in args.min_coverage:
        dim, _, ratio = spec.partition("=")
        try:
            floors[dim] = float(ratio)
        except ValueError:
            print(f"bad --min-coverage {spec!r}", file=sys.stderr)
            return 2
    baseline = None
    if args.ratchet:
        if not os.path.exists(args.ratchet):
            print(f"ratchet baseline {args.ratchet} not found", file=sys.stderr)
            return 2
        with open(args.ratchet, "r", encoding="utf-8") as f:
            baseline = json.load(f)

    print(f"\n=== ooptdd gate: {receipt_id} ===")
    c = evaluate(receipt_id, args.log, args.tree, args.node, args.url,
                 allow_unanchored=args.allow_unanchored, require_audit=args.require_audit,
                 census_floors=floors or None, census_baseline=baseline)
    print(c.render())
    done = c.done
    print(f"\nVERDICT: {'DONE ✅' if done else 'NOT DONE ❌'}")
    if not done:
        unver = [i["condition"] for i in c.items if i["status"] == UNVERIFIABLE]
        if unver:
            print(f"  unverifiable conditions count as failures: {unver}\n"
                  f"  'I could not check' is not 'it checked out'.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"receipt_id": receipt_id, "done": done, "conditions": c.items}, f,
                      ensure_ascii=False, indent=1)
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
