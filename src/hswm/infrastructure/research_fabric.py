"""Operate the bounded HSWM research-development infrastructure on dev-01.

The services managed here are evidence and execution projections.  They are not
HSWM cognition, canonical atom authority, causal credit, or durable learning.
The launcher binds every unauthenticated endpoint to loopback, enables Phoenix
authentication for its upstream wildcard gRPC collector, and starts both
services with a credential-minimal environment.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import stat
import subprocess
import time
from typing import Iterable, Mapping, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen


STATUS_SCHEMA = "hswm-research-fabric-status/v1"
PROCESS_SCHEMA = "hswm-research-fabric-process/v1"
SECRET_SCHEMA = "hswm-research-fabric-secrets/v1"
CLAIM_BOUNDARY = (
    "bounded infrastructure observation; not HSWM cognition, canonical "
    "admission, causal credit, continuous-learning evidence, or efficacy"
)
DEFAULT_STATE_ROOT = Path.home() / ".local/state/hswm-research-fabric"
DEFAULT_BIN_ROOT = Path.home() / ".local/bin"
_SAFE_ENVIRONMENT_NAMES = (
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "USER",
)


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    executable: Path
    argv: tuple[str, ...]
    environment: Mapping[str, str]
    ready_host: str
    ready_port: int
    health_url: str | None
    responsibility: str
    expected_version: str
    expected_executable_sha256: str | None


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    start_ticks: int
    cmdline: tuple[str, ...]


@dataclass(frozen=True)
class EndpointCheck:
    name: str
    host: str
    port: int
    responsibility: str
    health_url: str | None = None


def _state_root(override: str | os.PathLike[str] | None = None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    configured = os.environ.get("HSWM_RESEARCH_FABRIC_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_STATE_ROOT


def service_specs(
    root: Path,
    *,
    bin_root: Path = DEFAULT_BIN_ROOT,
) -> dict[str, ServiceSpec]:
    root = root.resolve()
    bin_root = bin_root.resolve()
    temporal = ServiceSpec(
        name="temporal",
        executable=bin_root / "temporal",
        argv=(
            "--disable-config-file",
            "--disable-config-env",
            "--log-format",
            "json",
            "server",
            "start-dev",
            "--ip",
            "127.0.0.1",
            "--port",
            "7233",
            "--ui-ip",
            "127.0.0.1",
            "--ui-port",
            "8233",
            "--ui-disable-news-fetch",
            "--http-port",
            "7243",
            "--metrics-port",
            "9464",
            "--db-filename",
            str(root / "temporal" / "temporal.db"),
            "--namespace",
            "hswm-dev",
            "--search-attribute",
            "HswmRunId=Keyword",
            "--search-attribute",
            "HswmSchemaVersion=Keyword",
            "--search-attribute",
            "HswmAtomUid=Keyword",
            "--search-attribute",
            "HswmOutcome=Keyword",
        ),
        environment={},
        ready_host="127.0.0.1",
        ready_port=7233,
        health_url="http://127.0.0.1:8233/",
        responsibility="durable development workflow-history projection",
        expected_version="1.8.2",
        expected_executable_sha256=(
            "95e6043afbbcf71137d3c953e83969e24217ca746bf535dbde561fed83a188e9"
        ),
    )
    phoenix = ServiceSpec(
        name="phoenix",
        executable=bin_root / "phoenix",
        argv=("serve",),
        environment={
            "PHOENIX_HOST": "127.0.0.1",
            "PHOENIX_PORT": "6006",
            "PHOENIX_GRPC_PORT": "4317",
            "PHOENIX_WORKING_DIR": str(root / "phoenix"),
            "PHOENIX_ENABLE_AUTH": "true",
            "PHOENIX_ALLOW_EXTERNAL_RESOURCES": "false",
            "PHOENIX_TELEMETRY_ENABLED": "false",
            "PHOENIX_ALLOWED_PROVIDERS": "NONE",
            # Keep the MCP projection explicit and non-executable.  Authorization
            # is still enforced by Phoenix; a dedicated VIEWER principal is
            # provisioned separately for Codex.
            "PHOENIX_ENABLE_MCP_SERVER": "true",
            "PHOENIX_ENABLE_MCP_CODE_MODE": "false",
            "PHOENIX_ENABLE_OAUTH2_AUTHORIZATION_SERVER": "false",
            "PHOENIX_OAUTH2_DYNAMIC_CLIENT_REGISTRATION": "disabled",
        },
        ready_host="127.0.0.1",
        ready_port=6006,
        health_url="http://127.0.0.1:6006/healthz",
        responsibility="LLM trajectory, trace, dataset, and evaluation projection",
        expected_version="20.4.0",
        expected_executable_sha256=None,
    )
    return {spec.name: spec for spec in (temporal, phoenix)}


def _phoenix_secret_path(root: Path) -> Path:
    return root / "secrets" / "phoenix.json"


def _phoenix_secrets(root: Path) -> dict[str, str]:
    path = _phoenix_secret_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        value = {
            "schema": SECRET_SCHEMA,
            "phoenix_secret": f"jwt1_{secrets.token_hex(32)}",
            "phoenix_admin_secret": f"admin1_{secrets.token_hex(32)}",
        }
        payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise RuntimeError(f"unsafe Phoenix secret file identity: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RuntimeError(
            f"Phoenix secret file must not be group/world accessible: {path}"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError(f"invalid Phoenix secret file: {path}") from error
    if not isinstance(value, dict) or value.get("schema") != SECRET_SCHEMA:
        raise RuntimeError(f"invalid Phoenix secret schema: {path}")
    jwt_secret = value.get("phoenix_secret")
    admin_secret = value.get("phoenix_admin_secret")
    if (
        not isinstance(jwt_secret, str)
        or not isinstance(admin_secret, str)
        or len(jwt_secret) < 32
        or len(admin_secret) < 32
        or jwt_secret == admin_secret
    ):
        raise RuntimeError(f"invalid Phoenix secret values: {path}")
    return {
        "PHOENIX_SECRET": jwt_secret,
        "PHOENIX_ADMIN_SECRET": admin_secret,
    }


def _service_environment(spec: ServiceSpec, root: Path) -> dict[str, str]:
    environment = {
        name: os.environ[name]
        for name in _SAFE_ENVIRONMENT_NAMES
        if name in os.environ
    }
    environment.update(spec.environment)
    if spec.name == "phoenix":
        environment.update(_phoenix_secrets(root))
    return environment


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _observed_version(spec: ServiceSpec) -> str | None:
    environment = {
        name: os.environ[name]
        for name in _SAFE_ENVIRONMENT_NAMES
        if name in os.environ
    }
    if spec.name == "temporal":
        argv = (str(spec.executable), "--version")
    elif spec.name == "phoenix":
        python = spec.executable.resolve().parent / "python"
        argv = (
            str(python),
            "-c",
            "from importlib.metadata import version; print(version('arize-phoenix'))",
        )
    else:
        return None
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            timeout=10,
            check=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = completed.stdout.strip()
    if spec.name == "temporal" and output.startswith("temporal version "):
        return output.split()[2]
    return output or None


def _validate_installation(spec: ServiceSpec) -> tuple[str, str]:
    if not spec.executable.is_file() or not os.access(spec.executable, os.X_OK):
        raise RuntimeError(f"missing executable: {spec.executable}")
    executable_sha256 = _sha256_file(spec.executable.resolve())
    if (
        spec.expected_executable_sha256 is not None
        and executable_sha256 != spec.expected_executable_sha256
    ):
        raise RuntimeError(
            f"{spec.name} executable SHA-256 drift: {executable_sha256}"
        )
    observed_version = _observed_version(spec)
    if observed_version != spec.expected_version:
        raise RuntimeError(
            f"{spec.name} version drift: expected {spec.expected_version}, "
            f"observed {observed_version!r}"
        )
    return observed_version, executable_sha256


def _process_identity(pid: int) -> ProcessIdentity | None:
    if pid <= 0:
        return None
    proc_root = Path("/proc") / str(pid)
    try:
        fields = (proc_root / "stat").read_text(encoding="utf-8").split()
        cmdline = tuple(
            value.decode("utf-8", errors="replace")
            for value in (proc_root / "cmdline").read_bytes().split(b"\0")
            if value
        )
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None
    if len(fields) < 22 or not cmdline:
        return None
    return ProcessIdentity(pid=pid, start_ticks=int(fields[21]), cmdline=cmdline)


def _record_path(root: Path, service: str) -> Path:
    return root / "run" / f"{service}.json"


def _load_record(root: Path, service: str) -> dict[str, object] | None:
    path = _record_path(root, service)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"invalid": True}
    if not isinstance(value, dict):
        return {"invalid": True}
    return value


def _write_record(root: Path, service: str, value: Mapping[str, object]) -> None:
    directory = root / "run"
    directory.mkdir(parents=True, exist_ok=True)
    path = _record_path(root, service)
    temporary = path.with_suffix(".json.new")
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _remove_record(root: Path, service: str) -> None:
    try:
        _record_path(root, service).unlink()
    except FileNotFoundError:
        pass


def _tracked_identity(
    root: Path, spec: ServiceSpec,
) -> tuple[str, ProcessIdentity | None, dict[str, object] | None]:
    record = _load_record(root, spec.name)
    if record is None:
        return "untracked", None, None
    if record.get("invalid") is True:
        return "invalid_record", None, record
    pid = record.get("pid")
    start_ticks = record.get("start_ticks")
    executable_sha256 = record.get("executable_sha256")
    if not isinstance(pid, int) or not isinstance(start_ticks, int):
        return "invalid_record", None, record
    identity = _process_identity(pid)
    if identity is None:
        return "stale_record", None, record
    if identity.start_ticks != start_ticks:
        return "identity_mismatch", identity, record
    if not spec.executable.exists():
        return "executable_missing", identity, record
    if executable_sha256 != _sha256_file(spec.executable.resolve()):
        return "executable_drift", identity, record
    executable_text = str(spec.executable.resolve())
    observed = {str(Path(arg).resolve()) for arg in identity.cmdline if arg.startswith("/")}
    if executable_text not in observed and spec.name not in " ".join(identity.cmdline):
        return "identity_mismatch", identity, record
    return "tracked", identity, record


def _tcp_ready(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ready(url: str, timeout: float = 2.0) -> tuple[bool, int | None]:
    request = Request(url, headers={"User-Agent": "hswm-research-fabric/1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400, response.status
    except URLError:
        return False, None


def _readiness(spec: ServiceSpec) -> dict[str, object]:
    tcp = _tcp_ready(spec.ready_host, spec.ready_port)
    http = None
    status_code = None
    if spec.health_url is not None:
        http, status_code = _http_ready(spec.health_url)
    ready = tcp and (http is not False)
    return {
        "ready": ready,
        "tcp": tcp,
        "http": http,
        "http_status": status_code,
    }


def service_status(root: Path, spec: ServiceSpec) -> dict[str, object]:
    tracking, identity, record = _tracked_identity(root, spec)
    readiness = _readiness(spec)
    if tracking == "tracked" and readiness["ready"]:
        state = "ready"
    elif tracking == "tracked":
        state = "starting_or_unhealthy"
    elif tracking == "untracked" and readiness["ready"]:
        state = "foreign_or_untracked_listener"
    elif tracking == "stale_record":
        state = "stale_record"
    else:
        state = "not_running" if tracking == "untracked" else tracking
    return {
        "service": spec.name,
        "state": state,
        "tracking": tracking,
        "pid": identity.pid if identity is not None else None,
        "ready_host": spec.ready_host,
        "ready_port": spec.ready_port,
        "health_url": spec.health_url,
        "readiness": readiness,
        "responsibility": spec.responsibility,
        "recorded_pid": record.get("pid") if isinstance(record, dict) else None,
    }


def start_service(
    root: Path, spec: ServiceSpec, *, timeout_seconds: float = 90.0,
) -> dict[str, object]:
    current = service_status(root, spec)
    if current["state"] == "ready":
        return current
    if current["state"] == "foreign_or_untracked_listener":
        raise RuntimeError(
            f"{spec.name} port is owned by an untracked process; refusing to replace it"
        )
    tracking, _, _ = _tracked_identity(root, spec)
    if tracking in {"stale_record", "invalid_record"}:
        _remove_record(root, spec.name)
    elif tracking not in {"untracked"}:
        raise RuntimeError(f"{spec.name} has unsafe process state {tracking!r}")
    observed_version, executable_sha256 = _validate_installation(spec)

    for directory in (root / spec.name, root / "logs", root / "run"):
        directory.mkdir(parents=True, exist_ok=True)
    log_path = root / "logs" / f"{spec.name}.log"
    with log_path.open("ab", buffering=0) as log_stream:
        process = subprocess.Popen(
            (str(spec.executable), *spec.argv),
            stdin=subprocess.DEVNULL,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            env=_service_environment(spec, root),
            start_new_session=True,
            close_fds=True,
        )
    identity = _process_identity(process.pid)
    if identity is None:
        raise RuntimeError(f"{spec.name} exited before its identity could be recorded")
    record = {
        "schema": PROCESS_SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "service": spec.name,
        "pid": identity.pid,
        "start_ticks": identity.start_ticks,
        "executable": str(spec.executable.resolve()),
        "executable_sha256": executable_sha256,
        "version": observed_version,
        "public_argv": list(spec.argv),
        "log_path": str(log_path),
        "started_unix_ns": time.time_ns(),
    }
    _write_record(root, spec.name, record)

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = service_status(root, spec)
        if status["state"] == "ready":
            return status
        if _process_identity(process.pid) is None:
            raise RuntimeError(f"{spec.name} exited during startup; inspect {log_path}")
        time.sleep(0.25)
    stop_service(root, spec)
    raise RuntimeError(f"{spec.name} did not become ready within {timeout_seconds}s")


def stop_service(
    root: Path, spec: ServiceSpec, *, grace_seconds: float = 10.0,
) -> dict[str, object]:
    tracking, identity, _ = _tracked_identity(root, spec)
    if tracking in {"untracked", "stale_record", "invalid_record"}:
        _remove_record(root, spec.name)
        return service_status(root, spec)
    if tracking != "tracked" or identity is None:
        raise RuntimeError(
            f"refusing to signal {spec.name} with unsafe process state {tracking!r}"
        )
    os.killpg(identity.pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline and _process_identity(identity.pid) is not None:
        time.sleep(0.1)
    if _process_identity(identity.pid) is not None:
        os.killpg(identity.pid, signal.SIGKILL)
    _remove_record(root, spec.name)
    return service_status(root, spec)


def _endpoint_status(check: EndpointCheck) -> dict[str, object]:
    tcp = _tcp_ready(check.host, check.port)
    http = None
    status_code = None
    if check.health_url is not None:
        http, status_code = _http_ready(check.health_url)
    return {
        "name": check.name,
        "endpoint": f"{check.host}:{check.port}",
        "tcp": tcp,
        "http": http,
        "http_status": status_code,
        "ready": tcp and (http is not False),
        "responsibility": check.responsibility,
    }


def doctor(root: Path, specs: Mapping[str, ServiceSpec]) -> dict[str, object]:
    dependencies = (
        EndpointCheck(
            "openobserve-canonical",
            "192.168.0.27",
            5081,
            "generic operational log and trace projection",
            "http://192.168.0.27:5081/healthz",
        ),
        EndpointCheck(
            "neo4j-canonical-kg",
            "192.168.0.25",
            7687,
            "bounded canonical-KG projection; not HSWM state authority",
        ),
        EndpointCheck(
            "neo4j-code-kg",
            "192.168.0.19",
            7687,
            "bounded code-graph projection",
        ),
        EndpointCheck(
            "grafana-mcp",
            "192.168.0.29",
            9090,
            "bounded observability query interface",
        ),
    )
    services = [service_status(root, specs[name]) for name in sorted(specs)]
    executables = []
    for name in sorted(specs):
        executable = specs[name].executable
        observed_version = _observed_version(specs[name]) if executable.is_file() else None
        executable_sha256 = (
            _sha256_file(executable.resolve()) if executable.is_file() else None
        )
        executables.append(
            {
                "service": name,
                "path": str(executable),
                "present": executable.is_file() and os.access(executable, os.X_OK),
                "sha256": executable_sha256,
                "expected_sha256": specs[name].expected_executable_sha256,
                "sha256_match": (
                    specs[name].expected_executable_sha256 is None
                    or executable_sha256 == specs[name].expected_executable_sha256
                ),
                "version": observed_version,
                "expected_version": specs[name].expected_version,
                "version_match": observed_version == specs[name].expected_version,
            }
        )
    endpoints = [_endpoint_status(check) for check in dependencies]
    ready = (
        all(item["state"] == "ready" for item in services)
        and all(item["ready"] for item in endpoints)
        and all(
            item["version_match"] and item["sha256_match"]
            for item in executables
        )
    )
    return {
        "schema": STATUS_SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "observed_unix_ns": time.time_ns(),
        "state_root": str(root),
        "ready": ready,
        "services": services,
        "executables": executables,
        "existing_proxmox_dependencies": endpoints,
    }


def _selected_specs(
    specs: Mapping[str, ServiceSpec], selected: str,
) -> Iterable[ServiceSpec]:
    if selected == "all":
        return tuple(specs[name] for name in sorted(specs))
    return (specs[selected],)


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operate the loopback-only HSWM research-development fabric."
    )
    parser.add_argument("--state-dir", help="Override the user state directory.")
    parser.add_argument(
        "command", choices=("start", "stop", "status", "doctor")
    )
    parser.add_argument(
        "--service", choices=("all", "phoenix", "temporal"), default="all"
    )
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args(argv)
    root = _state_root(args.state_dir)
    specs = service_specs(root)

    try:
        if args.command == "start":
            result = [
                start_service(root, spec, timeout_seconds=args.timeout)
                for spec in _selected_specs(specs, args.service)
            ]
        elif args.command == "stop":
            result = [
                stop_service(root, spec)
                for spec in reversed(tuple(_selected_specs(specs, args.service)))
            ]
        elif args.command == "status":
            result = [
                service_status(root, spec)
                for spec in _selected_specs(specs, args.service)
            ]
        else:
            report = doctor(root, specs)
            _emit(report)
            return 0 if report["ready"] else 1
    except (OSError, RuntimeError, ValueError) as error:
        _emit(
            {
                "schema": STATUS_SCHEMA,
                "claim_boundary": CLAIM_BOUNDARY,
                "error": f"{type(error).__name__}: {error}",
            }
        )
        return 1

    envelope = {
        "schema": STATUS_SCHEMA,
        "claim_boundary": CLAIM_BOUNDARY,
        "state_root": str(root),
        "services": result,
    }
    _emit(envelope)
    if args.command == "stop":
        return 0
    return 0 if all(item["state"] == "ready" for item in result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
