#!/usr/bin/env python3
"""Build the bounded HSWM adaptive-research strategy KG projection."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path(
    "docs/canon/sources/"
    "USER_PRIMARY_HSWM_TARGET_FIXED_METHODS_ADAPTIVE_2026-08-30.txt"
)
CANON_PATH = Path("docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md")
METHODOLOGY_PATH = Path(
    "docs/research/HSWM_ADAPTIVE_REALIZATION_METHODOLOGY_2026-08-30.md"
)
ONTOLOGY_PATH = Path(
    "ontology/identity/hswm_core/"
    "HSWM_ADAPTIVE_RESEARCH_STRATEGY_ONTOLOGY.v1.json"
)
SOURCE_BINDING_PATHS = (SOURCE_PATH, CANON_PATH, METHODOLOGY_PATH)

SCHEMA_VERSION = "hswm-adaptive-research-strategy-ontology/v1"
BUNDLE_UID = "sym:AbstractNode:hswm-adaptive-research-strategy-ontology-2026-08-30"
PROGRAM_UID = "sym:ResearchProgram:hswm-adaptive-realization-program-2026-08-30"
COMMITMENT_UID = "sym:Concept:hswm-target-persistence-adaptive-method-commitment"
STATUS = "TARGET_IDENTITY_FIXED_METHODS_ADAPTIVE_SCIENTIFICALLY_UNJUDGED"
NONCLAIM = (
    "TARGET_AND_KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_LEARNING_EFFICACY_"
    "CONSCIOUSNESS_PERSONHOOD_OR_SCALE_CLOSURE"
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
FCL_NAMES = {
    "FCL-1": "FCL-1 local causal learning law",
    "FCL-2": "FCL-2 composition preservation law",
    "FCL-3": "FCL-3 emergent coalition law",
    "FCL-4": "FCL-4 multiscale credit law",
    "FCL-5": "FCL-5 topology morphogenesis law",
    "FCL-6": "FCL-6 world-self co-model law",
    "FCL-7": "FCL-7 diachronic continuity law",
    "FCL-8": "FCL-8 HSWM-of-HSWMs law",
}

TARGET_INVARIANTS = {
    "TI-1": {
        "uid": "sym:Concept:hswm-adaptive-ti1-one-system-target",
        "name": "TI-1 — one-system HSWM target identity",
        "description": (
            "Preserve one token-native LLM-function macro-neural HSWM rather than "
            "reducing the target to a memory, KG, harness, workflow, or substrate."
        ),
        "fcl_ids": [],
        "authority": "USER_PRIMARY_TARGET_DIRECTION",
    },
    "TI-2": {
        "uid": "sym:Concept:hswm-adaptive-ti2-unified-evolving-hypergraph",
        "name": "TI-2 — unified evolving hypergraph roles",
        "description": (
            "Preserve the target in which one evolving canonical hypergraph plays "
            "living-harness, world/self-model, and continuous-learner roles."
        ),
        "fcl_ids": ["FCL-6", "FCL-7"],
        "authority": "USER_PRIMARY_TARGET_WITH_SECONDARY_FORMALIZATION",
    },
    "TI-3": {
        "uid": "sym:Concept:hswm-adaptive-ti3-local-causal-closure",
        "name": "TI-3 — outcome-bound local causal closure",
        "description": (
            "Preserve the target recurrence from independent outcome through credit "
            "and owner/Permit-valid canonical revision to changed fresh behavior."
        ),
        "fcl_ids": ["FCL-1", "FCL-4"],
        "authority": "USER_PRIMARY_FCL_WITH_SECONDARY_FORMALIZATION",
    },
    "TI-4": {
        "uid": "sym:Concept:hswm-adaptive-ti4-same-type-fractal-composition",
        "name": "TI-4 — same-type fractal HSWM composition",
        "description": (
            "Preserve cognition-bearing HSWMs as composable cells whose composite "
            "again satisfies Step, Learn, Inv, Permit, and identity-learning lineage."
        ),
        "fcl_ids": list(FCL_UIDS),
        "authority": "USER_PRIMARY_FRACTAL_TARGET_WITH_SECONDARY_FORMALIZATION",
    },
    "TI-5": {
        "uid": "sym:Concept:hswm-adaptive-ti5-difference-rights-lineage",
        "name": "TI-5 — difference, rights, and lineage preservation",
        "description": (
            "Preserve member addressability, provenance, responsibility, permission, "
            "consent, exit, rollback, and recovery across composition and rerouting."
        ),
        "fcl_ids": ["FCL-2", "FCL-5", "FCL-7", "FCL-8"],
        "authority": "MIXED_CANONICAL_TARGET_AND_SECONDARY_OPERATIONALIZATION",
    },
}

MECHANISM_FAMILIES = {
    "MF-1": ("outcome-credit", "Outcome source and causal-credit estimators."),
    "MF-2": (
        "revision-admission",
        "Canonical revision proposal, owner/Permit admission, compilation, and mediation algorithms.",
    ),
    "MF-3": ("memory-experience", "Memory, retrieval, reflection, lesson, and skill substrates."),
    "MF-4": (
        "coalition-hyperedge",
        "Coalition ignition, role assignment, and role-bearing n-ary interaction algorithms.",
    ),
    "MF-5": (
        "topology-morphogenesis",
        "Topology growth, prune, split, merge, specialization, repair, and recovery rules.",
    ),
    "MF-6": (
        "world-self-continuity",
        "World/self representation, lineage, migration, fork, merge, and recovery mechanisms.",
    ),
    "MF-7": (
        "composition-boundary",
        "Typed composition, macro-state, multiscale credit, and alternative boundary algorithms.",
    ),
    "MF-8": (
        "runtime-model-backend",
        "Foundation model, tokenizer, graph engine, store, runtime, and deployment choices.",
    ),
    "MF-9": (
        "method-testbed",
        "Benchmark, task, simulator, evaluator, estimator, gate ordering, and replication method.",
    ),
}

DISPOSITION_STATES = {
    "DRAFT": "Unsealed candidate auxiliary hypothesis.",
    "PREREGISTERED": "Prospective mechanism and falsification contract are sealed.",
    "TESTING": "The declared mechanism is under an active bounded intervention.",
    "SUPPORTED_WITHIN_SCOPE": "The bounded mechanism passed its declared contract; no broader inference follows.",
    "RED_WITHIN_SCOPE": "The exact mechanism family failed a valid declared contract in scope.",
    "UNDERDETERMINED": "Instrument, task, leakage, or identification failure prevents an efficacy verdict.",
    "RETIRED_WITH_EVIDENCE_PRESERVED": "The failed path is inactive while all negative evidence remains addressable.",
    "REROUTE_PROPOSED": "A successor mechanism with explicit delta and same-or-stronger controls is proposed.",
}

GUARDRAILS = {
    "RG-1": (
        "sym:Concept:hswm-adaptive-guard-falsification-contract",
        "Sealed falsification contract",
        "Metrics, thresholds, baselines, holdouts, budgets, stopping rules, and claim ceilings are fixed before outcome inspection.",
    ),
    "RG-2": (
        "sym:Concept:hswm-adaptive-guard-evidence-lineage",
        "Append-only failure evidence lineage",
        "RED, invalid, inconclusive, cost, and side-effect records remain addressable across every successor route.",
    ),
    "RG-3": (
        "sym:Concept:hswm-adaptive-guard-reroute-transaction",
        "Lineage-preserving reroute transaction",
        "Every reroute names the failed auxiliary, triggering evidence, preserved target invariants, conceptual delta, successor, and unchanged controls.",
    ),
    "RG-4": (
        "sym:Concept:hswm-adaptive-guard-no-immunization",
        "No post-hoc immunization",
        "Renaming failure, weakening controls, changing criteria after outcome, or using downstream scale to rescue upstream failure is forbidden.",
    ),
    "RG-5": (
        "sym:Concept:hswm-adaptive-guard-claim-ceiling",
        "Evidence-bound claim ceiling",
        "Target commitment never raises a scientific or public claim above direct bounded evidence and independent replication.",
    ),
    "RG-6": (
        "sym:Concept:hswm-adaptive-guard-anti-ragnarok",
        "Anti-Ragnarok burden discipline",
        "A reroute must add discriminating evidence rather than static protocol, ontology, judge, or exception burden alone.",
    ),
}

ANCHORS = [
    {"uid": "sym:Concept:hswm", "name": "HSWM", "required_labels": ["Concept"]},
    *[
        {
            "uid": uid,
            "name": FCL_NAMES[fcl_id],
            "required_labels": ["Concept", "Guardrail"],
        }
        for fcl_id, uid in FCL_UIDS.items()
    ],
    {
        "uid": "sym:ResearchProgram:hswm-causal-composition-research-2026-08-29",
        "name": "HSWM causal-composition research program",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
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


def _common(
    *,
    name: str,
    description: str,
    authority: str,
    scope: str,
    kind: str,
    plane: str,
    state: str,
    owner: str,
    roles: list[str],
    boundary: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "authority_class": authority,
        "canonical_scope": scope,
        "ontology_kind": kind,
        "ontology_plane": plane,
        "epistemic_state": state,
        "responsibility_owner": owner,
        "claim_boundary": boundary,
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
    bindings = [
        {"path": path.as_posix(), "sha256": _file_sha(path)}
        for path in SOURCE_BINDING_PATHS
    ]
    source_sha = _file_sha(SOURCE_PATH)
    nodes: list[dict[str, Any]] = []

    nodes.append(
        _node(
            BUNDLE_UID,
            ["AbstractNode", "ResearchArtifact"],
            _common(
                name="HSWM adaptive research strategy ontology",
                description=(
                    "Bounded KG projection of fixed HSWM target identity, replaceable "
                    "realization mechanisms, scoped dispositions, evidence lineage, "
                    "reroute transactions, and anti-immunization constraints."
                ),
                authority="SYSTEM_DERIVED",
                scope="BOUNDED_PROJECTION_OF_USER_PRIMARY_DIRECTION",
                kind="ARTIFACT",
                plane="INQUIRY",
                state="TARGET_FIXED_METHODS_ADAPTIVE_UNJUDGED",
                owner="adaptive_strategy_projection_custodian",
                roles=["RESEARCH_BUNDLE", "TARGET_METHOD_SEPARATION", "REROUTE_ONTOLOGY"],
                boundary=(
                    "The projection organizes a research commitment and method; it "
                    "does not establish HSWM cognition, efficacy, or scale closure."
                ),
            ),
        )
    )
    nodes.append(
        _node(
            PROGRAM_UID,
            ["Concept", "ResearchProgram", "ResearchArtifact"],
            {
                **_common(
                    name="HSWM adaptive realization research program",
                    description=(
                        "Preserve final HSWM identity and FCL obligations while "
                        "replacing failed algorithms, methods, backends, testbeds, "
                        "and research paths under unchanged evidence standards."
                    ),
                    authority="USER_PRIMARY_DIRECTION_WITH_SECONDARY_AI_METHOD",
                    scope="RESEARCH_COMMITMENT_AND_OPERATIONALIZATION",
                    kind="PLAN",
                    plane="INQUIRY",
                    state="ACTIVE_TARGET_UNJUDGED",
                    owner="adaptive_realization_program_custodian",
                    roles=["RESEARCH_PROGRAM", "ADAPTIVE_REALIZATION", "EVIDENCE_LINEAGE"],
                    boundary=(
                        "Program persistence is not a prediction of success and does "
                        "not protect any empirical mechanism from a RED decision."
                    ),
                ),
                "target_invariant_ids": list(TARGET_INVARIANTS),
                "mechanism_family_ids": list(MECHANISM_FAMILIES),
                "disposition_states": list(DISPOSITION_STATES),
                "guardrail_ids": list(GUARDRAILS),
            },
        )
    )
    nodes.append(
        _node(
            COMMITMENT_UID,
            ["Concept", "Guardrail"],
            {
                **_common(
                    name="HSWM target persistence and adaptive-method commitment",
                    description=(
                        "Do not reduce the final HSWM target; change algorithms and "
                        "methods, preserve failures, and continue through alternate routes."
                    ),
                    authority="USER_PRIMARY",
                    scope="CANONICAL_RESEARCH_COMMITMENT_NOT_EMPIRICAL_RESULT",
                    kind="TARGET_DIRECTION",
                    plane="MODEL",
                    state="USER_RATIFIED_DIRECTION_SCIENTIFICALLY_UNJUDGED",
                    owner="hswm_target_direction_custodian",
                    roles=["USER_PRIMARY_COMMITMENT", "TARGET_PERSISTENCE", "METHOD_ADAPTATION"],
                    boundary=(
                        "The commitment is not evidence, a guarantee, or permission to "
                        "rename failed mechanisms or lower success criteria."
                    ),
                ),
                "source_path": SOURCE_PATH.as_posix(),
                "source_sha256": source_sha,
            },
        )
    )

    document_specs = (
        (
            "sym:AbstractNode:user-primary-hswm-target-fixed-methods-adaptive-2026-08-30",
            SOURCE_PATH,
            "Exact USER_PRIMARY HSWM target-persistence source",
            "USER_PRIMARY",
            ["AbstractNode", "SourceDocument", "UserCanonicalUtterance"],
            "EXACT_USER_SOURCE",
        ),
        (
            "sym:AbstractNode:hswm-adaptive-research-strategy-canon-2026-08-30",
            CANON_PATH,
            "HSWM adaptive research strategy canon",
            "MIXED_USER_PRIMARY_AND_SECONDARY_AI",
            ["AbstractNode", "SourceDocument", "ResearchArtifact"],
            "CANONICAL_DIRECTION_DOCUMENT",
        ),
        (
            "sym:AbstractNode:hswm-adaptive-realization-methodology-2026-08-30",
            METHODOLOGY_PATH,
            "HSWM adaptive realization methodology",
            "SECONDARY_AI",
            ["AbstractNode", "SourceDocument", "ResearchArtifact"],
            "RESEARCH_METHODOLOGY_DOCUMENT",
        ),
    )
    for uid, path, name, authority, labels, role in document_specs:
        nodes.append(
            _node(
                uid,
                labels,
                {
                    **_common(
                        name=name,
                        description="Source-bound document for the adaptive realization strategy.",
                        authority=authority,
                        scope="SOURCE_BOUND_STRATEGY_RECORD",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="SOURCE_BOUND",
                        owner="adaptive_strategy_source_custodian",
                        roles=["SOURCE_RECORD", role],
                        boundary=(
                            "Source binding establishes provenance and authority "
                            "separation, not HSWM implementation or efficacy."
                        ),
                    ),
                    "source_path": path.as_posix(),
                    "source_sha256": _file_sha(path),
                },
            )
        )

    for invariant_id, invariant in TARGET_INVARIANTS.items():
        nodes.append(
            _node(
                invariant["uid"],
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=invariant["name"],
                        description=invariant["description"],
                        authority=invariant["authority"],
                        scope="TARGET_IDENTITY_CONDITION_EMPIRICALLY_UNJUDGED",
                        kind="TARGET_INVARIANT",
                        plane="MODEL",
                        state="TARGET_ONLY_UNJUDGED",
                        owner=f"adaptive_{invariant_id.lower().replace('-', '_')}_custodian",
                        roles=["TARGET_INVARIANT", "IDENTITY_CONDITION"],
                        boundary=(
                            "This is a target identity condition, not a proven natural "
                            "law or evidence that a current system realizes it."
                        ),
                    ),
                    "invariant_id": invariant_id,
                    "mapped_fcl_ids": invariant["fcl_ids"],
                    "amendment_policy": "EXPLICIT_SOURCE_BOUND_CANONICAL_SUPERSESSION_ONLY",
                },
            )
        )

    for mechanism_id, (slug, description) in MECHANISM_FAMILIES.items():
        nodes.append(
            _node(
                f"sym:Hypothesis:hswm-adaptive-mechanism-{slug}",
                ["Concept", "Hypothesis"],
                {
                    **_common(
                        name=f"{mechanism_id} — replaceable {slug} mechanism family",
                        description=description,
                        authority="SECONDARY_AI",
                        scope="REVISABLE_AUXILIARY_HYPOTHESIS_FAMILY",
                        kind="HYPOTHESIS",
                        plane="INQUIRY",
                        state="REPLACEABLE_UNJUDGED",
                        owner=f"adaptive_{slug.replace('-', '_')}_custodian",
                        roles=["AUXILIARY_HYPOTHESIS_FAMILY", "REPLACEABLE_REALIZATION_PATH"],
                        boundary=(
                            "No member of this family is evidence or canonical HSWM "
                            "identity; each exact implementation needs a sealed test."
                        ),
                    ),
                    "mechanism_family_id": mechanism_id,
                    "mechanism_family": slug,
                    "allowed_dispositions": list(DISPOSITION_STATES),
                },
            )
        )

    for state_id, description in DISPOSITION_STATES.items():
        nodes.append(
            _node(
                f"sym:Concept:hswm-adaptive-disposition-{state_id.lower().replace('_', '-')}",
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"Mechanism disposition — {state_id}",
                        description=description,
                        authority="SECONDARY_AI",
                        scope="RESEARCH_STATE_MACHINE_NOT_OBSERVED_RESULT",
                        kind="STATE",
                        plane="INQUIRY",
                        state="STATE_DEFINITION",
                        owner="adaptive_disposition_schema_custodian",
                        roles=["MECHANISM_DISPOSITION", "STATE_MACHINE"],
                        boundary=(
                            "This node defines a possible disposition and does not "
                            "assign that disposition to any current mechanism."
                        ),
                    ),
                    "disposition_id": state_id,
                },
            )
        )

    for guard_id, (uid, name, description) in GUARDRAILS.items():
        nodes.append(
            _node(
                uid,
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{guard_id} — {name}",
                        description=description,
                        authority="SECONDARY_AI_FORMALIZATION_OF_USER_DIRECTION",
                        scope="RESEARCH_INTEGRITY_CONTRACT",
                        kind="GUARDRAIL",
                        plane="INQUIRY",
                        state="REQUIRED_CONSTRAINT",
                        owner=f"adaptive_{guard_id.lower().replace('-', '_')}_custodian",
                        roles=["REROUTE_GUARDRAIL", "SELF_DECEPTION_GUARD"],
                        boundary=(
                            "The guard constrains research interpretation; it is not "
                            "a scientific result or a new cognition rule."
                        ),
                    ),
                    "guardrail_id": guard_id,
                },
            )
        )

    local_uids = {row["uid"] for row in nodes}
    relations: list[dict[str, str]] = []
    source_uid, canon_uid, method_uid = [row[0] for row in document_specs]

    for uid in sorted(local_uids - {BUNDLE_UID}):
        relations.append(
            _relation(BUNDLE_UID, "HAS_CONCEPT", uid, "BOUNDED_PROJECTION", "ACTIVE", "SYSTEM_DERIVED")
        )
    for uid in (source_uid, canon_uid, method_uid):
        relations.append(_relation(BUNDLE_UID, "HAS_SOURCE", uid, "PROJECTION_SOURCE", "BOUND", "SYSTEM_DERIVED"))
        relations.append(_relation(PROGRAM_UID, "HAS_SOURCE", uid, "RESEARCH_SOURCE", "BOUND"))

    relations.extend(
        (
            _relation(source_uid, "USER_PRIMARY_SOURCE_FOR", COMMITMENT_UID, "EXACT_USER_DIRECTION", "BOUND", "USER_PRIMARY"),
            _relation(source_uid, "USER_PRIMARY_SOURCE_FOR", canon_uid, "CANON_AUTHORITY", "BOUND", "USER_PRIMARY"),
            _relation(canon_uid, "DEFINES_DIRECTION_FOR", PROGRAM_UID, "TARGET_PERSISTENCE", "ACTIVE", "MIXED_USER_PRIMARY_AND_SECONDARY_AI"),
            _relation(method_uid, "HAS_CONCEPT", PROGRAM_UID, "OPERATIONAL_METHOD", "PROPOSED"),
            _relation(COMMITMENT_UID, "DEFINES_DIRECTION_FOR", PROGRAM_UID, "TARGET_PERSISTENCE", "USER_RATIFIED", "USER_PRIMARY"),
            _relation(PROGRAM_UID, "PRESERVES", "sym:Concept:hswm", "TARGET_IDENTITY", "TARGET_ONLY"),
            _relation(BUNDLE_UID, "DOES_NOT_ENFORCE", "sym:Concept:hswm", "PROJECTION_NONCLAIM", "NOT_EVIDENCE", "SYSTEM_DERIVED"),
            _relation(PROGRAM_UID, "SPECULATIVE_LINK", "sym:ResearchProgram:hswm-causal-composition-research-2026-08-29", "ACTIVE_RESEARCH_SPINE", "PROPOSED_OPERATIONALIZATION"),
            _relation(PROGRAM_UID, "SPECULATIVE_LINK", "sym:ResearchProgram:hswm-ragnarok-research-2026-08-29", "BURDEN_FALSIFIER", "WORKING_ALIGNMENT"),
            _relation(PROGRAM_UID, "SPECULATIVE_LINK", "sym:ResearchProgram:hswm-pidna-research-2026-08-29", "ITERATIVE_ASCENT", "WORKING_ALIGNMENT"),
        )
    )

    for fcl_uid in FCL_UIDS.values():
        relations.append(_relation(PROGRAM_UID, "PRESERVES", fcl_uid, "FCL_TARGET_OBLIGATION", "TARGET_ONLY"))

    for invariant in TARGET_INVARIANTS.values():
        invariant_uid = invariant["uid"]
        relations.append(_relation(PROGRAM_UID, "HAS_CONCEPT", invariant_uid, "TARGET_INVARIANT", "REQUIRED"))
        relations.append(_relation(COMMITMENT_UID, "PRESERVES", invariant_uid, "TARGET_DIRECTION", "USER_RATIFIED", "USER_PRIMARY"))
        for fcl_id in invariant["fcl_ids"]:
            relations.append(_relation(invariant_uid, "PRESERVES", FCL_UIDS[fcl_id], "FCL_MAPPING", "TARGET_ONLY"))

    mechanism_uids = [
        f"sym:Hypothesis:hswm-adaptive-mechanism-{slug}"
        for slug, _description in MECHANISM_FAMILIES.values()
    ]
    for uid in mechanism_uids:
        relations.append(_relation(PROGRAM_UID, "HAS_CONCEPT", uid, "REPLACEABLE_MECHANISM_PORTFOLIO", "PROPOSED"))
        relations.append(_relation(uid, "REALIZES", TARGET_INVARIANTS["TI-1"]["uid"], "REALIZATION_CANDIDATE", "UNJUDGED"))
        relations.append(_relation(GUARDRAILS["RG-1"][0], "TESTS", uid, "SEALED_MECHANISM_TEST", "REQUIRED_BEFORE_CLAIM"))
        relations.append(_relation(GUARDRAILS["RG-4"][0], "CONSTRAINS", uid, "ANTI_IMMUNIZATION", "REQUIRED"))

    state_uids = {
        state_id: f"sym:Concept:hswm-adaptive-disposition-{state_id.lower().replace('_', '-')}"
        for state_id in DISPOSITION_STATES
    }
    for uid in state_uids.values():
        relations.append(_relation(PROGRAM_UID, "HAS_CONCEPT", uid, "MECHANISM_DISPOSITION", "DEFINED"))
    for before, after in (
        ("DRAFT", "PREREGISTERED"),
        ("PREREGISTERED", "TESTING"),
        ("TESTING", "SUPPORTED_WITHIN_SCOPE"),
        ("TESTING", "RED_WITHIN_SCOPE"),
        ("TESTING", "UNDERDETERMINED"),
        ("RED_WITHIN_SCOPE", "RETIRED_WITH_EVIDENCE_PRESERVED"),
        ("RETIRED_WITH_EVIDENCE_PRESERVED", "REROUTE_PROPOSED"),
        ("REROUTE_PROPOSED", "PREREGISTERED"),
        ("UNDERDETERMINED", "REROUTE_PROPOSED"),
    ):
        relations.append(_relation(state_uids[before], "NEXT", state_uids[after], "MECHANISM_STATE_MACHINE", "ALLOWED_TRANSITION"))

    for guard_id, (guard_uid, _name, _description) in GUARDRAILS.items():
        relations.append(_relation(PROGRAM_UID, "HAS_CONCEPT", guard_uid, "RESEARCH_INTEGRITY", "REQUIRED"))
        relations.append(_relation(guard_uid, "CONSTRAINS", PROGRAM_UID, "RESEARCH_METHOD", "REQUIRED"))
        if guard_id != "RG-3":
            relations.append(_relation(GUARDRAILS["RG-3"][0], "REQUIRES", guard_uid, "REROUTE_TRANSACTION", "REQUIRED"))

    relations.extend(
        (
            _relation(GUARDRAILS["RG-2"][0], "PRESERVES", state_uids["RED_WITHIN_SCOPE"], "NEGATIVE_EVIDENCE", "APPEND_ONLY"),
            _relation(GUARDRAILS["RG-3"][0], "REQUIRES", state_uids["RED_WITHIN_SCOPE"], "FAILED_AUXILIARY_DISPOSITION", "REQUIRED_WHEN_RED"),
            _relation(GUARDRAILS["RG-3"][0], "REQUIRES", state_uids["REROUTE_PROPOSED"], "SUCCESSOR_ROUTE", "REQUIRED"),
            _relation(GUARDRAILS["RG-3"][0], "PRESERVES", TARGET_INVARIANTS["TI-1"]["uid"], "TARGET_IDENTITY", "REQUIRED"),
            _relation(GUARDRAILS["RG-3"][0], "PRESERVES", TARGET_INVARIANTS["TI-4"]["uid"], "FRACTAL_TARGET", "REQUIRED"),
            _relation(state_uids["REROUTE_PROPOSED"], "SUPERSEDES_AS_FOLLOWUP", state_uids["RETIRED_WITH_EVIDENCE_PRESERVED"], "PATH_CONTINUATION_NOT_EVIDENCE_REWRITE", "SUCCESSOR_ONLY"),
            _relation(GUARDRAILS["RG-5"][0], "BOUNDS", PROGRAM_UID, "EVIDENCE_CEILING", "REQUIRED"),
            _relation(GUARDRAILS["RG-6"][0], "SPECULATIVE_LINK", "sym:ResearchProgram:hswm-ragnarok-research-2026-08-29", "BURDEN_ACCOUNTING", "WORKING_ALIGNMENT"),
        )
    )

    relations.sort(key=lambda row: (row["from_uid"], row["type"], row["to_uid"]))
    category_counts = {
        "target_invariants": len(TARGET_INVARIANTS),
        "mechanism_families": len(MECHANISM_FAMILIES),
        "disposition_states": len(DISPOSITION_STATES),
        "guardrails": len(GUARDRAILS),
        "source_records": len(document_specs),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_uid": BUNDLE_UID,
        "status": STATUS,
        "nonclaim": NONCLAIM,
        "authority_boundary": (
            "The user's commitment to preserve the final HSWM target and adapt "
            "algorithms and methods is USER_PRIMARY. Target/method separation, "
            "state machines, reroute transactions, and this KG projection are "
            "SECONDARY_AI formalization. All integrated scientific claims remain UNJUDGED."
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
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--digests", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / ONTOLOGY_PATH)
    args = parser.parse_args()
    data = build_data()
    payload = encoded_data(data)
    if args.digests:
        print(
            json.dumps(
                {
                    "anchors_sha256": canonical_sha(data["anchors"]),
                    "file_sha256": sha256(payload).hexdigest(),
                    "nodes_sha256": canonical_sha(data["nodes"]),
                    "projection_sha256": canonical_sha(data),
                    "relations_sha256": canonical_sha(data["relations"]),
                },
                sort_keys=True,
            )
        )
        return
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            raise SystemExit("adaptive-research strategy ontology projection drifted")
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
