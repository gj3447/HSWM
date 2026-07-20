"""Executable teeth for the fixed nine-gate H3/B3 preflight receipt."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

import h3_b3_preflight as pre
from world_ir import canonical_json, content_id


EXPECTED_NODEIDS = (
    "tests/test_claim_builder.py::"
    "test_shared_exact_claim_roles_create_topology_beyond_title_anchors",
    "tests/test_typed_composition.py::"
    "test_relation_mismatch_blocks_second_edge_but_untyped_control_does_not",
    "tests/test_h3_b3_end_to_end.py::"
    "test_b3_non_title_two_edge_chain_first_reaches_gold_at_depth_two",
    "tests/test_typed_composition.py::"
    "test_second_edge_target_shuffle_kills_the_depth_two_target",
    "tests/test_typed_composition.py::"
    "test_mu_zero_is_bit_identical_and_never_claims_composition",
    "tests/test_typed_composition.py::"
    "test_two_hop_typed_path_beats_matched_k1_and_preserves_full_receipt",
    "tests/test_typed_composition.py::"
    "test_two_claims_in_one_paragraph_cannot_illegally_switch_claim_identity",
    "tests/test_typed_composition.py::"
    "test_target_predicate_and_role_cannot_look_ahead_to_score_current_hop",
    "tests/test_typed_composition.py::"
    "test_fanout_and_join_hub_gates_fail_closed",
)
EXPECTED_IMPLEMENTATION_MODULES = (
    "h3_b3_falsifier.py", "h3_arc_adjudicator.py",
    "h3_artifact_lifecycle.py", "h3_b3_preflight.py",
    "model_deployment_receipt.py", "bge_m3_embed.py",
    "recorded_llm_extractor.py", "h3_fresh_manifest.py",
    "h3_b3_prepare.py", "claim_builder.py", "typed_composition.py",
    "title_anchor_builder.py", "composition.py", "relation_eval.py",
    "metrics.py", "world_ir.py",
)


def _reseal(value: dict) -> dict:
    payload = {
        key: value[key]
        for key in (
            "schema_version", "cwd", "pytest_disable_plugin_autoload",
            "python_executable", "gate_mapping_sha256", "gate_count",
            "implementation_modules", "implementation_code_root_sha256",
            "all_passed", "gates",
        )
    }
    digest = pre._sha256_text(canonical_json(payload))
    value["receipt_sha256"] = digest
    value["receipt_id"] = content_id("h3_b3_preflight_receipt", {
        "receipt_sha256": digest,
        "gate_mapping_sha256": value["gate_mapping_sha256"],
        "implementation_code_root_sha256": value[
            "implementation_code_root_sha256"
        ],
    })
    return value


@pytest.fixture(scope="module")
def actual_receipt(tmp_path_factory: pytest.TempPathFactory):
    path = tmp_path_factory.mktemp("h3-preflight") / "receipt.json"
    receipt = pre.run_preflight(path)
    return path, receipt


def test_mapping_is_exactly_the_preregistered_nine_nodes():
    assert tuple(item[0] for item in pre.GATE_NODEIDS) == tuple(range(1, 10))
    assert tuple(item[2] for item in pre.GATE_NODEIDS) == EXPECTED_NODEIDS
    assert len({item[1] for item in pre.GATE_NODEIDS}) == 9
    assert len({item[2] for item in pre.GATE_NODEIDS}) == 9
    assert pre.FROZEN_IMPLEMENTATION_MODULE_PATHS == EXPECTED_IMPLEMENTATION_MODULES


def test_actual_preflight_runs_fixed_nodes_and_round_trips_first_write(actual_receipt):
    path, receipt = actual_receipt
    assert receipt.gate_count == 9
    assert receipt.all_passed
    assert all(item.passed and item.returncode == 0 for item in receipt.gates)
    assert all("1 passed" in item.stdout for item in receipt.gates)
    assert all(len(item.ast_span_sha256) == 64 for item in receipt.gates)
    assert all(item.command[-1] == item.nodeid for item in receipt.gates)
    assert tuple(item.path for item in receipt.implementation_modules) == (
        EXPECTED_IMPLEMENTATION_MODULES
    )
    assert receipt.implementation_code_root_sha256 == (
        pre.lifecycle.authorization_code_root({
            item.path: item.sha256 for item in receipt.implementation_modules
        })
    )
    assert pre.load_preflight_receipt(path) == receipt
    assert path.read_text(encoding="utf-8") == canonical_json(receipt) + "\n"

    with pytest.raises(pre.PreflightError, match="already exists"):
        pre.run_preflight(path)


def test_loader_rejects_self_consistent_favorable_node_or_ast_substitution(
    actual_receipt, tmp_path: Path,
):
    _path, receipt = actual_receipt
    value = json.loads(canonical_json(receipt))
    value["gates"][0]["nodeid"] = EXPECTED_NODEIDS[1]
    value["gates"][0]["command"][-1] = EXPECTED_NODEIDS[1]
    value["gates"][0]["result_sha256"] = pre._result_sha256(
        nodeid=EXPECTED_NODEIDS[1],
        stdout_sha256=value["gates"][0]["stdout_sha256"],
        stderr_sha256=value["gates"][0]["stderr_sha256"],
        returncode=0,
        passed=True,
    )
    _reseal(value)
    target = tmp_path / "favorable-node.json"
    target.write_text(canonical_json(value) + "\n", encoding="utf-8")
    with pytest.raises(pre.PreflightError, match="frozen node mapping"):
        pre.load_preflight_receipt(target)

    value = json.loads(canonical_json(receipt))
    value["gates"][0]["ast_span_sha256"] = "0" * 64
    _reseal(value)
    target = tmp_path / "forged-span.json"
    target.write_text(canonical_json(value) + "\n", encoding="utf-8")
    with pytest.raises(pre.PreflightError, match="AST span mismatch"):
        pre.load_preflight_receipt(target)


def test_failed_gate_receipt_is_written_but_never_loader_admissible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    original = pre._run_gate

    def fail_gate(gate: int, gate_name: str, nodeid: str):
        result = original(gate, gate_name, nodeid)
        if gate != 4:
            return result
        failed = replace(
            result, returncode=1, passed=False, result_sha256="",
        )
        return replace(failed, result_sha256=pre._result_sha256(
            nodeid=nodeid,
            stdout_sha256=failed.stdout_sha256,
            stderr_sha256=failed.stderr_sha256,
            returncode=1,
            passed=False,
        ))

    monkeypatch.setattr(pre, "_run_gate", fail_gate)
    path = tmp_path / "failed.json"
    receipt = pre.run_preflight(path)
    assert path.exists()
    assert receipt.all_passed is False
    assert receipt.gates[3].passed is False
    with pytest.raises(pre.PreflightError, match="root policy mismatch"):
        pre.load_preflight_receipt(path)


def test_loader_rejects_implementation_file_change_after_preflight(
    actual_receipt, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """A passing test receipt cannot survive a later kernel implementation edit."""

    original_root = pre.REPO_ROOT
    isolated_root = tmp_path / "isolated-repository"
    isolated_root.mkdir()
    required_paths = set(pre.FROZEN_IMPLEMENTATION_MODULE_PATHS)
    required_paths.update(pre._node_parts(item[2])[0] for item in pre.GATE_NODEIDS)
    for relative in sorted(required_paths):
        source = original_root / relative
        target = isolated_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    _path, prior = actual_receipt
    monkeypatch.setattr(pre, "REPO_ROOT", isolated_root)
    modules = pre.implementation_snapshot()
    isolated_receipt = pre._seal_receipt(prior.gates, modules)
    receipt_path = tmp_path / "isolated-preflight.json"
    pre._write_first(receipt_path, isolated_receipt)
    assert pre.load_preflight_receipt(receipt_path) == isolated_receipt

    implementation = isolated_root / "claim_builder.py"
    implementation.write_bytes(implementation.read_bytes() + b"\n# post-gate drift\n")
    with pytest.raises(pre.PreflightError, match="implementation code drift"):
        pre.load_preflight_receipt(receipt_path)


def test_cli_has_no_node_override_surface(tmp_path: Path):
    with pytest.raises(SystemExit):
        pre.main([
            "--output", str(tmp_path / "receipt.json"),
            "--nodeid", EXPECTED_NODEIDS[0],
        ])
