from __future__ import annotations

import copy

import pytest

from hswm.experiments.f5v2 import judge


PACKET_A = "a" * 64
PACKET_B = "b" * 64
MANIFEST = "c" * 64


def _pass_receipt():
    return judge.build_dev_smoke_receipt(
        manifest_sha256=MANIFEST,
        citation_rows=[{"cited_packet_sha256s": [PACKET_A, PACKET_B]}],
        allowed_packet_sha256s=[PACKET_A, PACKET_B],
        canary_cases=[{"should_reject": True, "rejected": True} for _ in range(10)],
        drm_cases=[
            {
                "case_id": "drm-1",
                "supported_claims": ["explicit:a"],
                "proposed_claims": ["explicit:a"],
            }
        ],
        legacy_downscale_negative_reproduced=True,
        bitemporal_fired=True,
        query_leakage_count=0,
    )


def test_unknown_or_missing_packet_citation_fails_closed():
    with pytest.raises(judge.JudgeContractError, match="unknown packet"):
        judge.verify_packet_citations(
            [{"cited_packet_sha256s": ["f" * 64]}], [PACKET_A]
        )
    with pytest.raises(judge.JudgeContractError, match="no packet citations"):
        judge.verify_packet_citations([{"cited_packet_sha256s": []}], [PACKET_A])


def test_canary_threshold_is_preregistered_ninety_percent():
    cases = [{"should_reject": True, "rejected": i < 9} for i in range(10)]
    assert judge.adversarial_canary_catch_rate(cases)["passed"] is True
    cases[-2]["rejected"] = False
    assert judge.adversarial_canary_catch_rate(cases)["passed"] is False


def test_related_but_unstated_drm_lure_is_detected():
    result = judge.score_drm_lures(
        [
            {
                "case_id": "x",
                "supported_claims": ["robin", "sparrow"],
                "proposed_claims": ["robin", "bird-can-fly"],
            }
        ]
    )
    assert result["lure_count"] == 1
    assert result["rows"][0]["lures"] == ["bird-can-fly"]
    assert result["passed"] is False


def test_pass_receipt_has_all_sealing_teeth_and_verifies():
    receipt = _pass_receipt()
    assert receipt["status"] == "PASS_OFFLINE_INTEGRITY"
    assert all(receipt["gates"].values())
    judge.verify_dev_smoke_receipt(receipt)


def test_injected_negative_turns_receipt_fail_and_tamper_is_rejected():
    receipt = judge.build_dev_smoke_receipt(
        manifest_sha256=MANIFEST,
        citation_rows=[{"cited_packet_sha256s": [PACKET_A]}],
        allowed_packet_sha256s=[PACKET_A],
        canary_cases=[{"should_reject": True, "rejected": False}],
        drm_cases=[
            {
                "supported_claims": ["explicit"],
                "proposed_claims": ["unstated-lure"],
            }
        ],
        legacy_downscale_negative_reproduced=True,
        bitemporal_fired=True,
        query_leakage_count=1,
    )
    assert receipt["status"] == "FAIL"
    assert receipt["gates"]["canary_passed"] is False
    assert receipt["gates"]["drm_lure_passed"] is False
    assert receipt["gates"]["query_leakage_zero"] is False

    tampered = copy.deepcopy(_pass_receipt())
    tampered["gates"]["drm_lure_passed"] = False
    with pytest.raises(judge.JudgeContractError, match="digest mismatch"):
        judge.verify_dev_smoke_receipt(tampered)
