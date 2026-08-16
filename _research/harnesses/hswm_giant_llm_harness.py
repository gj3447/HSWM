#!/usr/bin/env python3
"""Deterministic HSWM giant-LLM/world-model research contract harness.

This CLI validates a user-primary identity operationalization, a metadata-only
source dump, local evidence pointers, falsifiers, and ordered next experiments.
It never calls a model, fetches the network, or issues a scientific verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_NAME = "hswm_giant_llm_harness.v1.json"
CONFIG_PATH = Path("manifests") / CONFIG_NAME
CONFIG_SCHEMA = "hswm-giant-llm-harness-config/v1"
DUMP_SCHEMA = "hswm-research-source-dump/v1"
RECEIPT_SCHEMA = "hswm-giant-llm-harness-receipt/v1"

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_SOURCE_DUMP = 2
EXIT_LOCAL_EVIDENCE = 3

SOURCE_KEYS = {
    "source_id",
    "field",
    "topic",
    "title",
    "year",
    "venue_or_publisher",
    "url",
    "source_type",
    "retrieved_at",
    "content_mode",
    "fulltext_stored",
    "claims_supported",
    "hswm_implications",
    "does_not_establish",
}

GATE_KEYS = {
    "id",
    "title",
    "field",
    "priority",
    "current_status",
    "claim",
    "local_evidence",
    "required_source_ids",
    "operational_test",
    "strongest_baselines",
    "falsifier",
    "allowed_label",
    "next_action",
}


@dataclass
class Check:
    axis: str
    check_id: str
    status: str
    detail: str


class HarnessError(Exception):
    def __init__(self, exit_code: int, label: str, detail: str) -> None:
        super().__init__(detail)
        self.exit_code = exit_code
        self.label = label
        self.detail = detail


def _discover_repository_root(anchor: str | Path = __file__) -> Path:
    """Locate the HSWM checkout independently of this harness's depth."""
    resolved = Path(anchor).resolve(strict=True)
    start = resolved.parent if resolved.is_file() else resolved
    for candidate in (start, *start.parents):
        if (candidate / CONFIG_PATH).is_file():
            return candidate
    raise RuntimeError(f"cannot locate HSWM repository root from {resolved}")


REPO_ROOT = _discover_repository_root()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _find_symposium_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "HSWM" / CONFIG_PATH).is_file():
            return candidate
        if candidate.name == "HSWM" and (candidate / CONFIG_PATH).is_file():
            return candidate.parent
    return REPO_ROOT.parent


def _resolve_from_root(root: Path, path: Path | str) -> Path:
    candidate = Path(path)
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def _load_json(path: Path, *, exit_code: int, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HarnessError(exit_code, label, f"{path}: {error}") from error
    if not isinstance(data, dict):
        raise HarnessError(exit_code, label, f"{path}: root must be a JSON object")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_text_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_nonempty_text(item) for item in value)
    )


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != CONFIG_SCHEMA:
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            f"bad schema: {config.get('schema_version')!r}",
        )

    required_fields = config.get("required_fields")
    if not _nonempty_text_list(required_fields) or len(set(required_fields)) != len(
        required_fields
    ):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "required_fields must be a unique non-empty string list",
        )

    minimums = config.get("minimum_sources_per_field")
    if not isinstance(minimums, dict) or set(minimums) != set(required_fields):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "minimum_sources_per_field must cover required_fields exactly",
        )
    if any(not isinstance(value, int) or value < 1 for value in minimums.values()):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "minimum source counts must be positive integers",
        )

    authority = config.get("authority")
    if not isinstance(authority, dict):
        raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "authority is required")
    if authority.get("classification") != "SECONDARY_AI_OPERATIONALIZATION_OF_USER_PRIMARY":
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "authority classification must preserve user-primary separation",
        )
    user_primary = authority.get("user_primary")
    if not isinstance(user_primary, dict) or not _nonempty_text(
        user_primary.get("utterance")
    ):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "user_primary.utterance is required",
        )
    if not _nonempty_text_list(authority.get("never")):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "authority.never must state forbidden side effects and overclaims",
        )

    thesis = config.get("thesis")
    if not isinstance(thesis, dict):
        raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "thesis is required")
    if not _nonempty_text(thesis.get("one_line_ko")) or not _nonempty_text_list(
        thesis.get("system_equations")
    ):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "thesis requires one_line_ko and system_equations",
        )
    layers = thesis.get("layers")
    if not isinstance(layers, list) or not layers:
        raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "thesis.layers is required")
    layer_ids: list[str] = []
    for layer in layers:
        if not isinstance(layer, dict) or not _nonempty_text(layer.get("id")):
            raise HarnessError(
                EXIT_CONFIG, "CONFIG_ERROR", "each thesis layer requires an id"
            )
        if not _nonempty_text(layer.get("meaning")):
            raise HarnessError(
                EXIT_CONFIG,
                "CONFIG_ERROR",
                f"layer {layer.get('id')} requires meaning",
            )
        layer_ids.append(layer["id"])
    if len(set(layer_ids)) != len(layer_ids):
        raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "duplicate thesis layer id")

    boundary = config.get("claim_boundary")
    if not isinstance(boundary, dict) or not _nonempty_text(
        boundary.get("allowed_current_claim")
    ):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "claim_boundary.allowed_current_claim is required",
        )
    if not _nonempty_text_list(boundary.get("forbidden_overclaims")):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "claim_boundary.forbidden_overclaims is required",
        )
    if not _nonempty_text_list(boundary.get("bright_lines")):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "claim_boundary.bright_lines is required",
        )

    gates = config.get("gates")
    if not isinstance(gates, list) or not gates:
        raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "gates are required")
    gate_ids: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict):
            raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "gate must be an object")
        missing = sorted(GATE_KEYS - set(gate))
        if missing:
            raise HarnessError(
                EXIT_CONFIG,
                "CONFIG_ERROR",
                f"gate {gate.get('id', '<unknown>')} missing keys: {missing}",
            )
        gate_id = gate["id"]
        if not _nonempty_text(gate_id):
            raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "gate id must be text")
        gate_ids.append(gate_id)
        if gate["field"] not in required_fields:
            raise HarnessError(
                EXIT_CONFIG,
                "CONFIG_ERROR",
                f"gate {gate_id} has unknown field {gate['field']}",
            )
        if gate["priority"] not in {"P0", "P1", "P2"}:
            raise HarnessError(
                EXIT_CONFIG,
                "CONFIG_ERROR",
                f"gate {gate_id} has invalid priority {gate['priority']}",
            )
        for key in (
            "title",
            "current_status",
            "claim",
            "operational_test",
            "falsifier",
            "allowed_label",
            "next_action",
        ):
            if not _nonempty_text(gate[key]):
                raise HarnessError(
                    EXIT_CONFIG,
                    "CONFIG_ERROR",
                    f"gate {gate_id} requires non-empty {key}",
                )
        for key in ("required_source_ids", "strongest_baselines"):
            if not _nonempty_text_list(gate[key]):
                raise HarnessError(
                    EXIT_CONFIG,
                    "CONFIG_ERROR",
                    f"gate {gate_id} requires non-empty {key}",
                )
        evidence = gate["local_evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise HarnessError(
                EXIT_CONFIG,
                "CONFIG_ERROR",
                f"gate {gate_id} requires local_evidence",
            )
        for pointer in evidence:
            if not isinstance(pointer, dict) or not _nonempty_text(pointer.get("path")):
                raise HarnessError(
                    EXIT_CONFIG,
                    "CONFIG_ERROR",
                    f"gate {gate_id} has invalid evidence path",
                )
            if not _nonempty_text_list(pointer.get("markers")):
                raise HarnessError(
                    EXIT_CONFIG,
                    "CONFIG_ERROR",
                    f"gate {gate_id} evidence requires markers",
                )

    if len(set(gate_ids)) != len(gate_ids):
        raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "duplicate gate id")
    priority_order = config.get("priority_order")
    if not _nonempty_text_list(priority_order) or priority_order != list(
        dict.fromkeys(priority_order)
    ):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "priority_order must be a unique non-empty list",
        )
    if set(priority_order) != set(gate_ids):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "priority_order must cover every gate exactly once",
        )
    primary_ids = config.get("primary_identity_gate_ids")
    if not _nonempty_text_list(primary_ids) or not set(primary_ids).issubset(gate_ids):
        raise HarnessError(
            EXIT_CONFIG,
            "CONFIG_ERROR",
            "primary_identity_gate_ids must name one or more declared gates",
        )
    if not _nonempty_text(config.get("source_dump")):
        raise HarnessError(EXIT_CONFIG, "CONFIG_ERROR", "source_dump path is required")


def validate_source_dump(
    source_dump: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    if source_dump.get("schema_version") != DUMP_SCHEMA:
        raise HarnessError(
            EXIT_SOURCE_DUMP,
            "SOURCE_DUMP_ERROR",
            f"bad schema: {source_dump.get('schema_version')!r}",
        )
    copyright_scope = source_dump.get("copyright_scope")
    if not isinstance(copyright_scope, dict):
        raise HarnessError(
            EXIT_SOURCE_DUMP, "SOURCE_DUMP_ERROR", "copyright_scope is required"
        )
    if copyright_scope.get("fulltext_included") is not False:
        raise HarnessError(
            EXIT_SOURCE_DUMP,
            "SOURCE_DUMP_ERROR",
            "source dump must explicitly exclude fulltext",
        )
    if copyright_scope.get("content_mode") != "METADATA_AND_ORIGINAL_PARAPHRASE_ONLY":
        raise HarnessError(
            EXIT_SOURCE_DUMP,
            "SOURCE_DUMP_ERROR",
            "copyright content_mode must be metadata and original paraphrase only",
        )

    records = source_dump.get("records")
    if not isinstance(records, list) or not records:
        raise HarnessError(
            EXIT_SOURCE_DUMP, "SOURCE_DUMP_ERROR", "records must be a non-empty list"
        )
    if source_dump.get("source_count") != len(records):
        raise HarnessError(
            EXIT_SOURCE_DUMP,
            "SOURCE_DUMP_ERROR",
            "source_count does not match records length",
        )

    required_fields = set(config["required_fields"])
    source_by_id: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for record in records:
        if not isinstance(record, dict):
            raise HarnessError(
                EXIT_SOURCE_DUMP, "SOURCE_DUMP_ERROR", "source record must be an object"
            )
        missing = sorted(SOURCE_KEYS - set(record))
        if missing:
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"source {record.get('source_id', '<unknown>')} missing keys: {missing}",
            )
        source_id = record["source_id"]
        if not _nonempty_text(source_id) or source_id in source_by_id:
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"duplicate or invalid source_id: {source_id!r}",
            )
        if record["field"] not in required_fields:
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"source {source_id} has unknown field {record['field']}",
            )
        if not _nonempty_text(record["url"]) or not record["url"].startswith(
            ("https://", "http://")
        ):
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"source {source_id} requires an http(s) URL",
            )
        if record["fulltext_stored"] is not False:
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"source {source_id} must not store fulltext",
            )
        if record["content_mode"] != "METADATA_AND_ORIGINAL_PARAPHRASE_ONLY":
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"source {source_id} has forbidden content mode",
            )
        for key in (
            "topic",
            "title",
            "venue_or_publisher",
            "source_type",
            "retrieved_at",
        ):
            if not _nonempty_text(record[key]):
                raise HarnessError(
                    EXIT_SOURCE_DUMP,
                    "SOURCE_DUMP_ERROR",
                    f"source {source_id} requires non-empty {key}",
                )
        if not isinstance(record["year"], int):
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"source {source_id} year must be an integer",
            )
        for key in ("claims_supported", "hswm_implications", "does_not_establish"):
            if not _nonempty_text_list(record[key]):
                raise HarnessError(
                    EXIT_SOURCE_DUMP,
                    "SOURCE_DUMP_ERROR",
                    f"source {source_id} requires non-empty {key}",
                )
        source_by_id[source_id] = record
        counts[record["field"]] += 1

    for field_name, minimum in config["minimum_sources_per_field"].items():
        if counts[field_name] < minimum:
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"field {field_name} has {counts[field_name]} sources; requires {minimum}",
            )

    for gate in config["gates"]:
        missing_ids = sorted(set(gate["required_source_ids"]) - set(source_by_id))
        if missing_ids:
            raise HarnessError(
                EXIT_SOURCE_DUMP,
                "SOURCE_DUMP_ERROR",
                f"gate {gate['id']} references missing sources: {missing_ids}",
            )
    return source_by_id, counts


def validate_local_evidence(root: Path, config: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    root = root.resolve()
    for gate in config["gates"]:
        for index, pointer in enumerate(gate["local_evidence"], start=1):
            path = _resolve_from_root(root, pointer["path"])
            try:
                path.relative_to(root)
            except ValueError as error:
                raise HarnessError(
                    EXIT_LOCAL_EVIDENCE,
                    "LOCAL_EVIDENCE_ERROR",
                    f"gate {gate['id']} evidence escapes repository root: {path}",
                ) from error
            if not path.is_file():
                raise HarnessError(
                    EXIT_LOCAL_EVIDENCE,
                    "LOCAL_EVIDENCE_ERROR",
                    f"gate {gate['id']} missing evidence file: {path}",
                )
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                raise HarnessError(
                    EXIT_LOCAL_EVIDENCE,
                    "LOCAL_EVIDENCE_ERROR",
                    f"gate {gate['id']} cannot read {path}: {error}",
                ) from error
            matched = [marker for marker in pointer["markers"] if marker in text]
            if not matched:
                raise HarnessError(
                    EXIT_LOCAL_EVIDENCE,
                    "LOCAL_EVIDENCE_ERROR",
                    f"gate {gate['id']} found no expected marker in {path}",
                )
            checks.append(
                Check(
                    axis="VERIFY",
                    check_id=f"evidence.{gate['id']}.{index}",
                    status="PASS",
                    detail=f"{pointer['path']} matched {matched[0]!r}",
                )
            )
    return checks


def build_receipt(
    root: Path,
    config_path: Path,
    source_dump_path: Path,
    config: dict[str, Any],
    source_dump: dict[str, Any],
    source_by_id: dict[str, dict[str, Any]],
    source_counts: Counter[str],
    evidence_checks: list[Check],
) -> dict[str, Any]:
    checks = [
        Check(
            axis="INFORM",
            check_id="inform.source_coverage",
            status="PASS",
            detail=(
                f"{len(source_by_id)} metadata/paraphrase records; "
                + ", ".join(
                    f"{field_name}={source_counts[field_name]}"
                    for field_name in config["required_fields"]
                )
            ),
        ),
        Check(
            axis="INFORM",
            check_id="inform.fulltext_boundary",
            status="PASS",
            detail="fulltext and verbatim passages are explicitly excluded",
        ),
        Check(
            axis="CONSTRAIN",
            check_id="constrain.user_primary_boundary",
            status="PASS",
            detail="user utterance is preserved separately from secondary AI operationalization",
        ),
        Check(
            axis="CONSTRAIN",
            check_id="constrain.falsifiers_and_baselines",
            status="PASS",
            detail=f"all {len(config['gates'])} gates declare a falsifier and strongest baselines",
        ),
        *evidence_checks,
        Check(
            axis="VERIFY",
            check_id="verify.source_references",
            status="PASS",
            detail="every gate source id resolves to the source dump",
        ),
        Check(
            axis="CORRECT",
            check_id="correct.priority_order",
            status="PASS",
            detail="every gate has one ordered next action; open scientific gaps do not fail the harness",
        ),
    ]
    gate_summary = [
        {
            "id": gate["id"],
            "title": gate["title"],
            "field": gate["field"],
            "priority": gate["priority"],
            "current_status": gate["current_status"],
            "allowed_label": gate["allowed_label"],
            "falsifier": gate["falsifier"],
            "next_action": gate["next_action"],
        }
        for gate in config["gates"]
    ]
    return {
        "schema_version": RECEIPT_SCHEMA,
        "generated_at": _utc_now(),
        "mode": "READ_ONLY_RESEARCH_CONTRACT_DIAGNOSTIC",
        "repository_commit": _repo_commit(root),
        "config_path": str(config_path),
        "config_sha256": _sha256(config_path),
        "source_dump_path": str(source_dump_path),
        "source_dump_sha256": _sha256(source_dump_path),
        "authority_classification": config["authority"]["classification"],
        "user_primary_utterance": config["authority"]["user_primary"]["utterance"],
        "thesis": config["thesis"],
        "claim_boundary": config["claim_boundary"],
        "model_call_allowed_by_this_harness": False,
        "network_fetch_allowed_by_this_harness": False,
        "fulltext_stored": False,
        "source_count": len(source_by_id),
        "source_counts_by_field": {
            field_name: source_counts[field_name]
            for field_name in config["required_fields"]
        },
        "source_ids": list(source_by_id),
        "primary_identity_gate_ids": config["primary_identity_gate_ids"],
        "priority_order": config["priority_order"],
        "gates": gate_summary,
        "checks": [asdict(check) for check in checks],
        "next_actions": [
            {
                "gate_id": gate_id,
                "priority": next(
                    gate["priority"] for gate in config["gates"] if gate["id"] == gate_id
                ),
                "action": next(
                    gate["next_action"]
                    for gate in config["gates"]
                    if gate["id"] == gate_id
                ),
            }
            for gate_id in config["priority_order"]
        ],
        "scientific_verdict": "UNJUDGED_BY_THIS_HARNESS",
        "source_dump_metadata": {
            "title": source_dump.get("title"),
            "retrieved_at": source_dump.get("retrieved_at"),
            "collection_method": source_dump.get("collection_method"),
        },
    }


def print_thesis(receipt: dict[str, Any]) -> None:
    thesis = receipt["thesis"]
    print("=== HSWM giant LLM / executable world model ===")
    print("authority:", receipt["authority_classification"])
    print("USER_PRIMARY:", receipt["user_primary_utterance"])
    print("normalized:", thesis["one_line_ko"])
    print()
    print("-- layers --")
    for layer in thesis["layers"]:
        print(f"  {layer['id']}: {layer['meaning']}")
    print()
    print("-- operational equations (secondary AI) --")
    for equation in thesis["system_equations"]:
        print(f"  {equation}")


def print_status(receipt: dict[str, Any]) -> None:
    print("=== HSWM giant LLM research harness ===")
    print("mode:", receipt["mode"])
    print("repository_commit:", receipt["repository_commit"])
    print("thesis:", receipt["thesis"]["one_line_ko"])
    print("scientific_verdict:", receipt["scientific_verdict"])
    print(
        "source_dump:",
        f"{receipt['source_count']} records",
        "(metadata + original paraphrase; no fulltext)",
    )
    print()
    print("-- Inform / Constrain / Verify / Correct --")
    by_axis: dict[str, list[dict[str, Any]]] = {}
    for check in receipt["checks"]:
        by_axis.setdefault(check["axis"], []).append(check)
    for axis in ("INFORM", "CONSTRAIN", "VERIFY", "CORRECT"):
        axis_checks = by_axis.get(axis, [])
        status = "PASS" if axis_checks and all(c["status"] == "PASS" for c in axis_checks) else "FAIL"
        print(f"  [{status}] {axis}: {len(axis_checks)} checks")
    print()
    print("-- gates (open gaps are information, not harness failure) --")
    for gate in receipt["gates"]:
        print(
            f"  {gate['priority']} {gate['id']}: {gate['current_status']} "
            f"[{gate['allowed_label']}]"
        )
    print()
    print("-- allowed current claim --")
    print(" ", receipt["claim_boundary"]["allowed_current_claim"])
    print("-- forbidden overclaims --")
    for claim in receipt["claim_boundary"]["forbidden_overclaims"]:
        print(f"  ✗ {claim}")


def print_sources(
    receipt: dict[str, Any], source_by_id: dict[str, dict[str, Any]], field: str | None
) -> None:
    if field and field not in receipt["source_counts_by_field"]:
        raise HarnessError(
            EXIT_SOURCE_DUMP,
            "SOURCE_DUMP_ERROR",
            f"unknown field: {field}",
        )
    print("| id | field | year | title | URL |")
    print("|---|---|---:|---|---|")
    for source_id in receipt["source_ids"]:
        source = source_by_id[source_id]
        if field and source["field"] != field:
            continue
        print(
            f"| {source_id} | {source['field']} | {source['year']} | "
            f"{source['title']} | {source['url']} |"
        )
    print()
    print("content: metadata + original paraphrase only; fulltext_stored=false")


def print_next(receipt: dict[str, Any]) -> None:
    for index, item in enumerate(receipt["next_actions"], start=1):
        print(f"{index}. [{item['priority']}] {item['gate_id']}: {item['action']}")


def print_checks(receipt: dict[str, Any]) -> None:
    for check in receipt["checks"]:
        print(
            f"[{check['status']}] {check['axis']}.{check['check_id']}: "
            f"{check['detail']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the HSWM giant-LLM/world-model research contract"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "thesis", "sources", "next", "check", "json"],
    )
    parser.add_argument("--symposium-root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--source-dump", type=Path, default=None)
    parser.add_argument(
        "--field",
        default=None,
        help="Filter the sources command by mathematics, philosophy, science, or modern_ai",
    )
    parser.add_argument("--write-receipt", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        root = (args.symposium_root or _find_symposium_root()).resolve()
        config_path = _resolve_from_root(
            root, args.config or Path("HSWM") / CONFIG_PATH
        )
        config = _load_json(
            config_path, exit_code=EXIT_CONFIG, label="CONFIG_ERROR"
        )
        validate_config(config)
        source_dump_path = _resolve_from_root(
            root, args.source_dump or config["source_dump"]
        )
        source_dump = _load_json(
            source_dump_path,
            exit_code=EXIT_SOURCE_DUMP,
            label="SOURCE_DUMP_ERROR",
        )
        source_by_id, source_counts = validate_source_dump(source_dump, config)
        evidence_checks = validate_local_evidence(root, config)
        receipt = build_receipt(
            root,
            config_path,
            source_dump_path,
            config,
            source_dump,
            source_by_id,
            source_counts,
            evidence_checks,
        )
        if args.write_receipt:
            receipt_path = _resolve_from_root(root, args.write_receipt)
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        if args.command == "thesis":
            print_thesis(receipt)
        elif args.command == "sources":
            print_sources(receipt, source_by_id, args.field)
        elif args.command == "next":
            print_next(receipt)
        elif args.command == "check":
            print_checks(receipt)
        elif args.command == "json":
            print(json.dumps(receipt, indent=2, ensure_ascii=False))
        else:
            print_status(receipt)
        return EXIT_OK
    except HarnessError as error:
        print(f"{error.label}: {error.detail}", file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
