"""Local bwrap launcher and strict client validators for ALFWorld text G0.

This is a containment instrument, not an independent evaluator, canonical
owner, or a G1 result. The actor sees only stdout; terminal outcome is the
single canonical line on stderr. Extra file descriptors are deliberately
avoided because bwrap 0.11 does not support ``--preserve-fds``.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import time
from typing import Any, Mapping

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from .alfworld_text_worker import (
    ACTOR_SCHEMA, LOCAL_BOUNDARY_CLAIM, MAX_ACTION_BYTES, MAX_STEPS,
    OUTCOME_SCHEMA, WORKER_SCHEMA,
)

SANDBOX_GAME_PATH = "/run/hswm/game.tw-pddl"
MAX_PROTOCOL_LINE_BYTES = 131_072


class AlfworldTextRuntimeError(RuntimeError):
    """The local-only sandbox or its strict protocol was invalid."""


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise AlfworldTextRuntimeError(f"{field} must be a lowercase SHA-256")
    return value


def _regular(path: Path, field: str, *, allow_symlink: bool = False) -> Path:
    if not path.is_absolute() or not path.is_file() or (path.is_symlink() and not allow_symlink):
        raise AlfworldTextRuntimeError(f"{field} must be an absolute regular file")
    return path


def _directory(path: Path, field: str) -> Path:
    if not path.is_absolute() or not path.is_dir() or path.is_symlink():
        raise AlfworldTextRuntimeError(f"{field} must be an absolute non-symlink directory")
    return path


def _read_json_object(path: Path, field: str) -> tuple[bytes, Mapping[str, object]]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlfworldTextRuntimeError(f"{field} is unreadable JSON") from error
    if not isinstance(value, dict):
        raise AlfworldTextRuntimeError(f"{field} must be a JSON object")
    return raw, value


@dataclass(frozen=True, slots=True)
class LocalGameBinding:
    """One local, non-repository game record selected by the pool controller."""

    opaque_uid: str
    relative_path: str
    file_sha256: str
    bytes: int

    def validate(self) -> None:
        if not isinstance(self.opaque_uid, str) or not self.opaque_uid:
            raise AlfworldTextRuntimeError("game binding opaque UID is invalid")
        if (not isinstance(self.relative_path, str) or not self.relative_path
                or self.relative_path.startswith("/") or ".." in Path(self.relative_path).parts):
            raise AlfworldTextRuntimeError("game binding relative path is invalid")
        _sha(self.file_sha256, "game_binding.file_sha256")
        if type(self.bytes) is not int or self.bytes < 1:
            raise AlfworldTextRuntimeError("game binding bytes is invalid")


def load_local_game_binding(*, pool_manifest: Path, local_locator: Path, asset_root: Path,
                            opaque_uid: str) -> tuple[str, str, LocalGameBinding, Path]:
    """Verify public v2 commitment against an external local locator, then select one UID."""
    manifest_raw, manifest = _read_json_object(pool_manifest, "pool manifest")
    locator_raw, locator = _read_json_object(local_locator, "local locator")
    if manifest.get("schema_version") != "hswm-alfworld-text-clean-pool/v2":
        raise AlfworldTextRuntimeError("pool manifest schema drifted")
    if locator.get("schema_version") != "hswm-alfworld-text-clean-pool-local-locator/v1":
        raise AlfworldTextRuntimeError("local locator schema drifted")
    aggregate = manifest.get("aggregate_commitment")
    if not isinstance(aggregate, dict):
        raise AlfworldTextRuntimeError("pool aggregate commitment is absent")
    rendered_digest = sha256(locator_raw).hexdigest()
    canonical_digest = sha256(canonical_bytes(locator)).hexdigest()
    if aggregate.get("local_locator_rendered_json_sha256") != rendered_digest or aggregate.get("local_locator_canonical_json_sha256") != canonical_digest:
        raise AlfworldTextRuntimeError("local locator commitment mismatch")
    if locator.get("pool_commitment") != {
        key: aggregate.get(key)
        for key in (
            "selected_game_counts",
            "selected_game_bytes_by_split",
            "selected_task_group_counts",
            "task_group_overlap_counts",
            "selected_game_total",
        )
    }:
        raise AlfworldTextRuntimeError("local locator pool counts mismatch")
    source = manifest.get("source_binding")
    locator_source = locator.get("source_binding")
    if not isinstance(source, dict) or not isinstance(locator_source, dict):
        raise AlfworldTextRuntimeError("pool source binding is absent")
    if locator_source.get("repository_commit") != source.get("repository_commit") or locator_source.get("assets") != source.get("official_release_assets"):
        raise AlfworldTextRuntimeError("local locator source binding mismatch")
    records = locator.get("records")
    if not isinstance(records, list):
        raise AlfworldTextRuntimeError("local locator records are absent")
    selected = [record for record in records if isinstance(record, dict) and record.get("opaque_uid") == opaque_uid]
    if len(selected) != 1:
        raise AlfworldTextRuntimeError("opaque UID must select exactly one local game")
    record = selected[0]
    expected = {"bytes", "file_sha256", "opaque_uid", "relative_path", "relative_path_sha256", "split", "task_group_uid"}
    if set(record) != expected or not isinstance(record["relative_path"], str) or sha256(record["relative_path"].encode("utf-8")).hexdigest() != record["relative_path_sha256"]:
        raise AlfworldTextRuntimeError("local locator record contract drifted")
    binding = LocalGameBinding(record["opaque_uid"], record["relative_path"], record["file_sha256"], record["bytes"])
    binding.validate()
    _directory(asset_root, "asset_root")
    return sha256(manifest_raw).hexdigest(), rendered_digest, binding, asset_root / binding.relative_path


@dataclass(frozen=True, slots=True)
class LocalSandboxSpec:
    """Pinned local inputs plus pool and locator commitments, for G0 only."""

    bubblewrap: Path
    python: Path
    python_runtime_root: Path
    repository: Path
    upstream: Path
    venv: Path
    asset_root: Path
    game_file: Path
    pool_manifest_sha256: str
    local_locator_sha256: str
    game_binding: LocalGameBinding
    episode_uid: str
    max_steps: int = MAX_STEPS

    def validate(self) -> None:
        _regular(self.bubblewrap, "bubblewrap")
        _regular(self.python, "python", allow_symlink=True)
        runtime_root = _directory(self.python_runtime_root, "python_runtime_root")
        try:
            self.python.resolve(strict=True).relative_to(runtime_root.resolve(strict=True))
        except (OSError, ValueError) as error:
            raise AlfworldTextRuntimeError("python must resolve inside python_runtime_root") from error
        for field in ("repository", "upstream", "venv", "asset_root"):
            _directory(getattr(self, field), field)
        _regular(self.game_file, "game_file")
        _sha(self.pool_manifest_sha256, "pool_manifest_sha256")
        _sha(self.local_locator_sha256, "local_locator_sha256")
        if not isinstance(self.episode_uid, str) or not self.episode_uid:
            raise AlfworldTextRuntimeError("episode UID is invalid")
        if type(self.max_steps) is not int or not 1 <= self.max_steps <= MAX_STEPS:
            raise AlfworldTextRuntimeError(f"max_steps must be an integer from 1 through {MAX_STEPS}")
        binding = self.game_binding
        binding.validate()
        if self.game_file != self.asset_root / binding.relative_path:
            raise AlfworldTextRuntimeError("game file is not the exact pool locator path")
        try:
            root = self.asset_root.resolve(strict=True)
            current = root
            for component in Path(binding.relative_path).parts:
                current = current / component
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise AlfworldTextRuntimeError("game path must not traverse a symlink")
            if self.game_file.resolve(strict=True) != current or not self.game_file.resolve(strict=True).is_relative_to(root):
                raise AlfworldTextRuntimeError("game path escaped asset root")
        except OSError as error:
            raise AlfworldTextRuntimeError("game path ancestor is unavailable") from error
        if sha256(self.game_file.read_bytes()).hexdigest() != binding.file_sha256:
            raise AlfworldTextRuntimeError("game_file SHA-256 mismatch")
        if binding.bytes != self.game_file.stat().st_size:
            raise AlfworldTextRuntimeError("game locator bytes mismatch")


def _dynamic_library_roots() -> list[str]:
    return [path for path in ("/lib", "/lib64", "/usr/lib", "/usr/lib64") if Path(path).is_dir()]


def open_verified_game(spec: LocalSandboxSpec) -> int:
    """Open one non-followed game and pin its actual inode bytes before bwrap."""
    spec.validate()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(spec.game_file, flags)
    except OSError as error:
        raise AlfworldTextRuntimeError("game file could not be opened without following links") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size != spec.game_binding.bytes:
            raise AlfworldTextRuntimeError("opened game file type or bytes drifted")
        digest = sha256()
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            digest.update(block)
        if digest.hexdigest() != spec.game_binding.file_sha256:
            raise AlfworldTextRuntimeError("opened game file SHA-256 mismatch")
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except Exception:
        os.close(fd)
        raise


def build_bwrap_command(spec: LocalSandboxSpec, *, game_fd: int) -> list[str]:
    """Construct a bwrap-0.11 compatible no-network one-game command."""
    spec.validate()
    if type(game_fd) is not int or game_fd < 3:
        raise AlfworldTextRuntimeError("game FD must be a private non-stdio descriptor")
    command = [
        str(spec.bubblewrap), "--die-with-parent", "--new-session", "--unshare-all", "--unshare-net",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--dir", "/tmp/home", "--dir", "/tmp/xdg-cache", "--dir", "/tmp/alfworld-data",
        "--dir", "/run", "--dir", "/run/hswm",
        "--ro-bind", str(spec.repository), str(spec.repository),
        "--ro-bind", str(spec.upstream), str(spec.upstream),
        "--ro-bind", str(spec.venv), str(spec.venv),
        "--ro-bind", str(spec.python_runtime_root), str(spec.python_runtime_root),
    ]
    for root in _dynamic_library_roots():
        command.extend(["--ro-bind", root, root])
    command.extend([
        "--ro-bind-fd", str(game_fd), SANDBOX_GAME_PATH,
        "--clearenv", "--setenv", "PYTHONNOUSERSITE", "1",
        "--setenv", "HOME", "/tmp/home",
        "--setenv", "XDG_CACHE_HOME", "/tmp/xdg-cache",
        "--setenv", "ALFWORLD_DATA", "/tmp/alfworld-data",
        "--setenv", "TERM", "dumb",
        "--setenv", "PYTHONPATH", f"{spec.repository}:{spec.repository / 'src'}",
        "--chdir", str(spec.repository), "--",
        str(spec.python), "-m", "hswm.experiments.alfworld_text_worker",
        "--game-file", SANDBOX_GAME_PATH, "--source-game-sha256", spec.game_binding.file_sha256,
        "--episode-uid", spec.episode_uid, "--max-steps", str(spec.max_steps), "--outcome-fd", "2",
    ])
    return command


def _one_line(raw: bytes, *, label: str, bound: int = MAX_PROTOCOL_LINE_BYTES) -> bytes:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1 or len(raw) > bound:
        raise AlfworldTextRuntimeError(f"{label} must be exactly one bounded newline-delimited JSON line")
    return raw[:-1]


def validate_actor_projection(raw: bytes, *, episode_uid: str, previous_step: int | None = None) -> Mapping[str, Any]:
    try:
        value = parse_canonical(_one_line(raw, label="actor response"))
    except ValueError as error:
        raise AlfworldTextRuntimeError("actor response is not canonical JSON") from error
    expected = {"schema_version", "episode_uid", "observation", "step_index", "done"}
    if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != ACTOR_SCHEMA:
        raise AlfworldTextRuntimeError("actor projection field set drifted")
    if value["episode_uid"] != episode_uid or not isinstance(value["observation"], str) or type(value["step_index"]) is not int or value["step_index"] < 0 or type(value["done"]) is not bool:
        raise AlfworldTextRuntimeError("actor projection values drifted")
    if previous_step is not None and value["step_index"] != previous_step + 1:
        raise AlfworldTextRuntimeError("actor step index drifted")
    return value


def validate_outcome_receipt(raw: bytes, *, episode_uid: str, source_game_sha256: str, actor_steps: int) -> Mapping[str, Any]:
    try:
        value = parse_canonical(_one_line(raw, label="outcome response"))
    except ValueError as error:
        raise AlfworldTextRuntimeError("outcome response is not canonical JSON") from error
    expected = {"schema_version", "boundary_claim", "episode_uid", "action_digests_sha256", "observation_digests_sha256", "steps", "done", "won", "success", "score", "source_game_sha256", "receipt_sha256"}
    if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != OUTCOME_SCHEMA:
        raise AlfworldTextRuntimeError("outcome receipt field set drifted")
    if value["boundary_claim"] != LOCAL_BOUNDARY_CLAIM or value["episode_uid"] != episode_uid or value["source_game_sha256"] != source_game_sha256:
        raise AlfworldTextRuntimeError("outcome receipt identity drifted")
    for field in ("action_digests_sha256", "observation_digests_sha256", "source_game_sha256", "receipt_sha256"):
        _sha(value[field], field)
    if type(value["steps"]) is not int or value["steps"] != actor_steps or not all(type(value[key]) is bool for key in ("done", "won", "success")) or type(value["score"]) is not int:
        raise AlfworldTextRuntimeError("outcome receipt values drifted")
    if value["success"] != bool(value["done"] and value["won"]):
        raise AlfworldTextRuntimeError("outcome success predicate drifted")
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if value["receipt_sha256"] != sha256(canonical_bytes(unsigned)).hexdigest():
        raise AlfworldTextRuntimeError("outcome receipt digest drifted")
    return value


def action_line(*, episode_uid: str, action: str) -> bytes:
    if not isinstance(episode_uid, str) or not episode_uid or not isinstance(action, str) or not action or "\n" in action or "\r" in action:
        raise AlfworldTextRuntimeError("action request values are invalid")
    line = canonical_bytes({"schema_version": WORKER_SCHEMA, "kind": "ACTION", "episode_uid": episode_uid, "action": action}) + b"\n"
    if len(line) > MAX_ACTION_BYTES:
        raise AlfworldTextRuntimeError("action request exceeds byte bound")
    return line


def read_one_line(stream: Any, *, timeout_seconds: float, label: str) -> bytes:
    """Bound and surface parent-side timeout without accepting partial frames."""
    if timeout_seconds <= 0:
        raise AlfworldTextRuntimeError("timeout_seconds must be positive")
    fd = stream.fileno()
    deadline = time.monotonic() + timeout_seconds
    chunks: list[bytes] = []
    size = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AlfworldTextRuntimeError(f"{label} timed out")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise AlfworldTextRuntimeError(f"{label} timed out")
        part = os.read(fd, min(4096, MAX_PROTOCOL_LINE_BYTES + 1 - size))
        if not part:
            raise AlfworldTextRuntimeError(f"{label} closed before a complete line")
        chunks.append(part)
        size += len(part)
        raw = b"".join(chunks)
        if size > MAX_PROTOCOL_LINE_BYTES:
            raise AlfworldTextRuntimeError(f"{label} exceeds byte bound")
        if b"\n" in raw:
            _one_line(raw, label=label)
            return raw


class LocalAlfworldTextRuntime:
    """Thin G0 client; its local boundary is explicitly not an independent evaluator."""

    claim_ceiling = LOCAL_BOUNDARY_CLAIM

    def __init__(self, spec: LocalSandboxSpec) -> None:
        self.spec = spec

    def command(self, *, game_fd: int) -> list[str]:
        return build_bwrap_command(self.spec, game_fd=game_fd)

    def launch(self) -> subprocess.Popen[bytes]:
        """Launch with stdout=actor protocol and stderr=private outcome only."""
        game_fd = open_verified_game(self.spec)
        try:
            return subprocess.Popen(self.command(game_fd=game_fd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, pass_fds=(game_fd,), close_fds=True)
        finally:
            os.close(game_fd)
