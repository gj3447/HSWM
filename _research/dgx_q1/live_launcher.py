"""Exclusive, observed DGX service lease for the frozen live-Q1 runner.

The launcher performs no model POST. It validates the checked-in freeze and
its publication CI receipt, re-hashes the local model snapshot, launches one
digest-pinned loopback-only vLLM target, and emits typed boundary observations
for the sole live runner. Teardown precedes lease release.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import fcntl
from hashlib import sha1, sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_q1.github_ci_receipt import (
    GitHubCiReceiptRefusal,
    parse_github_actions_ci_receipt,
)
from _research.dgx_q1.live_protocol import (
    BOUNDARY_SCHEMA,
    NAMESPACE,
    strict_json,
    validate_boundary_attestation,
    validate_live_q1_plan,
    validate_live_q1_start_marker,
)
from _research.dgx_q1.model_snapshot_manifest import build_model_snapshot_manifest


_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
_GPU = re.compile(r"^GPU-[0-9a-f-]{8,80}$")
_SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./-]{1,768}$")
_MAX_OUTPUT = 16 * 1024 * 1024
_IDENTITY_NAMES = {
    "endpoint_sha256",
    "model_identity_sha256",
    "runtime_identity_sha256",
    "tls_identity_sha256",
    "declared_isolation_contract_sha256",
    "model_snapshot_manifest_sha256",
}


class LaunchRefused(RuntimeError):
    """The live target cannot be joined to the frozen control boundary."""


class LoopbackUnavailable(LaunchRefused):
    """A connection-level readiness condition; identity failures are not retryable."""


@dataclass(frozen=True, slots=True, kw_only=True)
class LiveQ1Spec:
    repo_root: Path
    expected_commit: str
    expected_tree: str
    publication_ci_receipt: Path
    publication_ci_receipt_sha256: str
    freeze_root: Path
    plan_sha256: str
    lock_path: Path
    container_name: str
    model_snapshot: Path
    hf_cache: Path
    compile_cache: Path


Command = Callable[[tuple[str, ...]], bytes]
HttpGet = Callable[[str], bytes]


def _safe_path(path: Path, label: str) -> Path:
    if not isinstance(path, Path) or _SAFE_PATH.fullmatch(str(path)) is None:
        raise LaunchRefused(f"{label} is outside the closed absolute-path vocabulary")
    return path


def _validate_ci_receipt(raw: bytes, commit: str, tree: str) -> dict[str, Any]:
    try:
        return parse_github_actions_ci_receipt(
            raw,
            repository="gj3447/HSWM",
            commit=commit,
            tree=tree,
        )
    except GitHubCiReceiptRefusal as error:
        raise LaunchRefused(
            "publication CI receipt semantic binding drifted"
        ) from error


def _validate_runtime_identity(raw: bytes) -> dict[str, Any]:
    try:
        runtime = parse_canonical(raw)
    except Exception as error:
        raise LaunchRefused("runtime identity is not canonical JSON") from error
    keys = {
        "schema_version",
        "container_image",
        "image_id",
        "vllm_version",
        "gpu_uuid",
        "gpu_name",
        "gpu_driver_version",
        "gpu_compute_capability",
        "endpoint",
        "served_model",
        "model_revision",
        "model_snapshot_manifest_sha256",
        "max_model_len",
        "max_num_seqs",
        "gpu_memory_utilization_milli",
        "prefix_cache",
        "enforce_eager",
        "batch_invariant",
        "v1_multiprocessing",
        "model_loading_offline",
        "generation_config",
        "engine_seed",
        "language_model_only",
        "container_internal_port",
        "container_network_mode",
        "container_ipc_mode",
        "host_publish_ip",
    }
    if type(runtime) is not dict or set(runtime) != keys:
        raise LaunchRefused("runtime identity key set drifted")
    if (
        runtime["schema_version"] != "hswm-dgx-q1-runtime-identity/v1"
        or type(runtime["container_image"]) is not str
        or _IMAGE.fullmatch(runtime["container_image"]) is None
        or type(runtime["image_id"]) is not str
        or _IMAGE_ID.fullmatch(runtime["image_id"]) is None
        or type(runtime["vllm_version"]) is not str
        or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", runtime["vllm_version"]) is None
        or type(runtime["gpu_uuid"]) is not str
        or _GPU.fullmatch(runtime["gpu_uuid"]) is None
        or any(
            type(runtime[name]) is not str or not runtime[name]
            for name in ("gpu_name", "gpu_driver_version", "gpu_compute_capability")
        )
        or type(runtime["endpoint"]) is not str
        or re.fullmatch(
            r"http://127\.0\.0\.1:([1-9][0-9]{0,4})/v1/chat/completions",
            runtime["endpoint"],
        )
        is None
        or type(runtime["served_model"]) is not str
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", runtime["served_model"]) is None
        or type(runtime["model_revision"]) is not str
        or _GIT.fullmatch(runtime["model_revision"]) is None
        or type(runtime["model_snapshot_manifest_sha256"]) is not str
        or _SHA.fullmatch(runtime["model_snapshot_manifest_sha256"]) is None
        or type(runtime["max_model_len"]) is not int
        or not 1 <= runtime["max_model_len"] <= 1_000_000
        or runtime["max_num_seqs"] != 1
        or type(runtime["gpu_memory_utilization_milli"]) is not int
        or not 100 <= runtime["gpu_memory_utilization_milli"] <= 990
        or runtime["prefix_cache"] is not False
        or runtime["enforce_eager"] is not True
        or runtime["batch_invariant"] is not True
        or runtime["v1_multiprocessing"] is not False
        or runtime["model_loading_offline"] is not True
        or runtime["generation_config"] != "vllm"
        or runtime["engine_seed"] != 0
        or runtime["language_model_only"] is not True
        or runtime["container_internal_port"] != 8000
        or runtime["container_network_mode"] != "bridge"
        or runtime["container_ipc_mode"] != "private"
        or runtime["host_publish_ip"] != "127.0.0.1"
    ):
        raise LaunchRefused("runtime identity semantic boundary drifted")
    return runtime


def _read_freeze(spec: LiveQ1Spec) -> dict[str, Any]:
    root = spec.freeze_root
    if root.is_symlink() or not root.is_dir():
        raise LaunchRefused("freeze root is absent or symlinked")
    closure_raw = (root / "closure_manifest.json").read_bytes()
    try:
        closure = parse_canonical(closure_raw)
    except Exception as error:
        raise LaunchRefused("freeze closure is not canonical JSON") from error
    if (
        type(closure) is not dict
        or set(closure) != {"schema_version", "namespace", "artifacts"}
        or closure["schema_version"] != "hswm-dgx-q1-live-preregistration-freeze/v1"
        or closure["namespace"] != NAMESPACE
        or type(closure["artifacts"]) is not list
        or not closure["artifacts"]
    ):
        raise LaunchRefused("freeze closure shape drifted")
    declared: dict[str, tuple[str, int]] = {}
    for item in closure["artifacts"]:
        if type(item) is not dict or set(item) != {"path", "sha256", "byte_length"}:
            raise LaunchRefused("freeze artifact descriptor drifted")
        relative = PurePosixPath(item["path"]) if type(item["path"]) is str else None
        if (
            relative is None
            or relative.is_absolute()
            or not relative.parts
            or ".." in relative.parts
            or item["path"] in declared
            or type(item["sha256"]) is not str
            or _SHA.fullmatch(item["sha256"]) is None
            or type(item["byte_length"]) is not int
            or item["byte_length"] < 0
        ):
            raise LaunchRefused("freeze artifact path/hash drifted")
        declared[item["path"]] = (item["sha256"], item["byte_length"])
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "closure_manifest.json"
    }
    if actual != set(declared) or any(path.is_symlink() for path in root.rglob("*")):
        raise LaunchRefused("freeze file closure drifted")
    artifacts: dict[str, bytes] = {}
    for relative, (digest, length) in declared.items():
        raw = (root / relative).read_bytes()
        if len(raw) != length or sha256(raw).hexdigest() != digest:
            raise LaunchRefused("freeze artifact bytes drifted")
        artifacts[relative] = raw
    plan_raw = artifacts.get("plan.json")
    marker_raw = artifacts.get("start_marker.json")
    if plan_raw is None or marker_raw is None or sha256(plan_raw).hexdigest() != spec.plan_sha256:
        raise LaunchRefused("freeze plan hash drifted")
    plan = validate_live_q1_plan(plan_raw)
    validate_live_q1_start_marker(marker_raw, plan_raw)
    identities = {
        name: artifacts.get(f"identities/{name}.json") for name in _IDENTITY_NAMES
    }
    if any(value is None for value in identities.values()) or any(
        sha256(identities[name]).hexdigest() != plan["identities"][name]  # type: ignore[arg-type]
        for name in identities
    ):
        raise LaunchRefused("freeze identity bindings drifted")
    runtime = _validate_runtime_identity(identities["runtime_identity_sha256"])  # type: ignore[arg-type]
    endpoint = parse_canonical(identities["endpoint_sha256"])  # type: ignore[arg-type]
    model = parse_canonical(identities["model_identity_sha256"])  # type: ignore[arg-type]
    if (
        type(endpoint) is not dict
        or endpoint.get("endpoint") != runtime["endpoint"]
        or type(model) is not dict
        or model.get("model") != runtime["served_model"]
        or model.get("revision") != runtime["model_revision"]
        or model.get("snapshot_manifest_sha256")
        != runtime["model_snapshot_manifest_sha256"]
        or runtime["model_snapshot_manifest_sha256"]
        != plan["identities"]["model_snapshot_manifest_sha256"]
    ):
        raise LaunchRefused("freeze endpoint/model/runtime join drifted")
    return {
        "plan_raw": plan_raw,
        "plan": plan,
        "identities": identities,
        "runtime": runtime,
        "model": model,
        "snapshot_manifest_raw": identities["model_snapshot_manifest_sha256"],
        "freeze_files": {
            "closure_manifest.json": closure_raw,
            **artifacts,
        },
    }


def _git_blob_sha1(raw: bytes) -> str:
    header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
    return sha1(header + raw).hexdigest()


class SubprocessCommandReader:
    """Closed-argv executor: no shell, caller environment, or stdin channel."""

    _PROGRAMS = {"git", "docker", "nvidia-smi", "ss", "cat", "readlink", "ps", "test", "find"}

    def __call__(self, argv: tuple[str, ...]) -> bytes:
        if not argv or argv[0] not in self._PROGRAMS:
            raise LaunchRefused("command program is not allowlisted")
        try:
            result = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=120,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise LaunchRefused("allowlisted command failed") from error
        if len(result.stdout) > _MAX_OUTPUT:
            raise LaunchRefused("command output exceeds bound")
        return result.stdout


def _get(url: str) -> bytes:
    if re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}/(?:version|v1/models|metrics)", url) is None:
        raise LaunchRefused("HTTP GET endpoint is not allowlisted")
    try:
        with urlopen(Request(url, method="GET"), timeout=10) as response:
            raw = response.read(_MAX_OUTPUT + 1)
    except (OSError, URLError) as error:
        raise LoopbackUnavailable("loopback GET is not ready") from error
    if len(raw) > _MAX_OUTPUT:
        raise LaunchRefused("loopback GET body exceeds bound")
    return raw


def _text(command: Command, argv: tuple[str, ...]) -> str:
    try:
        return command(argv).decode("utf-8", errors="strict").strip()
    except Exception as error:
        raise LaunchRefused("bounded command observation is unreadable") from error


def _descendants(command: Command, root_pid: int) -> set[int]:
    rows = _text(command, ("ps", "-eo", "pid=,ppid=")).splitlines()
    children: dict[int, set[int]] = {}
    for row in rows:
        pair = row.split()
        if len(pair) == 2 and all(value.isdigit() for value in pair):
            children.setdefault(int(pair[1]), set()).add(int(pair[0]))
    seen = {root_pid}
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        for child in children.get(parent, set()):
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return seen


def _metric_counters(raw: bytes) -> tuple[int, int, int, int]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise LaunchRefused("metrics are not UTF-8") from error
    running: list[Decimal] = []
    successes: list[Decimal] = []
    prefix_hits: list[Decimal] = []
    prefix_queries: list[Decimal] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        metric = parts[0].split("{", 1)[0]
        if metric not in {
            "vllm:num_requests_running", "vllm:request_success_total",
            "vllm:prefix_cache_hits", "vllm:prefix_cache_hits_total",
            "vllm:prefix_cache_queries", "vllm:prefix_cache_queries_total",
            "vllm_prefix_cache_hits", "vllm_prefix_cache_hits_total",
            "vllm_prefix_cache_queries", "vllm_prefix_cache_queries_total",
        }:
            continue
        try:
            value = Decimal(parts[1])
        except InvalidOperation as error:
            raise LaunchRefused("required metric value is invalid") from error
        if metric == "vllm:num_requests_running": running.append(value)
        elif metric == "vllm:request_success_total": successes.append(value)
        elif "prefix_cache_hits" in metric: prefix_hits.append(value)
        else: prefix_queries.append(value)
    if not running or not successes or any(value != 0 for value in running):
        raise LaunchRefused("required running/success metrics are absent or active")
    success_total = sum(successes, Decimal(0))
    if success_total != success_total.to_integral_value() or success_total < 0:
        raise LaunchRefused("request-success counter is not a nonnegative integer")
    if (
        not prefix_hits
        or not prefix_queries
        or any(value != 0 for value in prefix_hits + prefix_queries)
    ):
        raise LaunchRefused("prefix-cache metrics are absent or nonzero")
    return 0, int(success_total), 0, 0


class LiveQ1Lease:
    """Exclusive launch-to-teardown lease that emits typed per-call evidence."""

    def __init__(
        self,
        spec: LiveQ1Spec,
        command: Command | None = None,
        http_get: HttpGet | None = None,
    ) -> None:
        self.spec = spec
        self.command = command or SubprocessCommandReader()
        self.http_get = http_get or _get
        self._lock_descriptor: int | None = None
        self._started = False
        self._freeze: dict[str, Any] = {}
        self._server_arguments: tuple[str, ...] = ()
        self._required_environment: tuple[str, ...] = ()
        self.startup_attestation_raw: bytes | None = None

    def _cmd(self, argv: tuple[str, ...]) -> str:
        return _text(self.command, argv)

    def _validate_spec(self) -> None:
        spec = self.spec
        if (
            not isinstance(spec, LiveQ1Spec)
            or _GIT.fullmatch(spec.expected_commit) is None
            or _GIT.fullmatch(spec.expected_tree) is None
            or _SHA.fullmatch(spec.publication_ci_receipt_sha256) is None
            or _SHA.fullmatch(spec.plan_sha256) is None
            or _NAME.fullmatch(spec.container_name) is None
        ):
            raise LaunchRefused("live Q1 launch spec identity drifted")
        for label, path in (
            ("repository", spec.repo_root),
            ("publication CI receipt", spec.publication_ci_receipt),
            ("freeze root", spec.freeze_root),
            ("lock", spec.lock_path),
            ("model snapshot", spec.model_snapshot),
            ("HF cache", spec.hf_cache),
            ("compile cache", spec.compile_cache),
        ):
            _safe_path(path, label)

    def _before_launch(self) -> None:
        spec = self.spec
        if self._cmd(("git", "-C", str(spec.repo_root), "rev-parse", "HEAD")) != spec.expected_commit:
            raise LaunchRefused("publication Git commit mismatch")
        if self._cmd(("git", "-C", str(spec.repo_root), "show", "-s", "--format=%T", "HEAD")) != spec.expected_tree:
            raise LaunchRefused("publication Git tree mismatch")
        if self._cmd(("git", "-C", str(spec.repo_root), "status", "--porcelain=v1", "--untracked-files=all")):
            raise LaunchRefused("publication worktree is not clean")
        ci_raw = spec.publication_ci_receipt.read_bytes()
        if sha256(ci_raw).hexdigest() != spec.publication_ci_receipt_sha256:
            raise LaunchRefused("publication CI receipt hash mismatch")
        _validate_ci_receipt(ci_raw, spec.expected_commit, spec.expected_tree)
        self._freeze = _read_freeze(spec)
        self._validate_source_publication_lineage()
        self._validate_checked_in_freeze()
        runtime = self._freeze["runtime"]
        if self._cmd(("docker", "ps", "-q")):
            raise LaunchRefused("preexisting running container detected")
        if self._cmd(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits")):
            raise LaunchRefused("preexisting GPU compute process detected")
        port = self._port
        if self._unexpected_inference_listener(self._cmd(("ss", "-ltnpH")), port):
            raise LaunchRefused("non-allowlisted inference listener is present")
        static = self._cmd(("nvidia-smi", "--query-gpu=uuid,name,driver_version,compute_cap", "--format=csv,noheader,nounits"))
        expected_static = ", ".join(
            (
                runtime["gpu_uuid"],
                runtime["gpu_name"],
                runtime["gpu_driver_version"],
                runtime["gpu_compute_capability"],
            )
        )
        if static != expected_static:
            raise LaunchRefused("GPU static identity drifted")
        image = self._cmd(("docker", "image", "inspect", "--format", "{{.Id}}|{{index .RepoDigests 0}}", runtime["container_image"]))
        if image != runtime["image_id"] + "|" + runtime["container_image"]:
            raise LaunchRefused("container image ID/repository digest drifted")
        for path in (spec.model_snapshot, spec.hf_cache, spec.compile_cache):
            self._cmd(("test", "-d", str(path)))
        for path in (spec.hf_cache, spec.compile_cache):
            self._cmd(("test", "-w", str(path)))
            if self._cmd(("find", str(path), "-mindepth", "1", "-print", "-quit")):
                raise LaunchRefused("runtime cache is not fresh")
        if spec.model_snapshot.name != runtime["model_revision"] or len(spec.model_snapshot.parents) < 3:
            raise LaunchRefused("model snapshot path does not bind revision")
        rebuilt = build_model_snapshot_manifest(
            spec.model_snapshot.parents[2],
            repository=self._freeze["model"]["repository"],
            revision=runtime["model_revision"],
        )
        if canonical_bytes(rebuilt) != self._freeze["snapshot_manifest_raw"]:
            raise LaunchRefused("local model snapshot bytes drifted from preregistration")

    def _validate_source_publication_lineage(self) -> None:
        plan = self._freeze["plan"]
        source_commit = plan["source"]["commit"]
        verifier_commit = plan["verifier"]["source"]["commit"]
        for commit in {source_commit, verifier_commit}:
            self._cmd(
                (
                    "git",
                    "-C",
                    str(self.spec.repo_root),
                    "merge-base",
                    "--is-ancestor",
                    commit,
                    self.spec.expected_commit,
                )
            )
        source_paths = (
            "_research/dgx_q1/github_ci_receipt.py",
            "_research/dgx_q1/independent_live_verifier.py",
            "_research/dgx_q1/live_experiment.py",
            "_research/dgx_q1/live_launcher.py",
            "_research/dgx_q1/live_preregistration.py",
            "_research/dgx_q1/live_protocol.py",
            "_research/dgx_q1/live_runner.py",
            "_research/dgx_q1/model_snapshot_manifest.py",
        )
        self._cmd(
            (
                "git",
                "-C",
                str(self.spec.repo_root),
                "diff",
                "--quiet",
                source_commit,
                self.spec.expected_commit,
                "--",
                *source_paths,
            )
        )
        self._cmd(
            (
                "git",
                "-C",
                str(self.spec.repo_root),
                "diff",
                "--quiet",
                verifier_commit,
                self.spec.expected_commit,
                "--",
                "_research/dgx_q1/independent_live_verifier.py",
            )
        )

    def _validate_checked_in_freeze(self) -> None:
        """Bind every freeze byte to a regular blob in the publication tree."""

        repo = self.spec.repo_root
        freeze = self.spec.freeze_root
        try:
            relative_root = freeze.relative_to(repo)
            repo_real = repo.resolve(strict=True)
            freeze_real = freeze.resolve(strict=True)
            relative_real = freeze_real.relative_to(repo_real)
        except (OSError, ValueError) as error:
            raise LaunchRefused(
                "freeze must be a real descendant of the publication repository"
            ) from error
        if (
            relative_root != relative_real
            or len(relative_root.parts) < 4
            or relative_root.parts[:3] != ("_research", "dgx_q1", "preregistrations")
        ):
            raise LaunchRefused("freeze is outside the typed preregistration directory")

        freeze_files = self._freeze.get("freeze_files")
        if type(freeze_files) is not dict or not freeze_files:
            raise LaunchRefused("validated freeze file set is unavailable")
        expected: dict[str, bytes] = {}
        for name, raw in freeze_files.items():
            if type(name) is not str or type(raw) is not bytes:
                raise LaunchRefused("freeze file binding drifted")
            path = freeze / name
            try:
                metadata = path.lstat()
            except OSError as error:
                raise LaunchRefused("freeze file disappeared") from error
            if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
                raise LaunchRefused("freeze contains a non-regular file")
            expected[(relative_root / name).as_posix()] = raw

        raw_tree = self.command(
            (
                "git",
                "-C",
                str(repo),
                "ls-tree",
                "-r",
                "-z",
                "--full-tree",
                "HEAD",
                "--",
                relative_root.as_posix(),
            )
        )
        entries: dict[str, tuple[str, str, str]] = {}
        for record in raw_tree.split(b"\0"):
            if not record:
                continue
            try:
                metadata_raw, path_raw = record.split(b"\t", 1)
                mode, kind, object_id = metadata_raw.decode("ascii").split()
                path = path_raw.decode("utf-8", errors="strict")
            except (UnicodeDecodeError, ValueError) as error:
                raise LaunchRefused("publication tree entry is unreadable") from error
            if path in entries:
                raise LaunchRefused("publication tree contains duplicate freeze path")
            entries[path] = (mode, kind, object_id)
        if set(entries) != set(expected):
            raise LaunchRefused("publication tree and freeze file closure differ")
        for path, raw in expected.items():
            mode, kind, object_id = entries[path]
            if (
                mode != "100644"
                or kind != "blob"
                or re.fullmatch(r"[0-9a-f]{40}", object_id) is None
                or object_id != _git_blob_sha1(raw)
            ):
                raise LaunchRefused("freeze bytes are not exact publication-tree blobs")

    @property
    def _port(self) -> int:
        endpoint = self._freeze["runtime"]["endpoint"]
        match = re.fullmatch(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})/v1/chat/completions", endpoint)
        if match is None or not 1 <= int(match.group(1)) <= 65_535:
            raise LaunchRefused("runtime endpoint port drifted")
        return int(match.group(1))

    # Host-owned system listeners observed on the fixed DGX are intentionally
    # enumerated.  Any new or unclassified listener (notably Ollama :11434)
    # fails closed; this is not a blanket exemption for arbitrary services.
    _ALLOWED_NON_INFERENCE_LISTENERS = frozenset({
        "0.0.0.0:22", "[::]:22", "0.0.0.0:111", "[::]:111",
        "127.0.0.53%lo:53", "127.0.0.1:631", "[::1]:631",
        "0.0.0.0:43707", "0.0.0.0:50617", "127.0.0.1:11000", "127.0.0.54:53",
        "192.168.0.23:18000", "192.168.0.23:19000", "127.0.0.1:38115",
        "100.64.0.3:34152", "[::]:44489", "[::]:46737", "[fd7a:115c:a1e0::3]:34984",
    })

    @classmethod
    def _unexpected_inference_listener(cls, raw: str, port: int) -> bool:
        return any(
            len(parts := line.split()) >= 5
            and parts[0] == "LISTEN"
            and (parts[3] == f"127.0.0.1:{port}" or parts[3] not in cls._ALLOWED_NON_INFERENCE_LISTENERS)
            for line in raw.splitlines()
        )

    @staticmethod
    def _listener_present(raw: str, port: int) -> bool:
        return any(len(parts := line.split()) >= 5 and parts[0] == "LISTEN" and parts[3] == f"127.0.0.1:{port}" for line in raw.splitlines())

    @classmethod
    def _listener_inventory(cls, raw: str, port: int) -> tuple[bool, str, int]:
        endpoints = []
        unexpected = 0
        target = False
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0] != "LISTEN":
                continue
            endpoint = parts[3]
            endpoints.append(endpoint)
            if endpoint == f"127.0.0.1:{port}": target = True
            elif endpoint not in cls._ALLOWED_NON_INFERENCE_LISTENERS: unexpected += 1
        return target, sha256("\n".join(sorted(endpoints)).encode()).hexdigest(), unexpected

    def _launch(self) -> None:
        runtime = self._freeze["runtime"]
        milli = runtime["gpu_memory_utilization_milli"]
        utilization = f"{milli // 1000}.{milli % 1000:03d}"
        self._server_arguments = (
            "--model",
            f"/model-repository/snapshots/{runtime['model_revision']}",
            "--served-model-name",
            runtime["served_model"],
            "--host",
            "0.0.0.0",
            "--port",
            str(runtime["container_internal_port"]),
            "--max-num-seqs",
            "1",
            "--no-enable-prefix-caching",
            "--max-model-len",
            str(runtime["max_model_len"]),
            "--gpu-memory-utilization",
            utilization,
            "--generation-config",
            "vllm",
            "--seed",
            "0",
            "--enforce-eager",
            "--language-model-only",
        )
        self._required_environment = (
            "HF_HOME=/cache/huggingface",
            "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub",
            "VLLM_CACHE_ROOT=/cache/compile/vllm",
            "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor",
            "TRITON_CACHE_DIR=/cache/compile/triton",
            "HF_HUB_OFFLINE=1",
            "TRANSFORMERS_OFFLINE=1",
            "VLLM_BATCH_INVARIANT=1",
            "VLLM_ENABLE_V1_MULTIPROCESSING=0",
            "PYTHONHASHSEED=0",
            "CUBLAS_WORKSPACE_CONFIG=:4096:8",
        )
        argv: list[str] = [
            "docker",
            "run",
            "-d",
            "--name",
            self.spec.container_name,
            "--restart",
            "no",
            "--network", "bridge",
            "--ipc",
            "private",
            "-p", f"127.0.0.1:{self._port}:8000",
            "--gpus",
            f"device={runtime['gpu_uuid']}",
            "--mount",
            f"type=bind,src={self.spec.model_snapshot.parents[1]},dst=/model-repository,readonly",
            "--mount",
            f"type=bind,src={self.spec.hf_cache},dst=/cache/huggingface",
            "--mount",
            f"type=bind,src={self.spec.compile_cache},dst=/cache/compile",
        ]
        for value in self._required_environment:
            argv.extend(("-e", value))
        argv.append(runtime["container_image"])
        argv.extend(self._server_arguments)
        self._cmd(tuple(argv))
        self._started = True

    def _inspect(self) -> tuple[dict[str, Any], set[int], str, bytes]:
        runtime = self._freeze["runtime"]
        try:
            document = strict_json(self.command(("docker", "inspect", self.spec.container_name)))
        except Exception as error:
            raise LaunchRefused("container inspect is invalid") from error
        if type(document) is not list or len(document) != 1 or type(document[0]) is not dict:
            raise LaunchRefused("container inspect cardinality drifted")
        item = document[0]
        config = item.get("Config")
        host = item.get("HostConfig")
        state = item.get("State")
        mounts = item.get("Mounts")
        if (
            item.get("Image") != runtime["image_id"]
            or type(config) is not dict
            or config.get("Image") != runtime["container_image"]
            or config.get("Cmd") != list(self._server_arguments)
            or type(config.get("Env")) is not list
            or not set(self._required_environment).issubset(set(config["Env"]))
            or type(host) is not dict
            or host.get("NetworkMode") != "bridge"
            or host.get("IpcMode") != runtime["container_ipc_mode"]
            or host.get("RestartPolicy", {}).get("Name") != "no"
            or type(state) is not dict
            or state.get("Running") is not True
            or type(state.get("Pid")) is not int
            or state["Pid"] <= 0
            or type(state.get("StartedAt")) is not str
            or not state["StartedAt"]
            or type(mounts) is not list
            or item.get("NetworkSettings", {}).get("Ports") != {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(self._port)}]}
        ):
            raise LaunchRefused("actual container configuration drifted")
        device_requests = host.get("DeviceRequests")
        if (
            type(device_requests) is not list
            or not any(
                type(request) is dict
                and request.get("DeviceIDs") == [runtime["gpu_uuid"]]
                for request in device_requests
            )
        ):
            raise LaunchRefused("actual container GPU allocation drifted")
        expected_mounts = {
            "/model-repository": (str(self.spec.model_snapshot.parents[1]), False),
            "/cache/huggingface": (str(self.spec.hf_cache), True),
            "/cache/compile": (str(self.spec.compile_cache), True),
        }
        observed_mounts = {
            mount.get("Destination"): (mount.get("Source"), mount.get("RW"))
            for mount in mounts
            if type(mount) is dict and mount.get("Destination") in expected_mounts
        }
        if observed_mounts != expected_mounts:
            raise LaunchRefused("actual container mounts drifted")
        pid = state["Pid"]
        descendants = _descendants(self.command, pid)
        cgroup = self.command(("cat", f"/proc/{pid}/cgroup"))
        argv = self.command(("cat", f"/proc/{pid}/cmdline"))
        return item, descendants, cgroup.decode("utf-8", errors="strict"), argv

    def _attest(self, phase: str, attempt_id: str | None, completed: int) -> bytes:
        runtime = self._freeze["runtime"]
        item, descendants, cgroup, argv = self._inspect()
        version = strict_json(self.http_get(f"http://127.0.0.1:{self._port}/version"))
        models = strict_json(self.http_get(f"http://127.0.0.1:{self._port}/v1/models"))
        if version != {"version": runtime["vllm_version"]}:
            raise LaunchRefused("live vLLM version endpoint drifted")
        if (
            type(models) is not dict
            or type(models.get("data")) is not list
            or [row.get("id") for row in models["data"] if type(row) is dict]
            != [runtime["served_model"]]
        ):
            raise LaunchRefused("live served-model endpoint drifted")
        metrics_raw = self.http_get(f"http://127.0.0.1:{self._port}/metrics")
        requests_running, request_success_total, prefix_cache_hits, prefix_cache_queries = _metric_counters(metrics_raw)
        host_listener, listener_inventory_sha256, unexpected_listener_count = self._listener_inventory(self._cmd(("ss", "-ltnpH")), self._port)
        init_pid = item["State"]["Pid"]
        internal = self._cmd(
            ("docker", "exec", self.spec.container_name, "cat", "/proc/net/tcp")
        ) + "\n" + self._cmd(
            ("docker", "exec", self.spec.container_name, "cat", "/proc/net/tcp6")
        )
        netns = self._cmd(
            ("docker", "exec", self.spec.container_name, "readlink", "/proc/1/ns/net")
        )
        if re.fullmatch(r"net:\[[1-9][0-9]*\]", netns) is None:
            raise LaunchRefused("container network namespace identity unavailable")
        internal_port_hex = f":{runtime['container_internal_port']:04X}"
        if not host_listener or unexpected_listener_count != 0 or not any(
            row.split()[1].endswith(internal_port_hex) and row.split()[3] == "0A"
            for row in internal.splitlines()
            if len(row.split()) >= 4
        ):
            raise LaunchRefused("loopback publication/internal container listener absent")
        compute_raw = self._cmd(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"))
        compute_pids: set[int] = set()
        for line in compute_raw.splitlines():
            pair = [part.strip() for part in line.split(",")]
            if len(pair) != 2 or pair[0] != runtime["gpu_uuid"] or not pair[1].isdigit():
                raise LaunchRefused("foreign or malformed GPU compute process detected")
            compute_pids.add(int(pair[1]))
        if not compute_pids or not compute_pids.issubset(descendants):
            raise LaunchRefused("GPU process does not join target process tree")
        for pid in compute_pids:
            if self.command(("cat", f"/proc/{pid}/cgroup")).decode("utf-8", errors="strict") != cgroup:
                raise LaunchRefused("GPU process cgroup drifted")
        state = item["State"]
        receipt = canonical_bytes(
            {
                "schema_version": BOUNDARY_SCHEMA,
                "namespace": NAMESPACE,
                "q1_sha256": sha256(self._freeze["plan_raw"]).hexdigest(),
                "phase": phase,
                "attempt_id": attempt_id,
                "completed_attempts": completed,
                "endpoint_sha256": self._freeze["plan"]["identities"]["endpoint_sha256"],
                "model_identity_sha256": self._freeze["plan"]["identities"]["model_identity_sha256"],
                "runtime_identity_sha256": self._freeze["plan"]["identities"]["runtime_identity_sha256"],
                "model_snapshot_manifest_sha256": self._freeze["plan"]["identities"]["model_snapshot_manifest_sha256"],
                "container_id_sha256": sha256(item["Id"].encode("utf-8")).hexdigest(),
                "image_id": item["Image"],
                "configured_image": item["Config"]["Image"],
                "container_start_sha256": sha256(state["StartedAt"].encode("utf-8")).hexdigest(),
                "cgroup_sha256": sha256(cgroup.encode("utf-8")).hexdigest(),
                "argv_sha256": sha256(argv).hexdigest(),
                "gpu_uuid": runtime["gpu_uuid"],
                "gpu_compute_pids": sorted(compute_pids),
                "host_listener_present": True,
                "container_init_pid": state["Pid"],
                "container_network_namespace_sha256": sha256(
                    netns.encode("utf-8")
                ).hexdigest(),
                "container_tcp_tables_sha256": sha256(
                    internal.encode("utf-8")
                ).hexdigest(),
                "internal_listener_port": runtime["container_internal_port"],
                "host_listener_inventory_sha256": listener_inventory_sha256,
                "unexpected_listener_count": unexpected_listener_count,
                "requests_running": requests_running,
                "request_success_total": request_success_total,
                "prefix_cache_hits": prefix_cache_hits,
                "prefix_cache_queries": prefix_cache_queries,
                "raw_metrics_sha256": sha256(metrics_raw).hexdigest(),
                "boundary": "FINITE_OBSERVED_CONTROLS_NOT_NO_INTERFERENCE_PROOF",
                "nonclaim": "NOT_DISPATCH_AUTHORIZATION_OR_SOURCE_A_PERMIT_OR_NO_INTERFERENCE_PROOF",
            }
        )
        try:
            validate_boundary_attestation(
                receipt,
                self._freeze["plan_raw"],
                phase=phase,
                attempt_id=attempt_id,
                completed_attempts=completed,
            )
        except Exception as error:
            raise LaunchRefused("boundary request counters or context drifted") from error
        return receipt

    def __enter__(self) -> "LiveQ1Lease":
        self._validate_spec()
        self._lock_descriptor = os.open(self.spec.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._before_launch()
            self._launch()
            deadline = time.monotonic() + 900
            while True:
                try:
                    self.startup_attestation_raw = self._attest("STARTUP", None, 0)
                    return self
                except LoopbackUnavailable:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(2)
        except Exception:
            self.close()
            raise

    def attest(self, phase: str, attempt_id: str | None, completed: int) -> bytes:
        if not self._started or self.startup_attestation_raw is None:
            raise LaunchRefused("live Q1 lease is not active")
        return self._attest(phase, attempt_id, completed)

    @property
    def is_active(self) -> bool:
        return self._started and self.startup_attestation_raw is not None

    @property
    def validated_freeze_files(self) -> dict[str, bytes]:
        """Return the exact Git-verified freeze bytes held by this live lease."""

        if not self.is_active:
            raise LaunchRefused("validated freeze is unavailable outside an active lease")
        files = self._freeze.get("freeze_files")
        if (
            type(files) is not dict
            or not files
            or any(type(name) is not str or type(raw) is not bytes for name, raw in files.items())
        ):
            raise LaunchRefused("validated freeze byte set drifted")
        return dict(files)

    def close(self) -> None:
        if self._started:
            try:
                self.command(("docker", "rm", "-f", self.spec.container_name))
                deadline = time.monotonic() + 60
                while True:
                    compute = self._cmd(("nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"))
                    listeners = self._listener_present(self._cmd(("ss", "-ltnpH")), self._port)
                    if not compute and not listeners:
                        break
                    if time.monotonic() >= deadline:
                        raise LaunchRefused("target teardown observations did not quiesce")
                    time.sleep(1)
            except Exception as error:
                raise LaunchRefused("target cleanup failed; exclusive lease retained") from error
            self._started = False
        if self._lock_descriptor is not None:
            fcntl.flock(self._lock_descriptor, fcntl.LOCK_UN)
            os.close(self._lock_descriptor)
            self._lock_descriptor = None

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = ["LaunchRefused", "LiveQ1Lease", "LiveQ1Spec"]
