"""Deterministic aggregate teeth for the 40-control/400-fault S3 comparison."""
from __future__ import annotations

import certified_cut_compare as comparison


def test_comparison_preregistered_counts_and_verdict():
    result = comparison.run_comparison()
    assert result["verdict"] == "PASS"
    assert result["valid_controls"] == {
        "attempts": 40,
        "probe_oracle_bit_exact": 40,
        "cre_admitted": 40,
        "cre_oracle_bit_exact": 40,
        "false_refusals": 0,
        "golden_sha256": comparison.VALID_GOLDEN_SHA256,
        "golden_matches": True,
        "golden_profile": comparison.GOLDEN_PROFILE,
    }
    assert result["scope_fault_conformance"] == {
        "attempts": 400,
        "unbound_not_deployable_probe_payloads": 400,
        "cre_payloads": 0,
        "cre_typed_refusals": 400,
        "cre_pre_kernel_refusals": 400,
        "observed_zero_kernel_calls": 400,
        "expected_codes_exact": True,
    }
    assert len(result["scope_faults"]) == 10
    for fault in result["scope_faults"].values():
        assert fault["attempts"] == 40
        assert fault["probe_payloads"] == 40
        assert fault["cre_payloads"] == 0
        assert fault["typed_refusals"] == 40
        assert fault["pre_kernel_refusals"] == 40
        assert fault["observed_zero_kernel_calls"] == 40
        assert fault["observed_refusals"] == {fault["expected_refusal"]: 40}
    assert len(result["unique_adversarial_attacks"]) == 9
    for attack in result["unique_adversarial_attacks"].values():
        assert attack["observed_refusal"] == attack["expected_refusal"]
        assert attack["payload"] is False
        assert attack["kernel_calls"] == 0


def test_smart_traversal_apply_trip_and_off_receipts_are_honest():
    controls = comparison.run_comparison()["smart_traversal_safety_controls"]
    assert controls["mu_positive_apply"]["action"] == "apply"
    assert controls["mu_positive_apply"]["payload_component_bit_exact"] is True
    assert controls["mu_positive_apply"]["nonzero_traversal_residuals"] > 0
    assert controls["query_trip_fallback"]["action"] == "fallback_current_static"
    assert controls["certificate_off_fallback"] == {
        "action": "fallback_current_static",
        "executed_mu": 0.0,
    }


def test_comparison_is_deterministic():
    assert comparison.run_comparison() == comparison.run_comparison()


def test_portable_golden_ignores_only_substantive_irrelevant_float_tail():
    left = comparison._portable_golden_value({"score": 0.12345678901230001})
    same_at_profile = comparison._portable_golden_value({"score": 0.12345678901230002})
    meaningfully_different = comparison._portable_golden_value({"score": 0.1234567990123})

    assert left == same_at_profile
    assert left != meaningfully_different
