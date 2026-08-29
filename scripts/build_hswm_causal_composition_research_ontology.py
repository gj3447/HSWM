#!/usr/bin/env python3
"""Build the bounded HSWM causal-composition research ontology projection."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_PATH = Path("_research/causal_composition/project.v1.json")
README_PATH = Path("_research/causal_composition/README.md")
ONTOLOGY_PATH = Path(
    "ontology/identity/hswm_core/"
    "HSWM_CAUSAL_COMPOSITION_RESEARCH_ONTOLOGY.v1.json"
)
SCHEMA_VERSION = "hswm-causal-composition-research-ontology/v1"
BUNDLE_UID = (
    "sym:AbstractNode:hswm-causal-composition-research-ontology-2026-08-29"
)
PROGRAM_UID = "sym:ResearchProgram:hswm-causal-composition-research-2026-08-29"
BENCHMARK_UID = "sym:AbstractNode:hswm-causal-composition-benchmark-v1"
NONCLAIM = (
    "DESIGN_AND_KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_LEARNING_EFFICACY_"
    "SELFHOOD_CONSCIOUSNESS_PERSONHOOD_OR_UNBOUNDED_SCALE_CLOSURE"
)
FCL_UIDS = {
    "FCL-1": "sym:Concept:hswm-fractal-law-local-causal-learning",
    "FCL-2": "sym:Concept:hswm-fractal-law-composition-preservation",
    "FCL-3": "sym:Concept:hswm-fractal-law-emergent-coalition",
    "FCL-4": "sym:Concept:hswm-fractal-law-multiscale-credit",
    "FCL-5": "sym:Concept:hswm-fractal-law-topology-morphogenesis",
    "FCL-6": "sym:Concept:hswm-fractal-law-world-self-co-model",
    "FCL-7": "sym:Concept:hswm-fractal-law-diachronic-continuity",
    "FCL-8": "sym:Concept:hswm-fractal-law-hswm-of-hswms",
}
GATE_UIDS = {
    "G0": "sym:Hypothesis:hswm-meta-g0-measurement-integrity",
    "G1": "sym:Hypothesis:hswm-meta-g1-local-causal-rung",
    "G2A": "sym:Hypothesis:hswm-meta-g2a-counterfactual-credit",
    "G2B": "sym:Hypothesis:hswm-meta-g2b-dynamic-nary-coalition",
    "G3": "sym:Hypothesis:hswm-meta-g3-morphogenesis-recovery",
    "G4": "sym:Hypothesis:hswm-meta-g4-world-self-continuity",
    "G5": "sym:Hypothesis:hswm-meta-g5-two-scale-composition",
    "G6": "sym:Hypothesis:hswm-meta-g6-replication-scale-stress",
}
CONTROL_UIDS = {
    "CF-01": "sym:Hypothesis:hswm-control-cf01-model-compute-null",
    "CF-02": "sym:Hypothesis:hswm-control-cf02-retrieval-null",
    "CF-03": "sym:Hypothesis:hswm-control-cf03-fixed-orchestration-null",
    "CF-04": "sym:Hypothesis:hswm-control-cf04-hypergraph-representation-null",
    "CF-05": "sym:Hypothesis:hswm-control-cf05-sham-revision-null",
    "CF-06": "sym:Hypothesis:hswm-control-cf06-credit-attribution-null",
    "CF-07": "sym:Hypothesis:hswm-control-cf07-outcome-leakage-null",
    "CF-08": "sym:Hypothesis:hswm-control-cf08-hidden-burden-null",
    "CF-09": "sym:Hypothesis:hswm-control-cf09-instrument-validity-null",
    "CF-10": "sym:Hypothesis:hswm-control-cf10-lineage-theatre-null",
    "CF-11": "sym:Hypothesis:hswm-control-cf11-topology-null",
    "CF-12": "sym:Hypothesis:hswm-control-cf12-composition-illusion-null",
    "CF-13": "sym:Hypothesis:hswm-control-cf13-selection-holdout-null",
    "CF-14": "sym:Hypothesis:hswm-control-cf14-authority-invariant-null",
}
ALT_UIDS = {
    control_id: f"sym:Concept:hswm-alternative-{control_id.lower()}"
    for control_id in CONTROL_UIDS
}
AXIS_UIDS = {
    axis: f"sym:Concept:hswm-confound-axis-{axis.lower().replace('_', '-')}"
    for axis in (
        "RESOURCE",
        "INFORMATION",
        "DECISION_AUTHORITY",
        "STATE",
        "MEASUREMENT",
        "SCALE",
    )
}
CEILING_UIDS = {
    "MEASUREMENT_READY": "sym:Concept:hswm-claim-ceiling-measurement-ready",
    "LOCAL_CAUSAL_REVISION_UNDER_DECLARED_TASK": (
        "sym:Concept:hswm-claim-ceiling-local-causal-revision"
    ),
    "BOUNDED_COUNTERFACTUAL_CREDIT": (
        "sym:Concept:hswm-claim-ceiling-bounded-counterfactual-credit"
    ),
    "BOUNDED_DYNAMIC_NARY_COORDINATION": (
        "sym:Concept:hswm-claim-ceiling-bounded-dynamic-nary-coordination"
    ),
    "BOUNDED_OUTCOME_LINKED_MORPHOGENESIS": (
        "sym:Concept:hswm-claim-ceiling-bounded-morphogenesis"
    ),
    "BOUNDED_WORLD_SELF_CONTINUITY": (
        "sym:Concept:hswm-claim-ceiling-bounded-world-self-continuity"
    ),
    "WORLD_SELF_CONTINUITY_COMPONENT_SIGNAL_ONLY": (
        "sym:Concept:hswm-claim-ceiling-world-self-component-signal"
    ),
    "TWO_SCALE_BOUNDED_CAUSAL_COMPOSITION": (
        "sym:Concept:hswm-claim-ceiling-two-scale-causal-composition"
    ),
    "BOUNDED_REPLICATED_SCALING": (
        "sym:Concept:hswm-claim-ceiling-bounded-replicated-scaling"
    ),
    "HIERARCHICAL_COORDINATION_WITHOUT_MACRO_CAUSAL_IDENTIFICATION": (
        "sym:Concept:hswm-claim-ceiling-hierarchical-without-macro-causality"
    ),
    "MODEL_CONDITIONED_PERFORMANCE_ONLY": "sym:Concept:hswm-claim-ceiling-model-conditioned-performance",
    "RETRIEVAL_AUGMENTED_AGENT_RESULT": "sym:Concept:hswm-claim-ceiling-retrieval-agent-result",
    "CENTRALLY_ORCHESTRATED_MULTI_AGENT_RESULT": "sym:Concept:hswm-claim-ceiling-central-orchestration",
    "REPRESENTATIONAL_EQUIVALENCE_OR_UNRESOLVED": "sym:Concept:hswm-claim-ceiling-representation-unresolved",
    "POST_HOC_ASSOCIATION_ONLY": "sym:Concept:hswm-claim-ceiling-post-hoc-association",
    "WHOLE_SYSTEM_OUTCOME_ONLY": "sym:Concept:hswm-claim-ceiling-whole-system-outcome",
    "UNTRUSTED_EVALUATION_ONLY": "sym:Concept:hswm-claim-ceiling-untrusted-evaluation",
    "LOCAL_QUALITY_GAIN_WITH_UNKNOWN_SYSTEM_COST": "sym:Concept:hswm-claim-ceiling-local-quality-unknown-cost",
    "INSTRUMENT_VALIDATION_ONLY": "sym:Concept:hswm-claim-ceiling-instrument-validation",
    "STATE_PERSISTENCE_ONLY": "sym:Concept:hswm-claim-ceiling-state-persistence",
    "DYNAMIC_EXECUTION_ONLY": "sym:Concept:hswm-claim-ceiling-dynamic-execution",
    "MULTI_AGENT_OR_HIERARCHICAL_SYSTEM_ONLY": "sym:Concept:hswm-claim-ceiling-multi-agent-hierarchy",
    "EXPLORATORY_SIGNAL_ONLY": "sym:Concept:hswm-claim-ceiling-exploratory-signal",
    "FUNCTIONAL_MULTI_AGENT_RESULT_WITHOUT_HSWM_AUTHORITY_CLOSURE": "sym:Concept:hswm-claim-ceiling-functional-without-authority-closure",
    "INCONCLUSIVE_MEASUREMENT_NOT_READY": "sym:Concept:hswm-claim-ceiling-inconclusive-measurement-not-ready",
    "CONTROL_ALTERNATIVE_BOUNDED_WITHIN_SCOPE": "sym:Concept:hswm-claim-ceiling-control-bounded-within-scope",
    "GATE_NOT_PASSED_NO_UNLOCK": "sym:Concept:hswm-claim-ceiling-gate-not-passed",
}
RULE_UIDS = {
    "MR-01": "sym:Concept:hswm-meta-rule-target-evidence-separation",
    "MR-02": "sym:Concept:hswm-meta-rule-definition-instance-separation",
    "MR-03": "sym:Concept:hswm-meta-rule-one-primary-intervention",
    "MR-04": "sym:Concept:hswm-meta-rule-no-downstream-rescue",
    "MR-05": "sym:Concept:hswm-meta-rule-burden-yield-accounting",
}
RUN_ARTIFACT_UIDS = {
    "ControlInstance": "sym:Concept:hswm-run-artifact-control-instance",
    "MatchedBudget": "sym:Concept:hswm-run-artifact-matched-budget",
    "PreOutcomeSeal": "sym:Concept:hswm-run-artifact-pre-outcome-seal",
    "OutcomeSource": "sym:Concept:hswm-run-artifact-outcome-source",
    "InstrumentCalibration": "sym:Concept:hswm-run-artifact-instrument-calibration",
    "ObservedResult": "sym:Concept:hswm-run-artifact-observed-result",
    "ControlAssessment": "sym:Concept:hswm-run-artifact-control-assessment",
    "ClaimDecision": "sym:Concept:hswm-run-artifact-claim-decision",
    "GateAssessment": "sym:Concept:hswm-run-artifact-gate-assessment",
    "GateDecision": "sym:Concept:hswm-run-artifact-gate-decision",
    "BoundaryEvidence": "sym:Concept:hswm-run-artifact-boundary-evidence",
}
EXTENSION_UIDS = {
    "CF08LifecycleCostEvidence": "sym:Concept:hswm-run-extension-cf08-lifecycle-cost",
    "CF13SelectionEvidence": "sym:Concept:hswm-run-extension-cf13-selection",
    "CF14AuthorityEvidence": "sym:Concept:hswm-run-extension-cf14-authority",
    "G4PrecursorDecisionEvidence": "sym:Concept:hswm-run-extension-g4-precursor",
    "G5MacroIdentificationEvidence": "sym:Concept:hswm-run-extension-g5-macro-identification",
}
CONTROL_ARM_CLASS_UIDS = {
    "INFORMATION_MATCHED_COMPUTATIONAL_ORACLE": "sym:Concept:hswm-control-arm-information-matched-oracle",
    "PRIVILEGED_INFORMATION_ORACLE_UPPER_BOUND": "sym:Concept:hswm-control-arm-privileged-oracle-upper-bound",
    "LOSSY_PAIRWISE_DIAGNOSTIC": "sym:Concept:hswm-control-arm-lossy-pairwise-diagnostic",
    "INFORMATION_MATCHED_PAIRWISE_ENCODING": "sym:Concept:hswm-control-arm-information-matched-pairwise",
}
SOURCE_BINDING_PATHS = (
    README_PATH,
    PROJECT_PATH,
    Path("docs/canon/HSWM_CONSTITUTION_2026-08-20.md"),
    Path("docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md"),
    Path(
        "ontology/identity/human_universal_body/"
        "HSWM_HUMAN_UNIVERSAL_BODY_FRACTAL_PROJECTION.v1.json"
    ),
    Path("_research/ragnarok/README.md"),
    Path("_research/pidna/README.md"),
    Path("scripts/validate_hswm_causal_composition_run.py"),
)
ANCHORS = [
    {"uid": "sym:Concept:hswm", "name": "HSWM", "required_labels": ["Concept"]},
    {
        "uid": "sym:AbstractNode:hswm-fractal-scientific-connections-2026-08-28",
        "name": "HSWM fractal cognitive-composition scientific connection synthesis",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    *[
        {
            "uid": uid,
            "name": {
                "FCL-1": "FCL-1 local causal learning law",
                "FCL-2": "FCL-2 composition preservation law",
                "FCL-3": "FCL-3 emergent coalition law",
                "FCL-4": "FCL-4 multiscale credit law",
                "FCL-5": "FCL-5 topology morphogenesis law",
                "FCL-6": "FCL-6 world-self co-model law",
                "FCL-7": "FCL-7 diachronic continuity law",
                "FCL-8": "FCL-8 HSWM-of-HSWMs law",
            }[fcl_id],
            "required_labels": ["Concept", "EngineeringInstantiation", "Guardrail"],
        }
        for fcl_id, uid in FCL_UIDS.items()
    ],
    {
        "uid": "sym:ResearchProgram:hswm-ragnarok-research-2026-08-29",
        "name": "HSWM Ragnarok research project",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
    {
        "uid": "sym:ResearchProgram:hswm-pidna-research-2026-08-29",
        "name": "PIDNA — Pure Intelligence DNA research project",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
]


def _file_sha(path: Path) -> str:
    return sha256((ROOT / path).read_bytes()).hexdigest()


def _load_project() -> dict[str, Any]:
    value = json.loads((ROOT / PROJECT_PATH).read_text(encoding="utf-8"))
    if value.get("schema_version") != "hswm-causal-composition-research-program/v1":
        raise ValueError("unexpected causal-composition project schema")
    if value.get("uid") != PROGRAM_UID or value.get("nonclaim") != NONCLAIM:
        raise ValueError("project identity or nonclaim drifted")
    if value.get("claim_ceiling_uids") != CEILING_UIDS:
        raise ValueError("project claim-ceiling UID map drifted")
    return value


def _common(
    *,
    name: str,
    description: str,
    owner: str,
    kind: str,
    plane: str,
    state: str,
    roles: list[str],
    claim_boundary: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "authority_class": "SECONDARY_AI",
        "canonical_scope": "RESEARCH_PROJECTION_NOT_HSWM_CANON",
        "ontology_kind": kind,
        "ontology_plane": plane,
        "epistemic_state": state,
        "responsibility_owner": owner,
        "claim_boundary": claim_boundary,
        "projection_nonclaim": NONCLAIM,
        "ontology_domain": "AI",
        "record_lifecycle": "ACTIVE",
        "review_required": True,
        "semantic_roles": roles,
    }


def _node(uid: str, labels: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {"uid": uid, "labels": labels, "properties": properties}


def _relation(
    from_uid: str,
    relation_type: str,
    to_uid: str,
    scope: str,
    status: str,
    authority: str = "SECONDARY_AI",
) -> dict[str, str]:
    return {
        "from_uid": from_uid,
        "type": relation_type,
        "to_uid": to_uid,
        "authority_class": authority,
        "scope": scope,
        "status": status,
    }


def build_data() -> dict[str, Any]:
    project = _load_project()
    gates = {row["id"]: row for row in project["gates"]}
    controls = {row["id"]: row for row in project["control_families"]}
    axes = {row["id"]: row for row in project["confound_axes"]}
    rules = {row["id"]: row for row in project["metacognitive_rules"]}
    run_artifacts = {
        row["id"]: row for row in project["run_contract"]["artifact_schemas"]
    }
    extensions = {
        row["id"]: row for row in project["run_contract"]["extension_schemas"]
    }
    arm_classes = {row["id"]: row for row in project["control_arm_classes"]}
    if set(run_artifacts) != set(RUN_ARTIFACT_UIDS):
        raise ValueError("run-artifact schema kinds drifted")
    if set(extensions) != set(EXTENSION_UIDS):
        raise ValueError("run-artifact extension schema kinds drifted")
    if set(arm_classes) != set(CONTROL_ARM_CLASS_UIDS):
        raise ValueError("control-arm class kinds drifted")
    bindings = [
        {"path": path.as_posix(), "sha256": _file_sha(path)}
        for path in SOURCE_BINDING_PATHS
    ]
    nodes: list[dict[str, Any]] = []
    nodes.append(
        _node(
            BUNDLE_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name="HSWM causal-composition research ontology",
                    description=(
                        "Bounded KG projection of the ordered HSWM causal-learning "
                        "and composition gates, fourteen metacognitive control "
                        "families, run-artifact and conditional extension kinds, "
                        "control-arm classes, confound axes, claim ceilings, and "
                        "stop rules."
                    ),
                    owner="causal_composition_projection_custodian",
                    kind="ARTIFACT",
                    plane="INQUIRY",
                    state="DESIGN_SEEDED_UNJUDGED",
                    roles=[
                        "RESEARCH_BUNDLE",
                        "CONTROL_ONTOLOGY",
                        "CLAIM_BOUNDARY",
                        "FALSIFICATION_ORDER",
                    ],
                    claim_boundary=(
                        "Publication provides typed discoverability only and cannot "
                        "establish HSWM learning, cognition, efficacy, selfhood, or "
                        "scale closure."
                    ),
                ),
                "schema_version": SCHEMA_VERSION,
                "program_uid": PROGRAM_UID,
                "gate_ids": list(GATE_UIDS),
                "control_ids": list(CONTROL_UIDS),
                "run_artifact_kind_ids": list(RUN_ARTIFACT_UIDS),
                "extension_schema_ids": list(EXTENSION_UIDS),
                "control_arm_class_ids": list(CONTROL_ARM_CLASS_UIDS),
            },
        )
    )
    nodes.append(
        _node(
            PROGRAM_UID,
            ["Concept", "ResearchProgram", "ResearchArtifact"],
            {
                **_common(
                    name=project["name"],
                    description=project["canonical_role"],
                    owner="causal_composition_research_custodian",
                    kind="PLAN",
                    plane="INQUIRY",
                    state="DESIGN_SEEDED_UNJUDGED",
                    roles=[
                        "RESEARCH_PROGRAM",
                        "CAUSAL_LEARNING_SEQUENCE",
                        "FRACTAL_COMPOSITION_SEQUENCE",
                        "METACOGNITIVE_CONTROL",
                    ],
                    claim_boundary=(
                        "The program orders tests but does not establish that any "
                        "gate has passed or that HSWM is efficacious."
                    ),
                ),
                "target_identity": project["canonical_role"],
                "current_evidence": project["current_evidence"],
                "conceptual_delta": project["conceptual_delta"],
                "project_path": PROJECT_PATH.as_posix(),
                "readme_path": README_PATH.as_posix(),
                "gate_ids": list(GATE_UIDS),
                "control_ids": list(CONTROL_UIDS),
                "confound_axis_ids": list(AXIS_UIDS),
                "run_artifact_kind_ids": list(RUN_ARTIFACT_UIDS),
                "extension_schema_ids": list(EXTENSION_UIDS),
                "control_arm_class_ids": list(CONTROL_ARM_CLASS_UIDS),
            },
        )
    )
    nodes.append(
        _node(
            BENCHMARK_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name="HSWM causal composition benchmark contract",
                    description=(
                        "One bounded persistent environment and an ordered family "
                        "of causal interventions from local revision through "
                        "two-scale composition and replication."
                    ),
                    owner="causal_composition_benchmark_custodian",
                    kind="PLAN",
                    plane="INQUIRY",
                    state="PROPOSED_TEST",
                    roles=["BENCHMARK_CONTRACT", "INTERVENTION_PROGRAM", "RUN_ATOM_SEPARATION"],
                    claim_boundary=(
                        "A benchmark definition is not a run, result, passed control, "
                        "or evidence of HSWM cognition or efficacy."
                    ),
                ),
                "gate_ids": list(GATE_UIDS),
                "required_run_atoms": project["run_contract"]["separate_atom_roles"],
                "decision_states": list(project["run_contract"]["required_decisions"]),
                "immediate_gate": project["immediate_executable_target"]["gate"],
                "immediate_prerequisite": project["immediate_executable_target"]["prerequisite"],
                "instance_validator_path": project["run_contract"]["instance_validator"]["path"],
                "instance_validator_required_before_pass": project["run_contract"]["instance_validator"]["required_before_any_gate_pass"],
                "instance_validator_failure_mode": project["run_contract"]["instance_validator"]["failure_mode"],
                "instance_validator_scope": project["run_contract"]["instance_validator"]["validation_scope"],
                "evidence_bundle_schema_version": project["run_contract"]["bundle_contract"]["schema_version"],
                "evidence_bundle_kinds": project["run_contract"]["bundle_contract"]["bundle_kinds"],
                "source_bundle_binding_rule": project["run_contract"]["bundle_contract"]["canonical_source_binding"],
                "structural_integrity_boundary_status": project["run_contract"]["verification_boundaries"]["structural_integrity_not_authorship"]["status"],
                "structural_integrity_validated_now": project["run_contract"]["verification_boundaries"]["structural_integrity_not_authorship"]["validated_now"],
                "structural_integrity_not_validated_now": project["run_contract"]["verification_boundaries"]["structural_integrity_not_authorship"]["not_validated_now"],
                "external_public_promotion_requirement": project["run_contract"]["verification_boundaries"]["structural_integrity_not_authorship"]["required_for_external_public_promotion"],
                "reviewer_assessment_boundary_status": project["run_contract"]["verification_boundaries"]["reviewer_assessment_not_recomputed"]["status"],
                "reviewer_assessment_validated_now": project["run_contract"]["verification_boundaries"]["reviewer_assessment_not_recomputed"]["validated_now"],
                "reviewer_assessment_not_validated_now": project["run_contract"]["verification_boundaries"]["reviewer_assessment_not_recomputed"]["not_validated_now"],
                "automatic_scientific_promotion_requirement": project["run_contract"]["verification_boundaries"]["reviewer_assessment_not_recomputed"]["required_for_automatic_scientific_promotion"],
            },
        )
    )
    for uid, name, path, source_role in (
        (
            "sym:SourceDocument:hswm-causal-composition-readme-2026-08-29",
            "HSWM causal-composition research order source",
            README_PATH,
            "HUMAN_READABLE_RESEARCH_PROGRAM",
        ),
        (
            "sym:SourceDocument:hswm-causal-composition-project-v1-2026-08-29",
            "HSWM causal-composition machine research contract",
            PROJECT_PATH,
            "MACHINE_READABLE_RESEARCH_PROGRAM",
        ),
    ):
        nodes.append(
            _node(
                uid,
                ["AbstractNode", "SourceDocument", "ResearchArtifact"],
                {
                    **_common(
                        name=name,
                        description=(
                            "Repository source bound byte-for-byte to the bounded "
                            "causal-composition research projection."
                        ),
                        owner="causal_composition_source_record_custodian",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="SOURCE_BOUND",
                        roles=["SOURCE_RECORD", source_role],
                        claim_boundary=(
                            "Source binding establishes projection provenance, not "
                            "execution, control passage, or HSWM efficacy."
                        ),
                    ),
                    "source_path": path.as_posix(),
                    "source_sha256": _file_sha(path),
                },
            )
        )
    for gate_id, gate in gates.items():
        nodes.append(
            _node(
                GATE_UIDS[gate_id],
                ["Concept", "Hypothesis", "Guardrail"],
                {
                    **_common(
                        name=f"{gate_id} — {gate['name']}",
                        description=gate["primary_question"],
                        owner=f"causal_composition_{gate_id.lower()}_custodian",
                        kind="PLAN",
                        plane="INQUIRY",
                        state="PROPOSED_TEST",
                        roles=["RESEARCH_GATE", gate["kind"], "CLAIM_GATE"],
                        claim_boundary=(
                            f"At most {gate['claim_ceiling']} after a valid scoped "
                            "pass; no downstream or general HSWM claim follows."
                        ),
                    ),
                    "gate_id": gate_id,
                    "prerequisite_gate_ids": gate["prerequisites"],
                    "mapped_fcl_ids": gate["mapped_fcl_ids"],
                    "exact_intervention": gate["exact_intervention"],
                    "required_control_ids": gate["required_control_ids"],
                    "pass_rule": gate["pass_rule"],
                    "failure_observation": gate["fail_rule"],
                    "stop_rule": gate["stop_rule"],
                    "claim_ceiling": gate["claim_ceiling"],
                    "next_unlocks": gate["unlocks"],
                    **(
                        {
                            "precursor_claim_ceiling": gate["precursor_claim_ceiling"],
                            "precursor_gate_mode": gate["precursor_contract"]["gate_mode"],
                            "precursor_prerequisite_gate_ids": gate["precursor_contract"]["prerequisites"],
                            "precursor_allowed_targets": gate["precursor_contract"]["allowed_targets"],
                            "precursor_required_nulls": gate["precursor_contract"]["required_nulls"],
                            "precursor_forbidden_evidence_uses": gate["precursor_contract"]["forbidden_evidence_uses"],
                            "precursor_unlock_authorized": gate["precursor_contract"]["unlock_authorized"],
                            "precursor_stop_rule": gate["precursor_contract"]["stop_rule"],
                        }
                        if "precursor_claim_ceiling" in gate
                        else {}
                    ),
                    **(
                        {
                            "micro_trace_contract": gate["micro_trace_contract"],
                            "fallback_claim_ceiling": gate["fallback_claim_ceiling"],
                            "primary_estimand": gate["primary_estimand"],
                            "secondary_mediation_rule": gate["secondary_mediation_rule"],
                            "causal_comparator": gate["causal_comparator"],
                            "member_required_gate_passes": gate["member_eligibility_contract"]["required_independent_gate_passes"],
                            "member_required_evidence_uid_per_gate": gate["member_eligibility_contract"]["required_evidence_uid_per_gate"],
                            "member_required_decision_state": gate["member_eligibility_contract"]["required_decision_state"],
                            "member_required_g4_gate_mode": gate["member_eligibility_contract"]["required_g4_gate_mode"],
                            "member_required_g4_unlock_authorized": gate["member_eligibility_contract"]["required_g4_unlock_authorized"],
                            "member_required_same_lineage": gate["member_eligibility_contract"]["required_same_member_lineage"],
                            "member_required_boundaries": gate["member_eligibility_contract"]["required_independent_boundaries"],
                            "weaker_member_use": gate["member_eligibility_contract"]["weaker_member_use"],
                            "member_failure_rule": gate["member_eligibility_contract"]["failure_rule"],
                        }
                        if "micro_trace_contract" in gate
                        else {}
                    ),
                },
            )
        )
    for control_id, control in controls.items():
        nodes.append(
            _node(
                CONTROL_UIDS[control_id],
                ["Concept", "Hypothesis", "Guardrail"],
                {
                    **_common(
                        name=f"{control_id} — {control['name']}",
                        description=control["alternative_explanation"],
                        owner=f"causal_composition_{control_id.lower().replace('-', '_')}_custodian",
                        kind="CONTROL",
                        plane="INQUIRY",
                        state="PROPOSED_TEST",
                        roles=["CONTROL_FAMILY", "NEGATIVE_CONTROL", control["family"]],
                        claim_boundary=(
                            "Passing this control only bounds its named alternative "
                            "explanation in the declared run scope."
                        ),
                    ),
                    "control_id": control_id,
                    "control_family": control["family"],
                    "alternative_explanation": control["alternative_explanation"],
                    "intervention_axis_ids": control["intervention_axes"],
                    "matched_axis_ids": control["matched_axes"],
                    "preserved_factors": control["preserved_factors"],
                    "intervention": control["intervention"],
                    "primary_observables": control["primary_observables"],
                    "failure_inference": control["failure_inference"],
                    "claim_ceiling_if_failed": control["claim_ceiling_if_failed"],
                    "ragnarok_metric_ids": control["ragnarok_metric_ids"],
                    "pidna_links": control["pidna_links"],
                    "mapped_fcl_ids": control["mapped_fcl_ids"],
                    **(
                        {
                            "cost_scopes": control["cost_scopes"],
                            "amortization_required": control["amortization_required"],
                        }
                        if "cost_scopes" in control
                        else {}
                    ),
                },
            )
        )
        nodes.append(
            _node(
                ALT_UIDS[control_id],
                ["Concept", "Hypothesis", "Guardrail"],
                {
                    **_common(
                        name=f"Alternative explanation for {control_id}",
                        description=control["alternative_explanation"],
                        owner="causal_composition_alternative_explanation_custodian",
                        kind="HYPOTHESIS",
                        plane="INQUIRY",
                        state="ALTERNATIVE_EXPLANATION",
                        roles=["ALTERNATIVE_EXPLANATION", "CONFOUND_CANDIDATE"],
                        claim_boundary=(
                            "This is a rival explanation to test, not an established "
                            "cause or evidence against HSWM."
                        ),
                    ),
                    "alternative_id": f"ALT-{control_id}",
                    "control_id": control_id,
                    "failure_inference": control["failure_inference"],
                },
            )
        )
    for axis_id, axis in axes.items():
        nodes.append(
            _node(
                AXIS_UIDS[axis_id],
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"Confound axis — {axis_id}",
                        description=axis["definition"],
                        owner="causal_composition_confound_axis_custodian",
                        kind="CONCEPT",
                        plane="INQUIRY",
                        state="MEASUREMENT_CONTRACT",
                        roles=["CONFOUND_AXIS", "MATCHING_OBLIGATION"],
                        claim_boundary=(
                            "Declaring an axis does not establish that a run matched it."
                        ),
                    ),
                    "axis_id": axis_id,
                    "required_declaration": axis["required_declaration"],
                },
            )
        )
    forbidden_by_ceiling = {
        "MEASUREMENT_READY": ["learning", "efficacy", "cognition"],
        "LOCAL_CAUSAL_REVISION_UNDER_DECLARED_TASK": ["general_learning", "world_model", "fractal_composition"],
        "BOUNDED_COUNTERFACTUAL_CREDIT": ["stable_coalition", "topology_learning", "macro_agent"],
        "BOUNDED_DYNAMIC_NARY_COORDINATION": ["selfhood", "topology_morphogenesis", "scale_closure"],
        "BOUNDED_OUTCOME_LINKED_MORPHOGENESIS": ["world_self_model", "continuity", "scale_closure"],
        "BOUNDED_WORLD_SELF_CONTINUITY": ["consciousness", "personhood", "composite_closure"],
        "WORLD_SELF_CONTINUITY_COMPONENT_SIGNAL_ONLY": ["integrated_world_self", "topology_morphogenesis", "composition_unlock"],
        "TWO_SCALE_BOUNDED_CAUSAL_COMPOSITION": ["social_generalization", "infinite_fractal", "consciousness"],
        "BOUNDED_REPLICATED_SCALING": ["untested_scales", "infinite_fractal", "social_legitimacy", "consciousness"],
        "HIERARCHICAL_COORDINATION_WITHOUT_MACRO_CAUSAL_IDENTIFICATION": ["macro_causality", "same_type_scale_closure", "fractal_cognition"],
    }
    gate_pass_ceiling_ids = {gate["claim_ceiling"] for gate in gates.values()}
    control_failure_ceiling_ids = {
        control["claim_ceiling_if_failed"] for control in controls.values()
    }
    for ceiling, uid in CEILING_UIDS.items():
        ceiling_role = (
            "GATE_PASS_CEILING"
            if ceiling in gate_pass_ceiling_ids
            else "CONTROL_FAILURE_CEILING"
            if ceiling in control_failure_ceiling_ids
            else "INCONCLUSIVE_CEILING"
            if ceiling == "INCONCLUSIVE_MEASUREMENT_NOT_READY"
            else "CONTROL_PASS_CEILING"
            if ceiling == "CONTROL_ALTERNATIVE_BOUNDED_WITHIN_SCOPE"
            else "GATE_FAILURE_CEILING"
            if ceiling == "GATE_NOT_PASSED_NO_UNLOCK"
            else "PRECURSOR_OR_FALLBACK_CEILING"
        )
        nodes.append(
            _node(
                uid,
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"Claim ceiling — {ceiling}",
                        description=(
                            "Maximum internally admissible bounded claim after a "
                            "structurally valid decision under the declared scope and "
                            "controls. External or public use remains separately "
                            "blocked pending authenticated receipts; automatic "
                            "promotion also requires deterministic recalculation "
                            "from immutable outcome artifacts."
                        ),
                        owner="causal_composition_claim_ceiling_custodian",
                        kind="GUARDRAIL",
                        plane="INQUIRY",
                        state="CLAIM_BOUNDARY",
                        roles=["CLAIM_CEILING", "OVERCLAIM_GUARD"],
                        claim_boundary=(
                            "A ceiling limits a claim and does not assert that the "
                            "linked gate has passed."
                        ),
                    ),
                    "ceiling_id": ceiling,
                    "ceiling_role": ceiling_role,
                    "allowed_claim": ceiling,
                    "external_public_use_status": project["run_contract"]["verification_boundaries"]["structural_integrity_not_authorship"]["status"],
                    "automatic_promotion_status": project["run_contract"]["verification_boundaries"]["reviewer_assessment_not_recomputed"]["status"],
                    "forbidden_claims": forbidden_by_ceiling.get(
                        ceiling,
                        [
                            "general_hswm_efficacy",
                            "downstream_gate_unlock",
                            "consciousness",
                            "unbounded_scale_closure",
                        ],
                    ),
                },
            )
        )
    for rule_id, rule in rules.items():
        nodes.append(
            _node(
                RULE_UIDS[rule_id],
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{rule_id} — metacognitive research rule",
                        description=rule["rule"],
                        owner="causal_composition_metacognitive_rule_custodian",
                        kind="GUARDRAIL",
                        plane="INQUIRY",
                        state="RESEARCH_CONTRACT",
                        roles=["METACOGNITIVE_RULE", "SELF_DECEPTION_GUARD"],
                        claim_boundary=(
                            "A metacognitive rule constrains interpretation; it is "
                            "not itself a scientific result."
                        ),
                    ),
                    "rule_id": rule_id,
                    "violation_signal": rule["violation_signal"],
                    "required_response": rule["required_response"],
                },
            )
        )
    for artifact_id, artifact in run_artifacts.items():
        nodes.append(
            _node(
                RUN_ARTIFACT_UIDS[artifact_id],
                ["Concept", "ResearchArtifact", "Guardrail"],
                {
                    **_common(
                        name=f"Run artifact kind — {artifact_id}",
                        description=artifact["purpose"],
                        owner="causal_composition_run_artifact_schema_custodian",
                        kind="CONCEPT",
                        plane="INQUIRY",
                        state="SCHEMA_DEFINITION",
                        roles=[
                            "RUN_ARTIFACT_KIND",
                            "EVIDENCE_INSTANCE_SCHEMA",
                            artifact_id.upper(),
                        ],
                        claim_boundary=(
                            "This node defines a future run-artifact kind; it is not "
                            "an executed instance, observation, inference, decision, "
                            "or HSWM result."
                        ),
                    ),
                    "artifact_kind_id": artifact_id,
                    "required_fields": artifact["required_fields"],
                },
            )
        )
    for extension_id, extension in extensions.items():
        nodes.append(
            _node(
                EXTENSION_UIDS[extension_id],
                ["Concept", "ResearchArtifact", "Guardrail"],
                {
                    **_common(
                        name=f"Run evidence extension — {extension_id}",
                        description=(
                            "Conditional evidence fields required when the linked "
                            "control family or gate is executed."
                        ),
                        owner="causal_composition_run_extension_schema_custodian",
                        kind="CONCEPT",
                        plane="INQUIRY",
                        state="SCHEMA_DEFINITION",
                        roles=[
                            "RUN_ARTIFACT_EXTENSION_SCHEMA",
                            "CONDITIONAL_EVIDENCE_SCHEMA",
                        ],
                        claim_boundary=(
                            "This node defines required fields only; it is not an "
                            "executed control, observed evidence, or gate decision."
                        ),
                    ),
                    "extension_schema_id": extension_id,
                    "applies_to_id": extension["applies_to_id"],
                    "required_fields": extension["required_fields"],
                    **(
                        {"semantic_constraints": extension["semantic_constraints"]}
                        if "semantic_constraints" in extension
                        else {}
                    ),
                },
            )
        )
    for arm_id, arm in arm_classes.items():
        nodes.append(
            _node(
                CONTROL_ARM_CLASS_UIDS[arm_id],
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"Control arm class — {arm_id}",
                        description=arm["purpose"],
                        owner="causal_composition_control_arm_class_custodian",
                        kind="CONTROL",
                        plane="INQUIRY",
                        state="CONTROL_ARM_DEFINITION",
                        roles=["CONTROL_ARM_CLASS", "RANKING_ELIGIBILITY_RULE"],
                        claim_boundary=(
                            "This class defines comparator eligibility and does not "
                            "instantiate an arm or establish a causal result."
                        ),
                    ),
                    "arm_class_id": arm_id,
                    "control_id": arm["control_id"],
                    "eligible_for_causal_ranking": arm["eligible_for_causal_ranking"],
                    "information_contract": arm["information_contract"],
                },
            )
        )

    source_uids = (
        "sym:SourceDocument:hswm-causal-composition-readme-2026-08-29",
        "sym:SourceDocument:hswm-causal-composition-project-v1-2026-08-29",
    )
    relations: list[dict[str, str]] = []
    for source_uid in source_uids:
        relations.append(_relation(BUNDLE_UID, "HAS_SOURCE", source_uid, "PROJECTION_SOURCE", "BOUND", "SYSTEM_DERIVED"))
        relations.append(_relation(PROGRAM_UID, "HAS_SOURCE", source_uid, "RESEARCH_SOURCE", "BOUND", "SYSTEM_DERIVED"))
    relations.extend(
        (
            _relation(BUNDLE_UID, "HAS_CONCEPT", PROGRAM_UID, "PROJECTION_ROOT", "ACTIVE", "SYSTEM_DERIVED"),
            _relation(BUNDLE_UID, "HAS_CONCEPT", BENCHMARK_UID, "PROJECTION_ROOT", "ACTIVE", "SYSTEM_DERIVED"),
            _relation(PROGRAM_UID, "HAS_CONCEPT", BENCHMARK_UID, "RESEARCH_PROGRAM", "PROPOSED"),
            _relation(
                PROGRAM_UID,
                "SPECULATIVE_LINK",
                "sym:Concept:hswm",
                "TARGET_IDENTITY",
                "RESEARCH_DESIGN_ONLY",
            ),
            _relation(
                PROGRAM_UID,
                "HAS_SOURCE",
                "sym:AbstractNode:hswm-fractal-scientific-connections-2026-08-28",
                "SCIENTIFIC_CONNECTION_SOURCE",
                "BOUND_REFERENCE",
            ),
        )
    )
    for uid in (
        *GATE_UIDS.values(),
        *CONTROL_UIDS.values(),
        *AXIS_UIDS.values(),
        *CEILING_UIDS.values(),
        *RULE_UIDS.values(),
        *RUN_ARTIFACT_UIDS.values(),
        *EXTENSION_UIDS.values(),
        *CONTROL_ARM_CLASS_UIDS.values(),
    ):
        relations.append(_relation(PROGRAM_UID, "HAS_CONCEPT", uid, "RESEARCH_PROGRAM", "PROPOSED"))
    for uid in RUN_ARTIFACT_UIDS.values():
        relations.append(
            _relation(
                BENCHMARK_UID,
                "REQUIRES",
                uid,
                "RUN_ARTIFACT_SCHEMA",
                "REQUIRED",
            )
        )
    for uid in (*EXTENSION_UIDS.values(), *CONTROL_ARM_CLASS_UIDS.values()):
        relations.append(
            _relation(
                BENCHMARK_UID,
                "HAS_CONCEPT",
                uid,
                "CONDITIONAL_BENCHMARK_SCHEMA",
                "PROPOSED",
            )
        )
    for source_kind, target_kind in (
        ("ControlInstance", "MatchedBudget"),
        ("ControlInstance", "PreOutcomeSeal"),
        ("ObservedResult", "OutcomeSource"),
        ("ObservedResult", "InstrumentCalibration"),
        ("ObservedResult", "PreOutcomeSeal"),
        ("ControlAssessment", "ObservedResult"),
        ("ClaimDecision", "ControlAssessment"),
        ("GateAssessment", "ClaimDecision"),
        ("GateDecision", "GateAssessment"),
    ):
        relations.append(
            _relation(
                RUN_ARTIFACT_UIDS[source_kind],
                "REQUIRES",
                RUN_ARTIFACT_UIDS[target_kind],
                "RUN_ARTIFACT_DEPENDENCY",
                "REQUIRED",
            )
        )
    extension_base_dependencies = {
        "CF08LifecycleCostEvidence": ("MatchedBudget", "ObservedResult"),
        "CF13SelectionEvidence": (
            "ControlInstance",
            "PreOutcomeSeal",
            "ObservedResult",
            "ClaimDecision",
        ),
        "CF14AuthorityEvidence": (
            "ControlInstance",
            "ObservedResult",
            "ClaimDecision",
        ),
        "G4PrecursorDecisionEvidence": (
            "GateAssessment",
            "GateDecision",
        ),
        "G5MacroIdentificationEvidence": (
            "GateAssessment",
            "GateDecision",
            "BoundaryEvidence",
        ),
    }
    for extension_id, extension in extensions.items():
        applies_to_id = extension["applies_to_id"]
        owner_uid = (
            CONTROL_UIDS[applies_to_id]
            if applies_to_id in CONTROL_UIDS
            else GATE_UIDS[applies_to_id]
        )
        relations.append(
            _relation(
                owner_uid,
                "REQUIRES",
                EXTENSION_UIDS[extension_id],
                "CONDITIONAL_EVIDENCE_SCHEMA",
                "REQUIRED_WHEN_EXECUTED",
            )
        )
        for artifact_id in extension_base_dependencies[extension_id]:
            relations.append(
                _relation(
                    EXTENSION_UIDS[extension_id],
                    "REQUIRES",
                    RUN_ARTIFACT_UIDS[artifact_id],
                    "EXTENDS_RUN_ARTIFACT",
                    "REQUIRED",
                )
            )
    for arm_id, arm in arm_classes.items():
        relations.append(
            _relation(
                CONTROL_UIDS[arm["control_id"]],
                "HAS_CONCEPT",
                CONTROL_ARM_CLASS_UIDS[arm_id],
                "CONTROL_ARM_CLASS",
                "PROPOSED",
            )
        )
    for fcl_uid in FCL_UIDS.values():
        relations.append(_relation(PROGRAM_UID, "PRESERVES", fcl_uid, "FCL_TARGET_CONTRACT", "TARGET_ONLY"))
    for external_program in (
        "sym:ResearchProgram:hswm-ragnarok-research-2026-08-29",
        "sym:ResearchProgram:hswm-pidna-research-2026-08-29",
    ):
        relations.append(_relation(PROGRAM_UID, "SPECULATIVE_LINK", external_program, "RESEARCH_PROGRAM_ALIGNMENT", "WORKING_HYPOTHESIS"))
    for gate_id, gate in gates.items():
        gate_uid = GATE_UIDS[gate_id]
        relations.append(_relation(BENCHMARK_UID, "TESTS", gate_uid, "GATE_BENCHMARK", "PROPOSED_TEST"))
        for prerequisite in gate["prerequisites"]:
            relations.append(_relation(gate_uid, "REQUIRES", GATE_UIDS[prerequisite], "GATE_DEPENDENCY", "REQUIRED"))
        for fcl_id in gate["mapped_fcl_ids"]:
            relations.append(_relation(gate_uid, "SPECULATIVE_LINK", FCL_UIDS[fcl_id], "FCL_GATE_MAPPING", "PROPOSED_TEST"))
        relations.append(_relation(gate_uid, "HAS_CONCEPT", CEILING_UIDS[gate["claim_ceiling"]], "CLAIM_BOUNDARY", "REQUIRED"))
        if "precursor_claim_ceiling" in gate:
            relations.append(
                _relation(
                    gate_uid,
                    "HAS_CONCEPT",
                    CEILING_UIDS[gate["precursor_claim_ceiling"]],
                    "PRECURSOR_CLAIM_BOUNDARY",
                    "REQUIRED_FOR_PRECURSOR",
                )
            )
        if "fallback_claim_ceiling" in gate:
            relations.append(
                _relation(
                    gate_uid,
                    "HAS_CONCEPT",
                    CEILING_UIDS[gate["fallback_claim_ceiling"]],
                    "FALLBACK_CLAIM_BOUNDARY",
                    "REQUIRED_ON_IDENTIFICATION_FAILURE",
                )
            )
        for control_id in gate["required_control_ids"]:
            relations.append(_relation(gate_uid, "REQUIRES", CONTROL_UIDS[control_id], "CONTROL_REQUIREMENT", "REQUIRED"))
    for control_id, control in controls.items():
        control_uid = CONTROL_UIDS[control_id]
        relations.append(_relation(control_uid, "TARGETS", ALT_UIDS[control_id], "ALTERNATIVE_EXPLANATION", "PROPOSED_TEST"))
        relations.append(
            _relation(
                control_uid,
                "HAS_CONCEPT",
                CEILING_UIDS[control["claim_ceiling_if_failed"]],
                "CONTROL_FAILURE_CLAIM_BOUNDARY",
                "REQUIRED_ON_CONTROL_FAILURE",
            )
        )
        for axis_id in control["matched_axes"]:
            relations.append(_relation(control_uid, "PRESERVES", AXIS_UIDS[axis_id], "MATCHED_CONFOUND_AXIS", "REQUIRED"))
        for fcl_id in control["mapped_fcl_ids"]:
            relations.append(_relation(control_uid, "SPECULATIVE_LINK", FCL_UIDS[fcl_id], "FCL_CONTROL_MAPPING", "PROPOSED_TEST"))
    relations.sort(key=lambda row: (row["from_uid"], row["type"], row["to_uid"]))
    category_counts = {
        "gates": len(GATE_UIDS),
        "control_families": len(CONTROL_UIDS),
        "alternative_explanations": len(ALT_UIDS),
        "confound_axes": len(AXIS_UIDS),
        "claim_ceilings": len(CEILING_UIDS),
        "metacognitive_rules": len(RULE_UIDS),
        "source_records": len(source_uids),
        "run_artifact_kinds": len(RUN_ARTIFACT_UIDS),
        "run_artifact_extension_schemas": len(EXTENSION_UIDS),
        "control_arm_classes": len(CONTROL_ARM_CLASS_UIDS),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_uid": BUNDLE_UID,
        "status": "DESIGN_SEEDED_SCIENTIFICALLY_CONNECTED_INTEGRATED_CLAIM_UNJUDGED",
        "nonclaim": NONCLAIM,
        "authority_boundary": (
            "FCL-1 through FCL-8 and HSWM target identity remain USER_PRIMARY; "
            "gate order, controls, confound axes, ceilings, tests, and this KG "
            "projection are SECONDARY_AI proposed research design."
        ),
        "artifact_bindings": bindings,
        "expected_counts": {
            "nodes": len(nodes),
            "anchors": len(ANCHORS),
            "relations": len(relations),
            **category_counts,
        },
        "anchors": ANCHORS,
        "nodes": nodes,
        "relations": relations,
    }


def encoded_data(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / ONTOLOGY_PATH)
    args = parser.parse_args()
    payload = encoded_data(build_data())
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            raise SystemExit("causal-composition ontology projection drifted")
        print(json.dumps({"status": "MATCH", "path": str(args.output)}, sort_keys=True))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "status": "BUILT",
                "path": str(args.output),
                "sha256": sha256(payload).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
