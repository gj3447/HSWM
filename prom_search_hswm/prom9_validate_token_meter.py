#!/usr/bin/env python3
"""Validate a local token meter against a recorded F1 suite's server counts.

An F1 manifest binds one exact tokenizer identity, and that binding is only
honest if the meter provably reproduces the served model's own accounting.
This tool recomputes the chat-prompt token count of every call in a recorded
suite (system prompt from the embedded registries plus the canonical JSON of
the hashed input payload, exactly as the OpenAI-compatible transport sent it)
and requires an exact match with the server's recorded ``prompt_tokens`` on
every call.  Any mismatch, missing field, or hash drift refuses the run.

The emitted receipt is what a manifest's
``token_envelope.tokenizer.validation_receipt_sha256`` refers to.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_token_meter import QwenBpeMeter
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256


RECEIPT_SCHEMA = "hswm-prom9-token-meter-validation/v1"


class MeterValidationError(RuntimeError):
    pass


def _self_hash_check(value: Mapping[str, object], hash_field: str, label: str) -> None:
    if not isinstance(value, dict):
        raise MeterValidationError(f"{label} must be an object")
    declared = value.get(hash_field)
    unsigned = dict(value)
    unsigned.pop(hash_field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise MeterValidationError(f"{label} self-hash drifted")


def validate_meter_against_suite(
    *,
    meter: QwenBpeMeter,
    suite: Mapping[str, object],
) -> dict[str, object]:
    """Recompute every call's prompt tokens and require exact equality."""

    _self_hash_check(suite, "suite_receipt_sha256", "F1 suite")
    registries = suite.get("registries")
    if not isinstance(registries, dict) or not registries:
        raise MeterValidationError("suite lacks registries")
    prompts: dict[tuple[str, str], str] = {}
    for arm, registry in registries.items():
        _self_hash_check(registry, "registry_sha256", f"registry {arm}")
        functions = registry.get("functions")
        if not isinstance(functions, list):
            raise MeterValidationError(f"registry {arm} lacks functions")
        for function in functions:
            if not isinstance(function, dict):
                raise MeterValidationError(f"registry {arm} has an invalid function")
            if function.get("prompt_sha256") != canonical_sha256({"prompt": function.get("prompt")}):
                raise MeterValidationError(f"prompt hash drifted for {arm}")
            prompts[(str(arm), str(function.get("function_id")))] = str(function.get("prompt"))
    rows = suite.get("item_runs")
    if not isinstance(rows, list) or not rows:
        raise MeterValidationError("suite has no item runs")
    checked = 0
    mismatches: list[dict[str, object]] = []
    for row in rows:
        _self_hash_check(row, "run_receipt_sha256", "item run")
        arm = str(row.get("arm_id"))
        calls = row.get("calls")
        if not isinstance(calls, list):
            raise MeterValidationError("item run lacks calls")
        for call in calls:
            _self_hash_check(call, "receipt_sha256", "call receipt")
            key = (arm, str(call.get("function_id")))
            if key not in prompts:
                raise MeterValidationError(f"call references an unknown function: {key}")
            recorded = call.get("input_tokens")
            if isinstance(recorded, bool) or not isinstance(recorded, int) or recorded < 0:
                raise MeterValidationError("call receipt lacks a valid input_tokens")
            counted = meter.count_chat_prompt(
                prompts[key], canonical_json(call.get("input_payload"))
            )
            checked += 1
            if counted != recorded:
                mismatches.append(
                    {
                        "item_id": row.get("item_id"),
                        "arm_id": arm,
                        "call_index": call.get("call_index"),
                        "counted": counted,
                        "recorded": recorded,
                    }
                )
    if mismatches:
        raise MeterValidationError(
            f"meter disagrees with the server on {len(mismatches)}/{checked} calls: "
            + json.dumps(mismatches[:5], ensure_ascii=False)
        )
    unsigned = {
        "schema_version": RECEIPT_SCHEMA,
        "meter": meter.identity(),
        "suite_receipt_sha256": suite["suite_receipt_sha256"],
        "calls_checked": checked,
        "mismatches": 0,
        "result": f"EXACT_MATCH_{checked}_OF_{checked}",
    }
    return {**unsigned, "validation_receipt_sha256": canonical_sha256(unsigned)}


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MeterValidationError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise MeterValidationError(f"{label} must be an object")
    return value


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise MeterValidationError(f"refusing to replace output: {path}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        meter = QwenBpeMeter(
            args.tokenizer_dir / "vocab.json",
            args.tokenizer_dir / "merges.txt",
            args.tokenizer_dir / "tokenizer_config.json",
        )
        receipt = validate_meter_against_suite(
            meter=meter, suite=_read_json(args.suite, "recorded F1 suite")
        )
        _write_once(args.output, receipt)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception as error:
        print(
            json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False),
            file=os.sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RECEIPT_SCHEMA", "MeterValidationError", "validate_meter_against_suite"]
