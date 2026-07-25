from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "LONGINUS_HSWM_ORDERED_GATE_BINDING_2026-07-24.json"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_longinus_manifest_binds_all_seven_layers_and_keeps_claim_boundary() -> None:
    manifest = _manifest()

    assert manifest["schema"] == "longinus-hswm-ordered-gate-binding/v1"
    assert manifest["binding_state"] == "PIERCED"
    assert manifest["layers"] == [
        "KG_NODE",
        "CONTRACT_BINDING",
        "CODE_SYMBOL",
        "FILE_LINE",
        "LINE_RANGE",
        "SHA256",
        "CRATE_SCRIPT",
    ]
    assert manifest["active_gate"] == "F1_MULTI_LLM_FUNCTION_NETWORK"
    assert "does not establish" in str(manifest["claim_boundary"])


def test_every_longinus_binding_resolves_to_its_exact_hash_and_line_range() -> None:
    bindings = _manifest()["bindings"]
    assert isinstance(bindings, list)
    assert len(bindings) == 10

    for binding in bindings:
        assert isinstance(binding, dict)
        relative_path, separator, start_text = str(binding["sourcePath"]).rpartition(":")
        assert separator == ":"
        path = REPO_ROOT / relative_path
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == binding["sha256"]

        start, end = (int(value) for value in str(binding["lineRange"]).split("-", 1))
        line_count = len(payload.decode("utf-8").splitlines())
        expected_anchor = int(binding.get("anchorLine", start))
        assert int(start_text) == expected_anchor
        assert 1 <= start <= end <= line_count


def test_python_symbol_bindings_match_ast_spans_and_header_kg_refs() -> None:
    manifest = _manifest()
    bindings = manifest["bindings"]
    assert isinstance(bindings, list)
    symbol_bindings = {
        str(binding["sourceId"]).rsplit(".", 1)[-1]: binding
        for binding in bindings
        if isinstance(binding, dict) and binding["kind"] == "python_symbol"
    }
    source = (REPO_ROOT / "hswm_next_research_harness.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert set(symbol_bindings) == {
        "build_status",
        "verify_status",
        "build_lakatotree_packet",
    }
    lines = source.splitlines()
    for name, binding in symbol_bindings.items():
        node = functions[name]
        assert binding["lineRange"] == f"{node.lineno}-{node.end_lineno}"
        assert f"# KG: {binding['kg_ref']}" in lines[node.lineno - 1]
