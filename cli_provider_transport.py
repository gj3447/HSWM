"""Receipt-preserving, tool-isolated CLI providers for exploratory HSWM calls.

This module adapts the installed Claude, Grok, and Codex CLIs to the callable
``recorded_llm_extractor.Transport`` boundary.  It is deliberately not a
network service, scheduler, or retry engine.  Every call is one bounded local
process with a terminal receipt embedded in the returned OpenAI-compatible
envelope.

The transport is exploratory only.  A provider-managed CLI session is not a
content-attested model deployment and must not replace the pinned Qwen path in
the H3-B3 confirmatory protocol.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass, fields, replace
from enum import StrEnum
from hashlib import sha256
import base64
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from typing import Any, Mapping, Sequence

from recorded_llm_extractor import OpenAIRequestV1, TransportResponseV1
from world_ir import canonical_json, content_id, sha256_text


SCHEMA_VERSION = "hswm-cli-provider-invocation/v1"
MODEL_IDENTITY_STRENGTH = "provider-managed-unattested"
_ENV_NAME_RE = re.compile(r"[A-Z_][A-Z0-9_]*\Z")
_ROLE_RE = re.compile(r"[a-z][a-z0-9_:-]{0,63}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_TERMINAL_STATUSES = frozenset({
    "succeeded", "failed", "timed_out", "cancelled", "output_limit",
    "schema_rejected",
})
_COMMON_ENVIRONMENT_NAMES = (
    "ALL_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "NO_PROXY",
    "PATH",
    "SHELL",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TMPDIR",
    "USER",
)
_PROVIDER_ENVIRONMENT_NAMES = {
    "claude": ("ANTHROPIC_API_KEY",),
    "grok": ("XAI_API_KEY",),
    "codex": ("OPENAI_API_KEY",),
}
_CONTROLLED_ENVIRONMENT_NAMES = frozenset({
    "CLAUDE_CONFIG_DIR", "CODEX_HOME", "GROK_HOME", "HOME",
})
_KNOWN_PROVIDER_CREDENTIAL_NAMES = frozenset(
    name for names in _PROVIDER_ENVIRONMENT_NAMES.values() for name in names
)


class CLIProvider(StrEnum):
    CLAUDE = "claude"
    GROK = "grok"
    CODEX = "codex"


class OutputContract(StrEnum):
    CLAIMS_V1 = "claims_v1"
    BATCH_CLAIMS_V1 = "batch_claims_v1"


class InvocationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    OUTPUT_LIMIT = "output_limit"
    SCHEMA_REJECTED = "schema_rejected"


@dataclass(frozen=True)
class CLIProviderConfigV1:
    provider: CLIProvider
    executable: str
    requested_model: str
    timeout_seconds: float = 300.0
    terminate_grace_seconds: float = 2.0
    max_stdout_bytes: int = 4 * 1024 * 1024
    max_stderr_bytes: int = 1024 * 1024
    max_in_flight: int = 1
    max_retained_receipts: int = 16
    allow_soft_tool_isolation: bool = False
    inherited_environment_names: tuple[str, ...] = _COMMON_ENVIRONMENT_NAMES

    def __post_init__(self) -> None:
        if not isinstance(self.provider, CLIProvider):
            raise TypeError("provider must be CLIProvider")
        if not isinstance(self.executable, str) or not self.executable.strip():
            raise ValueError("executable must be non-empty")
        if not isinstance(self.requested_model, str) or not self.requested_model.strip():
            raise ValueError("requested_model must be non-empty")
        if not 0 < self.timeout_seconds <= 86_400:
            raise ValueError("timeout_seconds must be in (0, 86400]")
        if not 0 < self.terminate_grace_seconds <= 30:
            raise ValueError("terminate_grace_seconds must be in (0, 30]")
        for name, value in (
            ("max_stdout_bytes", self.max_stdout_bytes),
            ("max_stderr_bytes", self.max_stderr_bytes),
        ):
            if not isinstance(value, int) or not 1024 <= value <= 64 * 1024 * 1024:
                raise ValueError(f"{name} must be in [1024, 67108864]")
        if not isinstance(self.max_in_flight, int) or not 1 <= self.max_in_flight <= 16:
            raise ValueError("max_in_flight must be in [1, 16]")
        if (not isinstance(self.max_retained_receipts, int)
                or not 1 <= self.max_retained_receipts <= 1024):
            raise ValueError("max_retained_receipts must be in [1, 1024]")
        names = self.inherited_environment_names
        if (not isinstance(names, tuple) or len(names) != len(set(names))
                or any(not isinstance(name, str) or not _ENV_NAME_RE.fullmatch(name)
                       for name in names)):
            raise ValueError("inherited_environment_names must be unique safe names")
        if set(names) & _CONTROLLED_ENVIRONMENT_NAMES:
            raise ValueError("HOME and provider config directories are transport-controlled")
        allowed_credential = set(_PROVIDER_ENVIRONMENT_NAMES[self.provider.value])
        foreign_credentials = (
            set(names) & _KNOWN_PROVIDER_CREDENTIAL_NAMES
        ) - allowed_credential
        if foreign_credentials:
            raise ValueError("cross-provider credential inheritance is forbidden")
        if self.provider is CLIProvider.CODEX and not self.allow_soft_tool_isolation:
            raise ValueError(
                "Codex CLI has no hard tool-disable flag; set "
                "allow_soft_tool_isolation=True for exploratory use"
            )


@dataclass(frozen=True)
class CLIInvocationReceiptV1:
    schema_version: str
    invocation_id: str
    request_id: str
    provider: str
    requested_model: str
    observed_model: str
    model_identity_strength: str
    executable: str
    executable_sha256: str
    cli_version: str
    cli_version_sha256: str
    isolation_level: str
    message_role_projection: str
    generation_control_strength: str
    inherited_environment_names: tuple[str, ...]
    public_argv: tuple[str, ...]
    argv_sha256: str
    request_sha256: str
    prompt_sha256: str
    output_contract: str
    schema_sha256: str
    raw_stdout_b64: str
    raw_stdout_sha256: str
    raw_stdout_bytes: int
    raw_stderr_sha256: str
    raw_stderr_bytes: int
    stderr_excerpt: str
    result_text: str
    result_text_sha256: str
    return_code: int | None
    terminal_status: str
    terminal_reason: str
    started_unix_ns: int
    finished_unix_ns: int
    latency_ms: int
    provider_usage_json: str
    receipt_sha256: str


class CLITransportError(RuntimeError):
    """Typed process-boundary failure carrying its terminal receipt."""

    def __init__(self, message: str, receipt: CLIInvocationReceiptV1):
        super().__init__(message)
        self.receipt = receipt


class _DuplicateJSONKey(ValueError):
    pass


@dataclass
class _ActiveInvocation:
    cancel_event: threading.Event
    process: subprocess.Popen[bytes] | None = None


@dataclass(frozen=True)
class _CommandPlan:
    argv: tuple[str, ...]
    public_argv: tuple[str, ...]
    stdin_payload: bytes
    output_path: Path | None


def _strict_json(raw: str | bytes, *, label: str) -> Any:
    def reject_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateJSONKey(f"duplicate key {key!r} in {label}")
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON number {value!r} in {label}")

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="strict")
    return json.loads(
        raw,
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_nonfinite,
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def _receipt_digest(receipt: CLIInvocationReceiptV1) -> str:
    payload = asdict(replace(receipt, receipt_sha256=""))
    return sha256_text(canonical_json(payload))


def validate_cli_receipt(
    value: CLIInvocationReceiptV1 | Mapping[str, Any],
) -> CLIInvocationReceiptV1:
    """Validate receipt shape, hashes, terminal state, and self-integrity."""

    if isinstance(value, CLIInvocationReceiptV1):
        receipt = value
    elif isinstance(value, Mapping):
        expected = {field.name for field in fields(CLIInvocationReceiptV1)}
        if set(value) != expected:
            raise ValueError("CLI receipt keys mismatch")
        payload = dict(value)
        for key in ("inherited_environment_names", "public_argv"):
            if isinstance(payload.get(key), list):
                payload[key] = tuple(payload[key])
        receipt = CLIInvocationReceiptV1(**payload)
    else:
        raise TypeError("CLI receipt must be a receipt or mapping")

    if receipt.schema_version != SCHEMA_VERSION:
        raise ValueError("CLI receipt schema mismatch")
    if receipt.provider not in {item.value for item in CLIProvider}:
        raise ValueError("CLI receipt provider mismatch")
    if receipt.output_contract not in {item.value for item in OutputContract}:
        raise ValueError("CLI receipt output contract mismatch")
    if receipt.terminal_status not in _TERMINAL_STATUSES:
        raise ValueError("CLI receipt terminal status mismatch")
    if receipt.model_identity_strength != MODEL_IDENTITY_STRENGTH:
        raise ValueError("CLI receipt model identity mismatch")
    if receipt.isolation_level not in {
        "hard-no-tools", "isolated-no-external-tools", "soft-read-only",
    }:
        raise ValueError("CLI receipt isolation level mismatch")
    if receipt.message_role_projection != "nested-openai-request-json-v1":
        raise ValueError("CLI receipt message projection mismatch")
    if receipt.generation_control_strength != "requested-not-cli-enforced":
        raise ValueError("CLI receipt generation control mismatch")
    if not receipt.invocation_id.startswith("hswm:cli_provider_invocation:v1:"):
        raise ValueError("CLI receipt invocation ID mismatch")
    if not receipt.request_id or not receipt.requested_model or not receipt.executable:
        raise ValueError("CLI receipt identity is incomplete")
    if not receipt.cli_version or not receipt.public_argv:
        raise ValueError("CLI receipt command identity is incomplete")
    if (receipt.finished_unix_ns < receipt.started_unix_ns
            or receipt.started_unix_ns <= 0 or receipt.latency_ms < 0):
        raise ValueError("CLI receipt timing mismatch")
    if receipt.latency_ms != (
        receipt.finished_unix_ns - receipt.started_unix_ns
    ) // 1_000_000:
        raise ValueError("CLI receipt latency mismatch")
    if receipt.return_code is not None and not isinstance(receipt.return_code, int):
        raise ValueError("CLI receipt return code mismatch")
    if not receipt.terminal_reason:
        raise ValueError("CLI receipt terminal reason is empty")
    if receipt.stderr_excerpt != "":
        raise ValueError("CLI receipt must not retain stderr content")
    if (not isinstance(receipt.raw_stdout_bytes, int)
            or not isinstance(receipt.raw_stderr_bytes, int)
            or min(receipt.raw_stdout_bytes, receipt.raw_stderr_bytes) < 0):
        raise ValueError("CLI receipt byte counts mismatch")
    try:
        raw_stdout = base64.b64decode(receipt.raw_stdout_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("CLI receipt stdout encoding mismatch") from exc
    if receipt.raw_stdout_bytes != len(raw_stdout):
        raise ValueError("CLI receipt stdout byte count mismatch")
    if receipt.raw_stdout_sha256 != _bytes_sha256(raw_stdout):
        raise ValueError("CLI receipt stdout hash mismatch")
    if receipt.result_text_sha256 != sha256_text(receipt.result_text):
        raise ValueError("CLI receipt result hash mismatch")
    if receipt.cli_version_sha256 != sha256_text(receipt.cli_version):
        raise ValueError("CLI receipt version hash mismatch")
    for key in (
        "executable_sha256", "argv_sha256", "request_sha256", "prompt_sha256",
        "schema_sha256", "raw_stdout_sha256", "raw_stderr_sha256",
        "result_text_sha256", "receipt_sha256",
    ):
        if not _SHA256_RE.fullmatch(getattr(receipt, key)):
            raise ValueError(f"CLI receipt {key} mismatch")
    if (not isinstance(receipt.inherited_environment_names, tuple)
            or tuple(sorted(receipt.inherited_environment_names))
            != receipt.inherited_environment_names
            or len(receipt.inherited_environment_names)
            != len(set(receipt.inherited_environment_names))
            or any(not _ENV_NAME_RE.fullmatch(name)
                   for name in receipt.inherited_environment_names)):
        raise ValueError("CLI receipt environment-name set mismatch")
    try:
        usage = _strict_json(receipt.provider_usage_json, label="provider usage")
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJSONKey) as exc:
        raise ValueError("CLI receipt provider usage mismatch") from exc
    if not isinstance(usage, Mapping):
        raise ValueError("CLI receipt provider usage must be an object")
    if receipt.terminal_status == InvocationStatus.SUCCEEDED.value:
        if not receipt.result_text:
            raise ValueError("successful CLI receipt lacks a result")
    elif receipt.result_text:
        raise ValueError("failed CLI receipt must not publish a result")
    if receipt.receipt_sha256 != _receipt_digest(receipt):
        raise ValueError("CLI receipt self-hash mismatch")
    return receipt


def _argument_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["role", "exact"],
        "properties": {
            "role": {"type": "string", "pattern": "^[a-z][a-z0-9_:-]{0,63}$"},
            "exact": {"type": "string", "minLength": 1, "maxLength": 512},
        },
    }


def _claim_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["subject", "predicate", "arguments"],
        "properties": {
            "subject": {"type": "string", "minLength": 1, "maxLength": 512},
            "predicate": {"type": "string", "minLength": 1, "maxLength": 512},
            "arguments": {
                "type": "array", "minItems": 1, "maxItems": 12,
                "items": _argument_schema(),
            },
        },
    }


def output_schema(contract: OutputContract) -> dict[str, Any]:
    if not isinstance(contract, OutputContract):
        raise TypeError("contract must be OutputContract")
    claims = {
        "type": "array", "maxItems": 4, "items": _claim_schema(),
    }
    if contract is OutputContract.CLAIMS_V1:
        return {
            "type": "object", "additionalProperties": False,
            "required": ["claims"],
            "properties": {"claims": claims},
        }
    return {
        "type": "object", "additionalProperties": False,
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array", "minItems": 1, "maxItems": 8,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["source_id", "claims"],
                    "properties": {
                        "source_id": {"type": "string", "minLength": 1},
                        "claims": claims,
                    },
                },
            },
        },
    }


def _validate_claims(value: Any) -> None:
    if not isinstance(value, list) or len(value) > 4:
        raise ValueError("claims must be an array of at most four items")
    for claim in value:
        if not isinstance(claim, Mapping) or set(claim) != {
            "subject", "predicate", "arguments",
        }:
            raise ValueError("claim keys mismatch")
        if any(not isinstance(claim[key], str) or not claim[key]
               or len(claim[key]) > 512 for key in ("subject", "predicate")):
            raise ValueError("claim quote mismatch")
        arguments = claim["arguments"]
        if not isinstance(arguments, list) or not 1 <= len(arguments) <= 12:
            raise ValueError("claim arguments mismatch")
        for argument in arguments:
            if not isinstance(argument, Mapping) or set(argument) != {"role", "exact"}:
                raise ValueError("claim argument keys mismatch")
            role, exact = argument["role"], argument["exact"]
            if not isinstance(role, str) or not _ROLE_RE.fullmatch(role):
                raise ValueError("claim role mismatch")
            if not isinstance(exact, str) or not exact or len(exact) > 512:
                raise ValueError("claim argument quote mismatch")


def _validate_contract(value: Any, contract: OutputContract) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("CLI result must be one JSON object")
    if contract is OutputContract.CLAIMS_V1:
        if set(value) != {"claims"}:
            raise ValueError("claims result root keys mismatch")
        _validate_claims(value["claims"])
        return dict(value)
    if set(value) != {"results"}:
        raise ValueError("batch result root keys mismatch")
    results = value["results"]
    if not isinstance(results, list) or not 1 <= len(results) <= 8:
        raise ValueError("batch results mismatch")
    source_ids: list[str] = []
    for result in results:
        if not isinstance(result, Mapping) or set(result) != {"source_id", "claims"}:
            raise ValueError("batch result item keys mismatch")
        source_id = result["source_id"]
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("batch source_id mismatch")
        source_ids.append(source_id)
        _validate_claims(result["claims"])
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("batch source_id values must be unique")
    return dict(value)


def _minimal_environment(config: CLIProviderConfigV1) -> tuple[dict[str, str], tuple[str, ...]]:
    requested_names = (
        set(config.inherited_environment_names)
        | set(_PROVIDER_ENVIRONMENT_NAMES[config.provider.value])
    ) - _CONTROLLED_ENVIRONMENT_NAMES
    inherited = tuple(sorted(
        name for name in requested_names if name in os.environ
    ))
    environment = {name: os.environ[name] for name in inherited}
    environment["PYTHONUNBUFFERED"] = "1"
    environment["NO_COLOR"] = "1"
    return environment, inherited


def _credential_source(config: CLIProviderConfigV1) -> Path | None:
    provider = config.provider
    api_key_name = _PROVIDER_ENVIRONMENT_NAMES[provider.value][0]
    if os.environ.get(api_key_name):
        return None
    if provider is CLIProvider.CLAUDE:
        root = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        candidate = root / ".credentials.json"
    elif provider is CLIProvider.GROK:
        root = Path(os.environ.get("GROK_HOME", Path.home() / ".grok"))
        candidate = root / "auth.json"
    else:
        root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        candidate = root / "auth.json"
    try:
        return candidate.expanduser().resolve(strict=True)
    except OSError:
        return None


def _copy_private(source: Path, target: Path) -> None:
    payload = source.read_bytes()
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)


def _invocation_environment(
    config: CLIProviderConfigV1,
    base_environment: Mapping[str, str],
    temporary_root: Path,
    credential_source: Path | None,
) -> dict[str, str]:
    environment = dict(base_environment)
    isolated_home = temporary_root / "home"
    isolated_home.mkdir(mode=0o700)
    environment["HOME"] = str(isolated_home)
    if config.provider is CLIProvider.CLAUDE:
        config_root = isolated_home / ".claude"
        config_root.mkdir(mode=0o700)
        if credential_source is not None:
            _copy_private(credential_source, config_root / ".credentials.json")
        environment["CLAUDE_CONFIG_DIR"] = str(config_root)
    elif config.provider is CLIProvider.GROK:
        config_root = temporary_root / "grok-home"
        config_root.mkdir(mode=0o700)
        if credential_source is not None:
            _copy_private(credential_source, config_root / "auth.json")
        environment.update({
            "GROK_HOME": str(config_root),
            "GROK_CLAUDE_MCPS_ENABLED": "0",
            "GROK_CURSOR_MCPS_ENABLED": "0",
            "GROK_DISABLE_AUTOUPDATER": "1",
            "GROK_SUBAGENTS": "0",
            "GROK_WEB_FETCH": "0",
            "GROK_WRITE_FILE": "0",
        })
    else:
        config_root = temporary_root / "codex-home"
        config_root.mkdir(mode=0o700)
        if credential_source is not None:
            _copy_private(credential_source, config_root / "auth.json")
        environment["CODEX_HOME"] = str(config_root)
    return environment


def _resolve_executable(executable: str) -> Path:
    raw = Path(executable).expanduser()
    found = str(raw) if "/" in executable else shutil.which(executable)
    if not found:
        raise FileNotFoundError(f"CLI executable not found: {executable}")
    path = Path(found).resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise PermissionError(f"CLI executable is not executable: {path}")
    return path


def _probe_version(executable: Path, environment: Mapping[str, str]) -> str:
    try:
        completed = subprocess.run(
            (str(executable), "--version"), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(environment),
            timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("CLI version probe failed") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"CLI version probe exited {completed.returncode}")
    raw = completed.stdout or completed.stderr
    if len(raw) > 4096:
        raise RuntimeError("CLI version probe output exceeded 4096 bytes")
    try:
        version = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise RuntimeError("CLI version probe was not UTF-8") from exc
    if not version or "\n" in version or len(version) > 512:
        raise RuntimeError("CLI version probe returned an invalid version")
    return version


def _validate_request(request: OpenAIRequestV1, config: CLIProviderConfigV1) -> None:
    if not isinstance(request, OpenAIRequestV1):
        raise TypeError("request must be OpenAIRequestV1")
    if request.body.get("model") != config.requested_model:
        raise ValueError("request model does not equal configured CLI model")
    if request.body.get("temperature") != 0:
        raise ValueError("CLI transport accepts only temperature=0")
    if request.body.get("response_format") != {"type": "json_object"}:
        raise ValueError("CLI transport requires json_object response format")
    messages = request.body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("request messages must be a non-empty array")
    for message in messages:
        if (not isinstance(message, Mapping) or set(message) != {"role", "content"}
                or message["role"] not in {"system", "user", "assistant"}
                or not isinstance(message["content"], str)):
            raise ValueError("request message schema mismatch")
    if request.timeout_seconds <= 0:
        raise ValueError("request timeout must be positive")


def _make_prompt(request: OpenAIRequestV1, contract: OutputContract) -> str:
    return (
        "You are an isolated structured-output provider for HSWM. "
        "Do not use tools, files, network search, memory, or prior sessions. "
        "Apply the ordered messages in OPENAI_REQUEST_JSON and return exactly "
        "one JSON object matching OUTPUT_CONTRACT; no markdown or prose.\n"
        f"OUTPUT_CONTRACT={contract.value}\n"
        f"OPENAI_REQUEST_JSON={canonical_json(request.body)}"
    )


def _write_private(path: Path, text: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)


def _build_command(
    config: CLIProviderConfigV1,
    executable: Path,
    prompt: str,
    schema_json: str,
    temporary_root: Path,
) -> _CommandPlan:
    model = config.requested_model
    if config.provider is CLIProvider.CLAUDE:
        argv = (
            str(executable), "--print", "--output-format", "json",
            "--model", model, "--tools", "", "--safe-mode",
            "--no-session-persistence", "--permission-mode", "dontAsk",
            "--disable-slash-commands", "--no-chrome", "--strict-mcp-config",
            "--mcp-config", '{"mcpServers":{}}', "--json-schema", schema_json,
        )
        public = argv[:-1] + ("<output-schema-json>",)
        return _CommandPlan(argv, public, prompt.encode("utf-8"), None)
    if config.provider is CLIProvider.GROK:
        prompt_path = temporary_root / "prompt.txt"
        _write_private(prompt_path, prompt)
        argv = (
            str(executable), "--prompt-file", str(prompt_path), "--cwd",
            str(temporary_root), "--output-format", "json", "--max-turns", "1",
            "--model", model, "--no-memory", "--no-subagents",
            "--disable-web-search", "--no-plan", "--tools", "",
            "--disallowed-tools",
            "Agent,run_terminal_cmd,run_terminal_command,search_replace,"
            "web_search,web_fetch,read_file,grep,list_dir",
            "--deny", "*", "--sandbox", "read-only", "--no-auto-update",
            "--json-schema", schema_json, "--verbatim",
        )
        public = tuple(
            "<prompt-file>" if item == str(prompt_path)
            else "<isolated-cwd>" if item == str(temporary_root)
            else "<output-schema-json>" if item == schema_json
            else item
            for item in argv
        )
        return _CommandPlan(argv, public, b"", None)

    schema_path = temporary_root / "schema.json"
    output_path = temporary_root / "last-message.json"
    _write_private(schema_path, schema_json)
    argv = (
        str(executable), "--ask-for-approval", "never", "--sandbox", "read-only",
        "--cd", str(temporary_root), "--model", model, "exec",
        "--json", "--color", "never",
        "--ignore-user-config", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check", "--output-schema", str(schema_path),
        "--output-last-message", str(output_path), "-",
    )
    public = tuple(
        "<isolated-cwd>" if item == str(temporary_root)
        else "<output-schema-file>" if item == str(schema_path)
        else "<last-message-file>" if item == str(output_path)
        else item
        for item in argv
    )
    return _CommandPlan(argv, public, prompt.encode("utf-8"), output_path)


def _terminate_process_group(
    process: subprocess.Popen[bytes], grace_seconds: float,
) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    # Always target the original group once more.  The lead may have exited
    # during the grace period while a descendant kept pipes or work alive.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _write_stdin(pipe: Any, payload: bytes) -> None:
    try:
        if payload:
            pipe.write(payload)
            pipe.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            pipe.close()
        except OSError:
            pass


def _capture_process(
    process: subprocess.Popen[bytes],
    *,
    stdin_payload: bytes,
    cancel_event: threading.Event,
    timeout_seconds: float,
    grace_seconds: float,
    stdout_limit: int,
    stderr_limit: int,
) -> tuple[bytes, bytes, int | None, InvocationStatus | None, str | None]:
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    writer = threading.Thread(
        target=_write_stdin, args=(process.stdin, stdin_payload), daemon=True,
    )
    writer.start()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    sizes = {"stdout": 0, "stderr": 0}
    limits = {"stdout": stdout_limit, "stderr": stderr_limit}
    deadline = time.monotonic() + timeout_seconds
    forced_status: InvocationStatus | None = None
    forced_reason: str | None = None
    try:
        while selector.get_map():
            if cancel_event.is_set() and forced_status is None:
                forced_status = InvocationStatus.CANCELLED
                forced_reason = "cancel_requested"
                _terminate_process_group(process, grace_seconds)
            if time.monotonic() >= deadline and forced_status is None:
                forced_status = InvocationStatus.TIMED_OUT
                forced_reason = "deadline_exceeded"
                _terminate_process_group(process, grace_seconds)
            events = selector.select(timeout=0.05)
            for key, _mask in events:
                stream = key.data
                try:
                    chunk = os.read(key.fd, 65_536)
                except OSError:
                    chunk = b""
                if not chunk:
                    try:
                        selector.unregister(key.fileobj)
                    except Exception:
                        pass
                    continue
                remaining = max(0, limits[stream] - sizes[stream])
                chunks[stream].append(chunk[:remaining])
                sizes[stream] += len(chunk[:remaining])
                if len(chunk) > remaining and forced_status is None:
                    forced_status = InvocationStatus.OUTPUT_LIMIT
                    forced_reason = f"{stream}_limit_exceeded"
                    _terminate_process_group(process, grace_seconds)
            if process.poll() is not None and not events:
                # EOF notifications normally remove both descriptors.  This
                # guard prevents a broken descendant from holding a pipe open.
                if time.monotonic() > deadline + grace_seconds:
                    break
        if process.poll() is None:
            _terminate_process_group(process, grace_seconds)
        try:
            return_code = process.wait(timeout=max(1.0, grace_seconds))
        except subprocess.TimeoutExpired:
            _terminate_process_group(process, 0.01)
            return_code = process.poll()
        if forced_status is None and cancel_event.is_set():
            # Cancellation may race with the final EOF notification: the
            # caller can signal the group after the last loop guard but before
            # both descriptors are unregistered.
            forced_status = InvocationStatus.CANCELLED
            forced_reason = "cancel_requested"
    finally:
        selector.close()
        writer.join(timeout=1.0)
    return (
        b"".join(chunks["stdout"]), b"".join(chunks["stderr"]),
        return_code, forced_status, forced_reason,
    )


def _mapping_usage(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _candidate_result(outer: Mapping[str, Any]) -> Any:
    for key in ("structured_output", "structuredOutput"):
        if isinstance(outer.get(key), Mapping):
            return outer[key]
    for key in ("result", "text", "output_text"):
        candidate = outer.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return _strict_json(candidate, label="CLI result text")
        if isinstance(candidate, Mapping):
            return candidate
    raise ValueError("provider response lacks one structured result")


def _parse_provider_output(
    provider: CLIProvider,
    raw_stdout: bytes,
    output_path: Path | None,
    contract: OutputContract,
) -> tuple[str, str, dict[str, Any]]:
    stdout_text = raw_stdout.decode("utf-8", errors="strict")
    observed_model = ""
    usage: dict[str, Any] = {}
    if provider is CLIProvider.CODEX:
        if output_path is None or not output_path.is_file():
            raise ValueError("Codex did not create output-last-message")
        result_value = _strict_json(
            output_path.read_bytes(), label="Codex output-last-message",
        )
        for line in stdout_text.splitlines():
            if not line.strip():
                continue
            try:
                event = _strict_json(line, label="Codex JSONL event")
            except (json.JSONDecodeError, _DuplicateJSONKey):
                continue
            if isinstance(event, Mapping):
                if isinstance(event.get("model"), str):
                    observed_model = event["model"]
                if isinstance(event.get("usage"), Mapping):
                    usage = dict(event["usage"])
    else:
        outer = _strict_json(stdout_text, label=f"{provider.value} response")
        if not isinstance(outer, Mapping):
            raise ValueError("provider response must be one JSON object")
        result_value = _candidate_result(outer)
        for key in ("model", "modelId", "model_id"):
            if isinstance(outer.get(key), str):
                observed_model = outer[key]
                break
        if not observed_model and isinstance(outer.get("modelUsage"), Mapping):
            model_keys = tuple(
                key for key in outer["modelUsage"] if isinstance(key, str) and key
            )
            if len(model_keys) == 1:
                observed_model = model_keys[0]
        usage = _mapping_usage(outer.get("usage"))
    validated = _validate_contract(result_value, contract)
    return canonical_json(validated), observed_model, usage


def _openai_usage(provider_usage: Mapping[str, Any]) -> dict[str, int]:
    def number(*keys: str) -> int:
        for key in keys:
            value = provider_usage.get(key)
            if isinstance(value, int) and value >= 0:
                return value
        return 0

    prompt = number("prompt_tokens", "input_tokens", "inputTokens")
    completion = number("completion_tokens", "output_tokens", "outputTokens")
    total = number("total_tokens", "totalTokens") or prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


class CLIProviderTransport:
    """One-process-per-call exploratory transport with cancellation receipts."""

    def __init__(self, config: CLIProviderConfigV1, contract: OutputContract):
        if not isinstance(config, CLIProviderConfigV1):
            raise TypeError("config must be CLIProviderConfigV1")
        if not isinstance(contract, OutputContract):
            raise TypeError("contract must be OutputContract")
        self.config = config
        self.contract = contract
        self._environment, self._inherited_names = _minimal_environment(config)
        self._credential_source = _credential_source(config)
        self._executable = _resolve_executable(config.executable)
        self._executable_sha256 = _file_sha256(self._executable)
        self._cli_version = _probe_version(self._executable, self._environment)
        self._semaphore = threading.BoundedSemaphore(config.max_in_flight)
        self._lock = threading.RLock()
        self._active: dict[str, _ActiveInvocation] = {}
        self._receipts: OrderedDict[str, CLIInvocationReceiptV1] = OrderedDict()
        self._latest_by_request: dict[str, str] = {}
        self._closed = False

    def __enter__(self) -> "CLIProviderTransport":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def __call__(self, request: OpenAIRequestV1) -> TransportResponseV1:
        _validate_request(request, self.config)
        prompt = _make_prompt(request, self.contract)
        schema_json = canonical_json(output_schema(self.contract))
        request_json = canonical_json(request.body)
        started_ns = time.time_ns()
        invocation_id = content_id("cli_provider_invocation", {
            "request_id": request.request_id,
            "provider": self.config.provider.value,
            "started_unix_ns": started_ns,
            "executable_sha256": self._executable_sha256,
        })
        active = _ActiveInvocation(threading.Event())
        with self._lock:
            if self._closed:
                raise RuntimeError("CLI transport is closed")
            if request.request_id in self._active:
                raise RuntimeError("request_id is already active")
            self._active[request.request_id] = active

        raw_stdout = b""
        raw_stderr = b""
        return_code: int | None = None
        status = InvocationStatus.FAILED
        reason = "setup_failed"
        result_text = ""
        observed_model = ""
        provider_usage: dict[str, Any] = {}
        public_argv: tuple[str, ...] = (str(self._executable),)
        argv_sha256 = _bytes_sha256(str(self._executable).encode("utf-8"))
        acquired = False
        try:
            effective_timeout = min(
                self.config.timeout_seconds, request.timeout_seconds,
            )
            deadline = time.monotonic() + effective_timeout
            while not acquired:
                if active.cancel_event.is_set():
                    status, reason = InvocationStatus.CANCELLED, "cancel_requested_before_start"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status, reason = InvocationStatus.TIMED_OUT, "queue_deadline_exceeded"
                    break
                acquired = self._semaphore.acquire(timeout=min(0.05, remaining))
            if acquired:
                with tempfile.TemporaryDirectory(prefix="hswm-cli-provider-") as raw_temp:
                    temporary_root = Path(raw_temp)
                    os.chmod(temporary_root, 0o700)
                    plan = _build_command(
                        self.config, self._executable, prompt, schema_json,
                        temporary_root,
                    )
                    public_argv = plan.public_argv
                    argv_sha256 = _bytes_sha256(b"\0".join(
                        item.encode("utf-8") for item in plan.argv
                    ))
                    if active.cancel_event.is_set():
                        status, reason = InvocationStatus.CANCELLED, "cancel_requested_before_spawn"
                    elif not self._executable_unchanged():
                        status, reason = InvocationStatus.FAILED, "executable_drift"
                    else:
                        process_environment = _invocation_environment(
                            self.config, self._environment, temporary_root,
                            self._credential_source,
                        )
                        try:
                            process = subprocess.Popen(
                                plan.argv, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=temporary_root, env=process_environment,
                                start_new_session=True,
                            )
                        except OSError as exc:
                            status, reason = InvocationStatus.FAILED, f"spawn_{type(exc).__name__}"
                        else:
                            with self._lock:
                                active.process = process
                            raw_stdout, raw_stderr, return_code, forced, forced_reason = (
                                _capture_process(
                                    process, stdin_payload=plan.stdin_payload,
                                    cancel_event=active.cancel_event,
                                    timeout_seconds=max(0.001, deadline - time.monotonic()),
                                    grace_seconds=self.config.terminate_grace_seconds,
                                    stdout_limit=self.config.max_stdout_bytes,
                                    stderr_limit=self.config.max_stderr_bytes,
                                )
                            )
                            if forced is not None:
                                status, reason = forced, forced_reason or forced.value
                            elif return_code != 0:
                                status, reason = (
                                    InvocationStatus.FAILED,
                                    f"process_exit_{return_code}",
                                )
                            else:
                                try:
                                    result_text, observed_model, provider_usage = (
                                        _parse_provider_output(
                                            self.config.provider, raw_stdout,
                                            plan.output_path, self.contract,
                                        )
                                    )
                                except (
                                    UnicodeDecodeError, json.JSONDecodeError,
                                    _DuplicateJSONKey, OSError, ValueError,
                                ) as exc:
                                    status, reason = (
                                        InvocationStatus.SCHEMA_REJECTED,
                                        f"{type(exc).__name__}: {str(exc)[:160]}",
                                    )
                                else:
                                    status, reason = InvocationStatus.SUCCEEDED, "completed"
        except Exception as exc:
            # After registration, runtime/setup failures become one typed,
            # receipt-bearing terminal state. If capture itself failed, make
            # sure the whole child process group is gone before publishing it.
            if active.process is not None:
                _terminate_process_group(
                    active.process, self.config.terminate_grace_seconds,
                )
            status = InvocationStatus.FAILED
            reason = f"transport_{type(exc).__name__}"
        except BaseException as exc:
            # KeyboardInterrupt/SystemExit must retain their normal control
            # flow, but a child in its own session would otherwise outlive the
            # parent unwind with no active handle left for cancel()/close().
            if active.process is not None:
                _terminate_process_group(
                    active.process, self.config.terminate_grace_seconds,
                )
            status = InvocationStatus.FAILED
            reason = f"interrupted_{type(exc).__name__}"
            raise
        finally:
            if acquired:
                self._semaphore.release()
            finished_ns = time.time_ns()
            provisional = CLIInvocationReceiptV1(
                schema_version=SCHEMA_VERSION,
                invocation_id=invocation_id,
                request_id=request.request_id,
                provider=self.config.provider.value,
                requested_model=self.config.requested_model,
                observed_model=observed_model,
                model_identity_strength=MODEL_IDENTITY_STRENGTH,
                executable=str(self._executable),
                executable_sha256=self._executable_sha256,
                cli_version=self._cli_version,
                cli_version_sha256=sha256_text(self._cli_version),
                isolation_level=(
                    "soft-read-only" if self.config.provider is CLIProvider.CODEX
                    else "isolated-no-external-tools"
                    if self.config.provider is CLIProvider.GROK
                    else "hard-no-tools"
                ),
                message_role_projection="nested-openai-request-json-v1",
                generation_control_strength="requested-not-cli-enforced",
                inherited_environment_names=self._inherited_names,
                public_argv=public_argv,
                argv_sha256=argv_sha256,
                request_sha256=sha256_text(request_json),
                prompt_sha256=sha256_text(prompt),
                output_contract=self.contract.value,
                schema_sha256=sha256_text(schema_json),
                raw_stdout_b64=base64.b64encode(raw_stdout).decode("ascii"),
                raw_stdout_sha256=_bytes_sha256(raw_stdout),
                raw_stdout_bytes=len(raw_stdout),
                raw_stderr_sha256=_bytes_sha256(raw_stderr),
                raw_stderr_bytes=len(raw_stderr),
                # Provider stderr may contain arbitrary credentials or session
                # material. Persist only its byte count and digest.
                stderr_excerpt="",
                result_text=result_text if status is InvocationStatus.SUCCEEDED else "",
                result_text_sha256=sha256_text(
                    result_text if status is InvocationStatus.SUCCEEDED else ""
                ),
                return_code=return_code,
                terminal_status=status.value,
                terminal_reason=reason,
                started_unix_ns=started_ns,
                finished_unix_ns=finished_ns,
                latency_ms=(finished_ns - started_ns) // 1_000_000,
                provider_usage_json=canonical_json(provider_usage),
                receipt_sha256="",
            )
            receipt = replace(
                provisional, receipt_sha256=_receipt_digest(provisional),
            )
            validate_cli_receipt(receipt)
            with self._lock:
                self._receipts[invocation_id] = receipt
                self._latest_by_request[request.request_id] = invocation_id
                while len(self._receipts) > self.config.max_retained_receipts:
                    expired_id, expired = self._receipts.popitem(last=False)
                    if self._latest_by_request.get(expired.request_id) == expired_id:
                        self._latest_by_request.pop(expired.request_id, None)
                self._active.pop(request.request_id, None)

        if status is not InvocationStatus.SUCCEEDED:
            raise CLITransportError(reason, receipt)
        envelope = {
            "id": invocation_id,
            "object": "chat.completion",
            "created": started_ns // 1_000_000_000,
            "model": self.config.requested_model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result_text},
                "finish_reason": "stop",
            }],
            "usage": _openai_usage(provider_usage),
            "hswm_cli_receipt": asdict(receipt),
        }
        return TransportResponseV1(canonical_json(envelope), http_status=200)

    def cancel(self, request_id: str) -> bool:
        """Request cancellation; the invocation publishes a terminal receipt."""

        with self._lock:
            active = self._active.get(request_id)
            if active is None:
                return False
            active.cancel_event.set()
            process = active.process
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        return True

    def receipt(self, request_id: str) -> CLIInvocationReceiptV1:
        with self._lock:
            invocation_id = (
                request_id if request_id in self._receipts
                else self._latest_by_request.get(request_id)
            )
            if invocation_id is None:
                raise KeyError(f"no retained terminal receipt for {request_id}")
            receipt = self._receipts[invocation_id]
        return validate_cli_receipt(receipt)

    def _executable_unchanged(self) -> bool:
        try:
            return _file_sha256(self._executable) == self._executable_sha256
        except OSError:
            return False

    def close(self) -> None:
        with self._lock:
            self._closed = True
            active = tuple(self._active.values())
        for invocation in active:
            invocation.cancel_event.set()
            if invocation.process is not None:
                _terminate_process_group(
                    invocation.process, self.config.terminate_grace_seconds,
                )


def make_cli_transport(
    config: CLIProviderConfigV1,
    contract: OutputContract,
) -> CLIProviderTransport:
    return CLIProviderTransport(config, contract)


__all__ = [
    "CLIInvocationReceiptV1",
    "CLIProvider",
    "CLIProviderConfigV1",
    "CLIProviderTransport",
    "CLITransportError",
    "InvocationStatus",
    "OutputContract",
    "SCHEMA_VERSION",
    "make_cli_transport",
    "output_schema",
    "validate_cli_receipt",
]
