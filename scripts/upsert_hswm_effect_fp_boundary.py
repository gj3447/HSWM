#!/usr/bin/env python3
"""Validate and explicitly publish the HSWM Effect-runtime functional-boundary KG projection.

Dry run validates and prints VALIDATED_ONLY_NOT_PUBLISHED.  ``--apply`` asserts
the live schema registry and every anchor by exact name, creates the owned
nodes and relations in one transaction, and reads them back exactly.  KG
presence is publication of an engineering-status record, not a migration-gate
pass, a G0/G1 pass, or a scientific result.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from scripts import build_hswm_effect_fp_boundary_ontology as builder
from scripts.upsert_hswm_graph_and_loop_engineering import publish, read_flat_yaml


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH
EXPECTED_COUNTS: dict[str, int] = {
    "anchors": 17,
    "fp_gaps": 6,
    "gate_claims": 7,
    "gate_decisions": 7,
    "lane_files": 38,
    "lanes": 7,
    "lint_rules": 5,
    "lint_violations_outside_lanes": 0,
    "nodes": 84,
    "packages": 11,
    "qualification_runs": 2,
    "refactored_files": 25,
    "relations": 279,
    "services": 5,
    "source_records": 5
}
EXPECTED_PROJECTION_SHA256 = "ed808e9a1d3d15576fefd9a44ddc607c92ec812a69080762c213e916eb8c6a1f"
EXPECTED_FILE_SHA256 = "f6dd1236c1f763bc5d79db64784ca43a5f68b93fc942fe0b746c74d5d51481f2"


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _check_bindings(data: Mapping[str, Any], repo_root: Path) -> None:
    rows = data["artifact_bindings"]
    expected_paths = [path.as_posix() for path in builder.SOURCE_BINDING_PATHS]
    if [row["path"] for row in rows] != expected_paths:
        raise ValueError("artifact binding paths drifted")
    root = repo_root.resolve()
    for row in rows:
        logical = Path(row["path"])
        if logical.is_absolute() or ".." in logical.parts:
            raise ValueError("artifact binding path is not normalized")
        path = repo_root / logical
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"artifact binding is not a regular file: {logical}")
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError(f"artifact binding escapes repository: {logical}")
        if row["sha256"] != _file_sha(path):
            raise ValueError(f"artifact binding drifted: {logical}")


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    """Fail closed on source, graph, count, or digest drift before publication."""

    builder.validate_data(data)
    if data != builder.build_data():
        raise ValueError("projection is not the deterministic build")
    if data["expected_counts"] != EXPECTED_COUNTS:
        raise ValueError("effect fp-boundary declared counts drifted")
    _check_bindings(data, repo_root)
    if builder.canonical_sha(data) != EXPECTED_PROJECTION_SHA256:
        raise ValueError("effect fp-boundary projection digest drifted")
    for anchor in data["anchors"]:
        if set(anchor) != {"uid", "name", "required_labels"} or not anchor["required_labels"]:
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
        raise SystemExit("effect fp-boundary ontology file digest drifted")
    if not args.apply:
        print(
            json.dumps(
                {
                    "new_nodes": len(data["nodes"]),
                    "relations": len(data["relations"]),
                    "projection_sha256": projection_sha256,
                    "status": "VALIDATED_ONLY_NOT_PUBLISHED",
                },
                sort_keys=True,
            )
        )
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = publish(data, read_flat_yaml(args.source_config), projection_sha256)
    print(
        json.dumps(
            {**result, "projection_sha256": projection_sha256, "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION"},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
