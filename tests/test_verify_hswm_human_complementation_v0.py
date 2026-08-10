"""Tests for the HSWM human-complementation v0 artifact verifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "verification/verify_hswm_human_complementation_v0.py"
SPEC = importlib.util.spec_from_file_location("verify_hswm_human_complementation_v0", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_artifact_set_verifies() -> None:
    result = MODULE.verify()
    assert result["status"] == "PASS"
    assert result["metric"] == 1.0
    assert result["negative_rejected"] is True


def test_authority_escalation_is_rejected() -> None:
    text = MODULE.BENCHMARK.read_text(encoding="utf-8")
    mutated = text.replace(
        "measurement_authorized**: `false`",
        "measurement_authorized**: `true`",
        1,
    )
    with pytest.raises(MODULE.VerificationError):
        MODULE.check_benchmark_text(mutated)


def test_missing_charter_clause_is_rejected() -> None:
    text = MODULE.CHARTER.read_text(encoding="utf-8")
    mutated = text.replace("### HC-12 —", "### HC-X12 —", 1)
    with pytest.raises(MODULE.VerificationError):
        MODULE.check_charter_text(mutated)
