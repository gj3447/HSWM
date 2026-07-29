"""Target-deployment probes for the F1 durable transport (contract steps 5-6).

Runs ON the deployment host against the ACTUAL upstream (vLLM). Closes the two
G0 PENDING items that the local fixture battery cannot close:

1. ``disconnect``        — post-inference / pre-client-commit disconnect
   falsifier in the deployed topology: an in-process spool HTTP server with
   ``disconnect_after_commit_once=True`` fronting the real upstream. Acceptance:
   exactly one upstream dispatch (spool COMPLETE == 1 with a DELIVERY_AMBIGUOUS
   re-delivery in the client event chain), client ACCEPTED == 1, spool/client
   binding roots equal, and a follow-up idempotent raw PUT that returns
   ``X-HSWM-Spool-Replayed: true`` with a byte-identical body SHA-256.
2. ``crash-complete``    — target-filesystem crash durability: the spool CLI as
   a real subprocess, one fully accepted call, SIGKILL, offline reopen (the
   committed row and bytes must survive on disk), restart, byte-identical
   replay with no new dispatch.
3. ``crash-dispatching`` — SIGKILL the spool subprocess while a real upstream
   inference is DISPATCHING; after restart the row must be UNKNOWN, never
   redispatched, and the client must terminate in AMBIGUOUS_ABORT.

Boundary (stated honestly in the receipt): SIGKILL is OS process-crash evidence
on the target filesystem; electrical power loss is not exercised.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urllib_request

from prom_search_hswm.hswm_call_receipt import invoke_function
from prom_search_hswm.hswm_f1_durable_transport import (
    AmbiguousModelOutcome,
    DurableSpoolJSONPort,
    SQLiteF1CallLedger,
)
from prom_search_hswm.hswm_function_registry import FunctionSpecV1
from prom_search_hswm.hswm_result_spool import (
    SPOOL_ROUTE_PREFIX,
    ResultSpoolHTTPServer,
    ResultSpoolService,
    SQLiteResultSpool,
    load_model_deployment_binding,
)
from prom_search_hswm.hswm_typed_ports import canonical_sha256

TOKEN_ENV = "HSWM_PROBE_SPOOL_TOKEN"
RECEIPT_SCHEMA = "hswm-f1-target-deployment-probe/v2"


class ProbeFailure(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe_function(model: str, model_revision: str) -> FunctionSpecV1:
    prompt = "Compile one typed query plan."
    return FunctionSpecV1(
        function_id="QF_QUERY_COMPILER",
        model=model,
        model_revision=model_revision,
        input_type="QueryEnvelopeV1",
        output_type="QueryPlanV1",
        prompt=prompt,
        prompt_sha256=canonical_sha256({"prompt": prompt}),
    )


def _probe_input(request_id: str, query_text: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "query_text": query_text,
        "allowed_evidence_types": ["text"],
        "budget": {
            "max_candidates": 1,
            "max_evidence_items": 1,
            "max_input_tokens": 4096,
            "max_output_tokens": 2048,
        },
        "parity_filler": "",
    }


def _require_token() -> str:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise ProbeFailure(f"missing probe spool token environment: {TOKEN_ENV}")
    return token


def _client_events(ledger_path: Path) -> list[str]:
    connection = sqlite3.connect(ledger_path)
    try:
        rows = connection.execute(
            "SELECT event_type FROM attempt_events ORDER BY sequence"
        ).fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]


def _client_call_row(ledger_path: Path) -> dict[str, object]:
    connection = sqlite3.connect(ledger_path)
    try:
        row = connection.execute(
            "SELECT physical_call_id, intent_sha256, request_bytes, response_sha256, status"
            " FROM call_state LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ProbeFailure("client ledger has no call_state row")
    return {
        "physical_call_id": row[0],
        "intent_sha256": row[1],
        "request_bytes": row[2],
        "response_sha256": row[3],
        "status": row[4],
    }


def _spool_status_rows(spool_db: Path) -> dict[str, int]:
    connection = sqlite3.connect(spool_db)
    try:
        rows = connection.execute(
            "SELECT status, COUNT(*) FROM spool_calls GROUP BY status"
        ).fetchall()
    finally:
        connection.close()
    return {row[0]: row[1] for row in rows}


def _raw_idempotent_put(
    endpoint: str, call_row: dict[str, object], model_revision: str, token: str
) -> dict[str, object]:
    route = f"{endpoint}{SPOOL_ROUTE_PREFIX}{call_row['physical_call_id']}"
    request = urllib_request.Request(
        route,
        data=bytes(call_row["request_bytes"]),
        headers={
            "Content-Type": "application/json",
            "X-HSWM-Intent-SHA256": str(call_row["intent_sha256"]),
            "X-HSWM-Model-Revision": model_revision,
            "Authorization": f"Bearer {token}",
        },
        method="PUT",
    )
    with urllib_request.urlopen(request, timeout=180.0) as response:
        body = response.read()
        headers = {key.casefold(): value for key, value in response.headers.items()}
    return {
        "status": 200,
        "replayed": headers.get("x-hswm-spool-replayed"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "attested_response_sha256": headers.get("x-hswm-spool-response-sha256"),
    }


def probe_disconnect(
    workdir: Path,
    upstream: str,
    model: str,
    model_revision: str,
    deployment_receipt_path: Path,
    timeout: float,
) -> dict[str, object]:
    token = _require_token()
    spool_db = workdir / "disconnect.spool.sqlite3"
    client_db = workdir / "disconnect.client.sqlite3"
    started = _utc_now()
    deployment_binding = load_model_deployment_binding(
        deployment_receipt_path,
        upstream_endpoint=upstream,
        served_model=model,
        model_revision=model_revision,
        verify_live_process=True,
    )
    spool = SQLiteResultSpool(spool_db)
    service = ResultSpoolService(
        spool,
        upstream_endpoint=deployment_binding.upstream_endpoint,
        deployment_binding=deployment_binding,
        deployment_receipt_path=deployment_receipt_path,
        client_token=token,
        timeout_seconds=timeout,
    )
    server = ResultSpoolHTTPServer(
        ("127.0.0.1", 0), service, disconnect_after_commit_once=True
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    run_id = f"f1-target-probe-disconnect-{int(time.time())}"
    try:
        with DurableSpoolJSONPort(
            endpoint,
            client_db,
            spool_token_env=TOKEN_ENV,
            timeout_seconds=timeout,
            max_delivery_attempts=4,
            delivery_backoff_s=(1.0,),
        ) as port:
            output, receipt = invoke_function(
                run_id=run_id,
                arm_id="probe",
                item_id="probe-item-1",
                call_index=1,
                function=_probe_function(model, model_revision),
                input_payload=_probe_input(
                    "probe-disconnect-1", "What is the capital of France?"
                ),
                max_output_tokens=512,
                model_port=port,
            )
            client_audit = port.audit()
        spool_audit = spool.audit()
        replay_check = _raw_idempotent_put(
            endpoint, _client_call_row(client_db), model_revision, token
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        spool.close()
    events = _client_events(client_db)
    call_row = _client_call_row(client_db)
    checks = {
        "client_accepted_exactly_one": client_audit["status_counts"] == {"ACCEPTED": 1},
        "spool_complete_exactly_one": spool_audit["status_counts"] == {"COMPLETE": 1},
        "binding_roots_equal": (
            spool_audit["completed_root_sha256"]
            == client_audit["spool_binding_root_sha256"]
        ),
        "delivery_ambiguous_then_redelivered": (
            events.count("SENT") >= 2 and "DELIVERY_AMBIGUOUS" in events
        ),
        "raw_replay_flag_true": replay_check["replayed"] == "true",
        "raw_replay_body_sha_matches_ledger": (
            replay_check["body_sha256"] == call_row["response_sha256"]
        ),
        "output_is_typed_object": isinstance(output, dict),
        "receipt_minted": receipt is not None,
    }
    return {
        "probe": "disconnect_real_upstream",
        "started_at": started,
        "finished_at": _utc_now(),
        "run_id": run_id,
        "spool_status_counts": spool_audit["status_counts"],
        "client_status_counts": client_audit["status_counts"],
        "client_event_chain": events,
        "response_sha256": call_row["response_sha256"],
        "raw_replay": replay_check,
        "checks": checks,
        "pass": all(checks.values()),
    }


def _spawn_spool_cli(
    repo_root: Path,
    spool_db: Path,
    upstream: str,
    model: str,
    model_revision: str,
    deployment_receipt_path: Path,
    port_num: int,
    token: str,
    timeout: float,
) -> subprocess.Popen[bytes]:
    env = dict(os.environ)
    env[TOKEN_ENV] = token
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "prom_search_hswm.hswm_result_spool",
            "--db",
            str(spool_db),
            "--upstream",
            upstream,
            "--served-model",
            model,
            "--model-revision",
            model_revision,
            "--model-deployment-receipt",
            str(deployment_receipt_path),
            "--listen-host",
            "127.0.0.1",
            "--listen-port",
            str(port_num),
            "--client-token-env",
            TOKEN_ENV,
            "--timeout-seconds",
            str(timeout),
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ProbeFailure("spool CLI subprocess exited before binding")
        try:
            with socket.create_connection(("127.0.0.1", port_num), timeout=0.25):
                return process
        except OSError:
            time.sleep(0.1)
    process.kill()
    raise ProbeFailure("spool CLI subprocess never started listening")


def probe_crash_complete(
    workdir: Path,
    repo_root: Path,
    upstream: str,
    model: str,
    model_revision: str,
    deployment_receipt_path: Path,
    port_num: int,
    timeout: float,
) -> dict[str, object]:
    token = _require_token()
    spool_db = workdir / "crash_complete.spool.sqlite3"
    client_db = workdir / "crash_complete.client.sqlite3"
    started = _utc_now()
    endpoint = f"http://127.0.0.1:{port_num}"
    run_id = f"f1-target-probe-crash-complete-{int(time.time())}"
    process = _spawn_spool_cli(
        repo_root,
        spool_db,
        upstream,
        model,
        model_revision,
        deployment_receipt_path,
        port_num,
        token,
        timeout,
    )
    try:
        with DurableSpoolJSONPort(
            endpoint,
            client_db,
            spool_token_env=TOKEN_ENV,
            timeout_seconds=timeout,
            max_delivery_attempts=4,
            delivery_backoff_s=(1.0,),
        ) as port:
            invoke_function(
                run_id=run_id,
                arm_id="probe",
                item_id="probe-item-1",
                call_index=1,
                function=_probe_function(model, model_revision),
                input_payload=_probe_input(
                    "probe-crash-complete-1", "Name one primary color."
                ),
                max_output_tokens=512,
                model_port=port,
            )
            client_audit = port.audit()
    finally:
        kill_time = _utc_now()
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=10)
    call_row = _client_call_row(client_db)
    offline_spool = SQLiteResultSpool(spool_db)
    try:
        offline_audit = offline_spool.audit()
    finally:
        offline_spool.close()
    restarted = _spawn_spool_cli(
        repo_root,
        spool_db,
        upstream,
        model,
        model_revision,
        deployment_receipt_path,
        port_num,
        token,
        timeout,
    )
    try:
        replay_check = _raw_idempotent_put(endpoint, call_row, model_revision, token)
        post_replay_status = _spool_status_rows(spool_db)
    finally:
        restarted.terminate()
        restarted.wait(timeout=10)
    checks = {
        "client_accepted_exactly_one": client_audit["status_counts"] == {"ACCEPTED": 1},
        "committed_row_survives_sigkill": offline_audit["status_counts"]
        == {"COMPLETE": 1},
        "raw_replay_flag_true_after_restart": replay_check["replayed"] == "true",
        "raw_replay_body_sha_matches_ledger": (
            replay_check["body_sha256"] == call_row["response_sha256"]
        ),
        "no_new_dispatch_after_restart": post_replay_status == {"COMPLETE": 1},
    }
    return {
        "probe": "crash_complete_target_filesystem",
        "started_at": started,
        "finished_at": _utc_now(),
        "run_id": run_id,
        "sigkill_at": kill_time,
        "offline_status_counts_after_sigkill": offline_audit["status_counts"],
        "post_replay_status_counts": post_replay_status,
        "response_sha256": call_row["response_sha256"],
        "raw_replay": replay_check,
        "checks": checks,
        "pass": all(checks.values()),
    }


def probe_crash_dispatching(
    workdir: Path,
    repo_root: Path,
    upstream: str,
    model: str,
    model_revision: str,
    deployment_receipt_path: Path,
    port_num: int,
    timeout: float,
) -> dict[str, object]:
    token = _require_token()
    spool_db = workdir / "crash_dispatching.spool.sqlite3"
    client_db = workdir / "crash_dispatching.client.sqlite3"
    started = _utc_now()
    endpoint = f"http://127.0.0.1:{port_num}"
    run_id = f"f1-target-probe-crash-dispatching-{int(time.time())}"
    process = _spawn_spool_cli(
        repo_root,
        spool_db,
        upstream,
        model,
        model_revision,
        deployment_receipt_path,
        port_num,
        token,
        timeout,
    )
    outcome: dict[str, object] = {}

    def client_worker() -> None:
        try:
            with DurableSpoolJSONPort(
                endpoint,
                client_db,
                spool_token_env=TOKEN_ENV,
                timeout_seconds=timeout,
                max_delivery_attempts=6,
                delivery_backoff_s=(1.0,),
            ) as port:
                invoke_function(
                    run_id=run_id,
                    arm_id="probe",
                    item_id="probe-item-1",
                    call_index=1,
                    function=_probe_function(model, model_revision),
                    input_payload=_probe_input(
                        "probe-crash-dispatching-1",
                        "List, in exhaustive detail, every constraint that a typed"
                        " query plan for a multi-hop question about the history of"
                        " European capital cities should satisfy.",
                    ),
                    max_output_tokens=2048,
                    model_port=port,
                )
            outcome["result"] = "ACCEPTED"
        except AmbiguousModelOutcome as error:
            outcome["result"] = "AMBIGUOUS_ABORT"
            outcome["error"] = str(error)
        except Exception as error:  # noqa: BLE001 - recorded in receipt
            outcome["result"] = type(error).__name__
            outcome["error"] = str(error)

    worker = threading.Thread(target=client_worker, daemon=True)
    worker.start()
    saw_dispatching = False
    kill_time = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if _spool_status_rows(spool_db).get("DISPATCHING"):
                saw_dispatching = True
                process.send_signal(signal.SIGKILL)
                process.wait(timeout=10)
                kill_time = _utc_now()
                break
        except sqlite3.OperationalError:
            pass
        time.sleep(0.01)
    if not saw_dispatching:
        process.kill()
        process.wait(timeout=10)
        raise ProbeFailure(
            "never observed DISPATCHING before deadline; rerun with a longer prompt"
        )
    time.sleep(2.0)
    restarted = _spawn_spool_cli(
        repo_root,
        spool_db,
        upstream,
        model,
        model_revision,
        deployment_receipt_path,
        port_num,
        token,
        timeout,
    )
    try:
        worker.join(timeout=timeout + 60)
        final_status = _spool_status_rows(spool_db)
    finally:
        restarted.terminate()
        restarted.wait(timeout=10)
    offline_spool = SQLiteResultSpool(spool_db)
    try:
        offline_audit = offline_spool.audit()
    finally:
        offline_spool.close()
    checks = {
        "observed_dispatching_before_kill": saw_dispatching,
        "row_recovered_as_unknown": offline_audit["status_counts"] == {"UNKNOWN": 1},
        "client_ambiguous_abort": outcome.get("result") == "AMBIGUOUS_ABORT",
        "never_redispatched": final_status.get("COMPLETE", 0) == 0,
        "worker_finished": not worker.is_alive(),
    }
    return {
        "probe": "crash_dispatching_never_redispatch",
        "started_at": started,
        "finished_at": _utc_now(),
        "run_id": run_id,
        "sigkill_at": kill_time,
        "client_outcome": outcome,
        "spool_status_counts_after_recovery": offline_audit["status_counts"],
        "checks": checks,
        "pass": all(checks.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--model-deployment-receipt", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--crash-complete-port", type=int, default=8012)
    parser.add_argument("--crash-dispatching-port", type=int, default=8013)
    parser.add_argument(
        "--probe",
        choices=["disconnect", "crash-complete", "crash-dispatching", "all"],
        default="all",
    )
    args = parser.parse_args(argv)
    try:
        deployment_binding = load_model_deployment_binding(
            args.model_deployment_receipt,
            upstream_endpoint=args.upstream,
            served_model=args.model,
            model_revision=args.model_revision,
            verify_live_process=True,
        )
    except Exception as error:
        parser.error(f"model deployment attestation failed: {type(error).__name__}")
    args.workdir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    if args.probe in {"disconnect", "all"}:
        results.append(
            probe_disconnect(
                args.workdir,
                args.upstream,
                args.model,
                args.model_revision,
                args.model_deployment_receipt,
                args.timeout_seconds,
            )
        )
    if args.probe in {"crash-complete", "all"}:
        results.append(
            probe_crash_complete(
                args.workdir,
                args.repo_root,
                args.upstream,
                args.model,
                args.model_revision,
                args.model_deployment_receipt,
                args.crash_complete_port,
                args.timeout_seconds,
            )
        )
    if args.probe in {"crash-dispatching", "all"}:
        results.append(
            probe_crash_dispatching(
                args.workdir,
                args.repo_root,
                args.upstream,
                args.model,
                args.model_revision,
                args.model_deployment_receipt,
                args.crash_dispatching_port,
                args.timeout_seconds,
            )
        )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "generated_at": _utc_now(),
        "host": {
            "hostname": socket.gethostname(),
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "config": {
            "upstream": args.upstream,
            "model": args.model,
            "model_revision": args.model_revision,
            "deployment_receipt_sha256": (
                deployment_binding.deployment_receipt_sha256
            ),
            "deployment_id": deployment_binding.deployment_id,
            "workdir": str(args.workdir),
            "timeout_seconds": args.timeout_seconds,
        },
        "boundary": (
            "SIGKILL is OS process-crash evidence on the target filesystem;"
            " electrical power loss is not exercised."
        ),
        "probes": results,
        "overall_pass": bool(results) and all(entry["pass"] for entry in results),
    }
    receipt_path = args.workdir / "F1_TARGET_DEPLOYMENT_PROBE_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "receipt": str(receipt_path),
        "overall_pass": receipt["overall_pass"],
        "probes": {entry["probe"]: entry["pass"] for entry in results},
    }, indent=2))
    return 0 if receipt["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
