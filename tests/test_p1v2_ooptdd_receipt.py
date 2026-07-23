from __future__ import annotations

from p1v2_ooptdd_receipt import run_gate


def test_ooptdd_positive_and_injected_negative_hit_the_same_locked_spec():
    positive = run_gate()
    negative = run_gate(inject_scientific_verdict=True)

    assert positive["status"] == "green"
    assert negative["status"] == "green"
    assert positive["spec_sha256"] == negative["spec_sha256"]
    assert "verdict_free_evidence_verified" in positive["events"]
    assert "scientific_self_verdict_rejected" in negative["events"]
    assert "scientific_self_verdict_accepted" not in negative["events"]
