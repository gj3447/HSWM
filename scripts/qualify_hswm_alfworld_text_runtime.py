#!/usr/bin/env python3
"""Run one sealed ALFWorld text-runtime G0 instrument qualification.

This command is deliberately not an agent evaluator or a learning experiment.
It sends the fixed ``look`` action until the sealed text environment reaches a
terminal frame, writes a private local receipt outside the repository, and
writes a content-free public aggregate projection.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

# ``python scripts/<name>.py`` puts ``scripts/`` rather than the repository
# root on sys.path.  Keep the documented direct invocation independent of the
# caller's working directory before importing the repository-owned canonical
# JSON helper.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments.alfworld_text_runtime import (
    AlfworldTextRuntimeError,
    LocalAlfworldTextRuntime,
    LocalSandboxSpec,
    action_line,
    load_local_game_binding,
    read_one_line,
    validate_actor_projection,
    validate_outcome_receipt,
)


SCHEMA = "hswm-alfworld-text-runtime-qualification/v1"
PUBLIC_SCHEMA = "hswm-alfworld-text-runtime-qualification-public/v1"
STATUS = "ENGINEERING_INSTRUMENT_QUALIFIED_G0_NOT_PASSED"
CLAIM_CEILING = (
    "ONE_SEALED_TEXT_RUNTIME_FIXED_ACTION_SMOKE_ONLY_NOT_AGENT_EFFICACY_"
    "NOT_LEARNING_NOT_G1_NOT_INDEPENDENT_EVALUATION"
)
KEY_DISTRIBUTIONS = (
    "alfworld",
    "textworld",
    "fast-downward-textworld",
    "jericho",
    "numpy",
)


class QualificationError(RuntimeError):
    """A qualification input, sandbox transcript, or output contract failed."""


def _canonical_distribution_name(value: str) -> str:
    """Apply the PEP 503 distribution-name normalization used by installers."""
    return re.sub(r"[-_.]+", "-", value).lower()


def _sha256_file(path: Path, label: str) -> str:
    if not path.is_absolute() or not path.is_file():
        raise QualificationError(f"{label} must be an absolute regular file")
    return sha256(path.read_bytes()).hexdigest()


def _canonical_receipt(value: Mapping[str, object]) -> dict[str, object]:
    unsigned = dict(value)
    if "receipt_sha256" in unsigned:
        raise QualificationError("receipt input must not already contain receipt_sha256")
    return {**unsigned, "receipt_sha256": sha256(canonical_bytes(unsigned)).hexdigest()}


def _write_new_canonical_json(path: Path, value: Mapping[str, object], label: str) -> None:
    if not path.is_absolute() or not path.parent.is_dir():
        raise QualificationError(f"{label} parent must be an existing absolute directory")
    encoded = canonical_bytes(dict(value)) + b"\n"
    try:
        with path.open("xb") as stream:
            stream.write(encoded)
    except FileExistsError as error:
        raise QualificationError(f"{label} already exists; refusing to overwrite it") from error


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
    except ValueError:
        return False
    return True


def validate_output_paths(*, local_receipt: Path, public_aggregate: Path, repository: Path,
                          allow_public_outside_manifests: bool) -> None:
    """Refuse repository-local private receipts and accidental aggregate placement."""
    if not repository.is_absolute() or not repository.is_dir():
        raise QualificationError("repository must be an absolute existing directory")
    if not local_receipt.is_absolute() or not public_aggregate.is_absolute():
        raise QualificationError("receipt outputs must be absolute paths")
    if local_receipt == public_aggregate:
        raise QualificationError("private and public receipt paths must differ")
    if local_receipt.exists() or public_aggregate.exists():
        raise QualificationError("qualification output already exists; refusing to overwrite it")
    if _under(local_receipt, repository):
        raise QualificationError("local receipt must remain outside the repository")
    manifests = repository / "manifests"
    if not allow_public_outside_manifests and not _under(public_aggregate, manifests):
        raise QualificationError("public aggregate must be under repository/manifests or explicitly allowed outside")


def installed_packages(python: Path) -> tuple[str, list[dict[str, str]], dict[str, str]]:
    """Use the selected venv interpreter only; no package installation or network."""
    if not python.is_absolute() or not python.is_file():
        raise QualificationError("venv python must be an absolute regular file")
    probe = (
        "import importlib.metadata,json,sys; "
        "rows=sorted((d.metadata['Name'].lower(),d.version) for d in importlib.metadata.distributions() "
        "if d.metadata.get('Name')); "
        "print(json.dumps({'python':sys.version,'packages':[{'name':n,'version':v} for n,v in rows]},"
        "sort_keys=True,separators=(',',':'),ensure_ascii=True))"
    )
    completed = subprocess.run([str(python), "-c", probe], check=False, capture_output=True, timeout=30)
    if completed.returncode != 0 or completed.stderr:
        raise QualificationError("venv package probe failed")
    try:
        result = json.loads(completed.stdout)
        version = result["python"]
        packages = result["packages"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise QualificationError("venv package probe emitted invalid JSON") from error
    if not isinstance(version, str) or not isinstance(packages, list):
        raise QualificationError("venv package probe shape drifted")
    normalized: list[dict[str, str]] = []
    for row in packages:
        if not isinstance(row, dict) or set(row) != {"name", "version"} or not all(isinstance(row[key], str) and row[key] for key in row):
            raise QualificationError("venv package probe package shape drifted")
        normalized.append({"name": _canonical_distribution_name(row["name"]), "version": row["version"]})
    normalized.sort(key=lambda row: (row["name"], row["version"]))
    if len({row["name"] for row in normalized}) != len(normalized):
        raise QualificationError("venv contains colliding canonical distribution names")
    by_name = {row["name"]: row["version"] for row in normalized}
    missing = [name for name in KEY_DISTRIBUTIONS if name not in by_name]
    if missing:
        raise QualificationError(f"venv lacks required runtime distributions: {', '.join(missing)}")
    return version, normalized, {name: by_name[name] for name in KEY_DISTRIBUTIONS}


def bwrap_version(bubblewrap: Path) -> str:
    _sha256_file(bubblewrap, "bubblewrap")
    completed = subprocess.run([str(bubblewrap), "--version"], check=False, capture_output=True, timeout=15)
    if completed.returncode != 0 or completed.stderr:
        raise QualificationError("bubblewrap version probe failed")
    value = completed.stdout.decode("utf-8", "strict").strip()
    if not value or "\n" in value:
        raise QualificationError("bubblewrap version output is invalid")
    return value


def public_projection(local_receipt: Mapping[str, object]) -> dict[str, object]:
    """Create the sole repository-safe projection; deliberately omit game identity/content."""
    expected = {
        "schema_version", "status", "claim_ceiling", "pool_manifest_sha256", "local_locator_sha256",
        "source_code_sha256", "python", "packages", "bubblewrap", "protocol", "terminal",
        "local_receipt_sha256",
    }
    if set(local_receipt) != expected:
        raise QualificationError("local receipt field set drifted")
    terminal = local_receipt["terminal"]
    protocol = local_receipt["protocol"]
    if not isinstance(terminal, dict) or not isinstance(protocol, dict):
        raise QualificationError("local receipt result shape drifted")
    value = {
        "schema_version": PUBLIC_SCHEMA,
        "status": local_receipt["status"],
        "claim_ceiling": local_receipt["claim_ceiling"],
        "pool_manifest_sha256": local_receipt["pool_manifest_sha256"],
        "local_locator_sha256": local_receipt["local_locator_sha256"],
        "source_code_sha256": local_receipt["source_code_sha256"],
        "python": local_receipt["python"],
        "packages": {
            "key_versions": local_receipt["packages"]["key_versions"],
            "installed_package_count": local_receipt["packages"]["installed_package_count"],
            "installed_package_list_sha256": local_receipt["packages"]["installed_package_list_sha256"],
        },
        "bubblewrap": local_receipt["bubblewrap"],
        "protocol": {"actor_frame_count": protocol["actor_frame_count"], "action_count": protocol["action_count"]},
        "terminal": {key: terminal[key] for key in ("done", "won", "success", "score")},
        "local_receipt_sha256": local_receipt["local_receipt_sha256"],
    }
    forbidden = ("uid", "path", "observation", "game", "outcome", "digest")
    encoded_keys = " ".join(_all_keys(value)).lower()
    if any(token in encoded_keys for token in forbidden):
        raise QualificationError("public projection leakage guard rejected its own fields")
    return _canonical_receipt(value)


def _all_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value] + [key for item in value.values() for key in _all_keys(item)]
    if isinstance(value, list):
        return [key for item in value for key in _all_keys(item)]
    return []


def run(args: argparse.Namespace) -> tuple[dict[str, object], dict[str, object]]:
    repository = args.repository.resolve(strict=True)
    validate_output_paths(local_receipt=args.local_receipt, public_aggregate=args.public_aggregate,
                          repository=repository, allow_public_outside_manifests=args.allow_public_outside_manifests)
    pool_sha, locator_sha, binding, game_file = load_local_game_binding(
        pool_manifest=args.pool_manifest, local_locator=args.local_locator, asset_root=args.asset_root,
        opaque_uid=args.game_uid,
    )
    python_version, packages, key_versions = installed_packages(args.venv_python)
    source_code = {
        "qualification_cli": _sha256_file(Path(__file__).resolve(), "qualification CLI"),
        "runtime": _sha256_file(repository / "src/hswm/experiments/alfworld_text_runtime.py", "runtime source"),
        "worker": _sha256_file(repository / "src/hswm/experiments/alfworld_text_worker.py", "worker source"),
    }
    spec = LocalSandboxSpec(
        bubblewrap=args.bwrap, python=args.venv_python, python_runtime_root=args.python_runtime_root,
        repository=repository, upstream=args.upstream, venv=args.venv, asset_root=args.asset_root,
        game_file=game_file, pool_manifest_sha256=pool_sha, local_locator_sha256=locator_sha,
        game_binding=binding, episode_uid=args.episode_uid,
    )
    runtime = LocalAlfworldTextRuntime(spec)
    process = runtime.launch()
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    actor_frames = 0
    previous_step: int | None = None
    try:
        while True:
            raw = read_one_line(process.stdout, timeout_seconds=args.frame_timeout_seconds, label="actor frame")
            frame = validate_actor_projection(raw, episode_uid=args.episode_uid, previous_step=previous_step)
            if previous_step is None and frame["step_index"] != 0:
                raise QualificationError("first actor frame must have step index zero")
            actor_frames += 1
            previous_step = int(frame["step_index"])
            if frame["done"]:
                break
            process.stdin.write(action_line(episode_uid=args.episode_uid, action="look"))
            process.stdin.flush()
        process.stdin.close()
        try:
            return_code = process.wait(timeout=args.terminal_timeout_seconds)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait(timeout=10)
            raise QualificationError("worker did not terminate after terminal frame") from error
        extra_stdout = process.stdout.read()
        outcome_raw = process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    if return_code != 0:
        raise QualificationError(f"worker exited with status {return_code}")
    if extra_stdout:
        raise QualificationError("worker emitted extra stdout after terminal frame")
    outcome = validate_outcome_receipt(outcome_raw, episode_uid=args.episode_uid,
                                       source_game_sha256=binding.file_sha256,
                                       actor_steps=actor_frames - 1)
    if not bool(outcome["done"]):
        raise QualificationError("terminal outcome must report done")
    local_unsigned: dict[str, object] = {
        "schema_version": SCHEMA,
        "status": STATUS,
        "claim_ceiling": CLAIM_CEILING,
        "pool_manifest_sha256": pool_sha,
        "local_locator_sha256": locator_sha,
        "source_code_sha256": source_code,
        "python": {"executable_sha256": _sha256_file(args.venv_python, "venv python"), "version": python_version},
        "packages": {"key_versions": key_versions, "installed_package_count": len(packages),
                     "installed_package_list_sha256": sha256(canonical_bytes(packages)).hexdigest(),
                     "installed_packages": packages},
        "bubblewrap": {"binary_sha256": _sha256_file(args.bwrap, "bubblewrap"), "version": bwrap_version(args.bwrap)},
        "protocol": {"fixed_action": "look", "actor_frame_count": actor_frames, "action_count": actor_frames - 1},
        "terminal": {key: outcome[key] for key in ("done", "won", "success", "score")},
        "local_receipt_sha256": "",  # set after binding the private game/outcome fields below
    }
    # The public projection receives only the digest of this private object.  Its
    # game identity and outcome digests never enter repository-visible output.
    private_binding = {
        "episode_uid": args.episode_uid,
        "game_opaque_uid": binding.opaque_uid,
        "game_relative_path": binding.relative_path,
        "game_file_sha256": binding.file_sha256,
        "game_bytes": binding.bytes,
        "outcome_receipt": outcome,
    }
    local_without_link = {key: value for key, value in local_unsigned.items() if key != "local_receipt_sha256"}
    local = _canonical_receipt({**local_without_link, "private_binding": private_binding})
    # Use the canonical local receipt digest as the only link in the public file.
    local_receipt_sha = str(local["receipt_sha256"])
    public_input = {key: value for key, value in local_without_link.items()}
    public_input["local_receipt_sha256"] = local_receipt_sha
    public = public_projection(public_input)
    _write_new_canonical_json(args.local_receipt, local, "local receipt")
    _write_new_canonical_json(args.public_aggregate, public, "public aggregate")
    return local, public


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-manifest", type=Path, required=True)
    parser.add_argument("--local-locator", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--game-uid", required=True)
    parser.add_argument("--episode-uid", required=True)
    parser.add_argument("--bwrap", type=Path, required=True)
    parser.add_argument("--venv-python", type=Path, required=True)
    parser.add_argument("--python-runtime-root", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--local-receipt", type=Path, required=True)
    parser.add_argument("--public-aggregate", type=Path, required=True)
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
    except (AlfworldTextRuntimeError, QualificationError, OSError, subprocess.SubprocessError) as error:
        print(f"qualification refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
