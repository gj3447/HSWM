from __future__ import annotations

from dataclasses import replace
import inspect
import json

import pytest

from hswm.experiments import swm0_protocol as protocol


@pytest.fixture(scope="module")
def pilot_manifest() -> protocol.SWM0Manifest:
    return protocol.build_manifest(
        protocol.RunMode.PILOT,
        train_blocks=1,
        dev_blocks=1,
        fresh_blocks=1,
        bootstrap=protocol.BootstrapSpec(resamples=64, seed=17),
    )


@pytest.fixture(scope="module")
def pilot_result(pilot_manifest: protocol.SWM0Manifest) -> protocol.SWM0Result:
    return protocol.run_manifest(pilot_manifest)


def _estimate(point: float, lower: float, upper: float) -> protocol.Estimate:
    interval = protocol.ConfidenceInterval(lower, upper)
    return protocol.Estimate(
        point=point,
        paired_ci=interval,
        two_level_ci=interval,
    )


def _metrics(
    *,
    primary: tuple[float, float, float] = (0.20, 0.15, 0.25),
    star: tuple[float, float, float] = (0.0, -0.01, 0.01),
    chance: tuple[float, float, float] = (0.30, 0.25, 0.35),
    ablation: tuple[float, float, float] = (0.10, 0.05, 0.15),
    irrelevant: tuple[float, float, float] = (0.0, -0.01, 0.01),
    positive_seeds: int = 16,
    seed_count: int = 20,
) -> protocol.MetricSummary:
    return protocol.MetricSummary(
        primary_target_minus_lossy=_estimate(*primary),
        target_minus_star=_estimate(*star),
        target_minus_chance=_estimate(*chance),
        ablation_excess=_estimate(*ablation),
        target_minus_irrelevant_removal=_estimate(*irrelevant),
        ablation_removal_fraction=0.80,
        positive_seed_count=positive_seeds,
        seed_count=seed_count,
    )


def test_manifest_is_deterministic_block_atomic_and_source_bound(
    pilot_manifest: protocol.SWM0Manifest,
) -> None:
    repeated = protocol.build_manifest(
        "pilot",
        train_blocks=1,
        dev_blocks=1,
        fresh_blocks=1,
        bootstrap=protocol.BootstrapSpec(resamples=64, seed=17),
    )
    assert pilot_manifest.to_json() == repeated.to_json()
    assert pilot_manifest.seeds == protocol.PILOT_SEEDS == (0, 1, 2)
    assert set(protocol.PILOT_SEEDS).isdisjoint(protocol.CONFIRMATORY_SEEDS)
    assert len(pilot_manifest.blocks) == 3 * 3
    assert {row.split for row in pilot_manifest.blocks} == {"train", "dev", "test"}
    assert pilot_manifest.ridge == protocol.DEFAULT_RIDGE
    assert dict(pilot_manifest.source_sha256).keys() == set(protocol.SOURCE_PATHS)
    assert pilot_manifest.star_compiler_attestation["independent"] is True

    integrity = protocol.validate_manifest(pilot_manifest)
    assert integrity.passed
    assert integrity.blocks_checked == len(pilot_manifest.blocks)
    assert dict(integrity.checks)["exact_uniform_lossy_buckets"]
    assert dict(integrity.checks)["typed_star_independent_compiler"]


def test_exact_uniform_bucket_contract_rejects_label_leakage() -> None:
    digest = "a" * 64
    receipt = protocol.require_uniform_lossy_buckets(
        [digest, digest, digest], [0, 1, 2]
    )
    assert receipt["bucket_count"] == 1
    assert receipt["buckets"][0]["target_counts"] == [1, 1, 1]

    with pytest.raises(protocol.SWM0ProtocolError, match="target-uniform"):
        protocol.require_uniform_lossy_buckets(
            [digest, digest, digest], [0, 0, 1]
        )
    with pytest.raises(protocol.SWM0ProtocolError, match="no collision"):
        protocol.require_uniform_lossy_buckets(
            ["a" * 64, "b" * 64, "c" * 64], [0, 1, 2]
        )


def test_manifest_corruption_is_detected_even_when_outer_hash_is_resealed(
    pilot_manifest: protocol.SWM0Manifest,
) -> None:
    corrupt_ref = replace(pilot_manifest.blocks[0], block_sha256="0" * 64)
    corrupt = replace(
        pilot_manifest,
        blocks=(corrupt_ref, *pilot_manifest.blocks[1:]),
        manifest_sha256="0" * 64,
    )
    corrupt = replace(
        corrupt, manifest_sha256=protocol.canonical_sha256(corrupt.unsigned())
    )
    with pytest.raises(protocol.SWM0ProtocolError, match="deterministic replay"):
        protocol.validate_manifest(corrupt)


def test_confirmatory_contract_refuses_before_generating_any_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_generation(**_: object) -> None:
        raise AssertionError("confirmatory seeds must not run in unit tests")

    monkeypatch.setattr(protocol.worlds, "generate_block", forbidden_generation)
    with pytest.raises(protocol.SWM0ProtocolError, match="block counts"):
        protocol.build_manifest("confirmatory", fresh_blocks=2)
    with pytest.raises(protocol.SWM0ProtocolError, match="thresholds"):
        protocol.build_manifest(
            "confirmatory",
            thresholds=replace(protocol.Thresholds(), effect_floor=0.11),
        )
    with pytest.raises(protocol.SWM0ProtocolError, match="bootstrap"):
        protocol.build_manifest(
            "confirmatory",
            bootstrap=protocol.BootstrapSpec(resamples=1999),
        )
    with pytest.raises(protocol.SWM0ProtocolError, match="ridge"):
        protocol.build_manifest("confirmatory", ridge=2.0e-6)
    with pytest.raises(protocol.SWM0ProtocolError, match="preregistration"):
        protocol.build_manifest("confirmatory")


def test_preregistration_payload_binds_every_frozen_confirmatory_field() -> None:
    valid = {
        **protocol.frozen_preregistration_contract(),
        "question": "extra narrative fields are allowed",
    }
    assert len(protocol.validate_preregistration_payload(valid)) == 64

    corruptions = {
        "schema": "hswm-swm0r-preregistration/v0",
        "mode": "pilot",
        "q": 4,
        "seeds": [100],
        "block_counts": {"train": 1, "dev": 1, "test": 2},
        "arms": list(reversed(protocol.ALL_ARMS)),
        "lossy_arms": list(reversed(protocol.LOSSY_ARMS)),
        "thresholds": {
            **protocol.Thresholds().canonical(),
            "effect_floor": 0.11,
        },
        "bootstrap": {
            **protocol.BootstrapSpec().canonical(),
            "resamples": 1999,
        },
        "ridge": 2.0e-6,
        "source_paths": [*protocol.SOURCE_PATHS, "src/extra.py"],
        "registered_before_measurement": False,
        "confirmatory_measurements_run_before_registration": True,
    }
    for field, bad_value in corruptions.items():
        with pytest.raises(protocol.SWM0ProtocolError, match=field):
            protocol.validate_preregistration_payload(
                {**valid, field: bad_value}
            )

    missing = dict(valid)
    del missing["target_arm"]
    with pytest.raises(protocol.SWM0ProtocolError, match="target_arm"):
        protocol.validate_preregistration_payload(missing)


def test_paired_and_two_level_bootstraps_are_deterministic() -> None:
    spec = protocol.BootstrapSpec(resamples=256, seed=91)
    values = {0: (0.0, 0.2, 0.4), 1: (0.6, 0.8, 1.0), 2: (0.1, 0.3, 0.5)}
    paired = protocol.paired_bootstrap_ci(
        [value for seed in sorted(values) for value in values[seed]], spec=spec
    )
    clustered = protocol.two_level_bootstrap_ci(values, spec=spec)
    assert paired == protocol.paired_bootstrap_ci(
        [value for seed in sorted(values) for value in values[seed]], spec=spec
    )
    assert clustered == protocol.two_level_bootstrap_ci(values, spec=spec)
    assert 0.0 <= paired.lower <= paired.upper <= 1.0
    assert 0.0 <= clustered.lower <= clustered.upper <= 1.0


def test_reducer_has_explicit_pass_kill_inconclusive_and_void_states(
    pilot_manifest: protocol.SWM0Manifest,
) -> None:
    integrity = protocol.validate_manifest(pilot_manifest)
    passed = protocol.reduce_verdict("confirmatory", integrity, _metrics())
    assert passed.verdict is protocol.Verdict.PASS

    killed = protocol.reduce_verdict(
        "confirmatory",
        integrity,
        _metrics(primary=(0.02, 0.0, 0.05)),
    )
    assert killed.verdict is protocol.Verdict.KILL
    assert "PRIMARY_EFFECT_BELOW_FLOOR" in killed.reason_codes

    inconclusive = protocol.reduce_verdict(
        "confirmatory",
        integrity,
        _metrics(primary=(0.10, 0.05, 0.15)),
    )
    assert inconclusive.verdict is protocol.Verdict.INCONCLUSIVE

    failed_integrity = replace(
        integrity,
        passed=False,
        errors=("CORRUPTED_FIXTURE",),
    )
    void = protocol.reduce_verdict("confirmatory", failed_integrity, _metrics())
    assert void.verdict is protocol.Verdict.VOID

    star_outside_rope = protocol.reduce_verdict(
        "confirmatory",
        integrity,
        _metrics(star=(0.04, 0.03, 0.05)),
    )
    assert star_outside_rope.verdict is protocol.Verdict.KILL
    assert "STAR_EQUIVALENCE_FAILED" in star_outside_rope.reason_codes

    irrelevant_loss = protocol.reduce_verdict(
        "confirmatory",
        integrity,
        _metrics(irrelevant=(0.10, 0.08, 0.12)),
    )
    assert irrelevant_loss.verdict is protocol.Verdict.KILL
    assert "IRRELEVANT_REMOVAL_SPECIFICITY_FAILED" in irrelevant_loss.reason_codes


def test_small_pilot_runs_and_replays_without_scientific_promotion(
    pilot_manifest: protocol.SWM0Manifest,
    pilot_result: protocol.SWM0Result,
) -> None:
    assert pilot_result.integrity.passed
    assert pilot_result.reduction.verdict is protocol.Verdict.INCONCLUSIVE
    assert pilot_result.scientific_status == "UNJUDGED"
    assert pilot_result.implementation_status == "IMPLEMENTED"
    assert pilot_result.strongest_lossy_arm in protocol.LOSSY_ARMS
    assert pilot_result.metrics is not None
    assert pilot_result.metrics.primary_target_minus_lossy.point == pytest.approx(2 / 3)
    assert pilot_result.metrics.ablation_removal_fraction == pytest.approx(1.0)
    assert pilot_result.metrics.target_minus_irrelevant_removal.point == pytest.approx(0.0)
    assert protocol.replay_result(pilot_manifest, pilot_result) == pilot_result

    payload = json.loads(pilot_result.to_json())
    assert payload["learned_operator_claim"] is False
    assert payload["next_gate"] == "SWM-0W"
    assert payload["scientific_status"] == "UNJUDGED"
    assert payload["parity_scope"] == "NOMINAL_DENSE_READOUT_PARAMETER_COUNT_ONLY"
    assert {receipt["ridge"] for receipt in payload["model_receipts"] if "ridge" in receipt} == {
        protocol.DEFAULT_RIDGE
    }
    model_receipts = {
        receipt["arm"]: receipt
        for receipt in payload["model_receipts"]
        if receipt.get("seed") == protocol.PILOT_SEEDS[0]
    }
    target_receipt = model_receipts[protocol.TARGET_ARM]
    star_receipt = model_receipts[protocol.STAR_ARM]
    assert target_receipt["effective_feature_count"] > 0
    assert star_receipt["effective_feature_count"] > 0
    assert (
        target_receipt["encoder_operation_estimate"]["total_units"]
        != star_receipt["encoder_operation_estimate"]["total_units"]
    )
    assert {
        receipt["encoder_cost_scope"] for receipt in model_receipts.values()
    } == {"STRUCTURAL_UNITS_NOT_FLOPS_OR_EQUAL_COMPUTE"}
    assert "ridge" not in inspect.signature(protocol.run_manifest).parameters

    engineering_pass = replace(
        pilot_result,
        reduction=protocol.reduce_verdict(
            "confirmatory", pilot_result.integrity, _metrics()
        ),
    )
    assert engineering_pass.reduction.verdict is protocol.Verdict.PASS
    assert engineering_pass.scientific_status == "UNJUDGED"
    assert engineering_pass.claim.startswith("SWM-0R engineering PASS")
    assert "does not pass" in engineering_pass.claim


def test_cli_emits_canonical_machine_readable_pilot_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = protocol.main(
        [
            "--mode",
            "pilot",
            "--train-blocks",
            "1",
            "--dev-blocks",
            "1",
            "--fresh-blocks",
            "1",
            "--bootstrap-resamples",
            "32",
            "--bootstrap-seed",
            "11",
        ]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert output == protocol.canonical_json(payload) + "\n"
    assert payload["manifest"]["mode"] == "pilot"
    assert payload["manifest"]["seeds"] == [0, 1, 2]
    assert payload["result"]["reduction"]["verdict"] == "INCONCLUSIVE"
    assert payload["result"]["scientific_status"] == "UNJUDGED"
