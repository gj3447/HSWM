#!/usr/bin/env python3
"""Freeze deterministic, secret-blind environment/dependency preimages for F1 r8.

The environment and dependency documents are separate private receipts because
the execution lock binds them separately.  Their semantic component roots are
combined into one path-independent compatibility root, so a relocated but
byte-identical environment remains comparable while either receipt still binds
its exact local paths and representation.

Only the names in :data:`NONSECRET_ENV_ALLOWLIST` are ever read from the process
environment.  Small files carry their recoverable bytes; larger files are read
incrementally and carry a fixed-size chunk manifest plus a whole-file digest.
No model, endpoint, gold, or external service is consulted.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Collection, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256


ENVIRONMENT_SCHEMA = "hswm-prom9-f1-r8-environment-attestation/v2"
DEPENDENCY_SCHEMA = "hswm-prom9-f1-r8-dependency-preimages/v2"
BUNDLE_SCHEMA = "hswm-prom9-f1-r8-environment-dependency-bundle/v1"
ENVIRONMENT_ROOT_SCHEMA = "hswm-prom9-f1-r8-environment-root/v1"
DEPENDENCY_ROOT_SCHEMA = "hswm-prom9-f1-r8-dependency-root/v1"
COMPATIBILITY_ROOT_SCHEMA = "hswm-prom9-f1-r8-compatibility-root/v1"

DEFAULT_INLINE_LIMIT_BYTES = 64 * 1024
DEFAULT_CHUNK_SIZE_BYTES = 1024 * 1024
MAX_POLICY_BYTES = 64 * 1024 * 1024
MAX_ENV_VALUE_BYTES = 16 * 1024
MAX_PRIVATE_RECEIPT_BYTES = 64 * 1024 * 1024

# Deliberately excludes credentials, API keys, bearer headers, proxy URLs, and
# arbitrary caller-selected names.  Every listed variable can change numerical
# or Python/runtime behaviour and is safe to store in a private receipt.
NONSECRET_ENV_ALLOWLIST: tuple[str, ...] = (
    "CUBLAS_WORKSPACE_CONFIG",
    "CUDA_DEVICE_ORDER",
    "CUDA_VISIBLE_DEVICES",
    "HF_HUB_OFFLINE",
    "LANG",
    "LC_ALL",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_DYNAMIC",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "PYTHONHASHSEED",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONNOUSERSITE",
    "PYTHONPATH",
    "PYTORCH_CUDA_ALLOC_CONF",
    "TOKENIZERS_PARALLELISM",
    "TRANSFORMERS_OFFLINE",
    "TZ",
    "VLLM_USE_V1",
    "VLLM_WORKER_MULTIPROC_METHOD",
)

# Optional semantic labels are also closed-world.  They bind non-secret runtime
# policy without turning this module into an arbitrary environment dumper.
NONSECRET_LABEL_ALLOWLIST: tuple[str, ...] = (
    "model_deployment_receipt_sha256",
    "model_upstream_endpoint",
    "spool_endpoint",
    "hswm_commit",
    "model",
    "model_revision",
    "run_id",
    "symposium_commit",
)

R8_DEPENDENCY_NAMES: tuple[str, ...] = (
    "runner",
    "private_output",
    "environment",
    "lock_builder",
    "power_builder",
    "power_cli",
    "prior_exposure",
    "data_preparer_core",
    "function_network_adapter",
    "protocol_loader",
    "terminal_transport_exporter",
    "function_network",
    "durable_transport",
    "sqlite_schema_authority",
    "result_spool",
    "call_receipt",
    "function_registry",
    "token_meter",
    "typed_ports",
    "token_envelope",
    "token_envelope_derivation",
    "token_meter_validator",
    "model_deployment_receipt_code",
    "model_snapshot_attestation_core",
    "protocol_json",
    "data_preparer",
    "judge_core",
    "result_contract",
    "tokenizer_vocab",
    "tokenizer_merges",
    "tokenizer_config",
    "model_catalog",
    "model_deployment_receipt",
    "python_lock",
)
# Compatibility name for in-flight consumers; this is an alias, not a second
# inventory.  All measured paths compare against the same tuple above.
R8_REQUIRED_DEPENDENCY_NAMES = R8_DEPENDENCY_NAMES
R8_C801_DEPENDENCY_NAMES: tuple[str, ...] = (
    *R8_DEPENDENCY_NAMES,
    "selection_builder",
)
R8_COMMIT_BOUND_DEPENDENCY_NAMES = frozenset(
    {
        "runner",
        "private_output",
        "environment",
        "lock_builder",
        "power_builder",
        "power_cli",
        "prior_exposure",
        "data_preparer_core",
        "function_network_adapter",
        "protocol_json",
        "protocol_loader",
        "terminal_transport_exporter",
        "function_network",
        "durable_transport",
        "sqlite_schema_authority",
        "result_spool",
        "call_receipt",
        "function_registry",
        "token_meter",
        "typed_ports",
        "token_envelope",
        "token_envelope_derivation",
        "token_meter_validator",
        "model_deployment_receipt_code",
        "model_snapshot_attestation_core",
        "data_preparer",
    }
)
R8_C801_ADDITIONAL_COMMIT_BOUND_DEPENDENCY_NAMES = frozenset(
    {"selection_builder"}
)
R8_SYMPOSIUM_COMMIT_BOUND_DEPENDENCY_NAMES = frozenset({"judge_core"})

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_MODE = re.compile(r"^0o[0-7]{3,4}$")
_PYTHON_FLAG_NAMES: tuple[str, ...] = (
    "debug",
    "dev_mode",
    "dont_write_bytecode",
    "hash_randomization",
    "ignore_environment",
    "isolated",
    "no_site",
    "no_user_site",
    "optimize",
    "safe_path",
    "utf8_mode",
    "warn_default_encoding",
)


class EnvironmentPreimageError(RuntimeError):
    """An environment/dependency preimage is incomplete, mutable, or invalid."""


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise EnvironmentPreimageError(f"{label} is not a SHA-256 digest")
    return value


def _policy(inline_limit_bytes: int, chunk_size_bytes: int) -> dict[str, int]:
    for value, label, lower in (
        (inline_limit_bytes, "inline limit", 0),
        (chunk_size_bytes, "chunk size", 1),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not lower <= value <= MAX_POLICY_BYTES
        ):
            raise EnvironmentPreimageError(f"{label} is outside the frozen bounds")
    return {
        "inline_limit_bytes": inline_limit_bytes,
        "chunk_size_bytes": chunk_size_bytes,
    }


def _stat_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_chunk(descriptor: int, chunk_size: int) -> bytes:
    """Read one deterministic chunk even if ``os.read`` returns short."""

    value = bytearray()
    while len(value) < chunk_size:
        part = os.read(descriptor, chunk_size - len(value))
        if not part:
            break
        value.extend(part)
    return bytes(value)


def _capture_file(
    path: Path,
    *,
    inline_limit_bytes: int,
    chunk_size_bytes: int,
    allow_resolved_symlink: bool = False,
) -> dict[str, object]:
    """Capture one stable regular file without loading a large file at once."""

    policy = _policy(inline_limit_bytes, chunk_size_bytes)
    declared = Path(path).expanduser()
    try:
        path_before = declared.lstat()
    except OSError as error:
        raise EnvironmentPreimageError("dependency preimage is unavailable") from error
    if stat.S_ISLNK(path_before.st_mode):
        if not allow_resolved_symlink:
            raise EnvironmentPreimageError("dependency preimage may not be a symlink")
        declared = declared.resolve(strict=True)
        path_before = declared.lstat()
    if not stat.S_ISREG(path_before.st_mode):
        raise EnvironmentPreimageError("dependency preimage must be a regular file")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(declared, flags)
    except OSError as error:
        raise EnvironmentPreimageError("dependency preimage cannot be opened") from error

    whole = hashlib.sha256()
    chunks: list[dict[str, object]] = []
    inline = bytearray()
    total = 0
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != path_before.st_dev
            or opened.st_ino != path_before.st_ino
        ):
            raise EnvironmentPreimageError("dependency changed before hashing")
        should_inline = opened.st_size <= policy["inline_limit_bytes"]
        while True:
            block = _read_chunk(descriptor, policy["chunk_size_bytes"])
            if not block:
                break
            whole.update(block)
            if should_inline:
                inline.extend(block)
            else:
                chunks.append(
                    {
                        "index": len(chunks),
                        "size_bytes": len(block),
                        "sha256": hashlib.sha256(block).hexdigest(),
                    }
                )
            total += len(block)
        descriptor_after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    try:
        path_after = declared.lstat()
    except OSError as error:
        raise EnvironmentPreimageError("dependency disappeared while hashing") from error
    identity = _stat_identity(opened)
    if (
        identity != _stat_identity(descriptor_after)
        or identity != _stat_identity(path_after)
        or total != opened.st_size
    ):
        raise EnvironmentPreimageError("dependency changed while hashing")

    if should_inline:
        representation: dict[str, object] = {
            "kind": "inline-base64",
            "encoding": "base64",
            "bytes_b64": base64.b64encode(bytes(inline)).decode("ascii"),
        }
    else:
        representation = {
            "kind": "streamed-chunk-manifest",
            "chunk_size_bytes": policy["chunk_size_bytes"],
            "chunks": chunks,
            "manifest_sha256": canonical_sha256(chunks),
        }
    return {
        "resolved_path": str(declared.resolve(strict=True)),
        "size_bytes": int(opened.st_size),
        "mode": oct(stat.S_IMODE(opened.st_mode)),
        "sha256": whole.hexdigest(),
        "preimage": representation,
    }


def _file_projection(value: Mapping[str, object]) -> dict[str, object]:
    preimage = value["preimage"]
    assert isinstance(preimage, Mapping)
    return {
        "size_bytes": value["size_bytes"],
        "mode": value["mode"],
        "sha256": value["sha256"],
        "preimage_kind": preimage["kind"],
        "chunk_manifest_sha256": preimage.get("manifest_sha256"),
    }


def _validate_file_preimage(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "resolved_path",
        "size_bytes",
        "mode",
        "sha256",
        "preimage",
    }:
        raise EnvironmentPreimageError(f"{label} file preimage shape drifted")
    row = dict(value)
    resolved = row["resolved_path"]
    size = row["size_bytes"]
    mode = row["mode"]
    digest = row["sha256"]
    if (
        not isinstance(resolved, str)
        or not Path(resolved).is_absolute()
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
        or not isinstance(mode, str)
        or _MODE.fullmatch(mode) is None
    ):
        raise EnvironmentPreimageError(f"{label} file metadata drifted")
    _require_sha256(digest, f"{label} file")
    preimage = row["preimage"]
    if not isinstance(preimage, Mapping):
        raise EnvironmentPreimageError(f"{label} preimage representation is absent")
    kind = preimage.get("kind")
    if kind == "inline-base64":
        if set(preimage) != {"kind", "encoding", "bytes_b64"} or preimage.get(
            "encoding"
        ) != "base64":
            raise EnvironmentPreimageError(f"{label} inline preimage shape drifted")
        encoded = preimage.get("bytes_b64")
        if not isinstance(encoded, str):
            raise EnvironmentPreimageError(f"{label} inline bytes are absent")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise EnvironmentPreimageError(f"{label} inline bytes are invalid") from error
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise EnvironmentPreimageError(f"{label} inline bytes/hash drifted")
    elif kind == "streamed-chunk-manifest":
        if set(preimage) != {
            "kind",
            "chunk_size_bytes",
            "chunks",
            "manifest_sha256",
        }:
            raise EnvironmentPreimageError(f"{label} chunk manifest shape drifted")
        chunk_size = preimage.get("chunk_size_bytes")
        chunks = preimage.get("chunks")
        if (
            isinstance(chunk_size, bool)
            or not isinstance(chunk_size, int)
            or not 1 <= chunk_size <= MAX_POLICY_BYTES
            or not isinstance(chunks, list)
            or not chunks
        ):
            raise EnvironmentPreimageError(f"{label} chunk manifest is invalid")
        total = 0
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, Mapping) or set(chunk) != {
                "index",
                "size_bytes",
                "sha256",
            }:
                raise EnvironmentPreimageError(f"{label} chunk shape drifted")
            chunk_length = chunk.get("size_bytes")
            if (
                chunk.get("index") != index
                or isinstance(chunk_length, bool)
                or not isinstance(chunk_length, int)
                or not 1 <= chunk_length <= chunk_size
                or (index < len(chunks) - 1 and chunk_length != chunk_size)
            ):
                raise EnvironmentPreimageError(f"{label} chunk sequence drifted")
            _require_sha256(chunk.get("sha256"), f"{label} chunk")
            total += chunk_length
        if total != size or canonical_sha256(chunks) != preimage.get(
            "manifest_sha256"
        ):
            raise EnvironmentPreimageError(f"{label} chunk manifest root drifted")
    else:
        raise EnvironmentPreimageError(f"{label} preimage kind is unsupported")
    return row


def _capture_environment(environ: Mapping[str, str]) -> dict[str, object]:
    values: dict[str, object] = {}
    for name in NONSECRET_ENV_ALLOWLIST:
        present = name in environ
        value = environ.get(name) if present else None
        if present and (
            not isinstance(value, str)
            or "\x00" in value
            or len(value.encode("utf-8")) > MAX_ENV_VALUE_BYTES
        ):
            raise EnvironmentPreimageError(f"allowlisted environment value is invalid: {name}")
        values[name] = {"present": present, "value": value}
    return values


def _labels(values: Mapping[str, str] | None) -> dict[str, str]:
    labels = {} if values is None else dict(values)
    if not set(labels) <= set(NONSECRET_LABEL_ALLOWLIST):
        raise EnvironmentPreimageError("runtime label is not explicitly allowlisted")
    for name, value in labels.items():
        if (
            not isinstance(value, str)
            or not value
            or "\x00" in value
            or len(value.encode("utf-8")) > MAX_ENV_VALUE_BYTES
        ):
            raise EnvironmentPreimageError(f"runtime label is invalid: {name}")
        if name in {"model_upstream_endpoint", "spool_endpoint"}:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise EnvironmentPreimageError(
                    f"{name} label must be credential-free"
                )
            if (
                name == "model_upstream_endpoint"
                and parsed.path != "/v1/chat/completions"
            ):
                raise EnvironmentPreimageError(
                    "model_upstream_endpoint must be the exact completions route"
                )
            if name == "spool_endpoint" and parsed.path not in {"", "/"}:
                raise EnvironmentPreimageError(
                    "spool_endpoint must identify the server root"
                )
        if name == "model_deployment_receipt_sha256":
            _require_sha256(value, name)
    return {name: labels[name] for name in sorted(labels)}


def _runtime_preimage(
    *, inline_limit_bytes: int, chunk_size_bytes: int
) -> dict[str, object]:
    executable = Path(sys.executable).expanduser().resolve(strict=True)
    libc_name, libc_version = platform.libc_ver()
    return {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "version_info": [
                sys.version_info.major,
                sys.version_info.minor,
                sys.version_info.micro,
                sys.version_info.releaselevel,
                sys.version_info.serial,
            ],
            "cache_tag": getattr(sys.implementation, "cache_tag", None),
            "abi_flags": getattr(sys, "abiflags", ""),
            "byteorder": sys.byteorder,
            "flags": {
                name: int(getattr(sys.flags, name, 0)) for name in _PYTHON_FLAG_NAMES
            },
            "executable": _capture_file(
                executable,
                inline_limit_bytes=inline_limit_bytes,
                chunk_size_bytes=chunk_size_bytes,
                allow_resolved_symlink=True,
            ),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "libc_name": libc_name,
            "libc_version": libc_version,
        },
    }


def _runtime_projection(runtime: Mapping[str, object]) -> dict[str, object]:
    python = runtime["python"]
    assert isinstance(python, Mapping)
    executable = python["executable"]
    assert isinstance(executable, Mapping)
    return {
        "python": {
            key: python[key]
            for key in (
                "implementation",
                "version",
                "version_info",
                "cache_tag",
                "abi_flags",
                "byteorder",
                "flags",
            )
        }
        | {"executable": _file_projection(executable)},
        "platform": dict(runtime["platform"]),
    }


def _validate_runtime(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"python", "platform"}:
        raise EnvironmentPreimageError("runtime preimage shape drifted")
    runtime = dict(value)
    python = runtime["python"]
    expected_python = {
        "implementation",
        "version",
        "version_info",
        "cache_tag",
        "abi_flags",
        "byteorder",
        "flags",
        "executable",
    }
    if not isinstance(python, Mapping) or set(python) != expected_python:
        raise EnvironmentPreimageError("Python runtime preimage shape drifted")
    for key in ("implementation", "version", "abi_flags", "byteorder"):
        if not isinstance(python.get(key), str):
            raise EnvironmentPreimageError("Python runtime scalar drifted")
    if python.get("cache_tag") is not None and not isinstance(
        python.get("cache_tag"), str
    ):
        raise EnvironmentPreimageError("Python cache tag drifted")
    version_info = python.get("version_info")
    flags = python.get("flags")
    if (
        not isinstance(version_info, list)
        or len(version_info) != 5
        or any(isinstance(item, bool) or not isinstance(item, (int, str)) for item in version_info)
        or not isinstance(flags, Mapping)
        or set(flags) != set(_PYTHON_FLAG_NAMES)
        or any(isinstance(item, bool) or not isinstance(item, int) for item in flags.values())
    ):
        raise EnvironmentPreimageError("Python version/flags drifted")
    _validate_file_preimage(python["executable"], "Python executable")
    platform_value = runtime["platform"]
    if not isinstance(platform_value, Mapping) or set(platform_value) != {
        "system",
        "release",
        "machine",
        "libc_name",
        "libc_version",
    } or any(not isinstance(item, str) for item in platform_value.values()):
        raise EnvironmentPreimageError("platform preimage shape drifted")
    return runtime


def _environment_root_payload(
    *,
    runtime: Mapping[str, object],
    environment: Mapping[str, object],
    labels: Mapping[str, str],
) -> dict[str, object]:
    return {
        "schema_version": ENVIRONMENT_ROOT_SCHEMA,
        "runtime": _runtime_projection(runtime),
        "environment_allowlist": list(NONSECRET_ENV_ALLOWLIST),
        "environment": dict(environment),
        "labels": dict(labels),
    }


def _dependency_root_payload(files: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": DEPENDENCY_ROOT_SCHEMA,
        "files": {
            name: _file_projection(value)
            for name, value in sorted(files.items())
            if isinstance(value, Mapping)
        },
    }


def compatibility_root_sha256(
    environment_root_sha256: str, dependency_root_sha256: str
) -> str:
    """Return the common compatibility root for two verified component roots."""

    return canonical_sha256(
        {
            "schema_version": COMPATIBILITY_ROOT_SCHEMA,
            "environment_root_sha256": _require_sha256(
                environment_root_sha256, "environment root"
            ),
            "dependency_root_sha256": _require_sha256(
                dependency_root_sha256, "dependency root"
            ),
        }
    )


def build_preimage_receipts(
    dependencies: Mapping[str, Path],
    *,
    environ: Mapping[str, str] | None = None,
    labels: Mapping[str, str] | None = None,
    inline_limit_bytes: int = DEFAULT_INLINE_LIMIT_BYTES,
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build deterministic environment and dependency receipts as one pair."""

    policy = _policy(inline_limit_bytes, chunk_size_bytes)
    if not isinstance(dependencies, Mapping) or not dependencies:
        raise EnvironmentPreimageError("at least one dependency preimage is required")
    files: dict[str, object] = {}
    resolved_paths: set[str] = set()
    for name, path in sorted(dependencies.items()):
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise EnvironmentPreimageError("dependency name is not canonical")
        captured = _capture_file(
            Path(path),
            inline_limit_bytes=inline_limit_bytes,
            chunk_size_bytes=chunk_size_bytes,
        )
        resolved = str(captured["resolved_path"])
        if resolved in resolved_paths:
            raise EnvironmentPreimageError("dependency paths must be unique")
        resolved_paths.add(resolved)
        files[name] = captured

    captured_environment = _capture_environment(os.environ if environ is None else environ)
    captured_labels = _labels(labels)
    runtime = _runtime_preimage(
        inline_limit_bytes=inline_limit_bytes,
        chunk_size_bytes=chunk_size_bytes,
    )
    environment_root = canonical_sha256(
        _environment_root_payload(
            runtime=runtime,
            environment=captured_environment,
            labels=captured_labels,
        )
    )
    dependency_root = canonical_sha256(_dependency_root_payload(files))
    compatibility_root = compatibility_root_sha256(environment_root, dependency_root)

    environment_unsigned: dict[str, object] = {
        "schema_version": ENVIRONMENT_SCHEMA,
        "kind": "environment",
        "runtime": runtime,
        "environment_allowlist": list(NONSECRET_ENV_ALLOWLIST),
        "environment": captured_environment,
        "labels": captured_labels,
        "environment_root_sha256": environment_root,
        "compatibility_root_sha256": compatibility_root,
    }
    dependency_unsigned: dict[str, object] = {
        "schema_version": DEPENDENCY_SCHEMA,
        "kind": "dependencies",
        "preimage_policy": policy,
        "files": files,
        "dependency_root_sha256": dependency_root,
        "compatibility_root_sha256": compatibility_root,
    }
    environment_receipt = {
        **environment_unsigned,
        "receipt_sha256": canonical_sha256(environment_unsigned),
    }
    dependency_receipt = {
        **dependency_unsigned,
        "receipt_sha256": canonical_sha256(dependency_unsigned),
    }
    verify_compatibility_pair(environment_receipt, dependency_receipt)
    return environment_receipt, dependency_receipt


def build_preimage_bundle(
    dependencies: Mapping[str, Path],
    *,
    environ: Mapping[str, str] | None = None,
    labels: Mapping[str, str] | None = None,
    inline_limit_bytes: int = DEFAULT_INLINE_LIMIT_BYTES,
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> dict[str, object]:
    """Build one deterministic, self-hashed bundle around both receipts."""

    environment, dependency = build_preimage_receipts(
        dependencies,
        environ=environ,
        labels=labels,
        inline_limit_bytes=inline_limit_bytes,
        chunk_size_bytes=chunk_size_bytes,
    )
    compatibility_root = verify_compatibility_pair(environment, dependency)
    unsigned: dict[str, object] = {
        "schema_version": BUNDLE_SCHEMA,
        "environment_receipt": environment,
        "dependency_receipt": dependency,
        "compatibility_root_sha256": compatibility_root,
    }
    bundle = {**unsigned, "bundle_sha256": canonical_sha256(unsigned)}
    verify_preimage_bundle(bundle)
    return bundle


def verify_environment_receipt(
    value: Mapping[str, object],
    *,
    verify_live: bool = False,
    environ: Mapping[str, str] | None = None,
) -> str:
    expected = {
        "schema_version",
        "kind",
        "runtime",
        "environment_allowlist",
        "environment",
        "labels",
        "environment_root_sha256",
        "compatibility_root_sha256",
        "receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise EnvironmentPreimageError("environment receipt shape drifted")
    receipt = dict(value)
    if (
        receipt.get("schema_version") != ENVIRONMENT_SCHEMA
        or receipt.get("kind") != "environment"
        or receipt.get("environment_allowlist") != list(NONSECRET_ENV_ALLOWLIST)
    ):
        raise EnvironmentPreimageError("environment receipt policy drifted")
    environment = receipt.get("environment")
    if not isinstance(environment, Mapping) or set(environment) != set(
        NONSECRET_ENV_ALLOWLIST
    ):
        raise EnvironmentPreimageError("environment allowlist coverage drifted")
    for name, row in environment.items():
        if not isinstance(row, Mapping) or set(row) != {"present", "value"}:
            raise EnvironmentPreimageError(f"environment row drifted: {name}")
        present = row.get("present")
        env_value = row.get("value")
        if (
            not isinstance(present, bool)
            or (present and not isinstance(env_value, str))
            or (not present and env_value is not None)
            or (
                isinstance(env_value, str)
                and ("\x00" in env_value or len(env_value.encode("utf-8")) > MAX_ENV_VALUE_BYTES)
            )
        ):
            raise EnvironmentPreimageError(f"environment value drifted: {name}")
    labels = receipt.get("labels")
    if not isinstance(labels, Mapping) or _labels(labels) != dict(labels):
        raise EnvironmentPreimageError("environment labels drifted")
    runtime = _validate_runtime(receipt.get("runtime"))
    expected_root = canonical_sha256(
        _environment_root_payload(
            runtime=runtime,
            environment=environment,
            labels=labels,
        )
    )
    if expected_root != receipt.get("environment_root_sha256"):
        raise EnvironmentPreimageError("environment component root drifted")
    _require_sha256(receipt.get("compatibility_root_sha256"), "compatibility root")
    unsigned = dict(receipt)
    declared = unsigned.pop("receipt_sha256", None)
    if canonical_sha256(unsigned) != declared:
        raise EnvironmentPreimageError("environment receipt self-hash drifted")
    if verify_live:
        current_environment = _capture_environment(
            os.environ if environ is None else environ
        )
        if current_environment != dict(environment):
            raise EnvironmentPreimageError("live allowlisted environment drifted")
        python = runtime["python"]
        assert isinstance(python, Mapping)
        executable = python["executable"]
        assert isinstance(executable, Mapping)
        preimage = executable["preimage"]
        assert isinstance(preimage, Mapping)
        is_inline = preimage.get("kind") == "inline-base64"
        current_runtime = _runtime_preimage(
            inline_limit_bytes=(int(executable["size_bytes"]) if is_inline else 0),
            chunk_size_bytes=int(
                preimage.get("chunk_size_bytes", DEFAULT_CHUNK_SIZE_BYTES)
            ),
        )
        if _runtime_projection(current_runtime) != _runtime_projection(runtime):
            raise EnvironmentPreimageError("live runtime preimage drifted")
    return _require_sha256(declared, "environment receipt")


def verify_dependency_receipt(
    value: Mapping[str, object], *, verify_live: bool = False
) -> str:
    expected = {
        "schema_version",
        "kind",
        "preimage_policy",
        "files",
        "dependency_root_sha256",
        "compatibility_root_sha256",
        "receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise EnvironmentPreimageError("dependency receipt shape drifted")
    receipt = dict(value)
    if receipt.get("schema_version") != DEPENDENCY_SCHEMA or receipt.get(
        "kind"
    ) != "dependencies":
        raise EnvironmentPreimageError("dependency receipt policy drifted")
    policy = receipt.get("preimage_policy")
    if not isinstance(policy, Mapping) or set(policy) != {
        "inline_limit_bytes",
        "chunk_size_bytes",
    }:
        raise EnvironmentPreimageError("dependency preimage policy drifted")
    normalized_policy = _policy(
        policy.get("inline_limit_bytes"), policy.get("chunk_size_bytes")
    )
    files = receipt.get("files")
    if not isinstance(files, Mapping) or not files:
        raise EnvironmentPreimageError("dependency files are absent")
    normalized_files: dict[str, object] = {}
    resolved_paths: set[str] = set()
    for name, raw in sorted(files.items()):
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise EnvironmentPreimageError("dependency name is not canonical")
        row = _validate_file_preimage(raw, f"dependency {name}")
        resolved = str(row["resolved_path"])
        if resolved in resolved_paths:
            raise EnvironmentPreimageError("dependency paths repeat")
        resolved_paths.add(resolved)
        normalized_files[name] = row
    expected_root = canonical_sha256(_dependency_root_payload(normalized_files))
    if expected_root != receipt.get("dependency_root_sha256"):
        raise EnvironmentPreimageError("dependency component root drifted")
    _require_sha256(receipt.get("compatibility_root_sha256"), "compatibility root")
    unsigned = dict(receipt)
    declared = unsigned.pop("receipt_sha256", None)
    if canonical_sha256(unsigned) != declared:
        raise EnvironmentPreimageError("dependency receipt self-hash drifted")
    if verify_live:
        for name, expected_file in normalized_files.items():
            preimage = expected_file["preimage"]
            assert isinstance(preimage, Mapping)
            is_inline = preimage.get("kind") == "inline-base64"
            chunk_size = int(
                preimage.get(
                    "chunk_size_bytes", normalized_policy["chunk_size_bytes"]
                )
            )
            live = _capture_file(
                Path(str(expected_file["resolved_path"])),
                inline_limit_bytes=(
                    int(expected_file["size_bytes"]) if is_inline else 0
                ),
                chunk_size_bytes=chunk_size,
            )
            if live != expected_file:
                raise EnvironmentPreimageError(f"live dependency drifted: {name}")
    return _require_sha256(declared, "dependency receipt")


def verify_compatibility_pair(
    environment_receipt: Mapping[str, object],
    dependency_receipt: Mapping[str, object],
    *,
    verify_live: bool = False,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Self-verify both receipts and return their common compatibility root."""

    verify_environment_receipt(
        environment_receipt, verify_live=verify_live, environ=environ
    )
    verify_dependency_receipt(dependency_receipt, verify_live=verify_live)
    expected = compatibility_root_sha256(
        str(environment_receipt["environment_root_sha256"]),
        str(dependency_receipt["dependency_root_sha256"]),
    )
    if (
        environment_receipt.get("compatibility_root_sha256") != expected
        or dependency_receipt.get("compatibility_root_sha256") != expected
    ):
        raise EnvironmentPreimageError("environment/dependency compatibility roots differ")
    return expected


def verify_named_dependency_paths(
    dependency_receipt: Mapping[str, object],
    expected_paths: Mapping[str, Path],
    *,
    verify_live: bool = False,
) -> str:
    """Verify both dependency bytes and the closed-world semantic name/path map."""

    receipt_sha = verify_dependency_receipt(
        dependency_receipt, verify_live=verify_live
    )
    files = dependency_receipt.get("files")
    if not isinstance(files, Mapping) or set(files) != set(expected_paths):
        raise EnvironmentPreimageError("dependency semantic-name inventory drifted")
    for name, expected_path in expected_paths.items():
        row = files.get(name)
        declared_path = Path(expected_path).expanduser()
        try:
            before = declared_path.lstat()
            if stat.S_ISLNK(before.st_mode):
                raise EnvironmentPreimageError(
                    f"dependency semantic path is a symlink: {name}"
                )
            resolved = str(declared_path.resolve(strict=True))
        except EnvironmentPreimageError:
            raise
        except OSError as error:
            raise EnvironmentPreimageError(
                f"dependency semantic path is unavailable: {name}"
            ) from error
        if (
            not isinstance(row, Mapping)
            or row.get("resolved_path") != resolved
        ):
            raise EnvironmentPreimageError(
                f"dependency semantic path drifted: {name}"
            )
    return receipt_sha


def r8_dependency_paths(
    *,
    protocol_path: Path,
    judge_core_path: Path,
    result_contract_path: Path,
    tokenizer_dir: Path,
    model_catalog_path: Path,
    model_weight_receipt_path: Path,
    python_lock_path: Path,
) -> dict[str, Path]:
    """Return the closed-world semantic path map used by the r8 runtime."""

    module_dir = Path(__file__).resolve().parent
    paths = {
        "runner": module_dir / "prom9_f1_r8_runner.py",
        "private_output": module_dir / "prom9_f1_r8_private_output.py",
        "environment": module_dir / "prom9_f1_r8_environment.py",
        "lock_builder": module_dir / "prom9_f1_r8_lock.py",
        "power_builder": module_dir / "prom9_f1_r8_power.py",
        "power_cli": module_dir / "prom9_f1_r8_power_cli.py",
        "prior_exposure": module_dir / "prom9_f1_prior_exposure.py",
        "data_preparer_core": module_dir / "prom9_prepare_2wiki_f1.py",
        "function_network_adapter": module_dir / "prom_f1_function_network.py",
        "protocol_loader": module_dir / "prom9_protocol.py",
        "terminal_transport_exporter": module_dir / "prom9_f1_r8_transport_audit.py",
        "function_network": module_dir / "hswm_function_network.py",
        "durable_transport": module_dir / "hswm_f1_durable_transport.py",
        "sqlite_schema_authority": module_dir / "hswm_f1_sqlite_schema.py",
        "result_spool": module_dir / "hswm_result_spool.py",
        "call_receipt": module_dir / "hswm_call_receipt.py",
        "function_registry": module_dir / "hswm_function_registry.py",
        "token_meter": module_dir / "hswm_token_meter.py",
        "typed_ports": module_dir / "hswm_typed_ports.py",
        "token_envelope": module_dir / "prom9_f1_envelope.py",
        "token_envelope_derivation": module_dir / "prom9_f1_r8_envelope.py",
        "token_meter_validator": module_dir / "prom9_validate_token_meter.py",
        "model_deployment_receipt_code": (
            module_dir.parent / "model_deployment_receipt.py"
        ),
        "model_snapshot_attestation_core": module_dir.parent / "bge_m3_embed.py",
        "protocol_json": Path(protocol_path),
        "data_preparer": module_dir / "prom9_f1_r8_source.py",
        "judge_core": Path(judge_core_path),
        "result_contract": Path(result_contract_path),
        "tokenizer_vocab": Path(tokenizer_dir) / "vocab.json",
        "tokenizer_merges": Path(tokenizer_dir) / "merges.txt",
        "tokenizer_config": Path(tokenizer_dir) / "tokenizer_config.json",
        "model_catalog": Path(model_catalog_path),
        "model_deployment_receipt": Path(model_weight_receipt_path),
        "python_lock": Path(python_lock_path),
    }
    if set(paths) != set(R8_DEPENDENCY_NAMES):
        raise EnvironmentPreimageError("r8 dependency inventory drifted")
    return paths


def r8_c801_dependency_paths(
    *,
    protocol_path: Path,
    judge_core_path: Path,
    result_contract_path: Path,
    tokenizer_dir: Path,
    model_catalog_path: Path,
    model_weight_receipt_path: Path,
    python_lock_path: Path,
) -> dict[str, Path]:
    """Return the c801 generation's closed-world semantic dependency map."""

    module_dir = Path(__file__).resolve().parent
    paths = r8_dependency_paths(
        protocol_path=protocol_path,
        judge_core_path=judge_core_path,
        result_contract_path=result_contract_path,
        tokenizer_dir=tokenizer_dir,
        model_catalog_path=model_catalog_path,
        model_weight_receipt_path=model_weight_receipt_path,
        python_lock_path=python_lock_path,
    )
    paths.update(
        {
            "lock_builder": module_dir / "prom9_f1_r8_lock_v6.py",
            "token_envelope_derivation": (
                module_dir / "prom9_f1_r8_envelope_v6.py"
            ),
            "data_preparer": module_dir / "prom9_f1_r8_source_v6.py",
            "selection_builder": module_dir / "prom9_f1_r8_selection_v6.py",
        }
    )
    if tuple(paths) != R8_C801_DEPENDENCY_NAMES:
        raise EnvironmentPreimageError("r8 c801 dependency inventory drifted")
    return paths


def r8_environment_labels(
    *,
    spool_endpoint: str,
    model_upstream_endpoint: str,
    model_deployment_receipt_sha256: str,
    model: str,
    model_revision: str,
    run_id: str,
    hswm_commit: str,
    symposium_commit: str,
) -> dict[str, str]:
    labels = {
        "spool_endpoint": spool_endpoint,
        "model_upstream_endpoint": model_upstream_endpoint,
        "model_deployment_receipt_sha256": model_deployment_receipt_sha256,
        "model": model,
        "model_revision": model_revision,
        "run_id": run_id,
        "hswm_commit": hswm_commit,
        "symposium_commit": symposium_commit,
    }
    if (
        _GIT_COMMIT.fullmatch(hswm_commit) is None
        or _GIT_COMMIT.fullmatch(symposium_commit) is None
    ):
        raise EnvironmentPreimageError(
            "repository commit labels must be full lowercase commits"
        )
    if _GIT_COMMIT.fullmatch(model_revision) is None:
        raise EnvironmentPreimageError(
            "model revision label must be an exact lowercase 40-hex revision"
        )
    if _SHA256.fullmatch(model_deployment_receipt_sha256) is None:
        raise EnvironmentPreimageError(
            "model deployment receipt label must be a lowercase SHA-256 digest"
        )
    return _labels(labels)


def _isolated_git_environment() -> dict[str, str]:
    """Keep ambient Git control variables outside frozen-authority reads."""

    environ = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environ["GIT_NO_REPLACE_OBJECTS"] = "1"
    environ["GIT_LITERAL_PATHSPECS"] = "1"
    return environ


def verify_repository_commit(repo_root: Path, expected_commit: str) -> str:
    """Bind the non-secret commit label to the live checkout without requiring clean foreign state."""

    if _GIT_COMMIT.fullmatch(expected_commit) is None:
        raise EnvironmentPreimageError("HSWM commit label is not a full lowercase commit")
    try:
        result = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(Path(repo_root).resolve(strict=True)),
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=_isolated_git_environment(),
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise EnvironmentPreimageError("cannot read the live HSWM commit") from error
    observed = result.stdout.strip()
    if _GIT_COMMIT.fullmatch(observed) is None or observed != expected_commit:
        raise EnvironmentPreimageError("live HSWM commit differs from the environment label")
    return observed


def _git_repository_bytes(
    repo: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    """Run one replace-ref-immune Git read against an already resolved repo."""

    try:
        return subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(repo),
                *arguments,
            ],
            check=check,
            capture_output=True,
            env=_isolated_git_environment(),
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise EnvironmentPreimageError(
            "cannot read repository dependency from the frozen commit"
        ) from error


def verify_repository_dependency_blobs(
    repo_root: Path,
    expected_commit: str,
    expected_paths: Mapping[str, Path],
    *,
    required_names: Collection[str] = R8_COMMIT_BOUND_DEPENDENCY_NAMES,
) -> tuple[str, ...]:
    """Require every code dependency to be the exact committed blob.

    Unrelated dirty paths and explicitly external receipts remain permitted.
    An r8 code dependency cannot be untracked, staged away from the commit, or
    modified in the worktree while the environment still claims that commit.
    """

    repo = Path(repo_root).resolve(strict=True)
    verify_repository_commit(repo, expected_commit)
    relative_paths: list[str] = []
    for name, raw_path in expected_paths.items():
        if name not in required_names:
            continue
        declared = Path(os.path.abspath(os.fspath(Path(raw_path))))
        try:
            declared_stat = declared.lstat()
            canonical = declared.resolve(strict=True)
        except OSError as error:
            raise EnvironmentPreimageError(
                f"dependency semantic path is unavailable: {name}"
            ) from error
        if stat.S_ISLNK(declared_stat.st_mode) or not stat.S_ISREG(
            declared_stat.st_mode
        ):
            raise EnvironmentPreimageError(
                f"commit-bound dependency must be a regular non-symlink file: {name}"
            )
        if canonical != declared:
            raise EnvironmentPreimageError(
                f"commit-bound dependency path is not canonical: {name}"
            )
        if not canonical.is_relative_to(repo):
            raise EnvironmentPreimageError(
                f"commit-bound dependency is outside its declared repository: {name}"
            )
        relative = declared.relative_to(repo).as_posix()
        tree = _git_repository_bytes(
            repo, "ls-tree", "-z", expected_commit, "--", relative
        ).stdout
        entries = [entry for entry in tree.split(b"\0") if entry]
        if len(entries) != 1:
            raise EnvironmentPreimageError(
                f"repository dependency is absent from the frozen commit: {name}"
            )
        metadata, separator, committed_path = entries[0].partition(b"\t")
        fields = metadata.split(b" ")
        if (
            separator != b"\t"
            or len(fields) != 3
            or committed_path != os.fsencode(relative)
        ):
            raise EnvironmentPreimageError(
                f"repository dependency tree entry is ambiguous: {name}"
            )
        tree_mode, object_type, object_id = fields
        if object_type != b"blob" or tree_mode not in {b"100644", b"100755"}:
            rendered_mode = tree_mode.decode("ascii", errors="replace")
            raise EnvironmentPreimageError(
                f"unsupported committed tree mode {rendered_mode}: {name}"
            )
        observed = _capture_file(
            declared,
            inline_limit_bytes=DEFAULT_INLINE_LIMIT_BYTES,
            chunk_size_bytes=DEFAULT_CHUNK_SIZE_BYTES,
        )
        if observed["resolved_path"] != str(declared):
            raise EnvironmentPreimageError(
                f"repository dependency path changed while hashing: {name}"
            )
        observed_mode = int(str(observed["mode"]), 8)
        if bool(observed_mode & stat.S_IXUSR) != (tree_mode == b"100755"):
            raise EnvironmentPreimageError(
                f"repository dependency Git executable mode differs from the frozen commit: {name}"
            )
        try:
            object_name = object_id.decode("ascii")
        except UnicodeDecodeError as error:
            raise EnvironmentPreimageError(
                f"repository dependency object ID is invalid: {name}"
            ) from error
        committed_blob = _git_repository_bytes(
            repo, "cat-file", "blob", object_name
        ).stdout
        if (
            len(committed_blob) != observed["size_bytes"]
            or hashlib.sha256(committed_blob).hexdigest() != observed["sha256"]
        ):
            raise EnvironmentPreimageError(
                f"repository dependency blob differs from the frozen commit: {name}"
            )
        relative_paths.append(relative)
    if relative_paths:
        worktree = _git_repository_bytes(
            repo,
            "diff",
            "--quiet",
            expected_commit,
            "--",
            *relative_paths,
            check=False,
        )
        staged = _git_repository_bytes(
            repo,
            "diff",
            "--cached",
            "--quiet",
            expected_commit,
            "--",
            *relative_paths,
            check=False,
        )
        if worktree.returncode not in {0, 1} or staged.returncode not in {0, 1}:
            raise EnvironmentPreimageError(
                "cannot compare repository dependencies with the frozen commit"
            )
        if worktree.returncode != 0 or staged.returncode != 0:
            raise EnvironmentPreimageError(
                "an r8 repository dependency differs from the frozen commit"
            )
    verify_repository_commit(repo, expected_commit)
    return tuple(sorted(relative_paths))


def verify_environment_labels(
    environment_receipt: Mapping[str, object],
    expected_labels: Mapping[str, str],
    *,
    verify_live: bool = False,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Verify the live runtime plus the exact closed-world non-secret labels."""

    declared = verify_environment_receipt(
        environment_receipt, verify_live=verify_live, environ=environ
    )
    if environment_receipt.get("labels") != _labels(expected_labels):
        raise EnvironmentPreimageError("environment semantic labels drifted")
    return declared


def verify_r8_preimage_bundle(
    value: Mapping[str, object],
    *,
    expected_paths: Mapping[str, Path],
    expected_labels: Mapping[str, str],
    repo_root: Path,
    symposium_repo_root: Path,
    verify_live: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Verify the r8 bundle, semantic path/label identities, and live commit."""

    compatibility_root = verify_preimage_bundle(
        value, verify_live=verify_live, environ=environ
    )
    environment = value.get("environment_receipt")
    dependencies = value.get("dependency_receipt")
    if not isinstance(environment, Mapping) or not isinstance(dependencies, Mapping):
        raise EnvironmentPreimageError("r8 bundle receipts are absent")
    labels = r8_environment_labels(
        spool_endpoint=str(expected_labels.get("spool_endpoint", "")),
        model_upstream_endpoint=str(
            expected_labels.get("model_upstream_endpoint", "")
        ),
        model_deployment_receipt_sha256=str(
            expected_labels.get("model_deployment_receipt_sha256", "")
        ),
        model=str(expected_labels.get("model", "")),
        model_revision=str(expected_labels.get("model_revision", "")),
        run_id=str(expected_labels.get("run_id", "")),
        hswm_commit=str(expected_labels.get("hswm_commit", "")),
        symposium_commit=str(expected_labels.get("symposium_commit", "")),
    )
    environment_sha = verify_environment_labels(
        environment, labels, verify_live=False
    )
    dependency_sha = verify_named_dependency_paths(
        dependencies, expected_paths, verify_live=False
    )
    verify_repository_dependency_blobs(
        repo_root, labels["hswm_commit"], expected_paths
    )
    verify_repository_dependency_blobs(
        symposium_repo_root,
        labels["symposium_commit"],
        expected_paths,
        required_names=R8_SYMPOSIUM_COMMIT_BOUND_DEPENDENCY_NAMES,
    )
    bundle_sha = value.get("bundle_sha256")
    _require_sha256(bundle_sha, "preimage bundle")
    return {
        "bundle_sha256": str(bundle_sha),
        "compatibility_root_sha256": compatibility_root,
        "environment_receipt_sha256": environment_sha,
        "dependency_receipt_sha256": dependency_sha,
    }


def verify_r8_c801_preimage_bundle(
    value: Mapping[str, object],
    *,
    expected_paths: Mapping[str, Path],
    expected_labels: Mapping[str, str],
    repo_root: Path,
    symposium_repo_root: Path,
    verify_live: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Verify the c801 v6 dependency inventory without widening older runs."""

    if tuple(expected_paths) != R8_C801_DEPENDENCY_NAMES:
        raise EnvironmentPreimageError("r8 c801 dependency inventory drifted")
    verified = verify_r8_preimage_bundle(
        value,
        expected_paths=expected_paths,
        expected_labels=expected_labels,
        repo_root=repo_root,
        symposium_repo_root=symposium_repo_root,
        verify_live=verify_live,
        environ=environ,
    )
    verify_repository_dependency_blobs(
        repo_root,
        str(expected_labels.get("hswm_commit", "")),
        expected_paths,
        required_names=R8_C801_ADDITIONAL_COMMIT_BOUND_DEPENDENCY_NAMES,
    )
    return verified


def verify_preimage_bundle(
    value: Mapping[str, object],
    *,
    verify_live: bool = False,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Verify exact bundle/subreceipt schemas and return the compatibility root."""

    expected_keys = {
        "schema_version",
        "environment_receipt",
        "dependency_receipt",
        "compatibility_root_sha256",
        "bundle_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise EnvironmentPreimageError("preimage bundle top-level shape drifted")
    bundle = dict(value)
    if bundle.get("schema_version") != BUNDLE_SCHEMA:
        raise EnvironmentPreimageError("preimage bundle schema drifted")
    environment = bundle.get("environment_receipt")
    dependencies = bundle.get("dependency_receipt")
    if not isinstance(environment, Mapping) or not isinstance(dependencies, Mapping):
        raise EnvironmentPreimageError("preimage bundle entries are absent")
    compatibility_root = verify_compatibility_pair(
        environment,
        dependencies,
        verify_live=verify_live,
        environ=environ,
    )
    if bundle.get("compatibility_root_sha256") != compatibility_root:
        raise EnvironmentPreimageError("preimage bundle compatibility root drifted")
    unsigned = dict(bundle)
    declared = unsigned.pop("bundle_sha256", None)
    if canonical_sha256(unsigned) != declared:
        raise EnvironmentPreimageError("preimage bundle self-hash drifted")
    _require_sha256(declared, "preimage bundle")
    return compatibility_root


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_private_once(path: Path, value: Mapping[str, object]) -> str:
    """Atomically publish one validated 0600 receipt without replacement."""

    schema = value.get("schema_version") if isinstance(value, Mapping) else None
    if schema == BUNDLE_SCHEMA:
        verify_preimage_bundle(value)
    elif schema == ENVIRONMENT_SCHEMA:
        verify_environment_receipt(value)
    elif schema == DEPENDENCY_SCHEMA:
        verify_dependency_receipt(value)
    else:
        raise EnvironmentPreimageError("unsupported private receipt schema")
    output = Path(path).expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (canonical_json(value) + "\n").encode("utf-8")
    descriptor, raw_temp = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.pending-"
    )
    temporary = Path(raw_temp)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError as error:
            raise EnvironmentPreimageError("private receipt is first-write-wins") from error
        _fsync_directory(output.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EnvironmentPreimageError("private receipt contains a duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise EnvironmentPreimageError("private receipt contains a non-finite number")


def load_private_receipt(
    path: Path, *, verify_live: bool = False, environ: Mapping[str, str] | None = None
) -> dict[str, object]:
    """Load strict private JSON and dispatch to its schema self-verifier."""

    target = Path(path)
    try:
        before = target.lstat()
    except OSError as error:
        raise EnvironmentPreimageError("private receipt is unavailable") from error
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or stat.S_IMODE(before.st_mode) & 0o077
        or before.st_size > MAX_PRIVATE_RECEIPT_BYTES
    ):
        raise EnvironmentPreimageError("private receipt permissions/type/size are invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags)
    try:
        opened = os.fstat(descriptor)
        raw = bytearray()
        while block := os.read(descriptor, 1024 * 1024):
            raw.extend(block)
            if len(raw) > MAX_PRIVATE_RECEIPT_BYTES:
                raise EnvironmentPreimageError("private receipt exceeds the size bound")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        path_after = target.lstat()
    except OSError as error:
        raise EnvironmentPreimageError("private receipt disappeared while reading") from error
    if (
        _stat_identity(opened) != _stat_identity(after)
        or _stat_identity(opened) != _stat_identity(path_after)
        or len(raw) != opened.st_size
    ):
        raise EnvironmentPreimageError("private receipt changed while being read")
    try:
        value = json.loads(
            bytes(raw).decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except EnvironmentPreimageError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise EnvironmentPreimageError("private receipt is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise EnvironmentPreimageError("private receipt must be a JSON object")
    if value.get("schema_version") == BUNDLE_SCHEMA:
        verify_preimage_bundle(value, verify_live=verify_live, environ=environ)
    elif value.get("schema_version") == ENVIRONMENT_SCHEMA:
        verify_environment_receipt(value, verify_live=verify_live, environ=environ)
    elif value.get("schema_version") == DEPENDENCY_SCHEMA:
        verify_dependency_receipt(value, verify_live=verify_live)
    else:
        raise EnvironmentPreimageError("private receipt schema is unsupported")
    return value


def _named_path(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or _NAME.fullmatch(name) is None or not raw_path:
        raise argparse.ArgumentTypeError("dependency must be canonical NAME=PATH")
    return name, Path(raw_path)


def _named_label(value: str) -> tuple[str, str]:
    name, separator, raw_value = value.partition("=")
    if not separator or name not in NONSECRET_LABEL_ALLOWLIST or not raw_value:
        raise argparse.ArgumentTypeError("label is not explicitly allowlisted NAME=VALUE")
    return name, raw_value


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture", help="capture a new receipt pair")
    capture.add_argument("--dependency", action="append", type=_named_path, required=True)
    capture.add_argument("--label", action="append", type=_named_label, default=[])
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument(
        "--inline-limit-bytes", type=int, default=DEFAULT_INLINE_LIMIT_BYTES
    )
    capture.add_argument(
        "--chunk-size-bytes", type=int, default=DEFAULT_CHUNK_SIZE_BYTES
    )
    verify = commands.add_parser("verify", help="self-verify a stored receipt pair")
    verify.add_argument("--input", type=Path, required=True)
    verify.add_argument("--live", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    try:
        if args.command == "capture":
            dependencies = dict(args.dependency)
            labels = dict(args.label)
            if len(dependencies) != len(args.dependency) or len(labels) != len(args.label):
                raise EnvironmentPreimageError("dependency/label names must be unique")
            bundle = build_preimage_bundle(
                dependencies,
                labels=labels,
                inline_limit_bytes=args.inline_limit_bytes,
                chunk_size_bytes=args.chunk_size_bytes,
            )
            write_private_once(args.output, bundle)
            result = {
                "status": "CAPTURED",
                "compatibility_root_sha256": bundle["compatibility_root_sha256"],
                "bundle_sha256": bundle["bundle_sha256"],
                "dependency_count": len(
                    bundle["dependency_receipt"]["files"]
                ),
            }
        else:
            bundle = load_private_receipt(args.input, verify_live=args.live)
            root = verify_preimage_bundle(bundle, verify_live=args.live)
            result = {
                "status": "VERIFIED",
                "compatibility_root_sha256": root,
                "live": bool(args.live),
            }
    except Exception:
        print(json.dumps({"status": "REFUSED"}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
