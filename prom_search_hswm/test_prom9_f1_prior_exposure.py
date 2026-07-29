from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib import request as urllib_request

import pytest

import prom_search_hswm.prom9_f1_prior_exposure as prior_exposure
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.hswm_call_receipt import ModelCallV1, invoke_function
from prom_search_hswm.hswm_f1_durable_transport import DurableSpoolJSONPort
from prom_search_hswm.hswm_function_registry import FunctionSpecV1
from prom_search_hswm.hswm_result_spool import RawHTTPResponse, SQLiteResultSpool
from prom_search_hswm.hswm_f1_sqlite_schema import (
    SPOOL_HISTORICAL_V8_SCHEMA_SQL,
)
from prom_search_hswm.hswm_typed_ports import canonical_json
from prom_search_hswm.prom9_f1_prior_exposure import (
    ABORTED_ATTEMPT_EXPOSURE_SCHEMA,
    ABORTED_ATTEMPT_STATUS,
    EXPECTED_PAGE_SPECS,
    PriorExposureRefusal,
    SCHEMA,
    build_aborted_attempt_exposure_receipt,
    build_prior_exposure_receipt,
    inventory_stable_tree,
    merge_exposure_boundaries,
    verify_aborted_attempt_exposure_receipt,
    verify_aborted_attempt_private_witness,
    verify_forbidden_exposure_union,
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_source import (
    build_public_artifacts,
    redact_entries,
)
from prom_search_hswm.prom9_f1_r8_runner import (
    R8RunnerRefusal,
    read_stable_json,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_RECEIPT_PATH = (
    REPO_ROOT / "receipts" / "hswm_f1_r8_v8_aborted_exposure.v1.json"
)
INCIDENT_RECEIPT_SHA256 = (
    "6d3f2f8978a8502c0f01135ad7b998841dbb4bd61462934927f735e3932bad7d"
)


class _HistoricalV8Spool:
    """Minimal exact historical spool used only by the incident fixture."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.executescript(SPOOL_HISTORICAL_V8_SCHEMA_SQL)
        self._connection.execute("PRAGMA user_version=1")
        path.chmod(0o600)

    def close(self) -> None:
        self._connection.close()


def _row(index: int) -> dict[str, object]:
    return {
        "id": f"item-{index:03d}",
        "question": f"Question {index}?",
        "answer": f"PRIVATE_ANSWER_{index}",
        "context": {
            "title": [f"Title {index}"],
            "sentences": [[f"Sentence {index}."]],
        },
        "supporting_facts": {"title": [], "sent_id": []},
        "evidences": [],
        "type": "comparison",
    }


def _private_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _fixture(tmp_path: Path):
    rows = [_row(index) for index in range(104)]
    pages: dict[tuple[int, int], tuple[Path, str]] = {}
    for offset, length in EXPECTED_PAGE_SPECS:
        value = {"rows": [{"row": row} for row in rows[offset : offset + length]]}
        path = tmp_path / f"page-{offset}-{length}.json"
        _private_json(path, value)
        pages[(offset, length)] = (path, canonical_sha256(value))

    root = tmp_path / "artifacts"
    run = root / "f1-2wiki-sealed-r1"
    run.mkdir(parents=True)
    item_ids = [f"item-{index:03d}" for index in range(4, 104)]
    _private_json(
        run / "manifest.v2.json",
        {"run_id": "f1-2wiki-sealed-r1", "items": [{"item_id": value} for value in item_ids]},
    )
    _private_json(
        run / "suite.json",
        {
            "run_id": "f1-2wiki-sealed-r1",
            "item_runs": [{"item_id": value} for value in item_ids],
        },
    )
    source_unsigned = {
        "schema_version": "hswm-prom9-f1-2wiki-source-receipt/v1",
        "run_id": "f1-2wiki-sealed-r1",
        "offset": 4,
        "length": 100,
        "viewer_response_sha256": pages[(4, 100)][1],
        "rows": [{"item_id": value} for value in item_ids],
    }
    _private_json(
        run / "source.receipt.json",
        {**source_unsigned, "source_receipt_sha256": canonical_sha256(source_unsigned)},
    )
    opaque = run / "gold.separate.json"
    opaque.write_bytes(b"PRIVATE_ANSWER_SENTINEL not-json by design")
    opaque.chmod(0o600)
    return pages, root


def _receipt(tmp_path: Path):
    pages, root = _fixture(tmp_path)
    return build_prior_exposure_receipt(
        page_files=pages,
        artifact_roots={"fixture": root},
        dataset="framolfese/2WikiMultihopQA",
        config="default",
        split="validation",
        expected_run_dirs=1,
        expected_legacy_source_receipts=1,
        expected_manifests=1,
        expected_suites=1,
    )


def _incident_receipt() -> dict[str, object]:
    value, _raw_file_sha256 = read_stable_json(
        INCIDENT_RECEIPT_PATH, "aborted-attempt exposure receipt"
    )
    return value


def _resign_incident(value: dict[str, object]) -> None:
    unsigned = copy.deepcopy(value)
    unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
    if value.get("schema_version") == ABORTED_ATTEMPT_EXPOSURE_SCHEMA:
        commitment = unsigned["private_witness_commitment"]
        public_preimage = copy.deepcopy(unsigned)
        public_preimage.pop("assurance")
        public_preimage.pop("private_witness_commitment")
        preimage_root = canonical_sha256(public_preimage)
        commitment["incident_preimage_root_sha256"] = preimage_root
        value["private_witness_commitment"][
            "incident_preimage_root_sha256"
        ] = preimage_root
    value["aborted_attempt_exposure_receipt_sha256"] = canonical_sha256(unsigned)


def _rebind_private_witness(
    receipt: dict[str, object], witness_path: Path, witness: dict[str, object]
) -> None:
    public_preimage = copy.deepcopy(receipt)
    public_preimage.pop("aborted_attempt_exposure_receipt_sha256")
    public_preimage.pop("assurance")
    public_preimage.pop("private_witness_commitment")
    witness["incident_preimage_root_sha256"] = canonical_sha256(public_preimage)
    witness_unsigned = copy.deepcopy(witness)
    witness_unsigned.pop("private_witness_sha256")
    witness["private_witness_sha256"] = canonical_sha256(witness_unsigned)
    witness_path.write_text(
        json.dumps(witness, sort_keys=True), encoding="utf-8"
    )
    witness_path.chmod(0o600)
    receipt["private_witness_commitment"]["private_witness_sha256"] = witness[
        "private_witness_sha256"
    ]
    _resign_incident(receipt)


def _minimal_prior(
    *, item_ids: list[str], source_entity_ids: list[str], component_ids: list[str]
) -> dict[str, object]:
    aggregate = {
        "prior_item_ids": item_ids,
        "prior_source_entity_ids": source_entity_ids,
        "prior_component_ids": component_ids,
        "item_root_sha256": canonical_sha256(item_ids),
        "source_entity_root_sha256": canonical_sha256(source_entity_ids),
        "component_root_sha256": canonical_sha256(component_ids),
    }
    unsigned = {
        "schema_version": SCHEMA,
        "aggregate": aggregate,
        "complete": True,
    }
    return {
        **unsigned,
        "prior_exposure_receipt_sha256": canonical_sha256(unsigned),
    }


MODEL_REVISION = "f" * 40
PROTECTED_RESPONSE_SENTINEL = b"PROTECTED_RESPONSE_BLOB_MUST_NOT_BE_READ"


class _SyntheticCrash(BaseException):
    pass


def _public_incident_artifacts(
    public_selection_receipt_sha256: str,
    *,
    include_untouched: bool = False,
    two_shared_items: bool = False,
) -> dict[str, dict[str, object]]:
    full = [
        {
            "dataset_row_index": 124,
            "row": {
                "id": "incident-item",
                "question": "Question?",
                "answer": "PRIVATE_GOLD_NEVER_PASSED_TO_PRODUCER",
                "context": {
                    "title": ["Public title"],
                    "sentences": [["Public sentence."]],
                },
                "supporting_facts": {"title": [], "sent_id": []},
                "evidences": [],
                "type": "comparison",
            },
        }
    ]
    if include_untouched and two_shared_items:
        raise ValueError("synthetic public fixture modes are mutually exclusive")
    if include_untouched:
        full.append(
            {
                "dataset_row_index": 125,
                "row": {
                    "id": "incident-item-untouched",
                    "question": "Untouched question?",
                    "answer": "PRIVATE_UNTOUCHED_GOLD",
                    "context": {
                        "title": ["Untouched public title"],
                        "sentences": [["Untouched public sentence."]],
                    },
                    "supporting_facts": {"title": [], "sent_id": []},
                    "evidences": [],
                    "type": "comparison",
                },
            }
        )
    elif two_shared_items:
        shared = copy.deepcopy(full[0])
        shared["dataset_row_index"] = 125
        shared["row"]["id"] = "incident-item-shared"
        shared["row"]["question"] = "Shared question?"
        shared["row"]["answer"] = "PRIVATE_SHARED_GOLD"
        full.append(shared)
    public = redact_entries(full)
    return build_public_artifacts(
        public,
        public_selection_receipt_sha256=public_selection_receipt_sha256,
        dataset="framolfese/2WikiMultihopQA",
        config="default",
        split="validation",
        run_id="f1-2wiki-development-r8-incident-test",
        mode="development",
        model="fixed-model",
        model_revision=MODEL_REVISION,
        token_envelope={
            "schema_version": "hswm-prom9-f1-token-envelope/v1",
            "tokenizer": {},
            "filler": {
                "field": "parity_filler",
                "unit": "0",
                "max_filler_chars": 10000,
            },
            "per_call_input_caps": {"1": 275, "2": 1691, "3": 2359},
            "per_call_output_caps": {"1": 768, "2": 1536, "3": 768},
            "projected_output_tokens_by_arm": {
                arm: {"1": 1, "2": 1, "3": 1}
                for arm in prior_exposure._F1_ARMS
            },
            "projection_slack_tokens": 0,
        },
        preregistration_artifact_sha256=None,
    )


def _incident_function(
    call_index: int, *, prompt_override: str | None = None
) -> FunctionSpecV1:
    contracts = {
        1: ("QF_QUERY_COMPILER", "QueryEnvelopeV1", "QueryPlanV1"),
        2: ("BF_BOND_PROPOSER", "BondScoringEnvelopeV1", "BondProposalV1"),
    }
    function_id, input_type, output_type = contracts[call_index]
    prompt = prompt_override or f"Execute {function_id}."
    return FunctionSpecV1(
        function_id=function_id,
        model="fixed-model",
        model_revision=MODEL_REVISION,
        input_type=input_type,
        output_type=output_type,
        prompt=prompt,
        prompt_sha256=canonical_sha256({"prompt": prompt}),
    )


def _incident_input(
    request_id: str, item: dict[str, object]
) -> dict[str, object]:
    candidates = item["candidates"]
    assert isinstance(candidates, list)
    return {
        "request_id": request_id,
        "query_text": item["query_text"],
        "allowed_evidence_types": item["allowed_evidence_types"],
        "budget": {
            "max_candidates": len(candidates),
            "max_evidence_items": item["max_evidence_items"],
            "max_input_tokens": item["max_input_tokens"],
            "max_output_tokens": item["max_output_tokens_per_call"],
        },
        "parity_filler": "",
    }


def _incident_bond_input(
    request_id: str, item: dict[str, object], arm_id: str
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "query_plan": _incident_output(request_id),
        "candidate_table": prior_exposure._candidate_table_for_manifest_item(
            item, arm_id
        ),
        "candidate_budget": item["max_evidence_items"],
        "parity_filler": "",
    }


def _incident_output(request_id: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "objectives": ["answer"],
        "required_evidence_types": ["text"],
        "constraints": ["use supplied evidence"],
        "abstain": False,
    }


class _SyntheticAttestedTransport:
    def __call__(
        self, request: urllib_request.Request, _timeout: float
    ) -> RawHTTPResponse:
        request_value = json.loads(bytes(request.data or b"").decode("utf-8"))
        input_value = json.loads(request_value["messages"][1]["content"])
        content = canonical_json(_incident_output(str(input_value["request_id"])))
        body = canonical_json(
            {
                "model": "fixed-model",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
            }
        ).encode("utf-8")
        call_id = request.full_url.rsplit("/", 1)[-1]
        request_bytes = bytes(request.data or b"")
        return RawHTTPResponse(
            status=200,
            headers={
                "content-type": "application/json",
                "content-length": str(len(body)),
                "x-hswm-spool-call-id": call_id,
                "x-hswm-spool-intent-sha256": str(
                    request.get_header("X-hswm-intent-sha256")
                ),
                "x-hswm-spool-request-sha256": hashlib.sha256(
                    request_bytes
                ).hexdigest(),
                "x-hswm-spool-response-sha256": hashlib.sha256(body).hexdigest(),
                "x-hswm-spool-replayed": "false",
                "x-hswm-spool-server-revision": str(
                    request.get_header("X-hswm-model-revision")
                ),
            },
            body=body,
        )


def _private_artifact(path: Path, value: dict[str, object]) -> Path:
    _private_json(path, value)
    return path


def _build_synthetic_incident(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    qf_prompt_override: str | None = None,
    verify_private_witness_before_close: bool = False,
    verify_private_sidecar_tamper_before_close: bool = False,
    include_untouched: bool = False,
    two_shared_items: bool = False,
) -> dict[str, object]:
    selection_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-cohort-selection/v2"
    }
    selection_value = {
        **selection_unsigned,
        "selection_receipt_sha256": canonical_sha256(selection_unsigned),
    }
    artifacts = _public_incident_artifacts(
        str(selection_value["selection_receipt_sha256"]),
        include_untouched=include_untouched,
        two_shared_items=two_shared_items,
    )
    arm_id = "typed_hswm_three_function_network"
    manifest_item = artifacts["manifest"]["items"][0]
    assert isinstance(manifest_item, dict)
    request_id = "req-" + canonical_sha256(
        {
            "run_id": artifacts["manifest"]["run_id"],
            "arm_id": arm_id,
            "item_id": manifest_item["item_id"],
        }
    )[:8]
    attempt_db = tmp_path / "incident" / "attempt.sqlite3"
    spool_db = tmp_path / "incident" / "spool.sqlite3"
    attempt_db.parent.mkdir(mode=0o700)

    def fault(stage: str, call: ModelCallV1) -> None:
        if stage == "after_sent" and call.call_index == 2:
            raise _SyntheticCrash

    port = DurableSpoolJSONPort(
        "http://spool",
        attempt_db,
        transport=_SyntheticAttestedTransport(),
        delivery_backoff_s=(0.0,),
        fault_injector=fault,
    )
    port.ledger._connection.execute("PRAGMA wal_autocheckpoint=0")
    invoke_function(
        run_id=str(artifacts["manifest"]["run_id"]),
        arm_id=arm_id,
        item_id="incident-item",
        call_index=1,
        function=_incident_function(1, prompt_override=qf_prompt_override),
        input_payload=_incident_input(request_id, manifest_item),
        max_output_tokens=768,
        model_port=port,
    )
    if two_shared_items:
        shared_item = artifacts["manifest"]["items"][1]
        shared_request_id = "req-" + canonical_sha256(
            {
                "run_id": artifacts["manifest"]["run_id"],
                "arm_id": arm_id,
                "item_id": shared_item["item_id"],
            }
        )[:8]
        invoke_function(
            run_id=str(artifacts["manifest"]["run_id"]),
            arm_id=arm_id,
            item_id=str(shared_item["item_id"]),
            call_index=1,
            function=_incident_function(1),
            input_payload=_incident_input(shared_request_id, shared_item),
            max_output_tokens=768,
            model_port=port,
        )
    with pytest.raises(_SyntheticCrash):
        invoke_function(
            run_id=str(artifacts["manifest"]["run_id"]),
            arm_id=arm_id,
            item_id="incident-item",
            call_index=2,
            function=_incident_function(2),
            input_payload=_incident_bond_input(
                request_id, manifest_item, arm_id
            ),
            max_output_tokens=1536,
            model_port=port,
        )
    accepted_rows = port.ledger._connection.execute(
        "SELECT physical_call_id,intent_sha256,request_sha256,request_bytes,"
        "response_status,response_sha256 FROM call_state WHERE status='ACCEPTED'"
    ).fetchall()
    assert accepted_rows
    spool = _HistoricalV8Spool(spool_db)
    spool._connection.execute("PRAGMA wal_autocheckpoint=0")
    for accepted in accepted_rows:
        spool._connection.execute(
            "INSERT INTO spool_calls(physical_call_id,intent_sha256,request_sha256,"
            "request_bytes,status,response_status,response_headers,response_body,"
            "response_sha256,error_class) VALUES(?,?,?,?,'COMPLETE',?,?,?,?,NULL)",
            (
                accepted["physical_call_id"],
                accepted["intent_sha256"],
                accepted["request_sha256"],
                accepted["request_bytes"],
                accepted["response_status"],
                b'{"protected":"headers"}',
                PROTECTED_RESPONSE_SENTINEL,
                accepted["response_sha256"],
            ),
        )
    for member in (spool_db, Path(f"{spool_db}-wal"), Path(f"{spool_db}-shm")):
        if member.exists():
            member.chmod(0o600)

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    selection = _private_artifact(
        inputs / "selection.json", selection_value,
    )
    manifest = _private_artifact(inputs / "manifest.json", artifacts["manifest"])
    source = _private_artifact(inputs / "source.json", artifacts["source_receipt"])
    executable_commit = prior_exposure._HISTORICAL_RUNTIME_COMMITS[
        "hswm_executable"
    ]
    carrier_commit = prior_exposure._HISTORICAL_RUNTIME_COMMITS[
        "hswm_carrier"
    ]
    symposium_commit = prior_exposure._HISTORICAL_RUNTIME_COMMITS["symposium"]
    def db_identity(path: Path) -> dict[str, object]:
        info = path.stat()
        return {
            "resolved_path": str(path.resolve()),
            "st_dev": info.st_dev,
            "st_ino": info.st_ino,
        }

    def schema_sha(connection: sqlite3.Connection) -> str:
        tables = sorted(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        observed = {
            table: [
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({table})")
            ]
            for table in tables
        }
        return canonical_sha256(
            {"user_version": 1, "tables": observed}
        )

    attempt_identity = db_identity(attempt_db)
    spool_db_identity = db_identity(spool_db)
    genesis_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-transport-genesis/v1",
        "run_id": artifacts["manifest"]["run_id"],
        "attempt_db_identity": attempt_identity,
        "spool_db_identity": spool_db_identity,
        "attempt_schema_sha256": schema_sha(port.ledger._connection),
        "spool_schema_sha256": schema_sha(spool._connection),
        "attempt_integrity": "ok",
        "spool_integrity": "ok",
        "attempt_journal_mode": "wal",
        "spool_journal_mode": "wal",
        "attempt_audit_connection_synchronous": "2",
        "spool_audit_connection_synchronous": "2",
        "attempt_user_version": 1,
        "spool_user_version": 1,
        "call_count": 0,
        "item_run_count": 0,
        "attempt_event_count": 0,
        "spool_call_count": 0,
    }
    genesis_value = {
        **genesis_unsigned,
        "genesis_sha256": canonical_sha256(genesis_unsigned),
    }
    deployment_unsigned = {
        "schema_version": "hswm-openai-deployment-attestation/v2"
    }
    deployment_value = {
        **deployment_unsigned,
        "receipt_sha256": canonical_sha256(deployment_unsigned),
    }
    environment_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-environment-dependency-bundle/v1",
        "environment_receipt": {
            "labels": {"symposium_commit": symposium_commit},
        },
        "dependency_receipt": {
            "files": {
                "model_deployment_receipt": {
                    "sha256": hashlib.sha256(
                        json.dumps(deployment_value).encode("utf-8")
                    ).hexdigest(),
                }
            },
        },
    }
    environment_value = {
        **environment_unsigned,
        "bundle_sha256": canonical_sha256(environment_unsigned),
    }
    lock_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-execution-lock/v2",
        "run_id": artifacts["manifest"]["run_id"],
        "mode": artifacts["manifest"]["mode"],
        "model": artifacts["manifest"]["model"],
        "model_revision": artifacts["manifest"]["model_revision"],
        "hswm_commit": executable_commit,
        "manifest_sha256": canonical_sha256(artifacts["manifest"]),
        "selection_receipt_sha256": selection_value[
            "selection_receipt_sha256"
        ],
        "public_source_receipt_sha256": artifacts["source_receipt"][
            "source_receipt_sha256"
        ],
        "db_genesis_receipt_sha256": genesis_value["genesis_sha256"],
        "environment_dependency_bundle_sha256": environment_value[
            "bundle_sha256"
        ],
        "deployment_receipt_sha256": deployment_value["receipt_sha256"],
        "preregistration_artifact_sha256": artifacts["manifest"][
            "preregistration_artifact_sha256"
        ],
        "deployment_id": "test-deployment-id",
        "served_model": artifacts["manifest"]["model"],
        "upstream_endpoint": "http://model",
        "execution_policy": {"endpoint": "http://spool"},
    }
    lock = _private_artifact(
        inputs / "lock.json",
        {**lock_unsigned, "lock_sha256": canonical_sha256(lock_unsigned)},
    )
    genesis = _private_artifact(
        inputs / "genesis.json", genesis_value,
    )
    environment = _private_artifact(
        inputs / "environment.json", environment_value,
    )
    deployment = _private_artifact(
        inputs / "deployment.json", deployment_value,
    )
    spool_audit_unsigned = {
        "schema_version": "hswm-f1-result-spool/v1",
        "journal_mode": "wal",
        "synchronous": 2,
        "call_count": 0,
        "status_counts": {},
        "completed_root_sha256": canonical_sha256([]),
    }
    spool_audit = {
        **spool_audit_unsigned,
        "audit_sha256": canonical_sha256(spool_audit_unsigned),
    }
    endpoint_identity_unsigned = {
        "schema_version": "hswm-f1-result-spool-identity/v2",
        "normalized_upstream_endpoint": lock_unsigned["upstream_endpoint"],
        "deployment_receipt_sha256": deployment_value["receipt_sha256"],
        "deployment_id": lock_unsigned["deployment_id"],
        "served_model": lock_unsigned["served_model"],
        "model_revision": artifacts["manifest"]["model_revision"],
        "db_identity": spool_db_identity,
        "audit": spool_audit,
    }
    endpoint_identity = {
        **endpoint_identity_unsigned,
        "identity_sha256": canonical_sha256(endpoint_identity_unsigned),
    }
    spool_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-spool-endpoint-preflight/v2",
        "run_id": artifacts["manifest"]["run_id"],
        "model_revision": artifacts["manifest"]["model_revision"],
        "execution_lock_sha256": lock_unsigned["lock_sha256"]
        if "lock_sha256" in lock_unsigned
        else canonical_sha256(lock_unsigned),
        "db_genesis_sha256": genesis_value["genesis_sha256"],
        "deployment_receipt_sha256": deployment_value["receipt_sha256"],
        "deployment_id": lock_unsigned["deployment_id"],
        "served_model": lock_unsigned["served_model"],
        "upstream_endpoint": lock_unsigned["upstream_endpoint"],
        "endpoint": "http://spool",
        "endpoint_identity": endpoint_identity,
    }
    spool_identity = _private_artifact(
        inputs / "spool-identity.json",
        {
            **spool_unsigned,
            "preflight_sha256": canonical_sha256(spool_unsigned),
        },
    )
    job_dir = tmp_path / "jobs" / "hswm-f1-r8-v8-development-test"
    job_dir.mkdir(parents=True)
    job_command = job_dir / "cmd.sh"
    job_log = job_dir / "log"
    job_rc = job_dir / "rc"
    job_command.write_text(
        "F1_ROOT=" + str(attempt_db.parent.parent.resolve()) + "\n"
        "python -m prom_search_hswm.prom9_f1_r8_runner run "
        "--attempt-db attempt.sqlite3 --spool-db spool.sqlite3 "
        "--manifest manifest.json --execution-lock lock.json\n",
        encoding="utf-8",
    )
    job_log.write_bytes(b"Bus error (core dumped)\n")
    job_rc.write_bytes(b"135\n")
    job_command.chmod(0o664)
    job_log.chmod(0o664)
    roots = {
        "exec": tmp_path / "exec-root",
        "carrier": tmp_path / "carrier-root",
        "symposium": tmp_path / "symposium-root",
    }
    for root in roots.values():
        root.mkdir()
    git_bindings = {
        str(roots["exec"].resolve()): {
            "commit": executable_commit,
            "tree": "1" * 40,
        },
        str(roots["carrier"].resolve()): {
            "commit": carrier_commit,
            "tree": "2" * 40,
        },
        str(roots["symposium"].resolve()): {
            "commit": symposium_commit,
            "tree": "3" * 40,
        },
    }

    def fake_git_binding(root: Path, _label: str) -> dict[str, str]:
        return git_bindings[str(Path(root).resolve())]

    monkeypatch.setattr(prior_exposure, "_git_binding", fake_git_binding)
    producer_files = [
        {
            "relative_path": relative_path,
            "size_bytes": 1,
            "sha256": "0" * 64,
            "blob_mode": "100644",
            "blob_oid": "f" * 40,
        }
        for relative_path in prior_exposure._CURRENT_PRODUCER_IMPORT_LFP
    ]
    monkeypatch.setattr(
        prior_exposure,
        "_current_producer_authority",
        lambda _root: {
            "commit": "d" * 40,
            "tree": "e" * 40,
            "entrypoint": "prom_search_hswm/prom9_f1_prior_exposure.py",
            "closure_policy": "MODULE_SCOPE_LOCAL_AST_LFP_V1",
            "files": producer_files,
            "file_count": len(producer_files),
            "closure_root_sha256": canonical_sha256(producer_files),
        },
    )
    historical_files = [
        {
            "relative_path": relative_path,
            "size_bytes": 1,
            "sha256": "1" * 64,
            "blob_mode": "100644",
            "blob_oid": "a" * 40,
        }
        for relative_path in prior_exposure._HISTORICAL_REPLAY_IMPORT_LFP
    ]
    historical_result = {
        "manifest": artifacts["manifest"],
        "source_receipt": artifacts["source_receipt"],
        "protocol_roots": ["2" * 64],
        "registries_root_sha256": "3" * 64,
        "prompts": [
            {
                "arm_id": arm_id,
                "function_id": "QF_QUERY_COMPILER",
                "prompt": "Execute QF_QUERY_COMPILER.",
            },
            {
                "arm_id": arm_id,
                "function_id": "BF_BOND_PROPOSER",
                "prompt": "Execute BF_BOND_PROPOSER.",
            },
        ],
        "python": {"implementation": "cpython", "version": "3.12.0"},
    }
    historical_authority = {
        "repositories": {
            name: git_bindings[str(roots[alias].resolve())]
            for name, alias in (
                ("hswm_executable", "exec"),
                ("hswm_carrier", "carrier"),
                ("symposium", "symposium"),
            )
        },
        "replay_policy": "COMMIT_BLOBS_PYTHON_ISOLATED_NO_NETWORK_V1",
        "replay_files": historical_files,
        "replay_file_count": len(historical_files),
        "replay_closure_root_sha256": canonical_sha256(historical_files),
        "python_runtime": {
            "implementation": "CPython",
            "version": "3.12.0",
            "executable_size_bytes": 1,
            "executable_sha256": "4" * 64,
        },
        "replay_result_sha256": canonical_sha256(historical_result),
    }
    monkeypatch.setattr(
        prior_exposure,
        "_historical_runtime_replay",
        lambda **_kwargs: (historical_result, historical_authority),
    )
    monkeypatch.setattr(
        prior_exposure, "_verify_incident_artifact_semantics", lambda *_values: None
    )
    monkeypatch.setattr(
        prior_exposure,
        "_registry_prompt_authority",
        lambda *_args: {
            (arm_id, "QF_QUERY_COMPILER"): "Execute QF_QUERY_COMPILER.",
            (arm_id, "BF_BOND_PROPOSER"): "Execute BF_BOND_PROPOSER.",
        },
    )
    witness_parent = tmp_path / "private-witness"
    witness_parent.mkdir(mode=0o700)
    try:
        receipt = build_aborted_attempt_exposure_receipt(
            attempt_db=attempt_db,
            spool_db=spool_db,
            selection_receipt=selection,
            manifest=manifest,
            source_receipt=source,
            execution_lock=lock,
            db_genesis_receipt=genesis,
            environment_dependency_bundle=environment,
            model_deployment_receipt=deployment,
            spool_identity_receipt=spool_identity,
            job_command=job_command,
            job_log=job_log,
            job_rc=job_rc,
            hswm_executable_root=roots["exec"],
            hswm_carrier_root=roots["carrier"],
            symposium_root=roots["symposium"],
            snapshot_dir=tmp_path / "snapshot",
            private_witness_output=witness_parent / "witness.v1.json",
        )
        if verify_private_witness_before_close:
            assert (
                verify_aborted_attempt_private_witness(
                    receipt, witness_parent / "witness.v1.json"
                )
                == "RAW_WITNESS_VERIFIED"
            )
        if verify_private_sidecar_tamper_before_close:
            witness_path = witness_parent / "witness.v1.json"
            witness = json.loads(witness_path.read_text(encoding="utf-8"))
            sidecar = witness["databases"]["attempt"]["generation"]["shm"]
            assert isinstance(sidecar, dict)
            sidecar["sha256"] = "f" * 64
            _rebind_private_witness(receipt, witness_path, witness)
            with pytest.raises(PriorExposureRefusal, match="live generation drifted"):
                verify_aborted_attempt_private_witness(receipt, witness_path)
    finally:
        spool.close()
        port.close()
    return receipt


def test_complete_receipt_has_exact_104_item_union_and_opaque_gold(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path)
    assert receipt["complete"] is True
    assert receipt["counts"]["items"] == 104
    assert receipt["counts"]["pages"] == 4
    assert receipt["counts"]["legacy_source_receipts"] == 1
    assert verify_prior_exposure_receipt(receipt) == receipt[
        "prior_exposure_receipt_sha256"
    ]
    gold = next(
        row for row in receipt["artifact_inventory"] if row["path"].endswith("gold.separate.json")
    )
    assert gold["size_bytes"] == len(b"PRIVATE_ANSWER_SENTINEL not-json by design")


def test_missing_or_hash_drifted_legacy_page_is_refused(tmp_path: Path) -> None:
    pages, root = _fixture(tmp_path)
    missing = dict(pages)
    missing.pop((0, 1))
    with pytest.raises(PriorExposureRefusal, match="four legacy pages"):
        build_prior_exposure_receipt(
            page_files=missing,
            artifact_roots={"fixture": root},
            dataset="dataset",
            config="default",
            split="validation",
            expected_run_dirs=1,
            expected_legacy_source_receipts=1,
            expected_manifests=1,
            expected_suites=1,
        )
    drifted = dict(pages)
    drifted[(0, 1)] = (pages[(0, 1)][0], "0" * 64)
    with pytest.raises(PriorExposureRefusal, match="page hash drifted"):
        build_prior_exposure_receipt(
            page_files=drifted,
            artifact_roots={"fixture": root},
            dataset="dataset",
            config="default",
            split="validation",
            expected_run_dirs=1,
            expected_legacy_source_receipts=1,
            expected_manifests=1,
            expected_suites=1,
        )


def test_prior_receipt_self_hash_tamper_is_refused(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path)
    tampered = copy.deepcopy(receipt)
    tampered["aggregate"]["prior_item_ids"].pop()
    with pytest.raises(PriorExposureRefusal, match="self-hash"):
        verify_prior_exposure_receipt(tampered)


def test_artifact_tree_refuses_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    target = root / "target"
    target.write_bytes(b"value")
    (root / "link").symlink_to(target)
    with pytest.raises(PriorExposureRefusal, match="symlink"):
        inventory_stable_tree("fixture", root)


def test_private_reader_refuses_lstat_to_open_identity_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "private.json"
    replacement = tmp_path / "replacement.json"
    _private_json(target, {"identity": "before"})
    _private_json(replacement, {"identity": "after"})
    original_open = os.open
    swapped = False

    def swapping_open(path, flags, *args):
        nonlocal swapped
        if not swapped and Path(path) == target:
            os.replace(replacement, target)
            swapped = True
        return original_open(path, flags, *args)

    monkeypatch.setattr(prior_exposure.os, "open", swapping_open)
    with pytest.raises(PriorExposureRefusal, match="changed before"):
        prior_exposure._read_private_bytes(target)


def test_private_write_is_0600_and_write_once(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    write_private_once(output, {"value": 1})
    assert os.stat(output).st_mode & 0o777 == 0o600
    with pytest.raises(PriorExposureRefusal, match="replace"):
        write_private_once(output, {"value": 2})


def test_aborted_attempt_builder_replays_structural_evidence_without_blobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(
        tmp_path, monkeypatch, verify_private_witness_before_close=True
    )
    assert receipt["schema_version"] == ABORTED_ATTEMPT_EXPOSURE_SCHEMA
    assert receipt["status"] == ABORTED_ATTEMPT_STATUS
    assert receipt["complete"] is True
    assert set(receipt["run_identity"]) == {
        "carrier_commit",
        "implementation_commit",
        "job_alias",
        "mode",
        "model",
        "model_revision",
        "run_id",
        "symposium_commit",
    }
    assert receipt["run_identity"]["job_alias"] == (
        "HSWM_F1_R8_V8_DEVELOPMENT_SIGBUS"
    )
    assert (
        verify_aborted_attempt_exposure_receipt(receipt)
        == receipt["aborted_attempt_exposure_receipt_sha256"]
    )
    calls = receipt["call_observations"]
    assert [call["raw_attempt_state"] for call in calls] == ["ACCEPTED", "SENT"]
    assert [call["spool_snapshot_state"] for call in calls] == ["COMPLETE", None]
    assert all(call["dataset_row_index"] == 124 for call in calls)
    assert receipt["counts"] == {
        "attempt_calls": 2,
        "attempt_events": 8,
        "item_runs": 0,
        "spool_calls": 1,
        "attempt_states": {"ACCEPTED": 1, "SENT": 1},
        "spool_complete_calls": 1,
        "spool_absent_calls": 1,
        "items": 1,
        "source_entities": 1,
        "components": 1,
    }
    serialized = canonical_json(receipt)
    assert PROTECTED_RESPONSE_SENTINEL.decode("ascii") not in serialized
    assert "PRIVATE_GOLD_NEVER_PASSED_TO_PRODUCER" not in serialized
    assert "shm" not in canonical_json(receipt["database_snapshots"]).casefold()
    producer_authority = receipt["evidence_bindings"][
        "current_producer_authority"
    ]
    assert producer_authority["file_count"] == 20
    assert tuple(
        entry["relative_path"] for entry in producer_authority["files"]
    ) == prior_exposure._CURRENT_PRODUCER_IMPORT_LFP
    assert all(
        database["canonical_schema_sha256"]
        == prior_exposure.canonical_schema_sha256(
            prior_exposure._HISTORICAL_V8_SCHEMA_AUTHORITIES[name]
        )
        and "source_identity" not in database
        and "source_identity_sha256" not in database
        for name, database in receipt["database_snapshots"].items()
    )

    def strings(value: object):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)

    public_strings = list(strings(receipt))
    assert not any(value.startswith("/") for value in public_strings)
    assert not {"stage_path", "capture_host", "resolved_path", "source_identity"} & set(
        public_strings
    )
    witness_path = tmp_path / "private-witness" / "witness.v1.json"
    assert witness_path.stat().st_mode & 0o777 == 0o600
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    assert witness["nonce_hex"] not in serialized
    assert witness["stage_path"] not in serialized
    for database in witness["databases"].values():
        assert database["resolved_path"] not in serialized
        assert str(database["st_dev"]) not in public_strings
        assert str(database["st_ino"]) not in public_strings


@pytest.mark.parametrize(
    "mutation",
    ["stage_relative", "database_path", "generation", "role_swap"],
)
def test_aborted_attempt_private_witness_coherent_tamper_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    witness_path = tmp_path / "private-witness" / "witness.v1.json"
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    if mutation == "stage_relative":
        witness["stage_path"] = "relative/stage"
    elif mutation == "database_path":
        witness["databases"]["attempt"]["resolved_path"] = "relative.sqlite3"
    elif mutation == "generation":
        witness["databases"]["attempt"]["generation"]["main"]["sha256"] = (
            "f" * 64
        )
    else:
        witness["databases"]["attempt"], witness["databases"]["spool"] = (
            witness["databases"]["spool"],
            witness["databases"]["attempt"],
        )
    witness_unsigned = copy.deepcopy(witness)
    witness_unsigned.pop("private_witness_sha256")
    witness["private_witness_sha256"] = canonical_sha256(witness_unsigned)
    witness_path.write_text(
        json.dumps(witness, sort_keys=True), encoding="utf-8"
    )
    witness_path.chmod(0o600)
    receipt["private_witness_commitment"]["private_witness_sha256"] = witness[
        "private_witness_sha256"
    ]
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal):
        verify_aborted_attempt_private_witness(receipt, witness_path)


def test_aborted_attempt_private_witness_commitment_tamper_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    receipt["private_witness_commitment"]["private_witness_sha256"] = "f" * 64
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal, match="commitment mismatch"):
        verify_aborted_attempt_private_witness(
            receipt, tmp_path / "private-witness" / "witness.v1.json"
        )


def test_private_genesis_cannot_be_coherently_rewritten_against_public_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    witness_path = tmp_path / "private-witness" / "witness.v1.json"
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    genesis = witness["db_genesis_receipt"]
    genesis["run_id"] = "foreign-run"
    genesis_unsigned = copy.deepcopy(genesis)
    genesis_unsigned.pop("genesis_sha256")
    genesis["genesis_sha256"] = canonical_sha256(genesis_unsigned)
    preflight = witness["spool_identity_receipt"]
    preflight["db_genesis_sha256"] = genesis["genesis_sha256"]
    preflight_unsigned = copy.deepcopy(preflight)
    preflight_unsigned.pop("preflight_sha256")
    preflight["preflight_sha256"] = canonical_sha256(preflight_unsigned)
    artifacts = receipt["evidence_bindings"]["artifacts"]
    for artifact_name, value, self_field in (
        ("db_genesis_receipt", genesis, "genesis_sha256"),
        ("spool_identity_receipt", preflight, "preflight_sha256"),
    ):
        binding = artifacts[artifact_name]
        raw = (canonical_json(value) + "\n").encode("utf-8")
        binding["size_bytes"] = len(raw)
        binding["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        binding["canonical_sha256"] = canonical_sha256(value)
        binding["declared_hashes"][self_field] = value[self_field]
    _rebind_private_witness(receipt, witness_path, witness)
    with pytest.raises(PriorExposureRefusal, match="public run authority"):
        verify_aborted_attempt_private_witness(receipt, witness_path)


def test_private_generation_is_bound_to_public_snapshot_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    witness_path = tmp_path / "private-witness" / "witness.v1.json"
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    database = receipt["database_snapshots"]["attempt"]
    database["members"]["main"]["sha256"] = "f" * 64
    database["authority_root_sha256"] = canonical_sha256(database["members"])
    _rebind_private_witness(receipt, witness_path, witness)
    with pytest.raises(PriorExposureRefusal, match="public snapshot"):
        verify_aborted_attempt_private_witness(receipt, witness_path)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("deployment_id", "foreign-deployment"),
        ("upstream_endpoint", "http://foreign-model"),
    ],
)
def test_private_preflight_roles_cannot_diverge_from_endpoint_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: str,
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    witness_path = tmp_path / "private-witness" / "witness.v1.json"
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    preflight = witness["spool_identity_receipt"]
    preflight[field] = replacement
    preflight_unsigned = copy.deepcopy(preflight)
    preflight_unsigned.pop("preflight_sha256")
    preflight["preflight_sha256"] = canonical_sha256(preflight_unsigned)
    binding = receipt["evidence_bindings"]["artifacts"][
        "spool_identity_receipt"
    ]
    raw = (canonical_json(preflight) + "\n").encode("utf-8")
    binding["size_bytes"] = len(raw)
    binding["raw_sha256"] = hashlib.sha256(raw).hexdigest()
    binding["canonical_sha256"] = canonical_sha256(preflight)
    binding["declared_hashes"]["preflight_sha256"] = preflight[
        "preflight_sha256"
    ]
    _rebind_private_witness(receipt, witness_path, witness)
    with pytest.raises(PriorExposureRefusal, match="public run authority"):
        verify_aborted_attempt_private_witness(receipt, witness_path)


def test_current_producer_root_must_be_the_executing_checkout(
    tmp_path: Path,
) -> None:
    alternate = tmp_path / "alternate-checkout"
    alternate.mkdir()
    with pytest.raises(PriorExposureRefusal, match="executing module root"):
        prior_exposure._current_producer_root(alternate)


def test_private_sidecar_tamper_reaches_live_family_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_synthetic_incident(
        tmp_path,
        monkeypatch,
        verify_private_sidecar_tamper_before_close=True,
    )


def test_private_stage_cannot_be_broadened_after_coherent_resign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    witness_path = tmp_path / "private-witness" / "witness.v1.json"
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    witness["stage_path"] = str(Path(witness["stage_path"]).parent)
    _rebind_private_witness(receipt, witness_path, witness)
    with pytest.raises(PriorExposureRefusal, match="stage"):
        verify_aborted_attempt_private_witness(receipt, witness_path)


def test_attempt_input_preimages_are_bound_to_the_declared_manifest_item() -> None:
    selection_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-cohort-selection/v2"
    }
    artifacts = _public_incident_artifacts(canonical_sha256(selection_unsigned))
    manifest = copy.deepcopy(artifacts["manifest"])
    item = manifest["items"][0]
    assert isinstance(item, dict)
    foreign = copy.deepcopy(item)
    foreign["item_id"] = "foreign-item"
    foreign_candidate = foreign["candidates"][0]
    foreign_candidate["bond_id"] = "foreign-bond"
    foreign_candidate["evidence_id"] = "foreign-evidence"
    foreign_candidate["content"] = "Foreign public evidence."
    manifest["items"].append(foreign)
    arm_id = "typed_hswm_three_function_network"
    request_id = "req-" + canonical_sha256(
        {
            "run_id": manifest["run_id"],
            "arm_id": arm_id,
            "item_id": item["item_id"],
        }
    )[:8]
    call = {
        "run_id": manifest["run_id"],
        "arm_id": arm_id,
        "item_id": item["item_id"],
        "call_index": 2,
        "input_payload": _incident_bond_input(request_id, item, arm_id),
    }
    prior_exposure._verify_call_input_manifest_binding(call, manifest)
    bad_filler = copy.deepcopy(call)
    bad_filler["input_payload"]["parity_filler"] = "foreign"
    with pytest.raises(PriorExposureRefusal, match="parity filler"):
        prior_exposure._verify_call_input_manifest_binding(
            bad_filler, manifest
        )
    bad_plan = copy.deepcopy(call)
    bad_plan["input_payload"]["query_plan"]["request_id"] = "foreign"
    with pytest.raises(PriorExposureRefusal, match="candidate input"):
        prior_exposure._verify_call_input_manifest_binding(bad_plan, manifest)
    crossed = copy.deepcopy(call)
    crossed["input_payload"]["candidate_table"] = (
        prior_exposure._candidate_table_for_manifest_item(foreign, arm_id)
    )
    with pytest.raises(PriorExposureRefusal, match="candidate input"):
        prior_exposure._verify_call_input_manifest_binding(crossed, manifest)

    answer_call = {
        **call,
        "call_index": 3,
        "input_payload": {
            "request_id": request_id,
            "query_text": item["query_text"],
            "query_plan": _incident_output(request_id),
            "selected_evidence": [
                {
                    "evidence_id": foreign_candidate["evidence_id"],
                    "content": foreign_candidate["content"],
                }
            ],
            "max_answer_tokens": item["max_output_tokens_per_call"],
            "parity_filler": "",
        },
    }
    with pytest.raises(PriorExposureRefusal, match="answer input"):
        prior_exposure._verify_call_input_manifest_binding(answer_call, manifest)


def test_candidate_serializer_matches_canonical_network_for_every_arm() -> None:
    selection_unsigned = {
        "schema_version": "hswm-prom9-f1-r8-cohort-selection/v2"
    }
    artifacts = _public_incident_artifacts(canonical_sha256(selection_unsigned))
    item = artifacts["manifest"]["items"][0]
    candidates = [
        prior_exposure.EvidenceCandidateV1(
            bond_id=value["bond_id"],
            evidence_id=value["evidence_id"],
            source_entity_id=value["source_entity_id"],
            content=value["content"],
            observable=dict(value["observable"]),
        )
        for value in item["candidates"]
    ]
    for arm_id in prior_exposure._F1_ARMS:
        assert prior_exposure._candidate_table_for_manifest_item(
            item, arm_id
        ) == prior_exposure.candidate_table_for_arm(arm_id, candidates)


def test_current_producer_import_closure_is_exact() -> None:
    assert prior_exposure._discover_current_producer_import_lfp(REPO_ROOT) == (
        prior_exposure._CURRENT_PRODUCER_IMPORT_LFP
    )


def test_historical_replay_child_preloads_ssl_before_network_denial() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", prior_exposure._HISTORICAL_REPLAY_CHILD],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert completed.returncode != 0
    assert "IndexError" in completed.stderr
    assert "SSLSocket" not in completed.stderr


def test_untouched_public_manifest_mutation_is_refused_after_coherent_resign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(
        tmp_path, monkeypatch, include_untouched=True
    )
    source_binding = receipt["source_binding"]
    manifest = source_binding["public_manifest"]
    assert len(manifest["items"]) == 2
    manifest["items"] = [manifest["items"][0]]
    source_binding["manifest_canonical_sha256"] = canonical_sha256(manifest)
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal, match="public source authority"):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_two_touched_items_with_shared_source_form_one_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(
        tmp_path, monkeypatch, two_shared_items=True
    )
    assert (
        verify_aborted_attempt_exposure_receipt(receipt)
        == receipt["aborted_attempt_exposure_receipt_sha256"]
    )
    calls = receipt["call_observations"]
    metadata = {
        call["item_id"]: (
            tuple(call["source_entity_ids"]), call["component_id"]
        )
        for call in calls
    }
    assert set(metadata) == {"incident-item", "incident-item-shared"}
    assert metadata["incident-item"][0] == metadata["incident-item-shared"][0]
    assert metadata["incident-item"][1] == metadata["incident-item-shared"][1]
    assert receipt["counts"] == {
        "attempt_calls": 3,
        "attempt_events": 14,
        "item_runs": 0,
        "spool_calls": 2,
        "attempt_states": {"ACCEPTED": 2, "SENT": 1},
        "spool_complete_calls": 2,
        "spool_absent_calls": 1,
        "items": 2,
        "source_entities": 1,
        "components": 1,
    }


@pytest.mark.parametrize(
    "target", ["producer", "job_command", "job_log"]
)
def test_aborted_attempt_recorded_files_require_positive_size_after_resign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    evidence = receipt["evidence_bindings"]
    if target == "producer":
        authority = evidence["current_producer_authority"]
        authority["files"][0]["size_bytes"] = 0
        authority["closure_root_sha256"] = canonical_sha256(authority["files"])
    else:
        evidence[target]["size_bytes"] = 0
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_aborted_attempt_replay_refuses_foreign_system_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(PriorExposureRefusal, match="manifest identity"):
        _build_synthetic_incident(
            tmp_path,
            monkeypatch,
            qf_prompt_override="Foreign system prompt.",
        )


@pytest.mark.parametrize(
    ("ordinals", "boolean_sequence"),
    (([2], False), ([1, 1], False), ([1, 3], False), ([True], False), ([1], True)),
)
def test_attempt_event_replay_requires_monotone_delivery_ordinals(
    ordinals: list[int], boolean_sequence: bool,
) -> None:
    physical_call_id = "call"
    intent_sha256 = "a" * 64
    request_sha256 = "b" * 64
    events: list[dict[str, object]] = []
    previous = "0" * 64
    details = [
        (
            "PREPARED",
            {
                "intent_sha256": intent_sha256,
                "request_sha256": request_sha256,
            },
        ),
        *[
            (
                "SENT",
                {
                    "delivery_ordinal": ordinal,
                    "same_inference_identity": True,
                },
            )
            for ordinal in ordinals
        ],
    ]
    for sequence, (event_type, detail) in enumerate(details):
        value = {
            "schema_version": prior_exposure._DURABLE_CALL_SCHEMA,
            "sequence": True if boolean_sequence and sequence == 1 else sequence,
            "physical_call_id": physical_call_id,
            "event_type": event_type,
            "detail": detail,
            "previous_event_sha256": previous,
        }
        raw = canonical_json(value).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        events.append(
            {
                "sequence": sequence,
                "physical_call_id": physical_call_id,
                "event_type": event_type,
                "event_bytes": raw,
                "previous_event_sha256": previous,
                "event_sha256": digest,
            }
        )
        previous = digest
    expected = "attempt event chain" if boolean_sequence else "SENT event detail"
    with pytest.raises(PriorExposureRefusal, match=expected):
        prior_exposure._replay_attempt_event_chain(
            events,
            {physical_call_id: "SENT"},
            {
                physical_call_id: {
                    "intent_sha256": intent_sha256,
                    "request_sha256": request_sha256,
                }
            },
        )


def test_snapshot_sqlite_authorizer_denies_protected_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_synthetic_incident(tmp_path, monkeypatch)
    attempt, _attempt_metadata = prior_exposure._open_snapshot_read_only(
        tmp_path / "snapshot" / "attempt.sqlite3",
        expected_columns=prior_exposure._ATTEMPT_COLUMNS,
        authority="attempt",
        label="attempt",
    )
    spool, _spool_metadata = prior_exposure._open_snapshot_read_only(
        tmp_path / "snapshot" / "spool.sqlite3",
        expected_columns=prior_exposure._SPOOL_COLUMNS,
        authority=prior_exposure._HISTORICAL_V8_SCHEMA_AUTHORITIES["spool"],
        label="spool",
    )
    try:
        assert attempt.execute(
            "SELECT physical_call_id FROM call_state LIMIT 1"
        ).fetchone() is not None
        assert spool.execute(
            "SELECT physical_call_id FROM spool_calls LIMIT 1"
        ).fetchone() is not None
        for column in (
            "response_headers",
            "response_body",
            "model_response",
            "call_receipt",
        ):
            with pytest.raises(sqlite3.DatabaseError):
                attempt.execute(f"SELECT {column} FROM call_state LIMIT 1").fetchone()
        with pytest.raises(sqlite3.DatabaseError):
            attempt.execute("SELECT item_run_bytes FROM item_runs LIMIT 1").fetchone()
        for column in ("response_headers", "response_body"):
            with pytest.raises(sqlite3.DatabaseError):
                spool.execute(f"SELECT {column} FROM spool_calls LIMIT 1").fetchone()
    finally:
        attempt.close()
        spool.close()


def test_legacy_static_incident_receipt_is_not_accepted_as_v2_evidence() -> None:
    with pytest.raises(PriorExposureRefusal):
        verify_aborted_attempt_exposure_receipt(_incident_receipt())


def test_aborted_attempt_file_gate_refuses_duplicate_keys(tmp_path: Path) -> None:
    original = INCIDENT_RECEIPT_PATH.read_text(encoding="utf-8")
    duplicated = original.replace(
        '  "status": "ABORTED_QUARANTINED",',
        '  "status": "ABORTED",\n  "status": "ABORTED_QUARANTINED",',
        1,
    )
    assert duplicated != original
    path = tmp_path / "duplicate-key-incident.json"
    path.write_text(duplicated, encoding="utf-8")
    with pytest.raises(R8RunnerRefusal, match="duplicate JSON key"):
        read_stable_json(path, "aborted-attempt exposure receipt")


@pytest.mark.parametrize(
    ("section", "field", "replacement"),
    [
        ("capture_policy", "gold_inputs_accepted", True),
        ("capture_policy", "gold_inputs_accepted", 0),
        ("counts", "attempt_calls", 3),
        ("counts", "attempt_calls", True),
        ("termination", "exit_code", 135.0),
        ("call_observations", 0, None),
        (None, "status", "ABORTED"),
    ],
)
def test_aborted_attempt_tamper_and_resign_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    section: str | None,
    field: str | int,
    replacement: object,
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    target = receipt if section is None else receipt[section]
    if section == "call_observations":
        assert isinstance(target, list) and field == 0
        call = target[0]
        assert isinstance(call, dict)
        call["dataset_row_index"] = 124.0
    else:
        assert isinstance(target, dict) and isinstance(field, str)
        target[field] = replacement
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal):
        verify_aborted_attempt_exposure_receipt(receipt)


@pytest.mark.parametrize(
    "mutation",
    [
        "raw_stage_path",
        "raw_capture_host",
        "database_identity_hash",
        "hswm_f1_sqlite_schema.py",
        "hswm_function_network.py",
        "hswm_function_registry.py",
        "prom_f1_function_network.py",
        "prom9_protocol.py",
        "prom9_prepare_2wiki_f1.py",
    ],
)
def test_aborted_attempt_public_identity_and_producer_inventory_are_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    if mutation == "raw_stage_path":
        identity = receipt["run_identity"]
        assert isinstance(identity, dict)
        identity["stage_path"] = "/private/incident"
    elif mutation == "raw_capture_host":
        identity = receipt["run_identity"]
        assert isinstance(identity, dict)
        identity["capture_host"] = "private-host"
    elif mutation == "database_identity_hash":
        databases = receipt["database_snapshots"]
        assert isinstance(databases, dict)
        attempt = databases["attempt"]
        assert isinstance(attempt, dict)
        attempt["canonical_schema_sha256"] = "not-a-sha256"
    else:
        evidence = receipt["evidence_bindings"]
        assert isinstance(evidence, dict)
        authority = evidence["current_producer_authority"]
        assert isinstance(authority, dict)
        files = authority["files"]
        assert isinstance(files, list)
        authority["files"] = [
            entry
            for entry in files
            if not str(entry["relative_path"]).endswith(mutation)
        ]
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_aborted_attempt_re_signed_different_signal_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    termination = receipt["termination"]
    assert isinstance(termination, dict)
    termination.update({"signal": "SIGKILL", "signal_number": 9, "exit_code": 137})
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal, match="termination"):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_aborted_attempt_aggregate_root_mismatch_is_refused_after_resign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    aggregate = receipt["aggregate"]
    assert isinstance(aggregate, dict)
    aggregate["source_entity_root_sha256"] = "0" * 64
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal, match="aggregate root"):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_aborted_attempt_coherent_exposure_undercount_is_refused_by_public_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    replacement_component = "f" * 64
    calls = receipt["call_observations"]
    item_runs = receipt["item_run_observations"]
    assert isinstance(calls, list) and isinstance(item_runs, list)
    for observation in [*calls, *item_runs]:
        assert isinstance(observation, dict)
        observation["source_entity_ids"] = []
        observation["component_id"] = replacement_component
    aggregate = receipt["aggregate"]
    counts = receipt["counts"]
    source_binding = receipt["source_binding"]
    assert isinstance(aggregate, dict)
    assert isinstance(counts, dict)
    assert isinstance(source_binding, dict)
    aggregate["prior_source_entity_ids"] = []
    aggregate["source_entity_root_sha256"] = canonical_sha256([])
    aggregate["prior_component_ids"] = [replacement_component]
    aggregate["component_root_sha256"] = canonical_sha256(
        [replacement_component]
    )
    counts["source_entities"] = 0
    counts["components"] = 1
    item_id = str(calls[0]["item_id"])
    source_binding["touched_metadata_root_sha256"] = canonical_sha256(
        [
            {
                "item_id": item_id,
                "dataset_row_index": calls[0]["dataset_row_index"],
                "question_sha256": calls[0]["question_sha256"],
                "source_entity_ids": [],
                "component_id": replacement_component,
            }
        ]
    )
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal, match="public source authority"):
        verify_aborted_attempt_exposure_receipt(receipt)


@pytest.mark.parametrize("mutation", ["contract", "prefix", "spool_metadata"])
def test_aborted_attempt_call_semantics_survive_receipt_resigning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    receipt = _build_synthetic_incident(tmp_path, monkeypatch)
    calls = receipt["call_observations"]
    assert isinstance(calls, list) and len(calls) == 2
    first = calls[0]
    second = calls[1]
    assert isinstance(first, dict) and isinstance(second, dict)
    if mutation == "contract":
        first["function_id"] = "AF_ANSWER_SYNTHESIZER"
        expected = "call contract"
    elif mutation == "prefix":
        second.update(
            {
                "call_index": 3,
                "function_id": "AF_ANSWER_SYNTHESIZER",
                "input_type": "AnswerContextV1",
                "output_type": "AnswerEnvelopeV1",
            }
        )
        expected = "call sequence"
    else:
        first["spool_snapshot_state"] = "DISPATCHING"
        expected = "spool row exposes response metadata"
    _resign_incident(receipt)
    with pytest.raises(PriorExposureRefusal, match=expected):
        verify_aborted_attempt_exposure_receipt(receipt)


def test_merge_exposure_boundaries_returns_sorted_canonical_union(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    incident = _build_synthetic_incident(tmp_path, monkeypatch)
    incident_aggregate = incident["aggregate"]
    assert isinstance(incident_aggregate, dict)
    incident_items = incident_aggregate["prior_item_ids"]
    incident_sources = incident_aggregate["prior_source_entity_ids"]
    incident_components = incident_aggregate["prior_component_ids"]
    assert isinstance(incident_items, list)
    assert isinstance(incident_sources, list)
    assert isinstance(incident_components, list)
    prior = _minimal_prior(
        item_ids=sorted(["000-prior-item", incident_items[0]]),
        source_entity_ids=sorted(["0" * 64, incident_sources[0]]),
        component_ids=sorted(["0" * 64, incident_components[0]]),
    )

    merged = merge_exposure_boundaries(prior, incident)
    expected_items = sorted({"000-prior-item", *incident_items})
    expected_sources = sorted({"0" * 64, *incident_sources})
    expected_components = sorted({"0" * 64, *incident_components})
    assert merged == {
        "prior_exposure_receipt_sha256": prior[
            "prior_exposure_receipt_sha256"
        ],
        "aborted_attempt_exposure_receipt_sha256": incident[
            "aborted_attempt_exposure_receipt_sha256"
        ],
        "item_ids": expected_items,
        "source_entity_ids": expected_sources,
        "component_ids": expected_components,
        "item_root_sha256": canonical_sha256(expected_items),
        "source_entity_root_sha256": canonical_sha256(expected_sources),
        "component_root_sha256": canonical_sha256(expected_components),
    }


def test_forbidden_union_requires_exact_lock_lists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    incident = _build_synthetic_incident(tmp_path, monkeypatch)
    incident_aggregate = incident["aggregate"]
    prior = _minimal_prior(
        item_ids=["prior-item"],
        source_entity_ids=["0" * 64],
        component_ids=["1" * 64],
    )
    merged = merge_exposure_boundaries(prior, incident)
    lock = {
        "prior_exposure_receipt_sha256": merged[
            "prior_exposure_receipt_sha256"
        ],
        "aborted_attempt_exposure_receipt_sha256": merged[
            "aborted_attempt_exposure_receipt_sha256"
        ],
        "forbidden_prior_item_ids": merged["item_ids"],
        "forbidden_prior_source_entity_ids": merged["source_entity_ids"],
        "forbidden_prior_component_ids": merged["component_ids"],
    }
    assert verify_forbidden_exposure_union(prior, incident, lock) == merged
    tampered = copy.deepcopy(lock)
    tampered["forbidden_prior_item_ids"] = ["prior-item"]
    with pytest.raises(PriorExposureRefusal, match="forbidden exposure union"):
        verify_forbidden_exposure_union(prior, incident, tampered)
    assert incident_aggregate["prior_item_ids"] not in tampered.values()
