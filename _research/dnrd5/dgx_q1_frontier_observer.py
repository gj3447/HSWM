"""Read-only DGX adapter for the nonauthorizing Q1 control snapshot.

The adapter has a closed subprocess table and performs only loopback HTTP GETs
to ``/version``, ``/v1/models``, and ``/metrics``. It has no POST, chat,
completion, or provider-dispatch path. Raw command lines, container IDs,
cgroups, hostnames, HTTP bodies, and exceptions are parsed transiently; the
receipt retains only allowlisted values and identity hashes.

This adapter deliberately reports no host-owned lease. A real launcher must
own an allocation from launch through teardown and inject that evidence at
request boundaries. A snapshot of a pre-existing service cannot do so.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from _research.dnrd5.canonical_json import canonical_sha256
from _research.dnrd5.dgx_q1_frontier_preflight import (
    DgxQ1FrontierReceipt,
    Q1FrontierExpectation,
    ZERO_SHA256,
    observe_dgx_q1_frontier_preflight,
)


_MAX_READ_BYTES = 1_048_576
_MAX_COMMAND_BYTES = 4_194_304
_DIGEST = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ARGUMENT = re.compile(r"^[A-Za-z0-9_.:/@-]{1,256}$")
_METRIC = re.compile(
    r"^(?P<name>"
    r"vllm:num_requests_running|"
    r"vllm:prefix_cache_hits(?:_total)?|"
    r"vllm:prefix_cache_queries(?:_total)?|"
    r"vllm_prefix_cache_hits(?:_total)?|"
    r"vllm_prefix_cache_queries(?:_total)?"
    r")(?:\{[^}\n]*\})?\s+(?P<value>[^\s]+)$"
)
_FLAG_NAMES = frozenset(
    {
        "served-model-name",
        "model",
        "revision",
        "max-num-seqs",
        "port",
        "enable-prefix-caching",
        "no-enable-prefix-caching",
        "disable-prefix-caching",
    }
)
_BOOLEAN_FLAGS = frozenset(
    {
        "enable-prefix-caching",
        "no-enable-prefix-caching",
        "disable-prefix-caching",
    }
)
COMMAND_FACTS = frozenset(
    {
        "docker_ps",
        "docker_inspect",
        "docker_repo_digests",
        "docker_batch_invariant",
        "gpu",
        "compute_pids",
        "cgroup",
        "cmdline",
        "listeners",
        "host",
        "dmi_vendor",
        "dmi_product",
        "dmi_version",
        "os_release",
        "kernel",
        "architecture",
        "docker_version",
    }
)
HTTP_PATHS = frozenset({"/version", "/v1/models", "/metrics"})


class ObserverFailure(RuntimeError):
    """A finite safe observation could not be completed."""


@dataclass(frozen=True, slots=True)
class ReadOnlyCommandReader:
    """Run only the fixed, argument-vector command projections below."""

    def __call__(self, fact: str, argument: str | None = None) -> bytes:
        if fact not in COMMAND_FACTS:
            raise ObserverFailure("command fact is not allowlisted")
        if fact == "docker_ps":
            argv = ("docker", "ps", "--format", "{{.ID}}")
        elif fact == "docker_inspect":
            argv = (
                "docker",
                "inspect",
                "--format",
                "{{.Id}}|{{.Image}}|{{.Config.Image}}|{{.State.Pid}}|"
                "{{.State.StartedAt}}|{{json .NetworkSettings.Ports}}",
                _bounded_argument(argument),
            )
        elif fact == "docker_repo_digests":
            argv = (
                "docker",
                "image",
                "inspect",
                "--format",
                '{{join .RepoDigests "\\n"}}',
                _bounded_argument(argument),
            )
        elif fact == "docker_batch_invariant":
            argv = (
                "docker",
                "inspect",
                "--format",
                '{{range .Config.Env}}{{if eq . "VLLM_BATCH_INVARIANT=1"}}1'
                "{{end}}{{end}}",
                _bounded_argument(argument),
            )
        elif fact == "gpu":
            argv = (
                "nvidia-smi",
                "--query-gpu=name,uuid,driver_version,mig.mode.current",
                "--format=csv,noheader",
            )
        elif fact == "compute_pids":
            argv = (
                "nvidia-smi",
                "--query-compute-apps=pid",
                "--format=csv,noheader",
            )
        elif fact == "cgroup":
            argv = ("cat", f"/proc/{_positive_pid(argument)}/cgroup")
        elif fact == "cmdline":
            argv = ("cat", f"/proc/{_positive_pid(argument)}/cmdline")
        elif fact == "listeners":
            argv = ("ss", "-ltnH")
        elif fact == "dmi_vendor":
            argv = ("cat", "/sys/class/dmi/id/sys_vendor")
        elif fact == "dmi_product":
            argv = ("cat", "/sys/class/dmi/id/product_name")
        elif fact == "dmi_version":
            argv = ("cat", "/sys/class/dmi/id/product_version")
        elif fact == "os_release":
            argv = ("cat", "/etc/os-release")
        elif fact == "kernel":
            argv = ("uname", "-r")
        elif fact == "architecture":
            argv = ("uname", "-m")
        elif fact == "docker_version":
            argv = ("docker", "version", "--format", "{{.Server.Version}}")
        else:
            argv = ("hostname",)
        try:
            result = subprocess.run(
                argv,
                check=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=10,
            ).stdout
        except (OSError, subprocess.SubprocessError) as error:
            raise ObserverFailure("allowlisted read command failed") from error
        if len(result) > _MAX_COMMAND_BYTES:
            raise ObserverFailure("allowlisted command output exceeded bound")
        return result


def _positive_pid(value: str | None) -> str:
    if value is None or not value.isdigit() or int(value) <= 0:
        raise ObserverFailure("invalid process identity")
    return value


def _bounded_argument(value: str | None) -> str:
    if value is None or _SAFE_ARGUMENT.fullmatch(value) is None:
        raise ObserverFailure("invalid bounded command argument")
    return value


def _loopback_get(url: str) -> bytes:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in HTTP_PATHS
        or parsed.port is None
    ):
        raise ObserverFailure("HTTP read is not an allowlisted loopback path")
    try:
        with urlopen(
            Request(url, method="GET", headers={"Accept": "application/json,text/plain"}),
            timeout=5,
        ) as response:
            if response.status != 200:
                raise ObserverFailure("loopback status is not 200")
            raw = response.read(_MAX_READ_BYTES + 1)
    except Exception as error:
        if isinstance(error, ObserverFailure):
            raise
        raise ObserverFailure("loopback GET failed") from error
    if len(raw) > _MAX_READ_BYTES:
        raise ObserverFailure("loopback response exceeded bound")
    return raw


def _reject_constant(_: str) -> None:
    raise ObserverFailure("non-finite JSON number is forbidden")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ObserverFailure("duplicate JSON key is forbidden")
        result[key] = value
    return result


def _json(raw: bytes) -> Any:
    if len(raw) > _MAX_READ_BYTES:
        raise ObserverFailure("JSON response exceeded bound")
    try:
        return json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except ObserverFailure:
        raise
    except Exception as error:
        raise ObserverFailure("allowlisted JSON response is malformed") from error


def _sha(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _one_line(raw: bytes, label: str) -> str:
    try:
        lines = raw.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError as error:
        raise ObserverFailure(f"{label} is not UTF-8") from error
    if len(lines) != 1 or not lines[0] or len(lines[0].encode("utf-8")) > 4096:
        raise ObserverFailure(f"{label} is not bounded one-line text")
    return lines[0]


def _os_identity(raw: bytes) -> tuple[str, str]:
    try:
        lines = raw.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError as error:
        raise ObserverFailure("OS release projection is not UTF-8") from error
    values: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key not in {"ID", "VERSION_ID"}:
            continue
        if key in values:
            raise ObserverFailure("OS release key is duplicated")
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        if not value or len(value.encode("utf-8")) > 256:
            raise ObserverFailure("OS release value is invalid")
        values[key] = value
    if set(values) != {"ID", "VERSION_ID"}:
        raise ObserverFailure("OS identity is unavailable")
    return values["ID"], values["VERSION_ID"]


def _normalize_host(value: str) -> str:
    host = value.strip().strip("[]")
    if host in {"", "*", "0.0.0.0"}:
        return "0.0.0.0"
    if host == "::":
        return "::"
    if host in {"127.0.0.1", "::1"}:
        return host
    return "NON_LOOPBACK_OTHER"


def _parse_inspect(raw: bytes) -> dict[str, Any]:
    parts = raw.decode("utf-8", "strict").rstrip("\n").split("|", 5)
    if (
        len(parts) != 6
        or _HEX64.fullmatch(parts[0]) is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", parts[1]) is None
        or not parts[2]
        or not parts[3].isdigit()
        or int(parts[3]) <= 0
        or not parts[4]
    ):
        raise ObserverFailure("Docker inspect projection drifted")
    ports = _json(parts[5].encode("utf-8"))
    if type(ports) is not dict:
        raise ObserverFailure("Docker port projection drifted")
    bindings: set[tuple[str, int]] = set()
    for rows in ports.values():
        if rows is None:
            continue
        if type(rows) is not list:
            raise ObserverFailure("Docker binding projection drifted")
        for row in rows:
            if (
                type(row) is not dict
                or set(row) != {"HostIp", "HostPort"}
                or type(row["HostIp"]) is not str
                or type(row["HostPort"]) is not str
                or not row["HostPort"].isdigit()
                or not 1 <= int(row["HostPort"]) <= 65535
            ):
                raise ObserverFailure("Docker host binding drifted")
            bindings.add((_normalize_host(row["HostIp"]), int(row["HostPort"])))
    return {
        "container_id": parts[0],
        "container_id_sha256": _sha(parts[0]),
        "image_id": parts[1],
        "configured_image_reference": parts[2],
        "pid": int(parts[3]),
        "container_started_sha256": _sha(parts[4]),
        "published_bindings": sorted(bindings),
    }


def _tokens(raw: bytes) -> list[str]:
    if not raw or len(raw) > _MAX_READ_BYTES:
        raise ObserverFailure("cmdline is empty or exceeded bound")
    out: list[str] = []
    for token in raw.rstrip(b"\0").split(b"\0"):
        try:
            decoded = token.decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise ObserverFailure("cmdline token is not UTF-8") from error
        if not decoded or len(decoded.encode("utf-8")) > 4096:
            raise ObserverFailure("cmdline token is invalid")
        out.append(decoded)
    return out


def _is_vllm_serve(tokens: list[str]) -> bool:
    for index, token in enumerate(tokens[:-1]):
        if token.rsplit("/", 1)[-1] == "vllm" and tokens[index + 1] == "serve":
            return True
    return False


def _parse_flags(tokens: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            index += 1
            continue
        body = token[2:]
        if "=" in body:
            name, value = body.split("=", 1)
            if name in _BOOLEAN_FLAGS:
                raise ObserverFailure("boolean serving flag may not take a value")
            consumed = 1
        else:
            name = body
            if name in _BOOLEAN_FLAGS:
                value, consumed = "1", 1
            elif name in _FLAG_NAMES:
                if index + 1 >= len(tokens) or tokens[index + 1].startswith("--"):
                    raise ObserverFailure("serving flag lacks a value")
                value, consumed = tokens[index + 1], 2
            else:
                index += 1
                continue
        if name in _FLAG_NAMES:
            if name in result or not value or len(value.encode("utf-8")) > 4096:
                raise ObserverFailure("serving flag duplicated or invalid")
            result[name] = value
        index += consumed
    return result


def _prefix_state(flags: dict[str, str]) -> str:
    enabled = "enable-prefix-caching" in flags
    disabled = bool(
        {"no-enable-prefix-caching", "disable-prefix-caching"} & set(flags)
    )
    if enabled and disabled:
        raise ObserverFailure("contradictory prefix-cache flags")
    if enabled:
        return "ENABLED"
    if disabled:
        return "DISABLED"
    return "UNDECLARED"


def _metric_integer(value: str) -> int:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ObserverFailure("vLLM metric is not numeric") from error
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        raise ObserverFailure("vLLM metric is not a nonnegative integer")
    return int(parsed)


def _metrics(raw: bytes) -> dict[str, int]:
    if len(raw) > _MAX_READ_BYTES:
        raise ObserverFailure("metrics response exceeded bound")
    values: dict[str, list[int]] = {
        "running_requests": [],
        "prefix_cache_hits": [],
        "prefix_cache_queries": [],
    }
    try:
        lines = raw.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError as error:
        raise ObserverFailure("metrics response is not UTF-8") from error
    for line in lines:
        matched = _METRIC.fullmatch(line.strip())
        if matched is None:
            continue
        name = matched.group("name")
        value = _metric_integer(matched.group("value"))
        if "num_requests_running" in name:
            values["running_requests"].append(value)
        elif "hits" in name:
            values["prefix_cache_hits"].append(value)
        else:
            values["prefix_cache_queries"].append(value)
    if any(not rows for rows in values.values()):
        raise ObserverFailure("required vLLM metric is unavailable")
    return {name: sum(rows) for name, rows in values.items()}


def _model_identity(
    version_raw: bytes, models_raw: bytes
) -> tuple[str, str, str]:
    version = _json(version_raw)
    models = _json(models_raw)
    if (
        type(version) is not dict
        or set(version) != {"version"}
        or type(version["version"]) is not str
        or type(models) is not dict
        or type(models.get("data")) is not list
        or len(models["data"]) != 1
        or type(models["data"][0]) is not dict
    ):
        raise ObserverFailure("model/version response shape drifted")
    model = models["data"][0].get("id")
    root = models["data"][0].get("root")
    if type(model) is not str or not model or type(root) is not str or not root:
        raise ObserverFailure("served model identity is unavailable")
    return version["version"], model, root


def _cgroup(raw: bytes) -> tuple[str, str]:
    try:
        lines = [line for line in raw.decode("utf-8", "strict").splitlines() if line]
    except UnicodeDecodeError as error:
        raise ObserverFailure("cgroup projection is not UTF-8") from error
    unified = [line for line in lines if line.startswith("0::")]
    if len(unified) != 1 or len(unified[0]) > 4096:
        raise ObserverFailure("unified cgroup identity is unavailable")
    identity = unified[0]
    return identity, _sha(identity)


def _compute_cgroups(
    reader: Callable[[str, str | None], bytes]
) -> list[str]:
    try:
        lines = reader("compute_pids", None).decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError as error:
        raise ObserverFailure("compute PID projection is not UTF-8") from error
    pids = [line.strip() for line in lines if line.strip()]
    if any(not pid.isdigit() or int(pid) <= 0 for pid in pids):
        raise ObserverFailure("compute PID projection drifted")
    return sorted(_cgroup(reader("cgroup", pid))[1] for pid in pids)


def _listener_hosts(raw: bytes, port: int) -> list[str]:
    hosts: set[str] = set()
    try:
        lines = raw.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError as error:
        raise ObserverFailure("listener projection is not UTF-8") from error
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            continue
        local = fields[3]
        if ":" not in local:
            continue
        host, raw_port = local.rsplit(":", 1)
        if raw_port.isdigit() and int(raw_port) == port:
            hosts.add(_normalize_host(host))
    if not hosts:
        raise ObserverFailure("target inference listener is unavailable")
    return sorted(hosts)


def _repo_digest(raw: bytes, expected: str) -> str:
    try:
        rows = sorted(
            {
                line.strip()
                for line in raw.decode("utf-8", "strict").splitlines()
                if line.strip()
            }
        )
    except UnicodeDecodeError as error:
        raise ObserverFailure("repository digest projection is not UTF-8") from error
    valid = [row for row in rows if _DIGEST.fullmatch(row)]
    if expected in valid:
        return expected
    if not valid:
        raise ObserverFailure("immutable repository digest is unavailable")
    return valid[0]


def _group(
    inspect: dict[str, Any],
    flags: dict[str, str],
    *,
    cgroup_sha256: str,
    repo_digest: str,
    batch_invariant_env_declared: bool,
    http_reader: Callable[[str], bytes],
) -> dict[str, Any]:
    ports = sorted({port for _, port in inspect["published_bindings"]})
    if len(ports) != 1:
        raise ObserverFailure("vLLM published endpoint is ambiguous")
    port = ports[0]
    version, served_model, model_root = _model_identity(
        http_reader(f"http://127.0.0.1:{port}/version"),
        http_reader(f"http://127.0.0.1:{port}/v1/models"),
    )
    if "served-model-name" in flags and flags["served-model-name"] != served_model:
        raise ObserverFailure("served-model flag and API identity differ")
    if "model" in flags and flags["model"] != model_root:
        raise ObserverFailure("model flag and API root differ")
    max_num_seqs = flags.get("max-num-seqs", "0")
    if not max_num_seqs.isdigit():
        raise ObserverFailure("max-num-seqs is not an integer")
    return {
        "cgroup_sha256": cgroup_sha256,
        "container_id_sha256": inspect["container_id_sha256"],
        "container_started_sha256": inspect["container_started_sha256"],
        "repo_digest": repo_digest,
        "engine": "vllm",
        "vllm_version": version,
        "served_model": served_model,
        "model_revision": flags.get("revision", "UNPINNED"),
        "model_root": model_root,
        "endpoint_port": port,
        "max_num_seqs": int(max_num_seqs),
        "prefix_cache": _prefix_state(flags),
        # An environment declaration is not effective-config or model-support
        # evidence. A future launcher must qualify those separately.
        "batch_invariance": (
            "ENV_DECLARED" if batch_invariant_env_declared else "NOT_DECLARED"
        ),
    }


def _inspect_stable(
    before: dict[str, Any],
    after: dict[str, Any],
    before_cgroup_sha256: str,
    after_cgroup_sha256: str,
) -> bool:
    keys = {
        "container_id",
        "container_id_sha256",
        "image_id",
        "configured_image_reference",
        "pid",
        "container_started_sha256",
        "published_bindings",
    }
    return (
        all(before[key] == after[key] for key in keys)
        and before_cgroup_sha256 == after_cgroup_sha256
    )


def observe_frontier(
    expectation: Q1FrontierExpectation,
    *,
    command_reader: Callable[[str, str | None], bytes],
    http_reader: Callable[[str], bytes],
) -> DgxQ1FrontierReceipt:
    """Observe a bounded interval; any failure becomes a sanitized refusal."""
    try:
        if expectation.endpoint_host != "127.0.0.1":
            raise ObserverFailure(
                "this adapter supports only an exact IPv4 loopback endpoint"
            )
        container_ids = [
            line.strip()
            for line in command_reader("docker_ps", None)
            .decode("utf-8", "strict")
            .splitlines()
            if line.strip()
        ]
        if not container_ids or any(_SAFE_ARGUMENT.fullmatch(row) is None for row in container_ids):
            raise ObserverFailure("running container inventory is unavailable")

        groups: list[dict[str, Any]] = []
        inspect_by_hash: dict[str, dict[str, Any]] = {}
        cgroup_by_hash: dict[str, str] = {}
        for container_id in container_ids:
            inspect = _parse_inspect(command_reader("docker_inspect", container_id))
            tokens = _tokens(command_reader("cmdline", str(inspect["pid"])))
            if not _is_vllm_serve(tokens):
                continue
            flags = _parse_flags(tokens)
            _, cgroup_sha256 = _cgroup(
                command_reader("cgroup", str(inspect["pid"]))
            )
            repo_digest = _repo_digest(
                command_reader("docker_repo_digests", inspect["image_id"]),
                expectation.configured_image_reference,
            )
            group = _group(
                inspect,
                flags,
                cgroup_sha256=cgroup_sha256,
                repo_digest=repo_digest,
                batch_invariant_env_declared=command_reader(
                    "docker_batch_invariant", inspect["container_id"]
                ).strip()
                == b"1",
                http_reader=http_reader,
            )
            groups.append(group)
            inspect_by_hash[inspect["container_id_sha256"]] = inspect
            cgroup_by_hash[inspect["container_id_sha256"]] = cgroup_sha256
        groups.sort(key=lambda row: row["container_id_sha256"])

        targets = [
            row
            for row in groups
            if row["served_model"] == expectation.served_model
            and row["model_root"] == expectation.model_root
            and row["endpoint_port"] == expectation.endpoint_port
        ]
        if len(targets) != 1:
            raise ObserverFailure("target vLLM process group is not unique")
        target = targets[0]
        target_inspect = inspect_by_hash[target["container_id_sha256"]]
        target_cgroup_sha256 = cgroup_by_hash[target["container_id_sha256"]]

        gpu_lines = command_reader("gpu", None).decode("utf-8", "strict").splitlines()
        if len(gpu_lines) != 1:
            raise ObserverFailure("target GPU observation is ambiguous")
        gpu_parts = [part.strip() for part in gpu_lines[0].split(",")]
        if len(gpu_parts) != 4 or any(not part for part in gpu_parts):
            raise ObserverFailure("target GPU identity is unavailable")
        gpu_name, gpu_uuid, driver_version, mig_mode = gpu_parts

        os_id, os_version_id = _os_identity(command_reader("os_release", None))
        platform = {
            "system_vendor": _one_line(
                command_reader("dmi_vendor", None), "DMI system vendor"
            ),
            "product_name": _one_line(
                command_reader("dmi_product", None), "DMI product name"
            ),
            "product_version": _one_line(
                command_reader("dmi_version", None), "DMI product version"
            ),
            "os_id": os_id,
            "os_version_id": os_version_id,
            "kernel_release": _one_line(
                command_reader("kernel", None), "kernel release"
            ),
            "architecture": _one_line(
                command_reader("architecture", None), "architecture"
            ),
            "docker_server_version": _one_line(
                command_reader("docker_version", None), "Docker server version"
            ),
        }

        compute_before = _compute_cgroups(command_reader)
        listener_hosts_before = _listener_hosts(
            command_reader("listeners", None), expectation.endpoint_port
        )
        published_hosts = sorted(
            {
                host
                for host, port in target_inspect["published_bindings"]
                if port == expectation.endpoint_port
            }
        )
        if published_hosts != listener_hosts_before:
            raise ObserverFailure("Docker publication and host listener differ")

        pre_stats = _metrics(
            http_reader(f"http://127.0.0.1:{expectation.endpoint_port}/metrics")
        )
        post_stats = _metrics(
            http_reader(f"http://127.0.0.1:{expectation.endpoint_port}/metrics")
        )

        compute_after = _compute_cgroups(command_reader)
        listener_hosts_after = _listener_hosts(
            command_reader("listeners", None), expectation.endpoint_port
        )
        target_after = _parse_inspect(
            command_reader("docker_inspect", target_inspect["container_id"])
        )
        _, target_cgroup_after = _cgroup(
            command_reader("cgroup", str(target_after["pid"]))
        )

        target_count = min(
            compute_before.count(target_cgroup_sha256),
            compute_after.count(target_cgroup_sha256),
        )
        foreign = sorted(
            {
                digest
                for digest in compute_before + compute_after
                if digest != target_cgroup_sha256
            }
        )
        container_identity_stable = _inspect_stable(
            target_inspect,
            target_after,
            target_cgroup_sha256,
            target_cgroup_after,
        )
        listeners_stable = listener_hosts_before == listener_hosts_after
        compute_stable = compute_before == compute_after

        listeners = [
            {
                "host": host,
                "port": expectation.endpoint_port,
                # ss -ltnH and Docker publication do not bind socket inode to
                # PID/cgroup, so this adapter must not synthesize ownership.
                "owner": "UNBOUND_PUBLISHED_PORT",
            }
            for host in listener_hosts_before
        ]
        facts: dict[str, dict[str, Any]] = {
            "host": {
                "hostname_sha256": _sha(
                    _one_line(command_reader("host", None), "hostname")
                ),
                "platform": platform,
                "platform_sha256": canonical_sha256(platform),
            },
            "gpu": {
                "name": gpu_name,
                "uuid": gpu_uuid,
                "uuid_sha256": _sha(gpu_uuid),
                "driver_version": driver_version,
                "mig_mode": mig_mode,
                "target_cgroup_compute_process_count": target_count,
                "foreign_compute_cgroup_sha256s": foreign,
                "compute_cgroup_set_stable": compute_stable,
                # Cgroup equality alone cannot prove that every same-cgroup
                # CUDA PID belongs to the allowed vLLM worker process tree.
                "compute_process_tree_bound": False,
            },
            "container": {
                "image_id": target_inspect["image_id"],
                "configured_image_reference": target_inspect[
                    "configured_image_reference"
                ],
                "repo_digest": target["repo_digest"],
                "container_id_sha256": target_inspect["container_id_sha256"],
                "container_started_sha256": target_inspect[
                    "container_started_sha256"
                ],
                "cgroup_sha256": target_cgroup_sha256,
                "identity_stable": container_identity_stable,
            },
            # No environment variable, Docker label, or caller assertion can
            # manufacture lease evidence in this snapshot-only adapter.
            "lease": {
                "host_owned": False,
                "active": False,
                "lease_owner_sha256": ZERO_SHA256,
                "lease_id_sha256": ZERO_SHA256,
                "target_cgroup_sha256": ZERO_SHA256,
                "target_gpu_uuid": "UNAVAILABLE",
                "gpu_allocation": "UNAVAILABLE",
                "continuous_boundary": "UNAVAILABLE",
            },
            "inference_processes": {
                "process_group_count": len(groups),
                "process_groups": groups,
            },
            "listeners": {"listeners": listeners, "stable": listeners_stable},
            # The GETs are loopback-only, but their socket is not bound here to
            # a PID/start identity. A future launcher must perform that join.
            "pre_stats": {**pre_stats, "process_identity_bound": False},
            "post_stats": {**post_stats, "process_identity_bound": False},
        }
        return observe_dgx_q1_frontier_preflight(
            expectation,
            command_reader=lambda name: facts[name],
            http_reader=lambda name: facts[name],
        )
    except Exception:
        return observe_dgx_q1_frontier_preflight(
            expectation,
            command_reader=lambda _: {},
            http_reader=lambda _: {},
        )


def _write_exclusive(path: Path, raw: bytes) -> None:
    if not path.parent.is_dir():
        raise ObserverFailure("receipt parent directory is unavailable")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="read-only, nonauthorizing DGX Q1 control snapshot"
    )
    parser.add_argument("--host-platform-sha256", required=True)
    parser.add_argument("--target-gpu-name", required=True)
    parser.add_argument("--target-gpu-uuid", required=True)
    parser.add_argument("--target-driver-version", required=True)
    parser.add_argument("--target-mig-mode", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--configured-image-reference", required=True)
    parser.add_argument("--vllm-version", required=True)
    parser.add_argument("--served-model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--endpoint-host", required=True)
    parser.add_argument("--endpoint-port", required=True, type=int)
    parser.add_argument(
        "--output",
        type=Path,
        help="exclusive receipt path; defaults below HSWM_OUTPUT_ROOT",
    )
    args = parser.parse_args(argv)
    expectation = Q1FrontierExpectation(
        host_platform_sha256=args.host_platform_sha256,
        target_gpu_name=args.target_gpu_name,
        target_gpu_uuid=args.target_gpu_uuid,
        target_driver_version=args.target_driver_version,
        target_mig_mode=args.target_mig_mode,
        image_id=args.image_id,
        configured_image_reference=args.configured_image_reference,
        vllm_version=args.vllm_version,
        served_model=args.served_model,
        model_revision=args.model_revision,
        model_root=args.model_root,
        endpoint_host=args.endpoint_host,
        endpoint_port=args.endpoint_port,
    )
    try:
        output = args.output
        if output is None:
            output_root = os.environ.get("HSWM_OUTPUT_ROOT")
            if not output_root:
                raise ObserverFailure(
                    "--output or the hswm-run HSWM_OUTPUT_ROOT is required"
                )
            output = Path(output_root) / "dgx_q1_frontier_snapshot.json"
        receipt = observe_frontier(
            expectation,
            command_reader=ReadOnlyCommandReader(),
            http_reader=_loopback_get,
        )
        raw = receipt.canonical_bytes()
        _write_exclusive(output, raw)
        print(
            json.dumps(
                {
                    "status": receipt.status,
                    "receipt_sha256": sha256(raw).hexdigest(),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except Exception:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
