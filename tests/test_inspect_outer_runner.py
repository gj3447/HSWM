from __future__ import annotations

from pathlib import Path

from hswm.evaluation import inspect_outer_runner


def test_inspect_command_is_exact_pinned() -> None:
    argv = inspect_outer_runner.inspect_argv(
        "/usr/bin/uvx", "info", "version"
    )

    assert argv == (
        "/usr/bin/uvx",
        "--from",
        "inspect-ai==0.3.260",
        "inspect",
        "info",
        "version",
    )


def test_no_model_environment_does_not_inherit_provider_secrets() -> None:
    environment = inspect_outer_runner.sanitized_environment(
        {
            "PATH": "/usr/bin",
            "LANG": "C.UTF-8",
            "OPENAI_API_KEY": "must-not-cross-boundary",
            "ANTHROPIC_API_KEY": "must-not-cross-boundary",
            "ORCA_AGENT_HOOK_TOKEN": "must-not-cross-boundary",
        }
    )

    assert environment == {
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
    }


def test_preflight_receipt_binds_outputs_without_recording_them(
    tmp_path: Path, monkeypatch,
) -> None:
    uvx = tmp_path / "uvx"
    uvx.write_bytes(b"fake uvx")
    uvx.chmod(0o700)
    outputs = iter(("version: 0.3.260\npath: /external/cache\n", "cache table\n"))
    monkeypatch.setattr(
        inspect_outer_runner,
        "_run_no_model",
        lambda *args, **kwargs: next(outputs),
    )

    receipt = inspect_outer_runner.preflight(uvx_path=str(uvx))

    assert receipt.status == "PASS"
    assert receipt.observed_version == "0.3.260"
    assert receipt.requirement == "inspect-ai==0.3.260"
    assert receipt.ambient_provider_secrets_inherited is False
    assert not hasattr(receipt, "stdout")
