"""Seal a P1v4 evidence-and-budget pair for LakatoTree producer replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p1v3_calibration_preflight import file_sha256, write_once
from p1v4_replay_judge import build_replay_bundle, replay_metric


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    budget = json.loads(args.budget.read_text(encoding="utf-8"))
    bundle = build_replay_bundle(evidence=evidence, budget=budget)
    metric = replay_metric(bundle)
    write_once(args.output, bundle)
    print(json.dumps({
        "bundle_sha256": bundle["bundle_sha256"],
        "metric": metric,
        "output": str(args.output),
        "output_file_sha256": file_sha256(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
