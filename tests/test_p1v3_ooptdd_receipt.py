from __future__ import annotations

from p1v3_ooptdd_receipt import run_gate


def test_p1v3_ooptdd_positive_and_ceiling_injection_share_locked_spec():
    positive = run_gate()
    negative = run_gate(inject_ceiling_environment=True)

    assert positive["status"] == negative["status"] == "green"
    assert positive["spec_sha256"] == negative["spec_sha256"]
    assert "development_headroom_gate_passed" in positive["events"]
    assert "ceiling_environment_rejected" in negative["events"]
    assert "ceiling_environment_authorized" not in negative["events"]
