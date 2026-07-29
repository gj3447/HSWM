#!/usr/bin/env python3
"""Derive the outcome-blind F1 r8 token envelope from both frozen cohorts.

The historical envelope supplies the already validated tokenizer, filler,
output-cap, and projection policy.  Input caps are recomputed before any model
call as the componentwise maximum of the exact development and confirmatory
cohort minima.  The producer accepts no answer-bearing or gold input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from collections.abc import Mapping, Sequence

from prom_search_hswm.hswm_function_network import F1_ARMS
from prom_search_hswm.hswm_token_meter import QwenBpeMeter, TokenMeter
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_envelope import (
    check_tokenizer_identity,
    compute_minimum_input_caps,
    enforce_projection,
    validate_token_envelope,
)
from prom_search_hswm.prom9_f1_r8_power import (
    DEVELOPMENT_COMPONENTS,
    selected_entries,
    verify_selection_receipt,
)
from prom_search_hswm.prom9_f1_r8_runner import _item, _registries
from prom_search_hswm.prom9_f1_r8_source import (
    build_public_artifacts,
    read_json,
    write_json_once,
)
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL
from prom_search_hswm.prom9_validate_token_meter import RECEIPT_SCHEMA


DERIVATION_SCHEMA = "hswm-prom9-f1-r8-token-envelope-derivation/v1"
PROJECTED_OUTPUTS_SCHEMA = "hswm-prom9-f1-projected-outputs/v1"
EXPECTED_DEVELOPMENT_ITEMS = 55
EXPECTED_CONFIRMATORY_ITEMS = 100
EXPECTED_CONFIRMATORY_COMPONENTS = 100
DEFAULT_TOKEN_TOLERANCE = 512
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class R8EnvelopeRefusal(RuntimeError):
    """The public inputs cannot support one frozen r8 token envelope."""


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise R8EnvelopeRefusal(f"{label} self-hash drifted")
    return declared


def _validate_meter_receipt(
    value: Mapping[str, object], meter: TokenMeter
) -> tuple[str, str]:
    expected = {
        "schema_version", "meter", "suite_receipt_sha256", "calls_checked",
        "mismatches", "result", "validation_receipt_sha256",
    }
    if set(value) != expected or value.get("schema_version") != RECEIPT_SCHEMA:
        raise R8EnvelopeRefusal("token-meter validation receipt shape drifted")
    receipt_sha = _self_hash(
        value, "validation_receipt_sha256", "token-meter validation receipt"
    )
    if value.get("meter") != meter.identity():
        raise R8EnvelopeRefusal("token-meter validation identity drifted")
    checked = value.get("calls_checked")
    if (
        isinstance(checked, bool)
        or not isinstance(checked, int)
        or checked < 1
        or value.get("mismatches") != 0
        or value.get("result") != f"EXACT_MATCH_{checked}_OF_{checked}"
    ):
        raise R8EnvelopeRefusal("token-meter validation is not an exact match")
    source_suite = value.get("suite_receipt_sha256")
    if not isinstance(source_suite, str) or len(source_suite) != 64:
        raise R8EnvelopeRefusal("token-meter validation source suite is invalid")
    return receipt_sha, source_suite


def _validate_projected_outputs(
    value: Mapping[str, object], *, source_suite_sha256: str
) -> dict[str, dict[str, int]]:
    expected = {
        "schema_version", "derivation", "projected_output_tokens_by_arm",
        "source_suite_receipt_sha256",
    }
    if (
        set(value) != expected
        or value.get("schema_version") != PROJECTED_OUTPUTS_SCHEMA
        or value.get("source_suite_receipt_sha256") != source_suite_sha256
    ):
        raise R8EnvelopeRefusal("projected-output receipt identity drifted")
    raw = value.get("projected_output_tokens_by_arm")
    if not isinstance(raw, Mapping) or set(raw) != set(F1_ARMS):
        raise R8EnvelopeRefusal("projected outputs do not exactly cover F1 arms")
    result: dict[str, dict[str, int]] = {}
    for arm in F1_ARMS:
        triplet = raw.get(arm)
        if not isinstance(triplet, Mapping) or set(triplet) != {"1", "2", "3"}:
            raise R8EnvelopeRefusal(f"projected outputs for {arm} drifted")
        normalized: dict[str, int] = {}
        for call in ("1", "2", "3"):
            count = triplet.get(call)
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise R8EnvelopeRefusal(
                    f"projected output for {arm} call {call} is invalid"
                )
            normalized[call] = count
        result[arm] = normalized
    return result


def _cohort_items(
    *,
    selection: Mapping[str, object],
    selection_sha256: str,
    cohort: str,
    run_id: str,
    model: str,
    model_revision: str,
    envelope: Mapping[str, object],
) -> tuple[list[object], dict[str, object]]:
    entries = selected_entries(selection, cohort)
    built = build_public_artifacts(
        entries,
        public_selection_receipt_sha256=selection_sha256,
        dataset="framolfese/2WikiMultihopQA",
        config="default",
        split="validation",
        run_id=run_id,
        mode="development",
        model=model,
        model_revision=model_revision,
        token_envelope=envelope,
        preregistration_artifact_sha256=None,
    )
    raw_items = built["manifest"].get("items")
    if not isinstance(raw_items, list):
        raise R8EnvelopeRefusal(f"{cohort} manifest items are absent")
    return [
        _item(raw, f"{cohort} item {index}")
        for index, raw in enumerate(raw_items)
        if isinstance(raw, Mapping)
    ], dict(built["summary"])


def build_token_envelope_artifacts(
    *,
    selection: Mapping[str, object],
    historical_manifest: Mapping[str, object],
    validation_receipt: Mapping[str, object],
    projected_outputs_receipt: Mapping[str, object],
    meter: TokenMeter,
    protocol_path: Path,
    model: str,
    model_revision: str,
    development_run_id: str,
    confirmatory_run_id: str,
    token_tolerance: int = DEFAULT_TOKEN_TOLERANCE,
    expected_development_items: int = EXPECTED_DEVELOPMENT_ITEMS,
    expected_confirmatory_items: int = EXPECTED_CONFIRMATORY_ITEMS,
) -> dict[str, dict[str, object]]:
    """Build a tight common envelope and its outcome-blind derivation receipt."""

    if not model or _COMMIT.fullmatch(model_revision) is None:
        raise R8EnvelopeRefusal("model and immutable 40-hex revision are required")
    if not development_run_id or not confirmatory_run_id:
        raise R8EnvelopeRefusal("both cohort run IDs are required")
    if (
        isinstance(token_tolerance, bool)
        or not isinstance(token_tolerance, int)
        or token_tolerance < 0
    ):
        raise R8EnvelopeRefusal("token tolerance must be non-negative")
    selection_sha = verify_selection_receipt(selection)
    historical_raw = historical_manifest.get("token_envelope")
    historical = validate_token_envelope(historical_raw, arms=F1_ARMS)
    validation_sha, source_suite_sha = _validate_meter_receipt(
        validation_receipt, meter
    )
    check_tokenizer_identity(
        {
            **meter.identity(),
            "validation_receipt_sha256": validation_sha,
        },
        meter,
    )
    if historical.get("tokenizer") != {
        **meter.identity(),
        "validation_receipt_sha256": validation_sha,
    }:
        raise R8EnvelopeRefusal("historical envelope tokenizer binding drifted")
    projected = _validate_projected_outputs(
        projected_outputs_receipt, source_suite_sha256=source_suite_sha
    )
    if historical.get("projected_output_tokens_by_arm") != projected:
        raise R8EnvelopeRefusal("historical and committed output projections differ")

    registries = _registries(
        protocol_path=protocol_path, model=model, model_revision=model_revision
    )
    registry_root = canonical_sha256(
        {arm: registries[arm].canonical() for arm in sorted(registries)}
    )
    minima: dict[str, dict[str, int]] = {}
    for cohort, run_id in (
        ("development", development_run_id),
        ("confirmatory", confirmatory_run_id),
    ):
        items, _summary = _cohort_items(
            selection=selection,
            selection_sha256=selection_sha,
            cohort=cohort,
            run_id=run_id,
            model=model,
            model_revision=model_revision,
            envelope=historical,
        )
        minima[cohort] = compute_minimum_input_caps(
            run_id=run_id,
            items=items,
            arms=F1_ARMS,
            registries=registries,
            meter=meter,
            projected_outputs=projected,
            slack=int(historical["projection_slack_tokens"]),
        )

    common_caps = {
        call: max(minima["development"][call], minima["confirmatory"][call])
        for call in ("1", "2", "3")
    }
    envelope = validate_token_envelope(
        {
            **historical,
            "per_call_input_caps": common_caps,
            "projected_output_tokens_by_arm": projected,
        },
        arms=F1_ARMS,
    )
    cohort_receipts: dict[str, dict[str, object]] = {}
    for cohort, run_id, expected_items, expected_components in (
        (
            "development", development_run_id, expected_development_items,
            DEVELOPMENT_COMPONENTS,
        ),
        (
            "confirmatory", confirmatory_run_id, expected_confirmatory_items,
            EXPECTED_CONFIRMATORY_COMPONENTS,
        ),
    ):
        items, summary = _cohort_items(
            selection=selection,
            selection_sha256=selection_sha,
            cohort=cohort,
            run_id=run_id,
            model=model,
            model_revision=model_revision,
            envelope=envelope,
        )
        item_count = int(summary.get("items", -1))
        component_count = int(summary.get("components", -1))
        if item_count != expected_items or component_count != expected_components:
            raise R8EnvelopeRefusal(
                f"{cohort} scale drifted: items={item_count}, "
                f"components={component_count}"
            )
        projection = enforce_projection(
            run_id=run_id,
            items=items,
            arms=F1_ARMS,
            registries=registries,
            meter=meter,
            envelope=envelope,
            token_tolerance=token_tolerance,
        )
        cohort_receipts[cohort] = {
            "run_id": run_id,
            "items": item_count,
            "components": component_count,
            "minimum_input_caps": minima[cohort],
            "projection_sha256": canonical_sha256(projection),
            "projected_spread": projection["projected_spread"],
        }

    receipt_unsigned = {
        "schema_version": DERIVATION_SCHEMA,
        "derivation_policy": "tight_common_componentwise_max_of_both_frozen_cohorts/v1",
        "selection_receipt_sha256": selection_sha,
        "historical_token_envelope_sha256": canonical_sha256(historical),
        "historical_input_caps_used_as_floor": False,
        "model": model,
        "model_revision": model_revision,
        "protocol_sha256": next(iter(registries.values())).protocol_sha256,
        "registries_root_sha256": registry_root,
        "token_meter_validation_receipt_sha256": validation_sha,
        "token_meter": meter.identity(),
        "projected_outputs_receipt_sha256": canonical_sha256(
            projected_outputs_receipt
        ),
        "source_suite_receipt_sha256": source_suite_sha,
        "development": cohort_receipts["development"],
        "confirmatory": cohort_receipts["confirmatory"],
        "per_call_input_caps": common_caps,
        "per_call_output_caps": dict(envelope["per_call_output_caps"]),
        "total_input_tokens_per_run": sum(common_caps.values()),
        "total_allowed_output_tokens_per_run": sum(
            int(value) for value in envelope["per_call_output_caps"].values()
        ),
        "projection_slack_tokens": envelope["projection_slack_tokens"],
        "token_tolerance": token_tolerance,
        "token_envelope_sha256": canonical_sha256(envelope),
        "gold_inputs_read": False,
        "model_calls": 0,
    }
    receipt = {
        **receipt_unsigned,
        "receipt_sha256": canonical_sha256(receipt_unsigned),
    }
    return {"token_envelope": envelope, "derivation_receipt": receipt}


def write_artifacts_once(
    *, envelope_path: Path, receipt_path: Path, artifacts: Mapping[str, object]
) -> None:
    """Materialize the receipt first and the executable envelope last."""

    envelope_target = Path(envelope_path).resolve()
    receipt_target = Path(receipt_path).resolve()
    if envelope_target == receipt_target:
        raise R8EnvelopeRefusal("envelope and receipt outputs must be distinct")
    if envelope_target.exists() or receipt_target.exists():
        raise R8EnvelopeRefusal("refusing to replace an envelope artifact")
    receipt = artifacts.get("derivation_receipt")
    envelope = artifacts.get("token_envelope")
    if not isinstance(receipt, Mapping) or not isinstance(envelope, Mapping):
        raise R8EnvelopeRefusal("envelope artifacts are malformed")
    write_json_once(receipt_target, receipt)
    write_json_once(envelope_target, envelope)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-receipt", type=Path, required=True)
    parser.add_argument("--historical-manifest", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--validation-receipt", type=Path, required=True)
    parser.add_argument("--projected-outputs-receipt", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--development-run-id", required=True)
    parser.add_argument("--confirmatory-run-id", required=True)
    parser.add_argument("--token-tolerance", type=int, default=DEFAULT_TOKEN_TOLERANCE)
    parser.add_argument("--output-envelope", type=Path, required=True)
    parser.add_argument("--output-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        meter = QwenBpeMeter(
            args.tokenizer_dir / "vocab.json",
            args.tokenizer_dir / "merges.txt",
            args.tokenizer_dir / "tokenizer_config.json",
        )
        selection = read_json(args.selection_receipt, "public selection receipt")
        historical = read_json(args.historical_manifest, "historical manifest")
        validation = read_json(args.validation_receipt, "token-meter validation receipt")
        projected = read_json(
            args.projected_outputs_receipt, "projected-output receipt"
        )
        artifacts = build_token_envelope_artifacts(
            selection=selection,
            historical_manifest=historical,
            validation_receipt=validation,
            projected_outputs_receipt=projected,
            meter=meter,
            protocol_path=args.protocol,
            model=args.model,
            model_revision=args.model_revision,
            development_run_id=args.development_run_id,
            confirmatory_run_id=args.confirmatory_run_id,
            token_tolerance=args.token_tolerance,
        )
        write_artifacts_once(
            envelope_path=args.output_envelope,
            receipt_path=args.output_receipt,
            artifacts=artifacts,
        )
        receipt = artifacts["derivation_receipt"]
        assert isinstance(receipt, Mapping)
        print(
            json.dumps(
                {
                    "status": "FROZEN_PUBLIC_ONLY_NO_CALL",
                    "receipt_sha256": receipt["receipt_sha256"],
                    "token_envelope_sha256": receipt["token_envelope_sha256"],
                    "per_call_input_caps": receipt["per_call_input_caps"],
                    "total_input_tokens_per_run": receipt[
                        "total_input_tokens_per_run"
                    ],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DERIVATION_SCHEMA",
    "R8EnvelopeRefusal",
    "build_token_envelope_artifacts",
    "write_artifacts_once",
]
