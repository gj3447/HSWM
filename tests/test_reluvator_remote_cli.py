from __future__ import annotations

import json
import subprocess
import sys

import pytest

from hswm.infrastructure import reluvator_remote_cli


@pytest.mark.parametrize("exit_code", [0, 7])
def test_buffered_remote_source_preserves_abrupt_large_output_and_exit(exit_code: int) -> None:
    producer = [sys.executable, "-c", f"import os; os.write(1, b'x' * 32769); os._exit({exit_code})"]
    source = reluvator_remote_cli._buffered_program_source(producer)
    completed = subprocess.run([sys.executable, "-c", source], capture_output=True, check=False)
    assert completed.returncode == exit_code
    assert completed.stdout == b"x" * 32769
    assert completed.stderr == b""


def test_remote_output_overflow_is_a_failure_even_if_producer_exits_zero() -> None:
    producer = [sys.executable, "-c", "import os; os.write(1, b'x' * 75000); os._exit(0)"]
    completed = subprocess.run(
        [sys.executable, "-c", reluvator_remote_cli._buffered_program_source(producer)],
        capture_output=True, check=False,
    )
    assert completed.returncode == 65
    assert json.loads(completed.stdout) == {
        "status": "FAILED", "error": "REMOTE_OUTPUT_LIMIT", "max_output_bytes": 64000,
    }


def test_unknown_focus_is_rejected_before_ssh(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def unexpected(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("ssh must not run")

    monkeypatch.setattr(reluvator_remote_cli.subprocess, "run", unexpected)
    with pytest.raises(ValueError, match="focus"):
        reluvator_remote_cli.run("other")
    assert not called


def test_allowlist_uses_only_fixed_remote_read_only_targets() -> None:
    assert tuple(reluvator_remote_cli.COMMANDS) == ("contracts", "mesh")
    assert reluvator_remote_cli.COMMANDS["contracts"] == reluvator_remote_cli.REMOTE_PREFIX + (
        "packages/app/src/entrypoints/asyncapi-emit.ts", "--check")
    assert reluvator_remote_cli.COMMANDS["mesh"] == reluvator_remote_cli.REMOTE_PREFIX + (
        "tools/contract-mesh/mesh-check.mjs", "--deep", "--json")
    assert "pnpm" not in sum((list(value) for value in reluvator_remote_cli.COMMANDS.values()), [])
