#!/usr/bin/env python3
"""Replay a recorded F1 development cohort through the v2 envelope pipeline.

This is the development verification path for the token-parity repair.  It
takes the items of a recorded v1 development manifest, derives honest
per-arm output projections and tight per-call input caps from the recorded
suite's measurements, emits a v2 manifest, and re-executes the cohort with a
deterministic replay port: model outputs and output-token counts come from
the recorded suite byte-for-byte (only the transport ``request_id`` is
rebound to the new run), while input-token counts are recomputed with the
exact validated meter on the new fitted envelopes.  The result shows the
consumed-token spread the repaired pipeline produces on the same cohort
without needing the live model; the live rerun uses the standard ``run``
command on the emitted manifest.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_call_receipt import ModelCallV1, ModelResponseV1
from prom_search_hswm.hswm_function_network import F1_ARMS, request_id_for
from prom_search_hswm.hswm_function_registry import build_registry
from prom_search_hswm.hswm_token_meter import QwenBpeMeter, TokenMeter
from prom_search_hswm.hswm_typed_ports import canonical_json
from prom_search_hswm.prom9_f1_envelope import compute_minimum_input_caps
from prom_search_hswm.prom_f1_function_network import (
    MANIFEST_SCHEMA,
    _arm_overrides,
    _item,
    judge_suite,
    run_suite,
    verify_suite,
)
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL


class ReplayError(RuntimeError):
    pass


class RecordedReplayPort:
    """Deterministic model port replaying one recorded suite's outputs.

    Output payloads and output-token counts are the recorded ones; input
    tokens are recomputed with the exact meter on the actually-sent fitted
    envelope, mirroring how the served model accounted the original calls.
    """

    def __init__(self, suite: Mapping[str, object], meter: TokenMeter, run_id: str) -> None:
        self._meter = meter
        self._run_id = run_id
        self._outputs: dict[tuple[str, str, int], tuple[dict[str, object], int]] = {}
        for row in suite["item_runs"]:
            for call in row["calls"]:
                key = (str(row["item_id"]), str(row["arm_id"]), int(call["call_index"]))
                self._outputs[key] = (
                    json.loads(json.dumps(call["output_payload"])),
                    int(call["output_tokens"]),
                )

    def __call__(self, call: ModelCallV1) -> ModelResponseV1:
        key = (call.item_id, call.arm_id, call.call_index)
        if key not in self._outputs:
            raise ReplayError(f"no recorded output for {key}")
        payload, output_tokens = self._outputs[key]
        payload = json.loads(json.dumps(payload))
        payload["request_id"] = request_id_for(self._run_id, call.arm_id, call.item_id)
        return ModelResponseV1(
            payload=payload,
            model=call.model,
            model_revision=call.model_revision,
            input_tokens=self._meter.count_chat_prompt(
                call.system_prompt, canonical_json(call.input_payload)
            ),
            output_tokens=output_tokens,
            latency_ms=0,
            cache_status="hit",
        )


def measured_output_projections(
    suite: Mapping[str, object],
) -> dict[str, dict[str, int]]:
    """Honest per-arm output projections: the maximum observed per call."""

    projections: dict[str, dict[str, int]] = {
        arm: {"1": 1, "2": 1, "3": 1} for arm in F1_ARMS
    }
    for row in suite["item_runs"]:
        arm = str(row["arm_id"])
        if arm not in projections:
            raise ReplayError(f"recorded suite holds an unknown arm: {arm}")
        for call in row["calls"]:
            index = str(int(call["call_index"]))
            projections[arm][index] = max(
                projections[arm][index], int(call["output_tokens"])
            )
    return projections


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReplayError(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise ReplayError(f"{label} must be an object")
    return value


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise ReplayError(f"refusing to replace output: {path}") from error
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-manifest", type=Path, required=True)
    parser.add_argument("--old-suite", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--validation-receipt", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-caps", default="256,512,256")
    parser.add_argument("--projection-slack", type=int, default=32)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        old_manifest = _read_json(args.old_manifest, "recorded F1 manifest")
        old_suite = _read_json(args.old_suite, "recorded F1 suite")
        gold = _read_json(args.gold, "F1 gold")
        receipt = _read_json(args.validation_receipt, "token meter validation receipt")
        receipt_sha = receipt.get("validation_receipt_sha256")
        if not isinstance(receipt_sha, str) or len(receipt_sha) != 64:
            raise ReplayError("validation receipt lacks its SHA-256")
        meter = QwenBpeMeter(
            args.tokenizer_dir / "vocab.json",
            args.tokenizer_dir / "merges.txt",
            args.tokenizer_dir / "tokenizer_config.json",
        )
        output_cap_parts = args.output_caps.split(",")
        if len(output_cap_parts) != 3 or any(not part.isdigit() or int(part) < 1 for part in output_cap_parts):
            raise ReplayError("--output-caps must be three positive integers")
        output_caps = {
            str(index): int(output_cap_parts[index - 1]) for index in range(1, 4)
        }
        if args.projection_slack < 0:
            raise ReplayError("projection slack must be non-negative")
        model = str(old_manifest["model"])
        model_revision = str(old_manifest["model_revision"])
        registries = {
            arm: build_registry(
                args.protocol,
                model=model,
                model_revision=model_revision,
                prompt_overrides=_arm_overrides(arm),
            )
            for arm in F1_ARMS
        }
        items = [_item(raw) for raw in old_manifest["items"]]
        projections = measured_output_projections(old_suite)
        input_caps = compute_minimum_input_caps(
            run_id=args.run_id,
            items=items,
            arms=F1_ARMS,
            registries=registries,
            meter=meter,
            projected_outputs=projections,
            slack=args.projection_slack,
        )
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "run_id": args.run_id,
            "mode": "development",
            "model": model,
            "model_revision": model_revision,
            "token_tolerance": int(old_manifest["token_tolerance"]),
            "state_capacity_bytes": int(old_manifest["state_capacity_bytes"]),
            "state_bytes_by_arm": dict(old_manifest["state_bytes_by_arm"]),
            "preregistration_receipt_sha256": None,
            "token_envelope": {
                "schema_version": "hswm-prom9-f1-token-envelope/v1",
                "tokenizer": {**meter.identity(), "validation_receipt_sha256": receipt_sha},
                "filler": {"field": "parity_filler", "unit": "0", "max_filler_chars": 60000},
                "per_call_input_caps": input_caps,
                "per_call_output_caps": output_caps,
                "projected_output_tokens_by_arm": projections,
                "projection_slack_tokens": args.projection_slack,
            },
            "items": old_manifest["items"],
        }
        replay_port = RecordedReplayPort(old_suite, meter, args.run_id)
        suite = run_suite(
            manifest,
            protocol_path=args.protocol,
            model_port=replay_port,
            token_meter=meter,
        )
        verified = verify_suite(suite)
        # Development replay: the accepted answers are unchanged, but the gold
        # identity must name this run for the judge to accept the pairing.
        rebound_gold = {**gold, "run_id": args.run_id}
        judgment = judge_suite(suite, rebound_gold)
        _write_once(args.output_dir / "manifest.v2.json", manifest)
        _write_once(args.output_dir / "suite.v2.json", suite)
        _write_once(args.output_dir / "judgment.v2.json", judgment)

        def spreads(recorded_suite: Mapping[str, object]) -> dict[str, int]:
            indexed: dict[str, list[int]] = {}
            for row in recorded_suite["item_runs"]:
                indexed.setdefault(str(row["item_id"]), []).append(
                    int(row["total_input_tokens"]) + int(row["total_output_tokens"])
                )
            return {
                item: max(values) - min(values) for item, values in sorted(indexed.items())
            }

        before = spreads(old_suite)
        after = {entry["item_id"]: entry["spread"] for entry in suite["token_parity"]["items"]}
        summary = {
            "status": "REPLAYED_DEVELOPMENT_ONLY",
            "run_id": args.run_id,
            "suite_receipt_sha256": verified,
            "spread_before": before,
            "spread_after": after,
            "token_tolerance": manifest["token_tolerance"],
            "all_within_tolerance": suite["token_parity"]["all_within_tolerance"],
            "equal_budget_gate": judgment["gates"]["equal_budget"],
            "parity_failures": judgment["parity_failures"],
            "per_call_input_caps": input_caps,
            "verdict": judgment["verdict"],
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception as error:
        print(
            json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False),
            file=os.sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
