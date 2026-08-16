"""Bounded one-activation probe for the durable HSWM cell runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .openai import (
    FixtureCellPort,
    OpenAICompatibleCellPort,
    OpenAICompatibleConfig,
)
from .runtime import CellContract, RequestCellStep, make_packet
from .store import CommitReceipt, OutboxStatus, SqliteCellRuntime


def run_probe(
    *,
    mode: str,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 60.0,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if mode not in {"fixture", "live"}:
        raise ValueError("mode must be fixture or live")
    if mode == "live" and (not base_url or not model):
        raise ValueError("live mode requires base_url and model")
    if mode == "live" and db_path is None:
        raise ValueError("live mode requires a persistent db_path for reconciliation")
    registry = {
        "cell-probe": CellContract(
            cell_id="cell-probe",
            input_type="prompt/v1",
            output_type="text/v1",
        )
    }
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if db_path is None:
        temporary = tempfile.TemporaryDirectory(prefix="hswm-cell-probe-")
        resolved_db_path = Path(temporary.name) / "runtime.sqlite3"
    else:
        resolved_db_path = db_path
    try:
        store = SqliteCellRuntime(resolved_db_path, registry)
        store.create_stream("probe-stream", initial_budget=1)
        input_packet = make_packet(
            packet_id="probe-input-1",
            packet_type="prompt/v1",
            payload={
                "messages": [
                    {
                        "role": "user",
                        "content": "Return exactly the token HSWM_CELL_OK and nothing else.",
                    }
                ]
            },
            provenance={"probe": "hswm-cellular-durable-runtime/v2"},
        )
        request = RequestCellStep(
            expected_version=0,
            activation_id="probe-activation-1",
            cell_id="cell-probe",
            input=input_packet,
        )
        request_receipt = store.submit("probe-stream", request)
        if not isinstance(request_receipt, CommitReceipt):
            raise RuntimeError(f"probe request rejected: {request_receipt}")
        if mode == "fixture":
            port = FixtureCellPort(response_text="HSWM_CELL_OK")
        else:
            port = OpenAICompatibleCellPort(
                OpenAICompatibleConfig(
                    base_url=base_url or "",
                    model=model or "",
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    max_tokens=16,
                    temperature=0.0,
                )
            )
        dispatch = store.dispatch_one(port=port, claim_token="probe-claim-1")
        if dispatch is None:
            raise RuntimeError("probe produced no dispatch")
        state = store.load_state("probe-stream")
        outbox = store.list_outbox()
        text = None
        if state.completed:
            effect = outbox[0]
            text = effect.output_payload_sha256
        return {
            "schema": "hswm-cellular-live-probe/v1",
            "mode": mode,
            "status": "PASS" if dispatch.status is OutboxStatus.SUCCEEDED else dispatch.status.value,
            "model_probe": "LIVE_PASS" if mode == "live" and dispatch.status is OutboxStatus.SUCCEEDED else "FIXTURE_PASS" if mode == "fixture" and dispatch.status is OutboxStatus.SUCCEEDED else "FAILED",
            "port_calls": port.calls,
            "stream_version": state.version,
            "remaining_budget": state.remaining_budget,
            "pending_count": len(state.pending),
            "completed_count": len(state.completed),
            "outbox_status": outbox[0].status.value,
            "output_payload_sha256": text,
            "request_event_sequences": list(request_receipt.event_sequences),
            "completion_event_sequences": list(dispatch.completion.event_sequences) if dispatch.completion else [],
            "error": dispatch.error,
            "reconciliation_db": str(resolved_db_path) if dispatch.status is OutboxStatus.UNKNOWN_OUTCOME else None,
            "endpoint_class": "local-or-private-openai-compatible" if mode == "live" else "deterministic-fixture",
            "scientific_status": "UNJUDGED",
        }
    finally:
        if temporary is not None:
            temporary.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key-env")
    parser.add_argument("--db-path", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    try:
        result = run_probe(
            mode=args.mode,
            base_url=args.base_url,
            model=args.model,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
            db_path=args.db_path,
        )
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error": f"{type(error).__name__}: {error}"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
