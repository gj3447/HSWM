"""Run the sole preregistered DGX live-Q1 path under an exclusive lease."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import tempfile
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_q1.independent_live_verifier import VOID, verify
from _research.dgx_q1.live_launcher import LiveQ1Lease, LiveQ1Spec
from _research.dgx_q1.live_protocol import LiveQ1CaseMaterial, validate_live_q1_plan
from _research.dgx_q1.live_runner import LiveQ1Runner


RESULT_SCHEMA = "hswm-dgx-q1-live-experiment-result/v1"
IDENTITY_NAMES = (
    "endpoint_sha256",
    "model_identity_sha256",
    "runtime_identity_sha256",
    "tls_identity_sha256",
    "declared_isolation_contract_sha256",
    "model_snapshot_manifest_sha256",
)
PROVENANCE_NAMES = (
    "source_ci_receipt_sha256",
    "verifier_ci_receipt_sha256",
    "verifier_build_output_sha256",
)


class LiveExperimentRefusal(RuntimeError):
    pass


def _call_bounds(evidence_root: Path) -> dict[str, Any]:
    """Report conservative call bounds from the durable ledger prefix.

    A START is fsynced before the POST, so it is an upper bound on calls that
    may have reached the provider.  A stored raw envelope is a lower bound on
    completed provider responses.  Transport failures and process crashes can
    leave the exact count unknowable; they must never be reported as zero by
    default.
    """

    ledger = evidence_root / "q1_live_ledger.jsonl"
    if ledger.is_symlink() or not ledger.is_file():
        return {
            "completed_response_envelopes_lower_bound": 0,
            "durable_start_records_observed": 0,
            "provider_call_upper_bound": 0,
            "exact_count_known": True,
        }
    try:
        raw = ledger.read_bytes()
    except OSError:
        return {
            "completed_response_envelopes_lower_bound": 0,
            "durable_start_records_observed": 0,
            "provider_call_upper_bound": 96,
            "exact_count_known": False,
        }
    starts = 0
    responses = 0
    valid = raw.endswith(b"\n")
    lines = raw.splitlines()
    for line in lines:
        try:
            row = parse_canonical(line)
        except Exception:
            valid = False
            continue
        if type(row) is not dict:
            valid = False
            continue
        if row.get("record_type") == "START":
            starts += 1
        elif row.get("record_type") == "TERMINAL" and row.get("raw_envelope") is not None:
            responses += 1
    if not 0 <= responses <= starts <= 96:
        valid = False
    return {
        "completed_response_envelopes_lower_bound": responses if responses <= 96 else 0,
        "durable_start_records_observed": starts if starts <= 96 else 0,
        "provider_call_upper_bound": starts if valid else 96,
        "exact_count_known": valid and responses == starts,
    }


def _environment_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise LiveExperimentRefusal(f"{name} is required")
    path = Path(value)
    if not path.is_absolute():
        raise LiveExperimentRefusal(f"{name} must be an absolute path")
    return path


def load_frozen_inputs(freeze_root: Path) -> dict[str, Any]:
    """Load the standardized freeze layout; producer validation occurs in runner."""

    if not isinstance(freeze_root, Path) or not freeze_root.is_dir() or freeze_root.is_symlink():
        raise LiveExperimentRefusal("freeze root is unavailable")
    try:
        plan_raw = (freeze_root / "plan.json").read_bytes()
        plan = validate_live_q1_plan(plan_raw)
        identities = {
            name: (freeze_root / "identities" / f"{name}.json").read_bytes()
            for name in IDENTITY_NAMES
        }
        provenance = {
            name: (freeze_root / "provenance" / f"{name}.json").read_bytes()
            for name in PROVENANCE_NAMES
        }
        materials = tuple(
            LiveQ1CaseMaterial(
                case["case_id"],
                (freeze_root / "materials" / case["case_id"] / "instruction.txt").read_bytes(),
                (freeze_root / "materials" / case["case_id"] / "model_input.json").read_bytes(),
                (freeze_root / "materials" / case["case_id"] / "response_schema.json").read_bytes(),
                (freeze_root / "materials" / case["case_id"] / "rng.bin").read_bytes(),
                case["max_output_tokens"],
            )
            for case in plan["corpus"]
        )
        return {
            "plan_raw": plan_raw,
            "closure_manifest_raw": (freeze_root / "closure_manifest.json").read_bytes(),
            "marker_raw": (freeze_root / "start_marker.json").read_bytes(),
            "corpus_manifest_raw": (freeze_root / "corpus_manifest.json").read_bytes(),
            "root_genesis_raw": (freeze_root / "root_genesis.json").read_bytes(),
            "identities": identities,
            "provenance": provenance,
            "materials": materials,
        }
    except OSError as error:
        raise LiveExperimentRefusal("freeze input file is unavailable") from error


def _runner_input_file_map(frozen: dict[str, Any]) -> dict[str, bytes]:
    """Rebuild the complete freeze file set consumed by the runner."""

    plan = validate_live_q1_plan(frozen["plan_raw"])
    files = {
        "plan.json": frozen["plan_raw"],
        "closure_manifest.json": frozen["closure_manifest_raw"],
        "start_marker.json": frozen["marker_raw"],
        "corpus_manifest.json": frozen["corpus_manifest_raw"],
        "root_genesis.json": frozen["root_genesis_raw"],
    }
    files.update(
        {
            f"identities/{name}.json": raw
            for name, raw in frozen["identities"].items()
        }
    )
    files.update(
        {
            f"provenance/{name}.json": raw
            for name, raw in frozen["provenance"].items()
        }
    )
    materials = {material.case_id: material for material in frozen["materials"]}
    if len(materials) != 24 or set(materials) != {
        case["case_id"] for case in plan["corpus"]
    }:
        raise LiveExperimentRefusal("freeze material set drifted")
    for case_id, material in materials.items():
        prefix = f"materials/{case_id}/"
        files[prefix + "instruction.txt"] = material.instruction_bytes
        files[prefix + "model_input.json"] = material.model_input_bytes
        files[prefix + "response_schema.json"] = material.response_schema_bytes
        files[prefix + "rng.bin"] = material.rng_bytes
    if any(type(name) is not str or type(raw) is not bytes for name, raw in files.items()):
        raise LiveExperimentRefusal("freeze runner byte set drifted")
    return files


def _write_exclusive(path: Path, raw: bytes) -> None:
    if not path.parent.is_dir() or path.exists() or path.is_symlink():
        raise LiveExperimentRefusal("result path must be a fresh file")
    descriptor, temporary = tempfile.mkstemp(prefix=".q1-result-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def run_live_experiment(spec: LiveQ1Spec, evidence_root: Path) -> dict[str, Any]:
    frozen = load_frozen_inputs(spec.freeze_root)
    if evidence_root.exists() or not evidence_root.parent.is_dir():
        raise LiveExperimentRefusal("evidence root must be fresh")
    plan = parse_canonical(frozen["plan_raw"])
    consumption_root = Path(plan["consumption_registry"]["path"])
    if (
        not consumption_root.is_absolute()
        or not consumption_root.is_dir()
        or consumption_root.is_symlink()
    ):
        raise LiveExperimentRefusal(
            "frozen durable consumption registry is unavailable"
        )
    with LiveQ1Lease(spec) as lease:
        if lease.startup_attestation_raw is None:
            raise LiveExperimentRefusal("lease omitted startup attestation")
        if _runner_input_file_map(frozen) != lease.validated_freeze_files:
            raise LiveExperimentRefusal(
                "preflight freeze bytes differ from the Git-verified lease bytes"
            )
        runner = LiveQ1Runner(
            evidence_root,
            frozen["plan_raw"],
            frozen["marker_raw"],
            frozen["corpus_manifest_raw"],
            frozen["materials"],
            frozen["identities"],
            frozen["provenance"],
            frozen["root_genesis_raw"],
            frozen["closure_manifest_raw"],
            consumption_root=consumption_root,
            lease=lease,
        )
        runner.execute_all()
    verdict = verify(evidence_root, external_registry_root=consumption_root)
    return {
        "schema_version": RESULT_SCHEMA,
        "q1_sha256": sha256(frozen["plan_raw"]).hexdigest(),
        "terminal": verdict["terminal"],
        "provider_or_model_call_bounds": _call_bounds(evidence_root),
        "nonclaims": parse_canonical(frozen["plan_raw"])["nonclaims"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="run one frozen DGX live Q1 under the hswm-run environment"
    )
    for name in (
        "repo-root",
        "expected-commit",
        "expected-tree",
        "publication-ci-receipt",
        "publication-ci-receipt-sha256",
        "freeze-root",
        "plan-sha256",
        "lock-path",
        "container-name",
        "model-snapshot",
    ):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        cache_root = _environment_path("HSWM_CACHE_ROOT")
        output_root = _environment_path("HSWM_OUTPUT_ROOT")
        hf_cache = cache_root / "q1-huggingface"
        compile_cache = cache_root / "q1-compile"
        hf_cache.mkdir(mode=0o700)
        compile_cache.mkdir(mode=0o700)
        spec = LiveQ1Spec(
            repo_root=Path(args.repo_root),
            expected_commit=args.expected_commit,
            expected_tree=args.expected_tree,
            publication_ci_receipt=Path(args.publication_ci_receipt),
            publication_ci_receipt_sha256=args.publication_ci_receipt_sha256,
            freeze_root=Path(args.freeze_root),
            plan_sha256=args.plan_sha256,
            lock_path=Path(args.lock_path),
            container_name=args.container_name,
            model_snapshot=Path(args.model_snapshot),
            hf_cache=hf_cache,
            compile_cache=compile_cache,
        )
        result = run_live_experiment(spec, output_root / "live_q1_evidence")
        raw = canonical_bytes(result)
        _write_exclusive(output_root / "independent_live_q1_result.json", raw)
        print(raw.decode("utf-8"))
        return 2 if result["terminal"] == VOID else 0
    except Exception as error:
        try:
            output_root = _environment_path("HSWM_OUTPUT_ROOT")
            refusal = canonical_bytes(
                {
                    "schema_version": RESULT_SCHEMA,
                    "status": "LIVE_Q1_REFUSED_OR_ABORTED_NO_SCIENTIFIC_CLAIM",
                    "failure_code": type(error).__name__.upper(),
                    "provider_or_model_call_bounds": _call_bounds(
                        output_root / "live_q1_evidence"
                    ),
                }
            )
            _write_exclusive(output_root / "live_q1_refusal.json", refusal)
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
