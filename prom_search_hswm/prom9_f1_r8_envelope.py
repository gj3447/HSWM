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
from prom_search_hswm.prom9_f1_r8_runner import (
    _item,
    _registries,
    read_stable_json,
)
from prom_search_hswm.prom9_f1_r8_source import (
    build_public_artifacts,
    write_json_once,
)
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL
from prom_search_hswm.prom9_validate_token_meter import (
    RECEIPT_SCHEMA,
    validate_meter_against_suite,
)


DERIVATION_SCHEMA = "hswm-prom9-f1-r8-token-envelope-derivation/v1"
PROJECTED_OUTPUTS_SCHEMA = "hswm-prom9-f1-projected-outputs/v1"
SOURCE_SUITE_SCHEMA = "hswm-prom9-f1-suite/v1"
EXPECTED_DEVELOPMENT_ITEMS = 55
EXPECTED_CONFIRMATORY_ITEMS = 100
EXPECTED_CONFIRMATORY_COMPONENTS = 100
DEFAULT_TOKEN_TOLERANCE = 512
DEVELOPMENT_RUN_ID = "f1-2wiki-development-r8-try3"
CONFIRMATORY_RUN_ID = "f1-2wiki-sealed-r8-try3"
R8_DERIVATION_PREIMAGE_FILE_SHA256 = {
    "selection_receipt": (
        "8b16158db888ed0023056af85e204db8e0f9e3eb307ee53dc02be2ff9674ac91"
    ),
    "historical_manifest": (
        "02e453dc25d7ec657494105d5d1592358501ac3a1fdd179e2b7e032dc890ebcc"
    ),
    "validation_receipt": (
        "03309261a7fc187a2891dedcc56c0cbccd4c569d363f06e656cad4b7ae516b24"
    ),
    "projected_outputs_receipt": (
        "f59f85dbd60b17fa2c3f344f05bcd749f5fa693e81c2b6e9736b6e6d94620e85"
    ),
    "source_suite": (
        "18b2754312c85dc9b5e225df68ad2303d9ce30a45e61b9cffb00266d2282a5bd"
    ),
    "protocol": (
        "835f1c3543838405dcff97315da86b1cc185f0a1d7758df8b0cfdf380f2f518e"
    ),
}
R8_PROTOCOL_CANONICAL_SHA256 = (
    "e5715049e427cd1a12b92eab950d7679ca94038fdbe6167ef42ff5ac72b747bf"
)
R8_DERIVATION_PREIMAGE_CANONICAL_SHA256 = {
    "selection_receipt": (
        "2a98eb24d683c304af4561a6463dfa6683a9945d1d028845af4c448e2d915bd1"
    ),
    "historical_manifest": (
        "bf047193f84ca1888cc5e9d2527f6d6e2a89bc5c049ae3e4b7c73766e8fc5957"
    ),
    "validation_receipt": (
        "e678ef48c7292a1ed03fced8ad096c7903c9a826563f476cc2a524ac0250f143"
    ),
    "projected_outputs_receipt": (
        "49f3b76061d3ea49d9f32d85d1d121ab8a68f4398df42d93cc37964c40fed250"
    ),
    "source_suite": (
        "094743d9d2059a2cf2c3e68b34122ad0c332bfdaa22383c834791f695119708c"
    ),
    "protocol": R8_PROTOCOL_CANONICAL_SHA256,
}
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class R8EnvelopeRefusal(RuntimeError):
    """The public inputs cannot support one frozen r8 token envelope."""


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise R8EnvelopeRefusal(f"{label} self-hash drifted")
    return declared


def _read_bound_json(path: Path, label: str) -> tuple[dict[str, object], str]:
    try:
        return read_stable_json(path, label)
    except Exception as error:
        raise R8EnvelopeRefusal(f"cannot capture stable {label}") from error


def _validate_source_suite(
    value: Mapping[str, object],
) -> tuple[str, int, dict[str, dict[str, int]]]:
    expected = {
        "schema_version", "run_id", "mode", "model", "model_revision",
        "manifest_sha256", "preregistration_receipt_sha256",
        "token_tolerance", "state_capacity_bytes", "max_workers",
        "registries", "item_runs", "gold_opened",
        "scientific_verdict_emitted", "suite_receipt_sha256",
    }
    if (
        set(value) != expected
        or value.get("schema_version") != SOURCE_SUITE_SCHEMA
        or value.get("mode") != "development"
        or value.get("gold_opened") is not False
        or value.get("scientific_verdict_emitted") is not False
    ):
        raise R8EnvelopeRefusal("token-meter source suite shape drifted")
    suite_sha = _self_hash(value, "suite_receipt_sha256", "token-meter source suite")
    registries = value.get("registries")
    rows = value.get("item_runs")
    if (
        not isinstance(registries, Mapping)
        or set(registries) != set(F1_ARMS)
        or not isinstance(rows, list)
        or not rows
    ):
        raise R8EnvelopeRefusal("token-meter source suite coverage drifted")
    maxima = {arm: {call: 0 for call in ("1", "2", "3")} for arm in F1_ARMS}
    calls_checked = 0
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise R8EnvelopeRefusal(f"source-suite item run {index} is malformed")
        arm = row.get("arm_id")
        calls = row.get("calls")
        if arm not in F1_ARMS or not isinstance(calls, list) or len(calls) != 3:
            raise R8EnvelopeRefusal(f"source-suite item run {index} coverage drifted")
        by_call: dict[str, int] = {}
        for raw in calls:
            if not isinstance(raw, Mapping) or raw.get("arm_id") != arm:
                raise R8EnvelopeRefusal("source-suite call identity drifted")
            call_index = raw.get("call_index")
            output_tokens = raw.get("output_tokens")
            if (
                isinstance(call_index, bool)
                or not isinstance(call_index, int)
                or call_index not in (1, 2, 3)
                or str(call_index) in by_call
                or isinstance(output_tokens, bool)
                or not isinstance(output_tokens, int)
                or output_tokens < 1
            ):
                raise R8EnvelopeRefusal("source-suite call token record drifted")
            by_call[str(call_index)] = output_tokens
            calls_checked += 1
        if set(by_call) != {"1", "2", "3"}:
            raise R8EnvelopeRefusal("source-suite call indices drifted")
        for call, output_tokens in by_call.items():
            maxima[str(arm)][call] = max(maxima[str(arm)][call], output_tokens)
    if any(value < 1 for triplet in maxima.values() for value in triplet.values()):
        raise R8EnvelopeRefusal("source-suite projection coverage is incomplete")
    return suite_sha, calls_checked, maxima


def _validate_meter_receipt(
    value: Mapping[str, object],
    meter: TokenMeter,
    *,
    source_suite_sha256: str,
    calls_checked: int,
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
        or checked != calls_checked
        or value.get("mismatches") != 0
        or value.get("result") != f"EXACT_MATCH_{checked}_OF_{checked}"
    ):
        raise R8EnvelopeRefusal("token-meter validation is not an exact match")
    source_suite = value.get("suite_receipt_sha256")
    if source_suite != source_suite_sha256:
        raise R8EnvelopeRefusal("token-meter validation source suite is invalid")
    return receipt_sha, source_suite


def _validate_projected_outputs(
    value: Mapping[str, object],
    *,
    source_suite_sha256: str,
    observed: Mapping[str, Mapping[str, int]],
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
    if result != {arm: dict(observed[arm]) for arm in F1_ARMS}:
        raise R8EnvelopeRefusal("projected outputs differ from the source suite")
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
    source_suite: Mapping[str, object],
    meter: TokenMeter,
    protocol_path: Path | None = None,
    protocol: Mapping[str, object] | None = None,
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
    selection_sha = verify_selection_receipt(selection)
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


def verify_token_envelope_derivation(
    *,
    receipt: Mapping[str, object],
    manifest: Mapping[str, object],
    selection: Mapping[str, object],
    historical_manifest: Mapping[str, object],
    validation_receipt: Mapping[str, object],
    projected_outputs_receipt: Mapping[str, object],
    source_suite: Mapping[str, object],
    protocol: Mapping[str, object] | None = None,
    meter: TokenMeter,
    protocol_path: Path | None = None,
    file_sha256s: Mapping[str, str],
    expected_file_sha256s: Mapping[str, str] = R8_DERIVATION_PREIMAGE_FILE_SHA256,
    expected_canonical_sha256s: Mapping[str, str] = (
        R8_DERIVATION_PREIMAGE_CANONICAL_SHA256
    ),
    development_run_id: str = DEVELOPMENT_RUN_ID,
    confirmatory_run_id: str = CONFIRMATORY_RUN_ID,
    expected_development_items: int = EXPECTED_DEVELOPMENT_ITEMS,
    expected_confirmatory_items: int = EXPECTED_CONFIRMATORY_ITEMS,
) -> str:
    """Replay the exact public producer and require byte-semantic identity."""

    if protocol is None:
        if protocol_path is None:
            raise R8EnvelopeRefusal("protocol preimage is required")
        protocol, protocol_file_sha = _read_bound_json(
            protocol_path, "PROM-9 protocol"
        )
        if file_sha256s.get("protocol") != protocol_file_sha:
            raise R8EnvelopeRefusal("protocol file preimage drifted")
    if dict(file_sha256s) != dict(expected_file_sha256s):
        raise R8EnvelopeRefusal("token-envelope derivation file preimages drifted")
    observed_canonical = {
        "selection_receipt": canonical_sha256(selection),
        "historical_manifest": canonical_sha256(historical_manifest),
        "validation_receipt": canonical_sha256(validation_receipt),
        "projected_outputs_receipt": canonical_sha256(
            projected_outputs_receipt
        ),
        "source_suite": canonical_sha256(source_suite),
        "protocol": canonical_sha256(protocol),
    }
    if observed_canonical != dict(expected_canonical_sha256s):
        raise R8EnvelopeRefusal("token-envelope canonical preimages drifted")
    model = manifest.get("model")
    model_revision = manifest.get("model_revision")
    tolerance = manifest.get("token_tolerance")
    if (
        not isinstance(model, str)
        or not isinstance(model_revision, str)
        or isinstance(tolerance, bool)
        or not isinstance(tolerance, int)
    ):
        raise R8EnvelopeRefusal("manifest derivation identity drifted")
    artifacts = build_token_envelope_artifacts(
        selection=selection,
        historical_manifest=historical_manifest,
        validation_receipt=validation_receipt,
        projected_outputs_receipt=projected_outputs_receipt,
        source_suite=source_suite,
        protocol=protocol,
        meter=meter,
        model=model,
        model_revision=model_revision,
        development_run_id=development_run_id,
        confirmatory_run_id=confirmatory_run_id,
        token_tolerance=tolerance,
        expected_development_items=expected_development_items,
        expected_confirmatory_items=expected_confirmatory_items,
    )
    if artifacts["token_envelope"] != manifest.get("token_envelope"):
        raise R8EnvelopeRefusal("replayed token envelope differs from the manifest")
    if artifacts["derivation_receipt"] != dict(receipt):
        raise R8EnvelopeRefusal("token-envelope derivation receipt is not reproducible")
    return _self_hash(receipt, "receipt_sha256", "token-envelope derivation receipt")


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
    parser.add_argument("--source-suite", type=Path, required=True)
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
        selection, selection_file_sha = _read_bound_json(
            args.selection_receipt, "public selection receipt"
        )
        historical, historical_file_sha = _read_bound_json(
            args.historical_manifest, "historical manifest"
        )
        validation, validation_file_sha = _read_bound_json(
            args.validation_receipt, "token-meter validation receipt"
        )
        projected, projected_file_sha = _read_bound_json(
            args.projected_outputs_receipt, "projected-output receipt"
        )
        source_suite, source_suite_file_sha = _read_bound_json(
            args.source_suite, "token-meter source suite"
        )
        protocol, protocol_file_sha = _read_bound_json(
            args.protocol, "PROM-9 protocol"
        )
        observed_files = {
            "selection_receipt": selection_file_sha,
            "historical_manifest": historical_file_sha,
            "validation_receipt": validation_file_sha,
            "projected_outputs_receipt": projected_file_sha,
            "source_suite": source_suite_file_sha,
            "protocol": protocol_file_sha,
        }
        if observed_files != R8_DERIVATION_PREIMAGE_FILE_SHA256:
            raise R8EnvelopeRefusal("token-envelope derivation file preimages drifted")
        artifacts = build_token_envelope_artifacts(
            selection=selection,
            historical_manifest=historical,
            validation_receipt=validation,
            projected_outputs_receipt=projected,
            source_suite=source_suite,
            protocol=protocol,
            meter=meter,
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
    "CONFIRMATORY_RUN_ID",
    "DEVELOPMENT_RUN_ID",
    "DERIVATION_SCHEMA",
    "R8_DERIVATION_PREIMAGE_FILE_SHA256",
    "R8_DERIVATION_PREIMAGE_CANONICAL_SHA256",
    "R8_PROTOCOL_CANONICAL_SHA256",
    "R8EnvelopeRefusal",
    "build_token_envelope_artifacts",
    "verify_token_envelope_derivation",
    "write_artifacts_once",
]
