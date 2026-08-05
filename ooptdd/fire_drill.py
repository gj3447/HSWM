"""ooptdd v3.0 — integrity fire drill (Q5).

Two integrity claims, each with a drill that must prove it:

  drill        — LOCAL tamper-evidence. v2.5 tried two hand-picked faults;
                 v3.0 runs the machine-generated battery in ooptdd.attacks and
                 checks every result against a DECLARED detectability class.
                 A `local` fault that slips through fails the drill: the chain
                 is decorative for that class. An `anchor_only` fault that
                 slips through is expected — and is reported loudly, because
                 that is precisely the hole the anchor exists to fill.
  anchor-check — CROSS-MACHINE evidence: the chain head hash must equal the
                 newest LakatoTree anchor for this receipt, and the local seq
                 must not have gone BACKWARDS relative to it. The seq check is
                 the truncation detector: a chain missing its tail verifies
                 perfectly on its own and only an external memory can object.

  .venv/bin/python -m ooptdd.fire_drill drill --log receipts/receipt_log.jsonl
  .venv/bin/python -m ooptdd.fire_drill drill --strict-repairs
  .venv/bin/python -m ooptdd.fire_drill anchor-check \
      --tree LakatosTree_HSWM_20260719 --node d1-ooptdd-floor-scope-correction \
      --receipt-id receipt_cosine_floor

Exit codes: 0 clean, 1 a claim failed, 2 could not run (empty chain, no anchor).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.request

from ooptdd.attacks import ANCHOR_ONLY, ATTACKS, LOCAL, LOCAL_STRICT, Skip, battery_fingerprint, materialize
from ooptdd.receipt_log import load, repairs_path_for, verify

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")
DEFAULT_LAKATOS_URL = "http://127.0.0.1:55170"


def _load_repairs_file(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def drill(log_path: str, strict_repairs: bool = False, verbose: bool = True) -> tuple[int, dict]:
    """Run the whole battery. Returns (exit_code, summary) for chaining."""
    def out(*a, **kw):
        if verbose:
            print(*a, **kw)

    records = load(log_path)
    if not records:
        print("empty chain — nothing to drill", file=sys.stderr)
        return 2, {}
    repairs_src = repairs_path_for(log_path)
    repairs_file = _load_repairs_file(repairs_src)

    results: list[dict] = []
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        # Control first: a battery whose control case fails is measuring nothing.
        control = os.path.join(td, "00_control.jsonl")
        shutil.copyfile(log_path, control)
        if os.path.exists(repairs_src):
            shutil.copyfile(repairs_src, repairs_path_for(control))
        control_ok, control_errs = verify(control, strict_repairs=strict_repairs)
        out(f"control (untouched): {'OK — verifies' if control_ok else 'BROKEN — battery vacuous!'}"
            + ("" if control_ok else f" {control_errs[:2]}"))
        if not control_ok:
            failures += 1

        for i, attack in enumerate(ATTACKS, start=1):
            try:
                path = materialize(attack, records, repairs_file, td, i)
            except Skip as e:
                results.append({"attack": attack.name, "class": attack.detectability,
                                "outcome": "SKIPPED", "why": str(e)})
                out(f"  {attack.name:<32} {attack.detectability:<12} SKIPPED ({e})")
                continue
            ok, errs = verify(path, strict_repairs=strict_repairs)
            detected = not ok

            if attack.detectability == LOCAL:
                outcome = "DETECTED" if detected else "MISSED"
                bad = not detected
            elif attack.detectability == LOCAL_STRICT:
                if strict_repairs:
                    outcome = "DETECTED" if detected else "MISSED"
                    bad = not detected
                else:
                    # Permissive mode is the documented v2.8 behaviour; a miss
                    # here is the known indulgence, not a surprise.
                    outcome = "DETECTED" if detected else "WHITEWASHED (permissive repairs)"
                    bad = False
            elif attack.detectability == ANCHOR_ONLY:
                outcome = "DETECTED (stronger than claimed)" if detected else "INVISIBLE — anchor required"
                bad = False
            else:  # LEGACY_BLIND
                # Detected here means a `resign` record vouches for the signature.
                # That is a relocation, not a retirement: the attestation lives in a
                # LATER record, so truncating it away makes the strip invisible again.
                # The class the exposure moves to is anchor_only.
                outcome = ("DETECTED via resign attestation (now anchor_only, not closed)"
                           if detected else "BLIND — no verifier, no anchor; resign to relocate")
                bad = False

            failures += 1 if bad else 0
            results.append({"attack": attack.name, "class": attack.detectability,
                            "outcome": outcome, "first_error": errs[0] if errs else None})
            mark = "!!" if bad else "  "
            out(f"{mark}{attack.name:<32} {attack.detectability:<12} {outcome}"
                + (f"  [{errs[0][:70]}]" if errs else ""))

    counts = {k: sum(1 for r in results if r["outcome"].startswith(k)) for k in ("DETECTED", "MISSED", "SKIPPED")}
    invisible = [r["attack"] for r in results if r["outcome"].startswith("INVISIBLE")]
    whitewashed = [r["attack"] for r in results if r["outcome"].startswith("WHITEWASHED")]
    blind = [r["attack"] for r in results if r["outcome"].startswith("BLIND")]
    summary = {
        "battery": battery_fingerprint(),
        "attacks": len(ATTACKS),
        "strict_repairs": strict_repairs,
        "control_ok": control_ok,
        "counts": counts,
        "anchor_only_invisible": invisible,
        "whitewashed_by_permissive_repairs": whitewashed,
        "legacy_blind": blind,
        "results": results,
    }
    out(f"\nBATTERY {battery_fingerprint()[:12]}… — {len(ATTACKS)} attacks, "
        f"{counts['DETECTED']} detected, {counts['MISSED']} missed, {counts['SKIPPED']} skipped")
    if whitewashed:
        out(f"WHITEWASHED by permissive repairs: {whitewashed} — rerun with --strict-repairs "
            f"(the gate does); an unsigned skiplist entry is an unauthenticated override")
    if blind:
        out(f"LEGACY-BLIND: {blind} — records signed before v3.0 carry no commitment to their\n"
            f"  own signer, so a stripped signature moves no digest and the anchored head still\n"
            f"  matches. Not closable by verification; ooptdd.census counts the exposed records.")
    if invisible:
        out(f"ANCHOR-ONLY, INVISIBLE LOCALLY: {invisible}\n"
            f"  These are not drill failures. They are the bootstrap limit: the file cannot\n"
            f"  testify that nothing was cut off its end. Only the cross-machine anchor can,\n"
            f"  which is why ooptdd.gate refuses DONE without one.")
    return (1 if failures else 0), summary


def anchor_check(tree: str, node: str, receipt_id: str, log_path: str,
                 base_url: str = DEFAULT_LAKATOS_URL) -> tuple[int, dict]:
    records = load(log_path)
    mine = [r for r in records if r.get("receipt_id") == receipt_id]
    if not mine:
        print(f"no local records for {receipt_id}", file=sys.stderr)
        return 2, {}
    head = mine[-1]["hash"]
    local_seq = mine[-1]["seq"]
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
        return 2, {"error": str(e)}
    anchors = []
    for ev in events if isinstance(events, list) else events.get("events", []):
        payload = ev.get("payload", {})
        if isinstance(payload, dict) and payload.get("receipt_id") == receipt_id:
            anchors.append(payload)
    if not anchors:
        print(f"no anchors for {receipt_id} on {tree}/{node}", file=sys.stderr)
        return 2, {"error": "no anchors"}

    latest = anchors[-1]
    match = latest.get("hash") == head
    # v3.0 — the truncation detector. Anchored seq numbers are a monotonic
    # external memory of how long this chain has ever been; a local head that
    # sits BELOW the high-water mark means records were removed, and no amount
    # of local verification would have said so.
    anchored_seqs = [int(a["seq"]) for a in anchors if str(a.get("seq", "")).isdigit()]
    high_water = max(anchored_seqs) if anchored_seqs else None
    regressed = high_water is not None and local_seq < high_water

    # v3.1 — PREFIX CONSISTENCY. Every anchor is a claim about what this chain
    # looked like at some past length; the local chain must still agree with ALL
    # of them, not only the newest. v3.0 compared the latest and discarded the
    # rest, which is exactly the gap a rewriter walks through: edit an old record,
    # rehash the tail, re-anchor the new head, and the head comparison says MATCH
    # while every earlier anchor silently contradicts the file.
    #
    # This is a poor cousin of a transparency log's consistency proof — those are
    # O(log N) Merkle proofs a witness checks BEFORE co-signing, and a quorum of
    # independent witnesses is what actually defeats a split view. Here the log
    # hands over whole record hashes and we compare them. It closes the cheap
    # rewrite, not the general case; see docs and the tree's problemshift node.
    by_seq = {r["seq"]: r["hash"] for r in mine}
    inconsistent = [(int(a["seq"]), str(a["hash"])[:12])
                    for a in anchors
                    if str(a.get("seq", "")).isdigit() and a.get("hash")
                    and int(a["seq"]) in by_seq and by_seq[int(a["seq"])] != a["hash"]]

    print(f"local head:  {head[:16]}… (seq {local_seq})")
    print(f"tree anchor: {str(latest.get('hash'))[:16]}… (seq {latest.get('seq')})")
    print(f"anchors seen: {len(anchors)}"
          + (f", high-water seq {high_water}" if high_water is not None else ""))
    if regressed:
        print(f"TRUNCATION: local seq {local_seq} < anchored high-water {high_water} — "
              f"records were removed after being anchored ❌")
    if inconsistent:
        print(f"PREFIX INCONSISTENT at {inconsistent} — the local chain contradicts anchors it "
              f"already published; a head that still matches means the tail was rehashed ❌")
    print("ANCHOR:", "MATCH ✅" if match else "MISMATCH ❌ — chain tampered, rebuilt, or tree behind")
    detail = {"local_head": head, "local_seq": local_seq, "anchor_head": latest.get("hash"),
              "anchored_high_water": high_water, "match": match, "truncation_detected": regressed,
              "anchors_seen": len(anchors), "prefix_inconsistent": inconsistent}
    return (0 if (match and not regressed and not inconsistent) else 1), detail


def main() -> int:
    ap = argparse.ArgumentParser(description="integrity fire drill")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("drill")
    d.add_argument("--log", default=DEFAULT_LOG)
    d.add_argument("--strict-repairs", action="store_true",
                   help="honour only cryptographically signed repair entries")
    d.add_argument("--json", default=None, help="write the battery summary to this path")
    a = sub.add_parser("anchor-check")
    a.add_argument("--tree", required=True)
    a.add_argument("--node", required=True)
    a.add_argument("--receipt-id", required=True)
    a.add_argument("--log", default=DEFAULT_LOG)
    a.add_argument("--url", default=DEFAULT_LAKATOS_URL)
    args = ap.parse_args()
    if args.cmd == "drill":
        code, summary = drill(args.log, strict_repairs=args.strict_repairs)
        if args.json and summary:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=1)
        return code
    code, _detail = anchor_check(args.tree, args.node, args.receipt_id, args.log, args.url)
    return code


if __name__ == "__main__":
    sys.exit(main())
