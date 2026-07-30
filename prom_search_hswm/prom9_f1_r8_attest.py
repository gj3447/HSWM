#!/usr/bin/env python3
"""Freeze exact runtime/dependency preimages for HSWM F1 r8."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_prior_exposure import write_private_once


SCHEMAS = {
    "environment": "hswm-prom9-f1-r8-environment-attestation/v1",
    "dependencies": "hswm-prom9-f1-r8-dependency-preimages/v1",
}
REQUIRED_ENVIRONMENT_FILES = (
    "model_catalog", "tokenizer_vocab", "tokenizer_merges", "tokenizer_config",
)
REQUIRED_ENVIRONMENT_VALUES = ("endpoint", "model", "model_revision", "run_id")
REQUIRED_DEPENDENCY_FILES = (
    "runner", "function_network", "durable_transport", "result_spool",
    "call_receipt", "function_registry", "token_meter", "typed_ports",
    "token_envelope", "protocol_json", "data_preparer", "model_weight_receipt",
    "python_lock", "judge_core",
)
REQUIRED_DEPENDENCY_VALUES = ("hswm_commit",)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MODE = re.compile(r"^0o[0-7]{3,4}$")


class AttestationRefusal(RuntimeError):
    pass


def _named(value: str) -> tuple[str, str]:
    try:
        name, payload = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("entry must be NAME=VALUE") from error
    if not name or not payload:
        raise argparse.ArgumentTypeError("entry must contain non-empty NAME and VALUE")
    return name, payload


def _file_preimage(path: Path) -> dict[str, object]:
    target = Path(path)
    try:
        path_before = target.lstat()
    except OSError as error:
        raise AttestationRefusal(f"cannot stat dependency preimage: {target}") from error
    if stat.S_ISLNK(path_before.st_mode) or not stat.S_ISREG(path_before.st_mode):
        raise AttestationRefusal("dependency preimage must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as error:
        raise AttestationRefusal(f"cannot open dependency preimage: {target}") from error
    digest = hashlib.sha256()
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_dev != path_before.st_dev
            or info.st_ino != path_before.st_ino
        ):
            raise AttestationRefusal("dependency preimage changed before hashing")
        while block := os.read(descriptor, 1024 * 1024):
            digest.update(block)
        descriptor_after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        path_after = target.lstat()
    except OSError as error:
        raise AttestationRefusal("dependency preimage disappeared while hashing") from error
    identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    if identity != (
        descriptor_after.st_dev,
        descriptor_after.st_ino,
        descriptor_after.st_size,
        descriptor_after.st_mtime_ns,
    ) or identity != (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_size,
        path_after.st_mtime_ns,
    ):
        raise AttestationRefusal("dependency preimage changed while hashing")
    return {
        "resolved_path": str(target.resolve()),
        "size": int(info.st_size),
        "mode": oct(stat.S_IMODE(info.st_mode)),
        "sha256": digest.hexdigest(),
    }


def verify_attestation(
    value: Mapping[str, object],
    *,
    kind: str,
    required_files: Sequence[str] = (),
    required_values: Sequence[str] = (),
    verify_live_files: bool = False,
) -> str:
    expected = {
        "schema_version", "kind", "observed_at", "host", "files", "values",
        "receipt_sha256",
    }
    if set(value) != expected or kind not in SCHEMAS:
        raise AttestationRefusal("attestation shape or requested kind is invalid")
    unsigned = dict(value)
    declared = unsigned.pop("receipt_sha256", None)
    if (
        value.get("schema_version") != SCHEMAS[kind]
        or value.get("kind") != kind
        or not isinstance(value.get("observed_at"), str)
        or not value["observed_at"]
        or not isinstance(declared, str)
        or not _SHA256.fullmatch(declared)
        or canonical_sha256(unsigned) != declared
    ):
        raise AttestationRefusal("attestation identity or self-hash drifted")
    host = value.get("host")
    if not isinstance(host, Mapping) or set(host) != {
        "hostname", "platform", "python_version", "python_executable", "cwd",
    } or any(not isinstance(item, str) or not item for item in host.values()):
        raise AttestationRefusal("attestation host identity drifted")
    files = value.get("files")
    values = value.get("values")
    if not isinstance(files, Mapping) or not files or not isinstance(values, Mapping):
        raise AttestationRefusal("attestation files or values are malformed")
    if not set(required_files) <= set(files) or not set(required_values) <= set(values):
        raise AttestationRefusal("attestation is missing a required semantic preimage")
    for name, raw in files.items():
        if not isinstance(name, str) or not name or not isinstance(raw, Mapping) or set(raw) != {
            "resolved_path", "size", "mode", "sha256",
        }:
            raise AttestationRefusal("attestation file entry is malformed")
        resolved = raw.get("resolved_path")
        if (
            not isinstance(resolved, str)
            or not Path(resolved).is_absolute()
            or isinstance(raw.get("size"), bool)
            or not isinstance(raw.get("size"), int)
            or int(raw["size"]) < 0
            or not isinstance(raw.get("mode"), str)
            or not _MODE.fullmatch(str(raw["mode"]))
            or not isinstance(raw.get("sha256"), str)
            or not _SHA256.fullmatch(str(raw["sha256"]))
        ):
            raise AttestationRefusal("attestation file metadata is malformed")
        if verify_live_files and _file_preimage(Path(resolved)) != dict(raw):
            raise AttestationRefusal("live dependency preimage differs from attestation")
    if any(
        not isinstance(name, str)
        or not name
        or not isinstance(payload, str)
        or not payload
        for name, payload in values.items()
    ):
        raise AttestationRefusal("attestation literal values are malformed")
    return declared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=tuple(SCHEMAS), required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--file", action="append", type=_named, default=[])
    parser.add_argument("--value", action="append", type=_named, default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        files = dict(args.file)
        values = dict(args.value)
        if len(files) != len(args.file) or len(values) != len(args.value):
            raise AttestationRefusal("attestation names must be unique")
        if not files:
            raise AttestationRefusal("attestation requires at least one file preimage")
        unsigned = {
            "schema_version": SCHEMAS[args.kind],
            "kind": args.kind,
            "observed_at": args.observed_at,
            "host": {
                "hostname": platform.node(),
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "python_executable": str(Path(sys.executable).resolve()),
                "cwd": str(Path.cwd().resolve()),
            },
            "files": {
                name: _file_preimage(Path(path)) for name, path in sorted(files.items())
            },
            "values": {name: value for name, value in sorted(values.items())},
        }
        receipt = {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}
        write_private_once(args.output, receipt)
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "ATTESTED",
                "kind": args.kind,
                "receipt_sha256": receipt["receipt_sha256"],
                "file_count": len(receipt["files"]),
                "value_count": len(receipt["values"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
