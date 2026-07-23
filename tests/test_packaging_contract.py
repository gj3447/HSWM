from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_h3_runtime_and_entry_modules_are_shipped_in_the_wheel() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    shipped = set(project["tool"]["setuptools"]["py-modules"])

    assert {
        "h3_artifact_lifecycle",
        "h3_b3_falsifier",
        "h3_b3_manifest",
        "h3_b3_preflight",
        "h3_title_anchor_falsifier",
    } <= shipped

    assert {
        "qkv_routing",
        "qkv_routing_falsifier",
        "qkv_b1_probe",
        "qkv_b1_development_falsifier",
    } <= shipped

    assert {
        "p1v2_typed_lesson",
        "p1v2_prompt_parity",
        "p1v2_tokenizer_adapter",
        "p1v2_l0_harness",
        "p1v2_llm_answerer",
        "p1v2_l0_prepare",
        "p1v2_type6_environment",
        "p1v2_l0_preflight",
        "p1v2_l0_measure",
        "p1v2_l0_judge",
        "p1v2_l0_judge_fixtures",
        "p1v2_l0_refreeze",
        "p1v2_l0_diagnose",
        "p1v2_ooptdd_receipt",
        "p1v3_policy_environment",
        "p1v3_calibration_gate",
        "p1v3_ooptdd_receipt",
    } <= shipped


def test_default_pytest_surface_includes_public_research() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["tool"]["pytest"]["ini_options"]["testpaths"] == [
        "tests",
        "prom_search_hswm",
        "_research/shared_field_hypothesis",
    ]


def test_required_prom_fixture_is_content_addressed() -> None:
    fixture = REPO_ROOT / "prom_search_hswm" / "data" / "gold_badiou24.json"
    payload = fixture.read_bytes()

    assert hashlib.sha256(payload).hexdigest() == (
        "7eeac9e6915d645e846014db3e6d1798645f9c7ff90af7d94eb97576e0516489"
    )
    decoded = json.loads(payload)
    assert len(decoded["findings"]) == 24
    assert decoded["provenance"].startswith("Neo4j home canon 0.25")


def test_source_distribution_carries_the_default_test_surface() -> None:
    manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()

    assert "include *.json" in manifest
    assert "include *.py" in manifest
    assert "recursive-include prom_search_hswm *.py *.json *.md *.mmd" in manifest
    assert "recursive-exclude prom_search_hswm/data *" in manifest
    assert "include prom_search_hswm/data/gold_badiou24.json" in manifest
    assert "recursive-include _research/shared_field_hypothesis *.py *.json *.md" in manifest
