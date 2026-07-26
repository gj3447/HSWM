#!/usr/bin/env python3
"""Verify the HSWM active-programme Longinus chain without making verdicts.

This verifier checks reference integrity only: roots, symbols, line ranges,
hashes, predecessor lineage, the research ledger, and the sync authority split.
It deliberately has no Neo4j or LakatoTree write path.
"""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


class BindingError(RuntimeError):
    """Raised when a seven-layer reference chain is incomplete or drifted."""


SCRIPT_PATH = Path(__file__).resolve()
HSWM_ROOT = SCRIPT_PATH.parents[2]
SYMPOSIUM_ROOT = HSWM_ROOT.parents[1]
MANIFEST_PATH = HSWM_ROOT / "LONGINUS_HSWM_RESEARCH_PROGRAM_BINDING_2026-07-26.json"
ROOTS = {"HSWM": HSWM_ROOT, "SYMPOSIUM": SYMPOSIUM_ROOT}
CHAIN_FIELDS = (
    "kg_node",
    "contract_binding",
    "qualified_symbol",
    "file_line",
    "line_range",
    "sha256",
    "crate_script",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def safe_path(root_name: str, relative: str) -> Path:
    if root_name not in ROOTS:
        raise BindingError(f"unknown source_root: {root_name}")
    candidate = (ROOTS[root_name] / relative).resolve()
    root = ROOTS[root_name].resolve()
    if candidate != root and root not in candidate.parents:
        raise BindingError(f"path escapes {root_name}: {relative}")
    return candidate


def verify_git_provenance(programme: dict[str, Any], root: Path = HSWM_ROOT) -> str:
    """Verify commit ancestry locally or the immutable sync envelope on Proxmox.

    Snapshot sync intentionally excludes ``.git``.  Treating that absence as a
    failed Git ancestry check makes the registered verifier unreplayable on the
    adjudication host.  The fallback is allowed only inside the exact generated
    GIT/HSWM snapshot path and requires a verified, non-stale sync receipt; the
    per-file Longinus hashes remain the content identity check.
    """

    base_commit = programme["active_code_root"]["git_base_commit"]
    if (root / ".git").exists():
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", base_commit, "HEAD"],
            cwd=root,
            check=False,
        )
        if ancestor.returncode != 0:
            raise BindingError(f"git base commit is not an ancestor of HEAD: {base_commit}")
        return "GIT_ANCESTOR"

    suffix = "/COMPAT_SOURCES/CDROOT/SYMPOSIUM/GIT/HSWM"
    if not root.as_posix().endswith(suffix):
        raise BindingError(f"git metadata absent outside an approved snapshot root: {root}")
    snapshot = next(
        (
            parent
            for parent in (root, *root.parents)
            if parent.name.startswith("research-")
            and (parent / "RUNTIME_EVIDENCE/SYNC_RECEIPT.json").is_file()
        ),
        None,
    )
    if snapshot is None:
        raise BindingError("snapshot Git fallback has no sync receipt")
    receipt = json.loads(
        (snapshot / "RUNTIME_EVIDENCE/SYNC_RECEIPT.json").read_text(encoding="utf-8")
    )
    if receipt.get("verified") is not True or receipt.get("snapshot") != str(snapshot):
        raise BindingError("snapshot sync receipt is not exact and verified")
    if "COMPAT_SOURCES/CDROOT/SYMPOSIUM/GIT" in receipt.get("stale_mappings", []):
        raise BindingError("GIT snapshot mapping is explicitly stale")
    return "SNAPSHOT_CONTENT_HASH_PLUS_SYNC_RECEIPT"


def python_symbol_range(path: Path, symbol: str) -> tuple[int, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == symbol
    ]
    if len(matches) != 1:
        raise BindingError(f"expected one Python symbol {symbol}, found {len(matches)}")
    node = matches[0]
    if node.end_lineno is None:
        raise BindingError(f"Python AST has no end line for {symbol}")
    return node.lineno, node.end_lineno


def validate_binding(binding: dict[str, Any], crate: dict[str, Any]) -> None:
    source_id = binding.get("sourceId", "<missing>")
    chain = binding.get("chain")
    if not isinstance(chain, dict) or tuple(chain) != CHAIN_FIELDS:
        raise BindingError(f"{source_id}: incomplete or reordered seven-layer chain")
    if chain["kg_node"] != "hswm-ordered-research-harness-20260724":
        raise BindingError(f"{source_id}: wrong KG anchor")
    if chain["contract_binding"] != "hswm-ordered-research-gates-20260724":
        raise BindingError(f"{source_id}: wrong contract anchor")

    path = safe_path(binding["source_root"], binding["source_path"])
    if not path.is_file():
        raise BindingError(f"{source_id}: missing file {path}")
    actual_sha = sha256(path)
    if actual_sha != binding["sha256"] or actual_sha != chain["sha256"]:
        raise BindingError(
            f"{source_id}: SHA drift expected={binding['sha256']} actual={actual_sha}"
        )
    actual_lines = line_count(path)
    if actual_lines != binding["line_count"]:
        raise BindingError(
            f"{source_id}: line-count drift expected={binding['line_count']} "
            f"actual={actual_lines}"
        )

    start_text, end_text = binding["line_range"].split("-", 1)
    start, end = int(start_text), int(end_text)
    if chain["file_line"] != start or chain["line_range"] != binding["line_range"]:
        raise BindingError(f"{source_id}: FILE_LINE/LINE_RANGE mismatch")
    if not (1 <= start <= end <= actual_lines):
        raise BindingError(f"{source_id}: line range outside file")
    if chain["qualified_symbol"] != binding["qualified_symbol"]:
        raise BindingError(f"{source_id}: CODE_SYMBOL mismatch")

    witness = binding["witness"]
    method = witness["method"]
    if method == "PYTHON_AST":
        observed = python_symbol_range(path, witness["symbol"])
        if observed != (start, end):
            raise BindingError(
                f"{source_id}: AST range drift expected={(start, end)} actual={observed}"
            )
    elif method == "LEAN_DECLARATION":
        lines = path.read_text(encoding="utf-8").splitlines()
        marker = witness["marker"]
        if marker not in lines[start - 1]:
            raise BindingError(f"{source_id}: Lean declaration marker drift")
    elif method == "SHELL_CONTRACT":
        text = path.read_text(encoding="utf-8")
        for token in witness["must_contain"]:
            if token not in text:
                raise BindingError(f"{source_id}: missing shell contract token {token!r}")
        for token in witness["must_not_contain"]:
            if token in text:
                raise BindingError(f"{source_id}: forbidden shell contract token {token!r}")
    elif method not in {"WHOLE_FILE", "JSON_ARTIFACT", "MARKDOWN_ARTIFACT"}:
        raise BindingError(f"{source_id}: unsupported witness method {method}")

    crate_path = safe_path(crate["source_root"], crate["path"])
    if sha256(crate_path) != crate["sha256"]:
        raise BindingError(f"{source_id}: CRATE_SCRIPT hash drift")
    if chain["crate_script"] != crate["path"]:
        raise BindingError(f"{source_id}: CRATE_SCRIPT path mismatch")
    if binding["claim_boundary"] != "REFERENCE_INTEGRITY_ONLY_NO_SCIENTIFIC_VERDICT":
        raise BindingError(f"{source_id}: unsafe claim boundary")


def validate_manifest(manifest: dict[str, Any], *, inject_negative: bool = True) -> dict[str, Any]:
    authority = manifest["authority"]
    if authority != {
        "kg_write_state": "PROPOSED_NOT_WRITTEN",
        "lakatotree_write_state": "READBACK_ONLY",
        "scientific_status": "UNJUDGED",
        "meaning_binding_state": "PROPOSED",
    }:
        raise BindingError("authority block is not fail-closed")

    programme = manifest["programme"]
    if programme["relationship"] != "HAS_CONTRACT":
        raise BindingError("programme contract relationship drift")
    provenance_mode = verify_git_provenance(programme)

    predecessors = manifest["predecessor_manifests"]
    if len(predecessors) < 3:
        raise BindingError("predecessor manifest lineage is incomplete")
    for predecessor in predecessors:
        path = safe_path(predecessor["source_root"], predecessor["path"])
        if sha256(path) != predecessor["sha256"]:
            raise BindingError(f"predecessor drift not recorded exactly: {path}")
        if predecessor["relation"] != "PREDECESSOR_PRESERVED":
            raise BindingError("predecessor relation must be non-destructive")

    bindings = manifest["bindings"]
    crate = manifest["crate_script"]
    source_ids = [binding["sourceId"] for binding in bindings]
    if len(source_ids) != len(set(source_ids)):
        raise BindingError("duplicate sourceId")
    for binding in bindings:
        validate_binding(binding, crate)

    required_gap_ids = {gap["gap_id"] for gap in manifest["required_gaps"]}
    expected_gaps = {
        "semantic-weight-metric-contract",
        "operator-W-causal-mediation",
        "topology-causal-mediation",
        "weight-only-agent-transfer",
        "larger-ai-baselines-and-retention",
        "multi-agent-transfer-harness",
    }
    if required_gap_ids != expected_gaps:
        raise BindingError(
            f"required-gap set drift expected={sorted(expected_gaps)} "
            f"actual={sorted(required_gap_ids)}"
        )
    if any(gap["status"] not in {"MISSING_REQUIRED", "OPEN_UNJUDGED"} for gap in manifest["required_gaps"]):
        raise BindingError("required gap was silently promoted")

    negative_caught = False
    if inject_negative:
        damaged = deepcopy(bindings[0])
        damaged["sha256"] = "0" * 64
        damaged["chain"]["sha256"] = "0" * 64
        try:
            validate_binding(damaged, crate)
        except BindingError:
            negative_caught = True
        if not negative_caught:
            raise BindingError("injected SHA drift was not rejected")

    return {
        "schema": "longinus-hswm-active-programme-verification/v1",
        "status": "PASS",
        "binding_id": manifest["binding_id"],
        "bindings_verified": len(bindings),
        "predecessors_verified": len(predecessors),
        "required_gaps_preserved": len(required_gap_ids),
        "injected_negative_caught": negative_caught,
        "git_provenance_mode": provenance_mode,
        "scientific_status": "UNJUDGED",
    }


def main() -> int:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        receipt = validate_manifest(manifest)
        ledger = subprocess.run(
            [sys.executable, "scripts/validate_hswm_research_ledger.py"],
            cwd=HSWM_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if ledger.returncode != 0:
            raise BindingError(f"research ledger validation failed: {ledger.stderr.strip()}")
        receipt["ledger_validation"] = json.loads(ledger.stdout)
    except (BindingError, KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
