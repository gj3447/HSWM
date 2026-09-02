"""Source-pin and qualify bounded external graph-standard tooling.

This module operates only on external standards inputs and read-only
qualification adapters.  It is not a canonical HSWM writer, Permit issuer,
causal adjudicator, learning transition, or efficacy evaluator.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


LOCK_SCHEMA = "hswm-graph-standards-acceptance/v1"
RECEIPT_SCHEMA = "hswm-graph-standard-qualification-receipt/v1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOCK = (
    REPOSITORY_ROOT
    / "_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json"
)
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_RUNNABLE = {
    "RUNNABLE_REQUIRES_PINNED_SUITE",
    "RUNNABLE_NON_PROMOTING_DRAFT_DIAGNOSTIC",
}


class GraphStandardToolingError(RuntimeError):
    """Raised when a standards input or qualification boundary drifts."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise GraphStandardToolingError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise GraphStandardToolingError(f"{label} must be an array")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise GraphStandardToolingError(f"{label} must be a non-empty string")
    return value


def _digest(value: Any, label: str) -> str:
    text = _string(value, label)
    if _HEX64.fullmatch(text) is None:
        raise GraphStandardToolingError(f"{label} must be a lowercase SHA-256")
    return text


def _commit(value: Any, label: str) -> str:
    text = _string(value, label)
    if _HEX40.fullmatch(text) is None:
        raise GraphStandardToolingError(f"{label} must be a 40-character git id")
    return text


def _https(value: Any, label: str, *, git: bool = False) -> str:
    text = _string(value, label)
    if not text.startswith("https://") or "@" in text.split("/", 3)[2]:
        raise GraphStandardToolingError(f"{label} must be credential-free HTTPS")
    if git and not text.endswith(".git"):
        raise GraphStandardToolingError(f"{label} must name an explicit .git repository")
    return text


def _relative_path(value: Any, label: str) -> str:
    text = _string(value, label)
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise GraphStandardToolingError(f"{label} must stay repository-relative")
    return text


def _index_by_id(values: Any, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_array(values, label)):
        item = _object(raw, f"{label}[{index}]")
        identifier = _string(item.get("id"), f"{label}[{index}].id")
        if identifier in result:
            raise GraphStandardToolingError(f"duplicate {label} id: {identifier}")
        result[identifier] = item
    return result


def load_acceptance_lock(path: Path = DEFAULT_LOCK) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise GraphStandardToolingError(f"cannot read graph standards lock: {path}") from error
    lock = _object(value, "graph standards lock")
    if lock.get("schema_version") != LOCK_SCHEMA:
        raise GraphStandardToolingError("graph standards lock schema drift")
    return lock


def verify_acceptance_lock(
    lock: Mapping[str, Any], *, repository_root: Path = REPOSITORY_ROOT
) -> dict[str, Any]:
    policy = _object(lock.get("policy"), "policy")
    required_policy = {
        "official_standard_sdk_suite_first": True,
        "openai_system_or_curated_skill_first": True,
        "exact_version_commit_digest_and_lock_required": True,
        "mcp_role": "LIVE_DATA_ACTION_AUTH_BOUNDARY",
        "skill_role": "REUSABLE_WORKFLOW_INSTRUCTIONS_RESOURCES",
        "hswm_adapter_rule": (
            "ONLY_WHERE_NO_SUITABLE_STANDARD_SURFACE_AND_THEN_"
            "THIN_BOUNDED_AND_CLAIM_LIMITED"
        ),
        "mcp_registry_role": "DISCOVERY_ONLY_NO_AUTO_TRUST_NO_AUTO_INSTALL",
    }
    if any(policy.get(name) != value for name, value in required_policy.items()):
        raise GraphStandardToolingError("standard-first policy is not fail-closed")

    lanes = _object(lock.get("lanes"), "lanes")
    if set(lanes) != {"stable", "experimental", "metadata_only"}:
        raise GraphStandardToolingError("standards lanes must be explicit and closed")

    standards = _index_by_id(lock.get("standards"), "standards")
    for identifier, standard in standards.items():
        lane = _string(standard.get("lane"), f"standard {identifier} lane")
        if lane not in lanes:
            raise GraphStandardToolingError(f"standard {identifier} has an unknown lane")
        _https(standard.get("official_url"), f"standard {identifier} URL")
        if standard.get("status") == "DRAFT_STANDARD" and lane != "experimental":
            raise GraphStandardToolingError(
                f"draft standard {identifier} escaped experimental lane"
            )

    sources = _index_by_id(lock.get("suite_sources"), "suite_sources")
    for identifier, source in sources.items():
        if source.get("authority") != "W3C":
            raise GraphStandardToolingError(f"suite {identifier} is not an official W3C source")
        _https(source.get("repository"), f"source {identifier} repository", git=True)
        _commit(source.get("commit"), f"source {identifier} commit")
        _relative_path(source.get("selected_path"), f"source {identifier} selected path")
        _commit(source.get("git_tree_sha1"), f"source {identifier} tree")
        _digest(source.get("git_archive_sha256"), f"source {identifier} archive")
        _relative_path(source.get("manifest_path"), f"source {identifier} manifest path")
        _digest(source.get("manifest_sha256"), f"source {identifier} manifest")
        _relative_path(source.get("license_path"), f"source {identifier} license path")
        _digest(source.get("license_sha256"), f"source {identifier} license")

    adapters = _index_by_id(lock.get("tool_adapters"), "tool_adapters")
    for identifier, adapter in adapters.items():
        if not _string(adapter.get("authority_class"), f"adapter {identifier} authority").endswith(
            "NOT_W3C"
        ):
            raise GraphStandardToolingError(f"adapter {identifier} hides its non-W3C authority")
        package = _string(adapter.get("package"), f"adapter {identifier} package")
        version = _string(adapter.get("version"), f"adapter {identifier} version")
        integrity = _string(adapter.get("npm_integrity"), f"adapter {identifier} integrity")
        if not integrity.startswith("sha512-"):
            raise GraphStandardToolingError(f"adapter {identifier} lacks npm SHA-512 integrity")
        _https(adapter.get("source_repository"), f"adapter {identifier} source", git=True)
        _commit(adapter.get("source_commit"), f"adapter {identifier} source commit")
        lockfile_relative = _relative_path(
            adapter.get("lockfile"), f"adapter {identifier} lockfile"
        )
        lockfile_path = repository_root / lockfile_relative
        try:
            package_lock = json.loads(lockfile_path.read_bytes())
            package_entry = package_lock["packages"][f"node_modules/{package}"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise GraphStandardToolingError(
                f"adapter {identifier} is absent from {lockfile_relative}"
            ) from error
        if package_entry.get("version") != version or package_entry.get("integrity") != integrity:
            raise GraphStandardToolingError(f"adapter {identifier} package lock drift")
        if package_entry.get("license") != adapter.get("license"):
            raise GraphStandardToolingError(f"adapter {identifier} license drift")

    runtime = _object(lock.get("runtime_lock"), "runtime_lock")
    package_manifest_relative = _relative_path(
        runtime.get("package_manifest"), "runtime package manifest"
    )
    try:
        package_manifest_bytes = (repository_root / package_manifest_relative).read_bytes()
        package_manifest = json.loads(package_manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise GraphStandardToolingError("runtime package manifest is unavailable") from error
    if sha256(package_manifest_bytes).hexdigest() != _digest(
        runtime.get("package_manifest_sha256"), "runtime package manifest digest"
    ):
        raise GraphStandardToolingError("runtime package manifest digest drift")
    package_lock_relative = _relative_path(runtime.get("package_lock"), "runtime package lock")
    try:
        package_lock_bytes = (repository_root / package_lock_relative).read_bytes()
    except OSError as error:
        raise GraphStandardToolingError("runtime package lock is unavailable") from error
    if sha256(package_lock_bytes).hexdigest() != _digest(
        runtime.get("package_lock_sha256"), "runtime package lock digest"
    ):
        raise GraphStandardToolingError("runtime package lock digest drift")
    if package_manifest.get("engines", {}).get("node") != runtime.get("node"):
        raise GraphStandardToolingError("Node runtime lock drift")
    if package_manifest.get("packageManager") != f"npm@{runtime.get('npm')}":
        raise GraphStandardToolingError("npm runtime lock drift")

    profiles = _index_by_id(lock.get("qualification_profiles"), "qualification_profiles")
    for identifier, profile in profiles.items():
        lane = _string(profile.get("lane"), f"profile {identifier} lane")
        if lane not in lanes:
            raise GraphStandardToolingError(f"profile {identifier} has an unknown lane")
        standard_ids = _array(profile.get("standard_ids"), f"profile {identifier} standards")
        if not standard_ids or any(item not in standards for item in standard_ids):
            raise GraphStandardToolingError(f"profile {identifier} references an unknown standard")
        if lane == "stable" and any(
            standards[item]["lane"] == "experimental" for item in standard_ids
        ):
            raise GraphStandardToolingError(f"profile {identifier} promotes a draft standard")
        status = _string(profile.get("status"), f"profile {identifier} status")
        if status in _RUNNABLE:
            if profile.get("suite_source_id") not in sources:
                raise GraphStandardToolingError(f"profile {identifier} has no locked suite")
            if profile.get("adapter_id") not in adapters:
                raise GraphStandardToolingError(f"profile {identifier} has no locked adapter")
            runner_relative = _relative_path(profile.get("runner"), f"profile {identifier} runner")
            runner_path = repository_root / runner_relative
            if not runner_path.is_file():
                raise GraphStandardToolingError(f"profile {identifier} runner is unavailable")
            if sha256(runner_path.read_bytes()).hexdigest() != _digest(
                profile.get("runner_sha256"), f"profile {identifier} runner digest"
            ):
                raise GraphStandardToolingError(f"profile {identifier} runner digest drift")
            qualification_manifest_relative = _relative_path(
                profile.get("qualification_manifest_path"),
                f"profile {identifier} qualification manifest path",
            )
            selected_path = Path(sources[profile["suite_source_id"]]["selected_path"])
            try:
                Path(qualification_manifest_relative).relative_to(selected_path)
            except ValueError as error:
                raise GraphStandardToolingError(
                    f"profile {identifier} qualification manifest escapes selected source"
                ) from error
            _digest(
                profile.get("qualification_manifest_sha256"),
                f"profile {identifier} qualification manifest",
            )
            expected = _object(profile.get("expected"), f"profile {identifier} expected counts")
            if not expected or any(
                type(value) is not int or value <= 0 for value in expected.values()
            ):
                raise GraphStandardToolingError(
                    f"profile {identifier} expected counts are invalid"
                )

    seen_receipts: set[str] = set()
    receipt_records = _array(
        lock.get("qualification_receipts"), "qualification_receipts"
    )
    for index, raw in enumerate(receipt_records):
        receipt_record = _object(raw, f"qualification_receipts[{index}]")
        profile_id = _string(
            receipt_record.get("profile_id"), f"qualification_receipts[{index}].profile_id"
        )
        if profile_id not in profiles or profile_id in seen_receipts:
            raise GraphStandardToolingError(f"invalid or duplicate receipt profile: {profile_id}")
        seen_receipts.add(profile_id)
        receipt_relative = _relative_path(
            receipt_record.get("path"), f"qualification receipt {profile_id} path"
        )
        expected_receipt_digest = _digest(
            receipt_record.get("receipt_sha256"),
            f"qualification receipt {profile_id} digest",
        )
        try:
            receipt = _object(
                json.loads((repository_root / receipt_relative).read_bytes()),
                f"qualification receipt {profile_id}",
            )
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise GraphStandardToolingError(
                f"qualification receipt unavailable: {profile_id}"
            ) from error
        embedded_digest = receipt.pop("receipt_sha256", None)
        observed_digest = sha256(_canonical_json_bytes(receipt)).hexdigest()
        if (
            embedded_digest != expected_receipt_digest
            or observed_digest != expected_receipt_digest
        ):
            raise GraphStandardToolingError(f"qualification receipt digest drift: {profile_id}")
        profile = profiles[profile_id]
        result = _object(receipt.get("result"), f"qualification receipt {profile_id} result")
        counts = _object(
            result.get("counts"), f"qualification receipt {profile_id} counts"
        )
        adapter = _object(
            receipt.get("adapter"), f"qualification receipt {profile_id} adapter"
        )
        source = _object(
            receipt.get("source"), f"qualification receipt {profile_id} source"
        )
        runtime_receipt = _object(
            receipt.get("runtime"), f"qualification receipt {profile_id} runtime"
        )
        expected = _object(profile.get("expected"), f"qualification profile {profile_id} expected")
        locked_adapter = adapters[profile["adapter_id"]]
        locked_source = sources[profile["suite_source_id"]]
        if (
            receipt.get("schema_version") != RECEIPT_SCHEMA
            or receipt.get("profile_id") != profile_id
            or receipt.get("lane") != profile.get("lane")
            or receipt.get("standards") != profile.get("standard_ids")
            or result.get("status") != "PASS"
            or counts.get("failed") != 0
            or counts.get("passed") != expected.get("total")
            or any(counts.get(name) != count for name, count in expected.items())
            or receipt.get("claim_ceiling") != profile.get("claim_ceiling")
            or adapter.get("package") != locked_adapter.get("package")
            or adapter.get("version") != locked_adapter.get("version")
            or adapter.get("npm_integrity") != locked_adapter.get("npm_integrity")
            or adapter.get("source_commit") != locked_adapter.get("source_commit")
            or source.get("repository") != locked_source.get("repository")
            or source.get("commit") != locked_source.get("commit")
            or source.get("selected_path") != locked_source.get("selected_path")
            or source.get("tree_sha1") != locked_source.get("git_tree_sha1")
            or source.get("archive_sha256") != locked_source.get("git_archive_sha256")
            or source.get("license_sha256") != locked_source.get("license_sha256")
            or source.get("source_manifest_sha256") != locked_source.get("manifest_sha256")
            or source.get("qualification_manifest_path")
            != profile.get("qualification_manifest_path")
            or source.get("qualification_manifest_sha256")
            != profile.get("qualification_manifest_sha256")
            or runtime_receipt.get("node") != f"v{runtime.get('node')}"
            or runtime_receipt.get("npm") != runtime.get("npm")
            or runtime_receipt.get("package_lock_sha256")
            != runtime.get("package_lock_sha256")
            or runtime_receipt.get("installation")
            != "CLEAN_TEMPORARY_NPM_CI_IGNORE_SCRIPTS"
            or receipt.get("runner")
            != {"path": profile.get("runner"), "sha256": profile.get("runner_sha256")}
        ):
            raise GraphStandardToolingError(f"qualification receipt boundary drift: {profile_id}")

    runnable_profiles = {
        identifier
        for identifier, profile in profiles.items()
        if profile.get("status") in _RUNNABLE
    }
    if seen_receipts != runnable_profiles:
        missing = sorted(runnable_profiles - seen_receipts)
        extra = sorted(seen_receipts - runnable_profiles)
        raise GraphStandardToolingError(
            f"qualification receipt coverage drift: missing={missing}, extra={extra}"
        )

    mcp = _object(lock.get("mcp"), "mcp")
    registry = _object(mcp.get("registry"), "mcp.registry")
    if (
        registry.get("use") != "DISCOVERY_ONLY"
        or registry.get("auto_trust") is not False
        or registry.get("auto_install") is not False
    ):
        raise GraphStandardToolingError("MCP Registry boundary drift")
    _https(mcp.get("specification"), "MCP specification")
    sdk = _object(mcp.get("new_typescript_sdk"), "MCP TypeScript SDK")
    _https(sdk.get("source_repository"), "MCP SDK source", git=True)
    _commit(sdk.get("source_commit"), "MCP SDK source commit")
    packages = _array(sdk.get("packages"), "MCP SDK packages")
    if not packages or any(not isinstance(package, str) or not package for package in packages):
        raise GraphStandardToolingError("MCP SDK package metadata drift")
    tags = _object(sdk.get("source_tags"), "MCP SDK source tags")
    integrities = _object(sdk.get("npm_integrities"), "MCP SDK npm integrities")
    if set(tags) != set(packages) or set(integrities) != set(packages):
        raise GraphStandardToolingError("MCP SDK package pin coverage drift")
    for package in packages:
        if tags.get(package) != f"{package}@{sdk.get('version')}":
            raise GraphStandardToolingError(f"MCP SDK source tag drift: {package}")
        if not _string(integrities.get(package), f"MCP SDK {package} integrity").startswith(
            "sha512-"
        ):
            raise GraphStandardToolingError(f"MCP SDK package lacks integrity: {package}")
    if (
        sdk.get("license") != "MIT"
        or sdk.get("lockfile_status") != "NOT_APPLICABLE_UNTIL_ADOPTION"
        or sdk.get("install_status")
        != "NOT_INSTALLED_NO_CURRENT_TYPESCRIPT_MCP_IMPLEMENTATION"
    ):
        raise GraphStandardToolingError("unreviewed MCP SDK installation was recorded")

    skills = _object(lock.get("skills"), "skills")
    if skills.get("required_new_installations") != []:
        raise GraphStandardToolingError(
            "unexpected Skill installation entered the graph toolchain"
        )
    _https(skills.get("curated_repository"), "curated Skills repository", git=True)
    _commit(skills.get("observed_main_commit"), "curated Skills observation")

    return {
        "adapters": adapters,
        "profiles": profiles,
        "sources": sources,
        "standards": standards,
    }


def _run_git(arguments: Sequence[str], *, capture_bytes: bool = False) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise GraphStandardToolingError("git is unavailable")
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_ASKPASS": "/bin/false",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    try:
        result = subprocess.run(
            [executable, *arguments],
            check=True,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        raise GraphStandardToolingError(
            f"git operation failed with exit {error.returncode}"
        ) from error
    return result.stdout if capture_bytes else result.stdout.strip()


def verify_source_checkout(
    source: Mapping[str, Any], checkout: Path
) -> dict[str, str]:
    checkout = checkout.resolve(strict=True)
    if not (checkout / ".git").exists():
        raise GraphStandardToolingError(f"not a git checkout: {checkout}")
    commit = _commit(source.get("commit"), "source commit")
    observed_commit = _run_git(["-C", str(checkout), "rev-parse", "HEAD"]).decode("ascii")
    if observed_commit != commit:
        raise GraphStandardToolingError("source checkout commit drift")
    selected_path = _relative_path(source.get("selected_path"), "selected source path")
    observed_tree = _run_git(
        ["-C", str(checkout), "rev-parse", f"HEAD:{selected_path}"]
    ).decode("ascii")
    if observed_tree != source.get("git_tree_sha1"):
        raise GraphStandardToolingError("source checkout selected tree drift")
    archive = _run_git(
        ["-C", str(checkout), "archive", "--format=tar", commit, "--", selected_path],
        capture_bytes=True,
    )
    archive_digest = sha256(archive).hexdigest()
    if archive_digest != source.get("git_archive_sha256"):
        raise GraphStandardToolingError("source checkout archive digest drift")
    dirty = _run_git(
        [
            "-C",
            str(checkout),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            selected_path,
        ]
    )
    if dirty:
        raise GraphStandardToolingError("source checkout selected tree is dirty")
    observed_files: dict[str, str] = {}
    for field in ("manifest", "license"):
        relative = _relative_path(source.get(f"{field}_path"), f"source {field} path")
        path = (checkout / relative).resolve(strict=True)
        if checkout not in path.parents:
            raise GraphStandardToolingError(f"source {field} escapes checkout")
        digest = sha256(path.read_bytes()).hexdigest()
        if digest != source.get(f"{field}_sha256"):
            raise GraphStandardToolingError(f"source {field} digest drift")
        observed_files[field] = digest
    return {
        "archive_sha256": archive_digest,
        "commit": observed_commit,
        "license_sha256": observed_files["license"],
        "manifest_sha256": observed_files["manifest"],
        "tree_sha1": observed_tree,
    }


def materialize_source(source: Mapping[str, Any], destination: Path) -> dict[str, str]:
    if destination.exists() or destination.is_symlink():
        raise GraphStandardToolingError("materialization destination must not exist")
    parent = destination.parent.resolve(strict=True)
    repository_root = REPOSITORY_ROOT.resolve()
    if parent == repository_root or repository_root in parent.parents:
        raise GraphStandardToolingError(
            "official suites must be materialized outside the repository"
        )
    repository = _https(source.get("repository"), "source repository", git=True)
    commit = _commit(source.get("commit"), "source commit")
    _run_git(["init", "--quiet", str(destination)])
    _run_git(["-C", str(destination), "remote", "add", "origin", repository])
    _run_git(["-C", str(destination), "fetch", "--quiet", "--depth=1", "origin", commit])
    _run_git(["-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD"])
    return verify_source_checkout(source, destination)


def _write_exact_or_create(path: Path, payload: bytes) -> None:
    path.parent.resolve(strict=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise GraphStandardToolingError(f"refusing to overwrite different receipt: {path}")
        return
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def qualify_profile(
    lock: Mapping[str, Any],
    *,
    profile_id: str,
    source_root: Path,
    output: Path | None = None,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    indexes = verify_acceptance_lock(lock, repository_root=repository_root)
    try:
        profile = indexes["profiles"][profile_id]
    except KeyError as error:
        raise GraphStandardToolingError(f"unknown qualification profile: {profile_id}") from error
    if profile.get("status") not in _RUNNABLE:
        raise GraphStandardToolingError(f"profile is not runnable: {profile_id}")
    source = indexes["sources"][profile["suite_source_id"]]
    adapter = indexes["adapters"][profile["adapter_id"]]
    observed_source = verify_source_checkout(source, source_root)

    node = shutil.which("node")
    if node is None:
        raise GraphStandardToolingError("Node.js is unavailable")
    try:
        observed_node = subprocess.run(
            [node, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise GraphStandardToolingError("Node.js version probe failed") from error
    expected_node = f"v{lock['runtime_lock']['node']}"
    if observed_node != expected_node:
        raise GraphStandardToolingError(
            f"Node.js version drift: expected {expected_node}, observed {observed_node}"
        )
    npm = shutil.which("npm")
    if npm is None:
        raise GraphStandardToolingError("npm is unavailable")
    try:
        observed_npm = subprocess.run(
            [npm, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise GraphStandardToolingError("npm version probe failed") from error
    if observed_npm != lock["runtime_lock"]["npm"]:
        raise GraphStandardToolingError(
            f"npm version drift: expected {lock['runtime_lock']['npm']}, observed {observed_npm}"
        )
    runner = repository_root / profile["runner"]
    selected_root = (source_root / source["selected_path"]).resolve(strict=True)
    source_root_resolved = source_root.resolve(strict=True)
    if source_root_resolved not in selected_root.parents:
        raise GraphStandardToolingError("selected suite path escapes source checkout")
    runtime = lock["runtime_lock"]
    package_manifest = repository_root / runtime["package_manifest"]
    package_lock = repository_root / runtime["package_lock"]
    with tempfile.TemporaryDirectory(prefix="hswm-graph-standard-npm-") as temporary:
        module_root = Path(temporary)
        shutil.copy2(package_manifest, module_root / "package.json")
        shutil.copy2(package_lock, module_root / "package-lock.json")
        environment = os.environ.copy()
        environment.update(
            {
                "npm_config_audit": "false",
                "npm_config_fund": "false",
                "npm_config_ignore_scripts": "true",
            }
        )
        try:
            installed = subprocess.run(
                [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                cwd=module_root,
                check=False,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as error:
            raise GraphStandardToolingError(
                "clean npm dependency installation timed out"
            ) from error
        if installed.returncode != 0:
            raise GraphStandardToolingError("clean npm dependency installation failed")
        try:
            completed = subprocess.run(
                [
                    node,
                    str(runner),
                    "--module-root",
                    str(module_root),
                    "--profile",
                    profile_id,
                    "--suite-root",
                    str(selected_root),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as error:
            raise GraphStandardToolingError("graph standard qualification timed out") from error
    try:
        result = _object(json.loads(completed.stdout), "qualification result")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise GraphStandardToolingError("qualification runner returned non-JSON") from error
    if completed.returncode != 0 or result.get("status") != "PASS":
        raise GraphStandardToolingError(
            f"qualification failed for {profile_id}: {result.get('failures', completed.stderr)}"
        )
    if result.get("profile") != profile_id:
        raise GraphStandardToolingError("qualification profile identity drift")
    qualification_manifest = (
        source_root / profile["qualification_manifest_path"]
    ).resolve(strict=True)
    if source_root.resolve(strict=True) not in qualification_manifest.parents:
        raise GraphStandardToolingError("qualification manifest escapes source checkout")
    qualification_manifest_digest = sha256(qualification_manifest.read_bytes()).hexdigest()
    if (
        qualification_manifest_digest != profile["qualification_manifest_sha256"]
        or result.get("manifest_sha256") != qualification_manifest_digest
    ):
        raise GraphStandardToolingError("qualification manifest binding drift")
    observed_adapter = _object(result.get("adapter"), "qualification adapter")
    if (
        observed_adapter.get("package") != adapter.get("package")
        or observed_adapter.get("version") != adapter.get("version")
    ):
        raise GraphStandardToolingError("qualification adapter drift")
    counts = _object(result.get("counts"), "qualification counts")
    for name, expected in profile["expected"].items():
        if counts.get(name) != expected:
            raise GraphStandardToolingError(
                f"qualification count drift for {name}: {counts.get(name)} != {expected}"
            )
    unsigned = {
        "adapter": {
            "authority_class": adapter["authority_class"],
            "npm_integrity": adapter["npm_integrity"],
            "package": adapter["package"],
            "source_commit": adapter["source_commit"],
            "version": adapter["version"],
        },
        "claim_ceiling": profile["claim_ceiling"],
        "lane": profile["lane"],
        "nonclaims": [
            "NOT_HSWM_COGNITION",
            "NOT_CANONICAL_ADMISSION_OR_PERMIT",
            "NOT_OUTCOME_TRUTH_OR_CAUSAL_CREDIT",
            "NOT_CONTINUOUS_LEARNING_OR_LLM_EFFICACY",
            "TEST_SUITE_PASS_DOES_NOT_IMPLY_UNIVERSAL_SPECIFICATION_CONFORMANCE",
        ],
        "profile_id": profile_id,
        "result": {"counts": counts, "status": "PASS"},
        "runner": {"path": profile["runner"], "sha256": profile["runner_sha256"]},
        "runtime": {
            "installation": "CLEAN_TEMPORARY_NPM_CI_IGNORE_SCRIPTS",
            "node": observed_node,
            "npm": observed_npm,
            "package_lock_sha256": runtime["package_lock_sha256"],
        },
        "schema_version": RECEIPT_SCHEMA,
        "source": {
            "archive_sha256": observed_source["archive_sha256"],
            "commit": observed_source["commit"],
            "license_sha256": observed_source["license_sha256"],
            "qualification_manifest_path": profile["qualification_manifest_path"],
            "qualification_manifest_sha256": result["manifest_sha256"],
            "repository": source["repository"],
            "selected_path": source["selected_path"],
            "source_manifest_sha256": observed_source["manifest_sha256"],
            "tree_sha1": observed_source["tree_sha1"],
        },
        "standards": profile["standard_ids"],
    }
    receipt = {**unsigned, "receipt_sha256": sha256(_canonical_json_bytes(unsigned)).hexdigest()}
    if output is not None:
        _write_exact_or_create(output, _pretty_json_bytes(receipt))
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify and run source-pinned HSWM graph-standard qualification."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_LOCK)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--source-id", required=True)
    fetch.add_argument("--destination", required=True, type=Path)
    qualify = subparsers.add_parser("qualify")
    qualify.add_argument("--profile", required=True)
    qualify.add_argument("--source-root", required=True, type=Path)
    qualify.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        lock = load_acceptance_lock(arguments.manifest)
        indexes = verify_acceptance_lock(lock)
        if arguments.command == "verify":
            result: Any = {
                "schema_version": LOCK_SCHEMA,
                "status": "PASS",
                "suite_sources": len(indexes["sources"]),
                "runnable_profiles": sum(
                    profile.get("status") in _RUNNABLE
                    for profile in indexes["profiles"].values()
                ),
            }
        elif arguments.command == "fetch":
            try:
                source = indexes["sources"][arguments.source_id]
            except KeyError as error:
                raise GraphStandardToolingError(
                    f"unknown suite source: {arguments.source_id}"
                ) from error
            result = {
                "source_id": arguments.source_id,
                "status": "PASS",
                **materialize_source(source, arguments.destination),
            }
        else:
            result = qualify_profile(
                lock,
                profile_id=arguments.profile,
                source_root=arguments.source_root,
                output=arguments.output,
            )
    except GraphStandardToolingError as error:
        sys.stderr.write(f"REFUSED: {error}\n")
        return 2
    sys.stdout.buffer.write(_pretty_json_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
