#!/usr/bin/env python3
"""Fail-closed, zero-model-call readiness harness for HSWM F1 r8/try3.

The harness diagnoses authority, incident, test, and preregistration state.  It
never starts the model server, sends a model request, registers a prediction,
opens evaluator gold, or submits a scientific verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "hswm-prom9-f1-r8-scientific-gate-harness/v1"
RECEIPT_SCHEMA = "hswm-prom9-f1-r8-scientific-gate-receipt/v1"
EXPECTED_RUN_ID = "f1-2wiki-development-r8-try3-a3"
EXPECTED_METRIC = "f1_min_paired_component_cluster_bootstrap_lcb"
ZERO_SHA256 = "0" * 64
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
FULL_TEST_FILES = (
    "prom_search_hswm/test_prom9_f1_prior_exposure.py",
    "prom_search_hswm/test_prom9_f1_r8_environment.py",
    "prom_search_hswm/test_prom9_f1_r8_lock.py",
    "prom_search_hswm/test_prom9_f1_r8_runner.py",
    "prom_search_hswm/test_prom9_f1_r8_power.py",
    "prom_search_hswm/test_prom9_f1_r8_source.py",
    "prom_search_hswm/test_prom9_f1_r8_scientific_gate.py",
)

# Direct execution (``python prom_search_hswm/...py``) otherwise exposes only
# the package directory.  Bind imports to this checkout's repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


class GateRefusal(RuntimeError):
    """Raised when an input cannot be treated as authority."""


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise GateRefusal(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, label: str) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, GateRefusal) as error:
        raise GateRefusal(f"cannot read canonical {label}") from error
    if not isinstance(value, dict):
        raise GateRefusal(f"{label} is not an object")
    return value


def check(
    check_id: str,
    status: str,
    *,
    observed: object,
    expected: object,
    remediation: str,
    blocking: bool = True,
) -> dict[str, object]:
    if status not in {"PASS", "BLOCKED", "NOT_RUN"}:
        raise GateRefusal("invalid check status")
    return {
        "check_id": check_id,
        "status": status,
        "blocking": blocking,
        "observed": observed,
        "expected": expected,
        "remediation": remediation,
    }


def runtime_check() -> dict[str, object]:
    features: dict[str, bool] = {}
    features["path_stat_follow_symlinks"] = "follow_symlinks" in inspect.signature(Path.stat).parameters
    try:
        features["zip_strict"] = list(zip([1], [2], strict=True)) == [(1, 2)]
    except TypeError:
        features["zip_strict"] = False
    passed = sys.version_info >= (3, 11) and all(features.values())
    return check(
        "runtime.python_features",
        "PASS" if passed else "BLOCKED",
        observed={
            "executable": str(Path(sys.executable).resolve()),
            "version": list(sys.version_info[:3]),
            "features": features,
        },
        expected={"minimum_version": [3, 11], "all_features": True},
        remediation="run with the frozen HSWM/Dell venv; never use macOS /usr/bin/python3",
    )


def _git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise GateRefusal(f"cannot inspect Git repository: {repo}") from error
    return result.stdout.strip()


def repository_check(repo: Path, label: str, expected_commit: str | None) -> tuple[dict[str, object], dict[str, object]]:
    resolved = repo.resolve(strict=True)
    head = _git(resolved, "rev-parse", "--verify", "HEAD^{commit}")
    dirty_lines = _git(resolved, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    commit_ok = expected_commit is not None and COMMIT_RE.fullmatch(expected_commit) is not None and head == expected_commit
    clean = not dirty_lines
    status = "PASS" if commit_ok and clean else "BLOCKED"
    row = check(
        f"authority.{label}_repository",
        status,
        observed={"path": str(resolved), "head": head, "dirty_entry_count": len(dirty_lines)},
        expected={"head": expected_commit, "dirty_entry_count": 0, "detached_snapshot_recommended": True},
        remediation=f"create a clean detached {label} snapshot at an explicit full commit and rerun",
    )
    return row, {"path": str(resolved), "head_before": head, "dirty_entry_count_before": len(dirty_lines)}


def repository_stability_check(snapshot: Mapping[str, object], label: str) -> dict[str, object]:
    repo = Path(str(snapshot["path"]))
    head_after = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    dirty_after = _git(repo, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    stable = head_after == snapshot["head_before"] and len(dirty_after) == snapshot["dirty_entry_count_before"] == 0
    return check(
        f"authority.{label}_stable_during_audit",
        "PASS" if stable else "BLOCKED",
        observed={"head_before": snapshot["head_before"], "head_after": head_after, "dirty_entry_count_after": len(dirty_after)},
        expected={"head_unchanged": True, "dirty_entry_count_after": 0},
        remediation="discard this audit receipt and rerun in an immutable detached snapshot",
    )


def runbook_check(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    count = text.count(EXPECTED_RUN_ID)
    return check(
        "contract.runbook_a3_successor",
        "PASS" if count > 0 else "BLOCKED",
        observed={"path": str(path.resolve()), "expected_run_id_occurrences": count},
        expected={"development_run_id": EXPECTED_RUN_ID, "occurrences_minimum": 1},
        remediation="rebind the runbook, roots, lock, and examples from the retired a2 identity to the A3 successor before any call",
    )


def _placeholder_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(_placeholder_paths(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_placeholder_paths(child, f"{path}[{index}]"))
    elif isinstance(value, str) and ("FILL_" in value or value == ZERO_SHA256):
        found.append(path)
    return found


def preregistration_checks(value: Mapping[str, object]) -> list[dict[str, object]]:
    bootstrap = value.get("bootstrap")
    gates = value.get("gates")
    predicted = value.get("predicted_outcome")
    falsifier = value.get("falsification_condition")
    contract_ok = (
        value.get("metric") == EXPECTED_METRIC
        and isinstance(bootstrap, Mapping)
        and bootstrap.get("reps") == 10000
        and bootstrap.get("seed") == 20260724
        and bootstrap.get("unit") == "component_cluster_macro"
        and bootstrap.get("minimum_clusters") == 40
        and isinstance(gates, Mapping)
        and gates.get("expected_items") == 100
        and gates.get("expected_arms") == 5
        and gates.get("expected_calls") == 1500
        and isinstance(predicted, Mapping)
        and predicted.get("operator") == ">"
        and predicted.get("threshold") == 0
        and isinstance(falsifier, Mapping)
        and falsifier.get("operator") == "<="
        and falsifier.get("threshold") == 0
    )
    placeholders = _placeholder_paths(value)
    registered = value.get("status") not in {"DRAFT_NOT_REGISTERED", "DRAFT"} and not placeholders
    return [
        check(
            "contract.scientific_success_rule",
            "PASS" if contract_ok else "BLOCKED",
            observed={"metric": value.get("metric"), "bootstrap": bootstrap, "gates": gates},
            expected={"metric": EXPECTED_METRIC, "success": "min(four paired cluster bootstrap LCBs) > 0"},
            remediation="restore the frozen four-control LCB contract before development or preregistration",
        ),
        check(
            "confirmatory.external_preregistration_exact_readback",
            "PASS" if registered else "BLOCKED",
            observed={"status": value.get("status"), "placeholder_paths": placeholders},
            expected={"status": "REGISTERED_EXACT_READBACK", "placeholder_paths": []},
            remediation="after development power, freeze all hashes, register externally, and preserve exact server readback before sealed calls",
        ),
    ]


def incident_checks(value: Mapping[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    try:
        from prom_search_hswm.prom9_f1_prior_exposure import verify_aborted_attempt_exposure_receipt

        verified_sha = verify_aborted_attempt_exposure_receipt(value)
        verified = True
        verify_error = None
    except Exception as error:  # fail closed without leaking a large traceback into the receipt
        verified_sha = None
        verified = False
        verify_error = type(error).__name__
    termination = value.get("termination") if isinstance(value.get("termination"), Mapping) else {}
    counts = value.get("counts") if isinstance(value.get("counts"), Mapping) else {}
    calls = value.get("call_observations") if isinstance(value.get("call_observations"), list) else []
    completed = sum(isinstance(row, Mapping) and row.get("spool_snapshot_state") == "COMPLETE" for row in calls)
    nonterminal_without_response = sum(
        isinstance(row, Mapping)
        and row.get("raw_attempt_state") in {"PREPARED", "SENT"}
        and row.get("response_status") is None
        for row in calls
    )
    declared_complete = counts.get("spool_complete_calls")
    declared_absent = counts.get("spool_absent_calls")
    observed_incident = (
        value.get("status") == "ABORTED_QUARANTINED"
        and termination.get("signal") == "SIGBUS"
        and termination.get("exit_code") == 135
        and completed >= 1
        and completed == declared_complete
        and declared_absent == 1
        and nonterminal_without_response == 1
        and isinstance(counts.get("item_runs"), int)
    )
    analysis = {
        "classification": "EXECUTION_ABORT__NOT_HYPOTHESIS_FALSIFICATION",
        "proximate_cause": (
            f"runner terminated with observed SIGBUS after {completed} COMPLETE calls; "
            "one PREPARED/SENT call lacks a matching spool row"
        ),
        "root_cause_status": "UNRESOLVED_BELOW_OBSERVED_SIGNAL_BOUNDARY",
        "scientific_interpretation": "NO_VALID_CONFIRMATORY_MEASUREMENT",
        "signal": termination.get("signal"),
        "exit_code": termination.get("exit_code"),
        "complete_calls": completed,
        "nonterminal_without_response": nonterminal_without_response,
        "item_runs": counts.get("item_runs"),
    }
    return [
        check(
            "incident.public_receipt_integrity",
            "PASS" if verified else "BLOCKED",
            observed={"verified_sha256": verified_sha, "error_type": verify_error},
            expected={"verified": True},
            remediation="regenerate only from preserved forensic authority; never hand-edit or reset the incident",
        ),
        check(
            "incident.observed_failure_boundary",
            "PASS" if observed_incident else "BLOCKED",
            observed=analysis,
            expected={"status": "ABORTED_QUARANTINED", "signal": "SIGBUS", "exit_code": 135},
            remediation="retain the quarantine and test durable resume/WAL behavior in a fresh successor root",
        ),
    ], analysis


def test_check(hswm_repo: Path, run_tests: bool, static_ready: bool) -> dict[str, object]:
    if not run_tests:
        return check(
            "verification.full_a3_suite",
            "NOT_RUN",
            observed={"test_files": list(FULL_TEST_FILES)},
            expected={"return_code": 0},
            remediation="rerun with --run-tests inside clean detached HSWM and SYMPOSIUM snapshots",
        )
    if not static_ready:
        return check(
            "verification.full_a3_suite",
            "NOT_RUN",
            observed={"reason": "static authority gate blocked"},
            expected={"return_code": 0},
            remediation="fix snapshot/runbook/runtime authority before spending resources on the full suite",
        )
    command = [sys.executable, "-m", "pytest", "-q", *FULL_TEST_FILES]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        command,
        cwd=hswm_repo,
        capture_output=True,
        text=True,
        env=environment,
        timeout=3600,
    )
    combined = (result.stdout + "\n" + result.stderr).splitlines()
    return check(
        "verification.full_a3_suite",
        "PASS" if result.returncode == 0 else "BLOCKED",
        observed={"return_code": result.returncode, "tail": combined[-40:]},
        expected={"return_code": 0},
        remediation="treat every RED or checkout drift as a no-call blocker; repair and rerun from a fresh snapshot",
    )


def write_once(path: str, value: Mapping[str, object]) -> None:
    raw = canonical_bytes(value)
    if path == "-":
        sys.stdout.buffer.write(raw)
        return
    target = Path(path).resolve()
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def build_receipt(args: argparse.Namespace) -> dict[str, object]:
    hswm_repo = Path(args.hswm_repo).resolve(strict=True)
    symposium_repo = Path(args.symposium_repo).resolve(strict=True)
    checks: list[dict[str, object]] = [runtime_check()]
    hswm_check, hswm_snapshot = repository_check(hswm_repo, "hswm", args.expected_hswm_commit)
    symposium_check, symposium_snapshot = repository_check(symposium_repo, "symposium", args.expected_symposium_commit)
    checks.extend((hswm_check, symposium_check, runbook_check(Path(args.runbook))))
    prereg = read_json(Path(args.prereg_template), "preregistration template")
    prereg_checks = preregistration_checks(prereg)
    checks.append(prereg_checks[0])
    incident = read_json(Path(args.aborted_receipt), "aborted-attempt receipt")
    incident_rows, incident_analysis = incident_checks(incident)
    checks.extend(incident_rows)
    static_ready = all(row["status"] == "PASS" for row in checks)
    checks.append(test_check(hswm_repo, args.run_tests, static_ready))
    checks.extend(
        (
            repository_stability_check(hswm_snapshot, "hswm"),
            repository_stability_check(symposium_snapshot, "symposium"),
        )
    )
    source_ready = all(row["status"] == "PASS" for row in checks)
    checks.extend(prereg_checks[1:])
    receipt: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "harness_schema_version": SCHEMA,
        "mode": "ZERO_MODEL_CALL_DIAGNOSTIC_ONLY",
        "source_gate": "READY" if source_ready else "BLOCKED",
        "development_launch_gate": "BLOCKED_UNTIL_FRESH_FIRST_WRITE_AUTHORITY_AND_POWER_PILOT",
        "confirmatory_launch_gate": "BLOCKED" if prereg_checks[1]["status"] != "PASS" else "READY_PENDING_SOURCE_AND_DEVELOPMENT_GATES",
        "scientific_state": "NOT_MEASURED",
        "hypothesis_verdict": "NONE",
        "failure_analysis": incident_analysis,
        "scientific_success_contract": {
            "metric": EXPECTED_METRIC,
            "rule": "min(LCB_typed-flat, LCB_typed-vector, LCB_typed-role_removed, LCB_typed-role_shuffled) > 0",
            "falsifier": "any frozen control LCB <= 0",
            "bootstrap": {"reps": 10000, "seed": 20260724, "unit": "component_cluster_macro", "minimum_clusters": 40},
        },
        "checks": checks,
        "next_actions": [
            "select explicit full HSWM and SYMPOSIUM commits and create clean detached snapshots",
            "rebind the runbook and all development authority from retired a2 to the A3 successor run ID",
            "run this harness with --run-tests; require every check PASS and identical before/after HEADs",
            "on Dell, create a new first-write root and rebuild selection, source, token envelope, environment, empty transport genesis, and development lock",
            "run only the 55-item/48-component/825-call development power pilot, then freeze its power receipt",
            "build preregistration artifacts, register externally, preserve exact server readback, and only then allow the sealed 100-item/1500-call run",
            "judge the hypothesis only from the four frozen paired-cluster LCBs; never convert SIGBUS or engineering PASS counts into a scientific verdict",
        ],
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--hswm-repo", required=True)
    result.add_argument("--symposium-repo", required=True)
    result.add_argument("--runbook", required=True)
    result.add_argument("--prereg-template", required=True)
    result.add_argument("--aborted-receipt", required=True)
    result.add_argument("--expected-hswm-commit")
    result.add_argument("--expected-symposium-commit")
    result.add_argument("--run-tests", action="store_true")
    result.add_argument("--output", default="-")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        receipt = build_receipt(args)
        write_once(args.output, receipt)
    except Exception as error:
        print(json.dumps({"status": "REFUSED", "error_type": type(error).__name__}), file=sys.stderr)
        return 2
    return 0 if receipt["source_gate"] == "READY" and receipt["confirmatory_launch_gate"] != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
