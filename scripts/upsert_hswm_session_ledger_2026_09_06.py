#!/usr/bin/env python3
"""Validate and explicitly publish the HSWM session ledger KG projection (2026-09-06, v1).

Dry run validates and prints VALIDATED_ONLY_NOT_PUBLISHED.  ``--apply`` asserts
the live schema registry and every anchor by exact name, creates the owned
nodes and relations in one transaction, and reads them back exactly.  KG
presence is publication of an effort ledger, not a gate pass, a user
ratification, or a scientific result.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from scripts import build_hswm_session_ledger_2026_09_06 as builder
from scripts.upsert_hswm_graph_and_loop_engineering import publish, read_flat_yaml


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH
EXPECTED_COUNTS: dict[str, int] = {
    "anchors": 17,
    "commits": 48,
    "core_commits": 23,
    "nodes": 70,
    "open_items": 8,
    "readings": 3,
    "relations": 145,
    "streams": 10,
}
EXPECTED_PROJECTION_SHA256 = "94ec773a81571f0d9c6e7a1ebab434e0606e87068656b5f17534ac4161d3dc63"
EXPECTED_FILE_SHA256 = "2c663f9e82122badeea72dbec7e1aef74e541aece9c551491aa6812cfcbf6bd7"


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_data(data: dict[str, Any]) -> None:
    builder.validate_data(data)
    for row in data["artifact_bindings"]:
        path = ROOT / row["path"]
        if row["sha256"] != _file_sha(path):
            raise ValueError(f"artifact binding drifted: {row['path']}")
    if data["expected_counts"] != EXPECTED_COUNTS:
        raise ValueError("expected_counts drifted")
    if builder.canonical_sha(data) != EXPECTED_PROJECTION_SHA256:
        raise ValueError("projection digest drifted")
    for row in data["anchors"]:
        if not row["uid"].startswith("sym:") or not row["name"] or not row["required_labels"]:
            raise ValueError("unsafe anchor descriptor")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.ontology.read_text(encoding="utf-8"))
    validate_data(data)
    projection_sha256 = _file_sha(args.ontology)
    if projection_sha256 != EXPECTED_FILE_SHA256:
        raise SystemExit("session ledger file digest drifted")
    if not args.apply:
        print(json.dumps({"new_nodes": len(data["nodes"]), "relations": len(data["relations"]), "projection_sha256": projection_sha256, "status": "VALIDATED_ONLY_NOT_PUBLISHED"}, sort_keys=True))
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = publish(data, read_flat_yaml(args.source_config), projection_sha256)
    print(json.dumps({**result, "projection_sha256": projection_sha256, "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION"}, sort_keys=True))


if __name__ == "__main__":
    main()
