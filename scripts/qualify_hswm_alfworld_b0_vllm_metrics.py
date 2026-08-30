#!/usr/bin/env python3
"""Run the separate, pre-selection two-request vLLM metrics qualification."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for _import_root in (REPOSITORY_ROOT, REPOSITORY_ROOT / "src"):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from hswm.experiments.alfworld_b0_dgx import B0DgxLeaseSpec, LaunchRefused
from hswm.experiments.alfworld_b0_vllm_metrics import (
    MetricsQualificationError,
    ProbePaths,
    run_probe,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--declared-source", type=Path, required=True, action="append")
    parser.add_argument("--lock-path", type=Path, required=True)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--model-snapshot", type=Path, required=True)
    parser.add_argument("--hf-cache", type=Path, required=True)
    parser.add_argument("--compile-cache", type=Path, required=True)
    parser.add_argument("--private-receipt", type=Path, required=True)
    parser.add_argument("--public-aggregate", type=Path, required=True)
    parser.add_argument("--allow-public-outside-manifests", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("timeout must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repository = args.repository.resolve(strict=True)
        protocol = args.protocol.resolve(strict=True)
        spec = B0DgxLeaseSpec(repo_root=repository, protocol_path=protocol,
            protocol_sha256=sha256(protocol.read_bytes()).hexdigest(),
            declared_source_paths=tuple(path.resolve(strict=True) for path in args.declared_source),
            lock_path=args.lock_path, container_name=args.container_name,
            model_snapshot=args.model_snapshot, hf_cache=args.hf_cache, compile_cache=args.compile_cache)
        run_probe(ProbePaths(repository=repository, private_receipt=args.private_receipt,
            public_aggregate=args.public_aggregate,
            allow_public_outside_manifests=args.allow_public_outside_manifests,
            lease_spec=spec, timeout_seconds=args.timeout_seconds))
    except (MetricsQualificationError, LaunchRefused, OSError, ValueError) as error:
        print(f"metrics qualification refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
