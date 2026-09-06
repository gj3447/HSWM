from __future__ import annotations

from pathlib import Path

import pytest

from hswm.experiments import expel_b2_live as live


def _paths(tmp_path: Path) -> live.LivePaths:
    repo, asset, model, hub, output, cache = (tmp_path / name for name in ("repo", "asset", "model", "hub", "output", "cache"))
    for path in (repo, asset, model, hub, output, cache): path.mkdir(exist_ok=True)
    files = {}
    for name in ("protocol", "private", "public", "pool", "locator", "upstream", "venv", "python", "runtime", "bwrap", "sudo", "archive", "lock"):
        path = tmp_path / name; path.write_text("{}") if name not in {"python"} else path.write_text("python")
        files[name] = path
    return live.LivePaths(repo, files["protocol"], files["private"], files["public"], files["pool"], files["locator"], asset, files["upstream"], files["venv"], files["python"], files["runtime"], files["bwrap"], files["sudo"], model, hub, files["archive"], files["lock"], "hswm-expel-b2-test")


def test_public_retains_nested_sequence_splits() -> None:
    private = {"inner_public_receipt": {"splits": {"train": {"attempted": 8, "success_rate": 1.0}, "valid_seen": {"attempted": 4, "success_rate": 0.5}}}}
    public = live._public(private, status=live.INCONCLUSIVE_STATUS, binding={}, selection={})
    assert set(public["sequence"]["splits"]) == {"train", "valid_seen"}
    assert public["sequence"]["splits"]["train"]["success_rate"] is None


class _Lease:
    def __init__(self, _spec: object, *, fail_close: bool = False) -> None:
        self.startup = {"startup": b"start"}; self.final = {"final": b"final"}; self.teardown = {"quiet": ""}
        self.calls: list[tuple[int, int]] = []; self.fail_close = fail_close

    def __enter__(self) -> "_Lease": return self
    def attest(self, tokenize: int, completion: int) -> None: self.calls.append((tokenize, completion))
    def __exit__(self, *_: object) -> None:
        if self.fail_close: raise RuntimeError("teardown")


def test_host_retains_complete_inner_sequence_when_lease_teardown_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output, cache = tmp_path / "output", tmp_path / "cache"
    output.mkdir(); cache.mkdir(); monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output)); monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache))
    paths = _paths(tmp_path)
    binding = {"commit": "a" * 40, "tree": "b" * 40, "_source.py": "c" * 64}
    monkeypatch.setattr(live, "_verify_bindings", lambda _p: ({}, dict(binding)))
    monkeypatch.setattr(live, "_verify_protocol", lambda *_: None)
    monkeypatch.setattr(live, "_verify_b0_evidence", lambda *_: {})
    monkeypatch.setattr(live, "_verify_runtime_environment", lambda *_: {})
    monkeypatch.setattr(live, "_verify_selection", lambda *_: (object(), {"private_selection_sha256": "d" * 64}))
    monkeypatch.setattr(live, "_verify_selected_assets", lambda *_: {"selected_file_count": 12, "valid_unseen_selected_file_count": 0})
    monkeypatch.setattr(live, "dgx_sandbox_identity", lambda **_: {})
    lease = _Lease(None, fail_close=True)
    def sequence(**_kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        return ({"status": live.SEQUENCE_COMPLETE, "request_counts": {"action_tokenize": 240, "reflection_tokenize": 8, "action_completion": 240, "reflection_completion": 8}}, {"splits": {"train": {"attempted": 8}, "valid_seen": {"attempted": 4}}})
    private, public = live.run_live(paths, lease_factory=lambda _spec: lease, sequence_runner=sequence)
    assert lease.calls == [(248, 248)]
    assert private["status"] == live.INCONCLUSIVE_STATUS
    assert private["inner_private_receipt"]["status"] == live.SEQUENCE_COMPLETE
    assert public["sequence"]["splits"]["valid_seen"]["attempted"] == 4
    assert public["sequence"]["splits"]["valid_seen"]["success_rate"] is None
    assert {"startup:startup", "final:final", "teardown:quiet"} <= set(private["lease_blobs"])


def test_host_preserves_reserved_transport_prefix_when_sequence_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output, cache = tmp_path / "output", tmp_path / "cache"
    output.mkdir(); cache.mkdir(); monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output)); monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache))
    paths = _paths(tmp_path)
    monkeypatch.setattr(live, "_verify_bindings", lambda _p: ({}, {"commit": "a" * 40, "tree": "b" * 40, "_source.py": "c" * 64}))
    monkeypatch.setattr(live, "_verify_protocol", lambda *_: None); monkeypatch.setattr(live, "_verify_b0_evidence", lambda *_: {})
    monkeypatch.setattr(live, "_verify_runtime_environment", lambda *_: {}); monkeypatch.setattr(live, "_verify_selection", lambda *_: (object(), {}))
    monkeypatch.setattr(live, "_verify_selected_assets", lambda *_: {"selected_file_count": 12, "valid_unseen_selected_file_count": 0})
    monkeypatch.setattr(live, "dgx_sandbox_identity", lambda **_: {})
    def sequence(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        transport = kwargs["transport_factory"](lambda _event: None)
        transport._gate.reserve(operation="action", phase="tokenize")  # reservation is the pre-network evidence boundary
        raise RuntimeError("journal fsync failed")
    private, public = live.run_live(paths, lease_factory=lambda _spec: _Lease(None), sequence_runner=sequence)
    assert private["status"] == live.INCONCLUSIVE_STATUS
    assert private["issued_counts"]["issued_tokenize_post_count"] == 1
    assert private["transport_observation"]["request_counts"]["action_tokenize"] == 1
    assert public["sequence"]["usage"]["tokenize"]["input_tokens"]["unknown_request_count"] == 0
    assert public["sequence"]["splits"] == {}
