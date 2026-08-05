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
  5. optionally: --git-witness (a SECOND custodian — GitHub — still holds copies
     of this chain that are prefixes of it), cross-model audit upheld, census
     floors / ratchet held

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
             census_baseline: dict | None = None,
             git_witness: bool = False,
             git_repo: str = ".",
             git_path_in_repo: str = "receipts/receipt_log.jsonl",
             git_remote: str | None = "origin") -> Conditions:
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
                  (f"consistent with {detail.get('anchors_seen', 0)} anchor(s), no regression"
                   if detail.get("match") else "local chain contradicts its own anchors"))
            # v3.2 — consistency is necessary, not sufficient. A chain can agree
            # with every anchor it ever published and still have never anchored
            # THE record being judged. The gate asks that separately, because
            # "the chain is coherent" and "this claim was witnessed" are
            # different sentences and only the second one licenses DONE.
            anchored = set(detail.get("anchored_hashes") or [])
            c.add("this record anchored", PASS if latest.get("hash") in anchored else FAIL,
                  (f"seq={latest.get('seq')} hash={str(latest.get('hash'))[:12]}… is anchored"
                   if latest.get("hash") in anchored else
                   f"seq={latest.get('seq')} was never anchored ({len(anchored)} other anchor(s) "
                   f"exist) — run run_receipt --anchor-tree/--anchor-node --require-anchor"))

    # --- v3.3: the SECOND witness, opt-in on purpose -------------------------
    #
    # git/GitHub holds copies of this chain at past lengths, in a trust domain
    # the author does not control. ooptdd.witness_git checks each published copy
    # is still a PREFIX of the live chain. It is off by default and that is a
    # decision with a stated reason, not laziness:
    #
    #   1. It structurally CANNOT witness the record being judged. run_receipt
    #      appends to the working file; commits happen later and pushes later
    #      still. The newest records are always uncommitted, so a git witness
    #      that gated every receipt would gate on a claim it cannot make.
    #      Condition 5 ("this record anchored") already covers that question,
    #      and only LakatoTree can answer it.
    #   2. It requires the network, and UNVERIFIABLE is a failure here. Turning
    #      it on by default means no offline run can ever reach DONE — a real
    #      cost, paid for a witness that by (1) is about the past, not the claim.
    #
    # So it is `--git-witness`, and what it buys is worth stating exactly: it
    # detects a rewritten or truncated PAST that both verify() and the
    # LakatoTree anchor could miss if the tree were unavailable or complicit.
    # Two witnesses is two, not a quorum; a disagreement is reported, not voted on.
    if git_witness:
        from ooptdd.witness_git import gate_condition as _git_witness_condition
        wstatus, wdetail = _git_witness_condition(log_path, git_path_in_repo, git_repo,
                                                  remote=git_remote)
        c.add("git witness (2nd domain)", wstatus, wdetail)

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
    ap.add_argument("--git-witness", action="store_true",
                    help="also require the git/GitHub copies of the chain to still be prefixes "
                         "of it (second trust domain). Needs the network: offline this is "
                         "UNVERIFIABLE and therefore NOT DONE — that is the price, stated up front")
    ap.add_argument("--git-repo", default=".")
    ap.add_argument("--git-path-in-repo", default="receipts/receipt_log.jsonl")
    ap.add_argument("--git-remote", default="origin")
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
                 census_floors=floors or None, census_baseline=baseline,
                 git_witness=args.git_witness, git_repo=args.git_repo,
                 git_path_in_repo=args.git_path_in_repo, git_remote=args.git_remote)
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
