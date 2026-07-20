"""Contract tests for the exploratory CLI provider transport."""
from __future__ import annotations

from dataclasses import asdict
import base64
import json
import os
from pathlib import Path
import threading
import time
import tomllib

import pytest

import cli_provider_transport as cli
import recorded_llm_extractor as rx
from title_anchor_builder import ParagraphInputV1


FAKE_ENV_NAMES = cli.CLIProviderConfigV1.__dataclass_fields__[
    "inherited_environment_names"
].default + (
    "FAKE_CHILD_PID_PATH",
    "FAKE_DELAY_SECONDS",
    "FAKE_MODE",
    "FAKE_PROVIDER",
    "FAKE_RESULT",
    "FAKE_SECRET",
)


FAKE_CLI = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if "--version" in sys.argv:
    print("fake-cli 1.2.3")
    raise SystemExit(0)

provider = os.environ.get("FAKE_PROVIDER", "claude")
mode = os.environ.get("FAKE_MODE", "success")
result = os.environ.get("FAKE_RESULT", '{"claims":[]}')
model = ""
if "--model" in sys.argv:
    model = sys.argv[sys.argv.index("--model") + 1]
elif "-m" in sys.argv:
    model = sys.argv[sys.argv.index("-m") + 1]

if mode == "sleep":
    time.sleep(float(os.environ.get("FAKE_DELAY_SECONDS", "60")))
if mode == "spawn-child":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    Path(os.environ["FAKE_CHILD_PID_PATH"]).write_text(str(child.pid), encoding="utf-8")
    time.sleep(60)
if mode == "stdout-limit":
    os.write(1, b"x" * 8192)
    raise SystemExit(0)
if mode == "stderr-limit":
    os.write(2, b"y" * 8192)
    time.sleep(1)
    raise SystemExit(0)
if mode == "exit-seven":
    print("failed", file=sys.stderr)
    raise SystemExit(7)
if mode == "secret-stderr":
    print("token=top-secret Bearer another-secret", file=sys.stderr)
    raise SystemExit(7)
if mode == "nonfinite-usage":
    result = '{"claims":[]}'
if mode == "assert-isolation":
    home = os.environ.get("HOME", "")
    assert "hswm-cli-provider-" in home
    own_key = {"claude": "ANTHROPIC_API_KEY", "grok": "XAI_API_KEY",
               "codex": "OPENAI_API_KEY"}[provider]
    assert not ({"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"}
                - {own_key}) & set(os.environ)
    if provider == "claude":
        assert os.environ.get("CLAUDE_CONFIG_DIR", "").startswith(home)
    elif provider == "grok":
        assert "hswm-cli-provider-" in os.environ.get("GROK_HOME", "")
        assert "--deny" in sys.argv and sys.argv[sys.argv.index("--deny") + 1] == "*"
        assert os.environ.get("GROK_CLAUDE_MCPS_ENABLED") == "0"
        assert os.environ.get("GROK_CURSOR_MCPS_ENABLED") == "0"
    else:
        assert "hswm-cli-provider-" in os.environ.get("CODEX_HOME", "")
        assert "--json" in sys.argv

if provider == "codex":
    target = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
    target.write_text(result, encoding="utf-8")
    print(json.dumps({"type": "turn.completed", "model": model,
                      "usage": {"input_tokens": 11, "output_tokens": 7}}))
else:
    payload = {"model": model, "usage": {"input_tokens": 11, "output_tokens": 7}}
    if mode == "nonfinite-usage":
        payload["usage"] = {"input_tokens": float("nan")}
    if mode == "duplicate":
        payload["text"] = '{"claims":[],"claims":[]}'
    elif mode == "model-usage":
        payload.pop("model")
        payload["modelUsage"] = {"observed-provider-model": {}}
        payload["result" if provider == "claude" else "text"] = result
    else:
        payload["result" if provider == "claude" else "text"] = result
    print(json.dumps(payload, separators=(",", ":")))
'''


def _fake_cli(tmp_path: Path) -> Path:
    path = tmp_path / "fake-cli"
    path.write_text(FAKE_CLI, encoding="utf-8")
    path.chmod(0o755)
    return path


def _config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: cli.CLIProvider = cli.CLIProvider.CLAUDE,
    **changes,
) -> cli.CLIProviderConfigV1:
    monkeypatch.setenv("FAKE_PROVIDER", provider.value)
    values = {
        "provider": provider,
        "executable": str(_fake_cli(tmp_path)),
        "requested_model": "fake-model",
        "timeout_seconds": 3.0,
        "terminate_grace_seconds": 0.1,
        "max_stdout_bytes": 64 * 1024,
        "max_stderr_bytes": 64 * 1024,
        "max_in_flight": 1,
        "allow_soft_tool_isolation": provider is cli.CLIProvider.CODEX,
        "inherited_environment_names": FAKE_ENV_NAMES,
    }
    values.update(changes)
    return cli.CLIProviderConfigV1(**values)


def _request(request_id: str = "request-1", *, timeout: float = 3.0) -> rx.OpenAIRequestV1:
    return rx.OpenAIRequestV1(
        request_id=request_id,
        endpoint="cli://local",
        body={
            "model": "fake-model",
            "messages": [
                {"role": "system", "content": "Return evidenced claims."},
                {"role": "user", "content": "TEXT_JSON=\"Green exists.\""},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout_seconds=timeout,
    )


@pytest.mark.parametrize(
    "provider,isolation",
    [
        (cli.CLIProvider.CLAUDE, "hard-no-tools"),
        (cli.CLIProvider.GROK, "isolated-no-external-tools"),
        (cli.CLIProvider.CODEX, "soft-read-only"),
    ],
)
def test_three_providers_map_one_strict_result_to_openai_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: cli.CLIProvider,
    isolation: str,
):
    config = _config(tmp_path, monkeypatch, provider)
    with cli.make_cli_transport(config, cli.OutputContract.CLAIMS_V1) as transport:
        response = transport(_request())
        envelope = json.loads(response.raw_response)
        receipt = cli.validate_cli_receipt(envelope["hswm_cli_receipt"])

    assert response.http_status == 200
    assert envelope["model"] == "fake-model"
    assert json.loads(envelope["choices"][0]["message"]["content"]) == {"claims": []}
    assert envelope["usage"] == {
        "prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18,
    }
    assert receipt.provider == provider.value
    assert receipt.isolation_level == isolation
    assert receipt.model_identity_strength == "provider-managed-unattested"
    assert receipt.generation_control_strength == "requested-not-cli-enforced"
    assert receipt.message_role_projection == "nested-openai-request-json-v1"
    assert receipt.terminal_status == cli.InvocationStatus.SUCCEEDED.value
    assert receipt.cli_version == "fake-cli 1.2.3"
    assert receipt.receipt_sha256 == transport.receipt("request-1").receipt_sha256


def test_batch_contract_is_locally_validated_and_canonicalized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "FAKE_RESULT",
        '{"results":[{"source_id":"b","claims":[]},'
        '{"source_id":"a","claims":[]}]}',
    )
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.BATCH_CLAIMS_V1,
    )
    response = transport(_request())
    content = json.loads(response.raw_response)["choices"][0]["message"]["content"]
    assert content == (
        '{"results":[{"claims":[],"source_id":"b"},'
        '{"claims":[],"source_id":"a"}]}'
    )


@pytest.mark.parametrize(
    "mode,expected_status",
    [
        ("duplicate", cli.InvocationStatus.SCHEMA_REJECTED),
        ("stdout-limit", cli.InvocationStatus.OUTPUT_LIMIT),
        ("stderr-limit", cli.InvocationStatus.OUTPUT_LIMIT),
        ("exit-seven", cli.InvocationStatus.FAILED),
    ],
)
def test_duplicate_schema_output_caps_and_nonzero_exit_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_status: cli.InvocationStatus,
):
    monkeypatch.setenv("FAKE_MODE", mode)
    config = _config(
        tmp_path, monkeypatch, max_stdout_bytes=1024, max_stderr_bytes=1024,
    )
    transport = cli.make_cli_transport(config, cli.OutputContract.CLAIMS_V1)
    with pytest.raises(cli.CLITransportError) as caught:
        transport(_request())
    receipt = caught.value.receipt

    assert receipt.terminal_status == expected_status.value
    assert receipt.result_text == ""
    assert cli.validate_cli_receipt(receipt) == receipt
    if mode == "stdout-limit":
        assert len(base64.b64decode(receipt.raw_stdout_b64)) == 1024
    if mode == "stderr-limit":
        assert receipt.raw_stderr_bytes == 1024


def test_timeout_kills_process_group_and_publishes_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_MODE", "sleep")
    monkeypatch.setenv("FAKE_DELAY_SECONDS", "60")
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch, timeout_seconds=0.15),
        cli.OutputContract.CLAIMS_V1,
    )
    started = time.monotonic()
    with pytest.raises(cli.CLITransportError) as caught:
        transport(_request(timeout=0.15))
    assert time.monotonic() - started < 3
    assert caught.value.receipt.terminal_status == cli.InvocationStatus.TIMED_OUT.value


def test_explicit_cancellation_kills_descendant_and_is_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    child_path = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_MODE", "spawn-child")
    monkeypatch.setenv("FAKE_CHILD_PID_PATH", str(child_path))
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch, timeout_seconds=10),
        cli.OutputContract.CLAIMS_V1,
    )
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            transport(_request("cancel-me", timeout=10))
        except BaseException as exc:  # captured for the assertion thread
            errors.append(exc)

    thread = threading.Thread(target=invoke)
    thread.start()
    deadline = time.monotonic() + 3
    while not child_path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert child_path.exists()
    child_pid = int(child_path.read_text(encoding="utf-8"))
    assert transport.cancel("cancel-me") is True
    thread.join(timeout=4)

    assert not thread.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], cli.CLITransportError)
    assert transport.receipt("cancel-me").terminal_status == (
        cli.InvocationStatus.CANCELLED.value
    )
    child_gone = False
    for _ in range(100):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            child_gone = True
            break
        time.sleep(0.02)
    assert child_gone


def test_max_in_flight_bounds_process_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_MODE", "sleep")
    monkeypatch.setenv("FAKE_DELAY_SECONDS", "0.25")
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch, max_in_flight=1),
        cli.OutputContract.CLAIMS_V1,
    )
    results: list[rx.TransportResponseV1] = []
    threads = [
        threading.Thread(target=lambda rid=rid: results.append(transport(_request(rid))))
        for rid in ("one", "two")
    ]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=4)
    elapsed = time.monotonic() - started

    assert len(results) == 2
    assert elapsed >= 0.40


def test_receipt_tamper_and_secret_value_are_not_admissible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_SECRET", "do-not-record-this-value")
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.CLAIMS_V1,
    )
    transport(_request())
    receipt = transport.receipt("request-1")
    serialized = json.dumps(asdict(receipt), sort_keys=True)
    assert "do-not-record-this-value" not in serialized
    assert "FAKE_SECRET" in receipt.inherited_environment_names

    tampered = asdict(receipt)
    tampered["requested_model"] = "forged-model"
    with pytest.raises(ValueError, match="self-hash"):
        cli.validate_cli_receipt(tampered)


def test_codex_soft_isolation_requires_explicit_exploratory_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_PROVIDER", "codex")
    with pytest.raises(ValueError, match="no hard tool-disable"):
        cli.CLIProviderConfigV1(
            provider=cli.CLIProvider.CODEX,
            executable=str(_fake_cli(tmp_path)),
            requested_model="fake-model",
        )


@pytest.mark.parametrize("provider", list(cli.CLIProvider))
def test_each_provider_gets_ephemeral_home_and_only_its_credential_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: cli.CLIProvider,
):
    monkeypatch.setenv("FAKE_MODE", "assert-isolation")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test-value")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-value")
    monkeypatch.setenv("XAI_API_KEY", "xai-test-value")
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch, provider), cli.OutputContract.CLAIMS_V1,
    )
    response = transport(_request(f"isolated-{provider.value}"))
    receipt = transport.receipt(f"isolated-{provider.value}")

    assert response.http_status == 200
    own_key = {
        cli.CLIProvider.CLAUDE: "ANTHROPIC_API_KEY",
        cli.CLIProvider.GROK: "XAI_API_KEY",
        cli.CLIProvider.CODEX: "OPENAI_API_KEY",
    }[provider]
    assert own_key in receipt.inherited_environment_names
    assert not ({"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"}
                - {own_key}) & set(receipt.inherited_environment_names)


def test_cross_provider_credentials_and_home_overrides_are_rejected():
    with pytest.raises(ValueError, match="cross-provider"):
        cli.CLIProviderConfigV1(
            provider=cli.CLIProvider.CLAUDE,
            executable="claude",
            requested_model="sonnet",
            inherited_environment_names=("OPENAI_API_KEY",),
        )
    with pytest.raises(ValueError, match="transport-controlled"):
        cli.CLIProviderConfigV1(
            provider=cli.CLIProvider.CLAUDE,
            executable="claude",
            requested_model="sonnet",
            inherited_environment_names=("HOME",),
        )


def test_model_usage_single_key_is_observed_without_forging_requested_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_MODE", "model-usage")
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.CLAIMS_V1,
    )
    transport(_request())
    assert transport.receipt("request-1").observed_model == "observed-provider-model"


def test_stderr_content_is_not_retained_while_metadata_remains_hash_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_MODE", "secret-stderr")
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.CLAIMS_V1,
    )
    with pytest.raises(cli.CLITransportError) as caught:
        transport(_request())
    receipt = caught.value.receipt
    assert receipt.stderr_excerpt == ""
    assert receipt.raw_stderr_bytes > 0
    assert receipt.raw_stderr_sha256 != cli._bytes_sha256(b"")


def test_nonfinite_provider_json_is_typed_and_cleans_active_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_MODE", "nonfinite-usage")
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.CLAIMS_V1,
    )
    with pytest.raises(cli.CLITransportError) as caught:
        transport(_request())
    assert caught.value.receipt.terminal_status == "schema_rejected"
    assert "non-finite JSON number" in caught.value.receipt.terminal_reason
    assert transport.cancel("request-1") is False


def test_unexpected_capture_error_kills_group_and_returns_typed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_MODE", "sleep")
    monkeypatch.setenv("FAKE_DELAY_SECONDS", "60")
    spawned: dict[str, int] = {}

    def fail_capture(process, **_kwargs):
        spawned["pid"] = process.pid
        raise RuntimeError("selector failed")

    monkeypatch.setattr(cli, "_capture_process", fail_capture)
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.CLAIMS_V1,
    )
    with pytest.raises(cli.CLITransportError) as caught:
        transport(_request())
    assert caught.value.receipt.terminal_reason == "transport_RuntimeError"
    assert transport.cancel("request-1") is False
    with pytest.raises(ProcessLookupError):
        os.kill(spawned["pid"], 0)


def test_parent_interrupt_kills_group_then_reraises_original_control_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("FAKE_MODE", "sleep")
    monkeypatch.setenv("FAKE_DELAY_SECONDS", "60")
    spawned: dict[str, int] = {}

    def interrupt_capture(process, **_kwargs):
        spawned["pid"] = process.pid
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_capture_process", interrupt_capture)
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.CLAIMS_V1,
    )
    with pytest.raises(KeyboardInterrupt):
        transport(_request())
    assert transport.receipt("request-1").terminal_reason == (
        "interrupted_KeyboardInterrupt"
    )
    assert transport.cancel("request-1") is False
    with pytest.raises(ProcessLookupError):
        os.kill(spawned["pid"], 0)


def test_executable_drift_fails_before_spawn_with_terminal_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    config = _config(tmp_path, monkeypatch)
    transport = cli.make_cli_transport(config, cli.OutputContract.CLAIMS_V1)
    executable = Path(config.executable)
    executable.write_text(FAKE_CLI + "\n# drift\n", encoding="utf-8")
    executable.chmod(0o755)
    with pytest.raises(cli.CLITransportError) as caught:
        transport(_request())
    assert caught.value.receipt.terminal_reason == "executable_drift"
    assert caught.value.receipt.return_code is None


def test_retention_is_bounded_and_repeat_attempts_keep_distinct_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch, max_retained_receipts=2),
        cli.OutputContract.CLAIMS_V1,
    )
    first = json.loads(transport(_request("same")).raw_response)["id"]
    second = json.loads(transport(_request("same")).raw_response)["id"]
    assert first != second
    assert transport.receipt(first).invocation_id == first
    assert transport.receipt("same").invocation_id == second
    transport(_request("third"))
    with pytest.raises(KeyError, match="no retained"):
        transport.receipt(first)


def test_existing_extractor_seam_accepts_envelope_but_keeps_cli_arm_exploratory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    paragraph = ParagraphInputV1("src:one", "Green", "Green exists.")
    extractor_config = rx.ExtractorConfigV1(
        endpoint="cli://local",
        model="fake-model",
        model_revision="provider-managed-unattested:fake-model",
    )
    transport = cli.make_cli_transport(
        _config(tmp_path, monkeypatch), cli.OutputContract.CLAIMS_V1,
    )
    record = rx.extract_paragraph(paragraph, extractor_config, transport)
    envelope = json.loads(record.raw_response)

    assert record.status == rx.ExtractionStatus.SUCCESS
    assert record.response_model == "fake-model"
    assert envelope["hswm_cli_receipt"]["terminal_status"] == "succeeded"
    # This fixed producer is why the CLI arm is not confirmatory H3 evidence.
    assert record.producer == rx.PRODUCER


def test_cli_transport_is_shipped_in_the_wheel():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert "cli_provider_transport" in project["tool"]["setuptools"]["py-modules"]
