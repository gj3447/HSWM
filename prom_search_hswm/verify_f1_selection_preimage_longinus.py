"""Verify the F1 r8 selection-preimage Longinus v11 carrier."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prom_search_hswm.verify_f1_durable_transport_longinus import (
    BindingError,
    COMMIT_RE,
    LINE_RANGE_RE,
    REQUIRED_BINDING_KEYS,
    REQUIRED_LAYERS,
    SHA256_RE,
    _commit_blob,
    _exact_json_equal,
    _fail,
    _git,
    _load,
    _single_parent,
    _symbol_range,
)


DEFAULT_MANIFEST = (
    REPO_ROOT / "LONGINUS_HSWM_F1_SELECTION_PREIMAGE_BINDING_2026-07-30.json"
)
SCHEMA = "longinus-hswm-f1-r8-selection-preimage-binding/v11"
EXPECTED_BINDING_ID = "longinus-hswm-f1-r8-selection-preimage-v11-20260730"
EXPECTED_BASELINE_ANCESTOR = "7af2ad71777aca268497a13fd30d127abfd7e855"
EXPECTED_IMPLEMENTATION_COMMIT = "c0c5cef13262a19b0e6669cd2fd85c36320c5cee"
EXPECTED_IMPLEMENTATION_ACTUAL_PARENT = (
    "8bdb7eeb401acc9dd2a34036cc209485698ca03f"
)
EXPECTED_BINDING_SOURCE_COMMIT = EXPECTED_IMPLEMENTATION_COMMIT
EXPECTED_INCIDENT_ARTIFACT_SOURCE_COMMIT = (
    "d5a918da4fc691d4e47a320e23fc6ba5c42065db"
)
EXPECTED_INCIDENT_ARTIFACT_SOURCE_PARENT = (
    "624cab85f794ee4b64bb8616ae172c1bf2e9c985"
)
EXPECTED_SELECTION_BOUNDARY = {
    "selection_file_sha256": (
        "52f63a5cf4fdd04e7ca01c2af2caca8e0a68c54e51a6208e50bff6da01a929dc"
    ),
    "selection_canonical_sha256": (
        "5605545627dd00f547e0a159cef59c5570a5c120186ce7b73d9938a4877a9921"
    ),
    "selection_receipt_sha256": (
        "e2d36903dafb6b5e1387c9969ce9fb60cbd315c24f1d51e30618579291d9d6b8"
    ),
    "embedded_final_incident_self_sha256": (
        "f97634c0c4185b9bdbe983d6fe5fffc672e6c625923f027a780433acfc714afd"
    ),
    "incident_artifact_file_sha256": (
        "200e0708f556231b8ee4d83dea76ec923fb27071a76e2a27045e6ee218578fb0"
    ),
}
EXPECTED_SUPERSEDED_INTERIM = {
    "selection_file_sha256": (
        "999d5c38f0e0ccfe594a8c69cc0b697fb2a6972835f3472144b2d51fcce2fcab"
    ),
    "selection_canonical_sha256": (
        "03143d6e84e1d0c787d49db3e16f73b7833630b16f3a8f44a19d84fd5ed5a846"
    ),
    "selection_receipt_sha256": (
        "0cea21ecaaa7bb6ac19047326029120c84a8fcbdda8ff6f4141634d8279be641"
    ),
    "incident_v1_self_sha256": (
        "6d3f2f8978a8502c0f01135ad7b998841dbb4bd61462934927f735e3932bad7d"
    ),
}
EXPECTED_PREDECESSOR = {
    "binding_id": "longinus-hswm-f1-r8-durable-resume-v10-20260730",
    "carrier_commit": EXPECTED_BASELINE_ANCESTOR,
    "manifest_path": "LONGINUS_HSWM_F1_DURABLE_RESUME_BINDING_2026-07-30.json",
    "manifest_file_sha256": (
        "3eed2072037de747f0e23291df755f75a72a4e8dbda189753b109d3235e51f18"
    ),
}
EXPECTED_CHANGED_PATHS = {
    "prom_search_hswm/prom9_f1_r8_envelope.py",
    "prom_search_hswm/test_prom9_f1_r8_envelope.py",
}
EXPECTED_UNCHANGED_RELEVANT_PATHS = {
    "prom_search_hswm/prom9_f1_r8_power.py",
    "receipts/hswm_f1_r8_v8_aborted_exposure.v2.json",
}
EXPECTED_TARGET_PATHS = EXPECTED_CHANGED_PATHS | EXPECTED_UNCHANGED_RELEVANT_PATHS
EXPECTED_CONTRACTS = {
    "prom_search_hswm/prom9_f1_r8_envelope.py": (
        "R8_SELECTION_PREIMAGE_IMPLEMENTATION__UNJUDGED"
    ),
    "prom_search_hswm/test_prom9_f1_r8_envelope.py": (
        "R8_SELECTION_PREIMAGE_TEST__ENGINEERING_ONLY"
    ),
    "prom_search_hswm/prom9_f1_r8_power.py": (
        "R8_SELECTION_SOURCE_IMPLEMENTATION__UNJUDGED"
    ),
    "receipts/hswm_f1_r8_v8_aborted_exposure.v2.json": (
        "R8_ABORTED_EXPOSURE_ARTIFACT__QUARANTINED"
    ),
}
EXPECTED_INCIDENT_BOUNDARY = {
    "aborted_attempt_exposure_receipt_sha256": (
        EXPECTED_SELECTION_BOUNDARY["embedded_final_incident_self_sha256"]
    ),
    "historical_upstream_model_calls": 1,
    "prospective_successor_model_calls": 0,
    "confirmatory_upstream_model_calls": 0,
    "scientific_verdicts": 0,
}
EXPECTED_BLOB_AUTHORITY = (
    "Every source and artifact SHA, symbol, signature, constant, and line range "
    "is read from committed Git blobs, never from worktree Python."
)
EXPECTED_ANCESTRY_RULE = (
    "The v10 carrier precedes the two-path implementation span; the "
    "implementation parent is exact; d5 is the immutable v2 incident source "
    "and precedes implementation; its receipt and selector blobs remain "
    "byte-identical at binding source; binding source precedes HEAD."
)
TOP_LEVEL_KEYS = {
    "schema",
    "binding_id",
    "binding_state",
    "generated_at",
    "baseline_scope",
    "scientific_status",
    "evidence_class",
    "r7_status",
    "b22_gate",
    "model_calls",
    "incident_boundary",
    "selection_boundary",
    "superseded_interim",
    "predecessor",
    "git",
    "change_inventory",
    "kg",
    "layers",
    "required_target_paths",
    "bindings",
}


def _assignment_value(source: str, name: str, *, key: str | None = None) -> object:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        _fail("SIGNATURE_MISMATCHED", f"cannot parse envelope constants: {error}")
    matches = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    if len(matches) != 1:
        _fail("ORPHANED", f"constant {name} occurs {len(matches)} times")
    value = matches[0]
    if key is not None:
        if not isinstance(value, ast.Dict):
            _fail("SIGNATURE_MISMATCHED", f"constant {name} is not a mapping")
        keyed = [
            item
            for raw_key, item in zip(value.keys, value.values)
            if isinstance(raw_key, ast.Constant) and raw_key.value == key
        ]
        if len(keyed) != 1:
            _fail("ORPHANED", f"constant {name}[{key!r}] occurs {len(keyed)} times")
        value = keyed[0]
    try:
        return ast.literal_eval(value)
    except (TypeError, ValueError) as error:
        _fail("SIGNATURE_MISMATCHED", f"constant {name} is not literal: {error}")


def _active_selection_constants(blob: bytes) -> dict[str, object]:
    try:
        source = blob.decode("utf-8")
    except UnicodeError as error:
        _fail("SIGNATURE_MISMATCHED", f"cannot decode envelope source: {error}")
    return {
        "selection_file_sha256": _assignment_value(
            source, "R8_DERIVATION_PREIMAGE_FILE_SHA256", key="selection_receipt"
        ),
        "selection_canonical_sha256": _assignment_value(
            source,
            "R8_DERIVATION_PREIMAGE_CANONICAL_SHA256",
            key="selection_receipt",
        ),
        "selection_receipt_sha256": _assignment_value(
            source, "R8_SELECTION_RECEIPT_SHA256"
        ),
        "embedded_final_incident_self_sha256": _assignment_value(
            source, "R8_ABORTED_ATTEMPT_EXPOSURE_RECEIPT_SHA256"
        ),
    }


def _changed_paths(left: str, right: str) -> set[str]:
    return {
        item
        for item in _git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", left, right],
            classification="DIVERGENT",
            label="cannot derive implementation diff",
        )
        .decode("utf-8", "strict")
        .splitlines()
        if item
    }


def verify(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    manifest = _load(manifest_path)
    if set(manifest) != TOP_LEVEL_KEYS:
        _fail("LABEL_ROT", "manifest top-level shape drifted")
    if manifest.get("schema") != SCHEMA:
        _fail("LABEL_ROT", f"schema must be {SCHEMA}")
    if manifest.get("binding_id") != EXPECTED_BINDING_ID:
        _fail("LABEL_ROT", "binding identity drifted")
    if manifest.get("binding_state") != "PIERCED_LOCAL_NO_KG_WRITE":
        _fail("LABEL_ROT", "local/no-KG-write boundary drifted")
    inadmissible = "EXPLORATORY_ENGINEERING_ONLY__PREREGISTRATION_INADMISSIBLE"
    if (
        manifest.get("scientific_status") != "UNJUDGED"
        or manifest.get("evidence_class") != inadmissible
        or manifest.get("r7_status") != inadmissible
    ):
        _fail("LABEL_ROT", "scientific/r7 status drifted")
    if (
        manifest.get("b22_gate") != "LOCKED"
        or type(manifest.get("model_calls")) is not int
        or manifest.get("model_calls") != 1
        or not _exact_json_equal(
            manifest.get("incident_boundary"), EXPECTED_INCIDENT_BOUNDARY
        )
    ):
        _fail("LABEL_ROT", "B22/quarantined model-call boundary drifted")
    if not _exact_json_equal(
        manifest.get("selection_boundary"), EXPECTED_SELECTION_BOUNDARY
    ):
        _fail("LABEL_ROT", "active selection boundary drifted")
    if not _exact_json_equal(
        manifest.get("superseded_interim"), EXPECTED_SUPERSEDED_INTERIM
    ):
        _fail("LABEL_ROT", "superseded interim boundary drifted")
    if not _exact_json_equal(manifest.get("predecessor"), EXPECTED_PREDECESSOR):
        _fail("LABEL_ROT", "v10 predecessor identity drifted")
    if manifest.get("layers") != list(REQUIRED_LAYERS):
        _fail("LABEL_ROT", "Longinus seven-layer order drifted")

    kg = manifest.get("kg")
    if not isinstance(kg, dict) or set(kg) != {
        "write_state",
        "anchor_status",
        "provenance_actor",
        "source_path",
        "timestamp",
        "baseline_scope",
    }:
        _fail("LABEL_ROT", "KG provenance shape drifted")
    if (
        kg.get("write_state") != "NOT_AUTHORIZED_NOT_WRITTEN"
        or kg.get("anchor_status") != "LOCAL_PROPOSED_REFERENCE_IDENTITY"
        or kg.get("provenance_actor") != "Codex"
        or kg.get("source_path")
        != "LONGINUS_HSWM_F1_SELECTION_PREIMAGE_BINDING_2026-07-30.json"
        or kg.get("timestamp") != manifest.get("generated_at")
    ):
        _fail("LABEL_ROT", "KG write boundary drifted")
    if not isinstance(kg.get("baseline_scope"), str) or not kg["baseline_scope"]:
        _fail("LABEL_ROT", "KG baseline scope missing")

    git = manifest.get("git")
    if not isinstance(git, dict) or set(git) != {
        "remote",
        "branch",
        "baseline_ancestor",
        "implementation_commit",
        "implementation_actual_parent",
        "binding_source_commit",
        "incident_artifact_source_commit",
        "incident_artifact_source_parent",
        "blob_authority",
        "ancestry_rule",
    }:
        _fail("MISSING", "git binding shape drifted")
    expected_git = {
        "baseline_ancestor": EXPECTED_BASELINE_ANCESTOR,
        "implementation_commit": EXPECTED_IMPLEMENTATION_COMMIT,
        "implementation_actual_parent": EXPECTED_IMPLEMENTATION_ACTUAL_PARENT,
        "binding_source_commit": EXPECTED_BINDING_SOURCE_COMMIT,
        "incident_artifact_source_commit": EXPECTED_INCIDENT_ARTIFACT_SOURCE_COMMIT,
        "incident_artifact_source_parent": EXPECTED_INCIDENT_ARTIFACT_SOURCE_PARENT,
    }
    if git.get("remote") != "https://github.com/gj3447/HSWM.git" or git.get(
        "branch"
    ) != "main":
        _fail("LABEL_ROT", "repository authority drifted")
    for field, expected in expected_git.items():
        actual = git.get(field)
        if (
            not isinstance(actual, str)
            or COMMIT_RE.fullmatch(actual) is None
            or actual != expected
        ):
            _fail("LABEL_ROT", f"git coordinate drifted: {field}")
        _git(
            ["cat-file", "-e", f"{actual}^{{commit}}"],
            classification="MISSING",
            label=f"missing commit {field}",
        )
    if git.get("blob_authority") != EXPECTED_BLOB_AUTHORITY:
        _fail("LABEL_ROT", "blob authority label missing")
    if git.get("ancestry_rule") != EXPECTED_ANCESTRY_RULE:
        _fail("LABEL_ROT", "ancestry rule missing")
    _git(
        ["merge-base", "--is-ancestor", EXPECTED_BASELINE_ANCESTOR, EXPECTED_IMPLEMENTATION_COMMIT],
        classification="DIVERGENT",
        label="v10 carrier does not precede implementation",
    )
    if _single_parent(
        EXPECTED_IMPLEMENTATION_COMMIT, label="implementation actual parent"
    ) != EXPECTED_IMPLEMENTATION_ACTUAL_PARENT:
        _fail("DIVERGENT", "implementation actual parent drifted")
    if _single_parent(
        EXPECTED_INCIDENT_ARTIFACT_SOURCE_COMMIT,
        label="incident artifact source parent",
    ) != EXPECTED_INCIDENT_ARTIFACT_SOURCE_PARENT:
        _fail("DIVERGENT", "incident artifact source parent drifted")
    _git(
        [
            "merge-base",
            "--is-ancestor",
            EXPECTED_INCIDENT_ARTIFACT_SOURCE_COMMIT,
            EXPECTED_IMPLEMENTATION_COMMIT,
        ],
        classification="DIVERGENT",
        label="incident artifact source does not precede implementation",
    )
    _git(
        ["merge-base", "--is-ancestor", EXPECTED_BINDING_SOURCE_COMMIT, "HEAD"],
        classification="DIVERGENT",
        label="binding source does not precede HEAD",
    )

    predecessor_blob = _commit_blob(
        EXPECTED_BASELINE_ANCESTOR, EXPECTED_PREDECESSOR["manifest_path"]
    )
    if hashlib.sha256(predecessor_blob).hexdigest() != EXPECTED_PREDECESSOR[
        "manifest_file_sha256"
    ]:
        _fail("DIVERGENT", "v10 predecessor manifest bytes drifted")
    try:
        predecessor_value = json.loads(predecessor_blob)
    except (UnicodeError, json.JSONDecodeError) as error:
        _fail("SIGNATURE_MISMATCHED", f"cannot parse predecessor manifest: {error}")
    if (
        not isinstance(predecessor_value, dict)
        or predecessor_value.get("binding_id") != EXPECTED_PREDECESSOR["binding_id"]
    ):
        _fail("LABEL_ROT", "v10 predecessor binding ID drifted")

    changed_paths = _changed_paths(
        EXPECTED_BASELINE_ANCESTOR, EXPECTED_IMPLEMENTATION_COMMIT
    )
    if changed_paths != EXPECTED_CHANGED_PATHS:
        _fail("DIVERGENT", f"implementation diff drifted: {sorted(changed_paths)}")
    change_inventory = manifest.get("change_inventory")
    expected_inventory = {
        "implementation_changed_paths": 2,
        "binding_source_changed_paths": 2,
        "unchanged_relevant_paths": sorted(EXPECTED_UNCHANGED_RELEVANT_PATHS),
    }
    if not _exact_json_equal(change_inventory, expected_inventory):
        _fail("LABEL_ROT", "change inventory drifted")

    for relative in sorted(EXPECTED_UNCHANGED_RELEVANT_PATHS):
        source_blob = _commit_blob(EXPECTED_INCIDENT_ARTIFACT_SOURCE_COMMIT, relative)
        implementation_blob = _commit_blob(EXPECTED_IMPLEMENTATION_COMMIT, relative)
        if source_blob != implementation_blob:
            _fail("DIVERGENT", f"unchanged provenance blob drifted: {relative}")

    target_paths = manifest.get("required_target_paths")
    if (
        not isinstance(target_paths, list)
        or len(target_paths) != len(set(target_paths))
        or set(target_paths) != EXPECTED_TARGET_PATHS
    ):
        _fail("ORPHANED", "required target inventory drifted")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != 4:
        _fail("ORPHANED", "binding inventory must contain four targets")
    seen_paths: set[str] = set()
    seen_nodes: set[str] = set()
    implementation_count = 0
    test_count = 0
    artifact_count = 0
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict) or set(binding) != REQUIRED_BINDING_KEYS:
            _fail("LABEL_ROT", f"binding {index} does not expose seven layers")
        kg_node = binding.get("kg_node")
        if not isinstance(kg_node, str) or not kg_node.startswith("LOCAL_PROPOSED_"):
            _fail("LABEL_ROT", f"binding {index} local KG identity drifted")
        if kg_node in seen_nodes:
            _fail("ORPHANED", f"duplicate local KG identity: {kg_node}")
        seen_nodes.add(kg_node)
        file_line = binding.get("file_line")
        if not isinstance(file_line, str) or ":" not in file_line:
            _fail("MISSING", f"binding {index} file_line is missing")
        relative, line_text = file_line.rsplit(":", 1)
        if relative in seen_paths:
            _fail("ORPHANED", f"multiple bindings target {relative}")
        seen_paths.add(relative)
        if binding.get("contract_binding") != EXPECTED_CONTRACTS.get(relative):
            _fail("LABEL_ROT", f"contract binding drifted for {relative}")
        implementation_count += str(binding["contract_binding"]).endswith("__UNJUDGED")
        test_count += str(binding["contract_binding"]).endswith("__ENGINEERING_ONLY")
        artifact_count += str(binding["contract_binding"]).endswith("__QUARANTINED")

        blob = _commit_blob(EXPECTED_BINDING_SOURCE_COMMIT, relative)
        expected_sha = binding.get("sha256")
        if (
            not isinstance(expected_sha, str)
            or SHA256_RE.fullmatch(expected_sha) is None
            or hashlib.sha256(blob).hexdigest() != expected_sha
        ):
            _fail("DIVERGENT", f"Git blob SHA drifted for {relative}")
        code_symbol = binding.get("code_symbol")
        if not isinstance(code_symbol, Mapping):
            _fail("MISSING", f"code symbol missing for {relative}")
        symbol_start, symbol_end = _symbol_range(blob, relative, code_symbol)
        range_match = LINE_RANGE_RE.fullmatch(str(binding.get("line_range")))
        if range_match is None:
            _fail("MISSING", f"line range missing for {relative}")
        start, end = int(range_match.group(1)), int(range_match.group(2))
        if start != symbol_start or end != symbol_end or line_text != str(start):
            _fail("DIVERGENT", f"AST/file line range drifted for {relative}")
        crate_script = binding.get("crate_script")
        prefix = "python -m pytest -q "
        if not isinstance(crate_script, str) or not crate_script.startswith(prefix):
            _fail("LABEL_ROT", f"unsafe crate script for {relative}")
        crate_path = crate_script[len(prefix) :]
        if not Path(crate_path).name.startswith("test_"):
            _fail("ORPHANED", f"crate script is not a test for {relative}")
        _commit_blob(EXPECTED_BINDING_SOURCE_COMMIT, crate_path)

    if seen_paths != EXPECTED_TARGET_PATHS:
        _fail("ORPHANED", "binding reverse scan does not cover all targets")
    if (implementation_count, test_count, artifact_count) != (2, 1, 1):
        _fail("LABEL_ROT", "implementation/test/artifact binding counts drifted")
    if not EXPECTED_CHANGED_PATHS <= seen_paths:
        _fail("ORPHANED", "changed implementation path is not reverse-bound")
    if not EXPECTED_UNCHANGED_RELEVANT_PATHS <= seen_paths:
        _fail("ORPHANED", "unchanged provenance path is not reverse-bound")

    envelope_blob = _commit_blob(
        EXPECTED_BINDING_SOURCE_COMMIT,
        "prom_search_hswm/prom9_f1_r8_envelope.py",
    )
    active_constants = _active_selection_constants(envelope_blob)
    expected_active = {
        key: value
        for key, value in EXPECTED_SELECTION_BOUNDARY.items()
        if key != "incident_artifact_file_sha256"
    }
    if not _exact_json_equal(active_constants, expected_active):
        _fail("DIVERGENT", "active envelope selection constants drifted")
    if set(active_constants.values()) & set(EXPECTED_SUPERSEDED_INTERIM.values()):
        _fail("LABEL_ROT", "active envelope retained an interim selection identity")

    return {
        "status": "PASS",
        "binding_id": EXPECTED_BINDING_ID,
        "baseline_ancestor": EXPECTED_BASELINE_ANCESTOR,
        "implementation_commit": EXPECTED_IMPLEMENTATION_COMMIT,
        "implementation_actual_parent": EXPECTED_IMPLEMENTATION_ACTUAL_PARENT,
        "binding_source_commit": EXPECTED_BINDING_SOURCE_COMMIT,
        "incident_artifact_source_commit": EXPECTED_INCIDENT_ARTIFACT_SOURCE_COMMIT,
        "incident_artifact_source_parent": EXPECTED_INCIDENT_ARTIFACT_SOURCE_PARENT,
        "bindings_checked": len(bindings),
        "files_checked": len(seen_paths),
        "implementation_bindings": implementation_count,
        "test_bindings": test_count,
        "artifact_bindings": artifact_count,
        "implementation_changed_paths": len(changed_paths),
        "unchanged_relevant_paths": len(EXPECTED_UNCHANGED_RELEVANT_PATHS),
        "longinus_layers": len(REQUIRED_LAYERS),
        "classifications": {
            "MISSING": 0,
            "ORPHANED": 0,
            "SIGNATURE_MISMATCHED": 0,
            "DIVERGENT": 0,
            "LABEL_ROT": 0,
        },
        "blob_authority": "GIT_COMMIT_ONLY",
        "predecessor_binding_id": EXPECTED_PREDECESSOR["binding_id"],
        "selection_receipt_sha256": EXPECTED_SELECTION_BOUNDARY[
            "selection_receipt_sha256"
        ],
        "incident_receipt_sha256": EXPECTED_SELECTION_BOUNDARY[
            "embedded_final_incident_self_sha256"
        ],
        "kg_write_state": "NOT_AUTHORIZED_NOT_WRITTEN",
        "scientific_status": "UNJUDGED",
        "b22_gate": "LOCKED",
        "historical_upstream_model_calls": 1,
        "prospective_successor_model_calls": 0,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?", default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.manifest), sort_keys=True))
        return 0
    except BindingError as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["BindingError", "DEFAULT_MANIFEST", "verify"]
