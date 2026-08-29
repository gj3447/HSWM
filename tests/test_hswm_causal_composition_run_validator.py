"""Two-layer fail-closed evidence-bundle tests."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts.validate_hswm_causal_composition_run import RunBundleValidationError, validate_run_bundle


ROOT = Path(__file__).resolve().parents[1]
PROJECT = json.loads((ROOT / "_research/causal_composition/project.v1.json").read_text())
SCHEMAS = {x["id"]: x for x in PROJECT["run_contract"]["artifact_schemas"]}
EXTENSIONS = {x["id"]: x for x in PROJECT["run_contract"]["extension_schemas"]}
GATES = {x["id"]: x for x in PROJECT["gates"]}
CEILINGS = PROJECT["claim_ceiling_uids"]
SCHEMA_VERSION = PROJECT["run_contract"]["bundle_contract"]["schema_version"]


def _sha(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _row(uid: str, kind: str, **properties: object) -> dict:
    return {"uid": uid, "kind": kind, "properties": properties}


def _fill(kind: str, **overrides: object) -> dict:
    values = {field: "x" for field in SCHEMAS[kind]["required_fields"]}
    values.update(overrides)
    return values


def _control(
    control: str,
    gate: str,
    subject: str = "subject",
    scope: str = "scope",
    gate_mode: str = "INTEGRATED",
) -> dict:
    run = f"control:{gate}:{control}:{subject}"
    decision_uid = f"decision-{gate}-{control}-{subject}"
    extension_ids = [key for key, row in EXTENSIONS.items() if row["applies_to_id"] == control]
    rows = [
        _row("control", "ControlInstance", **_fill("ControlInstance", run_uid=run, subject_uid=subject, control_family_uid=control, gate_mode=gate_mode, required_evidence_extension_ids=extension_ids)),
        _row("budget", "MatchedBudget", **_fill("MatchedBudget", run_uid=run)),
        _row("seal", "PreOutcomeSeal", **_fill("PreOutcomeSeal", run_uid=run)),
        _row("outcome", "OutcomeSource", **_fill("OutcomeSource", run_uid=run)),
        _row("instrument", "InstrumentCalibration", **_fill("InstrumentCalibration", run_uid=run)),
        _row("observed", "ObservedResult", **_fill("ObservedResult", run_uid=run)),
        _row("assessment", "ControlAssessment", **_fill("ControlAssessment", run_uid=run, control_family_uid=control, observed_result_uid="observed", assessment_state="BOUNDED", applicable_claim_ceiling="CONTROL_ALTERNATIVE_BOUNDED_WITHIN_SCOPE")),
    ]
    for ext_id in extension_ids:
        values = {field: "x" for field in EXTENSIONS[ext_id]["required_fields"]}
        rows.append(_row(f"ext-{ext_id}", "ExtensionEvidence", schema_id=ext_id, **values))
    rows.append(_row(decision_uid, "ClaimDecision", **_fill("ClaimDecision", run_uid=run, subject_uid=subject, decision_scope="CONTROL", promotion_scope_uid=scope, decision="PASS", control_assessment_uid="assessment", claim_ceiling="CONTROL_ALTERNATIVE_BOUNDED_WITHIN_SCOPE", ceiling_uid=CEILINGS["CONTROL_ALTERNATIVE_BOUNDED_WITHIN_SCOPE"], gate_uid=gate, gate_mode=gate_mode, unlock_authorized=False, evidence_extension_uids=[f"ext-{x}" for x in extension_ids])))
    return {"schema_version": SCHEMA_VERSION, "bundle_kind": "CONTROL_RUN", "bundle_uid": run, "primary_decision_uid": decision_uid, "artifacts": rows, "source_bundles": []}


def _source(bundle: dict) -> dict:
    return {"canonical_sha256": _sha(bundle), "bundle": bundle}


def _set_control_state(bundle: dict, state: str) -> None:
    assessment = next(
        row for row in bundle["artifacts"] if row["kind"] == "ControlAssessment"
    )
    decision = next(
        row for row in bundle["artifacts"] if row["kind"] == "ClaimDecision"
    )
    control_id = next(
        row for row in bundle["artifacts"] if row["kind"] == "ControlInstance"
    )["properties"]["control_family_uid"]
    if state == "REMAINS_VIABLE":
        decision_state = "FAIL"
        ceiling = next(
            row["claim_ceiling_if_failed"]
            for row in PROJECT["control_families"]
            if row["id"] == control_id
        )
    elif state == "INCONCLUSIVE":
        decision_state = "INCONCLUSIVE"
        ceiling = "INCONCLUSIVE_MEASUREMENT_NOT_READY"
    else:
        raise AssertionError(state)
    assessment["properties"].update(
        assessment_state=state,
        applicable_claim_ceiling=ceiling,
    )
    decision["properties"].update(
        decision=decision_state,
        claim_ceiling=ceiling,
        ceiling_uid=CEILINGS[ceiling],
        unlock_authorized=False,
    )


def _promotion(gate: str, subject: str = "subject", scope: str = "scope", cache: dict | None = None) -> dict:
    cache = {} if cache is None else cache
    key = (gate, subject, scope)
    if key in cache:
        return cache[key]
    control_sources = [_control(control, gate, subject, scope) for control in GATES[gate]["required_control_ids"]]
    prereq_sources = [_promotion(prereq, subject, scope, cache) for prereq in GATES[gate]["prerequisites"]]
    source_bundles = [_source(x) for x in [*control_sources, *prereq_sources]]
    uid = f"gate:{gate}:{subject}"
    decision_uid = f"decision-{gate}-{subject}"
    assessment = _row("assessment", "GateAssessment", **_fill("GateAssessment", bundle_uid=uid, subject_uid=subject, gate_uid=gate, gate_mode="INTEGRATED", promotion_scope_uid=scope, required_control_decision_uids=[x["primary_decision_uid"] for x in control_sources], prerequisite_gate_decision_uids=[x["primary_decision_uid"] for x in prereq_sources], gate_extension_uids=[], pass_rule_state="SATISFIED", stop_rule_state="NOT_TRIGGERED"))
    decision = _row(decision_uid, "GateDecision", **_fill("GateDecision", bundle_uid=uid, subject_uid=subject, decision_scope="GATE", promotion_scope_uid=scope, decision="PASS", gate_assessment_uid="assessment", claim_ceiling=GATES[gate]["claim_ceiling"], ceiling_uid=CEILINGS[GATES[gate]["claim_ceiling"]], gate_uid=gate, gate_mode="INTEGRATED", unlock_authorized=True, gate_extension_uids=[]))
    value = {"schema_version": SCHEMA_VERSION, "bundle_kind": "GATE_PROMOTION", "bundle_uid": uid, "primary_decision_uid": decision_uid, "artifacts": [assessment, decision], "source_bundles": source_bundles}
    cache[key] = value
    return value


def _g4_precursor(subject: str = "subject", scope: str = "scope") -> dict:
    gate = GATES["G4"]
    control_sources = [
        _control(control, "G4", subject, scope, "PRECURSOR")
        for control in gate["required_control_ids"]
    ]
    prerequisite_sources = [
        _promotion(prerequisite, subject, scope)
        for prerequisite in gate["precursor_contract"]["prerequisites"]
    ]
    source_bundles = [
        _source(bundle) for bundle in [*control_sources, *prerequisite_sources]
    ]
    uid = f"gate:G4:precursor:{subject}"
    decision_uid = f"decision-G4-precursor-{subject}"
    extension_uid = "g4-precursor-extension"
    predecessor_by_gate = {
        bundle["artifacts"][1]["properties"]["gate_uid"]: bundle
        for bundle in prerequisite_sources
    }
    extension = _row(
        extension_uid,
        "ExtensionEvidence",
        schema_id="G4PrecursorDecisionEvidence",
        gate_mode="PRECURSOR",
        predecessor_g0_decision_uid=predecessor_by_gate["G0"][
            "primary_decision_uid"
        ],
        predecessor_g1_decision_uid=predecessor_by_gate["G1"][
            "primary_decision_uid"
        ],
        predecessor_g0_source_bundle_sha256=_sha(predecessor_by_gate["G0"]),
        predecessor_g1_source_bundle_sha256=_sha(predecessor_by_gate["G1"]),
        allowed_target=gate["precursor_contract"]["allowed_targets"][0],
        required_null_result_uids=["null-result"],
        artifact_partition="PRECURSOR_ONLY",
        unlock_authorized=False,
        ceiling_uid=CEILINGS[gate["precursor_claim_ceiling"]],
    )
    assessment = _row(
        "assessment",
        "GateAssessment",
        **_fill(
            "GateAssessment",
            bundle_uid=uid,
            subject_uid=subject,
            gate_uid="G4",
            gate_mode="PRECURSOR",
            promotion_scope_uid=scope,
            required_control_decision_uids=[
                bundle["primary_decision_uid"] for bundle in control_sources
            ],
            prerequisite_gate_decision_uids=[
                bundle["primary_decision_uid"] for bundle in prerequisite_sources
            ],
            gate_extension_uids=[extension_uid],
            pass_rule_state="SATISFIED",
            stop_rule_state="NOT_TRIGGERED",
        ),
    )
    decision = _row(
        decision_uid,
        "GateDecision",
        **_fill(
            "GateDecision",
            bundle_uid=uid,
            subject_uid=subject,
            decision_scope="GATE",
            promotion_scope_uid=scope,
            decision="PASS",
            gate_assessment_uid="assessment",
            claim_ceiling=gate["precursor_claim_ceiling"],
            ceiling_uid=CEILINGS[gate["precursor_claim_ceiling"]],
            gate_uid="G4",
            gate_mode="PRECURSOR",
            unlock_authorized=False,
            gate_extension_uids=[extension_uid],
        ),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_kind": "GATE_PROMOTION",
        "bundle_uid": uid,
        "primary_decision_uid": decision_uid,
        "artifacts": [assessment, decision, extension],
        "source_bundles": source_bundles,
    }


def test_control_pass_cannot_unlock_or_promote() -> None:
    bundle = _control("CF-05", "G1")
    validate_run_bundle(bundle)
    bundle["artifacts"][-1]["properties"]["unlock_authorized"] = True
    with pytest.raises(RunBundleValidationError, match="never unlock"):
        validate_run_bundle(bundle)


def test_valid_all_controls_g1_promotion() -> None:
    validate_run_bundle(_promotion("G1"))


@pytest.mark.parametrize("artifact_kind", ("GateAssessment", "GateDecision"))
def test_gate_artifact_bundle_uid_must_match_enclosing_bundle(
    artifact_kind: str,
) -> None:
    bundle = _promotion("G1")
    artifact = next(
        row for row in bundle["artifacts"] if row["kind"] == artifact_kind
    )
    artifact["properties"]["bundle_uid"] = "foreign-bundle"
    with pytest.raises(RunBundleValidationError, match="bundle UID differs"):
        validate_run_bundle(bundle)


def test_valid_g4_precursor_is_nonunlocking_and_separate() -> None:
    validate_run_bundle(_g4_precursor())


@pytest.mark.parametrize("missing", ("control", "prerequisite"))
def test_missing_control_and_prerequisite_are_refused(missing: str) -> None:
    bundle = _promotion("G1")
    bundle["source_bundles"].pop(0 if missing == "control" else -1)
    with pytest.raises(
        RunBundleValidationError,
        match="(coverage|prerequisite|invalid CONTROL_RUN source)",
    ):
        validate_run_bundle(bundle)


@pytest.mark.parametrize(("state", "decision", "ceiling"), [("REMAINS_VIABLE", "FAIL", "POST_HOC_ASSOCIATION_ONLY"), ("INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE_MEASUREMENT_NOT_READY")])
def test_control_fail_and_inconclusive_have_typed_nonunlocking_ceilings(state: str, decision: str, ceiling: str) -> None:
    bundle = _control("CF-05", "G1")
    assessment, verdict = bundle["artifacts"][-2], bundle["artifacts"][-1]
    assessment["properties"].update(assessment_state=state, applicable_claim_ceiling=ceiling)
    verdict["properties"].update(decision=decision, claim_ceiling=ceiling, ceiling_uid=CEILINGS[ceiling], unlock_authorized=False)
    validate_run_bundle(bundle)


@pytest.mark.parametrize(
    ("control_id", "ceiling"),
    [
        (row["id"], row["claim_ceiling_if_failed"])
        for row in PROJECT["control_families"]
    ],
)
def test_every_control_failure_ceiling_is_typed_and_validatable(
    control_id: str,
    ceiling: str,
) -> None:
    bundle = _control(control_id, "G6")
    _set_control_state(bundle, "REMAINS_VIABLE")
    decision = next(
        row for row in bundle["artifacts"] if row["kind"] == "ClaimDecision"
    )
    assert decision["properties"]["claim_ceiling"] == ceiling
    validate_run_bundle(bundle)


@pytest.mark.parametrize(
    ("control_state", "gate_state", "ceiling", "pass_state", "stop_state"),
    (
        (
            "REMAINS_VIABLE",
            "FAIL",
            "GATE_NOT_PASSED_NO_UNLOCK",
            "FAILED",
            "TRIGGERED",
        ),
        (
            "INCONCLUSIVE",
            "INCONCLUSIVE",
            "INCONCLUSIVE_MEASUREMENT_NOT_READY",
            "INCONCLUSIVE",
            "MEASUREMENT_OR_SOURCE_INVALID",
        ),
    ),
)
def test_gate_fail_and_inconclusive_are_typed_and_never_unlock(
    control_state: str,
    gate_state: str,
    ceiling: str,
    pass_state: str,
    stop_state: str,
) -> None:
    bundle = _promotion("G1")
    source = bundle["source_bundles"][0]
    _set_control_state(source["bundle"], control_state)
    source["canonical_sha256"] = _sha(source["bundle"])
    assessment, decision = bundle["artifacts"]
    assessment["properties"].update(
        pass_rule_state=pass_state,
        stop_rule_state=stop_state,
    )
    decision["properties"].update(
        decision=gate_state,
        claim_ceiling=ceiling,
        ceiling_uid=CEILINGS[ceiling],
        unlock_authorized=False,
    )
    validate_run_bundle(bundle)
    decision["properties"]["unlock_authorized"] = True
    with pytest.raises(RunBundleValidationError, match="ceiling or unlock"):
        validate_run_bundle(bundle)


@pytest.mark.parametrize("control_id", ("CF-13", "CF-14"))
def test_control_specific_extension_fields_fail_closed(control_id: str) -> None:
    bundle = _control(control_id, "G1")
    extension = next(
        row for row in bundle["artifacts"] if row["kind"] == "ExtensionEvidence"
    )
    schema_id = extension["properties"]["schema_id"]
    missing_field = EXTENSIONS[schema_id]["required_fields"][-1]
    extension["properties"].pop(missing_field)
    with pytest.raises(RunBundleValidationError, match="missing required fields"):
        validate_run_bundle(bundle)


def _g5_bundle() -> tuple[dict, dict[str, dict[str, dict]], dict]:
    cache: dict = {}
    member_a = {gate: _promotion(gate, "a", "scope", cache) for gate in ("G1", "G2A", "G2B", "G3", "G4")}
    member_b = {gate: _promotion(gate, "b", "scope", cache) for gate in ("G1", "G2A", "G2B", "G3", "G4")}
    bundle = _promotion("G5", "subject", "scope", cache)
    sources = [_source(x) for x in [*member_a.values(), *member_b.values(), *[row["bundle"] for row in bundle["source_bundles"]]]]
    maps = {member: {gate: item["primary_decision_uid"] for gate, item in values.items()} for member, values in {"a": member_a, "b": member_b}.items()}
    hashes = {
        member: {gate: _sha(item) for gate, item in values.items()}
        for member, values in {"a": member_a, "b": member_b}.items()
    }
    ext_values = {field: "x" for field in EXTENSIONS["G5MacroIdentificationEvidence"]["required_fields"]}
    ext_values.update(member_uid_to_gate_decision_uid_map=maps, member_uid_to_integrated_g4_decision_uid_map={member: value["G4"] for member, value in maps.items()}, member_uid_to_boundary_evidence_uid_map={"a": "boundary-a", "b": "boundary-b"}, member_uid_to_gate_source_bundle_sha256_map=hashes, member_eligibility_validation_state="PASS")
    ext_values.update(
        primary_total_effect_estimand=GATES["G5"]["primary_estimand"],
        post_treatment_mediator_rule=(
            "OBSERVE_NOT_CONDITION_FOR_PRIMARY_TOTAL_EFFECT"
        ),
        macro_identification_decision="PASS",
        fallback_ceiling_if_unmet=GATES["G5"]["fallback_claim_ceiling"],
    )
    for member in maps:
        boundary = _fill("BoundaryEvidence", bundle_uid=bundle["bundle_uid"], member_uid=member, owner_uid=f"owner-{member}", independent_owner_attestation=True, source_integrated_g4_decision_uid=maps[member]["G4"])
        bundle["artifacts"].append(_row(f"boundary-{member}", "BoundaryEvidence", **boundary))
    bundle["artifacts"].append(_row("g5-ext", "ExtensionEvidence", schema_id="G5MacroIdentificationEvidence", **ext_values))
    bundle["artifacts"][1]["properties"]["gate_extension_uids"] = ["g5-ext"]
    bundle["artifacts"][0]["properties"]["gate_extension_uids"] = ["g5-ext"]
    bundle["source_bundles"] = sources
    return bundle, {"a": member_a, "b": member_b}, ext_values


def test_valid_g5_requires_two_recursively_validated_members() -> None:
    bundle, _members, _extension = _g5_bundle()
    validate_run_bundle(bundle)


@pytest.mark.parametrize("reason", ["one_member", "precursor", "foreign_subject", "source_hash", "boundary_owner"])
def test_g5_member_lineage_failures_are_refused(reason: str) -> None:
    bundle, members, ext_values = _g5_bundle()
    maps = ext_values["member_uid_to_gate_decision_uid_map"]
    hashes = ext_values["member_uid_to_gate_source_bundle_sha256_map"]
    if reason == "one_member":
        for mapping in (
            maps,
            ext_values["member_uid_to_integrated_g4_decision_uid_map"],
            ext_values["member_uid_to_boundary_evidence_uid_map"],
            hashes,
        ):
            mapping.pop("b")
    elif reason == "precursor":
        precursor = _g4_precursor("a", "scope")
        old_uid = maps["a"]["G4"]
        maps["a"]["G4"] = precursor["primary_decision_uid"]
        ext_values["member_uid_to_integrated_g4_decision_uid_map"]["a"] = (
            precursor["primary_decision_uid"]
        )
        hashes["a"]["G4"] = _sha(precursor)
        boundary = next(
            row for row in bundle["artifacts"] if row["uid"] == "boundary-a"
        )
        boundary["properties"]["source_integrated_g4_decision_uid"] = precursor[
            "primary_decision_uid"
        ]
        bundle["source_bundles"] = [
            row
            for row in bundle["source_bundles"]
            if row["bundle"]["primary_decision_uid"] != old_uid
        ]
        bundle["source_bundles"].append(_source(precursor))
    elif reason == "foreign_subject":
        foreign = _promotion("G3", "other", "scope")
        old_uid = maps["a"]["G3"]
        maps["a"]["G3"] = foreign["primary_decision_uid"]
        hashes["a"]["G3"] = _sha(foreign)
        bundle["source_bundles"] = [
            row
            for row in bundle["source_bundles"]
            if row["bundle"]["primary_decision_uid"] != old_uid
        ]
        bundle["source_bundles"].append(_source(foreign))
    elif reason == "source_hash":
        hashes["a"]["G1"] = "0" * 64
    elif reason == "boundary_owner":
        boundary = next(
            row for row in bundle["artifacts"] if row["uid"] == "boundary-a"
        )
        boundary["properties"]["independent_owner_attestation"] = False
    with pytest.raises(RunBundleValidationError):
        validate_run_bundle(bundle)
