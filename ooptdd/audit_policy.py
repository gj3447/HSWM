"""ooptdd v2.6 — auditor assignment / rotation / budget policy.

v2.9: ed25519 identity (G1). register accepts a pubkey (rotation-refusing);
record_audit signs inside append()'s lock when a key exists; policy.signature
∈ {verified, untrusted, absent} and a registry-contradicting key is refused.
CLI gains genkey / verify-sigs. Crypto lives in ooptdd/signing.py (RFC 8032,
pure stdlib, RFC test-vector-pinned).

Closes the policy half of `ooptdd-v2-auditor-budget` (v2 design §8, KG
OpenQuestion 2026-07-23). audit.py gives the workflow (prepare/review/record);
this module decides WHO may audit next, WITH WHAT minimum budget, and refuses
policy-violating audits — fail-closed, like receipt_log.

Progressive enforcement (the repo's honesty pattern, cf. lock_binding absent /
derived_self demotion): what the machine can see, it enforces; what it cannot,
it flags as "unverifiable" in the chained record — never silently trusted.

  R1 no-self-audit: auditor_id must differ from the target receipt's
     author_id. Receipt records carry author_id from v2.6 (run_receipt
     --author / OOPTDD_AUTHOR). Receipts without author_id degrade honestly:
     the audit is chained with policy.no_self_audit = "unverifiable".
  R2 rotation: receipts/auditors.json lists known auditors. next_assignment
     picks the eligible auditor whose last audit (any receipt) is oldest
     (never-audited first; ties by auditor_id). Advisory, NOT a gate:
     auditor availability is social; hard-gating deadlocks.
  R3 budget calibration: base = {mutants: 10, counterexamples: 20,
     wall_clock_min: 30}. Every `broken` audit on the same receipt doubles
     the minimum (cap 8x) — a break is evidence the claim is fragile.
     An `upheld` audit with a structured budget below the calibrated minimum
     is REFUSED (ceremony is not chained); a `broken` verdict is always
     chained (falsify needs no budget). Free-text budgets are chained with
     policy.budget_check = "unverifiable".

Stdlib only.

CLI:
  python -m ooptdd.audit_policy register --auditor-id claude-opus-4.5 --kind agent
  python -m ooptdd.audit_policy assign receipts/receipt_cosine_floor.py
  python -m ooptdd.audit_policy budget receipts/receipt_cosine_floor.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from ooptdd.receipt_log import append, file_sha, load

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")
DEFAULT_REGISTRY = os.path.join("receipts", "auditors.json")

BASE_BUDGET = {"mutants": 10, "counterexamples": 20, "wall_clock_min": 30}
MAX_FACTOR = 8


class PolicyRefusal(ValueError):
    """An audit that violates R1/R3 is refused before it reaches the chain."""


# --- registry (R2) -----------------------------------------------------------

def load_registry(registry_path: str = DEFAULT_REGISTRY) -> list[dict]:
    if not os.path.exists(registry_path):
        return []
    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("auditors", []))


def register_auditor(auditor_id: str, kind: str = "agent",
                     registry_path: str = DEFAULT_REGISTRY,
                     pubkey: str | None = None) -> dict:
    """Idempotent by auditor_id; re-registering updates kind only.

    v2.9: an optional ed25519 pubkey binds the identity cryptographically.
    A registered pubkey is NEVER silently rotated — a conflicting re-register
    raises (deliberate rotation = remove the entry first, on purpose)."""
    if kind not in ("agent", "human"):
        raise ValueError(f"kind must be agent|human, got {kind!r}")
    if pubkey is not None:
        try:
            raw = bytes.fromhex(pubkey)
        except ValueError:
            raise ValueError("pubkey must be hex") from None
        if len(raw) != 32:
            raise ValueError(f"pubkey must be 32 bytes (ed25519), got {len(raw)}")
    auditors = load_registry(registry_path)
    for a in auditors:
        if a["auditor_id"] == auditor_id:
            a["kind"] = kind
            if pubkey is not None:
                existing = a.get("pubkey")
                if existing and existing != pubkey:
                    raise ValueError(
                        f"pubkey rotation refused for {auditor_id}: registry has "
                        f"{existing[:12]}…, got {pubkey[:12]}… (remove the entry deliberately to rotate)")
                a["pubkey"] = pubkey
                a["pubkey_registered_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            break
    else:
        entry = {
            "auditor_id": auditor_id,
            "kind": kind,
            "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if pubkey is not None:
            entry["pubkey"] = pubkey
            entry["pubkey_registered_at"] = entry["registered_at"]
        auditors.append(entry)
    os.makedirs(os.path.dirname(os.path.abspath(registry_path)), exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump({"auditors": auditors}, f, indent=1, ensure_ascii=False)
    return {"auditor_id": auditor_id, "kind": kind, "pubkey": pubkey}


def registry_pubkey(auditor_id: str, registry_path: str = DEFAULT_REGISTRY) -> str | None:
    for a in load_registry(registry_path):
        if a["auditor_id"] == auditor_id:
            return a.get("pubkey")
    return None


# --- derived chain facts -----------------------------------------------------

def latest_receipt_record(records: list[dict], receipt_id: str) -> dict | None:
    targets = [r for r in records if r.get("receipt_id") == receipt_id
               and r.get("kind") == "receipt"]
    return targets[-1] if targets else None


def _audits(records: list[dict], receipt_id: str | None = None) -> list[dict]:
    return [r for r in records if r.get("kind") == "audit"
            and (receipt_id is None or r.get("receipt_id") == receipt_id)]


def last_audit_seq(records: list[dict], auditor_id: str) -> int | None:
    seqs = [r["seq"] for r in _audits(records) if r.get("auditor_id") == auditor_id]
    return max(seqs) if seqs else None


def calibrated_budget(records: list[dict], receipt_id: str) -> dict:
    """R3 — base budget escalated by every break on this receipt (cap MAX_FACTOR)."""
    factor = 1
    for r in _audits(records, receipt_id):
        if r.get("audit_verdict") == "broken":
            factor = min(factor * 2, MAX_FACTOR)
    out = {k: v * factor for k, v in BASE_BUDGET.items()}
    out["factor"] = factor
    return out


def next_assignment(records: list[dict], registry: list[dict],
                    receipt_id: str) -> str | None:
    """R2 — deterministic LRU rotation among eligible (non-author) auditors."""
    target = latest_receipt_record(records, receipt_id)
    author = target.get("author_id") if target else None
    eligible = [a for a in registry if not author or a["auditor_id"] != author]
    if not eligible:
        return None

    def key(a: dict):
        seq = last_audit_seq(records, a["auditor_id"])
        return (seq is not None, seq if seq is not None else -1, a["auditor_id"])

    return min(eligible, key=key)["auditor_id"]


# --- enforcement (R1 + R3) ---------------------------------------------------

def enforce(target: dict, auditor_id: str, verdict: str,
            budget: dict | str | None, records: list[dict]) -> dict:
    """Return the policy block for the audit record; raise PolicyRefusal on violation."""
    author = target.get("author_id")
    if author and auditor_id == author:
        raise PolicyRefusal(
            f"self-audit refused: auditor_id={auditor_id!r} authored {target.get('receipt_id')!r} "
            f"(R1 — an author cannot audit their own receipt)")
    minimum = calibrated_budget(records, target["receipt_id"])
    budget_check = "unverifiable"
    if isinstance(budget, dict):
        budget_check = "enforced"
        if verdict == "upheld":
            missing = [k for k in BASE_BUDGET if budget.get(k) is None]
            short = {k: (budget.get(k), minimum[k]) for k in BASE_BUDGET
                     if budget.get(k) is not None and budget[k] < minimum[k]}
            if missing or short:
                raise PolicyRefusal(
                    f"upheld audit below calibrated minimum (R3): "
                    f"missing={missing or '[]'} below={short or '{}'} "
                    f"minimum={ {k: minimum[k] for k in BASE_BUDGET} } "
                    f"(factor x{minimum['factor']} — a break would still be chained)")
    return {
        "no_self_audit": "enforced" if author else "unverifiable",
        "budget_check": budget_check,
        "budget_min": {k: minimum[k] for k in BASE_BUDGET},
        "budget_factor": minimum["factor"],
    }


def record_audit(receipt_path: str, log_path: str, auditor_id: str, verdict: str,
                 notes: str, budget: dict | str | None,
                 registry_path: str = DEFAULT_REGISTRY) -> dict:
    """The enforced audit-record path. Refuses (raises) on R1/R3 violations;
    append() itself re-verifies the chain first (corrupt chain = no audit).

    v2.9: if a private key exists for auditor_id (OOPTDD_KEY_DIR or
    ~/.config/ooptdd/keys), the record is ed25519-signed inside append()'s
    lock, so the signature binds the exact chained content. A registry pubkey
    that contradicts the local key is refused (impersonation-shaped);
    a missing registry pubkey chains as policy.signature="untrusted";
    no key at all chains as "absent" (flagged, never silently trusted)."""
    from ooptdd import signing

    receipt_id = os.path.splitext(os.path.basename(receipt_path))[0]
    records = load(log_path)
    target = latest_receipt_record(records, receipt_id)
    if target is None:
        raise ValueError(f"{log_path}: no receipt record for {receipt_id} — run the harness first")
    policy = enforce(target, auditor_id, verdict, budget, records)
    policy["assigned"] = next_assignment(records, load_registry(registry_path), receipt_id)

    signer = None
    sig_status = "absent"
    sk = signing.load_secret(auditor_id)
    if sk is not None:
        pk_hex = signing.publickey(sk).hex()
        reg_pk = registry_pubkey(auditor_id, registry_path)
        if reg_pk and reg_pk != pk_hex:
            raise PolicyRefusal(
                f"key mismatch for {auditor_id}: local key pubkey {pk_hex[:12]}… "
                f"!= registry {reg_pk[:12]}… (impersonation-shaped; fail-closed)")
        sig_status = "verified" if reg_pk == pk_hex else "untrusted"
        signer = lambda rh: signing.sign_record(rh, sk)  # noqa: E731
    policy["signature"] = sig_status

    rec = append(log_path, {
        "kind": "audit",
        "receipt_id": receipt_id,
        "receipt_sha": file_sha(receipt_path),
        "source_shas": {},
        "lock_sha": target["lock_sha"],
        "lock_binding": target.get("lock_binding", "absent"),
        "verdict": "VALID" if verdict == "upheld" else "INVALID",
        "exit_code": 0 if verdict == "upheld" else 1,
        "status": "audited" if verdict == "upheld" else "self-valid",
        "auditor_id": auditor_id,
        "audit_verdict": verdict,
        "audit_budget": budget,
        "audit_notes": notes[:500],
        "target_hash": target["hash"],
        "mutation_score": None,
        "attestation": None,
        "policy": policy,
    }, signer=signer)
    return rec


def verify_signatures(log_path: str, registry_path: str = DEFAULT_REGISTRY) -> tuple[bool, list[str]]:
    """Walk every audit record and verify its signature block (v2.9).

    Returns (ok, lines). A record with policy.signature="absent" is reported
    (not failed); an invalid or registry-contradicting signature FAILS."""
    from ooptdd import signing

    records = load(log_path)
    lines: list[str] = []
    ok = True
    for r in records:
        if r.get("kind") != "audit":
            continue
        who = r.get("auditor_id", "?")
        block = r.get("signature")
        if block is None:
            lines.append(f"seq={r['seq']} {who}: absent (legacy/unsigned)")
            continue
        if not signing.verify_record_signature(r):
            lines.append(f"seq={r['seq']} {who}: *** INVALID SIGNATURE ***")
            ok = False
            continue
        reg_pk = registry_pubkey(who, registry_path)
        if reg_pk and reg_pk != block.get("pubkey"):
            lines.append(f"seq={r['seq']} {who}: *** pubkey contradicts registry ***")
            ok = False
        else:
            trust = "verified" if reg_pk else "untrusted (no registry pubkey)"
            lines.append(f"seq={r['seq']} {who}: sig OK — {trust}")
    return ok, lines


def main() -> int:
    ap = argparse.ArgumentParser(description="auditor assignment / rotation / budget policy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("register")
    g.add_argument("--auditor-id", required=True)
    g.add_argument("--kind", default="agent", choices=["agent", "human"])
    g.add_argument("--registry", default=DEFAULT_REGISTRY)
    g.add_argument("--pubkey", default=None, help="ed25519 pubkey hex (v2.9; refuses silent rotation)")
    k = sub.add_parser("genkey")
    k.add_argument("--auditor-id", required=True)
    v = sub.add_parser("verify-sigs")
    v.add_argument("--log", default=DEFAULT_LOG)
    v.add_argument("--registry", default=DEFAULT_REGISTRY)
    for name in ("assign", "budget"):
        p = sub.add_parser(name)
        p.add_argument("receipt")
        p.add_argument("--log", default=DEFAULT_LOG)
        p.add_argument("--registry", default=DEFAULT_REGISTRY)
    args = ap.parse_args()

    if args.cmd == "register":
        try:
            entry = register_auditor(args.auditor_id, args.kind, args.registry, pubkey=args.pubkey)
        except ValueError as e:
            print(f"register refused: {e}", file=sys.stderr)
            return 2
        print(f"registered: {entry['auditor_id']} ({entry['kind']})"
              + (f" pubkey={entry['pubkey'][:16]}…" if entry.get("pubkey") else ""))
        return 0
    if args.cmd == "genkey":
        from ooptdd import signing
        try:
            info = signing.genkey(args.auditor_id)
        except ValueError as e:
            print(f"genkey refused: {e}", file=sys.stderr)
            return 2
        print(f"key written: {info['key_path']} (0600 — never commit it)")
        print(f"pubkey: {info['pubkey']}")
        print(f"next: python -m ooptdd.audit_policy register --auditor-id {args.auditor_id} "
              f"--pubkey {info['pubkey']}")
        return 0
    if args.cmd == "verify-sigs":
        ok, lines = verify_signatures(args.log, args.registry)
        for line in lines:
            print(line)
        print("SIGNATURES:", "ALL OK" if ok else "FAILURES PRESENT")
        return 0 if ok else 1
    receipt_id = os.path.splitext(os.path.basename(args.receipt))[0]
    records = load(args.log)
    if latest_receipt_record(records, receipt_id) is None:
        print(f"{args.log}: no receipt record for {receipt_id}", file=sys.stderr)
        return 2
    if args.cmd == "assign":
        chosen = next_assignment(records, load_registry(args.registry), receipt_id)
        print(chosen if chosen else "NONE (registry empty or all auditors are the author)")
    else:
        print(json.dumps(calibrated_budget(records, receipt_id), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
