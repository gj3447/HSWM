"""Bounded, non-admitting execution adapters for adaptive cell manifests.

The caller is responsible for admitting a manifest cell before calling this
module.  This helper neither discovers commands nor turns an LLM response into
success, credit, or a canonical revision.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from typing import Any, Mapping

from .openai import OpenAICompatibleCellPort, OpenAICompatibleConfig, UnknownModelOutcome
from .runtime import CellPort, InvokeCellEffect, canonical_json_bytes, make_packet


MAX_INPUT_BYTES = 1_000_000
MAX_TIMEOUT_SECONDS = 3_600.0


def _bounded_text(raw: bytes, limit: int) -> tuple[str, bool]:
    captured = raw[:limit]
    return captured.decode("utf-8", errors="replace"), len(raw) > limit


def _result(status: str, success: bool | None, started: float, raw: bytes,
            output_limit: int, **metadata: Any) -> dict[str, Any]:
    text, truncated = _bounded_text(raw, output_limit)
    output_bytes_seen = metadata.pop("output_bytes_seen", len(raw))
    return {
        "status": status,
        "success": success,
        "duration_seconds": time.monotonic() - started,
        "output": text,
        "output_digest": sha256(text.encode("utf-8")).hexdigest(),
        "metadata": {**metadata, "output_bytes_seen": output_bytes_seen,
                     "output_truncated": truncated or output_bytes_seen > output_limit},
    }


def _require_text(cell: Mapping[str, Any], name: str) -> str:
    value = cell.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"cell.{name} must be a non-empty string")
    return value


def _packet_effect(cell: Mapping[str, Any], payload: dict[str, Any]) -> InvokeCellEffect:
    cell_id = _require_text(cell, "cell_id")
    input_type = _require_text(cell, "input_type")
    output_type = _require_text(cell, "output_type")
    payload_bytes = canonical_json_bytes(payload)
    payload_digest = sha256(payload_bytes).hexdigest()
    packet = make_packet(
        packet_id=f"adaptive-input-{payload_digest[:20]}", packet_type=input_type,
        payload=payload, provenance={"adapter": "adaptive-executor/v1", "cell_id": cell_id},
    )
    return InvokeCellEffect(
        activation_id=f"adaptive-{cell_id}-{payload_digest[:20]}", cell_id=cell_id,
        input=packet, expected_output_type=output_type,
    )


def _command_argv(cell: Mapping[str, Any]) -> list[str]:
    argv = cell.get("argv")
    if (not isinstance(argv, list) or not argv or
            any(not isinstance(item, str) or not item or item == "{input}" for item in argv)):
        raise ValueError("command cell.argv must be a non-empty literal string list")
    return list(argv)


def _command_outcome(cell: Mapping[str, Any]) -> bool:
    outcome = cell.get("outcome")
    if outcome is None:
        return False
    if outcome != "exit_code":
        raise ValueError("command cell.outcome must be exit_code when supplied")
    return True


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    # The leader can already have exited while a descendant still owns stdout.
    # Its process group remains the boundary that must be killed on timeout.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_command(argv: list[str], input_bytes: bytes, workspace: Path, timeout: float,
                 output_limit: int, started: float, exit_code_outcome: bool) -> dict[str, Any]:
    try:
        process = subprocess.Popen(
            argv, cwd=workspace, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    except OSError as error:
        return _result("FAILED", None, started, b"", output_limit,
                       kind="command", error_type=type(error).__name__)

    assert process.stdin is not None and process.stdout is not None
    selector = selectors.DefaultSelector()
    os.set_blocking(process.stdin.fileno(), False)
    os.set_blocking(process.stdout.fileno(), False)
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stdin, selectors.EVENT_WRITE)
    written, chunks, total = 0, [], 0
    deadline = started + timeout
    timed_out = False
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                timed_out = True
                _terminate_group(process)
                for key in tuple(selector.get_map().values()):
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                break
            for key, mask in selector.select(max(0.0, min(0.05, deadline - time.monotonic()))):
                if key.fileobj is process.stdin and mask & selectors.EVENT_WRITE:
                    try:
                        count = os.write(process.stdin.fileno(), input_bytes[written:])
                    except BrokenPipeError:
                        count = 0
                        written = len(input_bytes)
                    else:
                        written += count
                    if written >= len(input_bytes):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                elif key.fileobj is process.stdout and mask & selectors.EVENT_READ:
                    try:
                        data = os.read(process.stdout.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        selector.unregister(process.stdout)
                    else:
                        # Continue draining after the cap so a noisy command cannot deadlock.
                        total += len(data)
                        if sum(len(chunk) for chunk in chunks) < output_limit:
                            remaining = output_limit - sum(len(chunk) for chunk in chunks)
                            chunks.append(data[:remaining])
            if process.poll() is not None and not selector.get_map():
                break
        try:
            returncode = process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_group(process)
            returncode = process.wait(timeout=1)
    finally:
        selector.close()
        if process.poll() is None:
            _terminate_group(process)
        if not process.stdin.closed:
            process.stdin.close()
        if not process.stdout.closed:
            process.stdout.close()
    raw = b"".join(chunks)
    if timed_out:
        return _result("UNKNOWN", None, started, raw, output_limit, kind="command",
                       reason="timeout", output_bytes_seen=total)
    return _result("SUCCEEDED" if returncode == 0 else "FAILED",
                   returncode == 0 if exit_code_outcome else None,
                   started, raw, output_limit, kind="command", returncode=returncode,
                   output_bytes_seen=total)


def _llm_port(cell: Mapping[str, Any], timeout: float) -> CellPort:
    base_url = _require_text(cell, "base_url")
    model = _require_text(cell, "model")
    api_key_env = cell.get("api_key_env")
    if api_key_env is not None and (not isinstance(api_key_env, str) or not api_key_env):
        raise ValueError("cell.api_key_env must be a non-empty string when supplied")
    max_tokens = cell.get("max_tokens", 256)
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("cell.max_tokens must be a positive integer")
    return OpenAICompatibleCellPort(OpenAICompatibleConfig(
        base_url=base_url, model=model, api_key=os.environ.get(api_key_env) if api_key_env else None,
        timeout_seconds=timeout, max_tokens=max_tokens,
    ))


def execute(cell: dict[str, Any], payload: dict[str, Any], *, workspace: Path,
            timeout: float, output_limit: int, port: CellPort | None = None) -> dict[str, Any]:
    """Execute one already-allowlisted cell and return a bounded local record.

    Command payloads are canonical JSON on stdin.  LLM responses deliberately
    return ``success=None``: a model completion is not an outcome or reward.
    """
    started = time.monotonic()
    if not isinstance(cell, dict) or not isinstance(payload, dict):
        raise ValueError("cell and payload must be objects")
    if ((type(timeout) is int and not 0 < timeout <= MAX_TIMEOUT_SECONDS) or
            (type(timeout) is float and (not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT_SECONDS)) or
            type(timeout) not in (int, float)):
        raise ValueError("timeout must be finite and between 0 and 3600 seconds")
    if type(output_limit) is not int or not 1 <= output_limit <= 2_000_000:
        raise ValueError("output_limit must be between 1 and 2000000")
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    kind = cell.get("kind")
    # Callers must include a per-episode/call identifier in payload when the same
    # cell may receive identical content more than once; activation IDs hash this
    # typed payload and are intentionally deterministic for replay.
    effect = _packet_effect(cell, payload)
    if kind == "command":
        input_bytes = canonical_json_bytes(payload)
        if len(input_bytes) > MAX_INPUT_BYTES:
            raise ValueError("payload exceeds command input bound")
        return _run_command(_command_argv(cell), input_bytes, workspace, float(timeout),
                            output_limit, started, _command_outcome(cell))
    if kind != "llm":
        raise ValueError("cell.kind must be command or llm")
    active_port = port if port is not None else _llm_port(cell, float(timeout))
    try:
        packet = active_port.invoke(effect)
        if packet.packet_type != effect.expected_output_type:
            raise ValueError("LLM port returned an unexpected packet type")
        if sha256(canonical_json_bytes(packet.payload)).hexdigest() != packet.payload_sha256:
            raise ValueError("LLM port returned a packet with a bad payload digest")
        raw = canonical_json_bytes(packet.payload)
        return _result("SUCCEEDED", None, started, raw, output_limit, kind="llm",
                       packet_type=packet.packet_type, output_payload_sha256=packet.payload_sha256)
    except UnknownModelOutcome as error:
        return _result("UNKNOWN", None, started, b"", output_limit, kind="llm",
                       error_type=type(error).__name__)
    except Exception as error:
        return _result("FAILED", None, started, b"", output_limit, kind="llm",
                       error_type=type(error).__name__)
