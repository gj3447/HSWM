from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
import prom_search_hswm.prom9_f1_r8_lock_v6 as lock_v6


def _write_predecessor_lock(path: Path) -> tuple[dict[str, object], bytes]:
    unsigned = {
        "schema_version": lock_v6.EXECUTION_LOCK_SCHEMA,
        "purpose": "DEVELOPMENT_POWER_PILOT",
        "mode": "development",
        "run_id": lock_v6.C800_RUN_ID,
        "preregistration_artifact_sha256": None,
    }
    value = {**unsigned, "lock_sha256": canonical_sha256(unsigned)}
    raw = (canonical_json(value) + "\n").encode("utf-8")
    path.write_bytes(raw)
    path.chmod(0o600)
    return value, raw


def _successor_binding(
    value: dict[str, object], raw: bytes
) -> dict[str, object]:
    return {
        "c800_incident": {
            "artifact_bindings": {
                "execution_lock": {
                    "schema_version": lock_v6.EXECUTION_LOCK_SCHEMA,
                    "size_bytes": len(raw),
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "canonical_sha256": canonical_sha256(value),
                    "declared_hashes": {"lock_sha256": value["lock_sha256"]},
                }
            }
        }
    }


def test_predecessor_execution_lock_requires_exact_quarantined_binding(
    tmp_path: Path,
) -> None:
    path = tmp_path / "c800-execution-lock.json"
    value, raw = _write_predecessor_lock(path)
    successor = _successor_binding(value, raw)
    assert lock_v6._predecessor_execution_lock_authority(path, successor) == value

    for field in ("raw_sha256", "canonical_sha256", "size_bytes"):
        drifted = copy.deepcopy(successor)
        binding = drifted["c800_incident"]["artifact_bindings"][
            "execution_lock"
        ]
        binding[field] = 0 if field == "size_bytes" else "0" * 64
        with pytest.raises(
            lock_v6.LockRefusal,
            match="differs from quarantined authority",
        ):
            lock_v6._predecessor_execution_lock_authority(path, drifted)

    wrong_path = tmp_path / "wrong-run-lock.json"
    wrong = copy.deepcopy(value)
    wrong["run_id"] = lock_v6.C801_DEVELOPMENT_RUN_ID
    unsigned = dict(wrong)
    unsigned.pop("lock_sha256")
    wrong["lock_sha256"] = canonical_sha256(unsigned)
    wrong_raw = (canonical_json(wrong) + "\n").encode("utf-8")
    wrong_path.write_bytes(wrong_raw)
    wrong_path.chmod(0o600)
    with pytest.raises(lock_v6.LockRefusal, match="authority drifted"):
        lock_v6._predecessor_execution_lock_authority(
            wrong_path, _successor_binding(wrong, wrong_raw)
        )


def test_fresh_judge_authority_is_receipt_bound_and_not_predecessor() -> None:
    fresh_file = "1" * 64
    fresh_core = "2" * 64
    dependencies = {"files": {"judge_core": {"sha256": fresh_file}}}
    predecessor = {
        "judge_core_file_sha256": "3" * 64,
        "judge_core_sha256": "4" * 64,
    }
    lock_v6._validate_fresh_judge_authority(
        dependencies,
        predecessor,
        judge_core_file_sha256=fresh_file,
        judge_core_sha256=fresh_core,
    )

    wrong_receipt = copy.deepcopy(dependencies)
    wrong_receipt["files"]["judge_core"]["sha256"] = "5" * 64
    with pytest.raises(lock_v6.LockRefusal, match="verified c801 dependency"):
        lock_v6._validate_fresh_judge_authority(
            wrong_receipt,
            predecessor,
            judge_core_file_sha256=fresh_file,
            judge_core_sha256=fresh_core,
        )

    for field, value in (
        ("judge_core_file_sha256", fresh_file),
        ("judge_core_sha256", fresh_core),
    ):
        reused = copy.deepcopy(predecessor)
        reused[field] = value
        with pytest.raises(lock_v6.LockRefusal, match="not fresh"):
            lock_v6._validate_fresh_judge_authority(
                dependencies,
                reused,
                judge_core_file_sha256=fresh_file,
                judge_core_sha256=fresh_core,
            )

    for malformed in ({}, {"judge_core_file_sha256": "x", "judge_core_sha256": "4" * 64}):
        with pytest.raises(lock_v6.LockRefusal, match="predecessor judge"):
            lock_v6._validate_fresh_judge_authority(
                dependencies,
                malformed,
                judge_core_file_sha256=fresh_file,
                judge_core_sha256=fresh_core,
            )


def test_c801_judge_capability_preflight_is_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Judge:
        @staticmethod
        def c801_preflight_contract() -> dict[str, object]:
            return copy.deepcopy(lock_v6.JUDGE_CAPABILITY_V1)

    monkeypatch.setattr(
        lock_v6,
        "_load_c801_judge_core",
        lambda _path, **_kwargs: Judge(),
    )
    lock_v6._validate_c801_judge_capability(tmp_path / "judge.py")

    class DriftedJudge:
        @staticmethod
        def c801_preflight_contract() -> dict[str, object]:
            value = copy.deepcopy(lock_v6.JUDGE_CAPABILITY_V1)
            value["sealed_run_id"] = "f1-2wiki-sealed-r8-c800"
            return value

    monkeypatch.setattr(
        lock_v6, "_load_c801_judge_core", lambda _path, **_kwargs: DriftedJudge()
    )
    with pytest.raises(lock_v6.LockRefusal, match="not c801 scientific authority"):
        lock_v6._validate_c801_judge_capability(tmp_path / "judge.py")

    def refuse(_path: Path, **_kwargs: object) -> object:
        raise RuntimeError("private judge import detail")

    monkeypatch.setattr(lock_v6, "_load_c801_judge_core", refuse)
    with pytest.raises(lock_v6.LockRefusal, match="capability preflight failed"):
        lock_v6._validate_c801_judge_capability(tmp_path / "judge.py")


def test_result_contract_authority_is_receipt_bound() -> None:
    digest = "6" * 64
    lock_v6._validate_result_contract_authority(
        {"files": {"result_contract": {"sha256": digest}}}, digest
    )
    with pytest.raises(lock_v6.LockRefusal, match="result contract differs"):
        lock_v6._validate_result_contract_authority(
            {"files": {"result_contract": {"sha256": "7" * 64}}},
            digest,
        )
