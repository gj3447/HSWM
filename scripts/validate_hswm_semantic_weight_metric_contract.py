#!/usr/bin/env python3
"""Fail-closed validator for the HSWM semantic-weight metric draft.

This validates engineering identity and measurement authorization boundaries.
It has no model endpoint, KG write, external-governance write, or scientific-judgment
path.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any, Iterable, Mapping


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hswm_semantic_weight_metric import PARITY_FIELDS, REQUIRED_ARMS  # noqa: E402


CONTRACT_PATH = REPO_ROOT / "research/HSWM_SEMANTIC_WEIGHT_METRIC_CONTRACT.v1.json"
PREREG_PATH = REPO_ROOT / "research/PREREG_HSWM_SCALAR_W_CAUSAL_MEDIATION.v1.json"
SCHEMA_PATH = REPO_ROOT / "schemas/hswm_semantic_weight_metric_contract.v1.schema.json"

CONTRACT_FIELDS = {
    "schema_version",
    "contract_id",
    "status",
    "created_at",
    "authority",
    "scope",
    "weight_planes",
    "formulae",
    "required_arms",
    "required_metric_ids",
    "parity_fields",
    "intervention_invariants",
    "statistics",
    "thresholds",
    "firewalls",
    "measurement_gate",
    "source_artifacts",
    "runtime_artifacts",
    "schema_binding",
}

PREREG_FIELDS = {
    "schema_version",
    "preregistration_id",
    "experiment_id",
    "experiment_tag",
    "experiment_record",
    "status",
    "created_at",
    "title",
    "w_scope",
    "operator_w_claim_allowed",
    "authority",
    "predecessors",
    "contract_binding",
    "hypothesis",
    "testbed",
    "arms",
    "intervention_sequences",
    "arm_construction",
    "parity",
    "metrics_and_thresholds",
    "statistics",
    "firewalls",
    "judge_binding",
    "external_governance",
    "kill_conditions",
    "void_conditions",
    "required_before_lock",
    "measurement_gate",
}

PREREG_METRIC_KEYS = {
    "learned_gain",
    "full_over_embedding_delta",
    "full_over_hypergraph_delta",
    "w_ablation_delta",
    "w_shuffle_delta",
    "w_random_update_delta",
    "context_operator_delta",
    "removal_erasure_fraction",
    "shuffle_erasure_fraction",
    "random_update_erasure_fraction",
    "restoration_recovery_fraction",
    "restoration_gap",
    "route_jsd_normalized",
    "route_case_count",
    "route_divergence_cases",
    "retention_loss",
    "negative_transfer_rate",
    "seed_direction",
    "noise_band",
}

EXPECTED_SOURCE_ARTIFACT_IDS = {
    "semantic-weight-prom16-math",
    "semantic-weight-field-v0",
    "causal-plasticity-cpl1-draft",
    "immutable-scalar-weight-snapshot",
    "scalar-bond-readout",
}

EXPECTED_RUNTIME_ARTIFACT_IDS = {
    "w-ablation-builder",
    "semantic-weight-metric-reducer",
    "semantic-weight-contract-validator",
    "semantic-weight-negative-tests",
    "scalar-w-causal-judge",
    "scalar-w-causal-judge-tests",
}

REQUIRED_METRIC_IDS = {
    "transfer_gain",
    "embedding_delta",
    "hyper_only_delta",
    "full_over_embedding_delta",
    "full_over_hypergraph_delta",
    "learned_gain",
    "w_ablation_delta",
    "w_shuffle_delta",
    "w_uniform_delta",
    "w_random_update_delta",
    "context_operator_delta",
    "removal_erasure_fraction",
    "shuffle_erasure_fraction",
    "random_update_erasure_fraction",
    "restoration_recovery_fraction",
    "restoration_gap",
    "route_jsd_normalized",
    "route_case_count",
    "route_divergence_cases",
    "retention_loss",
    "negative_transfer_rate",
    "direction",
    "noise_band",
}

WEIGHT_PLANE_USES = {
    "query_gate": "EXCLUDED_FROM_LEARNED_W_CLAIM",
    "boost_channel": "EXCLUDED_FROM_LEARNED_W_CLAIM",
    "slow_log_salience": "SCALAR_CAUSAL_SHADOW_ONLY",
    "learned_fast_efficacy": "TARGET_NOT_IMPLEMENTED",
}

FORBIDDEN_PREREG_KEYS = {
    "result",
    "results",
    "outcome",
    "outcomes",
    "observations",
    "judgment",
    "verdict",
    "scientific_verdict",
}

_HEX = frozenset("0123456789abcdef")


class MetricContractValidationError(ValueError):
    """A metric contract or preregistration is unsafe or drifted."""


def _fail(message: str) -> None:
    raise MetricContractValidationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{field} must be an array")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{field} must be non-empty text")
    return value


def _sha(value: Any, field: str) -> str:
    text = _text(value, field)
    if len(text) != 64 or any(character not in _HEX for character in text):
        _fail(f"{field} must be a lowercase SHA-256")
    return text


def _date(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        _fail(f"{field} must be an ISO date: {error}")
    if parsed.isoformat() != text:
        _fail(f"{field} must use canonical YYYY-MM-DD form")
    return text


def _safe_file(relative: Any, field: str, repo_root: Path) -> Path:
    text = _text(relative, field)
    path = PurePosixPath(text)
    if path.is_absolute() or text.startswith(("~", "\\")) or ".." in path.parts:
        _fail(f"{field} is not a safe repository-relative path: {text!r}")
    resolved = (repo_root / text).resolve()
    root = repo_root.resolve()
    if root not in resolved.parents:
        _fail(f"{field} escapes repository root")
    if not resolved.is_file():
        _fail(f"{field} does not exist: {text}")
    return resolved


def _exact_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            f"{field} fields must be exact; missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )


def _schema_type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, Mapping)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    _fail(f"bound schema uses unsupported type {expected!r}")


def _resolve_local_ref(reference: str, root_schema: Mapping[str, Any]) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        _fail(f"bound schema uses non-local ref {reference!r}")
    current: Any = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or part not in current:
            _fail(f"bound schema has unresolved ref {reference!r}")
        current = current[part]
    return _mapping(current, f"schema ref {reference}")


def _validate_bound_schema(
    instance: Any,
    schema: Mapping[str, Any],
    *,
    root_schema: Mapping[str, Any],
    field: str,
) -> None:
    if "$ref" in schema:
        _validate_bound_schema(
            instance,
            _resolve_local_ref(_text(schema["$ref"], f"{field}.$ref"), root_schema),
            root_schema=root_schema,
            field=field,
        )
        return
    if "type" in schema and not _schema_type_matches(instance, schema["type"]):
        _fail(f"{field} does not match bound schema type {schema['type']!r}")
    if "const" in schema and instance != schema["const"]:
        _fail(f"{field} does not match bound schema const")
    if "enum" in schema and instance not in schema["enum"]:
        _fail(f"{field} is not in the bound schema enum")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            _fail(f"{field} is below bound schema minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            _fail(f"{field} is above bound schema maximum")

    if isinstance(instance, Mapping):
        required = schema.get("required", [])
        missing = sorted(set(required) - set(instance))
        if missing:
            _fail(f"{field} misses bound schema fields: {missing}")
        properties = _mapping(schema.get("properties", {}), f"{field}.schema.properties")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                _fail(f"{field} has bound-schema extra fields: {extra}")
        for key, nested_schema in properties.items():
            if key in instance:
                _validate_bound_schema(
                    instance[key],
                    _mapping(nested_schema, f"{field}.{key}.schema"),
                    root_schema=root_schema,
                    field=f"{field}.{key}",
                )
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            _fail(f"{field} has fewer than bound minItems")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            _fail(f"{field} has more than bound maxItems")
        if schema.get("uniqueItems") is True:
            identities = [
                json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                for value in instance
            ]
            if len(identities) != len(set(identities)):
                _fail(f"{field} violates bound uniqueItems")
        if "items" in schema:
            item_schema = _mapping(schema["items"], f"{field}.schema.items")
            for index, value in enumerate(instance):
                _validate_bound_schema(
                    value,
                    item_schema,
                    root_schema=root_schema,
                    field=f"{field}[{index}]",
                )
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            _fail(f"{field} is shorter than bound minLength")
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
            _fail(f"{field} does not match bound schema pattern")
        if schema.get("format") == "date":
            _date(instance, field)


def _validate_artifacts(
    values: Any, *, field: str, repo_root: Path
) -> tuple[str, ...]:
    artifacts = _list(values, field)
    if not artifacts:
        _fail(f"{field} must not be empty")
    identifiers: list[str] = []
    for index, raw in enumerate(artifacts):
        artifact = _mapping(raw, f"{field}[{index}]")
        _exact_keys(artifact, {"artifact_id", "path", "sha256", "role"}, f"{field}[{index}]")
        artifact_id = _text(artifact["artifact_id"], f"{field}[{index}].artifact_id")
        path = _safe_file(artifact["path"], f"{field}[{index}].path", repo_root)
        expected = _sha(artifact["sha256"], f"{field}[{index}].sha256")
        actual = sha256(path)
        if actual != expected:
            _fail(
                f"{field}[{index}] SHA drift expected={expected} actual={actual} "
                f"path={artifact['path']}"
            )
        _text(artifact["role"], f"{field}[{index}].role")
        identifiers.append(artifact_id)
    if len(identifiers) != len(set(identifiers)):
        _fail(f"{field} contains duplicate artifact_id")
    return tuple(identifiers)


def validate_contract(
    contract: Mapping[str, Any], *, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    _exact_keys(contract, CONTRACT_FIELDS, "contract")
    schema_binding = _mapping(contract["schema_binding"], "schema_binding")
    _exact_keys(
        schema_binding,
        {"artifact_id", "path", "sha256", "role"},
        "schema_binding",
    )
    schema_file = _safe_file(schema_binding["path"], "schema_binding.path", repo_root)
    expected_schema = (
        repo_root / "schemas/hswm_semantic_weight_metric_contract.v1.schema.json"
    ).resolve()
    if schema_file != expected_schema:
        _fail("schema binding points at the wrong file")
    if sha256(schema_file) != _sha(schema_binding["sha256"], "schema_binding.sha256"):
        _fail("schema binding SHA drift")
    try:
        schema_document = json.loads(schema_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        _fail(f"metric schema is not valid JSON: {error}")
    root_schema = _mapping(schema_document, "bound schema")
    _validate_bound_schema(
        contract,
        root_schema,
        root_schema=root_schema,
        field="contract",
    )
    if contract["schema_version"] != "hswm-semantic-weight-metric-contract/v1":
        _fail("unsupported metric contract schema")
    if contract["contract_id"] != "HSWM_SEMANTIC_WEIGHT_METRIC_CONTRACT_V1_20260726":
        _fail("metric contract id drift")
    if contract["status"] != "ENGINEERING_DRAFT_UNRATIFIED":
        _fail("metric contract was promoted without ratification")

    authority = _mapping(contract["authority"], "authority")
    if authority != {
        "user_ratified": False,
        "scientific_status": "UNJUDGED",
        "scientific_judgment_emitted": False,
        "kg_write_state": "NOT_WRITTEN",
        "external_governance": "NONE",
    }:
        _fail("authority block is not fail-closed")

    scope = _mapping(contract["scope"], "scope")
    if scope.get("implemented_weight_scope") != "scalar_slow_efficacy_v1":
        _fail("implemented scope must remain scalar_slow_efficacy_v1")
    if scope.get("target_weight_scope") != "operator_semantic_weight_future":
        _fail("operator semantic W must remain an explicit future target")
    excluded = set(_list(scope.get("excluded_claims"), "scope.excluded_claims"))
    if "operator-valued semantic W implemented" not in excluded:
        _fail("contract does not exclude an unsupported operator-W claim")

    planes = _list(contract["weight_planes"], "weight_planes")
    by_plane = {
        _text(_mapping(raw, "weight_planes[]")["plane_id"], "weight_planes[].plane_id"):
        _mapping(raw, "weight_planes[]")
        for raw in planes
    }
    if set(by_plane) != set(WEIGHT_PLANE_USES):
        _fail("query, boost, slow, and learned-fast planes must be distinct and complete")
    for plane_id, expected_use in WEIGHT_PLANE_USES.items():
        if by_plane[plane_id].get("claim_use") != expected_use:
            _fail(f"unsafe claim_use for weight plane {plane_id}")

    arm_values = _list(contract["required_arms"], "required_arms")
    arms = [_mapping(raw, "required_arms[]").get("arm_id") for raw in arm_values]
    if len(arms) != len(set(arms)) or set(arms) != set(REQUIRED_ARMS):
        _fail("required arm set is incomplete, duplicated, or drifted")
    metrics = _list(contract["required_metric_ids"], "required_metric_ids")
    if len(metrics) != len(set(metrics)) or set(metrics) != REQUIRED_METRIC_IDS:
        _fail("required metric set is incomplete, duplicated, or drifted")
    parity = _list(contract["parity_fields"], "parity_fields")
    if len(parity) != len(set(parity)) or set(parity) != set(PARITY_FIELDS):
        _fail("parity field set drift")

    stats = _mapping(contract["statistics"], "statistics")
    baseline = _mapping(stats.get("baseline_selection"), "statistics.baseline_selection")
    if baseline.get("status") != "UNSELECTED_BLOCKS_MEASUREMENT":
        _fail("strongest baseline was selected without a frozen development receipt")
    if (
        stats.get("bootstrap_samples") != 10_000
        or stats.get("bootstrap_seed") != 20260726
        or stats.get("bootstrap_interval") != "paired_percentile_95"
        or stats.get("confidence") != 0.95
    ):
        _fail("statistics lock drift")

    thresholds = _mapping(contract["thresholds"], "thresholds")
    required_thresholds = {
        "learned_gain_abs_min": 0.05,
        "paired_lcb_min_exclusive": 0.0,
        "removal_erasure_fraction_min": 0.7,
        "shuffle_erasure_fraction_min": 0.7,
        "random_update_erasure_fraction_min": 0.7,
        "restoration_recovery_fraction_min": 0.9,
        "restoration_equivalence_rope": [-0.02, 0.02],
        "context_operator_delta_min": 0.03,
        "retention_loss_max": 0.03,
        "negative_transfer_rate_max": 0.1,
        "route_divergence_cases_min": 1,
    }
    if thresholds != required_thresholds:
        _fail("threshold lock drift")

    gate = _mapping(contract["measurement_gate"], "measurement_gate")
    if not gate or any(value is not False for value in gate.values()):
        _fail("measurement gate must be entirely false in the unratified draft")
    firewalls = _mapping(contract["firewalls"], "firewalls")
    if firewalls.get("cache_hits_required") != 0 or any(
        firewalls.get(field) is not True
        for field in (
            "eligibility_pre_outcome",
            "answer_pre_gold",
            "natural_language_learning_state_forbidden",
            "f1_cohort_reuse_forbidden",
            "void_on_hash_or_parity_drift",
        )
    ):
        _fail("causal or leakage firewall drift")

    source_ids = _validate_artifacts(
        contract["source_artifacts"], field="source_artifacts", repo_root=repo_root
    )
    runtime_ids = _validate_artifacts(
        contract["runtime_artifacts"], field="runtime_artifacts", repo_root=repo_root
    )
    if set(source_ids) != EXPECTED_SOURCE_ARTIFACT_IDS:
        _fail("source artifact identity set drift")
    if set(runtime_ids) != EXPECTED_RUNTIME_ARTIFACT_IDS:
        _fail("runtime artifact identity set drift")

    return {
        "contract_id": contract["contract_id"],
        "arms_checked": len(arms),
        "metrics_checked": len(metrics),
        "source_artifacts_checked": len(source_ids),
        "runtime_artifacts_checked": len(runtime_ids),
        "scientific_status": "UNJUDGED",
    }


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def validate_preregistration(
    prereg: Mapping[str, Any],
    *,
    contract_path: Path = CONTRACT_PATH,
) -> dict[str, Any]:
    _exact_keys(prereg, PREREG_FIELDS, "preregistration")
    if prereg.get("schema_version") != "hswm-scalar-w-causal-preregistration/v1":
        _fail("unsupported scalar-W preregistration schema")
    if prereg.get("preregistration_id") != "PREREG_HSWM_SCALAR_W_CAUSAL_MEDIATION_V1_20260726":
        _fail("preregistration id drift")
    if prereg.get("experiment_id") != "HSWM-SWCM-1":
        _fail("experiment id drift")
    if prereg.get("experiment_tag") != "hswm-scalar-w-causal-mediation-v1":
        _fail("experiment tag drift")
    _date(prereg.get("created_at"), "prereg.created_at")
    _text(prereg.get("title"), "prereg.title")
    if prereg.get("status") != "DRAFT_UNRATIFIED_NO_MEASUREMENT":
        _fail("preregistration was promoted or measurement-enabled")
    experiment_record = _mapping(
        prereg.get("experiment_record"), "prereg.experiment_record"
    )
    if experiment_record != {
        "record_id": "LOCAL_ONLY",
        "external_authority": "NONE",
        "role": "PREDICTION_AND_MEASUREMENT_RECORD",
    }:
        _fail("preregistration local record binding drift")
    authority = _mapping(prereg.get("authority"), "prereg.authority")
    if authority != {
        "user_ratified": False,
        "scientific_status": "UNJUDGED",
        "scientific_judgment_emitted": False,
        "measurement_authorized": False,
    }:
        _fail("preregistration authority is not fail-closed")
    if prereg.get("w_scope") != "scalar_slow_efficacy_v1":
        _fail("preregistration overclaims beyond implemented scalar W")
    if prereg.get("operator_w_claim_allowed") is not False:
        _fail("operator-W claim must be forbidden in the scalar causal shadow")

    contract_binding = _mapping(prereg.get("contract_binding"), "contract_binding")
    _exact_keys(contract_binding, {"path", "sha256"}, "contract_binding")
    if contract_binding["path"] != "research/HSWM_SEMANTIC_WEIGHT_METRIC_CONTRACT.v1.json":
        _fail("preregistration points at the wrong metric contract")
    if contract_binding["sha256"] != sha256(contract_path):
        _fail("preregistration metric-contract SHA drift")

    predecessors = _list(prereg.get("predecessors"), "prereg.predecessors")
    if len(predecessors) != 2:
        _fail("preregistration must preserve exactly two declared predecessors")
    for index, raw in enumerate(predecessors):
        predecessor = _mapping(raw, f"prereg.predecessors[{index}]")
        _exact_keys(
            predecessor,
            {"path", "sha256", "relation"},
            f"prereg.predecessors[{index}]",
        )
        path = _safe_file(predecessor["path"], f"prereg.predecessors[{index}].path", REPO_ROOT)
        if sha256(path) != _sha(
            predecessor["sha256"], f"prereg.predecessors[{index}].sha256"
        ):
            _fail(f"prereg predecessor SHA drift at index {index}")
        _text(predecessor["relation"], f"prereg.predecessors[{index}].relation")

    hypothesis = _mapping(prereg.get("hypothesis"), "prereg.hypothesis")
    expected_hypothesis = {
        "primary",
        "mediation",
        "representation",
        "actuation",
        "retention",
        "interpretation_limit",
    }
    _exact_keys(hypothesis, expected_hypothesis, "prereg.hypothesis")
    for key in expected_hypothesis:
        _text(hypothesis[key], f"prereg.hypothesis.{key}")

    testbed = _mapping(prereg.get("testbed"), "prereg.testbed")
    required_testbed = {
        "family",
        "cohort_rule",
        "scorer",
        "cohorts",
        "cluster_unit",
        "minimum_independent_seeds",
        "sample_size_rule",
        "freshness_identity",
    }
    _exact_keys(testbed, required_testbed, "prereg.testbed")
    if testbed.get("cohorts") != ["development", "fresh", "retention"]:
        _fail("preregistration cohort lock drift")
    if testbed.get("minimum_independent_seeds") != 5:
        _fail("preregistration seed-count lock drift")

    arms = _list(prereg.get("arms"), "prereg.arms")
    if len(arms) != len(set(arms)) or set(arms) != set(REQUIRED_ARMS):
        _fail("preregistration arm set drift")
    sequences = _mapping(
        prereg.get("intervention_sequences"), "prereg.intervention_sequences"
    )
    _exact_keys(
        sequences,
        {
            "full_remove_shuffle_restore",
            "full_shuffle_remove_restore",
            "assignment",
            "carryover_control",
        },
        "prereg.intervention_sequences",
    )
    if sequences["full_remove_shuffle_restore"] != [
        "W_FULL_LEARNED",
        "W_REMOVED_BASE",
        "W_SHUFFLED_WITHIN_STRATUM",
        "W_RESTORED_EXACT",
    ] or sequences["full_shuffle_remove_restore"] != [
        "W_FULL_LEARNED",
        "W_SHUFFLED_WITHIN_STRATUM",
        "W_REMOVED_BASE",
        "W_RESTORED_EXACT",
    ]:
        _fail("intervention sequence lock drift")
    arm_construction = _mapping(prereg.get("arm_construction"), "prereg.arm_construction")
    required_constructions = {
        "W_FULL_LEARNED",
        "W_REMOVED_BASE",
        "W_SHUFFLED_WITHIN_STRATUM",
        "W_RESTORED_EXACT",
        "W_UNIFORM_L1_MATCHED",
        "W_RANDOM_UPDATE_MATCHED",
        "STRONG_CONTEXT_VECTOR_EQUAL_INFO",
    }
    _exact_keys(arm_construction, required_constructions, "prereg.arm_construction")
    parity = _mapping(prereg.get("parity"), "prereg.parity")
    if set(_list(parity.get("exact_fields"), "prereg.parity.exact_fields")) != set(PARITY_FIELDS):
        _fail("preregistration parity field drift")
    metrics = _mapping(
        prereg.get("metrics_and_thresholds"), "prereg.metrics_and_thresholds"
    )
    _exact_keys(metrics, PREREG_METRIC_KEYS, "prereg.metrics_and_thresholds")
    if metrics.get("noise_band") != [-0.02, 0.02]:
        _fail("preregistration noise band drift")
    prereg_statistics = _mapping(prereg.get("statistics"), "prereg.statistics")
    _exact_keys(
        prereg_statistics,
        {
            "primary_unit",
            "within_cluster",
            "resampling",
            "bootstrap_seed",
            "bootstrap_interval",
            "confidence",
            "strongest_baseline_selection",
            "multiple_views",
        },
        "prereg.statistics",
    )
    if (
        prereg_statistics["bootstrap_seed"] != 20260726
        or prereg_statistics["bootstrap_interval"] != "paired_percentile_95"
        or prereg_statistics["confidence"] != 0.95
    ):
        _fail("preregistration statistics lock drift")
    if not _mapping(prereg.get("firewalls"), "prereg.firewalls"):
        _fail("prereg.firewalls must not be empty")

    judge = _mapping(prereg.get("judge_binding"), "prereg.judge_binding")
    _exact_keys(
        judge,
        {"path", "sha256", "replay_command", "judgment_schema"},
        "prereg.judge_binding",
    )
    judge_path = _safe_file(judge["path"], "prereg.judge_binding.path", REPO_ROOT)
    if judge["path"] != "hswm_scalar_w_causal_judge.py":
        _fail("preregistration judge path drift")
    if sha256(judge_path) != _sha(judge["sha256"], "prereg.judge_binding.sha256"):
        _fail("preregistration judge SHA drift")
    if judge["replay_command"] != (
        "python3 hswm_scalar_w_causal_judge.py --metrics <sealed_metrics.json>"
    ) or judge["judgment_schema"] != "hswm-scalar-w-causal-judgment/v1":
        _fail("preregistration judge replay contract drift")

    external_governance = _mapping(
        prereg.get("external_governance"), "prereg.external_governance"
    )
    if external_governance != {
        "authority": "NONE",
        "required": False,
        "state": "DISABLED",
    }:
        _fail("external governance boundary drift")

    for field, minimum in (
        ("kill_conditions", 8),
        ("void_conditions", 9),
        ("required_before_lock", 9),
    ):
        values = _list(prereg.get(field), f"prereg.{field}")
        if len(values) < minimum or not all(isinstance(value, str) and value for value in values):
            _fail(f"prereg.{field} is incomplete")
    gate = _mapping(prereg.get("measurement_gate"), "prereg.measurement_gate")
    if not gate or any(value is not False for value in gate.values()):
        _fail("preregistration measurement gate must remain entirely false")
    if gate.get("f1_completed_and_adjudicated") is not False:
        _fail("preregistration lost the active F1 dependency")
    forbidden = sorted(set(_walk_keys(prereg)) & FORBIDDEN_PREREG_KEYS)
    if forbidden:
        _fail(f"preregistration contains outcome-bearing keys: {forbidden}")
    return {
        "preregistration_id": prereg.get("preregistration_id"),
        "experiment_id": prereg.get("experiment_id"),
        "experiment_tag": prereg.get("experiment_tag"),
        "experiment_record": experiment_record["record_id"],
        "arms_checked": len(arms),
        "judge_sha256": judge["sha256"],
        "external_governance": external_governance["state"],
        "measurement_authorized": False,
        "scientific_status": "UNJUDGED",
    }


def validate_with_injected_negative(
    contract: Mapping[str, Any], *, repo_root: Path = REPO_ROOT
) -> bool:
    damaged = deepcopy(contract)
    damaged["required_arms"] = [
        arm for arm in damaged["required_arms"] if arm["arm_id"] != "W_RESTORED_EXACT"
    ]
    try:
        validate_contract(damaged, repo_root=repo_root)
    except MetricContractValidationError:
        return True
    _fail("injected missing-arm negative was not rejected")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--prereg", type=Path, default=PREREG_PATH)
    parser.add_argument("--skip-prereg", action="store_true")
    args = parser.parse_args(argv)
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        contract_receipt = validate_contract(contract, repo_root=REPO_ROOT)
        prereg_receipt = None
        if not args.skip_prereg:
            prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
            prereg_receipt = validate_preregistration(
                prereg, contract_path=args.contract
            )
        negative_caught = validate_with_injected_negative(contract, repo_root=REPO_ROOT)
        receipt = {
            "schema_version": "hswm-semantic-weight-contract-validation/v1",
            "status": "PASS",
            "contract_sha256": sha256(args.contract),
            "schema_sha256": sha256(SCHEMA_PATH),
            "preregistration_sha256": (
                sha256(args.prereg) if prereg_receipt is not None else None
            ),
            "contract_validation": contract_receipt,
            "preregistration_validation": prereg_receipt,
            "injected_negative_caught": negative_caught,
            "measurement_authorized": False,
            "scientific_status": "UNJUDGED",
        }
    except (
        MetricContractValidationError,
        KeyError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
