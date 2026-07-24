from __future__ import annotations

from copy import deepcopy

import pytest

from hswm_weight_snapshot import canonical_sha256
from p1v4_heldout_measure import (
    P1V4HeldoutMeasurementError,
    build_p1v4_evidence,
    compatible_p1v3_preregistration,
)


def _inner_evidence():
    value = {
        "schema_version": "hswm-p1v3-policy-heldout-evidence/v1",
        "branch": "p1v3-nonredundant-policy-actuation",
        "conjecture": "old seed-3 wording",
        "preregistration_sha256": "1" * 64,
        "observations": [{"case_id": "fresh-seed5-r2-case"}],
        "scientific_judgment_emitted": False,
    }
    value["evidence_sha256"] = canonical_sha256(value)
    return value


def test_compatibility_preregistration_is_resealed_for_frozen_kernel():
    outer = {
        "schema_version": "hswm-p1v4-preregistration/v1",
        "registration_state": "SERVER_REGISTERED_FROZEN_UNRUN",
    }
    outer["preregistration_sha256"] = canonical_sha256(outer)

    compat = compatible_p1v3_preregistration(outer)
    unsigned = dict(compat)
    declared = unsigned.pop("preregistration_sha256")

    assert compat["schema_version"] == "hswm-p1v3-preregistration/v1"
    assert declared == canonical_sha256(unsigned)


def test_evidence_bridge_replaces_seed3_claim_and_preserves_inner_binding():
    inner = _inner_evidence()
    bridged = build_p1v4_evidence(
        inner_evidence=inner,
        preregistration_sha256="2" * 64,
        wrapper_command=("python", "p1v4_heldout_measure.py"),
        wrapper_sha256="3" * 64,
    )
    unsigned = dict(bridged)
    declared = unsigned.pop("evidence_sha256")

    assert bridged["schema_version"] == "hswm-p1v4-policy-heldout-evidence/v1"
    assert "seed-5 R2" in bridged["conjecture"]
    assert "seed-3" not in bridged["conjecture"]
    assert bridged["preregistration_sha256"] == "2" * 64
    assert bridged["compatibility_execution"]["inner_evidence_sha256"] == (
        inner["evidence_sha256"]
    )
    assert declared == canonical_sha256(unsigned)


def test_evidence_bridge_rejects_measurement_self_judgment():
    inner = deepcopy(_inner_evidence())
    inner["verdict"] = "PASS"
    unsigned = dict(inner)
    unsigned.pop("evidence_sha256")
    inner["evidence_sha256"] = canonical_sha256(unsigned)

    with pytest.raises(P1V4HeldoutMeasurementError, match="verdict key"):
        build_p1v4_evidence(
            inner_evidence=inner,
            preregistration_sha256="2" * 64,
            wrapper_command=("python", "p1v4_heldout_measure.py"),
            wrapper_sha256="3" * 64,
        )
