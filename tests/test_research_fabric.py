from __future__ import annotations

from pathlib import Path

from hswm.infrastructure import research_fabric


def test_service_specs_are_loopback_only_and_persistent(tmp_path: Path) -> None:
    specs = research_fabric.service_specs(tmp_path, bin_root=tmp_path / "bin")

    assert set(specs) == {"phoenix", "temporal"}
    assert all(spec.ready_host == "127.0.0.1" for spec in specs.values())
    assert specs["phoenix"].environment["PHOENIX_HOST"] == "127.0.0.1"
    assert specs["phoenix"].environment["PHOENIX_ENABLE_AUTH"] == "true"
    assert specs["phoenix"].environment["PHOENIX_TELEMETRY_ENABLED"] == "false"
    assert specs["phoenix"].environment["PHOENIX_ALLOWED_PROVIDERS"] == "NONE"
    assert specs["phoenix"].environment["PHOENIX_ENABLE_MCP_SERVER"] == "true"
    assert specs["phoenix"].environment["PHOENIX_ENABLE_MCP_CODE_MODE"] == "false"
    assert (
        specs["phoenix"].environment[
            "PHOENIX_ENABLE_OAUTH2_AUTHORIZATION_SERVER"
        ]
        == "false"
    )
    assert (
        specs["phoenix"].environment[
            "PHOENIX_OAUTH2_DYNAMIC_CLIENT_REGISTRATION"
        ]
        == "disabled"
    )
    assert specs["phoenix"].environment["PHOENIX_WORKING_DIR"] == str(
        tmp_path / "phoenix"
    )
    assert specs["phoenix"].expected_version == "20.4.0"
    assert specs["temporal"].expected_version == "1.8.2"
    assert specs["temporal"].expected_executable_sha256 is not None
    assert "--db-filename" in specs["temporal"].argv
    assert str(tmp_path / "temporal" / "temporal.db") in specs["temporal"].argv
    assert "--disable-config-file" in specs["temporal"].argv
    assert "--disable-config-env" in specs["temporal"].argv


def test_service_environment_does_not_inherit_session_secrets(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ORCA_AGENT_HOOK_TOKEN", "must-not-cross-boundary")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross-boundary")
    monkeypatch.setenv("PATH", "/usr/bin")
    spec = research_fabric.service_specs(tmp_path)["phoenix"]

    environment = research_fabric._service_environment(spec, tmp_path)

    assert environment["PATH"] == "/usr/bin"
    assert environment["PHOENIX_HOST"] == "127.0.0.1"
    assert "ORCA_AGENT_HOOK_TOKEN" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert len(environment["PHOENIX_SECRET"]) >= 32
    assert len(environment["PHOENIX_ADMIN_SECRET"]) >= 32
    assert (tmp_path / "secrets" / "phoenix.json").stat().st_mode & 0o077 == 0


def test_status_refuses_to_claim_an_untracked_listener(
    tmp_path: Path, monkeypatch,
) -> None:
    spec = research_fabric.service_specs(tmp_path)["temporal"]
    monkeypatch.setattr(research_fabric, "_tcp_ready", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        research_fabric, "_http_ready", lambda *args, **kwargs: (True, 200)
    )

    status = research_fabric.service_status(tmp_path, spec)

    assert status["state"] == "foreign_or_untracked_listener"
    assert status["tracking"] == "untracked"


def test_invalid_process_record_is_fail_closed(tmp_path: Path) -> None:
    spec = research_fabric.service_specs(tmp_path)["phoenix"]
    record = tmp_path / "run" / "phoenix.json"
    record.parent.mkdir(parents=True)
    record.write_text("not-json\n", encoding="utf-8")

    tracking, identity, value = research_fabric._tracked_identity(tmp_path, spec)

    assert tracking == "invalid_record"
    assert identity is None
    assert value == {"invalid": True}
