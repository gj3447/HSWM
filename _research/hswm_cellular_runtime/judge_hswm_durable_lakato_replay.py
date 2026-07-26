#!/usr/bin/env python3
"""LakatoTree producer-replay adapter for the locked durable-runtime judge.

The v2 judge intentionally remains byte-for-byte locked.  This adapter verifies
the v2 receipt digest, delegates the actual fault-gate decision to that judge,
and emits LakatoTree's numeric ``metric=<float>`` replay contract.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCKED_JUDGE = REPO_ROOT / "_research/hswm_cellular_runtime/judge_hswm_cellular_durable.py"
EXPECTED_LOCKED_JUDGE_SHA256 = "0fdad97294d9bb3450a64306aab4b45d87e1e1aca97d948440da74d5f48f8bb0"
CONTRACT_SCHEMA = "hswm-cellular-durable-runtime-lakato-replay/v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_locked_judge():
    if digest(LOCKED_JUDGE) != EXPECTED_LOCKED_JUDGE_SHA256:
        raise ValueError("locked v2 judge SHA-256 drift")
    spec = importlib.util.spec_from_file_location("hswm_locked_durable_judge", LOCKED_JUDGE)
    if spec is None or spec.loader is None:
        raise ValueError("locked v2 judge could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score(contract_path: Path) -> float:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError(f"contract schema must be {CONTRACT_SCHEMA!r}")
    receipt_path = Path(contract["base_receipt_path"])
    if not receipt_path.is_absolute():
        receipt_path = REPO_ROOT / receipt_path
    if digest(receipt_path) != contract.get("base_receipt_sha256"):
        raise ValueError("base receipt SHA-256 drift")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    result = load_locked_judge().judge(receipt)
    value = float(result["value"])
    if value != float(contract.get("expected_metric")):
        raise ValueError("delegated metric does not match the replay contract")
    if result.get("scientific_status") != "UNJUDGED":
        raise ValueError("delegated judge overclaimed scientific status")
    return value


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} REPLAY_CONTRACT.json", file=sys.stderr)
        return 2
    try:
        value = score(Path(sys.argv[1]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"scoring_refused={type(error).__name__}:{error}", file=sys.stderr)
        return 2
    print(f"metric={value:.17g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
