"""One-block-at-a-time DGX lease for the QCASE-024 mechanism diagnostic.

This deliberately does not import the Q1 launcher: its schema says 24 x 4
and a single target.  A MI lease owns exactly one fresh server and is useful
both with the real closed argv executor and injected dry-run observers.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import time
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_q1.live_launcher import (
    LaunchRefused, LoopbackUnavailable, SubprocessCommandReader, _get,
    _metric_counters, _text,
)
from _research.dgx_q1.model_snapshot_manifest import build_model_snapshot_manifest

Command = Callable[[tuple[str, ...]], bytes]
HttpGet = Callable[[str], bytes]
_NAME = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
_ENDPOINT = re.compile(r"^http://127\.0\.0\.1:([1-9][0-9]{0,4})/v1/chat/completions$")


@dataclass(frozen=True, slots=True, kw_only=True)
class MiLeaseSpec:
    """All block-specific plumbing is explicit; only async flag changes arm."""
    arm: str
    block_id: str
    endpoint: str
    container_name: str
    lock_path: Path
    model_snapshot: Path
    hf_cache: Path
    compile_cache: Path
    image: str
    image_id: str
    gpu_uuid: str
    served_model: str
    model_revision: str
    max_model_len: int
    gpu_memory_utilization_milli: int
    async_scheduling: bool
    model_repository: str = ""
    snapshot_manifest_raw: bytes = b""


class MiLease:
    """Exclusive lifecycle with no server/cache reuse across blocks."""
    def __init__(self, spec: MiLeaseSpec, command: Command | None = None,
                 http_get: HttpGet | None = None) -> None:
        self.spec, self.command, self.http_get = spec, command or SubprocessCommandReader(), http_get or _get
        self._lock: int | None = None
        self._started = False
        self._argv: tuple[str, ...] = ()
        self._baseline_success = 0
        self._identity: dict[str, Any] = {}

    @property
    def port(self) -> int:
        match = _ENDPOINT.fullmatch(self.spec.endpoint)
        if match is None or not 1 <= int(match.group(1)) <= 65535:
            raise LaunchRefused("MI endpoint must be an exact loopback chat target")
        return int(match.group(1))

    def _cmd(self, argv: tuple[str, ...]) -> str:
        return _text(self.command, argv)

    def _validate(self) -> None:
        s = self.spec
        if (s.arm not in {"ASYNC_ENABLED", "ASYNC_DISABLED"} or s.block_id not in {"B01", "B02"}
                or (s.arm == "ASYNC_ENABLED") != s.async_scheduling
                or _NAME.fullmatch(s.container_name) is None or not s.image or not s.image_id
                or not s.gpu_uuid or not s.served_model or len(s.model_revision) != 40
                or not s.model_repository or not s.snapshot_manifest_raw
                or not 1 <= s.max_model_len or not 100 <= s.gpu_memory_utilization_milli <= 990):
            raise LaunchRefused("MI lease identity/control drifted")
        self.port
        for path in (s.lock_path, s.model_snapshot, s.hf_cache, s.compile_cache):
            if not path.is_absolute() or path.is_symlink():
                raise LaunchRefused("MI lease path must be an absolute non-symlink")

    def _before(self) -> None:
        s = self.spec
        if self._cmd(("docker", "ps", "-q")):
            raise LaunchRefused("MI requires no preexisting running container")
        if self._cmd(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits")):
            raise LaunchRefused("MI requires a quiescent GPU before each block")
        if self._listener_present(self._cmd(("sudo", "-n", "ss", "-ltnpH"))):
            raise LaunchRefused("MI target listener remained before a fresh block")
        for cache in (s.hf_cache, s.compile_cache):
            if not cache.is_dir() or cache.is_symlink() or any(cache.iterdir()):
                raise LaunchRefused("MI per-block cache is absent, linked, or not fresh")
        if not s.model_snapshot.is_dir() or s.model_snapshot.is_symlink():
            raise LaunchRefused("MI pinned model snapshot is unavailable")
        try:
            rebuilt=build_model_snapshot_manifest(s.model_snapshot.parents[2],repository=s.model_repository,revision=s.model_revision)
            if canonical_bytes(rebuilt) != s.snapshot_manifest_raw:
                raise LaunchRefused("MI local snapshot manifest drifted")
        except LaunchRefused: raise
        except Exception as error: raise LaunchRefused("MI local snapshot manifest cannot be rebuilt") from error

    def _listener_present(self, rows: str) -> bool:
        return any(line.split()[:1] == ["LISTEN"] and f"127.0.0.1:{self.port}" in line.split() for line in rows.splitlines())

    def _server_argv(self) -> tuple[str, ...]:
        s = self.spec; milli = s.gpu_memory_utilization_milli
        # Both boolean spellings are intentional and recorded.  This makes the
        # arm contrast explicit rather than treating omission as a control.
        async_flag = "--async-scheduling" if s.async_scheduling else "--no-async-scheduling"
        return ("--model", f"/model-repository/snapshots/{s.model_revision}",
                "--served-model-name", s.served_model, "--host", "0.0.0.0", "--port", "8000",
                "--max-num-seqs", "1", "--no-enable-prefix-caching", "--max-model-len", str(s.max_model_len),
                "--gpu-memory-utilization", f"{milli // 1000}.{milli % 1000:03d}",
                "--generation-config", "vllm", "--seed", "0", "--enforce-eager", "--language-model-only",
                "--max-logprobs", "20", "--logprobs-mode", "processed_logprobs", async_flag)

    def _launch(self) -> None:
        s = self.spec; self._argv = self._server_argv()
        env = ("HF_HOME=/cache/huggingface", "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub",
               "VLLM_CACHE_ROOT=/cache/compile/vllm", "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor",
               "TRITON_CACHE_DIR=/cache/compile/triton", "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1",
               "VLLM_ENABLE_V1_MULTIPROCESSING=0", "PYTHONHASHSEED=0", "CUBLAS_WORKSPACE_CONFIG=:4096:8")
        argv: list[str] = ["docker", "run", "-d", "--name", s.container_name, "--restart", "no",
            "--network", "bridge", "--ipc", "private", "-p", f"127.0.0.1:{self.port}:8000", "--gpus", f"device={s.gpu_uuid}",
            "--mount", f"type=bind,src={s.model_snapshot.parents[1]},dst=/model-repository,readonly",
            "--mount", f"type=bind,src={s.hf_cache},dst=/cache/huggingface",
            "--mount", f"type=bind,src={s.compile_cache},dst=/cache/compile"]
        for value in env: argv += ["-e", value]
        argv += [s.image, *self._argv]
        raw_id = self.command(tuple(argv)).strip()
        # Bind the server incarnation before the first readiness probe.  The
        # raw docker-run output alone is insufficient: the observed ID, start
        # time, cgroup and net namespace are all carried into every boundary.
        if not raw_id or len(raw_id) > 128:
            raise LaunchRefused("MI launch did not return a bounded container identity")
        # From this point a container exists; an inspect/boundary failure must
        # flow through close() and remove it before the exclusive lock releases.
        self._started = True
        try:
            document = json.loads(self.command(("docker", "inspect", s.container_name)).decode("utf-8", errors="strict"))
            item = document[0]; pid = item["State"]["Pid"]; started = item["State"]["StartedAt"]
            cgroup = self.command(("cat", f"/proc/{pid}/cgroup"))
            netns = self.command(("docker", "exec", s.container_name, "readlink", "/proc/1/ns/net"))
            if not isinstance(item.get("Id"), str) or item["Id"].encode()!=raw_id or not isinstance(pid, int) or pid <= 0 or not isinstance(started, str) or not started or not netns.strip(): raise ValueError
            self._identity = {"container_id_sha256": sha256(item["Id"].encode()).hexdigest(),
                "container_start_sha256": sha256(started.encode()).hexdigest(), "cgroup_sha256": sha256(cgroup).hexdigest(),
                "network_namespace_sha256": sha256(netns).hexdigest(), "server_argv_sha256": sha256("\0".join(self._argv).encode()).hexdigest()}
        except Exception as e:
            raise LaunchRefused("MI immutable server identity observation failed") from e

    def attest(self, phase: str, completed: int) -> bytes:
        if not self._started or phase not in {"STARTUP", "PRE", "POST", "FINAL"} or not 0 <= completed <= 4:
            raise LaunchRefused("MI attestation phase/lease state drifted")
        try:
            item=json.loads(self.command(("docker","inspect",self.spec.container_name)).decode("utf-8",errors="strict"))[0]
            state=item["State"]; config=item["Config"]; host=item["HostConfig"]
            if (item.get("Image")!=self.spec.image_id or config.get("Image")!=self.spec.image or config.get("Cmd")!=list(self._argv)
                    or host.get("NetworkMode")!="bridge" or host.get("IpcMode")!="private"
                    or item.get("NetworkSettings",{}).get("Ports")!={"8000/tcp":[{"HostIp":"127.0.0.1","HostPort":str(self.port)}]}
                    or sha256(item["Id"].encode()).hexdigest()!=self._identity["container_id_sha256"]
                    or sha256(state["StartedAt"].encode()).hexdigest()!=self._identity["container_start_sha256"]):
                raise ValueError
            mounts={m.get("Destination"):(m.get("Source"),m.get("RW")) for m in item.get("Mounts",[]) if type(m) is dict}
            expected={"/model-repository":(str(self.spec.model_snapshot.parents[1]),False),"/cache/huggingface":(str(self.spec.hf_cache),True),"/cache/compile":(str(self.spec.compile_cache),True)}
            if any(mounts.get(name)!=value for name,value in expected.items()): raise ValueError
            required_env={"HF_HOME=/cache/huggingface","HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub","VLLM_CACHE_ROOT=/cache/compile/vllm","TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor","TRITON_CACHE_DIR=/cache/compile/triton","HF_HUB_OFFLINE=1","TRANSFORMERS_OFFLINE=1","VLLM_ENABLE_V1_MULTIPROCESSING=0","PYTHONHASHSEED=0","CUBLAS_WORKSPACE_CONFIG=:4096:8"}
            if not required_env.issubset(set(config.get("Env",[]))) or not any(request.get("DeviceIDs")==[self.spec.gpu_uuid] for request in host.get("DeviceRequests",[]) if type(request) is dict): raise ValueError
            cgroup=self.command(("cat",f"/proc/{state['Pid']}/cgroup")); netns=self.command(("docker","exec",self.spec.container_name,"readlink","/proc/1/ns/net"))
            if sha256(cgroup).hexdigest()!=self._identity["cgroup_sha256"] or sha256(netns).hexdigest()!=self._identity["network_namespace_sha256"]: raise ValueError
        except Exception as error: raise LaunchRefused("MI container configuration/identity continuity drifted") from error
        def ordinary(raw: bytes) -> dict[str, Any]:
            def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
                value: dict[str, Any] = {}
                for key, item in items:
                    if key in value: raise ValueError
                    value[key]=item
                return value
            try:
                value=json.loads(raw.decode("utf-8",errors="strict"),object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except Exception as error: raise LaunchRefused("MI vLLM ordinary JSON drifted") from error
            if type(value) is not dict: raise LaunchRefused("MI vLLM ordinary JSON object drifted")
            return value
        version = ordinary(self.http_get(f"http://127.0.0.1:{self.port}/version"))
        models = ordinary(self.http_get(f"http://127.0.0.1:{self.port}/v1/models"))
        metrics = self.http_get(f"http://127.0.0.1:{self.port}/metrics")
        _, successes, _, _ = _metric_counters(metrics)
        if phase == "STARTUP": self._baseline_success = successes
        if successes != self._baseline_success + completed:
            raise LaunchRefused("MI vLLM success counter does not match serialized ledger")
        if version.get("version") != "0.25.1" or [row.get("id") for row in models.get("data",[]) if type(row) is dict] != [self.spec.served_model]:
            raise LaunchRefused("MI server readiness identity drifted")
        return canonical_bytes({"schema_version": "hswm-dgx-qcase024-mi-boundary/v3", "arm": self.spec.arm,
            "block_id": self.spec.block_id, "phase": phase, "completed": completed,
            "async_scheduling": self.spec.async_scheduling, "server_argv": list(self._argv),
            "server_argv_sha256": sha256("\0".join(self._argv).encode()).hexdigest(),
            "server_identity": self._identity,
            "request_success_total": successes, "raw_metrics_sha256": sha256(metrics).hexdigest(),
            "terminal": "FINITE_BLOCK_BOUNDARY_NOT_NO_INTERFERENCE_PROOF"})

    def __enter__(self) -> "MiLease":
        self._validate(); self._lock = os.open(self.spec.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._before(); self._launch()
            deadline = time.monotonic() + 900
            while True:
                try: self.attest("STARTUP", 0); return self
                except LoopbackUnavailable:
                    if time.monotonic() >= deadline: raise
                    time.sleep(2)
        except Exception:
            self.close(); raise

    def close(self) -> None:
        if self._started:
            self.command(("docker", "rm", "-f", self.spec.container_name))
            deadline = time.monotonic() + 60
            while (self._cmd(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"))
                   or self._listener_present(self._cmd(("sudo", "-n", "ss", "-ltnpH")))):
                if time.monotonic() >= deadline: raise LaunchRefused("MI GPU did not quiesce after block teardown")
                time.sleep(1)
            self._started = False
        if self._lock is not None:
            fcntl.flock(self._lock, fcntl.LOCK_UN); os.close(self._lock); self._lock = None

    def __exit__(self, *_: object) -> None: self.close()


__all__ = ["MiLease", "MiLeaseSpec"]
