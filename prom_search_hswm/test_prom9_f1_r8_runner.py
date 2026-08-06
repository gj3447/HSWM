from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import threading

import pytest

from prom_search_hswm.hswm_call_receipt import ModelCallV1, ModelResponseV1
from prom_search_hswm.hswm_f1_durable_transport import (
    DURABLE_CALL_SCHEMA,
    DurableSpoolJSONPort,
)
from prom_search_hswm.hswm_function_network import F1_ARMS, TYPED_ARM
from prom_search_hswm.hswm_function_registry import build_registry
from prom_search_hswm.hswm_result_spool import (
    ModelDeploymentBinding,
    RawHTTPResponse,
    ResultSpoolHTTPServer,
    ResultSpoolService,
    SPOOL_IDENTITY_SCHEMA,
    SPOOL_SCHEMA,
    SQLiteResultSpool,
)
from prom_search_hswm.hswm_token_meter import FakeMeter
from prom_search_hswm.hswm_typed_ports import (
    canonical_json,
    canonical_sha256,
    output_schema_sha256,
)
from prom_search_hswm.prom9_f1_envelope import compute_minimum_input_caps
from prom_search_hswm.prom9_f1_r8_environment import (
    build_preimage_bundle,
    r8_dependency_paths,
    verify_environment_labels,
    verify_named_dependency_paths,
    verify_preimage_bundle,
    verify_repository_dependency_blobs,
)
from prom_search_hswm.prom9_f1_prior_exposure import (
    ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2,
    SCHEMA as PRIOR_EXPOSURE_SCHEMA,
    merge_exposure_boundaries,
)
import prom_search_hswm.prom9_f1_r8_runner as runner
import prom_search_hswm.prom9_f1_r8_private_output as private_output
from prom_search_hswm.prom9_f1_r8_runner import (
    GENERATION_POLICY,
    GENESIS_SCHEMA,
    REQUIRED_DEPENDENCY_FILES,
    R8RunnerRefusal,
    TRANSPORT_BINDINGS_SCHEMA,
    _database_identity,
    _database_schema,
    _read_only_database,
    build_development_execution_lock,
    finalize_suite_v3,
    initialize_transport_pair,
    run_suite_v3_draft,
    validate_execution_policy,
    validate_manifest_v3,
    verify_fresh_transport_genesis,
    verify_spool_endpoint_identity,
    verify_suite_v3_without_gold,
)
from prom_search_hswm.prom_f1_function_network import _arm_overrides
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL


REPO_ROOT = Path(__file__).resolve().parents[1]
ABORTED_ATTEMPT_EXPOSURE_PATH = (
    REPO_ROOT / "receipts/hswm_f1_r8_v8_aborted_exposure.v2.json"
)
_JUDGE_RELATIVE_PATH = Path(
    "FINDINGS/hswm-f1-r8-try3-2026-07-28/f1_r8_lakatotree_judge.py"
)


def _resolve_symposium_root() -> Path:
    candidates = (
        REPO_ROOT.parents[1],
        REPO_ROOT.parent / "SYMPOSIUM",
        REPO_ROOT.parent / "symposium",
    )
    matches: list[Path] = []
    match_identities: set[tuple[int, int]] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / ".git").exists() and (
            resolved / _JUDGE_RELATIVE_PATH
        ).is_file():
            stat = resolved.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in match_identities:
                continue
            matches.append(resolved)
            match_identities.add(identity)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one SYMPOSIUM checkout for {REPO_ROOT}; "
            f"found {matches}"
        )
    return matches[0]


SYMPOSIUM_ROOT = _resolve_symposium_root()
HSWM_COMMIT = subprocess.check_output(
    ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
).strip()
SYMPOSIUM_COMMIT = subprocess.check_output(
    ["git", "-C", str(SYMPOSIUM_ROOT), "rev-parse", "HEAD"], text=True
).strip()
ENDPOINT = "http://127.0.0.1:8011"
UPSTREAM_ENDPOINT = "http://127.0.0.1:18002/v1/chat/completions"
DEPLOYMENT_SHA256 = "d" * 64
TEST_REVISION = "f" * 40


@pytest.fixture(autouse=True)
def _historical_singular_incident_is_test_only_successor_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep runner-unit history fixtures without reopening production A2."""

    exact_successor = runner.verify_f1_r8_successor_exposure_set

    def verify_test_fixture(value):
        if (
            isinstance(value, dict)
            and value.get("schema_version") == ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2
        ):
            return runner.verify_aborted_attempt_exposure_receipt(value)
        return exact_successor(value)

    monkeypatch.setattr(
        runner, "verify_f1_r8_successor_exposure_set", verify_test_fixture
    )


def test_a3_exposure_gate_requires_exact_successor_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_sha = "a" * 64
    calls: list[str] = []

    def exact(_value):
        calls.append("exact")
        return receipt_sha

    def generic(_value):
        calls.append("generic")
        return receipt_sha

    monkeypatch.setattr(runner, "verify_f1_r8_successor_exposure_set", exact)
    monkeypatch.setattr(runner, "verify_aborted_attempt_exposure_receipt", generic)
    monkeypatch.setattr(
        runner, "verify_forbidden_exposure_union", lambda *_args: {}
    )
    assert runner._validate_aborted_attempt_exposure_gate(
        {"kind": "successor-wrapper"},
        prior_exposure_receipt={},
        execution_lock={
            "schema_version": runner.EXECUTION_LOCK_SCHEMA,
            "run_id": runner.F1_R8_A3_SUCCESSOR_RUN_ID,
            "aborted_attempt_exposure_receipt_sha256": receipt_sha,
        },
    ) == receipt_sha
    assert calls == ["exact"]

    calls.clear()
    assert runner._validate_aborted_attempt_exposure_gate(
        {"kind": "successor-wrapper"},
        prior_exposure_receipt={},
        execution_lock={
            "schema_version": runner.EXECUTION_LOCK_SCHEMA,
            "run_id": runner.C800_DEVELOPMENT_RUN_ID,
            "aborted_attempt_exposure_receipt_sha256": receipt_sha,
        },
    ) == receipt_sha
    assert calls == ["exact"]

    calls.clear()
    with pytest.raises(
        runner.R8RunnerRefusal, match="ratified development identity"
    ):
        runner._validate_aborted_attempt_exposure_gate(
            {"kind": "legacy-incident"},
            prior_exposure_receipt={},
            execution_lock={
                "schema_version": runner.EXECUTION_LOCK_SCHEMA,
                "run_id": "f1-2wiki-development-r8-try3-a2",
                "aborted_attempt_exposure_receipt_sha256": receipt_sha,
            },
        )
    assert calls == []

    assert runner._validate_aborted_attempt_exposure_gate(
        {"kind": "sealed-historical-incident"},
        prior_exposure_receipt={},
        execution_lock={
            "schema_version": runner.SEALED_LOCK_SCHEMA,
            "run_id": runner.SEALED_RUN_ID,
            "aborted_attempt_exposure_receipt_sha256": receipt_sha,
        },
    ) == receipt_sha
    assert calls == ["generic"]


def test_stable_reader_refuses_lstat_to_open_identity_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "authority.py"
    replacement = tmp_path / "replacement.py"
    target.write_bytes(b"before\n")
    replacement.write_bytes(b"after\n")
    original_open = os.open
    swapped = False

    def swapping_open(path, flags, *args):
        nonlocal swapped
        if not swapped and Path(path) == target:
            os.replace(replacement, target)
            swapped = True
        return original_open(path, flags, *args)

    monkeypatch.setattr(runner.os, "open", swapping_open)
    with pytest.raises(R8RunnerRefusal, match="changed before"):
        runner.read_stable_bytes(target, "authority")


def _deployment_binding() -> ModelDeploymentBinding:
    return ModelDeploymentBinding(
        upstream_endpoint=UPSTREAM_ENDPOINT,
        deployment_receipt_sha256=DEPLOYMENT_SHA256,
        deployment_id=f"hswm:model_deployment:v2:{DEPLOYMENT_SHA256}",
        served_model="fake-model",
        model_revision=TEST_REVISION,
    )


@pytest.fixture(autouse=True)
def _verify_dirty_owned_paths_without_weakening_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two owned runner files are untracked until the root session publishes.

    Production still calls ``verify_r8_preimage_bundle`` with committed-blob
    enforcement.  Focused unit tests retain exact names, paths, labels, live
    bytes, and HEAD identity while skipping only the impossible pre-commit
    cat-file assertion for these newly introduced files.
    """

    def verify(
        value,
        *,
        expected_paths,
        expected_labels,
        repo_root,
        symposium_repo_root,
        verify_live=False,
        environ=None,
    ):
        compatibility = verify_preimage_bundle(
            value, verify_live=verify_live, environ=environ
        )
        environment = value["environment_receipt"]
        dependencies = value["dependency_receipt"]
        environment_sha = verify_environment_labels(
            environment, expected_labels, verify_live=False
        )
        dependency_sha = verify_named_dependency_paths(
            dependencies, expected_paths, verify_live=False
        )
        if expected_labels["hswm_commit"] != HSWM_COMMIT:
            raise RuntimeError("live HEAD label drifted")
        if (
            Path(symposium_repo_root).resolve() != SYMPOSIUM_ROOT
            or expected_labels["symposium_commit"] != SYMPOSIUM_COMMIT
        ):
            raise RuntimeError("live SYMPOSIUM HEAD label drifted")
        verify_repository_dependency_blobs(
            SYMPOSIUM_ROOT,
            SYMPOSIUM_COMMIT,
            expected_paths,
            required_names={"judge_core"},
        )
        return {
            "bundle_sha256": value["bundle_sha256"],
            "compatibility_root_sha256": compatibility,
            "environment_receipt_sha256": environment_sha,
            "dependency_receipt_sha256": dependency_sha,
        }

    monkeypatch.setattr(runner, "verify_r8_preimage_bundle", verify)
    monkeypatch.setattr(
        runner,
        "load_model_deployment_binding",
        lambda *_args, **_kwargs: _deployment_binding(),
    )
    monkeypatch.setattr(
        runner,
        "_replay_token_envelope_derivation",
        lambda *, manifest, token_meter, **_kwargs: _derivation_receipt(
            manifest, token_meter
        )["receipt_sha256"],
    )


def _registries() -> dict[str, object]:
    return {
        arm: build_registry(
            REPO_ROOT / DEFAULT_PROTOCOL,
            model="fake-model",
            model_revision=TEST_REVISION,
            prompt_overrides=_arm_overrides(arm),
        )
        for arm in F1_ARMS
    }


def _items() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(2):
        entity = canonical_sha256(
            {
                "schema_version": "hswm-2wiki-paragraph-source/v1",
                "title": f"Title {index}",
                "sentences": [f"Sentence {index}."],
            }
        )
        component = canonical_sha256(
            {
                "schema_version": "hswm-source-entity-connected-component/v1",
                "source_entity_ids": [entity],
            }
        )
        rows.append(
            {
                "item_id": f"item-{index}",
                "query_text": "What is the answer?",
                "allowed_evidence_types": ["text"],
                "candidates": [
                    {
                        "bond_id": f"bond-{index}",
                        "evidence_id": f"evidence-{index}",
                        "source_entity_id": entity,
                        "content": "Paris is the answer.",
                        "observable": {
                            "flat_position": 0,
                            "flat_score": 1.0,
                            "vector_score": 1.0,
                            "source_type": "text",
                        },
                    }
                ],
                "component_id": component,
                "max_evidence_items": 1,
                "max_input_tokens": 1,
                "max_output_tokens_per_call": 16,
            }
        )
    return rows


def _manifest(meter: FakeMeter) -> dict[str, object]:
    items = _items()
    projected = {arm: {"1": 5, "2": 5, "3": 5} for arm in F1_ARMS}
    caps = compute_minimum_input_caps(
        run_id=runner.DEVELOPMENT_RUN_ID,
        items=[runner._item(value, "fixture") for value in items],
        arms=F1_ARMS,
        registries=_registries(),
        meter=meter,
        projected_outputs=projected,
        slack=4,
    )
    for item in items:
        item["max_input_tokens"] = sum(caps.values())
    return {
        "schema_version": runner.MANIFEST_SCHEMA,
        "run_id": runner.DEVELOPMENT_RUN_ID,
        "mode": "development",
        "model": "fake-model",
        "model_revision": TEST_REVISION,
        "token_tolerance": 32,
        "state_capacity_bytes": 128,
        "state_bytes_by_arm": {arm: 128 for arm in F1_ARMS},
        "preregistration_artifact_sha256": None,
        "generation_policy": copy.deepcopy(GENERATION_POLICY),
        "token_envelope": {
            "schema_version": "hswm-prom9-f1-token-envelope/v1",
            "tokenizer": {**meter.identity(), "validation_receipt_sha256": "b" * 64},
            "filler": {
                "field": "parity_filler",
                "unit": "0",
                "max_filler_chars": 60000,
            },
            "per_call_input_caps": caps,
            "per_call_output_caps": {"1": 16, "2": 16, "3": 16},
            "projected_output_tokens_by_arm": projected,
            "projection_slack_tokens": 4,
        },
        "items": items,
    }


def _derivation_receipt(
    manifest: dict[str, object],
    meter: FakeMeter,
    *,
    development_run_id: str = runner.DEVELOPMENT_RUN_ID,
) -> dict[str, object]:
    registries = _registries()
    envelope = manifest["token_envelope"]
    assert isinstance(envelope, dict)
    input_caps = dict(envelope["per_call_input_caps"])
    output_caps = dict(envelope["per_call_output_caps"])
    cohort = lambda run_id, items, components, marker: {  # noqa: E731
        "run_id": run_id,
        "items": items,
        "components": components,
        "minimum_input_caps": dict(input_caps),
        "projection_sha256": marker * 64,
        "projected_spread": 0,
    }
    unsigned = {
        "schema_version": "hswm-prom9-f1-r8-token-envelope-derivation/v1",
        "derivation_policy": (
            "tight_common_componentwise_max_of_both_frozen_cohorts/v1"
        ),
        "selection_receipt_sha256": "1" * 64,
        "historical_token_envelope_sha256": "2" * 64,
        "historical_input_caps_used_as_floor": False,
        "model": manifest["model"],
        "model_revision": manifest["model_revision"],
        "protocol_sha256": next(iter(registries.values())).protocol_sha256,
        "registries_root_sha256": canonical_sha256(
            {arm: registries[arm].registry_sha256 for arm in F1_ARMS}
        ),
        "token_meter_validation_receipt_sha256": "3" * 64,
        "token_meter": meter.identity(),
        "projected_outputs_receipt_sha256": "4" * 64,
        "source_suite_receipt_sha256": "5" * 64,
        "development": cohort(development_run_id, 54, 48, "6"),
        "confirmatory": cohort(runner.SEALED_RUN_ID, 100, 100, "7"),
        "per_call_input_caps": input_caps,
        "per_call_output_caps": output_caps,
        "total_input_tokens_per_run": sum(input_caps.values()),
        "total_allowed_output_tokens_per_run": sum(output_caps.values()),
        "projection_slack_tokens": envelope["projection_slack_tokens"],
        "token_tolerance": manifest["token_tolerance"],
        "token_envelope_sha256": canonical_sha256(envelope),
        "gold_inputs_read": False,
        "model_calls": 0,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def _derivation_inputs(
    manifest: dict[str, object], meter: FakeMeter
) -> dict[str, object]:
    protocol_path = REPO_ROOT / DEFAULT_PROTOCOL
    return {
        "receipt": _derivation_receipt(manifest, meter),
        "selection_receipt": {
            "schema_version": runner.SUCCESSOR_SELECTION_SCHEMA,
        },
        "historical_manifest": {},
        "validation_receipt": {},
        "projected_outputs_receipt": {},
        "source_suite": {},
        "protocol": json.loads(protocol_path.read_text(encoding="utf-8")),
        "file_sha256s": {
            "selection_receipt": "8" * 64,
            "historical_manifest": "9" * 64,
            "validation_receipt": "a" * 64,
            "projected_outputs_receipt": "b" * 64,
            "source_suite": "c" * 64,
            "protocol": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        },
    }


def _policy() -> dict[str, object]:
    return {
        "endpoint": ENDPOINT,
        "max_workers": 2,
        "timeout_seconds": 180.0,
        "max_delivery_attempts": 8,
        "spool_token_env": "SPOOL_CLIENT_TOKEN",
    }


def _empty_spool_audit() -> dict[str, object]:
    unsigned = {
        "schema_version": SPOOL_SCHEMA,
        "journal_mode": "wal",
        "synchronous": 2,
        "call_count": 0,
        "status_counts": {},
        "completed_root_sha256": canonical_sha256([]),
    }
    return {**unsigned, "audit_sha256": canonical_sha256(unsigned)}


def _preflight(run_id: str, lock_sha: str, genesis_sha: str) -> dict[str, object]:
    identity_unsigned = {
        "schema_version": SPOOL_IDENTITY_SCHEMA,
        "normalized_upstream_endpoint": UPSTREAM_ENDPOINT,
        "deployment_receipt_sha256": DEPLOYMENT_SHA256,
        "deployment_id": f"hswm:model_deployment:v2:{DEPLOYMENT_SHA256}",
        "served_model": "fake-model",
        "model_revision": TEST_REVISION,
        "db_identity": {
            "resolved_path": "/private/spool.sqlite3",
            "st_dev": 7,
            "st_ino": 11,
        },
        "audit": _empty_spool_audit(),
    }
    identity = {
        **identity_unsigned,
        "identity_sha256": canonical_sha256(identity_unsigned),
    }
    unsigned = {
        "schema_version": runner.SPOOL_PREFLIGHT_SCHEMA,
        "run_id": run_id,
        "execution_lock_sha256": lock_sha,
        "db_genesis_sha256": genesis_sha,
        "endpoint": ENDPOINT,
        "upstream_endpoint": UPSTREAM_ENDPOINT,
        "deployment_receipt_sha256": DEPLOYMENT_SHA256,
        "deployment_id": f"hswm:model_deployment:v2:{DEPLOYMENT_SHA256}",
        "served_model": "fake-model",
        "model_revision": TEST_REVISION,
        "endpoint_identity": identity,
    }
    return {**unsigned, "preflight_sha256": canonical_sha256(unsigned)}


def _genesis(run_id: str) -> dict[str, object]:
    unsigned = {
        "schema_version": GENESIS_SCHEMA,
        "run_id": run_id,
        "attempt_integrity": "ok",
        "spool_integrity": "ok",
        "attempt_journal_mode": "wal",
        "attempt_audit_connection_synchronous": "2",
        "spool_journal_mode": "wal",
        "spool_audit_connection_synchronous": "2",
        "attempt_user_version": 1,
        "spool_user_version": 1,
        "attempt_schema_sha256": "1" * 64,
        "spool_schema_sha256": "2" * 64,
        "attempt_db_identity": {
            "resolved_path": "/private/attempt.sqlite3",
            "st_dev": 7,
            "st_ino": 10,
        },
        "spool_db_identity": {
            "resolved_path": "/private/spool.sqlite3",
            "st_dev": 7,
            "st_ino": 11,
        },
        "call_count": 0,
        "item_run_count": 0,
        "attempt_event_count": 0,
        "spool_call_count": 0,
    }
    return {**unsigned, "genesis_sha256": canonical_sha256(unsigned)}


def _bundle(tmp_path: Path, manifest: dict[str, object], result_contract: Path):
    judge_core = SYMPOSIUM_ROOT / _JUDGE_RELATIVE_PATH
    model_catalog = tmp_path / "model_catalog.json"
    model_weight_receipt = tmp_path / "model_weight_receipt.json"
    python_lock = tmp_path / "requirements.lock"
    tokenizer_dir = tmp_path / "tokenizer"
    tokenizer_dir.mkdir()
    for path, payload in (
        (model_catalog, "{}\n"),
        (model_weight_receipt, "{}\n"),
        (python_lock, "pytest==test\n"),
        (tokenizer_dir / "vocab.json", "{}\n"),
        (tokenizer_dir / "merges.txt", "#version: 0.2\n"),
        (tokenizer_dir / "tokenizer_config.json", "{}\n"),
    ):
        path.write_text(payload)
    dependencies = r8_dependency_paths(
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        judge_core_path=judge_core,
        result_contract_path=result_contract,
        tokenizer_dir=tokenizer_dir,
        model_catalog_path=model_catalog,
        model_weight_receipt_path=model_weight_receipt,
        python_lock_path=python_lock,
    )
    assert set(dependencies) == set(REQUIRED_DEPENDENCY_FILES)
    bundle = build_preimage_bundle(
        dependencies,
        labels={
            "spool_endpoint": ENDPOINT,
            "model_upstream_endpoint": UPSTREAM_ENDPOINT,
            "model_deployment_receipt_sha256": DEPLOYMENT_SHA256,
            "hswm_commit": HSWM_COMMIT,
            "model": str(manifest["model"]),
            "model_revision": str(manifest["model_revision"]),
            "run_id": str(manifest["run_id"]),
            "symposium_commit": SYMPOSIUM_COMMIT,
        },
        inline_limit_bytes=1024 * 1024,
    )
    return bundle, {
        "judge_core_path": judge_core,
        "tokenizer_dir": tokenizer_dir,
        "model_catalog_path": model_catalog,
        "model_weight_receipt_path": model_weight_receipt,
        "python_lock_path": python_lock,
    }


@pytest.mark.parametrize(
    ("run_id", "expected_lock", "expected_count"),
    (
        (runner.C800_DEVELOPMENT_RUN_ID, "prom9_f1_r8_lock.py", 34),
        (runner.C801_DEVELOPMENT_RUN_ID, "prom9_f1_r8_lock_v6.py", 36),
        (runner.C801_SEALED_RUN_ID, "prom9_f1_r8_lock_v6.py", 36),
    ),
)
def test_dependency_path_dispatch_is_generation_exact(
    tmp_path: Path,
    run_id: str,
    expected_lock: str,
    expected_count: int,
) -> None:
    paths = runner._r8_dependency_paths_for_run(
        run_id=run_id,
        protocol_path=tmp_path / "protocol.json",
        judge_core_path=tmp_path / "judge.py",
        result_contract_path=tmp_path / "result-contract.json",
        tokenizer_dir=tmp_path / "tokenizer",
        model_catalog_path=tmp_path / "model-catalog.json",
        model_weight_receipt_path=tmp_path / "model-weight.json",
        python_lock_path=tmp_path / "requirements.lock",
    )
    assert paths["lock_builder"].name == expected_lock
    assert len(paths) == expected_count
    c801 = run_id in {
        runner.C801_DEVELOPMENT_RUN_ID,
        runner.C801_SEALED_RUN_ID,
    }
    assert ("selection_builder" in paths) == c801
    assert ("selection_primitives" in paths) == c801
    if c801:
        assert paths["power_builder"].name == "prom9_f1_r8_power_v6.py"
        assert paths["power_cli"].name == "prom9_f1_r8_power_cli_v6.py"


def _prior_exposure() -> dict[str, object]:
    items = ["prior-item"]
    source_entities = ["8" * 64]
    components = ["9" * 64]
    unsigned = {
        "schema_version": PRIOR_EXPOSURE_SCHEMA,
        "aggregate": {
            "prior_item_ids": items,
            "prior_source_entity_ids": source_entities,
            "prior_component_ids": components,
            "item_root_sha256": canonical_sha256(items),
            "source_entity_root_sha256": canonical_sha256(source_entities),
            "component_root_sha256": canonical_sha256(components),
        },
        "complete": True,
    }
    return {
        **unsigned,
        "prior_exposure_receipt_sha256": canonical_sha256(unsigned),
    }


def _lock(
    manifest: dict[str, object],
    *,
    prior_exposure_receipt: dict[str, object],
    aborted_attempt_exposure_receipt: dict[str, object],
    bundle: dict[str, object],
    result_contract: Path,
    genesis_sha: str,
    derivation_receipt_sha256: str,
) -> dict[str, object]:
    environment = bundle["environment_receipt"]
    dependencies = bundle["dependency_receipt"]
    assert isinstance(environment, dict) and isinstance(dependencies, dict)
    exposure_union = merge_exposure_boundaries(
        prior_exposure_receipt, aborted_attempt_exposure_receipt
    )
    return build_development_execution_lock(
        manifest,
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        selection_receipt_sha256="1" * 64,
        prior_exposure_receipt_sha256=str(
            exposure_union["prior_exposure_receipt_sha256"]
        ),
        aborted_attempt_exposure_receipt_sha256=str(
            aborted_attempt_exposure_receipt[
                "aborted_attempt_exposure_receipt_sha256"
            ]
        ),
        public_source_receipt_sha256="3" * 64,
        gold_source_receipt_sha256="4" * 64,
        gold_sha256="5" * 64,
        evaluator_receipt_sha256="6" * 64,
        db_genesis_receipt_sha256=genesis_sha,
        environment_receipt_sha256=str(environment["receipt_sha256"]),
        dependency_receipt_sha256=str(dependencies["receipt_sha256"]),
        environment_dependency_compatibility_root_sha256=str(
            bundle["compatibility_root_sha256"]
        ),
        environment_dependency_bundle_sha256=str(bundle["bundle_sha256"]),
        hswm_commit=HSWM_COMMIT,
        result_contract_sha256=hashlib.sha256(result_contract.read_bytes()).hexdigest(),
        judge_core_sha256="a" * 64,
        judge_core_file_sha256="b" * 64,
        token_envelope_derivation_receipt_sha256=(
            derivation_receipt_sha256
        ),
        deployment_binding=_deployment_binding(),
        forbidden_prior_item_ids=list(exposure_union["item_ids"]),
        forbidden_prior_source_entity_ids=list(
            exposure_union["source_entity_ids"]
        ),
        forbidden_prior_component_ids=list(exposure_union["component_ids"]),
        execution_policy=_policy(),
    )


def _context(tmp_path: Path) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    meter = FakeMeter()
    manifest = _manifest(meter)
    derivation = _derivation_inputs(manifest, meter)
    result_contract = tmp_path / "result_contract.v1.json"
    result_contract.write_text('{"schema_version":"result-contract/v1"}\n')
    bundle, dependency_args = _bundle(tmp_path, manifest, result_contract)
    genesis = _genesis(str(manifest["run_id"]))
    aborted_exposure = json.loads(
        ABORTED_ATTEMPT_EXPOSURE_PATH.read_text(encoding="utf-8")
    )
    assert isinstance(aborted_exposure, dict)
    prior_exposure = _prior_exposure()
    exposure_union = merge_exposure_boundaries(
        prior_exposure, aborted_exposure
    )
    lock = _lock(
        manifest,
        prior_exposure_receipt=prior_exposure,
        aborted_attempt_exposure_receipt=aborted_exposure,
        bundle=bundle,
        result_contract=result_contract,
        genesis_sha=str(genesis["genesis_sha256"]),
        derivation_receipt_sha256=str(
            derivation["receipt"]["receipt_sha256"]
        ),
    )
    return {
        "meter": meter,
        "manifest": manifest,
        "result_contract": result_contract,
        "bundle": bundle,
        "genesis": genesis,
        "lock": lock,
        "prior_exposure": prior_exposure,
        "aborted_exposure": aborted_exposure,
        "exposure_union": exposure_union,
        "derivation": derivation,
        "preflight": _preflight(
            str(manifest["run_id"]),
            str(lock["lock_sha256"]),
            str(genesis["genesis_sha256"]),
        ),
        **dependency_args,
    }


def _sealed_preregistration_context(
    context: dict[str, object],
    tmp_path: Path,
    *,
    run_id: str = runner.SEALED_RUN_ID,
):
    sealed_contract = runner._sealed_generation_contract(run_id)
    manifest = copy.deepcopy(context["manifest"])
    manifest["run_id"] = run_id
    manifest["mode"] = "sealed"
    manifest["preregistration_artifact_sha256"] = (
        runner.MANIFEST_PREREGISTRATION_UNFROZEN
    )
    judge = tmp_path / "anchored_judge.py"
    marker = "__F1_R8_MEASUREMENT_LOCK_SHA256_UNFROZEN__"
    template = Path(context["judge_core_path"]).read_text(encoding="utf-8")
    needle = f'EXPECTED_MEASUREMENT_LOCK_SHA256 = "{marker}"'
    assert template.count(needle) == 1
    judge_core_sha = hashlib.sha256(template.encode()).hexdigest()
    lock = copy.deepcopy(context["lock"])
    lock.pop("lock_sha256")
    lock.update(
        {
            "schema_version": runner.SEALED_LOCK_SCHEMA,
            "purpose": sealed_contract["purpose"],
            "experiment_tag": sealed_contract["experiment_tag"],
            "closes_question": sealed_contract["closes_question"],
            "run_id": run_id,
            "mode": "sealed",
            "judge_core_sha256": judge_core_sha,
            "judge_core_file_sha256": hashlib.sha256(template.encode()).hexdigest(),
        }
    )
    c801_generation = run_id == runner.C801_SEALED_RUN_ID
    artifact_unsigned = {
        "schema_version": runner.PREREGISTRATION_ARTIFACT_SCHEMA,
        "purpose": sealed_contract["purpose"],
        "experiment_tag": sealed_contract["experiment_tag"],
        "closes_question": sealed_contract["closes_question"],
        "run_id": run_id,
        "mode": "sealed",
        "hswm_commit": lock["hswm_commit"],
        "model": lock["model"],
        "model_revision": lock["model_revision"],
        "metric": (
            sealed_contract["metric"]
            if c801_generation
            else {"name": "exact_match"}
        ),
        "baseline": sealed_contract["baseline"] if c801_generation else {
            "arm": "flat_single_llm_three_call_workflow"
        },
        "direction": sealed_contract["direction"] if c801_generation else "higher",
        "noise_band": sealed_contract["noise_band"] if c801_generation else {
            "absolute": 0.01
        },
        "credence": 0.25 if c801_generation else {"alpha": 0.05},
        "bootstrap": (
            copy.deepcopy(sealed_contract["bootstrap"])
            if c801_generation
            else {"replicates": 1000}
        ),
        "gates": copy.deepcopy(lock["gates"]),
        "predicted_outcome": copy.deepcopy(sealed_contract["predicted_outcome"]),
        "falsification_condition": copy.deepcopy(
            sealed_contract["falsification_condition"]
        ),
        "manifest_core_sha256": runner.manifest_core_sha256(manifest),
        "judge_core_sha256": judge_core_sha,
        "result_contract_sha256": lock["result_contract_sha256"],
        "measurement_lock_schema_sha256": canonical_sha256(
            {"schema_version": runner.SEALED_LOCK_SCHEMA}
        ),
        "result_bundle_builder_sha256": "c" * 64,
        "power_operating_characteristic_receipt_sha256": "d" * 64,
        "calibration_receipt_sha256": "e" * 64,
        "selection_receipt_sha256": lock["selection_receipt_sha256"],
        "prior_exposure_receipt_sha256": lock["prior_exposure_receipt_sha256"],
        "aborted_attempt_exposure_receipt_sha256": lock[
            "aborted_attempt_exposure_receipt_sha256"
        ],
        "public_source_receipt_sha256": lock["public_source_receipt_sha256"],
        "gold_source_receipt_sha256": lock["gold_source_receipt_sha256"],
        "gold_sha256": lock["gold_sha256"],
        "evaluator_receipt_sha256": lock["evaluator_receipt_sha256"],
        "db_genesis_receipt_sha256": lock["db_genesis_receipt_sha256"],
        "environment_receipt_sha256": lock["environment_receipt_sha256"],
        "dependency_receipt_sha256": lock["dependency_receipt_sha256"],
        "environment_dependency_compatibility_root_sha256": lock[
            "environment_dependency_compatibility_root_sha256"
        ],
        "environment_dependency_bundle_sha256": lock[
            "environment_dependency_bundle_sha256"
        ],
        "protocol_sha256": lock["protocol_sha256"],
        "registries_root_sha256": lock["registries_root_sha256"],
        "token_envelope_sha256": lock["token_envelope_sha256"],
        "token_envelope_derivation_receipt_sha256": lock[
            "token_envelope_derivation_receipt_sha256"
        ],
        "generation_policy_sha256": lock["generation_policy_sha256"],
        "cohort_root_sha256": lock["cohort_root_sha256"],
        "candidate_universe_root_sha256": lock[
            "candidate_universe_root_sha256"
        ],
        "forbidden_prior_item_ids": copy.deepcopy(lock["forbidden_prior_item_ids"]),
        "forbidden_prior_source_entity_ids": copy.deepcopy(
            lock["forbidden_prior_source_entity_ids"]
        ),
        "forbidden_prior_component_ids": copy.deepcopy(
            lock["forbidden_prior_component_ids"]
        ),
    }
    artifact = {
        **artifact_unsigned,
        "preregistration_artifact_sha256": canonical_sha256(artifact_unsigned),
    }
    manifest["preregistration_artifact_sha256"] = artifact[
        "preregistration_artifact_sha256"
    ]
    lock["preregistration_artifact_sha256"] = artifact[
        "preregistration_artifact_sha256"
    ]
    lock["manifest_sha256"] = canonical_sha256(manifest)
    lock["lock_sha256"] = canonical_sha256(lock)
    judge.write_text(
        template.replace(
            needle,
            f'EXPECTED_MEASUREMENT_LOCK_SHA256 = "{lock["lock_sha256"]}"',
        )
    )
    full_judge_sha = hashlib.sha256(judge.read_bytes()).hexdigest()
    readback_unsigned = {
        "schema_version": runner.PREREGISTRATION_READBACK_SCHEMA,
        "purpose": sealed_contract["purpose"],
        "experiment_tag": sealed_contract["experiment_tag"],
        "closes_question": sealed_contract["closes_question"],
        "run_id": run_id,
        "measurement_lock_sha256": lock["lock_sha256"],
        "preregistration_artifact_sha256": artifact[
            "preregistration_artifact_sha256"
        ],
        "external_prediction_receipt_sha256": "f" * 64,
        "external_record_identity": "external-record-1",
        "canonical_readback_sha256": "1" * 64,
        "pred_script_sha256": full_judge_sha,
        "anchored_judge_file_sha256": full_judge_sha,
        "judge_core_sha256": judge_core_sha,
        "result_contract_sha256": lock["result_contract_sha256"],
    }
    readback = {
        **readback_unsigned,
        "receipt_sha256": canonical_sha256(readback_unsigned),
    }
    return manifest, lock, artifact, readback, judge


def _dependency_kwargs(context: dict[str, object]) -> dict[str, Path]:
    return {
        "judge_core_path": context["judge_core_path"],
        "symposium_repo_root": SYMPOSIUM_ROOT,
        "tokenizer_dir": context["tokenizer_dir"],
        "model_catalog_path": context["model_catalog_path"],
        "model_weight_receipt_path": context["model_weight_receipt_path"],
        "python_lock_path": context["python_lock_path"],
    }


def _model_response(call: ModelCallV1, meter: FakeMeter) -> ModelResponseV1:
    request_id = str(call.input_payload["request_id"])
    if call.function_id == "QF_QUERY_COMPILER":
        payload = {
            "request_id": request_id,
            "objectives": ["answer"],
            "required_evidence_types": ["text"],
            "constraints": ["evidence only"],
            "abstain": False,
        }
    elif call.function_id == "BF_BOND_PROPOSER":
        table = call.input_payload["candidate_table"]
        bond_index = table["columns"].index("bond_id")
        evidence_index = table["columns"].index("evidence_id")
        selected = table["rows"][0]
        payload = {
            "request_id": request_id,
            "ordered_bond_ids": [selected[bond_index]],
            "bond_potentials": {selected[bond_index]: 0.0},
            "evidence_refs": [selected[evidence_index]],
            "abstain": False,
        }
    else:
        evidence = call.input_payload["selected_evidence"]
        payload = {
            "request_id": request_id,
            "answer": "Paris" if call.arm_id == TYPED_ARM else "Lyon",
            "supporting_evidence_ids": (
                [evidence[0]["evidence_id"]] if evidence else []
            ),
            "uncertainty": "",
            "abstain": not bool(evidence),
        }
    return ModelResponseV1(
        payload=payload,
        model=call.model,
        model_revision=call.model_revision,
        input_tokens=meter.count_chat_prompt(
            call.system_prompt, canonical_json(call.input_payload)
        ),
        output_tokens=5,
        latency_ms=1,
    )


def _material(call: ModelCallV1, receipt: dict[str, object]) -> dict[str, object]:
    request_bytes = canonical_json(DurableSpoolJSONPort._request_body(call)).encode()
    intent_bytes = canonical_json(
        {
            "schema_version": DURABLE_CALL_SCHEMA,
            "spool_route": f"{ENDPOINT}/v1/hswm/calls/{call.physical_call_id}",
            "call": {
                "physical_call_id": call.physical_call_id,
                "run_id": call.run_id,
                "arm_id": call.arm_id,
                "item_id": call.item_id,
                "call_index": call.call_index,
                "function_id": call.function_id,
                "model": call.model,
                "model_revision": call.model_revision,
                "system_prompt": call.system_prompt,
                "input_type": call.input_type,
                "input_payload": call.input_payload,
                "output_type": call.output_type,
                "max_output_tokens": call.max_output_tokens,
            },
            "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
            "output_schema_sha256": output_schema_sha256(call.output_type),
        }
    ).encode()
    model_response_bytes = canonical_json(
        {
            "payload": receipt["output_payload"],
            "model": receipt["model"],
            "model_revision": receipt["model_revision"],
            "input_tokens": receipt["input_tokens"],
            "output_tokens": receipt["output_tokens"],
            "latency_ms": receipt["latency_ms"],
            "cache_status": receipt["cache_status"],
            "retries": receipt["retries"],
        }
    ).encode()
    response_bytes = canonical_json(
        {
            "model": receipt["model"],
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": canonical_json(receipt["output_payload"]),
                    },
                }
            ],
            "usage": {
                "prompt_tokens": receipt["input_tokens"],
                "completion_tokens": receipt["output_tokens"],
            },
        }
    ).encode()
    return {
        "intent": intent_bytes,
        "request": request_bytes,
        "model_response": model_response_bytes,
        "response": response_bytes,
    }


def _events(physical_ids: list[str]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    previous = "0" * 64
    event_types = (
        "PREPARED", "SENT", "RAW_COMPLETE", "ENVELOPE_VALID",
        "SCHEMA_VALID", "ACCEPTED",
    )
    for physical_id in sorted(physical_ids):
        for event_type in event_types:
            value = {
                "schema_version": DURABLE_CALL_SCHEMA,
                "sequence": len(result),
                "physical_call_id": physical_id,
                "event_type": event_type,
                "detail": {},
                "previous_event_sha256": previous,
            }
            raw = canonical_json(value).encode()
            event_sha = hashlib.sha256(raw).hexdigest()
            result.append(
                {
                    "sequence": len(result),
                    "physical_call_id": physical_id,
                    "event_type": event_type,
                    "previous_event_sha256": previous,
                    "event_sha256": event_sha,
                    "event_bytes_b64": base64.b64encode(raw).decode(),
                }
            )
            previous = event_sha
    return result


class FakeDurablePort:
    def __init__(self, meter: FakeMeter) -> None:
        self.meter = meter
        self.spool_endpoint = ENDPOINT
        self.timeout_seconds = 180.0
        self.max_delivery_attempts = 8
        self.spool_token_env = "SPOOL_CLIENT_TOKEN"
        self.calls: dict[str, ModelCallV1] = {}
        self.receipts: dict[str, dict[str, object]] = {}
        self.item_runs: list[dict[str, object]] = []
        self._lock = threading.Lock()

    def __call__(self, call: ModelCallV1) -> ModelResponseV1:
        with self._lock:
            self.calls[call.physical_call_id] = call
        return _model_response(call, self.meter)

    def accept_call_receipt(self, receipt) -> None:
        with self._lock:
            self.receipts[receipt.physical_call_id] = receipt.canonical()

    def accept_item_run(self, value: dict[str, object]) -> None:
        with self._lock:
            self.item_runs.append(value)

    def audit(self) -> dict[str, object]:
        with self._lock:
            ids = sorted(self.receipts)
            accepted = []
            spool = []
            for physical_id in ids:
                material = _material(self.calls[physical_id], self.receipts[physical_id])
                binding = {
                    "physical_call_id": physical_id,
                    "intent_sha256": hashlib.sha256(material["intent"]).hexdigest(),
                    "request_sha256": hashlib.sha256(material["request"]).hexdigest(),
                    "response_sha256": hashlib.sha256(material["response"]).hexdigest(),
                }
                spool.append(binding)
                accepted.append(
                    {
                        **binding,
                        "call_receipt_sha256": self.receipts[physical_id][
                            "receipt_sha256"
                        ],
                    }
                )
            item_bindings = sorted(
                (
                    {
                        "run_id": row["run_id"],
                        "arm_id": row["arm_id"],
                        "item_id": row["item_id"],
                        "run_receipt_sha256": row["run_receipt_sha256"],
                    }
                    for row in self.item_runs
                ),
                key=lambda row: (row["run_id"], row["arm_id"], row["item_id"]),
            )
            events = _events(ids)
            unsigned = {
                "schema_version": DURABLE_CALL_SCHEMA,
                "journal_mode": "wal",
                "synchronous": 2,
                "event_chain_tip_sha256": (
                    events[-1]["event_sha256"] if events else "0" * 64
                ),
                "call_count": len(ids),
                "status_counts": ({"ACCEPTED": len(ids)} if ids else {}),
                "accepted_call_root_sha256": canonical_sha256(accepted),
                "spool_binding_root_sha256": canonical_sha256(spool),
                "item_run_count": len(item_bindings),
                "item_run_root_sha256": canonical_sha256(item_bindings),
            }
            return {**unsigned, "audit_sha256": canonical_sha256(unsigned)}


def _run(context: dict[str, object]) -> tuple[dict[str, object], FakeDurablePort]:
    port = FakeDurablePort(context["meter"])
    draft = run_suite_v3_draft(
        context["manifest"],
        execution_lock=context["lock"],
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        model_port=port,
        token_meter=context["meter"],
        max_workers=2,
        token_envelope_derivation=context["derivation"],
        prior_exposure_receipt=context["prior_exposure"],
        aborted_attempt_exposure_receipt=context["aborted_exposure"],
        environment_dependency_bundle=context["bundle"],
        result_contract_path=context["result_contract"],
        **_dependency_kwargs(context),
        spool_identity_preflight=context["preflight"],
    )
    return draft, port


def _resume_prefix_for_draft(
    context: dict[str, object],
    draft: dict[str, object],
    port: FakeDurablePort,
) -> tuple[dict[str, object], list[tuple[str, str]]]:
    items = context["manifest"]["items"]
    assert isinstance(items, list)
    jobs = [
        (str(item["item_id"]), arm)
        for item in sorted(items, key=lambda value: str(value["item_id"]))
        for arm in F1_ARMS
    ]
    attempt_audit = port.audit()
    spool_unsigned = {
        "schema_version": SPOOL_SCHEMA,
        "journal_mode": "wal",
        "synchronous": 2,
        "call_count": attempt_audit["call_count"],
        "status_counts": {"COMPLETE": attempt_audit["call_count"]},
        "completed_root_sha256": attempt_audit["spool_binding_root_sha256"],
    }
    spool_audit = {
        **spool_unsigned,
        "audit_sha256": canonical_sha256(spool_unsigned),
    }
    call_positions = [
        {
            "job_ordinal": ordinal,
            "item_id": item_id,
            "arm_id": arm_id,
            "call_indices": [1, 2, 3],
            "item_run_committed": True,
        }
        for ordinal, (item_id, arm_id) in enumerate(jobs)
    ]
    events = _events(sorted(port.receipts))
    unsigned = {
        "schema_version": runner.RESUME_PREFIX_SCHEMA,
        "run_id": draft["run_id"],
        "db_genesis_sha256": context["genesis"]["genesis_sha256"],
        "attempt_integrity": "ok",
        "spool_integrity": "ok",
        "attempt_db_identity": context["genesis"]["attempt_db_identity"],
        "spool_db_identity": context["genesis"]["spool_db_identity"],
        "ordered_job_root_sha256": canonical_sha256(
            [
                {"item_id": item_id, "arm_id": arm_id}
                for item_id, arm_id in jobs
            ]
        ),
        "job_count": len(jobs),
        "max_workers": 2,
        "frontier_batch": (len(jobs) - 1) // 2,
        "call_positions": call_positions,
        "call_count": attempt_audit["call_count"],
        "item_run_count": len(jobs),
        "attempt_event_count": len(events),
        "spool_call_count": attempt_audit["call_count"],
        "event_chain_tip_sha256": attempt_audit["event_chain_tip_sha256"],
        "attempt_event_root_sha256": canonical_sha256(events),
        "attempt_live_audit": attempt_audit,
        "spool_live_audit": spool_audit,
        "zero_count_genesis": False,
    }
    return {
        **unsigned,
        "resume_prefix_sha256": canonical_sha256(unsigned),
    }, jobs


def _resign_resume_prefix(value: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(value)
    unsigned = dict(result)
    unsigned.pop("resume_prefix_sha256", None)
    result["resume_prefix_sha256"] = canonical_sha256(unsigned)
    return result


def _transport_bindings(
    draft: dict[str, object], port: FakeDurablePort, genesis: dict[str, object]
) -> dict[str, object]:
    accepted: list[dict[str, object]] = []
    auxiliary: list[dict[str, object]] = []
    spool_preimages: list[dict[str, object]] = []
    for physical_id in sorted(port.receipts):
        receipt = port.receipts[physical_id]
        material = _material(port.calls[physical_id], receipt)
        accepted_row = {
            "physical_call_id": physical_id,
            "intent_sha256": hashlib.sha256(material["intent"]).hexdigest(),
            "request_sha256": hashlib.sha256(material["request"]).hexdigest(),
            "response_sha256": hashlib.sha256(material["response"]).hexdigest(),
            "model_response_sha256": hashlib.sha256(
                material["model_response"]
            ).hexdigest(),
            "call_receipt_sha256": receipt["receipt_sha256"],
            "response_status": 200,
            "intent_bytes_b64": base64.b64encode(material["intent"]).decode(),
            "request_bytes_b64": base64.b64encode(material["request"]).decode(),
            "response_body_b64": base64.b64encode(material["response"]).decode(),
            "model_response_bytes_b64": base64.b64encode(
                material["model_response"]
            ).decode(),
        }
        accepted.append(accepted_row)
        headers = b"{}"
        receipt_bytes = canonical_json(receipt).encode()
        auxiliary.append(
            {
                "physical_call_id": physical_id,
                "endpoint": f"{ENDPOINT}/v1/hswm/calls/{physical_id}",
                "response_headers_sha256": hashlib.sha256(headers).hexdigest(),
                "response_headers_b64": base64.b64encode(headers).decode(),
                "call_receipt_bytes_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
                "call_receipt_bytes_b64": base64.b64encode(receipt_bytes).decode(),
            }
        )
        spool_preimages.append(
            {
                "physical_call_id": physical_id,
                "intent_sha256": accepted_row["intent_sha256"],
                "request_sha256": accepted_row["request_sha256"],
                "response_sha256": accepted_row["response_sha256"],
                "status": "COMPLETE",
                "response_status": 200,
                "request_bytes_b64": accepted_row["request_bytes_b64"],
                "response_headers_sha256": hashlib.sha256(headers).hexdigest(),
                "response_headers_b64": base64.b64encode(headers).decode(),
                "response_body_b64": accepted_row["response_body_b64"],
                "error_class": None,
            }
        )
    spool = [
        {
            key: row[key]
            for key in (
                "physical_call_id", "intent_sha256", "request_sha256",
                "response_sha256",
            )
        }
        for row in accepted
    ]
    item_rows = sorted(
        draft["item_runs"],
        key=lambda row: (row["run_id"], row["arm_id"], row["item_id"]),
    )
    item_bindings = [
        {
            "run_id": row["run_id"],
            "arm_id": row["arm_id"],
            "item_id": row["item_id"],
            "run_receipt_sha256": row["run_receipt_sha256"],
        }
        for row in item_rows
    ]
    item_preimages = []
    for row in item_rows:
        raw = canonical_json(row).encode()
        item_preimages.append(
            {
                "run_id": row["run_id"],
                "arm_id": row["arm_id"],
                "item_id": row["item_id"],
                "run_receipt_sha256": row["run_receipt_sha256"],
                "item_run_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                "item_run_bytes_b64": base64.b64encode(raw).decode(),
            }
        )
    events = _events([str(row["physical_call_id"]) for row in accepted])
    minimal = [
        {
            key: row[key]
            for key in (
                "physical_call_id", "intent_sha256", "request_sha256",
                "response_sha256", "call_receipt_sha256",
            )
        }
        for row in accepted
    ]
    unsigned = {
        "schema_version": TRANSPORT_BINDINGS_SCHEMA,
        "run_id": draft["run_id"],
        "db_genesis_sha256": genesis["genesis_sha256"],
        **{
            field: genesis[field]
            for field in (
                "attempt_integrity", "spool_integrity", "attempt_journal_mode",
                "attempt_audit_connection_synchronous", "spool_journal_mode",
                "spool_audit_connection_synchronous", "attempt_user_version",
                "spool_user_version", "attempt_schema_sha256",
                "spool_schema_sha256", "attempt_db_identity", "spool_db_identity",
            )
        },
        "call_count": len(accepted),
        "item_run_count": len(item_bindings),
        "attempt_event_count": len(events),
        "spool_call_count": len(spool),
        "attempt_status_counts": {"ACCEPTED": len(accepted)},
        "spool_status_counts": {"COMPLETE": len(spool)},
        "spool_unknown_count": 0,
        "identity_conflict_count": 0,
        "event_chain_tip_sha256": events[-1]["event_sha256"],
        "accepted_call_root_sha256": canonical_sha256(minimal),
        "accepted_call_export_root_sha256": canonical_sha256(accepted),
        "accepted_call_auxiliary_root_sha256": canonical_sha256(auxiliary),
        "spool_binding_root_sha256": canonical_sha256(spool),
        "spool_preimage_root_sha256": canonical_sha256(spool_preimages),
        "item_run_root_sha256": canonical_sha256(item_bindings),
        "item_run_preimage_root_sha256": canonical_sha256(item_preimages),
        "attempt_event_root_sha256": canonical_sha256(events),
        "accepted_calls": accepted,
        "accepted_call_auxiliary_preimages": auxiliary,
        "spool_bindings": spool,
        "spool_call_preimages": spool_preimages,
        "item_run_bindings": item_bindings,
        "item_run_preimages": item_preimages,
        "attempt_events": events,
    }
    return {**unsigned, "bindings_sha256": canonical_sha256(unsigned)}


def _rehash(value: dict[str, object], field: str) -> None:
    unsigned = dict(value)
    unsigned.pop(field, None)
    value[field] = canonical_sha256(unsigned)


def test_run_is_full_preflight_bound_and_gold_blind(tmp_path: Path) -> None:
    context = _context(tmp_path)
    assert context["manifest"]["run_id"] == runner.F1_R8_A3_SUCCESSOR_RUN_ID
    assert context["lock"]["schema_version"] == (
        "hswm-prom9-f1-r8-execution-lock/v4"
    )
    assert context["lock"]["aborted_attempt_exposure_receipt_sha256"] == (
        context["aborted_exposure"][
            "aborted_attempt_exposure_receipt_sha256"
        ]
    )
    assert context["lock"]["prior_exposure_receipt_sha256"] == context[
        "prior_exposure"
    ]["prior_exposure_receipt_sha256"]
    assert context["lock"]["forbidden_prior_item_ids"] == context[
        "exposure_union"
    ]["item_ids"]
    assert context["lock"]["forbidden_prior_source_entity_ids"] == context[
        "exposure_union"
    ]["source_entity_ids"]
    assert context["lock"]["forbidden_prior_component_ids"] == context[
        "exposure_union"
    ]["component_ids"]
    draft, port = _run(context)
    assert len(draft["item_runs"]) == 10
    assert len(port.receipts) == 30
    assert draft["pre_call_transport_audit"]["call_count"] == 0
    assert draft["live_transport_audit"]["call_count"] == 30
    assert draft["spool_identity_preflight"] == context["preflight"]
    assert draft["environment_dependency_bundle_sha256"] == context["bundle"][
        "bundle_sha256"
    ]
    assert draft["gold_opened"] is False
    forbidden = {
        item["component_id"] for item in context["manifest"]["items"]
    } | {
        candidate["source_entity_id"]
        for item in context["manifest"]["items"]
        for candidate in item["candidates"]
    }
    prompt_bytes = canonical_json(
        [call.input_payload for call in port.calls.values()]
    )
    assert all(value not in prompt_bytes for value in forbidden)


def test_resume_prefix_binds_frozen_jobs_workers_and_precedes_model_calls(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    draft, completed_port = _run(context)
    prefix, jobs = _resume_prefix_for_draft(context, draft, completed_port)
    validated = runner._validate_resume_prefix(
        prefix,
        run_id=str(draft["run_id"]),
        db_genesis_sha256=str(context["genesis"]["genesis_sha256"]),
        ordered_jobs=jobs,
        max_workers=2,
    )
    assert validated == prefix

    wrong_width = copy.deepcopy(prefix)
    wrong_width["max_workers"] = 1
    wrong_width = _resign_resume_prefix(wrong_width)
    with pytest.raises(R8RunnerRefusal, match="job universe or worker width"):
        runner._validate_resume_prefix(
            wrong_width,
            run_id=str(draft["run_id"]),
            db_genesis_sha256=str(context["genesis"]["genesis_sha256"]),
            ordered_jobs=jobs,
            max_workers=2,
        )

    truncated = copy.deepcopy(prefix)
    truncated["job_count"] = len(jobs) - 1
    truncated["ordered_job_root_sha256"] = canonical_sha256(
        [
            {"item_id": item_id, "arm_id": arm_id}
            for item_id, arm_id in jobs[:-1]
        ]
    )
    truncated = _resign_resume_prefix(truncated)
    with pytest.raises(R8RunnerRefusal, match="job universe or worker width"):
        runner._validate_resume_prefix(
            truncated,
            run_id=str(draft["run_id"]),
            db_genesis_sha256=str(context["genesis"]["genesis_sha256"]),
            ordered_jobs=jobs,
            max_workers=2,
        )

    empty_port = FakeDurablePort(context["meter"])
    with pytest.raises(R8RunnerRefusal, match="differs from the resume prefix"):
        run_suite_v3_draft(
            context["manifest"],
            execution_lock=context["lock"],
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            model_port=empty_port,
            token_meter=context["meter"],
            max_workers=2,
            token_envelope_derivation=context["derivation"],
            prior_exposure_receipt=context["prior_exposure"],
            aborted_attempt_exposure_receipt=context["aborted_exposure"],
            environment_dependency_bundle=context["bundle"],
            result_contract_path=context["result_contract"],
            **_dependency_kwargs(context),
            spool_identity_preflight=context["preflight"],
            resume_prefix=prefix,
        )
    assert empty_port.calls == {}


def test_sealed_preregistration_readback_and_manifest_core_are_exact(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path / "development")
    manifest, lock, artifact, readback, judge = _sealed_preregistration_context(
        context, tmp_path
    )
    assert lock["schema_version"] == "hswm-prom9-f1-r8-measurement-lock/v6"
    assert artifact["schema_version"] == (
        "hswm-prom9-f1-r8-preregistration-artifact/v4"
    )
    placeholder = copy.deepcopy(manifest)
    placeholder["preregistration_artifact_sha256"] = (
        runner.MANIFEST_PREREGISTRATION_UNFROZEN
    )
    assert runner.manifest_core_sha256(placeholder) == runner.manifest_core_sha256(
        manifest
    )
    validate_manifest_v3(
        manifest,
        execution_lock=lock,
        token_meter=context["meter"],
        registries=_registries(),
    )
    runner._validate_preregistration_gate(
        mode="sealed",
        manifest=manifest,
        execution_lock=lock,
        preregistration_artifact=artifact,
        preregistration_readback=readback,
        anchored_judge_path=judge,
        judge_core_path=context["judge_core_path"],
        symposium_repo_root=SYMPOSIUM_ROOT,
        result_contract_path=context["result_contract"],
    )
    drifted_prediction = copy.deepcopy(artifact)
    drifted_prediction["predicted_outcome"]["operator"] = ">="
    with pytest.raises(R8RunnerRefusal, match="prediction/falsifier"):
        runner._validate_preregistration_gate(
            mode="sealed",
            manifest=manifest,
            execution_lock=lock,
            preregistration_artifact=drifted_prediction,
            preregistration_readback=readback,
            anchored_judge_path=judge,
            judge_core_path=context["judge_core_path"],
            symposium_repo_root=SYMPOSIUM_ROOT,
            result_contract_path=context["result_contract"],
        )
    with pytest.raises(R8RunnerRefusal, match="complete preregistration"):
        runner._validate_preregistration_gate(
            mode="sealed",
            manifest=manifest,
            execution_lock=lock,
            preregistration_artifact=None,
            preregistration_readback=None,
            anchored_judge_path=None,
            judge_core_path=context["judge_core_path"],
            symposium_repo_root=SYMPOSIUM_ROOT,
            result_contract_path=context["result_contract"],
        )
    changed = copy.deepcopy(manifest)
    changed["items"][0]["query_text"] = "changed after preregistration"
    with pytest.raises(R8RunnerRefusal, match="manifest/lock-bound"):
        runner._validate_preregistration_gate(
            mode="sealed",
            manifest=changed,
            execution_lock=lock,
            preregistration_artifact=artifact,
            preregistration_readback=readback,
            anchored_judge_path=judge,
            judge_core_path=context["judge_core_path"],
            symposium_repo_root=SYMPOSIUM_ROOT,
            result_contract_path=context["result_contract"],
        )
    drifted_core_lock = copy.deepcopy(lock)
    drifted_core_lock["judge_core_file_sha256"] = "0" * 64
    with pytest.raises(R8RunnerRefusal, match="judge core differs"):
        runner._validate_preregistration_gate(
            mode="sealed",
            manifest=manifest,
            execution_lock=drifted_core_lock,
            preregistration_artifact=artifact,
            preregistration_readback=readback,
            anchored_judge_path=judge,
            judge_core_path=context["judge_core_path"],
            symposium_repo_root=SYMPOSIUM_ROOT,
            result_contract_path=context["result_contract"],
        )


def test_c801_sealed_preregistration_uses_exact_utility_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context(tmp_path / "development")
    manifest, lock, artifact, readback, judge = _sealed_preregistration_context(
        context,
        tmp_path,
        run_id=runner.C801_SEALED_RUN_ID,
    )
    assert artifact["predicted_outcome"] == runner.UTILITY_PREDICTED_OUTCOME
    assert (
        artifact["falsification_condition"]
        == runner.UTILITY_FALSIFICATION_CONDITION
    )
    assert artifact["metric"] == runner._SEALED_GENERATION_CONTRACTS[
        runner.C801_SEALED_RUN_ID
    ]["metric"]
    assert artifact["baseline"] == 0
    assert artifact["direction"] == "higher"
    assert artifact["noise_band"] == 0
    assert artifact["bootstrap"] == runner.C801_BOOTSTRAP
    validate_manifest_v3(
        manifest,
        execution_lock=lock,
        token_meter=context["meter"],
        registries=_registries(),
    )
    with pytest.raises(R8RunnerRefusal, match="explicit user verdict"):
        runner._validate_preregistration_gate(
            mode="sealed",
            manifest=manifest,
            execution_lock=lock,
            preregistration_artifact=artifact,
            preregistration_readback=readback,
            anchored_judge_path=judge,
            judge_core_path=context["judge_core_path"],
            symposium_repo_root=SYMPOSIUM_ROOT,
            result_contract_path=context["result_contract"],
        )
    monkeypatch.setattr(runner, "C801_CREDENCE_SELECTED", 0.25)
    runner._validate_preregistration_gate(
        mode="sealed",
        manifest=manifest,
        execution_lock=lock,
        preregistration_artifact=artifact,
        preregistration_readback=readback,
        anchored_judge_path=judge,
        judge_core_path=context["judge_core_path"],
        symposium_repo_root=SYMPOSIUM_ROOT,
        result_contract_path=context["result_contract"],
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("metric", "f1_min_paired_component_cluster_bootstrap_lcb", "scalar"),
        ("baseline", False, "scalar"),
        ("baseline", 1, "scalar"),
        ("direction", "lower", "scalar"),
        ("noise_band", False, "scalar"),
        ("noise_band", 0.01, "scalar"),
        ("credence", 0.50, "credence"),
        ("credence", False, "credence"),
    ),
)
def test_c801_preregistration_refuses_scientific_scalar_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    context = _context(tmp_path / "development")
    manifest, lock, artifact, readback, judge = _sealed_preregistration_context(
        context,
        tmp_path,
        run_id=runner.C801_SEALED_RUN_ID,
    )
    monkeypatch.setattr(runner, "C801_CREDENCE_SELECTED", 0.25)
    artifact[field] = value
    with pytest.raises(R8RunnerRefusal, match=message):
        runner._validate_preregistration_gate(
            mode="sealed",
            manifest=manifest,
            execution_lock=lock,
            preregistration_artifact=artifact,
            preregistration_readback=readback,
            anchored_judge_path=judge,
            judge_core_path=context["judge_core_path"],
            symposium_repo_root=SYMPOSIUM_ROOT,
            result_contract_path=context["result_contract"],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("reps", 9999),
        ("seed", 20260725),
        ("lower_index", 250),
        ("upper_index", 9750),
        ("paired", False),
        ("paired", 1),
        ("unit", "item_macro"),
        ("method", "unpaired_bootstrap"),
        ("minimum_clusters", 799),
        ("metric", "one_control_lcb"),
    ),
)
def test_c801_preregistration_refuses_bootstrap_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    context = _context(tmp_path / "development")
    manifest, lock, artifact, readback, judge = _sealed_preregistration_context(
        context,
        tmp_path,
        run_id=runner.C801_SEALED_RUN_ID,
    )
    monkeypatch.setattr(runner, "C801_CREDENCE_SELECTED", 0.25)
    artifact["bootstrap"][field] = value
    with pytest.raises(R8RunnerRefusal, match="paired-bootstrap"):
        runner._validate_preregistration_gate(
            mode="sealed",
            manifest=manifest,
            execution_lock=lock,
            preregistration_artifact=artifact,
            preregistration_readback=readback,
            anchored_judge_path=judge,
            judge_core_path=context["judge_core_path"],
            symposium_repo_root=SYMPOSIUM_ROOT,
            result_contract_path=context["result_contract"],
        )


@pytest.mark.parametrize(
    "run_id",
    (runner.C800_SEALED_RUN_ID, "f1-2wiki-sealed-r8-unknown"),
)
def test_unratified_sealed_generation_is_refused(run_id: str) -> None:
    with pytest.raises(R8RunnerRefusal, match="ratified run identity"):
        runner._sealed_generation_contract(run_id)


@pytest.mark.parametrize(
    ("selection_schema", "development_run_id"),
    (
        (
            runner.HISTORICAL_SELECTION_SCHEMA,
            runner.HISTORICAL_DERIVATION_DEVELOPMENT_RUN_ID,
        ),
        (runner.SUCCESSOR_SELECTION_SCHEMA, runner.DEVELOPMENT_RUN_ID),
    ),
)
def test_sealed_derivation_replay_routes_by_selection_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection_schema: str,
    development_run_id: str,
) -> None:
    context = _context(tmp_path / "development")
    manifest, lock, _artifact, _readback, _judge = (
        _sealed_preregistration_context(context, tmp_path)
    )
    derivation = copy.deepcopy(context["derivation"])
    derivation["selection_receipt"] = {"schema_version": selection_schema}
    receipt = _derivation_receipt(
        manifest,
        context["meter"],
        development_run_id=development_run_id,
    )
    derivation["receipt"] = receipt
    lock["token_envelope_derivation_receipt_sha256"] = receipt["receipt_sha256"]
    replayed_run_ids: list[str] = []

    def replay(*, development_run_id: str, **_kwargs: object) -> str:
        replayed_run_ids.append(development_run_id)
        return str(receipt["receipt_sha256"])

    monkeypatch.setattr(runner, "_replay_token_envelope_derivation", replay)
    assert runner._validate_token_envelope_derivation_gate(
        derivation,
        manifest=manifest,
        execution_lock=lock,
        token_meter=context["meter"],
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        preregistration_artifact=None,
    ) == receipt["receipt_sha256"]
    assert replayed_run_ids == [development_run_id]


def test_all_pure_drift_refuses_before_first_model_call(tmp_path: Path) -> None:
    context = _context(tmp_path)

    def wrong_head(_manifest, lock, _bundle, _preflight):
        lock["hswm_commit"] = "e" * 40
        _rehash(lock, "lock_sha256")

    for mutator, pattern in (
        (
            lambda manifest, _lock, _bundle, _preflight: manifest["items"][0].__setitem__(
                "query_text", "post-lock drift"
            ),
            "manifest bytes",
        ),
        (
            lambda _manifest, _lock, bundle, _preflight: bundle[
                "environment_receipt"
            ]["labels"].__setitem__("endpoint", "http://wrong"),
            "bundle verification",
        ),
        (
            lambda _manifest, _lock, _bundle, preflight: preflight.__setitem__(
                "endpoint", "http://wrong"
            ),
            "preflight",
        ),
        (wrong_head, "bundle verification"),
    ):
        manifest = copy.deepcopy(context["manifest"])
        lock = copy.deepcopy(context["lock"])
        bundle = copy.deepcopy(context["bundle"])
        preflight = copy.deepcopy(context["preflight"])
        mutator(manifest, lock, bundle, preflight)
        port = FakeDurablePort(context["meter"])
        with pytest.raises(R8RunnerRefusal, match=pattern):
            run_suite_v3_draft(
                manifest,
                execution_lock=lock,
                protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
                model_port=port,
                token_meter=context["meter"],
                max_workers=2,
                token_envelope_derivation=context["derivation"],
                prior_exposure_receipt=context["prior_exposure"],
                aborted_attempt_exposure_receipt=context["aborted_exposure"],
                environment_dependency_bundle=bundle,
                result_contract_path=context["result_contract"],
                **_dependency_kwargs(context),
                spool_identity_preflight=preflight,
            )
        assert port.calls == {}

    port = FakeDurablePort(context["meter"])
    wrong_root_args = _dependency_kwargs(context)
    wrong_root_args["symposium_repo_root"] = tmp_path
    with pytest.raises(R8RunnerRefusal, match="bundle verification"):
        run_suite_v3_draft(
            context["manifest"],
            execution_lock=context["lock"],
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=context["meter"],
            max_workers=2,
            token_envelope_derivation=context["derivation"],
            prior_exposure_receipt=context["prior_exposure"],
            aborted_attempt_exposure_receipt=context["aborted_exposure"],
            environment_dependency_bundle=context["bundle"],
            result_contract_path=context["result_contract"],
            **wrong_root_args,
            spool_identity_preflight=context["preflight"],
        )
    assert port.calls == {}


def test_derivation_missing_tampered_and_resigned_refuse_before_calls(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)

    missing = copy.deepcopy(context["derivation"])
    missing.pop("receipt")
    port = FakeDurablePort(context["meter"])
    untouched_ledger = tmp_path / "untouched-attempt.sqlite3"
    untouched_ledger.write_bytes(b"gate must not touch this ledger")
    untouched_ledger.chmod(0o644)
    port.ledger = type("LedgerPath", (), {"path": untouched_ledger})()
    with pytest.raises(R8RunnerRefusal, match="derivation input set"):
        run_suite_v3_draft(
            context["manifest"],
            execution_lock=context["lock"],
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=context["meter"],
            max_workers=2,
            token_envelope_derivation=missing,
            prior_exposure_receipt=context["prior_exposure"],
            aborted_attempt_exposure_receipt=context["aborted_exposure"],
            environment_dependency_bundle=context["bundle"],
            result_contract_path=context["result_contract"],
            **_dependency_kwargs(context),
            spool_identity_preflight=context["preflight"],
        )
    assert port.calls == {}
    assert untouched_ledger.stat().st_mode & 0o777 == 0o644

    tampered = copy.deepcopy(context["derivation"])
    tampered["receipt"]["model_calls"] = 1
    port = FakeDurablePort(context["meter"])
    with pytest.raises(R8RunnerRefusal, match="self-hash"):
        run_suite_v3_draft(
            context["manifest"],
            execution_lock=context["lock"],
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=context["meter"],
            max_workers=2,
            token_envelope_derivation=tampered,
            prior_exposure_receipt=context["prior_exposure"],
            aborted_attempt_exposure_receipt=context["aborted_exposure"],
            environment_dependency_bundle=context["bundle"],
            result_contract_path=context["result_contract"],
            **_dependency_kwargs(context),
            spool_identity_preflight=context["preflight"],
        )
    assert port.calls == {}

    resigned = copy.deepcopy(context["derivation"])
    resigned["receipt"]["historical_token_envelope_sha256"] = "f" * 64
    _rehash(resigned["receipt"], "receipt_sha256")
    resigned_lock = copy.deepcopy(context["lock"])
    resigned_lock["token_envelope_derivation_receipt_sha256"] = resigned[
        "receipt"
    ]["receipt_sha256"]
    _rehash(resigned_lock, "lock_sha256")
    resigned_preflight = _preflight(
        str(context["manifest"]["run_id"]),
        str(resigned_lock["lock_sha256"]),
        str(context["genesis"]["genesis_sha256"]),
    )
    port = FakeDurablePort(context["meter"])
    with pytest.raises(R8RunnerRefusal, match="replay SHA drifted"):
        run_suite_v3_draft(
            context["manifest"],
            execution_lock=resigned_lock,
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=context["meter"],
            max_workers=2,
            token_envelope_derivation=resigned,
            prior_exposure_receipt=context["prior_exposure"],
            aborted_attempt_exposure_receipt=context["aborted_exposure"],
            environment_dependency_bundle=context["bundle"],
            result_contract_path=context["result_contract"],
            **_dependency_kwargs(context),
            spool_identity_preflight=resigned_preflight,
        )
    assert port.calls == {}


def test_aborted_attempt_receipt_missing_tampered_and_resigned_refuse_cleanly(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path / "context")
    tampered = copy.deepcopy(context["aborted_exposure"])
    tampered["termination"]["exit_code"] = 1

    resigned = copy.deepcopy(context["aborted_exposure"])
    resigned["run_identity"]["run_id"] = "forged-aborted-attempt"
    _rehash(resigned, "aborted_attempt_exposure_receipt_sha256")
    resigned_lock = copy.deepcopy(context["lock"])
    resigned_lock["aborted_attempt_exposure_receipt_sha256"] = resigned[
        "aborted_attempt_exposure_receipt_sha256"
    ]
    _rehash(resigned_lock, "lock_sha256")
    resigned_preflight = _preflight(
        str(context["manifest"]["run_id"]),
        str(resigned_lock["lock_sha256"]),
        str(context["genesis"]["genesis_sha256"]),
    )

    cases = (
        ("missing", {}, context["lock"], context["preflight"]),
        ("tampered", tampered, context["lock"], context["preflight"]),
        ("resigned", resigned, resigned_lock, resigned_preflight),
    )
    for label, receipt, lock, preflight in cases:
        attempt_ledger = tmp_path / f"{label}-attempt.sqlite3"
        spool_ledger = tmp_path / f"{label}-spool.sqlite3"
        attempt_ledger.write_bytes(b"attempt-ledger-must-remain-unchanged")
        spool_ledger.write_bytes(b"spool-ledger-must-remain-unchanged")
        attempt_ledger.chmod(0o644)
        spool_ledger.chmod(0o644)
        before_attempt = attempt_ledger.read_bytes()
        before_spool = spool_ledger.read_bytes()
        port = FakeDurablePort(context["meter"])
        port.ledger = type("LedgerPath", (), {"path": attempt_ledger})()
        before_audit = port.audit()

        with pytest.raises(
            R8RunnerRefusal,
            match="aborted-attempt exposure receipt verification failed",
        ):
            run_suite_v3_draft(
                context["manifest"],
                execution_lock=lock,
                protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
                model_port=port,
                token_meter=context["meter"],
                max_workers=2,
                token_envelope_derivation=context["derivation"],
                prior_exposure_receipt=context["prior_exposure"],
                aborted_attempt_exposure_receipt=receipt,
                environment_dependency_bundle=context["bundle"],
                result_contract_path=context["result_contract"],
                **_dependency_kwargs(context),
                spool_identity_preflight=preflight,
            )

        assert port.calls == {}
        assert port.audit() == before_audit
        assert attempt_ledger.read_bytes() == before_attempt
        assert spool_ledger.read_bytes() == before_spool
        assert attempt_ledger.stat().st_mode & 0o777 == 0o644
        assert spool_ledger.stat().st_mode & 0o777 == 0o644


def test_prior_receipt_and_exact_exposure_union_drift_refuse_before_calls(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)

    def refuse(
        prior: dict[str, object], lock: dict[str, object]
    ) -> None:
        port = FakeDurablePort(context["meter"])
        with pytest.raises(
            R8RunnerRefusal,
            match="execution-lock forbidden exposure union verification failed",
        ):
            run_suite_v3_draft(
                context["manifest"],
                execution_lock=lock,
                protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
                model_port=port,
                token_meter=context["meter"],
                max_workers=2,
                token_envelope_derivation=context["derivation"],
                prior_exposure_receipt=prior,
                aborted_attempt_exposure_receipt=context["aborted_exposure"],
                environment_dependency_bundle=context["bundle"],
                result_contract_path=context["result_contract"],
                **_dependency_kwargs(context),
                spool_identity_preflight=context["preflight"],
            )
        assert port.calls == {}

    refuse({}, context["lock"])
    tampered = copy.deepcopy(context["prior_exposure"])
    tampered["aggregate"]["prior_item_ids"].append("tampered-prior-item")
    refuse(tampered, context["lock"])
    resigned = copy.deepcopy(context["prior_exposure"])
    resigned_items = sorted(
        [*resigned["aggregate"]["prior_item_ids"], "resigned-prior-item"]
    )
    resigned["aggregate"]["prior_item_ids"] = resigned_items
    resigned["aggregate"]["item_root_sha256"] = canonical_sha256(
        resigned_items
    )
    _rehash(resigned, "prior_exposure_receipt_sha256")
    refuse(resigned, context["lock"])

    extra_by_field = {
        "forbidden_prior_item_ids": "union-extra-item",
        "forbidden_prior_source_entity_ids": "7" * 64,
        "forbidden_prior_component_ids": "6" * 64,
    }
    for field, extra in extra_by_field.items():
        for operation in ("subset", "superset"):
            lock = copy.deepcopy(context["lock"])
            values = list(lock[field])
            if operation == "subset":
                values.pop(0)
            else:
                values = sorted({*values, extra})
            lock[field] = values
            _rehash(lock, "lock_sha256")
            refuse(context["prior_exposure"], lock)


def test_dummy_runner_dependency_is_rejected_before_first_model_call(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    paths = r8_dependency_paths(
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        judge_core_path=context["judge_core_path"],
        result_contract_path=context["result_contract"],
        tokenizer_dir=context["tokenizer_dir"],
        model_catalog_path=context["model_catalog_path"],
        model_weight_receipt_path=context["model_weight_receipt_path"],
        python_lock_path=context["python_lock_path"],
    )
    dummy = tmp_path / "dummy-runner.py"
    dummy.write_text("# not the runner\n")
    paths["runner"] = dummy
    bundle = build_preimage_bundle(
        paths,
        labels={
            "spool_endpoint": ENDPOINT,
            "model_upstream_endpoint": UPSTREAM_ENDPOINT,
            "model_deployment_receipt_sha256": DEPLOYMENT_SHA256,
            "hswm_commit": HSWM_COMMIT,
            "model": "fake-model",
            "model_revision": TEST_REVISION,
            "run_id": context["manifest"]["run_id"],
            "symposium_commit": SYMPOSIUM_COMMIT,
        },
        inline_limit_bytes=1024 * 1024,
    )
    lock = _lock(
        context["manifest"],
        prior_exposure_receipt=context["prior_exposure"],
        aborted_attempt_exposure_receipt=context["aborted_exposure"],
        bundle=bundle,
        result_contract=context["result_contract"],
        genesis_sha=context["genesis"]["genesis_sha256"],
        derivation_receipt_sha256=context["derivation"]["receipt"][
            "receipt_sha256"
        ],
    )
    port = FakeDurablePort(context["meter"])
    with pytest.raises(R8RunnerRefusal, match="bundle verification"):
        run_suite_v3_draft(
            context["manifest"],
            execution_lock=lock,
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=context["meter"],
            max_workers=2,
            token_envelope_derivation=context["derivation"],
            prior_exposure_receipt=context["prior_exposure"],
            aborted_attempt_exposure_receipt=context["aborted_exposure"],
            environment_dependency_bundle=bundle,
            result_contract_path=context["result_contract"],
            **_dependency_kwargs(context),
            spool_identity_preflight=_preflight(
                context["manifest"]["run_id"],
                lock["lock_sha256"],
                context["genesis"]["genesis_sha256"],
            ),
        )
    assert port.calls == {}


def test_direct_api_max_workers_is_lock_bound_before_calls(tmp_path: Path) -> None:
    context = _context(tmp_path)
    port = FakeDurablePort(context["meter"])
    with pytest.raises(R8RunnerRefusal, match="max_workers"):
        run_suite_v3_draft(
            context["manifest"],
            execution_lock=context["lock"],
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=context["meter"],
            max_workers=1,
            token_envelope_derivation=context["derivation"],
            prior_exposure_receipt=context["prior_exposure"],
            aborted_attempt_exposure_receipt=context["aborted_exposure"],
            environment_dependency_bundle=context["bundle"],
            result_contract_path=context["result_contract"],
            **_dependency_kwargs(context),
            spool_identity_preflight=context["preflight"],
        )
    assert port.calls == {}


def test_terminal_finalizer_binds_minimal_roots_and_enriched_preimages(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    draft, port = _run(context)
    bindings = _transport_bindings(draft, port, context["genesis"])
    suite = finalize_suite_v3(
        draft,
        transport_bindings=bindings,
        genesis_receipt=context["genesis"],
    )
    assert verify_suite_v3_without_gold(suite) == suite["suite_receipt_sha256"]
    assert suite["transport_audit"] == draft["live_transport_audit"]
    assert suite["transport_audit"]["accepted_call_root_sha256"] == bindings[
        "accepted_call_root_sha256"
    ]

    tampered = copy.deepcopy(bindings)
    raw = base64.b64decode(
        tampered["accepted_call_auxiliary_preimages"][0][
            "call_receipt_bytes_b64"
        ]
    )
    receipt = json.loads(raw)
    receipt["output_tokens"] += 1
    changed = canonical_json(receipt).encode()
    row = tampered["accepted_call_auxiliary_preimages"][0]
    row["call_receipt_bytes_b64"] = base64.b64encode(changed).decode()
    row["call_receipt_bytes_sha256"] = hashlib.sha256(changed).hexdigest()
    tampered["accepted_call_auxiliary_root_sha256"] = canonical_sha256(
        tampered["accepted_call_auxiliary_preimages"]
    )
    _rehash(tampered, "bindings_sha256")
    with pytest.raises(R8RunnerRefusal, match="call-receipt bytes"):
        finalize_suite_v3(
            draft,
            transport_bindings=tampered,
            genesis_receipt=context["genesis"],
        )


def test_spool_preflight_identity_continues_through_genesis_and_terminal(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    draft, port = _run(context)
    bindings = _transport_bindings(draft, port, context["genesis"])

    mismatched_draft = copy.deepcopy(draft)
    preflight = mismatched_draft["spool_identity_preflight"]
    identity = preflight["endpoint_identity"]
    identity["db_identity"]["st_ino"] += 1
    _rehash(identity, "identity_sha256")
    _rehash(preflight, "preflight_sha256")
    mismatched_draft["spool_identity_preflight_sha256"] = preflight[
        "preflight_sha256"
    ]
    _rehash(mismatched_draft, "draft_receipt_sha256")
    with pytest.raises(R8RunnerRefusal, match="preflight.*genesis"):
        finalize_suite_v3(
            mismatched_draft,
            transport_bindings=bindings,
            genesis_receipt=context["genesis"],
        )

    suite = finalize_suite_v3(
        draft,
        transport_bindings=bindings,
        genesis_receipt=context["genesis"],
    )
    forged = copy.deepcopy(suite)
    preflight = forged["spool_identity_preflight"]
    identity = preflight["endpoint_identity"]
    identity["db_identity"]["resolved_path"] = "/private/alternate-spool.sqlite3"
    _rehash(identity, "identity_sha256")
    _rehash(preflight, "preflight_sha256")
    forged["spool_identity_preflight_sha256"] = preflight["preflight_sha256"]
    _rehash(forged, "suite_receipt_sha256")
    with pytest.raises(R8RunnerRefusal, match="preflight.*terminal"):
        verify_suite_v3_without_gold(forged)


def test_runner_local_verifier_recomputes_physical_id_and_token_parity(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    draft, port = _run(context)
    bindings = _transport_bindings(draft, port, context["genesis"])
    suite = finalize_suite_v3(
        draft,
        transport_bindings=bindings,
        genesis_receipt=context["genesis"],
    )
    forged = copy.deepcopy(suite)
    call = forged["item_runs"][0]["calls"][0]
    call["physical_call_id"] = "f" * 64
    _rehash(call, "receipt_sha256")
    _rehash(forged["item_runs"][0], "run_receipt_sha256")
    _rehash(forged, "suite_receipt_sha256")
    with pytest.raises(R8RunnerRefusal, match="call identity"):
        verify_suite_v3_without_gold(forged)

    parity = copy.deepcopy(suite)
    parity["token_parity"]["spread_max"] += 1
    _rehash(parity, "suite_receipt_sha256")
    with pytest.raises(R8RunnerRefusal, match="token-parity"):
        verify_suite_v3_without_gold(parity)


def _frozen_genesis(attempt_db: Path, spool_db: Path, run_id: str):
    attempt = _read_only_database(attempt_db, "attempt ledger")
    spool = _read_only_database(spool_db, "result spool")
    try:
        attempt_version, attempt_schema = _database_schema(
            attempt, "attempt", "attempt ledger"
        )
        spool_version, spool_schema = _database_schema(
            spool, "spool", "result spool"
        )
        unsigned = {
            "schema_version": GENESIS_SCHEMA,
            "run_id": run_id,
            "attempt_integrity": str(
                attempt.execute("PRAGMA integrity_check").fetchone()[0]
            ),
            "spool_integrity": str(
                spool.execute("PRAGMA integrity_check").fetchone()[0]
            ),
            "attempt_journal_mode": str(
                attempt.execute("PRAGMA journal_mode").fetchone()[0]
            ),
            "attempt_audit_connection_synchronous": str(
                attempt.execute("PRAGMA synchronous").fetchone()[0]
            ),
            "spool_journal_mode": str(
                spool.execute("PRAGMA journal_mode").fetchone()[0]
            ),
            "spool_audit_connection_synchronous": str(
                spool.execute("PRAGMA synchronous").fetchone()[0]
            ),
            "attempt_user_version": attempt_version,
            "spool_user_version": spool_version,
            "attempt_schema_sha256": attempt_schema,
            "spool_schema_sha256": spool_schema,
            "attempt_db_identity": _database_identity(attempt_db, "attempt ledger"),
            "spool_db_identity": _database_identity(spool_db, "result spool"),
            "call_count": 0,
            "item_run_count": 0,
            "attempt_event_count": 0,
            "spool_call_count": 0,
        }
    finally:
        attempt.close()
        spool.close()
    return {**unsigned, "genesis_sha256": canonical_sha256(unsigned)}


def test_full_genesis_validator_and_runner_local_0600_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    observed_entries: list[tuple[str, int]] = []
    original_attempt = runner.SQLiteF1CallLedger
    original_spool = runner.SQLiteResultSpool

    def checked_attempt(path):
        store = original_attempt(path)
        observed_entries.append(("attempt", os.stat(path).st_mode & 0o777))
        return store

    def checked_spool(path):
        store = original_spool(path)
        observed_entries.append(("spool", os.stat(path).st_mode & 0o777))
        return store

    monkeypatch.setattr(runner, "SQLiteF1CallLedger", checked_attempt)
    monkeypatch.setattr(runner, "SQLiteResultSpool", checked_spool)
    initialize_transport_pair(attempt_db, spool_db)
    assert observed_entries == [("attempt", 0o600), ("spool", 0o600)]
    assert os.stat(attempt_db).st_mode & 0o777 == 0o600
    assert os.stat(spool_db).st_mode & 0o777 == 0o600
    genesis = _frozen_genesis(attempt_db, spool_db, "run")
    lock_unsigned = {"db_genesis_receipt_sha256": genesis["genesis_sha256"]}
    lock = {**lock_unsigned, "lock_sha256": canonical_sha256(lock_unsigned)}
    assert verify_fresh_transport_genesis(
        genesis,
        execution_lock=lock,
        run_id="run",
        attempt_db=attempt_db,
        spool_db=spool_db,
    ) == genesis["genesis_sha256"]

    extra = copy.deepcopy(genesis)
    extra["pseudo_genesis_field"] = True
    _rehash(extra, "genesis_sha256")
    with pytest.raises(R8RunnerRefusal, match="identity or schema"):
        verify_fresh_transport_genesis(
            extra,
            execution_lock=lock,
            run_id="run",
            attempt_db=attempt_db,
            spool_db=spool_db,
        )

    for suffix in ("-wal", "-shm"):
        member = Path(f"{attempt_db}{suffix}")
        member.write_bytes(b"sidecar")
        member.chmod(0o644)
    with pytest.raises(R8RunnerRefusal, match="owner-private unique"):
        runner._seal_private_sqlite_family(attempt_db, "attempt ledger")
    assert all(
        os.stat(f"{attempt_db}{suffix}").st_mode & 0o777 == 0o644
        for suffix in ("-wal", "-shm")
    )
    for suffix in ("-wal", "-shm"):
        Path(f"{attempt_db}{suffix}").chmod(0o600)
    runner._seal_private_sqlite_family(attempt_db, "attempt ledger")

    occupied_spool = tmp_path / "occupied-spool.sqlite3"
    occupied_spool.write_bytes(b"occupied")
    preserved_attempt = tmp_path / "preserved-attempt.sqlite3"
    with pytest.raises(R8RunnerRefusal, match="already occupied"):
        initialize_transport_pair(preserved_attempt, occupied_spool)
    assert preserved_attempt.exists()
    assert os.stat(preserved_attempt).st_mode & 0o777 == 0o600


def test_transport_database_family_refuses_public_or_hardlinked_members(
    tmp_path: Path,
) -> None:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)

    attempt_db.chmod(0o644)
    with pytest.raises(R8RunnerRefusal, match="owner-private unique"):
        _database_identity(attempt_db, "attempt ledger")
    assert stat.S_IMODE(attempt_db.stat().st_mode) == 0o644
    attempt_db.chmod(0o600)

    main_alias = tmp_path / "attempt-alias.sqlite3"
    os.link(attempt_db, main_alias)
    with pytest.raises(R8RunnerRefusal, match="owner-private unique"):
        _database_identity(attempt_db, "attempt ledger")
    main_alias.unlink()

    wal = Path(f"{attempt_db}-wal")
    wal.write_bytes(b"sidecar")
    wal.chmod(0o600)
    wal_alias = tmp_path / "attempt-wal-alias"
    os.link(wal, wal_alias)
    with pytest.raises(R8RunnerRefusal, match="owner-private unique"):
        runner._seal_private_sqlite_family(attempt_db, "attempt ledger")
    wal_alias.unlink()


def test_runtime_policy_and_live_spool_identity_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path / "context")
    with pytest.raises(R8RunnerRefusal, match="execution policy"):
        validate_execution_policy(
            context["lock"],
            endpoint=ENDPOINT,
            max_workers=3,
            timeout_seconds=180.0,
            max_delivery_attempts=8,
            spool_token_env="SPOOL_CLIENT_TOKEN",
        )
    spool_db = tmp_path / "spool.sqlite3"
    store = SQLiteResultSpool(spool_db)
    service = ResultSpoolService(
        store,
        upstream_endpoint="http://127.0.0.1:9/v1/chat/completions",
        deployment_binding=ModelDeploymentBinding(
            upstream_endpoint="http://127.0.0.1:9/v1/chat/completions",
            deployment_receipt_sha256=DEPLOYMENT_SHA256,
            deployment_id=f"hswm:model_deployment:v2:{DEPLOYMENT_SHA256}",
            served_model="fake-model",
            model_revision=TEST_REVISION,
        ),
        deployment_receipt_path=tmp_path / "deployment.json",
        client_token="private-token",
        upstream_transport=lambda *_args: RawHTTPResponse(500, {}, b""),
    )
    server = ResultSpoolHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("SPOOL_CLIENT_TOKEN", "private-token")
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        receipt = verify_spool_endpoint_identity(
            endpoint=endpoint,
            spool_db=spool_db,
            deployment_binding=ModelDeploymentBinding(
                upstream_endpoint="http://127.0.0.1:9/v1/chat/completions",
                deployment_receipt_sha256=DEPLOYMENT_SHA256,
                deployment_id=f"hswm:model_deployment:v2:{DEPLOYMENT_SHA256}",
                served_model="fake-model",
                model_revision=TEST_REVISION,
            ),
            spool_token_env="SPOOL_CLIENT_TOKEN",
            timeout_seconds=5.0,
            run_id="run",
            execution_lock_sha256="a" * 64,
            db_genesis_sha256="b" * 64,
        )
        assert receipt["endpoint_identity"]["audit"]["synchronous"] == 2
    finally:
        server.shutdown()
        server.server_close()
        store.close()
        thread.join(timeout=5)


def test_cli_preexisting_output_refuses_before_endpoint_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path / "context")
    manifest_path = tmp_path / "manifest.json"
    lock_path = tmp_path / "lock.json"
    genesis_path = tmp_path / "genesis.json"
    bundle_path = tmp_path / "bundle.json"
    prior_exposure_path = tmp_path / "prior-exposure.json"
    aborted_exposure_path = tmp_path / "aborted-exposure.json"
    derivation_paths = {
        "receipt": tmp_path / "derivation.json",
        "selection_receipt": tmp_path / "selection.json",
        "historical_manifest": tmp_path / "historical.json",
        "validation_receipt": tmp_path / "validation.json",
        "projected_outputs_receipt": tmp_path / "projected.json",
        "source_suite": tmp_path / "source-suite.json",
    }
    for path, value in (
        (manifest_path, context["manifest"]),
        (lock_path, context["lock"]),
        (genesis_path, {}),
        (bundle_path, {}),
        (prior_exposure_path, context["prior_exposure"]),
        (aborted_exposure_path, context["aborted_exposure"]),
    ):
        path.write_text(json.dumps(value))
    prior_exposure_path.chmod(0o600)
    aborted_exposure_path.chmod(0o600)
    for name, path in derivation_paths.items():
        path.write_text(json.dumps(context["derivation"][name]))
    tokenizer = context["tokenizer_dir"]
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    attempt_db.write_bytes(b"")
    spool_db.write_bytes(b"")
    output = tmp_path / "occupied-draft.json"
    output.write_text("keep-me")
    endpoint_calls = 0

    monkeypatch.setattr(
        runner, "load_private_receipt", lambda *_args, **_kwargs: context["bundle"]
    )
    monkeypatch.setattr(runner, "QwenBpeMeter", lambda *_args: context["meter"])
    monkeypatch.setattr(
        runner,
        "_validate_environment_dependency_bundle",
        lambda *_args, **_kwargs: context["bundle"]["bundle_sha256"],
    )
    monkeypatch.setattr(
        runner,
        "verify_fresh_transport_genesis",
        lambda *_args, **_kwargs: context["genesis"]["genesis_sha256"],
    )

    def endpoint_spy(**_kwargs):
        nonlocal endpoint_calls
        endpoint_calls += 1
        return context["preflight"]

    monkeypatch.setattr(runner, "verify_spool_endpoint_identity", endpoint_spy)
    result = runner.main(
        [
            "run",
            "--manifest", str(manifest_path),
            "--execution-lock", str(lock_path),
            "--protocol", str(REPO_ROOT / DEFAULT_PROTOCOL),
            "--endpoint", ENDPOINT,
            "--attempt-db", str(attempt_db),
            "--spool-db", str(spool_db),
            "--db-genesis-receipt", str(genesis_path),
            "--environment-dependency-bundle", str(bundle_path),
            "--token-envelope-derivation-receipt",
            str(derivation_paths["receipt"]),
            "--selection-receipt", str(derivation_paths["selection_receipt"]),
            "--prior-exposure-receipt", str(prior_exposure_path),
            "--aborted-attempt-exposure-receipt",
            str(aborted_exposure_path),
            "--historical-manifest", str(derivation_paths["historical_manifest"]),
            "--token-meter-validation-receipt",
            str(derivation_paths["validation_receipt"]),
            "--projected-outputs-receipt",
            str(derivation_paths["projected_outputs_receipt"]),
            "--token-meter-source-suite", str(derivation_paths["source_suite"]),
            "--result-contract", str(context["result_contract"]),
            "--judge-core", str(context["judge_core_path"]),
            "--symposium-repo-root", str(SYMPOSIUM_ROOT),
            "--model-catalog", str(context["model_catalog_path"]),
            "--model-deployment-receipt",
            str(context["model_weight_receipt_path"]),
            "--python-lock", str(context["python_lock_path"]),
            "--spool-token-env", "SPOOL_CLIENT_TOKEN",
                "--spool-identity-receipt", str(tmp_path / "spool-identity.json"),
                "--reservation-journal", str(tmp_path / "reservation.sqlite3"),
                "--timeout-seconds", "180",
            "--max-workers", "2",
            "--max-delivery-attempts", "8",
            "--tokenizer-dir", str(tokenizer),
            "--output", str(output),
        ]
    )
    assert result == 1
    assert endpoint_calls == 0
    assert output.read_text() == "keep-me"


def _resume_cli_case(
    tmp_path: Path, context: dict[str, object]
) -> tuple[list[str], dict[str, Path]]:
    root = tmp_path / "cli"
    root.mkdir(parents=True)
    paths = {
        "manifest": root / "manifest.json",
        "lock": root / "lock.json",
        "genesis": root / "genesis.json",
        "bundle": root / "bundle.json",
        "prior": root / "prior.json",
        "aborted": root / "aborted.json",
        "derivation": root / "derivation.json",
        "selection": root / "selection.json",
        "historical": root / "historical.json",
        "validation": root / "validation.json",
        "projected": root / "projected.json",
        "source_suite": root / "source-suite.json",
        "attempt_db": root / "attempt.sqlite3",
        "spool_db": root / "spool.sqlite3",
        "spool_identity": root / "spool-identity.json",
        "draft": root / "draft.json",
        "journal": root / "reservation.sqlite3",
    }
    values = {
        "manifest": context["manifest"],
        "lock": context["lock"],
        "genesis": context["genesis"],
        "bundle": context["bundle"],
        "prior": context["prior_exposure"],
        "aborted": context["aborted_exposure"],
        "derivation": context["derivation"]["receipt"],
        "selection": context["derivation"]["selection_receipt"],
        "historical": context["derivation"]["historical_manifest"],
        "validation": context["derivation"]["validation_receipt"],
        "projected": context["derivation"]["projected_outputs_receipt"],
        "source_suite": context["derivation"]["source_suite"],
    }
    for name, value in values.items():
        paths[name].write_text(json.dumps(value), encoding="utf-8")
    paths["prior"].chmod(0o600)
    paths["aborted"].chmod(0o600)
    paths["attempt_db"].write_bytes(b"")
    paths["spool_db"].write_bytes(b"")
    argv = [
        "run",
        "--resume",
        "--manifest", str(paths["manifest"]),
        "--execution-lock", str(paths["lock"]),
        "--protocol", str(REPO_ROOT / DEFAULT_PROTOCOL),
        "--endpoint", ENDPOINT,
        "--attempt-db", str(paths["attempt_db"]),
        "--spool-db", str(paths["spool_db"]),
        "--db-genesis-receipt", str(paths["genesis"]),
        "--environment-dependency-bundle", str(paths["bundle"]),
        "--token-envelope-derivation-receipt", str(paths["derivation"]),
        "--selection-receipt", str(paths["selection"]),
        "--prior-exposure-receipt", str(paths["prior"]),
        "--aborted-attempt-exposure-receipt", str(paths["aborted"]),
        "--historical-manifest", str(paths["historical"]),
        "--token-meter-validation-receipt", str(paths["validation"]),
        "--projected-outputs-receipt", str(paths["projected"]),
        "--token-meter-source-suite", str(paths["source_suite"]),
        "--result-contract", str(context["result_contract"]),
        "--judge-core", str(context["judge_core_path"]),
        "--symposium-repo-root", str(SYMPOSIUM_ROOT),
        "--model-catalog", str(context["model_catalog_path"]),
        "--model-deployment-receipt", str(context["model_weight_receipt_path"]),
        "--python-lock", str(context["python_lock_path"]),
        "--spool-token-env", "SPOOL_CLIENT_TOKEN",
        "--spool-identity-receipt", str(paths["spool_identity"]),
        "--reservation-journal", str(paths["journal"]),
        "--timeout-seconds", "180",
        "--max-workers", "2",
        "--max-delivery-attempts", "8",
        "--tokenizer-dir", str(context["tokenizer_dir"]),
        "--output", str(paths["draft"]),
    ]
    return argv, paths


def _patch_resume_cli_authorities(
    monkeypatch: pytest.MonkeyPatch,
    context: dict[str, object],
    prefix: dict[str, object],
) -> list[bool]:
    live_flags: list[bool] = []
    monkeypatch.setattr(
        runner, "load_private_receipt", lambda *_args, **_kwargs: context["bundle"]
    )
    monkeypatch.setattr(runner, "QwenBpeMeter", lambda *_args: context["meter"])
    monkeypatch.setattr(
        runner,
        "_validate_environment_dependency_bundle",
        lambda *_args, **_kwargs: context["bundle"]["bundle_sha256"],
    )
    monkeypatch.setattr(
        runner,
        "verify_fresh_transport_genesis",
        lambda *_args, **_kwargs: context["genesis"]["genesis_sha256"],
    )
    monkeypatch.setattr(
        runner, "export_resume_prefix", lambda **_kwargs: copy.deepcopy(prefix)
    )

    def deployment(*_args, **kwargs):
        live_flags.append(bool(kwargs.get("verify_live_process")))
        return _deployment_binding()

    monkeypatch.setattr(runner, "load_model_deployment_binding", deployment)
    monkeypatch.setattr(
        runner, "_seal_private_sqlite_family", lambda *_args, **_kwargs: None
    )
    return live_flags


def _seed_resume_journal(
    paths: dict[str, Path],
    context: dict[str, object],
    *,
    preflight: dict[str, object],
    draft: dict[str, object] | None = None,
    prepare_draft_only: bool = False,
) -> None:
    with private_output.reserve_private_outputs(
        [
            ("spool_identity_receipt", paths["spool_identity"]),
            ("suite_draft", paths["draft"]),
        ],
        run_id=str(context["manifest"]["run_id"]),
        journal_path=paths["journal"],
    ) as journal:
        journal["spool_identity_receipt"].commit(preflight)
        if draft is not None:
            if prepare_draft_only:
                payload = private_output._json_payload(draft)
                journal._prepare_commit(
                    "suite_draft", payload, hashlib.sha256(payload).hexdigest()
                )
            else:
                journal["suite_draft"].commit(draft)


def _forbid_endpoint_or_port(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("offline resume crossed a network/port boundary")

    monkeypatch.setattr(runner, "verify_spool_endpoint_identity", forbidden)
    monkeypatch.setattr(
        runner, "verify_spool_endpoint_resume_identity", forbidden
    )
    monkeypatch.setattr(runner, "DurableSpoolJSONPort", forbidden)


def test_committed_draft_resume_is_offline_and_rebound_to_current_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path / "context")
    draft, completed_port = _run(context)
    prefix, _jobs = _resume_prefix_for_draft(context, draft, completed_port)
    argv, paths = _resume_cli_case(tmp_path, context)
    _seed_resume_journal(
        paths, context, preflight=context["preflight"], draft=draft
    )
    live_flags = _patch_resume_cli_authorities(monkeypatch, context, prefix)
    _forbid_endpoint_or_port(monkeypatch)

    assert runner.main(argv) == 0
    assert live_flags == [False]
    assert json.loads(paths["draft"].read_text(encoding="utf-8")) == draft


def test_resigned_preflight_db_identity_refuses_before_live_or_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path / "context")
    draft, completed_port = _run(context)
    prefix, _jobs = _resume_prefix_for_draft(context, draft, completed_port)
    preflight = copy.deepcopy(context["preflight"])
    preflight["endpoint_identity"]["db_identity"]["st_ino"] += 97
    _rehash(preflight["endpoint_identity"], "identity_sha256")
    _rehash(preflight, "preflight_sha256")
    argv, paths = _resume_cli_case(tmp_path, context)
    _seed_resume_journal(paths, context, preflight=preflight)
    live_flags = _patch_resume_cli_authorities(monkeypatch, context, prefix)
    _forbid_endpoint_or_port(monkeypatch)

    assert runner.main(argv) == 1
    assert live_flags == [False]


def test_resigned_prepared_draft_drift_never_reconciles_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path / "context")
    draft, completed_port = _run(context)
    prefix, _jobs = _resume_prefix_for_draft(context, draft, completed_port)
    drifted = copy.deepcopy(draft)
    drifted["result_contract_sha256"] = "f" * 64
    _rehash(drifted, "draft_receipt_sha256")
    argv, paths = _resume_cli_case(tmp_path, context)
    _seed_resume_journal(
        paths,
        context,
        preflight=context["preflight"],
        draft=drifted,
        prepare_draft_only=True,
    )
    marker = paths["draft"].read_bytes()
    live_flags = _patch_resume_cli_authorities(monkeypatch, context, prefix)
    _forbid_endpoint_or_port(monkeypatch)

    assert runner.main(argv) == 1
    assert live_flags == [False]
    assert paths["draft"].read_bytes() == marker
    with private_output.reserve_private_outputs(
        [
            ("spool_identity_receipt", paths["spool_identity"]),
            ("suite_draft", paths["draft"]),
        ],
        run_id=str(context["manifest"]["run_id"]),
        journal_path=paths["journal"],
        resume=True,
    ) as journal:
        assert journal["suite_draft"].state == "COMMIT_PREPARED"
        assert journal["suite_draft"].prepared_value() == drifted


def test_complete_call_prefix_rebuilds_draft_without_live_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path / "context")
    expected_draft, completed_port = _run(context)
    prefix, _jobs = _resume_prefix_for_draft(
        context, expected_draft, completed_port
    )
    argv, paths = _resume_cli_case(tmp_path, context)
    _seed_resume_journal(paths, context, preflight=context["preflight"])
    live_flags = _patch_resume_cli_authorities(monkeypatch, context, prefix)

    def forbidden_endpoint(*_args, **_kwargs):
        raise AssertionError("complete prefix attempted endpoint access")

    monkeypatch.setattr(
        runner, "verify_spool_endpoint_identity", forbidden_endpoint
    )
    monkeypatch.setattr(
        runner, "verify_spool_endpoint_resume_identity", forbidden_endpoint
    )

    class IdempotentReplayPort(FakeDurablePort):
        def accept_item_run(self, value: dict[str, object]) -> None:
            identity = (value["run_id"], value["arm_id"], value["item_id"])
            with self._lock:
                for existing in self.item_runs:
                    observed = (
                        existing["run_id"], existing["arm_id"], existing["item_id"]
                    )
                    if observed == identity:
                        assert existing == value
                        return
                self.item_runs.append(value)

        def close(self) -> None:
            return None

    replay = IdempotentReplayPort(context["meter"])
    replay.calls = copy.deepcopy(completed_port.calls)
    replay.receipts = copy.deepcopy(completed_port.receipts)
    replay.item_runs = copy.deepcopy(completed_port.item_runs)
    transports: list[object] = []

    def port_factory(*_args, **kwargs):
        transports.append(kwargs.get("transport"))
        return replay

    monkeypatch.setattr(runner, "DurableSpoolJSONPort", port_factory)

    assert runner.main(argv) == 0
    assert live_flags and all(flag is False for flag in live_flags)
    assert len(transports) == 1 and callable(transports[0])
    rebuilt = json.loads(paths["draft"].read_text(encoding="utf-8"))
    assert runner.verify_suite_draft_without_gold(rebuilt) == rebuilt[
        "draft_receipt_sha256"
    ]


@pytest.mark.parametrize(
    (
        "selection_schema",
        "run_id",
        "sealed_run_id",
        "development_items",
        "dynamic",
    ),
    (
        (
            runner.SELECTION_SCHEMA_V5,
            runner.C800_DEVELOPMENT_RUN_ID,
            runner.C800_SEALED_RUN_ID,
            959,
            False,
        ),
        (
            runner.SELECTION_SCHEMA_V6,
            runner.C801_DEVELOPMENT_RUN_ID,
            runner.C801_SEALED_RUN_ID,
            17,
            True,
        ),
    ),
)
def test_derivation_cohort_counts_are_dynamic_only_for_v6(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection_schema: str,
    run_id: str,
    sealed_run_id: str,
    development_items: int,
    dynamic: bool,
) -> None:
    context = _context(tmp_path)
    manifest = copy.deepcopy(context["manifest"])
    manifest["run_id"] = run_id
    lock = copy.deepcopy(context["lock"])
    selection_sha = "d" * 64
    lock["selection_receipt_sha256"] = selection_sha

    selection: dict[str, object] = {"schema_version": selection_schema}
    if dynamic:
        selection.update(
            {
                "selection_receipt_sha256": selection_sha,
                "selection_policy": {
                    "dataset_split": "train",
                    "development_components": 800,
                    "confirmatory_items": 800,
                },
                "development": {
                    "item_ids": [
                        f"item-{index}" for index in range(development_items)
                    ]
                },
            }
        )
        monkeypatch.setattr(
            runner,
            "verify_selection_receipt_v6",
            lambda value: str(value["selection_receipt_sha256"]),
        )

    receipt = _derivation_receipt(
        manifest,
        context["meter"],
        development_run_id=run_id,
    )
    receipt["selection_generation"] = selection_schema
    receipt["dataset_split"] = "train"
    receipt["selection_receipt_sha256"] = selection_sha
    receipt["development"]["run_id"] = run_id
    receipt["development"]["items"] = development_items
    receipt["development"]["components"] = 800
    receipt["confirmatory"]["run_id"] = sealed_run_id
    receipt["confirmatory"]["items"] = 800
    receipt["confirmatory"]["components"] = 800
    _rehash(receipt, "receipt_sha256")
    lock["token_envelope_derivation_receipt_sha256"] = receipt[
        "receipt_sha256"
    ]

    derivation = copy.deepcopy(context["derivation"])
    derivation["selection_receipt"] = selection
    derivation["receipt"] = receipt
    monkeypatch.setattr(
        runner,
        "_replay_token_envelope_derivation",
        lambda **_kwargs: str(receipt["receipt_sha256"]),
    )

    assert runner._validate_token_envelope_derivation_gate(
        derivation,
        manifest=manifest,
        execution_lock=lock,
        token_meter=context["meter"],
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        preregistration_artifact=None,
    ) == receipt["receipt_sha256"]

    drifted = copy.deepcopy(receipt)
    drifted["development"]["items"] = development_items + 1
    _rehash(drifted, "receipt_sha256")
    drifted_lock = copy.deepcopy(lock)
    drifted_lock["token_envelope_derivation_receipt_sha256"] = drifted[
        "receipt_sha256"
    ]
    derivation["receipt"] = drifted
    with pytest.raises(R8RunnerRefusal, match="development cohort drifted"):
        runner._validate_token_envelope_derivation_gate(
            derivation,
            manifest=manifest,
            execution_lock=drifted_lock,
            token_meter=context["meter"],
            protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
            preregistration_artifact=None,
        )


@pytest.mark.parametrize(
    ("lock_schema", "run_id"),
    (
        (runner.EXECUTION_LOCK_SCHEMA, runner.C801_DEVELOPMENT_RUN_ID),
        (runner.SEALED_LOCK_SCHEMA, runner.C801_SEALED_RUN_ID),
    ),
)
def test_c801_successor_v2_union_accepts_exact_lock_and_refuses_drift_before_calls(
    monkeypatch: pytest.MonkeyPatch,
    lock_schema: str,
    run_id: str,
) -> None:
    receipt_sha = "a" * 64
    prior_sha = "b" * 64
    merged = {
        "prior_exposure_receipt_sha256": prior_sha,
        "aborted_attempt_exposure_receipt_sha256": receipt_sha,
        "item_ids": ["item-c800"],
        "source_entity_ids": ["c" * 64],
        "component_ids": ["d" * 64],
    }
    calls: list[str] = []

    def verify_v2(_value: object) -> str:
        calls.append("verify-v2")
        return receipt_sha

    def merge(_prior: object, _value: object) -> dict[str, object]:
        calls.append("merge-c801")
        return copy.deepcopy(merged)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("legacy exposure verifier or model call reached")

    monkeypatch.setattr(runner, "verify_f1_r8_successor_exposure_set_v2", verify_v2)
    monkeypatch.setattr(runner, "merge_c801_exposure_boundaries", merge)
    monkeypatch.setattr(runner, "verify_f1_r8_successor_exposure_set", forbidden)
    monkeypatch.setattr(runner, "verify_aborted_attempt_exposure_receipt", forbidden)
    monkeypatch.setattr(runner, "verify_forbidden_exposure_union", forbidden)
    monkeypatch.setattr(runner, "run_item", forbidden)

    lock = {
        "schema_version": lock_schema,
        "run_id": run_id,
        "prior_exposure_receipt_sha256": prior_sha,
        "aborted_attempt_exposure_receipt_sha256": receipt_sha,
        "forbidden_prior_item_ids": merged["item_ids"],
        "forbidden_prior_source_entity_ids": merged["source_entity_ids"],
        "forbidden_prior_component_ids": merged["component_ids"],
    }
    assert runner._validate_aborted_attempt_exposure_gate(
        {"kind": "successor-v2"},
        prior_exposure_receipt={"kind": "prior"},
        execution_lock=lock,
    ) == receipt_sha
    assert calls == ["verify-v2", "merge-c801"]

    drifted = copy.deepcopy(lock)
    drifted["forbidden_prior_item_ids"] = []
    calls.clear()
    with pytest.raises(
        R8RunnerRefusal,
        match="execution-lock forbidden exposure union verification failed",
    ):
        runner._validate_aborted_attempt_exposure_gate(
            {"kind": "successor-v2"},
            prior_exposure_receipt={"kind": "prior"},
            execution_lock=drifted,
        )
    assert calls == ["verify-v2", "merge-c801"]

    monkeypatch.setattr(
        runner,
        "verify_f1_r8_successor_exposure_set_v2",
        lambda _value: (_ for _ in ()).throw(RuntimeError("pin missing")),
    )
    calls.clear()
    with pytest.raises(
        R8RunnerRefusal,
        match="aborted-attempt exposure receipt verification failed",
    ):
        runner._validate_aborted_attempt_exposure_gate(
            {"kind": "successor-v2"},
            prior_exposure_receipt={"kind": "prior"},
            execution_lock=lock,
        )
    assert calls == []
