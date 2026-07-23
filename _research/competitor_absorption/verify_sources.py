#!/usr/bin/env python3
"""Fail-closed validation for the portable HSWM absorption source gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


RESTRICTED_LICENSES = {"NO-LICENSE", "CC-BY-NC-4.0"}
ALLOWED_STATES = {"off", "schema_only", "receipt_only"}
ALLOWED_IMPLEMENTATION_POLICIES = {
    "clean_room_reimplementation",
    "clean_room_reimplementation_vendor_audit",
    "evaluation_schema_only",
    "interface_schema_only",
    "reference_only_clean_room",
}
CANONICAL_LOCK_PATHS = {
    "repositories": "_research/competitor_absorption/source_locks/repos.lock.tsv",
    "papers": "_research/competitor_absorption/source_locks/papers.lock.tsv",
}
REPOSITORY_LOCK_COLUMNS = {"name", "upstream", "branch", "commit"}
PAPER_LOCK_COLUMNS = {
    "key",
    "title",
    "identifier",
    "pdf_url",
    "code_clone",
    "pages",
    "sha256",
    "local_pdf",
    "local_text",
}
SAFE_BASELINE_DEFAULTS = {
    "admission": "flat",
    "expansion": "gated_optional",
    "governance": "late",
    "traversal": "off",
    "fuse_weight_may_be_zero": True,
}
REQUIRED_CANDIDATE_FIELDS = {
    "id",
    "paper_keys",
    "code_clones",
    "mechanism",
    "code_refs",
    "paper_code_drift",
    "hswm_surface",
    "priority",
    "disposition",
    "deployment_default",
    "implementation_policy",
    "falsifier",
}
HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")


def _read_tsv(
    path: Path,
    key: str,
    required_columns: set[str],
) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        columns = set(reader.fieldnames or [])
        missing_columns = required_columns - columns
        if missing_columns:
            raise ValueError(f"{path}: missing columns {sorted(missing_columns)}")
        rows = list(reader)

    if not rows:
        raise ValueError(f"{path}: lock is empty")

    result: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        missing_values = sorted(
            column for column in required_columns if not (row.get(column) or "").strip()
        )
        if missing_values:
            raise ValueError(
                f"{path}:{row_number}: empty values for {missing_values}"
            )
        value = row[key]
        if value in result:
            raise ValueError(f"{path}: duplicate {key}={value}")
        result[value] = row
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def _resolve_relative(
    base: Path,
    raw_path: object,
    label: str,
    issues: list[str],
) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        issues.append(f"{label} must be a non-empty relative path")
        return None
    relative = Path(raw_path)
    if relative.is_absolute():
        issues.append(f"{label} must be relative, got {raw_path!r}")
        return None
    base = base.resolve()
    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        issues.append(f"{label} escapes its repository root: {raw_path!r}")
        return None
    return candidate


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_nonempty_string(item) for item in value)
    )


def _validate_baseline(
    root: Path,
    manifest: dict[str, Any],
    issues: list[str],
) -> None:
    baseline = manifest.get("hswm_baseline")
    if not isinstance(baseline, dict):
        issues.append("manifest hswm_baseline must be an object")
        return

    baseline_repo = _resolve_relative(
        root,
        baseline.get("repository"),
        "hswm_baseline.repository",
        issues,
    )
    baseline_commit = baseline.get("commit")
    if not isinstance(baseline_commit, str) or not HEX_40.fullmatch(baseline_commit):
        issues.append("hswm_baseline.commit must be a full 40-character SHA-1")
        baseline_commit = None

    if baseline_repo is None or not baseline_repo.is_dir():
        if baseline_repo is not None:
            issues.append(f"missing HSWM baseline repository: {baseline_repo}")
    elif baseline_commit is not None:
        try:
            head = _git(baseline_repo, "rev-parse", "--verify", "HEAD^{commit}")
            locked_commit = _git(
                baseline_repo,
                "rev-parse",
                "--verify",
                f"{baseline_commit}^{{commit}}",
            )
            _git(
                baseline_repo,
                "merge-base",
                "--is-ancestor",
                locked_commit,
                head,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            issues.append(
                "HSWM baseline ancestry failed: "
                f"{baseline_commit} is unavailable or not an ancestor of HEAD ({exc})"
            )

    contract_name = baseline.get("deployment_contract")
    if contract_name != "ABSORB_CONTRACT_v1.md":
        issues.append(
            "hswm_baseline.deployment_contract must be ABSORB_CONTRACT_v1.md"
        )
    contract_base = baseline_repo if baseline_repo is not None else root
    contract = _resolve_relative(
        contract_base,
        contract_name,
        "hswm_baseline.deployment_contract",
        issues,
    )
    if contract is not None and not contract.is_file():
        issues.append(f"missing HSWM deployment contract: {contract}")

    defaults = baseline.get("defaults")
    if not isinstance(defaults, dict):
        issues.append("hswm_baseline.defaults must be an object")
    else:
        for key, expected in SAFE_BASELINE_DEFAULTS.items():
            if defaults.get(key) != expected:
                issues.append(
                    f"unsafe baseline default {key}: {defaults.get(key)!r} != {expected!r}"
                )
    if not _nonempty_string(baseline.get("mandatory_predecessor_gate")):
        issues.append("hswm_baseline.mandatory_predecessor_gate must be non-empty")


def _validate_locks(
    root: Path,
    manifest: dict[str, Any],
    issues: list[str],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    locks = manifest.get("locks")
    if not isinstance(locks, dict):
        issues.append("manifest locks must be an object")
        locks = {}
    for kind, expected in CANONICAL_LOCK_PATHS.items():
        if locks.get(kind) != expected:
            issues.append(f"locks.{kind} must be {expected}")

    repos: dict[str, dict[str, str]] = {}
    papers: dict[str, dict[str, str]] = {}
    try:
        repos = _read_tsv(
            root / CANONICAL_LOCK_PATHS["repositories"],
            "name",
            REPOSITORY_LOCK_COLUMNS,
        )
    except (OSError, ValueError) as exc:
        issues.append(f"repository lock read failed: {exc}")
    try:
        papers = _read_tsv(
            root / CANONICAL_LOCK_PATHS["papers"],
            "key",
            PAPER_LOCK_COLUMNS,
        )
    except (OSError, ValueError) as exc:
        issues.append(f"paper lock read failed: {exc}")

    for name, row in repos.items():
        if not HEX_40.fullmatch(row["commit"]):
            issues.append(f"repository lock has invalid commit for {name}")
    for key, row in papers.items():
        if not HEX_64.fullmatch(row["sha256"]):
            issues.append(f"paper lock has invalid sha256 for {key}")
        try:
            if int(row["pages"]) <= 0:
                raise ValueError
        except ValueError:
            issues.append(f"paper lock has invalid page count for {key}")
        for column in ("local_pdf", "local_text"):
            relative = Path(row[column])
            if relative.is_absolute() or ".." in relative.parts:
                issues.append(f"paper lock {key}.{column} must be bundle-relative")
        for clone in row["code_clone"].split(","):
            if clone not in repos:
                issues.append(f"paper lock {key} references unknown code clone {clone}")
    return repos, papers


def _validate_policies_and_candidates(
    manifest: dict[str, Any],
    repos: dict[str, dict[str, str]],
    papers: dict[str, dict[str, str]],
    issues: list[str],
) -> None:
    sources = manifest.get("code_sources")
    if not isinstance(sources, dict):
        issues.append("manifest code_sources must be an object")
        sources = {}
    if repos and set(sources) != set(repos):
        issues.append(
            "code_sources coverage mismatch: "
            f"missing={sorted(set(repos) - set(sources))}, "
            f"extra={sorted(set(sources) - set(repos))}"
        )

    for name, policy in sources.items():
        if not isinstance(policy, dict):
            issues.append(f"code source policy must be an object: {name}")
            continue
        implementation_policy = policy.get("implementation_policy")
        if implementation_policy not in ALLOWED_IMPLEMENTATION_POLICIES:
            issues.append(f"unknown implementation policy for {name}")
        if not _nonempty_string(policy.get("license")):
            issues.append(f"missing license policy for {name}")
        if not isinstance(policy.get("notice_required_if_reused"), bool):
            issues.append(f"notice policy must be boolean for {name}")
        if (
            policy.get("license") in RESTRICTED_LICENSES
            and implementation_policy != "reference_only_clean_room"
        ):
            issues.append(f"restricted source lacks clean-room policy: {name}")

    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        issues.append("manifest has no candidates")
        candidates = []

    seen_ids: set[str] = set()
    used_repos: set[str] = set()
    used_papers: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            issues.append(f"candidate[{index}] must be an object")
            continue
        label_value = candidate.get("id")
        label = label_value if _nonempty_string(label_value) else f"candidate[{index}]"
        missing = REQUIRED_CANDIDATE_FIELDS - set(candidate)
        if missing:
            issues.append(f"{label}: missing fields {sorted(missing)}")
            continue
        if not _nonempty_string(label_value):
            issues.append(f"candidate[{index}]: id must be non-empty")
        elif label in seen_ids:
            issues.append(f"duplicate candidate id: {label}")
        seen_ids.add(label)

        if candidate.get("deployment_default") not in ALLOWED_STATES:
            issues.append(f"{label}: forbidden deployment state")
        for field in ("mechanism", "hswm_surface", "falsifier"):
            if not _nonempty_string(candidate.get(field)):
                issues.append(f"{label}: {field} must be non-empty")
        for field in ("priority", "disposition"):
            if not _nonempty_string(candidate.get(field)):
                issues.append(f"{label}: {field} must be non-empty")
        if not _string_list(candidate.get("paper_code_drift")):
            issues.append(f"{label}: paper_code_drift must be a non-empty string list")

        paper_keys = candidate.get("paper_keys")
        if not _string_list(paper_keys):
            issues.append(f"{label}: paper_keys must be a non-empty string list")
            paper_keys = []
        for key in paper_keys:
            used_papers.add(key)
            if key not in papers:
                issues.append(f"{label}: unknown paper key {key}")

        code_clones = candidate.get("code_clones")
        if not _string_list(code_clones):
            issues.append(f"{label}: code_clones must be a non-empty string list")
            code_clones = []
        candidate_policy = candidate.get("implementation_policy")
        if candidate_policy not in ALLOWED_IMPLEMENTATION_POLICIES:
            issues.append(f"{label}: unknown implementation policy")
        for clone in code_clones:
            used_repos.add(clone)
            if clone not in repos:
                issues.append(f"{label}: unknown code clone {clone}")
                continue
            source_policy = sources.get(clone)
            if not isinstance(source_policy, dict):
                continue
            if candidate_policy != source_policy.get("implementation_policy"):
                issues.append(f"{label}: implementation policy mismatch for {clone}")
            if (
                source_policy.get("license") in RESTRICTED_LICENSES
                and candidate_policy != "reference_only_clean_room"
            ):
                issues.append(f"{label}: restricted clone is not clean-room only")

        code_refs = candidate.get("code_refs")
        if not isinstance(code_refs, list) or not code_refs:
            issues.append(f"{label}: code_refs must be a non-empty list")
            code_refs = []
        for ref_index, ref in enumerate(code_refs):
            ref_label = f"{label}: code_refs[{ref_index}]"
            if not isinstance(ref, dict):
                issues.append(f"{ref_label} must be an object")
                continue
            clone = ref.get("clone")
            relpath = ref.get("path")
            line = ref.get("line")
            anchor = ref.get("anchor")
            if clone not in code_clones:
                issues.append(f"{label}: reference clone {clone!r} not bound")
            if not _nonempty_string(relpath):
                issues.append(f"{ref_label}.path must be non-empty")
            else:
                path = Path(relpath)
                if path.is_absolute() or ".." in path.parts:
                    issues.append(f"{ref_label}.path must be clone-relative")
            if not isinstance(line, int) or isinstance(line, bool) or line < 1:
                issues.append(f"{ref_label}.line must be a positive integer")
            if not _nonempty_string(anchor):
                issues.append(f"{ref_label}.anchor must be non-empty")

    if repos and used_repos != set(repos):
        issues.append(
            "candidate repository coverage mismatch: "
            f"missing={sorted(set(repos) - used_repos)}"
        )
    if papers and used_papers != set(papers):
        issues.append(
            "candidate paper coverage mismatch: "
            f"missing={sorted(set(papers) - used_papers)}"
        )

    prohibitions = manifest.get("prohibitions")
    if not _string_list(prohibitions):
        issues.append("manifest prohibitions must be a non-empty string list")


def _validate_bundle(
    bundle_root: Path,
    manifest: dict[str, Any],
    repos: dict[str, dict[str, str]],
    papers: dict[str, dict[str, str]],
    issues: list[str],
) -> None:
    bundle_root = bundle_root.resolve()
    if not bundle_root.is_dir():
        issues.append(f"explicit bundle root is missing or not a directory: {bundle_root}")
        return

    for name, row in sorted(repos.items()):
        repo = bundle_root / name
        if not repo.is_dir():
            issues.append(f"missing code clone: {name}")
            continue
        try:
            head = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
            dirty = _git(repo, "status", "--porcelain")
        except (OSError, subprocess.CalledProcessError) as exc:
            issues.append(f"git validation failed for {name}: {exc}")
            continue
        if head != row["commit"]:
            issues.append(f"commit mismatch {name}: {head} != {row['commit']}")
        if dirty:
            issues.append(f"dirty source clone: {name}")

    papers_root = bundle_root / "papers"
    for key, row in sorted(papers.items()):
        pdf = papers_root / row["local_pdf"]
        text = papers_root / row["local_text"]
        if not pdf.is_file():
            issues.append(f"missing PDF: {key}")
        elif _sha256(pdf) != row["sha256"]:
            issues.append(f"PDF hash mismatch: {key}")
        if not text.is_file() or text.stat().st_size < 1000:
            issues.append(f"missing or implausibly small extracted text: {key}")

    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        return
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        label = candidate.get("id", f"candidate[{index}]")
        refs = candidate.get("code_refs")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            clone = ref.get("clone")
            relpath = ref.get("path")
            line = ref.get("line")
            anchor = ref.get("anchor")
            if (
                not _nonempty_string(clone)
                or clone not in repos
                or not _nonempty_string(relpath)
                or Path(relpath).is_absolute()
                or ".." in Path(relpath).parts
            ):
                continue
            target = bundle_root / clone / relpath
            if not target.is_file():
                issues.append(f"{label}: missing code reference {clone}/{relpath}")
                continue
            try:
                lines = target.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                issues.append(f"{label}: non-UTF8 code reference {clone}/{relpath}")
                continue
            if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= len(lines):
                issues.append(f"{label}: invalid line anchor {clone}/{relpath}:{line}")
            elif not _nonempty_string(anchor) or anchor not in lines[line - 1]:
                issues.append(
                    f"{label}: anchor drift {clone}/{relpath}:{line} lacks {anchor!r}"
                )


def validate(
    root: Path,
    manifest_path: Path,
    bundle_root: Path | None = None,
) -> list[str]:
    """Validate the portable gate and, when requested, the external source bundle."""

    issues: list[str] = []
    root = root.resolve()
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"manifest read failed: {exc}"]
    if not isinstance(manifest_payload, dict):
        return ["manifest root must be an object"]
    manifest: dict[str, Any] = manifest_payload

    if manifest.get("schema") != "hswm-paper-code-absorption/v1":
        issues.append("manifest schema mismatch")
    if manifest.get("status") != "source_locked_not_activated":
        issues.append("manifest must remain source_locked_not_activated")

    _validate_baseline(root, manifest, issues)
    repos, papers = _validate_locks(root, manifest, issues)
    _validate_policies_and_candidates(manifest, repos, papers, issues)
    if bundle_root is not None:
        _validate_bundle(bundle_root, manifest, repos, papers, issues)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the portable HSWM source gate. External clones, PDFs, and "
            "line anchors are checked only when --bundle-root is supplied."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="HSWM repository checkout (default: checkout containing this script)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("manifest.v1.json"),
    )
    parser.add_argument(
        "--bundle-root",
        type=Path,
        help="external HSWM_COMPETITORS bundle; explicit missing paths fail closed",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    bundle_root = (
        args.bundle_root.expanduser().resolve()
        if args.bundle_root is not None
        else None
    )
    issues = validate(root, manifest_path, bundle_root)
    payload: dict[str, Any] = {
        "schema": "hswm-paper-code-source-verification/v1",
        "mode": "full_bundle" if bundle_root is not None else "portable_gate",
        "ok": not issues,
        "issues": issues,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
    elif bundle_root is None:
        print(
            "PASS: manifest, source locks, policies, deployment contract, and "
            "baseline ancestry are valid (external bundle not requested)"
        )
    else:
        print(
            "PASS: portable gate plus 11 code clones, 11 papers, and all code "
            "anchors are source-bound and inactive"
        )
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
