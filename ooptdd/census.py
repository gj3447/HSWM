"""ooptdd v3.0 — integrity census: count what the chain admits it cannot check.

The repo's best design decision is progressive enforcement — what the machine
can see it enforces, what it cannot it labels `unverifiable` and chains anyway
(audit_policy R1/R3, lock_binding="absent", harvest's lock_binding="harvested").
Everyone else would have written "verified".

The failure mode of that decision is drift. Honest labels are only honest while
someone reads them; a chain that is 60% "unverifiable" is decoration with
accurate captions, and no single record ever looks wrong. This module reads
them, on every dimension, and produces a number.

Two ways to hold the line, and the choice matters:

  --min-coverage DIM=RATIO   an explicit floor. Use where a floor is a real
                             policy decision, not a guess.
  --ratchet PREV.json        no floor at all: coverage may not go DOWN versus
                             a previous census. This is the default posture on
                             purpose. Inventing a target invites optimising for
                             the target; forbidding regression only forbids
                             getting worse, which is the actual failure mode.

  python -m ooptdd.census --log receipts/receipt_log.jsonl
  python -m ooptdd.census --json receipts/census_20260805.json
  python -m ooptdd.census --ratchet receipts/census_20260804.json
  python -m ooptdd.census --min-coverage lock_binding=0.5 --min-coverage author_id=0.9

Exit: 0 within policy, 1 a floor or the ratchet was breached, 2 nothing to count.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ooptdd.receipt_log import (
    load,
    load_repairs,
    registry_pubkeys_for,
    repairs_path_for,
)

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")

# dimension -> (applies_to, grade_fn, grades_that_count_as_covered)
# "covered" means a machine actually checked it. Everything else is a label.
DIMENSIONS: dict[str, tuple] = {}


def _dim(name: str, applies, grade, covered: tuple[str, ...]):
    DIMENSIONS[name] = (applies, grade, covered)


def _is_receipt(r: dict) -> bool:
    return r.get("kind") == "receipt"


def _is_audit(r: dict) -> bool:
    return r.get("kind") == "audit"


_dim("lock_binding", _is_receipt,
     lambda r: r.get("lock_binding") or "absent",
     ("verified",))
_dim("author_id", _is_receipt,
     lambda r: "present" if r.get("author_id") else "absent",
     ("present",))
_dim("mutation_score", _is_receipt,
     lambda r: "present" if r.get("mutation_score") else "absent",
     ("present",))
_dim("measured", _is_receipt,
     lambda r: "present" if r.get("measured") else "absent",
     ("present",))
_dim("xlocks", _is_receipt,
     lambda r: "present" if r.get("xlocks") else "absent",
     ("present",))
_dim("no_self_audit", _is_audit,
     lambda r: (r.get("policy") or {}).get("no_self_audit") or "absent",
     ("enforced",))
_dim("budget_check", _is_audit,
     lambda r: (r.get("policy") or {}).get("budget_check") or "absent",
     ("enforced",))
_dim("audit_signature", _is_audit,
     lambda r: (r.get("policy") or {}).get("signature") or "absent",
     ("verified",))
# Not a policy label but a structural exposure: a signature with no
# signer_pubkey in the hashed body can be stripped invisibly (see
# ooptdd.attacks signature_strip_legacy). Counted so the debt has a size.
_dim("signer_commitment", lambda r: isinstance(r.get("signature"), dict),
     lambda r: ("committed" if r.get("signer_pubkey")
                else ("resign_attested" if r.get("__resign_attested") else "strip_exposed")),
     ("committed", "resign_attested"))


# 앵커는 지금까지 census 에 없었다 — 그래서 kind='anchor' 레코드가 **0건**이라는
# 사실이 어떤 표에도 안 나왔다. gate 는 앵커를 요구하는데 아무도 앵커한 적이 없으면
# 그 게이트는 영구 거절기이고, 그 상태가 보이지 않으면 요구는 장식이다.
_dim("anchored", _is_receipt,
     lambda r: "anchored" if r.get("__anchored") else "never_anchored",
     ("anchored",))


def anchored_record_hashes(records: list[dict]) -> set[str]:
    """kind='anchor' 레코드가 성공적으로 앵커했다고 기록한 대상 레코드 해시."""
    return {a["target_hash"] for a in records
            if a.get("kind") == "anchor" and a.get("verdict") == "VALID" and a.get("target_hash")}


def resign_attested_hashes(records: list[dict]) -> set[str]:
    """Record hashes a later `resign` record vouches for (v3.1).

    Counted as covered, but the grade is deliberately its own name rather than
    `committed`: a resign attestation lives in a LATER record, so truncating the
    tail removes it. The exposure moves from legacy_blind to anchor_only, and the
    census should not let that read as fully closed.
    """
    out: set[str] = set()
    for rec in records:
        if rec.get("kind") != "resign":
            continue
        for a in rec.get("attests") or []:
            if isinstance(a, dict) and a.get("target_hash"):
                out.add(a["target_hash"])
    return out


def census(records: list[dict], repairs: dict | None = None) -> dict:
    """Grade every record on every applicable dimension. Pure; no I/O."""
    vouched = resign_attested_hashes(records)
    anchored = anchored_record_hashes(records)
    records = [dict(r,
                    __resign_attested=r.get("hash") in vouched,
                    __anchored=r.get("hash") in anchored)
               for r in records]
    out: dict = {"records": len(records),
                 "receipts": sum(1 for r in records if _is_receipt(r)),
                 "audits": sum(1 for r in records if _is_audit(r)),
                 "dimensions": {}}
    for name, (applies, grade, covered) in DIMENSIONS.items():
        subset = [r for r in records if applies(r)]
        counts: dict[str, int] = {}
        for r in subset:
            g = grade(r)
            counts[g] = counts.get(g, 0) + 1
        n = len(subset)
        n_covered = sum(v for k, v in counts.items() if k in covered)
        out["dimensions"][name] = {
            "applicable": n,
            "counts": dict(sorted(counts.items())),
            "covered": n_covered,
            # No applicable records means no coverage claim, not perfect
            # coverage. 1.0 here would let an empty dimension read as green.
            "coverage": (n_covered / n) if n else None,
        }

    repairs = repairs or {}
    grades: dict[str, int] = {}
    for e in repairs.values():
        t = e.get("trust", "invalid")
        grades[t] = grades.get(t, 0) + 1
    n_rep = len(repairs)
    out["repairs"] = {
        "entries": n_rep,
        "counts": dict(sorted(grades.items())),
        "covered": grades.get("signed", 0),
        "coverage": (grades.get("signed", 0) / n_rep) if n_rep else None,
        # Entries that suppress a real mismatch today but would not survive
        # strict mode — the size of the indulgence, in records.
        "honoured_unsigned": grades.get("unsigned", 0) + grades.get("untrusted", 0),
    }
    return out


def _coverages(c: dict) -> dict[str, float]:
    cov = {k: v["coverage"] for k, v in c["dimensions"].items() if v["coverage"] is not None}
    if c["repairs"]["coverage"] is not None:
        cov["repairs"] = c["repairs"]["coverage"]
    return cov


def check(c: dict, floors: dict[str, float] | None = None,
          previous: dict | None = None) -> tuple[bool, list[str]]:
    """Apply explicit floors and/or the no-regression ratchet."""
    problems: list[str] = []
    cov = _coverages(c)
    for dim, floor in (floors or {}).items():
        if dim not in cov:
            problems.append(f"{dim}: no applicable records — a floor cannot be met vacuously")
        elif cov[dim] < floor:
            problems.append(f"{dim}: coverage {cov[dim]:.1%} below floor {floor:.1%}")
    if previous is not None:
        prev_cov = _coverages(previous)
        for dim, now in cov.items():
            before = prev_cov.get(dim)
            if before is not None and now < before - 1e-9:
                problems.append(f"{dim}: coverage regressed {before:.1%} -> {now:.1%} (ratchet)")
        for dim in prev_cov:
            if dim not in cov:
                problems.append(f"{dim}: dimension disappeared since the previous census")
    return (not problems), problems


def render(c: dict) -> str:
    lines = [f"chain: {c['records']} records ({c['receipts']} receipts, {c['audits']} audits)", ""]
    lines.append(f"{'dimension':<20} {'covered':>12}  {'coverage':>9}  grades")
    for name, d in c["dimensions"].items():
        cov = "n/a" if d["coverage"] is None else f"{d['coverage']:.1%}"
        grades = ", ".join(f"{k}={v}" for k, v in d["counts"].items()) or "—"
        lines.append(f"{name:<20} {d['covered']:>5}/{d['applicable']:<6} {cov:>9}  {grades}")
    r = c["repairs"]
    cov = "n/a" if r["coverage"] is None else f"{r['coverage']:.1%}"
    grades = ", ".join(f"{k}={v}" for k, v in r["counts"].items()) or "—"
    lines.append(f"{'repairs':<20} {r['covered']:>5}/{r['entries']:<6} {cov:>9}  {grades}")
    if r["honoured_unsigned"]:
        lines.append(f"\n  {r['honoured_unsigned']} repair entr(y/ies) honoured on trust alone — "
                     f"they suppress nothing under --strict-repairs, but under default rules "
                     f"an unsigned entry is an unauthenticated override of verify().")
    exposed = c["dimensions"].get("signer_commitment", {}).get("counts", {}).get("strip_exposed", 0)
    if exposed:
        lines.append(f"  {exposed} signed record(s) carry no signer_pubkey — their signatures can be "
                     f"stripped with no digest change and no anchor mismatch (legacy_blind).")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="ooptdd integrity census")
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--json", default=None, help="write the census to this path")
    ap.add_argument("--ratchet", default=None, help="previous census json; coverage may not decrease")
    ap.add_argument("--min-coverage", action="append", default=[], metavar="DIM=RATIO",
                    help="explicit floor, repeatable (e.g. lock_binding=0.5)")
    args = ap.parse_args()

    records = load(args.log)
    if not records:
        print(f"{args.log}: empty chain — nothing to count", file=sys.stderr)
        return 2
    repairs = load_repairs(repairs_path_for(args.log), registry_pubkeys_for(args.log))
    c = census(records, repairs)

    floors = {}
    for spec in args.min_coverage:
        dim, _, ratio = spec.partition("=")
        try:
            floors[dim] = float(ratio)
        except ValueError:
            print(f"bad --min-coverage {spec!r} (expected DIM=RATIO)", file=sys.stderr)
            return 2

    previous = None
    if args.ratchet:
        if not os.path.exists(args.ratchet):
            print(f"ratchet baseline {args.ratchet} not found", file=sys.stderr)
            return 2
        with open(args.ratchet, "r", encoding="utf-8") as f:
            previous = json.load(f)

    print(render(c))
    ok, problems = check(c, floors, previous)
    if problems:
        print("\nPOLICY:")
        for p in problems:
            print(f"  ✗ {p}")
    elif floors or previous:
        print("\nPOLICY: within floors / no regression ✅")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=1)
        print(f"\ncensus -> {args.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
