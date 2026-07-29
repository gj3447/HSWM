from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
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
import prom_search_hswm.prom9_f1_r8_runner as runner
from prom_search_hswm.prom9_f1_r8_runner import (
    GENERATION_POLICY,
    GENESIS_SCHEMA,
    REQUIRED_DEPENDENCY_FILES,
    R8RunnerRefusal,
    TRANSPORT_BINDINGS_SCHEMA,
    _ATTEMPT_COLUMNS,
    _SPOOL_COLUMNS,
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
SYMPOSIUM_ROOT = REPO_ROOT.parents[1]
HSWM_COMMIT = subprocess.check_output(
    ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True
).strip()
SYMPOSIUM_COMMIT = subprocess.check_output(
    ["git", "-C", str(SYMPOSIUM_ROOT), "rev-parse", "HEAD"], text=True
).strip()
ENDPOINT = "http://127.0.0.1:8011"


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


def _registries() -> dict[str, object]:
    return {
        arm: build_registry(
            REPO_ROOT / DEFAULT_PROTOCOL,
            model="fake-model",
            model_revision="fake-revision",
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
        run_id="f1-2wiki-power-pilot-test",
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
        "run_id": "f1-2wiki-power-pilot-test",
        "mode": "development",
        "model": "fake-model",
        "model_revision": "fake-revision",
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
        "server_revision": "fake-revision",
        "db_identity": {
            "resolved_path": "/private/result-spool.sqlite3",
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
    judge_core = (
        SYMPOSIUM_ROOT
        / "FINDINGS/hswm-f1-r8-try3-2026-07-28/f1_r8_lakatotree_judge.py"
    )
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
            "endpoint": ENDPOINT,
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


def _lock(
    manifest: dict[str, object],
    *,
    bundle: dict[str, object],
    result_contract: Path,
    genesis_sha: str,
) -> dict[str, object]:
    environment = bundle["environment_receipt"]
    dependencies = bundle["dependency_receipt"]
    assert isinstance(environment, dict) and isinstance(dependencies, dict)
    return build_development_execution_lock(
        manifest,
        protocol_path=REPO_ROOT / DEFAULT_PROTOCOL,
        selection_receipt_sha256="1" * 64,
        prior_exposure_receipt_sha256="2" * 64,
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
        forbidden_prior_item_ids=["prior-item"],
        forbidden_prior_source_entity_ids=["8" * 64],
        forbidden_prior_component_ids=["9" * 64],
        execution_policy=_policy(),
    )


def _context(tmp_path: Path) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    meter = FakeMeter()
    manifest = _manifest(meter)
    result_contract = tmp_path / "result_contract.v1.json"
    result_contract.write_text('{"schema_version":"result-contract/v1"}\n')
    bundle, dependency_args = _bundle(tmp_path, manifest, result_contract)
    genesis = _genesis(str(manifest["run_id"]))
    lock = _lock(
        manifest,
        bundle=bundle,
        result_contract=result_contract,
        genesis_sha=str(genesis["genesis_sha256"]),
    )
    return {
        "meter": meter,
        "manifest": manifest,
        "result_contract": result_contract,
        "bundle": bundle,
        "genesis": genesis,
        "lock": lock,
        "preflight": _preflight(
            str(manifest["run_id"]),
            str(lock["lock_sha256"]),
            str(genesis["genesis_sha256"]),
        ),
        **dependency_args,
    }


def _sealed_preregistration_context(context: dict[str, object], tmp_path: Path):
    manifest = copy.deepcopy(context["manifest"])
    manifest["run_id"] = runner.SEALED_RUN_ID
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
            "purpose": runner.SEALED_LOCK_PURPOSE,
            "experiment_tag": runner.SEALED_EXPERIMENT_TAG,
            "closes_question": runner.SEALED_CLOSES_QUESTION,
            "run_id": runner.SEALED_RUN_ID,
            "mode": "sealed",
            "judge_core_sha256": judge_core_sha,
            "judge_core_file_sha256": hashlib.sha256(template.encode()).hexdigest(),
        }
    )
    artifact_unsigned = {
        "schema_version": runner.PREREGISTRATION_ARTIFACT_SCHEMA,
        "purpose": runner.SEALED_LOCK_PURPOSE,
        "experiment_tag": runner.SEALED_EXPERIMENT_TAG,
        "closes_question": runner.SEALED_CLOSES_QUESTION,
        "run_id": runner.SEALED_RUN_ID,
        "mode": "sealed",
        "hswm_commit": lock["hswm_commit"],
        "model": lock["model"],
        "model_revision": lock["model_revision"],
        "metric": {"name": "exact_match"},
        "baseline": {"arm": "flat_single_llm_three_call_workflow"},
        "direction": "higher",
        "noise_band": {"absolute": 0.01},
        "credence": {"alpha": 0.05},
        "bootstrap": {"replicates": 1000},
        "gates": copy.deepcopy(lock["gates"]),
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
        "purpose": runner.SEALED_LOCK_PURPOSE,
        "experiment_tag": runner.SEALED_EXPERIMENT_TAG,
        "closes_question": runner.SEALED_CLOSES_QUESTION,
        "run_id": runner.SEALED_RUN_ID,
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
        environment_dependency_bundle=context["bundle"],
        result_contract_path=context["result_contract"],
        **_dependency_kwargs(context),
        spool_identity_preflight=context["preflight"],
    )
    return draft, port


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


def test_sealed_preregistration_readback_and_manifest_core_are_exact(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path / "development")
    manifest, lock, artifact, readback, judge = _sealed_preregistration_context(
        context, tmp_path
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
            environment_dependency_bundle=context["bundle"],
            result_contract_path=context["result_contract"],
            **wrong_root_args,
            spool_identity_preflight=context["preflight"],
        )
    assert port.calls == {}


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
            "endpoint": ENDPOINT,
            "hswm_commit": HSWM_COMMIT,
            "model": "fake-model",
            "model_revision": "fake-revision",
            "run_id": context["manifest"]["run_id"],
            "symposium_commit": SYMPOSIUM_COMMIT,
        },
        inline_limit_bytes=1024 * 1024,
    )
    lock = _lock(
        context["manifest"],
        bundle=bundle,
        result_contract=context["result_contract"],
        genesis_sha=context["genesis"]["genesis_sha256"],
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
            attempt, _ATTEMPT_COLUMNS, "attempt ledger"
        )
        spool_version, spool_schema = _database_schema(
            spool, _SPOOL_COLUMNS, "result spool"
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
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    observed_entries: list[tuple[str, int]] = []
    original_attempt = runner.SQLiteF1CallLedger
    original_spool = runner.SQLiteResultSpool

    def checked_attempt(path):
        observed_entries.append(("attempt", os.stat(path).st_mode & 0o777))
        return original_attempt(path)

    def checked_spool(path):
        observed_entries.append(("spool", os.stat(path).st_mode & 0o777))
        return original_spool(path)

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
    runner._seal_private_sqlite_family(attempt_db, "attempt ledger")
    assert all(
        os.stat(f"{attempt_db}{suffix}").st_mode & 0o777 == 0o600
        for suffix in ("-wal", "-shm")
    )

    occupied_spool = tmp_path / "occupied-spool.sqlite3"
    occupied_spool.write_bytes(b"occupied")
    preserved_attempt = tmp_path / "preserved-attempt.sqlite3"
    with pytest.raises(R8RunnerRefusal, match="already occupied"):
        initialize_transport_pair(preserved_attempt, occupied_spool)
    assert preserved_attempt.exists()
    assert os.stat(preserved_attempt).st_mode & 0o777 == 0o600


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
        server_revision="fake-revision",
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
            model_revision="fake-revision",
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
    for path, value in (
        (manifest_path, context["manifest"]),
        (lock_path, context["lock"]),
        (genesis_path, {}),
        (bundle_path, {}),
    ):
        path.write_text(json.dumps(value))
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
            "--result-contract", str(context["result_contract"]),
            "--judge-core", str(context["judge_core_path"]),
            "--symposium-repo-root", str(SYMPOSIUM_ROOT),
            "--model-catalog", str(context["model_catalog_path"]),
            "--model-weight-receipt", str(context["model_weight_receipt_path"]),
            "--python-lock", str(context["python_lock_path"]),
            "--spool-token-env", "SPOOL_CLIENT_TOKEN",
            "--spool-identity-receipt", str(tmp_path / "spool-identity.json"),
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
