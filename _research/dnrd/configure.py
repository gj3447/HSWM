"""Offline, deterministic post-B execution-config construction for DNRD-4S1.

This is intentionally an operational boundary, not an execution boundary.  It
does not contact a model, network, beacon, or seed source, and it never invokes
the runner.  Given a detached clean preregistration-B checkout and retained
receipts, it creates only fresh owner-only mutable roots and one canonical
runtime configuration outside that checkout.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Sequence

from . import execute


class ConfigurationRefusal(ValueError):
    """The retained post-B evidence cannot produce a safe DNRD-4S1 config."""


@dataclass(frozen=True, slots=True)
class ConfigurationInputs:
    repo_root: Path
    preregistration_path: str
    source_manifest_path: str
    source_ci_receipt_path: Path
    preregistration_ci_receipt_path: Path
    qualification_path: Path
    runtime_manifest_path: Path
    bridge_state_root: Path
    attempt_registry_root: Path
    output_root: Path
    config_output_path: Path
    node_executable_path: Path
    python_executable_path: Path


def _sha(path: Path, label: str) -> str:
    _plain_file(path, label)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plain_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ConfigurationRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ConfigurationRefusal(f"{label} must be a plain regular file")


def _plain_directory(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise ConfigurationRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ConfigurationRefusal(f"{label} must be a plain directory")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if completed.returncode:
        raise ConfigurationRefusal(f"git {' '.join(args)} failed")
    try:
        return completed.stdout.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as error:
        raise ConfigurationRefusal("Git returned a non-ASCII identity") from error


def _sha1(value: str, label: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ConfigurationRefusal(f"{label} must be a lowercase Git SHA-1")
    return value


def _relative(value: str, label: str) -> str:
    if not value or value.startswith("/"):
        raise ConfigurationRefusal(f"{label} must be a nonempty relative path")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ConfigurationRefusal(f"{label} escapes its root")
    return path.as_posix()


def _clean_detached_b(
    inputs: ConfigurationInputs,
) -> tuple[str, str, str, str, int, int]:
    root = inputs.repo_root.resolve()
    _plain_directory(root, "preregistration-B checkout")
    if _git(root, "status", "--porcelain"):
        raise ConfigurationRefusal("preregistration-B checkout must be clean")
    if subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root).returncode == 0:
        raise ConfigurationRefusal("preregistration-B checkout must be detached")
    b_commit = _sha1(_git(root, "rev-parse", "HEAD"), "preregistration-B commit")
    b_tree = _sha1(_git(root, "rev-parse", "HEAD^{tree}"), "preregistration-B tree")
    parents = _git(root, "show", "-s", "--format=%P", "HEAD").split()
    if len(parents) != 1:
        raise ConfigurationRefusal("preregistration-B must have exactly one Source-A parent")
    a_commit = _sha1(parents[0], "Source-A commit")
    a_tree = _sha1(_git(root, "rev-parse", f"{a_commit}^{{tree}}"), "Source-A tree")
    try:
        source_freeze_unix = int(_git(root, "show", "-s", "--format=%ct", a_commit))
        preregistration_commit_unix = int(
            _git(root, "show", "-s", "--format=%ct", b_commit)
        )
    except ValueError as error:
        raise ConfigurationRefusal("Source-A/B commit time is malformed") from error
    if source_freeze_unix <= 0 or preregistration_commit_unix <= 0:
        raise ConfigurationRefusal("Source-A/B commit time is malformed")
    prereg = _relative(inputs.preregistration_path, "preregistration path")
    changed = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", a_commit, b_commit).splitlines()
    if changed != [prereg]:
        raise ConfigurationRefusal("preregistration-B must change exactly its one preregistration path")
    return (
        a_commit,
        a_tree,
        b_commit,
        b_tree,
        source_freeze_unix,
        preregistration_commit_unix,
    )


def _assert_local_origin_main(root: Path, b_commit: str) -> None:
    """Check only local refs/local bare remotes; never opens a network socket."""

    try:
        remote = _git(root, "config", "--get", "remote.origin.url")
    except ConfigurationRefusal:
        remote = ""
    tracking = subprocess.run(
        ["git", "show-ref", "--verify", "--hash", "refs/remotes/origin/main"],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if tracking.returncode == 0:
        observed = tracking.stdout.decode("ascii", errors="strict").strip()
        if observed != b_commit:
            raise ConfigurationRefusal("local refs/remotes/origin/main is not preregistration-B")
        return
    if remote.startswith("file://"):
        remote = remote.removeprefix("file://")
    candidate = Path(remote)
    if candidate.is_dir():
        observed = _git(candidate, "rev-parse", "refs/heads/main")
        if observed != b_commit:
            raise ConfigurationRefusal("local origin main is not preregistration-B")


def _canonical_object(path: Path, label: str) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = execute._strict_json_bytes(raw, label)
    except execute.ExecutionRefusal as error:
        raise ConfigurationRefusal(str(error)) from error
    return value


def _b_ci_completed(path: Path) -> int:
    value = _canonical_object(path, "preregistration B CI receipt")
    result = value.get("completed_at_unix")
    if type(result) is not int or result <= 0:
        raise ConfigurationRefusal("preregistration B CI receipt completion is malformed")
    return result


def _new_owner_directory(path: Path, label: str) -> list[Path]:
    """Create a previously absent path ancestry with owner-only modes only."""

    if not path.is_absolute():
        raise ConfigurationRefusal(f"{label} must be absolute")
    if path.exists() or path.is_symlink():
        raise ConfigurationRefusal(f"{label} must be a new path")
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            raise ConfigurationRefusal(f"{label} has no existing parent")
        cursor = cursor.parent
    _plain_directory(cursor, f"existing parent of {label}")
    created: list[Path] = []
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        directory.chmod(0o700)
        created.append(directory)
    return created


def _remove_new_directories(created: list[Path]) -> None:
    for directory in reversed(created):
        try:
            directory.rmdir()
        except OSError:
            pass


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _json_config(config: execute.ExecutionConfig) -> dict[str, Any]:
    value = asdict(config)
    for key, item in tuple(value.items()):
        if isinstance(item, Path):
            value[key] = str(item)
        elif isinstance(item, tuple):
            value[key] = list(item)
    return value


def _write_new_owner_file(path: Path, raw: bytes) -> str:
    if path.exists() or path.is_symlink():
        raise ConfigurationRefusal("configuration output must be a new path")
    _plain_directory(path.parent, "configuration output parent")
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o400,
        )
        created = True
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise OSError("configuration write made no forward progress")
            offset += written
        os.fchmod(descriptor, 0o400)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        _fsync_directory(path.parent)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise
    return hashlib.sha256(raw).hexdigest()


def configure_execution(inputs: ConfigurationInputs) -> str:
    """Create fresh mutable roots and a static-preflight-valid canonical config."""

    root = inputs.repo_root.resolve()
    expected_registry = inputs.bridge_state_root.resolve().parent / "attempt-registry"
    if inputs.attempt_registry_root.resolve() != expected_registry:
        raise ConfigurationRefusal(
            "attempt registry must be bridge-state parent/attempt-registry"
        )
    (
        a_commit,
        a_tree,
        b_commit,
        b_tree,
        source_freeze_unix,
        preregistration_commit_unix,
    ) = _clean_detached_b(inputs)
    _assert_local_origin_main(root, b_commit)
    prereg_path = _relative(inputs.preregistration_path, "preregistration path")
    source_manifest_path = _relative(inputs.source_manifest_path, "source manifest path")
    prereg_file = root / prereg_path
    source_manifest = root / source_manifest_path
    prereg_sha = _sha(prereg_file, "preregistration")
    source_manifest_sha = _sha(source_manifest, "source manifest")
    b_ci_completed = _b_ci_completed(inputs.preregistration_ci_receipt_path)
    runtime = _canonical_object(inputs.runtime_manifest_path, "runtime manifest")
    try:
        runtime_root = Path(runtime["root_path"])
        entrypoint = _relative(runtime["entrypoint"], "runtime manifest entrypoint")
    except (KeyError, TypeError) as error:
        raise ConfigurationRefusal("runtime manifest lacks root/entrypoint") from error
    if not runtime_root.is_absolute():
        raise ConfigurationRefusal("runtime manifest root must be absolute")
    bridge_implementation = runtime_root / entrypoint
    scorer = root / "_research/dnrd/scorer.py"
    helper = root / "_research/dnrd/verify-beacon.mjs"
    package_lock = root / "tools/swm0w_drand/package-lock.json"
    bundle = root / "tools/swm0w_drand/node_modules/drand-client/build/esm/index.mjs"
    for path, label in ((inputs.node_executable_path, "Node executable"), (inputs.python_executable_path, "Python executable"), (scorer, "scorer"), (helper, "verifier helper"), (package_lock, "verifier package lock"), (bundle, "verifier runtime bundle")):
        if not path.is_absolute():
            raise ConfigurationRefusal(f"{label} must be absolute")
    prereg = _canonical_object(prereg_file, "preregistration")
    try:
        bindings = prereg["runtime_bindings"]
        model_endpoint = bindings["model_endpoint"]
    except (KeyError, TypeError) as error:
        raise ConfigurationRefusal("preregistration lacks runtime bindings") from error
    if type(model_endpoint) is not str:
        raise ConfigurationRefusal("preregistration model endpoint is malformed")
    config = execute.ExecutionConfig(
        repo_root=root,
        source_a_commit=a_commit,
        source_a_tree=a_tree,
        source_manifest_path=source_manifest_path,
        source_manifest_sha256=source_manifest_sha,
        prereg_b_commit=b_commit,
        prereg_b_tree=b_tree,
        prereg_path=prereg_path,
        prereg_sha256=prereg_sha,
        source_freeze_unix=source_freeze_unix,
        preregistration_ci_completed_unix=b_ci_completed,
        output_root=inputs.output_root.resolve(),
        model_endpoint=model_endpoint,
        bridge_implementation_path=bridge_implementation,
        bridge_implementation_sha256=_sha(bridge_implementation, "bridge implementation"),
        bridge_command=(str(inputs.node_executable_path.resolve()), str(bridge_implementation)),
        bridge_config={"root_path": str(inputs.bridge_state_root.resolve()), "frozen_scorer_source_sha256": _sha(scorer, "scorer")},
        scorer_implementation_path=scorer,
        scorer_implementation_sha256=_sha(scorer, "scorer"),
        scorer_command=(str(inputs.python_executable_path.resolve()), *execute.SCORER_ARGUMENT_CONTRACT),
        verifier_command=(str(inputs.node_executable_path.resolve()), str(helper)),
        verifier_helper_path=helper,
        verifier_helper_sha256=_sha(helper, "verifier helper"),
        verifier_package_lock_path=package_lock,
        verifier_package_lock_sha256=_sha(package_lock, "verifier package lock"),
        verifier_runtime_bundle_path=bundle,
        verifier_runtime_bundle_sha256=_sha(bundle, "verifier runtime bundle"),
        attempt_registry_root=inputs.attempt_registry_root.resolve(),
        preregistration_ci_receipt_path=inputs.preregistration_ci_receipt_path.resolve(),
        preregistration_ci_receipt_sha256=_sha(inputs.preregistration_ci_receipt_path, "preregistration B CI receipt"),
        source_ci_receipt_path=inputs.source_ci_receipt_path.resolve(),
        source_ci_receipt_sha256=_sha(inputs.source_ci_receipt_path, "source CI receipt"),
        structured_output_qualification_path=inputs.qualification_path.resolve(),
        structured_output_qualification_sha256=_sha(inputs.qualification_path, "qualification"),
        tokenizer_preflight_prompt=execute.TOKENIZER_PREFLIGHT_PROMPT,
        bridge_runtime_root=runtime_root,
        bridge_state_root=inputs.bridge_state_root.resolve(),
        bridge_runtime_tree_manifest_path=inputs.runtime_manifest_path.resolve(),
        bridge_runtime_tree_manifest_sha256=_sha(inputs.runtime_manifest_path, "runtime manifest"),
        node_executable_path=inputs.node_executable_path.resolve(),
        node_executable_sha256=_sha(inputs.node_executable_path, "Node executable"),
        node_version=execute.OFFICIAL_NODE_VERSION,
        python_executable_path=inputs.python_executable_path.resolve(),
        python_executable_sha256=_sha(inputs.python_executable_path, "Python executable"),
        python_version=execute.OFFICIAL_PYTHON_VERSION,
        unicode_data_version=execute.OFFICIAL_UNICODE_DATA_VERSION,
        scorer_import_root=root,
    )
    if config.output_root.exists() or config.output_root.is_symlink():
        raise ConfigurationRefusal("planned evidence output root must be new")
    try:
        config.output_root.relative_to(root)
    except ValueError:
        pass
    else:
        raise ConfigurationRefusal("planned evidence output root must be outside preregistration-B checkout")
    try:
        inputs.config_output_path.resolve().relative_to(root)
    except ValueError:
        pass
    else:
        raise ConfigurationRefusal("configuration output must be outside preregistration-B checkout")
    created: list[Path] = []
    published_config = False
    try:
        created.extend(_new_owner_directory(config.bridge_state_root, "bridge-state root"))
        created.extend(_new_owner_directory(config.attempt_registry_root, "attempt-registry root"))
        # Validate all receipts/preregistration/runtime pins using the same
        # non-execution code path that the executor will use later.
        source_ci, _, source_ci_completed_unix = execute._load_source_ci_receipt(
            config
        )
        if not (
            source_freeze_unix
            <= source_ci_completed_unix
            <= preregistration_commit_unix
            <= b_ci_completed
        ):
            raise ConfigurationRefusal(
                "Source-A/A-CI/preregistration-B/B-CI chronology is invalid"
            )
        source_manifest_value = execute._load_source_manifest(config)
        execute._load_structured_output_qualification(
            config, source_manifest=source_manifest_value
        )
        execute._validate_preregistration(config, source_ci_receipt=source_ci)
        execute._load_preregistration_ci_receipt(
            config, SimpleNamespace(git_runner=None, git_bytes_runner=None)
        )
        execute._verify_static_pins(config, require_official_runtime_identity=True)
        raw = execute.canonical_json(_json_config(config))
        digest = _write_new_owner_file(inputs.config_output_path.resolve(), raw)
        published_config = True
        # The public CLI loader is the durable interface even where internal
        # helpers differ between revisions.
        if execute._config_from_json(inputs.config_output_path.resolve()) != config:
            raise ConfigurationRefusal("written configuration does not round-trip executor loader")
        return digest
    except (OSError, execute.ExecutionRefusal, ConfigurationRefusal) as error:
        if published_config:
            try:
                inputs.config_output_path.resolve().unlink()
                _fsync_directory(inputs.config_output_path.resolve().parent)
            except FileNotFoundError:
                pass
        _remove_new_directories(created)
        if isinstance(error, ConfigurationRefusal):
            raise
        raise ConfigurationRefusal(str(error)) from error


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m _research.dnrd.configure",
        description="Offline DNRD-4S1 post-B config builder; never calls model/network/seed/pulse/execute.",
    )
    for name in (
        "repo-root", "source-ci-receipt", "preregistration-ci-receipt", "qualification",
        "runtime-manifest", "bridge-state-root", "attempt-registry-root", "output-root",
        "config-output", "node-executable", "python-executable",
    ):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--preregistration-path", required=True)
    parser.add_argument("--source-manifest-path", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        digest = configure_execution(ConfigurationInputs(
            repo_root=_path(args.repo_root), preregistration_path=args.preregistration_path,
            source_manifest_path=args.source_manifest_path, source_ci_receipt_path=_path(args.source_ci_receipt),
            preregistration_ci_receipt_path=_path(args.preregistration_ci_receipt), qualification_path=_path(args.qualification),
            runtime_manifest_path=_path(args.runtime_manifest), bridge_state_root=_path(args.bridge_state_root),
            attempt_registry_root=_path(args.attempt_registry_root), output_root=_path(args.output_root),
            config_output_path=_path(args.config_output), node_executable_path=_path(args.node_executable),
            python_executable_path=_path(args.python_executable),
        ))
    except (OSError, ConfigurationRefusal, execute.ExecutionRefusal) as error:
        print(f"DNRD-4S1 configuration refused: {error}", file=sys.stderr)
        return 2
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
