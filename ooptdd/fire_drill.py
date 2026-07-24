"""ooptdd v2.5 — integrity fire drill (Q5).

Two integrity claims, each with a drill that must prove it:

  drill       — LOCAL tamper-evidence: copy the chain, flip a past verdict,
                delete a record; verify() MUST detect both. If a drill pass
                fails, the chain is decorative.
  anchor-check — CROSS-MACHINE evidence: the chain head hash must equal the
                newest LakatoTree anchor for this receipt. A tampered or
                rebuilt chain yields a different head -> MISMATCH.

  .venv/bin/python -m ooptdd.fire_drill drill --log receipts/receipt_log.jsonl
  .venv/bin/python -m ooptdd.fire_drill anchor-check \
      --tree LakatosTree_HSWM_20260719 --node d1-ooptdd-floor-scope-correction \
      --receipt-id receipt_cosine_floor
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.request

from ooptdd.receipt_log import load, verify

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")
DEFAULT_LAKATOS_URL = "http://127.0.0.1:55170"


def drill(log_path: str) -> int:
    records = load(log_path)
    if not records:
        print("empty chain — nothing to drill", file=sys.stderr)
        return 2
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        # drill 1: flip a past verdict -> must be detected
        p1 = os.path.join(td, "tampered_verdict.jsonl")
        tampered = [dict(r) for r in records]
        tampered[0]["verdict"] = "INVALID" if tampered[0]["verdict"] == "VALID" else "VALID"
        with open(p1, "w", encoding="utf-8") as f:
            for r in tampered:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        ok1, errs1 = verify(p1)
        print(f"drill verdict-tamper: {'DETECTED' if not ok1 else 'MISSED — chain decorative!'} {errs1[:1]}")
        failures += 0 if not ok1 else 1

        # drill 2: delete a middle record -> must be detected
        if len(records) >= 3:
            p2 = os.path.join(td, "deleted.jsonl")
            deleted = records[: len(records) // 2] + records[len(records) // 2 + 1:]
            with open(p2, "w", encoding="utf-8") as f:
                for r in deleted:
                    f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            ok2, errs2 = verify(p2)
            print(f"drill deletion:       {'DETECTED' if not ok2 else 'MISSED — chain decorative!'} {errs2[:1]}")
            failures += 0 if not ok2 else 1

        # control: untouched copy MUST verify (a drill that fires on everything is vacuous)
        p3 = os.path.join(td, "control.jsonl")
        shutil.copyfile(log_path, p3)
        ok3, _ = verify(p3)
        print(f"control (untouched):  {'OK — verifies' if ok3 else 'BROKEN — drill vacuous!'}")
        failures += 0 if ok3 else 1
    return 1 if failures else 0


def anchor_check(tree: str, node: str, receipt_id: str, log_path: str,
                 base_url: str = DEFAULT_LAKATOS_URL) -> int:
    records = load(log_path)
    mine = [r for r in records if r.get("receipt_id") == receipt_id]
    if not mine:
        print(f"no local records for {receipt_id}", file=sys.stderr)
        return 2
    head = mine[-1]["hash"]
    token = os.environ.get("LAKATOS_API_TOKEN", "")
    req = urllib.request.Request(
        f"{base_url}/api/tree/{tree}/node/{node}/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            events = json.loads(r.read().decode())
    except Exception as e:
        print(f"anchor fetch failed: {e}", file=sys.stderr)
        return 2
    anchors = []
    for ev in events if isinstance(events, list) else events.get("events", []):
        payload = ev.get("payload", {})
        if isinstance(payload, dict) and payload.get("receipt_id") == receipt_id:
            anchors.append(payload)
    if not anchors:
        print(f"no anchors for {receipt_id} on {tree}/{node}", file=sys.stderr)
        return 2
    latest = anchors[-1]
    match = latest.get("hash") == head
    print(f"local head:  {head[:16]}… (seq {mine[-1]['seq']})")
    print(f"tree anchor: {str(latest.get('hash'))[:16]}… (seq {latest.get('seq')})")
    print("ANCHOR:", "MATCH ✅" if match else "MISMATCH ❌ — chain tampered, rebuilt, or tree behind")
    return 0 if match else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="integrity fire drill")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("drill")
    d.add_argument("--log", default=DEFAULT_LOG)
    a = sub.add_parser("anchor-check")
    a.add_argument("--tree", required=True)
    a.add_argument("--node", required=True)
    a.add_argument("--receipt-id", required=True)
    a.add_argument("--log", default=DEFAULT_LOG)
    a.add_argument("--url", default=DEFAULT_LAKATOS_URL)
    args = ap.parse_args()
    if args.cmd == "drill":
        return drill(args.log)
    return anchor_check(args.tree, args.node, args.receipt_id, args.log, args.url)


if __name__ == "__main__":
    sys.exit(main())
