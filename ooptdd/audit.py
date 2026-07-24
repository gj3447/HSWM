"""ooptdd v2.5 — cross-model audit harness (Q4, activates the `audited` tier).

P1 said: author == auditor makes VALID meaningless. The audit workflow:

  1. PREPARE (author side): export an audit bundle — the receipt source, its
     LOCK, and the shas — for a reviewer that has NOT seen the claim context:
       .venv/bin/python -m ooptdd.audit prepare receipts/receipt_cosine_floor.py \
           --source learned_v3_additive.py --out audit_bundle.json
  2. REVIEW (auditor side, different model family/session): the auditor gets
     the bundle and tries to BREAK the lock (counterexample, vacuity proof,
     or "no break found within budget N").
  3. RECORD (either side): chain the outcome as kind=audit linked to the
     target receipt record:
       .venv/bin/python -m ooptdd.audit record receipts/receipt_cosine_floor.py \
           --auditor-id claude-opus-4.5 --verdict upheld --budget "12 mutants, 30min" \
           --notes "no break found"

audited_status(log, receipt_id) promotes only when the latest audit is
`upheld` AND no receipt record with a different receipt_sha came after it
(an edit reverts audited -> self-valid: re-audit required).

v2.6: record() delegates to ooptdd.audit_policy.record_audit — R1 no-self-audit
and R3 calibrated-budget enforcement live there; --mutants/--counterexamples/
--minutes give the budget a machine-checkable shape (free text still chains,
flagged policy.budget_check="unverifiable").
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ooptdd.audit_policy import record_audit
from ooptdd.receipt_log import canonical, file_sha, load, sha256_hex
from ooptdd.run_receipt import extract_lock

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")


def prepare(receipt_path: str, sources: list[str], out_path: str) -> dict:
    lock = extract_lock(receipt_path)
    bundle = {
        "receipt_id": os.path.splitext(os.path.basename(receipt_path))[0],
        "receipt_sha": file_sha(receipt_path),
        "receipt_source": open(receipt_path, "r", encoding="utf-8").read(),
        "lock": lock,
        "lock_sha": sha256_hex(canonical(lock)),
        "source_shas": {s: file_sha(s) for s in sources},
        "auditor_instructions": (
            "You have NOT seen the claim context. Try to BREAK the LOCK: find an "
            "input where the locked statement is false, or prove a check vacuous "
            "(cannot fail). Record budget spent. Answer: upheld | broken, with "
            "counterexample when broken."
        ),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=1, ensure_ascii=False)
    return bundle


def record(receipt_path: str, log_path: str, auditor_id: str, verdict: str,
           notes: str, budget) -> dict:
    """Chain an audit record via the enforced policy path (R1/R3, v2.6).

    `budget` is free text (unverifiable, flagged) or a structured dict
    {mutants, counterexamples, wall_clock_min} (enforced against the
    calibrated minimum for `upheld` verdicts)."""
    return record_audit(receipt_path, log_path, auditor_id, verdict, notes, budget)


def audited_status(log_path: str, receipt_id: str) -> str:
    """draft -> self-valid -> audited; an edit after the audit reverts it."""
    records = load(log_path)
    receipt_recs = [r for r in records if r.get("receipt_id") == receipt_id and r.get("kind") == "receipt"]
    if not receipt_recs:
        return "draft"
    latest = receipt_recs[-1]
    audits = [r for r in records if r.get("receipt_id") == receipt_id and r.get("kind") == "audit"
              and r.get("target_hash") == latest["hash"]]
    if audits and audits[-1].get("audit_verdict") == "upheld":
        return "audited"
    return "self-valid"


def main() -> int:
    ap = argparse.ArgumentParser(description="cross-model audit harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("receipt")
    p.add_argument("--source", action="append", default=[])
    p.add_argument("--out", required=True)
    r = sub.add_parser("record")
    r.add_argument("receipt")
    r.add_argument("--log", default=DEFAULT_LOG)
    r.add_argument("--auditor-id", required=True)
    r.add_argument("--verdict", required=True, choices=["upheld", "broken"])
    r.add_argument("--budget", default="")
    r.add_argument("--mutants", type=int, default=None)
    r.add_argument("--counterexamples", type=int, default=None)
    r.add_argument("--minutes", type=int, default=None, dest="wall_clock_min")
    r.add_argument("--notes", default="")
    s = sub.add_parser("status")
    s.add_argument("receipt")
    s.add_argument("--log", default=DEFAULT_LOG)
    args = ap.parse_args()

    if args.cmd == "prepare":
        bundle = prepare(args.receipt, args.source, args.out)
        print(f"audit bundle -> {args.out} (receipt_sha={bundle['receipt_sha'][:12]}, "
              f"lock_sha={bundle['lock_sha'][:12]})")
    elif args.cmd == "record":
        structured = {k: v for k, v in (("mutants", args.mutants),
                                        ("counterexamples", args.counterexamples),
                                        ("wall_clock_min", args.wall_clock_min)) if v is not None}
        budget = structured if structured else args.budget
        try:
            rec = record(args.receipt, args.log, args.auditor_id, args.verdict, args.notes, budget)
        except ValueError as e:
            print(f"audit refused: {e}", file=sys.stderr)
            return 2
        rid = os.path.splitext(os.path.basename(args.receipt))[0]
        print(f"audit chained: seq={rec['seq']} verdict={rec['audit_verdict']} "
              f"policy={json.dumps(rec['policy'], ensure_ascii=False)} "
              f"status={audited_status(args.log, rid)}")
    else:
        rid = os.path.splitext(os.path.basename(args.receipt))[0]
        print(audited_status(args.log, rid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
