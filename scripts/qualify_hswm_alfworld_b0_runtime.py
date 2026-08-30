#!/usr/bin/env python3
"""Qualify the sealed 20-action ALFWorld B0 runtime on DGX ARM64.

This is an engineering fixed-action check, not a B0 occurrence: it makes no
model or network request, learns nothing, and cannot support G0 or G1.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any, Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments.alfworld_b0_calibration import verify_protocol
from hswm.experiments.alfworld_b0_runtime import load_local_game_binding
from hswm.experiments.alfworld_text_runtime import (
    AlfworldTextRuntimeError,
    LocalAlfworldTextRuntime,
    LocalSandboxSpec,
    action_line,
    read_one_line,
    validate_actor_projection,
    validate_outcome_receipt,
)


SCHEMA = "hswm-alfworld-b0-runtime-dgx-qualification/v1"
PUBLIC_SCHEMA = "hswm-alfworld-b0-runtime-dgx-qualification-public/v1"
STATUS = "ENGINEERING_INSTRUMENT_QUALIFIED_DGX_ARM64_G0_NOT_PASSED"
CLAIM_CEILING = (
    "ONE_SEALED_20_ACTION_FIXED_LOOK_RUNTIME_CHECK_ONLY_NOT_MODEL_OR_AGENT_"
    "EFFICACY_NOT_LEARNING_NOT_G0_NOT_G1"
)
FIXED_ACTION = "look"
MAX_STEPS = 20
PYTHON_VERSION = "3.9.25"
PLATFORM_MACHINE = "aarch64"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class QualificationError(RuntimeError):
    """A sealed B0 runtime qualification contract failed."""


def _sha256_file(path: Path, label: str, *, symlink: bool = False) -> str:
    if not path.is_absolute() or not path.is_file() or (path.is_symlink() and not symlink):
        raise QualificationError(f"{label} must be an absolute regular file")
    return sha256(path.read_bytes()).hexdigest()


def _canonical_receipt(value: Mapping[str, object]) -> dict[str, object]:
    unsigned = dict(value)
    if "receipt_sha256" in unsigned:
        raise QualificationError("receipt input must not already contain receipt_sha256")
    return {**unsigned, "receipt_sha256": sha256(canonical_bytes(unsigned)).hexdigest()}


def _write_new(path: Path, value: Mapping[str, object], label: str) -> None:
    if not path.is_absolute() or not path.parent.is_dir():
        raise QualificationError(f"{label} parent must be an existing absolute directory")
    try:
        with path.open("xb") as stream:
            stream.write(canonical_bytes(dict(value)) + b"\n")
    except FileExistsError as error:
        raise QualificationError(f"{label} already exists; refusing to overwrite it") from error


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except ValueError:
        return False
    return True


def _git(repository: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(repository), *args), check=False, capture_output=True, timeout=30
    )
    if completed.returncode or completed.stderr:
        raise QualificationError("qualification source checkout binding failed")
    return completed.stdout


def committed_execution(repository: Path, sources: Mapping[str, Path]) -> dict[str, str]:
    """Require a clean checkout and bind every qualification source to HEAD."""
    if _git(repository, "status", "--porcelain").strip():
        raise QualificationError("qualification source checkout is dirty")
    commit = _git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    tree = _git(repository, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9a-f]{40}", tree):
        raise QualificationError("qualification commit or tree is invalid")
    for path in sources.values():
        if not _under(path, repository):
            raise QualificationError("qualification source escaped the repository")
        relative = path.relative_to(repository).as_posix()
        if path.read_bytes() != _git(repository, "show", f"HEAD:{relative}"):
            raise QualificationError("qualification source differs from HEAD")
    return {"commit": commit, "tree": tree}


def validate_output_paths(*, local_receipt: Path, public_aggregate: Path, repository: Path,
                          allow_public_outside_manifests: bool) -> None:
    """Private receipt stays external; public output needs an explicit placement choice."""
    if not repository.is_absolute() or not repository.is_dir():
        raise QualificationError("repository must be an absolute existing directory")
    if not local_receipt.is_absolute() or not public_aggregate.is_absolute():
        raise QualificationError("receipt outputs must be absolute paths")
    if local_receipt == public_aggregate or local_receipt.exists() or public_aggregate.exists():
        raise QualificationError("qualification outputs must be distinct, new paths")
    if _under(local_receipt, repository):
        raise QualificationError("private receipt must remain outside the repository")
    if not allow_public_outside_manifests and not _under(public_aggregate, repository / "manifests"):
        raise QualificationError("public aggregate must be under repository/manifests or explicitly allowed outside")


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _requirements(path: Path) -> dict[str, str]:
    raw = _sha256_file(path, "requirements")
    del raw  # The protocol binds the rendered file; parsing is only a local consistency check.
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s#]+)", line)
        if match is None:
            raise QualificationError("requirements must contain only exact pinned distributions")
        name = _canonical_name(match.group(1))
        if name in rows:
            raise QualificationError("requirements contain a duplicate distribution")
        rows[name] = match.group(2)
    if not rows:
        raise QualificationError("requirements are empty")
    return rows


def installed_environment(python: Path, *, required: Mapping[str, str]) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Probe only the selected interpreter and require every pinned package."""
    if not python.is_absolute() or not python.is_file():
        raise QualificationError("venv python must be an absolute regular file")
    probe = (
        "import importlib.metadata,json,platform,sys; "
        "rows=sorted((d.metadata['Name'].lower(),d.version) for d in importlib.metadata.distributions() if d.metadata.get('Name')); "
        "print(json.dumps({'version':'.'.join(map(str,sys.version_info[:3])),'machine':platform.machine(),"
        "'packages':[{'name':n,'version':v} for n,v in rows]},sort_keys=True,separators=(',',':'),ensure_ascii=True))"
    )
    completed = subprocess.run([str(python), "-c", probe], check=False, capture_output=True, timeout=30)
    if completed.returncode != 0 or completed.stderr:
        raise QualificationError("venv environment probe failed")
    try:
        value = json.loads(completed.stdout)
        version, machine, rows = value["version"], value["machine"], value["packages"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise QualificationError("venv environment probe emitted invalid JSON") from error
    if version != PYTHON_VERSION or machine != PLATFORM_MACHINE:
        raise QualificationError(f"requires Python {PYTHON_VERSION} on {PLATFORM_MACHINE}, got {version!r}/{machine!r}")
    if not isinstance(rows, list):
        raise QualificationError("venv package inventory shape drifted")
    packages: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "version"} or not all(isinstance(row[k], str) and row[k] for k in row):
            raise QualificationError("venv package inventory row drifted")
        packages.append({"name": _canonical_name(row["name"]), "version": row["version"]})
    packages.sort(key=lambda item: (item["name"], item["version"]))
    if len({item["name"] for item in packages}) != len(packages):
        raise QualificationError("venv has colliding canonical package names")
    by_name = {item["name"]: item["version"] for item in packages}
    expected = {**required, "textworld": "1.7.0", "alfworld": "0.5.0"}
    mismatches = [name for name, version in expected.items() if by_name.get(name) != version]
    if mismatches:
        raise QualificationError("exact required package versions missing: " + ", ".join(sorted(mismatches)))
    extras = sorted(set(by_name) - set(expected))
    if extras:
        raise QualificationError("venv contains undeclared distributions: " + ", ".join(extras))
    return packages, {name: by_name[name] for name in sorted(expected)}


def bwrap_identity(bubblewrap: Path) -> dict[str, str]:
    digest = _sha256_file(bubblewrap, "bubblewrap")
    completed = subprocess.run([str(bubblewrap), "--version"], check=False, capture_output=True, timeout=15)
    if completed.returncode != 0 or completed.stderr:
        raise QualificationError("bubblewrap version probe failed")
    version = completed.stdout.decode("utf-8", "strict").strip()
    if not version or "\n" in version:
        raise QualificationError("bubblewrap version output is invalid")
    return {"binary_sha256": digest, "version": version}


def public_projection(local: Mapping[str, object]) -> dict[str, object]:
    """Render an aggregate-only projection with exactly one private-file link."""
    expected = {
        "schema_version", "status", "claim_ceiling", "protocol", "execution", "source_code_sha256", "python",
        "packages", "bubblewrap", "pool_manifest_sha256", "local_locator_sha256", "terminal",
        "fixed_action", "actor_frame_count", "action_count", "local_receipt_file_sha256",
    }
    if set(local) != expected:
        raise QualificationError("private receipt field set drifted")
    terminal, protocol = local["terminal"], local["protocol"]
    if not isinstance(terminal, dict) or not isinstance(protocol, dict):
        raise QualificationError("private receipt nested contract drifted")
    public = {
        "schema_version": PUBLIC_SCHEMA, "status": local["status"], "claim_ceiling": local["claim_ceiling"],
        "protocol": {"file_sha256": protocol["file_sha256"], "verified_sha256": protocol["verified_binding_sha256"]},
        "execution": local["execution"],
        "source_code_sha256": local["source_code_sha256"], "python": local["python"],
        "packages": {"key_versions": local["packages"]["key_versions"], "installed_package_count": local["packages"]["installed_package_count"], "installed_package_list_sha256": local["packages"]["installed_package_list_sha256"]},
        "bubblewrap": local["bubblewrap"], "pool_manifest_sha256": local["pool_manifest_sha256"],
        "local_locator_sha256": local["local_locator_sha256"], "fixed_action": local["fixed_action"],
        "actor_frame_count": local["actor_frame_count"], "action_count": local["action_count"],
        "terminal": {key: terminal[key] for key in ("done", "won", "success", "score")},
        "local_receipt_file_sha256": local["local_receipt_file_sha256"],
    }
    forbidden = ("uid", "path", "observation", "game", "outcome", "digest", "binding")
    keys = " ".join(_all_keys(public)).lower()
    if any(word in keys for word in forbidden):
        raise QualificationError("public projection leakage guard rejected its own fields")
    return _canonical_receipt(public)


def _all_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value] + [child for item in value.values() for child in _all_keys(item)]
    if isinstance(value, list):
        return [child for item in value for child in _all_keys(item)]
    return []


def run(args: argparse.Namespace) -> tuple[dict[str, object], dict[str, object]]:
    repository = args.repository.resolve(strict=True)
    validate_output_paths(local_receipt=args.local_receipt, public_aggregate=args.public_aggregate,
                          repository=repository, allow_public_outside_manifests=args.allow_public_outside_manifests)
    if platform.machine() != PLATFORM_MACHINE:
        raise QualificationError(f"qualification launcher must run on {PLATFORM_MACHINE}")
    verified = verify_protocol(args.protocol)
    protocol_sha = _sha256_file(args.protocol, "protocol")
    protocol_raw = json.loads(args.protocol.read_bytes())
    environment = protocol_raw.get("environment_runtime") if isinstance(protocol_raw, dict) else None
    if not isinstance(environment, dict):
        raise QualificationError("protocol environment runtime is missing")
    requirements = repository / str(environment.get("arm64_pddl_only_requirements_path", ""))
    if (
        _sha256_file(requirements, "requirements")
        != environment.get("arm64_pddl_only_requirements_sha256")
    ):
        raise QualificationError("requirements file does not match protocol")
    inherited_requirements = repository / str(environment.get("inherited_requirements_path", ""))
    if (
        _sha256_file(inherited_requirements, "inherited requirements")
        != environment.get("inherited_requirements_sha256")
    ):
        raise QualificationError("inherited requirements file does not match protocol")
    textworld = environment.get("textworld")
    if not isinstance(textworld, dict):
        raise QualificationError("TextWorld adapter contract is absent")
    textworld_patch = repository / str(textworld.get("patch_path", ""))
    if _sha256_file(textworld_patch, "TextWorld patch") != textworld.get("patch_sha256"):
        raise QualificationError("TextWorld adapter patch does not match protocol")
    packages, key_versions = installed_environment(args.venv_python, required=_requirements(requirements))
    pool_sha, locator_sha, binding, game_file = load_local_game_binding(pool_manifest=args.pool_manifest,
        local_locator=args.local_locator, asset_root=args.asset_root, opaque_uid=args.game_uid)
    source_paths = {
        "qualification_cli": Path(__file__).resolve(),
        "b0_runtime": repository / "src/hswm/experiments/alfworld_b0_runtime.py",
        "historical_runtime": repository / "src/hswm/experiments/alfworld_text_runtime.py",
        "worker": repository / "src/hswm/experiments/alfworld_text_worker.py",
        "arm64_requirements": requirements,
        "inherited_requirements": inherited_requirements,
        "textworld_patch": textworld_patch,
    }
    execution = committed_execution(repository, source_paths)
    source_code = {
        name: _sha256_file(path, name.replace("_", " "))
        for name, path in source_paths.items()
    }
    spec = LocalSandboxSpec(args.bwrap, args.venv_python, args.python_runtime_root, repository, args.upstream,
        args.venv, args.asset_root, game_file, pool_sha, locator_sha, binding, args.episode_uid, max_steps=MAX_STEPS)
    process = LocalAlfworldTextRuntime(spec).launch()
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    actor_frames, previous_step = 0, None
    try:
        while True:
            frame = validate_actor_projection(read_one_line(process.stdout, timeout_seconds=args.frame_timeout_seconds,
                label="actor frame"), episode_uid=args.episode_uid, previous_step=previous_step)
            if (previous_step is None and frame["step_index"] != 0) or int(frame["step_index"]) > MAX_STEPS:
                raise QualificationError("actor frame step index drifted from fixed 20-action protocol")
            actor_frames += 1; previous_step = int(frame["step_index"])
            if frame["done"]:
                break
            if previous_step >= MAX_STEPS:
                raise QualificationError("worker failed to terminate at 20 actions")
            process.stdin.write(action_line(episode_uid=args.episode_uid, action=FIXED_ACTION)); process.stdin.flush()
        process.stdin.close()
        return_code = process.wait(timeout=args.terminal_timeout_seconds)
        extra_stdout, outcome_raw = process.stdout.read(), process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=10)
    if return_code != 0 or extra_stdout:
        raise QualificationError("worker exit or stdout closure contract failed")
    outcome = validate_outcome_receipt(outcome_raw, episode_uid=args.episode_uid,
        source_game_sha256=binding.file_sha256, actor_steps=actor_frames - 1)
    if not bool(outcome["done"]) or actor_frames - 1 > MAX_STEPS:
        raise QualificationError("terminal outcome or 20-action bound failed")
    private_without_link: dict[str, object] = {
        "schema_version": SCHEMA, "status": STATUS, "claim_ceiling": CLAIM_CEILING,
        "protocol": {"path": str(args.protocol.relative_to(repository)), "file_sha256": protocol_sha,
                     "verified_binding_sha256": verified.binding_sha256}, "execution": execution,
        "source_code_sha256": source_code,
        "python": {"executable_sha256": _sha256_file(args.venv_python, "venv python", symlink=True), "version": PYTHON_VERSION, "platform_machine": PLATFORM_MACHINE},
        "packages": {"key_versions": key_versions, "installed_package_count": len(packages),
                     "installed_package_list_sha256": sha256(canonical_bytes(packages)).hexdigest(), "installed_packages": packages},
        "bubblewrap": bwrap_identity(args.bwrap), "pool_manifest_sha256": pool_sha, "local_locator_sha256": locator_sha,
        "fixed_action": FIXED_ACTION, "actor_frame_count": actor_frames, "action_count": actor_frames - 1,
        "terminal": {key: outcome[key] for key in ("done", "won", "success", "score")},
    }
    private = _canonical_receipt({**private_without_link, "private_binding": {"episode_uid": args.episode_uid,
        "game_opaque_uid": binding.opaque_uid, "game_relative_path": binding.relative_path,
        "game_file_sha256": binding.file_sha256, "game_bytes": binding.bytes, "outcome_receipt": outcome}})
    serialized_private = canonical_bytes(private) + b"\n"
    local_for_public = {**private_without_link, "local_receipt_file_sha256": sha256(serialized_private).hexdigest()}
    public = public_projection(local_for_public)
    _write_new(args.local_receipt, private, "private receipt")
    _write_new(args.public_aggregate, public, "public aggregate")
    return private, public


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pool-manifest", "local-locator", "asset-root", "bwrap", "venv-python", "python-runtime-root", "repository", "upstream", "venv", "protocol", "local-receipt", "public-aggregate"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--game-uid", required=True); parser.add_argument("--episode-uid", required=True)
    parser.add_argument("--allow-public-outside-manifests", action="store_true")
    parser.add_argument("--frame-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--terminal-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.frame_timeout_seconds <= 0 or args.terminal_timeout_seconds <= 0:
        parser.error("timeouts must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        run(parse_args(argv))
    except (AlfworldTextRuntimeError, QualificationError, OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"qualification refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
