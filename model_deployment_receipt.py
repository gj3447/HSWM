"""Content-attested receipt for an OpenAI-compatible local deployment.

``/v1/models`` proves only a served alias.  H3 also needs to know which local
snapshot the serving process was started from.  This tool binds the live model
catalog, the server process command identity, and content hashes of the exact
Hugging Face snapshot into one first-write receipt.  It never records process
environment variables or API credentials.

Longinus ReferenceSite: ``H3_B3_COMPOSITION_PREREG_2026-07-20.md`` model
identity and evidence-preserving producer gates.
"""
from __future__ import annotations

from hashlib import sha256
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import tempfile
import time
from typing import Any, Mapping, Sequence
from urllib import request as urllib_request
from urllib.parse import urlsplit, urlunsplit

from bge_m3_embed import (
    MODEL_ATTESTATION_SCHEMA_VERSION,
    attest_model_snapshot,
    canonical_json,
    validate_model_attestation,
)


SCHEMA_VERSION = "hswm-openai-deployment-attestation/v2"
PROCESS_SCHEMA_VERSION = "hswm-serving-process-attestation/v2"
_DEPLOYMENT_RECEIPT_KEYS = frozenset({
    "schema_version", "created_unix_ns", "host", "endpoint", "served_model",
    "advertised_models", "models_response", "models_response_sha256",
    "snapshot", "server_process", "runtime_versions", "receipt_sha256",
    "deployment_id",
})
_PROCESS_KEYS = frozenset({
    "schema_version", "pid", "process_start_ticks", "executable",
    "executable_sha256", "argv_sha256", "argc", "model_reference",
    "model_reference_kind", "revision_binding", "served_alias",
    "served_alias_explicit",
})


class DeploymentAttestationError(RuntimeError):
    pass


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json(raw: str | bytes, *, label: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DeploymentAttestationError(
                    f"{label} contains duplicate JSON key {key!r}"
                )
            result[key] = value
        return result

    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(text, object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeploymentAttestationError(f"{label} is not strict JSON") from exc


def _require_sha256(value: Any, *, label: str) -> str:
    if (not isinstance(value, str) or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)):
        raise DeploymentAttestationError(f"{label} is not a SHA-256 digest")
    return value


def _integrity_digest(value: Mapping[str, Any], *excluded: str) -> str:
    payload = {key: item for key, item in value.items() if key not in excluded}
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _normalize_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.query or parsed.fragment or parsed.username
            or parsed.password):
        raise DeploymentAttestationError("endpoint must be a credential-free HTTP URL")
    path = parsed.path.rstrip("/")
    if path != "/v1":
        raise DeploymentAttestationError("endpoint path must be exactly /v1")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _fetch_models(endpoint: str, *, timeout_seconds: float) -> tuple[str, Mapping[str, Any]]:
    endpoint = _normalize_endpoint(endpoint)
    if timeout_seconds <= 0:
        raise DeploymentAttestationError("timeout_seconds must be positive")
    url = endpoint + "/models"
    request = urllib_request.Request(url, method="GET")
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            status = int(response.status)
    except Exception as exc:  # network boundary becomes a fail-closed receipt error
        raise DeploymentAttestationError(
            f"model catalog request failed: {type(exc).__name__}"
        ) from exc
    if status != 200:
        raise DeploymentAttestationError(f"model catalog HTTP status {status}")
    value = _strict_json(raw, label="model catalog")
    if not isinstance(value, Mapping) or not isinstance(value.get("data"), list):
        raise DeploymentAttestationError("model catalog schema mismatch")
    return raw, value


def _process_attestation(
    pid: int,
    *,
    expected_model_id: str,
    expected_revision: str,
    served_model: str,
    snapshot_path: str | Path,
) -> dict[str, Any]:
    if pid <= 0:
        raise DeploymentAttestationError("server pid must be positive")
    proc = Path("/proc") / str(pid)
    try:
        raw_stat_before = (proc / "stat").read_text(encoding="utf-8")
        raw_cmdline = (proc / "cmdline").read_bytes()
        executable = Path(proc / "exe").resolve(strict=True)
        raw_stat_after = (proc / "stat").read_text(encoding="utf-8")
    except OSError as exc:
        raise DeploymentAttestationError("cannot inspect serving process") from exc
    try:
        args = tuple(
            item.decode("utf-8", errors="strict")
            for item in raw_cmdline.split(b"\0") if item
        )
    except UnicodeDecodeError as exc:
        raise DeploymentAttestationError("serving process argv is not UTF-8") from exc
    if not args or not executable.is_file():
        raise DeploymentAttestationError("serving process identity is incomplete")
    before_ticks = _process_start_ticks(raw_stat_before)
    after_ticks = _process_start_ticks(raw_stat_after)
    if before_ticks != after_ticks:
        raise DeploymentAttestationError("serving process changed during attestation")
    binding = _validate_process_args(
        args, expected_model_id=expected_model_id,
        expected_revision=expected_revision, served_model=served_model,
        snapshot_path=snapshot_path,
    )
    return {
        "schema_version": PROCESS_SCHEMA_VERSION,
        "pid": pid,
        "process_start_ticks": before_ticks,
        "executable": str(executable),
        "executable_sha256": _file_sha256(executable),
        "argv_sha256": sha256(raw_cmdline).hexdigest(),
        "argc": len(args),
        **binding,
    }


def _process_start_ticks(raw_stat: str) -> str:
    """Parse Linux proc stat without splitting the parenthesized comm field."""

    closing = raw_stat.rfind(")")
    if closing < 0:
        raise DeploymentAttestationError("serving process stat schema mismatch")
    fields_after_comm = raw_stat[closing + 1:].strip().split()
    # fields_after_comm[0] is field 3 (state); starttime is field 22.
    if len(fields_after_comm) <= 19 or not fields_after_comm[19].isdigit():
        raise DeploymentAttestationError("serving process stat schema mismatch")
    return fields_after_comm[19]


def _single_option(args: Sequence[str], option: str) -> str | None:
    values: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token == option:
            if index + 1 >= len(args) or not args[index + 1]:
                raise DeploymentAttestationError(f"{option} lacks a value")
            values.append(args[index + 1])
            index += 2
            continue
        prefix = option + "="
        if token.startswith(prefix):
            value = token[len(prefix):]
            if not value:
                raise DeploymentAttestationError(f"{option} lacks a value")
            values.append(value)
        index += 1
    if len(values) > 1:
        raise DeploymentAttestationError(f"{option} is ambiguous")
    return values[0] if values else None


def _validate_process_args(
    args: Sequence[str],
    *,
    expected_model_id: str,
    expected_revision: str,
    served_model: str,
    snapshot_path: str | Path,
) -> dict[str, Any]:
    """Extract exact vLLM model, revision, and alias argv tokens.

    Mere substring occurrence is deliberately worthless: a note, log path, or
    similarly named option cannot satisfy any identity gate.
    """

    if not args or not expected_model_id or not expected_revision or not served_model:
        raise DeploymentAttestationError("serving command identity is incomplete")
    command_name = Path(args[0]).name
    python_module: str | None = None
    for index, token in enumerate(args[:-1]):
        if token == "-m":
            if python_module is not None:
                raise DeploymentAttestationError("serving Python module is ambiguous")
            python_module = args[index + 1]
    is_vllm_cli = command_name == "vllm"
    is_vllm_module = (
        command_name.startswith("python")
        and isinstance(python_module, str)
        and (python_module == "vllm" or python_module.startswith("vllm."))
    )
    if not is_vllm_cli and not is_vllm_module:
        raise DeploymentAttestationError("serving command is not an exact vLLM entrypoint")
    resolved_snapshot = str(Path(snapshot_path).expanduser().resolve(strict=True))
    if Path(resolved_snapshot).name != expected_revision:
        raise DeploymentAttestationError("snapshot path/revision mismatch")

    option_model = _single_option(args, "--model")
    positional_model: str | None = None
    if is_vllm_cli:
        if len(args) < 3 or args[1] != "serve":
            raise DeploymentAttestationError("vLLM CLI is not the serve command")
        if not args[2].startswith("-"):
            positional_model = args[2]
    model_references = {
        item for item in (option_model, positional_model) if item is not None
    }
    if len(model_references) != 1:
        raise DeploymentAttestationError("serving process lacks one exact model reference")
    model_reference = next(iter(model_references))
    revision_option = _single_option(args, "--revision")
    if model_reference == expected_model_id:
        if revision_option != expected_revision:
            raise DeploymentAttestationError(
                "repository model reference lacks the exact immutable revision"
            )
        reference_kind = "repository_revision"
        revision_binding = revision_option
    else:
        try:
            resolved_reference = str(
                Path(model_reference).expanduser().resolve(strict=True)
            )
        except OSError as exc:
            raise DeploymentAttestationError(
                "serving process model reference is not the attested snapshot"
            ) from exc
        if resolved_reference != resolved_snapshot:
            raise DeploymentAttestationError(
                "serving process model reference is not the attested snapshot"
            )
        if revision_option not in {None, expected_revision}:
            raise DeploymentAttestationError("serving process revision conflicts with snapshot")
        model_reference = resolved_reference
        reference_kind = "snapshot_path"
        revision_binding = expected_revision

    served_alias_option = _single_option(args, "--served-model-name")
    if served_alias_option is None:
        if served_model != expected_model_id:
            raise DeploymentAttestationError(
                "served alias is not explicitly bound in the command"
            )
        served_alias_explicit = False
    elif served_alias_option != served_model:
        raise DeploymentAttestationError("served alias command binding mismatch")
    else:
        served_alias_explicit = True
    return {
        "model_reference": model_reference,
        "model_reference_kind": reference_kind,
        "revision_binding": revision_binding,
        "served_alias": served_model,
        "served_alias_explicit": served_alias_explicit,
    }


def build_receipt(
    *,
    endpoint: str,
    served_model: str,
    model_id: str,
    model_revision: str,
    snapshot_path: str | Path,
    server_pid: int,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    normalized_endpoint = _normalize_endpoint(endpoint)
    _raw_models, models = _fetch_models(
        normalized_endpoint, timeout_seconds=timeout_seconds,
    )
    advertised_raw: list[str] = []
    for item in models["data"]:
        if (not isinstance(item, Mapping) or not isinstance(item.get("id"), str)
                or not item["id"]):
            raise DeploymentAttestationError("model catalog contains an invalid model row")
        advertised_raw.append(item["id"])
    if len(advertised_raw) != len(set(advertised_raw)):
        raise DeploymentAttestationError("model catalog contains duplicate model IDs")
    advertised = sorted(advertised_raw)
    if advertised_raw.count(served_model) != 1:
        raise DeploymentAttestationError(
            "served model must appear exactly once in /v1/models"
        )
    try:
        snapshot = attest_model_snapshot(
            snapshot_path, expected_model=model_id,
            expected_revision=model_revision,
        )
    except ValueError as exc:
        raise DeploymentAttestationError("model snapshot attestation failed") from exc
    process = _process_attestation(
        server_pid, expected_model_id=model_id,
        expected_revision=model_revision, served_model=served_model,
        snapshot_path=snapshot["resolved_snapshot_path"],
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_unix_ns": time.time_ns(),
        "host": socket.gethostname(),
        "endpoint": normalized_endpoint,
        "served_model": served_model,
        "advertised_models": advertised,
        "models_response": models,
        "models_response_sha256": sha256(
            canonical_json(models).encode("utf-8")
        ).hexdigest(),
        "snapshot": snapshot,
        "server_process": process,
        "runtime_versions": {
            "vllm": _package_version("vllm"),
            "transformers": _package_version("transformers"),
            "torch": _package_version("torch"),
        },
    }
    integrity = _integrity_digest(payload)
    payload["receipt_sha256"] = integrity
    payload["deployment_id"] = f"hswm:model_deployment:v2:{integrity}"
    validate_deployment_receipt(payload)
    return payload


def write_once(path: str | Path, value: Mapping[str, Any]) -> str:
    validate_deployment_receipt(value)
    output = Path(path).expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise DeploymentAttestationError("deployment receipt is first-write-wins")
    payload = canonical_json(value) + "\n"
    descriptor, raw_temp = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.pending-",
    )
    temp = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp, output)
        _fsync_directory(output.parent)
    except FileExistsError as exc:
        raise DeploymentAttestationError(
            "deployment receipt is first-write-wins"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temp.unlink(missing_ok=True)
    return sha256(payload.encode("utf-8")).hexdigest()


def _catalog_model_ids(models: Any) -> list[str]:
    if not isinstance(models, Mapping) or not isinstance(models.get("data"), list):
        raise DeploymentAttestationError("stored model catalog schema mismatch")
    identifiers: list[str] = []
    for row in models["data"]:
        if (not isinstance(row, Mapping) or not isinstance(row.get("id"), str)
                or not row["id"]):
            raise DeploymentAttestationError("stored model catalog row mismatch")
        identifiers.append(row["id"])
    if len(identifiers) != len(set(identifiers)):
        raise DeploymentAttestationError("stored model catalog has duplicates")
    return identifiers


def validate_deployment_receipt(
    value: Mapping[str, Any],
    *,
    snapshot_path: str | Path | None = None,
    verify_snapshot: bool = False,
    verify_live_process: bool = False,
) -> dict[str, Any]:
    """Validate receipt self-integrity and optional live snapshot/process state."""

    if not isinstance(value, Mapping) or set(value) != _DEPLOYMENT_RECEIPT_KEYS:
        raise DeploymentAttestationError("deployment receipt keys mismatch")
    receipt = dict(value)
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise DeploymentAttestationError("deployment receipt schema mismatch")
    if (not isinstance(receipt.get("created_unix_ns"), int)
            or receipt["created_unix_ns"] <= 0):
        raise DeploymentAttestationError("deployment receipt timestamp mismatch")
    if not isinstance(receipt.get("host"), str) or not receipt["host"]:
        raise DeploymentAttestationError("deployment receipt host mismatch")
    if receipt.get("endpoint") != _normalize_endpoint(str(receipt.get("endpoint", ""))):
        raise DeploymentAttestationError("deployment receipt endpoint is not canonical")
    served_model = receipt.get("served_model")
    if not isinstance(served_model, str) or not served_model:
        raise DeploymentAttestationError("deployment receipt served model mismatch")
    advertised = receipt.get("advertised_models")
    if (not isinstance(advertised, list) or advertised != sorted(advertised)
            or len(advertised) != len(set(advertised))
            or advertised.count(served_model) != 1):
        raise DeploymentAttestationError("deployment receipt advertised models mismatch")
    observed_ids = _catalog_model_ids(receipt.get("models_response"))
    if sorted(observed_ids) != advertised:
        raise DeploymentAttestationError("deployment receipt/catalog identity mismatch")
    catalog_digest = sha256(
        canonical_json(receipt["models_response"]).encode("utf-8")
    ).hexdigest()
    if receipt.get("models_response_sha256") != catalog_digest:
        raise DeploymentAttestationError("deployment model catalog hash mismatch")
    try:
        snapshot = validate_model_attestation(
            receipt.get("snapshot"), snapshot_path=snapshot_path,
            verify_files=verify_snapshot,
        )
    except ValueError as exc:
        raise DeploymentAttestationError("deployment snapshot receipt mismatch") from exc

    process = receipt.get("server_process")
    if not isinstance(process, Mapping) or set(process) != _PROCESS_KEYS:
        raise DeploymentAttestationError("deployment process receipt keys mismatch")
    if process.get("schema_version") != PROCESS_SCHEMA_VERSION:
        raise DeploymentAttestationError("deployment process schema mismatch")
    if (not isinstance(process.get("pid"), int) or process["pid"] <= 0
            or not isinstance(process.get("process_start_ticks"), str)
            or not process["process_start_ticks"].isdigit()
            or not isinstance(process.get("argc"), int) or process["argc"] < 1):
        raise DeploymentAttestationError("deployment process identity mismatch")
    for key in ("executable_sha256", "argv_sha256"):
        _require_sha256(process.get(key), label=f"server_process.{key}")
    if not isinstance(process.get("executable"), str) or not process["executable"]:
        raise DeploymentAttestationError("deployment executable identity mismatch")
    if process.get("revision_binding") != snapshot["resolved_revision"]:
        raise DeploymentAttestationError("deployment process revision binding mismatch")
    kind = process.get("model_reference_kind")
    if kind == "repository_revision":
        if process.get("model_reference") != snapshot["resolved_model_id"]:
            raise DeploymentAttestationError("deployment repository binding mismatch")
    elif kind == "snapshot_path":
        if process.get("model_reference") != snapshot["resolved_snapshot_path"]:
            raise DeploymentAttestationError("deployment snapshot path binding mismatch")
    else:
        raise DeploymentAttestationError("deployment model reference kind mismatch")
    if process.get("served_alias") != served_model:
        raise DeploymentAttestationError("deployment process alias binding mismatch")
    if not isinstance(process.get("served_alias_explicit"), bool):
        raise DeploymentAttestationError("deployment alias evidence mismatch")
    runtime_versions = receipt.get("runtime_versions")
    if (not isinstance(runtime_versions, Mapping)
            or set(runtime_versions) != {"vllm", "transformers", "torch"}
            or any(value is not None and not isinstance(value, str)
                   for value in runtime_versions.values())):
        raise DeploymentAttestationError("deployment runtime versions mismatch")
    _require_sha256(receipt.get("receipt_sha256"), label="receipt_sha256")
    expected_integrity = _integrity_digest(
        receipt, "receipt_sha256", "deployment_id",
    )
    if receipt["receipt_sha256"] != expected_integrity:
        raise DeploymentAttestationError("deployment receipt self-hash mismatch")
    if receipt.get("deployment_id") != f"hswm:model_deployment:v2:{expected_integrity}":
        raise DeploymentAttestationError("deployment ID mismatch")

    if verify_live_process:
        live = _process_attestation(
            process["pid"], expected_model_id=snapshot["resolved_model_id"],
            expected_revision=snapshot["resolved_revision"],
            served_model=served_model,
            snapshot_path=snapshot["resolved_snapshot_path"],
        )
        if live != process:
            raise DeploymentAttestationError("serving process no longer matches receipt")
    return receipt


def load_deployment_receipt(
    path: str | Path,
    *,
    snapshot_path: str | Path | None = None,
    verify_snapshot: bool = False,
    verify_live_process: bool = False,
) -> dict[str, Any]:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise DeploymentAttestationError("cannot read deployment receipt") from exc
    value = _strict_json(raw, label="deployment receipt")
    if not isinstance(value, Mapping):
        raise DeploymentAttestationError("deployment receipt must be a JSON object")
    return validate_deployment_receipt(
        value, snapshot_path=snapshot_path, verify_snapshot=verify_snapshot,
        verify_live_process=verify_live_process,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--served-model", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--snapshot-path", required=True)
    parser.add_argument("--server-pid", required=True, type=int)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    receipt = build_receipt(
        endpoint=args.endpoint, served_model=args.served_model,
        model_id=args.model_id, model_revision=args.model_revision,
        snapshot_path=args.snapshot_path, server_pid=args.server_pid,
        timeout_seconds=args.timeout_seconds,
    )
    digest = write_once(args.out, receipt)
    print(canonical_json({
        "deployment_id": receipt["deployment_id"],
        "out": str(args.out), "file_sha256": digest,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
