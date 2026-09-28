#!/usr/bin/env python3
"""Publish the source-bound 2026-09-28 whole-system Lean round.

This builder is intentionally a local publication snapshot: it validates exact
source hashes against three already-produced verification reports, then writes
a verification projection, a content-addressed receipt, and a development KG
bundle.  The Korean research note is authored separately and must already
exist.  This tool never reruns Lean/tests, connects to a graph server, or
claims LLM efficacy.  Run only from a final, reviewed worktree:

    python3 _research/whole_system_lean_round_v1/build_publication.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
DATE = "2026-09-28"
DOC = Path("docs/research/HSWM_WHOLE_SYSTEM_LEAN_ROUND_2026-09-28.md")
VERIFY = Path("_research/whole_system_lean_round_v1/verification.v1.json")
KG = Path("ontology/development/HSWM_WHOLE_SYSTEM_LEAN_ROUND_2026-09-28.v1.json")
EVIDENCE_DIR = Path("evidence/hswm_whole_system_lean_round_2026-09-28")
CORE_REPORT = Path("_research/whole_system_lean_round_v1/core-lean-verification.v1.json")
STAT_REPORT = Path("_research/whole_system_lean_round_v1/statistical-lean-verification.v1.json")
RUNTIME_REPORT = Path("_research/whole_system_lean_round_v1/runtime-verification.v1.json")
CLAIM_CEILING = (
    "THREE_BOUNDED_FORMAL_AND_ADAPTER_RESULTS_NOT_FULL_P1_P2_P3_NOT_LLM_EFFICACY_"
    "NOT_CHRONOLOGY_NOT_FULL_HSWM_NOT_P4_OR_P5"
)

# The three newly targeted Lean modules, the two P1 adapters, their decoder,
# focused test, both Lake environments, and the pre-existing statistical
# aggregate/auditor that AdaptiveRounds reuses.
SOURCE_PATHS = (
    "_research/whole_system_lean_round_v1/build_publication.py",
    "formal/HSWMSemanticLifecycleRefinement.lean",
    "formal/HSWMSemanticReadLocality.lean",
    "formal/statistical-learning/HSWMStatisticalLearning/AdaptiveRounds.lean",
    "src/hswm/effect-runtime/src/semantic-lifecycle-refinement.ts",
    "src/hswm/effect-runtime/src/semantic-lifecycle-refinement-process.ts",
    "formal/HSWMSemanticLifecycleCli.lean",
    "tests/effect-runtime/semantic-lifecycle-refinement.test.ts",
    "formal/lakefile.toml",
    "formal/lake-manifest.json",
    "formal/lean-toolchain",
    "formal/statistical-learning/lakefile.toml",
    "formal/statistical-learning/lake-manifest.json",
    "formal/statistical-learning/lean-toolchain",
    "formal/statistical-learning/HSWMStatisticalLearning.lean",
    "src/hswm/effect-runtime/src/statistical-learning-proof-process.ts",
    "src/hswm/effect-runtime/src/semantic-philosophy-proof-process.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-semantic-selected-state.ts",
    "docs/canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md",
    "docs/canon/USER_PRIMARY_HSWM_CROSS_LAYER_MAP_2026-09-27.md",
    "docs/canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md",
    "docs/operations/artifacts/hswm_whole_system_lean_targets_2026-09-28/source-map.v1.json",
    "_research/statistical_learning_proof_v1/lean-verification.v1.json",
)
REQUIRED_REPORTED_LEAN = {
    "formal/HSWMSemanticLifecycleRefinement.lean",
    "formal/HSWMSemanticReadLocality.lean",
    "formal/statistical-learning/HSWMStatisticalLearning/AdaptiveRounds.lean",
}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in SOURCE_PATHS:
        path = REPO / relative
        if not path.is_file():
            raise RuntimeError(f"required source is absent: {relative}")
        raw = path.read_bytes()
        records.append({"path": relative, "sha256": sha256(raw), "byte_length": len(raw)})
    return records


def require_new(path: Path) -> None:
    if (REPO / path).exists():
        raise RuntimeError(f"publication target already exists: {path}")


def write_new(relative: Path, raw: bytes) -> None:
    path = REPO / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"refusing to overwrite: {relative}")
    path.write_bytes(raw)


def read_json_report(relative: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = REPO / relative
    if not path.is_file():
        raise RuntimeError(f"required verification report is absent: {relative}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"verification report is not JSON: {relative}: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"verification report is not an object: {relative}")
    return value, {"path": str(relative), "sha256": sha256(raw), "byte_length": len(raw)}


def report_sources(report: dict[str, Any], relative: Path) -> dict[str, str]:
    rows = report.get("source_records")
    if not isinstance(rows, list):
        raise RuntimeError(f"verification report lacks source_records: {relative}")
    mapped: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise RuntimeError(f"invalid source_records entry: {relative}")
        path, digest = row["path"], row["sha256"]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise RuntimeError(f"invalid source hash in {relative}: {path}")
        if path in mapped and mapped[path] != digest:
            raise RuntimeError(f"conflicting source hash in {relative}: {path}")
        mapped[path] = digest
    return mapped


def verify_report_source_hashes(report: dict[str, Any], relative: Path) -> dict[str, str]:
    mapped = report_sources(report, relative)
    for source, digest in mapped.items():
        path = REPO / source
        if not path.is_file():
            raise RuntimeError(f"report references absent source: {relative}: {source}")
        if sha256(path.read_bytes()) != digest:
            raise RuntimeError(f"report source hash drift: {relative}: {source}")
    return mapped


def count(report: dict[str, Any], plural: str, singular: str) -> int:
    value = report.get(plural, report.get(f"{singular}_count"))
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise RuntimeError(f"runtime report must expose {plural} or {singular}_count")


def validate_runtime_report(report: dict[str, Any]) -> None:
    if count(report, "tests", "test") < 3:
        raise RuntimeError("runtime report must include the 3 focused runtime tests")
    if count(report, "mutations", "mutation") != 22:
        raise RuntimeError("runtime report must record exactly 22 mutation cases")
    commands = report.get("commands")
    if not isinstance(commands, list) or not commands:
        raise RuntimeError("runtime report must retain the commands it ran")


def node(uid: str, name: str, role: str, description: str, status: str) -> dict[str, Any]:
    return {
        "uid": uid,
        "labels": ["AbstractNode" if role == "BOUNDED_FORMAL_RESULT" else "Concept"],
        "properties": {
            "name": name,
            "description": description,
            "standard_graph_role": role,
            "authority_class": "SECONDARY_AI",
            "ontology_authority_class_v1": "SECONDARY_AI",
            "ontology_record_lifecycle_v1": "ACTIVE",
            "ontology_sensitivity_v1": "NORMAL",
            "ontology_review_required_v1": True,
            "responsibility_owner": "hswm:research:whole-system-lean-round",
            "status": status,
            "claim_boundary": CLAIM_CEILING,
            "projection_nonclaim": "NOT_RUNTIME_STATE_NOT_CANONICAL_LEARNING_NOT_WORLD_TRUTH",
        },
    }


def bundle(records: list[dict[str, Any]], evidence_path: str, evidence_sha: str,
           verification_sha: str, doc_sha: str, reports: list[dict[str, Any]]) -> dict[str, Any]:
    root = "sym:AbstractNode:hswm-whole-system-lean-round-2026-09-28"
    p1 = "sym:Concept:hswm-whole-system-lean-round-2026-09-28-p1"
    p2 = "sym:Concept:hswm-whole-system-lean-round-2026-09-28-p2"
    p3 = "sym:Concept:hswm-whole-system-lean-round-2026-09-28-p3"
    assumptions = "sym:Concept:hswm-whole-system-lean-round-2026-09-28-assumptions"
    nodes = [
        node(root, "HSWM whole-system Lean round", "BOUNDED_FORMAL_RESULT",
             "Source-bound projection of three bounded implementation results.", "KERNEL_AND_ADAPTER_CHECKED"),
        node(p1, "P1 decoded semantic lifecycle", "FORMAL_RUNTIME_CORRESPONDENCE",
             "Byte-checked adapter projects a decoded structural witness to Lean.", "ADAPTER_TESTED_DECODED_STRUCTURAL_WITNESS"),
        node(p2, "P2 read-set locality", "FORMAL_LOCALITY_RESULT",
             "Bounded locality proof with missing exception/role counterexamples; planner, expanded prior evidence, and full request locality remain open.", "FORMAL_MODEL_ONLY"),
        node(p3, "P3 finite-history selection", "FORMAL_STATISTICAL_RESULT",
             "Finite history-indexed fresh kernels, finite mixtures, and alpha spending.", "KERNEL_CHECKED_UNDER_DECLARED_PREMISES"),
        node(assumptions, "Unaddressed boundaries", "FORMAL_ASSUMPTION_BOUNDARY",
             "No full P1/P2/P3 closure, efficacy, authenticated chronology, P4, or P5 result.", "OPEN"),
    ]
    source_hashes = {row["path"]: row["sha256"] for row in records}
    for item, source in zip(nodes[1:4], (
        "formal/HSWMSemanticLifecycleRefinement.lean",
        "formal/HSWMSemanticReadLocality.lean",
        "formal/statistical-learning/HSWMStatisticalLearning/AdaptiveRounds.lean",
    )):
        item["properties"].update(source_path=source, source_sha256=source_hashes[source])
    relation_scope = "SOURCE_BOUND_FORMAL_RESEARCH_NAVIGATION_NOT_REAL_LLM_EFFICACY"
    relations = [
        {"from_uid": root, "type": "HAS_COMPONENT", "to_uid": target, "authority_class": "SECONDARY_AI", "status": "ACTIVE", "scope": relation_scope}
        for target in (p1, p2, p3, assumptions)
    ]
    relations.extend({"from_uid": target, "type": "HAS_ASSUMPTION_BOUNDARY", "to_uid": assumptions,
                      "authority_class": "SECONDARY_AI", "status": "ACTIVE", "scope": relation_scope}
                     for target in (p1, p2, p3))
    return {
        "schema_version": "hswm-whole-system-lean-round-kg/v1",
        "bundle_uid": root,
        "status": "SOURCE_BOUND_BOUNDED_FORMAL_RESULT",
        "authority_boundary": "All interpretation is SECONDARY_AI. Formal premises and adapter checks are not empirical evidence.",
        "nonclaim": CLAIM_CEILING,
        "artifact_bindings": [
            {"path": str(DOC), "sha256": doc_sha},
            {"path": str(VERIFY), "sha256": verification_sha},
            {"path": evidence_path, "sha256": evidence_sha},
            *[{"path": row["path"], "sha256": row["sha256"]} for row in reports],
            *[{"path": row["path"], "sha256": row["sha256"]} for row in records],
        ],
        "expected_counts": {"nodes": len(nodes), "anchors": 0, "relations": len(relations)},
        "anchors": [],
        "nodes": nodes,
        "relations": relations,
    }


def main() -> int:
    if not (REPO / DOC).is_file():
        raise RuntimeError(f"root-authored Korean research note is required: {DOC}")
    for target in (VERIFY, KG):
        require_new(target)
    if (REPO / EVIDENCE_DIR).exists():
        raise RuntimeError(f"publication evidence directory already exists: {EVIDENCE_DIR}")
    before = source_records()
    core, core_binding = read_json_report(CORE_REPORT)
    statistical, statistical_binding = read_json_report(STAT_REPORT)
    runtime, runtime_binding = read_json_report(RUNTIME_REPORT)
    if any(report.get("status") != "EXACT_SOURCE_KERNEL_CHECKED" for report in (core, statistical)):
        raise RuntimeError("core/statistical kernel audit did not pass")
    core_sources = verify_report_source_hashes(core, CORE_REPORT)
    statistical_sources = verify_report_source_hashes(statistical, STAT_REPORT)
    if not REQUIRED_REPORTED_LEAN.issubset(set(core_sources) | set(statistical_sources)):
        missing = sorted(REQUIRED_REPORTED_LEAN - (set(core_sources) | set(statistical_sources)))
        raise RuntimeError(f"core/statistical reports omit required Lean source records: {missing}")
    validate_runtime_report(runtime)
    after = source_records()
    if before != after:
        raise RuntimeError("a source-bound input changed while snapshotting reports")
    doc_sha = sha256((REPO / DOC).read_bytes())
    verification = {
        "schema_version": "hswm-whole-system-lean-round-verification/v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "EXACT_SOURCE_VERIFICATION_REPORT_SNAPSHOT_RECORDED",
        "claim_ceiling": CLAIM_CEILING,
        "source_records": before,
        "upstream_reports": [core_binding, statistical_binding, runtime_binding],
        "core_and_statistical_source_hashes_match_current_workspace": True,
        "runtime_verification": {
            "focused_test_count": 3,
            "total_test_count": count(runtime, "tests", "test"),
            "mutation_case_count": 22,
            "commands": runtime["commands"],
        },
        "statistical_auditor": {
            "aggregate_path": "formal/statistical-learning/HSWMStatisticalLearning.lean",
            "auditor_path": "src/hswm/effect-runtime/src/statistical-learning-proof-process.ts",
            "statistical_report": str(STAT_REPORT),
            "note": "The source-bound statistical report is the current audit input for AdaptiveRounds and its aggregate; this snapshot tool does not rerun it.",
        },
        "result_boundaries": {
            "p1": "DECODED_STRUCTURAL_WITNESS_WITH_TESTED_BYTE_ADAPTER_NOT_FULL_TS_REFINEMENT_OR_AUTHENTICATED_CHRONOLOGY",
            "p2": "FORMAL_LOCALITY_MODEL_WITH_MISSING_EXCEPTION_AND_ROLE_COUNTEREXAMPLES_PLANNER_EXPANDED_PRIOR_EVIDENCE_AND_FULL_REQUEST_LOCALITY_REMAIN",
            "p3": "FINITE_HISTORY_FRESH_KERNEL_STATISTICAL_SELECTION_AND_FINITE_ALPHA_SPENDING_UNDER_DECLARED_PREMISES",
            "unaddressed": ["FULL_P1_P2_P3", "LLM_EFFICACY", "AUTHENTICATED_SELECTED_BEFORE_HELDOUT_CHRONOLOGY", "P4_TOPOLOGY_LEARNING", "P5_MULTICELL_COMPOSITION"],
        },
        "publication_mode": "SNAPSHOT_ONLY_NOT_AN_APPROVAL_GATE",
        "live_kg_published": False,
    }
    write_new(VERIFY, canonical(verification))
    verification_sha = sha256((REPO / VERIFY).read_bytes())
    receipt = {
        "schema_version": "hswm-whole-system-lean-round-receipt/v1",
        "date": DATE,
        "status": "SOURCE_BOUND_BOUNDED_FORMAL_AND_ADAPTER_RESULT",
        "authority_class": "SECONDARY_AI",
        "claim_ceiling": CLAIM_CEILING,
        "sources": [
            *before,
            {"path": str(DOC), "sha256": doc_sha, "byte_length": (REPO / DOC).stat().st_size},
            core_binding,
            statistical_binding,
            runtime_binding,
            {"path": str(VERIFY), "sha256": verification_sha, "byte_length": (REPO / VERIFY).stat().st_size},
        ],
        "nonclaims": ["NO_LIVE_KG_PUBLICATION", "NO_LLM_EFFICACY", "NO_AUTHENTICATED_CHRONOLOGY", "P4_P5_UNADDRESSED"],
    }
    receipt_raw = canonical(receipt)
    receipt_sha = sha256(receipt_raw)
    evidence_path = EVIDENCE_DIR / f"{receipt_sha}.json"
    write_new(evidence_path, receipt_raw)
    write_new(KG, canonical(bundle(before, str(evidence_path), receipt_sha, verification_sha, doc_sha,
                                  [core_binding, statistical_binding, runtime_binding])))
    print(json.dumps({"doc": str(DOC), "verification": str(VERIFY), "kg": str(KG),
                      "evidence": str(evidence_path), "receipt_sha256": receipt_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"WHOLE_SYSTEM_LEAN_ROUND_PUBLICATION_REFUSED: {error}", file=sys.stderr)
        raise SystemExit(1)
