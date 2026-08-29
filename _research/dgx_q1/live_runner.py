"""Single fail-closed POST path for a separately preregistered live Q1.

The runner owns a fresh, non-resumable evidence root. It reconstructs all 24
requests, makes the frozen 96-call order exactly once, and records one typed
lease attestation around every POST. Qualification is decided only by the
separate independent verifier.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import fcntl
from hashlib import sha256
from http.client import HTTPConnection
import os
from pathlib import Path
import re
import socket
import tempfile
from typing import Any

from _research.dnrd5.canonical_json import (
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)
from _research.dgx_q1.live_protocol import (
    LiveQ1CaseMaterial,
    LiveQ1Refusal,
    NAMESPACE,
    RUNNER_VERSION,
    bind_case_material,
    loopback_q1_target,
    validate_boundary_attestation,
    validate_declared_isolation_contract,
    validate_live_envelope,
    validate_live_q1_plan,
    validate_live_q1_start_marker,
)
from _research.dgx_q1.live_launcher import LiveQ1Lease


LEDGER_SCHEMA = "hswm-dgx-q1-live-attempt-ledger/v1"
ZERO = "0" * 64
_MAX_BLOB_BYTES = 16 * 1024 * 1024
_ATTEMPT = re.compile(r"^DNRD5-Q1L-([0-9]{3})-R(00[1-4])$")


@dataclass(frozen=True, slots=True)
class LiveObservation:
    status: int
    body: bytes
    response_content_type: str | None = None
    provider_request_id: str | None = None


BoundaryAttester = Callable[[str, str | None, int], bytes]
Transport = Callable[[str, bytes, int], LiveObservation]


def _descriptor(raw: bytes) -> dict[str, Any]:
    return {"sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _put(root: Path, raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw) > _MAX_BLOB_BYTES:
        raise LiveQ1Refusal("evidence blob is not bounded exact bytes")
    digest = sha256(raw).hexdigest()
    target = root / "content" / digest
    if target.exists():
        if not target.is_file() or target.read_bytes() != raw:
            raise LiveQ1Refusal("content-address collision")
        return _descriptor(raw)
    descriptor, temporary = tempfile.mkstemp(prefix=".q1-live-", dir=root / "content")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != raw:
                raise LiveQ1Refusal("content-address collision")
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    _sync_directory(root / "content")
    return _descriptor(raw)


def _append(root: Path, core: dict[str, Any]) -> dict[str, Any]:
    ledger = root / "q1_live_ledger.jsonl"
    descriptor = os.open(ledger, os.O_RDWR)
    with os.fdopen(descriptor, "r+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        raw = handle.read()
        previous = ZERO
        ordinal = 1
        if raw:
            if not raw.endswith(b"\n"):
                raise LiveQ1Refusal("ledger framing breach")
            for line in raw[:-1].split(b"\n"):
                row = parse_canonical(line)
                body = {key: value for key, value in row.items() if key != "record_sha256"}
                if (
                    type(row) is not dict
                    or row.get("ordinal") != ordinal
                    or row.get("previous_record_sha256") != previous
                    or row.get("record_sha256") != canonical_sha256(body)
                ):
                    raise LiveQ1Refusal("ledger hash-chain breach")
                previous = row["record_sha256"]
                ordinal += 1
        row = {**core, "ordinal": ordinal, "previous_record_sha256": previous}
        row["record_sha256"] = canonical_sha256(row)
        handle.seek(0, os.SEEK_END)
        handle.write(canonical_bytes(row) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    _sync_directory(root)
    return row


def _loopback_endpoint(endpoint: str) -> tuple[str, int, str]:
    target = loopback_q1_target(endpoint)
    return "127.0.0.1", int(target.rsplit(":", 1)[1]), "/v1/chat/completions"


def _post_loopback(endpoint: str, request: bytes, maximum: int) -> LiveObservation:
    host, port, path = _loopback_endpoint(endpoint)
    if type(request) is not bytes or not request or len(request) > 4 * 1024 * 1024:
        raise LiveQ1Refusal("request bytes are not bounded")
    connection = HTTPConnection(host, port, timeout=120)
    try:
        connection.request(
            "POST",
            path,
            body=request,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Content-Length": str(len(request)),
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        content_length = response.getheader("Content-Length")
        if content_length is not None and (
            not content_length.isdigit() or int(content_length) > maximum
        ):
            raise LiveQ1Refusal("response content-length exceeds bound")
        body = response.read(maximum + 1)
        if len(body) > maximum:
            raise LiveQ1Refusal("response body exceeds bound")
        return LiveObservation(
            response.status,
            body,
            response.getheader("Content-Type"),
            response.getheader("X-Request-Id") or response.getheader("X-Request-ID"),
        )
    except (OSError, socket.error) as error:
        raise LiveQ1Refusal("single loopback POST failed") from error
    finally:
        connection.close()


def _bounded_optional_text(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or len(value.encode("utf-8", errors="strict")) > 512
        or any(ord(character) < 32 and character != "\t" for character in value)
    ):
        raise LiveQ1Refusal(f"{label} is not bounded text")
    return value


def _semantic_identities(
    identity_bytes: Mapping[str, bytes],
    plan: dict[str, Any],
) -> tuple[str, str]:
    expected = set(plan["identities"])
    if set(identity_bytes) != expected:
        raise LiveQ1Refusal("identity blob key set drifted")
    if any(
        type(identity_bytes[name]) is not bytes
        or sha256(identity_bytes[name]).hexdigest() != plan["identities"][name]
        for name in expected
    ):
        raise LiveQ1Refusal("identity blob hash binding drifted")
    try:
        endpoint_identity = parse_canonical(identity_bytes["endpoint_sha256"])
        model_identity = parse_canonical(identity_bytes["model_identity_sha256"])
        tls_identity = parse_canonical(identity_bytes["tls_identity_sha256"])
        declared = parse_canonical(identity_bytes["declared_isolation_contract_sha256"])
        snapshot = parse_canonical(identity_bytes["model_snapshot_manifest_sha256"])
        runtime = parse_canonical(identity_bytes["runtime_identity_sha256"])
    except Exception as error:
        raise LiveQ1Refusal("identity blob is not canonical JSON") from error
    if (
        endpoint_identity
        != {
            "schema_version": "hswm-dgx-q1-endpoint-identity/v1",
            "endpoint": endpoint_identity.get("endpoint")
            if type(endpoint_identity) is dict
            else None,
            "method": "POST",
            "transport": "LOOPBACK_HTTP_NO_TLS",
        }
        or type(endpoint_identity.get("endpoint")) is not str
    ):
        raise LiveQ1Refusal("endpoint identity drifted")
    endpoint = endpoint_identity["endpoint"]
    _loopback_endpoint(endpoint)
    if (
        type(model_identity) is not dict
        or set(model_identity)
        != {
            "schema_version",
            "model",
            "repository",
            "revision",
            "snapshot_manifest_sha256",
        }
        or model_identity["schema_version"] != "hswm-dgx-q1-model-identity/v1"
        or type(model_identity["model"]) is not str
        or not model_identity["model"]
        or type(model_identity["repository"]) is not str
        or not model_identity["repository"]
        or type(model_identity["revision"]) is not str
        or re.fullmatch(r"[0-9a-f]{40}", model_identity["revision"]) is None
        or model_identity["snapshot_manifest_sha256"]
        != plan["identities"]["model_snapshot_manifest_sha256"]
    ):
        raise LiveQ1Refusal("model identity drifted")
    if tls_identity != {
        "schema_version": "hswm-dgx-q1-tls-identity/v1",
        "endpoint_scheme": "http",
        "tls": "NOT_APPLICABLE_LOOPBACK_ONLY",
    }:
        raise LiveQ1Refusal("TLS identity drifted")
    validate_declared_isolation_contract(
        identity_bytes["declared_isolation_contract_sha256"],
        target=loopback_q1_target(endpoint),
    )
    if (
        type(snapshot) is not dict
        or snapshot.get("schema_version")
        != "hswm-dgx-q1-model-snapshot-manifest/v1"
        or snapshot.get("repository") != model_identity["repository"]
        or snapshot.get("revision") != model_identity["revision"]
        or type(snapshot.get("file_count")) is not int
        or snapshot["file_count"] <= 0
        or type(snapshot.get("files")) is not list
        or len(snapshot["files"]) != snapshot["file_count"]
    ):
        raise LiveQ1Refusal("model snapshot manifest identity drifted")
    if (
        type(runtime) is not dict
        or runtime.get("schema_version") != "hswm-dgx-q1-runtime-identity/v1"
        or runtime.get("served_model") != model_identity["model"]
        or runtime.get("endpoint") != endpoint
        or runtime.get("model_revision") != model_identity["revision"]
        or runtime.get("model_snapshot_manifest_sha256")
        != plan["identities"]["model_snapshot_manifest_sha256"]
    ):
        raise LiveQ1Refusal("runtime identity drifted")
    return endpoint, model_identity["model"]


class LiveQ1Runner:
    """Fresh finite runner; entering execution permanently consumes the root."""

    def __init__(
        self,
        root: Path,
        plan_raw: bytes,
        marker_raw: bytes,
        corpus_manifest_raw: bytes,
        materials: Sequence[LiveQ1CaseMaterial],
        identity_bytes: Mapping[str, bytes],
        provenance_bytes: Mapping[str, bytes],
        root_genesis_raw: bytes,
        freeze_closure_raw: bytes,
        startup_attestation_raw: bytes | None = None,
        boundary_attester: BoundaryAttester | None = None,
        *,
        consumption_root: Path,
        transport_for_testing: Transport | None = None,
        lease: LiveQ1Lease | None = None,
        fixture_mode: bool = False,
        max_response_bytes: int = 1_048_576,
    ) -> None:
        plan = validate_live_q1_plan(plan_raw)
        validate_live_q1_start_marker(marker_raw, plan_raw)
        if (
            not isinstance(root, Path)
            or root.exists()
            or not root.parent.is_dir()
            or type(corpus_manifest_raw) is not bytes
            or type(root_genesis_raw) is not bytes
            or type(max_response_bytes) is not int
            or not 1 <= max_response_bytes <= _MAX_BLOB_BYTES
        ):
            raise LiveQ1Refusal("live Q1 root or execution boundary drifted")
        if lease is not None:
            if (
                fixture_mode
                or transport_for_testing is not None
                or startup_attestation_raw is not None
                or boundary_attester is not None
                or type(lease) is not LiveQ1Lease
                or not lease.is_active
                or lease.startup_attestation_raw is None
            ):
                raise LiveQ1Refusal("production runner requires one active non-fixture lease")
            startup_attestation_raw = lease.startup_attestation_raw
            boundary_attester = lease.attest
        elif (
            not fixture_mode
            or startup_attestation_raw is None
            or not callable(boundary_attester)
            or transport_for_testing is None
        ):
            raise LiveQ1Refusal("injected transport/attestation requires explicit fixture mode")
        if type(freeze_closure_raw) is not bytes:
            raise LiveQ1Refusal("freeze closure bytes are required")
        try:
            freeze_closure = parse_canonical(freeze_closure_raw)
        except Exception as error:
            raise LiveQ1Refusal("freeze closure is not canonical JSON") from error
        if (
            type(freeze_closure) is not dict
            or set(freeze_closure) != {"schema_version", "namespace", "artifacts"}
            or freeze_closure.get("schema_version")
            != "hswm-dgx-q1-live-preregistration-freeze/v1"
            or freeze_closure.get("namespace") != NAMESPACE
            or type(freeze_closure.get("artifacts")) is not list
            or not freeze_closure["artifacts"]
        ):
            raise LiveQ1Refusal("freeze closure semantic shape drifted")
        try:
            manifest = parse_canonical(corpus_manifest_raw)
        except Exception as error:
            raise LiveQ1Refusal("corpus manifest is not canonical JSON") from error
        if (
            sha256(corpus_manifest_raw).hexdigest() != plan["corpus_manifest_sha256"]
            or type(manifest) is not dict
            or set(manifest)
            != {
                "schema_version",
                "namespace",
                "q0_public_synthetic_manifest",
                "corpus",
            }
            or manifest.get("schema_version")
            != "hswm-dgx-q1-live-public-synthetic-corpus/v1"
            or manifest.get("namespace") != NAMESPACE
            or type(manifest.get("q0_public_synthetic_manifest")) is not dict
            or manifest["q0_public_synthetic_manifest"].get("classification")
            != "PUBLIC_SYNTHETIC_QUALIFICATION_ONLY_NO_CORRECTNESS_EVALUATOR"
            or manifest.get("corpus") != plan["corpus"]
            or sha256(root_genesis_raw).hexdigest()
            != plan["evidence_root_genesis_sha256"]
        ):
            raise LiveQ1Refusal("corpus manifest or root genesis binding drifted")
        endpoint, model = _semantic_identities(identity_bytes, plan)
        expected_provenance = {
            "source_ci_receipt_sha256": plan["source"]["ci_receipt_sha256"],
            "verifier_ci_receipt_sha256": plan["verifier"]["source"][
                "ci_receipt_sha256"
            ],
            "verifier_build_output_sha256": plan["verifier"]["build_output_sha256"],
        }
        if set(provenance_bytes) != set(expected_provenance) or any(
            type(provenance_bytes[name]) is not bytes
            or sha256(provenance_bytes[name]).hexdigest() != digest
            for name, digest in expected_provenance.items()
        ):
            raise LiveQ1Refusal("source/verifier provenance binding drifted")
        if (
            type(materials) not in {tuple, list}
            or len(materials) != 24
            or any(type(item) is not LiveQ1CaseMaterial for item in materials)
        ):
            raise LiveQ1Refusal("live Q1 requires 24 exact case materials")
        by_id = {item.case_id: item for item in materials}
        cases = {item["case_id"]: item for item in plan["corpus"]}
        if len(by_id) != 24 or set(by_id) != set(cases):
            raise LiveQ1Refusal("case material set drifted")
        requests = {
            case_id: bind_case_material(cases[case_id], by_id[case_id], model)
            for case_id in cases
        }
        declared_isolation_raw = identity_bytes[
            "declared_isolation_contract_sha256"
        ]
        target = loopback_q1_target(endpoint)
        startup_attestation = validate_boundary_attestation(
            startup_attestation_raw,
            plan_raw,
            phase="STARTUP",
            attempt_id=None,
            completed_attempts=0,
            declared_isolation_raw=declared_isolation_raw,
            target=target,
        )

        root.mkdir(mode=0o700)
        (root / "content").mkdir(mode=0o700)
        (root / "q1_live_ledger.jsonl").touch(mode=0o600)
        (root / "dispatch.lock").touch(mode=0o600)
        _sync_directory(root / "content")
        _sync_directory(root)
        for raw in (
            plan_raw,
            marker_raw,
            corpus_manifest_raw,
            root_genesis_raw,
            freeze_closure_raw,
            startup_attestation_raw,
            *identity_bytes.values(),
            *provenance_bytes.values(),
        ):
            _put(root, raw)
        for item in materials:
            for raw in (
                item.instruction_bytes,
                item.model_input_bytes,
                item.response_schema_bytes,
                item.rng_bytes,
                requests[item.case_id],
            ):
                _put(root, raw)
        self._marker_core = {
                "schema_version": LEDGER_SCHEMA,
                "namespace": NAMESPACE,
                "record_type": "LIVE_MARKER",
                "evidence_mode": "LIVE_LEASE" if lease is not None else "TEST_FIXTURE_INJECTED",
                "plan": _descriptor(plan_raw),
                "marker": _descriptor(marker_raw),
                "corpus_manifest": _descriptor(corpus_manifest_raw),
                "root_genesis": _descriptor(root_genesis_raw),
                "freeze_closure": _descriptor(freeze_closure_raw),
                "identities": {
                    name: _descriptor(raw) for name, raw in sorted(identity_bytes.items())
                },
                "provenance": {
                    name: _descriptor(raw)
                    for name, raw in sorted(provenance_bytes.items())
                },
                "startup_boundary_attestation": _descriptor(startup_attestation_raw),
                "all_request_blobs_durable": True,
                "request_sha256s": [
                    case["request_sha256"] for case in plan["corpus"]
                ],
                "retry": "NONE",
                "terminal": (
                    "ALL_24_EXACT_REQUEST_BLOBS_FSYNCED_BEFORE_FIRST_LIVE_START"
                ),
        }
        self.root = root
        self.plan_raw = plan_raw
        self.marker_raw = marker_raw
        self.corpus_manifest_raw = corpus_manifest_raw
        self.root_genesis_raw = root_genesis_raw
        self.freeze_closure_raw = freeze_closure_raw
        self.startup_attestation_raw = startup_attestation_raw
        self.plan = plan
        self.cases = cases
        self.materials = by_id
        self.requests = requests
        self.endpoint = endpoint
        self.model = model
        self.boundary_attester = boundary_attester
        self.declared_isolation_raw = declared_isolation_raw
        self.target = target
        self.startup_dynamic_kernel_rpc_registrations = tuple(
            startup_attestation["dynamic_kernel_rpc_registrations"]
        )
        self.startup_dynamic_kernel_rpc_tcp_listeners = tuple(
            startup_attestation["dynamic_kernel_rpc_tcp_listeners"]
        )
        self.transport = _post_loopback if lease is not None else transport_for_testing
        self._test_transport = transport_for_testing is not None
        self.consumption_root = consumption_root
        if (not isinstance(self.consumption_root, Path) or not self.consumption_root.is_dir()
                or self.consumption_root.is_symlink()
                or self.consumption_root == root
                or self.consumption_root.is_relative_to(root)):
            raise LiveQ1Refusal("consumption root must be a pre-existing external real directory")
        if lease is not None and self.consumption_root != Path(
            plan["consumption_registry"]["path"]
        ):
            raise LiveQ1Refusal("production consumption registry path drifted")
        self.max_response_bytes = max_response_bytes
        self.sealed = False
        self.evidence_mode = (
            "LIVE_LEASE" if lease is not None else "TEST_FIXTURE_INJECTED"
        )

    def _consume_plan_before_start(self) -> dict[str, Any]:
        """Atomically burn this plan before any live START can be appended."""
        directory = self.consumption_root
        if not directory.is_dir() or directory.is_symlink():
            raise LiveQ1Refusal("consumption directory is unavailable")
        plan_sha256 = sha256(self.plan_raw).hexdigest()
        closure_sha256 = sha256(self.freeze_closure_raw).hexdigest()
        raw = canonical_bytes(
            {
                "schema_version": "hswm-dgx-q1-plan-consumption/v1",
                "plan_sha256": plan_sha256,
                "closure_manifest_sha256": closure_sha256,
                "evidence_root": str(self.root),
                "registry_path": str(directory),
                "evidence_mode": self.evidence_mode,
                "launch_identity_sha256": sha256(
                    self.startup_attestation_raw
                ).hexdigest(),
                "terminal": "PLAN_BURNED_BEFORE_FIRST_LIVE_START_NO_REUSE",
            }
        )
        target = directory / (plan_sha256 + ".consumed")
        descriptor, temporary = tempfile.mkstemp(prefix=".q1-consume-", dir=directory)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError as error:
                raise LiveQ1Refusal("frozen live Q1 plan was already consumed") from error
            _sync_directory(directory)
            return _put(self.root, raw)
        except LiveQ1Refusal:
            raise
        except Exception:
            # A partially created record still burns the plan.  Do not unlink it.
            raise LiveQ1Refusal("plan consumption record could not be durably sealed")
        finally:
            try: os.unlink(temporary)
            except FileNotFoundError: pass

    def _attest(self, phase: str, attempt_id: str | None, completed: int) -> dict[str, Any]:
        raw = self.boundary_attester(phase, attempt_id, completed)
        validate_boundary_attestation(
            raw,
            self.plan_raw,
            phase=phase,
            attempt_id=attempt_id,
            completed_attempts=completed,
            declared_isolation_raw=self.declared_isolation_raw,
            target=self.target,
            startup_dynamic_kernel_rpc_registrations=(
                self.startup_dynamic_kernel_rpc_registrations
            ),
            startup_dynamic_kernel_rpc_tcp_listeners=(
                self.startup_dynamic_kernel_rpc_tcp_listeners
            ),
        )
        return _put(self.root, raw)

    def _run_seal(
        self,
        *,
        status: str,
        started: int,
        succeeded: int,
        failure_code: str | None,
        final_attestation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return _append(
            self.root,
            {
                "schema_version": LEDGER_SCHEMA,
                "namespace": NAMESPACE,
                "record_type": "RUN_SEAL",
                "status": status,
                "started_slots": started,
                "successful_slots": succeeded,
                "failed_slots": started - succeeded,
                "failure_code": failure_code,
                "final_boundary_attestation": final_attestation,
                "retry": "NONE",
                "retry_allowed": False,
                "terminal": "LIVE_Q1_ROOT_SEALED_NO_RESUME_OR_REPLACEMENT",
            },
        )

    def execute_all(self) -> tuple[dict[str, Any], ...]:
        if self.sealed:
            raise LiveQ1Refusal("live Q1 root is sealed and cannot resume")
        lock_descriptor = os.open(self.root / "dispatch.lock", os.O_RDWR)
        try:
            try:
                fcntl.flock(lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise LiveQ1Refusal("another dispatcher holds the live Q1 root") from error
            ledger = self.root / "q1_live_ledger.jsonl"
            if ledger.read_bytes():
                raise LiveQ1Refusal("live Q1 root was already entered")
            consumption = self._consume_plan_before_start()
            _append(
                self.root,
                {
                    "schema_version": LEDGER_SCHEMA,
                    "namespace": NAMESPACE,
                    "record_type": "PLAN_CONSUMPTION",
                    "consumption": consumption,
                    "plan_sha256": sha256(self.plan_raw).hexdigest(),
                    "closure_manifest_sha256": sha256(
                        self.freeze_closure_raw
                    ).hexdigest(),
                    "registry_path": str(self.consumption_root),
                    "evidence_mode": self.evidence_mode,
                    "retry": "NONE",
                    "terminal": "DURABLE_PLAN_BURN_BEFORE_ANY_PRE_OR_START",
                },
            )
            _append(self.root, self._marker_core)
            terminals: list[dict[str, Any]] = []
            started = 0
            succeeded = 0
            for attempt_id in self.plan["call_order"]:
                match = _ATTEMPT.fullmatch(attempt_id)
                if match is None:
                    raise LiveQ1Refusal("frozen attempt identity drifted")
                case_id = "QCASE-" + match.group(1)
                replicate = int(match.group(2))
                case = self.cases[case_id]
                material = self.materials[case_id]
                request = self.requests[case_id]
                try:
                    pre = self._attest("PRE", attempt_id, started)
                except Exception as error:
                    self._run_seal(
                        status="HALTED_BEFORE_LIVE_POST",
                        started=started,
                        succeeded=succeeded,
                        failure_code=type(error).__name__.upper(),
                        final_attestation=None,
                    )
                    self.sealed = True
                    return tuple(terminals)
                start = _append(
                    self.root,
                    {
                        "schema_version": LEDGER_SCHEMA,
                        "namespace": NAMESPACE,
                        "record_type": "START",
                        "attempt_id": attempt_id,
                        "case_id": case_id,
                        "replicate": replicate,
                        "call_class": case["call_class"],
                        "request": _descriptor(request),
                        "response_schema": _descriptor(material.response_schema_bytes),
                        "plan_sha256": sha256(self.plan_raw).hexdigest(),
                        "pre_boundary_attestation": pre,
                        "retry": "NONE",
                        "terminal": "DURABLY_VISIBLE_BEFORE_SINGLE_LIVE_POST",
                    },
                )
                started += 1
                try:
                    observation = self.transport(
                        self.endpoint,
                        request,
                        self.max_response_bytes,
                    )
                    if type(observation) is not LiveObservation:
                        raise LiveQ1Refusal("transport observation type drifted")
                    if (
                        type(observation.status) is not int
                        or type(observation.body) is not bytes
                        or len(observation.body) > self.max_response_bytes
                    ):
                        raise LiveQ1Refusal("transport observation bound drifted")
                    content_type = _bounded_optional_text(
                        observation.response_content_type,
                        "response content type",
                    )
                    request_id = _bounded_optional_text(
                        observation.provider_request_id,
                        "provider request id",
                    )
                except Exception as error:
                    terminal = _append(
                        self.root,
                        {
                            "schema_version": LEDGER_SCHEMA,
                            "namespace": NAMESPACE,
                            "record_type": "TERMINAL",
                            "attempt_id": attempt_id,
                            "case_id": case_id,
                            "replicate": replicate,
                            "call_class": case["call_class"],
                            "start_record_sha256": start["record_sha256"],
                            "observation": None,
                            "raw_envelope": None,
                            "post_boundary_attestation": None,
                            "model_content_utf8": None,
                            "structured_content_diagnostic": None,
                            "outcome": "FAILED",
                            "failure_code": type(error).__name__.upper(),
                            "retry": "NONE",
                            "retry_allowed": False,
                            "terminal": "LIVE_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT",
                        },
                    )
                    terminals.append(terminal)
                    self._run_seal(
                        status="HALTED_AFTER_TRANSPORT_FAILURE",
                        started=started,
                        succeeded=succeeded,
                        failure_code=type(error).__name__.upper(),
                        final_attestation=None,
                    )
                    self.sealed = True
                    return tuple(terminals)

                raw_envelope = _put(self.root, observation.body)
                try:
                    post = self._attest("POST", attempt_id, started)
                except Exception as error:
                    terminal = _append(
                        self.root,
                        {
                            "schema_version": LEDGER_SCHEMA,
                            "namespace": NAMESPACE,
                            "record_type": "TERMINAL",
                            "attempt_id": attempt_id,
                            "case_id": case_id,
                            "replicate": replicate,
                            "call_class": case["call_class"],
                            "start_record_sha256": start["record_sha256"],
                            "observation": {
                                "status": observation.status,
                                "response_content_type": content_type,
                                "provider_request_id": request_id,
                            },
                            "raw_envelope": raw_envelope,
                            "post_boundary_attestation": None,
                            "model_content_utf8": None,
                            "structured_content_diagnostic": None,
                            "outcome": "FAILED",
                            "failure_code": type(error).__name__.upper(),
                            "retry": "NONE",
                            "retry_allowed": False,
                            "terminal": "LIVE_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT",
                        },
                    )
                    terminals.append(terminal)
                    self._run_seal(
                        status="HALTED_AFTER_POST_BOUNDARY_FAILURE",
                        started=started,
                        succeeded=succeeded,
                        failure_code=type(error).__name__.upper(),
                        final_attestation=None,
                    )
                    self.sealed = True
                    return tuple(terminals)

                try:
                    content, structured = validate_live_envelope(
                        observation.body,
                        observation.status,
                        self.model,
                        material.response_schema_bytes,
                    )
                    content_descriptor = _put(self.root, content)
                    structured_descriptor = _put(self.root, structured)
                    outcome = "SUCCEEDED"
                    failure_code = None
                    succeeded += 1
                except Exception as error:
                    content_descriptor = None
                    structured_descriptor = None
                    outcome = "FAILED"
                    failure_code = type(error).__name__.upper()
                terminal = _append(
                    self.root,
                    {
                        "schema_version": LEDGER_SCHEMA,
                        "namespace": NAMESPACE,
                        "record_type": "TERMINAL",
                        "attempt_id": attempt_id,
                        "case_id": case_id,
                        "replicate": replicate,
                        "call_class": case["call_class"],
                        "start_record_sha256": start["record_sha256"],
                        "observation": {
                            "status": observation.status,
                            "response_content_type": content_type,
                            "provider_request_id": request_id,
                        },
                        "raw_envelope": raw_envelope,
                        "post_boundary_attestation": post,
                        "model_content_utf8": content_descriptor,
                        "structured_content_diagnostic": structured_descriptor,
                        "outcome": outcome,
                        "failure_code": failure_code,
                        "retry": "NONE",
                        "retry_allowed": False,
                        "terminal": "LIVE_SLOT_CONSUMED_NO_RETRY_OR_REPLACEMENT",
                    },
                )
                terminals.append(terminal)

            try:
                final = self._attest("FINAL", None, started)
                status = "COMPLETE_96_LIVE_POSTS"
                failure_code = None
            except Exception as error:
                final = None
                status = "HALTED_AFTER_FINAL_BOUNDARY_FAILURE"
                failure_code = type(error).__name__.upper()
            self._run_seal(
                status=status,
                started=started,
                succeeded=succeeded,
                failure_code=failure_code,
                final_attestation=final,
            )
            self.sealed = True
            return tuple(terminals)
        finally:
            fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
            os.close(lock_descriptor)


__all__ = [
    "LEDGER_SCHEMA",
    "LiveObservation",
    "LiveQ1Runner",
]
