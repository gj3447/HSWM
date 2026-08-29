#!/usr/bin/env python3
"""Fail-closed two-layer validator for causal-composition evidence bundles."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PATH = ROOT / "_research/causal_composition/project.v1.json"
CONTROL_KINDS = {"ControlInstance", "MatchedBudget", "PreOutcomeSeal", "OutcomeSource", "InstrumentCalibration", "ObservedResult", "ControlAssessment", "ClaimDecision"}


class RunBundleValidationError(ValueError):
    """A bundle attempts a claim not supported by its bounded evidence."""


def _sha(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _project(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "hswm-causal-composition-research-program/v1":
        raise RunBundleValidationError("unexpected research-program schema")
    return value


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != {} and value != []


def _artifacts(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = bundle.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise RunBundleValidationError("artifacts must be a non-empty array")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"uid", "kind", "properties"}:
            raise RunBundleValidationError("artifact shape must be uid, kind, properties")
        if not isinstance(row["uid"], str) or not row["uid"] or row["uid"] in result:
            raise RunBundleValidationError("artifact UIDs must be unique and non-empty")
        if not isinstance(row["kind"], str) or not isinstance(row["properties"], dict):
            raise RunBundleValidationError("artifact kind/properties are invalid")
        result[row["uid"]] = row
    return result


def _required(row: Mapping[str, Any], fields: list[str], label: str) -> None:
    empties_ok = {"evidence_extension_uids", "required_evidence_extension_ids", "gate_extension_uids", "prerequisite_gate_decision_uids"}
    missing = [f for f in fields if f not in row["properties"] or (f not in empties_ok and not _present(row["properties"][f]))]
    if missing:
        raise RunBundleValidationError(f"{label} missing required fields: {', '.join(missing)}")


def _local(rows: Mapping[str, Mapping[str, Any]], uid: Any, kind: str, field: str) -> Mapping[str, Any]:
    if not isinstance(uid, str) or uid not in rows or rows[uid]["kind"] != kind:
        raise RunBundleValidationError(f"{field} must reference local {kind}")
    return rows[uid]


def _extensions(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    answer: dict[str, Mapping[str, Any]] = {}
    for row in rows.values():
        if row["kind"] == "ExtensionEvidence":
            key = row["properties"].get("schema_id")
            if not isinstance(key, str) or not key or key in answer:
                raise RunBundleValidationError("extension schema IDs must be unique")
            answer[key] = row
    return answer


def _ceiling(project: Mapping[str, Any], ceiling: str, uid: Any) -> None:
    if project["claim_ceiling_uids"].get(ceiling) != uid:
        raise RunBundleValidationError("claim ceiling ID and ontology UID are inconsistent")


def _summary(bundle: Mapping[str, Any], decision: Mapping[str, Any], *, scope: str, control_id: str | None = None) -> dict[str, Any]:
    p = decision["properties"]
    return {"uid": decision["uid"], "subject_uid": p["subject_uid"], "gate_uid": p["gate_uid"], "gate_mode": p["gate_mode"], "decision": p["decision"], "scope": scope, "promotion_scope_uid": p["promotion_scope_uid"], "ceiling": p["claim_ceiling"], "unlock": p["unlock_authorized"], "bundle_sha256": _sha(bundle), "control_id": control_id, "artifacts": _artifacts(bundle)}


def _validate_control(bundle: Mapping[str, Any], project: Mapping[str, Any], rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    schemas = {x["id"]: x for x in project["run_contract"]["artifact_schemas"]}
    controls = {x["id"]: x for x in project["control_families"]}
    gates = {x["id"]: x for x in project["gates"]}
    run = bundle["bundle_uid"]
    if any(row["kind"] not in CONTROL_KINDS | {"ExtensionEvidence"} for row in rows.values()):
        raise RunBundleValidationError("CONTROL_RUN contains an inapplicable artifact kind")
    decision = _local(rows, bundle["primary_decision_uid"], "ClaimDecision", "primary_decision_uid")
    for kind in CONTROL_KINDS:
        found = [x for x in rows.values() if x["kind"] == kind and x["properties"].get("run_uid") == run]
        if len(found) != 1:
            raise RunBundleValidationError(f"CONTROL_RUN requires exactly one primary {kind}")
        _required(found[0], schemas[kind]["required_fields"], kind)
    d = decision["properties"]
    if d["decision_scope"] != "CONTROL" or d["unlock_authorized"] is not False:
        raise RunBundleValidationError("CONTROL_RUN decisions are CONTROL scoped and never unlock")
    gate = gates.get(d["gate_uid"])
    control = next(x for x in rows.values() if x["kind"] == "ControlInstance" and x["properties"].get("run_uid") == run)
    cid = control["properties"]["control_family_uid"]
    if gate is None or cid not in controls or cid not in gate["required_control_ids"] or control["properties"]["subject_uid"] != d["subject_uid"] or control["properties"]["gate_mode"] != d["gate_mode"]:
        raise RunBundleValidationError("control is not applicable to declared gate/subject")
    allowed_gate_modes = {"PRECURSOR", "INTEGRATED"} if d["gate_uid"] == "G4" else {"INTEGRATED"}
    if d["gate_mode"] not in allowed_gate_modes:
        raise RunBundleValidationError("CONTROL_RUN gate mode is invalid")
    assessment = _local(rows, d["control_assessment_uid"], "ControlAssessment", "control_assessment_uid")
    observed = _local(rows, assessment["properties"]["observed_result_uid"], "ObservedResult", "observed_result_uid")
    if assessment["properties"]["run_uid"] != run or observed["properties"]["run_uid"] != run or assessment["properties"]["control_family_uid"] != cid:
        raise RunBundleValidationError("control assessment references foreign evidence")
    state = assessment["properties"]["assessment_state"]
    expected = {"BOUNDED": "PASS", "REMAINS_VIABLE": "FAIL", "INCONCLUSIVE": "INCONCLUSIVE"}.get(state)
    if d["decision"] != expected:
        raise RunBundleValidationError("ControlAssessment and ClaimDecision state mismatch")
    ceiling = "CONTROL_ALTERNATIVE_BOUNDED_WITHIN_SCOPE" if state == "BOUNDED" else controls[cid]["claim_ceiling_if_failed"] if state == "REMAINS_VIABLE" else "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    if d["claim_ceiling"] != ceiling or assessment["properties"]["applicable_claim_ceiling"] != ceiling:
        raise RunBundleValidationError("CONTROL_RUN uses an illegal claim ceiling")
    _ceiling(project, ceiling, d["ceiling_uid"])
    extension_schemas = {x["id"]: x for x in project["run_contract"]["extension_schemas"]}
    actual = _extensions(rows)
    needed = {key for key, schema in extension_schemas.items() if schema["applies_to_id"] == cid}
    if set(control["properties"]["required_evidence_extension_ids"]) != needed or set(actual) != needed or set(d["evidence_extension_uids"]) != {x["uid"] for x in actual.values()}:
        raise RunBundleValidationError("CONTROL_RUN conditional extension coverage is not exact")
    for key, row in actual.items():
        _required(row, ["schema_id", *extension_schemas[key]["required_fields"]], key)
    return _summary(bundle, decision, scope="CONTROL", control_id=cid)


def _sources(bundle: Mapping[str, Any], path: Path, seen: set[str]) -> dict[str, dict[str, Any]]:
    answer: dict[str, dict[str, Any]] = {}
    if not isinstance(bundle["source_bundles"], list):
        raise RunBundleValidationError("source_bundles must be an array")
    for row in bundle["source_bundles"]:
        if not isinstance(row, dict) or set(row) != {"canonical_sha256", "bundle"} or not isinstance(row["canonical_sha256"], str) or not isinstance(row["bundle"], dict):
            raise RunBundleValidationError("source bundle shape is invalid")
        digest = _sha(row["bundle"])
        if digest != row["canonical_sha256"] or digest in answer:
            raise RunBundleValidationError("source bundle canonical SHA-256 is invalid")
        answer[digest] = _validate(row["bundle"], path, seen)
    return answer


def _source_by_decision(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for source in sources.values():
        if source["uid"] in result:
            raise RunBundleValidationError("duplicate source primary decision UID")
        result[source["uid"]] = source
    return result


def _g5_members(extension: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]], project: Mapping[str, Any], bundle_uid: str) -> tuple[set[str], set[str]]:
    p = extension["properties"]
    decisions, integrated, boundaries, hashes = (p["member_uid_to_gate_decision_uid_map"], p["member_uid_to_integrated_g4_decision_uid_map"], p["member_uid_to_boundary_evidence_uid_map"], p["member_uid_to_gate_source_bundle_sha256_map"])
    if not all(isinstance(x, dict) for x in (decisions, integrated, boundaries, hashes)) or len(decisions) < 2 or any(set(x) != set(decisions) for x in (integrated, boundaries, hashes)) or p["member_eligibility_validation_state"] != "PASS":
        raise RunBundleValidationError("G5 requires two or more exactly mapped eligible members")
    by_uid = _source_by_decision(sources)
    gates = {x["id"]: x for x in project["gates"]}
    needed = {"G1", "G2A", "G2B", "G3", "G4"}
    used_boundaries: set[str] = set()
    source_hashes: set[str] = set()
    for member, mapping in decisions.items():
        if not isinstance(mapping, dict) or set(mapping) != needed or not isinstance(hashes[member], dict) or set(hashes[member]) != needed:
            raise RunBundleValidationError("G5 member source/boundary mapping is incomplete")
        if boundaries[member] in used_boundaries:
            raise RunBundleValidationError("G5 members require distinct BoundaryEvidence UIDs")
        used_boundaries.add(boundaries[member])
        boundary = _local(extension["_all_artifacts"], boundaries[member], "BoundaryEvidence", "G5 boundary evidence")
        fields = extension["_boundary_fields"]
        _required(boundary, fields, "BoundaryEvidence")
        bp = boundary["properties"]
        if bp["bundle_uid"] != bundle_uid or bp["member_uid"] != member or bp["source_integrated_g4_decision_uid"] != integrated[member] or not _present(bp["owner_uid"]) or bp["independent_owner_attestation"] is not True:
            raise RunBundleValidationError("G5 boundary evidence has invalid member/owner/G4 linkage")
        for gate, uid in mapping.items():
            source = by_uid.get(uid)
            if not source or hashes[member][gate] != source["bundle_sha256"] or source["scope"] != "GATE" or source["subject_uid"] != member or source["gate_uid"] != gate or source["decision"] != "PASS" or source["unlock"] is not True or source["ceiling"] != gates[gate]["claim_ceiling"]:
                raise RunBundleValidationError("G5 counted member lacks integrated passing gate evidence")
            source_hashes.add(hashes[member][gate])
            if gate == "G4" and (source["artifacts"][uid]["properties"]["gate_mode"] != "INTEGRATED" or integrated[member] != uid):
                raise RunBundleValidationError("G5 rejects precursor G4 constituent")
    return source_hashes, used_boundaries


def _validate_gate(bundle: Mapping[str, Any], project: Mapping[str, Any], rows: Mapping[str, Mapping[str, Any]], sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    schemas = {x["id"]: x for x in project["run_contract"]["artifact_schemas"]}
    gates = {x["id"]: x for x in project["gates"]}
    allowed_gate_kinds = {
        "GateAssessment",
        "GateDecision",
        "ExtensionEvidence",
        "BoundaryEvidence",
    }
    if any(row["kind"] not in allowed_gate_kinds for row in rows.values()):
        raise RunBundleValidationError("GATE_PROMOTION contains an inapplicable artifact kind")
    if sum(row["kind"] == "GateAssessment" for row in rows.values()) != 1 or sum(
        row["kind"] == "GateDecision" for row in rows.values()
    ) != 1:
        raise RunBundleValidationError("GATE_PROMOTION requires one assessment and one decision")
    decision = _local(rows, bundle["primary_decision_uid"], "GateDecision", "primary_decision_uid")
    assessment = _local(rows, decision["properties"]["gate_assessment_uid"], "GateAssessment", "gate_assessment_uid")
    _required(decision, schemas["GateDecision"]["required_fields"], "GateDecision")
    _required(assessment, schemas["GateAssessment"]["required_fields"], "GateAssessment")
    d, a, gate = decision["properties"], assessment["properties"], gates.get(decision["properties"]["gate_uid"])
    if d["bundle_uid"] != bundle["bundle_uid"] or a["bundle_uid"] != bundle["bundle_uid"]:
        raise RunBundleValidationError(
            "GateAssessment/GateDecision bundle UID differs from enclosing bundle"
        )
    if gate is None or d["decision_scope"] != "GATE" or any(d[key] != a[key] for key in ("subject_uid", "gate_uid", "gate_mode", "promotion_scope_uid")):
        raise RunBundleValidationError("GateAssessment/GateDecision scope mismatch")
    by_uid = _source_by_decision(sources)
    expected_source_hashes: set[str] = set()
    controls = a["required_control_decision_uids"]
    if not isinstance(controls, list) or len(controls) != len(gate["required_control_ids"]):
        raise RunBundleValidationError("gate promotion control coverage is incomplete")
    found, control_states = set(), []
    for uid in controls:
        source = by_uid.get(uid)
        if not source or source["scope"] != "CONTROL" or source["subject_uid"] != d["subject_uid"] or source["gate_uid"] != d["gate_uid"] or source["gate_mode"] != d["gate_mode"] or source["promotion_scope_uid"] != d["promotion_scope_uid"]:
            raise RunBundleValidationError("gate promotion has invalid CONTROL_RUN source")
        found.add(source["control_id"])
        control_states.append(source["decision"])
        expected_source_hashes.add(source["bundle_sha256"])
    if found != set(gate["required_control_ids"]):
        raise RunBundleValidationError("gate promotion control coverage is not exact")
    if d["decision"] == "PASS" and any(state != "PASS" for state in control_states):
        raise RunBundleValidationError("gate PASS requires every control PASS")
    if d["decision"] == "FAIL" and "INCONCLUSIVE" in control_states:
        raise RunBundleValidationError("gate FAIL cannot override an inconclusive control")
    if d["decision"] == "FAIL" and "FAIL" not in control_states and a["pass_rule_state"] != "FAILED":
        raise RunBundleValidationError("gate FAIL requires a control FAIL or failed pass rule")
    if d["decision"] == "INCONCLUSIVE" and "INCONCLUSIVE" not in control_states and a["pass_rule_state"] != "INCONCLUSIVE":
        raise RunBundleValidationError("gate INCONCLUSIVE requires inconclusive control or assessment")
    prereq = a["prerequisite_gate_decision_uids"]
    required_prereq = {"G0", "G1"} if d["gate_uid"] == "G4" and d["gate_mode"] == "PRECURSOR" else set(gate["prerequisites"])
    found_prereq = set()
    prerequisite_sources: dict[str, Mapping[str, Any]] = {}
    for uid in prereq:
        source = by_uid.get(uid)
        if not source or source["scope"] != "GATE" or source["decision"] != "PASS" or source["unlock"] is not True or source["subject_uid"] != d["subject_uid"] or source["promotion_scope_uid"] != d["promotion_scope_uid"]:
            raise RunBundleValidationError("gate promotion has invalid prerequisite source")
        found_prereq.add(source["gate_uid"])
        prerequisite_sources[source["gate_uid"]] = source
        expected_source_hashes.add(source["bundle_sha256"])
    if found_prereq != required_prereq or len(prereq) != len(required_prereq):
        raise RunBundleValidationError("gate prerequisite coverage is not exact")
    state_contract = project["run_contract"]["gate_assessment_state_contract"].get(d["decision"])
    if not state_contract or any(a[key] != value for key, value in state_contract.items()):
        raise RunBundleValidationError("GateAssessment state is inconsistent with GateDecision")
    extensions = _extensions(rows)
    needed_extensions = {"G4PrecursorDecisionEvidence"} if d["gate_uid"] == "G4" and d["gate_mode"] == "PRECURSOR" else {"G5MacroIdentificationEvidence"} if d["gate_uid"] == "G5" else set()
    if set(extensions) != needed_extensions or set(d["gate_extension_uids"]) != {row["uid"] for row in extensions.values()} or set(a["gate_extension_uids"]) != {row["uid"] for row in extensions.values()}:
        raise RunBundleValidationError("gate extension coverage is not exact")
    extension_schemas = {x["id"]: x for x in project["run_contract"]["extension_schemas"]}
    for key, row in extensions.items():
        _required(row, ["schema_id", *extension_schemas[key]["required_fields"]], key)
    ceiling, unlock = gate["claim_ceiling"], d["decision"] == "PASS"
    if d["gate_uid"] == "G4" and d["gate_mode"] == "PRECURSOR":
        precursor = extensions["G4PrecursorDecisionEvidence"]["properties"]
        precursor_contract = gate["precursor_contract"]
        if (
            precursor["gate_mode"] != "PRECURSOR"
            or precursor["artifact_partition"] != "PRECURSOR_ONLY"
            or precursor["unlock_authorized"] is not False
            or precursor["allowed_target"] not in precursor_contract["allowed_targets"]
            or not isinstance(precursor["required_null_result_uids"], list)
            or not precursor["required_null_result_uids"]
            or precursor["ceiling_uid"]
            != project["claim_ceiling_uids"][gate["precursor_claim_ceiling"]]
        ):
            raise RunBundleValidationError("G4 precursor evidence must never unlock")
        if (
            precursor["predecessor_g0_decision_uid"]
            != prerequisite_sources["G0"]["uid"]
            or precursor["predecessor_g1_decision_uid"]
            != prerequisite_sources["G1"]["uid"]
            or precursor["predecessor_g0_source_bundle_sha256"]
            != prerequisite_sources["G0"]["bundle_sha256"]
            or precursor["predecessor_g1_source_bundle_sha256"]
            != prerequisite_sources["G1"]["bundle_sha256"]
        ):
            raise RunBundleValidationError("G4 precursor source hashes are not exact")
        ceiling, unlock = gate["precursor_claim_ceiling"], False
    if d["decision"] == "FAIL":
        ceiling, unlock = "GATE_NOT_PASSED_NO_UNLOCK", False
    elif d["decision"] == "INCONCLUSIVE":
        ceiling, unlock = "INCONCLUSIVE_MEASUREMENT_NOT_READY", False
    expected_boundary_uids: set[str] = set()
    if d["gate_uid"] == "G5" and d["decision"] == "PASS":
        extension = extensions.get("G5MacroIdentificationEvidence")
        if extension is None:
            raise RunBundleValidationError("G5 requires macro-identification extension")
        ep = extension["properties"]
        if (
            ep["primary_total_effect_estimand"] != gate["primary_estimand"]
            or ep["post_treatment_mediator_rule"]
            != "OBSERVE_NOT_CONDITION_FOR_PRIMARY_TOTAL_EFFECT"
            or ep["macro_identification_decision"] != "PASS"
            or ep["fallback_ceiling_if_unmet"] != gate["fallback_claim_ceiling"]
        ):
            raise RunBundleValidationError("G5 macro-identification semantics drifted")
        extension = dict(extension)
        extension["_all_artifacts"] = rows
        extension["_boundary_fields"] = schemas["BoundaryEvidence"]["required_fields"]
        member_hashes, expected_boundary_uids = _g5_members(
            extension, sources, project, bundle["bundle_uid"]
        )
        expected_source_hashes |= member_hashes
    observed_boundary_uids = {
        row["uid"] for row in rows.values() if row["kind"] == "BoundaryEvidence"
    }
    if observed_boundary_uids != expected_boundary_uids:
        raise RunBundleValidationError("G5 BoundaryEvidence coverage is not exact")
    if d["claim_ceiling"] != ceiling or d["unlock_authorized"] is not unlock:
        raise RunBundleValidationError("GateDecision has illegal ceiling or unlock")
    _ceiling(project, ceiling, d["ceiling_uid"])
    if set(sources) != expected_source_hashes:
        raise RunBundleValidationError("GATE_PROMOTION source-bundle coverage is not exact")
    return _summary(bundle, decision, scope="GATE")


def _validate(bundle: Mapping[str, Any], path: Path, seen: set[str]) -> dict[str, Any]:
    keys = {"schema_version", "bundle_kind", "bundle_uid", "primary_decision_uid", "artifacts", "source_bundles"}
    if set(bundle) != keys or bundle.get("bundle_kind") not in {"CONTROL_RUN", "GATE_PROMOTION"} or not isinstance(bundle.get("bundle_uid"), str) or not bundle["bundle_uid"]:
        raise RunBundleValidationError("run bundle top-level shape/identity is invalid")
    digest = _sha(bundle)
    if digest in seen:
        raise RunBundleValidationError("recursive source-bundle cycle")
    project = _project(path)
    if bundle.get("schema_version") != project["run_contract"]["bundle_contract"]["schema_version"]:
        raise RunBundleValidationError("run bundle schema is not the project bundle contract")
    rows = _artifacts(bundle)
    sources = _sources(bundle, path, seen | {digest})
    if bundle["bundle_kind"] == "CONTROL_RUN":
        if sources:
            raise RunBundleValidationError("CONTROL_RUN cannot carry source bundles")
        return _validate_control(bundle, project, rows)
    return _validate_gate(bundle, project, rows, sources)


def validate_run_bundle(bundle: Mapping[str, Any], project_path: Path = PROJECT_PATH) -> None:
    _validate(bundle, project_path, set())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        validate_run_bundle(json.loads(args.path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, RunBundleValidationError) as exc:
        raise SystemExit(f"INVALID: {exc}") from exc
    print(json.dumps({"status": "VALID", "path": str(args.path)}, sort_keys=True))


if __name__ == "__main__":
    main()
