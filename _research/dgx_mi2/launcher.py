"""Fresh two-request vLLM lease for the MI-2 paired-launch diagnostic.

This is intentionally a new runtime namespace.  MI-1's frozen four-block
lease is not imported: MI-2 has twelve pairs, two requests per launch, and a
different evidence identity.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes
from _research.dgx_q1.live_launcher import (
    LaunchRefused, LoopbackUnavailable, SubprocessCommandReader, _get,
    _metric_counters, _text,
)
from _research.dgx_q1.model_snapshot_manifest import build_model_snapshot_manifest

Command = Callable[[tuple[str, ...]], bytes]
HttpGet = Callable[[str], bytes]
_ENDPOINT = re.compile(r"^http://127\.0\.0\.1:([1-9][0-9]{0,4})/v1/chat/completions$")
_NAME = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


def global_quiescence(*, gpu_uuid: str, endpoint: str,
                      command: Command | None = None) -> tuple[bytes, bytes]:
    """Observe the empty DGX boundary before consuming an MI-2 plan."""
    reader = command or SubprocessCommandReader()
    match = _ENDPOINT.fullmatch(endpoint)
    if match is None:
        raise LaunchRefused("MI-2 global endpoint identity")
    def text(argv: tuple[str, ...]) -> str:
        return _text(reader, argv)
    if (text(("docker", "ps", "-q"))
            or text(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"))
            or f"127.0.0.1:{match.group(1)}" in text(("sudo", "-n", "ss", "-ltnpH"))):
        raise LaunchRefused("MI-2 global shared-state quiescence failed")
    gpu_raw = reader(("nvidia-smi", "--query-gpu=uuid,temperature.gpu,power.draw,clocks.sm,pstate", "--format=csv,noheader,nounits"))
    lines = [line for line in gpu_raw.decode("utf-8", "strict").splitlines() if line.strip()]
    if (len(gpu_raw) > 16 * 1024 or len(lines) != 1 or len(lines[0].split(",")) != 5
            or lines[0].split(",")[0].strip() != gpu_uuid):
        raise LaunchRefused("MI-2 global pinned GPU observation drifted")
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return canonical_bytes({"schema_version": "hswm-dgx-mi2-global-quiescence/v1", "gpu_uuid": gpu_uuid,
                            "endpoint": endpoint, "observed_at_utc": observed_at,
                            "gpu_observation": {"sha256": sha256(gpu_raw).hexdigest(), "byte_length": len(gpu_raw), "validated_projection": {"line_count": 1, "columns_per_line": 5}},
                            "quiescence": {"docker_containers": 0, "gpu_compute_apps": 0, "target_listener_present": False},
                            "terminal": "PRE_BURN_SHARED_DGX_QUIESCENCE_NOT_NO_INTERFERENCE_PROOF"}), gpu_raw


@dataclass(frozen=True, slots=True, kw_only=True)
class Mi2LeaseSpec:
    pair_id: str
    launch_index: int
    arm: str
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
    model_repository: str
    snapshot_manifest_raw: bytes
    # Set only by Mi2Runner after it has acquired the one study-wide lock.
    shared_dgx_lock_held: bool = False


class Mi2Lease:
    """One exclusive, non-reusable launch; it owns exactly R001 and R002."""
    def __init__(self, spec: Mi2LeaseSpec, command: Command | None = None,
                 http_get: HttpGet | None = None) -> None:
        self.spec, self.command = spec, command or SubprocessCommandReader()
        self.http_get = http_get or _get
        self._lock: int | None = None
        self._started = False
        self._argv: tuple[str, ...] = ()
        self._baseline_success = 0
        self._identity: dict[str, str] = {}
        self._teardown: tuple[bytes, bytes] | None = None

    @property
    def port(self) -> int:
        match = _ENDPOINT.fullmatch(self.spec.endpoint)
        if match is None:
            raise LaunchRefused("MI-2 endpoint is not an exact loopback target")
        return int(match.group(1))

    def _cmd(self, argv: tuple[str, ...]) -> str:
        return _text(self.command, argv)

    def _validate(self) -> None:
        s = self.spec
        if (not re.fullmatch(r"P(0[1-9]|1[0-2])", s.pair_id) or not 1 <= s.launch_index <= 24
                or s.arm not in {"ASYNC_ENABLED", "ASYNC_DISABLED"}
                or s.async_scheduling != (s.arm == "ASYNC_ENABLED")
                or _NAME.fullmatch(s.container_name) is None or len(s.model_revision) != 40
                or not s.image or not s.image_id or not s.gpu_uuid or not s.served_model
                or not s.model_repository or not s.snapshot_manifest_raw
                or not 1 <= s.max_model_len or not 100 <= s.gpu_memory_utilization_milli <= 990):
            raise LaunchRefused("MI-2 lease identity/control drifted")
        self.port
        for path in (s.lock_path, s.model_snapshot, s.hf_cache, s.compile_cache):
            if not path.is_absolute() or path.is_symlink():
                raise LaunchRefused("MI-2 lease path must be absolute and non-linked")
        if s.lock_path.parent.is_symlink() or not s.lock_path.parent.is_dir():
            raise LaunchRefused("MI-2 lease lock parent must be a non-linked directory")

    def _listener_present(self, rows: str) -> bool:
        return any(line.split()[:1] == ["LISTEN"] and f"127.0.0.1:{self.port}" in line.split()
                   for line in rows.splitlines())

    def _before(self) -> None:
        s = self.spec
        if (self._cmd(("docker", "ps", "-q"))
                or self._cmd(("docker", "ps", "-aq", "--filter", f"name=^/{s.container_name}$"))
                or self._cmd(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"))):
            raise LaunchRefused("MI-2 requires quiescent container and GPU")
        if self._listener_present(self._cmd(("sudo", "-n", "ss", "-ltnpH"))):
            raise LaunchRefused("MI-2 target listener survived a prior launch")
        for cache in (s.hf_cache, s.compile_cache):
            if not cache.is_dir() or cache.is_symlink() or any(cache.iterdir()):
                raise LaunchRefused("MI-2 cache is absent, linked, or reused")
        if not s.model_snapshot.is_dir() or s.model_snapshot.is_symlink():
            raise LaunchRefused("MI-2 pinned snapshot unavailable")
        rebuilt = build_model_snapshot_manifest(s.model_snapshot.parents[2], repository=s.model_repository,
                                                revision=s.model_revision)
        if canonical_bytes(rebuilt) != s.snapshot_manifest_raw:
            raise LaunchRefused("MI-2 local snapshot manifest drifted")

    def _server_argv(self) -> tuple[str, ...]:
        s = self.spec
        return ("--model", f"/model-repository/snapshots/{s.model_revision}", "--served-model-name", s.served_model,
                "--host", "0.0.0.0", "--port", "8000", "--max-num-seqs", "1", "--no-enable-prefix-caching",
                "--max-model-len", str(s.max_model_len), "--gpu-memory-utilization",
                f"{s.gpu_memory_utilization_milli // 1000}.{s.gpu_memory_utilization_milli % 1000:03d}",
                "--generation-config", "vllm", "--seed", "0", "--enforce-eager", "--language-model-only",
                "--max-logprobs", "20", "--logprobs-mode", "processed_logprobs",
                "--async-scheduling" if s.async_scheduling else "--no-async-scheduling")

    def _launch(self) -> None:
        s = self.spec; self._argv = self._server_argv()
        env = ("HF_HOME=/cache/huggingface", "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub",
               "VLLM_CACHE_ROOT=/cache/compile/vllm", "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor",
               "TRITON_CACHE_DIR=/cache/compile/triton", "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1",
               "VLLM_ENABLE_V1_MULTIPROCESSING=0", "PYTHONHASHSEED=0", "CUBLAS_WORKSPACE_CONFIG=:4096:8")
        argv = ["docker", "run", "-d", "--pull", "never", "--name", s.container_name, "--restart", "no", "--network", "bridge", "--ipc", "private",
                "-p", f"127.0.0.1:{self.port}:8000", "--gpus", f"device={s.gpu_uuid}",
                "--mount", f"type=bind,src={s.model_snapshot.parents[1]},dst=/model-repository,readonly",
                "--mount", f"type=bind,src={s.hf_cache},dst=/cache/huggingface",
                "--mount", f"type=bind,src={s.compile_cache},dst=/cache/compile"]
        for item in env: argv += ["-e", item]
        raw_id = self.command(tuple([*argv, s.image, *self._argv])).strip()
        if not raw_id or len(raw_id) > 128:
            raise LaunchRefused("MI-2 launch did not return bounded container ID")
        self._started = True
        try:
            item = json.loads(self.command(("docker", "inspect", s.container_name)).decode("utf-8", "strict"))[0]
            pid, started = item["State"]["Pid"], item["State"]["StartedAt"]
            cgroup = self.command(("cat", f"/proc/{pid}/cgroup"))
            netns = self.command(("docker", "exec", s.container_name, "readlink", "/proc/1/ns/net"))
            if not isinstance(item.get("Id"), str) or item["Id"].encode() != raw_id or not isinstance(pid, int) or pid <= 0:
                raise ValueError
            self._identity = {"container_id_sha256": sha256(item["Id"].encode()).hexdigest(),
                              "container_start_sha256": sha256(started.encode()).hexdigest(),
                              "cgroup_sha256": sha256(cgroup).hexdigest(), "network_namespace_sha256": sha256(netns).hexdigest(),
                              "server_argv_sha256": sha256("\0".join(self._argv).encode()).hexdigest()}
        except Exception as error:
            raise LaunchRefused("MI-2 immutable server identity observation failed") from error

    def attest(self, phase: str, completed: int) -> bytes:
        if not self._started or phase not in {"STARTUP", "PRE", "POST", "FINAL"} or not 0 <= completed <= 2:
            raise LaunchRefused("MI-2 attestation phase/slot drifted")
        try:
            item = json.loads(self.command(("docker", "inspect", self.spec.container_name)).decode("utf-8", "strict"))[0]
            state, config, host = item["State"], item["Config"], item["HostConfig"]
            if (item.get("Image") != self.spec.image_id or config.get("Image") != self.spec.image or config.get("Cmd") != list(self._argv)
                    or host.get("NetworkMode") != "bridge" or host.get("IpcMode") != "private"
                    or sha256(item["Id"].encode()).hexdigest() != self._identity["container_id_sha256"]
                    or sha256(state["StartedAt"].encode()).hexdigest() != self._identity["container_start_sha256"]):
                raise ValueError
            cgroup = self.command(("cat", f"/proc/{state['Pid']}/cgroup")); netns = self.command(("docker", "exec", self.spec.container_name, "readlink", "/proc/1/ns/net"))
            if sha256(cgroup).hexdigest() != self._identity["cgroup_sha256"] or sha256(netns).hexdigest() != self._identity["network_namespace_sha256"]:
                raise ValueError
        except Exception as error:
            raise LaunchRefused("MI-2 container identity continuity drifted") from error
        version = json.loads(self.http_get(f"http://127.0.0.1:{self.port}/version").decode("utf-8", "strict"))
        models = json.loads(self.http_get(f"http://127.0.0.1:{self.port}/v1/models").decode("utf-8", "strict"))
        metrics = self.http_get(f"http://127.0.0.1:{self.port}/metrics")
        _, successes, _, _ = _metric_counters(metrics)
        # A fresh launch owns exactly the two preregistered requests.  A
        # nonzero server counter at readiness is an unrecorded request, not a
        # harmless offset that may be normalized away.
        if phase == "STARTUP":
            if successes != 0:
                raise LaunchRefused("MI-2 fresh server already processed a request")
            self._baseline_success = 0
        if successes != self._baseline_success + completed or version.get("version") != "0.25.1" or [row.get("id") for row in models.get("data", []) if type(row) is dict] != [self.spec.served_model]:
            raise LaunchRefused("MI-2 server readiness/counter identity drifted")
        return canonical_bytes({"schema_version": "hswm-dgx-mi2-boundary/v1", "pair_id": self.spec.pair_id,
                                "launch_index": self.spec.launch_index, "arm": self.spec.arm, "phase": phase,
                                "completed": completed, "async_scheduling": self.spec.async_scheduling,
                                "server_argv": list(self._argv), "server_argv_sha256": self._identity["server_argv_sha256"],
                                "server_identity": self._identity, "request_success_total": successes,
                                "raw_metrics_sha256": sha256(metrics).hexdigest(),
                                "terminal": "FINITE_LAUNCH_BOUNDARY_NOT_NO_INTERFERENCE_PROOF"})

    def __enter__(self) -> "Mi2Lease":
        self._validate()
        if not self.spec.shared_dgx_lock_held:
            self._lock = os.open(self.spec.lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            if self._lock is not None:
                if not stat.S_ISREG(os.fstat(self._lock).st_mode):
                    raise LaunchRefused("MI-2 lease lock is not regular")
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
        try:
            if self._started:
                self.command(("docker", "rm", "-f", self.spec.container_name)); deadline = time.monotonic() + 60
                while (self._cmd(("docker", "ps", "-q"))
                       or self._cmd(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"))
                       or self._listener_present(self._cmd(("sudo", "-n", "ss", "-ltnpH")))):
                    if time.monotonic() >= deadline: raise LaunchRefused("MI-2 GPU/listener did not quiesce")
                    time.sleep(1)
                gpu_raw = self.command((
                    "nvidia-smi",
                    "--query-gpu=uuid,temperature.gpu,power.draw,clocks.sm,pstate",
                    "--format=csv,noheader,nounits",
                ))
                if len(gpu_raw) > 16 * 1024 or not gpu_raw.strip():
                    raise LaunchRefused("MI-2 teardown GPU observation is unbounded")
                lines = [line for line in gpu_raw.decode("utf-8", "strict").splitlines() if line.strip()]
                if len(lines) != 1 or len(lines[0].split(",")) != 5 or lines[0].split(",")[0].strip() != self.spec.gpu_uuid:
                    raise LaunchRefused("MI-2 teardown GPU observation is malformed")
                observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                self._teardown = (
                    canonical_bytes({
                        "schema_version": "hswm-dgx-mi2-launch-crossed-teardown/v1",
                        "pair_id": self.spec.pair_id,
                        "launch_index": self.spec.launch_index,
                        "arm": self.spec.arm,
                        "observed_at_utc": observed_at,
                        "gpu_observation": {
                            "sha256": sha256(gpu_raw).hexdigest(),
                            "byte_length": len(gpu_raw),
                            "validated_projection": {"line_count": 1, "columns_per_line": 5},
                        },
                        "quiescence": {
                            "docker_containers": 0,
                            "gpu_compute_apps": 0,
                            "target_listener_present": False,
                        },
                        "terminal": "FINITE_TEARDOWN_NOT_NO_INTERFERENCE_PROOF",
                    }),
                    gpu_raw,
                )
                self._started = False
        finally:
            if self._lock is not None:
                fcntl.flock(self._lock, fcntl.LOCK_UN); os.close(self._lock); self._lock = None

    def __exit__(self, *_: object) -> None: self.close()

    @property
    def teardown_attestation(self) -> tuple[bytes, bytes]:
        if self._teardown is None:
            raise LaunchRefused("MI-2 teardown has not completed")
        return self._teardown


__all__ = ["Mi2Lease", "Mi2LeaseSpec", "global_quiescence"]
