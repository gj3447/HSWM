"""Production-shaped DNRD-3 rehearsal boundary tests.

These tests deliberately use the execute test's injected bridge/scorer and
closure exporter.  They prove byte-boundary plumbing, not an authoritative
scientific occurrence: the independent judge must retain its production
closure/source gate and therefore refuse to promote this rehearsal to GO.
"""

from __future__ import annotations

import importlib.util
import json
import os
from hashlib import sha256
from dataclasses import replace
from pathlib import Path
import stat

import pytest

from _research.dnrd.execute import _copy_runtime_closure, execute_with_dependencies
from _research.dnrd.judge import judge_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]
_EXECUTE_TEST = Path(__file__).with_name("test_hswm_dnrd_execute.py")
_SPEC = importlib.util.spec_from_file_location("dnrd_execute_fixture", _EXECUTE_TEST)
assert _SPEC is not None and _SPEC.loader is not None
_FIXTURES = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIXTURES)


def _regular_runtime_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            # The production manifest admits only regular files; npm's local
            # executable links are intentionally outside its raw closure.
            continue
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path
    return files


def _runtime_manifest_rows(runtime_root: Path, relative_root: str) -> list[dict[str, str]]:
    source_root = runtime_root / relative_root
    if not source_root.is_dir():
        pytest.skip(f"current runtime closure input is unavailable: {relative_root}")
    rows: list[dict[str, str]] = []
    for relative, path in _regular_runtime_files(source_root).items():
        rows.append(
            {
                "path": f"{relative_root}/{relative}",
                "sha256": sha256(path.read_bytes()).hexdigest(),
            }
        )
    return sorted(rows, key=lambda row: row["path"])


def test_current_runtime_closure_copies_all_4050_manifest_selected_files(
    tmp_path: Path,
) -> None:
    """Exercise the checkout's production-selected runtime tree and sealing.

    This is a closure construction rehearsal, separate from the raw 16-mount
    closure and from a scientific candidate or authority judgment.
    """
    runtime_root = REPO_ROOT / "src" / "hswm" / "effect-runtime"
    packages = (
        "@standard-schema/spec", "@types/node", "effect", "fast-check",
        "pure-rand", "typescript", "undici-types",
    )
    compiled = _runtime_manifest_rows(runtime_root, "dist-dnrd")
    package_rows = [_runtime_manifest_rows(runtime_root, f"node_modules/{name}") for name in packages]
    assert len(compiled) == 56
    assert sum(len(rows) for rows in package_rows) == 3_994
    manifest = {"files": compiled, "external_packages": [{"files": rows} for rows in package_rows]}

    _copy_runtime_closure(tmp_path, runtime_root, manifest)

    copied_root = tmp_path / "bridge_runtime_closure"
    copied = _regular_runtime_files(copied_root)
    expected = {row["path"]: row["sha256"] for row in compiled}
    expected.update({row["path"]: row["sha256"] for rows in package_rows for row in rows})
    assert len(copied) == 4_050
    assert set(copied) == set(expected)
    assert all(sha256(path.read_bytes()).hexdigest() == expected[relative] for relative, path in copied.items())
    assert sum(path.stat().st_size for path in copied.values()) == sum(
        (runtime_root / relative).stat().st_size for relative in expected
    )
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o400 for path in copied.values())
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o500 for path in [copied_root, *copied_root.rglob("*")] if path.is_dir())


def test_rehearsal_execute_to_judge_preserves_production_shape_but_not_authority(
    tmp_path: Path,
) -> None:
    config, dependencies, _ = _FIXTURES._fixture(tmp_path)
    result = execute_with_dependencies(config, dependencies)
    assert result.runner_result.candidate is not None

    output = result.output_dir
    runner_rows = [json.loads(line) for line in (output / "runner_events.jsonl").read_text().splitlines()]
    model_rows = [json.loads(line) for line in (output / "model_events.jsonl").read_text().splitlines()]
    closure = json.loads((output / "bridge_mount_closure.json").read_text())
    candidate = json.loads((output / "candidate.json").read_text())

    assert len(runner_rows) == 256
    assert len(model_rows) == 256
    assert [row["event"] for row in runner_rows[:2]] == [
        "PRE_DISPATCH_READOUT", "COMPLETED_CALL",
    ]
    assert len(closure["mounts"]) == 16
    assert candidate["call_ledger"]["client_dispatched_generation_requests"] == 128

    judgment = judge_bundle(output)
    assert judgment["terminal"] == "VOID_PROTOCOL"
    assert judgment["authority"] == "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
    assert any(
        reason in judgment["failure_reason"].casefold()
        for reason in ("production hash-bound adapter boundary", "exact frozen dnrd source closure")
    )


def test_execute_void_terminal_crosses_the_same_bundle_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bounded pre-call failure is durably terminal, never a candidate."""
    config, dependencies, _ = _FIXTURES._fixture(tmp_path)

    def fail_copy(*_args: object, **_kwargs: object) -> None:
        raise OSError("integration injected closure copy failure")

    monkeypatch.setattr(_FIXTURES.dnrd_execute, "_copy_source_closure", fail_copy)
    with pytest.raises(OSError, match="integration injected closure"):
        execute_with_dependencies(config, dependencies)

    assert (config.output_root / "void_protocol.json").is_file()
    assert not (config.output_root / "candidate.json").exists()
    result = judge_bundle(config.output_root)
    assert result["terminal"] == "VOID_PROTOCOL"
    assert result["authority"] == "PRE_DISPATCH_VOID_PROTOCOL_TERMINAL_RETAINED"


def test_execute_inconclusive_terminal_preserves_the_partial_ledger_boundary(
    tmp_path: Path,
) -> None:
    """A post-dispatch durability fault produces an indexed partial terminal."""
    config, dependencies, _ = _FIXTURES._fixture(tmp_path)
    ledger = _FIXTURES._DurableJsonlEventLedger(config.output_root / "model_events.jsonl")

    class DurableAnswerer(_FIXTURES.EvidenceAnswerer):
        def answer(self, request: object):  # type: ignore[override]
            before = len(self.events)
            reply = super().answer(request)  # type: ignore[arg-type]
            for event in self.events[before:]:
                ledger(event)
            return reply

    answerer = DurableAnswerer(model=_FIXTURES.MODEL_ID, endpoint=config.model_endpoint)
    reads = 0

    def tampered_snapshot() -> tuple[dict, ...]:
        nonlocal reads
        reads += 1
        if reads == 2:
            ledger.path.chmod(0o600)
            with ledger.path.open("ab") as handle:
                handle.write(b"tamper\n")
                handle.flush()
                os.fsync(handle.fileno())
        return ledger.snapshot()

    altered = replace(
        dependencies, answerer=answerer, model_event_ledger=tampered_snapshot,
        model_event_ledger_path=ledger.path,
    )
    with pytest.raises(RuntimeError, match="differs from in-memory"):
        execute_with_dependencies(config, altered)

    assert (config.output_root / "inconclusive.json").is_file()
    assert not (config.output_root / "candidate.json").exists()
    result = judge_bundle(config.output_root)
    # The injected rehearsal still reaches the same production authority gate;
    # it is deliberately not promoted to an indexed scientific occurrence.
    assert result["terminal"] == "VOID_PROTOCOL"
    assert result["authority"] == "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
