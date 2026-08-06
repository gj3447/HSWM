#!/usr/bin/env python3
"""Build and publish one fail-closed HSWM F1 r8 c801 utility-power receipt.

The command handles private gold/source preimages.  It therefore exposes only a
generic refusal on stderr and publishes nothing until the environment graph,
the four execution-lock hashes, and the frozen power gates have all passed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import stat
import sys

from prom_search_hswm.hswm_result_spool import (
    ResultSpoolError,
    load_model_deployment_binding,
)
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    _strict_object,
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_c801_exposure import (
    C801_DEVELOPMENT_RUN_ID,
    merge_c801_exposure_boundaries,
    verify_f1_r8_successor_exposure_set_v2,
)
from prom_search_hswm.prom9_f1_r8_envelope_v6 import (
    _read_bound_selection_json,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    EnvironmentPreimageError,
    R8_C801_DEPENDENCY_NAMES,
    load_private_receipt,
    r8_c801_dependency_paths,
    r8_environment_labels,
    verify_r8_c801_preimage_bundle,
)
from prom_search_hswm.prom9_f1_r8_power_v6 import (
    BOOTSTRAP_V6,
    DEVELOPMENT_COMPONENTS_V6,
    MDE_V6,
    POWER_DEVELOPMENT_SCHEMA_V6,
    POWER_EVIDENCE_SCHEMA_V6,
    POWER_RECEIPT_SCHEMA_V6,
    POWER_SCENARIOS_V6,
    POWER_SIMULATION_SEED,
    POWER_SIMULATOR_SCHEMA_V6,
    SELECTED_CLUSTERS_V6,
    TARGET_POWER_V6,
    TRIALS_V6,
    UTILITY_COST_C,
    UTILITY_METRIC,
    PowerRefusal,
    _load_c801_judge_core,
    build_power_receipt_v6,
)
from prom_search_hswm.prom9_f1_r8_selection_v5 import (
    verify_selection_receipt_v5,
)
from prom_search_hswm.prom9_f1_r8_runner import (
    _validate_execution_policy_for_run,
    read_stable_json,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_POWER_RECEIPT_SCHEMA = POWER_RECEIPT_SCHEMA_V6
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


def _read_private_bytes_bounded(path: Path, label: str, max_bytes: int) -> bytes:
    """Capture one private regular file without allocating past its ceiling."""

    target = Path(path)
    try:
        info = target.lstat()
    except OSError as error:
        raise PowerCLIRefusal(f"{label} is unavailable") from error
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) & 0o077
        or info.st_size < 0
        or info.st_size > max_bytes
    ):
        raise PowerCLIRefusal(f"{label} is not a bounded private regular file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as error:
        raise PowerCLIRefusal(f"{label} cannot be opened") from error
    chunks: list[bytes] = []
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != info.st_dev
            or opened.st_ino != info.st_ino
            or stat.S_IMODE(opened.st_mode) & 0o077
            or opened.st_size != info.st_size
            or opened.st_size > max_bytes
        ):
            raise PowerCLIRefusal(f"{label} changed before capture")
        remaining = opened.st_size
        while remaining:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                raise PowerCLIRefusal(f"{label} was truncated during capture")
            chunks.append(block)
            remaining -= len(block)
        if os.read(descriptor, 1):
            raise PowerCLIRefusal(f"{label} grew during capture")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(info, field) != getattr(after, field) for field in identity_fields):
        raise PowerCLIRefusal(f"{label} changed during capture")
    return b"".join(chunks)


def _read(
    path: Path, label: str, *, max_bytes: int = 128 * 1024 * 1024
) -> dict[str, object]:
    return _strict_object(_read_private_bytes_bounded(path, label, max_bytes), label)


def _read_public(path: Path, label: str) -> dict[str, object]:
    try:
        value, _file_sha256 = read_stable_json(path, label)
    except Exception as error:
        raise PowerCLIRefusal(f"cannot capture stable {label}") from error
    return value


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


def _verify_model_deployment_receipt(
    path: Path,
    *,
    execution_lock: Mapping[str, object],
    manifest: Mapping[str, object],
) -> dict[str, str]:
    """Verify the official deployment receipt and its frozen lock projection."""

    upstream_endpoint = _text(
        execution_lock.get("upstream_endpoint"), "model upstream endpoint"
    )
    model = _text(manifest.get("model"), "manifest model")
    model_revision = _text(
        manifest.get("model_revision"), "manifest model revision"
    )
    try:
        binding = load_model_deployment_binding(
            path,
            upstream_endpoint=upstream_endpoint,
            served_model=model,
            model_revision=model_revision,
            verify_live_process=False,
        )
    except ResultSpoolError as error:
        raise PowerCLIRefusal("model deployment receipt semantics failed") from error
    observed = {
        "upstream_endpoint": binding.upstream_endpoint,
        "deployment_receipt_sha256": binding.deployment_receipt_sha256,
        "deployment_id": binding.deployment_id,
        "served_model": binding.served_model,
        "model_revision": binding.model_revision,
    }
    if (
        execution_lock.get("model") != model
        or any(execution_lock.get(field) != value for field, value in observed.items())
    ):
        raise PowerCLIRefusal(
            "model deployment receipt differs from the frozen execution lock"
        )
    return observed


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
    if (
        len(expected_paths) != len(R8_C801_DEPENDENCY_NAMES)
        or set(expected_paths) != set(R8_C801_DEPENDENCY_NAMES)
    ):
        raise PowerCLIRefusal("measured r8 dependency inventory drifted")
    deployment_receipt_path = expected_paths.get("model_deployment_receipt")
    if not isinstance(deployment_receipt_path, Path):
        raise PowerCLIRefusal("model deployment receipt path is absent")
    _verify_model_deployment_receipt(
        deployment_receipt_path,
        execution_lock=execution_lock,
        manifest=manifest,
    )
    policy = _mapping(execution_lock.get("execution_policy"), "execution policy")
    bundle_labels = _mapping(environment.get("labels"), "environment labels")
    try:
        expected_labels = r8_environment_labels(
            spool_endpoint=_text(
                policy.get("endpoint"), "execution spool endpoint"
            ),
            model_upstream_endpoint=_text(
                execution_lock.get("upstream_endpoint"),
                "model upstream endpoint",
            ),
            model_deployment_receipt_sha256=_sha256(
                execution_lock.get("deployment_receipt_sha256"),
                "model deployment receipt",
            ),
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
        verified = verify_r8_c801_preimage_bundle(
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
        "metric",
        "utility_cost_c",
        "receipt_sha256",
    }
    if set(receipt) != expected_receipt_keys:
        raise PowerCLIRefusal("power receipt shape drifted")
    if (
        POWER_RECEIPT_SCHEMA_V6 != EXPECTED_POWER_RECEIPT_SCHEMA
        or receipt.get("schema_version") != EXPECTED_POWER_RECEIPT_SCHEMA
        or receipt.get("metric") != UTILITY_METRIC
        or receipt.get("utility_cost_c") != UTILITY_COST_C
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
    expected_evidence_keys = {
        "schema_version",
        "manifest",
        "execution_lock",
        "public_source_receipt",
        "selection_receipt",
        "predecessor_selection_receipt",
        "gold_source_receipt",
        "prior_exposure_receipt",
        "aborted_attempt_exposure_receipt",
        "suite",
        "evaluator_receipt",
        "gold",
        "db_genesis_receipt",
        "environment_dependency_bundle",
        "artifact_receipts",
    }
    if (
        set(evidence) != expected_evidence_keys
        or evidence.get("schema_version") != POWER_EVIDENCE_SCHEMA_V6
        or canonical_sha256(evidence) != receipt.get("development_evidence_sha256")
    ):
        raise PowerCLIRefusal("development evidence self-hash drifted")
    if (
        receipt.get("inference_unit") != "component_cluster_macro"
        or receipt.get("selected_method")
        != "paired_cluster_percentile_bootstrap_v1"
    ):
        raise PowerCLIRefusal("power reducer contract drifted")
    _exact_integer(
        receipt.get("minimum_clusters"),
        SELECTED_CLUSTERS_V6,
        "minimum clusters",
    )

    analysis = _mapping(receipt.get("analysis_input"), "power analysis input")
    if set(analysis) != {
        "schema_version",
        "development_components",
        "simulation_plan",
    } or analysis.get("schema_version") != POWER_DEVELOPMENT_SCHEMA_V6:
        raise PowerCLIRefusal("power analysis-input contract drifted")
    components = analysis.get("development_components")
    if (
        not isinstance(components, list)
        or len(components) != DEVELOPMENT_COMPONENTS_V6
    ):
        raise PowerCLIRefusal("power development-component count drifted")
    if canonical_sha256(components) != receipt.get("development_data_sha256"):
        raise PowerCLIRefusal("power development-data preimage drifted")
    execution_lock = _mapping(
        evidence.get("execution_lock"), "development execution lock"
    )
    if execution_lock.get("run_id") != C801_DEVELOPMENT_RUN_ID:
        raise PowerCLIRefusal("power receipt is not c801 development evidence")
    try:
        execution_policy = _validate_execution_policy_for_run(
            execution_lock.get("execution_policy"),
            run_id=execution_lock.get("run_id"),
        )
    except Exception as error:
        raise PowerCLIRefusal("c801 execution policy drifted") from error
    suite = _mapping(evidence.get("suite"), "terminal development suite")
    if (
        suite.get("execution_policy") != execution_policy
        or suite.get("max_workers") != execution_policy.get("max_workers")
    ):
        raise PowerCLIRefusal("c801 terminal execution policy drifted")
    environment_bundle = _mapping(
        evidence.get("environment_dependency_bundle"),
        "environment/dependency bundle",
    )
    dependency_receipt = _mapping(
        environment_bundle.get("dependency_receipt"), "dependency receipt"
    )
    dependency_files = _mapping(
        dependency_receipt.get("files"), "dependency files"
    )
    judge_row = _mapping(dependency_files.get("judge_core"), "judge dependency")
    expected_judge_file_sha = _sha256(
        execution_lock.get("judge_core_file_sha256"),
        "execution-lock judge file",
    )
    expected_derivation_sha = _sha256(
        execution_lock.get("token_envelope_derivation_receipt_sha256"),
        "execution-lock token-envelope derivation receipt",
    )
    if judge_row.get("sha256") != expected_judge_file_sha:
        raise PowerCLIRefusal("judge file differs from the frozen dependency graph")
    try:
        judge = _load_c801_judge_core(
            judge_core_path,
            expected_file_sha256=expected_judge_file_sha,
            expected_derivation_sha256=expected_derivation_sha,
        )
        selection = _mapping(
            evidence.get("selection_receipt"), "development selection receipt"
        )
        rederived_components = judge._derive_power_development_components(
            evidence,
            selection=selection,
        )
    except (
        PowerCLIRefusal,
        PowerRefusal,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise PowerCLIRefusal(
            "development components were not rederived from evidence"
        ) from error
    if canonical_json(components) != canonical_json(rederived_components):
        raise PowerCLIRefusal(
            "development components were not rederived from evidence"
        )
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
        plan.get("schema_version") != POWER_SIMULATOR_SCHEMA_V6
        or plan.get("master_seed") != POWER_SIMULATION_SEED
        or plan.get("selection_method")
        != "complete_seed_block_without_replacement/v1"
        or plan.get("scenarios") != list(POWER_SCENARIOS_V6)
    ):
        raise PowerCLIRefusal("power simulation-plan contract drifted")
    _exact_integer(
        plan.get("trials"), TRIALS_V6, "power simulation trial count"
    )
    _exact_integer(
        plan.get("selected_cluster_count"),
        SELECTED_CLUSTERS_V6,
        "power selected cluster count",
    )
    if _finite(plan.get("mde"), "power MDE") != MDE_V6 or _finite(
        plan.get("target_power"), "target power"
    ) != TARGET_POWER_V6:
        raise PowerCLIRefusal("power MDE or target drifted from the frozen design")

    raw_characteristics = _mapping(
        receipt.get("operating_characteristics"), "power operating characteristics"
    )
    if set(raw_characteristics) != OPERATING_CHARACTERISTIC_KEYS:
        raise PowerCLIRefusal("power operating-characteristic shape drifted")
    _exact_integer(
        raw_characteristics.get("trial_count"),
        TRIALS_V6,
        "observed trial count",
    )
    _exact_integer(
        raw_characteristics.get("selected_cluster_count"),
        SELECTED_CLUSTERS_V6,
        "observed selected cluster count",
    )
    judge_core_sha = _sha256(
        getattr(judge, "__hswm_captured_core_sha256__", None),
        "captured judge semantic core",
    )
    if (
        judge_core_sha != receipt.get("judge_core_sha256")
        or judge_core_sha != receipt.get("simulator_sha256")
    ):
        raise PowerCLIRefusal("power receipt targets a different judge semantic core")
    try:
        recomputed = judge._recompute_power_characteristics(
            components,
            plan,
            bootstrap=BOOTSTRAP_V6,
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

    if (
        numeric["mde"] != MDE_V6
        or numeric["target_power"] != TARGET_POWER_V6
    ):
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


def verify_receipt_aborted_attempt_exposure_binding(
    receipt: Mapping[str, object],
) -> str:
    """Exact-verify the c801 successor exposure and predecessor boundary."""

    evidence = _mapping(receipt.get("development_evidence"), "development evidence")
    incident = _mapping(
        evidence.get("aborted_attempt_exposure_receipt"),
        "aborted-attempt exposure receipt",
    )
    try:
        incident_sha256 = verify_f1_r8_successor_exposure_set_v2(incident)
    except Exception as error:
        raise PowerCLIRefusal(
            "aborted-attempt exposure receipt failed exact verification"
        ) from error

    artifacts = _mapping(evidence.get("artifact_receipts"), "artifact receipts")
    selection = _mapping(evidence.get("selection_receipt"), "selection receipt")
    predecessor = _mapping(
        evidence.get("predecessor_selection_receipt"),
        "predecessor selection receipt",
    )
    execution_lock = _mapping(evidence.get("execution_lock"), "execution lock")
    prior = _mapping(
        evidence.get("prior_exposure_receipt"), "prior-exposure receipt"
    )
    try:
        prior_sha256 = verify_prior_exposure_receipt(prior)
        predecessor_sha256 = verify_selection_receipt_v5(predecessor)
        boundary = merge_c801_exposure_boundaries(prior, incident)
    except Exception as error:
        raise PowerCLIRefusal(
            "prior-exposure receipt failed exact verification"
        ) from error
    for container, label in (
        (artifacts, "artifact receipts"),
        (selection, "selection receipt"),
        (execution_lock, "execution lock"),
    ):
        if (
            container.get("prior_exposure_receipt_sha256") != prior_sha256
            or container.get("aborted_attempt_exposure_receipt_sha256")
            != incident_sha256
        ):
            raise PowerCLIRefusal(
                f"{label} exposure receipt binding drifted"
            )
    if (
        selection.get("predecessor_selection_receipt_sha256")
        != predecessor_sha256
        or artifacts.get("predecessor_selection_receipt_sha256")
        != predecessor_sha256
    ):
        raise PowerCLIRefusal("predecessor selection binding drifted")
    for lock_field, boundary_field in (
        ("forbidden_prior_item_ids", "item_ids"),
        ("forbidden_prior_source_entity_ids", "source_entity_ids"),
        ("forbidden_prior_component_ids", "component_ids"),
    ):
        if execution_lock.get(lock_field) != boundary.get(boundary_field):
            raise PowerCLIRefusal(
                "execution-lock forbidden exposure union verification failed"
            )
    return incident_sha256


def write_validated_power_receipt(
    path: Path,
    receipt: Mapping[str, object],
    *,
    expected_environment_hashes: Mapping[str, str],
    judge_core_path: Path,
) -> None:
    """Run every terminal gate before the first-write-wins filesystem effect."""

    verify_receipt_aborted_attempt_exposure_binding(receipt)
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
    parser.add_argument(
        "--predecessor-selection-receipt", type=Path, required=True
    )
    parser.add_argument("--prior-exposure-receipt", type=Path, required=True)
    parser.add_argument(
        "--aborted-attempt-exposure-receipt", type=Path, required=True
    )
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
    parser.add_argument(
        "--model-deployment-receipt",
        dest="model_weight_receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--python-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = _read(args.manifest, "development manifest")
        execution_lock = _read(args.execution_lock, "development execution lock")
        environment_bundle = load_private_receipt(
            args.environment_dependency_bundle, verify_live=False
        )
        expected_dependency_paths = r8_c801_dependency_paths(
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
        selection, _selection_file_sha = _read_bound_selection_json(
            args.selection_receipt, "v6 cohort selection receipt"
        )
        predecessor, _predecessor_file_sha = _read_bound_selection_json(
            args.predecessor_selection_receipt,
            "predecessor selection receipt",
        )
        receipt = build_power_receipt_v6(
            manifest=manifest,
            execution_lock=execution_lock,
            public_source_receipt=_read(
                args.public_source_receipt, "development public-source receipt"
            ),
            gold_source_receipt=_read(
                args.gold_source_receipt,
                "development gold-source receipt",
                max_bytes=512 * 1024 * 1024,
            ),
            selection_receipt=selection,
            predecessor_selection_receipt=predecessor,
            prior_exposure_receipt=_read(
                args.prior_exposure_receipt, "prior-exposure receipt"
            ),
            aborted_attempt_exposure_receipt=_read_public(
                args.aborted_attempt_exposure_receipt,
                "aborted-attempt exposure receipt",
            ),
            suite=_read(
                args.suite,
                "terminal development suite",
                max_bytes=1024 * 1024 * 1024,
            ),
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
    "verify_receipt_aborted_attempt_exposure_binding",
    "verify_receipt_environment_hashes",
    "write_validated_power_receipt",
]
