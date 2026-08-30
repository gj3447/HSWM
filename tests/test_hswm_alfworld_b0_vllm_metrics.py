from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from dataclasses import replace

import pytest

from hswm.experiments.alfworld_b0_vllm_metrics import (
    MetricsQualificationError,
    PUBLIC_SCHEMA,
    STATUS_QUALIFIED,
    _canonical_receipt,
    parse_metric_snapshot,
    public_projection,
    ProbePaths,
    run_probe,
    source_binding,
    FIXED_SOURCE_RELATIVE_PATHS,
    PROTOCOL_RELATIVE_PATH,
    validate_output_paths,
)


def _private() -> dict[str, object]:
    return {"schema_version": "hswm-alfworld-b0-vllm-metrics-private/v1", "status": STATUS_QUALIFIED,
        "claim_ceiling": "counter-only", "prefix_counter_prerequisite": "must-export", "source_binding": {"repository_commit": "a" * 40, "repository_tree": "b" * 40, "protocol_relative_path": PROTOCOL_RELATIVE_PATH, "protocol_file_sha256": "c" * 64, "declared_source_sha256": {"src/hswm/experiments/alfworld_b0_vllm_metrics.py": "d" * 64}}, "lease_startup_sha256": "a" * 64, "tokenize_request_sha256": "b" * 64,
        "tokenize_response_sha256": "c" * 64, "completion_request_sha256": "d" * 64, "completion_response_sha256": "e" * 64,
        "metrics": {stage: {"raw_sha256": "0" * 64, "running": 0, "success_total": 0, "prefix_hits": 0, "prefix_queries": 0} for stage in ("startup", "after_tokenize", "after_completion")}, "counter_deltas": {"tokenize": {}, "completion": {}},
        "cleanup_attestation": "passed", "private_receipt_file_sha256": "f" * 64}


def test_metric_parser_sums_labels_and_requires_all_counter_families() -> None:
    raw = (b'vllm:num_requests_running 0\n'
           b'vllm:request_success_total{finished_reason="stop"} 1\n'
           b'vllm:request_success_total{finished_reason="length"} 2\n'
           b'vllm:prefix_cache_hits_total 0\n'
           b'vllm:prefix_cache_queries_total 0\n')
    value = parse_metric_snapshot(raw)
    assert (value.running, value.success_total, value.prefix_hits, value.prefix_queries) == (0, 3, 0, 0)
    with pytest.raises(MetricsQualificationError, match="absent"):
        parse_metric_snapshot(b"vllm:num_requests_running 0\n")


def test_public_projection_is_self_hashed_and_excludes_raw_requests() -> None:
    public = public_projection(_private())
    assert public["schema_version"] == PUBLIC_SCHEMA
    assert public["receipt_sha256"] == _canonical_receipt({k: v for k, v in public.items() if k != "receipt_sha256"})["receipt_sha256"]
    keys = " ".join(public).lower()
    for token in ("raw", "prompt", "message", "content", "episode"):
        assert token not in keys
    assert "src/hswm/experiments/alfworld_b0_vllm_metrics.py" in public["source_binding"]["declared_source_sha256"]


def test_output_policy_keeps_raw_private_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; (repo / "manifests").mkdir(parents=True)
    external = tmp_path / "external"; external.mkdir()
    with pytest.raises(MetricsQualificationError, match="private raw"):
        validate_output_paths(private_receipt=repo / "private.json", public_aggregate=repo / "manifests" / "public.json", repository=repo, allow_public_outside_manifests=False)
    with pytest.raises(MetricsQualificationError, match="public aggregate"):
        validate_output_paths(private_receipt=external / "private.json", public_aggregate=external / "public.json", repository=repo, allow_public_outside_manifests=False)


def test_cli_is_directly_executable() -> None:
    repo = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, str(repo / "scripts/qualify_hswm_alfworld_b0_vllm_metrics.py"), "--help"], cwd=repo.parent, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert "pre-selection two-request" in completed.stdout


def test_two_post_probe_records_measured_semantics_and_closes_fake_lease(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Lease:
        def __init__(self) -> None:
            self.startup = {"metrics": _metrics(0)}; self.final = None; self.closed = False; self._observed_requests = None; self.calls = 0
        def __enter__(self): return self
        def __exit__(self, *_args): self.final = {"metrics": _metrics(1)}; self.closed = True
        def http_get(self, _url: str) -> bytes:
            return _metrics(0 if self.calls == 1 else 1)
    lease = Lease()
    class Spec: endpoint = "http://127.0.0.1:18080"
    repo = tmp_path / "repo"; repo.mkdir(); external = tmp_path / "external"; external.mkdir()
    monkeypatch.setattr("hswm.experiments.alfworld_b0_vllm_metrics.source_binding", lambda _spec: {"repository_commit": "a" * 40})
    def post(_url: str, _body: bytes, *, timeout_seconds: float) -> bytes:
        assert timeout_seconds == 10; lease.calls += 1; return b"{}"
    private, public = run_probe(ProbePaths(repository=repo, private_receipt=external / "private.json", public_aggregate=external / "public.json", allow_public_outside_manifests=True, lease_spec=Spec(), timeout_seconds=10), lease_factory=lambda _spec: lease, http_post=post)  # type: ignore[arg-type]
    assert lease.closed and lease._observed_requests == (1, 1)
    assert private["status"] == STATUS_QUALIFIED and public["status"] == STATUS_QUALIFIED
    assert (external / "private.json").exists() and (external / "public.json").exists()


def test_source_binding_requires_exact_fixed_closure_and_clean_committed_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hswm.experiments.alfworld_b0_dgx import B0DgxLeaseSpec
    repo = tmp_path / "repo"; repo.mkdir()
    for relative in FIXED_SOURCE_RELATIVE_PATHS:
        path = repo / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(relative)
    command = lambda args, **kwargs: type("R", (), {"returncode": 0, "stderr": b"", "stdout": (b"" if args[-2:] == ("status", "--porcelain") else (b"a" * 40 + b"\n" if args[-1] in {"HEAD", "HEAD^{tree}"} else (repo / args[-1].split("HEAD:", 1)[1]).read_bytes()))})()
    monkeypatch.setattr(subprocess, "run", command)
    protocol = repo / PROTOCOL_RELATIVE_PATH
    spec = B0DgxLeaseSpec(repo_root=repo.resolve(), protocol_path=protocol.resolve(), protocol_sha256=__import__("hashlib").sha256(protocol.read_bytes()).hexdigest(), declared_source_paths=tuple((repo / item).resolve() for item in FIXED_SOURCE_RELATIVE_PATHS), lock_path=tmp_path / "lock", container_name="hswm-alfworld-b0-metrics-001", model_snapshot=tmp_path / "snapshot", hf_cache=tmp_path / "hf", compile_cache=tmp_path / "compile")
    binding = source_binding(spec)
    assert binding["protocol_relative_path"] == PROTOCOL_RELATIVE_PATH
    assert set(binding["declared_source_sha256"]) == set(FIXED_SOURCE_RELATIVE_PATHS)
    with pytest.raises(MetricsQualificationError, match="exactly match"):
        source_binding(replace(spec, declared_source_paths=spec.declared_source_paths[:-1]))


def _metrics(success: int) -> bytes:
    return (f"vllm:num_requests_running 0\nvllm:request_success_total {success}\n"
            "vllm:prefix_cache_hits_total 0\nvllm:prefix_cache_queries_total 0\n").encode()
