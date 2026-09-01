#!/usr/bin/env python3
"""Build the bounded HSWM graph-and-loop-engineering research KG projection."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = Path(
    "ontology/identity/hswm_core/HSWM_GRAPH_AND_LOOP_ENGINEERING_ONTOLOGY.v2.json"
)
SYNTHESIS_PATH = Path(
    "docs/research/HSWM_GRAPH_AND_LOOP_ENGINEERING_SYNTHESIS_2026-09-01.md"
)
CONSTITUTION_PATH = Path("docs/canon/HSWM_CONSTITUTION_2026-08-20.md")
ADAPTIVE_STRATEGY_PATH = Path(
    "docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md"
)
CAUSAL_PROGRAM_PATH = Path("_research/causal_composition/README.md")
GRAPH_AUDIT_PATH = Path(
    "docs/research/HSWM_DEPENDENT_FACTORIZATION_GRAPH_ENGINEERING_AUDIT_2026-08-26.md"
)
HYPERGRAPH_PATH = Path("src/hswm/substrate/hypergraph.py")
CELLS_RUNTIME_PATH = Path("src/hswm/cells/runtime.py")
SELFMOD_RUNTIME_PATH = Path("src/hswm/selfmod/runtime.py")
ADMISSION_PATH = Path(
    "docs/research/HSWM_PERSISTED_VERIFIED_ADMISSION_DECISION_2026-09-01.md"
)
SOURCE_BINDING_PATHS = (
    SYNTHESIS_PATH,
    CONSTITUTION_PATH,
    ADAPTIVE_STRATEGY_PATH,
    CAUSAL_PROGRAM_PATH,
    GRAPH_AUDIT_PATH,
    HYPERGRAPH_PATH,
    CELLS_RUNTIME_PATH,
    SELFMOD_RUNTIME_PATH,
    ADMISSION_PATH,
)

SCHEMA_VERSION = "hswm-graph-and-loop-engineering-ontology/v2"
UID_RELEASE = "2026-09-01-v2"
BUNDLE_UID = (
    "sym:AbstractNode:hswm-graph-and-loop-engineering-ontology-2026-09-01-v2"
)
PROGRAM_UID = "sym:ResearchProgram:hswm-graph-and-loop-engineering-2026-09-01-v2"
PREVIOUS_PROGRAM_UID = "sym:ResearchProgram:hswm-graph-and-loop-engineering-2026-09-01"
NONCLAIM = (
    "SECONDARY_AI_RESEARCH_SYNTHESIS_AND_BOUNDED_KG_PROJECTION_ONLY_NOT_HSWM_"
    "COGNITION_LEARNING_EFFICACY_CONSCIOUSNESS_PERSONHOOD_OR_SCALE_CLOSURE"
)
SOURCE_ACCESS_DATE = "2026-09-01"
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
SAFE_RELATION = re.compile(r"[A-Z_][A-Z0-9_]*\Z")

EXTERNAL_SOURCES = (
    (
        "prov-o",
        "W3C PROV-O",
        "https://www.w3.org/TR/prov-o/",
        "STANDARD",
        "Entity, Activity, Agent, derivation, and delegation vocabulary for provenance.",
        "Truth, causal credit, permission, or HSWM learning.",
    ),
    (
        "shacl",
        "W3C SHACL",
        "https://www.w3.org/TR/shacl/",
        "STANDARD",
        "Explicit shape-based validation for a data graph.",
        "That RDF is HSWM's required storage model or that validation produces cognition.",
    ),
    (
        "graphblas",
        "GraphBLAS C API v2.1",
        "https://graphblas.org/docs/GraphBLAS_API_C_v2.1.0.pdf",
        "STANDARD",
        "Sparse matrix/vector and semiring compiled-plane option.",
        "That a sparse matrix is a lossless n-ary canonical state or a learning rule.",
    ),
    (
        "open-graphs-dpo",
        "Open Graphs and Monoidal Theories",
        "https://arxiv.org/abs/1011.4114",
        "PEER_REVIEWED_RESEARCH",
        "Typed open graphs and type-safe DPO rewriting reference.",
        "Confluence, authorization, recovery, or HSWM topology learning.",
    ),
    (
        "differential-dataflow",
        "Differential dataflow",
        "https://www.cidrdb.org/cidr2013/Papers/CIDR13_Paper111.pdf",
        "PEER_REVIEWED_RESEARCH",
        "Versioned incremental, nested iterative materialization reference.",
        "Causal credit, semantic correctness, or outcome value.",
    ),
    (
        "naiad",
        "Naiad timely dataflow",
        "https://www.microsoft.com/en-us/research/publication/naiad-a-timely-dataflow-system-2/",
        "PEER_REVIEWED_RESEARCH",
        "Logical clocks and progress tracking for episode, outcome, and revision time.",
        "A distributed HSWM runtime or a policy boundary.",
    ),
    (
        "neo4j-modeling",
        "Neo4j graph data modeling",
        "https://neo4j.com/docs/getting-started/data-modeling/",
        "OFFICIAL_DOCUMENTATION",
        "Query-led modeling, schema constraints, and model refactoring practice.",
        "Preservation of n-ary incidence without explicit reification.",
    ),
    (
        "neo4j-transactions",
        "Neo4j transaction semantics",
        "https://neo4j.com/docs/cypher-manual/4.1/introduction/transactions/",
        "OFFICIAL_DOCUMENTATION",
        "Atomic commit and rollback as a backend property.",
        "Distributed durability, semantic rollback, or permission validity.",
    ),
    (
        "ibm-loop-engineering",
        "IBM: What is loop engineering?",
        "https://www.ibm.com/think/topics/loop-engineering",
        "OFFICIAL_PRACTITIONER_GUIDANCE",
        "Current loop-engineering terminology for iterative agent workflows.",
        "A settled standard or causal benefit for a particular loop.",
    ),
    (
        "loop-engineering-study",
        "Loop Engineering: Building Blocks, Adoption, and Impact",
        "https://arxiv.org/abs/2608.21884",
        "EXPLORATORY_PREPRINT",
        "Machine-checkable stops, persistent state, verification, budgets, and human escalation as candidate loop ingredients.",
        "Causal benefit; the source is a recent exploratory preprint.",
    ),
    (
        "anthropic-effective-agents",
        "Anthropic: Building effective agents",
        "https://www.anthropic.com/engineering/building-effective-agents",
        "OFFICIAL_PRACTITIONER_GUIDANCE",
        "Tool-result grounding, iteration limits, guardrails, and evaluator separation.",
        "That a static workflow is a living HSWM harness.",
    ),
    (
        "anthropic-agent-evals",
        "Anthropic: Demystifying evals for AI agents",
        "https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents",
        "OFFICIAL_PRACTITIONER_GUIDANCE",
        "Multi-turn agent loops need task-and-environment-level evaluation.",
        "That test quantity or a favorable evaluator result demonstrates causal learning.",
    ),
    (
        "kubernetes-controllers",
        "Kubernetes controllers",
        "https://kubernetes.io/docs/concepts/architecture/controller/",
        "OFFICIAL_DOCUMENTATION",
        "Desired/actual reconciliation analogy for recovery and drift detection.",
        "That target state can replace outcome-bound learning.",
    ),
    (
        "react",
        "ReAct",
        "https://arxiv.org/abs/2210.03629",
        "PEER_REVIEWED_RESEARCH",
        "Interleaved reasoning, action, and environment observation baseline.",
        "Canonical revision, causal credit, topology learning, or HSWM identity.",
    ),
    (
        "reflexion",
        "Reflexion",
        "https://arxiv.org/abs/2303.11366",
        "PEER_REVIEWED_RESEARCH",
        "Feedback-conditioned future behavior baseline.",
        "Canonical revision, causal credit, topology learning, or HSWM identity.",
    ),
)

CAPABILITIES = (
    (
        "canonical-nary-state",
        "Canonical n-ary graph state",
        "Versioned canonical atom, reified hyperedge/incidence, typed reference, schema-relative owner, source/authority/lineage, and explicit lifecycle.",
        "GRAPH_STATE_CONTRACT",
    ),
    (
        "compiled-projection",
        "Canonical-to-compiled graph projection",
        "A source snapshot, compiler version, mapping and loss declaration, sparse/materialized view, write-back policy, and invalidation rule.",
        "COMPILED_GRAPH_CONTRACT",
    ),
    (
        "graph-delta-transaction",
        "Typed graph-delta transaction",
        "Proposal, match, precondition, authority, conflict policy, candidate epoch, and commit/reject/quarantine/restore receipt.",
        "GRAPH_TRANSACTION_CONTRACT",
    ),
    (
        "graph-readout",
        "Bounded graph readout",
        "Query intent, graph cut, serialization budget, omitted information, and traceable use in the following action.",
        "GRAPH_READOUT_CONTRACT",
    ),
    (
        "outcome-loop",
        "Outcome-bound graph-and-loop transition",
        "Exact snapshot, bounded action, sealed trajectory, independent outcome, declared credit, transition decision, replay, and stop/retry/escalation disposition.",
        "OUTCOME_BOUND_LOOP_CONTRACT",
    ),
)

CURRENT_SURFACES = (
    (
        "hypergraph-prototype",
        "Reified hypergraph prototype",
        HYPERGRAPH_PATH,
        "Member-set representation and incidence-matrix computation are present.",
        "PROTOTYPE_SUBSTRATE_NOT_CANONICAL_GRAPH_SERVICE",
    ),
    (
        "cell-event-runtime",
        "Cell event/effect runtime",
        CELLS_RUNTIME_PATH,
        "Admission, replay, budget accounting, activation correlation, and post-commit effects are present.",
        "LOCAL_EXECUTION_ENGINEERING_NOT_LIVING_HARNESS_EVIDENCE",
    ),
    (
        "selfmod-runtime",
        "Self-authored structural runtime",
        SELFMOD_RUNTIME_PATH,
        "Frozen snapshots, typed agent proposals, budgets, and compare-and-swap activation are present.",
        "MUTATION_MECHANICS_NOT_OUTCOME_GATED_CAUSAL_LEARNING",
    ),
    (
        "causal-program",
        "Causal-composition research program",
        CAUSAL_PROGRAM_PATH,
        "G0–G6 define sealed trajectory, independent outcome, credit, revision, held-out behavior, and remove/restore controls.",
        "RESEARCH_PROTOCOL_NOT_PASSED_EFFICACY_GATE",
    ),
    (
        "persisted-admission",
        "Persisted verified-admission decision boundary",
        ADMISSION_PATH,
        "One local Permit-bound decision is persisted with a local transition and revalidated on recovery.",
        "SOURCE_LEVEL_REFINEMENT_UNPROVED_AND_NOT_END_TO_END_HSWM",
    ),
)

GAPS = (
    (
        "projection-manifest",
        "Canonical-to-compiled projection manifest gap",
        "No active generic contract proves every compiled edge/index entry derives from exact canonical atom/incidence versions with declared loss, write-back policy, and invalidation.",
        "SOURCE_INVENTORY_AND_PROPOSED_CONTRACT_INFERENCE",
    ),
    (
        "nary-delta-transaction",
        "Typed n-ary graph-delta transaction gap",
        "The proposed rewrite transaction, conflict/critical-pair policy, quarantine, and semantic restore requirements are not an active generic n-ary graph runtime.",
        "PROPOSED_ENGINEERING_PATH_NOT_IMPLEMENTED_CLOSURE",
    ),
    (
        "integrated-loop-controller",
        "Integrated graph-and-loop controller gap",
        "Execution loops, mutation mechanics, and research gates exist in separate bounded surfaces; no one controller binds graph compilation, outcome credit, transition verdict, and research disposition.",
        "SOURCE_INVENTORY_INFERENCE_NOT_EFFICACY_RESULT",
    ),
    (
        "causal-graph-efficacy",
        "Outcome-bound graph efficacy gap",
        "No current result establishes that a canonical graph delta, rather than matched retrieval, lesson, static workflow, sham, or shuffled credit, mediates fresh behavior.",
        "SCIENTIFICALLY_UNJUDGED",
    ),
)

GATES = (
    (
        "ge-0",
        "GE-0 canonical n-ary graph contract",
        "Shape, ownership, lifecycle, and source/restore-round-trip qualification.",
        "A record cannot round-trip, has ambiguous ownership, or silently aliases a projection.",
        "GRAPH_STATE_CONTRACT_ENGINEERING_ONLY",
    ),
    (
        "ge-1",
        "GE-1 compiled projection qualification",
        "Canonical-to-compiled manifest, deterministic replay, and stale/tamper refusal.",
        "Entries cannot be traced to exact source versions and declared loss.",
        "COMPILED_GRAPH_TRACEABILITY_ENGINEERING_ONLY",
    ),
    (
        "ge-2",
        "GE-2 graph-delta transaction qualification",
        "Typed delta transaction with conflict, quarantine, restore, and concurrent-edit tests.",
        "A rejected or competing delta changes canonical state or recovery loses lineage.",
        "GRAPH_TRANSACTION_ENGINEERING_ONLY",
    ),
    (
        "le-0",
        "LE-0 loop-control qualification",
        "Record trigger, snapshot, budget, verifier, stop/retry/escalation, and all verdicts.",
        "The loop can run unbounded, self-approve, erase a failed attempt, or silently change contract.",
        "LOOP_CONTROL_ENGINEERING_ONLY",
    ),
    (
        "gl-1",
        "GL-1 local causal graph revision",
        "Pre-registered G1 test that an outcome-bound graph revision mediates fresh held-out behavior and loses/recovers effect under remove/restore.",
        "Matched RAG, lesson, static workflow, sham, shuffled credit, or fixed graph explains the gain.",
        "EXISTING_G1_CEILING_ONLY_IF_GATE_PASSES",
    ),
    (
        "gl-3",
        "GL-3 topology morphogenesis and recovery",
        "Later G3 test for outcome-bound topology change and recovery.",
        "Fixed topology, matched random rewiring, or manual central repair explains the result.",
        "EXISTING_G3_CEILING_ONLY_IF_PREREQUISITES_PASS",
    ),
)

ANCHORS = [
    {"uid": "sym:Concept:hswm", "name": "HSWM", "required_labels": ["Concept"]},
    {
        "uid": "sym:ResearchProgram:hswm-causal-composition-research-2026-08-29",
        "name": "HSWM causal-composition research program",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
    {
        "uid": "sym:Hypothesis:hswm-meta-g1-local-causal-rung",
        "name": "G1 — Minimal outcome-bound causal rung",
        "required_labels": ["Concept", "Hypothesis"],
    },
    {
        "uid": "sym:Hypothesis:hswm-meta-g3-morphogenesis-recovery",
        "name": "G3 — Topology morphogenesis and recovery",
        "required_labels": ["Concept", "Hypothesis"],
    },
    {
        "uid": PREVIOUS_PROGRAM_UID,
        "name": "HSWM graph and loop engineering reinforcement program",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
]


def _file_sha(path: Path) -> str:
    return sha256((ROOT / path).read_bytes()).hexdigest()


def _common(
    *,
    name: str,
    description: str,
    scope: str,
    kind: str,
    plane: str,
    state: str,
    owner: str,
    roles: list[str],
    boundary: str,
    authority: str = "SECONDARY_AI",
) -> dict[str, Any]:
    return {
        "name": f"{name} [{UID_RELEASE}]",
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


def _source_uid(slug: str) -> str:
    return f"sym:AbstractNode:hswm-graph-loop-source-{slug}-{UID_RELEASE}"


def _local_source_uid(path: Path) -> str:
    slug = "-".join(path.with_suffix("").parts).lower().replace("_", "-")
    return _source_uid(f"local-{slug}")


def _capability_uid(slug: str) -> str:
    return f"sym:Concept:hswm-graph-loop-{slug}-{UID_RELEASE}"


def _current_surface_uid(slug: str) -> str:
    return f"sym:AbstractNode:hswm-graph-loop-current-{slug}-{UID_RELEASE}"


def _gap_uid(slug: str) -> str:
    return f"sym:Hypothesis:hswm-graph-loop-gap-{slug}-{UID_RELEASE}"


def _gate_uid(slug: str) -> str:
    return f"sym:Hypothesis:hswm-graph-loop-gate-{slug}-{UID_RELEASE}"


def build_data() -> dict[str, Any]:
    bindings = [
        {"path": path.as_posix(), "sha256": _file_sha(path)}
        for path in SOURCE_BINDING_PATHS
    ]
    nodes: list[dict[str, Any]] = [
        _node(
            BUNDLE_UID,
            ["AbstractNode", "ResearchArtifact"],
            _common(
                name="HSWM graph and loop engineering ontology",
                description=(
                    "Bounded KG projection of source-checked graph engineering, "
                    "loop engineering, current repository surfaces, gaps, and "
                    "proposed research gates."
                ),
                scope="BOUNDED_RESEARCH_PROJECTION",
                kind="ARTIFACT",
                plane="INQUIRY",
                state="PROPOSED_ENGINEERING_PATH_SCIENTIFICALLY_UNJUDGED",
                owner="graph_loop_ontology_projection_custodian",
                roles=["RESEARCH_BUNDLE", "GRAPH_ENGINEERING", "LOOP_ENGINEERING"],
                boundary=(
                    "This projection is research infrastructure; it is not canonical "
                    "HSWM state, cognition, learning, permission, or efficacy."
                ),
                authority="SYSTEM_DERIVED",
            ),
        ),
        _node(
            PROGRAM_UID,
            ["Concept", "ResearchProgram", "ResearchArtifact"],
            _common(
                name="HSWM graph and loop engineering reinforcement program",
                description=(
                    "Strengthen the replaceable graph and loop realization path "
                    "without changing HSWM target identity or claim ceilings."
                ),
                scope="SECONDARY_AI_RESEARCH_PATH",
                kind="PLAN",
                plane="INQUIRY",
                state="PROPOSED_ENGINEERING_PATH",
                owner="graph_loop_research_program_custodian",
                roles=[
                    "RESEARCH_PROGRAM",
                    "GRAPH_ENGINEERING_REINFORCEMENT",
                    "LOOP_ENGINEERING_REINFORCEMENT",
                ],
                boundary=(
                    "The program proposes engineering work and falsifiers; it does "
                    "not establish a working HSWM or any causal-learning effect."
                ),
            ),
        ),
    ]

    for path in SOURCE_BINDING_PATHS:
        nodes.append(
            _node(
                _local_source_uid(path),
                ["AbstractNode", "SourceDocument", "ResearchArtifact"],
                {
                    **_common(
                        name=path.name,
                        description="Source-bound local artifact for this research projection.",
                        scope="LOCAL_SOURCE_BINDING",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="SOURCE_BOUND",
                        owner="graph_loop_source_custodian",
                        roles=["LOCAL_SOURCE_RECORD"],
                        boundary=(
                            "A source binding proves only the bytes used by this "
                            "projection, not the scientific content of the source."
                        ),
                        authority="MIXED_EXISTING_SOURCE",
                    ),
                    "source_path": path.as_posix(),
                    "source_sha256": _file_sha(path),
                },
            )
        )

    for slug, name, url, source_type, import_text, nonimport_text in EXTERNAL_SOURCES:
        nodes.append(
            _node(
                _source_uid(slug),
                ["AbstractNode", "SourceDocument", "ResearchArtifact"],
                {
                    **_common(
                        name=name,
                        description="External source recorded as a bounded engineering input.",
                        scope="EXTERNAL_SOURCE_METADATA",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="EXTERNAL_SOURCE_CHECKED",
                        owner="graph_loop_external_source_custodian",
                        roles=["EXTERNAL_SOURCE_RECORD", source_type],
                        boundary=(
                            "External source relevance does not establish HSWM "
                            "identity, implementation, or efficacy."
                        ),
                        authority="EXTERNAL_SOURCE",
                    ),
                    "source_url": url,
                    "source_type": source_type,
                    "accessed_on": SOURCE_ACCESS_DATE,
                    "engineering_import": import_text,
                    "does_not_establish": nonimport_text,
                },
            )
        )

    for slug, name, description, role in CAPABILITIES:
        nodes.append(
            _node(
                _capability_uid(slug),
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=name,
                        description=description,
                        scope="PROPOSED_REPLACEABLE_ENGINEERING_CONTRACT",
                        kind="ENGINEERING_CONTRACT",
                        plane="INQUIRY",
                        state="PROPOSED_UNJUDGED",
                        owner=f"graph_loop_{slug.replace('-', '_')}_custodian",
                        roles=[role, "RESEARCH_CONTRACT"],
                        boundary=(
                            "This contract defines engineering obligations and "
                            "falsifiers, not HSWM cognition or empirical success."
                        ),
                    ),
                    "contract_id": slug.upper().replace("-", "_"),
                },
            )
        )

    for slug, name, path, description, boundary in CURRENT_SURFACES:
        nodes.append(
            _node(
                _current_surface_uid(slug),
                ["AbstractNode", "ResearchArtifact"],
                {
                    **_common(
                        name=name,
                        description=description,
                        scope="CURRENT_SOURCE_INVENTORY",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="ENGINEERING_SURFACE_ONLY",
                        owner="graph_loop_current_surface_custodian",
                        roles=["CURRENT_IMPLEMENTATION_SURFACE"],
                        boundary=boundary,
                        authority="SOURCE_INVENTORY",
                    ),
                    "source_path": path.as_posix(),
                    "source_sha256": _file_sha(path),
                },
            )
        )

    for slug, name, description, state in GAPS:
        nodes.append(
            _node(
                _gap_uid(slug),
                ["Concept", "Hypothesis"],
                {
                    **_common(
                        name=name,
                        description=description,
                        scope="CURRENT_GAP_OR_PROPOSED_CLOSURE",
                        kind="GAP",
                        plane="INQUIRY",
                        state=state,
                        owner=f"graph_loop_gap_{slug.replace('-', '_')}_custodian",
                        roles=["ENGINEERING_GAP", "FALSIFICATION_TARGET"],
                        boundary=(
                            "A recorded gap is neither failure of the HSWM target nor "
                            "evidence for a mechanism; it names a bounded work item."
                        ),
                    ),
                    "gap_id": slug.upper().replace("-", "_"),
                },
            )
        )

    for slug, name, description, falsifier, ceiling in GATES:
        nodes.append(
            _node(
                _gate_uid(slug),
                ["Concept", "Hypothesis", "Guardrail"],
                {
                    **_common(
                        name=name,
                        description=description,
                        scope="PROSPECTIVE_ENGINEERING_OR_RESEARCH_GATE",
                        kind="FALSIFICATION_CONTRACT",
                        plane="INQUIRY",
                        state="PROPOSED_NOT_EXECUTED",
                        owner=f"graph_loop_gate_{slug.replace('-', '_')}_custodian",
                        roles=["PROPOSED_GATE", "FALSIFICATION_CONTRACT"],
                        boundary=(
                            "This is a prospective contract, not preregistration, "
                            "execution, result, or authorization to raise a claim."
                        ),
                    ),
                    "gate_id": slug.upper().replace("-", "_"),
                    "falsifier": falsifier,
                    "claim_ceiling": ceiling,
                },
            )
        )

    local_uids = {node["uid"] for node in nodes}
    relations: list[dict[str, str]] = []
    for uid in sorted(local_uids - {BUNDLE_UID}):
        relations.append(
            _relation(
                BUNDLE_UID,
                "HAS_CONCEPT",
                uid,
                "BOUNDED_PROJECTION_MEMBERSHIP",
                "ACTIVE",
                "SYSTEM_DERIVED",
            )
        )

    local_source_uids = [
        _local_source_uid(path)
        for path in SOURCE_BINDING_PATHS
    ]
    external_source_uids = [_source_uid(item[0]) for item in EXTERNAL_SOURCES]
    for uid in local_source_uids + external_source_uids:
        relations.append(
            _relation(
                BUNDLE_UID,
                "HAS_SOURCE",
                uid,
                "SOURCE_PROVENANCE",
                "BOUND",
                "SYSTEM_DERIVED",
            )
        )
        relations.append(
            _relation(
                PROGRAM_UID, "HAS_SOURCE", uid, "RESEARCH_INPUT", "CHECKED"
            )
        )

    for slug, _, _, role in CAPABILITIES:
        capability_uid = _capability_uid(slug)
        relations.append(
            _relation(
                PROGRAM_UID,
                "REALIZES",
                capability_uid,
                "REPLACEABLE_ENGINEERING_CANDIDATE",
                "PROPOSED",
            )
        )
        relations.append(
            _relation(
                capability_uid,
                "CONSTRAINS",
                "sym:Concept:hswm",
                "TARGET_IDENTITY_BOUNDARY",
                "ACTIVE",
            )
        )
    for slug, _, _, _ in GAPS:
        relations.append(
            _relation(
                PROGRAM_UID,
                "TARGETS",
                _gap_uid(slug),
                "ENGINEERING_GAP_CLOSURE",
                "PROPOSED",
            )
        )
    for slug, _, _, _, _ in GATES:
        gate_uid = _gate_uid(slug)
        relations.append(
            _relation(PROGRAM_UID, "TESTS", gate_uid, "PROSPECTIVE_GATE", "PROPOSED")
        )
        relations.append(
            _relation(gate_uid, "CONSTRAINS", "sym:Concept:hswm", "CLAIM_BOUNDARY", "ACTIVE")
        )
    relations.extend(
        (
            _relation(
                PROGRAM_UID,
                "PRESERVES",
                "sym:ResearchProgram:hswm-causal-composition-research-2026-08-29",
                "EXISTING_G0_TO_G6_ORDER",
                "ACTIVE",
            ),
            _relation(
                _gate_uid("gl-1"),
                "REQUIRES",
                "sym:Hypothesis:hswm-meta-g1-local-causal-rung",
                "EXISTING_G1_GATE",
                "ACTIVE",
            ),
            _relation(
                _gate_uid("gl-3"),
                "REQUIRES",
                "sym:Hypothesis:hswm-meta-g3-morphogenesis-recovery",
                "EXISTING_G3_GATE",
                "ACTIVE",
            ),
            _relation(
                BUNDLE_UID,
                "DOES_NOT_ENFORCE",
                "sym:Concept:hswm",
                "KG_PROJECTION_BOUNDARY",
                "ACTIVE",
                "SYSTEM_DERIVED",
            ),
            _relation(
                PROGRAM_UID,
                "SUPERSEDES_AS_FOLLOWUP",
                PREVIOUS_PROGRAM_UID,
                "SOURCE_CORRECTION_WITHOUT_SCIENTIFIC_STATUS_CHANGE",
                "ACTIVE",
            ),
        )
    )

    category_counts = {
        "local_source_records": len(local_source_uids),
        "external_source_records": len(external_source_uids),
        "capabilities": len(CAPABILITIES),
        "current_surfaces": len(CURRENT_SURFACES),
        "gaps": len(GAPS),
        "gates": len(GATES),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_uid": BUNDLE_UID,
        "status": "PROPOSED_ENGINEERING_PATH_SCIENTIFICALLY_UNJUDGED",
        "nonclaim": NONCLAIM,
        "source_accessed_on": SOURCE_ACCESS_DATE,
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
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=False, indent=2) + "\n"
    ).encode("utf-8")


def validate_data(data: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "bundle_uid",
        "status",
        "nonclaim",
        "source_accessed_on",
        "artifact_bindings",
        "expected_counts",
        "anchors",
        "nodes",
        "relations",
    }
    if set(data) != expected_keys:
        raise ValueError("graph-loop ontology top-level shape drifted")
    if data["schema_version"] != SCHEMA_VERSION or data["bundle_uid"] != BUNDLE_UID:
        raise ValueError("graph-loop ontology identity drifted")
    if data["nonclaim"] != NONCLAIM or data["source_accessed_on"] != SOURCE_ACCESS_DATE:
        raise ValueError("graph-loop ontology boundary drifted")
    if data != build_data():
        raise ValueError("graph-loop ontology is not the deterministic build")

    bindings = data["artifact_bindings"]
    expected_paths = [path.as_posix() for path in SOURCE_BINDING_PATHS]
    if [item.get("path") for item in bindings] != expected_paths:
        raise ValueError("artifact binding paths drifted")
    for binding in bindings:
        if set(binding) != {"path", "sha256"}:
            raise ValueError("artifact binding shape drifted")
        if binding["sha256"] != _file_sha(Path(binding["path"])):
            raise ValueError(f"artifact binding drifted: {binding['path']}")

    nodes = data["nodes"]
    anchors = data["anchors"]
    relations = data["relations"]
    if not all(isinstance(rows, list) for rows in (nodes, anchors, relations)):
        raise ValueError("graph records must be arrays")
    if (
        len(nodes),
        len(anchors),
        len(relations),
    ) != (
        data["expected_counts"]["nodes"],
        data["expected_counts"]["anchors"],
        data["expected_counts"]["relations"],
    ):
        raise ValueError("declared graph counts drifted")

    node_uids = [node.get("uid") for node in nodes]
    anchor_uids = [anchor.get("uid") for anchor in anchors]
    duplicates = {
        uid: count
        for uid, count in Counter(node_uids + anchor_uids).items()
        if not isinstance(uid, str) or not uid or count > 1
    }
    if duplicates or set(node_uids) & set(anchor_uids):
        raise ValueError(f"duplicate or overlapping uid: {duplicates}")
    all_uids = set(node_uids) | set(anchor_uids)

    for node in nodes:
        if set(node) != {"uid", "labels", "properties"}:
            raise ValueError("node shape drifted")
        if (
            not isinstance(node["labels"], list)
            or not node["labels"]
            or len(node["labels"]) != len(set(node["labels"]))
            or any(not SAFE_LABEL.fullmatch(label) for label in node["labels"])
        ):
            raise ValueError(f"unsafe node labels: {node['uid']}")
        properties = node["properties"]
        required = {
            "name",
            "description",
            "authority_class",
            "canonical_scope",
            "ontology_kind",
            "ontology_plane",
            "epistemic_state",
            "responsibility_owner",
            "claim_boundary",
            "projection_nonclaim",
            "ontology_domain",
            "record_lifecycle",
            "review_required",
            "semantic_roles",
        }
        if not required <= set(properties):
            raise ValueError(f"missing common properties: {node['uid']}")
        if properties["projection_nonclaim"] != NONCLAIM:
            raise ValueError(f"nonclaim drifted: {node['uid']}")
        url = properties.get("source_url")
        if url is not None and (
            not isinstance(url, str) or not url.startswith("https://")
        ):
            raise ValueError(f"unsafe external source url: {node['uid']}")

    seen_relations: set[tuple[str, str, str]] = set()
    for relation in relations:
        if set(relation) != {
            "from_uid",
            "type",
            "to_uid",
            "authority_class",
            "scope",
            "status",
        }:
            raise ValueError("relation shape drifted")
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        if key in seen_relations:
            raise ValueError(f"duplicate relation: {key}")
        seen_relations.add(key)
        if (
            relation["from_uid"] not in all_uids
            or relation["to_uid"] not in all_uids
            or not SAFE_RELATION.fullmatch(relation["type"])
        ):
            raise ValueError(f"invalid relation endpoint or type: {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / ONTOLOGY_PATH)
    args = parser.parse_args()
    data = build_data()
    validate_data(data)
    payload = encoded_data(data)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            raise SystemExit("graph-loop ontology projection drifted")
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
