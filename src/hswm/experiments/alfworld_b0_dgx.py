"""Narrow, fresh DGX vLLM lease for the ALFWorld B0 calibration.

This is an engineering boundary only.  It starts one pinned model service and
accounts for at most the declared requests.  It neither selects episodes nor
interprets their outcomes, and therefore cannot establish a G0 or efficacy
claim.  Docker bridge networking supplies host-loopback ingress only; it is
not an independent egress-isolation claim.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from _research.dgx_mi2.experiment import _restore_services, _stop_services
from _research.dgx_q1.live_launcher import LaunchRefused, LoopbackUnavailable, _get
from _research.dgx_q1.model_snapshot_manifest import build_model_snapshot_manifest
from hswm.selfmod.contracts import canonical_json_bytes


Command = Callable[[tuple[str, ...]], bytes]
HttpGet = Callable[[str], bytes]

IMAGE = "vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089"
IMAGE_ID = "sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95"
MODEL_REPOSITORY = "Qwen/Qwen3.6-35B-A3B-FP8"
MODEL_REVISION = "95a723d08a9490559dae23d0cff1d9466213d989"
SNAPSHOT_MANIFEST_SHA256 = "2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47"
SERVED_MODEL = "qwen3.6-35b-a3b"
VLLM_VERSION = "0.25.1"
GPU_UUID = "GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5"
GPU_NAME = "NVIDIA GB10"
MAX_TOKENIZE_REQUESTS = 240
MAX_COMPLETION_REQUESTS = 240
MAX_REQUESTS = MAX_TOKENIZE_REQUESTS + MAX_COMPLETION_REQUESTS
NETWORK_BOUNDARY = "DOCKER_BRIDGE_LOOPBACK_INGRESS_EGRESS_NOT_INDEPENDENTLY_CLAIMED"
PROTOCOL_SCHEMA = "hswm-alfworld-b0-calibration-protocol/v1"
MODEL_RUNTIME = {
    "model_repository": MODEL_REPOSITORY,
    "model_revision": MODEL_REVISION,
    "served_model": SERVED_MODEL,
    "snapshot_manifest_sha256": SNAPSHOT_MANIFEST_SHA256,
    "container_image": IMAGE,
    "container_image_id": IMAGE_ID,
    "vllm_version": VLLM_VERSION,
    "gpu_name": GPU_NAME,
    "gpu_uuid": GPU_UUID,
    "endpoint_origin": "http://127.0.0.1:18080",
    "host_ingress": "LOOPBACK_ONLY",
    "container_egress": "BRIDGE_EGRESS_NOT_INDEPENDENTLY_BLOCKED",
    "max_model_len": 32768,
    "max_num_seqs": 1,
    "prefix_cache": False,
    "async_scheduling": False,
    "enforce_eager": True,
    "cuda_launch_blocking": True,
    "language_model_only": True,
    "generation_config": "vllm",
    "engine_seed": 0,
    "temperature": 0.0,
    "top_p": 1.0,
    "enable_thinking": False,
    "v1_multiprocessing": False,
    "fresh_service_for_occurrence": True,
    "fresh_compile_and_huggingface_cache_directories": True,
    "request_success_counter_at_start": 0,
    "maximum_completion_posts": MAX_COMPLETION_REQUESTS,
    "maximum_tokenize_posts": MAX_TOKENIZE_REQUESTS,
    "maximum_total_http_posts": MAX_REQUESTS,
    "byte_exactness_required": False,
    "sampling_note": "Greedy decoding is retained from the already measured DGX deployment to reduce one source of noise. Provider-byte equality is not a prerequisite or evidence of learning.",
}

CONTAINER_ENVIRONMENT = (
    "HF_HOME=/cache/huggingface",
    "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub",
    "VLLM_CACHE_ROOT=/cache/compile/vllm",
    "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor",
    "TRITON_CACHE_DIR=/cache/compile/triton",
    "HF_HUB_OFFLINE=1",
    "TRANSFORMERS_OFFLINE=1",
    "VLLM_ENABLE_V1_MULTIPROCESSING=0",
    "CUDA_LAUNCH_BLOCKING=1",
    "PYTHONHASHSEED=0",
    "CUBLAS_WORKSPACE_CONFIG=:4096:8",
)

_NAME = re.compile(r"^hswm-alfworld-b0-[a-z0-9-]{3,48}$")
_ENDPOINT = re.compile(r"^http://127\.0\.0\.1:([1-9][0-9]{0,4})$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class B0DgxLeaseSpec:
    """All mutable locations and source bindings for one calibration lease."""

    repo_root: Path
    protocol_path: Path
    protocol_sha256: str
    declared_source_paths: tuple[Path, ...]
    lock_path: Path
    container_name: str
    model_snapshot: Path
    hf_cache: Path
    compile_cache: Path
    endpoint: str = "http://127.0.0.1:18080"


def expected_server_argv() -> tuple[str, ...]:
    """Return the complete frozen server command, without a G1 protocol."""

    return (
        "--model", f"/model-repository/snapshots/{MODEL_REVISION}",
        "--served-model-name", SERVED_MODEL,
        "--host", "0.0.0.0", "--port", "8000",
        "--max-num-seqs", "1", "--no-enable-prefix-caching",
        "--max-model-len", "32768", "--gpu-memory-utilization", "0.500",
        "--generation-config", "vllm", "--seed", "0", "--enforce-eager",
        "--language-model-only", "--no-async-scheduling",
    )


def parse_success_total(raw: bytes) -> int:
    """Accept only an idle, cache-free metrics snapshot and total successes."""

    if not isinstance(raw, bytes) or not raw or len(raw) > 4_000_000:
        raise LaunchRefused("B0 DGX metrics are unavailable or unbounded")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise LaunchRefused("B0 DGX metrics are not UTF-8") from error
    values: dict[str, list[float]] = {"running": [], "success": [], "hits": [], "queries": []}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        name = fields[0].split("{", 1)[0]
        try:
            value = float(fields[1])
        except ValueError as error:
            raise LaunchRefused("B0 DGX metric value is invalid") from error
        if value < 0 or value != value or value == float("inf"):
            raise LaunchRefused("B0 DGX metric value is non-finite")
        if name == "vllm:num_requests_running": values["running"].append(value)
        elif name == "vllm:request_success_total": values["success"].append(value)
        elif name in {"vllm:prefix_cache_hits", "vllm:prefix_cache_hits_total", "vllm_prefix_cache_hits", "vllm_prefix_cache_hits_total"}: values["hits"].append(value)
        elif name in {"vllm:prefix_cache_queries", "vllm:prefix_cache_queries_total", "vllm_prefix_cache_queries", "vllm_prefix_cache_queries_total"}: values["queries"].append(value)
    if any(not values[key] for key in values) or any(item != 0 for key in ("running", "hits", "queries") for item in values[key]):
        raise LaunchRefused("B0 DGX required counters are absent, active, or nonzero")
    total = sum(values["success"])
    if total != int(total):
        raise LaunchRefused("B0 DGX success counter is not integral")
    return int(total)


class B0DgxLease:
    """Fail-closed fresh model-service lifecycle, deliberately smaller than G1."""

    def __init__(self, spec: B0DgxLeaseSpec, *, command: Command | None = None,
                 http_get: HttpGet | None = None,
                 stop_services: Callable[[list[tuple[str, str]]], list[tuple[str, str]]] = _stop_services,
                 restore_services: Callable[[list[tuple[str, str]]], None] = _restore_services) -> None:
        self.spec, self.command, self.http_get = spec, command or self._subprocess, http_get or _get
        self.stop_services, self.restore_services = stop_services, restore_services
        self._lock: int | None = None
        self._started = False
        self._stopped: list[tuple[str, str]] = []
        self._identity: tuple[str, str] | None = None
        self.startup: dict[str, bytes] | None = None
        self.final: dict[str, bytes] | None = None
        self._observed_requests = (0, 0)
        self.teardown: dict[str, str] | None = None

    @staticmethod
    def _subprocess(argv: tuple[str, ...]) -> bytes:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode:
            raise LaunchRefused("B0 DGX command failed: " + argv[0])
        return result.stdout

    def _text(self, argv: tuple[str, ...]) -> str:
        return self.command(argv).decode("utf-8", "strict").strip()

    @property
    def port(self) -> int:
        match = _ENDPOINT.fullmatch(self.spec.endpoint)
        if match is None or not 1 <= int(match.group(1)) <= 65535:
            raise LaunchRefused("B0 DGX endpoint must be exact loopback")
        return int(match.group(1))

    def _validate_protocol_runtime(self) -> None:
        """Bind every launch identity to the exact checked-in B0 protocol."""

        try:
            protocol = json.loads(self.spec.protocol_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LaunchRefused("B0 DGX protocol is not readable JSON") from error
        if (not isinstance(protocol, dict) or protocol.get("schema_version") != PROTOCOL_SCHEMA
                or protocol.get("model_runtime") != MODEL_RUNTIME
                or self.spec.endpoint != MODEL_RUNTIME["endpoint_origin"]):
            raise LaunchRefused("B0 DGX protocol runtime identity drifted")

    def _validate(self) -> None:
        spec = self.spec
        if _NAME.fullmatch(spec.container_name) is None or _HEX64.fullmatch(spec.protocol_sha256) is None:
            raise LaunchRefused("B0 DGX name or protocol hash is invalid")
        if (not spec.repo_root.is_absolute() or spec.repo_root.is_symlink() or not spec.repo_root.is_dir()
                or not spec.protocol_path.is_absolute() or spec.protocol_path.is_symlink()
                or not spec.protocol_path.is_file() or not spec.protocol_path.is_relative_to(spec.repo_root)):
            raise LaunchRefused("B0 DGX source boundary is invalid")
        if self._text(("git", "-C", str(spec.repo_root), "status", "--porcelain")):
            raise LaunchRefused("B0 DGX source checkout is dirty")
        if _HEX40.fullmatch(self._text(("git", "-C", str(spec.repo_root), "rev-parse", "HEAD"))) is None:
            raise LaunchRefused("B0 DGX source commit is invalid")
        declared = tuple(dict.fromkeys(spec.declared_source_paths))
        if not declared or spec.protocol_path not in declared:
            raise LaunchRefused("B0 DGX declared source paths omit protocol")
        for path in declared:
            if (not path.is_absolute() or path.is_symlink() or not path.is_file() or not path.is_relative_to(spec.repo_root)):
                raise LaunchRefused("B0 DGX declared source path is invalid")
            relative = path.relative_to(spec.repo_root).as_posix()
            if path.read_bytes() != self.command(("git", "-C", str(spec.repo_root), "show", f"HEAD:{relative}")):
                raise LaunchRefused("B0 DGX declared source differs from commit")
        if sha256(spec.protocol_path.read_bytes()).hexdigest() != spec.protocol_sha256:
            raise LaunchRefused("B0 DGX protocol hash drifted")
        self._validate_protocol_runtime()
        for path in (spec.lock_path, spec.model_snapshot, spec.hf_cache, spec.compile_cache):
            if not path.is_absolute() or path.is_symlink():
                raise LaunchRefused("B0 DGX path is linked or relative")
        if any(path.exists() for path in (spec.hf_cache, spec.compile_cache)) or any(not path.parent.is_dir() or path.parent.is_symlink() for path in (spec.hf_cache, spec.compile_cache)):
            raise LaunchRefused("B0 DGX caches are not fresh")
        image_raw = self.command(("docker", "image", "inspect", IMAGE))
        try:
            image = json.loads(image_raw.decode("utf-8", "strict"))
            valid_image = type(image) is list and len(image) == 1 and image[0].get("Id") == IMAGE_ID and IMAGE in image[0].get("RepoDigests", [])
        except (UnicodeDecodeError, json.JSONDecodeError):
            valid_image = False
        if not valid_image:
            raise LaunchRefused("B0 DGX image identity drifted")
        gpu = [field.strip() for field in self.command(("nvidia-smi", "--query-gpu=uuid,name", "--format=csv,noheader,nounits")).decode("utf-8", "strict").split(",")]
        if gpu != [GPU_UUID, GPU_NAME]:
            raise LaunchRefused("B0 DGX GPU identity drifted")
        hub_root = spec.model_snapshot.parents[2]
        expected_snapshot = hub_root / "models--Qwen--Qwen3.6-35B-A3B-FP8" / "snapshots" / MODEL_REVISION
        try:
            manifest = canonical_json_bytes(build_model_snapshot_manifest(
                hub_root, repository=MODEL_REPOSITORY, revision=MODEL_REVISION
            ))
        except Exception as error:
            raise LaunchRefused("B0 DGX model snapshot is unavailable") from error
        if (spec.model_snapshot != expected_snapshot or not spec.model_snapshot.is_dir() or spec.model_snapshot.is_symlink()
                or sha256(manifest).hexdigest() != SNAPSHOT_MANIFEST_SHA256):
            raise LaunchRefused("B0 DGX model snapshot drifted")

    def _acquire_lock(self) -> None:
        path = self.spec.lock_path
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise LaunchRefused("B0 DGX lock parent unavailable")
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise LaunchRefused("B0 DGX lock is not regular")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(descriptor)
            raise
        self._lock = descriptor

    def _quiescent(self) -> bool:
        docker = self.command(("docker", "ps", "-q"))
        gpu = self.command(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"))
        listeners = self.command(("sudo", "-n", "ss", "-ltnpH"))
        quiet = not docker.strip() and not gpu.strip() and f"127.0.0.1:{self.port}" not in listeners.decode("utf-8", "strict")
        if quiet:
            self.teardown = {"docker_ps_utf8": docker.decode("utf-8", "strict"), "gpu_compute_utf8": gpu.decode("utf-8", "strict"), "listeners_utf8": listeners.decode("utf-8", "strict")}
        return quiet

    def _assert_fresh_container_name(self) -> None:
        """Refuse a stopped name before shared services are changed."""

        if self._text(("docker", "ps", "-aq", "--filter", f"name=^/{self.spec.container_name}$")):
            raise LaunchRefused("B0 DGX container name is not fresh")

    def _launch(self) -> None:
        spec = self.spec
        spec.hf_cache.mkdir(parents=True, mode=0o700)
        spec.compile_cache.mkdir(mode=0o700)
        environment = CONTAINER_ENVIRONMENT
        argv = ["docker", "run", "-d", "--pull", "never", "--name", spec.container_name, "--restart", "no", "--network", "bridge", "--ipc", "private", "-p", f"127.0.0.1:{self.port}:8000", "--gpus", f"device={GPU_UUID}", "--mount", f"type=bind,src={spec.model_snapshot.parents[1]},dst=/model-repository,readonly", "--mount", f"type=bind,src={spec.hf_cache},dst=/cache/huggingface", "--mount", f"type=bind,src={spec.compile_cache},dst=/cache/compile"]
        for item in environment:
            argv.extend(("-e", item))
        raw_id = self.command(tuple([*argv, IMAGE, *expected_server_argv()])).strip()
        # A command can return malformed output after Docker has made the
        # container.  From this point close() owns removal by exact name.
        self._started = True
        if re.fullmatch(rb"[0-9a-f]{64}", raw_id) is None:
            raise LaunchRefused("B0 DGX launch did not return a container ID")
        try:
            row = json.loads(self.command(("docker", "inspect", spec.container_name)).decode("utf-8", "strict"))[0]
            ports = row["HostConfig"].get("PortBindings", {}).get("8000/tcp")
            if (row.get("Id") != raw_id.decode("ascii") or row.get("Image") != IMAGE_ID
                    or row.get("Config", {}).get("Image") != IMAGE or row.get("Config", {}).get("Cmd") != list(expected_server_argv())
                    or not set(environment).issubset(set(row.get("Config", {}).get("Env", [])))
                    or row["HostConfig"].get("NetworkMode") != "bridge" or row["HostConfig"].get("IpcMode") != "private"
                    or ports != [{"HostIp": "127.0.0.1", "HostPort": str(self.port)}]):
                raise ValueError
            self._identity = (sha256(raw_id).hexdigest(), sha256(row["State"]["StartedAt"].encode()).hexdigest())
        except Exception as error:
            raise LaunchRefused("B0 DGX container identity drifted") from error

    def _assert_startup_container_alive(self) -> None:
        """Refuse immediately when the owned engine exits before readiness."""

        try:
            row = json.loads(
                self.command(("docker", "inspect", self.spec.container_name)).decode(
                    "utf-8", "strict"
                )
            )[0]
            identity = (
                sha256(row["Id"].encode()).hexdigest(),
                sha256(row["State"]["StartedAt"].encode()).hexdigest(),
            )
            if (
                self._identity is None
                or identity != self._identity
                or row.get("Image") != IMAGE_ID
                or row.get("Config", {}).get("Cmd") != list(expected_server_argv())
                or row.get("State", {}).get("Running") is not True
            ):
                raise ValueError
        except Exception as error:
            raise LaunchRefused(
                "B0 DGX owned container exited before readiness"
            ) from error

    def attest(self, tokenize_completed: int, completion_completed: int) -> dict[str, bytes]:
        """Check the service counter against the two declared B0 request caps."""

        if (not self._started or self._identity is None
                or not isinstance(tokenize_completed, int) or not isinstance(completion_completed, int)
                or not 0 <= tokenize_completed <= MAX_TOKENIZE_REQUESTS
                or not 0 <= completion_completed <= MAX_COMPLETION_REQUESTS):
            raise LaunchRefused("B0 DGX request count is invalid")
        requests_completed = tokenize_completed + completion_completed
        try:
            inspect = self.command(("docker", "inspect", self.spec.container_name))
            row = json.loads(inspect.decode("utf-8", "strict"))[0]
            if (sha256(row["Id"].encode()).hexdigest(), sha256(row["State"]["StartedAt"].encode()).hexdigest()) != self._identity or row.get("Image") != IMAGE_ID or row.get("Config", {}).get("Cmd") != list(expected_server_argv()):
                raise ValueError
            if row.get("State", {}).get("Running") is not True:
                raise ValueError
            models = self.http_get(f"{self.spec.endpoint}/v1/models")
            version = self.http_get(f"{self.spec.endpoint}/version")
            version_repeat = self.http_get(f"{self.spec.endpoint}/version")
            metrics = self.http_get(f"{self.spec.endpoint}/metrics")
            model_ids = [item.get("id") for item in json.loads(models.decode("utf-8", "strict")).get("data", []) if isinstance(item, dict)]
            if (version_repeat != version
                    or json.loads(version.decode("utf-8", "strict")).get("version") != VLLM_VERSION
                    or model_ids != [SERVED_MODEL] or parse_success_total(metrics) != requests_completed):
                raise ValueError
        except LoopbackUnavailable:
            raise
        except Exception as error:
            raise LaunchRefused("B0 DGX service attestation drifted") from error
        self._observed_requests = (tokenize_completed, completion_completed)
        return {"container_inspect": inspect, "models": models, "version": version,
                "version_repeat": version_repeat, "metrics": metrics}

    def __enter__(self) -> "B0DgxLease":
        self._validate(); self._acquire_lock()
        try:
            self._assert_fresh_container_name()
            self._stopped = self.stop_services([])
            if not self._quiescent():
                raise LaunchRefused("B0 DGX prelaunch boundary is not quiescent")
            self._launch()
            deadline = time.monotonic() + 900
            while True:
                try:
                    self.startup = self.attest(0, 0); return self
                except LoopbackUnavailable:
                    self._assert_startup_container_alive()
                    if time.monotonic() >= deadline: raise
                    time.sleep(2)
        except BaseException as primary:
            try:
                self.close()
            except BaseException as cleanup:
                primary.add_note("B0 DGX startup cleanup failure: " + type(cleanup).__name__)
            raise primary

    def close(self) -> None:
        """Always attempt owned-container cleanup before propagating failure."""

        primary: BaseException | None = None
        cleanup_failures: list[BaseException] = []
        unsafe = False
        try:
            if self._started:
                try:
                    # This is deliberately before removal: it records the final
                    # service-side counter instead of trusting a caller-side log.
                    self.final = self.attest(*self._observed_requests)
                except BaseException as error:
                    primary = error
                try:
                    self.command(("docker", "rm", "-f", self.spec.container_name))
                    self._started = False
                except BaseException as error:
                    cleanup_failures.append(error)
            if self._started or self._stopped:
                try:
                    deadline = time.monotonic() + 60
                    while not self._quiescent():
                        if time.monotonic() >= deadline:
                            unsafe = True
                            break
                        time.sleep(1)
                except BaseException as error:
                    unsafe = True
                    cleanup_failures.append(error)
            if not unsafe and self._stopped:
                try:
                    self.restore_services(self._stopped)
                except BaseException as error:
                    cleanup_failures.append(error)
        finally:
            if self._lock is not None:
                descriptor, self._lock = self._lock, None
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except BaseException as error:
                    cleanup_failures.append(error)
                try:
                    os.close(descriptor)
                except BaseException as error:
                    cleanup_failures.append(error)
        if unsafe:
            cleanup_failures.append(LaunchRefused("B0 DGX teardown was not quiescent"))
        if primary is not None:
            for error in cleanup_failures:
                primary.add_note("B0 DGX cleanup failure: " + type(error).__name__)
            raise primary
        if cleanup_failures:
            raise LaunchRefused("B0 DGX teardown failed") from cleanup_failures[0]

    def __exit__(self, *_: object) -> None:
        self.close()
