"""Run the exact-pinned Inspect AI preflight outside HSWM execution semantics.

Inspect is an evaluation observer for already bounded research protocols.  It is
not an HSWM transition executor, retry controller, provider transport, canonical
admission path, causal-credit mechanism, or continuous learner.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Mapping, Sequence


INSPECT_AI_VERSION = "0.3.260"
INSPECT_AI_REQUIREMENT = f"inspect-ai=={INSPECT_AI_VERSION}"
RECEIPT_SCHEMA = "hswm-inspect-outer-preflight/v1"
CLAIM_BOUNDARY = (
    "evaluation-infrastructure preflight only; not HSWM cognition, transition "
    "execution, causal credit, canonical learning, or efficacy evidence"
)
_SAFE_ENVIRONMENT_NAMES = (
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "USER",
)
_VERSION_PATTERN = re.compile(r"(?m)^version:\s*([^\s]+)\s*$")


@dataclass(frozen=True)
class InspectPreflightReceipt:
    schema: str
    claim_boundary: str
    requirement: str
    observed_version: str
    uvx_path: str
    uvx_sha256: str
    version_output_sha256: str
    cache_output_sha256: str
    ambient_provider_secrets_inherited: bool
    status: str


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitized_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a credential-minimal environment for no-model Inspect commands."""

    source = os.environ if source is None else source
    environment = {
        name: source[name] for name in _SAFE_ENVIRONMENT_NAMES if name in source
    }
    environment["NO_COLOR"] = "1"
    return environment


def inspect_argv(uvx_path: str, *arguments: str) -> tuple[str, ...]:
    """Build an Inspect command with the dependency pinned outside the repo lock."""

    return (
        uvx_path,
        "--from",
        INSPECT_AI_REQUIREMENT,
        "inspect",
        *arguments,
    )


def _run_no_model(
    uvx_path: str,
    arguments: Sequence[str],
    *,
    timeout_seconds: float,
) -> str:
    completed = subprocess.run(
        inspect_argv(uvx_path, *arguments),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=sanitized_environment(),
        timeout=timeout_seconds,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        stderr_sha256 = sha256(completed.stderr.encode("utf-8")).hexdigest()
        raise RuntimeError(
            "exact-pinned Inspect command failed "
            f"(exit={completed.returncode}, stderr_sha256={stderr_sha256})"
        )
    return completed.stdout


def preflight(
    *,
    uvx_path: str | None = None,
    timeout_seconds: float = 60.0,
) -> InspectPreflightReceipt:
    """Verify the pinned CLI and its cache surface without invoking a model."""

    resolved = uvx_path or shutil.which("uvx")
    if resolved is None:
        raise RuntimeError("uvx is not installed")
    resolved_path = Path(resolved).expanduser().resolve()
    if not resolved_path.is_file() or not os.access(resolved_path, os.X_OK):
        raise RuntimeError(f"uvx is not an executable file: {resolved_path}")

    version_output = _run_no_model(
        str(resolved_path), ("info", "version"), timeout_seconds=timeout_seconds
    )
    match = _VERSION_PATTERN.search(version_output)
    observed_version = match.group(1) if match else ""
    if observed_version != INSPECT_AI_VERSION:
        raise RuntimeError(
            "Inspect version drift: "
            f"expected {INSPECT_AI_VERSION}, observed {observed_version!r}"
        )
    cache_output = _run_no_model(
        str(resolved_path), ("cache", "list"), timeout_seconds=timeout_seconds
    )
    return InspectPreflightReceipt(
        schema=RECEIPT_SCHEMA,
        claim_boundary=CLAIM_BOUNDARY,
        requirement=INSPECT_AI_REQUIREMENT,
        observed_version=observed_version,
        uvx_path=str(resolved_path),
        uvx_sha256=_sha256_file(resolved_path),
        version_output_sha256=sha256(version_output.encode("utf-8")).hexdigest(),
        cache_output_sha256=sha256(cache_output.encode("utf-8")).hexdigest(),
        ambient_provider_secrets_inherited=False,
        status="PASS",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the exact-pinned outer Inspect AI evaluation CLI."
    )
    parser.add_argument("--uvx", help="Override the uvx executable path.")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)
    try:
        receipt = preflight(uvx_path=args.uvx, timeout_seconds=args.timeout)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "claim_boundary": CLAIM_BOUNDARY,
                    "status": "FAIL",
                    "error": f"{type(error).__name__}: {error}",
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
        return 1
    print(
        json.dumps(
            asdict(receipt), ensure_ascii=False, sort_keys=True, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
