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
        "personal_governance_layers": 0,
    }


def test_personal_governance_is_deleted_and_causal_evidence_is_one_receipt():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))

    removed = data["removed_personal_governance"]
    assert removed["status"] == "DELETED"
    assert removed["restoration_allowed"] is False
    assert removed["historical_verdict_authority"] == "NONE"
    assert "tests and packaging hooks" in removed["removed_surfaces"]
    assert "ordered-gate and research-ledger integrations" in removed["removed_surfaces"]

    mcp = data["mcp"]
    assert mcp["default"] == "EXTERNAL_BOUNDED_ONTOLOGY_ADAPTER"
    assert mcp["provider"] == "Google MCP Toolbox 1.9.0"
    assert mcp["normal_read_tools"] == [
        "ontology_contract_get",
        "ontology_search",
        "ontology_get",
        "ontology_neighbors",
        "ontology_claim_history",
        "ontology_drift_report",
    ]
    assert {"raw Cypher", "canonical write", "ratification"} <= set(mcp["forbidden"])
    assert "PENDING-only" in mcp["cross_repo_pending_exception"]
    assert data["causal_learning_receipt"]["count"] == 1
    assert data["causal_learning_receipt"]["field"] == "causal_test_receipt_sha256"
    assert set(data["causal_learning_receipt"]["must_attest"]) == {
        "fixed-context replay",
        "matched compute or token budget",
        "removal ablation",
    }
