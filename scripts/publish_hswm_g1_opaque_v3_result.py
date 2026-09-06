#!/usr/bin/env python3
"""Project one completed opaque v3 (G0-local) occurrence into public, redacted artifacts.

Runs on the run host inside the checkout, after ``hswm-run`` published the
private closure.  It replays the frozen-file, one-shot-registry, and DGX
final-attestation joins with the checked-in verifiers, then writes:

* ``results/raw/<slug>/independent_verification.json``  (verifier outputs)
* ``results/raw/<slug>/public_redacted_projection.json`` (aggregate result,
  rule, runtime identity, digests; no prompts, completions, salts, canaries,
  correct codes, or Permit keys)
* ``evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_<date>.json``

Nothing here changes the terminal the instrument sealed, and a projection is
not a G0 pass, a G1 result, or efficacy evidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hswm.experiments import g1_micro, g1_opaque_v3  # noqa: E402
from hswm.experiments.g1_micro_dgx import verify_dgx_execution_receipt  # noqa: E402
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256  # noqa: E402


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--execution-registry", type=Path, required=True)
    parser.add_argument("--live-run-dir", type=Path, required=True, help="/mnt/hswm/runs/<live run id> (artifacts.tar + receipt.json)")
    parser.add_argument("--preflight-run-dir", type=Path, required=True)
    parser.add_argument("--aborted-run-dir", type=Path, action="append", default=[], help="earlier VOID attempt(s) of the same family, recorded not hidden")
    parser.add_argument("--slug", required=True, help="results/raw/<slug>")
    parser.add_argument("--study-date", required=True)
    parser.add_argument("--family", default="V3", help="evidence file label: V3 or V4 (design revision)")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    protocol, protocol_sha = g1_opaque_v3.load_v3_protocol(args.protocol)
    live_receipt = _load(args.live_run_dir / "receipt.json")
    preflight_receipt = _load(args.preflight_run_dir / "receipt.json")
    archive = args.live_run_dir / "artifacts.tar"
    with tempfile.TemporaryDirectory(prefix="hswm-v3-publish-") as scratch:
        with tarfile.open(archive) as tar:
            tar.extractall(scratch, filter="data")
        closure = Path(scratch) / "outputs" / "g1_opaque_v3"
        bundle_path = closure / "result.json"
        receipt_path = closure / "dgx_runtime_receipt.json"
        bundle = g1_micro._canonical_object(bundle_path.read_bytes(), "v3 result bundle")
        frozen = g1_micro.verify_frozen_execution_files(
            bundle_path=bundle_path, protocol_path=args.protocol, execution_registry_path=args.execution_registry,
        )
        runtime_receipt = g1_micro._canonical_object(receipt_path.read_bytes(), "DGX runtime receipt")
        final = verify_dgx_execution_receipt(receipt=runtime_receipt, bundle=bundle, protocol=protocol)
        marker = _load(closure / "sealed_before_reveal.json")
        reveal_sha = _sha(closure / "evaluator_reveal.json")

    metrics = bundle["metrics"]
    runtime_binding = bundle["runtime_binding"]["payload"]
    registry = _load(args.execution_registry)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    observed = bool(metrics["g0_local_identifiability_observed"])
    verification = {
        "bundle_sha256": bundle["bundle_sha256"],
        "frozen_execution": frozen,
        "final_runtime": final,
        "seal_marker": {"sealed_journals_sha256": marker["sealed_journals_sha256"], "behavior_calls_sealed": marker["behavior_calls_sealed"]},
        "verification": "VALID_V3_FROZEN_FILES_ONE_SHOT_SEAL_AND_DGX_FINAL_ATTESTATION_JOIN",
        "verifier_commit": g1_micro._source_manifest(),
    }
    aborted = []
    for run_dir in args.aborted_run_dir:
        receipt = _load(run_dir / "receipt.json")
        aborted.append({
            "run_id": receipt.get("run_id"),
            "wrapper_receipt_sha256": _sha(run_dir / "receipt.json"),
            "artifact_tar_sha256": _sha(run_dir / "artifacts.tar"),
            "terminal": "INCONCLUSIVE_MEASUREMENT_NOT_READY",
            "cause": "instrument defect after seal (actor stat of the evaluator-private ledger); repaired and rerun within 24 hours under SR-3",
        })
    projection = {
        "schema_version": "hswm-g1-opaque-identifiability-v3-public-redacted-projection/v1",
        "record_role": "POST_EXECUTION_AGGREGATE_G0_LOCAL_IDENTIFIABILITY_RESULT_NOT_G0_EXTERNAL_NOT_G1_EFFICACY",
        "authority": "CONTENT_ADDRESSED_PUBLIC_PROJECTION_OF_ONE_PRIVATE_SEALED_DGX_OCCURRENCE",
        "study_uid": protocol["study_uid"],
        "recorded_at_utc": now,
        "terminal": bundle["terminal"],
        "claim_ceiling": bundle["claim_ceiling"],
        "scientific_status": bundle["scientific_status"],
        "preregistration": {
            "path": str(args.protocol.relative_to(args.repo_root)) if args.protocol.is_absolute() else str(args.protocol),
            "canonical_sha256": protocol_sha,
            "raw_file_sha256": _sha(args.protocol),
            "reveal_commitment_root": protocol["evaluator_reveal_contract"]["reveal_commitment_root"],
            "seed_commitment_sha256": protocol["generation"]["seed_commitment_sha256"],
            "code_selection": protocol["generation"]["code_selection"],
            "freeze": protocol["freeze"],
            "tokenizer_binding_status": protocol["tokenizer_binding"]["status"],
        },
        "frozen_source": {
            "source_commit": runtime_binding["source_commit"],
            "source_tree": runtime_binding["source_tree"],
            "source_manifest": runtime_binding["source_manifest"],
        },
        "model_runtime": {
            key: runtime_binding[key] for key in (
                "container_image", "container_image_id", "gpu_name", "gpu_uuid", "model_repository", "model_revision",
                "model_snapshot_manifest_sha256", "served_model", "vllm_version", "network_boundary", "endpoint_origin",
            )
        },
        "execution": {
            "preflight_run_id": preflight_receipt.get("run_id"),
            "preflight_receipt_sha256": _sha(args.preflight_run_dir / "receipt.json"),
            "live_run_id": live_receipt.get("run_id"),
            "live_wrapper_receipt_sha256": _sha(args.live_run_dir / "receipt.json"),
            "private_live_archive_sha256": _sha(archive),
            "private_live_archive_bytes": archive.stat().st_size,
            "registry_sha256": _sha(args.execution_registry),
            "registry_status": registry["payload"]["status"],
            "bundle_sha256": bundle["bundle_sha256"],
            "runtime_binding_record_sha256": bundle["runtime_binding"]["record_sha256"],
            "runtime_receipt_record_sha256": runtime_receipt["record_sha256"],
            "completion_posts": bundle["total_completion_posts"],
            "tokenize_posts": bundle["total_tokenize_posts"],
            "retry_or_refill_permitted": False,
            "aborted_attempts_same_family": aborted,
        },
        "custody": {
            "evaluator_boundary": bundle["evaluator_boundary"],
            "evaluator_separate_os_user_episodes": metrics["evaluator_separate_os_user_episodes"],
            "evaluator_feedback_verified": metrics["evaluator_feedback_verified"],
            "evaluator_ledger_readable_by_actor": bundle["evaluator_ledger"].get("readable_by_actor", False),
            "reveal_attached_after_seal": bundle["reveal_attached_after_seal"],
            "evaluator_reveal_sha256": reveal_sha,
            "actor_holds_passwordless_sudo": True,
            "custody_ceiling": "OS_USER_SEPARATION_NOT_PRIVILEGE_SEPARATION",
        },
        "aggregate_result": {
            key: metrics[key] for key in (
                "episode_count", "branch_correct", "branch_wilson_95", "credit_and_admission", "atom_v2_permit_commits",
                "exact_remove_and_restore_count", "delta_state", "six_branch_signature_rate", "contrasts",
                "no_state_correct_by_position", "no_state_position_stratum_sizes", "correct_position_balance_stateful",
                "stateful_correct_by_stateful_position",
                "g0_local_identifiability_observed", "terminal",
            ) if key in metrics
        },
        "preregistered_identifiability_rule": dict(protocol["analysis"]["g0_local_identifiability_rule"]),
        "confidentiality_boundary": {
            "private_raw_closure_checked_in": False,
            "private_raw_closure_content_addressed_on_durable_storage": True,
            "excluded_from_public_projection": ["prompts", "completions", "salts", "leakage canaries", "correct action codes", "Permit keys", "per-episode ledgers"],
        },
        "claim_boundary": {
            "claim_ceiling": bundle["claim_ceiling"],
            "g0_local": "MEASUREMENT_READY_SINGLE_OWNER_CANDIDATE_OBSERVED" if observed else "NOT_OBSERVED",
            "g0_external": "DEFERRED_PUBLICATION_GATE_UNTIL_SECOND_PARTY",
            "g1": "NOT_EVALUATED",
            "hswm_learning_or_efficacy_established": False,
            "canonical_hswm_admission_performed": False,
            "reuse_first_comparator_evaluated": False,
            "fractal_research_status_unchanged": "SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED",
            "live_kg_mutated": False,
        },
    }
    raw_dir = args.repo_root / "results" / "raw" / args.slug
    raw_dir.mkdir(parents=True, exist_ok=True)
    projection_path = raw_dir / "public_redacted_projection.json"
    verification_path = raw_dir / "independent_verification.json"
    for path, value in ((projection_path, projection), (verification_path, verification)):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
        path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    evidence = {
        "schema_version": "hswm-g1-opaque-identifiability-v3-evidence-projection/v1",
        "record_role": "POST_EXECUTION_MATERIAL_G0_LOCAL_EVIDENCE_NOT_G0_EXTERNAL_NOT_G1_GATE_JUDGMENT",
        "authority": "CONTENT_ADDRESSED_PUBLIC_EVIDENCE_PROJECTION_BOUND_TO_PRIVATE_DURABLE_CLOSURE",
        "study_uid": protocol["study_uid"],
        "recorded_at_utc": now,
        "terminal": bundle["terminal"],
        "claim_ceiling": bundle["claim_ceiling"],
        "scientific_status": bundle["scientific_status"],
        "preregistration": projection["preregistration"],
        "execution_join": projection["execution"],
        "measurement": projection["aggregate_result"],
        "custody": projection["custody"],
        "independent_local_verification": {
            "path": str(verification_path.relative_to(args.repo_root)),
            "sha256": _sha(verification_path),
            "overall": verification["verification"],
            "independently_owned_scientific_adjudicator": False,
        },
        "public_artifacts": {
            "redacted_projection": {"path": str(projection_path.relative_to(args.repo_root)), "bytes": projection_path.stat().st_size, "sha256": _sha(projection_path)},
            "independent_verification": {"path": str(verification_path.relative_to(args.repo_root)), "bytes": verification_path.stat().st_size, "sha256": _sha(verification_path)},
        },
        "confidentiality_boundary": projection["confidentiality_boundary"],
        "claim_boundary": projection["claim_boundary"],
        "closure_plan": {"step": "S-3", "decision": "D-1 (G0-local / G0-external split, RATIFIED)", "stop_rule_applied": "SR-3 repaired rerun within 24 hours" if aborted else None},
    }
    evidence_path = args.repo_root / "evidence" / f"EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_{args.family}_{args.study_date}.json"
    if evidence_path.exists():
        raise SystemExit(f"refusing to overwrite {evidence_path}")
    evidence_path.write_bytes(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({
        "terminal": bundle["terminal"], "claim_ceiling": bundle["claim_ceiling"],
        "branch_correct": metrics["branch_correct"], "delta_state": metrics["delta_state"],
        "g0_local_identifiability_observed": observed,
        "projection": str(projection_path.relative_to(args.repo_root)), "projection_sha256": _sha(projection_path),
        "verification": str(verification_path.relative_to(args.repo_root)),
        "evidence": str(evidence_path.relative_to(args.repo_root)), "evidence_sha256": _sha(evidence_path),
        "bundle_sha256": bundle["bundle_sha256"], "protocol_canonical_sha256": protocol_sha,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
