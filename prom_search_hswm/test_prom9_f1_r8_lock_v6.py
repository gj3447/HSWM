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
