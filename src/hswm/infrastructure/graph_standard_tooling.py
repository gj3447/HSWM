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
import tomllib
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


def _repository_file(root: Path, relative: str, label: str) -> Path:
    try:
        resolved_root = root.resolve(strict=True)
        candidate = (resolved_root / relative).resolve(strict=True)
        candidate.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise GraphStandardToolingError(f"{label} escapes or is unavailable") from error
    if not candidate.is_file():
        raise GraphStandardToolingError(f"{label} is not a regular file")
    return candidate


def _index_by_id(values: Any, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_array(values, label)):
        item = _object(raw, f"{label}[{index}]")
        identifier = _string(item.get("id"), f"{label}[{index}].id")
        if identifier in result:
            raise GraphStandardToolingError(f"duplicate {label} id: {identifier}")
        result[identifier] = item
    return result


def _distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _adapter_receipt(adapter: Mapping[str, Any]) -> dict[str, Any]:
    value = {
        "authority_class": adapter["authority_class"],
        "ecosystem": adapter["ecosystem"],
        "package": adapter["package"],
        "source_commit": adapter["source_commit"],
        "version": adapter["version"],
    }
    if adapter["ecosystem"] == "npm":
        value["npm_integrity"] = adapter["npm_integrity"]
    else:
        value["sdist_sha256"] = adapter["sdist_sha256"]
        value["wheel_sha256"] = adapter["wheel_sha256"]
    return value


def _locked_runtime_receipt(
    lock: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, Any]:
    runner_runtime = profile.get("runner_runtime", "node")
    if runner_runtime == "node":
        runtime = _object(lock.get("runtime_lock"), "runtime_lock")
        return {
            "installation": "CLEAN_TEMPORARY_NPM_CI_IGNORE_SCRIPTS",
            "kind": "node-npm",
            "node": f"v{runtime['node']}",
            "npm": runtime["npm"],
            "package_lock_sha256": runtime["package_lock_sha256"],
        }
    if runner_runtime == "python":
        runtime = _object(lock.get("python_runtime_lock"), "python_runtime_lock")
        return {
            "extra": runtime["extra"],
            "installation": "CLEAN_ISOLATED_UV_RUN_LOCKED",
            "kind": "python-uv",
            "project_manifest_sha256": runtime["project_manifest_sha256"],
            "python": runtime["python"],
            "uv": runtime["uv"],
            "uv_lock_sha256": runtime["uv_lock_sha256"],
        }
    raise GraphStandardToolingError(
        f"unsupported qualification runner runtime: {runner_runtime}"
    )


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
        ecosystem = _string(adapter.get("ecosystem"), f"adapter {identifier} ecosystem")
        if ecosystem not in {"npm", "pypi"}:
            raise GraphStandardToolingError(f"adapter {identifier} has an unknown ecosystem")
        _https(adapter.get("source_repository"), f"adapter {identifier} source", git=True)
        _commit(adapter.get("source_commit"), f"adapter {identifier} source commit")
        lockfile_relative = _relative_path(
            adapter.get("lockfile"), f"adapter {identifier} lockfile"
        )
        lockfile_path = _repository_file(
            repository_root, lockfile_relative, f"adapter {identifier} lockfile"
        )
        if ecosystem == "npm":
            integrity = _string(
                adapter.get("npm_integrity"), f"adapter {identifier} integrity"
            )
            if not integrity.startswith("sha512-"):
                raise GraphStandardToolingError(
                    f"adapter {identifier} lacks npm SHA-512 integrity"
                )
            try:
                package_lock = json.loads(lockfile_path.read_bytes())
                package_entry = package_lock["packages"][f"node_modules/{package}"]
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
                raise GraphStandardToolingError(
                    f"adapter {identifier} is absent from {lockfile_relative}"
                ) from error
            if package_lock.get("lockfileVersion") != 3:
                raise GraphStandardToolingError("npm package lock format drift")
            for package_path, locked_package in package_lock.get("packages", {}).items():
                if not package_path:
                    continue
                resolved = locked_package.get("resolved")
                locked_integrity = locked_package.get("integrity")
                if (
                    locked_package.get("link") is True
                    or not isinstance(resolved, str)
                    or not resolved.startswith("https://registry.npmjs.org/")
                    or not isinstance(locked_integrity, str)
                    or not locked_integrity.startswith("sha512-")
                ):
                    raise GraphStandardToolingError(
                        f"npm package lock contains an unbound dependency: {package_path}"
                    )
            if (
                package_entry.get("version") != version
                or package_entry.get("integrity") != integrity
            ):
                raise GraphStandardToolingError(
                    f"adapter {identifier} package lock drift"
                )
            if package_entry.get("license") != adapter.get("license"):
                raise GraphStandardToolingError(f"adapter {identifier} license drift")
        else:
            sdist_sha256 = _digest(
                adapter.get("sdist_sha256"), f"adapter {identifier} sdist"
            )
            wheel_sha256 = _digest(
                adapter.get("wheel_sha256"), f"adapter {identifier} wheel"
            )
            project_manifest_relative = _relative_path(
                adapter.get("project_manifest"),
                f"adapter {identifier} project manifest",
            )
            extra = _string(adapter.get("project_extra"), f"adapter {identifier} extra")
            try:
                uv_lock = tomllib.loads(lockfile_path.read_text(encoding="utf-8"))
                candidates = [
                    entry
                    for entry in uv_lock["package"]
                    if _distribution_name(entry["name"]) == _distribution_name(package)
                ]
                project = tomllib.loads(
                    _repository_file(
                        repository_root,
                        project_manifest_relative,
                        f"adapter {identifier} project manifest",
                    ).read_text(encoding="utf-8")
                )
                requirements = project["project"]["optional-dependencies"][extra]
            except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
                raise GraphStandardToolingError(
                    f"adapter {identifier} Python lock is unavailable"
                ) from error
            if len(candidates) != 1 or candidates[0].get("version") != version:
                raise GraphStandardToolingError(
                    f"adapter {identifier} Python package lock drift"
                )
            locked = candidates[0]
            observed_sdist = str(locked.get("sdist", {}).get("hash", ""))
            observed_wheels = {
                str(wheel.get("hash", "")) for wheel in locked.get("wheels", [])
            }
            if (
                observed_sdist != f"sha256:{sdist_sha256}"
                or f"sha256:{wheel_sha256}" not in observed_wheels
                or not any(
                    _distribution_name(str(requirement).split("==", 1)[0])
                    == _distribution_name(package)
                    and str(requirement) == f"{package}=={version}"
                    for requirement in requirements
                )
            ):
                raise GraphStandardToolingError(
                    f"adapter {identifier} Python integrity or exact requirement drift"
                )

    runtime = _object(lock.get("runtime_lock"), "runtime_lock")
    package_manifest_relative = _relative_path(
        runtime.get("package_manifest"), "runtime package manifest"
    )
    try:
        package_manifest_bytes = _repository_file(
            repository_root, package_manifest_relative, "runtime package manifest"
        ).read_bytes()
        package_manifest = json.loads(package_manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise GraphStandardToolingError("runtime package manifest is unavailable") from error
    if sha256(package_manifest_bytes).hexdigest() != _digest(
        runtime.get("package_manifest_sha256"), "runtime package manifest digest"
    ):
        raise GraphStandardToolingError("runtime package manifest digest drift")
    package_lock_relative = _relative_path(runtime.get("package_lock"), "runtime package lock")
    try:
        package_lock_bytes = _repository_file(
            repository_root, package_lock_relative, "runtime package lock"
        ).read_bytes()
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

    python_runtime = _object(lock.get("python_runtime_lock"), "python_runtime_lock")
    python_manifest_relative = _relative_path(
        python_runtime.get("project_manifest"), "Python runtime project manifest"
    )
    python_lock_relative = _relative_path(
        python_runtime.get("uv_lock"), "Python runtime uv lock"
    )
    try:
        python_manifest_bytes = _repository_file(
            repository_root,
            python_manifest_relative,
            "Python runtime project manifest",
        ).read_bytes()
        python_lock_bytes = _repository_file(
            repository_root, python_lock_relative, "Python runtime uv lock"
        ).read_bytes()
    except OSError as error:
        raise GraphStandardToolingError("Python runtime lock is unavailable") from error
    if sha256(python_manifest_bytes).hexdigest() != _digest(
        python_runtime.get("project_manifest_sha256"),
        "Python runtime project manifest digest",
    ):
        raise GraphStandardToolingError("Python runtime project manifest digest drift")
    if sha256(python_lock_bytes).hexdigest() != _digest(
        python_runtime.get("uv_lock_sha256"), "Python runtime uv lock digest"
    ):
        raise GraphStandardToolingError("Python runtime uv lock digest drift")
    _string(python_runtime.get("python"), "Python runtime version")
    _string(python_runtime.get("uv"), "uv runtime version")
    _string(python_runtime.get("extra"), "Python runtime extra")

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
        for artifact_index, raw_artifact in enumerate(
            _array(profile.get("implementation_artifacts", []), f"profile {identifier} artifacts")
        ):
            artifact = _object(
                raw_artifact, f"profile {identifier} artifacts[{artifact_index}]"
            )
            artifact_relative = _relative_path(
                artifact.get("path"), f"profile {identifier} artifact path"
            )
            try:
                artifact_bytes = _repository_file(
                    repository_root,
                    artifact_relative,
                    f"profile {identifier} implementation artifact",
                ).read_bytes()
            except OSError as error:
                raise GraphStandardToolingError(
                    f"profile {identifier} implementation artifact is unavailable"
                ) from error
            if sha256(artifact_bytes).hexdigest() != _digest(
                artifact.get("sha256"), f"profile {identifier} artifact digest"
            ):
                raise GraphStandardToolingError(
                    f"profile {identifier} implementation artifact drift"
                )
        if status in _RUNNABLE:
            if profile.get("suite_source_id") not in sources:
                raise GraphStandardToolingError(f"profile {identifier} has no locked suite")
            if profile.get("adapter_id") not in adapters:
                raise GraphStandardToolingError(f"profile {identifier} has no locked adapter")
            runner_relative = _relative_path(profile.get("runner"), f"profile {identifier} runner")
            runner_path = _repository_file(
                repository_root, runner_relative, f"profile {identifier} runner"
            )
            if sha256(runner_path.read_bytes()).hexdigest() != _digest(
                profile.get("runner_sha256"), f"profile {identifier} runner digest"
            ):
                raise GraphStandardToolingError(f"profile {identifier} runner digest drift")
            runner_runtime = _string(
                profile.get("runner_runtime", "node"),
                f"profile {identifier} runner runtime",
            )
            if runner_runtime not in {"node", "python"}:
                raise GraphStandardToolingError(
                    f"profile {identifier} runner runtime is unsupported"
                )
            if profile.get("runner_suite_scope", "selected_path") not in {
                "selected_path",
                "checkout_root",
            }:
                raise GraphStandardToolingError(
                    f"profile {identifier} runner suite scope is unsupported"
                )
            if profile.get("runner_suite_argument", "--suite-root") not in {
                "--suite-root",
                "--suite-checkout",
            }:
                raise GraphStandardToolingError(
                    f"profile {identifier} runner suite argument is unsupported"
                )
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
                type(value) is not int or value < 0 for value in expected.values()
            ):
                raise GraphStandardToolingError(
                    f"profile {identifier} expected counts are invalid"
                )
            pass_count_field = _string(
                profile.get("pass_count_field", "total"),
                f"profile {identifier} pass count field",
            )
            if expected.get(pass_count_field, 0) <= 0:
                raise GraphStandardToolingError(
                    f"profile {identifier} has no positive pass denominator"
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
                json.loads(
                    _repository_file(
                        repository_root,
                        receipt_relative,
                        f"qualification receipt {profile_id}",
                    ).read_bytes()
                ),
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
        pass_count_field = profile.get("pass_count_field", "total")
        expected_adapter = _adapter_receipt(locked_adapter)
        expected_runtime_receipt = _locked_runtime_receipt(lock, profile)
        if (
            receipt.get("schema_version") != RECEIPT_SCHEMA
            or receipt.get("profile_id") != profile_id
            or receipt.get("lane") != profile.get("lane")
            or receipt.get("standards") != profile.get("standard_ids")
            or result.get("status") != "PASS"
            or counts.get("failed") != 0
            or counts.get("passed") != counts.get(pass_count_field)
            or any(counts.get(name) != count for name, count in expected.items())
            or receipt.get("claim_ceiling") != profile.get("claim_ceiling")
            or adapter != expected_adapter
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
            or runtime_receipt != expected_runtime_receipt
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


def _external_environment() -> dict[str, str]:
    """Keep only process settings needed for local runtimes and HTTPS fetches."""
    allowed = {
        "CURL_CA_BUNDLE",
        "HOME",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "LANG",
        "LC_ALL",
        "NO_PROXY",
        "PATH",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_FILE",
        "TZ",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
    }
    environment = {name: value for name, value in os.environ.items() if name in allowed}
    environment.setdefault("LANG", "C.UTF-8")
    environment.setdefault("LC_ALL", "C.UTF-8")
    return environment


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

    runner = _repository_file(
        repository_root, profile["runner"], f"profile {profile_id} runner"
    )
    selected_root = (source_root / source["selected_path"]).resolve(strict=True)
    source_root_resolved = source_root.resolve(strict=True)
    try:
        selected_root.relative_to(source_root_resolved)
    except ValueError as error:
        raise GraphStandardToolingError("selected suite path escapes source checkout")
    suite_scope = (
        source_root_resolved
        if profile.get("runner_suite_scope", "selected_path") == "checkout_root"
        else selected_root
    )
    suite_argument = profile.get("runner_suite_argument", "--suite-root")
    runner_runtime = profile.get("runner_runtime", "node")

    if runner_runtime == "node":
        node = shutil.which("node")
        npm = shutil.which("npm")
        if node is None or npm is None:
            raise GraphStandardToolingError("Node.js and npm are required")
        try:
            observed_node = subprocess.run(
                [node, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            observed_npm = subprocess.run(
                [npm, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError as error:
            raise GraphStandardToolingError("Node.js or npm version probe failed") from error
        expected_runtime = _locked_runtime_receipt(lock, profile)
        if (
            observed_node != expected_runtime["node"]
            or observed_npm != expected_runtime["npm"]
        ):
            raise GraphStandardToolingError("Node.js or npm version drift")
        runtime = lock["runtime_lock"]
        package_manifest = _repository_file(
            repository_root, runtime["package_manifest"], "runtime package manifest"
        )
        package_lock = _repository_file(
            repository_root, runtime["package_lock"], "runtime package lock"
        )
        with tempfile.TemporaryDirectory(prefix="hswm-graph-standard-npm-") as temporary:
            module_root = Path(temporary)
            home = module_root / "home"
            cache = module_root / "cache"
            home.mkdir()
            cache.mkdir()
            user_config = module_root / "npm-user.ini"
            global_config = module_root / "npm-global.ini"
            user_config.touch(mode=0o600)
            global_config.touch(mode=0o600)
            shutil.copy2(package_manifest, module_root / "package.json")
            shutil.copy2(package_lock, module_root / "package-lock.json")
            environment = _external_environment()
            environment.update(
                {
                    "HOME": str(home),
                    "npm_config_audit": "false",
                    "npm_config_cache": str(cache),
                    "npm_config_fund": "false",
                    "npm_config_globalconfig": str(global_config),
                    "npm_config_ignore_scripts": "true",
                    "npm_config_registry": "https://registry.npmjs.org/",
                    "npm_config_userconfig": str(user_config),
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
                    timeout=180,
                )
            except subprocess.TimeoutExpired as error:
                raise GraphStandardToolingError(
                    "clean npm dependency installation timed out"
                ) from error
            if installed.returncode != 0:
                raise GraphStandardToolingError(
                    f"clean npm dependency installation failed: {installed.stderr[-2000:]}"
                )
            command = [
                node,
                str(runner),
                "--module-root",
                str(module_root),
                "--profile",
                profile_id,
                suite_argument,
                str(suite_scope),
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=180,
                )
            except subprocess.TimeoutExpired as error:
                raise GraphStandardToolingError(
                    "graph standard qualification timed out"
                ) from error
        runtime_receipt = expected_runtime
    else:
        uv = shutil.which("uv")
        if uv is None:
            raise GraphStandardToolingError("uv is unavailable")
        try:
            uv_output = subprocess.run(
                [uv, "--version"],
                check=True,
                env=_external_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError as error:
            raise GraphStandardToolingError("uv version probe failed") from error
        observed_uv_parts = uv_output.split()
        observed_uv = observed_uv_parts[1] if len(observed_uv_parts) >= 2 else ""
        expected_runtime = _locked_runtime_receipt(lock, profile)
        if observed_uv != expected_runtime["uv"]:
            raise GraphStandardToolingError(
                f"uv version drift: expected {expected_runtime['uv']}, observed {observed_uv}"
            )
        environment = _external_environment()
        environment.update(
            {
                "UV_DEFAULT_INDEX": "https://pypi.org/simple",
                "UV_NO_CONFIG": "1",
                "UV_NO_PYTHON_DOWNLOADS": "1",
                "UV_PROJECT": str(repository_root.resolve(strict=True)),
            }
        )
        command = [
            uv,
            "run",
            "--isolated",
            "--locked",
            "--no-python-downloads",
            "--python",
            expected_runtime["python"],
            "--extra",
            expected_runtime["extra"],
            "python",
            "-I",
            str(runner),
            "--profile",
            profile_id,
            suite_argument,
            str(suite_scope),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=repository_root,
                check=False,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=240,
            )
        except subprocess.TimeoutExpired as error:
            raise GraphStandardToolingError("graph standard qualification timed out") from error
        runtime_receipt = expected_runtime
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
    if runner_runtime == "python":
        runner_runtime_result = _object(
            result.get("runtime"), "qualification Python runtime"
        )
        if (
            runner_runtime_result.get("implementation") != "CPython"
            or runner_runtime_result.get("python") != runtime_receipt["python"]
        ):
            raise GraphStandardToolingError("qualification Python runtime drift")
    qualification_manifest = (
        source_root / profile["qualification_manifest_path"]
    ).resolve(strict=True)
    if source_root.resolve(strict=True) not in qualification_manifest.parents:
        raise GraphStandardToolingError("qualification manifest escapes source checkout")
    qualification_manifest_digest = sha256(qualification_manifest.read_bytes()).hexdigest()
    if qualification_manifest_digest != profile["qualification_manifest_sha256"] or (
        result.get("manifest_sha256") != qualification_manifest_digest
    ):
        raise GraphStandardToolingError("qualification manifest binding drift")
    observed_adapter = _object(result.get("adapter"), "qualification adapter")
    if (
        _distribution_name(str(observed_adapter.get("package")))
        != _distribution_name(adapter.get("package"))
        or observed_adapter.get("version") != adapter.get("version")
    ):
        raise GraphStandardToolingError("qualification adapter drift")
    counts = _object(result.get("counts"), "qualification counts")
    for name, expected in profile["expected"].items():
        if counts.get(name) != expected:
            raise GraphStandardToolingError(
                f"qualification count drift for {name}: {counts.get(name)} != {expected}"
            )
    pass_count_field = profile.get("pass_count_field", "total")
    if counts.get("failed") != 0 or counts.get("passed") != counts.get(pass_count_field):
        raise GraphStandardToolingError("qualification pass denominator drift")
    unsigned = {
        "adapter": _adapter_receipt(adapter),
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
        "runtime": runtime_receipt,
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
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="full HSWM checkout or extracted source distribution containing bound artifacts",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="acceptance lock path (defaults inside --repository-root)",
    )
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
        repository_root = arguments.repository_root
        manifest = arguments.manifest or (
            repository_root
            / "_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json"
        )
        lock = load_acceptance_lock(manifest)
        indexes = verify_acceptance_lock(lock, repository_root=repository_root)
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
                repository_root=repository_root,
            )
    except GraphStandardToolingError as error:
        sys.stderr.write(f"REFUSED: {error}\n")
        return 2
    sys.stdout.buffer.write(_pretty_json_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
