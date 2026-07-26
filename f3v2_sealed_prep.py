#!/usr/bin/env python3
"""F3v2 sealed cohort prep (prereg execution_order step 3) — F1-style lock.

PREREG (machine-locked, binding spec — read-only input):
  prom_search_hswm/evidence/PREREG_F3V2_harder_transfer_20260726.json

Mirrors the discipline of prom_search_hswm/prom9_prepare_2wiki_f1.py:
dev-form manifest (mode "development") -> --seal flip (mode "sealed"), with
_write_once semantics (O_EXCL + fsync; never replace an existing artifact).
Everything is offline/deterministic: worlds come from the prereg's
seeds/sizes/tiers via f3v2_procedural_worlds, so the manifest content is a
pure function of the prereg file (no timestamps inside).

Cohort (locked prereg): train {hard:32, mid:16, seed:20260727}, test
{hard:384, mid:128, seed:20260810}; 10 contexts per test world (6 core +
g_flat_file §6.5 strong null + 3 gated variants); budget 2*48 + 10*512 =
5216 <= 5400 hard cap; per_call_max_tokens 768.  The prereg's
environment.generator_sha256_at_lock placeholder ("TO_BE_FILLED_BY_SEALED_
PREP") is filled HERE in the manifest — the prereg file itself stays
untouched (it is hash-pinned; editing it would void the lock).

Split audit: every world sha256 across train+test must be unique and the
train/test intersection must be empty (world_id collides across seeds by
construction; content sha is the identity) — fail closed otherwise.

Usage:
  python3 f3v2_sealed_prep.py \
      --out _research/f3v2_runs/f3v2-sealed-prep-r1/manifest.dev.json \
      --receipt _research/f3v2_runs/f3v2-sealed-prep-r1/prep_receipt.json
  python3 f3v2_sealed_prep.py --seal \
      --in _research/f3v2_runs/f3v2-sealed-prep-r1/manifest.dev.json \
      --out _research/f3v2_runs/f3v2-sealed-prep-r1/manifest.sealed.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

fw = importlib.import_module("f3v2_procedural_worlds")
arms = importlib.import_module("f3v2_arms")

DEFAULT_PREREG = (HERE / "prom_search_hswm" / "evidence"
                  / "PREREG_F3V2_harder_transfer_20260726.json")
MANIFEST_SCHEMA = arms.MANIFEST_SCHEMA
PREP_RECEIPT_SCHEMA = "hswm-f3v2-sealed-prep-receipt/v1"
SEAL_RECEIPT_SCHEMA = "hswm-f3v2-sealed-flip-receipt/v1"

HARNESS_MODULES = ("f3v2_procedural_worlds.py", "f2_delta_w_credit.py",
                   "f3v2_arms.py", "f3v2_sealed_prep.py")


class PrepError(RuntimeError):
    pass


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_once(path: Path, value: dict) -> None:
    """O_EXCL + fsync (F1 convention): refuse to replace any existing file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                          indent=2) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                             0o644)
    except FileExistsError as error:
        raise PrepError(f"refusing to replace output: {path}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _split_worlds(block: dict) -> list[dict]:
    """All worlds of one cohort split: every tier in fw.TIERS present as a
    numeric key, generated in sorted-tier order (deterministic)."""
    tiers = {t: block[t] for t in fw.TIERS if t in block}
    if not tiers:
        raise PrepError(f"cohort split has no tier sizes: {sorted(block)}")
    worlds = []
    for tier in sorted(tiers):
        worlds.extend(fw.generate_batch(tiers[tier], tier, block["seed"]))
    return worlds


def _world_entry(w: dict) -> dict:
    return {"world_id": w["world_id"], "tier": w["tier"], "seed": w["seed"],
            "n_items": len(w["items"]), "optimal_len": w["optimal_len"],
            "step_cap": w["step_cap"], "watermark": w["watermark"],
            "world_sha256": fw.world_sha256(w)}


def build_manifest(prereg: dict, *, prereg_path: str,
                   prereg_sha256: str, run_id: str) -> dict:
    """Pure dev-form manifest from the locked prereg (fail-closed)."""
    try:
        cohort = prereg["cohort"]
        contract = prereg["budget_contract"]
    except (TypeError, KeyError) as error:
        raise PrepError(f"prereg missing cohort/budget_contract: {error}")
    train_worlds = _split_worlds(cohort["train"])
    test_worlds = _split_worlds(cohort["test"])

    all_shas = [fw.world_sha256(w) for w in train_worlds + test_worlds]
    train_shas = {fw.world_sha256(w) for w in train_worlds}
    test_shas = {fw.world_sha256(w) for w in test_worlds}
    shared = sorted(train_shas & test_shas)
    duplicates = sorted({s for s in all_shas if all_shas.count(s) > 1})
    if shared or duplicates:
        raise PrepError(
            f"cohort split audit failed: shared={shared} duplicates={duplicates}")

    contexts = list(arms.SEALED_CONTEXTS)
    n_train, n_test = len(train_worlds), len(test_worlds)
    budget = {
        "contexts_per_test_world": len(contexts),
        "receiver_test": n_test * len(contexts),
        "receiver_train": n_train,
        "donor_train": n_train,
        "total": 2 * n_train + n_test * len(contexts),
        "per_call_max_tokens": int(contract.get("per_call_max_tokens", 768)),
        "hard_cap": int(contract.get("hard_cap", 0)),
    }
    registered = int(contract.get("contexts_per_test_world", 0))
    if registered and registered != len(contexts):
        raise PrepError(
            f"prereg registers {registered} contexts/test world but the "
            f"harness has {len(contexts)} (SEALED_CONTEXTS drift)")
    estimated = (contract.get("estimated_calls") or {}).get("total")
    if estimated is not None and int(estimated) != budget["total"]:
        raise PrepError(
            f"prereg estimated_calls.total {estimated} != computed "
            f"{budget['total']} (2*{n_train} + {len(contexts)}*{n_test})")
    if budget["hard_cap"] and budget["total"] > budget["hard_cap"]:
        raise PrepError(
            f"budget {budget['total']} exceeds hard_cap {budget['hard_cap']}")
    budget["within_cap"] = (budget["total"] <= budget["hard_cap"]
                            if budget["hard_cap"] else None)

    estimation = {}
    est_text = (prereg.get("metrics") or {}).get("estimation") or ""
    m = re.search(r"reps=(\d+)", est_text)
    if m:
        estimation["bootstrap_reps"] = int(m.group(1))
    m = re.search(r"seed=(\d+)", est_text)
    if m:
        estimation["bootstrap_seed"] = int(m.group(1))
    estimation["source"] = est_text

    generator_sha = _sha256_path(HERE / "f3v2_procedural_worlds.py")
    return {
        "schema_version": MANIFEST_SCHEMA,
        "mode": "development",
        "run_id": run_id,
        "branch": prereg.get("branch"),
        "preregistration_file": str(prereg_path),
        "preregistration_receipt_sha256": prereg_sha256,
        "preregistration_schema": prereg.get("schema_version"),
        "cohort": {
            "train": {"seed": cohort["train"]["seed"],
                      "tiers": {t: cohort["train"][t] for t in fw.TIERS
                                if t in cohort["train"]},
                      "n_worlds": n_train,
                      "role": cohort["train"].get("role"),
                      "worlds": [_world_entry(w) for w in train_worlds]},
            "test": {"seed": cohort["test"]["seed"],
                     "tiers": {t: cohort["test"][t] for t in fw.TIERS
                               if t in cohort["test"]},
                     "n_worlds": n_test,
                     "role": cohort["test"].get("role"),
                     "worlds": [_world_entry(w) for w in test_worlds]},
            "cluster_key": cohort.get("cluster_key"),
            "split_rule": cohort.get("split_rule"),
        },
        "arms": contexts,
        "models": prereg.get("models"),
        "budget": budget,
        "estimation": estimation,
        "split_audit": {
            "shared_world_sha256": shared,
            "duplicate_world_sha256": duplicates,
            "verdict": "DISJOINT",
            "note": ("world_id is per-seed and collides across splits by "
                     "construction; content sha256 is the split identity."),
        },
        "generator": {
            "module": "f3v2_procedural_worlds.py",
            "sha256": generator_sha,
            "note": ("fills prereg environment.generator_sha256_at_lock "
                     "(placeholder TO_BE_FILLED_BY_SEALED_PREP stays in the "
                     "locked prereg file; the value is sealed HERE)."),
        },
        "harness_module_sha256": {
            name: _sha256_path(HERE / name) for name in HARNESS_MODULES},
        "honesty": ("sealed cohort manifest only; no measurement here. "
                    "Judgment belongs to the gate."),
    }


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PrepError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise PrepError(f"{path} is not a JSON object")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--expect-prereg-sha", default="",
                        help="fail closed unless sha256(prereg file) equals "
                             "this value")
    parser.add_argument("--run-id", default="f3v2-sealed-prep-r1")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--seal", action="store_true",
                        help="flip a dev-form manifest (--in) to mode sealed")
    parser.add_argument("--in", dest="seal_in", type=Path, default=None,
                        help="dev-form manifest to seal (with --seal)")
    args = parser.parse_args(argv)
    try:
        if args.seal:
            if args.seal_in is None:
                raise PrepError("--seal needs --in <dev-form manifest>")
            manifest = _load_json(args.seal_in)
            if manifest.get("schema_version") != MANIFEST_SCHEMA:
                raise PrepError(f"--in is not a {MANIFEST_SCHEMA} manifest")
            if manifest.get("mode") != "development":
                raise PrepError(
                    f"refusing to seal: source mode is "
                    f"{manifest.get('mode')!r} (already sealed?)")
            sealed = dict(manifest)
            sealed["mode"] = "sealed"
            _write_once(args.out, sealed)
            receipt = {
                "schema_version": SEAL_RECEIPT_SCHEMA,
                "status": "SEALED",
                "run_id": sealed.get("run_id"),
                "dev_manifest_file": str(args.seal_in),
                "dev_manifest_sha256": _sha256_path(args.seal_in),
                "sealed_manifest_file": str(args.out),
                "sealed_manifest_sha256": _sha256_path(args.out),
                "note": "mode flip only — every other byte identical.",
            }
            if args.receipt is not None:
                _write_once(args.receipt, receipt)
            print(json.dumps(receipt, sort_keys=True))
            return 0

        prereg_sha = _sha256_path(args.prereg)
        if args.expect_prereg_sha and prereg_sha != args.expect_prereg_sha:
            raise PrepError(
                f"prereg sha mismatch: expected {args.expect_prereg_sha}, "
                f"got {prereg_sha} — the locked prereg drifted")
        prereg = _load_json(args.prereg)
        manifest = build_manifest(prereg, prereg_path=str(args.prereg),
                                  prereg_sha256=prereg_sha,
                                  run_id=args.run_id)
        _write_once(args.out, manifest)
        receipt = {
            "schema_version": PREP_RECEIPT_SCHEMA,
            "status": "PREPARED_DEVELOPMENT_ONLY",
            "run_id": args.run_id,
            "manifest_file": str(args.out),
            "manifest_sha256": _sha256_path(args.out),
            "preregistration_file": str(args.prereg),
            "preregistration_receipt_sha256": prereg_sha,
            "cohort_counts": {
                "train": manifest["cohort"]["train"]["n_worlds"],
                "test": manifest["cohort"]["test"]["n_worlds"],
                "train_tiers": manifest["cohort"]["train"]["tiers"],
                "test_tiers": manifest["cohort"]["test"]["tiers"]},
            "contexts_per_test_world": manifest["budget"]
            ["contexts_per_test_world"],
            "budget": manifest["budget"],
            "generator_sha256": manifest["generator"]["sha256"],
            "split_audit": manifest["split_audit"]["verdict"],
        }
        if args.receipt is not None:
            _write_once(args.receipt, receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except Exception as error:  # noqa: BLE001 — refusal is data, not a crash
        print(json.dumps({"status": "REFUSED", "reason": str(error)},
                         sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
