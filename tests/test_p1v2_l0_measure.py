from __future__ import annotations

from pathlib import Path

import pytest

from p1v2_l0_measure import (
    FROZEN_OUTCOME_MODULES,
    L0MeasurementError,
    preregistration_guard,
)


def test_measurement_guard_refuses_local_draft_before_any_model_call():
    prereg = {
        "schema": "hswm-preregistration/v1",
        "registration_state": "LOCAL_DRAFT_UNREGISTERED_MEASUREMENT_FORBIDDEN",
        "registered_before_measurement": False,
    }
    with pytest.raises(L0MeasurementError, match="server registration"):
        preregistration_guard(
            prereg,
            here=Path(__file__).resolve().parents[1],
            public={"public_manifest_sha256": "1" * 64},
            budget={"budget_manifest_sha256": "2" * 64},
            deployment_file_sha256="3" * 64,
            prediction_receipt_file_sha256="4" * 64,
        )


def test_measurement_module_cut_includes_runner_and_excludes_judge():
    assert "p1v2_l0_measure.py" in FROZEN_OUTCOME_MODULES
    assert "p1v2_l0_judge.py" not in FROZEN_OUTCOME_MODULES
