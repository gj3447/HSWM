"""Thin development-only bridge to the native F3 PostgreSQL caller.

The child process owns request identity, persistence, budget admission and HTTP.
This module only maps the historical chat seam and validates its process reply.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

PROCESS = Path(__file__).resolve().parents[1] / "effect-runtime/dist/native-f3-development-process.js"
MAX_BYTES = 1_048_576
MAX_SAFE_INTEGER = 9_007_199_254_740_991


class NativeF3BridgeError(RuntimeError):
    """A bounded terminal or an uncertain process outcome; never retried here."""


@dataclass
class NativeF3SharedBudgetView:
    max_calls: int
    used: int = 0
    observed: bool = False


def _natural(value: Any) -> bool:
    return type(value) is int and 0 <= value <= MAX_SAFE_INTEGER


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate reply key")
        result[key] = value
    return result


@dataclass
class NativeF3DevelopmentChat:
    endpoint: str
    budget: NativeF3SharedBudgetView
    run_id: str
    config_digest: str
    client_id: str
    config_path: Path = field(repr=False)
    database_schema: str = "hswm_f3"
    hits: int = 0
    misses: int = 0
    backend_name: str = "native-f3-postgres-development-v1"

    def chat(self, *, model: str, system: str, user: str, seed: int,
             max_tokens: int, timeout: float = 240.0) -> dict:
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or timeout <= 0 or timeout > 86400 or int(timeout) != timeout):
            raise NativeF3BridgeError("F3 timeout must be whole seconds from 1 to 86400")
        request = {
            "schema_version": "hswm-native-f3-development-request/v1",
            "mode": "DEVELOPMENT_ONLY", "config_path": str(self.config_path),
            "database_schema": self.database_schema,
            "run": {"runId": self.run_id, "configDigest": self.config_digest,
                    "maxCalls": self.budget.max_calls},
            "client_id": self.client_id,
            "request": {"endpoint": self.endpoint, "model": model,
                        "system": system, "user": user, "seed": seed,
                        "maxTokens": max_tokens},
            "timeout_seconds": int(timeout),
        }
        source = json.dumps(request, ensure_ascii=False, allow_nan=False,
                            separators=(",", ":")).encode()
        if len(source) > MAX_BYTES:
            raise NativeF3BridgeError("F3 process input exceeds bound")
        self.budget.observed = False
        try:
            completed = subprocess.run(
                [os.environ.get("HSWM_NODE", "node"), str(PROCESS)],
                input=source, capture_output=True, check=False, timeout=timeout + 20,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise NativeF3BridgeError("F3 process outcome is unknown; inspect the same run") from error
        if completed.returncode != 0 or len(completed.stdout) > MAX_BYTES:
            raise NativeF3BridgeError("F3 process refused or failed; no automatic retry")
        try:
            reply = json.loads(completed.stdout, object_pairs_hook=_unique_object)
        except (ValueError, UnicodeError) as error:
            raise NativeF3BridgeError("invalid F3 process reply") from error
        if (not isinstance(reply, dict)
                or reply.get("schema_version") != "hswm-native-f3-development-result/v1"
                or reply.get("mode") != "DEVELOPMENT_ONLY"
                or reply.get("run_id") != self.run_id
                or reply.get("client_id") != self.client_id
                or not re.fullmatch(r"[0-9a-f]{64}", str(reply.get("request_sha256", "")))):
            raise NativeF3BridgeError("F3 process reply correlation failed")
        state = reply.get("state")
        if state is not None:
            if (not isinstance(state, dict)
                    or set(state) != {"maxCalls", "used", "hits", "misses"}
                    or not all(_natural(value) for value in state.values())
                    or state["maxCalls"] != self.budget.max_calls
                    or state["used"] > state["maxCalls"]
                    or state["used"] < self.budget.used
                    or state["hits"] < self.hits or state["misses"] < self.misses):
                raise NativeF3BridgeError("F3 counter observation is invalid")
            self.budget.used = state["used"]
            self.budget.observed = True
            self.hits, self.misses = state["hits"], state["misses"]
        terminal = reply.get("terminal")
        if terminal not in ("CACHE_HIT", "COMPLETED"):
            allowed = {"BUDGET_EXHAUSTED", "CACHE_READ_ERROR", "TRANSPORT_ERROR",
                       "TRANSPORT_UNCERTAIN", "RESPONSE_SCHEMA_ERROR", "CACHE_WRITE_ERROR",
                       "UNRESOLVED_DISPATCH", "PERSISTENCE_ERROR"}
            raise NativeF3BridgeError(f"native F3 terminal: {terminal if terminal in allowed else 'INVALID_REPLY'}")
        meta = reply.get("response_meta")
        if (state is None or not isinstance(meta, dict)
                or meta.get("request_sha256") != reply["request_sha256"]
                or meta.get("cached") is not (terminal == "CACHE_HIT")
                or not {"text", "finish_reason", "response_model", "usage"}.issubset(meta)):
            raise NativeF3BridgeError("F3 response metadata is invalid")
        return meta


def make_native_f3_development_chats(*, run_id: str, config_path: str,
                                     run_snapshot: dict, max_calls: int,
                                     donor_endpoint: str, receiver_endpoint: str):
    if not run_id or len(run_id) > 256 or "\x00" in run_id or not _natural(max_calls):
        raise NativeF3BridgeError("invalid F3 run identity")
    digest = hashlib.sha256(json.dumps(run_snapshot, sort_keys=True,
                                      ensure_ascii=False, allow_nan=False,
                                      separators=(",", ":")).encode()).hexdigest()
    budget = NativeF3SharedBudgetView(max_calls)
    config = Path(config_path).expanduser().resolve()
    common = {"budget": budget, "run_id": run_id, "config_digest": digest,
              "config_path": config}
    donor = NativeF3DevelopmentChat(donor_endpoint, client_id="f3v2-donor", **common)
    receiver = NativeF3DevelopmentChat(receiver_endpoint, client_id="f3v2-receiver", **common)
    return budget, donor, receiver, digest
