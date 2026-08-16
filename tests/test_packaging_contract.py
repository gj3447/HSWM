from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import tomllib

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _manifest_lines() -> list[str]:
    text = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _recursive_includes() -> dict[str, set[str]]:
    """directory -> glob patterns declared by `recursive-include <dir> <patterns...>`."""
    covered: dict[str, set[str]] = {}
    for line in _manifest_lines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "recursive-include":
            covered.setdefault(parts[1], set()).update(parts[2:])
    return covered


def _test_suite_import_roots() -> set[str]:
    """Top-level import names used by tests/ that are directories in this repo.

    These are exactly the directories an sdist must carry or the test suite cannot
    even be collected there. Computed rather than enumerated so future package
    additions are caught automatically.
    """
    roots: set[str] = set()
    for path in sorted((REPO_ROOT / "tests").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return {name for name in roots if (REPO_ROOT / name).is_dir()}


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
        "p1v3_policy_environment",
        "p1v3_calibration_gate",
        "p1v3_calibration_preflight",
        "p1v3_calibration_measure",
        "p1v3_heldout_preflight",
        "p1v3_heldout_measure",
        "p1v3_heldout_judge",
        "p1v3_prepare",
        "p1v4_replay_judge",
        "p1v4_replay_bundle",
        "p1v4_heldout_measure",
    } <= shipped

    assert {
        "f5v2_operators",
        "f5v2_topic_cache",
        "f5v2_judge",
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
    manifest = _manifest_lines()
    covered = _recursive_includes()

    assert "include *.json" in manifest
    assert "include *.py" in manifest
    assert "recursive-exclude prom_search_hswm/data *" in manifest
    assert "include prom_search_hswm/data/gold_badiou24.json" in manifest

    # Patterns are asserted as a subset so that widening a line (adding *.sh, say)
    # is not a test failure, while dropping a pattern still is.
    required: dict[str, set[str]] = {
        "receipts": {"*.py", "*.json"},
        "prom_search_hswm": {"*.py", "*.json", "*.md", "*.mmd"},
        "_research": {"*.py", "*.json", "*.md", "*.sh", "*.tsv"},
    }
    for directory, patterns in required.items():
        assert patterns <= covered.get(directory, set()), (
            f"MANIFEST.in dropped patterns for {directory}/: "
            f"missing {sorted(patterns - covered.get(directory, set()))}"
        )


def test_sdist_carries_every_directory_the_test_suite_imports() -> None:
    """Every repository package imported by tests must ship in the sdist."""
    import_roots = _test_suite_import_roots()

    # Guard against a vacuous pass: if the scanner silently stops finding anything,
    # this test must fail rather than green out.
    assert {"scripts"} <= import_roots, import_roots

    covered = _recursive_includes()
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packages = set(project["tool"]["setuptools"]["packages"])

    for directory in sorted(import_roots):
        assert "*.py" in covered.get(directory, set()), (
            f"tests/ imports from {directory}/ but MANIFEST.in has no "
            f"`recursive-include {directory} *.py` — it will be absent from the sdist"
        )
        if directory == "tests":
            continue
        assert directory in packages, (
            f"tests/ imports from {directory}/ but [tool.setuptools].packages does "
            f"not list it — it will be absent from the wheel"
        )


def test_sdist_carries_the_data_directories_the_tests_read() -> None:
    """Non-importable directories the suite reads by path. Import scanning cannot
    see these, so they are enumerated; each entry is a gap that was measured."""
    covered = _recursive_includes()
    required: dict[str, str] = {
        "research": "*.json",  # checked-in metric and runtime contracts
        "ontology": "*.json",  # repository and mathematical ontologies
        "schemas": "*.json",  # schemas loaded by contract validators
        "docs": "*.md",  # docs/research/ARTIFACT_LAYOUT.md
        "prereg": "*.json",
        "evidence": "*.json",
        "formal": "*.lean",
        "results": "*.md",
        "manifests": "*.json",
    }
    for directory, pattern in required.items():
        assert (REPO_ROOT / directory).is_dir(), directory
        assert pattern in covered.get(directory, set()), (
            f"MANIFEST.in does not ship {directory}/{pattern} into the sdist"
        )


def test_the_sdist_itself_is_checked_not_just_the_manifest_text():
    """★래칫이 실제로 래칫인가 — 산출물을 연다.

    형제 테스트들은 MANIFEST.in/pyproject.toml 의 **텍스트**만 파싱한다. 그래서
    MANIFEST.in 끝에 `prune scripts` 두 줄을 붙여도 전부 초록인데 빌드된 sdist 에는
    scripts/ 가 0개이고 수집오류 2건이 되살아난다(2026-08-05 적대검증 실측).
    텍스트를 읽는 계약은 계약이 아니라 주석이다.

    여기서는 실제로 빌드해서 tar 안을 본다. 빌드 도구가 없으면 **시끄럽게** 건너뛴다 —
    조용한 skip 은 통과와 구별되지 않는다.
    """
    import shutil
    import subprocess
    import tarfile
    import tempfile

    if shutil.which("uv") is None:
        pytest.skip("uv 없음 — 이 래칫은 실제 빌드를 요구한다. 커버리지 구멍이며 통과가 아니다")

    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(["uv", "build", "--sdist", "--out-dir", td],
                              cwd=root, capture_output=True, text=True, timeout=600)
        assert proc.returncode == 0, proc.stderr[-2000:]
        tarballs = list(Path(td).glob("*.tar.gz"))
        assert len(tarballs) == 1, tarballs
        with tarfile.open(tarballs[0]) as tar:
            names = tar.getnames()

    inner = [n.split("/", 1)[1] for n in names if "/" in n]
    scripts_py = [n for n in inner if n.startswith("scripts/") and n.endswith(".py")]
    assert scripts_py, "scripts/*.py 가 sdist 에 없다 — tests/ 가 그걸 import 한다"
    # 루트 *.sh 는 배포하지 않는다. 일부 운영 스크립트가 장비별 호스트명을
    # 포함할 수 있으므로 source distribution의 공용 표면에서 제외한다.
    root_sh = [n for n in inner if "/" not in n and n.endswith(".sh")]
    assert not root_sh, f"루트 셸 스크립트가 배포물에 실렸다(호스트명 유출): {root_sh}"
