#!/usr/bin/env python3
"""Fail-closed validation for the HSWM paper/code absorption source bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


RESTRICTED_LICENSES = {"NO-LICENSE", "CC-BY-NC-4.0"}
ALLOWED_STATES = {
    "off",
    "schema_only",
    "receipt_only",
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


def _read_tsv(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value:
            raise ValueError(f"{path}: missing key column {key!r}")
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


def validate(root: Path, manifest_path: Path) -> list[str]:
    issues: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "hswm-paper-code-absorption/v1":
        issues.append("manifest schema mismatch")
    if manifest.get("status") != "source_locked_not_activated":
        issues.append("manifest must remain source_locked_not_activated")

    baseline = manifest.get("hswm_baseline", {})
    baseline_repo = Path(baseline.get("repository", ""))
    baseline_commit = baseline.get("commit", "")
    if not baseline_repo.is_dir() or not baseline_commit:
        issues.append("missing HSWM baseline repository or commit")
    else:
        try:
            head = _git(baseline_repo, "rev-parse", "HEAD")
        except (OSError, subprocess.CalledProcessError) as exc:
            issues.append(f"HSWM baseline validation failed: {exc}")
        else:
            if not head.startswith(baseline_commit):
                issues.append(
                    f"HSWM baseline drift: {head} does not start with {baseline_commit}"
                )
        contract = baseline_repo / baseline.get("deployment_contract", "")
        if not contract.is_file():
            issues.append(f"missing HSWM deployment contract: {contract}")

    locks = manifest.get("locks", {})
    try:
        repos = _read_tsv(root / locks["repositories"], "name")
        papers = _read_tsv(root / locks["papers"], "key")
    except (KeyError, OSError, ValueError) as exc:
        return [f"lock read failed: {exc}"]

    bundle = root / "GIT" / "HSWM_COMPETITORS"
    for name, row in sorted(repos.items()):
        repo = bundle / name
        if not repo.is_dir():
            issues.append(f"missing code clone: {name}")
            continue
        try:
            head = _git(repo, "rev-parse", "HEAD")
            dirty = _git(repo, "status", "--porcelain")
        except (OSError, subprocess.CalledProcessError) as exc:
            issues.append(f"git validation failed for {name}: {exc}")
            continue
        if head != row["commit"]:
            issues.append(f"commit mismatch {name}: {head} != {row['commit']}")
        if dirty:
            issues.append(f"dirty source clone: {name}")

    papers_root = bundle / "papers"
    for key, row in sorted(papers.items()):
        pdf = papers_root / row["local_pdf"]
        text = papers_root / row["local_text"]
        if not pdf.is_file():
            issues.append(f"missing PDF: {key}")
        elif _sha256(pdf) != row["sha256"]:
            issues.append(f"PDF hash mismatch: {key}")
        if not text.is_file() or text.stat().st_size < 1000:
            issues.append(f"missing or implausibly small extracted text: {key}")

    sources = manifest.get("code_sources", {})
    if set(sources) != set(repos):
        issues.append(
            "code_sources coverage mismatch: "
            f"missing={sorted(set(repos) - set(sources))}, "
            f"extra={sorted(set(sources) - set(repos))}"
        )
    for name, policy in sources.items():
        if policy.get("license") in RESTRICTED_LICENSES and policy.get(
            "implementation_policy"
        ) != "reference_only_clean_room":
            issues.append(f"restricted source lacks clean-room policy: {name}")

    seen_ids: set[str] = set()
    used_repos: set[str] = set()
    used_papers: set[str] = set()
    candidates = manifest.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        issues.append("manifest has no candidates")
        candidates = []

    for index, candidate in enumerate(candidates):
        label = candidate.get("id", f"candidate[{index}]")
        missing = REQUIRED_CANDIDATE_FIELDS - set(candidate)
        if missing:
            issues.append(f"{label}: missing fields {sorted(missing)}")
            continue
        if label in seen_ids:
            issues.append(f"duplicate candidate id: {label}")
        seen_ids.add(label)
        if candidate["deployment_default"] not in ALLOWED_STATES:
            issues.append(f"{label}: forbidden deployment state")
        if not candidate["mechanism"].strip() or not candidate["falsifier"].strip():
            issues.append(f"{label}: empty mechanism or falsifier")
        if not candidate["hswm_surface"].strip():
            issues.append(f"{label}: empty HSWM surface")

        for key in candidate["paper_keys"]:
            used_papers.add(key)
            if key not in papers:
                issues.append(f"{label}: unknown paper key {key}")
        for clone in candidate["code_clones"]:
            used_repos.add(clone)
            if clone not in repos:
                issues.append(f"{label}: unknown code clone {clone}")
                continue
            source_policy = sources.get(clone, {})
            if source_policy.get("license") in RESTRICTED_LICENSES and candidate[
                "implementation_policy"
            ] != "reference_only_clean_room":
                issues.append(f"{label}: restricted clone is not clean-room only")

        for ref in candidate["code_refs"]:
            clone = ref.get("clone", "")
            relpath = ref.get("path", "")
            line = ref.get("line")
            anchor = ref.get("anchor", "")
            if clone not in candidate["code_clones"]:
                issues.append(f"{label}: reference clone {clone!r} not bound")
                continue
            target = bundle / clone / relpath
            if not target.is_file():
                issues.append(f"{label}: missing code reference {clone}/{relpath}")
                continue
            try:
                lines = target.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                issues.append(f"{label}: non-UTF8 code reference {clone}/{relpath}")
                continue
            if not isinstance(line, int) or not 1 <= line <= len(lines):
                issues.append(f"{label}: invalid line anchor {clone}/{relpath}:{line}")
            elif anchor not in lines[line - 1]:
                issues.append(
                    f"{label}: anchor drift {clone}/{relpath}:{line} lacks {anchor!r}"
                )

    if used_repos != set(repos):
        issues.append(
            f"candidate repository coverage mismatch: missing={sorted(set(repos) - used_repos)}"
        )
    if used_papers != set(papers):
        issues.append(
            f"candidate paper coverage mismatch: missing={sorted(set(papers) - used_papers)}"
        )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="SYMPOSIUM repository root",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("manifest.v1.json"),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    issues = validate(args.root.resolve(), args.manifest.resolve())
    payload: dict[str, Any] = {
        "schema": "hswm-paper-code-source-verification/v1",
        "ok": not issues,
        "issues": issues,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("PASS: 11 code clones, 11 papers, and 11 absorption candidates are source-bound and inactive")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
