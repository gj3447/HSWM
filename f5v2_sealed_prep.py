#!/usr/bin/env python3
"""Fail-closed F5v2 B-prime manifest preparation.

This module performs no measurement and never contacts a model endpoint.  It
exists to make the ORDERED research contract executable:

* the amended preregistration must structurally declare a ratified state;
* the canonical ordered status must expose P4 as the unique active gate;
* every earlier gate must be SATISFIED;
* a real CPL1 numeric-packet/provenance unlock receipt must pass;
* preparation is write-once and offline sealing additionally requires a bound
  development-smoke integrity receipt.

Self-hashes prove integrity, not authority.  This offline substrate never
authorizes measurement: external user-ratification, raw ORDERED/CPL1 replay,
independent smoke evidence, and the missing live runtime must be added first.

The current repository state is expected to REFUSE preparation because F1 is
still active.  A refusal is evidence that the sequence guard works, not an
experiment result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

import hswm_next_research_harness as ordered_harness
from f5v2_judge import JudgeContractError, verify_dev_smoke_receipt
from f5v2_operators import F5V2ContractError, parse_cpl1_numeric_packet


HERE = Path(__file__).resolve().parent
DEFAULT_PREREG = (
    HERE
    / "prom_search_hswm"
    / "evidence"
    / "PREREG_F5V2_BPRIME_DURABLE_CACHE_20260726.draft.json"
)
DEFAULT_ORDERED_STATUS = HERE / "receipts" / "HSWM_ORDERED_GATE_STATUS_20260724.json"
DEFAULT_ORDERED_PLAN = HERE / "_research" / "next_gate_harness" / "plan.v1.json"

PREREG_SCHEMA = "hswm-prereg-f5v2-bprime/v1"
ORDERED_SCHEMA = "hswm-next-research-status/v2"
CPL1_UNLOCK_SCHEMA = "hswm-cpl1-unlock-receipt/v1"
MANIFEST_SCHEMA = "hswm-f5v2-bprime-manifest/v1"
PREP_RECEIPT_SCHEMA = "hswm-f5v2-bprime-prep-receipt/v1"
SEAL_RECEIPT_SCHEMA = "hswm-f5v2-bprime-seal-receipt/v1"
DEV_SMOKE_SCHEMA = "hswm-f5v2-dev-smoke-receipt/v1"

ORDERED_SEQUENCE = (
    "F1_MULTI_LLM_FUNCTION_NETWORK",
    "B22_GATE0_REAL_PACKS",
    "P1V5_THREE_FACTOR_BOND_PLASTICITY",
    "P2_AGENT_A_TO_FROZEN_B_TRANSFER",
    "P3_SINGLE_TYPED_TOPOLOGY_OPERATION",
    "P4_HOMEOSTASIS_SLEEP_AND_SCALE",
)
P4_GATE = ORDERED_SEQUENCE[-1]
LEGACY_IMMUTABLE = ("f5_consolidation.py", "f5_replay_judge.py")
F5V2_MODULES = (
    "f5v2_operators.py",
    "f5v2_topic_cache.py",
    "f5v2_judge.py",
    "f5v2_sealed_prep.py",
)


class PrepError(RuntimeError):
    """The requested state transition is not legal or not reproducible."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def require_sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PrepError(f"{label} must be a lowercase SHA-256")
    return value


def add_self_hash(
    value: Mapping[str, Any], key: str = "receipt_sha256"
) -> dict[str, Any]:
    unsigned = dict(value)
    unsigned.pop(key, None)
    return {**unsigned, key: sha256_bytes(canonical_bytes(unsigned))}


def verify_self_hash(
    value: Mapping[str, Any], key: str, label: str
) -> str:
    unsigned = dict(value)
    declared = require_sha256(unsigned.pop(key, None), f"{label} {key}")
    if sha256_bytes(canonical_bytes(unsigned)) != declared:
        raise PrepError(f"{label} self-hash mismatch")
    return declared


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PrepError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except PrepError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PrepError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise PrepError(f"{path} must contain one JSON object")
    return value


def _require_object_matches_file(
    value: Mapping[str, Any], path: Path, label: str
) -> None:
    if Path(path).is_symlink():
        raise PrepError(f"{label} path must not be a symlink")
    loaded = load_json(Path(path))
    if canonical_bytes(loaded) != canonical_bytes(dict(value)):
        raise PrepError(f"{label} object does not match its bound file")


def write_once(path: Path, value: dict[str, Any]) -> None:
    """Persist canonical pretty JSON without replacing an existing artifact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise PrepError(f"refusing to replace output: {path}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def validate_prereg(prereg: dict[str, Any]) -> None:
    if prereg.get("schema_version") != PREREG_SCHEMA:
        raise PrepError(f"prereg schema must be {PREREG_SCHEMA}")
    status = str(prereg.get("status", ""))
    if status != "USER_RATIFIED_READY_FOR_MACHINE_LOCK":
        raise PrepError(
            "prereg status does not declare user-ratified: expected "
            "USER_RATIFIED_READY_FOR_MACHINE_LOCK, got " + repr(status)
        )
    authority = prereg.get("authority") or {}
    if authority.get("c4_selection") != "B_PRIME_QUERY_AGNOSTIC_DURABLE_SLOW_W_H":
        raise PrepError("C4 is not locked to B-prime durable slow-W/H")
    if authority.get("c4_user_canon_inferred") is not False:
        raise PrepError("prereg must not infer user canon for the C4 design")
    contract = prereg.get("input_contract") or {}
    deny = set(contract.get("denylist") or [])
    for key in ("query", "query_text", "query_sha256", "training_answer", "verdict_text"):
        if key not in deny:
            raise PrepError(f"prereg denylist is missing {key}")
    invariants = prereg.get("bprime_invariants") or {}
    required_true = (
        "query_agnostic_build",
        "content_addressed_blocks",
        "durable_reuse_across_queries",
        "derived_numeric_novelty_required",
        "source_packet_and_provenance_hashes_required",
        "canonical_output_independent_of_input_order",
    )
    missing = [key for key in required_true if invariants.get(key) is not True]
    if missing:
        raise PrepError(f"prereg B-prime invariants are not locked: {missing}")


def validate_ordered_status(status: dict[str, Any]) -> None:
    try:
        verified_status_sha = ordered_harness.verify_status(status)
    except ordered_harness.NextResearchHarnessError as error:
        raise PrepError(f"ordered status verification failed: {error}") from error
    if status.get("schema_version") != ORDERED_SCHEMA:
        raise PrepError(f"ordered status schema must be {ORDERED_SCHEMA}")
    if status.get("status_receipt_sha256") != verified_status_sha:
        raise PrepError("ordered status receipt identity mismatch")
    if status.get("sequence_locked") is not True:
        raise PrepError("ordered research sequence is not locked")
    active = status.get("active_gate") or {}
    if active.get("id") != P4_GATE:
        raise PrepError(
            f"out-of-order: active gate is {active.get('id')!r}, not {P4_GATE}"
        )
    current_harness_sha = sha256_path(HERE / "hswm_next_research_harness.py")
    current_plan_sha = sha256_path(DEFAULT_ORDERED_PLAN)
    if status.get("harness_sha256") != current_harness_sha:
        raise PrepError("P4 ordered status is not bound to the current harness SHA")
    if status.get("plan_sha256") != current_plan_sha:
        raise PrepError("P4 ordered status is not bound to the current plan SHA")
    gates = {gate.get("id"): gate for gate in status.get("gates") or []}
    missing = [gate_id for gate_id in ORDERED_SEQUENCE if gate_id not in gates]
    if missing:
        raise PrepError(f"ordered status omits gates: {missing}")
    unsatisfied = [
        gate_id
        for gate_id in ORDERED_SEQUENCE[:-1]
        if gates[gate_id].get("state") != "SATISFIED"
    ]
    if unsatisfied:
        raise PrepError(f"upstream ordered gates are not SATISFIED: {unsatisfied}")
    p4 = gates[P4_GATE]
    if p4.get("state") not in ("ACTION_REQUIRED", "READY"):
        raise PrepError(f"P4 is not open for action: state={p4.get('state')!r}")
    if p4.get("missing_dependencies"):
        raise PrepError(f"P4 still has missing dependencies: {p4['missing_dependencies']}")
    if list(status.get("ordered_remaining") or []) != [P4_GATE]:
        raise PrepError(
            "ordered_remaining must contain only P4 before F5v2 preparation"
        )
    if status.get("scientific_verdict_emitted") is not False:
        raise PrepError("ordered status unexpectedly carries a scientific verdict")


def validate_cpl1_unlock(receipt: dict[str, Any]) -> None:
    verify_self_hash(receipt, "receipt_sha256", "CPL1 unlock receipt")
    if receipt.get("schema_version") != CPL1_UNLOCK_SCHEMA:
        raise PrepError(f"CPL1 unlock schema must be {CPL1_UNLOCK_SCHEMA}")
    if receipt.get("status") != "PASS_F5V2_UNLOCK":
        raise PrepError("CPL1 receipt does not authorize the F5v2 unlock")
    packet = receipt.get("numeric_packet") or {}
    if not isinstance(packet, Mapping) or set(packet) != {
        "packet_sha256",
        "payload",
        "pre_outcome_receipt_sha256",
    }:
        raise PrepError(
            "CPL1 numeric packet must contain exact packet_sha256, payload, "
            "and pre_outcome_receipt_sha256 fields"
        )
    packet_sha = require_sha256(
        packet.get("packet_sha256"), "CPL1 numeric packet packet_sha256"
    )
    require_sha256(
        packet.get("pre_outcome_receipt_sha256"),
        "CPL1 numeric packet pre_outcome_receipt_sha256",
    )
    try:
        parsed_payload = parse_cpl1_numeric_packet(packet.get("payload"))
    except F5V2ContractError as error:
        raise PrepError(f"CPL1 exact five-field payload is invalid: {error}") from error
    if parsed_payload.packet_sha256 != packet_sha:
        raise PrepError("CPL1 numeric packet canonical packet_sha256 mismatch")
    gates = receipt.get("causal_gates") or {}
    required = {
        "numeric_W_gain_positive": True,
        "W_removal_erases_gain": True,
        "G_match_lcb_positive": True,
        "DSI_lcb_positive": True,
        "prompt_forbidden_overlap_count_zero": True,
    }
    bad = [key for key, expected in required.items() if gates.get(key) is not expected]
    if bad:
        raise PrepError(f"CPL1 causal unlock gates failed or are absent: {bad}")


def build_manifest(
    prereg: dict[str, Any],
    ordered_status: dict[str, Any],
    cpl1_unlock: dict[str, Any],
    *,
    prereg_path: Path,
    ordered_status_path: Path,
    cpl1_unlock_path: Path,
    run_id: str,
) -> dict[str, Any]:
    """Build a deterministic development manifest after all gates validate."""
    _require_object_matches_file(prereg, prereg_path, "preregistration")
    _require_object_matches_file(ordered_status, ordered_status_path, "ordered status")
    _require_object_matches_file(cpl1_unlock, cpl1_unlock_path, "CPL1 unlock")
    prereg_path = Path(prereg_path).resolve()
    ordered_status_path = Path(ordered_status_path).resolve()
    cpl1_unlock_path = Path(cpl1_unlock_path).resolve()
    validate_prereg(prereg)
    validate_ordered_status(ordered_status)
    validate_cpl1_unlock(cpl1_unlock)
    if not isinstance(run_id, str) or not run_id.strip() or run_id != run_id.strip():
        raise PrepError("run_id must be non-empty canonical text")
    missing_modules = [name for name in F5V2_MODULES if not (HERE / name).is_file()]
    if missing_modules:
        raise PrepError(f"F5v2 implementation modules are missing: {missing_modules}")
    legacy_hashes = {name: sha256_path(HERE / name) for name in LEGACY_IMMUTABLE}
    implementation_hashes = {name: sha256_path(HERE / name) for name in F5V2_MODULES}
    unsigned = {
        "schema_version": MANIFEST_SCHEMA,
        "mode": "development",
        "run_id": run_id,
        "experiment_id": prereg["experiment_id"],
        "ordered_active_gate": P4_GATE,
        "preregistration": {
            "path": str(prereg_path),
            "sha256": sha256_path(prereg_path),
            "status": prereg["status"],
        },
        "ordered_status": {
            "path": str(ordered_status_path),
            "sha256": sha256_path(ordered_status_path),
            "status_receipt_sha256": ordered_status.get("status_receipt_sha256"),
        },
        "cpl1_unlock": {
            "path": str(cpl1_unlock_path),
            "sha256": sha256_path(cpl1_unlock_path),
            "receipt_sha256": cpl1_unlock.get("receipt_sha256"),
            "numeric_packet": cpl1_unlock["numeric_packet"],
        },
        "arms": [arm["id"] for arm in prereg["arms"]],
        "statistics": prereg["statistics"],
        "cost_contract": prereg["cost_contract"],
        "judge_contract": prereg["judge_contract"],
        "legacy_immutable_sha256": legacy_hashes,
        "implementation_sha256": implementation_hashes,
        "authority_state": "UNVERIFIED_SELF_HASH_INTEGRITY_ONLY",
        "measurement_authorized": False,
        "honesty": (
            "This manifest locks configuration only. It is not a scientific "
            "result and does not authorize a sealed run by itself."
        ),
    }
    return add_self_hash(unsigned, "manifest_self_sha256")


def _manifest_binding(manifest: Mapping[str, Any], key: str) -> tuple[Path, str]:
    binding = manifest.get(key)
    if not isinstance(binding, Mapping):
        raise PrepError(f"development manifest lacks {key} binding")
    raw_path = binding.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise PrepError(f"development manifest {key} path is invalid")
    path = Path(raw_path)
    if path.is_symlink():
        raise PrepError(f"development manifest {key} path must not be a symlink")
    expected_sha = require_sha256(binding.get("sha256"), f"{key} file hash")
    try:
        actual_sha = sha256_path(path)
    except OSError as error:
        raise PrepError(f"cannot read bound {key} file: {error}") from error
    if actual_sha != expected_sha:
        raise PrepError(f"bound {key} file hash drifted")
    return path, expected_sha


def validate_development_manifest(
    manifest: dict[str, Any], *, dev_manifest_path: Path
) -> None:
    """Re-read every bound input and reproduce the manifest from current code."""

    _require_object_matches_file(manifest, dev_manifest_path, "development manifest")
    verify_self_hash(manifest, "manifest_self_sha256", "development manifest")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise PrepError(f"input is not a {MANIFEST_SCHEMA} manifest")
    if manifest.get("mode") != "development":
        raise PrepError("only a development manifest can be sealed")
    prereg_path, _ = _manifest_binding(manifest, "preregistration")
    ordered_path, _ = _manifest_binding(manifest, "ordered_status")
    cpl1_path, _ = _manifest_binding(manifest, "cpl1_unlock")
    prereg = load_json(prereg_path)
    ordered = load_json(ordered_path)
    cpl1 = load_json(cpl1_path)
    rebuilt = build_manifest(
        prereg,
        ordered,
        cpl1,
        prereg_path=prereg_path,
        ordered_status_path=ordered_path,
        cpl1_unlock_path=cpl1_path,
        run_id=manifest.get("run_id"),
    )
    if canonical_bytes(rebuilt) != canonical_bytes(manifest):
        raise PrepError(
            "development manifest does not reproduce from bound inputs and current code"
        )


def build_prep_receipt(
    manifest: dict[str, Any], *, dev_manifest_path: Path
) -> dict[str, Any]:
    """Bind the written development manifest to all three input receipts."""

    _require_object_matches_file(manifest, dev_manifest_path, "development manifest")
    manifest_self_sha = verify_self_hash(
        manifest, "manifest_self_sha256", "development manifest"
    )
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("mode") != "development":
        raise PrepError("prep receipt requires a development manifest")
    prereg = manifest.get("preregistration") or {}
    ordered = manifest.get("ordered_status") or {}
    cpl1 = manifest.get("cpl1_unlock") or {}
    unsigned = {
        "schema_version": PREP_RECEIPT_SCHEMA,
        "status": "OFFLINE_PREPARED_NOT_AUTHORIZED",
        "run_id": manifest.get("run_id"),
        "manifest_sha256": sha256_path(dev_manifest_path),
        "manifest_self_sha256": manifest_self_sha,
        "preregistration_sha256": prereg.get("sha256"),
        "ordered_status_sha256": ordered.get("sha256"),
        "ordered_status_receipt_sha256": ordered.get("status_receipt_sha256"),
        "cpl1_unlock_sha256": cpl1.get("sha256"),
        "cpl1_unlock_receipt_sha256": cpl1.get("receipt_sha256"),
    }
    for key, value in unsigned.items():
        if key.endswith("sha256"):
            require_sha256(value, f"prep receipt {key}")
    return add_self_hash(unsigned, "receipt_sha256")


def validate_prep_receipt(
    receipt: dict[str, Any],
    *,
    prep_receipt_path: Path,
    manifest: dict[str, Any],
    dev_manifest_path: Path,
) -> None:
    _require_object_matches_file(receipt, prep_receipt_path, "prep receipt")
    verify_self_hash(receipt, "receipt_sha256", "prep receipt")
    expected = build_prep_receipt(manifest, dev_manifest_path=dev_manifest_path)
    if canonical_bytes(expected) != canonical_bytes(receipt):
        raise PrepError("prep receipt is not bound to this manifest and input chain")


def _validate_smoke(
    smoke: dict[str, Any], *, smoke_path: Path, dev_manifest_path: Path
) -> None:
    _require_object_matches_file(smoke, smoke_path, "development smoke")
    try:
        verify_dev_smoke_receipt(smoke)
    except JudgeContractError as error:
        raise PrepError(f"development smoke verification failed: {error}") from error
    if smoke.get("schema_version") != DEV_SMOKE_SCHEMA:
        raise PrepError(f"dev smoke schema must be {DEV_SMOKE_SCHEMA}")
    if smoke.get("status") != "PASS_OFFLINE_INTEGRITY":
        raise PrepError("development smoke did not PASS offline integrity")
    if smoke.get("manifest_sha256") != sha256_path(dev_manifest_path):
        raise PrepError("development smoke is not bound to this manifest")
    required = smoke.get("gates") or {}
    for key in (
        "legacy_downscale_negative_reproduced",
        "bitemporal_fired",
        "provenance_passed",
        "canary_passed",
        "drm_lure_passed",
        "query_leakage_zero",
    ):
        if required.get(key) is not True:
            raise PrepError(f"development smoke gate failed or absent: {key}")


def seal_manifest(
    manifest: dict[str, Any],
    smoke: dict[str, Any],
    prep_receipt: dict[str, Any],
    *,
    dev_manifest_path: Path,
    smoke_path: Path,
    prep_receipt_path: Path,
) -> dict[str, Any]:
    validate_development_manifest(manifest, dev_manifest_path=dev_manifest_path)
    validate_prep_receipt(
        prep_receipt,
        prep_receipt_path=prep_receipt_path,
        manifest=manifest,
        dev_manifest_path=dev_manifest_path,
    )
    _validate_smoke(smoke, smoke_path=smoke_path, dev_manifest_path=dev_manifest_path)
    sealed = dict(manifest)
    sealed.pop("manifest_self_sha256", None)
    sealed["mode"] = "offline-sealed"
    sealed["development_smoke"] = {
        "path": str(Path(smoke_path).resolve()),
        "sha256": sha256_path(smoke_path),
        "receipt_sha256": smoke.get("receipt_sha256"),
    }
    sealed["prep_receipt"] = {
        "path": str(Path(prep_receipt_path).resolve()),
        "sha256": sha256_path(prep_receipt_path),
        "receipt_sha256": prep_receipt.get("receipt_sha256"),
    }
    sealed["authority_state"] = "BLOCKED_EXTERNAL_AUTHORITIES_AND_RUNTIME_MISSING"
    sealed["missing_authorities"] = [
        "external_user_ratification_receipt",
        "ordered_raw_evidence_rejudgment",
        "cpl1_source_provenance_replay",
        "independent_raw_dev_smoke",
        "sqlite_cas_slow_h_live_runner_and_replay_runtime",
    ]
    sealed["measurement_authorized"] = False
    return add_self_hash(sealed, "manifest_self_sha256")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--ordered-status", type=Path, default=DEFAULT_ORDERED_STATUS)
    parser.add_argument("--cpl1-unlock", type=Path)
    parser.add_argument("--run-id", default="f5v2-bprime-r1")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--refusal-receipt", type=Path)
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--in", dest="seal_in", type=Path)
    parser.add_argument("--dev-smoke", type=Path)
    parser.add_argument("--prep-receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.seal:
            if (
                args.seal_in is None
                or args.dev_smoke is None
                or args.prep_receipt is None
            ):
                raise PrepError(
                    "--seal requires --in, --dev-smoke, and --prep-receipt"
                )
            manifest = load_json(args.seal_in)
            smoke = load_json(args.dev_smoke)
            prep_receipt = load_json(args.prep_receipt)
            sealed = seal_manifest(
                manifest,
                smoke,
                prep_receipt,
                dev_manifest_path=args.seal_in,
                smoke_path=args.dev_smoke,
                prep_receipt_path=args.prep_receipt,
            )
            write_once(args.out, sealed)
            receipt = add_self_hash(
                {
                    "schema_version": SEAL_RECEIPT_SCHEMA,
                    "status": "OFFLINE_SEALED_NOT_AUTHORIZED",
                    "run_id": sealed.get("run_id"),
                    "dev_manifest_sha256": sha256_path(args.seal_in),
                    "prep_receipt_sha256": sha256_path(args.prep_receipt),
                    "dev_smoke_sha256": sha256_path(args.dev_smoke),
                    "sealed_manifest_sha256": sha256_path(args.out),
                    "sealed_manifest_self_sha256": sealed.get(
                        "manifest_self_sha256"
                    ),
                },
                "receipt_sha256",
            )
        else:
            if args.cpl1_unlock is None:
                # Validate the prereg first so the present DRAFT state yields the
                # most actionable refusal rather than a generic missing-arg error.
                validate_prereg(load_json(args.prereg))
                raise PrepError("--cpl1-unlock is required after ratification")
            prereg = load_json(args.prereg)
            ordered = load_json(args.ordered_status)
            cpl1 = load_json(args.cpl1_unlock)
            manifest = build_manifest(
                prereg,
                ordered,
                cpl1,
                prereg_path=args.prereg,
                ordered_status_path=args.ordered_status,
                cpl1_unlock_path=args.cpl1_unlock,
                run_id=args.run_id,
            )
            write_once(args.out, manifest)
            receipt = build_prep_receipt(manifest, dev_manifest_path=args.out)
        if args.receipt is not None:
            write_once(args.receipt, receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as error:  # noqa: BLE001 -- a refusal is an evidence outcome
        refusal = add_self_hash(
            {
                "schema_version": "hswm-f5v2-prep-refusal/v1",
                "status": "REFUSED",
                "reason": str(error),
                "preregistration_file": str(args.prereg),
                "ordered_status_file": str(args.ordered_status),
                "requested_transition": "SEAL" if args.seal else "PREPARE",
                "prep_implementation_sha256": sha256_path(
                    HERE / "f5v2_sealed_prep.py"
                ),
            },
            "receipt_sha256",
        )
        if args.refusal_receipt is not None:
            try:
                write_once(args.refusal_receipt, refusal)
            except Exception as write_error:  # preserve the original refusal
                refusal["refusal_receipt_error"] = str(write_error)
        print(json.dumps(refusal, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
