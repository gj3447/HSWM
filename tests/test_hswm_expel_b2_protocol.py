from __future__ import annotations

from pathlib import Path

import pytest

from hswm.experiments import expel_b2_protocol as protocol
from hswm.selfmod.contracts import canonical_json_bytes


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _fixture_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Create a complete harmless source tree so the real builder hashes every input."""
    repo = tmp_path / "repo"
    for relative in protocol.EXECUTION_SOURCES:
        _write(repo / relative, b"fixture source\n")
    _write(
        repo / protocol.B0_PROTOCOL_PATH,
        canonical_json_bytes({"environment_runtime": {
            "arm64_pddl_only_requirements_path": "fixtures/arm64-requirements.txt"
        }}) + b"\n",
    )
    _write(repo / "fixtures/arm64-requirements.txt", b"fixture requirement\n")
    module_path = repo / "src/hswm/experiments/expel_b2_protocol.py"
    monkeypatch.setattr(protocol, "__file__", str(module_path))
    artifact = repo / protocol.RELATIVE_PATH
    artifact.parent.mkdir(parents=True, exist_ok=True)
    return repo, artifact


def _freeze(repo: Path, artifact: Path) -> None:
    artifact.write_bytes(canonical_json_bytes(protocol.build_protocol(repo, frozen=True)) + b"\n")


def test_verifier_rejects_a_canonical_draft_at_the_declared_artifact_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, artifact = _fixture_repo(tmp_path, monkeypatch)
    artifact.write_bytes(canonical_json_bytes(protocol.build_protocol(repo, frozen=False)) + b"\n")
    with pytest.raises(protocol.B2ProtocolError, match="exact frozen source-bound"):
        protocol.verify_protocol(artifact)


def test_verifier_rejects_a_tampered_hashed_execution_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, artifact = _fixture_repo(tmp_path, monkeypatch)
    _freeze(repo, artifact)
    assert protocol.verify_protocol(artifact)["registration_status"] == protocol.FROZEN
    (repo / "src/hswm/experiments/expel_b2_transport.py").write_bytes(b"tampered fixture source\n")
    with pytest.raises(protocol.B2ProtocolError, match="exact frozen source-bound"):
        protocol.verify_protocol(artifact)


def test_verifier_rejects_model_budget_drift_even_when_source_files_are_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, artifact = _fixture_repo(tmp_path, monkeypatch)
    _freeze(repo, artifact)
    monkeypatch.setattr(protocol, "MODEL_RUNTIME", {
        **protocol.MODEL_RUNTIME, "maximum_total_http_posts": 497,
    })
    with pytest.raises(protocol.B2ProtocolError, match="exact frozen source-bound"):
        protocol.verify_protocol(artifact)
