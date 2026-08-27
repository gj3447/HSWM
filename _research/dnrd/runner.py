"""Single-purpose DNRD measurement runner.

This module is deliberately not a generic harness.  It runs only the frozen
32-training/128-evaluation DNRD shape through injected model, local-V2 bridge,
and separate scorer-process interfaces.  It never imports or invokes a judge.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Mapping, Protocol, Sequence

from .task_family import (
    ManifestError,
    audit_public_manifest,
    canonical_json,
    commitment,
    is_response_token,
    training_provenance_canaries,
)


ARMS = ("FULL", "NO_MEMORY_ROLLBACK", "RAW_EQUAL_BUDGET", "BINDING_DERANGED_NUMERIC_PLACEBO")
MOUNT_ROLES = {
    "NO_MEMORY_ROLLBACK": "W0_ROLLBACK",
    "FULL": "FULL_TRAINABLE",
    "RAW_EQUAL_BUDGET": "RAW_CONTROL",
    "BINDING_DERANGED_NUMERIC_PLACEBO": "DERANGED_CONTROL",
}
CANDIDATE_SCHEMA = "hswm-dnrd-candidate/v1"
INCONCLUSIVE_SCHEMA = "hswm-dnrd-inconclusive-occurrence/v1"
EXPERIMENT_ID = "HSWM-DNRD-2"
RAW_DELTA_RULE = "signed_reward_times_100000_div_1000000/v1"
MAX_OUTPUT_TOKENS = 64
SCORER_ROLE_SEPARATION = "DECLARED_ROLE_SEPARATION_NOT_PROVEN"
SCORER_OUTCOME_FIELDS = frozenset(
    {
        "episode_id",
        "selected_route_id",
        "reward",
        "outcome_digest",
        "scorer_source_identity",
        "scorer_address",
        "role_separation",
    }
)
TRACE_STATUS = "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
LIVE_EVENT_SCHEMA = "hswm-dnrd-live-model-event/v2"
PREFLIGHT_SCHEMA = "hswm-dnrd-live-preflight-receipt/v1"
PROVIDER_CACHE_UNOBSERVABLE = "NOT_OBSERVABLE_BY_CLIENT"
BRIDGE_STATE_EVIDENCE_SCHEMA = "hswm-dnrd-bridge-state-evidence/v1"
BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA = "hswm-dnrd-bridge-mount-closure-plan/v1"
SUBPROCESS_TIMEOUT_SECONDS = 30.0
MAX_SUBPROCESS_STDOUT_BYTES = 1_048_576
MAX_SUBPROCESS_STDERR_BYTES = 65_536
PROCESS_INSTANCE_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class RunnerRefusal(ValueError):
    """A pre-call contract error: no measurement occurrence may be emitted."""


class PreDispatchAnswererError(RuntimeError):
    """The injected answerer guarantees no provider request was dispatched."""


@dataclass(frozen=True)
class ModelRequest:
    episode_id: str
    selected_route_id: str
    prompt: str
    max_output_tokens: int
    ordinal: int = 0
    phase: str = "UNSPECIFIED"
    arm: str | None = None


@dataclass(frozen=True)
class ModelReply:
    response_token: str
    input_tokens: int
    output_tokens: int
    client_cache_hit: bool = False
    server_usage: Mapping[str, int] | None = None


class Answerer(Protocol):
    def answer(self, request: ModelRequest) -> ModelReply: ...


@dataclass(frozen=True)
class RoutingState:
    state_sha256: str
    revision_id: str
    lineage_id: str
    owner_id: str
    mount_id: str
    mount_role: str
    scores: Mapping[str, Mapping[str, int]]
    immutable: bool = True


@dataclass(frozen=True)
class RecoveryObservation:
    state: RoutingState
    journal_sha256: str
    recovered: bool
    fresh_process: bool
    process_instance_id: str
    routing_payload_utf8: str
    routing_payload_sha256: str
    routing_payload_bytes: int


@dataclass(frozen=True)
class InitializationObservation:
    """Actual V2-owned W0/W1 mounts sharing one verified common prefix."""

    w0: RoutingState
    w1: RoutingState
    initialization_receipt_sha256: str
    common_prefix_sha256: str
    equal_genesis_content: bool


@dataclass(frozen=True)
class ControlMaterialization:
    """A bridge-owned durable control mount, never a Python-synthesized state."""

    state: RoutingState
    receipt_sha256: str


class Bridge(Protocol):
    def initialize(self, stream: Mapping[str, Any]) -> InitializationObservation: ...
    def materialize_control(self, state: RoutingState, stream_id: str, arm: str, training_update_records: Sequence[Mapping[str, Any]], matched_derangement: Mapping[str, str]) -> ControlMaterialization: ...
    def seal_trace(self, state: RoutingState, episode: Mapping[str, Any], selected_route_id: str, request_sha256: str, response_sha256: str) -> Mapping[str, Any]: ...
    def apply_outcome(self, state: RoutingState, trace: Mapping[str, Any], outcome: Mapping[str, Any]) -> tuple[RoutingState, Mapping[str, Any]]: ...
    def recover(self, state: RoutingState) -> RecoveryObservation: ...


class BridgeMountClosureExporter(Protocol):
    """Exports bounded raw durable files after all read-only evaluation checks.

    The runner supplies only observed mount/journal/payload identities.  The
    production execution boundary owns the filesystem copy and returns the
    SHA-256 of the exact closure-manifest bytes that it wrote.
    """

    def export(
        self,
        plan: Mapping[str, Any],
        *,
        forbidden_markers: frozenset[str],
    ) -> "BridgeMountClosureExport": ...


@dataclass(frozen=True)
class BridgeMountClosureExport:
    """Content identity plus an observation over every exported raw byte."""

    artifact_sha256: str
    watermark_detected: bool


class OutcomeScorer(Protocol):
    """Outcome process boundary; it owns any private scorer material."""

    def score(self, sealed_response: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class MeasurementMetadata:
    bindings: Mapping[str, Any]
    chronology: Mapping[str, Any]
    overlap: Mapping[str, Any]
    deployment_receipt: Mapping[str, Any]
    scorer_source_identity: str
    scorer_address: str
    active_state_byte_ceiling: int
    scorer_role_separation: str = SCORER_ROLE_SEPARATION


EventSink = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class RunnerResult:
    candidate: Mapping[str, Any] | None
    inconclusive_occurrence: Mapping[str, Any] | None
    client_cache_hits: int
    model_usage: Mapping[str, int]
    runner_event_ledger_sha256: str | None = None
    model_event_ledger_sha256: str | None = None
    bridge_state_evidence: Mapping[str, Any] | None = None
    bridge_state_evidence_sha256: str | None = None
    bridge_mount_closure_sha256: str | None = None
    client_cache_observability: str = "CLIENT_REPORTED_ONLY_NOT_PROVIDER_CACHE_OBSERVABILITY"


def _sha(value: Any) -> str:
    return commitment(value)


def _strict_sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _strict_canonical_json_line(raw: bytes, label: str) -> dict[str, Any]:
    """Accept exactly one canonical JSON object followed by one LF.

    A subprocess is part of the evidence boundary, so accepting arbitrary
    whitespace, duplicate keys, NaN, or multiple records would make its
    observable output ambiguous even if the final parsed object looked valid.
    """
    if len(raw) > MAX_SUBPROCESS_STDOUT_BYTES:
        raise RuntimeError(f"{label} stdout exceeds the frozen byte ceiling")
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise RuntimeError(f"{label} must emit one canonical JSON line")
    body = raw[:-1]

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise RuntimeError(f"{label} repeats JSON key {key!r}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise RuntimeError(f"{label} emits non-finite JSON value {value!r}")

    try:
        value = json.loads(
            body.decode("utf-8", errors="strict"),
            object_pairs_hook=no_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as error:
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"{label} emitted invalid UTF-8 JSON") from error
    if type(value) is not dict or canonical_json(value) != body:
        raise RuntimeError(f"{label} output is not an exact canonical JSON object")
    return value


class SubprocessJsonBridge:
    """Production bridge adapter for a future hash-bound V2 JSON CLI."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        implementation_path: str | Path,
        implementation_sha256: str,
        config: Mapping[str, Any],
        working_directory: str | Path | None = None,
        environment: Mapping[str, str] | None = None,
        timeout_seconds: float = SUBPROCESS_TIMEOUT_SECONDS,
        deferred_binding: bool = False,
    ) -> None:
        implementation = Path(implementation_path)
        if not command or not implementation.is_absolute():
            raise RunnerRefusal("bridge implementation path/hash binding mismatch")
        _require_sha256(implementation_sha256, "bridge implementation SHA-256")
        if not deferred_binding and _strict_sha(implementation) != implementation_sha256:
            raise RunnerRefusal("bridge implementation path/hash binding mismatch")
        self._command = tuple(command)
        self._implementation_path = str(implementation)
        self._implementation_sha256 = implementation_sha256
        self._config = dict(config)
        self._config_sha256 = _sha(self._config)
        self._working_directory = None if working_directory is None else str(working_directory)
        self._environment = None if environment is None else dict(environment)
        if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
            raise RunnerRefusal("bridge subprocess timeout must be positive")
        self._timeout_seconds = float(timeout_seconds)

    def _call(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            observed_implementation_sha256 = _strict_sha(self._implementation_path)
        except (FileNotFoundError, IsADirectoryError, OSError) as error:
            raise RuntimeError("V2 bridge implementation is unavailable at invocation") from error
        if observed_implementation_sha256 != self._implementation_sha256:
            raise RuntimeError("V2 bridge implementation bytes drifted before invocation")
        request = {"operation": operation, "implementation_path": self._implementation_path, "implementation_sha256": self._implementation_sha256, "config": self._config, "config_sha256": self._config_sha256, "payload": payload}
        try:
            completed = subprocess.run(
                self._command,
                input=canonical_json(request) + b"\n",
                text=False,
                capture_output=True,
                check=False,
                cwd=self._working_directory,
                env=self._environment,
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("V2 bridge subprocess exceeded the frozen timeout") from error
        if len(completed.stdout) > MAX_SUBPROCESS_STDOUT_BYTES or len(completed.stderr) > MAX_SUBPROCESS_STDERR_BYTES:
            raise RuntimeError("V2 bridge subprocess exceeded frozen output limits")
        if completed.returncode != 0:
            raise RuntimeError("V2 bridge subprocess refused request")
        if completed.stderr:
            raise RuntimeError("V2 bridge subprocess emitted unexpected stderr")
        return _strict_canonical_json_line(completed.stdout, "V2 bridge")

    def initialize(self, stream: Mapping[str, Any]) -> InitializationObservation:
        result = self._call("INIT_STREAM", {"stream": stream})
        expected = {
            "w0",
            "w1",
            "initialization_receipt_sha256",
            "common_prefix_sha256",
            "equal_genesis_content",
        }
        if set(result) != expected:
            raise RuntimeError("V2 INIT_STREAM response exact schema drifted")
        _require_sha256(
            result["initialization_receipt_sha256"],
            "V2 initialization_receipt_sha256",
        )
        _require_sha256(result["common_prefix_sha256"], "V2 common_prefix_sha256")
        if type(result["equal_genesis_content"]) is not bool:
            raise RuntimeError("V2 equal_genesis_content must be an exact boolean")
        return InitializationObservation(
            _state_from_wire(result["w0"]),
            _state_from_wire(result["w1"]),
            result["initialization_receipt_sha256"],
            result["common_prefix_sha256"],
            result["equal_genesis_content"],
        )

    def materialize_control(self, state: RoutingState, stream_id: str, arm: str, training_update_records: Sequence[Mapping[str, Any]], matched_derangement: Mapping[str, str]) -> ControlMaterialization:
        if arm not in {"RAW_EQUAL_BUDGET", "BINDING_DERANGED_NUMERIC_PLACEBO"}:
            raise RunnerRefusal("only RAW and DERANGED controls may be materialized")
        payload: dict[str, Any] = {"state": _state_wire(state), "stream_id": stream_id, "arm": arm}
        if arm == "RAW_EQUAL_BUDGET":
            payload.update({"raw_delta_rule": RAW_DELTA_RULE, "training_update_records": list(training_update_records), "required_training_outcome_count": 8})
        else:
            payload["matched_derangement"] = dict(matched_derangement)
        result = self._call("MATERIALIZE_CONTROL", payload)
        if set(result) != {"state", "receipt_sha256"}:
            raise RuntimeError("V2 MATERIALIZE_CONTROL response exact schema drifted")
        _require_sha256(result["receipt_sha256"], "V2 control receipt_sha256")
        return ControlMaterialization(_state_from_wire(result["state"]), result["receipt_sha256"])

    def seal_trace(self, state: RoutingState, episode: Mapping[str, Any], selected_route_id: str, request_sha256: str, response_sha256: str) -> Mapping[str, Any]:
        return self._call("SEAL_TRACE", {"state": _state_wire(state), "episode_id": episode["episode_id"], "context_key": episode["context_key"], "selected_route_id": selected_route_id, "request_sha256": request_sha256, "response_sha256": response_sha256})

    def apply_outcome(self, state: RoutingState, trace: Mapping[str, Any], outcome: Mapping[str, Any]) -> tuple[RoutingState, Mapping[str, Any]]:
        result = self._call("APPLY_OUTCOME", {"state": _state_wire(state), "trace": trace, "outcome": outcome})
        return _state_from_wire(result["state"]), result["receipt"]

    def recover(self, state: RoutingState) -> RecoveryObservation:
        result = self._call("RECOVER", {"state": _state_wire(state)})
        expected = {
            "state",
            "journal_sha256",
            "recovered",
            "fresh_process",
            "process_instance_id",
            "mount_role",
            "routing_payload_utf8",
            "routing_payload_sha256",
            "routing_payload_bytes",
        }
        if set(result) != expected:
            raise RuntimeError("V2 RECOVER response exact schema drifted")
        state = _state_from_wire(result["state"])
        if not isinstance(result["mount_role"], str) or not result["mount_role"]:
            raise RuntimeError("V2 RECOVER mount_role must be a nonempty string")
        if result["mount_role"] != state.mount_role:
            raise RuntimeError("V2 RECOVER mount role does not bind returned state")
        if type(result["recovered"]) is not bool or type(result["fresh_process"]) is not bool:
            raise RuntimeError("V2 RECOVER recovery flags must be exact booleans")
        if type(result["process_instance_id"]) is not str:
            raise RuntimeError("V2 RECOVER process_instance_id must be a string")
        _require_process_instance_uuid(
            result["process_instance_id"],
            "V2 RECOVER process_instance_id",
        )
        _require_sha256(result["journal_sha256"], "V2 RECOVER journal_sha256")
        if type(result["routing_payload_utf8"]) is not str:
            raise RuntimeError("V2 RECOVER routing_payload_utf8 must be a string")
        _require_sha256(
            result["routing_payload_sha256"],
            "V2 RECOVER routing_payload_sha256",
        )
        if type(result["routing_payload_bytes"]) is not int or result["routing_payload_bytes"] <= 0:
            raise RuntimeError("V2 RECOVER routing_payload_bytes must be a positive exact integer")
        return RecoveryObservation(
            state,
            result["journal_sha256"],
            result["recovered"],
            result["fresh_process"],
            result["process_instance_id"],
            result["routing_payload_utf8"],
            result["routing_payload_sha256"],
            result["routing_payload_bytes"],
        )


class SubprocessOutcomeScorer:
    """Separate-process scorer adapter; command bytes are bound before use."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        implementation_path: str | Path,
        implementation_sha256: str,
        private_manifest_path: str | Path,
        working_directory: str | Path | None = None,
        environment: Mapping[str, str] | None = None,
        timeout_seconds: float = SUBPROCESS_TIMEOUT_SECONDS,
        deferred_binding: bool = False,
    ) -> None:
        implementation = Path(implementation_path)
        if not command or not implementation.is_absolute():
            raise RunnerRefusal("scorer implementation path/hash binding mismatch")
        _require_sha256(implementation_sha256, "scorer implementation SHA-256")
        if not deferred_binding and _strict_sha(implementation) != implementation_sha256:
            raise RunnerRefusal("scorer implementation path/hash binding mismatch")
        private_path = Path(private_manifest_path)
        if not private_path.is_absolute():
            raise RunnerRefusal("scorer private manifest path must be absolute")
        # Do not read or parse the private file in the runner process.  The
        # scorer child owns its contents and receives this fixed path only.
        self._private_manifest_path = str(private_path)
        self._command, self._implementation_path, self._implementation_sha256 = tuple(command), str(implementation), implementation_sha256
        self._working_directory = None if working_directory is None else str(working_directory)
        self._environment = None if environment is None else dict(environment)
        if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
            raise RunnerRefusal("scorer subprocess timeout must be positive")
        self._timeout_seconds = float(timeout_seconds)

    def score(self, sealed_response: Mapping[str, Any]) -> Mapping[str, Any]:
        # The checked-in scorer owns a fixed private-manifest path.  The runner
        # writes only the sealed response into its temporary directory and
        # never parses or passes private scorer material.
        try:
            observed_implementation_sha256 = _strict_sha(self._implementation_path)
        except (FileNotFoundError, IsADirectoryError, OSError) as error:
            raise RuntimeError("scorer implementation is unavailable at invocation") from error
        if observed_implementation_sha256 != self._implementation_sha256:
            raise RuntimeError("scorer implementation bytes drifted before invocation")
        with tempfile.TemporaryDirectory(prefix="hswm-dnrd-scorer-") as temporary:
            os.chmod(temporary, 0o700)
            root = Path(temporary)
            sealed_path = root / "sealed.json"
            sealed_path.write_bytes(canonical_json(sealed_response))
            os.chmod(sealed_path, 0o600)
            try:
                completed = subprocess.run(
                    [*self._command, "--private-manifest", self._private_manifest_path, "--sealed-response", str(sealed_path)],
                    text=False,
                    capture_output=True,
                    check=False,
                    cwd=self._working_directory,
                    env=self._environment,
                    timeout=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired as error:
                raise RuntimeError("scorer subprocess exceeded the frozen timeout") from error
        if len(completed.stdout) > MAX_SUBPROCESS_STDOUT_BYTES or len(completed.stderr) > MAX_SUBPROCESS_STDERR_BYTES:
            raise RuntimeError("scorer subprocess exceeded frozen output limits")
        if completed.returncode != 0:
            raise RuntimeError("scorer subprocess refused response")
        if completed.stderr:
            raise RuntimeError("scorer subprocess emitted unexpected stderr")
        result = _strict_canonical_json_line(completed.stdout, "scorer subprocess")
        expected = {"episode_id", "selected_route_id", "reward", "outcome_digest", "scorer_source_identity", "scorer_address", "role_separation"}
        if set(result) != expected:
            raise RuntimeError("scorer subprocess output violates the non-gold outcome contract")
        return result


def _state_wire(state: RoutingState) -> dict[str, Any]:
    return {
        "state_sha256": state.state_sha256,
        "revision_id": state.revision_id,
        "lineage_id": state.lineage_id,
        "owner_id": state.owner_id,
        "mount_id": state.mount_id,
        "mount_role": state.mount_role,
        "immutable": state.immutable,
        "scores": state.scores,
    }


def _state_from_wire(value: Any) -> RoutingState:
    expected = {
        "state_sha256",
        "revision_id",
        "lineage_id",
        "owner_id",
        "mount_id",
        "mount_role",
        "scores",
        "immutable",
    }
    if type(value) is not dict or set(value) != expected:
        raise RuntimeError("bridge state exact wire schema drifted")
    for key in (
        "state_sha256",
        "revision_id",
        "lineage_id",
        "owner_id",
        "mount_id",
        "mount_role",
    ):
        if not isinstance(value[key], str) or not value[key]:
            raise RuntimeError(f"bridge state {key} is malformed")
    _require_sha256(value["state_sha256"], "bridge state state_sha256")
    if type(value["immutable"]) is not bool or type(value["scores"]) is not dict or not value["scores"]:
        raise RuntimeError("bridge state immutable/scores fields are malformed")
    scores: dict[str, dict[str, int]] = {}
    for context, routes in value["scores"].items():
        if not isinstance(context, str) or not context or type(routes) is not dict or not routes:
            raise RuntimeError("bridge state score support is malformed")
        parsed_routes: dict[str, int] = {}
        for route, score in routes.items():
            if not isinstance(route, str) or not route or type(score) is not int:
                raise RuntimeError("bridge state score values must be exact integers")
            parsed_routes[route] = score
        scores[context] = parsed_routes
    return RoutingState(
        state_sha256=value["state_sha256"],
        revision_id=value["revision_id"],
        lineage_id=value["lineage_id"],
        owner_id=value["owner_id"],
        mount_id=value["mount_id"],
        mount_role=value["mount_role"],
        scores=scores,
        immutable=value["immutable"],
    )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_sha256(value: Any, label: str) -> str:
    if not _is_sha256(value):
        raise RunnerRefusal(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_process_instance_uuid(value: Any, label: str) -> str:
    """Accept the raw per-process identifier emitted by the bridge runtime.

    The TypeScript process deliberately exposes a UUID rather than inventing a
    digest at this boundary.  Preserve that observed value verbatim so the
    evidence bundle can establish distinct recoveries without relabelling it.
    """
    if not isinstance(value, str) or PROCESS_INSTANCE_UUID_RE.fullmatch(value) is None:
        raise RunnerRefusal(f"{label} must be a lowercase UUID")
    return value


def _canonical_jsonl(events: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json(dict(event)) + b"\n" for event in events)


def _ledger_sha256(events: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(_canonical_jsonl(events)).hexdigest()


def _select(state: RoutingState, episode: Mapping[str, Any]) -> str:
    scores = state.scores[episode["context_key"]]
    return sorted(episode["candidate_route_ids"], key=lambda route: (-scores[route], route))[0]


def _route_digest(state: RoutingState, episode: Mapping[str, Any]) -> str:
    route = _select(state, episode)
    return _sha({"context_key": episode["context_key"], "selected_route_id": route, "score": state.scores[episode["context_key"]][route]})


def _selected_evidence(episode: Mapping[str, Any], route: str) -> Mapping[str, Any]:
    records = [record for record in episode["route_evidence"] if record["route_id"] == route]
    if len(records) != 1:
        raise RunnerRefusal("public episode has no unique selected evidence")
    return records[0]


def _request(
    episode: Mapping[str, Any],
    route: str,
    *,
    ordinal: int,
    phase: str,
    arm: str | None,
) -> ModelRequest:
    evidence = _selected_evidence(episode, route)
    # This is intentionally the only episode material presented to a model.
    prompt = f"{episode['prompt']}\nSelected evidence:\n{evidence['evidence_text']}"
    return ModelRequest(
        str(episode["episode_id"]),
        route,
        prompt,
        MAX_OUTPUT_TOKENS,
        ordinal,
        phase,
        arm,
    )


def _sealed_response(episode: Mapping[str, Any], route: str, reply: ModelReply, private_commitment: str) -> dict[str, Any]:
    payload = {"schema_version": "hswm-dnrd-sealed-response/v1", "episode_id": episode["episode_id"], "selected_route_id": route, "answer": reply.response_token, "private_manifest_commitment": private_commitment}
    return {**payload, "response_commitment": _sha(payload)}


def _state_observation(state: RoutingState, *, owner: bool) -> dict[str, Any]:
    value = {"state_sha256": state.state_sha256, "revision_id": state.revision_id, "lineage_id": state.lineage_id, "immutable": state.immutable}
    if owner:
        value["owner_id"] = state.owner_id
    return value


def _validate_recovery_observation(recovery: RecoveryObservation) -> None:
    if (
        type(recovery.recovered) is not bool
        or type(recovery.fresh_process) is not bool
        or type(recovery.routing_payload_bytes) is not int
        or recovery.routing_payload_bytes <= 0
        or not isinstance(recovery.routing_payload_utf8, str)
    ):
        raise RuntimeError("bridge recovery observation is malformed")
    for value, label in (
        (recovery.journal_sha256, "bridge recovery journal_sha256"),
        (recovery.routing_payload_sha256, "bridge recovery routing_payload_sha256"),
    ):
        _require_sha256(value, label)
    _require_process_instance_uuid(
        recovery.process_instance_id,
        "bridge recovery process_instance_id",
    )
    payload = recovery.routing_payload_utf8.encode("utf-8")
    try:
        decoded = json.loads(recovery.routing_payload_utf8)
    except json.JSONDecodeError as error:
        raise RuntimeError("bridge recovery routing payload is not UTF-8 JSON") from error
    if (
        type(decoded) is not dict
        or canonical_json(decoded) != payload
        or hashlib.sha256(payload).hexdigest() != recovery.routing_payload_sha256
        or len(payload) != recovery.routing_payload_bytes
        or recovery.state.state_sha256 != recovery.routing_payload_sha256
    ):
        raise RuntimeError("bridge recovery payload bytes do not bind recovered durable state")


def _bridge_state_entry(recovery: RecoveryObservation) -> dict[str, Any]:
    """Actual durable payload plus an explicitly non-authoritative score projection."""
    _validate_recovery_observation(recovery)
    state = recovery.state
    score_projection = canonical_json({"scores": state.scores})
    return {
        "mount_id": state.mount_id,
        "mount_role": state.mount_role,
        "state_sha256": state.state_sha256,
        "routing_payload_utf8": recovery.routing_payload_utf8,
        "routing_payload_sha256": recovery.routing_payload_sha256,
        "routing_payload_bytes": recovery.routing_payload_bytes,
        "score_projection_utf8": score_projection.decode("utf-8"),
        "score_projection_sha256": hashlib.sha256(score_projection).hexdigest(),
        "score_projection_bytes": len(score_projection),
    }


def _recovery_evidence(recovery: RecoveryObservation) -> dict[str, Any]:
    return {
        "recovered": recovery.recovered,
        "fresh_process": recovery.fresh_process,
        "journal_sha256": recovery.journal_sha256,
        "process_instance_id": recovery.process_instance_id,
    }


def _bridge_mount_closure_plan(
    bridge_state_evidence: Mapping[str, Any],
    bridge_state_evidence_sha256: str,
) -> dict[str, Any]:
    """Freeze the only mount files an occurrence is allowed to export.

    This is deliberately a small plan rather than a filesystem walk: the
    exporter must copy exactly the sixteen post-evaluation arm mounts already
    observed by the runner, with their pre/post journal and durable-routing
    identities.  It cannot broaden the closure by discovering another mount.
    """
    if (
        bridge_state_evidence.get("schema_version") != BRIDGE_STATE_EVIDENCE_SCHEMA
        or _sha(bridge_state_evidence) != bridge_state_evidence_sha256
        or type(bridge_state_evidence.get("streams")) is not list
        or len(bridge_state_evidence["streams"]) != 4
    ):
        raise RuntimeError("bridge mount closure plan lacks exact state evidence")
    streams: list[dict[str, Any]] = []
    seen_streams: set[str] = set()
    seen_mounts: set[str] = set()
    for index, item in enumerate(bridge_state_evidence["streams"]):
        if type(item) is not dict or set(item) != {
            "stream_id",
            "pre_evaluation",
            "post_evaluation",
        }:
            raise RuntimeError("bridge state evidence stream schema drifted")
        stream_id = item["stream_id"]
        if (
            not isinstance(stream_id, str)
            or stream_id != f"stream-{index}"
            or stream_id in seen_streams
        ):
            raise RuntimeError("bridge state evidence stream identity is malformed")
        seen_streams.add(stream_id)
        pre, post = item["pre_evaluation"], item["post_evaluation"]
        if (
            type(pre) is not dict
            or type(post) is not dict
            or set(pre) != {"arms", "fresh_recovery"}
            or set(post) != {"arms", "fresh_recovery"}
            or type(pre["arms"]) is not dict
            or type(post["arms"]) is not dict
            or type(pre["fresh_recovery"]) is not dict
            or type(post["fresh_recovery"]) is not dict
            or set(pre["arms"]) != set(ARMS)
            or set(post["arms"]) != set(ARMS)
            or set(pre["fresh_recovery"]) != set(ARMS)
            or set(post["fresh_recovery"]) != set(ARMS)
        ):
            raise RuntimeError("bridge state evidence arm schema drifted")
        arms: dict[str, Any] = {}
        for arm in ARMS:
            before, after = pre["arms"][arm], post["arms"][arm]
            before_recovery = pre["fresh_recovery"][arm]
            after_recovery = post["fresh_recovery"][arm]
            if type(before) is not dict or type(after) is not dict:
                raise RuntimeError("bridge state evidence arm payload is malformed")
            expected_entry = {
                "mount_id",
                "mount_role",
                "state_sha256",
                "routing_payload_utf8",
                "routing_payload_sha256",
                "routing_payload_bytes",
                "score_projection_utf8",
                "score_projection_sha256",
                "score_projection_bytes",
            }
            if set(before) != expected_entry or set(after) != expected_entry:
                raise RuntimeError("bridge state evidence entry schema drifted")
            if before != after:
                raise RuntimeError("mount closure may export only post-audited unchanged routing evidence")
            if (
                type(before_recovery) is not dict
                or type(after_recovery) is not dict
                or set(before_recovery)
                != {"recovered", "fresh_process", "journal_sha256", "process_instance_id"}
                or set(after_recovery)
                != {"recovered", "fresh_process", "journal_sha256", "process_instance_id"}
            ):
                raise RuntimeError("bridge recovery evidence schema drifted")
            mount_id, mount_role = before["mount_id"], before["mount_role"]
            if (
                not isinstance(mount_id, str)
                or not mount_id
                or mount_id in seen_mounts
                or mount_role != MOUNT_ROLES[arm]
            ):
                raise RuntimeError("bridge state evidence mount identity/role is malformed")
            seen_mounts.add(mount_id)
            for value, label in (
                (before["routing_payload_sha256"], "pre routing payload"),
                (after["routing_payload_sha256"], "post routing payload"),
                (before_recovery["journal_sha256"], "pre journal"),
                (after_recovery["journal_sha256"], "post journal"),
            ):
                _require_sha256(value, f"bridge mount closure {label}")
            arms[arm] = {
                "mount_id": mount_id,
                "mount_role": mount_role,
                "pre_evaluation_journal_sha256": before_recovery["journal_sha256"],
                "post_evaluation_journal_sha256": after_recovery["journal_sha256"],
                "pre_evaluation_routing_payload_sha256": before[
                    "routing_payload_sha256"
                ],
                "post_evaluation_routing_payload_sha256": after[
                    "routing_payload_sha256"
                ],
            }
        streams.append({"stream_id": stream_id, "arms": arms})
    if len(seen_streams) != 4 or len(seen_mounts) != 16:
        raise RuntimeError("bridge mount closure plan lacks exactly four streams and sixteen mounts")
    return {
        "schema_version": BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA,
        "bridge_state_evidence_sha256": bridge_state_evidence_sha256,
        "streams": streams,
    }


def _verify_initialization(initial: InitializationObservation, stream: Mapping[str, Any]) -> None:
    if not initial.equal_genesis_content or len(initial.common_prefix_sha256) != 64 or len(initial.initialization_receipt_sha256) != 64:
        raise RunnerRefusal("bridge did not attest an exact common W0/W1 genesis prefix")
    if initial.w0.state_sha256 != initial.w1.state_sha256:
        raise RunnerRefusal("W0 and W1 genesis content hashes differ")
    if initial.w0.scores != initial.w1.scores:
        raise RunnerRefusal("W0 and W1 genesis score content differs")
    if initial.w0.mount_id == initial.w1.mount_id:
        raise RunnerRefusal("W0 and W1 must be separately mounted durable views")
    if (
        initial.w0.mount_role != MOUNT_ROLES["NO_MEMORY_ROLLBACK"]
        or initial.w1.mount_role != MOUNT_ROLES["FULL"]
    ):
        raise RunnerRefusal("bridge initialization does not expose immutable W0/FULL mount roles")
    expected_contexts, expected_routes = set(stream["context_keys"]), set(stream["route_ids"])
    for state in (initial.w0, initial.w1):
        if set(state.scores) != expected_contexts:
            raise RunnerRefusal("bridge genesis context support differs from public stream")
        for routes in state.scores.values():
            if set(routes) != expected_routes or any(score != 0 for score in routes.values()):
                raise RunnerRefusal("bridge genesis W0/W1 must expose exact zero score support")


def _require_mount_role(state: RoutingState, arm: str, label: str) -> None:
    expected = MOUNT_ROLES[arm]
    if state.mount_role != expected:
        raise RuntimeError(f"{label} has mount role {state.mount_role!r}, not immutable {expected!r}")


def _same_routing_state(before: RecoveryObservation, after: RecoveryObservation) -> bool:
    """Compare routing state only; trace journals are allowed to append."""
    left, right = before.state, after.state
    return (
        left.state_sha256 == right.state_sha256
        and left.revision_id == right.revision_id
        and left.lineage_id == right.lineage_id
        and left.owner_id == right.owner_id
        and left.mount_id == right.mount_id
        and left.mount_role == right.mount_role
        and left.immutable == right.immutable
        and left.scores == right.scores
        and before.routing_payload_utf8 == after.routing_payload_utf8
        and before.routing_payload_sha256 == after.routing_payload_sha256
        and before.routing_payload_bytes == after.routing_payload_bytes
    )


def _derangement_observation(full: RoutingState, deranged: RoutingState, stream: Mapping[str, Any]) -> dict[str, Any]:
    full_scores = [score for context in sorted(full.scores) for _, score in sorted(full.scores[context].items())]
    deranged_scores = [score for context in sorted(deranged.scores) for _, score in sorted(deranged.scores[context].items())]
    full_bytes = canonical_json({"scores": full.scores})
    deranged_bytes = canonical_json({"scores": deranged.scores})
    fixed_points = sum(source == target for source, target in stream["matched_derangement"].items())
    return {
        "algorithm": "within-stratum-no-fixed-point/v1",
        "seed_sha256": _sha(stream["matched_derangement"]),
        "fixed_point_count": fixed_points,
        "preserves_update_multiset": sorted(full_scores) == sorted(deranged_scores),
        "preserves_precision": all(type(score) is int for score in full_scores + deranged_scores),
        "preserves_l1_l2_norms": sum(abs(score) for score in full_scores) == sum(abs(score) for score in deranged_scores) and sum(score * score for score in full_scores) == sum(score * score for score in deranged_scores),
        "preserves_routing_payload_byte_count": len(full_bytes) == len(deranged_bytes),
        "routing_payload_content_differs": full_bytes != deranged_bytes,
    }


def _expected_raw_scores(w0: RoutingState, records: Sequence[Mapping[str, Any]], stream: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    if len(records) != 8:
        raise RuntimeError("RAW control requires exactly eight training update records")
    expected_ids = {episode["episode_id"] for episode in stream["training"]}
    seen_ids: set[str] = set()
    scores = {context: dict(routes) for context, routes in w0.scores.items()}
    for record in records:
        required = {"episode_id", "context_key", "selected_route_id", "reward", "trace_id", "outcome_digest"}
        if set(record) != required:
            raise RuntimeError("RAW training update record fields drifted")
        episode_id, context, route = record["episode_id"], record["context_key"], record["selected_route_id"]
        reward = record["reward"]
        if not all(isinstance(value, str) and value for value in (episode_id, context, route, record["trace_id"], record["outcome_digest"])):
            raise RuntimeError("RAW training update record identity drifted")
        if episode_id in seen_ids or episode_id not in expected_ids or context not in scores or route not in scores[context]:
            raise RuntimeError("RAW training update record support drifted")
        if type(reward) is not int or reward not in {-1_000_000, 0, 1_000_000}:
            raise RuntimeError("RAW training update reward violates frozen contract")
        seen_ids.add(episode_id)
        delta = reward * 100_000 // 1_000_000
        scores[context][route] = max(-100_000, min(100_000, scores[context][route] + delta))
    if seen_ids != expected_ids:
        raise RuntimeError("RAW training update record set differs from public forced exposures")
    return scores


def _expected_deranged_scores(full: RoutingState, mapping: Mapping[str, str]) -> dict[str, dict[str, int]]:
    if set(mapping) != set(full.scores) or set(mapping.values()) != set(full.scores) or any(source == target for source, target in mapping.items()):
        raise RuntimeError("DERANGED control map is not the exact public fixed-point-free mapping")
    return {receiver: dict(full.scores[donor]) for receiver, donor in mapping.items()}


def _request_object(request: ModelRequest) -> dict[str, Any]:
    """Canonical full request observation, including non-provider call context.

    ``phase``/``arm`` make the public ledger reconcilable.  They are never
    interpolated into ``prompt`` and therefore never enter the model request
    body.  The bridge seals the whole object so a response cannot be moved
    between calls with otherwise identical provider-visible text.
    """
    return {
        "episode_id": request.episode_id,
        "selected_route_id": request.selected_route_id,
        "prompt": request.prompt,
        "max_output_tokens": request.max_output_tokens,
        "ordinal": request.ordinal,
        "phase": request.phase,
        "arm": request.arm,
    }


def model_request_commitment(request: ModelRequest) -> str:
    """Stable call identity shared with the live OpenAI boundary ledger."""
    return _sha(_request_object(request))


def _response_object(reply: ModelReply) -> dict[str, Any]:
    return {"response_token": reply.response_token, "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens, "client_cache_hit": reply.client_cache_hit, "server_usage": dict(reply.server_usage or {})}


def _validate_reply(reply: ModelReply) -> None:
    if not is_response_token(reply.response_token):
        raise RuntimeError("answerer response token violates exact DNRD-2 form")
    for label, value in (("input_tokens", reply.input_tokens), ("output_tokens", reply.output_tokens)):
        if type(value) is not int or value < 0:
            raise RuntimeError(f"answerer {label} must be a nonnegative integer")
    if reply.output_tokens <= 0 or reply.output_tokens > MAX_OUTPUT_TOKENS:
        raise RuntimeError("answerer output token count exceeds frozen DNRD limit")
    if type(reply.client_cache_hit) is not bool:
        raise RuntimeError("answerer client_cache_hit must be boolean")
    if reply.server_usage is not None:
        if not isinstance(reply.server_usage, Mapping):
            raise RuntimeError("answerer server usage must be a mapping")
        for key, value in reply.server_usage.items():
            if not isinstance(key, str) or type(value) is not int or value < 0:
                raise RuntimeError("answerer server usage must be nonnegative integer telemetry")


def _validate_trace(
    trace: Mapping[str, Any],
    *,
    state: RoutingState,
    episode: Mapping[str, Any],
    route: str,
    request_sha256: str,
    response_sha256: str,
) -> None:
    expected = {
        "trace_id",
        "episode_id",
        "context_key",
        "context_sha256",
        "stratum",
        "selected_route_id",
        "pre_outcome_score_micros",
        "routing_payload_sha256",
        "request_sha256",
        "response_sha256",
        "status",
    }
    if set(trace) != expected:
        raise RuntimeError("bridge trace violates the frozen exact trace schema")
    for key in (
        "trace_id",
        "context_sha256",
        "routing_payload_sha256",
        "request_sha256",
        "response_sha256",
    ):
        _require_sha256(trace[key], f"trace.{key}")
    if (
        trace["episode_id"] != episode["episode_id"]
        or trace["context_key"] != episode["context_key"]
        or trace["selected_route_id"] != route
        or trace["context_sha256"] != hashlib.sha256(episode["context_key"].encode("utf-8")).hexdigest()
        or trace["routing_payload_sha256"] != state.state_sha256
        or trace["request_sha256"] != request_sha256
        or trace["response_sha256"] != response_sha256
        or trace["status"] != TRACE_STATUS
    ):
        raise RuntimeError("bridge trace does not bind exact state, episode, request, and response")
    expected_stratum = f"stratum:{hashlib.sha256(str(episode['stream_id']).encode('utf-8')).hexdigest()}"
    if trace["stratum"] != expected_stratum:
        raise RuntimeError("bridge trace stratum differs from the frozen stream binding")
    if (
        type(trace["pre_outcome_score_micros"]) is not int
        or trace["pre_outcome_score_micros"]
        != state.scores[episode["context_key"]][route]
    ):
        raise RuntimeError("bridge trace pre-outcome score differs from recovered state")


def _validate_scorer_outcome(
    outcome: Mapping[str, Any],
    *,
    sealed: Mapping[str, Any],
    metadata: MeasurementMetadata,
) -> None:
    if set(outcome) != SCORER_OUTCOME_FIELDS:
        raise RuntimeError("scorer outcome violates the exact seven-field non-gold schema")
    reward = outcome["reward"]
    if type(reward) is not int or reward not in {-1_000_000, 0, 1_000_000}:
        raise RuntimeError("scorer outcome reward violates frozen signed-integer contract")
    if (
        outcome["episode_id"] != sealed["episode_id"]
        or outcome["selected_route_id"] != sealed["selected_route_id"]
        or outcome["scorer_source_identity"] != metadata.scorer_source_identity
        or outcome["scorer_address"] != metadata.scorer_address
        or outcome["role_separation"] != metadata.scorer_role_separation
    ):
        raise RuntimeError("scorer outcome does not match the sealed call or frozen scorer pin")
    _require_sha256(outcome["scorer_source_identity"], "scorer_source_identity")
    _require_sha256(outcome["outcome_digest"], "outcome_digest")
    expected_digest = _sha(
        {
            "episode_id": sealed["episode_id"],
            "selected_route_id": sealed["selected_route_id"],
            "response_commitment": sealed["response_commitment"],
            "private_manifest_commitment": sealed["private_manifest_commitment"],
            "reward": reward,
            "scorer_source_identity": metadata.scorer_source_identity,
        }
    )
    if outcome["outcome_digest"] != expected_digest:
        raise RuntimeError("scorer outcome digest does not bind the sealed response and frozen scorer")


def _observe_call(
    answerer: Answerer,
    bridge: Bridge,
    scorer: OutcomeScorer,
    state: RoutingState,
    episode: Mapping[str, Any],
    route: str,
    private_manifest_commitment: str,
    metadata: MeasurementMetadata,
    *,
    ordinal: int,
    phase: str,
    arm: str | None,
    on_response: Callable[[ModelReply | None], None],
) -> tuple[ModelRequest, ModelReply, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    request = _request(episode, route, ordinal=ordinal, phase=phase, arm=arm)
    try:
        reply = answerer.answer(request)
    except PreDispatchAnswererError:
        raise
    except Exception:
        # The answerer did not declare pre-dispatch failure. Count conservatively.
        on_response(None)
        raise
    on_response(reply)
    _validate_reply(reply)
    sealed = _sealed_response(episode, route, reply, private_manifest_commitment)
    request_sha256 = model_request_commitment(request)
    response_sha256 = _sha(_response_object(reply))
    trace = bridge.seal_trace(state, episode, route, request_sha256, response_sha256)
    if not isinstance(trace, Mapping):
        raise RuntimeError("bridge trace is not an object")
    _validate_trace(
        trace,
        state=state,
        episode=episode,
        route=route,
        request_sha256=request_sha256,
        response_sha256=response_sha256,
    )
    outcome = scorer.score(sealed)
    if not isinstance(outcome, Mapping):
        raise RuntimeError("scorer outcome is not an object")
    _validate_scorer_outcome(outcome, sealed=sealed, metadata=metadata)
    return request, reply, sealed, trace, outcome


def _inconclusive(calls: int, cache_hits: int, error: Exception) -> dict[str, Any]:
    return {"schema_version": INCONCLUSIVE_SCHEMA, "experiment_id": EXPERIMENT_ID, "post_first_call": True, "calls_completed": calls, "client_cache_hits": cache_hits, "failure_type": type(error).__name__, "failure_digest": _sha({"type": type(error).__name__, "message": str(error)})}


def _record_usage(usage: dict[str, int], reply: ModelReply) -> None:
    usage["input_tokens"] += reply.input_tokens
    usage["output_tokens"] += reply.output_tokens
    for key, value in (reply.server_usage or {}).items():
        if type(value) is not int or value < 0:
            raise RuntimeError("server usage must be nonnegative integer telemetry")
        usage[f"server:{key}"] = usage.get(f"server:{key}", 0) + value


def _validate_deployment_receipt(receipt: Mapping[str, Any], bindings: Mapping[str, Any]) -> None:
    """Validate the observable, self-addressed three-call live preflight.

    The runner deliberately validates only evidence it can inspect.  The
    execution boundary additionally pins the exact frozen live constants and
    reparses retained raw preflight responses before it permits a model call.
    """
    required = {
        "schema_version",
        "endpoint",
        "model",
        "model_root",
        "model_max_model_len",
        "vllm_version",
        "chat_config",
        "model_list_request_sha256",
        "model_list_response_sha256",
        "model_list_response_utf8",
        "version_request_sha256",
        "version_response_sha256",
        "version_response_utf8",
        "tokenizer_request_sha256",
        "tokenizer_response_sha256",
        "tokenizer_response_utf8",
        "tokenizer_count",
        "provider_cache_independence",
        "generation_calls",
        "non_generation_http_calls",
        "preflight_call_order",
        "receipt_sha256",
    }
    if set(receipt) != required:
        raise RunnerRefusal("deployment preflight receipt field set drifted")
    if receipt["schema_version"] != PREFLIGHT_SCHEMA:
        raise RunnerRefusal("deployment preflight schema drifted")
    if not all(isinstance(receipt[key], str) and receipt[key] for key in ("endpoint", "model", "model_root", "vllm_version")):
        raise RunnerRefusal("deployment identity receipt is malformed")
    if type(receipt["model_max_model_len"]) is not int or receipt["model_max_model_len"] <= 0:
        raise RunnerRefusal("deployment model max length is malformed")
    if not isinstance(receipt["chat_config"], Mapping):
        raise RunnerRefusal("deployment chat configuration is malformed")
    for key in (
        "model_list_request_sha256",
        "model_list_response_sha256",
        "version_request_sha256",
        "version_response_sha256",
        "tokenizer_request_sha256",
        "tokenizer_response_sha256",
        "receipt_sha256",
    ):
        _require_sha256(receipt[key], f"deployment.{key}")
    for response_key, digest_key in (
        ("model_list_response_utf8", "model_list_response_sha256"),
        ("version_response_utf8", "version_response_sha256"),
        ("tokenizer_response_utf8", "tokenizer_response_sha256"),
    ):
        if not isinstance(receipt[response_key], str) or hashlib.sha256(
            receipt[response_key].encode("utf-8")
        ).hexdigest() != receipt[digest_key]:
            raise RunnerRefusal("deployment raw response body does not match its receipt digest")
    if type(receipt["tokenizer_count"]) is not int or receipt["tokenizer_count"] < 0:
        raise RunnerRefusal("deployment tokenizer count is malformed")
    if (
        receipt["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
        or receipt["generation_calls"] != 0
        or receipt["non_generation_http_calls"] != 3
        or receipt["preflight_call_order"]
        != ["GET /v1/models", "GET /version", "POST /tokenize"]
    ):
        raise RunnerRefusal("deployment receipt does not attest the exact non-generation preflight")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if receipt["receipt_sha256"] != _sha(unsigned):
        raise RunnerRefusal("deployment receipt self-hash mismatch")
    if bindings.get("model_deployment_sha256") != _sha(dict(receipt)):
        raise RunnerRefusal("candidate deployment binding does not match observed preflight receipt")


def _chat_completion_endpoint(deployment: Mapping[str, Any]) -> str:
    """Derive the actual request endpoint from the normalized preflight base."""
    base = deployment.get("endpoint")
    if not isinstance(base, str) or not base:
        raise RuntimeError("deployment receipt lacks a normalized endpoint base")
    return f"{base.rstrip('/')}/v1/chat/completions"


def _validate_metadata(metadata: MeasurementMetadata) -> None:
    if metadata.scorer_role_separation != SCORER_ROLE_SEPARATION:
        raise RunnerRefusal("scorer role-separation declaration is not frozen")
    _require_sha256(metadata.scorer_source_identity, "metadata.scorer_source_identity")
    if not isinstance(metadata.scorer_address, str) or not metadata.scorer_address:
        raise RunnerRefusal("metadata.scorer_address must be nonempty")
    if type(metadata.active_state_byte_ceiling) is not int or metadata.active_state_byte_ceiling <= 0:
        raise RunnerRefusal("active state byte ceiling must be a positive frozen integer")
    if metadata.bindings.get("scorer_sha256") != metadata.scorer_source_identity:
        raise RunnerRefusal("scorer binding does not match the expected scorer source identity")
    _validate_deployment_receipt(metadata.deployment_receipt, metadata.bindings)


def _model_event_call_identity(event: Mapping[str, Any], label: str) -> tuple[int, str, str | None, str]:
    if type(event.get("ordinal")) is not int or event["ordinal"] < 1:
        raise RuntimeError(f"{label}.ordinal must be a positive integer")
    phase, arm = event.get("phase"), event.get("arm")
    if phase not in {"training", "heldout"} or (arm is not None and arm not in ARMS):
        raise RuntimeError(f"{label} call context is malformed")
    digest = event.get("dnrd_request_sha256")
    if not _is_sha256(digest):
        raise RuntimeError(f"{label}.dnrd_request_sha256 is malformed")
    return event["ordinal"], phase, arm, digest


def _validate_model_event_ledger(
    model_events: Sequence[Mapping[str, Any]],
    runner_events: Sequence[Mapping[str, Any]],
    deployment: Mapping[str, Any],
) -> None:
    """Reconcile raw OpenAI-boundary observations with all 160 runner calls."""
    observed: dict[str, Mapping[str, Any]] = {}
    accepted: dict[str, Mapping[str, Any]] = {}
    expected_common = {
        "schema_version",
        "event",
        "ordinal",
        "phase",
        "arm",
        "dnrd_request_sha256",
        "endpoint",
        "model",
        "request_sha256",
        "raw_response_sha256",
        "chat_config",
        "elapsed_nanoseconds",
        "provider_cache_independence",
    }
    for index, item in enumerate(model_events):
        if not isinstance(item, Mapping):
            raise RuntimeError(f"model event {index} is not an object")
        event = dict(item)
        name = event.get("event")
        if name == "CHAT_COMPLETION_OBSERVED":
            expected = expected_common | {"http_status"}
        elif name == "CHAT_COMPLETION_ACCEPTED":
            expected = expected_common | {"usage", "dnrd_response_sha256", "raw_response_utf8"}
        else:
            raise RuntimeError("complete candidate model ledger may contain only observed and accepted calls")
        if set(event) != expected:
            raise RuntimeError("model event exact schema drifted")
        ordinal, phase, arm, digest = _model_event_call_identity(event, "model event")
        if (
            event["schema_version"] != LIVE_EVENT_SCHEMA
            or event["endpoint"] != _chat_completion_endpoint(deployment)
            or event["model"] != deployment["model"]
            or event["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
            or type(event["elapsed_nanoseconds"]) is not int
            or event["elapsed_nanoseconds"] < 0
            or not _is_sha256(event["request_sha256"])
            or not _is_sha256(event["raw_response_sha256"])
            or not isinstance(event["chat_config"], Mapping)
        ):
            raise RuntimeError("model event does not carry a valid raw boundary observation")
        if name == "CHAT_COMPLETION_OBSERVED":
            if type(event["http_status"]) is not int:
                raise RuntimeError("observed model event must carry exact HTTP status")
            target = observed
        else:
            if (
                not _is_sha256(event["dnrd_response_sha256"])
                or not isinstance(event["usage"], Mapping)
                or not isinstance(event["raw_response_utf8"], str)
                or hashlib.sha256(event["raw_response_utf8"].encode("utf-8")).hexdigest()
                != event["raw_response_sha256"]
            ):
                raise RuntimeError("accepted model event lacks a sealed response or usage observation")
            usage = event["usage"]
            if any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in usage.items()):
                raise RuntimeError("accepted model event usage is malformed")
            try:
                raw_completion = json.loads(event["raw_response_utf8"])
                choice = raw_completion["choices"][0]
                raw_usage = raw_completion["usage"]
                response_token = choice["message"]["content"].strip(" \t\r\n")
                response_object = {
                    "response_token": response_token,
                    "input_tokens": raw_usage["prompt_tokens"],
                    "output_tokens": raw_usage["completion_tokens"],
                    "client_cache_hit": False,
                    "server_usage": {
                        key: value
                        for key, value in raw_usage.items()
                        if key not in {"prompt_tokens", "completion_tokens", "total_tokens"}
                        and type(value) is int
                    },
                }
            except (AttributeError, KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
                raise RuntimeError("accepted model event raw completion is not independently parseable") from error
            if (
                raw_completion.get("model") != deployment["model"]
                or type(raw_completion.get("choices")) is not list
                or len(raw_completion["choices"]) != 1
                or type(choice) is not dict
                or type(choice.get("message")) is not dict
                or choice.get("finish_reason") != "stop"
                or not is_response_token(response_token)
                or type(raw_usage.get("prompt_tokens")) is not int
                or type(raw_usage.get("completion_tokens")) is not int
                or raw_usage.get("total_tokens")
                != raw_usage["prompt_tokens"] + raw_usage["completion_tokens"]
                or event["dnrd_response_sha256"] != _sha(response_object)
                or event["usage"]
                != {
                    "prompt_tokens": raw_usage["prompt_tokens"],
                    "completion_tokens": raw_usage["completion_tokens"],
                    **response_object["server_usage"],
                }
            ):
                raise RuntimeError("accepted model event raw completion does not bind frozen response semantics")
            target = accepted
        if digest in target:
            raise RuntimeError("model event ledger repeats one DNRD call identity")
        target[digest] = event
        if (ordinal, phase, arm, digest) != _model_event_call_identity(event, "model event"):
            raise RuntimeError("unreachable inconsistent model event identity")

    expected_calls: dict[str, Mapping[str, Any]] = {}
    for event in runner_events:
        request = event["request"]
        request_value = ModelRequest(
            request["episode_id"],
            request["selected_route_id"],
            request["prompt"],
            request["max_output_tokens"],
            request["ordinal"],
            request["phase"],
            request["arm"],
        )
        digest = model_request_commitment(request_value)
        if digest in expected_calls:
            raise RuntimeError("runner ledger repeats a call identity")
        expected_calls[digest] = event
    if set(observed) != set(expected_calls) or set(accepted) != set(expected_calls):
        raise RuntimeError("model boundary ledger does not exactly cover all runner calls")
    for digest, runner_event in expected_calls.items():
        request = runner_event["request"]
        trace = runner_event["trace"]
        for model_event in (observed[digest], accepted[digest]):
            if (
                model_event["ordinal"] != request["ordinal"]
                or model_event["phase"] != request["phase"]
                or model_event["arm"] != request["arm"]
                or model_event["chat_config"].get("max_tokens") != MAX_OUTPUT_TOKENS
            ):
                raise RuntimeError("model event is not bound to the exact runner call")
        if accepted[digest]["dnrd_response_sha256"] != trace["response_sha256"]:
            raise RuntimeError("accepted model event does not bind the bridge-sealed response")


def _expected_prompt(episode: Mapping[str, Any], route: str) -> str:
    evidence = _selected_evidence(episode, route)
    return f"{episode['prompt']}\nSelected evidence:\n{evidence['evidence_text']}"


def _derive_parity(
    public: Mapping[str, Any],
    runner_events: Sequence[Mapping[str, Any]],
    model_events: Sequence[Mapping[str, Any]],
    deployment: Mapping[str, Any],
    active_state_byte_sizes: Sequence[Mapping[str, int]],
    active_state_byte_ceiling: int,
    recovery_process_ids: Sequence[str],
    subprocess_per_operation: bool,
    arm_mount_sets: Sequence[set[str]],
    evaluation_read_only: Sequence[bool],
) -> dict[str, bool]:
    """Derive every candidate parity bit from concrete observations only."""
    if len(runner_events) != 160 or len(model_events) != 320:
        raise RuntimeError("complete parity requires exact runner and model event ledgers")
    episodes = {
        episode["episode_id"]: episode
        for stream in public["streams"]
        for episode in stream["training"] + stream["heldout"]
    }
    candidate_evidence = True
    labels_hidden = True
    for event in runner_events:
        request = event["request"]
        episode = episodes.get(request["episode_id"])
        if episode is None or request["selected_route_id"] not in episode["candidate_route_ids"]:
            candidate_evidence = False
            continue
        expected_phase = episode["phase"]
        expected_arm = None if expected_phase == "training" else request["arm"]
        if (
            request["phase"] != expected_phase
            or request["arm"] != expected_arm
            or request["prompt"] != _expected_prompt(episode, request["selected_route_id"])
            or request["max_output_tokens"] != MAX_OUTPUT_TOKENS
        ):
            candidate_evidence = False
        labels_hidden = labels_hidden and all(arm not in request["prompt"] for arm in ARMS)
    return {
        # A live boundary can observe only a served model identifier and
        # endpoint.  It cannot establish checkpoint-weight identity.
        "same_served_model_id_and_chat_endpoint": all(
            event["model"] == deployment["model"]
            and event["endpoint"] == _chat_completion_endpoint(deployment)
            for event in model_events
        ),
        "equal_client_dispatched_and_logical_requests": len(runner_events) == 160 and len(model_events) == 320,
        # Provider-reported input-token counts remain in the raw event ledger,
        # but this small repeated-context mechanics diagnostic does not claim
        # input-token parity across different selected-evidence prompts.
        "equal_generation_limits_input_token_parity_not_claimed": all(
            event["chat_config"].get("max_tokens") == MAX_OUTPUT_TOKENS
            for event in model_events
        ),
        "equal_candidate_evidence_universe": candidate_evidence,
        # W0 is an exact zero genesis routing payload and is not padded to
        # masquerade as byte-equal W1.  The observable budget claim is a
        # ceiling, while the intended numeric controls are paired to FULL.
        "all_active_payloads_within_byte_ceiling": bool(active_state_byte_sizes)
        and all(size <= active_state_byte_ceiling for row in active_state_byte_sizes for size in row.values()),
        "full_raw_numeric_payload_bytes_equal": bool(active_state_byte_sizes)
        and all(row["FULL"] == row["RAW_EQUAL_BUDGET"] for row in active_state_byte_sizes),
        "full_deranged_numeric_payload_byte_count_equal": bool(active_state_byte_sizes)
        and all(row["FULL"] == row["BINDING_DERANGED_NUMERIC_PLACEBO"] for row in active_state_byte_sizes),
        "arm_labels_hidden_from_model": labels_hidden,
        # The boolean emitted by a child is not enough on its own.  The
        # production adapter launches one bridge process per operation, and
        # independently supplied process-instance IDs must all differ.
        "fresh_process_recovery_observed": bool(recovery_process_ids)
        and subprocess_per_operation
        and len(set(recovery_process_ids)) == len(recovery_process_ids),
        "distinct_arm_mount_ids": bool(arm_mount_sets) and all(len(mounts) == 4 for mounts in arm_mount_sets),
        "evaluation_read_only_wrt_routing_observed": bool(evaluation_read_only)
        and all(evaluation_read_only),
    }


def _contains_any_canary(value: object, canaries: frozenset[str]) -> bool:
    if isinstance(value, str):
        return any(canary in value for canary in canaries)
    if isinstance(value, Mapping):
        return any(
            _contains_any_canary(key, canaries) or _contains_any_canary(child, canaries)
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_any_canary(child, canaries) for child in value)
    return False


def _derive_overlap_observation(
    public: Mapping[str, Any],
    runner_events: Sequence[Mapping[str, Any]],
    model_events: Sequence[Mapping[str, Any]],
    bridge_state_evidence: Mapping[str, Any],
    declared: Mapping[str, Any],
    *,
    raw_closure_canary_seen: bool,
) -> dict[str, Any]:
    """Derive leakage bits from retained observations, never a hard-coded flag."""

    canaries = training_provenance_canaries(dict(public))
    heldout_events = [event for event in runner_events if event["phase"] == "heldout"]
    heldout_canary_seen = any(
        _contains_any_canary(event["request"], canaries)
        for event in heldout_events
    )
    response_canary_seen = any(
        _contains_any_canary(event["sealed_response"], canaries)
        for event in runner_events
    ) or any(
        event.get("event") == "CHAT_COMPLETION_ACCEPTED"
        and _contains_any_canary(event.get("raw_response_utf8"), canaries)
        for event in model_events
    )
    routing_key_canary_seen = any(
        _contains_any_canary(episode["context_key"], canaries)
        or any(_contains_any_canary(route, canaries) for route in episode["candidate_route_ids"])
        for stream in public["streams"]
        for episode in stream["training"] + stream["heldout"]
    )
    durable_payload_canary_seen = _contains_any_canary(bridge_state_evidence, canaries)
    watermark_detected = (
        heldout_canary_seen
        or response_canary_seen
        or routing_key_canary_seen
        or durable_payload_canary_seen
        or raw_closure_canary_seen
    )
    expected = {
        "normalizer_sha256",
        "training_heldout_exact_overlap",
        "training_heldout_normalized_overlap",
        "prior_item_overlap",
        "leak_detected",
        "watermark_detected",
    }
    if set(declared) != expected:
        raise RunnerRefusal("declared overlap metadata schema drifted")
    result = dict(declared)
    # The fixture audit establishes its declared string-overlap measurements;
    # runtime evidence supplies the two leakage bits rather than trusting the
    # executor's prefilled values.
    result["leak_detected"] = bool(declared["leak_detected"]) or watermark_detected
    result["watermark_detected"] = watermark_detected
    return result


def run_diagnostic(
    public: Mapping[str, Any],
    *,
    private_manifest_commitment: str,
    answerer: Answerer,
    bridge: Bridge,
    scorer: OutcomeScorer,
    metadata: MeasurementMetadata,
    inconclusive_path: Path | None = None,
    event_sink: EventSink | None = None,
    model_event_ledger_provider: Callable[[], Sequence[Mapping[str, Any]]] | None = None,
    closure_exporter: BridgeMountClosureExporter | None = None,
) -> RunnerResult:
    """Run repeated-context tabular routing mechanics, never an efficacy test.

    The runner API and implemented code path receive only public fixture
    material plus a private-manifest commitment; they do not receive, read, or
    parse private answers or correct-route bindings.  Same-UID/OS-enforced
    independence from the scorer process is not established by this design.
    """
    try:
        audit_public_manifest(dict(public))
        if not _is_sha256(private_manifest_commitment):
            raise RunnerRefusal("private manifest commitment must be a SHA-256")
        if public["private_manifest_commitment"] != private_manifest_commitment:
            raise RunnerRefusal("private manifest commitment does not match public fixture")
        _validate_metadata(metadata)
        if model_event_ledger_provider is None:
            raise RunnerRefusal("a complete DNRD candidate requires an actual model-boundary event ledger")
        if closure_exporter is None:
            raise RunnerRefusal("a complete DNRD candidate requires a raw bridge mount-closure exporter")
        if len(public["streams"]) != 4 or any(len(stream["training"]) != 8 or len(stream["heldout"]) != 8 for stream in public["streams"]):
            raise RunnerRefusal("DNRD requires exactly 4 streams of 8+8 episodes")
    except (ManifestError, KeyError, TypeError) as error:
        raise RunnerRefusal(str(error)) from error

    calls = cache_hits = 0
    usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
    runner_events: list[Mapping[str, Any]] = []
    active_state_byte_sizes: list[dict[str, int]] = []
    recovery_process_ids: list[str] = []
    arm_mount_sets: list[set[str]] = []
    evaluation_read_only: list[bool] = []
    bridge_state_streams: list[Mapping[str, Any]] = []

    def emit(event: Mapping[str, Any]) -> None:
        frozen = dict(event)
        runner_events.append(frozen)
        if event_sink is not None:
            event_sink(frozen)

    def count_response(reply: ModelReply | None) -> None:
        nonlocal calls, cache_hits
        calls += 1
        if reply is not None:
            cache_hits += int(reply.client_cache_hit)
            _record_usage(usage, reply)
            if reply.client_cache_hit:
                raise RuntimeError("client-reported cache hit violates no-cache diagnostic execution")

    def require_fresh_recovery(recovery: RecoveryObservation, label: str) -> None:
        _validate_recovery_observation(recovery)
        if not recovery.recovered or not recovery.fresh_process:
            raise RuntimeError(f"bridge failed fresh durable recovery for {label}")
        if recovery.process_instance_id in recovery_process_ids:
            raise RuntimeError("bridge reused a recovery process-instance identity")
        recovery_process_ids.append(recovery.process_instance_id)

    try:
        stream_work: list[dict[str, Any]] = []
        for stream in public["streams"]:
            initial = bridge.initialize(stream)
            _verify_initialization(initial, stream)
            stream_work.append({"stream": stream, "initial": initial, "w0": initial.w0, "w1": initial.w1, "trusted_mount_ids": {initial.w0.mount_id, initial.w1.mount_id}, "training_update_records": [], "receipts": [], "outcomes": [], "traces": []})

        # The common treatment is globally complete before *any* arm observation.
        for work in stream_work:
            stream, w1 = work["stream"], work["w1"]
            for episode in stream["training"]:
                route = episode["forced_route_id"]
                if w1.mount_id not in work["trusted_mount_ids"]:
                    raise RunnerRefusal("unbacked synthetic state may not enter SEAL_TRACE")
                _require_mount_role(w1, "FULL", "training state")
                pre_state = w1
                request, _, sealed, trace, outcome = _observe_call(
                    answerer,
                    bridge,
                    scorer,
                    w1,
                    episode,
                    route,
                    private_manifest_commitment,
                    metadata,
                    ordinal=calls + 1,
                    phase="training",
                    arm=None,
                    on_response=count_response,
                )
                w1, receipt = bridge.apply_outcome(w1, trace, outcome)
                _require_mount_role(w1, "FULL", "post-credit training state")
                work["trusted_mount_ids"].add(w1.mount_id)
                try:
                    raw_record = {"episode_id": episode["episode_id"], "context_key": episode["context_key"], "selected_route_id": route, "reward": outcome["reward"], "trace_id": trace["trace_id"], "outcome_digest": outcome["outcome_digest"]}
                except KeyError as error:
                    raise RuntimeError("bridge/scorer omitted a required RAW provenance field") from error
                work["training_update_records"].append(raw_record)
                work["traces"].append(trace); work["outcomes"].append(outcome); work["receipts"].append(receipt)
                emit({
                    "schema_version": "hswm-dnrd-runner-event/v1",
                    "ordinal": calls,
                    "phase": "training",
                    "arm": None,
                    "request": _request_object(request),
                    "sealed_response": sealed,
                    "trace": trace,
                    "scorer_outcome": outcome,
                    "credit_receipt": receipt,
                    "route_digest_sha256": _route_digest(pre_state, episode),
                    "route_replay": None,
                })
            work["w1"] = w1
        if calls != 32:
            raise RuntimeError(f"common training call arithmetic drifted: {calls}")

        stream_runs: list[dict[str, Any]] = []
        pending_post_evaluations: list[dict[str, Any]] = []
        for work in stream_work:
            stream, w0, w1 = work["stream"], work["w0"], work["w1"]
            w0_recovery = bridge.recover(w0)
            w1_recovery = bridge.recover(w1)
            for recovery in (w0_recovery, w1_recovery):
                require_fresh_recovery(recovery, "pre-evaluation W0/FULL")
                work["trusted_mount_ids"].add(recovery.state.mount_id)
            _require_mount_role(w0_recovery.state, "NO_MEMORY_ROLLBACK", "recovered W0")
            _require_mount_role(w1_recovery.state, "FULL", "recovered FULL")
            recovered_w1 = w1_recovery.state
            raw_expected = _expected_raw_scores(w0_recovery.state, work["training_update_records"], stream)
            if recovered_w1.scores != raw_expected:
                raise RuntimeError("trained FULL routing scores do not equal independent frozen RAW replay")
            deranged_expected = _expected_deranged_scores(recovered_w1, stream["matched_derangement"])
            _require_mount_role(w0_recovery.state, "NO_MEMORY_ROLLBACK", "RAW materialization source")
            _require_mount_role(recovered_w1, "FULL", "DERANGED materialization source")
            raw_material = bridge.materialize_control(w0_recovery.state, stream["stream_id"], "RAW_EQUAL_BUDGET", work["training_update_records"], stream["matched_derangement"])
            deranged_material = bridge.materialize_control(recovered_w1, stream["stream_id"], "BINDING_DERANGED_NUMERIC_PLACEBO", work["training_update_records"], stream["matched_derangement"])
            if raw_material.state.mount_id == recovered_w1.mount_id or deranged_material.state.mount_id == recovered_w1.mount_id:
                raise RuntimeError("control materialization reused the FULL durable mount")
            _require_mount_role(raw_material.state, "RAW_EQUAL_BUDGET", "materialized RAW control")
            _require_mount_role(deranged_material.state, "BINDING_DERANGED_NUMERIC_PLACEBO", "materialized DERANGED control")
            raw_recovery, deranged_recovery = bridge.recover(raw_material.state), bridge.recover(deranged_material.state)
            for recovery in (raw_recovery, deranged_recovery):
                require_fresh_recovery(recovery, "pre-evaluation control")
                work["trusted_mount_ids"].add(recovery.state.mount_id)
            raw, deranged = raw_recovery.state, deranged_recovery.state
            _require_mount_role(raw, "RAW_EQUAL_BUDGET", "recovered RAW control")
            _require_mount_role(deranged, "BINDING_DERANGED_NUMERIC_PLACEBO", "recovered DERANGED control")
            if raw.scores != raw_expected:
                raise RuntimeError("bridge RAW materialization does not equal frozen independent record replay")
            if deranged.scores != deranged_expected:
                raise RuntimeError("bridge DERANGED materialization does not equal exact public binding map")
            arm_states = {"FULL": recovered_w1, "NO_MEMORY_ROLLBACK": w0_recovery.state, "RAW_EQUAL_BUDGET": raw, "BINDING_DERANGED_NUMERIC_PLACEBO": deranged}
            pre_recoveries = {
                "FULL": w1_recovery,
                "NO_MEMORY_ROLLBACK": w0_recovery,
                "RAW_EQUAL_BUDGET": raw_recovery,
                "BINDING_DERANGED_NUMERIC_PLACEBO": deranged_recovery,
            }
            mounts = {state.mount_id for state in arm_states.values()}
            if len(mounts) != len(ARMS):
                raise RuntimeError("evaluation arms do not occupy separate bridge-owned mounts")
            arm_mount_sets.append(mounts)
            pre_entries = {arm: _bridge_state_entry(pre_recoveries[arm]) for arm in ARMS}
            if pre_entries["FULL"]["routing_payload_utf8"] != pre_entries["RAW_EQUAL_BUDGET"]["routing_payload_utf8"]:
                raise RuntimeError("FULL and RAW durable routing payload bytes differ")
            derangement = _derangement_observation(recovered_w1, deranged, stream)
            if not (
                derangement["fixed_point_count"] == 0
                and derangement["preserves_update_multiset"]
                and derangement["preserves_precision"]
                and derangement["preserves_l1_l2_norms"]
                and derangement["preserves_routing_payload_byte_count"]
                and derangement["routing_payload_content_differs"]
                and pre_entries["FULL"]["routing_payload_bytes"]
                == pre_entries["BINDING_DERANGED_NUMERIC_PLACEBO"]["routing_payload_bytes"]
                and pre_entries["FULL"]["routing_payload_utf8"]
                != pre_entries["BINDING_DERANGED_NUMERIC_PLACEBO"]["routing_payload_utf8"]
            ):
                raise RuntimeError("DERANGED control does not preserve only the frozen numeric budget/norm boundary")
            active_state_byte_sizes.append(
                {
                    arm: int(pre_entries[arm]["routing_payload_bytes"])
                    for arm in ARMS
                }
            )
            bridge_stream_evidence: dict[str, Any] = {
                "stream_id": stream["stream_id"],
                "pre_evaluation": {
                    "arms": {arm: pre_entries[arm] for arm in ARMS},
                    "fresh_recovery": {
                        arm: _recovery_evidence(pre_recoveries[arm]) for arm in ARMS
                    },
                },
            }
            bridge_state_streams.append(bridge_stream_evidence)
            w0_mismatches = [episode["episode_id"] for episode in stream["heldout"] if (_select(w0, episode), _route_digest(w0, episode)) != (_select(w0_recovery.state, episode), _route_digest(w0_recovery.state, episode))]
            probes: list[dict[str, Any]] = []
            for episode in stream["heldout"]:
                initial_w0_route, initial_w0_digest = _select(w0, episode), _route_digest(w0, episode)
                rollback_route, rollback_digest = _select(w0_recovery.state, episode), _route_digest(w0_recovery.state, episode)
                restore_route, restore_digest = _select(recovered_w1, episode), _route_digest(recovered_w1, episode)
                route_replay = {
                    "initial_w0": {
                        "selected_route_id": initial_w0_route,
                        "route_digest_sha256": initial_w0_digest,
                    },
                    "rollback": {
                        "selected_route_id": rollback_route,
                        "route_digest_sha256": rollback_digest,
                    },
                    "restore": {
                        "selected_route_id": restore_route,
                        "route_digest_sha256": restore_digest,
                    },
                }
                observations: dict[str, Any] = {}
                for arm in episode["arm_order"]:
                    state = arm_states[arm]
                    if state.mount_id not in work["trusted_mount_ids"]:
                        raise RunnerRefusal("unbacked synthetic state may not enter evaluation SEAL_TRACE")
                    _require_mount_role(state, arm, "heldout evaluation state")
                    route = _select(state, episode)
                    request, _, sealed, trace, outcome = _observe_call(
                        answerer,
                        bridge,
                        scorer,
                        state,
                        episode,
                        route,
                        private_manifest_commitment,
                        metadata,
                        ordinal=calls + 1,
                        phase="heldout",
                        arm=arm,
                        on_response=count_response,
                    )
                    # Evaluation is read-only: outcome is sealed and ledgered but
                    # is never fed back into any shared or durable arm state.
                    work["traces"].append(trace); work["outcomes"].append(outcome)
                    route_digest = _route_digest(state, episode)
                    emit({
                        "schema_version": "hswm-dnrd-runner-event/v1",
                        "ordinal": calls,
                        "phase": "heldout",
                        "arm": arm,
                        "request": _request_object(request),
                        "sealed_response": sealed,
                        "trace": trace,
                        "scorer_outcome": outcome,
                        "credit_receipt": None,
                        "route_digest_sha256": route_digest,
                        "route_replay": route_replay,
                    })
                    observations[arm] = {"selected_route_id": route, "route_digest_sha256": route_digest, "utility": int(outcome["reward"])}
                probes.append({"probe_id": episode["episode_id"], "arms": observations, "rollback": {"selected_route_id": rollback_route, "route_digest_sha256": rollback_digest}, "restore": {"selected_route_id": restore_route, "route_digest_sha256": restore_digest}})
            pending_post_evaluations.append(
                {
                    "work": work,
                    "stream": stream,
                    "w0_recovery": w0_recovery,
                    "w1_recovery": w1_recovery,
                    "recovered_w1": recovered_w1,
                    "pre_recoveries": pre_recoveries,
                    "arm_states": arm_states,
                    "bridge_stream_evidence": bridge_stream_evidence,
                    "raw_material": raw_material,
                    "deranged_material": deranged_material,
                    "derangement": derangement,
                    "w0_mismatches": w0_mismatches,
                    "probes": probes,
                }
            )
        if calls != 160:
            raise RuntimeError(f"frozen DNRD call arithmetic drifted: {calls}")
        # Only after every one of the 128 heldout calls has completed do we
        # fresh-recover all sixteen arm mounts.  This catches a mutation on a
        # final arm trace that no later model call would otherwise expose.
        for pending in pending_post_evaluations:
            arm_states = pending["arm_states"]
            pre_recoveries = pending["pre_recoveries"]
            post_recoveries = {arm: bridge.recover(arm_states[arm]) for arm in ARMS}
            for arm, recovery in post_recoveries.items():
                require_fresh_recovery(recovery, f"post-evaluation {arm}")
                _require_mount_role(recovery.state, arm, f"post-evaluation {arm}")
                if not _same_routing_state(pre_recoveries[arm], recovery):
                    raise RuntimeError("evaluation changed routing state rather than only appending trace evidence")
            evaluation_read_only.append(
                all(_same_routing_state(pre_recoveries[arm], post_recoveries[arm]) for arm in ARMS)
            )
            bridge_stream_evidence = pending["bridge_stream_evidence"]
            bridge_stream_evidence["post_evaluation"] = {
                "arms": {arm: _bridge_state_entry(post_recoveries[arm]) for arm in ARMS},
                "fresh_recovery": {arm: _recovery_evidence(post_recoveries[arm]) for arm in ARMS},
            }
            work = pending["work"]
            stream = pending["stream"]
            w0_recovery = pending["w0_recovery"]
            w1_recovery = pending["w1_recovery"]
            recovered_w1 = pending["recovered_w1"]
            local_hash = _sha({"traces": work["traces"], "outcomes": work["outcomes"], "receipts": work["receipts"]})
            stream_runs.append({"stream_id": stream["stream_id"], "w0": _state_observation(w0_recovery.state, owner=False), "w1": _state_observation(recovered_w1, owner=True), "clean_process_recovery": {"recovered": w1_recovery.recovered, "fresh_process": w1_recovery.fresh_process, "journal_sha256": w1_recovery.journal_sha256, "recovered_state_sha256": recovered_w1.state_sha256, "process_instance_id": w1_recovery.process_instance_id}, "local_v2_linkage": {"experimental_schema_id": "hswm:dnrd:v1", "owner_id": recovered_w1.owner_id, "outcome_ledger_sha256": _sha(work["outcomes"]), "credit_ledger_sha256": _sha(work["receipts"]), "local_structural_receipt_sha256": _sha({"local": local_hash, "init": work["initial"].initialization_receipt_sha256, "raw": pending["raw_material"].receipt_sha256, "deranged": pending["deranged_material"].receipt_sha256}), "transition_evidence_sha256": _sha(work["traces"]), "local_only": True, "schema_owner_matches": recovered_w1.owner_id == work["w1"].owner_id, "outcome_present": bool(work["outcomes"]), "reference_grant_matched_not_canonical_permit": True}, "derangement": pending["derangement"], "w0_replay_mismatch_probe_ids": pending["w0_mismatches"], "probes": pending["probes"]})
        assert model_event_ledger_provider is not None  # pre-call contract above
        supplied_model_events = tuple(dict(event) for event in model_event_ledger_provider())
        _validate_model_event_ledger(
            supplied_model_events,
            runner_events,
            metadata.deployment_receipt,
        )
        runner_ledger_sha256 = _ledger_sha256(runner_events)
        model_ledger_sha256 = _ledger_sha256(supplied_model_events)
        bridge_state_evidence = {
            "schema_version": BRIDGE_STATE_EVIDENCE_SCHEMA,
            "streams": bridge_state_streams,
        }
        bridge_state_evidence_sha256 = _sha(bridge_state_evidence)
        closure_plan = _bridge_mount_closure_plan(
            bridge_state_evidence,
            bridge_state_evidence_sha256,
        )
        assert closure_exporter is not None  # pre-call contract above
        canaries = training_provenance_canaries(dict(public))
        closure_export = closure_exporter.export(
            closure_plan,
            forbidden_markers=canaries,
        )
        bridge_mount_closure_sha256 = closure_export.artifact_sha256
        _require_sha256(
            bridge_mount_closure_sha256,
            "bridge mount closure exact artifact SHA-256",
        )
        overlap = _derive_overlap_observation(
            public,
            runner_events,
            supplied_model_events,
            bridge_state_evidence,
            metadata.overlap,
            raw_closure_canary_seen=closure_export.watermark_detected,
        )
        parity = _derive_parity(
            public,
            runner_events,
            supplied_model_events,
            metadata.deployment_receipt,
            active_state_byte_sizes,
            metadata.active_state_byte_ceiling,
            recovery_process_ids,
            isinstance(bridge, SubprocessJsonBridge),
            arm_mount_sets,
            evaluation_read_only,
        )
        bindings = dict(metadata.bindings)
        bindings["event_ledger_sha256"] = runner_ledger_sha256
        bindings["model_event_ledger_sha256"] = model_ledger_sha256
        bindings["bridge_state_evidence_sha256"] = bridge_state_evidence_sha256
        bindings["bridge_mount_closure_sha256"] = bridge_mount_closure_sha256
        candidate = {"schema_version": CANDIDATE_SCHEMA, "experiment_id": EXPERIMENT_ID, "bindings": bindings, "chronology": dict(metadata.chronology), "overlap": overlap, "parity": parity, "call_ledger": {"common_training_model_calls": 32, "evaluation_model_calls": 128, "client_dispatched_generation_requests": 160, "logical_model_calls": 160, "route_only_model_calls": 0, "scorer_model_calls": 0, "retries": 0, "client_cache_hits": 0, "post_first_call_operational_failure": False}, "streams": stream_runs}
        return RunnerResult(
            candidate,
            None,
            cache_hits,
            usage,
            runner_event_ledger_sha256=runner_ledger_sha256,
            model_event_ledger_sha256=model_ledger_sha256,
            bridge_state_evidence=bridge_state_evidence,
            bridge_state_evidence_sha256=bridge_state_evidence_sha256,
            bridge_mount_closure_sha256=bridge_mount_closure_sha256,
        )
    except Exception as error:
        if calls == 0:
            raise RunnerRefusal(f"pre-first-call refusal: {error}") from error
        receipt = _inconclusive(calls, cache_hits, error)
        if inconclusive_path is not None:
            inconclusive_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        partial_runner_ledger_sha256 = _ledger_sha256(runner_events)
        partial_model_ledger_sha256: str | None = None
        if model_event_ledger_provider is not None:
            try:
                partial_model_ledger_sha256 = _ledger_sha256(
                    tuple(dict(event) for event in model_event_ledger_provider())
                )
            except Exception:
                # The occurrence remains inconclusive; an unavailable event
                # collector must not be silently replaced with a fake ledger.
                partial_model_ledger_sha256 = None
        return RunnerResult(
            None,
            receipt,
            cache_hits,
            usage,
            runner_event_ledger_sha256=partial_runner_ledger_sha256,
            model_event_ledger_sha256=partial_model_ledger_sha256,
        )
