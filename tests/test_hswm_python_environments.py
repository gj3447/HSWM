"""Named development environments must not reconcile a caller's environment."""
from pathlib import Path
import json
import os
import shutil
import subprocess

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "src/hswm/development/bin/hswm-python"


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout with spaces"
    launcher = root / "src/hswm/development/bin/hswm-python"
    launcher.parent.mkdir(parents=True)
    shutil.copy2(SOURCE, launcher)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    uv = fake_bin / "uv"
    uv.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('uv 0.12.3 (test fixture)')\n"
        "else:\n"
        "    with open(os.environ['CALL_LOG'], 'a') as out:\n"
        "        out.write(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(), "
        "'environment': os.environ.get('UV_PROJECT_ENVIRONMENT'), "
        "'active': os.environ.get('VIRTUAL_ENV')}) + '\\n')\n"
    )
    uv.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}", CALL_LOG=str(log),
               UV_PROJECT_ENVIRONMENT="/must-not-reconcile", VIRTUAL_ENV="/active-user-env")
    return root, launcher, log, env


def invoke(checkout, *args):
    root, launcher, log, env = checkout
    result = subprocess.run([str(launcher), *args], cwd=root.parent, env=env,
                            capture_output=True, text=True, timeout=10)
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_sync_uses_two_pinned_environments_and_preserves_original_venv(checkout):
    root, _, _, _ = checkout
    marker = root / ".venv" / "user-marker"
    marker.parent.mkdir()
    marker.write_text("preserve existing research packages")
    result, calls = invoke(checkout, "sync")
    assert result.returncode == 0, result.stderr
    assert [c["environment"] for c in calls] == [
        str(root / ".hswm-local/envs/core"), str(root / "_research/graph_standards/runtime/.venv")]
    assert all("--locked" in c["args"] and "3.12.13" in c["args"] and
               "--no-python-downloads" in c["args"] for c in calls)
    assert marker.read_text() == "preserve existing research packages"


@pytest.mark.parametrize("lane,relative", [
    ("core", ".hswm-local/envs/core"), ("graph", "_research/graph_standards/runtime/.venv")])
def test_run_is_no_sync_and_preserves_argv_from_outside_checkout(checkout, lane, relative):
    root, _, _, _ = checkout
    python = root / relative / "bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    result, calls = invoke(checkout, lane, "python", "-c", "print('argument with spaces')")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 1
    assert calls[0]["cwd"] == str(root)
    assert calls[0]["environment"] == str(root / relative)
    assert "--no-sync" in calls[0]["args"]
    assert calls[0]["args"][-3:] == ["python", "-c", "print('argument with spaces')"]


def test_missing_environment_cannot_fall_back_to_global_tools(checkout):
    result, calls = invoke(checkout, "core", "pytest")
    assert result.returncode == 2
    assert "sync first" in result.stderr
    assert calls == []


def test_infra_uses_existing_script_lock_with_no_inherited_project(checkout):
    result, calls = invoke(checkout, "infra", "fabric")
    assert result.returncode == 0, result.stderr
    assert calls[0]["environment"] is None and calls[0]["active"] is None
    assert "--locked" in calls[0]["args"] and "--script" in calls[0]["args"]
    assert calls[0]["args"][-1] == "_research/infrastructure_smoke/research_fabric_smoke.py"


def test_unknown_infra_tool_does_not_invoke_uv_run(checkout):
    result, calls = invoke(checkout, "infra", "unregistered-tool")
    assert result.returncode == 2
    assert calls == []
