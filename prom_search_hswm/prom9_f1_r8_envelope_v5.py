#!/usr/bin/env python3
"""Derive the tight common token envelope for the F1 r8 C-recontract (v5).

Fork of the v4 derivation for the cohort-expansion generation ratified
2026-08-05: the selection receipt is a v5 receipt (800/800 cohorts, train or
validation split recorded in its policy), cohort scales come from that
policy instead of frozen 54/100/100 constants, and the manifest rows carry
the selection's own dataset split.  Everything else — tokenizer identity,
historical envelope binding, meter validation replay, projected outputs,
componentwise-max cap derivation, zero-model-call discipline — is byte-for-
byte the v4 machinery, imported rather than copied.

The derivation receipt binds the actual v5 selection self-hash; freezing
that hash into the execution lock and judge is the next stage's job, so this
module deliberately carries no baked selection pin.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.hswm_function_network import F1_ARMS
from prom_search_hswm.hswm_token_meter import QwenBpeMeter, TokenMeter
from prom_search_hswm.prom9_f1_r8_envelope import (
    DEFAULT_TOKEN_TOLERANCE,
    DERIVATION_SCHEMA,
    R8EnvelopeRefusal,
    R8_PROTOCOL_CANONICAL_SHA256,
    R8_DERIVATION_PREIMAGE_FILE_SHA256,
    _COMMIT,
    _item,
    _read_bound_json,
    _registries,
    _validate_meter_receipt,
    _validate_projected_outputs,
    _validate_source_suite,
    check_tokenizer_identity,
    compute_minimum_input_caps,
    enforce_projection,
    validate_token_envelope,
)
from prom_search_hswm.prom9_f1_r8_selection_v5 import (
    verify_selection_receipt_v5,
)
from prom_search_hswm.prom9_f1_r8_source import build_public_artifacts
from prom_search_hswm.prom9_f1_r8_power import _selected_entries_unverified
from prom_search_hswm.prom9_f1_r8_runner import (
    R8RunnerRefusal,
    _pairs,
    read_stable_bytes,
)
from prom_search_hswm.prom9_validate_token_meter import (
    validate_meter_against_suite,
)


DEVELOPMENT_RUN_ID_C800 = "f1-2wiki-development-r8-c800"
CONFIRMATORY_RUN_ID_C800 = "f1-2wiki-sealed-r8-c800"
DATASET_C800 = "framolfese/2WikiMultihopQA"
DATASET_CONFIG_C800 = "default"

# The v5 selection receipt embeds every redacted pool page (450 pages for the
# ratified 800/800 train cohorts, ~240 MB), so the 64 MiB default stable-read
# bound refuses it.  The bound stays explicit and fail-closed — only this one
# input is allowed the larger ceiling, and its self-hash is still verified by
# verify_selection_receipt_v5 after parsing.
SELECTION_RECEIPT_MAX_BYTES = 512 * 1024 * 1024


def _read_bound_selection_json(
    path: Path, label: str
) -> tuple[dict[str, object], str]:
    """`_read_bound_json` with the v5 selection-receipt byte ceiling."""

    try:
        raw, digest = read_stable_bytes(
            path, label, max_bytes=SELECTION_RECEIPT_MAX_BYTES
        )
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                R8RunnerRefusal(f"non-finite JSON number in {label}")
            ),
        )
    except Exception as error:
        raise R8EnvelopeRefusal(f"cannot capture stable {label}") from error
    if not isinstance(value, dict):
        raise R8EnvelopeRefusal(f"{label} must be a JSON object")
    return value, digest


def _cohort_items_v5(
    *,
    selection: Mapping[str, object],
    selection_sha256: str,
    cohort: str,
    run_id: str,
    model: str,
    model_revision: str,
    envelope: Mapping[str, object],
    dataset_split: str,
) -> tuple[list[object], dict[str, object]]:
    entries = _selected_entries_unverified(selection[cohort])
    built = build_public_artifacts(
        entries,
        public_selection_receipt_sha256=selection_sha256,
        dataset=DATASET_C800,
        config=DATASET_CONFIG_C800,
        split=dataset_split,
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


def build_token_envelope_artifacts_v5(
    *,
    selection: Mapping[str, object],
    historical_manifest: Mapping[str, object],
    validation_receipt: Mapping[str, object],
    projected_outputs_receipt: Mapping[str, object],
    source_suite: Mapping[str, object],
    meter: TokenMeter,
    protocol_path: Path | None = None,
    protocol: Mapping[str, object] | None = None,
    model: str,
    model_revision: str,
    development_run_id: str = DEVELOPMENT_RUN_ID_C800,
    confirmatory_run_id: str = CONFIRMATORY_RUN_ID_C800,
    token_tolerance: int = DEFAULT_TOKEN_TOLERANCE,
) -> dict[str, dict[str, object]]:
    """Build the c800 common envelope and its outcome-blind derivation receipt."""

    if not model or _COMMIT.fullmatch(model_revision) is None:
        raise R8EnvelopeRefusal("model and immutable 40-hex revision are required")
    if not development_run_id or not confirmatory_run_id:
        raise R8EnvelopeRefusal("both cohort run IDs are required")
    if development_run_id == confirmatory_run_id:
        raise R8EnvelopeRefusal("cohort run IDs must differ")
    if protocol is None:
        if protocol_path is None:
            raise R8EnvelopeRefusal("protocol preimage is required")
        protocol, protocol_file_sha = _read_bound_json(
            protocol_path, "PROM-9 protocol"
        )
        if protocol_file_sha != R8_DERIVATION_PREIMAGE_FILE_SHA256["protocol"]:
            raise R8EnvelopeRefusal("protocol file preimage drifted")
    if canonical_sha256(protocol) != R8_PROTOCOL_CANONICAL_SHA256:
        raise R8EnvelopeRefusal("protocol canonical preimage drifted")
    if (
        isinstance(token_tolerance, bool)
        or not isinstance(token_tolerance, int)
        or token_tolerance < 0
    ):
        raise R8EnvelopeRefusal("token tolerance must be non-negative")

    selection_sha = verify_selection_receipt_v5(selection)
    policy = selection["selection_policy"]
    dataset_split = str(policy["dataset_split"])
    expected = {
        "development": {
            "items": len(selection["development"]["item_ids"]),
            "components": int(policy["development_components"]),
        },
        "confirmatory": {
            "items": int(policy["confirmatory_items"]),
            "components": int(policy["confirmatory_items"]),
        },
    }

    historical_raw = historical_manifest.get("token_envelope")
    historical = validate_token_envelope(historical_raw, arms=F1_ARMS)
    source_suite_sha, calls_checked, observed_projected = _validate_source_suite(
        source_suite
    )
    try:
        replayed_validation = validate_meter_against_suite(
            meter=meter, suite=source_suite
        )
    except Exception as error:
        raise R8EnvelopeRefusal(
            "token meter does not reproduce the source suite"
        ) from error
    if replayed_validation != dict(validation_receipt):
        raise R8EnvelopeRefusal(
            "token-meter validation receipt is not reproducible"
        )
    validation_sha, source_suite_sha = _validate_meter_receipt(
        validation_receipt,
        meter,
        source_suite_sha256=source_suite_sha,
        calls_checked=calls_checked,
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
        projected_outputs_receipt,
        source_suite_sha256=source_suite_sha,
        observed=observed_projected,
    )
    if historical.get("projected_output_tokens_by_arm") != projected:
        raise R8EnvelopeRefusal("historical and committed output projections differ")

    registries = _registries(
        protocol=protocol,
        model=model,
        model_revision=model_revision,
    )
    registry_root = canonical_sha256(
        {arm: registries[arm].registry_sha256 for arm in sorted(registries)}
    )
    minima: dict[str, dict[str, int]] = {}
    for cohort, run_id in (
        ("development", development_run_id),
        ("confirmatory", confirmatory_run_id),
    ):
        items, _summary = _cohort_items_v5(
            selection=selection,
            selection_sha256=selection_sha,
            cohort=cohort,
            run_id=run_id,
            model=model,
            model_revision=model_revision,
            envelope=historical,
            dataset_split=dataset_split,
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
    for cohort, run_id in (
        ("development", development_run_id),
        ("confirmatory", confirmatory_run_id),
    ):
        items, summary = _cohort_items_v5(
            selection=selection,
            selection_sha256=selection_sha,
            cohort=cohort,
            run_id=run_id,
            model=model,
            model_revision=model_revision,
            envelope=envelope,
            dataset_split=dataset_split,
        )
        item_count = int(summary.get("items", -1))
        component_count = int(summary.get("components", -1))
        if (
            item_count != expected[cohort]["items"]
            or component_count != expected[cohort]["components"]
        ):
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
        "derivation_policy": (
            "tight_common_componentwise_max_of_both_frozen_cohorts/v1"
        ),
        "selection_generation": "hswm-prom9-f1-r8-cohort-selection/v5",
        "dataset_split": dataset_split,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-receipt", type=Path, required=True)
    parser.add_argument("--source-suite", type=Path, required=True)
    parser.add_argument("--historical-manifest", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--validation-receipt", type=Path, required=True)
    parser.add_argument("--projected-outputs-receipt", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument(
        "--development-run-id", default=DEVELOPMENT_RUN_ID_C800
    )
    parser.add_argument(
        "--confirmatory-run-id", default=CONFIRMATORY_RUN_ID_C800
    )
    parser.add_argument(
        "--token-tolerance", type=int, default=DEFAULT_TOKEN_TOLERANCE
    )
    parser.add_argument("--output-envelope", type=Path, required=True)
    parser.add_argument("--output-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        selection, selection_file_sha = _read_bound_selection_json(
            args.selection_receipt, "v5 selection receipt"
        )
        source_suite, _suite_sha = _read_bound_json(
            args.source_suite, "source suite"
        )
        historical_manifest, _manifest_sha = _read_bound_json(
            args.historical_manifest, "historical manifest"
        )
        validation_receipt, _validation_sha = _read_bound_json(
            args.validation_receipt, "token-meter validation receipt"
        )
        projected_receipt, _projected_sha = _read_bound_json(
            args.projected_outputs_receipt, "projected outputs receipt"
        )
        meter = QwenBpeMeter(
            args.tokenizer_dir / "vocab.json",
            args.tokenizer_dir / "merges.txt",
            args.tokenizer_dir / "tokenizer_config.json",
        )
        artifacts = build_token_envelope_artifacts_v5(
            selection=selection,
            historical_manifest=historical_manifest,
            validation_receipt=validation_receipt,
            projected_outputs_receipt=projected_receipt,
            source_suite=source_suite,
            meter=meter,
            protocol_path=args.protocol,
            model=args.model,
            model_revision=args.model_revision,
            development_run_id=args.development_run_id,
            confirmatory_run_id=args.confirmatory_run_id,
            token_tolerance=args.token_tolerance,
        )
        for path, value in (
            (args.output_envelope, artifacts["token_envelope"]),
            (args.output_receipt, artifacts["derivation_receipt"]),
        ):
            if path.exists():
                raise R8EnvelopeRefusal(f"refusing to replace {path}")
            path.write_text(
                json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n",
                encoding="utf-8",
            )
            path.chmod(0o600)
        receipt = artifacts["derivation_receipt"]
        print(
            json.dumps(
                {
                    "status": "FROZEN_BEFORE_MODEL_CALLS",
                    "selection_receipt_sha256": receipt[
                        "selection_receipt_sha256"
                    ],
                    "selection_file_sha256": selection_file_sha,
                    "dataset_split": receipt["dataset_split"],
                    "per_call_input_caps": receipt["per_call_input_caps"],
                    "total_input_tokens_per_run": receipt[
                        "total_input_tokens_per_run"
                    ],
                    "development_projected_spread": receipt["development"][
                        "projected_spread"
                    ],
                    "confirmatory_projected_spread": receipt["confirmatory"][
                        "projected_spread"
                    ],
                    "receipt_sha256": receipt["receipt_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
