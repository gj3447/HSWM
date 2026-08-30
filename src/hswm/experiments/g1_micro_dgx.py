"""Fresh DGX lease with loopback-bound host ingress for one G1 micro exploration.

This module only owns runtime isolation. The protocol, one-shot registry,
causal records, and result verification remain in ``g1_micro``. The container
uses Docker bridge networking, so outbound egress is not independently blocked.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
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
from typing import Any

from _research.dgx_mi2.experiment import (
    _active_shared_containers,
    _restore_services,
    _stop_services,
)
from _research.dgx_q1.live_launcher import (
    LaunchRefused,
    LoopbackUnavailable,
    _get,
)
from _research.dgx_q1.model_snapshot_manifest import build_model_snapshot_manifest
from hswm.experiments import g1_micro
from hswm.selfmod.contracts import canonical_json_bytes


Command = Callable[[tuple[str, ...]], bytes]
HttpGet = Callable[[str], bytes]
_NAME = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
_ENDPOINT = re.compile(r"^http://127\.0\.0\.1:([1-9][0-9]{0,4})$")


def offline_action_code_tokenizer_receipt(
    *, command: Command, snapshot: Path, tokenizer_binding: Mapping[str, Any] | None = None,
    image: str | None = None, image_id: str | None = None,
    snapshot_manifest_sha256: str | None = None, episodes: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Measure public action codes inside the pinned vLLM image, offline.

    The host never imports tokenizer libraries.  The image digest and local
    snapshot are the same pinned objects used by the subsequent vLLM service.
    Output is canonical JSON so it can be bound to execution START before any
    model or tokenizer HTTP request.
    """
    if tokenizer_binding is not None:
        image = tokenizer_binding.get("container_image")
        image_id = tokenizer_binding.get("container_image_id")
        snapshot_manifest_sha256 = tokenizer_binding.get("snapshot_manifest_sha256")
        episodes = tokenizer_binding.get("episodes")
    if not isinstance(image, str) or not isinstance(image_id, str) or not isinstance(snapshot_manifest_sha256, str) or not isinstance(episodes, Sequence) or not snapshot.is_absolute() or snapshot.is_symlink() or not snapshot.is_dir():
        raise LaunchRefused("tokenizer snapshot is unavailable")
    public = []
    for episode in episodes:
        if not isinstance(episode, Mapping) or not isinstance(episode.get("episode_uid"), str) or not isinstance(episode.get("action_codes"), list) or len(episode["action_codes"]) != 2:
            raise LaunchRefused("tokenizer action-code episode contract is invalid")
        public.append({"action_codes": episode["action_codes"], "episode_uid": episode["episode_uid"]})
    payload = canonical_json_bytes({"episodes": public}).decode("utf-8")
    program = (
        "import json,sys; import transformers,tokenizers; "
        "from transformers import AutoTokenizer; "
        "p=json.loads(sys.argv[1]); t=AutoTokenizer.from_pretrained('/model-repository/snapshots/' + sys.argv[2],local_files_only=True); "
        "r={'transformers_version':transformers.__version__,'tokenizers_version':tokenizers.__version__,"
        "'episodes':[{'episode_uid':e['episode_uid'],'token_ids':[t.encode(x,add_special_tokens=False) for x in e['action_codes']]} for e in p['episodes']]}; "
        "print(json.dumps(r,sort_keys=True,separators=(',',':')))"
    )
    raw = command((
        "docker", "run", "--rm", "--network", "none", "--ipc", "none", "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--mount", f"type=bind,src={snapshot.parents[1]},dst=/model-repository,readonly",
        "--entrypoint", "/usr/bin/python3", image, "-c", program, payload, snapshot.name,
    ))
    try:
        observed = json.loads(raw.decode("utf-8", "strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LaunchRefused("offline tokenizer measurement is not JSON") from error
    rows = observed.get("episodes") if isinstance(observed, dict) else None
    if not isinstance(rows, list) or len(rows) != len(public) or not isinstance(observed.get("transformers_version"), str) or not isinstance(observed.get("tokenizers_version"), str):
        raise LaunchRefused("offline tokenizer measurement shape drifted")
    normalized: list[dict[str, Any]] = []
    for expected, row in zip(public, rows, strict=True):
        ids = row.get("token_ids") if isinstance(row, Mapping) else None
        if row.get("episode_uid") != expected["episode_uid"] or not isinstance(ids, list) or len(ids) != 2 or any(not isinstance(part, list) or not part or any(isinstance(token, bool) or not isinstance(token, int) or token < 0 for token in part) for part in ids) or len(ids[0]) != len(ids[1]):
            raise LaunchRefused("opaque action codes do not have equal offline token counts")
        normalized.append({"episode_uid": expected["episode_uid"], "token_ids": ids, "token_counts": [len(ids[0]), len(ids[1])]})
    receipt = {
        "schema_version": "hswm-g1-opaque-offline-tokenizer-receipt/v1",
        "container_image": image, "container_image_id": image_id,
        "model_repository": "Qwen/Qwen3.6-35B-A3B-FP8", "model_revision": snapshot.name,
        "snapshot_manifest_sha256": snapshot_manifest_sha256,
        "encoding": {"add_special_tokens": False, "api": "AutoTokenizer.encode", "local_files_only": True},
        "episodes": [{**entry, "action_codes": item["action_codes"]} for entry, item in zip(normalized, public, strict=True)],
        "tokenizers_version": observed["tokenizers_version"], "transformers_version": observed["transformers_version"],
    }
    result = {**receipt, "receipt_sha256": sha256(canonical_json_bytes(receipt)).hexdigest()}
    if tokenizer_binding is not None:
        _validate_opaque_tokenizer_receipt(result, tokenizer_binding)
    return result


def _validate_opaque_tokenizer_receipt(
    receipt: Mapping[str, Any], tokenizer_binding: Mapping[str, Any]
) -> None:
    """Recheck the pre-mutation measurement against the exact frozen binding."""

    unsigned = dict(receipt)
    digest = unsigned.pop("receipt_sha256", None)
    expected = {
        "schema_version": "hswm-g1-opaque-offline-tokenizer-receipt/v1",
        **{
            key: tokenizer_binding.get(key)
            for key in (
                "container_image", "container_image_id", "model_repository",
                "model_revision", "snapshot_manifest_sha256", "encoding",
                "transformers_version", "tokenizers_version", "episodes",
            )
        },
    }
    if not isinstance(digest, str) or digest != sha256(canonical_json_bytes(unsigned)).hexdigest() or unsigned != expected:
        raise LaunchRefused("offline tokenizer receipt differs from preregistered binding")


@dataclass(frozen=True, slots=True, kw_only=True)
class DGXFreshSpec:
    repo_root: Path
    protocol_path: Path
    output_dir: Path
    runtime_binding_path: Path
    execution_registry: Path
    lock_path: Path
    container_name: str
    model_snapshot: Path
    hf_cache: Path
    compile_cache: Path
    evaluator_reveal: Path | None = None
    endpoint: str = "http://127.0.0.1:18080"


def make_runtime_binding_record(
    *,
    protocol: Mapping[str, Any],
    protocol_sha256: str,
    source_commit: str,
    source_tree: str,
    source_manifest: Mapping[str, str],
    tracked_source_sha256: Mapping[str, str],
    protocol_file_sha256: str,
    container_id_sha256: str,
    container_start_sha256: str,
    container_inspect_raw: bytes,
    image_inspect_raw: bytes,
    gpu_observation_raw: bytes,
    snapshot_manifest_raw: bytes,
    startup_metrics_raw: bytes,
    startup_models_raw: bytes,
    startup_version_raw: bytes,
) -> dict[str, Any]:
    """Build the startup record accepted by the core live entrypoint."""

    binding = protocol["live_binding"]
    server_argv = g1_micro.expected_dgx_server_argv(protocol)
    record = g1_micro.make_record(
        "DGXFreshRuntimeBinding",
        owner_uid="principal:g1-micro-dgx-runtime-custodian",
        payload={
            "async_scheduling": binding["async_scheduling"],
            "container_inspect_json": container_inspect_raw.decode("utf-8", "strict"),
            "container_inspect_sha256": sha256(container_inspect_raw).hexdigest(),
            "container_id_sha256": container_id_sha256,
            "container_image": binding["container_image"],
            "container_image_id": binding["container_image_id"],
            "container_start_sha256": container_start_sha256,
            "endpoint_origin": binding["endpoint_origin"],
            "fresh_cache_directories_empty_before_launch": True,
            "gpu_name": binding["gpu_name"],
            "gpu_observation_sha256": sha256(gpu_observation_raw).hexdigest(),
            "gpu_observation_utf8": gpu_observation_raw.decode("utf-8", "strict"),
            "gpu_uuid": binding["gpu_uuid"],
            "image_inspect_json": image_inspect_raw.decode("utf-8", "strict"),
            "image_inspect_sha256": sha256(image_inspect_raw).hexdigest(),
            "model_repository": binding["model_repository"],
            "model_revision": binding["model_revision"],
            "model_snapshot_manifest_json": snapshot_manifest_raw.decode(
                "utf-8", "strict"
            ),
            "model_snapshot_manifest_sha256": sha256(
                snapshot_manifest_raw
            ).hexdigest(),
            "network_boundary": binding["network_boundary"],
            "protocol_file_sha256": protocol_file_sha256,
            "protocol_sha256": protocol_sha256,
            "request_success_total_at_start": 0,
            "served_model": binding["served_model"],
            "server_argv": server_argv,
            "server_argv_sha256": sha256(
                "\0".join(server_argv).encode("utf-8")
            ).hexdigest(),
            "source_commit": source_commit,
            "source_manifest": dict(source_manifest),
            "source_tree": source_tree,
            "startup_metrics_sha256": sha256(startup_metrics_raw).hexdigest(),
            "startup_metrics_utf8": startup_metrics_raw.decode("utf-8", "strict"),
            "startup_models_json": startup_models_raw.decode("utf-8", "strict"),
            "startup_models_sha256": sha256(startup_models_raw).hexdigest(),
            "startup_version_json": startup_version_raw.decode("utf-8", "strict"),
            "startup_version_sha256": sha256(startup_version_raw).hexdigest(),
            "terminal": (
                "FRESH_CONTAINER_STARTUP_ATTESTATION_NOT_NO_INTERFERENCE_PROOF"
            ),
            "tracked_source_sha256": dict(tracked_source_sha256),
            "vllm_version": binding["vllm_version"],
        },
    )
    g1_micro.validate_dgx_runtime_binding(
        record,
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        source_manifest=source_manifest,
    )
    return record


class DGXFreshRuntime:
    """Fail-closed lifecycle for one fresh vLLM container."""

    def __init__(
        self,
        spec: DGXFreshSpec,
        *,
        command: Command | None = None,
        http_get: HttpGet | None = None,
        stop_services: Callable[
            [list[tuple[str, str]]], list[tuple[str, str]]
        ] = _stop_services,
        restore_services: Callable[[list[tuple[str, str]]], None] = _restore_services,
    ) -> None:
        self.spec = spec
        self.command = command or self._subprocess
        self.http_get = http_get or _get
        self.stop_services = stop_services
        self.restore_services = restore_services
        self._lock: int | None = None
        self._started = False
        self._stopped: list[tuple[str, str]] = []
        self._protocol: dict[str, Any] | None = None
        self._protocol_sha256 = ""
        self._source_commit = ""
        self._source_tree = ""
        self._source_manifest: dict[str, str] = {}
        self._tracked_source_sha256: dict[str, str] = {}
        self._protocol_file_sha256 = ""
        self._image_inspect_raw = b""
        self._gpu_observation_raw = b""
        self._snapshot_manifest_raw = b""
        self._container_inspect_raw = b""
        self._container_identity: dict[str, str] = {}
        self.teardown_observation: dict[str, str] | None = None
        self.runtime_binding: dict[str, Any] | None = None

    @staticmethod
    def _subprocess(argv: tuple[str, ...]) -> bytes:
        result = subprocess.run(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )
        if result.returncode:
            raise LaunchRefused("G1 micro DGX command failed: " + argv[0])
        return result.stdout

    def _text(self, argv: tuple[str, ...]) -> str:
        return self.command(argv).decode("utf-8", "strict").strip()

    @property
    def port(self) -> int:
        match = _ENDPOINT.fullmatch(self.spec.endpoint)
        if match is None:
            raise LaunchRefused("G1 micro DGX endpoint must be exact loopback")
        return int(match.group(1))

    def _validate(self) -> None:
        spec = self.spec
        if _NAME.fullmatch(spec.container_name) is None:
            raise LaunchRefused("G1 micro DGX container name is invalid")
        if (
            not spec.repo_root.is_absolute()
            or spec.repo_root.is_symlink()
            or not spec.repo_root.is_dir()
            or not spec.protocol_path.is_absolute()
            or spec.protocol_path.is_symlink()
            or not spec.protocol_path.is_file()
            or not spec.protocol_path.is_relative_to(spec.repo_root)
        ):
            raise LaunchRefused("G1 micro DGX source or protocol path is invalid")
        if self._text(("git", "-C", str(spec.repo_root), "status", "--porcelain")):
            raise LaunchRefused("G1 micro DGX source checkout is dirty")
        self._source_commit = self._text(
            ("git", "-C", str(spec.repo_root), "rev-parse", "HEAD")
        )
        if re.fullmatch(r"[0-9a-f]{40}", self._source_commit) is None:
            raise LaunchRefused("G1 micro DGX source commit is invalid")
        self._source_tree = self._text(
            ("git", "-C", str(spec.repo_root), "rev-parse", "HEAD^{tree}")
        )
        if re.fullmatch(r"[0-9a-f]{40}", self._source_tree) is None:
            raise LaunchRefused("G1 micro DGX source tree is invalid")
        protocol_relative = spec.protocol_path.relative_to(spec.repo_root).as_posix()
        if protocol_relative not in g1_micro.DGX_PROTOCOL_PATHS:
            raise LaunchRefused("G1 micro DGX protocol path is not canonical")
        selected_paths = g1_micro.dgx_tracked_source_paths_for_protocol_path(
            protocol_relative
        )
        for relative in selected_paths:
            current = (spec.repo_root / relative).read_bytes()
            committed = self.command(
                ("git", "-C", str(spec.repo_root), "show", f"HEAD:{relative}")
            )
            if current != committed:
                raise LaunchRefused("G1 micro DGX source differs from its commit")
            self._tracked_source_sha256[relative] = sha256(current).hexdigest()
        self._protocol_file_sha256 = self._tracked_source_sha256[
            protocol_relative
        ]
        self._protocol, self._protocol_sha256 = g1_micro.load_protocol(
            spec.protocol_path
        )
        if self._protocol.get("schema_version") == g1_micro.OPAQUE_PILOT_PROTOCOL:
            if (
                spec.evaluator_reveal is None
                or not spec.evaluator_reveal.is_absolute()
                or spec.evaluator_reveal.is_symlink()
                or not spec.evaluator_reveal.is_file()
            ):
                raise LaunchRefused("opaque pilot requires a regular external evaluator reveal")
            try:
                reveal = g1_micro._canonical_object(
                    spec.evaluator_reveal.read_bytes(), "opaque evaluator reveal preflight"
                )
                if (
                    reveal.get("schema_version") != "hswm-g1-opaque-evaluator-reveal/v1"
                    or reveal.get("study_uid") != self._protocol["study_uid"]
                    or reveal.get("protocol_canonical_sha256") != self._protocol_sha256
                    or reveal.get("reveal_commitment_root")
                    != self._protocol["evaluator_reveal_contract"]["reveal_commitment_root"]
                ):
                    raise ValueError
                g1_micro.opaque_pilot_tasks(self._protocol, reveal)
            except (ValueError, g1_micro.G1MicroError) as error:
                raise LaunchRefused("opaque pilot evaluator reveal cannot satisfy preflight") from error
        binding = self._protocol["live_binding"]
        if spec.endpoint != binding["endpoint_origin"]:
            raise LaunchRefused("G1 micro DGX endpoint differs from protocol")
        self._source_manifest = g1_micro._source_manifest()
        for path in (
            spec.lock_path,
            spec.model_snapshot,
            spec.hf_cache,
            spec.compile_cache,
            spec.output_dir,
            spec.runtime_binding_path,
            spec.execution_registry,
        ):
            if not path.is_absolute() or path.is_symlink():
                raise LaunchRefused("G1 micro DGX path is linked or relative")
        if (
            spec.output_dir.exists()
            or spec.runtime_binding_path.exists()
            or spec.execution_registry.exists()
            or str(spec.execution_registry)
            != self._protocol["consumption_registry"]["path"]
            or not spec.execution_registry.parent.is_dir()
            or spec.execution_registry.parent.is_symlink()
        ):
            raise LaunchRefused("G1 micro DGX one-shot artifacts are unavailable")
        output_root = Path(os.environ.get("HSWM_OUTPUT_ROOT", ""))
        if (
            not output_root.is_absolute()
            or output_root.is_symlink()
            or not output_root.is_dir()
            or output_root not in spec.output_dir.parents
            or output_root not in spec.runtime_binding_path.parents
        ):
            raise LaunchRefused("G1 micro DGX artifacts are outside wrapper output")
        if any(path.exists() for path in (spec.hf_cache, spec.compile_cache)) or any(
            not path.parent.is_dir() or path.parent.is_symlink()
            for path in (spec.hf_cache, spec.compile_cache)
        ):
            raise LaunchRefused("G1 micro DGX caches are not fresh")
        self._image_inspect_raw = self.command(
            ("docker", "image", "inspect", binding["container_image"])
        )
        image = json.loads(self._image_inspect_raw.decode("utf-8", "strict"))
        if (
            type(image) is not list
            or len(image) != 1
            or image[0].get("Id") != binding["container_image_id"]
            or binding["container_image"] not in image[0].get("RepoDigests", [])
        ):
            raise LaunchRefused("G1 micro DGX image identity drifted")
        self._gpu_observation_raw = self.command(
            (
                "nvidia-smi",
                "--query-gpu=uuid,name",
                "--format=csv,noheader,nounits",
            )
        )
        gpu_rows = [
            item.strip()
            for item in self._gpu_observation_raw.decode("utf-8", "strict").split(",")
        ]
        if gpu_rows != [binding["gpu_uuid"], binding["gpu_name"]]:
            raise LaunchRefused("G1 micro DGX GPU identity drifted")
        manifest = build_model_snapshot_manifest(
            spec.model_snapshot.parents[2],
            repository=binding["model_repository"],
            revision=binding["model_revision"],
        )
        self._snapshot_manifest_raw = canonical_json_bytes(manifest)
        if (
            not spec.model_snapshot.is_dir()
            or spec.model_snapshot.is_symlink()
            or sha256(self._snapshot_manifest_raw).hexdigest()
            != binding["model_snapshot_manifest_sha256"]
        ):
            raise LaunchRefused("G1 micro DGX model snapshot drifted")

    def _acquire_lock(self) -> None:
        path = self.spec.lock_path
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise LaunchRefused("G1 micro DGX lock parent unavailable")
        descriptor = os.open(
            path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise LaunchRefused("G1 micro DGX lock is not regular")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(descriptor)
            raise
        self._lock = descriptor

    def _assert_prelaunch_quiescence(self) -> None:
        spec = self.spec
        if (
            self._text(("docker", "ps", "-q"))
            or self._text(
                ("docker", "ps", "-aq", "--filter", f"name=^/{spec.container_name}$")
            )
            or self._text(
                (
                    "nvidia-smi",
                    "--query-compute-apps=gpu_uuid,pid",
                    "--format=csv,noheader,nounits",
                )
            )
            or f"127.0.0.1:{self.port}"
            in self._text(("sudo", "-n", "ss", "-ltnpH"))
        ):
            raise LaunchRefused("G1 micro DGX prelaunch boundary is not quiescent")

    def _server_argv(self) -> tuple[str, ...]:
        if self._protocol is None:
            raise LaunchRefused("G1 micro DGX protocol was not validated")
        return tuple(g1_micro.expected_dgx_server_argv(self._protocol))

    def _launch(self) -> None:
        spec = self.spec
        assert self._protocol is not None
        binding = self._protocol["live_binding"]
        spec.hf_cache.mkdir(parents=True, mode=0o700)
        spec.compile_cache.mkdir(mode=0o700)
        required_environment = (
            "HF_HOME=/cache/huggingface",
            "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub",
            "VLLM_CACHE_ROOT=/cache/compile/vllm",
            "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor",
            "TRITON_CACHE_DIR=/cache/compile/triton",
            "HF_HUB_OFFLINE=1",
            "TRANSFORMERS_OFFLINE=1",
            "VLLM_ENABLE_V1_MULTIPROCESSING=0",
            "PYTHONHASHSEED=0",
            "CUBLAS_WORKSPACE_CONFIG=:4096:8",
        )
        argv = [
            "docker",
            "run",
            "-d",
            "--pull",
            "never",
            "--name",
            spec.container_name,
            "--restart",
            "no",
            "--network",
            "bridge",
            "--ipc",
            "private",
            "-p",
            f"127.0.0.1:{self.port}:8000",
            "--gpus",
            f"device={binding['gpu_uuid']}",
            "--mount",
            f"type=bind,src={spec.model_snapshot.parents[1]},dst=/model-repository,readonly",
            "--mount",
            f"type=bind,src={spec.hf_cache},dst=/cache/huggingface",
            "--mount",
            f"type=bind,src={spec.compile_cache},dst=/cache/compile",
        ]
        for item in required_environment:
            argv.extend(("-e", item))
        raw_id = self.command(
            tuple([*argv, binding["container_image"], *self._server_argv()])
        ).strip()
        if re.fullmatch(rb"[0-9a-f]{64}", raw_id) is None:
            raise LaunchRefused("G1 micro DGX launch did not return a container id")
        self._started = True
        try:
            self._container_inspect_raw = self.command(
                ("docker", "inspect", spec.container_name)
            )
            row = json.loads(self._container_inspect_raw.decode("utf-8", "strict"))[0]
            host = row["HostConfig"]
            ports = host.get("PortBindings", {}).get("8000/tcp")
            if (
                row.get("Id") != raw_id.decode("ascii")
                or row.get("Image") != binding["container_image_id"]
                or row.get("Config", {}).get("Image") != binding["container_image"]
                or row.get("Config", {}).get("Cmd") != list(self._server_argv())
                or not set(required_environment).issubset(
                    set(row.get("Config", {}).get("Env", []))
                )
                or host.get("NetworkMode") != "bridge"
                or host.get("IpcMode") != "private"
                or ports != [{"HostIp": "127.0.0.1", "HostPort": str(self.port)}]
            ):
                raise ValueError
            self._container_identity = {
                "container_id_sha256": sha256(raw_id).hexdigest(),
                "container_start_sha256": sha256(
                    row["State"]["StartedAt"].encode("utf-8")
                ).hexdigest(),
            }
        except Exception as error:
            raise LaunchRefused("G1 micro DGX container identity drifted") from error

    def attest(self, completed: int) -> dict[str, bytes]:
        if not self._started or self._protocol is None or not 0 <= completed <= g1_micro.expected_completion_posts(self._protocol):
            raise LaunchRefused("G1 micro DGX attestation count is invalid")
        binding = self._protocol["live_binding"]
        try:
            container_raw = self.command(("docker", "inspect", self.spec.container_name))
            row = json.loads(container_raw.decode("utf-8", "strict"))[0]
            if (
                sha256(row["Id"].encode("utf-8")).hexdigest()
                != self._container_identity["container_id_sha256"]
                or sha256(row["State"]["StartedAt"].encode("utf-8")).hexdigest()
                != self._container_identity["container_start_sha256"]
                or row.get("Image") != binding["container_image_id"]
                or row.get("Config", {}).get("Cmd") != list(self._server_argv())
            ):
                raise ValueError
        except Exception as error:
            raise LaunchRefused("G1 micro DGX container continuity drifted") from error
        models_raw = self.http_get(f"{self.spec.endpoint}/v1/models")
        version_raw = self.http_get(f"{self.spec.endpoint}/version")
        models = json.loads(models_raw.decode("utf-8", "strict"))
        version = json.loads(version_raw.decode("utf-8", "strict"))
        metrics = self.http_get(f"{self.spec.endpoint}/metrics")
        successes = g1_micro.parse_vllm_success_total(metrics)
        model_ids = [
            item.get("id")
            for item in models.get("data", [])
            if isinstance(item, dict)
        ]
        if (
            version.get("version") != binding["vllm_version"]
            or model_ids != [binding["served_model"]]
            or successes != completed
        ):
            raise LaunchRefused("G1 micro DGX service attestation drifted")
        return {
            "container_inspect": container_raw,
            "metrics": metrics,
            "models": models_raw,
            "version": version_raw,
        }

    def __enter__(self) -> "DGXFreshRuntime":
        self._validate()
        self._acquire_lock()
        try:
            self._stopped = self.stop_services([])
            self._assert_prelaunch_quiescence()
            self._launch()
            deadline = time.monotonic() + 900
            while True:
                try:
                    startup = self.attest(0)
                    break
                except LoopbackUnavailable:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(2)
            assert self._protocol is not None
            self.runtime_binding = make_runtime_binding_record(
                protocol=self._protocol,
                protocol_sha256=self._protocol_sha256,
                source_commit=self._source_commit,
                source_tree=self._source_tree,
                source_manifest=self._source_manifest,
                tracked_source_sha256=self._tracked_source_sha256,
                protocol_file_sha256=self._protocol_file_sha256,
                container_id_sha256=self._container_identity["container_id_sha256"],
                container_start_sha256=self._container_identity[
                    "container_start_sha256"
                ],
                container_inspect_raw=self._container_inspect_raw,
                image_inspect_raw=self._image_inspect_raw,
                gpu_observation_raw=self._gpu_observation_raw,
                snapshot_manifest_raw=self._snapshot_manifest_raw,
                startup_metrics_raw=startup["metrics"],
                startup_models_raw=startup["models"],
                startup_version_raw=startup["version"],
            )
            return self
        except Exception:
            self.close()
            raise

    def _quiescent(self) -> bool:
        docker = self.command(("docker", "ps", "-q"))
        gpu = self.command(
            (
                "nvidia-smi",
                "--query-compute-apps=gpu_uuid,pid",
                "--format=csv,noheader,nounits",
            )
        )
        listeners = self.command(("sudo", "-n", "ss", "-ltnpH"))
        quiet = (
            not docker.strip()
            and not gpu.strip()
            and f"127.0.0.1:{self.port}" not in listeners.decode("utf-8", "strict")
        )
        if quiet:
            self.teardown_observation = {
                "docker_ps_utf8": docker.decode("utf-8", "strict"),
                "gpu_compute_utf8": gpu.decode("utf-8", "strict"),
                "listeners_utf8": listeners.decode("utf-8", "strict"),
            }
        return quiet

    def close(self) -> None:
        unsafe = False
        try:
            if self._started:
                self.command(("docker", "rm", "-f", self.spec.container_name))
                self._started = False
            deadline = time.monotonic() + 60
            while not self._quiescent():
                if time.monotonic() >= deadline:
                    unsafe = True
                    break
                time.sleep(1)
            if not unsafe and self._stopped:
                self.restore_services(self._stopped)
        finally:
            if self._lock is not None:
                fcntl.flock(self._lock, fcntl.LOCK_UN)
                os.close(self._lock)
                self._lock = None
        if unsafe:
            raise LaunchRefused(
                "G1 micro DGX teardown unsafe; shared services were left stopped"
            )

    def __exit__(self, *_: object) -> None:
        self.close()


def verify_dgx_execution_receipt(
    *,
    receipt: Mapping[str, Any],
    bundle: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    """Join final service evidence and teardown to the completed local bundle."""

    g1_micro.validate_record(receipt, kind="DGXRuntimeExecutionReceipt")
    payload = receipt["payload"]
    runtime_binding = bundle.get("runtime_binding")
    expected_fields = {
        "bundle_sha256",
        "completion_posts",
        "final_container_inspect_json",
        "final_container_inspect_sha256",
        "final_metrics_sha256",
        "final_metrics_utf8",
        "final_models_json",
        "final_models_sha256",
        "final_version_json",
        "final_version_sha256",
        "network_boundary",
        "runtime_image_identity_verified",
        "shared_service_snapshot",
        "shared_services_restored_after_quiescence",
        "successful_generation_requests",
        "teardown_observation",
        "terminal",
        "tokenize_posts",
    }
    expected_posts = g1_micro.expected_completion_posts(protocol)
    if (
        receipt["owner_uid"] != "principal:g1-micro-dgx-runtime-custodian"
        or not isinstance(runtime_binding, Mapping)
        or receipt["refs"] != [g1_micro._ref("runtime_binding", runtime_binding)]
        or set(payload) != expected_fields
        or payload["bundle_sha256"] != bundle.get("bundle_sha256")
        or payload["completion_posts"] != expected_posts
        or payload["tokenize_posts"] != expected_posts
        or payload["successful_generation_requests"] != expected_posts
        or payload["terminal"] != bundle.get("terminal")
        or payload["runtime_image_identity_verified"] is not True
        or payload["network_boundary"] != g1_micro.DGX_NETWORK_BOUNDARY
        or payload["shared_services_restored_after_quiescence"] is not True
    ):
        raise LaunchRefused("G1 micro DGX execution receipt drifted")
    raw_fields = {
        "final_container_inspect_json": "final_container_inspect_sha256",
        "final_metrics_utf8": "final_metrics_sha256",
        "final_models_json": "final_models_sha256",
        "final_version_json": "final_version_sha256",
    }
    raw: dict[str, bytes] = {}
    for field, digest_field in raw_fields.items():
        value = payload[field]
        if not isinstance(value, str):
            raise LaunchRefused("G1 micro DGX final evidence is not text")
        encoded = value.encode("utf-8")
        if (
            not encoded
            or len(encoded) > 4_000_000
            or sha256(encoded).hexdigest() != payload[digest_field]
        ):
            raise LaunchRefused("G1 micro DGX final evidence preimage drifted")
        raw[field] = encoded
    try:
        container = json.loads(raw["final_container_inspect_json"])[0]
        models = json.loads(raw["final_models_json"])
        version = json.loads(raw["final_version_json"])
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise LaunchRefused("G1 micro DGX final JSON evidence is invalid") from error
    runtime_payload = runtime_binding["payload"]
    expected_argv = g1_micro.expected_dgx_server_argv(protocol)
    teardown = payload["teardown_observation"]
    services = payload["shared_service_snapshot"]
    if (
        not isinstance(container, dict)
        or sha256(str(container.get("Id", "")).encode()).hexdigest()
        != runtime_payload["container_id_sha256"]
        or sha256(str(container.get("State", {}).get("StartedAt", "")).encode()).hexdigest()
        != runtime_payload["container_start_sha256"]
        or container.get("Image") != protocol["live_binding"]["container_image_id"]
        or container.get("Config", {}).get("Cmd") != expected_argv
        or g1_micro.parse_vllm_success_total(raw["final_metrics_utf8"]) != expected_posts
        or not isinstance(models, dict)
        or [item.get("id") for item in models.get("data", []) if isinstance(item, dict)]
        != [protocol["live_binding"]["served_model"]]
        or not isinstance(version, dict)
        or version.get("version") != protocol["live_binding"]["vllm_version"]
        or not isinstance(teardown, Mapping)
        or set(teardown) != {"docker_ps_utf8", "gpu_compute_utf8", "listeners_utf8"}
        or teardown["docker_ps_utf8"].strip()
        or teardown["gpu_compute_utf8"].strip()
        or "127.0.0.1:18080" in teardown["listeners_utf8"]
        or not isinstance(services, list)
        or len({item.get("name") for item in services if isinstance(item, dict)})
        != len(services)
        or any(
            not isinstance(item, dict)
            or set(item) != {"container_id_sha256", "name"}
            or item["name"] not in {"vllm-receiver", "vllm", "comfyui-10eros"}
            or re.fullmatch(r"[0-9a-f]{64}", item["container_id_sha256"])
            is None
            for item in services
        )
    ):
        raise LaunchRefused("G1 micro DGX final service evidence does not close")
    return {
        "bundle_sha256": bundle["bundle_sha256"],
        "receipt_sha256": receipt["record_sha256"],
        "successful_generation_requests": expected_posts,
        "terminal": bundle["terminal"],
        "verification": "VALID_LOCAL_DGX_FINAL_ATTESTATION_AND_RESTORATION_JOIN",
    }


def _prepare_opaque_tokenizer_before_runtime_mutation(
    spec: DGXFreshSpec,
) -> tuple[str, dict[str, Any] | None]:
    """Validate and measure before stopping services or launching vLLM."""

    preflight = DGXFreshRuntime(spec)
    preflight._validate()
    assert preflight._protocol is not None
    if preflight._protocol.get("schema_version") != g1_micro.OPAQUE_PILOT_PROTOCOL:
        return preflight._protocol_sha256, None
    receipt = offline_action_code_tokenizer_receipt(
        command=preflight.command,
        snapshot=spec.model_snapshot,
        tokenizer_binding=preflight._protocol["tokenizer_binding"],
    )
    _validate_opaque_tokenizer_receipt(receipt, preflight._protocol["tokenizer_binding"])
    return preflight._protocol_sha256, receipt


def run_dgx_micro(spec: DGXFreshSpec) -> dict[str, Any]:
    """Run the official one-shot slice and retain the runtime lifecycle receipt."""

    prepared_protocol_sha256, tokenizer_receipt = (
        _prepare_opaque_tokenizer_before_runtime_mutation(spec)
    )
    with DGXFreshRuntime(spec) as runtime:
        if runtime.runtime_binding is None:
            raise LaunchRefused("G1 micro DGX startup binding is absent")
        g1_micro._atomic_write(
            spec.runtime_binding_path,
            canonical_json_bytes(runtime.runtime_binding),
        )
        assert runtime._protocol is not None
        if runtime._protocol_sha256 != prepared_protocol_sha256:
            raise LaunchRefused("G1 micro DGX protocol drifted after tokenizer preflight")
        binding = runtime._protocol["live_binding"]
        if runtime._protocol.get("schema_version") == g1_micro.OPAQUE_PILOT_PROTOCOL:
            if tokenizer_receipt is None:
                raise LaunchRefused("opaque tokenizer preflight receipt is absent")
            _validate_opaque_tokenizer_receipt(
                tokenizer_receipt, runtime._protocol["tokenizer_binding"]
            )
        bundle = g1_micro.run_exploratory_slice(
            protocol_path=spec.protocol_path,
            endpoint=spec.endpoint,
            model=binding["served_model"],
            expected_max_model_len=binding["expected_max_model_len"],
            output_dir=spec.output_dir,
            execution_registry_path=spec.execution_registry,
            runtime_binding_path=spec.runtime_binding_path,
            evaluator_reveal_path=spec.evaluator_reveal,
            tokenizer_receipt=tokenizer_receipt,
        )
        expected_posts = g1_micro.expected_completion_posts(runtime._protocol)
        final = runtime.attest(expected_posts)
        stopped = list(runtime._stopped)
        runtime_binding = runtime.runtime_binding
    if runtime.teardown_observation is None:
        raise LaunchRefused("G1 micro DGX teardown observation is absent")
    restored = _active_shared_containers()
    if restored != stopped:
        raise LaunchRefused("G1 micro DGX shared-service restoration identity drifted")
    verified = g1_micro.verify_frozen_execution_files(
        bundle_path=spec.output_dir / "result.json",
        protocol_path=spec.protocol_path,
        execution_registry_path=spec.execution_registry,
    )
    receipt = g1_micro.make_record(
        "DGXRuntimeExecutionReceipt",
        owner_uid="principal:g1-micro-dgx-runtime-custodian",
        payload={
            "bundle_sha256": bundle["bundle_sha256"],
            "completion_posts": expected_posts,
            "final_container_inspect_json": final["container_inspect"].decode(
                "utf-8", "strict"
            ),
            "final_container_inspect_sha256": sha256(
                final["container_inspect"]
            ).hexdigest(),
            "final_metrics_sha256": sha256(final["metrics"]).hexdigest(),
            "final_metrics_utf8": final["metrics"].decode("utf-8", "strict"),
            "final_models_json": final["models"].decode("utf-8", "strict"),
            "final_models_sha256": sha256(final["models"]).hexdigest(),
            "final_version_json": final["version"].decode("utf-8", "strict"),
            "final_version_sha256": sha256(final["version"]).hexdigest(),
            "network_boundary": g1_micro.DGX_NETWORK_BOUNDARY,
            "runtime_image_identity_verified": True,
            "shared_service_snapshot": [
                {
                    "container_id_sha256": sha256(
                        identifier.encode("utf-8")
                    ).hexdigest(),
                    "name": name,
                }
                for name, identifier in stopped
            ],
            "shared_services_restored_after_quiescence": True,
            "successful_generation_requests": expected_posts,
            "teardown_observation": dict(runtime.teardown_observation),
            "terminal": bundle["terminal"],
            "tokenize_posts": expected_posts,
        },
        refs=(g1_micro._ref("runtime_binding", runtime_binding),),
    )
    protocol, _ = g1_micro.load_protocol(spec.protocol_path)
    verify_dgx_execution_receipt(receipt=receipt, bundle=bundle, protocol=protocol)
    g1_micro._atomic_write(
        spec.output_dir / "dgx_runtime_receipt.json", canonical_json_bytes(receipt)
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-snapshot", type=Path, required=True)
    parser.add_argument("--lock-path", type=Path, required=True)
    parser.add_argument("--execution-registry", type=Path, required=True)
    parser.add_argument("--evaluator-reveal", type=Path)
    parser.add_argument("--container-name", default="hswm-g1-micro-001")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    output_root = Path(os.environ["HSWM_OUTPUT_ROOT"])
    cache_root = Path(os.environ["HSWM_CACHE_ROOT"])
    spec = DGXFreshSpec(
        repo_root=Path.cwd(),
        protocol_path=args.protocol.resolve(),
        output_dir=output_root / "g1_micro",
        runtime_binding_path=output_root / "g1_micro_runtime_binding.json",
        execution_registry=args.execution_registry,
        lock_path=args.lock_path,
        container_name=args.container_name,
        model_snapshot=args.model_snapshot,
        hf_cache=cache_root / "g1_micro_hf",
        compile_cache=cache_root / "g1_micro_compile",
        evaluator_reveal=(None if args.evaluator_reveal is None else args.evaluator_reveal.resolve()),
    )
    if args.preflight_only:
        runtime = DGXFreshRuntime(spec)
        runtime._validate()
        tokenizer_receipt = None
        assert runtime._protocol is not None
        if runtime._protocol.get("schema_version") == g1_micro.OPAQUE_PILOT_PROTOCOL:
            tokenizer_receipt = offline_action_code_tokenizer_receipt(
                command=runtime.command,
                snapshot=spec.model_snapshot,
                tokenizer_binding=runtime._protocol["tokenizer_binding"],
            )
            _validate_opaque_tokenizer_receipt(
                tokenizer_receipt, runtime._protocol["tokenizer_binding"]
            )
        print(
            canonical_json_bytes(
                {
                    "ephemeral_offline_tokenizer_containers": (
                        1 if tokenizer_receipt is not None else 0
                    ),
                    "network_calls": 0,
                    "offline_tokenizer_receipt_sha256": (
                        None
                        if tokenizer_receipt is None
                        else tokenizer_receipt["receipt_sha256"]
                    ),
                    "protocol_canonical_sha256": runtime._protocol_sha256,
                    "service_mutations": 0,
                    "source_commit": runtime._source_commit,
                    "status": "READY_FOR_ONE_FRESH_DGX_EXPLORATION",
                }
            ).decode("utf-8")
        )
        return 0
    receipt = run_dgx_micro(spec)
    print(canonical_json_bytes(receipt).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
