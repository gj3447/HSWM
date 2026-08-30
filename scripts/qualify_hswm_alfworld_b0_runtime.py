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
import tarfile
from typing import Any, Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for _import_root in (REPOSITORY_ROOT, REPOSITORY_ROOT / "src"):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

from _research.dnrd5.canonical_json import canonical_bytes
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
CONTRACT_SCHEMA = "hswm-alfworld-b0-runtime-dgx-qualification-contract/v1"
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


def _read_contract(path: Path, repository: Path) -> tuple[dict[str, object], str]:
    """Load the immutable pre-B0 qualification contract, never the live protocol."""

    if not path.is_absolute() or path.is_symlink() or not path.is_file() or not _under(path, repository):
        raise QualificationError("qualification contract must be a repository regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QualificationError("qualification contract is unreadable JSON") from error
    if not isinstance(value, dict) or canonical_bytes(value) + b"\n" != raw:
        raise QualificationError("qualification contract must be canonical JSON")
    try:
        canonical_bytes(value)
    except ValueError as error:
        raise QualificationError("qualification contract is outside canonical JSON") from error
    expected_sources = {
        "qualification_contract": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/runtime_qualification_contract.v1.json",
        "qualification_cli": "scripts/qualify_hswm_alfworld_b0_runtime.py",
        "canonical_json": "_research/dnrd5/canonical_json.py",
        "b0_calibration": "src/hswm/experiments/alfworld_b0_calibration.py",
        "b0_actor": "src/hswm/experiments/alfworld_b0_actor.py",
        "b0_runtime": "src/hswm/experiments/alfworld_b0_runtime.py",
        "historical_runtime": "src/hswm/experiments/alfworld_text_runtime.py",
        "worker": "src/hswm/experiments/alfworld_text_worker.py",
        "arm64_requirements": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.arm64_pddl_only.requirements.v1.txt",
        "inherited_requirements": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.requirements.v1.txt",
        "textworld_patch": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/textworld-pddl-only.v1.patch",
    }
    profile = value.get("runtime_profile")
    if (
        value.get("schema_version") != CONTRACT_SCHEMA
        or value.get("record_role") != "IMMUTABLE_PRE_B0_RUNTIME_QUALIFICATION_CONTRACT"
        or value.get("registration_status")
        != "PROSPECTIVE_BEFORE_ANY_B0_SELECTION_ENVIRONMENT_MODEL_OR_OUTCOME_CALL"
        or value.get("status") != "RUNTIME_QUALIFICATION_CONTRACT_ONLY_G0_NOT_PASSED"
        or value.get("claim_ceiling") != CLAIM_CEILING
        or value.get("boundary")
        != {
            "no_b0_selection": True,
            "no_model_or_network_request": True,
            "no_learning_or_revision": True,
            "no_hswm_efficacy_claim": True,
            "valid_unseen_record_access": "SPLIT_TOKEN_ONLY_NO_UID_OR_PATH_DECODE_OR_RETENTION",
        }
        or value.get("fixed_look") != {"action": FIXED_ACTION, "maximum_actions": MAX_STEPS}
        or not isinstance(profile, dict)
        or value.get("execution_sources") != expected_sources
        or value.get("public_record")
        != {"schema_version": PUBLIC_SCHEMA, "status": STATUS, "aggregate_only": True}
    ):
        raise QualificationError("qualification contract boundary or source binding drifted")
    expected_profile = {
        "platform_machine": PLATFORM_MACHINE,
        "python_version": PYTHON_VERSION,
        "alfworld": {
            "upstream_repository": "https://github.com/alfworld/alfworld",
            "upstream_revision": "aaba6870f86c5be6a08a491f32a50b906227bc3e",
            "upstream_tree": "339069f91317079df9e378efd4ab253417d79b82",
            "source_archive_sha256": "5592fbb36124b08d24167c5f7612a55a2cc610e0c39170f638a69b628835ee3b",
            "extracted_tree_member_manifest_sha256": "6c956159bbedeb82f9c44a08196d78633a50f1cbd98db8036ad92c45e262048e",
            "clean_checkout_required": True,
        },
        "requirements": {
            "inherited_path": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.requirements.v1.txt",
            "inherited_sha256": "2cd843b101554f7935709168be65be5039bcac41f32a2aa7b1b4f54f8ee320c8",
            "arm64_pddl_only_path": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.arm64_pddl_only.requirements.v1.txt",
            "arm64_pddl_only_sha256": "2835136ea0b72f65374d584ddae3c4951737e8c0eabb7effae7d588a313655e7",
        },
        "textworld": {
            "upstream_repository": "https://github.com/microsoft/TextWorld",
            "upstream_revision": "9fce9ee107fa042ef2656e41e0b362450a35ecd8",
            "upstream_tree": "c3d347b795b9c83b30250892606017d2742929d2",
            "patch_path": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/textworld-pddl-only.v1.patch",
            "patch_sha256": "8b623fe87548694b3990896d69260ae3325c2d686cac62c7daf3963a23772c1d",
            "patched_setup_py_sha256": "896b896f3d9662042aa5ba666cfdb3debc2d548206f0569a16d9508908ad933a",
            "install_environment": {"TEXTWORLD_PDDL_ONLY": "1"},
            "capability": "PDDL_ONLY_NO_INFORM7_SETUP_OR_CAPABILITY",
        },
    }
    if profile != expected_profile:
        raise QualificationError("qualification contract platform drifted")
    return value, sha256(raw).hexdigest()


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


def _external_git(repository: Path, *args: str) -> bytes:
    if not repository.is_absolute() or repository.is_symlink() or not repository.is_dir():
        raise QualificationError("upstream checkout must be an absolute non-symlink directory")
    completed = subprocess.run(
        ("git", "-C", str(repository), *args), check=False, capture_output=True, timeout=30
    )
    if completed.returncode or completed.stderr:
        raise QualificationError("upstream checkout identity check failed")
    return completed.stdout


def _exact_checkout(
    checkout: Path,
    *,
    revision: str,
    tree: str,
    require_clean: bool,
    label: str,
) -> None:
    if require_clean and _external_git(checkout, "status", "--porcelain").strip():
        raise QualificationError(f"{label} checkout is dirty")
    observed_revision = _external_git(checkout, "rev-parse", "HEAD").decode("ascii").strip()
    observed_tree = _external_git(checkout, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    if observed_revision != revision or observed_tree != tree:
        raise QualificationError(f"{label} checkout revision or tree drifted")


def _verify_textworld_patch(checkout: Path, profile: Mapping[str, object], patch: Path) -> None:
    """Require exactly the one declared setup.py patch atop the pinned upstream tree."""

    revision, tree = profile.get("upstream_revision"), profile.get("upstream_tree")
    if not isinstance(revision, str) or not isinstance(tree, str):
        raise QualificationError("TextWorld source identity is malformed")
    _exact_checkout(checkout, revision=revision, tree=tree, require_clean=False, label="TextWorld")
    changed = _external_git(checkout, "diff", "--name-only").decode("utf-8", "strict").splitlines()
    if changed != ["setup.py"]:
        raise QualificationError("TextWorld checkout must contain only the declared setup.py patch")
    if _sha256_file(checkout / "setup.py", "patched TextWorld setup.py") != profile.get("patched_setup_py_sha256"):
        raise QualificationError("patched TextWorld setup.py identity drifted")
    checked = subprocess.run(
        ("git", "-C", str(checkout), "apply", "--reverse", "--check", str(patch)),
        check=False,
        capture_output=True,
        timeout=30,
    )
    if checked.returncode or checked.stderr:
        raise QualificationError("TextWorld patch is not exactly applied")


def _source_member_rows_from_archive(archive: Path, *, root: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    try:
        with tarfile.open(archive, "r:gz") as stream:
            for member in stream.getmembers():
                if not member.isfile():
                    continue
                prefix = root + "/"
                if not member.name.startswith(prefix) or not member.name[len(prefix):]:
                    raise QualificationError("ALFWorld archive member path drifted")
                extracted = stream.extractfile(member)
                if extracted is None:
                    raise QualificationError("ALFWorld archive member is unreadable")
                payload = extracted.read()
                rows.append({"path": member.name[len(prefix):], "bytes": len(payload), "sha256": sha256(payload).hexdigest()})
    except (OSError, tarfile.TarError) as error:
        raise QualificationError("ALFWorld source archive cannot be read") from error
    rows.sort(key=lambda row: str(row["path"]))
    if not rows or len({str(row["path"]) for row in rows}) != len(rows):
        raise QualificationError("ALFWorld archive member set is invalid")
    return rows


def _source_member_rows_from_tree(tree: Path) -> list[dict[str, object]]:
    if not tree.is_absolute() or tree.is_symlink() or not tree.is_dir():
        raise QualificationError("ALFWorld extracted source tree is invalid")
    rows: list[dict[str, object]] = []
    for path in tree.rglob("*"):
        relative = path.relative_to(tree).as_posix()
        if "__pycache__" in path.parts or relative.endswith(".pyc"):
            continue
        if path.is_symlink() or not path.is_file():
            if path.is_symlink():
                raise QualificationError("ALFWorld extracted source tree contains a symlink")
            continue
        payload = path.read_bytes()
        rows.append({"path": relative, "bytes": len(payload), "sha256": sha256(payload).hexdigest()})
    rows.sort(key=lambda row: str(row["path"]))
    if not rows or len({str(row["path"]) for row in rows}) != len(rows):
        raise QualificationError("ALFWorld extracted member set is invalid")
    return rows


def _verify_alfworld_archive_tree(archive: Path, tree: Path, profile: Mapping[str, object]) -> None:
    revision = profile.get("upstream_revision")
    if not isinstance(revision, str):
        raise QualificationError("ALFWorld source revision is malformed")
    root = "alfworld-" + revision
    archive_rows = _source_member_rows_from_archive(archive, root=root)
    archive_manifest = sha256(canonical_bytes(archive_rows)).hexdigest()
    if archive_manifest != profile.get("extracted_tree_member_manifest_sha256"):
        raise QualificationError("ALFWorld archive member manifest drifted")
    if _source_member_rows_from_tree(tree) != archive_rows:
        raise QualificationError("ALFWorld extracted tree differs from exact source archive")


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
    del raw  # The immutable qualification contract binds rendered requirement bytes.
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
        "schema_version", "status", "claim_ceiling", "qualification_contract", "execution", "source_code_sha256", "python",
        "packages", "bubblewrap", "pool_manifest_sha256", "local_locator_sha256", "terminal",
        "fixed_action", "actor_frame_count", "action_count", "local_receipt_file_sha256",
    }
    if set(local) != expected:
        raise QualificationError("private receipt field set drifted")
    terminal, contract = local["terminal"], local["qualification_contract"]
    if not isinstance(terminal, dict) or not isinstance(contract, dict):
        raise QualificationError("private receipt nested contract drifted")
    if (
        contract.get("file_sha256") is None
        or set(terminal) != {"done", "won", "success", "score"}
        or any(type(terminal[key]) is not bool for key in ("done", "won", "success"))
        or type(terminal["score"]) not in {int, float}
        or local.get("fixed_action") != FIXED_ACTION
        or type(local.get("actor_frame_count")) is not int
        or type(local.get("action_count")) is not int
    ):
        raise QualificationError("private receipt cannot safely project an aggregate")
    public = {
        "schema_version": PUBLIC_SCHEMA, "status": local["status"], "claim_ceiling": local["claim_ceiling"],
        "qualification_contract": {"file_sha256": contract["file_sha256"]},
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
    contract, contract_sha = _read_contract(args.qualification_contract, repository)
    profile = contract["runtime_profile"]
    assert isinstance(profile, dict)
    requirements_profile = profile.get("requirements")
    alfworld_profile = profile.get("alfworld")
    textworld_profile = profile.get("textworld")
    if not all(isinstance(value, dict) for value in (requirements_profile, alfworld_profile, textworld_profile)):
        raise QualificationError("qualification contract runtime profile is malformed")
    requirements = repository / str(requirements_profile.get("arm64_pddl_only_path", ""))
    if (
        _sha256_file(requirements, "requirements")
        != requirements_profile.get("arm64_pddl_only_sha256")
    ):
        raise QualificationError("requirements file does not match qualification contract")
    inherited_requirements = repository / str(requirements_profile.get("inherited_path", ""))
    if (
        _sha256_file(inherited_requirements, "inherited requirements")
        != requirements_profile.get("inherited_sha256")
    ):
        raise QualificationError("inherited requirements file does not match qualification contract")
    textworld_patch = repository / str(textworld_profile.get("patch_path", ""))
    if _sha256_file(textworld_patch, "TextWorld patch") != textworld_profile.get("patch_sha256"):
        raise QualificationError("TextWorld adapter patch does not match qualification contract")
    source_archive = _sha256_file(args.alfworld_source_archive, "ALFWorld source archive")
    if source_archive != alfworld_profile.get("source_archive_sha256"):
        raise QualificationError("ALFWorld source archive identity drifted")
    _verify_alfworld_archive_tree(args.alfworld_source_archive, args.upstream, alfworld_profile)
    _verify_textworld_patch(args.textworld, textworld_profile, textworld_patch)
    packages, key_versions = installed_environment(args.venv_python, required=_requirements(requirements))
    pool_sha, locator_sha, binding, game_file = load_local_game_binding(pool_manifest=args.pool_manifest,
        local_locator=args.local_locator, asset_root=args.asset_root, opaque_uid=args.game_uid)
    declared_sources = contract["execution_sources"]
    assert isinstance(declared_sources, dict)
    source_paths = {name: repository / relative for name, relative in declared_sources.items()}
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
        "qualification_contract": {"path": str(args.qualification_contract.relative_to(repository)), "file_sha256": contract_sha}, "execution": execution,
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
    for name in ("pool-manifest", "local-locator", "asset-root", "bwrap", "venv-python", "python-runtime-root", "repository", "upstream", "venv", "qualification-contract", "alfworld-source-archive", "textworld", "local-receipt", "public-aggregate"):
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
