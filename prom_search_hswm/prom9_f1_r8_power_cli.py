#!/usr/bin/env python3
"""Build and publish one fail-closed HSWM F1 r8 development-power receipt.

The command handles private gold/source preimages.  It therefore exposes only a
generic refusal on stderr and publishes nothing until the environment graph,
the four execution-lock hashes, and the frozen power gates have all passed.
"""
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import sys

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    _read_private_bytes,
    _strict_object,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    EnvironmentPreimageError,
    R8_DEPENDENCY_NAMES,
    load_private_receipt,
    r8_dependency_paths,
    r8_environment_labels,
    verify_r8_preimage_bundle,
)
from prom_search_hswm.prom9_f1_r8_power import (
    BOOTSTRAP,
    DEVELOPMENT_COMPONENTS,
    POWER_DEVELOPMENT_SCHEMA,
    POWER_RECEIPT_SCHEMA,
    POWER_SCENARIOS,
    POWER_SIMULATOR_SCHEMA,
    SELECTION_SEED,
    SELECTED_CLUSTERS,
    TRIALS,
    _load_judge_core,
    build_power_receipt,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_POWER_RECEIPT_SCHEMA = "hswm-prom9-f1-r8-power-operating-characteristic/v3"
ENVIRONMENT_HASH_FIELDS = (
    "environment_receipt_sha256",
    "dependency_receipt_sha256",
    "environment_dependency_compatibility_root_sha256",
    "environment_dependency_bundle_sha256",
)
SENSITIVITY_SCENARIOS = (
    "unequal_cluster",
    "heavy_tail",
    "seed_interaction",
    "carryover",
)
OPERATING_CHARACTERISTIC_KEYS = frozenset(
    {
        "trial_count",
        "selected_cluster_count",
        "mde",
        "target_power",
        "observed_power_at_mde",
        "observed_power_lower_95",
        "null_false_support_rate",
        "null_false_support_upper_95",
        "interval_coverage",
        "interval_coverage_lower_95",
        "expected_interval_width",
        "effect_0_03_support_rate",
        "effect_0_08_support_rate",
        *(
            f"{scenario}_{suffix}"
            for scenario in SENSITIVITY_SCENARIOS
            for suffix in ("support_rate", "support_lower_95", "sensitivity_pass")
        ),
    }
)


class PowerCLIRefusal(RuntimeError):
    """Private power evidence failed a terminal publication gate."""


def _read(path: Path, label: str) -> dict[str, object]:
    return _strict_object(_read_private_bytes(path), label)


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PowerCLIRefusal(f"{label} is not an exact SHA-256 digest")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PowerCLIRefusal(f"{label} is absent or malformed")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PowerCLIRefusal(f"{label} is absent or malformed")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PowerCLIRefusal(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PowerCLIRefusal(f"{label} is not finite")
    return result


def _exact_integer(value: object, expected: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        raise PowerCLIRefusal(f"{label} drifted from the frozen design")
    return value


def verify_measured_environment_bundle(
    bundle: Mapping[str, object],
    *,
    execution_lock: Mapping[str, object],
    manifest: Mapping[str, object],
    expected_paths: Mapping[str, Path],
    repo_root: Path | None = None,
    symposium_repo_root: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, str]]:
    """Verify the exact r8 path/label graph and its four locked identities."""

    environment = _mapping(bundle.get("environment_receipt"), "environment receipt")
    dependency = _mapping(bundle.get("dependency_receipt"), "dependency receipt")
    if set(expected_paths) != set(R8_DEPENDENCY_NAMES) or len(expected_paths) != len(
        R8_DEPENDENCY_NAMES
    ):
        raise PowerCLIRefusal("measured r8 dependency inventory drifted")
    policy = _mapping(execution_lock.get("execution_policy"), "execution policy")
    bundle_labels = _mapping(environment.get("labels"), "environment labels")
    try:
        expected_labels = r8_environment_labels(
            endpoint=_text(policy.get("endpoint"), "execution endpoint"),
            model=_text(manifest.get("model"), "manifest model"),
            model_revision=_text(
                manifest.get("model_revision"), "manifest model revision"
            ),
            run_id=_text(manifest.get("run_id"), "manifest run ID"),
            hswm_commit=_text(execution_lock.get("hswm_commit"), "HSWM commit"),
            symposium_commit=_text(
                bundle_labels.get("symposium_commit"), "SYMPOSIUM commit"
            ),
        )
        verified = verify_r8_preimage_bundle(
            bundle,
            expected_paths=expected_paths,
            expected_labels=expected_labels,
            repo_root=repo_root or Path(__file__).resolve().parents[1],
            symposium_repo_root=symposium_repo_root,
            verify_live=True,
        )
    except EnvironmentPreimageError as error:
        raise PowerCLIRefusal(
            "measured r8 environment/dependency semantics failed"
        ) from error
    hashes = {
        "environment_receipt_sha256": _sha256(
            verified.get("environment_receipt_sha256"), "environment receipt"
        ),
        "dependency_receipt_sha256": _sha256(
            verified.get("dependency_receipt_sha256"), "dependency receipt"
        ),
        "environment_dependency_compatibility_root_sha256": _sha256(
            verified.get("compatibility_root_sha256"),
            "environment/dependency compatibility root",
        ),
        "environment_dependency_bundle_sha256": _sha256(
            verified.get("bundle_sha256"), "environment/dependency bundle"
        ),
    }
    for field, observed in hashes.items():
        if execution_lock.get(field) != observed:
            raise PowerCLIRefusal(f"execution lock {field} drifted")

    return dict(environment), dict(dependency), hashes


def verify_power_operating_characteristics(
    receipt: Mapping[str, object],
    *,
    judge_core_path: Path,
) -> str:
    """Enforce the frozen prospective-judge thresholds before publication."""

    expected_receipt_keys = {
        "schema_version",
        "analysis_input",
        "development_evidence",
        "development_evidence_sha256",
        "development_data_sha256",
        "simulator_sha256",
        "judge_core_sha256",
        "inference_unit",
        "selected_method",
        "minimum_clusters",
        "operating_characteristics",
        "receipt_sha256",
    }
    if set(receipt) != expected_receipt_keys:
        raise PowerCLIRefusal("power receipt shape drifted")
    if (
        POWER_RECEIPT_SCHEMA != EXPECTED_POWER_RECEIPT_SCHEMA
        or receipt.get("schema_version") != EXPECTED_POWER_RECEIPT_SCHEMA
    ):
        raise PowerCLIRefusal("power receipt schema drifted")
    unsigned = dict(receipt)
    declared = _sha256(unsigned.pop("receipt_sha256", None), "power receipt")
    if canonical_sha256(unsigned) != declared:
        raise PowerCLIRefusal("power receipt self-hash drifted")
    for field in (
        "development_evidence_sha256",
        "development_data_sha256",
        "simulator_sha256",
        "judge_core_sha256",
    ):
        _sha256(receipt.get(field), f"power receipt {field}")
    evidence = _mapping(receipt.get("development_evidence"), "development evidence")
    if canonical_sha256(evidence) != receipt.get("development_evidence_sha256"):
        raise PowerCLIRefusal("development evidence self-hash drifted")
    if (
        receipt.get("inference_unit") != "component_cluster_macro"
        or receipt.get("selected_method")
        != "paired_cluster_percentile_bootstrap_v1"
    ):
        raise PowerCLIRefusal("power reducer contract drifted")
    _exact_integer(receipt.get("minimum_clusters"), SELECTED_CLUSTERS, "minimum clusters")

    analysis = _mapping(receipt.get("analysis_input"), "power analysis input")
    if set(analysis) != {
        "schema_version",
        "development_components",
        "simulation_plan",
    } or analysis.get("schema_version") != POWER_DEVELOPMENT_SCHEMA:
        raise PowerCLIRefusal("power analysis-input contract drifted")
    components = analysis.get("development_components")
    if not isinstance(components, list) or len(components) != DEVELOPMENT_COMPONENTS:
        raise PowerCLIRefusal("power development-component count drifted")
    if canonical_sha256(components) != receipt.get("development_data_sha256"):
        raise PowerCLIRefusal("power development-data preimage drifted")
    plan = _mapping(analysis.get("simulation_plan"), "power simulation plan")
    if set(plan) != {
        "schema_version",
        "trials",
        "master_seed",
        "selected_cluster_count",
        "selection_method",
        "mde",
        "target_power",
        "scenarios",
    }:
        raise PowerCLIRefusal("power simulation-plan shape drifted")
    if (
        plan.get("schema_version") != POWER_SIMULATOR_SCHEMA
        or plan.get("master_seed") != SELECTION_SEED
        or plan.get("selection_method")
        != "complete_seed_block_without_replacement/v1"
        or plan.get("scenarios") != list(POWER_SCENARIOS)
    ):
        raise PowerCLIRefusal("power simulation-plan contract drifted")
    _exact_integer(plan.get("trials"), TRIALS, "power simulation trial count")
    _exact_integer(
        plan.get("selected_cluster_count"),
        SELECTED_CLUSTERS,
        "power selected cluster count",
    )
    if _finite(plan.get("mde"), "power MDE") != 0.05 or _finite(
        plan.get("target_power"), "target power"
    ) != 0.80:
        raise PowerCLIRefusal("power MDE or target drifted from the frozen design")

    raw_characteristics = _mapping(
        receipt.get("operating_characteristics"), "power operating characteristics"
    )
    if set(raw_characteristics) != OPERATING_CHARACTERISTIC_KEYS:
        raise PowerCLIRefusal("power operating-characteristic shape drifted")
    _exact_integer(
        raw_characteristics.get("trial_count"), TRIALS, "observed trial count"
    )
    _exact_integer(
        raw_characteristics.get("selected_cluster_count"),
        SELECTED_CLUSTERS,
        "observed selected cluster count",
    )
    try:
        judge = _load_judge_core(judge_core_path)
        judge_core_sha = _sha256(
            judge.judge_core_sha256(judge_core_path), "live judge semantic core"
        )
    except Exception as error:
        raise PowerCLIRefusal("independent power judge verification failed") from error
    if (
        judge_core_sha != receipt.get("judge_core_sha256")
        or judge_core_sha != receipt.get("simulator_sha256")
    ):
        raise PowerCLIRefusal("power receipt targets a different judge semantic core")
    try:
        recomputed = judge._recompute_power_characteristics(
            components,
            plan,
            bootstrap=BOOTSTRAP,
        )
    except Exception as error:
        raise PowerCLIRefusal("independent power replay failed") from error
    if (
        not isinstance(recomputed, Mapping)
        or dict(raw_characteristics) != dict(recomputed)
    ):
        raise PowerCLIRefusal(
            "power operating characteristics were not independently replayed"
        )
    numeric: dict[str, float] = {}
    for key, raw in raw_characteristics.items():
        if key in {"trial_count", "selected_cluster_count"} or key.endswith(
            "_sensitivity_pass"
        ):
            continue
        numeric[key] = _finite(raw, f"operating characteristic {key}")
    for key, value in numeric.items():
        if (
            key.endswith("_rate")
            or key.endswith("_lower_95")
            or key.endswith("_upper_95")
            or key in {"observed_power_at_mde", "interval_coverage", "target_power"}
        ) and not 0.0 <= value <= 1.0:
            raise PowerCLIRefusal(f"operating characteristic {key} is outside [0,1]")

    if numeric["mde"] != 0.05 or numeric["target_power"] != 0.80:
        raise PowerCLIRefusal("reported power MDE or target drifted")
    if numeric["observed_power_lower_95"] > numeric["observed_power_at_mde"]:
        raise PowerCLIRefusal("power lower confidence bound exceeds its estimate")
    if numeric["null_false_support_rate"] > numeric["null_false_support_upper_95"]:
        raise PowerCLIRefusal("null upper confidence bound is incoherent")
    if numeric["interval_coverage_lower_95"] > numeric["interval_coverage"]:
        raise PowerCLIRefusal("coverage lower confidence bound exceeds its estimate")

    target = numeric["target_power"]
    if (
        numeric["observed_power_at_mde"] < target
        or numeric["observed_power_lower_95"] < target
        or numeric["null_false_support_upper_95"] > 0.05
        or numeric["interval_coverage"] < 0.95
        or not 0.0 < numeric["expected_interval_width"] <= 0.10
    ):
        raise PowerCLIRefusal("power operating characteristics miss frozen thresholds")
    for scenario in SENSITIVITY_SCENARIOS:
        rate = numeric[f"{scenario}_support_rate"]
        lower = numeric[f"{scenario}_support_lower_95"]
        if lower > rate:
            raise PowerCLIRefusal(f"{scenario} sensitivity confidence bound is incoherent")
        if (
            raw_characteristics.get(f"{scenario}_sensitivity_pass") is not True
            or lower < target
        ):
            raise PowerCLIRefusal(f"{scenario} sensitivity gate failed")
    return declared


def verify_receipt_environment_hashes(
    receipt: Mapping[str, object], expected_hashes: Mapping[str, str]
) -> None:
    """Require exact readback of all four measured environment graph hashes."""

    if set(expected_hashes) != set(ENVIRONMENT_HASH_FIELDS):
        raise PowerCLIRefusal("expected environment hash inventory drifted")
    evidence = _mapping(receipt.get("development_evidence"), "development evidence")
    artifacts = _mapping(evidence.get("artifact_receipts"), "artifact receipts")
    for field in ENVIRONMENT_HASH_FIELDS:
        expected = _sha256(expected_hashes.get(field), f"expected {field}")
        if artifacts.get(field) != expected:
            raise PowerCLIRefusal(f"power receipt {field} drifted")


def write_validated_power_receipt(
    path: Path,
    receipt: Mapping[str, object],
    *,
    expected_environment_hashes: Mapping[str, str],
    judge_core_path: Path,
) -> None:
    """Run every terminal gate before the first-write-wins filesystem effect."""

    verify_receipt_environment_hashes(receipt, expected_environment_hashes)
    verify_power_operating_characteristics(
        receipt,
        judge_core_path=judge_core_path,
    )
    write_private_once(path, receipt)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execution-lock", type=Path, required=True)
    parser.add_argument("--public-source-receipt", type=Path, required=True)
    parser.add_argument("--gold-source-receipt", type=Path, required=True)
    parser.add_argument("--selection-receipt", type=Path, required=True)
    parser.add_argument("--prior-exposure-receipt", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--evaluator-receipt", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--db-genesis-receipt", type=Path, required=True)
    parser.add_argument("--environment-dependency-bundle", type=Path, required=True)
    parser.add_argument("--symposium-repo-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--judge-core", type=Path, required=True)
    parser.add_argument("--result-contract", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--model-catalog", type=Path, required=True)
    parser.add_argument("--model-weight-receipt", type=Path, required=True)
    parser.add_argument("--python-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = _read(args.manifest, "development manifest")
        execution_lock = _read(args.execution_lock, "development execution lock")
        environment_bundle = load_private_receipt(
            args.environment_dependency_bundle, verify_live=False
        )
        expected_dependency_paths = r8_dependency_paths(
            protocol_path=args.protocol,
            judge_core_path=args.judge_core,
            result_contract_path=args.result_contract,
            tokenizer_dir=args.tokenizer_dir,
            model_catalog_path=args.model_catalog,
            model_weight_receipt_path=args.model_weight_receipt,
            python_lock_path=args.python_lock,
        )
        _, _, environment_hashes = verify_measured_environment_bundle(
            environment_bundle,
            execution_lock=execution_lock,
            manifest=manifest,
            expected_paths=expected_dependency_paths,
            symposium_repo_root=args.symposium_repo_root,
        )
        receipt = build_power_receipt(
            manifest=manifest,
            execution_lock=execution_lock,
            public_source_receipt=_read(
                args.public_source_receipt, "development public-source receipt"
            ),
            gold_source_receipt=_read(
                args.gold_source_receipt, "development gold-source receipt"
            ),
            selection_receipt=_read(
                args.selection_receipt, "cohort selection receipt"
            ),
            prior_exposure_receipt=_read(
                args.prior_exposure_receipt, "prior-exposure receipt"
            ),
            suite=_read(args.suite, "terminal development suite"),
            evaluator_receipt=_read(args.evaluator_receipt, "evaluator receipt"),
            gold=_read(args.gold, "private development gold"),
            db_genesis_receipt=_read(args.db_genesis_receipt, "DB genesis receipt"),
            environment_dependency_bundle=environment_bundle,
            judge_core_path=args.judge_core,
        )
        write_validated_power_receipt(
            args.output,
            receipt,
            expected_environment_hashes=environment_hashes,
            judge_core_path=args.judge_core,
        )
    except Exception:
        # Never echo an exception: it could include answer-bearing preimages.
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "TERMINAL_DEVELOPMENT_POWER_RECEIPT",
                "receipt_sha256": receipt["receipt_sha256"],
                "development_components": len(
                    receipt["analysis_input"]["development_components"]
                ),
                "minimum_clusters": receipt["minimum_clusters"],
                "environment_dependency_bundle_sha256": environment_hashes[
                    "environment_dependency_bundle_sha256"
                ],
                "operating_characteristics": receipt["operating_characteristics"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ENVIRONMENT_HASH_FIELDS",
    "OPERATING_CHARACTERISTIC_KEYS",
    "PowerCLIRefusal",
    "main",
    "verify_measured_environment_bundle",
    "verify_power_operating_characteristics",
    "verify_receipt_environment_hashes",
    "write_validated_power_receipt",
]
