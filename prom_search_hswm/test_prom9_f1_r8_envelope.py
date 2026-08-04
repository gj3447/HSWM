from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_function_network import F1_ARMS
from prom_search_hswm.hswm_function_registry import (
    FunctionRegistryError,
    build_registry,
    build_registry_from_protocol,
)
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_r8_envelope import (
    DEVELOPMENT_RUN_ID,
    EXPECTED_DEVELOPMENT_ITEMS,
    R8_ABORTED_ATTEMPT_EXPOSURE_RECEIPT_SHA256,
    R8_DERIVATION_PREIMAGE_CANONICAL_SHA256,
    R8_DERIVATION_PREIMAGE_FILE_SHA256,
    R8_SELECTION_RECEIPT_SHA256,
    R8EnvelopeRefusal,
    _verify_frozen_selection_identity,
    build_token_envelope_artifacts,
    verify_token_envelope_derivation,
    write_artifacts_once,
)
from prom_search_hswm.prom9_f1_r8_power import build_selection_receipts
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL, read_json as read_protocol
from prom_search_hswm.prom9_validate_token_meter import validate_meter_against_suite
from prom_search_hswm.prom_f1_function_network import _arm_overrides
from prom_search_hswm.test_prom9_f1_r8_power import (
    SENTINEL,
    _incident,
    _pages,
    _prior,
    _successor_wrapper,
    _synthetic_incident_source_entities,
)


REVISION = "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"


class FakeMeter:
    def count_text(self, text: str) -> int:
        return max(1, len(text.encode("utf-8")) // 5)

    def count_chat_prompt(self, system_prompt: str, user_text: str) -> int:
        return 11 + self.count_text(system_prompt) + self.count_text(user_text)

    def identity(self) -> dict[str, object]:
        return {
            "kind": "test-byte-meter/v1",
            "source": "unit-test",
            "vocab_sha256": "1" * 64,
            "merges_sha256": "2" * 64,
            "config_sha256": "3" * 64,
            "chat_template_id": "test-chat-template/v1",
        }


def _public_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    development, confirmatory = _pages(tmp_path, answer=SENTINEL)
    successor, _second_component = _successor_wrapper(
        monkeypatch, distinct_component=True
    )
    selection, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        aborted_attempt_exposure_receipt=successor,
        development_pages=development,
        confirmatory_pages=confirmatory,
        forensic_legacy_replay=False,
    )
    assert SENTINEL not in json.dumps(selection, ensure_ascii=False)
    return selection


def _source_suite(meter: FakeMeter) -> dict[str, object]:
    registries = {
        arm: build_registry(
            DEFAULT_PROTOCOL,
            model="qwen3.6-27b",
            model_revision=REVISION,
            prompt_overrides=_arm_overrides(arm),
        ).canonical()
        for arm in F1_ARMS
    }
    rows: list[dict[str, object]] = []
    output_by_call = {1: 7, 2: 11, 3: 5}
    for arm in F1_ARMS:
        calls: list[dict[str, object]] = []
        for call_index, function in enumerate(registries[arm]["functions"], start=1):
            payload = {"request_id": f"{arm}-{call_index}"}
            call_unsigned = {
                "schema_version": "hswm-model-call/v1",
                "arm_id": arm,
                "function_id": function["function_id"],
                "call_index": call_index,
                "input_payload": payload,
                "input_tokens": meter.count_chat_prompt(
                    function["prompt"], canonical_json(payload)
                ),
                "output_tokens": output_by_call[call_index],
            }
            calls.append(
                {
                    **call_unsigned,
                    "receipt_sha256": canonical_sha256(call_unsigned),
                }
            )
        row_unsigned = {
            "schema_version": "hswm-f1-item-run/v1",
            "run_id": "f1-2wiki-dev-r4-20260724",
            "arm_id": arm,
            "item_id": f"item-{arm}",
            "calls": calls,
        }
        rows.append(
            {**row_unsigned, "run_receipt_sha256": canonical_sha256(row_unsigned)}
        )
    unsigned = {
        "schema_version": "hswm-prom9-f1-suite/v1",
        "run_id": "f1-2wiki-dev-r4-20260724",
        "mode": "development",
        "model": "qwen3.6-27b",
        "model_revision": REVISION,
        "manifest_sha256": "4" * 64,
        "preregistration_receipt_sha256": None,
        "token_tolerance": 768,
        "state_capacity_bytes": 4096,
        "max_workers": 1,
        "registries": registries,
        "item_runs": rows,
        "gold_opened": False,
        "scientific_verdict_emitted": False,
    }
    return {**unsigned, "suite_receipt_sha256": canonical_sha256(unsigned)}


def _validation(meter: FakeMeter, source_suite: dict[str, object]) -> dict[str, object]:
    return validate_meter_against_suite(meter=meter, suite=source_suite)


def _projected(source_suite: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "hswm-prom9-f1-projected-outputs/v1",
        "derivation": "unit-test public projection",
        "projected_output_tokens_by_arm": {
            arm: {"1": 7, "2": 11, "3": 5} for arm in F1_ARMS
        },
        "source_suite_receipt_sha256": source_suite["suite_receipt_sha256"],
    }


def _historical(
    meter: FakeMeter,
    validation: dict[str, object],
    source_suite: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": "hswm-prom9-f1-manifest/v2",
        "token_envelope": {
            "schema_version": "hswm-prom9-f1-token-envelope/v1",
            "tokenizer": {
                **meter.identity(),
                "validation_receipt_sha256": validation[
                    "validation_receipt_sha256"
                ],
            },
            "filler": {
                "field": "parity_filler",
                "unit": "0",
                "max_filler_chars": 60000,
            },
            # Deliberately loose: the r8 producer must derive a tight common
            # envelope, not preserve these historical input caps as a floor.
            "per_call_input_caps": {"1": 9000, "2": 9000, "3": 9000},
            "per_call_output_caps": {"1": 64, "2": 64, "3": 64},
            "projected_output_tokens_by_arm": _projected(source_suite)[
                "projected_output_tokens_by_arm"
            ],
            "projection_slack_tokens": 8,
        },
    }


def _artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    meter = FakeMeter()
    source_suite = _source_suite(meter)
    validation = _validation(meter, source_suite)
    selection = _public_selection(tmp_path, monkeypatch)
    artifacts = build_token_envelope_artifacts(
        selection=selection,
        historical_manifest=_historical(meter, validation, source_suite),
        validation_receipt=validation,
        projected_outputs_receipt=_projected(source_suite),
        source_suite=source_suite,
        meter=meter,
        protocol_path=DEFAULT_PROTOCOL,
        model="qwen3.6-27b",
        model_revision=REVISION,
        development_run_id=DEVELOPMENT_RUN_ID,
        confirmatory_run_id="f1-2wiki-sealed-r8-try3",
        expected_development_items=len(selection["development"]["item_ids"]),
        expected_confirmatory_items=100,
    )
    return artifacts, selection


def test_public_only_builder_derives_tight_common_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts, selection = _artifacts(tmp_path, monkeypatch)
    receipt = artifacts["derivation_receipt"]
    development = receipt["development"]["minimum_input_caps"]
    confirmatory = receipt["confirmatory"]["minimum_input_caps"]
    expected = {
        call: max(development[call], confirmatory[call])
        for call in ("1", "2", "3")
    }
    assert receipt["per_call_input_caps"] == expected
    assert artifacts["token_envelope"]["per_call_input_caps"] == expected
    assert expected != {"1": 9000, "2": 9000, "3": 9000}
    assert receipt["historical_input_caps_used_as_floor"] is False
    assert receipt["development"]["items"] == len(
        selection["development"]["item_ids"]
    )
    assert receipt["development"]["components"] == 48
    assert receipt["confirmatory"]["items"] == 100
    assert receipt["confirmatory"]["components"] == 100
    assert receipt["gold_inputs_read"] is False
    assert receipt["model_calls"] == 0
    unsigned = dict(receipt)
    declared = unsigned.pop("receipt_sha256")
    assert canonical_sha256(unsigned) == declared


def test_meter_or_projection_drift_refuses_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meter = FakeMeter()
    source_suite = _source_suite(meter)
    validation = _validation(meter, source_suite)
    validation["meter"] = {**meter.identity(), "source": "mutated"}
    with pytest.raises(R8EnvelopeRefusal, match="not reproducible"):
        build_token_envelope_artifacts(
            selection=_public_selection(tmp_path, monkeypatch),
            historical_manifest=_historical(
                meter, _validation(meter, source_suite), source_suite
            ),
            validation_receipt=validation,
            projected_outputs_receipt=_projected(source_suite),
            source_suite=source_suite,
            meter=meter,
            protocol_path=DEFAULT_PROTOCOL,
            model="qwen3.6-27b",
            model_revision=REVISION,
            development_run_id="dev",
            confirmatory_run_id="sealed",
            expected_development_items=EXPECTED_DEVELOPMENT_ITEMS,
            expected_confirmatory_items=100,
        )


def test_production_selection_preimage_binds_final_v2_incident(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert R8_DERIVATION_PREIMAGE_FILE_SHA256["selection_receipt"] == (
        "47d1cc8095564d1efe2aae5e6c9de1da00c5eb24f7cf0063c9350313b8886c6c"
    )
    assert R8_DERIVATION_PREIMAGE_CANONICAL_SHA256["selection_receipt"] == (
        "e7408d8be7ad6d1ea5a2a31779c0d3968dbf4a3bc1e19c45e59cf57ad8db711d"
    )
    assert R8_SELECTION_RECEIPT_SHA256 == (
        "7cc231d965ee21618481fe8af2fbbd06641c536c514aef5e2f4d9a2fe0f2b1bc"
    )
    assert R8_ABORTED_ATTEMPT_EXPOSURE_RECEIPT_SHA256 == (
        "59a9a1cd4b54517b7b2193fff17acd5402f84525b40cbbd628af1ab4fd38fd0a"
    )
    assert (
        R8_DERIVATION_PREIMAGE_FILE_SHA256["selection_receipt"]
        != "999d5c38f0e0ccfe594a8c69cc0b697fb2a6972835f3472144b2d51fcce2fcab"
    )
    assert (
        R8_DERIVATION_PREIMAGE_CANONICAL_SHA256["selection_receipt"]
        != "03143d6e84e1d0c787d49db3e16f73b7833630b16f3a8f44a19d84fd5ed5a846"
    )
    assert R8_SELECTION_RECEIPT_SHA256 != (
        "0cea21ecaaa7bb6ac19047326029120c84a8fcbdda8ff6f4141634d8279be641"
    )
    assert R8_ABORTED_ATTEMPT_EXPOSURE_RECEIPT_SHA256 != (
        "6d3f2f8978a8502c0f01135ad7b998841dbb4bd61462934927f735e3932bad7d"
    )
    assert R8_ABORTED_ATTEMPT_EXPOSURE_RECEIPT_SHA256 != (
        "200e0708f556231b8ee4d83dea76ec923fb27071a76e2a27045e6ee218578fb0"
    )

    resigned = copy.deepcopy(_public_selection(tmp_path, monkeypatch))
    resigned["aborted_attempt_exposure_receipt_sha256"] = (
        "6d3f2f8978a8502c0f01135ad7b998841dbb4bd61462934927f735e3932bad7d"
    )
    unsigned = dict(resigned)
    unsigned.pop("selection_receipt_sha256")
    resigned["selection_receipt_sha256"] = canonical_sha256(unsigned)
    synthetic_file_sha = "7" * 64
    with pytest.raises(
        R8EnvelopeRefusal, match="selection exposure binding is not final v2"
    ):
        _verify_frozen_selection_identity(
            resigned,
            file_sha256=synthetic_file_sha,
            expected_file_sha256=synthetic_file_sha,
            expected_canonical_sha256=canonical_sha256(resigned),
            expected_receipt_sha256=str(resigned["selection_receipt_sha256"]),
            expected_aborted_exposure_sha256=(
                R8_ABORTED_ATTEMPT_EXPOSURE_RECEIPT_SHA256
            ),
        )


def test_verifier_replays_receipt_and_rejects_resigned_preimage_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meter = FakeMeter()
    selection = _public_selection(tmp_path, monkeypatch)
    source_suite = _source_suite(meter)
    validation = _validation(meter, source_suite)
    projected = _projected(source_suite)
    historical = _historical(meter, validation, source_suite)
    artifacts = build_token_envelope_artifacts(
        selection=selection,
        historical_manifest=historical,
        validation_receipt=validation,
        projected_outputs_receipt=projected,
        source_suite=source_suite,
        meter=meter,
        protocol_path=DEFAULT_PROTOCOL,
        model="qwen3.6-27b",
        model_revision=REVISION,
        development_run_id=DEVELOPMENT_RUN_ID,
        confirmatory_run_id="f1-2wiki-sealed-r8-try3",
        expected_development_items=len(selection["development"]["item_ids"]),
        expected_confirmatory_items=100,
    )
    receipt = artifacts["derivation_receipt"]
    manifest = {
        "model": "qwen3.6-27b",
        "model_revision": REVISION,
        "token_tolerance": receipt["token_tolerance"],
        "token_envelope": artifacts["token_envelope"],
    }
    fixed_files = {
        "selection_receipt": "8" * 64,
        "historical_manifest": "9" * 64,
        "validation_receipt": "a" * 64,
        "projected_outputs_receipt": "b" * 64,
        "source_suite": "c" * 64,
        "protocol": (
            "835f1c3543838405dcff97315da86b1cc185f0a1d7758df8b0cfdf380f2f518e"
        ),
    }
    fixed_canonical = {
        "selection_receipt": canonical_sha256(selection),
        "historical_manifest": canonical_sha256(historical),
        "validation_receipt": canonical_sha256(validation),
        "projected_outputs_receipt": canonical_sha256(projected),
        "source_suite": canonical_sha256(source_suite),
        "protocol": (
            "e5715049e427cd1a12b92eab950d7679ca94038fdbe6167ef42ff5ac72b747bf"
        ),
    }
    selection_identity = {
        "expected_selection_receipt_sha256": selection[
            "selection_receipt_sha256"
        ],
        "expected_aborted_exposure_sha256": selection[
            "aborted_attempt_exposure_receipt_sha256"
        ],
    }
    assert verify_token_envelope_derivation(
        receipt=receipt,
        manifest=manifest,
        selection=selection,
        historical_manifest=historical,
        validation_receipt=validation,
        projected_outputs_receipt=projected,
        source_suite=source_suite,
        meter=meter,
        protocol_path=DEFAULT_PROTOCOL,
        file_sha256s=fixed_files,
        expected_file_sha256s=fixed_files,
        expected_canonical_sha256s=fixed_canonical,
        **selection_identity,
        expected_development_items=len(selection["development"]["item_ids"]),
        expected_confirmatory_items=100,
    ) == receipt["receipt_sha256"]

    resigned = copy.deepcopy(receipt)
    resigned["historical_token_envelope_sha256"] = "f" * 64
    unsigned = dict(resigned)
    unsigned.pop("receipt_sha256")
    resigned["receipt_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(R8EnvelopeRefusal, match="not reproducible"):
        verify_token_envelope_derivation(
            receipt=resigned,
            manifest=manifest,
            selection=selection,
            historical_manifest=historical,
            validation_receipt=validation,
            projected_outputs_receipt=projected,
            source_suite=source_suite,
            meter=meter,
            protocol_path=DEFAULT_PROTOCOL,
            file_sha256s=fixed_files,
            expected_file_sha256s=fixed_files,
            expected_canonical_sha256s=fixed_canonical,
            **selection_identity,
            expected_development_items=len(selection["development"]["item_ids"]),
            expected_confirmatory_items=100,
        )

    drifted_files = {**fixed_files, "source_suite": "d" * 64}
    with pytest.raises(R8EnvelopeRefusal, match="file preimages drifted"):
        verify_token_envelope_derivation(
            receipt=receipt,
            manifest=manifest,
            selection=selection,
            historical_manifest=historical,
            validation_receipt=validation,
            projected_outputs_receipt=projected,
            source_suite=source_suite,
            meter=meter,
            protocol_path=DEFAULT_PROTOCOL,
            file_sha256s=drifted_files,
            expected_file_sha256s=fixed_files,
            expected_canonical_sha256s=fixed_canonical,
            **selection_identity,
            expected_development_items=len(selection["development"]["item_ids"]),
            expected_confirmatory_items=100,
        )

    resigned_source_suite = copy.deepcopy(source_suite)
    resigned_source_suite["max_workers"] = 2
    source_unsigned = dict(resigned_source_suite)
    source_unsigned.pop("suite_receipt_sha256")
    resigned_source_suite["suite_receipt_sha256"] = canonical_sha256(
        source_unsigned
    )
    with pytest.raises(R8EnvelopeRefusal, match="canonical preimages drifted"):
        verify_token_envelope_derivation(
            receipt=receipt,
            manifest=manifest,
            selection=selection,
            historical_manifest=historical,
            validation_receipt=validation,
            projected_outputs_receipt=projected,
            source_suite=resigned_source_suite,
            meter=meter,
            protocol_path=DEFAULT_PROTOCOL,
            file_sha256s=fixed_files,
            expected_file_sha256s=fixed_files,
            expected_canonical_sha256s=fixed_canonical,
            **selection_identity,
            expected_development_items=len(selection["development"]["item_ids"]),
            expected_confirmatory_items=100,
        )

    drifted_protocol = read_protocol(DEFAULT_PROTOCOL, "test PROM-9 protocol")
    drifted_protocol["llm_functions"][0]["prompt"] += " altered"
    with pytest.raises(R8EnvelopeRefusal, match="canonical preimages drifted"):
        verify_token_envelope_derivation(
            receipt=receipt,
            manifest=manifest,
            selection=selection,
            historical_manifest=historical,
            validation_receipt=validation,
            projected_outputs_receipt=projected,
            source_suite=source_suite,
            protocol=drifted_protocol,
            meter=meter,
            file_sha256s=fixed_files,
            expected_file_sha256s=fixed_files,
            expected_canonical_sha256s=fixed_canonical,
            **selection_identity,
            expected_development_items=len(selection["development"]["item_ids"]),
            expected_confirmatory_items=100,
        )


def test_first_write_is_private_and_never_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts, _selection = _artifacts(tmp_path, monkeypatch)
    envelope = tmp_path / "out" / "token-envelope.v1.json"
    receipt = tmp_path / "out" / "token-envelope-derivation.v1.json"
    write_artifacts_once(
        envelope_path=envelope, receipt_path=receipt, artifacts=artifacts
    )
    assert os.stat(envelope).st_mode & 0o777 == 0o600
    assert os.stat(receipt).st_mode & 0o777 == 0o600
    before = (envelope.read_bytes(), receipt.read_bytes())
    with pytest.raises(R8EnvelopeRefusal, match="refusing to replace"):
        write_artifacts_once(
            envelope_path=envelope, receipt_path=receipt, artifacts=artifacts
        )
    assert (envelope.read_bytes(), receipt.read_bytes()) == before


def test_cli_exposes_no_gold_or_model_call_option() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prom_search_hswm.prom9_f1_r8_envelope", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--gold" not in result.stdout
    assert "--endpoint" not in result.stdout
    assert "--upstream" not in result.stdout


def test_registry_from_captured_protocol_matches_path_and_refuses_drift() -> None:
    protocol = read_protocol(DEFAULT_PROTOCOL, "test PROM-9 protocol")
    expected = build_registry(
        DEFAULT_PROTOCOL,
        model="qwen3.6-27b",
        model_revision=REVISION,
        prompt_overrides=_arm_overrides(F1_ARMS[0]),
    )
    captured = build_registry_from_protocol(
        protocol,
        model="qwen3.6-27b",
        model_revision=REVISION,
        prompt_overrides=_arm_overrides(F1_ARMS[0]),
    )
    assert captured == expected
    drifted = copy.deepcopy(protocol)
    drifted.pop("llm_functions")
    with pytest.raises(FunctionRegistryError):
        build_registry_from_protocol(
            drifted,
            model="qwen3.6-27b",
            model_revision=REVISION,
        )
