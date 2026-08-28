"""Production-shaped DNRD-4 rehearsal boundary tests.

These tests deliberately use the execute test's injected bridge/scorer and
closure exporter.  They prove byte-boundary plumbing, not an authoritative
scientific occurrence: the independent judge must retain its production
closure/source gate and therefore refuse to promote this rehearsal to GO.
"""

from __future__ import annotations

import importlib.util
import json
from hashlib import sha256
from dataclasses import replace
from pathlib import Path
import stat

import pytest

from _research.dnrd.execute import _copy_runtime_closure, execute_with_dependencies
from _research.dnrd.judge import _runtime_closure_files, judge_bundle
from _research.dnrd.live import HttpResponse, OpenAICompatibleDnrdAnswerer, OpenAICompatibleDnrdConfig


REPO_ROOT = Path(__file__).resolve().parents[1]
_EXECUTE_TEST = Path(__file__).with_name("test_hswm_dnrd_execute.py")
_SPEC = importlib.util.spec_from_file_location("dnrd_execute_fixture", _EXECUTE_TEST)
assert _SPEC is not None and _SPEC.loader is not None
_FIXTURES = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIXTURES)


@pytest.fixture(autouse=True)
def _bind_hermetic_fixture_python_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Match the imported execute fixture's Python identity to CI's runtime."""
    executable = _FIXTURES.Path(_FIXTURES.sys.executable).resolve()
    monkeypatch.setattr(
        _FIXTURES.dnrd_execute,
        "OFFICIAL_PYTHON_EXECUTABLE_SHA256",
        _FIXTURES.hashlib.sha256(executable.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        _FIXTURES.dnrd_execute,
        "OFFICIAL_PYTHON_VERSION",
        f"{_FIXTURES.sys.version_info.major}.{_FIXTURES.sys.version_info.minor}.{_FIXTURES.sys.version_info.micro}",
    )
    monkeypatch.setattr(
        _FIXTURES.dnrd_execute,
        "OFFICIAL_UNICODE_DATA_VERSION",
        _FIXTURES.unicodedata.unidata_version,
    )


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


def _runtime_manifest_rows(runtime_root: Path, relative_root: str) -> list[dict[str, str | int]]:
    source_root = runtime_root / relative_root
    if not source_root.is_dir():
        pytest.skip(f"current runtime closure input is unavailable: {relative_root}")
    rows: list[dict[str, str]] = []
    for relative, path in _regular_runtime_files(source_root).items():
        rows.append(
            {
                "path": f"{relative_root}/{relative}",
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    return sorted(rows, key=lambda row: row["path"])


def test_current_runtime_closure_copies_all_4050_manifest_selected_files_and_judge_reads_it(
    tmp_path: Path,
) -> None:
    """Exercise the checkout's production-selected runtime tree and sealing.

    This is the strongest checkout-faithful runtime edge that can be exercised
    without fabricating a Source-A/B-CI provenance chain: execute's copier
    seals the complete 4,050-file manifest and the judge-side closure reader
    consumes those sealed bytes.  The terminal tests below intentionally use
    a small source/runtime fixture, because a full candidate judgment also
    requires the checkout's source closure, lockfile, Node pin, and CI
    chronology to be the same frozen occurrence.  Splicing this checkout
    runtime into that fixture would test invented provenance rather than a
    production-shaped occurrence.
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
    known_zero = "node_modules/@standard-schema/spec/dist/index.js"
    assert known_zero in expected
    assert expected[known_zero] == sha256(b"").hexdigest()
    assert copied[known_zero].stat().st_size == 0
    # This is the judge-side closure walk used after execute's copy and
    # bundle-indexing.  It must retain the manifest-addressed zero-byte npm
    # member instead of voiding the occurrence before exact row rehashing.
    judge_files = _runtime_closure_files(tmp_path)
    assert len(judge_files) == 4_050
    assert judge_files[known_zero] == b""
    # The production copy is intentionally sealed. Re-open this test-owned
    # temporary tree so pytest can remove it without emitting cleanup noise.
    for path in sorted(copied_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o700 if path.is_dir() else 0o600)
    copied_root.chmod(0o700)


def test_rehearsal_execute_to_judge_preserves_production_shape_but_not_authority(
    tmp_path: Path,
) -> None:
    config, dependencies, _ = _FIXTURES._fixture(tmp_path)
    answerer = _FIXTURES.EvidenceAnswerer(
        pretty_response=True, model=_FIXTURES.MODEL_ID, endpoint=config.model_endpoint,
    )
    dependencies = replace(dependencies, answerer=answerer, model_event_ledger=lambda: tuple(answerer.events))
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
    assert all(
        '\n  "response_token" :' in json.loads(row["raw_response_utf8"])["choices"][0]["message"]["content"]
        for row in model_rows if row["event"] == "CHAT_COMPLETION_ACCEPTED"
    )

    judgment = judge_bundle(output)
    assert judgment["terminal"] == "VOID_PROTOCOL"
    assert judgment["authority"] == "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
    assert any(
        reason in judgment["failure_reason"].casefold()
        for reason in (
            "production hash-bound adapter boundary",
            "exact frozen dnrd source closure",
            "runtime identities differ from source-a protocol constants",
            "structured-output qualification python/unicode runtime identities",
        )
    )


def test_execute_terminal_model_boundary_rejection_stays_indexed_inconclusive(
    tmp_path: Path,
) -> None:
    """A real retained response rejection is the only partial INCONCLUSIVE path."""
    config, dependencies, _ = _FIXTURES._fixture(tmp_path)
    events: list[dict] = []

    class BoundaryTransport:
        calls = 0

        def request(self, **kwargs: object) -> HttpResponse:
            self.calls += 1
            if self.calls == 1:
                prompt = json.loads(kwargs["body"])["messages"][0]["content"]  # type: ignore[index]
                token = prompt.rsplit("nonce=", 1)[1]
                return HttpResponse(200, json.dumps({
                    "model": _FIXTURES.MODEL_ID,
                    "choices": [{"finish_reason": "stop", "message": {"content": '{\n  "response_token" : "' + token + '"\n}'}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }).encode())
            return HttpResponse(200, json.dumps({
                "model": _FIXTURES.MODEL_ID,
                "choices": [{"finish_reason": "length", "message": {"content": "x"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode())

    answerer = OpenAICompatibleDnrdAnswerer(
        OpenAICompatibleDnrdConfig(config.model_endpoint), BoundaryTransport(), event_sink=events.append,
    )
    altered = replace(dependencies, answerer=answerer, model_event_ledger=lambda: tuple(events))
    result = execute_with_dependencies(config, altered)
    assert result.runner_result.inconclusive_occurrence is not None
    assert (config.output_root / "inconclusive.json").is_file()
    judgment = judge_bundle(config.output_root)
    assert judgment["terminal"] == "INCONCLUSIVE_OCCURRENCE"
    assert judgment["authority"] == "INDEXED_INCONCLUSIVE_MODEL_BOUNDARY_AND_RUNNER_IDENTITY_LEDGER_VERIFIED"


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


def test_execute_internal_post_dispatch_fault_seals_a_ledger_bound_void_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-acceptance finalization fault is a ledger-bound VOID, not INCONCLUSIVE."""
    config, dependencies, _ = _FIXTURES._fixture(tmp_path)
    original = _FIXTURES.dnrd_execute.run_diagnostic

    def bad_final_binding(*args: object, **kwargs: object):
        result = original(*args, **kwargs)
        candidate = json.loads(json.dumps(result.candidate))
        assert candidate is not None
        candidate["bindings"]["event_ledger_sha256"] = "0" * 64
        return replace(result, candidate=candidate)

    monkeypatch.setattr(_FIXTURES.dnrd_execute, "run_diagnostic", bad_final_binding)
    with pytest.raises(RuntimeError, match="candidate ledger binding"):
        execute_with_dependencies(config, dependencies)

    assert (config.output_root / "void_protocol.json").is_file()
    assert not (config.output_root / "candidate.json").exists()
    result = judge_bundle(config.output_root)
    # The injected rehearsal still reaches the same production authority gate;
    # it is deliberately not promoted to an indexed scientific occurrence.
    assert result["terminal"] == "VOID_PROTOCOL"
    assert result["authority"] == "POST_DISPATCH_VOID_PROTOCOL_TERMINAL_LEDGER_BOUND"
