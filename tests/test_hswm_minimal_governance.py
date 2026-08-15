from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "research" / "HSWM_MINIMAL_GOVERNANCE.v1.json"


def test_minimal_governance_binds_user_source_and_small_default_path():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = ROOT / data["authority"]["source"]

    assert hashlib.sha256(source.read_bytes()).hexdigest() == data["authority"][
        "source_sha256"
    ]
    assert data["status"] == "ACTIVE_DEFAULT"
    assert data["default_path"] == [
        "IMPLEMENT_OR_RUN",
        "DIRECT_MEASUREMENT",
        "ONE_CONTENT_ADDRESSED_RECEIPT_IF_RESULT_IS_MATERIAL",
        "COMMIT_AND_PUSH",
    ]
    assert data["budgets"] == {
        "material_result_receipts": 1,
        "optional_governance_layers_without_explicit_escalation": 1,
    }


def test_complex_governance_is_optional_and_causal_evidence_is_one_receipt():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert data["optional_layers"]["lakatotree"]["default"] == "OFF"
    assert data["optional_layers"]["ooptdd"]["default"] == "LEGACY_OPTIONAL_AUDIT"
    assert data["optional_layers"]["omd"]["default"] == "OFF"
    assert data["optional_layers"]["mcp"]["default"] == "OPTIONAL_IO_ADAPTER"
    assert data["causal_learning_receipt"]["count"] == 1
    assert data["causal_learning_receipt"]["field"] == "causal_test_receipt_sha256"
    assert set(data["causal_learning_receipt"]["must_attest"]) == {
        "fixed-context replay",
        "matched compute or token budget",
        "removal ablation",
    }
