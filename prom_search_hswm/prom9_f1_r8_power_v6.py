#!/usr/bin/env python3
"""Build the fail-closed c801 utility-power receipt.

This generation-only producer accepts the v6 selection, the quarantined c800
successor-exposure set, and a fresh c801 judge.  The independent judge derives
all +1/-2/0 utility contrasts and replays the operating characteristics; this
module only assembles and cross-binds the private development evidence graph.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from types import ModuleType
from collections.abc import Mapping
from pathlib import Path

from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
)
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import (
    verify_prior_exposure_receipt,
)
from prom_search_hswm.prom9_f1_r8_c801_exposure import (
    C801_DEVELOPMENT_RUN_ID,
    C801_SEALED_RUN_ID,
    F1_R8_SUCCESSOR_EXPOSURE_SET_SCHEMA_V2,
    merge_c801_exposure_boundaries,
    verify_f1_r8_successor_exposure_set_v2,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    R8_C801_DEPENDENCY_NAMES,
    verify_dependency_receipt,
    verify_environment_receipt,
    verify_preimage_bundle,
)
from prom_search_hswm.prom9_f1_r8_power import (
    PowerRefusal,
    _component_overlaps_boundary,
    _decode_gold_selected_block,
    _manifest_source_entity_ids,
    _self_hash,
    _verify_deployment_environment_binding,
)
from prom_search_hswm.prom9_f1_r8_selection_v5 import (
    verify_selection_receipt_v5,
)
from prom_search_hswm.prom9_f1_r8_selection_v6 import (
    DEVELOPMENT_COMPONENTS_V6,
    SELECTION_SCHEMA_V6,
    replay_selection_receipt_v6,
    verify_gold_source_receipt_v6,
)
from prom_search_hswm.prom9_f1_r8_runner import (
    C801_MAX_DELIVERY_ATTEMPTS,
    C801_MAX_WORKERS,
    C801_TIMEOUT_SECONDS,
    _validate_execution_policy_for_run,
)


POWER_RECEIPT_SCHEMA_V6 = (
    "hswm-prom9-f1-r8-power-operating-characteristic/v2-utility"
)
POWER_DEVELOPMENT_SCHEMA_V6 = (
    "hswm-prom9-f1-r8-power-v2-development-data/v1"
)
POWER_EVIDENCE_SCHEMA_V6 = (
    "hswm-prom9-f1-r8-power-v2-development-evidence/v1"
)
POWER_SIMULATOR_SCHEMA_V6 = (
    "hswm-prom9-f1-r8-power-v2-simulator-spec/v1"
)
UTILITY_METRIC = "utility_c2_min_paired_component_cluster_bootstrap_lcb"
UTILITY_COST_C = 2
POWER_SIMULATION_SEED = 20260728
SELECTED_CLUSTERS_V6 = 800
TRIALS_V6 = 60
MDE_V6 = 0.15
TARGET_POWER_V6 = 0.80
BOOTSTRAP_V6 = {
    "reps": 10000,
    "seed": 20260724,
    "lower_index": 249,
    "upper_index": 9749,
    "paired": True,
    "unit": "component_cluster_macro",
    "method": "paired_cluster_percentile_bootstrap_v1",
    "minimum_clusters": SELECTED_CLUSTERS_V6,
    "metric": "min_of_four_paired_cluster_bootstrap_lcbs",
}
POWER_SCENARIOS_V6 = (
    "null",
    "effect_0_03",
    "mde",
    "effect_0_08",
    "coverage",
    "unequal_cluster",
    "heavy_tail",
    "seed_interaction",
    "carryover",
)
CONTROLS = (FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)
ARMS = (TYPED_ARM, *CONTROLS)
JUDGE_CAPABILITY_V1 = {
    "schema_version": "hswm-f1-r8-c801-judge-capability/v1",
    "development_run_id": C801_DEVELOPMENT_RUN_ID,
    "sealed_run_id": C801_SEALED_RUN_ID,
    "selection_schema": SELECTION_SCHEMA_V6,
    "successor_exposure_schema": F1_R8_SUCCESSOR_EXPOSURE_SET_SCHEMA_V2,
    "power_receipt_schema": POWER_RECEIPT_SCHEMA_V6,
    "metric": UTILITY_METRIC,
    "utility_cost_c": UTILITY_COST_C,
    "development_components": DEVELOPMENT_COMPONENTS_V6,
    "confirmatory_components": 800,
    "minimum_clusters": SELECTED_CLUSTERS_V6,
    "mde": MDE_V6,
    "target_power": TARGET_POWER_V6,
    "max_workers": C801_MAX_WORKERS,
    "timeout_seconds": C801_TIMEOUT_SECONDS,
    "max_delivery_attempts": C801_MAX_DELIVERY_ATTEMPTS,
    # The prospective judge changes this field from None to the exact
    # zero-call derivation receipt.  Fixed capability fields remain immutable.
    "token_envelope_derivation_receipt_sha256": None,
}
_MAX_JUDGE_BYTES = 8 * 1024 * 1024
_JUDGE_LOCK_ANCHOR = "__F1_R8_MEASUREMENT_LOCK_SHA256_UNFROZEN__"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _validate_c801_judge_capability_value(
    value: object, *, expected_derivation_sha256: str | None = None
) -> dict[str, object]:
    """Validate fixed judge authority plus its prospective derivation pin."""

    if not isinstance(value, Mapping) or set(value) != set(JUDGE_CAPABILITY_V1):
        raise PowerRefusal("frozen judge is not c801 scientific authority")
    dynamic_field = "token_envelope_derivation_receipt_sha256"
    if any(
        value.get(field) != expected
        for field, expected in JUDGE_CAPABILITY_V1.items()
        if field != dynamic_field
    ):
        raise PowerRefusal("frozen judge is not c801 scientific authority")
    declared = value.get(dynamic_field)
    if expected_derivation_sha256 is None:
        if declared is not None and (
            not isinstance(declared, str) or _SHA256.fullmatch(declared) is None
        ):
            raise PowerRefusal("frozen judge derivation capability is malformed")
    elif (
        _SHA256.fullmatch(expected_derivation_sha256) is None
        or declared != expected_derivation_sha256
    ):
        raise PowerRefusal(
            "frozen judge derivation capability differs from the execution lock"
        )
    return dict(value)


def _capture_judge_bytes(path: Path) -> tuple[bytes, str, str]:
    """Capture one bounded regular-file snapshot and both judge identities."""

    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise PowerRefusal("cannot open frozen c801 judge") from error
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > _MAX_JUDGE_BYTES
        ):
            raise PowerRefusal("frozen c801 judge is not a bounded regular file")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                raise PowerRefusal("frozen c801 judge was truncated during capture")
            chunks.append(block)
            remaining -= len(block)
        if os.read(descriptor, 1):
            raise PowerRefusal("frozen c801 judge grew during capture")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in identity_fields):
        raise PowerRefusal("frozen c801 judge changed during capture")
    raw = b"".join(chunks)
    try:
        source = raw.decode("utf-8")
    except UnicodeError as error:
        raise PowerRefusal("frozen c801 judge is not UTF-8") from error
    pattern = re.compile(
        r'^EXPECTED_MEASUREMENT_LOCK_SHA256 = "(?:[0-9a-f]{64}|'
        + re.escape(_JUDGE_LOCK_ANCHOR)
        + r')"$',
        re.MULTILINE,
    )
    normalized, count = pattern.subn(
        f'EXPECTED_MEASUREMENT_LOCK_SHA256 = "{_JUDGE_LOCK_ANCHOR}"',
        source,
    )
    if count != 1:
        raise PowerRefusal("frozen c801 judge lock anchor is ambiguous")
    return (
        raw,
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def _load_c801_judge_core(
    path: Path,
    *,
    expected_file_sha256: str | None = None,
    expected_derivation_sha256: str | None = None,
):
    raw, file_sha256, core_sha256 = _capture_judge_bytes(path)
    if expected_file_sha256 is not None and file_sha256 != expected_file_sha256:
        raise PowerRefusal("frozen c801 judge differs from its dependency receipt")
    module = ModuleType("hswm_f1_r8_c801_frozen_judge")
    module.__file__ = str(path)
    module.__package__ = ""
    try:
        code = compile(raw, str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except Exception as error:
        raise PowerRefusal("cannot import frozen c801 judge") from error
    for name in (
        "judge_core_sha256",
        "c801_preflight_contract",
        "_derive_power_development_components",
        "_recompute_power_characteristics",
    ):
        if not callable(getattr(module, name, None)):
            raise PowerRefusal(f"frozen c801 judge lacks {name}")
    try:
        capability = module.c801_preflight_contract()
    except Exception as error:
        raise PowerRefusal("frozen c801 judge capability preflight failed") from error
    _validate_c801_judge_capability_value(
        capability, expected_derivation_sha256=expected_derivation_sha256
    )
    module.__hswm_captured_file_sha256__ = file_sha256
    module.__hswm_captured_core_sha256__ = core_sha256
    return module


def _dependency_files(
    bundle: Mapping[str, object],
) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    environment = bundle.get("environment_receipt")
    dependencies = bundle.get("dependency_receipt")
    files = dependencies.get("files") if isinstance(dependencies, Mapping) else None
    if (
        not isinstance(environment, Mapping)
        or not isinstance(dependencies, Mapping)
        or not isinstance(files, Mapping)
        or len(files) != len(R8_C801_DEPENDENCY_NAMES)
        or set(files) != set(R8_C801_DEPENDENCY_NAMES)
    ):
        raise PowerRefusal("c801 environment/dependency entries are absent or drifted")
    return environment, dependencies, files


def build_power_receipt_v6(
    *,
    manifest: Mapping[str, object],
    execution_lock: Mapping[str, object],
    public_source_receipt: Mapping[str, object],
    selection_receipt: Mapping[str, object],
    predecessor_selection_receipt: Mapping[str, object],
    gold_source_receipt: Mapping[str, object],
    prior_exposure_receipt: Mapping[str, object],
    aborted_attempt_exposure_receipt: Mapping[str, object],
    suite: Mapping[str, object],
    evaluator_receipt: Mapping[str, object],
    gold: Mapping[str, object],
    db_genesis_receipt: Mapping[str, object],
    environment_dependency_bundle: Mapping[str, object],
    judge_core_path: Path,
) -> dict[str, object]:
    """Assemble one c801 development receipt without emitting private data."""

    from prom_search_hswm.prom9_f1_r8_runner import verify_suite_v3_without_gold
    from prom_search_hswm.prom9_f1_r8_source import (
        EVALUATOR_SEAL_SCHEMA,
        GOLD_SCHEMA,
        SOURCE_RECEIPT_SCHEMA,
        verify_evaluator_seal,
        verify_public_source_receipt,
    )
    from prom_search_hswm.prom_f1_function_network import _verify_token_blocks

    prior_sha = verify_prior_exposure_receipt(prior_exposure_receipt)
    successor_sha = verify_f1_r8_successor_exposure_set_v2(
        aborted_attempt_exposure_receipt
    )
    predecessor_sha = verify_selection_receipt_v5(
        predecessor_selection_receipt
    )
    selection_sha = replay_selection_receipt_v6(
        selection_receipt,
        prior_receipt=prior_exposure_receipt,
        successor_exposure_set=aborted_attempt_exposure_receipt,
        predecessor_selection=predecessor_selection_receipt,
    )
    exposure_boundary = merge_c801_exposure_boundaries(
        prior_exposure_receipt, aborted_attempt_exposure_receipt
    )
    if (
        selection_receipt.get("schema_version") != SELECTION_SCHEMA_V6
        or selection_receipt.get("prior_exposure_receipt_sha256") != prior_sha
        or selection_receipt.get("aborted_attempt_exposure_receipt_sha256")
        != successor_sha
        or selection_receipt.get("predecessor_selection_receipt_sha256")
        != predecessor_sha
        or manifest.get("run_id") != C801_DEVELOPMENT_RUN_ID
        or execution_lock.get("run_id") != C801_DEVELOPMENT_RUN_ID
        or manifest.get("mode") != "development"
        or execution_lock.get("mode") != "development"
        or execution_lock.get("purpose") != "DEVELOPMENT_POWER_PILOT"
    ):
        raise PowerRefusal("power inputs are not the ratified c801 development graph")
    try:
        execution_policy = _validate_execution_policy_for_run(
            execution_lock.get("execution_policy"),
            run_id=execution_lock.get("run_id"),
        )
    except Exception as error:
        raise PowerRefusal("c801 execution policy drifted") from error
    for lock_field, boundary_field in (
        ("forbidden_prior_item_ids", "item_ids"),
        ("forbidden_prior_source_entity_ids", "source_entity_ids"),
        ("forbidden_prior_component_ids", "component_ids"),
    ):
        if execution_lock.get(lock_field) != exposure_boundary.get(boundary_field):
            raise PowerRefusal("c801 lock differs from the complete exposure boundary")

    suite_sha = verify_suite_v3_without_gold(suite)
    execution_lock_sha = _self_hash(
        execution_lock, "lock_sha256", "development execution lock"
    )
    if canonical_sha256(manifest) != suite.get("manifest_sha256"):
        raise PowerRefusal("development manifest differs from terminal suite")
    source_sha = verify_public_source_receipt(public_source_receipt)
    gold_source_sha = verify_gold_source_receipt_v6(
        gold_source_receipt, selection_receipt
    )
    evaluator_sha = verify_evaluator_seal(evaluator_receipt)
    genesis_sha = _self_hash(
        db_genesis_receipt, "genesis_sha256", "DB genesis"
    )
    compatibility_root = verify_preimage_bundle(
        environment_dependency_bundle, verify_live=True
    )
    environment, dependencies, dependency_files = _dependency_files(
        environment_dependency_bundle
    )
    environment_sha = verify_environment_receipt(environment, verify_live=True)
    dependency_sha = verify_dependency_receipt(dependencies, verify_live=True)
    bundle_sha = environment_dependency_bundle.get("bundle_sha256")
    if not isinstance(bundle_sha, str):
        raise PowerRefusal("c801 environment bundle hash is absent")

    manifest_items = manifest.get("items")
    source_rows = public_source_receipt.get("rows")
    if not isinstance(manifest_items, list) or not isinstance(source_rows, list):
        raise PowerRefusal("development manifest/source rows are absent")
    manifest_by_id = {
        str(item.get("item_id")): item
        for item in manifest_items
        if isinstance(item, Mapping)
    }
    source_by_id = {
        str(row.get("item_id")): row
        for row in source_rows
        if isinstance(row, Mapping)
    }
    if (
        len(manifest_by_id) != len(manifest_items)
        or set(source_by_id) != set(manifest_by_id)
    ):
        raise PowerRefusal("development source receipt and manifest identities differ")
    for item_id, item in manifest_by_id.items():
        if source_by_id[item_id].get("source_entity_ids") != _manifest_source_entity_ids(
            item
        ):
            raise PowerRefusal("development source-entity binding drifted")
    cohort_root = canonical_sha256(sorted(manifest_by_id))
    full_entries = _decode_gold_selected_block(
        gold_source_receipt, "development"
    )
    expected_gold = {
        "schema_version": GOLD_SCHEMA,
        "run_id": C801_DEVELOPMENT_RUN_ID,
        "items": [
            {
                "item_id": str(entry["row"]["id"]),
                "accepted_answers": [entry["row"]["answer"]],
            }
            for entry in full_entries
        ],
    }
    gold_sha = canonical_sha256(gold)
    labels = environment.get("labels")
    _verify_deployment_environment_binding(
        labels, execution_lock=execution_lock, manifest=manifest
    )
    if (
        public_source_receipt.get("schema_version") != SOURCE_RECEIPT_SCHEMA
        or gold.get("schema_version") != GOLD_SCHEMA
        or dict(gold) != expected_gold
        or evaluator_receipt.get("schema_version") != EVALUATOR_SEAL_SCHEMA
        or evaluator_receipt.get("run_id") != C801_DEVELOPMENT_RUN_ID
        or gold.get("run_id") != C801_DEVELOPMENT_RUN_ID
        or suite.get("measurement_lock_sha256") != execution_lock_sha
        or execution_lock.get("manifest_sha256") != canonical_sha256(manifest)
        or execution_lock.get("selection_receipt_sha256") != selection_sha
        or execution_lock.get("prior_exposure_receipt_sha256") != prior_sha
        or execution_lock.get("aborted_attempt_exposure_receipt_sha256")
        != successor_sha
        or execution_lock.get("public_source_receipt_sha256") != source_sha
        or execution_lock.get("gold_source_receipt_sha256") != gold_source_sha
        or execution_lock.get("gold_sha256") != gold_sha
        or execution_lock.get("evaluator_receipt_sha256") != evaluator_sha
        or execution_lock.get("db_genesis_receipt_sha256") != genesis_sha
        or execution_lock.get("environment_receipt_sha256") != environment_sha
        or execution_lock.get("dependency_receipt_sha256") != dependency_sha
        or execution_lock.get("environment_dependency_compatibility_root_sha256")
        != compatibility_root
        or execution_lock.get("environment_dependency_bundle_sha256") != bundle_sha
        or any(
            suite.get(field) != execution_lock.get(field)
            for field in (
                "upstream_endpoint",
                "deployment_receipt_sha256",
                "deployment_id",
                "served_model",
                "model_revision",
            )
        )
        or evaluator_receipt.get("cohort_root_sha256") != cohort_root
        or evaluator_receipt.get("raw_source_sha256")
        != public_source_receipt.get("raw_source_sha256")
        or evaluator_receipt.get("public_selection_receipt_sha256")
        != selection_sha
        or evaluator_receipt.get("public_source_receipt_sha256") != source_sha
        or evaluator_receipt.get("gold_source_receipt_sha256") != gold_source_sha
        or evaluator_receipt.get("gold_sha256") != gold_sha
        or public_source_receipt.get("public_selection_receipt_sha256")
        != selection_sha
        or suite.get("gold_opened") is not False
        or suite.get("scientific_verdict_emitted") is not False
    ):
        raise PowerRefusal("c801 development evidence identity drifted")
    parity = suite.get("token_parity")
    transport = suite.get("transport_audit")
    runs = suite.get("item_runs")
    if (
        not isinstance(parity, Mapping)
        or parity.get("all_within_tolerance") is not True
        or not isinstance(transport, Mapping)
        or not isinstance(runs, list)
    ):
        raise PowerRefusal("c801 terminal transport or token parity is absent")
    _verify_token_blocks(suite, runs)
    if (
        transport.get("call_count") != len(runs) * 3
        or transport.get("item_run_count") != len(runs)
        or transport.get("status_counts") != {"ACCEPTED": len(runs) * 3}
        or suite.get("execution_policy") != execution_policy
        or suite.get("max_workers") != execution_policy.get("max_workers")
    ):
        raise PowerRefusal("c801 terminal counts or execution policy drifted")

    artifact_receipts = {
        "selection_receipt_sha256": selection_sha,
        "predecessor_selection_receipt_sha256": predecessor_sha,
        "prior_exposure_receipt_sha256": prior_sha,
        "aborted_attempt_exposure_receipt_sha256": successor_sha,
        "execution_lock_sha256": execution_lock_sha,
        "public_source_receipt_sha256": source_sha,
        "gold_source_receipt_sha256": gold_source_sha,
        "suite_receipt_sha256": suite_sha,
        "evaluator_receipt_sha256": evaluator_sha,
        "db_genesis_receipt_sha256": genesis_sha,
        "gold_sha256": gold_sha,
        "environment_receipt_sha256": environment_sha,
        "dependency_receipt_sha256": dependency_sha,
        "environment_dependency_compatibility_root_sha256": compatibility_root,
        "environment_dependency_bundle_sha256": bundle_sha,
    }
    evidence = {
        "schema_version": POWER_EVIDENCE_SCHEMA_V6,
        "manifest": dict(manifest),
        "execution_lock": dict(execution_lock),
        "public_source_receipt": dict(public_source_receipt),
        "selection_receipt": dict(selection_receipt),
        "predecessor_selection_receipt": dict(predecessor_selection_receipt),
        "gold_source_receipt": dict(gold_source_receipt),
        "prior_exposure_receipt": dict(prior_exposure_receipt),
        "aborted_attempt_exposure_receipt": dict(
            aborted_attempt_exposure_receipt
        ),
        "suite": dict(suite),
        "evaluator_receipt": dict(evaluator_receipt),
        "gold": dict(gold),
        "db_genesis_receipt": dict(db_genesis_receipt),
        "environment_dependency_bundle": dict(environment_dependency_bundle),
        "artifact_receipts": artifact_receipts,
    }
    judge_row = dependency_files.get("judge_core")
    if (
        not isinstance(judge_row, Mapping)
        or not isinstance(judge_row.get("sha256"), str)
        or execution_lock.get("judge_core_file_sha256") != judge_row.get("sha256")
    ):
        raise PowerRefusal("frozen c801 judge differs from the development lock")
    judge = _load_c801_judge_core(
        judge_core_path,
        expected_file_sha256=str(judge_row["sha256"]),
        expected_derivation_sha256=str(
            execution_lock.get("token_envelope_derivation_receipt_sha256")
        ),
    )
    judge_core_sha = str(judge.__hswm_captured_core_sha256__)
    if judge_core_sha != execution_lock.get("judge_core_sha256"):
        raise PowerRefusal("c801 judge semantics changed after development lock")
    try:
        components = judge._derive_power_development_components(
            evidence, selection=selection_receipt
        )
    except Exception as error:
        raise PowerRefusal("c801 judge could not derive development utilities") from error
    if (
        not isinstance(components, list)
        or len(components) != DEVELOPMENT_COMPONENTS_V6
        or any(
            _component_overlaps_boundary(component, exposure_boundary)
            for component in components
        )
    ):
        raise PowerRefusal("c801 development components are incomplete or exposed")

    plan = {
        "schema_version": POWER_SIMULATOR_SCHEMA_V6,
        "trials": TRIALS_V6,
        "master_seed": POWER_SIMULATION_SEED,
        "selected_cluster_count": SELECTED_CLUSTERS_V6,
        "selection_method": "complete_seed_block_without_replacement/v1",
        "mde": MDE_V6,
        "target_power": TARGET_POWER_V6,
        "scenarios": list(POWER_SCENARIOS_V6),
    }
    analysis = {
        "schema_version": POWER_DEVELOPMENT_SCHEMA_V6,
        "development_components": components,
        "simulation_plan": plan,
    }
    try:
        characteristics = judge._recompute_power_characteristics(
            components, plan, bootstrap=BOOTSTRAP_V6
        )
    except Exception as error:
        raise PowerRefusal("c801 judge could not replay power characteristics") from error
    unsigned = {
        "schema_version": POWER_RECEIPT_SCHEMA_V6,
        "analysis_input": analysis,
        "development_evidence": evidence,
        "development_evidence_sha256": canonical_sha256(evidence),
        "development_data_sha256": canonical_sha256(components),
        "simulator_sha256": judge_core_sha,
        "judge_core_sha256": judge_core_sha,
        "inference_unit": "component_cluster_macro",
        "selected_method": BOOTSTRAP_V6["method"],
        "minimum_clusters": SELECTED_CLUSTERS_V6,
        "operating_characteristics": characteristics,
        "metric": UTILITY_METRIC,
        "utility_cost_c": UTILITY_COST_C,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


__all__ = [
    "BOOTSTRAP_V6",
    "DEVELOPMENT_COMPONENTS_V6",
    "JUDGE_CAPABILITY_V1",
    "MDE_V6",
    "POWER_DEVELOPMENT_SCHEMA_V6",
    "POWER_EVIDENCE_SCHEMA_V6",
    "POWER_RECEIPT_SCHEMA_V6",
    "POWER_SCENARIOS_V6",
    "POWER_SIMULATION_SEED",
    "POWER_SIMULATOR_SCHEMA_V6",
    "SELECTED_CLUSTERS_V6",
    "TARGET_POWER_V6",
    "TRIALS_V6",
    "UTILITY_COST_C",
    "UTILITY_METRIC",
    "PowerRefusal",
    "_load_c801_judge_core",
    "build_power_receipt_v6",
]
