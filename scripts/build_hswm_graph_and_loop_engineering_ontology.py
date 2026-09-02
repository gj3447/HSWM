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
    "ontology/identity/hswm_core/HSWM_GRAPH_AND_LOOP_ENGINEERING_ONTOLOGY.v6.json"
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
RDF_PROJECTION_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-rdf-projection.ts"
)
RDF_PROJECTION_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-rdf-projection.test.ts"
)
DURABLE_RDF_PROJECTION_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-durable-rdf-projection.ts"
)
DURABLE_RDF_PROJECTION_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-durable-rdf-projection.test.ts"
)
DURABLE_RUNTIME_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.ts"
)
STATE_JOURNAL_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.ts"
)
STATE_JOURNAL_STORE_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-store.ts"
)
STATE_JOURNAL_STORE_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-state-journal-store.test.ts"
)
STATE_JOURNAL_FILE_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-file.ts"
)
STATE_JOURNAL_FILE_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-state-journal-file.test.ts"
)
PUBLIC_API_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/public-api.test.ts"
)
DNRD5_SOURCE_CLOSURE_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/dnrd5-source-closure.test.ts"
)
CROSS_PROJECT_ADOPTION_PATH = Path(
    "docs/research/HSWM_CROSS_PROJECT_GRAPH_HARNESS_ADOPTION_2026-09-01.md"
)
IMPLEMENTATION_PATH = Path(
    "docs/research/HSWM_GRAPH_LOOP_ENGINEERING_IMPLEMENTATION_2026-09-01.md"
)
GRAPH_LOOP_ENGINEERING_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.ts"
)
GRAPH_LOOP_ENGINEERING_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-graph-loop-engineering.test.ts"
)
GRAPH_LOOP_STANDARD_ENFORCEMENT_PATH = Path(
    "docs/research/HSWM_GRAPH_LOOP_STANDARD_ENFORCEMENT_2026-09-02.md"
)
GRAPH_LOOP_RESEARCH_JOB_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-research-job.ts"
)
GRAPH_LOOP_RESEARCH_JOB_PROCESS_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-job-process.ts"
)
GRAPH_LOOP_ENFORCEMENT_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-graph-loop-enforcement-boundary.test.ts"
)
GRAPH_LOOP_RESEARCH_JOB_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-graph-loop-research-job.test.ts"
)
ROUTING_DIAGNOSTIC_FILE_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-routing-diagnostic-file.ts"
)
LOOP_JOB_PROFILES_PATH = Path(
    "_research/loop_jobs/HSWM_STANDARD_RESEARCH_JOB_PROFILES.v1.json"
)
LOOP_JOB_PROFILES_README_PATH = Path("_research/loop_jobs/README.md")
LOOP_JOB_PROFILE_MATERIALIZER_PATH = Path(
    "src/hswm/experiments/graph_loop_job_profiles.py"
)
DGX_Q1_LE0_VERIFIER_PATH = Path(
    "src/hswm/experiments/dgx_q1_le0_verifier.py"
)
LOOP_JOB_PROFILE_TEST_PATH = Path("tests/test_hswm_graph_loop_job_profiles.py")
PROOF_STATUS_PATH = Path(
    "docs/research/HSWM_PROOF_STATUS_GRAPH_2026-09-02.md"
)
TYPESCRIPT_LEAN_STATUS_PATH = Path(
    "docs/research/HSWM_TYPESCRIPT_EFFECT_LEAN_AND_CAUSAL_EVIDENCE_STATUS_2026-08-31.md"
)
END_TO_END_REFINEMENT_PATH = Path(
    "docs/research/HSWM_END_TO_END_RUNTIME_REFINEMENT_LEAN_BOUNDARY_2026-08-31.md"
)
CAUSAL_EFFICACY_BRIDGE_PATH = Path(
    "docs/research/HSWM_CAUSAL_EFFICACY_OCCURRENCE_LEAN_BRIDGE_2026-09-01.md"
)
CANONICAL_LEARNING_LEAN_PATH = Path("formal/HSWMCanonicalLearning.lean")
VERIFIED_ADMISSION_KERNEL_LEAN_PATH = Path(
    "formal/HSWMVerifiedAdmissionKernel.lean"
)
END_TO_END_REFINEMENT_LEAN_PATH = Path(
    "formal/HSWMEndToEndRuntimeRefinement.lean"
)
CAUSAL_EFFICACY_BRIDGE_LEAN_PATH = Path("formal/HSWMCausalEfficacyBridge.lean")
VERIFIED_ADMISSION_GATEWAY_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts"
)
VERIFIED_ADMISSION_GATEWAY_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-verified-admission-gateway-v2.test.ts"
)
LOCAL_PERMIT_COMMIT_PATH = Path(
    "src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.ts"
)
LOCAL_PERMIT_COMMIT_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-local-permit-commit.test.ts"
)
LOCAL_PERMIT_COMMIT_CRASH_TEST_PATH = Path(
    "src/hswm/effect-runtime/test/canonical-atom-v2-local-permit-commit-process-crash.test.ts"
)
FORMAL_LAKEFILE_PATH = Path("formal/lakefile.toml")
LEAN_TOOLCHAIN_PATH = Path("formal/lean-toolchain")
EFFECT_PACKAGE_PATH = Path("src/hswm/effect-runtime/package.json")
EFFECT_PACKAGE_LOCK_PATH = Path("src/hswm/effect-runtime/package-lock.json")
ONTOLOGY_BUILDER_PATH = Path(
    "scripts/build_hswm_graph_and_loop_engineering_ontology.py"
)
ONTOLOGY_TEST_PATH = Path(
    "tests/test_hswm_graph_and_loop_engineering_ontology.py"
)
PORTABLE_MATH_COMPILER_PATH = Path("scripts/compile_portable_markdown_math.py")
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
    RDF_PROJECTION_PATH,
    RDF_PROJECTION_TEST_PATH,
    DURABLE_RDF_PROJECTION_PATH,
    DURABLE_RDF_PROJECTION_TEST_PATH,
    DURABLE_RUNTIME_PATH,
    STATE_JOURNAL_PATH,
    STATE_JOURNAL_STORE_PATH,
    STATE_JOURNAL_STORE_TEST_PATH,
    STATE_JOURNAL_FILE_PATH,
    STATE_JOURNAL_FILE_TEST_PATH,
    PUBLIC_API_TEST_PATH,
    DNRD5_SOURCE_CLOSURE_TEST_PATH,
    CROSS_PROJECT_ADOPTION_PATH,
    IMPLEMENTATION_PATH,
    GRAPH_LOOP_ENGINEERING_PATH,
    GRAPH_LOOP_ENGINEERING_TEST_PATH,
    GRAPH_LOOP_STANDARD_ENFORCEMENT_PATH,
    GRAPH_LOOP_RESEARCH_JOB_PATH,
    GRAPH_LOOP_RESEARCH_JOB_PROCESS_PATH,
    GRAPH_LOOP_ENFORCEMENT_TEST_PATH,
    GRAPH_LOOP_RESEARCH_JOB_TEST_PATH,
    ROUTING_DIAGNOSTIC_FILE_PATH,
    LOOP_JOB_PROFILES_PATH,
    LOOP_JOB_PROFILES_README_PATH,
    LOOP_JOB_PROFILE_MATERIALIZER_PATH,
    DGX_Q1_LE0_VERIFIER_PATH,
    LOOP_JOB_PROFILE_TEST_PATH,
    PROOF_STATUS_PATH,
    TYPESCRIPT_LEAN_STATUS_PATH,
    END_TO_END_REFINEMENT_PATH,
    CAUSAL_EFFICACY_BRIDGE_PATH,
    CANONICAL_LEARNING_LEAN_PATH,
    VERIFIED_ADMISSION_KERNEL_LEAN_PATH,
    END_TO_END_REFINEMENT_LEAN_PATH,
    CAUSAL_EFFICACY_BRIDGE_LEAN_PATH,
    VERIFIED_ADMISSION_GATEWAY_PATH,
    VERIFIED_ADMISSION_GATEWAY_TEST_PATH,
    LOCAL_PERMIT_COMMIT_PATH,
    LOCAL_PERMIT_COMMIT_TEST_PATH,
    LOCAL_PERMIT_COMMIT_CRASH_TEST_PATH,
    FORMAL_LAKEFILE_PATH,
    LEAN_TOOLCHAIN_PATH,
    EFFECT_PACKAGE_PATH,
    EFFECT_PACKAGE_LOCK_PATH,
    ONTOLOGY_BUILDER_PATH,
    ONTOLOGY_TEST_PATH,
    PORTABLE_MATH_COMPILER_PATH,
)

SCHEMA_VERSION = "hswm-graph-and-loop-engineering-ontology/v6"
UID_RELEASE = "2026-09-02-v6"
BUNDLE_UID = (
    "sym:AbstractNode:hswm-graph-and-loop-engineering-ontology-2026-09-02-v6"
)
PROGRAM_UID = "sym:ResearchProgram:hswm-graph-and-loop-engineering-2026-09-02-v6"
PREVIOUS_PROGRAM_UID = "sym:ResearchProgram:hswm-graph-and-loop-engineering-2026-09-02-v5"
NONCLAIM = (
    "SECONDARY_AI_RESEARCH_SYNTHESIS_AND_BOUNDED_KG_PROJECTION_ONLY_NOT_HSWM_"
    "COGNITION_LEARNING_EFFICACY_CONSCIOUSNESS_PERSONHOOD_OR_SCALE_CLOSURE"
)
SOURCE_ACCESS_DATE = "2026-09-02"
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
SAFE_RELATION = re.compile(r"[A-Z_][A-Z0-9_]*\Z")

EXTERNAL_SOURCES = (
    (
        "rdf-11-concepts",
        "W3C RDF 1.1 Concepts and Abstract Syntax",
        "https://www.w3.org/TR/rdf11-concepts/",
        "STANDARD",
        "A standard RDF dataset model with one default graph and zero or more named graphs.",
        "That an RDF dataset is canonical HSWM state or cognition.",
    ),
    (
        "n-quads-11",
        "W3C N-Quads 1.1",
        "https://www.w3.org/TR/n-quads/",
        "STANDARD",
        "A line-oriented standard exchange syntax for RDF datasets.",
        "Canonical byte identity, signatures, truth, or write authority by itself.",
    ),
    (
        "n-quads-11-tests",
        "W3C RDF 1.1 N-Quads test suite",
        "https://w3c.github.io/rdf-tests/rdf/rdf11/rdf-n-quads/",
        "OFFICIAL_TEST_SUITE",
        "Approved positive and negative syntax fixtures for a pinned parser configuration.",
        "Universal parser correctness or HSWM emitter correctness beyond the tested corpus and profile.",
    ),
    (
        "rdfc-10",
        "W3C RDF Dataset Canonicalization 1.0",
        "https://www.w3.org/TR/rdf-canon/",
        "STANDARD",
        "Canonical N-Quads for graph-isomorphism-independent hashing, comparison, and downstream signing.",
        "A graph-signature scheme, denial-of-service immunity, or HSWM native-state identity.",
    ),
    (
        "rdfc-10-tests",
        "W3C RDFC-1.0 test suite",
        "https://w3c.github.io/rdf-canon/tests/",
        "OFFICIAL_TEST_SUITE",
        "Manifest-based canonicalization and canonical-map vectors for qualifying one pinned implementation.",
        "More than the tested RDFC aspects, executable-artifact identity, or application-level truth.",
    ),
    (
        "json-ld-11",
        "W3C JSON-LD 1.1",
        "https://www.w3.org/TR/json-ld/",
        "STANDARD",
        "Human- and API-oriented JSON serialization of RDF datasets.",
        "Stable bytes without a separate canonicalization contract or authority over the native journal.",
    ),
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
        "iso-gql-2024",
        "ISO/IEC 39075:2024 GQL",
        "https://www.iso.org/standard/76120.html",
        "STANDARD",
        "A portable language and data model for property-graph query implementations.",
        "Lossless HSWM n-ary semantics, causal meaning, or permission to replace the native plane.",
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
    (
        "flrh-graph-harness-profile",
        "Experimental FLRH graph and harness profile",
        "https://github.com/gj3447/agent-coding-paradigm/tree/000d5fd0d40518a700713e55e9167ca07a514189",
        "PROJECT_LOCAL_EXPERIMENTAL_PROFILE",
        "Project-neutral graph envelopes, deltas, receipts, reconciliation, and bounded harness lifecycle as an adapter target.",
        "An industry standard, cross-project runtime qualification, HSWM identity, or development-efficiency result.",
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
    (
        "controlled-mutation-entrypoint",
        "GE-2-controlled graph mutation entrypoint",
        "A public read/stage/snapshot graph view omits raw mutation; the standard GE-2 controller owns the externally composable graph-delta and restore entrypoints.",
        "MUTATION_BOUNDARY_CONTRACT",
    ),
    (
        "research-job-control",
        "LE-0 research subprocess job control",
        "A declared action command and separately identified verifier command produce content-addressed observations, bounded retry, stop, or escalation records without a shell.",
        "RESEARCH_JOB_LOOP_CONTRACT",
    ),
)

CURRENT_SURFACES = (
    (
        "canonical-rdf-projection",
        "Canonical atom v2 RDF projection",
        RDF_PROJECTION_PATH,
        "A self-consistent caller-bundle-bound manifest compiles validated canonical atom state into a deterministic blank-node-free RDF 1.1 N-Quads profile with reified typed references and fail-closed recompilation.",
        "READ_ONLY_LOCAL_DETERMINISTIC_PROFILE_NOT_RDFC_SHACL_PROV_CAUSAL_OR_COGNITIVE_CONFORMANCE",
    ),
    (
        "durable-rdf-projection",
        "Durable canonical atom v2 RDF projection envelope",
        DURABLE_RDF_PROJECTION_PATH,
        "One registered local durable-runtime recovery observation supplies the complete contiguous ordered journal prefix returned by that observation and semantic replay when bounded raw-journal recovery succeeds within its declared record and byte limits; an exact descriptor predecessor commitment binds the inner RDF projection and refuses stale or tampered artifacts after fresh recovery. Concurrent or deleted later tails and total referenced-content replay I/O, memory, and CPU are not attested.",
        "LOCAL_OBSERVED_PREFIX_RECOVERY_ATTESTATION_NOT_GLOBAL_TAIL_ANTIROLLBACK_RDFC_SHACL_PROV_CAUSAL_OR_COGNITIVE_CONFORMANCE",
    ),
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
    (
        "local-permit-commit",
        "Local Permit issuance and POSIX commit occurrence",
        LOCAL_PERMIT_COMMIT_PATH,
        "One bounded v1 Node path generates an ephemeral Ed25519 key, mints a random one-use nonce, checks caller-relative time, signs and verifies one Permit envelope, and publishes one no-replace local POSIX successor with process-crash recovery tests.",
        "BOUNDED_V1_LOCAL_OCCURRENCE_NOT_V2_CRASH_QUALIFICATION_PRODUCTION_AUTHORITY_TRUSTED_TIME_GLOBAL_NONCE_POWER_LOSS_OR_DISTRIBUTED_STORAGE_PROOF",
    ),
    (
        "graph-loop-controller",
        "GE-2 and LE-0 graph-loop engineering controller",
        GRAPH_LOOP_ENGINEERING_PATH,
        "A local create-only control journal records trigger, source-bound durable RDF snapshot, action, separately identified verifier outcome, delta intent, commit/reject/quarantine, retry, restore, stop, and escalation. The public standard layer exposes no raw durable submit and the controller alone reaches the internal GE-2 commit seam.",
        "LOCAL_RESEARCH_CONTROL_HARNESS_NOT_CANONICAL_HSWM_STATE_NOT_PERMIT_NOT_CAUSAL_CREDIT_OR_EFFICACY",
    ),
    (
        "graph-loop-public-boundary",
        "Public GE-2 mutation boundary",
        DURABLE_RUNTIME_PATH,
        "The published durable graph surface provides schema, stage/read, snapshot, and history without raw submit; the standard file-layer composition provides the graph-loop controller and graph view together.",
        "API_MODULE_BOUNDARY_NOT_HOSTILE_SAME_PROCESS_ISOLATION_CANONICAL_PERMIT_OR_DISTRIBUTED_AUTHORITY",
    ),
    (
        "research-job-runner",
        "LE-0 action and verifier subprocess runner",
        GRAPH_LOOP_RESEARCH_JOB_PATH,
        "A real bounded subprocess runner executes a no-shell action and separately identified verifier, content-addresses both observations, and records accept/retry/reject/escalate through LE-0. The companion process entrypoint constructs the protected file layer from canonical request input.",
        "LOCAL_ENGINEERING_COMMAND_CONTROL_NOT_PROOF_OF_FROZEN_INPUT_OUTCOME_TRUTH_VERIFIER_INDEPENDENCE_CAUSAL_CREDIT_OR_EFFICACY",
    ),
    (
        "frozen-dgx-job-profiles",
        "Future DGX Q1/MI/MI-2 LE-0 job profiles",
        LOOP_JOB_PROFILES_PATH,
        "A strict profile materializer binds Q1, MI, and MI-2 action/verifier module pairs, one-shot budgets, schema/grants, and declared frozen files into the standard no-shell job-process request without changing their hash-bound sources. The Q1 bridge invokes its independent reader in a distinct process.",
        "FUTURE_LAUNCH_LOCAL_PROFILE_INTEGRATION_NOT_A_RERUN_HISTORICAL_QUALIFICATION_UNIVERSAL_RUNNER_ADOPTION_OUTCOME_INDEPENDENCE_OR_CAUSAL_EFFICACY",
    ),
    (
        "diagnostic-mutation-internalization",
        "Local diagnostic mutation internalization",
        ROUTING_DIAGNOSTIC_FILE_PATH,
        "The local DNRD routing diagnostic no longer invokes raw runtime submit directly; it uses a named internal structural-only seam and is not promoted to GE-2 independent-outcome admission.",
        "LEGACY_LOCAL_DIAGNOSTIC_ONLY_NOT_STANDARD_RESEARCH_ADMISSION_OR_CAUSAL_EFFICACY",
    ),
)

GAPS = (
    (
        "projection-manifest",
        "Canonical-to-compiled projection portability gap",
        "The local v1 compiler binds a validated schema/state/tail bundle, and the durable envelope now recompiles it from the complete contiguous prefix returned by one replay-verified recovery observation, accepted within declared raw-journal record and byte limits, with an ordered exact-descriptor commitment. Total content-replay I/O/CPU, concurrent or deleted later tails, global anti-rollback, executable compiler identity, independent N-Quads/RDFC/SHACL qualification, and sparse/query adapters remain open.",
        "PARTIALLY_CLOSED_LOCAL_DURABLE_PREFIX_GE1_EXTERNAL_ANTIROLLBACK_AND_STANDARDS_OPEN",
    ),
    (
        "nary-delta-transaction",
        "Typed n-ary graph-delta transaction gap",
        "A local source-bound graph-delta controller now requires snapshot/read-set binding, separate verifier outcome, content-readable evidence descriptors, an explicit serializable CAS policy, durable intent, quarantine on stale/conflicting state, exact-payload restore, and a package-root boundary that withholds raw durable submit. Canonical Permit/Inv composition, hostile same-process isolation, semantic critical-pair analysis, distributed recovery, and behavioral restore remain open.",
        "PARTIALLY_CLOSED_LOCAL_GE2_MUTATION_BOUNDARY_NOT_CANONICAL_PERMIT_OR_CAUSAL_EFFICACY",
    ),
    (
        "integrated-loop-controller",
        "Integrated graph-and-loop controller gap",
        "A bounded local controller now persists trigger, graph snapshot, action, verifier verdict, delta disposition, retry, stop, escalation, and restore in one append-only research-control journal; the standard job runner executes declared action and verifier subprocesses without a shell. It does not prove outcome independence, issue Permit, generate a graph delta automatically, or turn a committed delta into a scientific disposition.",
        "PARTIALLY_CLOSED_LOCAL_LE0_JOB_ENGINEERING_NOT_INDEPENDENT_OUTCOME_OR_CAUSAL_EFFICACY",
    ),
    (
        "research-job-adoption",
        "Universal active-runner LE-0 adoption gap",
        "The standard job entrypoint now registers future Q1, MI, and MI-2 launches with exact role-separated module pairs, one-shot budgets, and frozen-input manifests. DNRD and other active research launchers still lack their own registered action/verifier wrapper, recovery procedure, and independent qualification. Hash-bound historical sources are intentionally preserved rather than rewritten.",
        "PARTIALLY_CLOSED_FROZEN_DGX_PROFILE_ADOPTION_FULL_ACTIVE_RUNNER_ADOPTION_UNQUALIFIED",
    ),
    (
        "causal-graph-efficacy",
        "Outcome-bound graph efficacy gap",
        "No current result establishes that a canonical graph delta, rather than matched retrieval, lesson, static workflow, sham, or shuffled credit, mediates fresh behavior.",
        "SCIENTIFICALLY_UNJUDGED",
    ),
    (
        "universal-source-refinement",
        "Universal TypeScript/Effect-to-Lean source refinement gap",
        "No verified TypeScript, Effect, Node crypto, canonical-byte, or POSIX semantics, proof-producing extraction, or full-program simulation theorem establishes that every in-scope runtime execution refines the Lean transition model.",
        "UNPROVED_CURRENT_PROFILE_OBSTRUCTED",
    ),
    (
        "authoritative-permit-storage",
        "Authoritative Permit and storage qualification gap",
        "The bounded local occurrence does not supply production key custody, authoritative monotonic time, globally atomic nonce consumption, power-loss qualification, anti-rollback, or distributed linearizability.",
        "LOCAL_OCCURRENCE_SUPPORTED_BROADER_AUTHORITY_AND_STORAGE_UNPROVED",
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
        "Typed delta transaction with conflict, quarantine, restore, concurrent-edit tests, and no public raw durable mutation export.",
        "A rejected or competing delta changes canonical state or recovery loses lineage.",
        "GRAPH_TRANSACTION_ENGINEERING_ONLY",
    ),
    (
        "le-0",
        "LE-0 loop-control qualification",
        "Record trigger, snapshot, budget, action, separately identified verifier, stop/retry/escalation, and all verdicts; declared commands may execute through the standard no-shell job runner.",
        "The loop can run unbounded, self-approve, erase a failed attempt, or silently change contract.",
        "LOOP_CONTROL_ENGINEERING_ONLY",
    ),
    (
        "le-1",
        "LE-1 active research-job adoption qualification",
        "Register each active launcher with exact action and verifier command identities, frozen-input binding, bounded budget, control-journal root, stop/retry/escalation policy, and recovery test before a new scientific occurrence. Q1, MI, and MI-2 profile materialization is present; remaining families remain required.",
        "An active job bypasses the standard entrypoint, has no separately identified verifier record, silently retries, or cannot recover its control-journal lineage.",
        "RESEARCH_RUNNER_ADOPTION_ENGINEERING_ONLY",
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

PROOF_STATUSES = (
    {
        "slug": "lean-model-theorems",
        "status_id": "PS-1",
        "name": "Lean model safety and conditional-composition theorems",
        "claim": (
            "The cited declared Lean models machine-check their internal safety, binding, "
            "non-entailment, and conditional-composition statements under their explicit premises."
        ),
        "assessment": (
            "Supported inside the declared formal models; this does not interpret TypeScript, "
            "cryptography, storage, external truth, causal identification, or a real LLM provider."
        ),
        "scope": "LEAN_DECLARED_MODEL",
        "implementation_status": "QUALIFIED",
        "implementation_boundary": "CITED_LEAN_MODELS_AND_DECLARED_PREMISES_ONLY",
        "evidence_disposition": "SUPPORTED_IN_SCOPE",
        "claim_ceiling": "FORMAL_MODEL_ONLY",
        "formal_status": "PROVED_UNDER_DECLARED_PREMISES",
        "summary_bucket": "FORMAL_MODEL_PROVED",
        "route_disposition": "ACTIVE_FORMAL_BOUNDARY",
        "falsifier": (
            "The checked-in Lean modules fail their declared build, acquire an undeclared "
            "axiom or placeholder, or no longer prove the recorded theorem boundary."
        ),
        "next_evidence": (
            "Preserve the formal build; runtime and scientific claims must close their "
            "separate proof-status obligations."
        ),
        "sources": (
            CANONICAL_LEARNING_LEAN_PATH,
            VERIFIED_ADMISSION_KERNEL_LEAN_PATH,
            END_TO_END_REFINEMENT_LEAN_PATH,
            CAUSAL_EFFICACY_BRIDGE_LEAN_PATH,
        ),
        "source_status": "SUPPORTS_DECLARED_FORMAL_SCOPE",
        "gap": None,
    },
    {
        "slug": "typescript-lean-local-boundary",
        "status_id": "PS-2",
        "name": "Tested TypeScript-to-Lean local wire and persisted-decision boundary",
        "claim": (
            "Strict wire vectors and one protected local v2 gateway path agree with the "
            "configured Lean admission decision and retain the exact request and response for recovery."
        ),
        "assessment": (
            "Bounded engineering evidence is present for the tested path; it is not a "
            "source-level theorem over all TypeScript or Effect executions."
        ),
        "scope": "TESTED_LOCAL_GATEWAY_PATH",
        "implementation_status": "IMPLEMENTED",
        "implementation_boundary": "TESTED_LOCAL_V2_GATEWAY_PATH_ONLY",
        "evidence_disposition": "SUPPORTED_IN_SCOPE",
        "claim_ceiling": "LOCAL_RUNTIME_ONLY",
        "formal_status": "ENGINEERING_EVIDENCE_NOT_UNIVERSAL_PROOF",
        "summary_bucket": "LOCAL_ENGINEERING_SUPPORTED",
        "route_disposition": "CONTINUE_WITH_STRONGER_ADAPTER_QUALIFICATION",
        "falsifier": (
            "A canonical fixed or adversarial vector disagrees across the boundary, or fresh "
            "recovery accepts a persisted decision whose exact request or response no longer validates."
        ),
        "next_evidence": (
            "Pin executable identity, audit an actual recovered v2 receipt into a complete "
            "certificate, and independently qualify the cross-language boundary."
        ),
        "sources": (
            TYPESCRIPT_LEAN_STATUS_PATH,
            ADMISSION_PATH,
            VERIFIED_ADMISSION_GATEWAY_PATH,
            VERIFIED_ADMISSION_GATEWAY_TEST_PATH,
            VERIFIED_ADMISSION_KERNEL_LEAN_PATH,
        ),
        "source_status": "SUPPORTS_BOUNDED_ENGINEERING_SCOPE",
        "gap": "universal-source-refinement",
    },
    {
        "slug": "universal-typescript-lean-refinement",
        "status_id": "PS-3",
        "name": "Universal TypeScript/Effect-to-Lean refinement",
        "claim": (
            "Every in-scope TypeScript/Effect runtime execution simulates the declared Lean "
            "transition and atomic-learning relations."
        ),
        "assessment": (
            "Unproved. Conditional Lean bridges and tested vectors do not supply a semantics "
            "or extraction theorem, and the recorded current profile has explicit blockers."
        ),
        "scope": "FULL_SOURCE_AND_RUNTIME_SEMANTICS",
        "implementation_status": "PARTIAL",
        "evidence_disposition": "UNDERDETERMINED",
        "claim_ceiling": "NO_UNIVERSAL_REFINEMENT_CLAIM",
        "implementation_boundary": "BOUNDARY_AND_OBSTRUCTION_ARTIFACTS_ONLY",
        "formal_status": "UNPROVED_CURRENT_PROFILE_OBSTRUCTED",
        "summary_bucket": "CORE_UNPROVED",
        "route_disposition": "CURRENT_PROFILE_BLOCKED_TARGET_RETAINED",
        "falsifier": (
            "One admitted in-scope runtime trace cannot be simulated by the Lean relation, "
            "or a supposedly protected path bypasses an obligation required by that relation."
        ),
        "next_evidence": (
            "Choose a verified source semantics, proof-producing extraction, or auditable "
            "simulation route and prove it for an explicitly bounded runtime surface."
        ),
        "sources": (
            TYPESCRIPT_LEAN_STATUS_PATH,
            END_TO_END_REFINEMENT_PATH,
            END_TO_END_REFINEMENT_LEAN_PATH,
        ),
        "source_status": "DOCUMENTS_UNPROVED_AND_OBSTRUCTED_BOUNDARY",
        "gap": "universal-source-refinement",
    },
    {
        "slug": "local-permit-posix-occurrence",
        "status_id": "PS-4",
        "name": "Local key, time, nonce, Permit, atomic publication, and recovery occurrence",
        "claim": (
            "One bounded v1 local Node/POSIX path actually issues and verifies a Permit with an "
            "ephemeral key, caller-relative time and a one-use nonce, then publishes and recovers one successor."
        ),
        "assessment": (
            "Supported in the tested v1 local process-crash scope. This is not v2 persisted-"
            "decision crash qualification; production authority, power-loss, global nonce, "
            "anti-rollback, and distributed-storage claims remain unproved."
        ),
        "scope": "LOCAL_NODE_POSIX_PROCESS_CRASH",
        "implementation_status": "IMPLEMENTED",
        "implementation_boundary": "V1_LOCAL_PERMIT_COMMIT_NAMESPACE_ONLY",
        "evidence_disposition": "SUPPORTED_IN_SCOPE",
        "claim_ceiling": "LOCAL_RUNTIME_ONLY",
        "formal_status": "BOUNDED_LOCAL_OCCURRENCE_NOT_PRODUCTION_PROOF",
        "summary_bucket": "LOCAL_ENGINEERING_SUPPORTED",
        "route_disposition": "RETAIN_LOCAL_SLICE_QUALIFY_BEFORE_EXPANSION",
        "falsifier": (
            "Replay, stale head, forged or expired Permit, duplicate nonce, interrupted publish, "
            "or competing writer yields an accepted invalid or non-linear recovered successor."
        ),
        "next_evidence": (
            "Add v2-specific SIGKILL checkpoints, then qualify durable key custody, trusted time, "
            "cross-store nonce atomicity, power loss, anti-rollback, and the intended deployment "
            "filesystem or distributed backend."
        ),
        "sources": (
            TYPESCRIPT_LEAN_STATUS_PATH,
            LOCAL_PERMIT_COMMIT_PATH,
            LOCAL_PERMIT_COMMIT_TEST_PATH,
            LOCAL_PERMIT_COMMIT_CRASH_TEST_PATH,
        ),
        "source_status": "SUPPORTS_BOUNDED_LOCAL_OCCURRENCE",
        "gap": "authoritative-permit-storage",
    },
    {
        "slug": "outcome-truth-causal-credit",
        "status_id": "PS-5",
        "name": "External outcome truth and independent causal credit",
        "claim": (
            "The outcome consumed by an admitted revision is externally true and the exact "
            "revision receives independently identified causal credit."
        ),
        "assessment": (
            "Not established. Lean states conditional premises and non-entailment boundaries, "
            "but no qualifying external truth, evaluator-independence, or causal-identification occurrence inhabits them."
        ),
        "scope": "REAL_WORLD_OUTCOME_AND_CAUSAL_IDENTIFICATION",
        "implementation_status": "PARTIAL",
        "implementation_boundary": "PROTOCOL_AND_CONDITIONAL_BRIDGE_ONLY",
        "evidence_disposition": "NOT_EVALUATED",
        "claim_ceiling": "CAUSAL_CLAIM_PENDING",
        "formal_status": "REAL_WORLD_PREMISES_UNINHABITED",
        "summary_bucket": "CORE_UNPROVED",
        "route_disposition": "G0_NOT_PASSED_G1_NOT_EVALUATED",
        "falsifier": (
            "Outcome provenance, evaluator independence, sham, delayed-credit, shuffled-credit, "
            "remove or restore control, or independent replay fails the frozen identification contract."
        ),
        "next_evidence": (
            "Run a pre-registered externally operated occurrence with sealed outcomes, separate "
            "evaluator and judge, frozen controls, complete custody, and independent replay."
        ),
        "sources": (
            TYPESCRIPT_LEAN_STATUS_PATH,
            END_TO_END_REFINEMENT_PATH,
            CAUSAL_EFFICACY_BRIDGE_PATH,
            CAUSAL_EFFICACY_BRIDGE_LEAN_PATH,
            CAUSAL_PROGRAM_PATH,
        ),
        "source_status": "DOCUMENTS_CONDITIONAL_PREMISES_AND_MISSING_OCCURRENCE",
        "gap": "causal-graph-efficacy",
    },
    {
        "slug": "revision-real-llm-efficacy",
        "status_id": "PS-6",
        "name": "Revision-caused improvement in real LLM behavior",
        "claim": (
            "The exact admitted HSWM revision causes a reproducible improvement in fresh real-LLM "
            "behavior under a frozen evaluation and loses and recovers that effect under controls."
        ),
        "assessment": (
            "Not established. Exploratory provider calls are baseline-saturated or confounded; "
            "there is no passed G0/G1 confirmatory occurrence or independent causal terminal."
        ),
        "scope": "CONFIRMATORY_REAL_LLM_CAUSAL_EFFICACY",
        "implementation_status": "PARTIAL",
        "implementation_boundary": "PROTOCOL_BRIDGE_AND_EXPLORATORY_RUNS_ONLY",
        "evidence_disposition": "NOT_EVALUATED",
        "claim_ceiling": "INTEGRATED_CLAIM_UNJUDGED",
        "formal_status": "NO_CONFIRMATORY_OCCURRENCE",
        "summary_bucket": "CORE_UNPROVED",
        "route_disposition": "G0_NOT_PASSED_G1_NOT_EVALUATED",
        "falsifier": (
            "Matched retrieval, static lesson, sham, position bias, shuffled or delayed credit, "
            "fixed graph, evaluator leakage, or failure of remove/restore explains the gain."
        ),
        "next_evidence": (
            "Close G0, then execute G1 or the frozen DNRD-5 route with fresh held-out probes, "
            "remove/restore controls, independent evaluation, uncertainty, and reproducibility."
        ),
        "sources": (
            TYPESCRIPT_LEAN_STATUS_PATH,
            CAUSAL_EFFICACY_BRIDGE_PATH,
            CAUSAL_EFFICACY_BRIDGE_LEAN_PATH,
            CAUSAL_PROGRAM_PATH,
        ),
        "source_status": "DOCUMENTS_EXPLORATORY_ONLY_AND_MISSING_CONFIRMATION",
        "gap": "causal-graph-efficacy",
    },
)

QUALIFICATION_RUNS = (
    {
        "slug": "lean-formal-build",
        "run_id": "QR-1",
        "name": "Lean formal boundary build qualification",
        "scope": "CITED_LEAN_BOUNDARIES_AND_FORMAL_PROJECT_BUILD",
        "commands": [
            "cd formal && lake build",
            "cd formal && lake env lean HSWMCanonicalLearning.lean",
            "cd formal && lake env lean HSWMVerifiedAdmissionKernel.lean",
            "cd formal && lake env lean HSWMEndToEndRuntimeRefinement.lean",
            "cd formal && lake env lean HSWMCausalEfficacyBridge.lean",
        ],
        "environment": (
            "Lean 4.32.1 f054605aea4b840552cca2e725580bffd1e1b704; "
            "Lake 5.0.0-src+f054605; linux-x86_64"
        ),
        "result": "REPORTED_PASS",
        "result_summary": (
            "lake build completed 35 jobs; all four cited modules also compiled directly "
            "with no diagnostics"
        ),
        "input_closure": "SELECTED_DIRECT_SOURCES_AND_PROJECT_CONFIG_NOT_FULL_TRANSITIVE_CLOSURE",
        "qualified_claims": ("lean-model-theorems",),
        "sources": (
            FORMAL_LAKEFILE_PATH,
            LEAN_TOOLCHAIN_PATH,
            CANONICAL_LEARNING_LEAN_PATH,
            VERIFIED_ADMISSION_KERNEL_LEAN_PATH,
            END_TO_END_REFINEMENT_LEAN_PATH,
            CAUSAL_EFFICACY_BRIDGE_LEAN_PATH,
        ),
        "limitation": (
            "Local reproducibility run over the recorded worktree; no independent attestation "
            "and no interpretation of foreign runtime or real-world premises."
        ),
    },
    {
        "slug": "typescript-local-boundaries",
        "run_id": "QR-2",
        "name": "TypeScript local gateway and Permit occurrence qualification",
        "scope": "TARGETED_LOCAL_V1_AND_V2_TESTS_PLUS_PACKAGE_TYPECHECK",
        "commands": [
            "cd src/hswm/effect-runtime && npm run check",
            (
                "cd src/hswm/effect-runtime && npm test -- "
                "canonical-atom-v2-verified-admission-gateway-v2.test.ts "
                "canonical-atom-v2-local-permit-commit.test.ts "
                "canonical-atom-v2-local-permit-commit-process-crash.test.ts"
            ),
        ],
        "environment": (
            "Node 24.13.0; npm 11.6.2; TypeScript 5.9.3; Vitest 3.2.7; "
            "linux-x64"
        ),
        "result": "REPORTED_PASS",
        "result_summary": "tsc --noEmit passed; 3 test files and 12 tests passed",
        "input_closure": "SELECTED_DIRECT_SOURCES_AND_PACKAGE_LOCK_NOT_FULL_TRANSITIVE_CLOSURE",
        "qualified_claims": (
            "typescript-lean-local-boundary",
            "local-permit-posix-occurrence",
        ),
        "sources": (
            EFFECT_PACKAGE_PATH,
            EFFECT_PACKAGE_LOCK_PATH,
            VERIFIED_ADMISSION_GATEWAY_PATH,
            VERIFIED_ADMISSION_GATEWAY_TEST_PATH,
            LOCAL_PERMIT_COMMIT_PATH,
            LOCAL_PERMIT_COMMIT_TEST_PATH,
            LOCAL_PERMIT_COMMIT_CRASH_TEST_PATH,
        ),
        "limitation": (
            "The v2 gateway tests persist and revalidate the Lean decision; the SIGKILL tests "
            "qualify only the separate v1 local Permit-commit namespace. This run is not v2 "
            "crash, power-loss, production-authority, or universal-refinement evidence."
        ),
    },
    {
        "slug": "proof-status-projection",
        "run_id": "QR-3",
        "name": "Proof-status projection reproducibility qualification",
        "scope": "V6_DETERMINISTIC_BUILD_GRAPH_SHAPE_AND_PORTABLE_MARKDOWN",
        "commands": [
            "uv run python scripts/build_hswm_graph_and_loop_engineering_ontology.py --check",
            "uv run pytest -q tests/test_hswm_graph_and_loop_engineering_ontology.py",
            (
                "uv run python scripts/compile_portable_markdown_math.py README.md "
                "INDEX.md docs/canon docs/research ontology"
            ),
            "git diff --check",
        ],
        "environment": "Python 3.12.13; pytest 9.1.1; linux-x86_64",
        "result": "REPORTED_PASS",
        "result_summary": (
            "deterministic v6 matched; ontology test passed; portable Markdown compiled; "
            "Git whitespace check passed"
        ),
        "input_closure": "DETERMINISTIC_BUILDER_CHECKS_ALL_DECLARED_V6_SOURCE_BINDINGS",
        "qualified_claims": (),
        "sources": (
            ONTOLOGY_BUILDER_PATH,
            ONTOLOGY_TEST_PATH,
            PORTABLE_MATH_COMPILER_PATH,
            PROOF_STATUS_PATH,
            SYNTHESIS_PATH,
        ),
        "limitation": (
            "This qualifies projection reproducibility and shape only; it is not evidence that "
            "HSWM cognition, causal learning, or scientific efficacy occurred."
        ),
    },
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
        "name": "HSWM graph and loop engineering reinforcement program [2026-09-02-v5]",
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


def _proof_claim_uid(slug: str) -> str:
    return f"sym:Concept:hswm-proof-status-claim-{slug}-{UID_RELEASE}"


def _proof_decision_uid(slug: str) -> str:
    return f"sym:Concept:hswm-proof-status-decision-{slug}-{UID_RELEASE}"


def _qualification_run_uid(slug: str) -> str:
    return f"sym:AbstractNode:hswm-qualification-run-{slug}-{UID_RELEASE}"


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
                    "loop engineering, current repository surfaces, partial local "
                    "engineering closures, proof-status claims, decisions, gaps, and "
                    "research gates."
                ),
                scope="BOUNDED_RESEARCH_PROJECTION",
                kind="ARTIFACT",
                plane="INQUIRY",
                state="LOCAL_ENGINEERING_IMPLEMENTATION_SCIENTIFICALLY_UNJUDGED",
                owner="graph_loop_ontology_projection_custodian",
                roles=[
                    "RESEARCH_BUNDLE",
                    "GRAPH_ENGINEERING",
                    "LOOP_ENGINEERING",
                    "CLAIM_EVIDENCE_GAP_STATUS",
                ],
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
                    "without changing HSWM target identity or claim ceilings; local "
                    "GE-2/LE-0 engineering is present but remains unqualified as efficacy."
                ),
                scope="SECONDARY_AI_RESEARCH_PATH",
                kind="PLAN",
                plane="INQUIRY",
                state="LOCAL_ENGINEERING_IMPLEMENTATION_WITH_OPEN_RESEARCH_GATES",
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

    proof_evidence_paths = {
        path for item in PROOF_STATUSES for path in item["sources"]
    }
    qualification_source_paths = {
        path for item in QUALIFICATION_RUNS for path in item["sources"]
    }
    evidence_artifact_paths = proof_evidence_paths | qualification_source_paths

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
                    "standard_graph_role": (
                        "EVIDENCE_ARTIFACT"
                        if path in evidence_artifact_paths
                        else "SOURCE_RECORD"
                    ),
                    "evidence_boundary": (
                        "SOURCE_BYTES_AND_PROVENANCE_ONLY_UNLESS_A_QUALIFICATION_RUN_CITES_THIS_ARTIFACT"
                        if path in evidence_artifact_paths
                        else "SOURCE_BYTES_AND_PROVENANCE_ONLY"
                    ),
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

    for item in PROOF_STATUSES:
        slug = item["slug"]
        status_id = item["status_id"]
        nodes.append(
            _node(
                _proof_claim_uid(slug),
                ["Concept"],
                {
                    **_common(
                        name=item["name"],
                        description=item["claim"],
                        scope=item["scope"],
                        kind="CLAIM",
                        plane="INQUIRY",
                        state="TRACKED_WITH_SEPARATE_CURRENT_DECISION",
                        owner=f"proof_status_claim_{slug.replace('-', '_')}_custodian",
                        roles=["PROOF_OBLIGATION", "CLAIM"],
                        boundary=(
                            "This node names one fixed cross-cutting obligation. Its "
                            "separate status decision and cited sources do not expand the claim."
                        ),
                    ),
                    "proof_status_id": status_id,
                    "claim_text": item["claim"],
                    "falsifier": item["falsifier"],
                    "next_evidence": item["next_evidence"],
                    "current_decision_uid": _proof_decision_uid(slug),
                    "open_gap_uid": (
                        "" if item["gap"] is None else _gap_uid(item["gap"])
                    ),
                    "evidence_source_uids": [
                        _local_source_uid(path) for path in item["sources"]
                    ],
                    "standard_graph_role": "CLAIM",
                },
            )
        )
        nodes.append(
            _node(
                _proof_decision_uid(slug),
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{item['name']} current decision",
                        description=item["assessment"],
                        scope="STATUS_AS_OF_2026_09_02",
                        kind="DECISION",
                        plane="EVIDENCE",
                        state=item["summary_bucket"],
                        owner="proof_status_assessment_custodian",
                        roles=["STATUS_DECISION", "CLAIM_CEILING_GUARDRAIL"],
                        boundary=(
                            "The decision is valid only for the named scope and cited "
                            "source snapshot; it is not a broader scientific terminal."
                        ),
                    ),
                    "proof_status_id": status_id,
                    "assessed_on": "2026-09-02",
                    "implementation_status": item["implementation_status"],
                    "implementation_boundary": item["implementation_boundary"],
                    "evidence_disposition": item["evidence_disposition"],
                    "claim_ceiling": item["claim_ceiling"],
                    "formal_status": item["formal_status"],
                    "summary_bucket": item["summary_bucket"],
                    "route_disposition": item["route_disposition"],
                    "assesses_claim_uid": _proof_claim_uid(slug),
                    "decision_relation_semantics": "CURRENT_STATUS_DECISION",
                    "standard_graph_role": "DECISION",
                },
            )
        )

    for item in QUALIFICATION_RUNS:
        nodes.append(
            _node(
                _qualification_run_uid(item["slug"]),
                ["AbstractNode", "ResearchArtifact"],
                {
                    **_common(
                        name=item["name"],
                        description=item["result_summary"],
                        scope=item["scope"],
                        kind="QUALIFICATION_RUN",
                        plane="EVIDENCE",
                        state="LOCAL_RUN_REPORTED_PASS_NOT_INDEPENDENTLY_QUALIFIED",
                        owner="proof_status_qualification_run_custodian",
                        roles=["QUALIFICATION_RUN", "SELF_ATTESTED_LOCAL_RUN_RECORD"],
                        boundary=item["limitation"],
                        authority="SECONDARY_AI_SELF_ATTESTED_LOCAL_RUN",
                    ),
                    "qualification_run_id": item["run_id"],
                    "executed_on": "2026-09-02",
                    "commands": item["commands"],
                    "environment": item["environment"],
                    "result": item["result"],
                    "result_summary": item["result_summary"],
                    "input_closure": item["input_closure"],
                    "raw_log_status": "NOT_PERSISTED",
                    "attestation_level": "SELF_ATTESTED_LOCAL_ONLY",
                    "qualification_status": "NOT_INDEPENDENTLY_QUALIFIED",
                    "evidence_ceiling": "LOCAL_REPRODUCIBILITY_STATUS_ONLY",
                    "source_snapshot": "V6_CONTENT_HASH_BINDINGS",
                    "qualified_claim_uids": [
                        _proof_claim_uid(slug)
                        for slug in item["qualified_claims"]
                    ],
                    "evidence_source_uids": [
                        _local_source_uid(path) for path in item["sources"]
                    ],
                    "standard_graph_role": "QUALIFICATION_RUN",
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
    for item in PROOF_STATUSES:
        claim_uid = _proof_claim_uid(item["slug"])
        decision_uid = _proof_decision_uid(item["slug"])
        relations.extend(
            (
                _relation(
                    PROGRAM_UID,
                    "HAS_CONCEPT",
                    claim_uid,
                    "PROOF_STATUS_CLAIM",
                    "ACTIVE",
                ),
                _relation(
                    claim_uid,
                    "HAS_CONCEPT",
                    decision_uid,
                    "CURRENT_STATUS_DECISION",
                    "ASSESSED_2026_09_02",
                ),
                _relation(
                    decision_uid,
                    "CONSTRAINS",
                    claim_uid,
                    "CLAIM_CEILING_AND_SCOPE",
                    item["evidence_disposition"],
                ),
                _relation(
                    claim_uid,
                    "CONSTRAINS",
                    "sym:Concept:hswm",
                    "TARGET_CLAIM_BOUNDARY",
                    "ACTIVE",
                ),
            )
        )
        for source_path in item["sources"]:
            relations.append(
                _relation(
                    claim_uid,
                    "HAS_SOURCE",
                    _local_source_uid(source_path),
                    "CLAIM_EVIDENCE_SOURCE",
                    item["source_status"],
                )
            )
        if item["gap"] is not None:
            relations.append(
                _relation(
                    claim_uid,
                    "TARGETS",
                    _gap_uid(item["gap"]),
                    "OPEN_CLAIM_GAP",
                    "OPEN",
                )
            )
    for item in QUALIFICATION_RUNS:
        run_uid = _qualification_run_uid(item["slug"])
        relations.append(
            _relation(
                PROGRAM_UID,
                "HAS_CONCEPT",
                run_uid,
                "QUALIFICATION_RUN",
                "REPORTED_PASS_NOT_ATTESTED",
            )
        )
        for source_path in item["sources"]:
            relations.append(
                _relation(
                    run_uid,
                    "HAS_SOURCE",
                    _local_source_uid(source_path),
                    "QUALIFICATION_INPUT_SNAPSHOT",
                    "BOUND",
                )
            )
        tested_uids = [
            _proof_claim_uid(slug) for slug in item["qualified_claims"]
        ] or [BUNDLE_UID]
        for tested_uid in tested_uids:
            relations.append(
                _relation(
                    run_uid,
                    "TESTS",
                    tested_uid,
                    "LOCAL_REPRODUCIBILITY_QUALIFICATION",
                    "REPORTED_PASS_NOT_ATTESTED",
                )
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
                "NON_OVERWRITING_STATUS_FOLLOWUP_WITHOUT_SCIENTIFIC_PROMOTION",
                "ACTIVE",
            ),
        )
    )
    relations.extend(
        (
            _relation(
                _current_surface_uid("graph-loop-controller"),
                "REALIZES",
                _gate_uid("ge-2"),
                "LOCAL_ENGINEERING_IMPLEMENTATION",
                "IMPLEMENTED_LOCAL_NOT_INDEPENDENTLY_QUALIFIED",
            ),
            _relation(
                _current_surface_uid("graph-loop-controller"),
                "REALIZES",
                _gate_uid("le-0"),
                "LOCAL_ENGINEERING_IMPLEMENTATION",
                "IMPLEMENTED_LOCAL_NOT_INDEPENDENTLY_QUALIFIED",
            ),
            _relation(
                _current_surface_uid("graph-loop-public-boundary"),
                "REALIZES",
                _gate_uid("ge-2"),
                "PUBLIC_MUTATION_ENTRYPOINT_ENFORCEMENT",
                "IMPLEMENTED_LOCAL_NOT_INDEPENDENTLY_QUALIFIED",
            ),
            _relation(
                _current_surface_uid("research-job-runner"),
                "REALIZES",
                _gate_uid("le-0"),
                "DECLARED_SUBPROCESS_LOOP_CONTROL",
                "IMPLEMENTED_LOCAL_NOT_INDEPENDENTLY_QUALIFIED",
            ),
            _relation(
                _current_surface_uid("research-job-runner"),
                "TARGETS",
                _gate_uid("le-1"),
                "ACTIVE_RUNNER_ADOPTION_PATH",
                "PROPOSED",
            ),
            _relation(
                _current_surface_uid("frozen-dgx-job-profiles"),
                "TARGETS",
                _gate_uid("le-1"),
                "PARTIAL_ACTIVE_RUNNER_REGISTRATION",
                "IMPLEMENTED_LOCAL_NOT_INDEPENDENTLY_QUALIFIED",
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
        "proof_claims": len(PROOF_STATUSES),
        "proof_decisions": len(PROOF_STATUSES),
        "qualification_runs": len(QUALIFICATION_RUNS),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_uid": BUNDLE_UID,
        "status": "LOCAL_ENGINEERING_IMPLEMENTATION_SCIENTIFICALLY_UNJUDGED",
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

    status_ids = [item["status_id"] for item in PROOF_STATUSES]
    status_slugs = [item["slug"] for item in PROOF_STATUSES]
    if status_ids != [f"PS-{index}" for index in range(1, 7)]:
        raise ValueError("proof-status obligation identity drifted")
    if len(status_slugs) != len(set(status_slugs)):
        raise ValueError("duplicate proof-status obligation slug")
    if Counter(item["summary_bucket"] for item in PROOF_STATUSES) != Counter(
        {
            "FORMAL_MODEL_PROVED": 1,
            "LOCAL_ENGINEERING_SUPPORTED": 2,
            "CORE_UNPROVED": 3,
        }
    ):
        raise ValueError("proof-status summary buckets drifted")
    allowed_implementation = {"NOT_STARTED", "PARTIAL", "IMPLEMENTED", "QUALIFIED"}
    allowed_disposition = {
        "NOT_EVALUATED",
        "SUPPORTED_IN_SCOPE",
        "RED",
        "UNDERDETERMINED",
    }
    for item in PROOF_STATUSES:
        if item["implementation_status"] not in allowed_implementation:
            raise ValueError(f"invalid implementation status: {item['status_id']}")
        if item["evidence_disposition"] not in allowed_disposition:
            raise ValueError(f"invalid evidence disposition: {item['status_id']}")
        if any(path not in SOURCE_BINDING_PATHS for path in item["sources"]):
            raise ValueError(f"unbound proof-status source: {item['status_id']}")
        if item["gap"] is not None and item["gap"] not in {
            gap[0] for gap in GAPS
        }:
            raise ValueError(f"unknown proof-status gap: {item['status_id']}")

    run_ids = [item["run_id"] for item in QUALIFICATION_RUNS]
    run_slugs = [item["slug"] for item in QUALIFICATION_RUNS]
    if run_ids != [f"QR-{index}" for index in range(1, 4)]:
        raise ValueError("qualification-run identity drifted")
    if len(run_slugs) != len(set(run_slugs)):
        raise ValueError("duplicate qualification-run slug")
    proof_slugs = set(status_slugs)
    for item in QUALIFICATION_RUNS:
        if item["result"] != "REPORTED_PASS" or not item["commands"]:
            raise ValueError(f"invalid qualification run: {item['run_id']}")
        if set(item["qualified_claims"]) - proof_slugs:
            raise ValueError(f"unknown qualified claim: {item['run_id']}")
        if any(path not in SOURCE_BINDING_PATHS for path in item["sources"]):
            raise ValueError(f"unbound qualification source: {item['run_id']}")

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
