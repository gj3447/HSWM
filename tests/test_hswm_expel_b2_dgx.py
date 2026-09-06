"""Focused no-launch checks for the prospective B2 DGX lease identity."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.experiments import expel_b2_dgx as b2
from hswm.experiments.alfworld_b0_dgx import LaunchRefused


def _spec(tmp_path: Path, *, name: str = "hswm-expel-b2-test-01") -> b2.ExpelB2DgxLeaseSpec:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    protocol = repo / "protocol.json"
    protocol.write_text(json.dumps({"schema_version": b2.PROTOCOL_SCHEMA, "model_runtime": b2.MODEL_RUNTIME}))
    snapshot = tmp_path / "hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989"
    snapshot.mkdir(parents=True)
    return b2.ExpelB2DgxLeaseSpec(
        repo_root=repo, protocol_path=protocol, protocol_sha256=sha256(protocol.read_bytes()).hexdigest(),
        declared_source_paths=(protocol,), lock_path=tmp_path / "lock", container_name=name,
        model_snapshot=snapshot, hf_cache=tmp_path / "hf", compile_cache=tmp_path / "compile",
    )


def test_b2_profile_is_separate_from_b0_and_caps_each_phase_at_248(tmp_path: Path) -> None:
    lease = b2.ExpelB2DgxLease(_spec(tmp_path), command=lambda _: b"[]")
    assert b2.LEASE_PROFILE.arm_label == "B2"
    assert b2.LEASE_PROFILE.protocol_schema == b2.PROTOCOL_SCHEMA
    assert b2.LEASE_PROFILE.model_runtime == b2.MODEL_RUNTIME
    assert b2.MAX_TOKENIZE_REQUESTS == b2.MAX_COMPLETION_REQUESTS == 248
    assert b2.MAX_REQUESTS == 496
    lease._started = True
    lease._identity = ("a" * 64, "b" * 64)
    with pytest.raises(LaunchRefused, match="B2 DGX service attestation"):
        lease.attest(248, 248)
    with pytest.raises(LaunchRefused, match="B2 DGX request count"):
        lease.attest(249, 248)
    with pytest.raises(LaunchRefused, match="B2 DGX request count"):
        lease.attest(248, 249)


def test_b2_refuses_b0_protocol_runtime_or_container_name(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    lease = b2.ExpelB2DgxLease(spec)
    spec.protocol_path.write_text(json.dumps({"schema_version": "hswm-alfworld-b0-calibration-protocol/v1", "model_runtime": b2.MODEL_RUNTIME}))
    with pytest.raises(LaunchRefused, match="B2 DGX protocol runtime identity"):
        lease._validate_protocol_runtime()

    wrong_name = _spec(tmp_path / "wrong", name="hswm-alfworld-b0-test-01")
    with pytest.raises(LaunchRefused, match="B2 DGX name or protocol hash"):
        b2.ExpelB2DgxLease(wrong_name)._validate()


def test_b2_refuses_its_own_schema_when_model_runtime_drifts(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    drifted = {**b2.MODEL_RUNTIME, "maximum_completion_posts": 247}
    spec.protocol_path.write_text(json.dumps({"schema_version": b2.PROTOCOL_SCHEMA, "model_runtime": drifted}))
    with pytest.raises(LaunchRefused, match="B2 DGX protocol runtime identity"):
        b2.ExpelB2DgxLease(spec)._validate_protocol_runtime()
