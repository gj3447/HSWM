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
    assert data["optional_layers"]["omd"] == {
        "default": "RETIRED_HISTORICAL_READ_ONLY",
        "activation_allowed": False,
        "forbidden_actions": [
            "MCP registration or invocation",
            "coordination database writes",
            "declare, claim, heartbeat, release, or cancel leases",
            "health, heal, or conditional reactivation",
        ],
    }
    mcp = data["optional_layers"]["mcp"]
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


def test_observed_mcp_surface_has_no_personal_or_raw_cypher_server():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    observed = data["observed_mcp_state_2026_08_15"]

    assert observed["dev_01_claude"] == ["ontology"]
    assert observed["dev_01_codex"] == ["ontology"]
    assert observed["provider"] == "Google MCP Toolbox 1.9.0"
    assert observed["codex_normal_enabled_tools"] == 6
    assert observed["claude_server_tools"] == 7
    assert observed["raw_cypher_tools"] == 0
    assert observed["canonical_write_tools"] == 0
