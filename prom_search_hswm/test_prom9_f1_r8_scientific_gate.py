from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess

import pytest

import prom9_f1_r8_scientific_gate as gate


def _git_repo(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "gate@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "gate-test"], check=True)
    (path / "tracked.txt").write_text("bound\n")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "bound"], check=True)
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _prereg() -> dict[str, object]:
    return {
        "status": "DRAFT_NOT_REGISTERED",
        "metric": gate.EXPECTED_METRIC,
        "bootstrap": {
            "reps": 10000,
            "seed": 20260724,
            "unit": "component_cluster_macro",
            "minimum_clusters": 40,
        },
        "gates": {"expected_items": 100, "expected_arms": 5, "expected_calls": 1500},
        "predicted_outcome": {"operator": ">", "threshold": 0},
        "falsification_condition": {"operator": "<=", "threshold": 0},
        "symposium_commit": "FILL_FULL_SYMPOSIUM_COMMIT",
        "power_receipt_sha256": gate.ZERO_SHA256,
    }


def test_runtime_requires_features_used_by_the_r8_code() -> None:
    assert gate.runtime_check()["status"] == "PASS"


def test_repository_gate_requires_exact_clean_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    commit = _git_repo(repo)
    row, snapshot = gate.repository_check(repo, "test", commit)
    assert row["status"] == "PASS"
    assert gate.repository_stability_check(snapshot, "test")["status"] == "PASS"
    (repo / "untracked.txt").write_text("drift\n")
    row, _ = gate.repository_check(repo, "test", commit)
    assert row["status"] == "BLOCKED"


def test_runbook_refuses_retired_a2_identity(tmp_path: Path) -> None:
    runbook = tmp_path / "runbook.md"
    runbook.write_text("development=f1-2wiki-development-r8-try3-a2\n")
    assert gate.runbook_check(runbook)["status"] == "BLOCKED"
    runbook.write_text(f"development={gate.EXPECTED_RUN_ID}\n")
    assert gate.runbook_check(runbook)["status"] == "PASS"


def test_prereg_contract_is_valid_but_draft_blocks_confirmatory() -> None:
    rows = gate.preregistration_checks(_prereg())
    assert rows[0]["status"] == "PASS"
    assert rows[1]["status"] == "BLOCKED"
    assert rows[1]["observed"]["placeholder_paths"]


def test_prereg_rule_drift_is_blocked() -> None:
    value = _prereg()
    value["bootstrap"] = {**value["bootstrap"], "seed": 9}
    assert gate.preregistration_checks(value)[0]["status"] == "BLOCKED"


def test_incident_classification_is_not_a_hypothesis_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    import prom_search_hswm.prom9_f1_prior_exposure as prior

    monkeypatch.setattr(prior, "verify_aborted_attempt_exposure_receipt", lambda _value: "a" * 64)
    value = {
        "status": "ABORTED_QUARANTINED",
        "termination": {"signal": "SIGBUS", "exit_code": 135},
        "counts": {"item_runs": 0, "spool_complete_calls": 1, "spool_absent_calls": 1},
        "call_observations": [
            {"raw_attempt_state": "ACCEPTED", "response_status": 200, "spool_snapshot_state": "COMPLETE"},
            {"raw_attempt_state": "SENT", "response_status": None, "spool_snapshot_state": None},
        ],
    }
    rows, analysis = gate.incident_checks(value)
    assert [row["status"] for row in rows] == ["PASS", "PASS"]
    assert analysis["classification"] == "EXECUTION_ABORT__NOT_HYPOTHESIS_FALSIFICATION"
    assert analysis["scientific_interpretation"] == "NO_VALID_CONFIRMATORY_MEASUREMENT"


def test_incident_classification_accepts_latest_v4_count_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    import prom_search_hswm.prom9_f1_prior_exposure as prior

    monkeypatch.setattr(prior, "verify_aborted_attempt_exposure_receipt", lambda _value: "b" * 64)
    calls = [
        {"raw_attempt_state": "ACCEPTED", "response_status": 200, "spool_snapshot_state": "COMPLETE"}
        for _ in range(26)
    ] + [{"raw_attempt_state": "PREPARED", "response_status": None, "spool_snapshot_state": None}]
    value = {
        "status": "ABORTED_QUARANTINED",
        "termination": {"signal": "SIGBUS", "exit_code": 135},
        "counts": {"item_runs": 8, "spool_complete_calls": 26, "spool_absent_calls": 1},
        "call_observations": calls,
    }
    rows, analysis = gate.incident_checks(value)
    assert [row["status"] for row in rows] == ["PASS", "PASS"]
    assert analysis["complete_calls"] == 26
    assert analysis["nonterminal_without_response"] == 1


def test_receipt_hash_excludes_its_own_field() -> None:
    value = {"schema_version": "example/v1", "state": "BLOCKED"}
    value["receipt_sha256"] = gate.canonical_sha256(value)
    unsigned = copy.deepcopy(value)
    declared = unsigned.pop("receipt_sha256")
    assert declared == gate.canonical_sha256(unsigned)


def test_write_once_is_private_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    gate.write_once(str(output), {"ok": True})
    assert output.stat().st_mode & 0o777 == 0o600
    assert json.loads(output.read_text()) == {"ok": True}
    with pytest.raises(FileExistsError):
        gate.write_once(str(output), {"ok": False})
