from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from hswm.infrastructure import graph_standard_tooling as tooling


def _lock() -> dict[str, object]:
    return tooling.load_acceptance_lock()


def _copy_lock_bound_files(lock: dict[str, object], destination: Path) -> None:
    relative_paths = {
        lock["runtime_lock"]["package_manifest"],
        lock["runtime_lock"]["package_lock"],
        *(profile["runner"] for profile in lock["qualification_profiles"] if "runner" in profile),
        *(record["path"] for record in lock["qualification_receipts"]),
    }
    for relative in relative_paths:
        source = tooling.REPOSITORY_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_checked_in_acceptance_lock_and_package_integrities_are_exact() -> None:
    indexes = tooling.verify_acceptance_lock(_lock())

    assert set(indexes["adapters"]) == {
        "n3-nquads-parser",
        "rdf-canonize-rdfc10",
    }
    assert {
        identifier
        for identifier, profile in indexes["profiles"].items()
        if profile["status"] in tooling._RUNNABLE
    } == {
        "rdf11-nquads-n3",
        "rdf12-nquads-n3-experimental",
        "rdfc10-rdf-canonize",
    }


def test_draft_standard_cannot_enter_the_stable_lane() -> None:
    lock = deepcopy(_lock())
    rdf12 = next(item for item in lock["standards"] if item["id"] == "rdf-1.2-n-quads")
    rdf12["lane"] = "stable"

    with pytest.raises(tooling.GraphStandardToolingError, match="draft standard"):
        tooling.verify_acceptance_lock(lock)


def test_registry_cannot_auto_install_or_auto_trust() -> None:
    lock = deepcopy(_lock())
    lock["mcp"]["registry"]["auto_install"] = True

    with pytest.raises(tooling.GraphStandardToolingError, match="Registry boundary"):
        tooling.verify_acceptance_lock(lock)


def test_mcp_and_skill_roles_cannot_collapse_into_one_boundary() -> None:
    lock = deepcopy(_lock())
    lock["policy"]["skill_role"] = lock["policy"]["mcp_role"]

    with pytest.raises(tooling.GraphStandardToolingError, match="not fail-closed"):
        tooling.verify_acceptance_lock(lock)


def test_uninstalled_official_mcp_sdk_metadata_still_has_complete_package_pins() -> None:
    lock = deepcopy(_lock())
    del lock["mcp"]["new_typescript_sdk"]["npm_integrities"][
        "@modelcontextprotocol/client"
    ]

    with pytest.raises(tooling.GraphStandardToolingError, match="pin coverage drift"):
        tooling.verify_acceptance_lock(lock)


def test_every_runnable_qualification_requires_one_receipt() -> None:
    lock = deepcopy(_lock())
    lock["qualification_receipts"] = lock["qualification_receipts"][1:]

    with pytest.raises(tooling.GraphStandardToolingError, match="receipt coverage drift"):
        tooling.verify_acceptance_lock(lock)


def test_malformed_receipt_result_is_refused_as_boundary_drift(tmp_path: Path) -> None:
    lock = deepcopy(_lock())
    _copy_lock_bound_files(lock, tmp_path)
    source_receipt = tmp_path / lock["qualification_receipts"][0]["path"]
    receipt = json.loads(source_receipt.read_bytes())
    receipt["result"] = "PASS"
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    receipt["receipt_sha256"] = sha256(tooling._canonical_json_bytes(unsigned)).hexdigest()
    receipt_path = tmp_path / "malformed-receipt.json"
    receipt_path.write_bytes(tooling._pretty_json_bytes(receipt))
    lock["qualification_receipts"][0]["path"] = str(receipt_path.relative_to(tmp_path))
    lock["qualification_receipts"][0]["receipt_sha256"] = receipt["receipt_sha256"]

    with pytest.raises(tooling.GraphStandardToolingError, match="result must be an object"):
        tooling.verify_acceptance_lock(lock, repository_root=tmp_path)


def test_adapter_package_integrity_drift_is_refused() -> None:
    lock = deepcopy(_lock())
    lock["tool_adapters"][0]["npm_integrity"] = "sha512-not-the-lock-value"

    with pytest.raises(tooling.GraphStandardToolingError, match="package lock drift"):
        tooling.verify_acceptance_lock(lock)


def _git(arguments: list[str], *, cwd: Path, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_source_checkout_verification_binds_commit_tree_archive_manifest_and_license(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "suite"
    checkout.mkdir()
    _git(["init", "--quiet"], cwd=checkout)
    _git(["config", "user.email", "test@invalid.example"], cwd=checkout)
    _git(["config", "user.name", "HSWM test"], cwd=checkout)
    selected = checkout / "tests"
    selected.mkdir()
    manifest = selected / "manifest.json"
    vector = selected / "vector.nq"
    license_path = checkout / "LICENSE.md"
    manifest.write_text('{"tests":[]}\n', encoding="utf-8")
    vector.write_text('<urn:s> <urn:p> <urn:o> .\n', encoding="utf-8")
    license_path.write_text("test-only license fixture\n", encoding="utf-8")
    _git(["add", "LICENSE.md", "tests/manifest.json", "tests/vector.nq"], cwd=checkout)
    _git(["commit", "--quiet", "-m", "fixture"], cwd=checkout)
    commit = _git(["rev-parse", "HEAD"], cwd=checkout)
    tree = _git(["rev-parse", "HEAD:tests"], cwd=checkout)
    archive = _git(["archive", "--format=tar", commit, "--", "tests"], cwd=checkout, binary=True)
    source = {
        "commit": commit,
        "git_archive_sha256": sha256(archive).hexdigest(),
        "git_tree_sha1": tree,
        "license_path": "LICENSE.md",
        "license_sha256": sha256(license_path.read_bytes()).hexdigest(),
        "manifest_path": "tests/manifest.json",
        "manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
        "selected_path": "tests",
    }

    observed = tooling.verify_source_checkout(source, checkout)
    assert observed["commit"] == commit
    assert observed["tree_sha1"] == tree

    vector.write_text('<urn:changed> <urn:p> <urn:o> .\n', encoding="utf-8")
    with pytest.raises(tooling.GraphStandardToolingError, match="selected tree is dirty"):
        tooling.verify_source_checkout(source, checkout)


def test_materializer_refuses_an_existing_destination(tmp_path: Path) -> None:
    source = tooling.verify_acceptance_lock(_lock())["sources"][
        "w3c-rdf-tests-rdf11-nquads"
    ]
    destination = tmp_path / "already-there"
    destination.mkdir()

    with pytest.raises(tooling.GraphStandardToolingError, match="must not exist"):
        tooling.materialize_source(source, destination)


def test_project_skill_no_longer_requires_the_retired_fixed_decomposition() -> None:
    skill = (
        tooling.REPOSITORY_ROOT
        / ".agents/skills/hswm-research-readout/SKILL.md"
    ).read_text(encoding="utf-8")

    assert "mapping to `H/W/A/F/Π`" not in skill
    assert "schema-relative" in skill
    assert "canonical atom" in skill


def test_qualification_receipt_hash_contract_is_canonical() -> None:
    unsigned = {"schema_version": tooling.RECEIPT_SCHEMA, "value": [2, 1]}
    first = sha256(tooling._canonical_json_bytes(unsigned)).hexdigest()
    reordered = {"value": [2, 1], "schema_version": tooling.RECEIPT_SCHEMA}
    second = sha256(tooling._canonical_json_bytes(reordered)).hexdigest()

    assert first == second
    assert json.loads(tooling._pretty_json_bytes({**unsigned, "receipt_sha256": first}))[
        "receipt_sha256"
    ] == first
