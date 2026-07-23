from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
MANIFEST = HERE / "manifest.v1.json"
sys.path.insert(0, str(HERE))

import verify_contract as contract  # noqa: E402


def _payload() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def test_repository_design_lock_is_valid_and_explicitly_unregistered() -> None:
    assert contract.validate(REPO_ROOT, MANIFEST) == []

    payload = contract.load_json(MANIFEST)
    assert payload["status"] == contract.STATUS
    assert payload["registration"]["registered_before_measurement"] is False
    assert payload["registration"]["prediction_receipt_sha256"] is None
    assert payload["protocol_implementation"]["run_verifier_capability"] == (
        "UNIMPLEMENTED_ARTIFACT_DERIVATION"
    )
    assert payload["mechanism_baseline"]["source_hashes"] == (
        contract.MECHANISM_SOURCE_HASHES
    )
    assert contract.VERIFIER_PATH not in payload["mechanism_baseline"]["source_hashes"]


def test_self_reported_equal_budget_can_never_admit_a_v1_run(tmp_path: Path) -> None:
    run = _write(
        tmp_path / "run.json",
        {
            "equal_budget": True,
            "arm_counters": {
                "separate_heads": {"online_model_calls": 1},
                "shared_field": {"online_model_calls": 1},
            },
        },
    )

    with pytest.raises(contract.ContractError, match="cannot admit runs"):
        contract.verify_run(REPO_ROOT, MANIFEST, run)


def test_fake_hashes_cannot_promote_v1_to_preregistered(tmp_path: Path) -> None:
    payload = _payload()
    payload["status"] = "PREREGISTERED_UNRUN"
    payload["registration"] = {
        "authority": "self report",
        "locked_at": "2026-07-23",
        "registered_before_measurement": True,
        "prediction_receipt_sha256": "1" * 64,
        "run_admission": "ADMITTED",
    }
    manifest = _write(tmp_path / "fake-registration.json", payload)

    errors = contract.validate(REPO_ROOT, manifest)
    assert f"status must remain {contract.STATUS} in protocol v1" in errors
    assert "registration must remain an explicitly unregistered blocked design" in errors


def _mutate_metric_direction(payload: dict) -> None:
    payload["metrics"][0]["direction"] = "lower"


def _mutate_task_meaning(payload: dict) -> None:
    payload["tasks"][2]["purpose"] = "Alias retrieval argmax."


def _mutate_shared_identity(payload: dict) -> None:
    payload["arms"][3]["uses_shared_field"] = False


def _mutate_arm_family(payload: dict) -> None:
    payload["arms"][2]["family"] = "uncontrolled"


def _mutate_ablation(payload: dict) -> None:
    payload["arms"][4]["disabled_components"] = []


def _mutate_budget_scope(payload: dict) -> None:
    payload["budget_contract"]["parity_scope"] = "AGGREGATE_ONLY"


def _mutate_success_rule(payload: dict) -> None:
    payload["success_boundary"]["quality_path"]["require_equal_measured_budget"] = False


@pytest.mark.parametrize(
    "mutator",
    [
        _mutate_metric_direction,
        _mutate_task_meaning,
        _mutate_shared_identity,
        _mutate_arm_family,
        _mutate_ablation,
        _mutate_budget_scope,
        _mutate_success_rule,
    ],
)
def test_every_protocol_meaning_is_covered_by_one_semantic_lock(
    tmp_path: Path, mutator,
) -> None:
    payload = copy.deepcopy(_payload())
    mutator(payload)
    manifest = _write(tmp_path / f"{mutator.__name__}.json", payload)

    assert "protocol semantic lock drifted" in contract.validate(REPO_ROOT, manifest)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.update({"results_v2": {}}),
        lambda payload: payload["protocol_implementation"].update(
            {"run_admission": "ADMITTED"}
        ),
    ],
)
def test_additive_manifest_fields_cannot_bypass_semantic_lock(
    tmp_path: Path, mutator,
) -> None:
    payload = copy.deepcopy(_payload())
    mutator(payload)
    manifest = _write(tmp_path / "additive-field.json", payload)

    assert "protocol semantic lock drifted" in contract.validate(REPO_ROOT, manifest)


def test_mechanism_baseline_inventory_cannot_absorb_new_protocol_code(tmp_path: Path) -> None:
    payload = _payload()
    payload["mechanism_baseline"]["source_hashes"][contract.VERIFIER_PATH] = (
        payload["protocol_implementation"]["verifier_sha256"]
    )
    manifest = _write(tmp_path / "conflated-baseline.json", payload)

    assert "mechanism baseline source inventory drifted" in contract.validate(
        REPO_ROOT, manifest
    )


def test_verifier_bytes_are_bound_separately_from_mechanism_baseline(tmp_path: Path) -> None:
    payload = _payload()
    payload["protocol_implementation"]["verifier_sha256"] = "0" * 64
    manifest = _write(tmp_path / "verifier-drift.json", payload)

    assert "protocol verifier SHA-256 drifted" in contract.validate(REPO_ROOT, manifest)


def test_unresolved_artifacts_cannot_be_silently_filled_in_v1(tmp_path: Path) -> None:
    payload = _payload()
    payload["frozen_inputs"]["dataset_manifest_sha256"] = "a" * 64
    payload["predecessors"]["neutral_replay_receipt_sha256"] = "b" * 64
    manifest = _write(tmp_path / "fake-artifacts.json", payload)

    errors = contract.validate(REPO_ROOT, manifest)
    assert "v1 predecessors must remain present and visibly unresolved" in errors
    assert "v1 frozen inputs must remain present and visibly unresolved" in errors


def test_design_only_manifest_rejects_observed_results(tmp_path: Path) -> None:
    payload = _payload()
    payload["results"] = {"winner": "shared_field"}
    manifest = _write(tmp_path / "result-leak.json", payload)

    assert "design-only manifest cannot contain results" in contract.validate(
        REPO_ROOT, manifest
    )


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "duplicate.json"
    manifest.write_text(
        '{"schema":"hswm-shared-field-experiment/v1","schema":"other"}\n',
        encoding="utf-8",
    )

    assert contract.validate(REPO_ROOT, manifest) == ["duplicate JSON key: schema"]
