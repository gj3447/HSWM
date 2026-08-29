"""Executable, qualification-only Q gateway for a frozen DNRD-5 Q0 plan.

This module deliberately does not import or extend the occurrence gateway's
call/ledger types.  It has a distinct root, receipt chain, and Q call IDs.
The shared HTTP transport and strict response validator only preserve provider
wire semantics; they confer no occurrence authority.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from _research.dnrd5.canonical_json import (
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)
from _research.dnrd5.provider_gateway import (
    SYSTEM_MESSAGE,
    Dnrd5ProviderConfig,
    HttpObservation,
    SingleShotHttpTransport,
    UrllibSingleShotTransport,
    _validate_model_input,
    _validate_response,
)
from _research.dnrd5.q0_qualification import (
    Q_NAMESPACE,
    validate_q0_plan,
    validate_q_start_marker,
)

Q_GATEWAY_VERSION = "hswm-dnrd5-q-provider-gateway/v1"
Q_LEDGER_SCHEMA = "hswm-dnrd5-q-executable-attempt-ledger/v1"
ZERO = "0" * 64


class QGatewayRefusal(ValueError):
    pass


class QGatewayExecutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class QCorpusMaterial:
    case_id: str
    instruction_bytes: bytes
    model_input_bytes: bytes
    response_schema_bytes: bytes
    rng_bytes: bytes
    max_output_tokens: int


def _descriptor(raw: bytes) -> dict[str, Any]:
    return {"sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_named(root: Path, name: str, raw: bytes) -> None:
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(root)


def _tautological_schema(schema: Any) -> bool:
    if type(schema) is not dict:
        return False
    if "const" in schema:
        return True
    if "enum" in schema:
        return type(schema["enum"]) is list and len(schema["enum"]) <= 1
    if schema.get("type") == "object" and type(schema.get("properties")) is dict:
        children = list(schema["properties"].values())
        return bool(children) and all(_tautological_schema(child) for child in children)
    return False


def _persist(root: Path, raw: bytes) -> None:
    target = root / "content" / sha256(raw).hexdigest()
    if target.exists():
        if target.read_bytes() != raw:
            raise QGatewayRefusal("content-addressed collision")
        return
    fd, name = tempfile.mkstemp(prefix=".q-content-", dir=root / "content")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(name, target)
    except FileExistsError:
        if target.read_bytes() != raw:
            raise QGatewayRefusal("content-addressed collision")
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
    _fsync_directory(root / "content")


def _append(root: Path, core: Mapping[str, Any]) -> dict[str, Any]:
    ledger = root / "q_attempts.jsonl"
    previous = ZERO
    ordinal = 1
    fd = os.open(ledger, os.O_RDWR)
    with os.fdopen(fd, "r+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        raw_existing = handle.read()
        if raw_existing:
            if not raw_existing.endswith(b"\n"):
                raise QGatewayRefusal("Q ledger framing drifted")
            for index, line in enumerate(raw_existing[:-1].split(b"\n"), 1):
                row = parse_canonical(line)
                supplied = row.get("record_sha256")
                core_row = {
                    key: value for key, value in row.items() if key != "record_sha256"
                }
                if (
                    row.get("ordinal") != index
                    or row.get("previous_record_sha256") != previous
                    or supplied != canonical_sha256(core_row)
                ):
                    raise QGatewayRefusal("Q ledger chain drifted")
                previous = supplied
                ordinal = index + 1
        record = {**core, "ordinal": ordinal, "previous_record_sha256": previous}
        record["record_sha256"] = canonical_sha256(record)
        raw = canonical_bytes(record) + b"\n"
        handle.seek(0, os.SEEK_END)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    _fsync_directory(root)
    return record


def build_q_request(
    config: Dnrd5ProviderConfig, call_class: str, material: QCorpusMaterial
) -> bytes:
    """Reconstruct the exact precommitted request from raw corpus bytes."""
    if call_class not in {"PRE_OUTCOME_TRAJECTORY", "REVISION_PROPOSAL", "FRESH_PROBE"}:
        raise QGatewayRefusal("Q corpus call class is invalid")
    try:
        model_input = parse_canonical(material.model_input_bytes)
        schema = parse_canonical(material.response_schema_bytes)
        instruction = material.instruction_bytes.decode("utf-8", errors="strict")
    except Exception as error:
        raise QGatewayRefusal(
            "Q corpus bytes are not strict canonical/UTF-8 inputs"
        ) from error
    _validate_model_input(call_class, model_input)
    if _tautological_schema(schema):
        raise QGatewayRefusal(
            "Q response schema has a single valid tautological output"
        )
    if (
        not instruction
        or not material.rng_bytes
        or material.max_output_tokens not in {64, 128, 256}
    ):
        raise QGatewayRefusal("Q corpus instruction/RNG is empty")
    seed = int.from_bytes(sha256(material.rng_bytes).digest()[:6], "big")
    return canonical_bytes(
        {
            "chat_template_kwargs": {"enable_thinking": False},
            "logprobs": False,
            "max_tokens": material.max_output_tokens,
            "messages": [
                {"content": SYSTEM_MESSAGE, "role": "system"},
                {
                    "content": canonical_bytes(
                        {
                            "contractVersion": "hswm-dnrd5-q-model-input/v1",
                            "callClass": call_class,
                            "instruction": instruction,
                            "input": model_input,
                        }
                    ).decode(),
                    "role": "user",
                },
            ],
            "model": config.expected_model,
            "n": 1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "hswm_dnrd5_q_" + call_class.lower(),
                    "schema": schema,
                    "strict": True,
                },
            },
            "seed": seed,
            "stream": False,
            "temperature": 0,
            "top_p": 1,
        }
    )


class QProviderGateway:
    """One frozen Q0 plan, one fresh root, sequential no-retry execution."""

    def __init__(
        self,
        root: Path,
        plan_raw: bytes,
        marker_raw: bytes,
        root_genesis_raw: bytes,
        corpus_manifest_raw: bytes,
        ci_receipt_bytes: bytes,
        verifier_build_bytes: bytes,
        verifier_source_bytes: bytes,
        config: Dnrd5ProviderConfig,
        *,
        model_identity_bytes: bytes,
        runtime_identity_bytes: bytes,
        tls_identity_bytes: bytes,
        isolation_identity_bytes: bytes,
        transport: SingleShotHttpTransport | None = None,
    ) -> None:
        self.plan = validate_q0_plan(plan_raw)
        validate_q_start_marker(marker_raw, plan_raw)
        if (
            sha256(root_genesis_raw).hexdigest()
            != self.plan["evidence_root_genesis_sha256"]
            or sha256(corpus_manifest_raw).hexdigest()
            != self.plan["corpus_manifest_sha256"]
        ):
            raise QGatewayRefusal(
                "root genesis or corpus manifest differs from frozen Q0"
            )
        if (
            sha256(ci_receipt_bytes).hexdigest()
            != self.plan["source"]["ci_receipt_sha256"]
            or sha256(verifier_build_bytes).hexdigest()
            != self.plan["verifier"]["build_output_sha256"]
        ):
            raise QGatewayRefusal("CI receipt or verifier build differs from frozen Q0")
        try:
            verifier_build = parse_canonical(verifier_build_bytes)
        except Exception as error:
            raise QGatewayRefusal("verifier build must be canonical bytes") from error
        if (
            type(verifier_build) is not dict
            or verifier_build.get("file_sha256")
            != sha256(verifier_source_bytes).hexdigest()
        ):
            raise QGatewayRefusal(
                "verifier source differs from frozen verifier build SHA"
            )
        parse_canonical(root_genesis_raw)
        parse_canonical(corpus_manifest_raw)
        identity_bytes = {
            "endpoint_sha256": config.endpoint.encode(),
            "model_identity_sha256": model_identity_bytes,
            "runtime_identity_sha256": runtime_identity_bytes,
            "tls_identity_sha256": tls_identity_bytes,
            "isolation_identity_sha256": isolation_identity_bytes,
        }
        if any(
            sha256(raw).hexdigest() != self.plan["identities"][key]
            for key, raw in identity_bytes.items()
        ):
            raise QGatewayRefusal("runtime identity differs from frozen Q0")
        if root.exists() or not root.parent.is_dir():
            raise QGatewayRefusal("Q evidence root must be a fresh child path")
        root.mkdir(mode=0o700)
        (root / "content").mkdir(mode=0o700)
        for name in ("q_attempts.jsonl", "q_dispatch.lock"):
            fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        _fsync_directory(root / "content")
        _fsync_directory(root)
        _fsync_directory(root.parent)
        self.identity_sha256s = {
            key: sha256(raw).hexdigest() for key, raw in identity_bytes.items()
        }
        self.root, self.plan_raw, self.config = root, plan_raw, config
        self.transport = transport or UrllibSingleShotTransport()
        # Everything that identifies the frozen root is durable before the
        # marker record; no Q START can be the first durable evidence.
        for raw in (
            plan_raw,
            marker_raw,
            root_genesis_raw,
            corpus_manifest_raw,
            ci_receipt_bytes,
            verifier_build_bytes,
            verifier_source_bytes,
            *identity_bytes.values(),
        ):
            _persist(root, raw)
        _write_named(root, "root-genesis.json", root_genesis_raw)
        _write_named(root, "q0.verifier-source.py", verifier_source_bytes)
        _append(
            root,
            {
                "schema_version": Q_LEDGER_SCHEMA,
                "namespace": Q_NAMESPACE,
                "record_type": "Q_START_MARKER",
                "q0": _descriptor(plan_raw),
                "marker": _descriptor(marker_raw),
                "root_genesis": _descriptor(root_genesis_raw),
                "corpus_manifest": _descriptor(corpus_manifest_raw),
                "ci_receipt": _descriptor(ci_receipt_bytes),
                "verifier_build": _descriptor(verifier_build_bytes),
                "verifier_source": _descriptor(verifier_source_bytes),
                "source": self.plan["source"],
                "terminal": "Q_START_MARKER_PERSISTED_BEFORE_ANY_Q_GATEWAY_START",
            },
        )

    def execute_all(
        self, corpus: Sequence[QCorpusMaterial]
    ) -> tuple[dict[str, Any], ...]:
        if len(corpus) != len(self.plan["corpus"]):
            raise QGatewayRefusal("Q raw corpus cardinality drifted")
        by_case = {item.case_id: item for item in corpus}
        if len(by_case) != len(corpus):
            raise QGatewayRefusal("Q raw corpus duplicates case IDs")
        cases = {item["case_id"]: item for item in self.plan["corpus"]}
        if set(by_case) != set(cases):
            raise QGatewayRefusal("Q raw corpus does not exactly match Q0 cases")
        # The entire raw corpus must bind before the first START.  A drift in a
        # later randomized slot must not consume an earlier Q attempt.
        for case_id, material in by_case.items():
            self._validate_material(cases[case_id], material)
            for raw in (
                material.instruction_bytes,
                material.model_input_bytes,
                material.response_schema_bytes,
                material.rng_bytes,
            ):
                _persist(self.root, raw)
        results = []
        for attempt_id in self.plan["call_order"]:
            case_id, replicate = "QCASE-" + attempt_id[8:11], int(attempt_id[-3:])
            results.append(
                self.execute_one(
                    attempt_id, case_id, replicate, cases[case_id], by_case[case_id]
                )
            )
        return tuple(results)

    def _validate_material(
        self, case: Mapping[str, Any], material: QCorpusMaterial
    ) -> bytes:
        request = build_q_request(self.config, case["call_class"], material)
        hashes = {
            "instruction_sha256": sha256(material.instruction_bytes).hexdigest(),
            "model_input_sha256": sha256(material.model_input_bytes).hexdigest(),
            "response_schema_sha256": sha256(
                material.response_schema_bytes
            ).hexdigest(),
            "rng_sha256": sha256(material.rng_bytes).hexdigest(),
            "request_sha256": sha256(request).hexdigest(),
        }
        if (
            any(case[key] != value for key, value in hashes.items())
            or case["max_output_tokens"] != material.max_output_tokens
        ):
            raise QGatewayRefusal(
                "raw Q corpus/request reconstruction drifted from frozen Q0 hashes"
            )
        return request

    def execute_one(
        self,
        attempt_id: str,
        case_id: str,
        replicate: int,
        case: Mapping[str, Any],
        material: QCorpusMaterial,
    ) -> dict[str, Any]:
        fd = os.open(self.root / "q_dispatch.lock", os.O_RDWR)
        with os.fdopen(fd, "r+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            return self._execute_one_locked(
                attempt_id, case_id, replicate, case, material
            )

    def _execute_one_locked(
        self,
        attempt_id: str,
        case_id: str,
        replicate: int,
        case: Mapping[str, Any],
        material: QCorpusMaterial,
    ) -> dict[str, Any]:
        if (
            attempt_id not in self.plan["call_order"]
            or attempt_id != f"DNRD5-Q-{case_id[-3:]}-R{replicate:03d}"
        ):
            raise QGatewayRefusal("attempt is outside frozen Q0 order/namespace")
        started = [
            record["attempt_id"]
            for record in self._records()
            if record.get("record_type") == "START"
        ]
        if (
            len(started) >= self.plan["budget"]
            or attempt_id != self.plan["call_order"][len(started)]
        ):
            raise QGatewayRefusal(
                "attempt is not the exact next frozen Q0 schedule slot"
            )
        if any(record.get("attempt_id") == attempt_id for record in self._records()):
            raise QGatewayRefusal("Q attempt ID is consumed and never reusable")
        request = self._validate_material(case, material)
        _persist(self.root, request)
        start = _append(
            self.root,
            {
                "schema_version": Q_LEDGER_SCHEMA,
                "namespace": Q_NAMESPACE,
                "record_type": "START",
                "attempt_id": attempt_id,
                "case_id": case_id,
                "replicate": replicate,
                "call_class": case["call_class"],
                "request": _descriptor(request),
                "response_schema": _descriptor(material.response_schema_bytes),
                "identities": self.identity_sha256s,
                "retry": "NONE",
                "terminal": "DURABLY_VISIBLE_BEFORE_SINGLE_DISPATCH",
            },
        )
        observed: HttpObservation | None = None
        try:
            observed = self.transport.request(
                url=self.config.endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.config.api_key
                    if self.config.api_key
                    else "",
                    "Cache-Control": "no-store",
                    "X-HSWM-DNRD5-Q-Attempt": attempt_id,
                },
                body=request,
                timeout_milliseconds=self.config.timeout_milliseconds,
            )
            _validate_response(
                observed.body,
                observed.status,
                self.config.expected_model,
                material.response_schema_bytes,
            )
            envelope = parse_canonical(observed.body)
            content = envelope["choices"][0]["message"]["content"].encode("utf-8")
            structured = canonical_bytes(parse_canonical(content))
            _persist(self.root, observed.body)
            _persist(self.root, content)
            _persist(self.root, structured)
            return _append(
                self.root,
                {
                    "schema_version": Q_LEDGER_SCHEMA,
                    "namespace": Q_NAMESPACE,
                    "record_type": "TERMINAL",
                    "attempt_id": attempt_id,
                    "case_id": case_id,
                    "replicate": replicate,
                    "call_class": case["call_class"],
                    "start_record_sha256": start["record_sha256"],
                    "raw_envelope": _descriptor(observed.body),
                    "model_content_utf8": _descriptor(content),
                    "structured_content": _descriptor(structured),
                    "outcome": "SUCCEEDED",
                    "retry": "NONE",
                    "retry_allowed": False,
                    "terminal": "CALL_ID_CONSUMED_NO_RETRY_RESUME_OR_REPLACEMENT",
                },
            )
        except Exception as error:
            raw_envelope = None if observed is None else _descriptor(observed.body)
            if observed is not None:
                _persist(self.root, observed.body)
            _append(
                self.root,
                {
                    "schema_version": Q_LEDGER_SCHEMA,
                    "namespace": Q_NAMESPACE,
                    "record_type": "TERMINAL",
                    "attempt_id": attempt_id,
                    "case_id": case_id,
                    "replicate": replicate,
                    "call_class": case["call_class"],
                    "start_record_sha256": start["record_sha256"],
                    "raw_envelope": raw_envelope,
                    "model_content_utf8": None,
                    "structured_content": None,
                    "http_status": None if observed is None else observed.status,
                    "response_content_type": None
                    if observed is None
                    else observed.response_content_type,
                    "provider_request_id": None
                    if observed is None
                    else observed.provider_request_id,
                    "outcome": "FAILED",
                    "failure_code": type(error).__name__.upper(),
                    "retry": "NONE",
                    "retry_allowed": False,
                    "terminal": "CALL_ID_CONSUMED_NO_RETRY_RESUME_OR_REPLACEMENT",
                },
            )
            raise QGatewayExecutionError(
                "Q attempt consumed without accepted response"
            ) from error

    def _records(self) -> tuple[Mapping[str, Any], ...]:
        path = self.root / "q_attempts.jsonl"
        return tuple(
            parse_canonical(line)
            for line in path.read_bytes().rstrip(b"\n").split(b"\n")
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DNRD-5 Q0 qualification-only gateway; never occurrence execution"
    )
    parser.add_argument("--q0", type=Path, required=True)
    parser.add_argument("--q-start-marker", type=Path, required=True)
    parser.add_argument("--root-genesis", type=Path, required=True)
    parser.add_argument("--ci-receipt", type=Path, required=True)
    parser.add_argument("--verifier-build", type=Path, required=True)
    parser.add_argument("--verifier-source", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="canonical JSON Q raw-corpus hex manifest",
    )
    parser.add_argument("--model-identity", type=Path, required=True)
    parser.add_argument("--runtime-identity", type=Path, required=True)
    parser.add_argument("--tls-identity", type=Path, required=True)
    parser.add_argument("--isolation-identity", type=Path, required=True)
    parser.add_argument("--api-key-env", default="")
    args = parser.parse_args(argv)
    try:
        manifest = parse_canonical(args.corpus.read_bytes())
        if (
            type(manifest) is not dict
            or set(manifest) != {"schema_version", "classification", "cases"}
            or manifest["schema_version"] != "hswm-dnrd5-q0-public-synthetic-corpus/v1"
            or manifest["classification"]
            != "PUBLIC_SYNTHETIC_QUALIFICATION_ONLY_NO_CORRECTNESS_EVALUATOR"
            or type(manifest["cases"]) is not list
        ):
            raise QGatewayRefusal(
                "Q corpus CLI manifest must be the exact frozen corpus object"
            )
        corpus = tuple(
            QCorpusMaterial(
                item["case_id"],
                item["instruction"].encode("utf-8"),
                canonical_bytes(item["model_input"]),
                canonical_bytes(item["response_schema"]),
                bytes.fromhex(item["rng_hex"]),
                item["max_output_tokens"],
            )
            for item in manifest["cases"]
            if type(item) is dict
            and set(item)
            == {
                "case_id",
                "call_class",
                "instruction",
                "max_output_tokens",
                "model_input",
                "response_schema",
                "rng_hex",
                "size_class",
            }
        )
        if len(corpus) != len(manifest["cases"]):
            raise QGatewayRefusal("Q corpus CLI manifest row shape drifted")
        api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
        gateway = QProviderGateway(
            args.evidence_root,
            args.q0.read_bytes(),
            args.q_start_marker.read_bytes(),
            args.root_genesis.read_bytes(),
            args.corpus.read_bytes(),
            args.ci_receipt.read_bytes(),
            args.verifier_build.read_bytes(),
            args.verifier_source.read_bytes(),
            Dnrd5ProviderConfig(
                endpoint=args.endpoint, expected_model=args.model, api_key=api_key
            ),
            model_identity_bytes=args.model_identity.read_bytes(),
            runtime_identity_bytes=args.runtime_identity.read_bytes(),
            tls_identity_bytes=args.tls_identity.read_bytes(),
            isolation_identity_bytes=args.isolation_identity.read_bytes(),
        )
        gateway.execute_all(corpus)
    except (OSError, ValueError, QGatewayExecutionError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
