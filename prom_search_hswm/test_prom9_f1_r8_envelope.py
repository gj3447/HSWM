from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from prom_search_hswm.hswm_function_network import F1_ARMS
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_r8_envelope import (
    R8EnvelopeRefusal,
    build_token_envelope_artifacts,
    write_artifacts_once,
)
from prom_search_hswm.prom9_f1_r8_power import build_selection_receipts
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL
from prom_search_hswm.test_prom9_f1_r8_power import SENTINEL, _pages, _prior


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


def _public_selection(tmp_path: Path) -> dict[str, object]:
    development, confirmatory = _pages(tmp_path, answer=SENTINEL)
    selection, _gold_source = build_selection_receipts(
        prior_receipt=_prior(),
        development_pages=development,
        confirmatory_pages=confirmatory,
    )
    assert SENTINEL not in json.dumps(selection, ensure_ascii=False)
    return selection


def _validation(meter: FakeMeter) -> dict[str, object]:
    unsigned = {
        "schema_version": "hswm-prom9-token-meter-validation/v1",
        "meter": meter.identity(),
        "suite_receipt_sha256": "a" * 64,
        "calls_checked": 60,
        "mismatches": 0,
        "result": "EXACT_MATCH_60_OF_60",
    }
    return {**unsigned, "validation_receipt_sha256": canonical_sha256(unsigned)}


def _projected() -> dict[str, object]:
    return {
        "schema_version": "hswm-prom9-f1-projected-outputs/v1",
        "derivation": "unit-test public projection",
        "projected_output_tokens_by_arm": {
            arm: {"1": 7, "2": 11, "3": 5} for arm in F1_ARMS
        },
        "source_suite_receipt_sha256": "a" * 64,
    }


def _historical(meter: FakeMeter, validation: dict[str, object]) -> dict[str, object]:
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
            "projected_output_tokens_by_arm": _projected()[
                "projected_output_tokens_by_arm"
            ],
            "projection_slack_tokens": 8,
        },
    }


def _artifacts(tmp_path: Path) -> dict[str, dict[str, object]]:
    meter = FakeMeter()
    validation = _validation(meter)
    return build_token_envelope_artifacts(
        selection=_public_selection(tmp_path),
        historical_manifest=_historical(meter, validation),
        validation_receipt=validation,
        projected_outputs_receipt=_projected(),
        meter=meter,
        protocol_path=DEFAULT_PROTOCOL,
        model="qwen3.6-27b",
        model_revision=REVISION,
        development_run_id="f1-2wiki-development-r8-try3",
        confirmatory_run_id="f1-2wiki-sealed-r8-try3",
        expected_development_items=66,
        expected_confirmatory_items=100,
    )


def test_public_only_builder_derives_tight_common_caps(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
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
    assert receipt["development"]["items"] == 66
    assert receipt["development"]["components"] == 48
    assert receipt["confirmatory"]["items"] == 100
    assert receipt["confirmatory"]["components"] == 100
    assert receipt["gold_inputs_read"] is False
    assert receipt["model_calls"] == 0
    unsigned = dict(receipt)
    declared = unsigned.pop("receipt_sha256")
    assert canonical_sha256(unsigned) == declared


def test_meter_or_projection_drift_refuses_before_output(tmp_path: Path) -> None:
    meter = FakeMeter()
    validation = _validation(meter)
    validation["meter"] = {**meter.identity(), "source": "mutated"}
    with pytest.raises(R8EnvelopeRefusal, match="self-hash drifted"):
        build_token_envelope_artifacts(
            selection=_public_selection(tmp_path),
            historical_manifest=_historical(meter, _validation(meter)),
            validation_receipt=validation,
            projected_outputs_receipt=_projected(),
            meter=meter,
            protocol_path=DEFAULT_PROTOCOL,
            model="qwen3.6-27b",
            model_revision=REVISION,
            development_run_id="dev",
            confirmatory_run_id="sealed",
            expected_development_items=66,
            expected_confirmatory_items=100,
        )


def test_first_write_is_private_and_never_replaced(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
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
