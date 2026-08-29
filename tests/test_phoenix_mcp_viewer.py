from __future__ import annotations

import json
from pathlib import Path

import pytest

from hswm.infrastructure import phoenix_mcp_viewer


def test_base_url_is_restricted_to_loopback() -> None:
    assert (
        phoenix_mcp_viewer._assert_loopback_base_url(
            "http://127.0.0.1:6006"
        )
        == "http://127.0.0.1:6006/"
    )
    with pytest.raises(RuntimeError, match="127.0.0.1"):
        phoenix_mcp_viewer._assert_loopback_base_url("http://192.168.0.10:6006")
    with pytest.raises(RuntimeError, match="credentials"):
        phoenix_mcp_viewer._assert_loopback_base_url(
            "http://user:password@127.0.0.1:6006"
        )


def test_secret_writer_is_private_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "secrets" / "viewer.json"
    value = {"schema": "test", "api_key": "not-a-real-key"}

    phoenix_mcp_viewer._write_secret_json(path, value)

    assert path.stat().st_mode & 0o077 == 0
    assert path.parent.stat().st_mode & 0o077 == 0
    assert phoenix_mcp_viewer._read_secret_json(path) == value


def test_existing_secret_with_broad_permissions_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "viewer.json"
    path.write_text(json.dumps({"schema": "test"}), encoding="utf-8")
    path.chmod(0o644)

    with pytest.raises(RuntimeError, match="mode 0600"):
        phoenix_mcp_viewer._read_secret_json(path)


def test_pending_credential_has_dedicated_viewer_identity() -> None:
    value = phoenix_mcp_viewer._new_pending_credential()

    assert value["schema"] == phoenix_mcp_viewer.CREDENTIAL_SCHEMA
    assert value["role"] == "VIEWER"
    assert value["username"] == "hswm_phoenix_mcp_viewer"
    assert len(value["password"]) >= 32
    assert value["api_key"] is None


def test_server_side_tool_allowlist_is_exact() -> None:
    assert phoenix_mcp_viewer.EXPOSED_TOOL_NAMES == {
        "describeSqlSchema",
        "executeSql",
        "getProjects",
        "getProject",
    }
    assert "enable_tool_group" not in phoenix_mcp_viewer.EXPOSED_TOOL_NAMES
    assert "createProject" not in phoenix_mcp_viewer.EXPOSED_TOOL_NAMES
