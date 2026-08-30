"""Replay frozen local, DGX startup/final, and restoration joins for one bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from hswm.experiments import g1_micro
from hswm.experiments.g1_micro_dgx import verify_dgx_execution_receipt
from hswm.selfmod.contracts import canonical_json_bytes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--execution-registry", type=Path, required=True)
    parser.add_argument("--dgx-runtime-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    frozen = g1_micro.verify_frozen_execution_files(
        bundle_path=args.bundle,
        protocol_path=args.protocol,
        execution_registry_path=args.execution_registry,
    )
    bundle = g1_micro._canonical_object(args.bundle.read_bytes(), "result bundle")
    receipt = g1_micro._canonical_object(
        args.dgx_runtime_receipt.read_bytes(), "DGX runtime receipt"
    )
    protocol, _ = g1_micro.load_protocol(args.protocol)
    final = verify_dgx_execution_receipt(
        receipt=receipt, bundle=bundle, protocol=protocol
    )
    result = {
        "bundle_sha256": bundle["bundle_sha256"],
        "final_runtime": final,
        "frozen_execution": frozen,
        "verification": "VALID_LOCAL_FROZEN_DGX_EXPLORATORY_EXECUTION",
    }
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
